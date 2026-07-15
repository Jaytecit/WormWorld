"""Versioned heritable traits and deterministic inheritance operations."""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from typing import Any, Self, cast

from worm_world.organisms import BodyConfig, PhysiologyConfig

GENOME_SCHEMA_VERSION = 1
LATEST_GENOME_SCHEMA_VERSION = 2
SENSOR_WIDTH = 10
ACTION_WIDTH = 6

_PHENOTYPE_FIELDS = (
    "segment_count",
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
_V2_FIELDS = (
    "brain_hidden_size",
    "brain_priors",
    "plasticity_rate",
    "eligibility_trace_decay",
    "homeostatic_energy_weight",
    "homeostatic_hydration_weight",
    "homeostatic_injury_weight",
)


def _bounded(name: str, value: float, minimum: float, maximum: float) -> None:
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be finite and in [{minimum}, {maximum}]")


def controller_prior_count(hidden_size: int) -> int:
    """Return the fixed flattened controller-prior width for a hidden size."""
    if isinstance(hidden_size, bool) or not 1 <= hidden_size <= 64:
        raise ValueError("brain_hidden_size must be an integer in [1, 64]")
    return (
        hidden_size * SENSOR_WIDTH
        + hidden_size**2
        + hidden_size
        + ACTION_WIDTH * hidden_size
        + ACTION_WIDTH
    )


def controller_prior_values_from_id(genome_id: str, hidden_size: int) -> tuple[float, ...]:
    """Expand a v1 identity using the retained P3-T01 platform-independent rule."""
    if len(genome_id) != 64 or any(character not in "0123456789abcdef" for character in genome_id):
        raise ValueError("genome_id must be a lowercase SHA-256 digest")
    count = controller_prior_count(hidden_size)
    values: list[float] = []
    block = 0
    while len(values) < count:
        digest = hashlib.sha256(f"{genome_id}:controller-v1:{block}".encode()).digest()
        values.extend(((byte / 255.0) - 0.5) * 0.5 for byte in digest)
        block += 1
    return tuple(values[:count])


@dataclass(frozen=True, slots=True)
class Genome:
    """Immutable heritable phenotype and optional version-2 brain priors."""

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
    brain_hidden_size: int | None = None
    brain_priors: tuple[float, ...] | None = None
    plasticity_rate: float | None = None
    eligibility_trace_decay: float | None = None
    homeostatic_energy_weight: float | None = None
    homeostatic_hydration_weight: float | None = None
    homeostatic_injury_weight: float | None = None

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
        if self.schema_version not in (GENOME_SCHEMA_VERSION, LATEST_GENOME_SCHEMA_VERSION):
            raise ValueError("unsupported genome schema version")
        brain_values = tuple(getattr(self, name) for name in _V2_FIELDS)
        if self.schema_version == GENOME_SCHEMA_VERSION:
            if any(value is not None for value in brain_values):
                raise ValueError("version-1 genomes cannot contain brain fields")
            return
        if any(value is None for value in brain_values):
            raise ValueError("version-2 genomes require every brain field")
        assert self.brain_hidden_size is not None and self.brain_priors is not None
        if len(self.brain_priors) != controller_prior_count(self.brain_hidden_size):
            raise ValueError("brain_priors has invalid flattened shape")
        for value in self.brain_priors:
            _bounded("brain prior", value, -1.0, 1.0)
        assert self.plasticity_rate is not None and self.eligibility_trace_decay is not None
        _bounded("plasticity_rate", self.plasticity_rate, 0.0, 1.0)
        _bounded("eligibility_trace_decay", self.eligibility_trace_decay, 0.0, 1.0)
        assert self.homeostatic_energy_weight is not None
        assert self.homeostatic_hydration_weight is not None
        assert self.homeostatic_injury_weight is not None
        _bounded("homeostatic_energy_weight", self.homeostatic_energy_weight, -4.0, 4.0)
        _bounded("homeostatic_hydration_weight", self.homeostatic_hydration_weight, -4.0, 4.0)
        _bounded("homeostatic_injury_weight", self.homeostatic_injury_weight, -4.0, 4.0)

    @classmethod
    def version2(
        cls,
        base: Genome | None = None,
        *,
        hidden_size: int = 8,
        plasticity_rate: float = 0.01,
        eligibility_trace_decay: float = 0.9,
        homeostatic_energy_weight: float = 1.0,
        homeostatic_hydration_weight: float = 1.0,
        homeostatic_injury_weight: float = -1.0,
    ) -> Genome:
        """Promote a strict v1 genome while making its retained priors explicit."""
        source = cls() if base is None else base
        if source.schema_version != GENOME_SCHEMA_VERSION:
            raise ValueError("only a version-1 genome can be promoted")
        return cls(
            segment_count=source.segment_count,
            segment_length=source.segment_length,
            max_speed=source.max_speed,
            max_turn_rate=source.max_turn_rate,
            max_energy=source.max_energy,
            max_hydration=source.max_hydration,
            basal_energy_rate=source.basal_energy_rate,
            basal_hydration_rate=source.basal_hydration_rate,
            movement_energy_rate=source.movement_energy_rate,
            fertility_energy_fraction=source.fertility_energy_fraction,
            offspring_energy_fraction=source.offspring_energy_fraction,
            mutation_scale=source.mutation_scale,
            schema_version=LATEST_GENOME_SCHEMA_VERSION,
            brain_hidden_size=hidden_size,
            brain_priors=controller_prior_values_from_id(source.genome_id, hidden_size),
            plasticity_rate=plasticity_rate,
            eligibility_trace_decay=eligibility_trace_decay,
            homeostatic_energy_weight=homeostatic_energy_weight,
            homeostatic_hydration_weight=homeostatic_hydration_weight,
            homeostatic_injury_weight=homeostatic_injury_weight,
        )

    def _phenotype_dict(self) -> dict[str, int | float]:
        return {name: cast(int | float, getattr(self, name)) for name in _PHENOTYPE_FIELDS}

    def to_dict(self) -> dict[str, Any]:
        values: dict[str, Any] = self._phenotype_dict()
        values["schema_version"] = self.schema_version
        if self.schema_version == LATEST_GENOME_SCHEMA_VERSION:
            for name in _V2_FIELDS:
                value = getattr(self, name)
                values[name] = list(value) if name == "brain_priors" else value
        return values

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def genome_id(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, serialized: str) -> Self:
        decoded: object = json.loads(serialized)
        if not isinstance(decoded, dict):
            raise ValueError("genome must be a JSON object")
        values = cast(dict[str, Any], decoded)
        version = values.get("schema_version")
        expected = set(_PHENOTYPE_FIELDS) | {"schema_version"}
        if "schema_version" not in values:
            raise ValueError("genome has missing or unknown fields")
        if version == LATEST_GENOME_SCHEMA_VERSION:
            expected.update(_V2_FIELDS)
        elif version != GENOME_SCHEMA_VERSION:
            raise ValueError("unsupported genome schema version")
        if set(values) != expected:
            raise ValueError("genome has missing or unknown fields")
        if version == LATEST_GENOME_SCHEMA_VERSION:
            priors = cast(object, values["brain_priors"])
            if not isinstance(priors, list):
                raise ValueError("brain_priors must be a JSON array")
            numeric_priors = cast(list[object], priors)
            if any(
                isinstance(value, bool) or not isinstance(value, int | float)
                for value in numeric_priors
            ):
                raise ValueError("brain_priors must contain only numbers")
            values["brain_priors"] = tuple(
                float(cast(int | float, value)) for value in numeric_priors
            )
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


_FLOAT_TRAITS = _PHENOTYPE_FIELDS[1:]


def genetic_distance(left: Genome, right: Genome) -> float:
    """Return a normalized inherited-trait distance for compatibility analysis."""
    terms = [abs(left.segment_count - right.segment_count) / 30.0]
    for name in _FLOAT_TRAITS:
        a = float(getattr(left, name))
        b = float(getattr(right, name))
        scale = max(abs(a), abs(b), 1e-12)
        terms.append(abs(a - b) / scale)
    if left.schema_version != right.schema_version:
        terms.append(1.0)
    elif left.schema_version == LATEST_GENOME_SCHEMA_VERSION:
        assert left.brain_priors is not None and right.brain_priors is not None
        assert left.brain_hidden_size is not None and right.brain_hidden_size is not None
        terms.append(abs(left.brain_hidden_size - right.brain_hidden_size) / 63.0)
        for name in _V2_FIELDS[2:]:
            a = float(cast(float, getattr(left, name)))
            b = float(cast(float, getattr(right, name)))
            terms.append(abs(a - b) / max(abs(a), abs(b), 1e-12))
        terms.append(
            sum(
                abs(a - b) / max(abs(a), abs(b), 1e-12)
                for a, b in zip(left.brain_priors, right.brain_priors, strict=True)
            )
            / len(left.brain_priors)
            if len(left.brain_priors) == len(right.brain_priors)
            else 1.0
        )
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
    other = first if second is None else second
    if first.schema_version != other.schema_version:
        raise ValueError("parents must use the same genome schema version")
    values: dict[str, Any] = {}
    for name in _PHENOTYPE_FIELDS:
        values[name] = getattr(first, name) if rng.randrange(2) == 0 else getattr(other, name)
    if first.schema_version == LATEST_GENOME_SCHEMA_VERSION:
        if first.brain_hidden_size != other.brain_hidden_size:
            raise ValueError("version-2 parents must use the same brain hidden size")
        for name in _V2_FIELDS:
            if name == "brain_priors":
                assert first.brain_priors is not None and other.brain_priors is not None
                values[name] = tuple(
                    a if rng.randrange(2) == 0 else b
                    for a, b in zip(first.brain_priors, other.brain_priors, strict=True)
                )
            else:
                values[name] = (
                    getattr(first, name) if rng.randrange(2) == 0 else getattr(other, name)
                )
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
            "plasticity_rate": (0.0, 1.0),
            "eligibility_trace_decay": (0.0, 1.0),
            "homeostatic_energy_weight": (-4.0, 4.0),
            "homeostatic_hydration_weight": (-4.0, 4.0),
            "homeostatic_injury_weight": (-4.0, 4.0),
        }
        for name, (minimum, maximum) in bounds.items():
            if name in values and rng.random() < scale:
                base = float(values[name])
                if name in _V2_FIELDS:
                    mutated = base + rng.gauss(0.0, scale * (maximum - minimum) * 0.05)
                else:
                    mutated = base * (1.0 + rng.gauss(0.0, scale))
                values[name] = min(maximum, max(minimum, mutated))
        if "brain_priors" in values:
            values["brain_priors"] = tuple(
                min(1.0, max(-1.0, value + rng.gauss(0.0, scale * 0.1)))
                if rng.random() < scale
                else value
                for value in values["brain_priors"]
            )
    if float(values["offspring_energy_fraction"]) >= float(values["fertility_energy_fraction"]):
        values["offspring_energy_fraction"] = max(
            0.05, float(values["fertility_energy_fraction"]) - 0.05
        )
    return Genome(**values, schema_version=first.schema_version)
