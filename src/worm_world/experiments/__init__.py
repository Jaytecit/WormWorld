"""Experiment configuration and execution support."""

from worm_world.experiments.config import ExperimentConfig, WorldConfig
from worm_world.experiments.evolution import (
    EvolutionExperimentConfig,
    EvolutionRunReport,
    run_evolution_experiment,
    run_phase2_acceptance_suite,
    simulate_evolution,
    verify_evolution_replay,
)
from worm_world.experiments.learning import (
    LearningExperimentConfig,
    LearningRunReport,
    run_learning_experiment,
    simulate_learning,
    verify_learning_replay,
)
from worm_world.experiments.learning_sensitivity import (
    ActionDivergenceReport,
    PlasticitySensitivityConfig,
    compare_action_divergence,
    run_plasticity_sensitivity,
    verify_plasticity_sensitivity,
)
from worm_world.experiments.learning_suite import (
    LearningGateCriteria,
    LearningSuiteConfig,
    run_learning_evaluation_suite,
    verify_learning_evaluation_suite,
)
from worm_world.experiments.runner import (
    ReplayArtifacts,
    run_noop_experiment,
    run_sandbox_experiment,
    simulate_sandbox,
    verify_sandbox_replay,
)
from worm_world.experiments.sandbox_config import SandboxExperimentConfig

__all__ = [
    "ExperimentConfig",
    "EvolutionExperimentConfig",
    "EvolutionRunReport",
    "ActionDivergenceReport",
    "LearningExperimentConfig",
    "LearningGateCriteria",
    "LearningRunReport",
    "LearningSuiteConfig",
    "PlasticitySensitivityConfig",
    "ReplayArtifacts",
    "SandboxExperimentConfig",
    "WorldConfig",
    "run_noop_experiment",
    "run_plasticity_sensitivity",
    "run_evolution_experiment",
    "run_learning_experiment",
    "run_learning_evaluation_suite",
    "run_phase2_acceptance_suite",
    "run_sandbox_experiment",
    "simulate_sandbox",
    "compare_action_divergence",
    "simulate_evolution",
    "simulate_learning",
    "verify_evolution_replay",
    "verify_learning_replay",
    "verify_learning_evaluation_suite",
    "verify_sandbox_replay",
    "verify_plasticity_sensitivity",
]
