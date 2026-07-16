"""Persistent deterministic population world with reproduction and competition."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from worm_world.experiments.config import WorldConfig
from worm_world.genetics import Genome, LineageStore, compatible, founder_phenotype, inherit_genome
from worm_world.organisms import (
    PhysiologyState,
    PopulationStore,
    SensorReadings,
    WormAction,
    WormState,
    apply_physiology,
)
from worm_world.rng import NamedRandomStreams
from worm_world.schemas import JsonValue, SimulationEvent, WorldSnapshot
from worm_world.world.detritus import DetritusConfig, DetritusPool, DetritusTransfer
from worm_world.world.plants import PlantGrowth, PlantPatch, PlantPatchConfig
from worm_world.world.sandbox import InitialOrganismConfig, ResourceFieldConfig


@dataclass(frozen=True, slots=True)
class Founder:
    genome: Genome
    initial: InitialOrganismConfig
    label: str

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("founder label must not be empty")


@dataclass(frozen=True, slots=True)
class ReproductionConfig:
    mode: Literal["asexual", "sexual"] = "asexual"
    minimum_age_seconds: float = 1.0
    cooldown_seconds: float = 2.0
    interaction_radius: float = 0.5
    maximum_compatibility_distance: float = 0.2
    maximum_population: int = 256
    mutation_enabled: bool = True
    heritability_enabled: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("minimum_age_seconds", self.minimum_age_seconds),
            ("cooldown_seconds", self.cooldown_seconds),
            ("interaction_radius", self.interaction_radius),
            ("maximum_compatibility_distance", self.maximum_compatibility_distance),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.interaction_radius <= 0.0:
            raise ValueError("interaction_radius must be positive")
        if self.maximum_compatibility_distance > 1.0:
            raise ValueError("maximum_compatibility_distance must be at most one")
        if isinstance(self.maximum_population, bool) or self.maximum_population < 1:
            raise ValueError("maximum_population must be a positive integer")


@dataclass(frozen=True, slots=True)
class PopulationAction:
    motion: WormAction = field(default_factory=WormAction)
    reproduce: bool = False
    mate_id: int | None = None

    def __post_init__(self) -> None:
        if self.mate_id is not None and (isinstance(self.mate_id, bool) or self.mate_id <= 0):
            raise ValueError("mate_id must be a positive entity ID")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "mate_id": self.mate_id,
            "motion": self.motion.to_dict(),
            "reproduce": self.reproduce,
        }


@dataclass(frozen=True, slots=True)
class PopulationTransition:
    events: tuple[SimulationEvent, ...]
    births: tuple[int, ...]
    deaths: tuple[int, ...]


def _fair_allocations(claims: Mapping[int, float], available: float) -> dict[int, float]:
    """Water-fill limited claims without entity-order priority."""
    allocations = {entity_id: 0.0 for entity_id in claims}
    remaining = max(0.0, available)
    pending = {entity_id for entity_id, claim in claims.items() if claim > 0.0}
    while pending and remaining > 0.0:
        share = remaining / len(pending)
        satisfied: list[int] = []
        for entity_id in sorted(pending):
            need = claims[entity_id] - allocations[entity_id]
            amount = min(share, need)
            allocations[entity_id] += amount
            remaining -= amount
            if allocations[entity_id] >= claims[entity_id] - 1e-12:
                satisfied.append(entity_id)
        if not satisfied:
            break
        pending.difference_update(satisfied)
    return allocations


class PopulationWorld:
    """Headless persistent population whose only selection is birth and survival."""

    def __init__(
        self,
        *,
        seed: int,
        world_config: WorldConfig,
        resource_config: ResourceFieldConfig,
        reproduction_config: ReproductionConfig,
        founders: Sequence[Founder],
        plant_config: PlantPatchConfig | None = None,
        detritus_config: DetritusConfig | None = None,
        initial_event_sequence: int = 0,
    ) -> None:
        if not founders:
            raise ValueError("at least one founder is required")
        if len(founders) > reproduction_config.maximum_population:
            raise ValueError("founders exceed maximum population")
        self.world_config = world_config
        self.resource_config = resource_config
        self.reproduction_config = reproduction_config
        self.population = PopulationStore()
        self.lineages = LineageStore()
        self._streams = NamedRandomStreams(seed)
        self._genomes: dict[str, Genome] = {}
        self._genome_by_entity: dict[int, str] = {}
        self._founder_label_by_entity: dict[int, str] = {}
        self._root_founder_by_entity: dict[int, int] = {}
        self._next_reproduction_step: dict[int, int] = {}
        self._boundary_contacts: dict[int, bool] = {}
        self._step_index = 0
        if isinstance(initial_event_sequence, bool) or initial_event_sequence < 0:
            raise ValueError("initial_event_sequence must be non-negative")
        self._event_sequence = initial_event_sequence
        self.food_energy = resource_config.food_energy
        self.water_amount = resource_config.water_amount
        self.plant_patch: PlantPatch | None = None
        if plant_config is not None and plant_config.enabled:
            if resource_config.food_energy != 0.0:
                raise ValueError("static food must be zero when the plant patch is enabled")
            self.plant_patch = PlantPatch(
                plant_config,
                world_width=world_config.width_meters,
                world_height=world_config.height_meters,
            )
        self.detritus_pool: DetritusPool | None = None
        if detritus_config is not None and detritus_config.enabled:
            if self.plant_patch is None:
                raise ValueError("detritus recycling requires an enabled plant patch")
            self.detritus_pool = DetritusPool(detritus_config)
        self.energy_dissipated = 0.0
        self.hydration_dissipated = 0.0
        self.birth_count = 0
        self.death_count = 0
        self._founder_genomes = tuple(founder.genome for founder in founders)
        for founder in founders:
            self._validate_initial(founder.initial, founder.genome)
            entity_id = self._insert(
                founder.genome,
                founder.initial,
                parent_ids=(),
                founder_label=founder.label,
                root_founder=None,
            )
            self._root_founder_by_entity[entity_id] = entity_id

    @property
    def step_index(self) -> int:
        return self._step_index

    @property
    def elapsed_seconds(self) -> float:
        return self._step_index * self.world_config.timestep_seconds

    @property
    def next_event_sequence(self) -> int:
        return self._event_sequence

    def genome(self, entity_id: int) -> Genome:
        return self._genomes[self._genome_by_entity[entity_id]]

    def root_founder(self, entity_id: int) -> int:
        return self._root_founder_by_entity[entity_id]

    def _resource_signal(
        self, state: WormState, x: float, y: float, amount: float
    ) -> tuple[float, float, float]:
        dx = x - state.x
        dy = y - state.y
        distance = math.hypot(dx, dy)
        if amount <= 0.0 or distance > self.resource_config.sensor_range:
            return (0.0, 0.0, 0.0)
        if distance == 0.0:
            return (0.0, 0.0, 1.0)
        return (dx / distance, dy / distance, 1.0 - distance / self.resource_config.sensor_range)

    def sense(self, entity_id: int) -> SensorReadings:
        """Read existing raw signals without mutating authoritative state."""
        if not self.population.is_active(entity_id):
            raise ValueError("cannot sense for a tombstoned entity")
        state = self.population.state(entity_id)
        phenotype = founder_phenotype(self.genome(entity_id))
        food_x, food_y, food_energy = self._edible_resource()
        food_dx, food_dy, food_intensity = self._resource_signal(state, food_x, food_y, food_energy)
        water_dx, water_dy, water_intensity = self._resource_signal(
            state, self.resource_config.water_x, self.resource_config.water_y, self.water_amount
        )
        return SensorReadings(
            energy_fraction=state.physiology.energy / phenotype.physiology.max_energy,
            hydration_fraction=state.physiology.hydration / phenotype.physiology.max_hydration,
            injury_fraction=state.physiology.injury / phenotype.physiology.max_injury,
            food_dx=food_dx,
            food_dy=food_dy,
            food_intensity=food_intensity,
            water_dx=water_dx,
            water_dy=water_dy,
            water_intensity=water_intensity,
            boundary_contact=self._boundary_contacts[entity_id],
        )

    def _validate_initial(self, initial: InitialOrganismConfig, genome: Genome) -> None:
        phenotype = founder_phenotype(genome)
        if (
            not 0.0 <= initial.x <= self.world_config.width_meters
            or not 0.0 <= initial.y <= self.world_config.height_meters
        ):
            raise ValueError("founder must be inside the world")
        if not 0.0 < initial.energy <= phenotype.physiology.max_energy:
            raise ValueError("founder energy must be positive and within genome capacity")
        if not 0.0 < initial.hydration <= phenotype.physiology.max_hydration:
            raise ValueError("founder hydration must be positive and within genome capacity")
        if not 0.0 <= initial.injury < phenotype.physiology.max_injury:
            raise ValueError("founder injury must be below lethal injury")

    def _insert(
        self,
        genome: Genome,
        initial: InitialOrganismConfig,
        *,
        parent_ids: tuple[int, ...],
        founder_label: str,
        root_founder: int | None,
    ) -> int:
        entity_id = self.population.insert(
            WormState(
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
        )
        self._genomes[genome.genome_id] = genome
        self._genome_by_entity[entity_id] = genome.genome_id
        self._founder_label_by_entity[entity_id] = founder_label
        if root_founder is not None:
            self._root_founder_by_entity[entity_id] = root_founder
        self._boundary_contacts[entity_id] = False
        self._next_reproduction_step[entity_id] = 0
        self.lineages.add(entity_id, genome.genome_id, parent_ids, self._step_index)
        return entity_id

    @staticmethod
    def _distance(first: WormState, second: WormState) -> float:
        return math.hypot(first.x - second.x, first.y - second.y)

    def _move(self, entity_id: int, action: WormAction) -> WormState:
        state = self.population.state(entity_id)
        body = founder_phenotype(self.genome(entity_id)).body
        dt = self.world_config.timestep_seconds
        forward = 0.0 if action.rest else action.forward
        turn = 0.0 if action.rest else action.turn
        state.heading_radians += turn * body.max_turn_rate * dt
        state.heading_radians = math.atan2(
            math.sin(state.heading_radians), math.cos(state.heading_radians)
        )
        distance = forward * body.max_speed * dt
        target_x = state.x + math.cos(state.heading_radians) * distance
        target_y = state.y + math.sin(state.heading_radians) * distance
        state.x = min(self.world_config.width_meters, max(0.0, target_x))
        state.y = min(self.world_config.height_meters, max(0.0, target_y))
        self._boundary_contacts[entity_id] = state.x != target_x or state.y != target_y
        return state

    def _near(self, state: WormState, x: float, y: float) -> bool:
        return math.hypot(state.x - x, state.y - y) <= self.resource_config.interaction_radius

    def _edible_resource(self) -> tuple[float, float, float]:
        if self.plant_patch is not None:
            return (
                self.plant_patch.config.x,
                self.plant_patch.config.y,
                self.plant_patch.biomass_energy,
            )
        return (
            self.resource_config.food_x,
            self.resource_config.food_y,
            self.food_energy,
        )

    def advance(self, actions: Mapping[int, PopulationAction]) -> PopulationTransition:
        active_ids = self.population.active_entity_ids()
        if set(actions) != set(active_ids):
            raise ValueError("actions must contain exactly the active entity IDs")
        states = {
            entity_id: self._move(entity_id, actions[entity_id].motion) for entity_id in active_ids
        }
        dt = self.world_config.timestep_seconds
        plant_growth: PlantGrowth | None = None
        if self.plant_patch is not None:
            plant_growth = self.plant_patch.grow(dt)
        food_x, food_y, edible_energy = self._edible_resource()
        food_claims: dict[int, float] = {}
        water_claims: dict[int, float] = {}
        for entity_id in active_ids:
            state = states[entity_id]
            phenotype = founder_phenotype(self.genome(entity_id))
            food_claims[entity_id] = (
                min(
                    self.resource_config.eat_rate * dt,
                    (phenotype.physiology.max_energy - state.physiology.energy)
                    / self.resource_config.food_assimilation_efficiency,
                )
                if actions[entity_id].motion.eat and self._near(state, food_x, food_y)
                else 0.0
            )
            water_claims[entity_id] = (
                min(
                    self.resource_config.drink_rate * dt,
                    phenotype.physiology.max_hydration - state.physiology.hydration,
                )
                if actions[entity_id].motion.drink
                and self._near(state, self.resource_config.water_x, self.resource_config.water_y)
                else 0.0
            )
        food = _fair_allocations(food_claims, edible_energy)
        water = _fair_allocations(water_claims, self.water_amount)
        food_consumed = sum(food.values())
        if self.plant_patch is not None:
            self.plant_patch.consume(food_consumed)
        else:
            self.food_energy -= food_consumed
        self.water_amount -= sum(water.values())
        next_step = self._step_index + 1
        deaths: list[int] = []
        events: list[SimulationEvent] = []
        if self.plant_patch is not None and plant_growth is not None:
            events.append(
                self._event(
                    "plant.step",
                    0,
                    {
                        "biomass_after": self.plant_patch.biomass_energy,
                        "biomass_before": plant_growth.biomass_before,
                        "biomass_consumed": food_consumed,
                        "biomass_grown": plant_growth.biomass_grown,
                        "light_used": plant_growth.light_used,
                        "nutrients_used": plant_growth.nutrients_used,
                        "water_used": plant_growth.water_used,
                    },
                    step=next_step,
                )
            )
        for entity_id in active_ids:
            state = states[entity_id]
            action = actions[entity_id].motion
            phenotype = founder_phenotype(self.genome(entity_id))
            energy_gain = food[entity_id] * self.resource_config.food_assimilation_efficiency
            food_waste = food[entity_id] - energy_gain
            delta = apply_physiology(
                state.physiology,
                phenotype.physiology,
                timestep_seconds=dt,
                movement_effort=0.0 if action.rest else abs(action.forward),
                rest=action.rest,
                energy_gain=energy_gain,
                hydration_gain=water[entity_id],
                food_waste=food_waste,
            )
            state.physiology.age_seconds = (
                next_step * dt - self.lineages.record(entity_id).birth_step * dt
            )
            self.energy_dissipated += delta.energy_dissipated
            self.hydration_dissipated += delta.hydration_dissipated
            self.population.update(entity_id, state)
            events.append(
                self._event(
                    "organism.step",
                    entity_id,
                    {
                        "action": actions[entity_id].to_dict(),
                        "food_removed": food[entity_id],
                        "water_removed": water[entity_id],
                        "genome_id": self._genome_by_entity[entity_id],
                    },
                    step=next_step,
                )
            )
            if delta.death_transition:
                deaths.append(entity_id)
        self._step_index = next_step
        for entity_id in deaths:
            state = self.population.state(entity_id)
            physical_biomass = state.physiology.energy
            transfer: DetritusTransfer | None = None
            if self.detritus_pool is not None:
                transfer = self.detritus_pool.transfer_from_death(physical_biomass)
                self.energy_dissipated += transfer.energy_unrecovered
                state.physiology.energy = 0.0
                self.population.update(entity_id, state)
            self.population.tombstone(entity_id)
            self.lineages.mark_death(entity_id, self._step_index)
            self.death_count += 1
            events.append(
                self._event(
                    "organism.died",
                    entity_id,
                    {
                        "genome_id": self._genome_by_entity[entity_id],
                        "lineage_id": self.lineages.record(entity_id).lineage_id,
                    },
                )
            )
            if transfer is not None:
                assert self.detritus_pool is not None
                events.append(
                    self._event(
                        "detritus.transfer",
                        entity_id,
                        {
                            "biomass_transferred": transfer.biomass_transferred,
                            "detritus_after": self.detritus_pool.detritus,
                            "energy_unrecovered": transfer.energy_unrecovered,
                            "physical_biomass": transfer.physical_biomass,
                        },
                    )
                )
        if self.detritus_pool is not None:
            assert self.plant_patch is not None
            decay = self.detritus_pool.decay(dt)
            self.plant_patch.receive_nutrients(decay.nutrients_returned)
            events.append(
                self._event(
                    "detritus.step",
                    0,
                    {
                        "decay_loss": decay.decay_loss,
                        "detritus_after": self.detritus_pool.detritus,
                        "detritus_before": decay.detritus_before,
                        "nutrients_returned": decay.nutrients_returned,
                        "plant_nutrients_after": self.plant_patch.nutrients,
                    },
                )
            )
        births: list[int] = []
        if len(self.population) < self.reproduction_config.maximum_population:
            births.extend(self._reproduce(actions, events))
        return PopulationTransition(tuple(events), tuple(births), tuple(deaths))

    def _event(
        self,
        event_type: str,
        entity_id: int,
        data: dict[str, JsonValue],
        *,
        step: int | None = None,
    ) -> SimulationEvent:
        payload: dict[str, JsonValue] = {"entity_id": entity_id, **data}
        event = SimulationEvent(
            step_index=self._step_index if step is None else step,
            sequence=self._event_sequence,
            event_type=event_type,
            data=payload,
        )
        self._event_sequence += 1
        return event

    def _eligible(self, entity_id: int) -> bool:
        state = self.population.state(entity_id)
        phenotype = founder_phenotype(self.genome(entity_id))
        return (
            self.population.is_active(entity_id)
            and state.physiology.age_seconds >= self.reproduction_config.minimum_age_seconds
            and self._step_index >= self._next_reproduction_step[entity_id]
            and state.physiology.energy >= phenotype.fertility_energy
            and state.physiology.hydration
            >= self.genome(entity_id).max_hydration
            * self.genome(entity_id).offspring_energy_fraction
        )

    def _reproduce(
        self, actions: Mapping[int, PopulationAction], events: list[SimulationEvent]
    ) -> list[int]:
        requests: list[tuple[int, ...]] = []
        active = set(self.population.active_entity_ids())
        if self.reproduction_config.mode == "asexual":
            requests = [
                (entity_id,)
                for entity_id in sorted(active)
                if actions[entity_id].reproduce and self._eligible(entity_id)
            ]
        else:
            used: set[int] = set()
            for first in sorted(active):
                second = actions[first].mate_id
                if (
                    second is None
                    or second not in active
                    or first in used
                    or second in used
                    or first >= second
                ):
                    continue
                if (
                    actions[second].mate_id != first
                    or not actions[first].reproduce
                    or not actions[second].reproduce
                ):
                    continue
                if not self._eligible(first) or not self._eligible(second):
                    continue
                if (
                    self._distance(self.population.state(first), self.population.state(second))
                    > self.reproduction_config.interaction_radius
                ):
                    continue
                if not compatible(
                    self.genome(first),
                    self.genome(second),
                    self.reproduction_config.maximum_compatibility_distance,
                ):
                    continue
                requests.append((first, second))
                used.update((first, second))
        births: list[int] = []
        for parents in requests:
            if len(self.population) >= self.reproduction_config.maximum_population:
                break
            rng = self._streams.stream("inheritance")
            if self.reproduction_config.heritability_enabled:
                child_genome = inherit_genome(
                    self.genome(parents[0]),
                    self.genome(parents[1]) if len(parents) == 2 else None,
                    rng,
                    mutation_enabled=self.reproduction_config.mutation_enabled,
                )
            else:
                child_genome = self._founder_genomes[rng.randrange(len(self._founder_genomes))]
            child_phenotype = founder_phenotype(child_genome)
            child_energy = child_phenotype.offspring_energy
            child_hydration = child_genome.max_hydration * child_genome.offspring_energy_fraction
            shares = len(parents)
            if any(
                self.population.state(parent).physiology.energy < child_energy / shares
                or self.population.state(parent).physiology.hydration < child_hydration / shares
                for parent in parents
            ):
                continue
            for parent in parents:
                state = self.population.state(parent)
                state.physiology.energy -= child_energy / shares
                state.physiology.hydration -= child_hydration / shares
                self.population.update(parent, state)
                cooldown_steps = math.ceil(
                    self.reproduction_config.cooldown_seconds / self.world_config.timestep_seconds
                )
                self._next_reproduction_step[parent] = self._step_index + cooldown_steps
            first_state = self.population.state(parents[0])
            angle = rng.random() * math.tau
            radius = min(0.1, self.reproduction_config.interaction_radius / 2.0)
            initial = InitialOrganismConfig(
                x=min(
                    self.world_config.width_meters,
                    max(0.0, first_state.x + math.cos(angle) * radius),
                ),
                y=min(
                    self.world_config.height_meters,
                    max(0.0, first_state.y + math.sin(angle) * radius),
                ),
                heading_radians=angle,
                energy=child_energy,
                hydration=child_hydration,
            )
            root = self.root_founder(parents[0])
            label = self._founder_label_by_entity[parents[0]]
            child_id = self._insert(
                child_genome,
                initial,
                parent_ids=tuple(sorted(parents)),
                founder_label=label,
                root_founder=root,
            )
            self._next_reproduction_step[child_id] = self._step_index + math.ceil(
                self.reproduction_config.minimum_age_seconds / self.world_config.timestep_seconds
            )
            self.birth_count += 1
            births.append(child_id)
            record = self.lineages.record(child_id)
            events.append(
                self._event(
                    "organism.born",
                    child_id,
                    {
                        "genome_id": child_genome.genome_id,
                        "lineage_id": record.lineage_id,
                        "parent_ids": list(record.parent_ids),
                        "root_founder_id": root,
                    },
                )
            )
        return births

    def state_dict(self) -> dict[str, JsonValue]:
        organisms: list[JsonValue] = []
        for entity_id in self.population.entity_ids():
            state = self.population.state(entity_id)
            genome = self.genome(entity_id)
            body = founder_phenotype(genome).body
            organisms.append(
                {
                    **self.lineages.record(entity_id).to_dict(),
                    "active": self.population.is_active(entity_id),
                    "energy": state.physiology.energy,
                    "hydration": state.physiology.hydration,
                    "injury": state.physiology.injury,
                    "age_seconds": state.physiology.age_seconds,
                    "heading_radians": state.heading_radians,
                    "x": state.x,
                    "y": state.y,
                    "root_founder_id": self.root_founder(entity_id),
                    "segments": [{"x": x, "y": y} for x, y in state.segment_positions(body)],
                }
            )
        resources: dict[str, JsonValue] = {
            "food_energy": self.food_energy,
            "water_amount": self.water_amount,
        }
        if self.plant_patch is not None:
            resources["plant_patch"] = self.plant_patch.state_dict()
        if self.detritus_pool is not None:
            resources["detritus"] = self.detritus_pool.state_dict()
        return {
            "accounting": {
                "energy_dissipated": self.energy_dissipated,
                "hydration_dissipated": self.hydration_dissipated,
            },
            "lifecycle": {"births": self.birth_count, "deaths": self.death_count},
            "organisms": organisms,
            "resources": resources,
        }

    def snapshot(self) -> WorldSnapshot:
        return WorldSnapshot(self._step_index, self.elapsed_seconds, self.state_dict())
