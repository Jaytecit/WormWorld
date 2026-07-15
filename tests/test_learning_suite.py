import json
from dataclasses import replace
from pathlib import Path

import pytest

from worm_world.experiments import (
    LearningSuiteConfig,
    run_learning_evaluation_suite,
    verify_learning_evaluation_suite,
)

PROJECT_ROOT = Path(__file__).parents[1]


def _config() -> LearningSuiteConfig:
    return LearningSuiteConfig(
        development_seeds=(10,),
        heldout_seeds=(21, 22, 23),
        founder_count=2,
        step_count=4,
        bootstrap_seed=99,
        bootstrap_samples=100,
    )


def test_learning_suite_config_is_strict_and_seed_partitions_are_locked() -> None:
    config = _config()
    assert LearningSuiteConfig.from_json(config.to_json()) == config
    assert LearningSuiteConfig.from_json(config.to_json()).config_id == config.config_id
    with pytest.raises(ValueError, match="disjoint"):
        LearningSuiteConfig((10, 21), (21, 22, 23))
    with pytest.raises(ValueError, match="at least 3"):
        LearningSuiteConfig((10,), (21, 22))
    with pytest.raises(ValueError, match="missing or unknown"):
        LearningSuiteConfig.from_json('{"development_seeds":[10]}')
    semantic = replace(config, eligibility_rule="action_activation", schema_version=2)
    assert LearningSuiteConfig.from_json(semantic.to_json()) == semantic
    assert "eligibility_rule" not in config.to_json()


def test_suite_reports_honest_failed_gate_and_replays_deterministically(tmp_path: Path) -> None:
    config = _config()
    first_directory = tmp_path / "first"
    second_directory = tmp_path / "second"
    first = run_learning_evaluation_suite(
        config, artifact_directory=first_directory, project_root=PROJECT_ROOT
    )
    second = run_learning_evaluation_suite(
        config, artifact_directory=second_directory, project_root=PROJECT_ROOT
    )
    assert first == second == verify_learning_evaluation_suite(first_directory)
    assert first["acceptance_passed"] is False
    assert first["suite_config_id"] == config.config_id
    statistics = first["statistics"]
    assert isinstance(statistics, dict)
    births = statistics["births"]
    assert isinstance(births, dict)
    assert births["paired_differences"] == [0.0, 0.0, 0.0]
    assert births["ci_lower"] == births["ci_upper"] == 0.0

    for split, seeds in (("development", (10,)), ("heldout", (21, 22, 23))):
        for seed in seeds:
            on = json.loads(
                (first_directory / f"{split}_seed_{seed}_on" / "config.json").read_text()
            )
            off = json.loads(
                (first_directory / f"{split}_seed_{seed}_off" / "config.json").read_text()
            )
            assert on.pop("plasticity_enabled") is True
            assert off.pop("plasticity_enabled") is False
            assert on == off


def test_suite_verifier_rejects_tampered_condition_artifact(tmp_path: Path) -> None:
    directory = tmp_path / "suite"
    run_learning_evaluation_suite(
        _config(), artifact_directory=directory, project_root=PROJECT_ROOT
    )
    events = directory / "heldout_seed_21_on" / "events.jsonl"
    events.write_bytes(events.read_bytes() + b"{}\n")
    with pytest.raises(ValueError, match="event replay diverged"):
        verify_learning_evaluation_suite(directory)
