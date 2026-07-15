"""Tests for deterministic no-op replay artifact generation."""

import hashlib
from pathlib import Path

from worm_world.experiments import ExperimentConfig, WorldConfig, run_noop_experiment
from worm_world.schemas import CODE_REVISION_UNAVAILABLE, ReplayManifest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_identical_inputs_create_identical_replay_identity(tmp_path: Path) -> None:
    """Repeated runs produce byte-identical records and manifest contents."""
    config = ExperimentConfig(seed=2025)
    first = run_noop_experiment(
        config, step_count=12, artifact_directory=tmp_path / "first", project_root=PROJECT_ROOT
    )
    second = run_noop_experiment(
        config, step_count=12, artifact_directory=tmp_path / "second", project_root=PROJECT_ROOT
    )

    assert first.manifest == second.manifest
    assert first.events_path.read_bytes() == second.events_path.read_bytes()
    assert first.snapshots_path.read_bytes() == second.snapshots_path.read_bytes()
    assert ReplayManifest.from_json(first.manifest_path.read_text(encoding="utf-8")) == (
        first.manifest
    )
    assert hashlib.sha256(first.events_path.read_bytes()).hexdigest() == first.manifest.event_hash
    assert first.manifest.code_revision
    if not (PROJECT_ROOT / ".git").exists():
        assert first.manifest.code_revision == CODE_REVISION_UNAVAILABLE


def test_changed_seed_changes_config_and_event_identity(tmp_path: Path) -> None:
    """A seed is a first-class replay input even in the no-op bootstrap world."""
    first = run_noop_experiment(
        ExperimentConfig(seed=1),
        step_count=2,
        artifact_directory=tmp_path / "seed-1",
        project_root=PROJECT_ROOT,
    )
    second = run_noop_experiment(
        ExperimentConfig(seed=2),
        step_count=2,
        artifact_directory=tmp_path / "seed-2",
        project_root=PROJECT_ROOT,
    )

    assert first.manifest.config_id != second.manifest.config_id
    assert first.manifest.event_hash != second.manifest.event_hash


def test_changed_world_configuration_changes_replay_identity(tmp_path: Path) -> None:
    """World configuration participates in both config and event identities."""
    first = run_noop_experiment(
        ExperimentConfig(seed=7),
        step_count=2,
        artifact_directory=tmp_path / "default",
        project_root=PROJECT_ROOT,
    )
    second = run_noop_experiment(
        ExperimentConfig(seed=7, world=WorldConfig(width_meters=250.0)),
        step_count=2,
        artifact_directory=tmp_path / "wide",
        project_root=PROJECT_ROOT,
    )

    assert first.manifest.config_id != second.manifest.config_id
    assert first.manifest.event_hash != second.manifest.event_hash
