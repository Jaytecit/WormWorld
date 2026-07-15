"""Behaviour and invariant tests for the single-organism sandbox."""

import math

from worm_world.experiments import WorldConfig
from worm_world.organisms import BodyConfig, PhysiologyConfig, WormAction
from worm_world.world import InitialOrganismConfig, ResourceFieldConfig, SandboxWorld


def make_world(
    *,
    initial: InitialOrganismConfig | None = None,
    resources: ResourceFieldConfig | None = None,
    physiology: PhysiologyConfig | None = None,
    timestep: float = 1.0,
) -> SandboxWorld:
    return SandboxWorld(
        WorldConfig(width_meters=10.0, height_meters=10.0, timestep_seconds=timestep),
        BodyConfig(max_speed=1.0, max_turn_rate=1.0),
        physiology or PhysiologyConfig(),
        resources or ResourceFieldConfig(),
        initial or InitialOrganismConfig(),
    )


def test_action_sequence_causes_predictable_movement_and_boundary_contact() -> None:
    world = make_world(initial=InitialOrganismConfig(x=9.5, y=5.0, energy=50.0, hydration=50.0))
    first = world.advance(WormAction(forward=0.25))
    second = world.advance(WormAction(forward=1.0))

    assert math.isclose(first.distance_moved, 0.25)
    assert world.organism.x == 10.0
    assert math.isclose(second.distance_moved, 0.25)
    assert second.sensors.boundary_contact is True


def test_eating_conserves_resource_energy_and_dissipation() -> None:
    physiology = PhysiologyConfig(
        basal_energy_rate=0.0,
        basal_hydration_rate=0.0,
        movement_energy_rate=0.0,
    )
    resources = ResourceFieldConfig(
        food_x=5.0,
        food_y=5.0,
        food_energy=10.0,
        eat_rate=5.0,
        food_assimilation_efficiency=0.8,
    )
    world = make_world(
        initial=InitialOrganismConfig(energy=10.0, hydration=10.0),
        resources=resources,
        physiology=physiology,
    )
    initial_total = world.organism.physiology.energy + world.food_energy
    result = world.advance(WormAction(eat=True))
    final_total = world.organism.physiology.energy + world.food_energy + world.energy_dissipated

    assert math.isclose(result.food_removed, 5.0)
    assert math.isclose(world.organism.physiology.energy, 14.0)
    assert math.isclose(world.food_energy, 5.0)
    assert math.isclose(final_total, initial_total)


def test_drinking_conserves_finite_water_and_respects_capacity() -> None:
    physiology = PhysiologyConfig(basal_energy_rate=0.0, basal_hydration_rate=0.0)
    resources = ResourceFieldConfig(water_x=5.0, water_y=5.0, water_amount=20.0, drink_rate=50.0)
    world = make_world(
        initial=InitialOrganismConfig(energy=10.0, hydration=98.0),
        resources=resources,
        physiology=physiology,
    )
    result = world.advance(WormAction(drink=True))

    assert math.isclose(result.water_removed, 2.0)
    assert math.isclose(world.organism.physiology.hydration, 100.0)
    assert math.isclose(world.water_amount, 18.0)


def test_sensors_expose_gradients_and_bounded_interoception() -> None:
    world = make_world(timestep=0.1)
    sensors = world.sense()

    assert math.isclose(sensors.food_dx, 1.0)
    assert math.isclose(sensors.water_dx, -1.0)
    assert math.isclose(sensors.food_intensity, 0.8)
    assert 0.0 <= sensors.energy_fraction <= 1.0
    assert 0.0 <= sensors.hydration_fraction <= 1.0
    assert 0.0 <= sensors.injury_fraction <= 1.0


def test_dead_organism_stops_acting_and_does_not_emit_a_second_death() -> None:
    world = make_world(
        initial=InitialOrganismConfig(energy=0.1, hydration=10.0),
        physiology=PhysiologyConfig(
            basal_energy_rate=1.0,
            basal_hydration_rate=0.0,
            movement_energy_rate=0.0,
        ),
    )
    first = world.advance(WormAction())
    x_at_death = world.organism.x
    second = world.advance(WormAction(forward=1.0, eat=True, drink=True))

    assert first.death_transition is True
    assert second.death_transition is False
    assert world.organism.x == x_at_death
    assert world.organism.physiology.age_seconds == 1.0


def test_snapshot_contains_segmented_body_resources_sensors_and_accounting() -> None:
    snapshot = make_world().snapshot()
    organism = snapshot.state["organism"]

    assert isinstance(organism, dict)
    segments = organism["segments"]
    assert isinstance(segments, list)
    assert len(segments) == 4
    assert set(snapshot.state) == {"accounting", "organism", "resources", "sensors"}


def test_energy_and_water_accounting_is_conserved_across_mixed_actions() -> None:
    resources = ResourceFieldConfig(
        food_x=5.0,
        food_y=5.0,
        food_energy=10.0,
        water_x=5.0,
        water_y=5.0,
        water_amount=10.0,
        eat_rate=1.0,
        drink_rate=1.0,
    )
    world = make_world(
        initial=InitialOrganismConfig(energy=10.0, hydration=10.0),
        resources=resources,
        physiology=PhysiologyConfig(
            basal_energy_rate=0.2,
            basal_hydration_rate=0.1,
            movement_energy_rate=0.3,
        ),
        timestep=0.25,
    )
    initial_energy = world.organism.physiology.energy + world.food_energy
    initial_water = world.organism.physiology.hydration + world.water_amount
    for action in (
        WormAction(eat=True, drink=True),
        WormAction(forward=0.5),
        WormAction(rest=True),
    ):
        world.advance(action)

    assert math.isclose(
        world.organism.physiology.energy + world.food_energy + world.energy_dissipated,
        initial_energy,
    )
    assert math.isclose(
        world.organism.physiology.hydration + world.water_amount + world.hydration_dissipated,
        initial_water,
    )
