"""Replay tests for complete Phase 1 action-sequence experiments."""

from pathlib import Path

import pytest

from worm_world.experiments import (
    SandboxExperimentConfig,
    run_sandbox_experiment,
    simulate_sandbox,
    verify_sandbox_replay,
)
from worm_world.organisms import WormAction

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_sandbox_configuration_is_canonical_and_round_trips() -> None:
    config = SandboxExperimentConfig(
        seed=7,
        actions=(WormAction(forward=1.0), WormAction(eat=True)),
    )

    assert SandboxExperimentConfig.from_json(config.to_json()) == config
    assert SandboxExperimentConfig.from_json(config.to_json()).config_id == config.config_id


def test_identical_inputs_replay_to_identical_bytes(tmp_path: Path) -> None:
    config = SandboxExperimentConfig(
        seed=42,
        actions=tuple([WormAction(forward=1.0)] * 10 + [WormAction(eat=True)] * 3),
    )
    first = run_sandbox_experiment(
        config, artifact_directory=tmp_path / "first", project_root=PROJECT_ROOT
    )
    second = run_sandbox_experiment(
        config, artifact_directory=tmp_path / "second", project_root=PROJECT_ROOT
    )

    assert first.manifest == second.manifest
    assert first.events_path.read_bytes() == second.events_path.read_bytes()
    assert first.snapshots_path.read_bytes() == second.snapshots_path.read_bytes()
    assert verify_sandbox_replay(first.directory) == first.manifest


def test_changed_actions_change_movement_consumption_and_replay_identity(tmp_path: Path) -> None:
    idle = run_sandbox_experiment(
        SandboxExperimentConfig(seed=1, actions=(WormAction(),)),
        artifact_directory=tmp_path / "idle",
        project_root=PROJECT_ROOT,
    )
    moving = run_sandbox_experiment(
        SandboxExperimentConfig(seed=1, actions=(WormAction(forward=1.0),)),
        artifact_directory=tmp_path / "moving",
        project_root=PROJECT_ROOT,
    )

    assert idle.manifest.config_id != moving.manifest.config_id
    assert idle.manifest.event_hash != moving.manifest.event_hash
    assert idle.snapshots[-1].state["organism"] != moving.snapshots[-1].state["organism"]


def test_replay_verifier_detects_tampered_event_bytes(tmp_path: Path) -> None:
    artifacts = run_sandbox_experiment(
        SandboxExperimentConfig(seed=1, actions=(WormAction(),)),
        artifact_directory=tmp_path / "run",
        project_root=PROJECT_ROOT,
    )
    artifacts.events_path.write_bytes(artifacts.events_path.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="event replay diverged"):
        verify_sandbox_replay(artifacts.directory)


def test_death_event_occurs_exactly_once() -> None:
    from worm_world.organisms import PhysiologyConfig
    from worm_world.world import InitialOrganismConfig

    config = SandboxExperimentConfig(
        seed=3,
        actions=(WormAction(), WormAction(), WormAction()),
        physiology=PhysiologyConfig(
            basal_energy_rate=1.0,
            basal_hydration_rate=0.0,
            movement_energy_rate=0.0,
        ),
        initial_organism=InitialOrganismConfig(energy=0.1, hydration=10.0),
    )
    events, _ = simulate_sandbox(config)

    assert [event.event_type for event in events].count("organism.died") == 1
