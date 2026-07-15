"""Versioned wire schemas for events, snapshots, and replay manifests."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import cast

from worm_world.experiments.config import ExperimentConfig

EVENT_SCHEMA_VERSION = 1
SNAPSHOT_SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1
CODE_REVISION_UNAVAILABLE = "unavailable:not-a-git-repository"

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]


def _empty_json_object() -> dict[str, JsonValue]:
    """Create a correctly typed empty object for schema defaults."""
    return {}


def _canonical_json(value: dict[str, JsonValue]) -> str:
    """Encode a schema value using the project's deterministic JSON representation."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _decode_object(serialized: str, expected: set[str], schema_name: str) -> dict[str, JsonValue]:
    """Decode a JSON object and enforce an exact top-level field set."""
    decoded: object = json.loads(serialized)
    if not isinstance(decoded, dict):
        raise ValueError(f"{schema_name} must be a JSON object")
    values = cast(dict[str, JsonValue], decoded)
    fields = set(values)
    unknown = fields - expected
    missing = expected - fields
    if unknown:
        raise ValueError(f"unknown {schema_name} fields: {sorted(unknown)}")
    if missing:
        raise ValueError(f"missing {schema_name} fields: {sorted(missing)}")
    return values


def _require_int(value: JsonValue, name: str, *, minimum: int = 0) -> int:
    """Narrow a JSON value to a bounded integer, excluding booleans."""
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer greater than or equal to {minimum}")
    return value


def _require_string(value: JsonValue, name: str, *, allow_empty: bool = False) -> str:
    """Narrow a JSON value to a string with an optional non-empty constraint."""
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _require_object(value: JsonValue, name: str) -> dict[str, JsonValue]:
    """Narrow a JSON value to an object."""
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def _require_version(value: JsonValue, expected: int, schema_name: str) -> int:
    """Reject schema versions the current implementation cannot interpret."""
    version = _require_int(value, "schema_version", minimum=1)
    if version != expected:
        raise ValueError(f"unsupported {schema_name} schema version {version}; expected {expected}")
    return version


def _is_sha256(value: str) -> bool:
    """Return whether a string is a lowercase SHA-256 hexadecimal digest."""
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    """One ordered fact emitted by the authoritative simulation."""

    step_index: int
    sequence: int
    event_type: str
    data: dict[str, JsonValue] = field(default_factory=_empty_json_object)
    schema_version: int = EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.step_index < 0 or self.sequence < 0:
            raise ValueError("event indices must be non-negative")
        if not self.event_type:
            raise ValueError("event_type must not be empty")
        _canonical_json(self.to_dict())

    def to_dict(self) -> dict[str, JsonValue]:
        """Return the event's versioned wire representation."""
        return {
            "data": self.data,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "sequence": self.sequence,
            "step_index": self.step_index,
        }

    def to_json(self) -> str:
        """Serialize the event to canonical JSON."""
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, serialized: str) -> SimulationEvent:
        """Deserialize an event using strict schema compatibility."""
        values = _decode_object(
            serialized,
            {"data", "event_type", "schema_version", "sequence", "step_index"},
            "event",
        )
        return cls(
            step_index=_require_int(values["step_index"], "step_index"),
            sequence=_require_int(values["sequence"], "sequence"),
            event_type=_require_string(values["event_type"], "event_type"),
            data=_require_object(values["data"], "data"),
            schema_version=_require_version(
                values["schema_version"], EVENT_SCHEMA_VERSION, "event"
            ),
        )


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    """Replayable world state captured at a fixed simulation step."""

    step_index: int
    elapsed_seconds: float
    state: dict[str, JsonValue] = field(default_factory=_empty_json_object)
    schema_version: int = SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.step_index < 0:
            raise ValueError("step_index must be non-negative")
        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0.0:
            raise ValueError("elapsed_seconds must be finite and non-negative")
        _canonical_json(self.to_dict())

    def to_dict(self) -> dict[str, JsonValue]:
        """Return the snapshot's versioned wire representation."""
        return {
            "elapsed_seconds": self.elapsed_seconds,
            "schema_version": self.schema_version,
            "state": self.state,
            "step_index": self.step_index,
        }

    def to_json(self) -> str:
        """Serialize the snapshot to canonical JSON."""
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, serialized: str) -> WorldSnapshot:
        """Deserialize a snapshot using strict schema compatibility."""
        values = _decode_object(
            serialized,
            {"elapsed_seconds", "schema_version", "state", "step_index"},
            "snapshot",
        )
        elapsed = values["elapsed_seconds"]
        if isinstance(elapsed, bool) or not isinstance(elapsed, int | float):
            raise ValueError("elapsed_seconds must be a number")
        return cls(
            step_index=_require_int(values["step_index"], "step_index"),
            elapsed_seconds=float(elapsed),
            state=_require_object(values["state"], "state"),
            schema_version=_require_version(
                values["schema_version"], SNAPSHOT_SCHEMA_VERSION, "snapshot"
            ),
        )


@dataclass(frozen=True, slots=True)
class ReplayManifest:
    """Complete identity and integrity metadata for a headless replay."""

    config_id: str
    config_json: str
    master_seed: int
    code_revision: str
    dependency_lock_sha256: str
    event_hash: str
    event_count: int
    snapshot_count: int
    final_step: int
    event_schema_version: int = EVENT_SCHEMA_VERSION
    snapshot_schema_version: int = SNAPSHOT_SCHEMA_VERSION
    schema_version: int = MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        config = ExperimentConfig.from_json(self.config_json)
        if config.config_id != self.config_id:
            raise ValueError("config_id does not match config_json")
        if config.seed != self.master_seed:
            raise ValueError("master_seed does not match the serialized configuration")
        if not self.code_revision:
            raise ValueError("code_revision must be explicit")
        for name, digest in (
            ("dependency_lock_sha256", self.dependency_lock_sha256),
            ("event_hash", self.event_hash),
        ):
            if not _is_sha256(digest):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        if min(self.event_count, self.snapshot_count, self.final_step) < 0:
            raise ValueError("manifest counts and final_step must be non-negative")
        if self.event_schema_version != EVENT_SCHEMA_VERSION:
            raise ValueError("unsupported event schema version in manifest")
        if self.snapshot_schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("unsupported snapshot schema version in manifest")
        if self.schema_version != MANIFEST_SCHEMA_VERSION:
            raise ValueError("unsupported replay manifest schema version")

    def to_dict(self) -> dict[str, JsonValue]:
        """Return the manifest's versioned wire representation."""
        return {
            "code_revision": self.code_revision,
            "config_id": self.config_id,
            "config_json": self.config_json,
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "event_count": self.event_count,
            "event_hash": self.event_hash,
            "event_schema_version": self.event_schema_version,
            "final_step": self.final_step,
            "master_seed": self.master_seed,
            "schema_version": self.schema_version,
            "snapshot_count": self.snapshot_count,
            "snapshot_schema_version": self.snapshot_schema_version,
        }

    def to_json(self) -> str:
        """Serialize the replay manifest to canonical JSON."""
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, serialized: str) -> ReplayManifest:
        """Deserialize a replay manifest using strict schema compatibility."""
        expected = {
            "code_revision",
            "config_id",
            "config_json",
            "dependency_lock_sha256",
            "event_count",
            "event_hash",
            "event_schema_version",
            "final_step",
            "master_seed",
            "schema_version",
            "snapshot_count",
            "snapshot_schema_version",
        }
        values = _decode_object(serialized, expected, "replay manifest")
        return cls(
            config_id=_require_string(values["config_id"], "config_id"),
            config_json=_require_string(values["config_json"], "config_json"),
            master_seed=_require_int(values["master_seed"], "master_seed"),
            code_revision=_require_string(values["code_revision"], "code_revision"),
            dependency_lock_sha256=_require_string(
                values["dependency_lock_sha256"], "dependency_lock_sha256"
            ),
            event_hash=_require_string(values["event_hash"], "event_hash"),
            event_count=_require_int(values["event_count"], "event_count"),
            snapshot_count=_require_int(values["snapshot_count"], "snapshot_count"),
            final_step=_require_int(values["final_step"], "final_step"),
            event_schema_version=_require_int(
                values["event_schema_version"], "event_schema_version", minimum=1
            ),
            snapshot_schema_version=_require_int(
                values["snapshot_schema_version"], "snapshot_schema_version", minimum=1
            ),
            schema_version=_require_version(
                values["schema_version"], MANIFEST_SCHEMA_VERSION, "replay manifest"
            ),
        )
