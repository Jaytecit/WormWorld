"""Phase 4 deterministic resource-limited plant patch tests."""

from __future__ import annotations

import math

import pytest

from worm_world.experiments import WorldConfig
from worm_world.genetics import Genome
from worm_world.organisms import WormAction
from worm_world.world import (
    Founder,
    InitialOrganismConfig,
    PlantPatch,
    PlantPatchConfig,
    PopulationAction,
    PopulationWorld,
    ReproductionConfig,
    ResourceFieldConfig,
)


def _founder(label: str) -> Founder:
    return Founder(
        Genome(
            basal_energy_rate=0.0,
            basal_hydration_rate=0.0,
            movement_energy_rate=0.0,
            mutation_scale=0.0,
        ),
        InitialOrganismConfig(x=5.0, y=5.0, energy=80.0, hydration=80.0),
        label,
    )


def _world(*, founders: int = 1, plant: PlantPatchConfig | None = None) -> PopulationWorld:
    return PopulationWorld(
        seed=42,
        world_config=WorldConfig(width_meters=10.0, height_meters=10.0, timestep_seconds=0.5),
        resource_config=ResourceFieldConfig(
            food_x=5.0,
            food_y=5.0,
            food_energy=0.0,
            water_amount=0.0,
        ),
        reproduction_config=ReproductionConfig(maximum_population=founders),
        founders=[_founder(str(index)) for index in range(founders)],
        plant_config=plant,
    )


def test_no_input_means_no_growth() -> None:
    patch = PlantPatch(
        PlantPatchConfig(enabled=True, initial_biomass_energy=2.0),
        world_width=10.0,
        world_height=10.0,
    )

    growth = patch.grow(1.0)

    assert growth.biomass_grown == 0.0
    assert patch.biomass_energy == 2.0


def test_growth_deducts_each_input_and_stops_at_capacity() -> None:
    patch = PlantPatch(
        PlantPatchConfig(
            enabled=True,
            initial_biomass_energy=9.0,
            maximum_biomass_energy=10.0,
            initial_light_energy=10.0,
            initial_water=10.0,
            initial_nutrients=10.0,
            maximum_growth_rate=4.0,
            light_per_biomass=2.0,
            water_per_biomass=3.0,
            nutrients_per_biomass=4.0,
        ),
        world_width=10.0,
        world_height=10.0,
    )

    growth = patch.grow(1.0)

    assert growth.biomass_grown == 1.0
    assert growth.light_used == 2.0
    assert growth.water_used == 3.0
    assert growth.nutrients_used == 4.0
    assert patch.biomass_energy == 10.0
    assert patch.light_energy == 8.0
    assert patch.water == 7.0
    assert patch.nutrients == 6.0
    assert patch.grow(1.0).biomass_grown == 0.0


def test_plant_food_uses_existing_fair_simultaneous_consumption() -> None:
    world = _world(
        founders=2,
        plant=PlantPatchConfig(
            enabled=True,
            x=5.0,
            y=5.0,
            initial_biomass_energy=1.0,
            maximum_biomass_energy=1.0,
            maximum_growth_rate=0.0,
        ),
    )
    before = [world.population.state(entity_id).physiology.energy for entity_id in (1, 2)]
    action = PopulationAction(WormAction(eat=True))

    transition = world.advance({2: action, 1: action})

    gains = [
        world.population.state(entity_id).physiology.energy - before[entity_id - 1]
        for entity_id in (1, 2)
    ]
    assert all(math.isclose(gain, 0.4) for gain in gains)
    assert world.plant_patch is not None
    assert world.plant_patch.biomass_energy == 0.0
    assert transition.events[0].event_type == "plant.step"
    assert transition.events[0].data["biomass_consumed"] == 1.0


def test_energy_and_plant_lifecycle_accounting_close() -> None:
    world = _world(
        plant=PlantPatchConfig(
            enabled=True,
            x=5.0,
            y=5.0,
            initial_biomass_energy=2.0,
            maximum_biomass_energy=2.0,
            maximum_growth_rate=0.0,
        )
    )
    assert world.plant_patch is not None
    initial = world.population.state(1).physiology.energy + world.plant_patch.biomass_energy

    world.advance({1: PopulationAction(WormAction(eat=True))})

    final = (
        world.population.state(1).physiology.energy
        + world.plant_patch.biomass_energy
        + world.energy_dissipated
    )
    assert math.isclose(initial, final)
    assert world.plant_patch.total_biomass_consumed == 2.0


def test_config_identity_is_canonical_and_strict() -> None:
    config = PlantPatchConfig(enabled=True, initial_light_energy=3.0)

    assert PlantPatchConfig.from_json(config.to_json()) == config
    assert PlantPatchConfig.from_json(config.to_json()).config_id == config.config_id
    with pytest.raises(ValueError, match="missing or unknown"):
        PlantPatchConfig.from_json(config.to_json()[:-1] + ',"extra":1}')
    with pytest.raises(ValueError, match="enabled must be a boolean"):
        PlantPatchConfig.from_json(config.to_json().replace('"enabled":true', '"enabled":1'))


def test_disabled_patch_preserves_historical_events_and_snapshot_bytes() -> None:
    historical = _world()
    explicitly_disabled = _world(plant=PlantPatchConfig())
    action = {1: PopulationAction()}

    historical_transition = historical.advance(action)
    disabled_transition = explicitly_disabled.advance(action)

    assert historical_transition == disabled_transition
    assert historical.snapshot().to_json() == explicitly_disabled.snapshot().to_json()


def test_enabled_patch_is_projected_into_snapshot_without_mutable_authority() -> None:
    world = _world(
        plant=PlantPatchConfig(
            enabled=True,
            initial_biomass_energy=2.0,
            maximum_biomass_energy=3.0,
            initial_light_energy=1.0,
            initial_water=1.0,
            initial_nutrients=1.0,
        )
    )

    resources = world.snapshot().state["resources"]

    assert isinstance(resources, dict)
    plant = resources["plant_patch"]
    assert isinstance(plant, dict)
    assert plant["biomass_energy"] == 2.0
    plant["biomass_energy"] = 999.0
    assert world.plant_patch is not None
    assert world.plant_patch.biomass_energy == 2.0


def test_enabled_patch_rejects_ambiguous_static_food_pool() -> None:
    with pytest.raises(ValueError, match="static food must be zero"):
        PopulationWorld(
            seed=1,
            world_config=WorldConfig(),
            resource_config=ResourceFieldConfig(food_energy=1.0),
            reproduction_config=ReproductionConfig(),
            founders=[_founder("one")],
            plant_config=PlantPatchConfig(enabled=True),
        )
