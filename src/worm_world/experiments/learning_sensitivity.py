"""Development-only causal action-divergence analysis for plasticity sensitivity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Self, cast

from worm_world.experiments.config import MAX_SEED
from worm_world.experiments.learning import (
    LearningExperimentConfig,
    LearningSimulation,
    run_learning_experiment,
    simulate_learning,
    verify_learning_replay,
)
from worm_world.experiments.learning_suite import LearningGateCriteria, LearningSuiteConfig
from worm_world.genetics import Genome
from worm_world.schemas import JsonValue

SENSITIVITY_SCHEMA_VERSION = 1
SENSITIVITY_EXPERIMENT_TYPE = "development_plasticity_sensitivity"


@dataclass(frozen=True, slots=True)
class PlasticitySensitivityConfig:
    """Locked development inputs and an unexecuted future confirmation contract."""

    development_seeds: tuple[int, ...]
    future_heldout_seeds: tuple[int, ...]
    candidate_genome: Genome
    founder_count: int = 4
    step_count: int = 128
    criteria: LearningGateCriteria = LearningGateCriteria()
    experiment_type: str = SENSITIVITY_EXPERIMENT_TYPE
    schema_version: int = SENSITIVITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, seeds, minimum in (
            ("development_seeds", self.development_seeds, 3),
            ("future_heldout_seeds", self.future_heldout_seeds, 3),
        ):
            if len(seeds) < minimum or len(set(seeds)) != len(seeds):
                raise ValueError(f"{name} requires at least {minimum} distinct seeds")
            if any(isinstance(seed, bool) or not 0 <= seed <= MAX_SEED for seed in seeds):
                raise ValueError(f"{name} contains an invalid seed")
        if set(self.development_seeds) & set(self.future_heldout_seeds):
            raise ValueError("development and future held-out seeds must be disjoint")
        if self.candidate_genome.schema_version != 2:
            raise ValueError("sensitivity analysis requires a version-2 genome")
        if self.candidate_genome.plasticity_rate is None:
            raise ValueError("candidate genome must encode a plasticity rate")
        if isinstance(self.founder_count, bool) or not 1 <= self.founder_count <= 16:
            raise ValueError("founder_count must be in [1, 16]")
        if isinstance(self.step_count, bool) or self.step_count < 1:
            raise ValueError("step_count must be positive")
        if self.experiment_type != SENSITIVITY_EXPERIMENT_TYPE:
            raise ValueError("unsupported sensitivity experiment type")
        if self.schema_version != SENSITIVITY_SCHEMA_VERSION:
            raise ValueError("unsupported sensitivity schema version")

    @property
    def zero_rate_genome(self) -> Genome:
        return replace(self.candidate_genome, plasticity_rate=0.0)

    @property
    def future_suite(self) -> LearningSuiteConfig:
        return LearningSuiteConfig(
            self.development_seeds,
            self.future_heldout_seeds,
            founder_genome=self.candidate_genome,
            founder_count=self.founder_count,
            step_count=self.step_count,
            criteria=self.criteria,
        )

    def to_json(self) -> str:
        values = asdict(self)
        values["candidate_genome"] = self.candidate_genome.to_dict()
        return json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def config_id(self) -> str:
        return hashlib.sha256(self.to_json().encode()).hexdigest()

    @classmethod
    def from_json(cls, serialized: str) -> Self:
        decoded: object = json.loads(serialized)
        if not isinstance(decoded, dict):
            raise ValueError("sensitivity configuration must be an object")
        raw = cast(dict[str, Any], decoded)
        sample_genome = LearningExperimentConfig.training_fixture(
            0, plasticity_enabled=True
        ).founder_genome
        expected = set(asdict(cls((1, 2, 3), (4, 5, 6), sample_genome)))
        if set(raw) != expected:
            raise ValueError("sensitivity configuration has missing or unknown fields")
        return cls(
            development_seeds=tuple(raw["development_seeds"]),
            future_heldout_seeds=tuple(raw["future_heldout_seeds"]),
            candidate_genome=Genome.from_json(json.dumps(raw["candidate_genome"])),
            founder_count=raw["founder_count"],
            step_count=raw["step_count"],
            criteria=LearningGateCriteria(**raw["criteria"]),
            experiment_type=raw["experiment_type"],
            schema_version=raw["schema_version"],
        )


@dataclass(frozen=True, slots=True)
class ActionDivergenceReport:
    matched_steps: int
    continuous_motion_divergences: int
    eat_divergences: int
    drink_divergences: int
    rest_divergences: int
    reproduce_divergences: int
    first_divergence: tuple[int, int] | None
    maximum_output_delta: float

    def to_dict(self) -> dict[str, JsonValue]:
        values = asdict(self)
        first = values["first_divergence"]
        values["first_divergence"] = list(first) if first is not None else None
        return cast(dict[str, JsonValue], values)


def center_binary_output_biases(genome: Genome) -> Genome:
    """Return a v2 genome with all four binary-action biases at the neutral logit."""
    if genome.schema_version != 2 or genome.brain_priors is None:
        raise ValueError("binary bias centering requires a version-2 genome")
    if len(genome.brain_priors) < 6:
        raise ValueError("controller priors do not contain output biases")
    return replace(genome, brain_priors=(*genome.brain_priors[:-4], 0.0, 0.0, 0.0, 0.0))


def analyze_binary_action_margins(simulation: LearningSimulation) -> dict[str, JsonValue]:
    """Summarize signed and absolute pre-threshold logits for binary action channels."""
    events = _controller_events(simulation)
    channels = {"eat": 2, "drink": 3, "rest": 4, "reproduce": 5}
    report: dict[str, JsonValue] = {}
    for name, index in channels.items():
        values: list[float] = []
        for event in events.values():
            outputs = event["controller_outputs"]
            if not isinstance(outputs, list) or len(outputs) != 6:
                raise ValueError("controller outputs must contain six values")
            value = outputs[index]
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError("controller output must be numeric")
            values.append(float(value))
        if not values:
            raise ValueError("binary margin analysis requires controller events")
        report[name] = {
            "maximum": max(values),
            "mean_absolute": sum(abs(value) for value in values) / len(values),
            "minimum": min(values),
            "minimum_absolute": min(abs(value) for value in values),
            "sample_count": len(values),
        }
    return report


def _controller_events(
    simulation: LearningSimulation,
) -> dict[tuple[int, int], dict[str, JsonValue]]:
    events: dict[tuple[int, int], dict[str, JsonValue]] = {}
    for event in simulation.events:
        if event.event_type != "controller.step":
            continue
        entity_id = event.data["entity_id"]
        if isinstance(entity_id, bool) or not isinstance(entity_id, int):
            raise ValueError("controller event entity ID must be an integer")
        events[(event.step_index, entity_id)] = event.data
    return events


def compare_action_divergence(
    first: LearningSimulation, second: LearningSimulation
) -> ActionDivergenceReport:
    """Compare paired controller outputs and executed actions without scoring them."""
    left = _controller_events(first)
    right = _controller_events(second)
    keys = sorted(set(left) & set(right))
    continuous = eat = drink = rest = reproduce = 0
    first_divergence: tuple[int, int] | None = None
    maximum_output_delta = 0.0
    for key in keys:
        left_outputs = left[key]["controller_outputs"]
        right_outputs = right[key]["controller_outputs"]
        if not isinstance(left_outputs, list) or not isinstance(right_outputs, list):
            raise ValueError("controller outputs must be arrays")
        if any(
            isinstance(value, bool) or not isinstance(value, int | float)
            for value in (*left_outputs, *right_outputs)
        ):
            raise ValueError("controller outputs must be numeric")
        maximum_output_delta = max(
            maximum_output_delta,
            *(
                abs(float(cast(int | float, a)) - float(cast(int | float, b)))
                for a, b in zip(left_outputs, right_outputs, strict=True)
            ),
        )
        left_action = cast(dict[str, JsonValue], left[key]["action"])
        right_action = cast(dict[str, JsonValue], right[key]["action"])
        left_motion = cast(dict[str, JsonValue], left_action["motion"])
        right_motion = cast(dict[str, JsonValue], right_action["motion"])
        differences = {
            "continuous": left_motion["forward"] != right_motion["forward"]
            or left_motion["turn"] != right_motion["turn"],
            "eat": left_motion["eat"] != right_motion["eat"],
            "drink": left_motion["drink"] != right_motion["drink"],
            "rest": left_motion["rest"] != right_motion["rest"],
            "reproduce": left_action["reproduce"] != right_action["reproduce"],
        }
        continuous += differences["continuous"]
        eat += differences["eat"]
        drink += differences["drink"]
        rest += differences["rest"]
        reproduce += differences["reproduce"]
        if first_divergence is None and any(differences.values()):
            first_divergence = key
    return ActionDivergenceReport(
        len(keys),
        continuous,
        eat,
        drink,
        rest,
        reproduce,
        first_divergence,
        maximum_output_delta,
    )


def _condition_config(
    config: PlasticitySensitivityConfig, seed: int, condition: str
) -> LearningExperimentConfig:
    if condition == "on":
        genome, enabled = config.candidate_genome, True
    elif condition == "off":
        genome, enabled = config.candidate_genome, False
    elif condition == "zero":
        genome, enabled = config.zero_rate_genome, True
    else:
        raise ValueError("unknown sensitivity condition")
    return LearningExperimentConfig.training_fixture(
        seed,
        plasticity_enabled=enabled,
        founder_count=config.founder_count,
        step_count=config.step_count,
        founder_genome=genome,
    )


def _summary(
    config: PlasticitySensitivityConfig,
    simulations: dict[tuple[int, str], LearningSimulation],
    identities: dict[tuple[int, str], tuple[str, str]],
) -> dict[str, JsonValue]:
    records: list[JsonValue] = []
    birth_differences: list[int] = []
    population_differences: list[int] = []
    wins = 0
    zero_controls_identical = True
    for seed in config.development_seeds:
        on = simulations[(seed, "on")]
        off = simulations[(seed, "off")]
        zero = simulations[(seed, "zero")]
        on_off = compare_action_divergence(on, off)
        off_zero = compare_action_divergence(off, zero)
        off_report = off.report.to_dict()
        zero_report = zero.report.to_dict()
        off_report.pop("plasticity_enabled")
        zero_report.pop("plasticity_enabled")
        zero_identical = (
            off_zero.maximum_output_delta == 0.0
            and off_zero.continuous_motion_divergences == 0
            and off_zero.eat_divergences == 0
            and off_zero.drink_divergences == 0
            and off_zero.rest_divergences == 0
            and off_zero.reproduce_divergences == 0
            and off_report == zero_report
        )
        zero_controls_identical &= zero_identical
        birth_difference = on.report.births - off.report.births
        population_difference = on.report.final_population - off.report.final_population
        birth_differences.append(birth_difference)
        population_differences.append(population_difference)
        if birth_difference > 0 and population_difference > 0:
            wins += 1
        records.append(
            {
                "birth_difference": birth_difference,
                "conditions": {
                    label: {
                        "config_id": identities[(seed, label)][0],
                        "event_hash": identities[(seed, label)][1],
                        "report": simulations[(seed, label)].report.to_dict(),
                    }
                    for label in ("on", "off", "zero")
                },
                "off_zero_divergence": off_zero.to_dict(),
                "on_off_divergence": on_off.to_dict(),
                "population_difference": population_difference,
                "seed": seed,
                "zero_control_identical": zero_identical,
            }
        )
    criteria = config.criteria
    birth_mean = sum(birth_differences) / len(birth_differences)
    population_mean = sum(population_differences) / len(population_differences)
    win_fraction = wins / len(config.development_seeds)
    candidate_development_passed = (
        birth_mean > criteria.minimum_birth_mean_advantage
        and population_mean > criteria.minimum_population_mean_advantage
        and win_fraction >= criteria.minimum_paired_win_fraction
        and zero_controls_identical
    )
    return {
        "candidate_development_passed": candidate_development_passed,
        "candidate_rate": cast(float, config.candidate_genome.plasticity_rate),
        "development_birth_mean_advantage": birth_mean,
        "development_population_mean_advantage": population_mean,
        "development_win_fraction": win_fraction,
        "future_confirmatory_authorized": candidate_development_passed,
        "future_suite_config_id": config.future_suite.config_id,
        "records": records,
        "sensitivity_config_id": config.config_id,
        "zero_controls_identical": zero_controls_identical,
    }


def run_plasticity_sensitivity(
    config: PlasticitySensitivityConfig,
    *,
    artifact_directory: Path,
    project_root: Path,
) -> dict[str, JsonValue]:
    artifact_directory.mkdir(parents=True, exist_ok=False)
    simulations: dict[tuple[int, str], LearningSimulation] = {}
    identities: dict[tuple[int, str], tuple[str, str]] = {}
    for seed in config.development_seeds:
        for condition in ("on", "off", "zero"):
            run_config = _condition_config(config, seed, condition)
            manifest = run_learning_experiment(
                run_config,
                artifact_directory=artifact_directory / f"seed_{seed}_{condition}",
                project_root=project_root,
            )
            simulations[(seed, condition)] = simulate_learning(run_config)
            identities[(seed, condition)] = (manifest.config_id, manifest.event_hash)
    summary = _summary(config, simulations, identities)
    (artifact_directory / "sensitivity_config.json").write_text(
        config.to_json() + "\n", encoding="utf-8"
    )
    (artifact_directory / "future_suite_config.json").write_text(
        config.future_suite.to_json() + "\n", encoding="utf-8"
    )
    (artifact_directory / "analysis.json").write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def verify_plasticity_sensitivity(artifact_directory: Path) -> dict[str, JsonValue]:
    config = PlasticitySensitivityConfig.from_json(
        (artifact_directory / "sensitivity_config.json").read_text(encoding="utf-8").rstrip()
    )
    if (artifact_directory / "future_suite_config.json").read_text(
        encoding="utf-8"
    ).rstrip() != config.future_suite.to_json():
        raise ValueError("future suite preregistration diverged")
    simulations: dict[tuple[int, str], LearningSimulation] = {}
    identities: dict[tuple[int, str], tuple[str, str]] = {}
    for seed in config.development_seeds:
        for condition in ("on", "off", "zero"):
            directory = artifact_directory / f"seed_{seed}_{condition}"
            manifest = verify_learning_replay(directory)
            run_config = _condition_config(config, seed, condition)
            if manifest.config_id != run_config.config_id:
                raise ValueError("sensitivity child config diverged")
            simulations[(seed, condition)] = simulate_learning(run_config)
            identities[(seed, condition)] = (manifest.config_id, manifest.event_hash)
    recomputed = _summary(config, simulations, identities)
    stored_raw: object = json.loads(
        (artifact_directory / "analysis.json").read_text(encoding="utf-8")
    )
    if recomputed != stored_raw:
        raise ValueError("sensitivity analysis replay diverged")
    return recomputed


def _binary_margin_analysis(config: PlasticitySensitivityConfig) -> dict[str, JsonValue]:
    records: list[JsonValue] = []
    for seed in config.development_seeds:
        for condition in ("on", "off", "zero"):
            run_config = _condition_config(config, seed, condition)
            records.append(
                {
                    "condition": condition,
                    "margins": analyze_binary_action_margins(simulate_learning(run_config)),
                    "seed": seed,
                }
            )
    priors = config.candidate_genome.brain_priors
    assert priors is not None
    return {
        "binary_output_biases": list(priors[-4:]),
        "records": records,
        "sensitivity_config_id": config.config_id,
    }


def write_binary_margin_analysis(artifact_directory: Path) -> dict[str, JsonValue]:
    """Write deterministic margin analysis beside an existing sensitivity run."""
    config = PlasticitySensitivityConfig.from_json(
        (artifact_directory / "sensitivity_config.json").read_text(encoding="utf-8").rstrip()
    )
    analysis = _binary_margin_analysis(config)
    (artifact_directory / "margin_analysis.json").write_text(
        json.dumps(analysis, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return analysis


def verify_binary_margin_analysis(artifact_directory: Path) -> dict[str, JsonValue]:
    """Verify all child replays and recompute the stored binary margin analysis."""
    verify_plasticity_sensitivity(artifact_directory)
    config = PlasticitySensitivityConfig.from_json(
        (artifact_directory / "sensitivity_config.json").read_text(encoding="utf-8").rstrip()
    )
    recomputed = _binary_margin_analysis(config)
    stored: object = json.loads(
        (artifact_directory / "margin_analysis.json").read_text(encoding="utf-8")
    )
    if recomputed != stored:
        raise ValueError("binary margin analysis replay diverged")
    return recomputed
