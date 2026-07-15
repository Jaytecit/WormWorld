"""Deterministic fixed-step single-organism survival world."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Self

from worm_world.experiments.config import WorldConfig
from worm_world.organisms import (
    BodyConfig,
    PhysiologyConfig,
    PhysiologyState,
    PopulationStore,
    SensorReadings,
    WormAction,
    WormState,
    apply_physiology,
)
from worm_world.schemas import JsonValue, SimulationEvent, WorldSnapshot


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


@dataclass(frozen=True, slots=True)
class EntityStepResult:
    """One ID-associated outcome from a simultaneous population step."""

    entity_id: int
    outcome: StepResult


@dataclass(frozen=True, slots=True)
class PopulationStepResult:
    """Stable outcomes and lifecycle events from one population transition."""

    outcomes: tuple[EntityStepResult, ...]
    events: tuple[SimulationEvent, ...]


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
        self.population = PopulationStore()
        self._primary_entity_id = self.population.insert(self._state_from_initial(initial))
        self.food_energy = resource_config.food_energy
        self.water_amount = resource_config.water_amount
        self.energy_dissipated = 0.0
        self.hydration_dissipated = 0.0
        self._step_index = 0
        self._boundary_contacts = {self._primary_entity_id: False}
        self._event_sequence = 0

    @staticmethod
    def _state_from_initial(initial: InitialOrganismConfig) -> WormState:
        return WormState(
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

    @property
    def organism(self) -> WormState:
        """Phase 1 adapter exposing the retained primary organism state."""
        return self.population.state(self._primary_entity_id)

    @property
    def primary_entity_id(self) -> int:
        return self._primary_entity_id

    @property
    def step_index(self) -> int:
        return self._step_index

    @property
    def elapsed_seconds(self) -> float:
        return self._step_index * self.world_config.timestep_seconds

    @staticmethod
    def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
        return math.hypot(x2 - x1, y2 - y1)

    def add_organism(self, initial: InitialOrganismConfig) -> int:
        """Insert another independently identified live organism."""
        if not 0.0 <= initial.x <= self.world_config.width_meters:
            raise ValueError("initial x must be inside the world")
        if not 0.0 <= initial.y <= self.world_config.height_meters:
            raise ValueError("initial y must be inside the world")
        if not 0.0 < initial.energy <= self.physiology_config.max_energy:
            raise ValueError("initial energy must be positive and within physiological capacity")
        if not 0.0 < initial.hydration <= self.physiology_config.max_hydration:
            raise ValueError("initial hydration must be positive and within physiological capacity")
        if not 0.0 <= initial.injury < self.physiology_config.max_injury:
            raise ValueError("initial injury must be below physiological capacity")
        entity_id = self.population.insert(self._state_from_initial(initial))
        self._boundary_contacts[entity_id] = False
        return entity_id

    def _resource_signal(
        self, organism: WormState, x: float, y: float, amount: float
    ) -> tuple[float, float, float]:
        dx = x - organism.x
        dy = y - organism.y
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

    def sense(self, entity_id: int | None = None) -> SensorReadings:
        """Read signals without mutating the authoritative world."""
        entity_id = self._primary_entity_id if entity_id is None else entity_id
        organism = self.population.state(entity_id)
        food_dx, food_dy, food_intensity = self._resource_signal(
            organism,
            self.resource_config.food_x,
            self.resource_config.food_y,
            self.food_energy,
        )
        water_dx, water_dy, water_intensity = self._resource_signal(
            organism,
            self.resource_config.water_x,
            self.resource_config.water_y,
            self.water_amount,
        )
        physiology = organism.physiology
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
            boundary_contact=self._boundary_contacts[entity_id],
        )

    def _advance_entity(self, entity_id: int, action: WormAction) -> StepResult:
        """Apply one action without advancing authoritative world time."""
        organism = self.population.state(entity_id)
        physiology = organism.physiology
        dt = self.world_config.timestep_seconds
        forward = 0.0 if action.rest else action.forward
        turn = 0.0 if action.rest else action.turn
        organism.heading_radians += turn * self.body_config.max_turn_rate * dt
        organism.heading_radians = math.atan2(
            math.sin(organism.heading_radians), math.cos(organism.heading_radians)
        )
        intended_distance = forward * self.body_config.max_speed * dt
        old_x, old_y = organism.x, organism.y
        intended_x = old_x + math.cos(organism.heading_radians) * intended_distance
        intended_y = old_y + math.sin(organism.heading_radians) * intended_distance
        organism.x = min(self.world_config.width_meters, max(0.0, intended_x))
        organism.y = min(self.world_config.height_meters, max(0.0, intended_y))
        self._boundary_contacts[entity_id] = organism.x != intended_x or organism.y != intended_y
        distance_moved = self._distance(old_x, old_y, organism.x, organism.y)

        food_removed = 0.0
        energy_gain = 0.0
        food_waste = 0.0
        if (
            action.eat
            and self._distance(
                organism.x,
                organism.y,
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
                organism.x,
                organism.y,
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
        physiology.age_seconds = (self._step_index + 1) * dt
        self.population.update(entity_id, organism)
        return StepResult(
            distance_moved=distance_moved,
            food_removed=food_removed,
            water_removed=water_removed,
            energy_dissipated=delta.energy_dissipated,
            hydration_dissipated=delta.hydration_dissipated,
            death_transition=delta.death_transition,
            sensors=self.sense(entity_id),
        )

    def advance_population(self, actions: Mapping[int, WormAction]) -> PopulationStepResult:
        """Advance every active entity once using actions looked up by stable ID."""
        active_ids = self.population.active_entity_ids()
        if set(actions) != set(active_ids):
            raise ValueError("actions must contain exactly the active entity IDs")
        outcomes: list[EntityStepResult] = []
        deaths: list[tuple[int, StepResult]] = []
        for entity_id in active_ids:
            outcome = self._advance_entity(entity_id, actions[entity_id])
            outcomes.append(EntityStepResult(entity_id, outcome))
            if outcome.death_transition:
                deaths.append((entity_id, outcome))

        self._step_index += 1
        events: list[SimulationEvent] = []
        for entity_result in outcomes:
            events.append(
                SimulationEvent(
                    step_index=self._step_index,
                    sequence=self._event_sequence,
                    event_type="organism.step",
                    data={
                        "action": actions[entity_result.entity_id].to_dict(),
                        "entity_id": entity_result.entity_id,
                        "outcome": entity_result.outcome.to_dict(),
                    },
                )
            )
            self._event_sequence += 1
        for entity_id, _ in deaths:
            state = self.population.state(entity_id)
            if self.population.tombstone(entity_id):
                events.append(
                    SimulationEvent(
                        step_index=self._step_index,
                        sequence=self._event_sequence,
                        event_type="organism.died",
                        data={
                            "age_seconds": state.physiology.age_seconds,
                            "energy": state.physiology.energy,
                            "entity_id": entity_id,
                            "hydration": state.physiology.hydration,
                            "injury": state.physiology.injury,
                        },
                    )
                )
                self._event_sequence += 1
        return PopulationStepResult(tuple(outcomes), tuple(events))

    def advance(self, action: WormAction) -> StepResult:
        """Apply the retained Phase 1 single-organism adapter transition."""
        if not self.population.is_active(self._primary_entity_id):
            self._step_index += 1
            return StepResult(0.0, 0.0, 0.0, 0.0, 0.0, False, self.sense())
        result = self._advance_entity(self._primary_entity_id, action)
        self._step_index += 1
        if result.death_transition:
            self.population.tombstone(self._primary_entity_id)
        return result

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

    def population_state_dict(self) -> dict[str, JsonValue]:
        """Return all allocated entities in stable ID order for Phase 2 replay."""
        organisms: list[JsonValue] = []
        for entity_id in self.population.entity_ids():
            organism = self.population.state(entity_id)
            physiology = organism.physiology
            organisms.append(
                {
                    "active": self.population.is_active(entity_id),
                    "age_seconds": physiology.age_seconds,
                    "alive": physiology.alive,
                    "energy": physiology.energy,
                    "entity_id": entity_id,
                    "heading_radians": organism.heading_radians,
                    "hydration": physiology.hydration,
                    "injury": physiology.injury,
                    "segments": [
                        {"x": x, "y": y} for x, y in organism.segment_positions(self.body_config)
                    ],
                    "sensors": self.sense(entity_id).to_dict(),
                    "x": organism.x,
                    "y": organism.y,
                }
            )
        return {
            "accounting": {
                "energy_dissipated": self.energy_dissipated,
                "hydration_dissipated": self.hydration_dissipated,
            },
            "population": organisms,
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
        }

    def snapshot(self) -> WorldSnapshot:
        return WorldSnapshot(
            step_index=self.step_index,
            elapsed_seconds=self.elapsed_seconds,
            state=self.state_dict(),
        )

    def population_snapshot(self) -> WorldSnapshot:
        """Capture the Phase 2 population view without changing Phase 1 bytes."""
        return WorldSnapshot(
            step_index=self.step_index,
            elapsed_seconds=self.elapsed_seconds,
            state=self.population_state_dict(),
        )
