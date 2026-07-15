"""Versioned heritable traits and deterministic inheritance operations."""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Any, Self, cast

from worm_world.organisms import BodyConfig, PhysiologyConfig

GENOME_SCHEMA_VERSION = 1


def _bounded(name: str, value: float, minimum: float, maximum: float) -> None:
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be finite and in [{minimum}, {maximum}]")


@dataclass(frozen=True, slots=True)
class Genome:
    """Immutable Phase 2 genome containing phenotype and reproduction priors only."""

    segment_count: int = 4
    segment_length: float = 0.25
    max_speed: float = 1.0
    max_turn_rate: float = math.pi
    max_energy: float = 100.0
    max_hydration: float = 100.0
    basal_energy_rate: float = 0.2
    basal_hydration_rate: float = 0.1
    movement_energy_rate: float = 0.4
    fertility_energy_fraction: float = 0.65
    offspring_energy_fraction: float = 0.2
    mutation_scale: float = 0.05
    schema_version: int = GENOME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if isinstance(self.segment_count, bool) or not 2 <= self.segment_count <= 32:
            raise ValueError("segment_count must be an integer in [2, 32]")
        _bounded("segment_length", self.segment_length, 0.05, 2.0)
        _bounded("max_speed", self.max_speed, 0.05, 5.0)
        _bounded("max_turn_rate", self.max_turn_rate, 0.05, 4.0 * math.pi)
        _bounded("max_energy", self.max_energy, 1.0, 10_000.0)
        _bounded("max_hydration", self.max_hydration, 1.0, 10_000.0)
        _bounded("basal_energy_rate", self.basal_energy_rate, 0.0, 10.0)
        _bounded("basal_hydration_rate", self.basal_hydration_rate, 0.0, 10.0)
        _bounded("movement_energy_rate", self.movement_energy_rate, 0.0, 20.0)
        _bounded("fertility_energy_fraction", self.fertility_energy_fraction, 0.25, 0.95)
        _bounded("offspring_energy_fraction", self.offspring_energy_fraction, 0.05, 0.4)
        _bounded("mutation_scale", self.mutation_scale, 0.0, 0.5)
        if self.offspring_energy_fraction >= self.fertility_energy_fraction:
            raise ValueError("offspring energy fraction must be below fertility threshold")
        if self.schema_version != GENOME_SCHEMA_VERSION:
            raise ValueError("unsupported genome schema version")

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def genome_id(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, serialized: str) -> Self:
        decoded: object = json.loads(serialized)
        if not isinstance(decoded, dict):
            raise ValueError("genome must be a JSON object")
        values = cast(dict[str, Any], decoded)
        if set(values) != set(asdict(cls())):
            raise ValueError("genome has missing or unknown fields")
        return cls(**values)


@dataclass(frozen=True, slots=True)
class FounderPhenotype:
    """Pure phenotype projection used to initialize a lifetime state."""

    body: BodyConfig
    physiology: PhysiologyConfig
    fertility_energy: float
    offspring_energy: float


def founder_phenotype(genome: Genome) -> FounderPhenotype:
    """Map inherited values to existing body and physiology contracts."""
    return FounderPhenotype(
        body=BodyConfig(
            segment_count=genome.segment_count,
            segment_length=genome.segment_length,
            max_speed=genome.max_speed,
            max_turn_rate=genome.max_turn_rate,
        ),
        physiology=PhysiologyConfig(
            max_energy=genome.max_energy,
            max_hydration=genome.max_hydration,
            basal_energy_rate=genome.basal_energy_rate,
            basal_hydration_rate=genome.basal_hydration_rate,
            movement_energy_rate=genome.movement_energy_rate,
        ),
        fertility_energy=genome.max_energy * genome.fertility_energy_fraction,
        offspring_energy=genome.max_energy * genome.offspring_energy_fraction,
    )


_FLOAT_TRAITS = (
    "segment_length",
    "max_speed",
    "max_turn_rate",
    "max_energy",
    "max_hydration",
    "basal_energy_rate",
    "basal_hydration_rate",
    "movement_energy_rate",
    "fertility_energy_fraction",
    "offspring_energy_fraction",
    "mutation_scale",
)


def genetic_distance(left: Genome, right: Genome) -> float:
    """Return a normalized morphology/physiology distance for compatibility analysis."""
    left_values = asdict(left)
    right_values = asdict(right)
    terms = [abs(left.segment_count - right.segment_count) / 30.0]
    for name in _FLOAT_TRAITS:
        a = float(left_values[name])
        b = float(right_values[name])
        scale = max(abs(a), abs(b), 1e-12)
        terms.append(abs(a - b) / scale)
    return sum(terms) / len(terms)


def compatible(left: Genome, right: Genome, maximum_distance: float) -> bool:
    if not math.isfinite(maximum_distance) or not 0.0 <= maximum_distance <= 1.0:
        raise ValueError("maximum compatibility distance must be in [0, 1]")
    return genetic_distance(left, right) <= maximum_distance


def inherit_genome(
    first: Genome,
    second: Genome | None,
    rng: random.Random,
    *,
    mutation_enabled: bool = True,
) -> Genome:
    """Recombine optional parents and mutate using only the supplied seeded stream."""
    first_values = asdict(first)
    second_values = asdict(second) if second is not None else first_values
    values: dict[str, int | float] = {}
    for name in ("segment_count", *_FLOAT_TRAITS):
        values[name] = first_values[name] if rng.randrange(2) == 0 else second_values[name]
    if mutation_enabled and float(values["mutation_scale"]) > 0.0:
        scale = float(values["mutation_scale"])
        if rng.random() < scale:
            values["segment_count"] = min(
                32, max(2, int(values["segment_count"]) + rng.choice((-1, 1)))
            )
        bounds = {
            "segment_length": (0.05, 2.0),
            "max_speed": (0.05, 5.0),
            "max_turn_rate": (0.05, 4.0 * math.pi),
            "max_energy": (1.0, 10_000.0),
            "max_hydration": (1.0, 10_000.0),
            "basal_energy_rate": (0.0, 10.0),
            "basal_hydration_rate": (0.0, 10.0),
            "movement_energy_rate": (0.0, 20.0),
            "fertility_energy_fraction": (0.25, 0.95),
            "offspring_energy_fraction": (0.05, 0.4),
            "mutation_scale": (0.0, 0.5),
        }
        for name, (minimum, maximum) in bounds.items():
            if rng.random() < scale:
                base = float(values[name])
                values[name] = min(maximum, max(minimum, base * (1.0 + rng.gauss(0.0, scale))))
    if float(values["offspring_energy_fraction"]) >= float(values["fertility_energy_fraction"]):
        values["offspring_energy_fraction"] = max(
            0.05, float(values["fertility_energy_fraction"]) - 0.05
        )
    return Genome(
        segment_count=int(values["segment_count"]),
        segment_length=float(values["segment_length"]),
        max_speed=float(values["max_speed"]),
        max_turn_rate=float(values["max_turn_rate"]),
        max_energy=float(values["max_energy"]),
        max_hydration=float(values["max_hydration"]),
        basal_energy_rate=float(values["basal_energy_rate"]),
        basal_hydration_rate=float(values["basal_hydration_rate"]),
        movement_energy_rate=float(values["movement_energy_rate"]),
        fertility_energy_fraction=float(values["fertility_energy_fraction"]),
        offspring_energy_fraction=float(values["offspring_energy_fraction"]),
        mutation_scale=float(values["mutation_scale"]),
    )
