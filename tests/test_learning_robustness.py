from dataclasses import replace
from pathlib import Path

import pytest

from worm_world.experiments import (
    LearningExperimentConfig,
    RobustnessScreenConfig,
    run_robustness_screen,
    verify_robustness_screen,
    write_robustness_survival_preregistration,
)
from worm_world.experiments.learning_robustness import select_robustness_candidate_rate
from worm_world.schemas import JsonValue

PROJECT_ROOT = Path(__file__).parents[1]


def _config() -> RobustnessScreenConfig:
    genome = LearningExperimentConfig.training_fixture(0, plasticity_enabled=True).founder_genome
    return RobustnessScreenConfig(
        tuple(range(401, 411)),
        replace(genome, plasticity_rate=1.0),
        founder_count=2,
        step_count=2,
    )


def test_robustness_config_is_strict_canonical_and_excludes_consumed_seeds() -> None:
    config = _config()
    assert RobustnessScreenConfig.from_json(config.to_json()) == config
    assert RobustnessScreenConfig.from_json(config.to_json()).config_id == config.config_id
    with pytest.raises(ValueError, match="consumed held-out"):
        replace(config, development_seeds=(201, *range(401, 410)))
    with pytest.raises(ValueError, match="exactly"):
        replace(config, rates=(0.5, 1.0))
    with pytest.raises(ValueError, match="missing or unknown"):
        RobustnessScreenConfig.from_json('{"development_seeds":[401]}')


def test_candidate_selection_is_deterministic_and_reports_no_candidate() -> None:
    records: list[dict[str, JsonValue]] = [
        {"qualified": True, "rate": 1.0},
        {"qualified": False, "rate": 0.25},
        {"qualified": True, "rate": 0.5},
    ]
    assert select_robustness_candidate_rate(records) == 0.5
    assert select_robustness_candidate_rate(list(reversed(records))) == 0.5
    assert select_robustness_candidate_rate([{"qualified": False, "rate": 1.0}]) is None


def test_robustness_screen_replays_matrix_and_rejects_tampering(tmp_path: Path) -> None:
    config = _config()
    directory = tmp_path / "screen"
    summary = run_robustness_screen(config, artifact_directory=directory, project_root=PROJECT_ROOT)
    assert summary == verify_robustness_screen(directory)
    assert summary["candidate_found"] is False
    assert summary["selected_rate"] is None
    rate_records = summary["rate_records"]
    assert isinstance(rate_records, list) and len(rate_records) == 3
    for rate_record in rate_records:
        assert isinstance(rate_record, dict)
        records = rate_record["records"]
        assert isinstance(records, list) and len(records) == 10
        assert rate_record["zero_controls_identical"] is True
        for record in records:
            assert isinstance(record, dict)
            conditions = record["conditions"]
            assert isinstance(conditions, dict)
            for condition in ("on", "off", "zero"):
                child = conditions[condition]
                assert isinstance(child, dict)
                outcomes = child["outcomes"]
                assert isinstance(outcomes, dict)
                assert "births" in outcomes and "surviving_descendants" in outcomes
    assert not (directory / "future_survival_gate_config.json").exists()
    with pytest.raises(ValueError, match="did not qualify"):
        write_robustness_survival_preregistration(
            robustness_directory=directory,
            artifact_directory=tmp_path / "preregistration",
            heldout_seeds=(501, 502, 503, 504, 505),
        )
    (directory / "summary.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="robustness screen replay diverged"):
        verify_robustness_screen(directory)
