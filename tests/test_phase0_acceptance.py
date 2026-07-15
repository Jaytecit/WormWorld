"""End-to-end acceptance gate for Phase 0."""

import hashlib
from pathlib import Path

from worm_world.experiments import ExperimentConfig, run_noop_experiment
from worm_world.schemas import (
    CODE_REVISION_UNAVAILABLE,
    EVENT_SCHEMA_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    ReplayManifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_phase0_noop_run_emits_complete_reproducible_manifest(tmp_path: Path) -> None:
    """All Phase 0 reproducibility inputs and integrity outputs are retained."""
    config = ExperimentConfig(seed=42)
    artifacts = run_noop_experiment(
        config,
        step_count=1_000,
        artifact_directory=tmp_path / "acceptance",
        project_root=PROJECT_ROOT,
    )

    assert {path.name for path in artifacts.directory.iterdir()} == {
        "config.json",
        "events.jsonl",
        "manifest.json",
        "snapshots.jsonl",
    }
    manifest = ReplayManifest.from_json(artifacts.manifest_path.read_text(encoding="utf-8"))
    assert manifest.config_json == config.to_json()
    assert manifest.config_id == config.config_id
    assert manifest.master_seed == 42
    assert manifest.code_revision
    if not (PROJECT_ROOT / ".git").exists():
        assert manifest.code_revision == CODE_REVISION_UNAVAILABLE
    assert (
        manifest.dependency_lock_sha256
        == hashlib.sha256((PROJECT_ROOT / "uv.lock").read_bytes()).hexdigest()
    )
    assert manifest.event_schema_version == EVENT_SCHEMA_VERSION
    assert manifest.snapshot_schema_version == SNAPSHOT_SCHEMA_VERSION
    assert manifest.event_hash == hashlib.sha256(artifacts.events_path.read_bytes()).hexdigest()
    assert manifest.event_count == 2
    assert manifest.snapshot_count == 2
    assert manifest.final_step == 1_000
