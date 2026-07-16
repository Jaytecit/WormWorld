"""Deterministic detritus pool that recycles dead biomass into plant nutrients."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Self, cast

from worm_world.schemas import JsonValue

DETRITUS_POOL_SCHEMA_VERSION = 1
DETRITUS_POOL_TYPE = "organism_detritus_pool"


@dataclass(frozen=True, slots=True)
class DetritusConfig:
    """Complete, canonical inputs for one optional detritus pool.

    Physical biomass of a newly dead organism is defined as its remaining
    physiological energy at the death transition. ``death_biomass_fraction`` of
    that value enters this pool exactly once; the unrecovered remainder is
    recorded as energy dissipated.
    """

    enabled: bool = False
    initial_detritus: float = 0.0
    death_biomass_fraction: float = 1.0
    maximum_decay_rate: float = 1.0
    nutrients_per_detritus: float = 1.0
    pool_type: str = DETRITUS_POOL_TYPE
    schema_version: int = DETRITUS_POOL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("enabled must be a boolean")
        for name in ("initial_detritus", "maximum_decay_rate"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if (
            isinstance(self.death_biomass_fraction, bool)
            or not math.isfinite(self.death_biomass_fraction)
            or not 0.0 <= self.death_biomass_fraction <= 1.0
        ):
            raise ValueError("death_biomass_fraction must be finite and in [0, 1]")
        if (
            isinstance(self.nutrients_per_detritus, bool)
            or not math.isfinite(self.nutrients_per_detritus)
            or self.nutrients_per_detritus <= 0.0
        ):
            raise ValueError("nutrients_per_detritus must be finite and positive")
        if self.pool_type != DETRITUS_POOL_TYPE:
            raise ValueError(f"pool_type must be {DETRITUS_POOL_TYPE!r}")
        if self.schema_version != DETRITUS_POOL_SCHEMA_VERSION:
            raise ValueError("unsupported detritus pool schema version")

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def config_id(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, serialized: str) -> Self:
        decoded: object = json.loads(serialized)
        if not isinstance(decoded, dict):
            raise ValueError("detritus configuration must be a JSON object")
        raw = cast(dict[str, Any], decoded)
        expected = set(cls.__dataclass_fields__)
        if set(raw) != expected:
            raise ValueError("detritus configuration has missing or unknown fields")
        return cls(**raw)


@dataclass(frozen=True, slots=True)
class DetritusDecay:
    """Auditable transfers made during one fixed detritus-decay step."""

    detritus_before: float
    decay_loss: float
    nutrients_returned: float


@dataclass(frozen=True, slots=True)
class DetritusTransfer:
    """Auditable death-to-detritus transfer for one organism."""

    physical_biomass: float
    biomass_transferred: float
    energy_unrecovered: float


class DetritusPool:
    """Mutable authoritative state for one configured detritus pool."""

    def __init__(self, config: DetritusConfig) -> None:
        if not config.enabled:
            raise ValueError("cannot construct a disabled detritus pool")
        self.config = config
        self.detritus: float = config.initial_detritus
        self.total_biomass_transferred: float = 0.0
        self.total_decay_loss: float = 0.0
        self.total_nutrients_returned: float = 0.0

    def transfer_from_death(self, physical_biomass: float) -> DetritusTransfer:
        """Move the configured fraction of one death's physical biomass into the pool."""
        if (
            isinstance(physical_biomass, bool)
            or not math.isfinite(physical_biomass)
            or physical_biomass < 0.0
        ):
            raise ValueError("physical biomass must be finite and non-negative")
        transferred = physical_biomass * self.config.death_biomass_fraction
        unrecovered = physical_biomass - transferred
        self.detritus += transferred
        self.total_biomass_transferred += transferred
        return DetritusTransfer(physical_biomass, transferred, unrecovered)

    def decay(self, timestep_seconds: float) -> DetritusDecay:
        """Convert bounded detritus into plant-nutrient return units."""
        if not math.isfinite(timestep_seconds) or timestep_seconds < 0.0:
            raise ValueError("timestep_seconds must be finite and non-negative")
        before = self.detritus
        decay_loss = min(self.config.maximum_decay_rate * timestep_seconds, before)
        nutrients_returned = decay_loss * self.config.nutrients_per_detritus
        self.detritus -= decay_loss
        self.total_decay_loss += decay_loss
        self.total_nutrients_returned += nutrients_returned
        return DetritusDecay(before, decay_loss, nutrients_returned)

    def state_dict(self) -> dict[str, JsonValue]:
        return {
            "config_id": self.config.config_id,
            "detritus": self.detritus,
            "total_biomass_transferred": self.total_biomass_transferred,
            "total_decay_loss": self.total_decay_loss,
            "total_nutrients_returned": self.total_nutrients_returned,
        }
