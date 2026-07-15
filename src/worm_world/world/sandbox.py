"""Deterministic fixed-step single-organism survival world."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Self

from worm_world.experiments.config import WorldConfig
from worm_world.organisms import (
    BodyConfig,
    PhysiologyConfig,
    PhysiologyState,
    SensorReadings,
    WormAction,
    WormState,
    apply_physiology,
)
from worm_world.schemas import JsonValue, WorldSnapshot


def _finite_non_negative(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ResourceFieldConfig:
    """Two finite point patches with general distance-based affordances."""

    food_x: float = 6.0
    food_y: float = 5.0
    food_energy: float = 50.0
    water_x: float = 4.0
    water_y: float = 5.0
    water_amount: float = 50.0
    interaction_radius: float = 0.35
    sensor_range: float = 5.0
    eat_rate: float = 5.0
    drink_rate: float = 5.0
    food_assimilation_efficiency: float = 0.8

    def __post_init__(self) -> None:
        for name, value in (
            ("food_x", self.food_x),
            ("food_y", self.food_y),
            ("food_energy", self.food_energy),
            ("water_x", self.water_x),
            ("water_y", self.water_y),
            ("water_amount", self.water_amount),
            ("interaction_radius", self.interaction_radius),
            ("sensor_range", self.sensor_range),
            ("eat_rate", self.eat_rate),
            ("drink_rate", self.drink_rate),
        ):
            _finite_non_negative(name, value)
        if self.interaction_radius <= 0.0 or self.sensor_range <= 0.0:
            raise ValueError("interaction_radius and sensor_range must be greater than zero")
        if not 0.0 < self.food_assimilation_efficiency <= 1.0:
            raise ValueError("food_assimilation_efficiency must be in (0, 1]")

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> Self:
        return cls(**values)


@dataclass(frozen=True, slots=True)
class InitialOrganismConfig:
    """Explicit initial condition for the sole organism."""

    x: float = 5.0
    y: float = 5.0
    heading_radians: float = 0.0
    energy: float = 50.0
    hydration: float = 50.0
    injury: float = 0.0

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> Self:
        return cls(**values)


@dataclass(frozen=True, slots=True)
class StepResult:
    """Observable outcome of one authoritative fixed step."""

    distance_moved: float
    food_removed: float
    water_removed: float
    energy_dissipated: float
    hydration_dissipated: float
    death_transition: bool
    sensors: SensorReadings

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "death_transition": self.death_transition,
            "distance_moved": self.distance_moved,
            "energy_dissipated": self.energy_dissipated,
            "food_removed": self.food_removed,
            "hydration_dissipated": self.hydration_dissipated,
            "sensors": self.sensors.to_dict(),
            "water_removed": self.water_removed,
        }


class SandboxWorld:
    """Headless 2.5D sandbox with one worm and two finite resource patches."""

    def __init__(
        self,
        world_config: WorldConfig,
        body_config: BodyConfig,
        physiology_config: PhysiologyConfig,
        resource_config: ResourceFieldConfig,
        initial: InitialOrganismConfig,
    ) -> None:
        if not 0.0 <= initial.x <= world_config.width_meters:
            raise ValueError("initial x must be inside the world")
        if not 0.0 <= initial.y <= world_config.height_meters:
            raise ValueError("initial y must be inside the world")
        if not 0.0 <= initial.energy <= physiology_config.max_energy:
            raise ValueError("initial energy must be within physiological capacity")
        if not 0.0 <= initial.hydration <= physiology_config.max_hydration:
            raise ValueError("initial hydration must be within physiological capacity")
        if not 0.0 <= initial.injury <= physiology_config.max_injury:
            raise ValueError("initial injury must be within physiological capacity")
        if (
            initial.energy <= 0.0
            or initial.hydration <= 0.0
            or initial.injury >= physiology_config.max_injury
        ):
            raise ValueError("the initial organism must be alive")
        for name, x, y in (
            ("food", resource_config.food_x, resource_config.food_y),
            ("water", resource_config.water_x, resource_config.water_y),
        ):
            if (
                not 0.0 <= x <= world_config.width_meters
                or not 0.0 <= y <= world_config.height_meters
            ):
                raise ValueError(f"{name} patch must be inside the world")

        self.world_config = world_config
        self.body_config = body_config
        self.physiology_config = physiology_config
        self.resource_config = resource_config
        self.organism = WormState(
            x=initial.x,
            y=initial.y,
            heading_radians=initial.heading_radians,
            physiology=PhysiologyState(
                energy=initial.energy,
                hydration=initial.hydration,
                injury=initial.injury,
                alive=True,
            ),
        )
        self.food_energy = resource_config.food_energy
        self.water_amount = resource_config.water_amount
        self.energy_dissipated = 0.0
        self.hydration_dissipated = 0.0
        self._step_index = 0
        self._boundary_contact = False

    @property
    def step_index(self) -> int:
        return self._step_index

    @property
    def elapsed_seconds(self) -> float:
        return self._step_index * self.world_config.timestep_seconds

    @staticmethod
    def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
        return math.hypot(x2 - x1, y2 - y1)

    def _resource_signal(self, x: float, y: float, amount: float) -> tuple[float, float, float]:
        dx = x - self.organism.x
        dy = y - self.organism.y
        distance = math.hypot(dx, dy)
        if amount <= 0.0 or distance > self.resource_config.sensor_range:
            return (0.0, 0.0, 0.0)
        if distance == 0.0:
            return (0.0, 0.0, 1.0)
        return (
            dx / distance,
            dy / distance,
            1.0 - distance / self.resource_config.sensor_range,
        )

    def sense(self) -> SensorReadings:
        """Read signals without mutating the authoritative world."""
        food_dx, food_dy, food_intensity = self._resource_signal(
            self.resource_config.food_x, self.resource_config.food_y, self.food_energy
        )
        water_dx, water_dy, water_intensity = self._resource_signal(
            self.resource_config.water_x, self.resource_config.water_y, self.water_amount
        )
        physiology = self.organism.physiology
        return SensorReadings(
            energy_fraction=physiology.energy / self.physiology_config.max_energy,
            hydration_fraction=physiology.hydration / self.physiology_config.max_hydration,
            injury_fraction=physiology.injury / self.physiology_config.max_injury,
            food_dx=food_dx,
            food_dy=food_dy,
            food_intensity=food_intensity,
            water_dx=water_dx,
            water_dy=water_dy,
            water_intensity=water_intensity,
            boundary_contact=self._boundary_contact,
        )

    def advance(self, action: WormAction) -> StepResult:
        """Apply one simultaneous action and one metabolism transition."""
        physiology = self.organism.physiology
        if not physiology.alive:
            self._step_index += 1
            return StepResult(0.0, 0.0, 0.0, 0.0, 0.0, False, self.sense())

        dt = self.world_config.timestep_seconds
        forward = 0.0 if action.rest else action.forward
        turn = 0.0 if action.rest else action.turn
        self.organism.heading_radians += turn * self.body_config.max_turn_rate * dt
        self.organism.heading_radians = math.atan2(
            math.sin(self.organism.heading_radians), math.cos(self.organism.heading_radians)
        )
        intended_distance = forward * self.body_config.max_speed * dt
        old_x, old_y = self.organism.x, self.organism.y
        intended_x = old_x + math.cos(self.organism.heading_radians) * intended_distance
        intended_y = old_y + math.sin(self.organism.heading_radians) * intended_distance
        self.organism.x = min(self.world_config.width_meters, max(0.0, intended_x))
        self.organism.y = min(self.world_config.height_meters, max(0.0, intended_y))
        self._boundary_contact = self.organism.x != intended_x or self.organism.y != intended_y
        distance_moved = self._distance(old_x, old_y, self.organism.x, self.organism.y)

        food_removed = 0.0
        energy_gain = 0.0
        food_waste = 0.0
        if (
            action.eat
            and self._distance(
                self.organism.x,
                self.organism.y,
                self.resource_config.food_x,
                self.resource_config.food_y,
            )
            <= self.resource_config.interaction_radius
        ):
            capacity = self.physiology_config.max_energy - physiology.energy
            maximum_removed = min(self.food_energy, self.resource_config.eat_rate * dt)
            food_removed = min(
                maximum_removed,
                capacity / self.resource_config.food_assimilation_efficiency,
            )
            energy_gain = food_removed * self.resource_config.food_assimilation_efficiency
            food_waste = food_removed - energy_gain
            self.food_energy -= food_removed

        water_removed = 0.0
        hydration_gain = 0.0
        if (
            action.drink
            and self._distance(
                self.organism.x,
                self.organism.y,
                self.resource_config.water_x,
                self.resource_config.water_y,
            )
            <= self.resource_config.interaction_radius
        ):
            capacity = self.physiology_config.max_hydration - physiology.hydration
            water_removed = min(self.water_amount, self.resource_config.drink_rate * dt, capacity)
            hydration_gain = water_removed
            self.water_amount -= water_removed

        delta = apply_physiology(
            physiology,
            self.physiology_config,
            timestep_seconds=dt,
            movement_effort=abs(forward),
            rest=action.rest,
            energy_gain=energy_gain,
            hydration_gain=hydration_gain,
            food_waste=food_waste,
        )
        self.energy_dissipated += delta.energy_dissipated
        self.hydration_dissipated += delta.hydration_dissipated
        self._step_index += 1
        physiology.age_seconds = self.elapsed_seconds
        return StepResult(
            distance_moved=distance_moved,
            food_removed=food_removed,
            water_removed=water_removed,
            energy_dissipated=delta.energy_dissipated,
            hydration_dissipated=delta.hydration_dissipated,
            death_transition=delta.death_transition,
            sensors=self.sense(),
        )

    def state_dict(self) -> dict[str, JsonValue]:
        """Return the complete authoritative state in canonical-schema values."""
        physiology = self.organism.physiology
        segments: list[JsonValue] = [
            {"x": x, "y": y} for x, y in self.organism.segment_positions(self.body_config)
        ]
        return {
            "accounting": {
                "energy_dissipated": self.energy_dissipated,
                "hydration_dissipated": self.hydration_dissipated,
            },
            "organism": {
                "age_seconds": physiology.age_seconds,
                "alive": physiology.alive,
                "energy": physiology.energy,
                "heading_radians": self.organism.heading_radians,
                "hydration": physiology.hydration,
                "injury": physiology.injury,
                "segments": segments,
                "x": self.organism.x,
                "y": self.organism.y,
            },
            "resources": {
                "food": {
                    "amount": self.food_energy,
                    "x": self.resource_config.food_x,
                    "y": self.resource_config.food_y,
                },
                "water": {
                    "amount": self.water_amount,
                    "x": self.resource_config.water_x,
                    "y": self.resource_config.water_y,
                },
            },
            "sensors": self.sense().to_dict(),
        }

    def snapshot(self) -> WorldSnapshot:
        return WorldSnapshot(
            step_index=self.step_index,
            elapsed_seconds=self.elapsed_seconds,
            state=self.state_dict(),
        )
