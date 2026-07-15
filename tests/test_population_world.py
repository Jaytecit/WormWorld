"""Phase 2 population boundary and deterministic replay tests."""

from worm_world.experiments import WorldConfig
from worm_world.organisms import BodyConfig, PhysiologyConfig, WormAction
from worm_world.world import InitialOrganismConfig, ResourceFieldConfig, SandboxWorld


def make_world(*, lethal: bool = False) -> SandboxWorld:
    return SandboxWorld(
        WorldConfig(width_meters=10.0, height_meters=10.0, timestep_seconds=1.0),
        BodyConfig(max_speed=1.0, max_turn_rate=1.0),
        PhysiologyConfig(
            basal_energy_rate=1.0 if lethal else 0.0,
            basal_hydration_rate=0.0,
            movement_energy_rate=0.0,
        ),
        ResourceFieldConfig(),
        InitialOrganismConfig(x=1.0, y=1.0, energy=0.5 if lethal else 10.0),
    )


def test_action_mapping_order_does_not_change_simultaneous_step() -> None:
    first = make_world()
    first_second_id = first.add_organism(InitialOrganismConfig(x=8.0, y=8.0))
    second = make_world()
    second_second_id = second.add_organism(InitialOrganismConfig(x=8.0, y=8.0))
    assert first_second_id == second_second_id == 2

    first_result = first.advance_population({1: WormAction(forward=1.0), 2: WormAction(turn=0.5)})
    second_result = second.advance_population({2: WormAction(turn=0.5), 1: WormAction(forward=1.0)})

    assert first_result == second_result
    assert first.population_snapshot().to_json() == second.population_snapshot().to_json()
    assert tuple(result.entity_id for result in first_result.outcomes) == (1, 2)
    assert first.step_index == 1
    assert all(
        first.population.state(entity_id).physiology.age_seconds == 1.0 for entity_id in (1, 2)
    )


def test_actions_must_match_active_ids_exactly() -> None:
    world = make_world()
    world.add_organism(InitialOrganismConfig(x=2.0, y=2.0))

    try:
        world.advance_population({1: WormAction()})
    except ValueError as error:
        assert "exactly the active entity IDs" in str(error)
    else:
        raise AssertionError("missing entity action was accepted")


def test_death_is_tombstoned_and_emitted_exactly_once() -> None:
    world = make_world(lethal=True)
    first = world.advance_population({1: WormAction()})
    second = world.advance_population({})

    assert [event.event_type for event in first.events] == ["organism.step", "organism.died"]
    assert second.events == ()
    assert world.population.active_entity_ids() == ()
    record = world.population_snapshot().state["population"]
    assert isinstance(record, list)
    assert record[0]["entity_id"] == 1  # type: ignore[index]
    assert record[0]["active"] is False  # type: ignore[index]


def test_multi_organism_event_and_snapshot_replay_is_byte_deterministic() -> None:
    def simulate() -> tuple[tuple[str, ...], tuple[str, ...]]:
        world = make_world()
        world.add_organism(InitialOrganismConfig(x=8.0, y=8.0))
        snapshots = [world.population_snapshot().to_json()]
        events: list[str] = []
        for actions in (
            {2: WormAction(forward=-0.5), 1: WormAction(forward=1.0)},
            {1: WormAction(turn=0.25), 2: WormAction(rest=True)},
        ):
            result = world.advance_population(actions)
            events.extend(event.to_json() for event in result.events)
            snapshots.append(world.population_snapshot().to_json())
        return tuple(events), tuple(snapshots)

    assert simulate() == simulate()
