"""Deterministic resource-limited plant biomass owned by the world."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Self, cast

from worm_world.schemas import JsonValue

PLANT_PATCH_SCHEMA_VERSION = 1
PLANT_PATCH_TYPE = "resource_limited_plant_patch"


@dataclass(frozen=True, slots=True)
class PlantPatchConfig:
    """Complete, canonical inputs for one optional plant patch."""

    enabled: bool = False
    x: float = 6.0
    y: float = 5.0
    initial_biomass_energy: float = 0.0
    maximum_biomass_energy: float = 100.0
    initial_light_energy: float = 0.0
    initial_water: float = 0.0
    initial_nutrients: float = 0.0
    maximum_growth_rate: float = 1.0
    light_per_biomass: float = 1.0
    water_per_biomass: float = 1.0
    nutrients_per_biomass: float = 1.0
    patch_type: str = PLANT_PATCH_TYPE
    schema_version: int = PLANT_PATCH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("enabled must be a boolean")
        non_negative = (
            "x",
            "y",
            "initial_biomass_energy",
            "maximum_biomass_energy",
            "initial_light_energy",
            "initial_water",
            "initial_nutrients",
            "maximum_growth_rate",
        )
        for name in non_negative:
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        for name in ("light_per_biomass", "water_per_biomass", "nutrients_per_biomass"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if self.initial_biomass_energy > self.maximum_biomass_energy:
            raise ValueError("initial biomass must not exceed maximum biomass")
        if self.patch_type != PLANT_PATCH_TYPE:
            raise ValueError(f"patch_type must be {PLANT_PATCH_TYPE!r}")
        if self.schema_version != PLANT_PATCH_SCHEMA_VERSION:
            raise ValueError("unsupported plant patch schema version")

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def config_id(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, serialized: str) -> Self:
        decoded: object = json.loads(serialized)
        if not isinstance(decoded, dict):
            raise ValueError("plant patch configuration must be a JSON object")
        raw = cast(dict[str, Any], decoded)
        expected = set(cls.__dataclass_fields__)
        if set(raw) != expected:
            raise ValueError("plant patch configuration has missing or unknown fields")
        return cls(**raw)


@dataclass(frozen=True, slots=True)
class PlantGrowth:
    """Auditable transfers made during one fixed plant-growth step."""

    biomass_before: float
    biomass_grown: float
    light_used: float
    water_used: float
    nutrients_used: float


class PlantPatch:
    """Mutable authoritative state for one configured plant patch."""

    def __init__(
        self, config: PlantPatchConfig, *, world_width: float, world_height: float
    ) -> None:
        if not config.enabled:
            raise ValueError("cannot construct a disabled plant patch")
        if config.x > world_width or config.y > world_height:
            raise ValueError("plant patch must be inside the world")
        self.config = config
        self.biomass_energy: float = config.initial_biomass_energy
        self.light_energy: float = config.initial_light_energy
        self.water: float = config.initial_water
        self.nutrients: float = config.initial_nutrients
        self.total_biomass_grown: float = 0.0
        self.total_biomass_consumed: float = 0.0

    def grow(self, timestep_seconds: float) -> PlantGrowth:
        """Convert explicitly deducted inputs into bounded edible biomass."""
        before = self.biomass_energy
        capacity = max(0.0, self.config.maximum_biomass_energy - before)
        grown = min(
            self.config.maximum_growth_rate * timestep_seconds,
            capacity,
            self.light_energy / self.config.light_per_biomass,
            self.water / self.config.water_per_biomass,
            self.nutrients / self.config.nutrients_per_biomass,
        )
        light_used = grown * self.config.light_per_biomass
        water_used = grown * self.config.water_per_biomass
        nutrients_used = grown * self.config.nutrients_per_biomass
        self.biomass_energy += grown
        self.light_energy -= light_used
        self.water -= water_used
        self.nutrients -= nutrients_used
        self.total_biomass_grown += grown
        return PlantGrowth(before, grown, light_used, water_used, nutrients_used)

    def consume(self, amount: float) -> None:
        if not math.isfinite(amount) or amount < 0.0 or amount > self.biomass_energy + 1e-12:
            raise ValueError("plant consumption must be finite and within available biomass")
        self.biomass_energy = max(0.0, self.biomass_energy - amount)
        self.total_biomass_consumed += amount

    def receive_nutrients(self, amount: float) -> None:
        if not math.isfinite(amount) or amount < 0.0:
            raise ValueError("nutrient return must be finite and non-negative")
        self.nutrients += amount

    def state_dict(self) -> dict[str, JsonValue]:
        return {
            "biomass_energy": self.biomass_energy,
            "config_id": self.config.config_id,
            "light_energy": self.light_energy,
            "nutrients": self.nutrients,
            "total_biomass_consumed": self.total_biomass_consumed,
            "total_biomass_grown": self.total_biomass_grown,
            "water": self.water,
            "x": self.config.x,
            "y": self.config.y,
        }
