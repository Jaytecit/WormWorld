"""Unit tests for deterministic lifetime-only physiology."""

import math

from worm_world.organisms import PhysiologyConfig, PhysiologyState, apply_physiology


def test_metabolism_is_deterministic_and_scales_with_timestep() -> None:
    config = PhysiologyConfig(
        basal_energy_rate=2.0,
        basal_hydration_rate=1.0,
        movement_energy_rate=0.0,
    )
    one = PhysiologyState(energy=10.0, hydration=10.0)
    two = PhysiologyState(energy=10.0, hydration=10.0)

    apply_physiology(
        one,
        config,
        timestep_seconds=1.0,
        movement_effort=0.0,
        rest=False,
        energy_gain=0.0,
        hydration_gain=0.0,
        food_waste=0.0,
    )
    for _ in range(2):
        apply_physiology(
            two,
            config,
            timestep_seconds=0.5,
            movement_effort=0.0,
            rest=False,
            energy_gain=0.0,
            hydration_gain=0.0,
            food_waste=0.0,
        )

    assert one.energy == two.energy == 8.0
    assert one.hydration == two.hydration == 9.0
    assert one.age_seconds == two.age_seconds == 1.0


def test_signals_are_bounded_and_death_transition_is_idempotent() -> None:
    config = PhysiologyConfig(basal_energy_rate=1.0, basal_hydration_rate=0.0)
    state = PhysiologyState(energy=0.25, hydration=1.0, injury=-2.0)
    first = apply_physiology(
        state,
        config,
        timestep_seconds=1.0,
        movement_effort=0.0,
        rest=False,
        energy_gain=0.0,
        hydration_gain=0.0,
        food_waste=0.0,
    )
    second = apply_physiology(
        state,
        config,
        timestep_seconds=1.0,
        movement_effort=0.0,
        rest=False,
        energy_gain=0.0,
        hydration_gain=0.0,
        food_waste=0.0,
    )

    assert state.energy == 0.0
    assert state.injury == 0.0
    assert state.alive is False
    assert first.death_transition is True
    assert second.death_transition is False
    assert second.energy_dissipated == 0.0


def test_rest_reduces_only_baseline_cost_and_movement_has_explicit_cost() -> None:
    config = PhysiologyConfig(
        basal_energy_rate=2.0,
        basal_hydration_rate=0.0,
        movement_energy_rate=3.0,
        resting_metabolism_multiplier=0.25,
    )
    moving = PhysiologyState(energy=20.0, hydration=20.0)
    resting = PhysiologyState(energy=20.0, hydration=20.0)
    apply_physiology(
        moving,
        config,
        timestep_seconds=1.0,
        movement_effort=1.0,
        rest=False,
        energy_gain=0.0,
        hydration_gain=0.0,
        food_waste=0.0,
    )
    apply_physiology(
        resting,
        config,
        timestep_seconds=1.0,
        movement_effort=0.0,
        rest=True,
        energy_gain=0.0,
        hydration_gain=0.0,
        food_waste=0.0,
    )

    assert math.isclose(moving.energy, 15.0)
    assert math.isclose(resting.energy, 19.5)
