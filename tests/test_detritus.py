"""Phase 4 deterministic detritus and nutrient-recycling tests."""

from __future__ import annotations

import math

import pytest

from worm_world.experiments import WorldConfig
from worm_world.genetics import Genome
from worm_world.world import (
    DetritusConfig,
    DetritusPool,
    Founder,
    InitialOrganismConfig,
    PlantPatchConfig,
    PopulationAction,
    PopulationWorld,
    ReproductionConfig,
    ResourceFieldConfig,
)


def _founder(
    label: str,
    *,
    energy: float = 80.0,
    hydration: float = 80.0,
    basal_energy_rate: float = 0.0,
    basal_hydration_rate: float = 0.0,
) -> Founder:
    return Founder(
        Genome(
            basal_energy_rate=basal_energy_rate,
            basal_hydration_rate=basal_hydration_rate,
            movement_energy_rate=0.0,
            mutation_scale=0.0,
        ),
        InitialOrganismConfig(x=5.0, y=5.0, energy=energy, hydration=hydration),
        label,
    )


def _world(
    *,
    founders: list[Founder] | None = None,
    plant: PlantPatchConfig | None = None,
    detritus: DetritusConfig | None = None,
) -> PopulationWorld:
    members = founders if founders is not None else [_founder("0")]
    return PopulationWorld(
        seed=42,
        world_config=WorldConfig(width_meters=10.0, height_meters=10.0, timestep_seconds=0.5),
        resource_config=ResourceFieldConfig(
            food_x=5.0,
            food_y=5.0,
            food_energy=0.0,
            water_amount=0.0,
        ),
        reproduction_config=ReproductionConfig(maximum_population=len(members)),
        founders=members,
        plant_config=plant,
        detritus_config=detritus,
    )


def _enabled_plant(
    *,
    initial_biomass_energy: float = 0.0,
    initial_nutrients: float = 0.0,
    maximum_biomass_energy: float = 100.0,
    maximum_growth_rate: float = 0.0,
) -> PlantPatchConfig:
    return PlantPatchConfig(
        enabled=True,
        x=5.0,
        y=5.0,
        initial_biomass_energy=initial_biomass_energy,
        maximum_biomass_energy=maximum_biomass_energy,
        maximum_growth_rate=maximum_growth_rate,
        initial_nutrients=initial_nutrients,
    )


def test_no_death_means_no_detritus_transfer() -> None:
    world = _world(
        plant=_enabled_plant(),
        detritus=DetritusConfig(enabled=True, maximum_decay_rate=0.0),
    )
    assert world.detritus_pool is not None

    transition = world.advance({1: PopulationAction()})

    assert world.death_count == 0
    assert world.detritus_pool.detritus == 0.0
    assert world.detritus_pool.total_biomass_transferred == 0.0
    assert all(event.event_type != "detritus.transfer" for event in transition.events)
    assert transition.events[-1].event_type == "detritus.step"
    assert transition.events[-1].data["decay_loss"] == 0.0


def test_death_transfers_documented_biomass_fraction_exactly_once() -> None:
    world = _world(
        founders=[_founder("thirst", energy=40.0, hydration=0.2, basal_hydration_rate=1.0)],
        plant=_enabled_plant(),
        detritus=DetritusConfig(
            enabled=True,
            death_biomass_fraction=0.25,
            maximum_decay_rate=0.0,
        ),
    )
    assert world.detritus_pool is not None

    first = world.advance({1: PopulationAction()})

    assert world.death_count == 1
    assert world.population.active_entity_ids() == ()
    transfer_events = [event for event in first.events if event.event_type == "detritus.transfer"]
    assert len(transfer_events) == 1
    assert transfer_events[0].data["physical_biomass"] == 40.0
    assert transfer_events[0].data["biomass_transferred"] == 10.0
    assert transfer_events[0].data["energy_unrecovered"] == 30.0
    assert world.detritus_pool.detritus == 10.0
    assert world.detritus_pool.total_biomass_transferred == 10.0
    assert world.energy_dissipated == 30.0
    assert world.population.state(1).physiology.energy == 0.0
    assert sum(1 for event in first.events if event.event_type == "detritus.transfer") == 1


def test_decay_is_bounded_and_returns_nutrients_to_plant() -> None:
    pool = DetritusPool(
        DetritusConfig(
            enabled=True,
            initial_detritus=5.0,
            maximum_decay_rate=2.0,
            nutrients_per_detritus=3.0,
        )
    )

    first = pool.decay(1.0)
    second = pool.decay(1.0)
    third = pool.decay(1.0)

    assert first.decay_loss == 2.0
    assert first.nutrients_returned == 6.0
    assert second.decay_loss == 2.0
    assert third.decay_loss == 1.0
    assert third.nutrients_returned == 3.0
    assert pool.detritus == 0.0
    assert pool.total_decay_loss == 5.0
    assert pool.total_nutrients_returned == 15.0


def test_world_decay_returns_nutrients_into_plant_patch() -> None:
    world = _world(
        plant=_enabled_plant(initial_nutrients=1.0),
        detritus=DetritusConfig(
            enabled=True,
            initial_detritus=4.0,
            maximum_decay_rate=2.0,
            nutrients_per_detritus=0.5,
        ),
    )
    assert world.plant_patch is not None
    assert world.detritus_pool is not None

    transition = world.advance({1: PopulationAction()})

    assert world.detritus_pool.detritus == 3.0
    assert world.plant_patch.nutrients == 1.5
    step = transition.events[-1]
    assert step.event_type == "detritus.step"
    assert step.data["decay_loss"] == 1.0
    assert step.data["nutrients_returned"] == 0.5
    assert step.data["plant_nutrients_after"] == 1.5


def test_mass_and_energy_accounting_close_across_death_and_decay() -> None:
    world = _world(
        founders=[_founder("thirst", energy=20.0, hydration=0.2, basal_hydration_rate=1.0)],
        plant=_enabled_plant(initial_nutrients=0.0),
        detritus=DetritusConfig(
            enabled=True,
            death_biomass_fraction=1.0,
            maximum_decay_rate=100.0,
            nutrients_per_detritus=1.0,
        ),
    )
    assert world.plant_patch is not None
    assert world.detritus_pool is not None
    initial = 20.0

    world.advance({1: PopulationAction()})

    final = (
        world.energy_dissipated
        + world.detritus_pool.detritus
        + world.plant_patch.nutrients
        + sum(
            world.population.state(entity_id).physiology.energy
            for entity_id in world.population.active_entity_ids()
        )
    )
    assert math.isclose(initial, final)
    assert world.detritus_pool.total_biomass_transferred == 20.0
    assert world.plant_patch.nutrients == 20.0


def test_simultaneous_deaths_transfer_in_stable_order() -> None:
    world = _world(
        founders=[
            _founder("a", energy=10.0, hydration=0.2, basal_hydration_rate=1.0),
            _founder("b", energy=30.0, hydration=0.2, basal_hydration_rate=1.0),
        ],
        plant=_enabled_plant(),
        detritus=DetritusConfig(
            enabled=True,
            death_biomass_fraction=1.0,
            maximum_decay_rate=0.0,
        ),
    )
    assert world.detritus_pool is not None

    transition = world.advance({1: PopulationAction(), 2: PopulationAction()})
    transfers = [event for event in transition.events if event.event_type == "detritus.transfer"]

    assert [event.data["entity_id"] for event in transfers] == [1, 2]
    assert transfers[0].data["biomass_transferred"] == 10.0
    assert transfers[0].data["detritus_after"] == 10.0
    assert transfers[1].data["biomass_transferred"] == 30.0
    assert transfers[1].data["detritus_after"] == 40.0
    assert world.detritus_pool.detritus == 40.0


def test_config_identity_is_canonical_and_strict() -> None:
    config = DetritusConfig(enabled=True, initial_detritus=2.0, death_biomass_fraction=0.5)

    assert DetritusConfig.from_json(config.to_json()) == config
    assert DetritusConfig.from_json(config.to_json()).config_id == config.config_id
    with pytest.raises(ValueError, match="missing or unknown"):
        DetritusConfig.from_json(config.to_json()[:-1] + ',"extra":1}')
    with pytest.raises(ValueError, match="enabled must be a boolean"):
        DetritusConfig.from_json(config.to_json().replace('"enabled":true', '"enabled":1'))


def test_disabled_detritus_preserves_historical_events_and_snapshot_bytes() -> None:
    historical = _world(plant=_enabled_plant(initial_biomass_energy=1.0))
    explicitly_disabled = _world(
        plant=_enabled_plant(initial_biomass_energy=1.0),
        detritus=DetritusConfig(),
    )
    action = {1: PopulationAction()}

    historical_transition = historical.advance(action)
    disabled_transition = explicitly_disabled.advance(action)

    assert historical_transition == disabled_transition
    assert historical.snapshot().to_json() == explicitly_disabled.snapshot().to_json()
    resources = historical.snapshot().state["resources"]
    assert isinstance(resources, dict)
    assert "detritus" not in resources


def test_enabled_detritus_is_projected_into_snapshot_without_mutable_authority() -> None:
    world = _world(
        plant=_enabled_plant(),
        detritus=DetritusConfig(enabled=True, initial_detritus=3.0, maximum_decay_rate=0.0),
    )

    resources = world.snapshot().state["resources"]
    assert isinstance(resources, dict)
    detritus = resources["detritus"]
    assert isinstance(detritus, dict)
    assert detritus["detritus"] == 3.0
    detritus["detritus"] = 999.0
    assert world.detritus_pool is not None
    assert world.detritus_pool.detritus == 3.0


def test_enabled_detritus_requires_enabled_plant_patch() -> None:
    with pytest.raises(ValueError, match="requires an enabled plant patch"):
        _world(detritus=DetritusConfig(enabled=True))
