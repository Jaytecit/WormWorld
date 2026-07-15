import math

import pytest

from worm_world.experiments import WorldConfig
from worm_world.genetics import Genome
from worm_world.learning import (
    ControllerConfig,
    ControllerPriors,
    ControllerState,
    PopulationController,
    RecurrentController,
)
from worm_world.organisms import SensorReadings
from worm_world.world import (
    Founder,
    InitialOrganismConfig,
    PopulationAction,
    PopulationWorld,
    ReproductionConfig,
    ResourceFieldConfig,
)


def _sensors(energy: float = 0.5) -> SensorReadings:
    return SensorReadings(energy, 0.5, 0.0, 1.0, 0.0, 0.5, -1.0, 0.0, 0.5, False)


def test_prior_shape_and_state_bounds_are_validated() -> None:
    genome_id = Genome().genome_id
    priors = ControllerPriors.from_genome_id(genome_id, 4)
    assert len(priors.input_weights) == 4
    assert len(priors.output_weights) == 6
    with pytest.raises(ValueError, match="hidden sizes disagree"):
        RecurrentController(ControllerConfig(hidden_size=3), priors)
    with pytest.raises(ValueError, match="finite"):
        ControllerState((math.nan,))


def test_controller_transition_and_actions_are_deterministic_and_bounded() -> None:
    config = ControllerConfig(hidden_size=5)
    priors = ControllerPriors.from_genome_id(Genome().genome_id, 5)
    controller = RecurrentController(config, priors)
    first = controller.step(_sensors(), ControllerState.clean(5))
    second = controller.step(_sensors(), ControllerState.clean(5))
    assert first == second
    assert -1.0 <= first.action.motion.forward <= 1.0
    assert -1.0 <= first.action.motion.turn <= 1.0


def test_learning_off_has_no_history_dependence() -> None:
    config = ControllerConfig(hidden_size=4, recurrent_enabled=False)
    controller = RecurrentController(config, ControllerPriors.from_genome_id(Genome().genome_id, 4))
    first = controller.step(_sensors(), ControllerState((0.9, -0.8, 0.7, -0.6), 20))
    second = controller.step(_sensors(), ControllerState.clean(4))
    assert first.action == second.action
    assert first.state.hidden == (0.0,) * 4


def test_population_state_is_isolated_order_independent_and_clean_for_births() -> None:
    genome = Genome(
        basal_energy_rate=0.0,
        basal_hydration_rate=0.0,
        movement_energy_rate=0.0,
        mutation_scale=0.0,
    )
    world = PopulationWorld(
        seed=4,
        world_config=WorldConfig(timestep_seconds=0.5),
        resource_config=ResourceFieldConfig(food_energy=0.0, water_amount=0.0),
        reproduction_config=ReproductionConfig(minimum_age_seconds=0.5, mutation_enabled=False),
        founders=[
            Founder(genome, InitialOrganismConfig(energy=80.0, hydration=80.0), "one"),
            Founder(genome, InitialOrganismConfig(x=4.0, energy=80.0, hydration=80.0), "two"),
        ],
    )
    controller = PopulationController(ControllerConfig(hidden_size=4))
    sensors = {entity_id: world.sense(entity_id) for entity_id in (2, 1)}
    actions = controller.decide(sensors, {2: genome.genome_id, 1: genome.genome_id})
    assert tuple(actions) == (1, 2)
    assert controller.state(1).step_count == controller.state(2).step_count == 1
    transition = world.advance(
        {
            1: PopulationAction(reproduce=True),
            2: PopulationAction(),
        }
    )
    assert transition.births == (3,)
    active = world.population.active_entity_ids()
    controller.decide(
        {entity_id: world.sense(entity_id) for entity_id in reversed(active)},
        {entity_id: world.genome(entity_id).genome_id for entity_id in reversed(active)},
    )
    assert controller.state(1).step_count == controller.state(2).step_count == 2
    assert controller.state(3).step_count == 1
