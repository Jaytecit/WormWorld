from typing import cast

from worm_world.experiments import WorldConfig
from worm_world.genetics import Genome
from worm_world.organisms import WormAction
from worm_world.world import (
    Founder,
    InitialOrganismConfig,
    PopulationAction,
    PopulationWorld,
    ReproductionConfig,
    ResourceFieldConfig,
)


def _founder(label: str, x: float = 5.0, *, metabolism: float = 0.0) -> Founder:
    return Founder(
        Genome(
            basal_energy_rate=metabolism,
            basal_hydration_rate=0.0,
            movement_energy_rate=0.0,
            mutation_scale=0.0,
        ),
        InitialOrganismConfig(x=x, y=5.0, energy=80.0, hydration=80.0),
        label,
    )


def _world(*founders: Founder, reproduction: ReproductionConfig | None = None) -> PopulationWorld:
    return PopulationWorld(
        seed=12,
        world_config=WorldConfig(timestep_seconds=0.5, width_meters=10, height_meters=10),
        resource_config=ResourceFieldConfig(food_energy=1.0, water_amount=1.0),
        reproduction_config=reproduction or ReproductionConfig(minimum_age_seconds=0.5),
        founders=founders,
    )


def test_shared_resource_allocation_is_simultaneous_and_fair() -> None:
    world = _world(_founder("a", 6.0), _founder("b", 6.0))
    before = {
        entity_id: world.population.state(entity_id).physiology.energy for entity_id in (1, 2)
    }
    action = PopulationAction(WormAction(eat=True))
    world.advance({2: action, 1: action})
    gains = [
        world.population.state(entity_id).physiology.energy - before[entity_id]
        for entity_id in (1, 2)
    ]
    assert abs(gains[0] - 0.4) < 1e-12
    assert abs(gains[1] - 0.4) < 1e-12
    assert world.food_energy == 0.0


def test_asexual_birth_funds_child_and_records_lineage_deterministically() -> None:
    worlds = [_world(_founder("root")) for _ in range(2)]
    snapshots: list[str] = []
    for world in worlds:
        transition = world.advance({1: PopulationAction(reproduce=True)})
        assert transition.births == (2,)
        child = world.population.state(2)
        parent = world.population.state(1)
        assert child.physiology.energy == 20.0
        assert parent.physiology.energy == 60.0
        assert world.lineages.record(2).parent_ids == (1,)
        assert world.root_founder(2) == 1
        snapshots.append(world.snapshot().to_json())
    assert snapshots[0] == snapshots[1]


def test_sexual_birth_requires_mutual_compatible_nearby_request() -> None:
    config = ReproductionConfig(mode="sexual", minimum_age_seconds=0.5, mutation_enabled=False)
    world = _world(_founder("one"), _founder("two", 5.1), reproduction=config)
    actions = {
        1: PopulationAction(reproduce=True, mate_id=2),
        2: PopulationAction(reproduce=True, mate_id=1),
    }
    transition = world.advance(actions)
    assert transition.births == (3,)
    assert world.lineages.record(3).parent_ids == (1, 2)


def test_death_tombstones_once_and_retains_genome_association() -> None:
    founder = Founder(
        Genome(basal_energy_rate=2.0, basal_hydration_rate=0.0, mutation_scale=0.0),
        InitialOrganismConfig(energy=1.0, hydration=10.0),
        "short",
    )
    world = _world(founder)
    transition = world.advance({1: PopulationAction()})
    assert transition.deaths == (1,)
    assert not world.population.is_active(1)
    organisms = cast(list[object], world.state_dict()["organisms"])
    record = organisms[0]
    assert isinstance(record, dict)
    assert record["genome_id"] == founder.genome.genome_id
