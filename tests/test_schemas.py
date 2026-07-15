"""Tests for the versioned replay wire schemas."""

import json

import pytest

from worm_world.experiments import ExperimentConfig
from worm_world.schemas import (
    CODE_REVISION_UNAVAILABLE,
    ReplayManifest,
    SimulationEvent,
    WorldSnapshot,
)


def test_event_serialization_is_canonical_and_round_trips() -> None:
    """Event bytes are stable and sufficient to reconstruct the record."""
    event = SimulationEvent(
        step_index=3,
        sequence=1,
        event_type="world.tick",
        data={"active": True, "count": 0},
    )
    expected = (
        '{"data":{"active":true,"count":0},"event_type":"world.tick",'
        '"schema_version":1,"sequence":1,"step_index":3}'
    )
    assert event.to_json() == expected
    assert SimulationEvent.from_json(expected) == event


def test_snapshot_serialization_is_canonical_and_round_trips() -> None:
    """Snapshot state retains fixed-step timing and arbitrary JSON state."""
    snapshot = WorldSnapshot(step_index=2, elapsed_seconds=0.1, state={"entities": []})
    assert WorldSnapshot.from_json(snapshot.to_json()) == snapshot


def test_manifest_serialization_is_canonical_and_round_trips() -> None:
    """A manifest binds config, seed, revision, lockfile, and replay integrity."""
    config = ExperimentConfig(seed=42)
    manifest = ReplayManifest(
        config_id=config.config_id,
        config_json=config.to_json(),
        master_seed=config.seed,
        code_revision=CODE_REVISION_UNAVAILABLE,
        dependency_lock_sha256="a" * 64,
        event_hash="b" * 64,
        event_count=2,
        snapshot_count=1,
        final_step=10,
    )
    serialized = manifest.to_json()
    assert serialized == json.dumps(
        manifest.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    assert ReplayManifest.from_json(serialized) == manifest


@pytest.mark.parametrize(
    ("record", "loader"),
    [
        (SimulationEvent(0, 0, "run.started").to_json(), SimulationEvent.from_json),
        (WorldSnapshot(0, 0.0).to_json(), WorldSnapshot.from_json),
    ],
)
def test_unknown_fields_are_rejected(record: str, loader: object) -> None:
    """Schema typos and unversioned extensions cannot silently enter a replay."""
    decoded = json.loads(record)
    decoded["unexpected"] = True
    with pytest.raises(ValueError, match="unknown"):
        loader(json.dumps(decoded))  # type: ignore[operator]


def test_incompatible_versions_are_rejected() -> None:
    """Readers fail explicitly when they cannot interpret a schema version."""
    decoded = json.loads(SimulationEvent(0, 0, "run.started").to_json())
    decoded["schema_version"] = 2
    with pytest.raises(ValueError, match="unsupported event schema version"):
        SimulationEvent.from_json(json.dumps(decoded))


def test_manifest_rejects_configuration_identity_mismatch() -> None:
    """A replay cannot claim metadata belonging to a different configuration."""
    config = ExperimentConfig(seed=1)
    with pytest.raises(ValueError, match="config_id does not match"):
        ReplayManifest(
            config_id="0" * 64,
            config_json=config.to_json(),
            master_seed=1,
            code_revision=CODE_REVISION_UNAVAILABLE,
            dependency_lock_sha256="a" * 64,
            event_hash="b" * 64,
            event_count=0,
            snapshot_count=0,
            final_step=0,
        )
