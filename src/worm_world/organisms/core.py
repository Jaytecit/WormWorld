"""Single-organism body, physiology, sensing, and action contracts."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Self, cast

from worm_world.schemas import JsonValue


def _positive_finite(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")


def _non_negative_finite(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class BodyConfig:
    """Geometry and locomotion limits for one simple segmented worm body."""

    segment_count: int = 4
    segment_length: float = 0.25
    max_speed: float = 1.0
    max_turn_rate: float = math.pi

    def __post_init__(self) -> None:
        if isinstance(self.segment_count, bool) or self.segment_count < 2:
            raise ValueError("segment_count must be an integer greater than or equal to two")
        for name, value in (
            ("segment_length", self.segment_length),
            ("max_speed", self.max_speed),
            ("max_turn_rate", self.max_turn_rate),
        ):
            _positive_finite(name, value)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> Self:
        return cls(**values)


@dataclass(frozen=True, slots=True)
class PhysiologyConfig:
    """Homeostatic capacities and per-second costs, with no task reward."""

    max_energy: float = 100.0
    max_hydration: float = 100.0
    max_injury: float = 1.0
    basal_energy_rate: float = 0.2
    basal_hydration_rate: float = 0.1
    movement_energy_rate: float = 0.4
    resting_metabolism_multiplier: float = 0.5

    def __post_init__(self) -> None:
        for name, value in (
            ("max_energy", self.max_energy),
            ("max_hydration", self.max_hydration),
            ("max_injury", self.max_injury),
        ):
            _positive_finite(name, value)
        for name, value in (
            ("basal_energy_rate", self.basal_energy_rate),
            ("basal_hydration_rate", self.basal_hydration_rate),
            ("movement_energy_rate", self.movement_energy_rate),
        ):
            _non_negative_finite(name, value)
        if not 0.0 < self.resting_metabolism_multiplier <= 1.0:
            raise ValueError("resting_metabolism_multiplier must be in (0, 1]")

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> Self:
        return cls(**values)


@dataclass(frozen=True, slots=True)
class WormAction:
    """Minimal simultaneous motor and ingestion command for one fixed step."""

    forward: float = 0.0
    turn: float = 0.0
    eat: bool = False
    drink: bool = False
    rest: bool = False

    def __post_init__(self) -> None:
        for name, value in (("forward", self.forward), ("turn", self.turn)):
            if not math.isfinite(value) or not -1.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [-1, 1]")

    def to_dict(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], asdict(self))

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> Self:
        expected = {"forward", "turn", "eat", "drink", "rest"}
        if set(values) != expected:
            raise ValueError("action fields must be exactly forward, turn, eat, drink, and rest")
        return cls(**values)


@dataclass(slots=True)
class PhysiologyState:
    """Mutable lifetime-only physiological condition."""

    energy: float
    hydration: float
    injury: float = 0.0
    age_seconds: float = 0.0
    alive: bool = True


@dataclass(slots=True)
class WormState:
    """Authoritative head pose and physiology for a segmented body."""

    x: float
    y: float
    heading_radians: float
    physiology: PhysiologyState

    def segment_positions(self, config: BodyConfig) -> tuple[tuple[float, float], ...]:
        """Derive a deterministic straight body chain behind the head."""
        cos_heading = math.cos(self.heading_radians)
        sin_heading = math.sin(self.heading_radians)
        return tuple(
            (
                self.x - index * config.segment_length * cos_heading,
                self.y - index * config.segment_length * sin_heading,
            )
            for index in range(config.segment_count)
        )


@dataclass(frozen=True, slots=True)
class SensorReadings:
    """Weak exteroceptive and interoceptive signals available to a controller."""

    energy_fraction: float
    hydration_fraction: float
    injury_fraction: float
    food_dx: float
    food_dy: float
    food_intensity: float
    water_dx: float
    water_dy: float
    water_intensity: float
    boundary_contact: bool

    def to_dict(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], asdict(self))


@dataclass(frozen=True, slots=True)
class PhysiologyDelta:
    """Conserved transfers and losses produced by one transition."""

    food_removed: float = 0.0
    water_removed: float = 0.0
    energy_gained: float = 0.0
    energy_dissipated: float = 0.0
    hydration_gained: float = 0.0
    hydration_dissipated: float = 0.0
    death_transition: bool = False


def apply_physiology(
    state: PhysiologyState,
    config: PhysiologyConfig,
    *,
    timestep_seconds: float,
    movement_effort: float,
    rest: bool,
    energy_gain: float,
    hydration_gain: float,
    food_waste: float,
) -> PhysiologyDelta:
    """Advance homeostasis once and emit an idempotent death transition."""
    if not state.alive:
        return PhysiologyDelta()
    multiplier = config.resting_metabolism_multiplier if rest else 1.0
    energy_loss = (
        config.basal_energy_rate * multiplier + config.movement_energy_rate * movement_effort
    ) * timestep_seconds
    hydration_loss = config.basal_hydration_rate * multiplier * timestep_seconds
    available_energy = min(config.max_energy, state.energy + energy_gain)
    actual_energy_loss = min(available_energy, energy_loss)
    available_hydration = min(config.max_hydration, state.hydration + hydration_gain)
    actual_hydration_loss = min(available_hydration, hydration_loss)
    state.energy = available_energy - actual_energy_loss
    state.hydration = available_hydration - actual_hydration_loss
    state.injury = min(config.max_injury, max(0.0, state.injury))
    state.age_seconds += timestep_seconds
    died = state.energy <= 0.0 or state.hydration <= 0.0 or state.injury >= config.max_injury
    state.alive = not died
    return PhysiologyDelta(
        energy_gained=energy_gain,
        energy_dissipated=actual_energy_loss + food_waste,
        hydration_gained=hydration_gain,
        hydration_dissipated=actual_hydration_loss,
        death_transition=died,
    )
