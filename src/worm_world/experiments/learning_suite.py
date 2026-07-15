"""Predeclared matched development/held-out evaluation for Phase 3."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Self, cast

from worm_world.experiments.config import MAX_SEED
from worm_world.experiments.learning import (
    LearningExperimentConfig,
    LearningRunReport,
    run_learning_experiment,
    simulate_learning,
    verify_learning_replay,
)
from worm_world.genetics import Genome
from worm_world.learning import EligibilityRule
from worm_world.rng import NamedRandomStreams
from worm_world.schemas import JsonValue

LEARNING_SUITE_SCHEMA_VERSION = 1
LATEST_LEARNING_SUITE_SCHEMA_VERSION = 2
LEARNING_SUITE_TYPE = "matched_heldout_learning_evaluation"


@dataclass(frozen=True, slots=True)
class LearningGateCriteria:
    """Predeclared aggregate thresholds; values are experiment inputs."""

    minimum_birth_mean_advantage: float = 0.25
    minimum_birth_ci_lower: float = 0.0
    minimum_population_mean_advantage: float = 0.25
    minimum_population_ci_lower: float = 0.0
    minimum_energy_ci_lower: float = -0.02
    minimum_paired_win_fraction: float = 2.0 / 3.0

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not 0.0 <= self.minimum_paired_win_fraction <= 1.0:
            raise ValueError("minimum_paired_win_fraction must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class LearningSuiteConfig:
    """Locked seed partitions, genome, statistics, and gate criteria."""

    development_seeds: tuple[int, ...]
    heldout_seeds: tuple[int, ...]
    founder_genome: Genome = field(
        default_factory=lambda: (
            LearningExperimentConfig.training_fixture(0, plasticity_enabled=True).founder_genome
        )
    )
    founder_count: int = 4
    step_count: int = 64
    bootstrap_seed: int = 918_273
    bootstrap_samples: int = 2_000
    confidence_level: float = 0.95
    criteria: LearningGateCriteria = field(default_factory=LearningGateCriteria)
    experiment_type: str = LEARNING_SUITE_TYPE
    eligibility_rule: EligibilityRule = "legacy_tanh"
    schema_version: int = LEARNING_SUITE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, seeds, minimum in (
            ("development_seeds", self.development_seeds, 1),
            ("heldout_seeds", self.heldout_seeds, 3),
        ):
            if len(seeds) < minimum or len(set(seeds)) != len(seeds):
                raise ValueError(f"{name} requires at least {minimum} distinct seeds")
            if any(isinstance(seed, bool) or not 0 <= seed <= MAX_SEED for seed in seeds):
                raise ValueError(f"{name} contains an invalid seed")
        if set(self.development_seeds) & set(self.heldout_seeds):
            raise ValueError("development and held-out seeds must be disjoint")
        if isinstance(self.founder_count, bool) or not 1 <= self.founder_count <= 16:
            raise ValueError("founder_count must be in [1, 16]")
        if isinstance(self.step_count, bool) or self.step_count < 1:
            raise ValueError("step_count must be positive")
        if isinstance(self.bootstrap_seed, bool) or not 0 <= self.bootstrap_seed <= MAX_SEED:
            raise ValueError("bootstrap_seed is invalid")
        if isinstance(self.bootstrap_samples, bool) or self.bootstrap_samples < 100:
            raise ValueError("bootstrap_samples must be at least 100")
        if not math.isfinite(self.confidence_level) or not 0.5 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be in (0.5, 1)")
        if self.founder_genome.schema_version != 2:
            raise ValueError("learning suite requires a version-2 founder genome")
        if self.experiment_type != LEARNING_SUITE_TYPE:
            raise ValueError("unsupported learning suite type")
        if self.schema_version not in (
            LEARNING_SUITE_SCHEMA_VERSION,
            LATEST_LEARNING_SUITE_SCHEMA_VERSION,
        ):
            raise ValueError("unsupported learning suite schema version")
        if self.schema_version == LEARNING_SUITE_SCHEMA_VERSION:
            if self.eligibility_rule != "legacy_tanh":
                raise ValueError("version-1 learning suites require the legacy eligibility rule")
        elif self.eligibility_rule not in ("legacy_tanh", "action_activation"):
            raise ValueError("unknown eligibility rule")

    def to_json(self) -> str:
        values = asdict(self)
        values["founder_genome"] = self.founder_genome.to_dict()
        if self.schema_version == LEARNING_SUITE_SCHEMA_VERSION:
            values.pop("eligibility_rule")
        return json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def config_id(self) -> str:
        return hashlib.sha256(self.to_json().encode()).hexdigest()

    @classmethod
    def from_json(cls, serialized: str) -> Self:
        decoded: object = json.loads(serialized)
        if not isinstance(decoded, dict):
            raise ValueError("learning suite configuration must be an object")
        raw = cast(dict[str, Any], decoded)
        if "schema_version" not in raw:
            raise ValueError("learning suite configuration has missing or unknown fields")
        version = raw.get("schema_version")
        expected = set(asdict(cls((1,), (2, 3, 4))))
        if version == LEARNING_SUITE_SCHEMA_VERSION:
            expected.remove("eligibility_rule")
        elif version != LATEST_LEARNING_SUITE_SCHEMA_VERSION:
            raise ValueError("unsupported learning suite schema version")
        if set(raw) != expected:
            raise ValueError("learning suite configuration has missing or unknown fields")
        return cls(
            development_seeds=tuple(raw["development_seeds"]),
            heldout_seeds=tuple(raw["heldout_seeds"]),
            founder_genome=Genome.from_json(json.dumps(raw["founder_genome"])),
            founder_count=raw["founder_count"],
            step_count=raw["step_count"],
            bootstrap_seed=raw["bootstrap_seed"],
            bootstrap_samples=raw["bootstrap_samples"],
            confidence_level=raw["confidence_level"],
            criteria=LearningGateCriteria(**raw["criteria"]),
            experiment_type=raw["experiment_type"],
            eligibility_rule=raw.get("eligibility_rule", "legacy_tanh"),
            schema_version=raw["schema_version"],
        )


@dataclass(frozen=True, slots=True)
class SuiteRunRecord:
    split: Literal["development", "heldout"]
    seed: int
    plasticity_enabled: bool
    report: LearningRunReport
    mean_energy_fraction: float
    mean_hydration_fraction: float
    mean_injury_fraction: float
    config_id: str
    event_hash: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "config_id": self.config_id,
            "event_hash": self.event_hash,
            "mean_energy_fraction": self.mean_energy_fraction,
            "mean_hydration_fraction": self.mean_hydration_fraction,
            "mean_injury_fraction": self.mean_injury_fraction,
            "plasticity_enabled": self.plasticity_enabled,
            "report": self.report.to_dict(),
            "seed": self.seed,
            "split": self.split,
        }


def _condition_config(
    config: LearningSuiteConfig, seed: int, enabled: bool
) -> LearningExperimentConfig:
    return LearningExperimentConfig.training_fixture(
        seed,
        plasticity_enabled=enabled,
        founder_count=config.founder_count,
        step_count=config.step_count,
        founder_genome=config.founder_genome,
        eligibility_rule=config.eligibility_rule,
    )


def _mean_homeostasis(
    config: LearningExperimentConfig,
) -> tuple[float, float, float]:
    simulation = simulate_learning(config)
    organisms = simulation.snapshots[-1].state["organisms"]
    if not isinstance(organisms, list):
        raise ValueError("final snapshot organisms must be an array")
    active = [
        cast(dict[str, JsonValue], organism)
        for organism in organisms
        if isinstance(organism, dict) and organism.get("active") is True
    ]
    if not active:
        return (0.0, 0.0, 1.0)

    def mean_fraction(name: str, maximum: float) -> float:
        values = [organism[name] for organism in active]
        if any(isinstance(value, bool) or not isinstance(value, int | float) for value in values):
            raise ValueError(f"final {name} values must be numeric")
        return sum(float(cast(int | float, value)) / maximum for value in values) / len(values)

    return (
        mean_fraction("energy", config.founder_genome.max_energy),
        mean_fraction("hydration", config.founder_genome.max_hydration),
        mean_fraction("injury", 1.0),
    )


def _record(
    split: Literal["development", "heldout"],
    config: LearningExperimentConfig,
    artifact_directory: Path,
    project_root: Path,
) -> SuiteRunRecord:
    manifest = run_learning_experiment(
        config, artifact_directory=artifact_directory, project_root=project_root
    )
    report = simulate_learning(config).report
    energy, hydration, injury = _mean_homeostasis(config)
    return SuiteRunRecord(
        split,
        config.seed,
        config.plasticity_enabled,
        report,
        energy,
        hydration,
        injury,
        manifest.config_id,
        manifest.event_hash,
    )


def _bootstrap_summary(
    values: list[float], rng: random.Random, samples: int, confidence_level: float
) -> dict[str, JsonValue]:
    if not values:
        raise ValueError("paired summary requires at least one value")
    means = sorted(
        sum(values[rng.randrange(len(values))] for _ in values) / len(values)
        for _ in range(samples)
    )
    alpha = (1.0 - confidence_level) / 2.0
    lower = means[math.floor(alpha * (samples - 1))]
    upper = means[math.ceil((1.0 - alpha) * (samples - 1))]
    return {
        "ci_lower": lower,
        "ci_upper": upper,
        "confidence_level": confidence_level,
        "mean": sum(values) / len(values),
        "paired_differences": cast(list[JsonValue], values),
    }


def _paired_statistics(
    config: LearningSuiteConfig, records: list[SuiteRunRecord]
) -> dict[str, JsonValue]:
    heldout = [record for record in records if record.split == "heldout"]
    pairs = {
        seed: {record.plasticity_enabled: record for record in heldout if record.seed == seed}
        for seed in config.heldout_seeds
    }
    if any(set(pair) != {False, True} for pair in pairs.values()):
        raise ValueError("every held-out seed requires matched conditions")
    metric_values: dict[str, list[float]] = {
        "births": [],
        "final_population": [],
        "mean_energy_fraction": [],
        "mean_hydration_fraction": [],
        "mean_injury_fraction": [],
    }
    wins = 0
    for seed in config.heldout_seeds:
        enabled = pairs[seed][True]
        disabled = pairs[seed][False]
        birth_difference = enabled.report.births - disabled.report.births
        population_difference = enabled.report.final_population - disabled.report.final_population
        metric_values["births"].append(float(birth_difference))
        metric_values["final_population"].append(float(population_difference))
        metric_values["mean_energy_fraction"].append(
            enabled.mean_energy_fraction - disabled.mean_energy_fraction
        )
        metric_values["mean_hydration_fraction"].append(
            enabled.mean_hydration_fraction - disabled.mean_hydration_fraction
        )
        metric_values["mean_injury_fraction"].append(
            disabled.mean_injury_fraction - enabled.mean_injury_fraction
        )
        if birth_difference > 0 and population_difference > 0:
            wins += 1
    streams = NamedRandomStreams(config.bootstrap_seed)
    statistics: dict[str, JsonValue] = {
        metric: _bootstrap_summary(
            values,
            streams.stream(f"phase3-bootstrap-{metric}"),
            config.bootstrap_samples,
            config.confidence_level,
        )
        for metric, values in metric_values.items()
    }
    statistics["paired_win_fraction"] = wins / len(config.heldout_seeds)
    statistics["difference_direction"] = (
        "positive favors plasticity-on; injury is plasticity-off minus plasticity-on"
    )
    return statistics


def _summary(
    config: LearningSuiteConfig,
    records: list[SuiteRunRecord],
    hardware: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    statistics = _paired_statistics(config, records)
    births = cast(dict[str, JsonValue], statistics["births"])
    population = cast(dict[str, JsonValue], statistics["final_population"])
    energy = cast(dict[str, JsonValue], statistics["mean_energy_fraction"])
    criteria = config.criteria
    passed = (
        cast(float, births["mean"]) > criteria.minimum_birth_mean_advantage
        and cast(float, births["ci_lower"]) > criteria.minimum_birth_ci_lower
        and cast(float, population["mean"]) > criteria.minimum_population_mean_advantage
        and cast(float, population["ci_lower"]) > criteria.minimum_population_ci_lower
        and cast(float, energy["ci_lower"]) >= criteria.minimum_energy_ci_lower
        and cast(float, statistics["paired_win_fraction"]) >= criteria.minimum_paired_win_fraction
    )
    return {
        "acceptance_passed": passed,
        "criteria": cast(dict[str, JsonValue], asdict(criteria)),
        "hardware": hardware,
        "records": [record.to_dict() for record in records],
        "statistics": statistics,
        "suite_config_id": config.config_id,
    }


def run_learning_evaluation_suite(
    config: LearningSuiteConfig,
    *,
    artifact_directory: Path,
    project_root: Path,
) -> dict[str, JsonValue]:
    artifact_directory.mkdir(parents=True, exist_ok=False)
    records: list[SuiteRunRecord] = []
    for split, seeds in (
        ("development", config.development_seeds),
        ("heldout", config.heldout_seeds),
    ):
        for seed in seeds:
            for enabled, label in ((True, "on"), (False, "off")):
                run_config = _condition_config(config, seed, enabled)
                records.append(
                    _record(
                        cast(Literal["development", "heldout"], split),
                        run_config,
                        artifact_directory / f"{split}_seed_{seed}_{label}",
                        project_root,
                    )
                )
    hardware: dict[str, JsonValue] = {
        "machine": platform.machine(),
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
    summary = _summary(config, records, hardware)
    (artifact_directory / "suite_config.json").write_text(config.to_json() + "\n", encoding="utf-8")
    (artifact_directory / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def verify_learning_evaluation_suite(artifact_directory: Path) -> dict[str, JsonValue]:
    config = LearningSuiteConfig.from_json(
        (artifact_directory / "suite_config.json").read_text(encoding="utf-8").rstrip()
    )
    stored_raw: object = json.loads(
        (artifact_directory / "summary.json").read_text(encoding="utf-8")
    )
    if not isinstance(stored_raw, dict):
        raise ValueError("learning suite summary must be an object")
    stored = cast(dict[str, JsonValue], stored_raw)
    hardware = stored.get("hardware")
    if not isinstance(hardware, dict):
        raise ValueError("learning suite hardware must be an object")
    records: list[SuiteRunRecord] = []
    for split, seeds in (
        ("development", config.development_seeds),
        ("heldout", config.heldout_seeds),
    ):
        for seed in seeds:
            for enabled, label in ((True, "on"), (False, "off")):
                directory = artifact_directory / f"{split}_seed_{seed}_{label}"
                manifest = verify_learning_replay(directory)
                run_config = _condition_config(config, seed, enabled)
                if manifest.config_id != run_config.config_id:
                    raise ValueError("suite condition config does not match its locked input")
                report = LearningRunReport.from_json(
                    (directory / "report.json").read_text(encoding="utf-8").rstrip()
                )
                energy, hydration, injury = _mean_homeostasis(run_config)
                records.append(
                    SuiteRunRecord(
                        cast(Literal["development", "heldout"], split),
                        seed,
                        enabled,
                        report,
                        energy,
                        hydration,
                        injury,
                        manifest.config_id,
                        manifest.event_hash,
                    )
                )
    recomputed = _summary(config, records, hardware)
    if recomputed != stored:
        raise ValueError("learning suite summary replay diverged")
    return stored
