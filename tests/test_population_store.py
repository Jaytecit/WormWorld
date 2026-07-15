"""Deterministic structure-of-arrays population storage tests."""

import pytest

from worm_world.organisms import PhysiologyState, PopulationStore, WormState


def state(x: float, *, alive: bool = True) -> WormState:
    return WormState(x, 2.0, 0.0, PhysiologyState(10.0, 10.0, alive=alive))


def test_ids_are_monotonic_and_iteration_is_stable_after_tombstoning() -> None:
    population = PopulationStore()
    first = population.insert(state(1.0))
    second = population.insert(state(2.0))
    third = population.insert(state(3.0))

    assert (first, second, third) == (1, 2, 3)
    assert population.active_entity_ids() == (1, 2, 3)
    assert population.tombstone(second) is True
    assert population.tombstone(second) is False
    assert population.active_entity_ids() == (1, 3)
    assert population.entity_ids() == (1, 2, 3)
    assert population.insert(state(4.0)) == 4
    assert population.active_entity_ids() == (1, 3, 4)


def test_state_is_detached_and_tombstone_records_are_retained() -> None:
    population = PopulationStore()
    entity_id = population.insert(state(1.0))
    detached = population.state(entity_id)
    detached.x = 99.0

    assert population.state(entity_id).x == 1.0
    population.tombstone(entity_id)
    assert population.state(entity_id).physiology.alive is False
    assert population.records()[0]["active"] is False  # type: ignore[index]
    with pytest.raises(ValueError, match="tombstoned"):
        population.update(entity_id, state(5.0))


def test_dead_states_cannot_be_inserted() -> None:
    with pytest.raises(ValueError, match="must be alive"):
        PopulationStore().insert(state(1.0, alive=False))
