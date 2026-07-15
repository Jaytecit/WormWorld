import json
from pathlib import Path

import pytest

from worm_world.experiments import (
    EvolutionExperimentConfig,
    run_evolution_experiment,
    run_phase2_acceptance_suite,
    simulate_evolution,
    verify_evolution_replay,
)

PROJECT_ROOT = Path(__file__).parents[1]


def test_evolution_config_round_trip_and_control_identity() -> None:
    config = EvolutionExperimentConfig(seed=44, heritability_enabled=False, step_count=3)
    restored = EvolutionExperimentConfig.from_json(config.to_json())
    assert restored == config
    assert restored.config_id == config.config_id
    changed = EvolutionExperimentConfig(seed=44, heritability_enabled=True, step_count=3)
    assert changed.config_id != config.config_id
    with pytest.raises(ValueError, match="missing or unknown"):
        EvolutionExperimentConfig.from_json('{"seed":44}')


def test_evolution_simulation_is_deterministic_and_sequences_are_unique() -> None:
    config = EvolutionExperimentConfig(seed=5, heritability_enabled=True, step_count=25)
    first = simulate_evolution(config)
    second = simulate_evolution(config)
    assert [event.to_json() for event in first.events] == [
        event.to_json() for event in second.events
    ]
    assert [snapshot.to_json() for snapshot in first.snapshots] == [
        snapshot.to_json() for snapshot in second.snapshots
    ]
    sequences = [event.sequence for event in first.events]
    assert sequences == list(range(len(sequences)))


def test_evolution_artifact_replays_byte_for_byte(tmp_path: Path) -> None:
    directory = tmp_path / "run"
    config = EvolutionExperimentConfig(seed=8, heritability_enabled=True, step_count=30)
    manifest = run_evolution_experiment(
        config, artifact_directory=directory, project_root=PROJECT_ROOT
    )
    assert verify_evolution_replay(directory) == manifest
    assert json.loads((directory / "report.json").read_text())["seed"] == 8


def test_phase2_multi_seed_gate_passes_with_matched_control(tmp_path: Path) -> None:
    summary = run_phase2_acceptance_suite(
        (11, 22, 33), artifact_directory=tmp_path / "suite", project_root=PROJECT_ROOT
    )
    assert summary["acceptance_passed"] is True
    heritable = summary["heritable_reports"]
    controls = summary["control_reports"]
    assert isinstance(heritable, list) and isinstance(controls, list)
    assert len(heritable) == len(controls) == 3
