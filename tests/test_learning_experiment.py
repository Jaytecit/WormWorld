import json
from dataclasses import replace
from pathlib import Path

import pytest

from worm_world.experiments import (
    LearningExperimentConfig,
    run_learning_experiment,
    simulate_learning,
    verify_learning_replay,
)
from worm_world.genetics import Genome
from worm_world.world import ReproductionConfig, ResourceFieldConfig

PROJECT_ROOT = Path(__file__).parents[1]


def test_learning_config_is_strict_procedural_and_matched() -> None:
    enabled = LearningExperimentConfig.training_fixture(
        12, plasticity_enabled=True, founder_count=3, step_count=5
    )
    disabled = LearningExperimentConfig.training_fixture(
        12, plasticity_enabled=False, founder_count=3, step_count=5
    )
    assert LearningExperimentConfig.from_json(enabled.to_json()) == enabled
    enabled_values = json.loads(enabled.to_json())
    disabled_values = json.loads(disabled.to_json())
    enabled_values.pop("plasticity_enabled")
    disabled_values.pop("plasticity_enabled")
    assert enabled_values == disabled_values
    assert enabled.config_id != disabled.config_id
    assert (
        enabled.resources
        != LearningExperimentConfig.training_fixture(13, plasticity_enabled=True).resources
    )
    with pytest.raises(ValueError, match="missing or unknown"):
        LearningExperimentConfig.from_json('{"seed":12}')

    semantic = LearningExperimentConfig.training_fixture(
        12, plasticity_enabled=True, eligibility_rule="action_activation"
    )
    assert semantic.schema_version == 2
    assert semantic.eligibility_rule == "action_activation"
    assert LearningExperimentConfig.from_json(semantic.to_json()) == semantic
    assert "eligibility_rule" not in enabled.to_json()


def test_learning_diagnostics_are_ordered_complete_and_deterministic() -> None:
    config = LearningExperimentConfig.training_fixture(
        4, plasticity_enabled=True, founder_count=2, step_count=6
    )
    first = simulate_learning(config)
    second = simulate_learning(config)
    assert first == second
    assert [event.sequence for event in first.events] == list(range(len(first.events)))
    diagnostics = [event for event in first.events if event.event_type == "controller.step"]
    assert diagnostics
    assert [(event.step_index, event.data["entity_id"]) for event in diagnostics] == sorted(
        (event.step_index, event.data["entity_id"]) for event in diagnostics
    )
    expected = {
        "action",
        "controller_outputs",
        "entity_id",
        "genome_id",
        "homeostatic_changes",
        "plasticity_enabled",
        "raw_homeostasis",
    }
    assert all(set(event.data) == expected for event in diagnostics)
    assert all(event.data["plasticity_enabled"] is True for event in diagnostics)


def test_learning_artifact_replays_and_detects_tampering(tmp_path: Path) -> None:
    config = LearningExperimentConfig.training_fixture(
        7, plasticity_enabled=False, founder_count=2, step_count=5
    )
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_manifest = run_learning_experiment(
        config, artifact_directory=first, project_root=PROJECT_ROOT
    )
    second_manifest = run_learning_experiment(
        config, artifact_directory=second, project_root=PROJECT_ROOT
    )
    assert first_manifest == second_manifest == verify_learning_replay(first)
    for name in ("config.json", "events.jsonl", "snapshots.jsonl", "report.json", "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    (first / "events.jsonl").write_bytes((first / "events.jsonl").read_bytes() + b"{}\n")
    with pytest.raises(ValueError, match="event replay diverged"):
        verify_learning_replay(first)


def test_birth_starts_clean_and_death_stops_controller_diagnostics() -> None:
    base = Genome(
        basal_energy_rate=0.0,
        basal_hydration_rate=0.0,
        movement_energy_rate=0.0,
        fertility_energy_fraction=0.5,
        offspring_energy_fraction=0.1,
        mutation_scale=0.0,
    )
    genome = Genome.version2(base, hidden_size=2)
    assert genome.brain_priors is not None
    priors = (*genome.brain_priors[:-1], 1.0)
    reproductive = replace(genome, brain_priors=priors)
    birth_config = LearningExperimentConfig(
        seed=2,
        plasticity_enabled=True,
        founder_positions=((5.0, 5.0),),
        step_count=2,
        founder_genome=reproductive,
        resources=ResourceFieldConfig(food_energy=0.0, water_amount=0.0),
        reproduction=ReproductionConfig(
            minimum_age_seconds=0.5,
            cooldown_seconds=10.0,
            maximum_population=2,
            mutation_enabled=False,
        ),
    )
    birth_run = simulate_learning(birth_config)
    assert birth_run.report.births == 1
    child_first = next(
        event
        for event in birth_run.events
        if event.event_type == "controller.step" and event.data["entity_id"] == 2
    )
    changes = child_first.data["homeostatic_changes"]
    assert isinstance(changes, dict)
    assert changes["energy_change"] == changes["hydration_change"] == 0.0
    assert changes["update_l1"] == changes["learned_weight_l1"] == 0.0

    dying = Genome.version2(
        Genome(
            basal_energy_rate=10.0,
            basal_hydration_rate=0.0,
            movement_energy_rate=0.0,
            mutation_scale=0.0,
        ),
        hidden_size=2,
    )
    death_config = replace(
        birth_config,
        step_count=40,
        founder_genome=dying,
        reproduction=replace(birth_config.reproduction, maximum_population=1),
    )
    death_run = simulate_learning(death_config)
    assert death_run.report.deaths == 1
    death_step = next(
        event.step_index for event in death_run.events if event.event_type == "organism.died"
    )
    assert not any(
        event.event_type == "controller.step" and event.step_index > death_step
        for event in death_run.events
    )
