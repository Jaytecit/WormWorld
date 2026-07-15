from dataclasses import replace
from pathlib import Path

import pytest

from worm_world.experiments import (
    LearningExperimentConfig,
    PlasticitySensitivityConfig,
    SurvivalGateConfig,
    run_plasticity_sensitivity,
    verify_survival_gate_preregistration,
    write_survival_gate_preregistration,
)

PROJECT_ROOT = Path(__file__).parents[1]


def _sensitivity() -> PlasticitySensitivityConfig:
    genome = LearningExperimentConfig.training_fixture(0, plasticity_enabled=True).founder_genome
    return PlasticitySensitivityConfig(
        (101, 102, 103),
        (301, 302, 303, 304, 305),
        replace(genome, plasticity_rate=1.0),
        founder_count=2,
        step_count=4,
        eligibility_rule="action_activation",
        schema_version=2,
    )


def _gate(sensitivity: PlasticitySensitivityConfig) -> SurvivalGateConfig:
    return SurvivalGateConfig(
        sensitivity.development_seeds,
        sensitivity.future_heldout_seeds,
        sensitivity.candidate_genome,
        sensitivity.config_id,
        founder_count=sensitivity.founder_count,
        step_count=sensitivity.step_count,
        bootstrap_samples=100,
    )


def test_survival_gate_config_is_strict_and_canonical() -> None:
    config = _gate(_sensitivity())
    assert SurvivalGateConfig.from_json(config.to_json()) == config
    assert SurvivalGateConfig.from_json(config.to_json()).config_id == config.config_id
    with pytest.raises(ValueError, match="disjoint"):
        replace(config, heldout_seeds=(103, 301, 302, 303, 304))
    with pytest.raises(ValueError, match="missing or unknown"):
        SurvivalGateConfig.from_json('{"development_seeds":[101,102,103]}')


def test_survival_preregistration_reports_descendants_and_replays(tmp_path: Path) -> None:
    sensitivity = _sensitivity()
    evidence = tmp_path / "evidence"
    run_plasticity_sensitivity(sensitivity, artifact_directory=evidence, project_root=PROJECT_ROOT)
    preregistration = tmp_path / "preregistration"
    authorization = write_survival_gate_preregistration(
        _gate(sensitivity),
        artifact_directory=preregistration,
        development_evidence_directory=evidence,
    )
    assert authorization == verify_survival_gate_preregistration(
        preregistration, development_evidence_directory=evidence
    )
    assert authorization["confirmation_authorized"] is False
    records = authorization["records"]
    assert isinstance(records, list)
    for record in records:
        assert isinstance(record, dict)
        on, off = record["on"], record["off"]
        assert isinstance(on, dict) and isinstance(off, dict)
        assert "surviving_descendants" in on and "surviving_descendants" in off
    path = preregistration / "development_authorization.json"
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="authorization replay diverged"):
        verify_survival_gate_preregistration(
            preregistration, development_evidence_directory=evidence
        )
