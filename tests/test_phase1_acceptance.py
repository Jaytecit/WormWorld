"""End-to-end acceptance gate for Phase 1."""

import hashlib
from pathlib import Path

from worm_world.experiments import (
    SandboxExperimentConfig,
    run_sandbox_experiment,
    verify_sandbox_replay,
)
from worm_world.organisms import WormAction

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_phase1_survival_run_passes_replay_and_lifecycle_gate(tmp_path: Path) -> None:
    actions = tuple(
        [WormAction(forward=1.0)] * 20
        + [WormAction(eat=True)] * 5
        + [WormAction(forward=-1.0)] * 40
        + [WormAction(drink=True)] * 5
    )
    config = SandboxExperimentConfig(seed=42, actions=actions)
    artifacts = run_sandbox_experiment(
        config,
        artifact_directory=tmp_path / "phase1",
        project_root=PROJECT_ROOT,
    )
    manifest = verify_sandbox_replay(artifacts.directory)
    final_state = artifacts.snapshots[-1].state
    organism = final_state["organism"]
    resources = final_state["resources"]

    assert isinstance(organism, dict)
    assert isinstance(resources, dict)
    assert organism["alive"] is True
    food = resources["food"]
    water = resources["water"]
    assert isinstance(food, dict)
    assert isinstance(water, dict)
    food_amount = food["amount"]
    water_amount = water["amount"]
    assert isinstance(food_amount, float)
    assert isinstance(water_amount, float)
    assert food_amount < config.resources.food_energy
    assert water_amount < config.resources.water_amount
    assert manifest.final_step == len(actions)
    assert manifest.snapshot_count == len(actions) + 1
    assert manifest.event_hash == hashlib.sha256(artifacts.events_path.read_bytes()).hexdigest()
