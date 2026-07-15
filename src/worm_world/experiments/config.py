"""Versioned, canonical configuration for reproducible experiments."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Self, cast

CONFIG_SCHEMA_VERSION = 1
MAX_SEED = (1 << 64) - 1


@dataclass(frozen=True, slots=True)
class WorldConfig:
    """Static dimensions and timing for a headless 2.5D world."""

    width_meters: float = 100.0
    height_meters: float = 100.0
    timestep_seconds: float = 0.05

    def __post_init__(self) -> None:
        """Reject world parameters that cannot define a finite simulation."""
        for name, value in (
            ("width_meters", self.width_meters),
            ("height_meters", self.height_meters),
            ("timestep_seconds", self.timestep_seconds),
        ):
            if not 0.0 < value < float("inf"):
                raise ValueError(f"{name} must be finite and greater than zero")

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> Self:
        """Create a world configuration while rejecting unknown fields."""
        expected = {"width_meters", "height_meters", "timestep_seconds"}
        unknown = values.keys() - expected
        if unknown:
            raise ValueError(f"unknown world configuration fields: {sorted(unknown)}")
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """Complete versioned input configuration for one experiment run."""

    seed: int
    world: WorldConfig = field(default_factory=WorldConfig)
    schema_version: int = CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Validate values that participate in replay identity."""
        if isinstance(self.seed, bool) or not 0 <= self.seed <= MAX_SEED:
            raise ValueError(f"seed must be an integer from 0 to {MAX_SEED}")
        if self.schema_version != CONFIG_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported configuration schema version {self.schema_version}; "
                f"expected {CONFIG_SCHEMA_VERSION}"
            )

    def to_json(self) -> str:
        """Serialize to compact canonical JSON suitable for hashing and storage."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def config_id(self) -> str:
        """Return a content-derived identifier for the canonical configuration."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, serialized: str) -> Self:
        """Deserialize canonical JSON, validating its version and field names."""
        decoded: object = json.loads(serialized)
        if not isinstance(decoded, dict):
            raise ValueError("experiment configuration must be a JSON object")
        raw = cast(dict[str, object], decoded)

        expected = {"seed", "world", "schema_version"}
        unknown = raw.keys() - expected
        if unknown:
            raise ValueError(f"unknown experiment configuration fields: {sorted(unknown)}")
        missing = expected - raw.keys()
        if missing:
            raise ValueError(f"missing experiment configuration fields: {sorted(missing)}")

        world_values = raw["world"]
        if not isinstance(world_values, dict):
            raise ValueError("world must be a JSON object")
        seed = raw["seed"]
        schema_version = raw["schema_version"]
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("seed must be an integer")
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            raise ValueError("schema_version must be an integer")

        world = WorldConfig.from_dict(cast(dict[str, Any], world_values))
        return cls(seed=seed, world=world, schema_version=schema_version)
