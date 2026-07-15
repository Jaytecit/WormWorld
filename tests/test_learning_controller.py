import math

import pytest

from worm_world.experiments import WorldConfig
from worm_world.genetics import Genome
from worm_world.learning import (
    ControllerConfig,
    ControllerPriors,
    ControllerState,
    PlasticityParameters,
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


def test_three_factor_update_arithmetic_and_diagnostics_use_only_internal_change() -> None:
    priors = ControllerPriors(
        input_weights=((1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),),
        recurrent_weights=((0.0,),),
        hidden_bias=(0.0,),
        output_weights=((0.0,),) * 6,
        output_bias=(0.5,) * 6,
    )
    parameters = PlasticityParameters(
        learning_rate=0.1,
        trace_decay=0.5,
        energy_weight=1.0,
        hydration_weight=2.0,
        injury_weight=-3.0,
    )
    controller = RecurrentController(ControllerConfig(hidden_size=1), priors, parameters)
    first = controller.step(_sensors(0.5), ControllerState.clean(1))
    changed = SensorReadings(0.6, 0.4, 0.1, 1.0, 0.0, 0.5, -1.0, 0.0, 0.5, False)
    second = controller.step(changed, first.state)

    expected_modulator = 0.1 + 2.0 * -0.1 + -3.0 * 0.1
    expected_trace = math.tanh(0.5) * math.tanh(0.5)
    expected_update = 0.1 * expected_modulator * expected_trace
    assert math.isclose(second.diagnostic.energy_change, 0.1)
    assert math.isclose(second.diagnostic.hydration_change, -0.1)
    assert math.isclose(second.diagnostic.injury_change, 0.1)
    assert math.isclose(second.diagnostic.neuromodulator, expected_modulator)
    assert math.isclose(second.state.output_weight_deltas[0][0], expected_update)
    assert math.isclose(second.diagnostic.update_l1, 6.0 * abs(expected_update))
    assert set(second.diagnostic.to_dict()) == {
        "energy_change",
        "hydration_change",
        "injury_change",
        "neuromodulator",
        "update_l1",
        "learned_weight_l1",
    }


def test_plasticity_off_is_identical_to_zero_rate_control() -> None:
    genome = Genome.version2(hidden_size=3, plasticity_rate=0.1)
    assert genome.brain_priors is not None
    priors = ControllerPriors.from_genome(genome)
    parameters = PlasticityParameters.from_genome(genome)
    off = RecurrentController(
        ControllerConfig(hidden_size=3, plasticity_enabled=False), priors, parameters
    )
    zero = RecurrentController(
        ControllerConfig(hidden_size=3),
        priors,
        PlasticityParameters(
            learning_rate=0.0,
            trace_decay=parameters.trace_decay,
            energy_weight=parameters.energy_weight,
            hydration_weight=parameters.hydration_weight,
            injury_weight=parameters.injury_weight,
        ),
    )
    off_state = zero_state = ControllerState.clean(3)
    for sensors in (_sensors(0.5), _sensors(0.4), _sensors(0.7)):
        off_step = off.step(sensors, off_state)
        zero_step = zero.step(sensors, zero_state)
        assert off_step.action == zero_step.action
        assert off_step.outputs == zero_step.outputs
        assert off_step.state.output_weight_deltas == zero_step.state.output_weight_deltas
        off_state, zero_state = off_step.state, zero_step.state


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


def test_version_2_birth_gets_clean_lifetime_plasticity_state() -> None:
    genome = Genome.version2(
        Genome(
            basal_energy_rate=0.0,
            basal_hydration_rate=0.0,
            movement_energy_rate=0.0,
            mutation_scale=0.0,
        ),
        hidden_size=3,
    )
    world = PopulationWorld(
        seed=7,
        world_config=WorldConfig(timestep_seconds=0.5),
        resource_config=ResourceFieldConfig(food_energy=0.0, water_amount=0.0),
        reproduction_config=ReproductionConfig(minimum_age_seconds=0.5, mutation_enabled=False),
        founders=[Founder(genome, InitialOrganismConfig(energy=80.0, hydration=80.0), "one")],
    )
    controller = PopulationController(ControllerConfig(hidden_size=3))
    controller.decide({1: world.sense(1)}, {1: world.genome(1)})
    transition = world.advance({1: PopulationAction(reproduce=True)})
    assert transition.births == (2,)
    controller.decide(
        {entity_id: world.sense(entity_id) for entity_id in (2, 1)},
        {entity_id: world.genome(entity_id) for entity_id in (2, 1)},
    )
    assert controller.state(1).step_count == 2
    assert controller.state(2).step_count == 1
    assert controller.state(2).output_weight_deltas == ((0.0,) * 3,) * 6
    assert controller.diagnostic(2).update_l1 == 0.0
