from dataclasses import replace
from pathlib import Path

import pytest

from worm_world.experiments import (
    LearningExperimentConfig,
    PlasticitySensitivityConfig,
    analyze_binary_action_margins,
    center_binary_output_biases,
    compare_action_divergence,
    run_plasticity_sensitivity,
    simulate_learning,
    verify_binary_margin_analysis,
    verify_plasticity_sensitivity,
    write_binary_margin_analysis,
)

PROJECT_ROOT = Path(__file__).parents[1]


def _config() -> PlasticitySensitivityConfig:
    base = LearningExperimentConfig.training_fixture(0, plasticity_enabled=True).founder_genome
    return PlasticitySensitivityConfig(
        (101, 102, 103),
        (301, 302, 303),
        replace(base, plasticity_rate=1.0),
        founder_count=2,
        step_count=4,
    )


def test_sensitivity_config_is_strict_and_preregisters_without_running() -> None:
    config = _config()
    assert PlasticitySensitivityConfig.from_json(config.to_json()) == config
    assert config.future_suite.heldout_seeds == (301, 302, 303)
    assert config.future_suite.founder_genome.plasticity_rate == 1.0
    with pytest.raises(ValueError, match="disjoint"):
        replace(config, future_heldout_seeds=(103, 301, 302))
    with pytest.raises(ValueError, match="missing or unknown"):
        PlasticitySensitivityConfig.from_json('{"development_seeds":[101,102,103]}')


def test_action_divergence_is_causal_and_zero_rate_matches_off() -> None:
    config = _config()
    on_config = LearningExperimentConfig.training_fixture(
        101,
        plasticity_enabled=True,
        founder_count=2,
        step_count=8,
        founder_genome=config.candidate_genome,
    )
    off_config = replace(on_config, plasticity_enabled=False)
    zero_config = replace(
        on_config, founder_genome=replace(config.candidate_genome, plasticity_rate=0.0)
    )
    on = simulate_learning(on_config)
    off = simulate_learning(off_config)
    zero = simulate_learning(zero_config)
    on_off = compare_action_divergence(on, off)
    off_zero = compare_action_divergence(off, zero)
    assert on_off.continuous_motion_divergences > 0
    assert on_off.first_divergence is not None
    assert off_zero.maximum_output_delta == 0.0
    assert off_zero.continuous_motion_divergences == 0
    off_report = off.report.to_dict()
    zero_report = zero.report.to_dict()
    off_report.pop("plasticity_enabled")
    zero_report.pop("plasticity_enabled")
    assert off_report == zero_report


def test_sensitivity_artifacts_replay_and_block_unqualified_confirmation(tmp_path: Path) -> None:
    directory = tmp_path / "sensitivity"
    summary = run_plasticity_sensitivity(
        _config(), artifact_directory=directory, project_root=PROJECT_ROOT
    )
    assert summary == verify_plasticity_sensitivity(directory)
    assert summary["zero_controls_identical"] is True
    assert summary["candidate_development_passed"] is False
    assert summary["future_confirmatory_authorized"] is False
    assert (directory / "future_suite_config.json").is_file()
    events = directory / "seed_101_on" / "events.jsonl"
    events.write_bytes(events.read_bytes() + b"{}\n")
    with pytest.raises(ValueError, match="event replay diverged"):
        verify_plasticity_sensitivity(directory)


def test_binary_bias_centering_and_margin_analysis_are_exact(tmp_path: Path) -> None:
    original = _config().candidate_genome
    centered = center_binary_output_biases(original)
    assert original.brain_priors is not None and centered.brain_priors is not None
    assert centered.brain_priors[:-4] == original.brain_priors[:-4]
    assert centered.brain_priors[-4:] == (0.0, 0.0, 0.0, 0.0)
    run_config = LearningExperimentConfig.training_fixture(
        101,
        plasticity_enabled=True,
        founder_count=2,
        step_count=4,
        founder_genome=centered,
    )
    margins = analyze_binary_action_margins(simulate_learning(run_config))
    assert set(margins) == {"eat", "drink", "rest", "reproduce"}
    assert all(isinstance(value, dict) and value["sample_count"] == 8 for value in margins.values())

    sensitivity = replace(_config(), candidate_genome=centered)
    directory = tmp_path / "margins"
    run_plasticity_sensitivity(sensitivity, artifact_directory=directory, project_root=PROJECT_ROOT)
    analysis = write_binary_margin_analysis(directory)
    assert analysis == verify_binary_margin_analysis(directory)
    assert analysis["binary_output_biases"] == [0.0, 0.0, 0.0, 0.0]
