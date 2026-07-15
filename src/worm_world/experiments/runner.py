"""Headless experiment execution and deterministic replay artifact writing."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from worm_world.experiments.config import ExperimentConfig
from worm_world.schemas import (
    CODE_REVISION_UNAVAILABLE,
    ReplayManifest,
    SimulationEvent,
    WorldSnapshot,
)
from worm_world.world import NoOpWorld


@dataclass(frozen=True, slots=True)
class ReplayArtifacts:
    """Paths and validated records emitted by a completed headless run."""

    directory: Path
    manifest: ReplayManifest
    events: tuple[SimulationEvent, ...]
    snapshots: tuple[WorldSnapshot, ...]

    @property
    def manifest_path(self) -> Path:
        return self.directory / "manifest.json"

    @property
    def events_path(self) -> Path:
        return self.directory / "events.jsonl"

    @property
    def snapshots_path(self) -> Path:
        return self.directory / "snapshots.jsonl"


def _sha256_file(path: Path) -> str:
    """Hash a required experiment input without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _code_revision(project_root: Path) -> str:
    """Return the Git commit and dirty state, or an explicit unavailable marker."""
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        return CODE_REVISION_UNAVAILABLE
    return f"{revision}+dirty" if dirty else revision


def _json_lines(records: tuple[SimulationEvent, ...] | tuple[WorldSnapshot, ...]) -> bytes:
    """Encode canonical records with a terminal newline for stable file hashing."""
    return ("".join(f"{record.to_json()}\n" for record in records)).encode("utf-8")


def run_noop_experiment(
    config: ExperimentConfig,
    *,
    step_count: int,
    artifact_directory: Path,
    project_root: Path,
) -> ReplayArtifacts:
    """Run the Phase 0 no-op world and write a complete deterministic replay."""
    if isinstance(step_count, bool) or step_count < 0:
        raise ValueError("step_count must be a non-negative integer")
    lockfile = project_root / "uv.lock"
    if not lockfile.is_file():
        raise FileNotFoundError(f"required dependency lockfile not found: {lockfile}")

    world = NoOpWorld(config.world)
    snapshots = (world.snapshot(),)
    start = SimulationEvent(
        step_index=0,
        sequence=0,
        event_type="run.started",
        data={"config_id": config.config_id, "master_seed": config.seed},
    )
    for _ in range(step_count):
        world.advance()
    complete = SimulationEvent(
        step_index=world.step_index,
        sequence=1,
        event_type="run.completed",
        data={"final_step": world.step_index},
    )
    events = (start, complete)
    snapshots += (world.snapshot(),)
    event_bytes = _json_lines(events)
    snapshot_bytes = _json_lines(snapshots)

    manifest = ReplayManifest(
        config_id=config.config_id,
        config_json=config.to_json(),
        master_seed=config.seed,
        code_revision=_code_revision(project_root),
        dependency_lock_sha256=_sha256_file(lockfile),
        event_hash=hashlib.sha256(event_bytes).hexdigest(),
        event_count=len(events),
        snapshot_count=len(snapshots),
        final_step=world.step_index,
    )

    artifact_directory.mkdir(parents=True, exist_ok=False)
    (artifact_directory / "config.json").write_text(config.to_json() + "\n", encoding="utf-8")
    (artifact_directory / "events.jsonl").write_bytes(event_bytes)
    (artifact_directory / "snapshots.jsonl").write_bytes(snapshot_bytes)
    (artifact_directory / "manifest.json").write_text(manifest.to_json() + "\n", encoding="utf-8")
    return ReplayArtifacts(
        directory=artifact_directory,
        manifest=manifest,
        events=events,
        snapshots=snapshots,
    )
