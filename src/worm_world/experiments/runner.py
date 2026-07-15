"""Headless experiment execution and deterministic replay artifact writing."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from worm_world.experiments.config import ExperimentConfig
from worm_world.experiments.sandbox_config import SandboxExperimentConfig
from worm_world.schemas import (
    CODE_REVISION_UNAVAILABLE,
    ReplayManifest,
    SimulationEvent,
    WorldSnapshot,
)
from worm_world.world import NoOpWorld, SandboxWorld


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


def simulate_sandbox(
    config: SandboxExperimentConfig,
) -> tuple[tuple[SimulationEvent, ...], tuple[WorldSnapshot, ...]]:
    """Execute the authoritative sandbox without filesystem side effects."""
    world = SandboxWorld(
        config.world,
        config.body,
        config.physiology,
        config.resources,
        config.initial_organism,
    )
    events: list[SimulationEvent] = [
        SimulationEvent(
            step_index=0,
            sequence=0,
            event_type="run.started",
            data={"config_id": config.config_id, "master_seed": config.seed},
        )
    ]
    snapshots = [world.snapshot()]
    sequence = 1
    for action in config.actions:
        result = world.advance(action)
        events.append(
            SimulationEvent(
                step_index=world.step_index,
                sequence=sequence,
                event_type="organism.step",
                data={"action": action.to_dict(), "outcome": result.to_dict()},
            )
        )
        sequence += 1
        if result.death_transition:
            events.append(
                SimulationEvent(
                    step_index=world.step_index,
                    sequence=sequence,
                    event_type="organism.died",
                    data={
                        "age_seconds": world.organism.physiology.age_seconds,
                        "energy": world.organism.physiology.energy,
                        "hydration": world.organism.physiology.hydration,
                        "injury": world.organism.physiology.injury,
                    },
                )
            )
            sequence += 1
        snapshots.append(world.snapshot())
    events.append(
        SimulationEvent(
            step_index=world.step_index,
            sequence=sequence,
            event_type="run.completed",
            data={
                "alive": world.organism.physiology.alive,
                "final_step": world.step_index,
            },
        )
    )
    return tuple(events), tuple(snapshots)


def run_sandbox_experiment(
    config: SandboxExperimentConfig,
    *,
    artifact_directory: Path,
    project_root: Path,
) -> ReplayArtifacts:
    """Run Phase 1 and write a complete replay bound to its action sequence."""
    lockfile = project_root / "uv.lock"
    if not lockfile.is_file():
        raise FileNotFoundError(f"required dependency lockfile not found: {lockfile}")
    events, snapshots = simulate_sandbox(config)
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
        final_step=len(config.actions),
    )
    artifact_directory.mkdir(parents=True, exist_ok=False)
    (artifact_directory / "config.json").write_text(config.to_json() + "\n", encoding="utf-8")
    (artifact_directory / "events.jsonl").write_bytes(event_bytes)
    (artifact_directory / "snapshots.jsonl").write_bytes(snapshot_bytes)
    (artifact_directory / "manifest.json").write_text(manifest.to_json() + "\n", encoding="utf-8")
    return ReplayArtifacts(artifact_directory, manifest, events, snapshots)


def verify_sandbox_replay(artifact_directory: Path) -> ReplayManifest:
    """Re-simulate stored inputs and reject any event or snapshot divergence."""
    manifest = ReplayManifest.from_json(
        (artifact_directory / "manifest.json").read_text(encoding="utf-8")
    )
    config_text = (artifact_directory / "config.json").read_text(encoding="utf-8").rstrip("\n")
    config = SandboxExperimentConfig.from_json(config_text)
    if config.to_json() != manifest.config_json:
        raise ValueError("stored config does not match replay manifest")
    events, snapshots = simulate_sandbox(config)
    event_bytes = _json_lines(events)
    snapshot_bytes = _json_lines(snapshots)
    if event_bytes != (artifact_directory / "events.jsonl").read_bytes():
        raise ValueError("event replay diverged from stored bytes")
    if snapshot_bytes != (artifact_directory / "snapshots.jsonl").read_bytes():
        raise ValueError("snapshot replay diverged from stored bytes")
    if hashlib.sha256(event_bytes).hexdigest() != manifest.event_hash:
        raise ValueError("event hash does not match replay manifest")
    if (len(events), len(snapshots), len(config.actions)) != (
        manifest.event_count,
        manifest.snapshot_count,
        manifest.final_step,
    ):
        raise ValueError("replay counts do not match manifest")
    return manifest
