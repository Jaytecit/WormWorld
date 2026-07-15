"""Versioned survival-focused Phase 3 gate preregistration and development authorization."""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Self, cast

from worm_world.experiments.config import MAX_SEED
from worm_world.experiments.learning import (
    LearningExperimentConfig,
    LearningSimulation,
    simulate_learning,
)
from worm_world.experiments.learning_sensitivity import (
    PlasticitySensitivityConfig,
    verify_plasticity_sensitivity,
)
from worm_world.genetics import Genome
from worm_world.rng import NamedRandomStreams
from worm_world.schemas import JsonValue

SURVIVAL_GATE_SCHEMA_VERSION = 1
SURVIVAL_GATE_TYPE = "phase3_survival_confirmation"


@dataclass(frozen=True, slots=True)
class SurvivalGateCriteria:
    """Frozen lifetime-learning criteria that do not treat birth count as a reward."""

    minimum_population_mean_advantage: float = 1.0
    minimum_population_ci_lower: float = 0.0
    minimum_energy_ci_lower: float = 0.0
    minimum_seed_win_fraction: float = 1.0
    maximum_learning_extinction_fraction: float = 0.0
    minimum_control_extinction_fraction: float = 0.4

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        for name, value in (
            ("minimum_seed_win_fraction", self.minimum_seed_win_fraction),
            ("maximum_learning_extinction_fraction", self.maximum_learning_extinction_fraction),
            ("minimum_control_extinction_fraction", self.minimum_control_extinction_fraction),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class SurvivalGateConfig:
    """Complete unexecuted confirmation contract plus development evidence identity."""

    development_seeds: tuple[int, ...]
    heldout_seeds: tuple[int, ...]
    founder_genome: Genome
    development_evidence_id: str
    founder_count: int = 4
    step_count: int = 384
    bootstrap_seed: int = 918_273
    bootstrap_samples: int = 2_000
    confidence_level: float = 0.95
    criteria: SurvivalGateCriteria = SurvivalGateCriteria()
    eligibility_rule: str = "action_activation"
    experiment_type: str = SURVIVAL_GATE_TYPE
    schema_version: int = SURVIVAL_GATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, seeds, minimum in (
            ("development_seeds", self.development_seeds, 3),
            ("heldout_seeds", self.heldout_seeds, 5),
        ):
            if len(seeds) < minimum or len(set(seeds)) != len(seeds):
                raise ValueError(f"{name} requires at least {minimum} distinct seeds")
            if any(isinstance(seed, bool) or not 0 <= seed <= MAX_SEED for seed in seeds):
                raise ValueError(f"{name} contains an invalid seed")
        if set(self.development_seeds) & set(self.heldout_seeds):
            raise ValueError("development and held-out seeds must be disjoint")
        if len(self.development_evidence_id) != 64 or any(
            character not in "0123456789abcdef" for character in self.development_evidence_id
        ):
            raise ValueError("development_evidence_id must be a SHA-256 digest")
        if self.founder_genome.schema_version != 2:
            raise ValueError("survival gate requires a version-2 founder genome")
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
        if self.eligibility_rule != "action_activation":
            raise ValueError("survival confirmation requires action-semantic eligibility")
        if self.experiment_type != SURVIVAL_GATE_TYPE:
            raise ValueError("unsupported survival gate type")
        if self.schema_version != SURVIVAL_GATE_SCHEMA_VERSION:
            raise ValueError("unsupported survival gate schema version")

    def to_json(self) -> str:
        values = asdict(self)
        values["founder_genome"] = self.founder_genome.to_dict()
        return json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def config_id(self) -> str:
        return hashlib.sha256(self.to_json().encode()).hexdigest()

    @classmethod
    def from_json(cls, serialized: str) -> Self:
        decoded: object = json.loads(serialized)
        if not isinstance(decoded, dict):
            raise ValueError("survival gate configuration must be an object")
        raw = cast(dict[str, Any], decoded)
        sample = cls(
            (1, 2, 3),
            (4, 5, 6, 7, 8),
            LearningExperimentConfig.training_fixture(0, plasticity_enabled=True).founder_genome,
            "0" * 64,
        )
        if set(raw) != set(asdict(sample)):
            raise ValueError("survival gate configuration has missing or unknown fields")
        return cls(
            development_seeds=tuple(raw["development_seeds"]),
            heldout_seeds=tuple(raw["heldout_seeds"]),
            founder_genome=Genome.from_json(json.dumps(raw["founder_genome"])),
            development_evidence_id=raw["development_evidence_id"],
            founder_count=raw["founder_count"],
            step_count=raw["step_count"],
            bootstrap_seed=raw["bootstrap_seed"],
            bootstrap_samples=raw["bootstrap_samples"],
            confidence_level=raw["confidence_level"],
            criteria=SurvivalGateCriteria(**raw["criteria"]),
            eligibility_rule=raw["eligibility_rule"],
            experiment_type=raw["experiment_type"],
            schema_version=raw["schema_version"],
        )


def _condition_config(
    config: SurvivalGateConfig, seed: int, enabled: bool
) -> LearningExperimentConfig:
    return LearningExperimentConfig.training_fixture(
        seed,
        plasticity_enabled=enabled,
        founder_count=config.founder_count,
        step_count=config.step_count,
        founder_genome=config.founder_genome,
        eligibility_rule="action_activation",
    )


def _outcomes(
    config: LearningExperimentConfig, simulation: LearningSimulation
) -> dict[str, JsonValue]:
    organisms = simulation.snapshots[-1].state["organisms"]
    if not isinstance(organisms, list):
        raise ValueError("final organisms must be an array")
    active = [
        cast(dict[str, JsonValue], organism)
        for organism in organisms
        if isinstance(organism, dict) and organism.get("active") is True
    ]
    descendants = [organism for organism in active if organism.get("parent_ids") != []]
    energies = [organism["energy"] for organism in active]
    if any(isinstance(value, bool) or not isinstance(value, int | float) for value in energies):
        raise ValueError("active energy values must be numeric")
    mean_energy = (
        sum(float(cast(int | float, value)) for value in energies)
        / len(energies)
        / config.founder_genome.max_energy
        if energies
        else 0.0
    )
    return {
        "births": simulation.report.births,
        "deaths": simulation.report.deaths,
        "extinct": not active,
        "final_population": len(active),
        "mean_energy_fraction": mean_energy,
        "surviving_descendants": len(descendants),
    }


def _bootstrap(
    values: list[float], rng: random.Random, samples: int, confidence_level: float
) -> dict[str, JsonValue]:
    means = sorted(
        sum(values[rng.randrange(len(values))] for _ in values) / len(values)
        for _ in range(samples)
    )
    alpha = (1.0 - confidence_level) / 2.0
    return {
        "ci_lower": means[math.floor(alpha * (samples - 1))],
        "ci_upper": means[math.ceil((1.0 - alpha) * (samples - 1))],
        "confidence_level": confidence_level,
        "mean": sum(values) / len(values),
        "paired_differences": cast(list[JsonValue], values),
    }


def _authorization(
    config: SurvivalGateConfig,
    evidence: PlasticitySensitivityConfig,
    zero_controls_identical: bool,
) -> dict[str, JsonValue]:
    records: list[JsonValue] = []
    population_differences: list[float] = []
    energy_differences: list[float] = []
    learning_extinctions = control_extinctions = wins = 0
    for seed in config.development_seeds:
        on_config = _condition_config(config, seed, True)
        off_config = _condition_config(config, seed, False)
        on = _outcomes(on_config, simulate_learning(on_config))
        off = _outcomes(off_config, simulate_learning(off_config))
        population_difference = cast(int, on["final_population"]) - cast(
            int, off["final_population"]
        )
        energy_difference = cast(float, on["mean_energy_fraction"]) - cast(
            float, off["mean_energy_fraction"]
        )
        population_differences.append(float(population_difference))
        energy_differences.append(energy_difference)
        wins += population_difference > 0
        learning_extinctions += on["extinct"] is True
        control_extinctions += off["extinct"] is True
        records.append(
            {
                "off": off,
                "on": on,
                "population_difference": population_difference,
                "seed": seed,
            }
        )
    streams = NamedRandomStreams(config.bootstrap_seed)
    population = _bootstrap(
        population_differences,
        streams.stream("phase3-survival-population"),
        config.bootstrap_samples,
        config.confidence_level,
    )
    energy = _bootstrap(
        energy_differences,
        streams.stream("phase3-survival-energy"),
        config.bootstrap_samples,
        config.confidence_level,
    )
    count = len(config.development_seeds)
    win_fraction = wins / count
    learning_extinction_fraction = learning_extinctions / count
    control_extinction_fraction = control_extinctions / count
    criteria = config.criteria
    authorized = (
        evidence.config_id == config.development_evidence_id
        and zero_controls_identical
        and cast(float, population["mean"]) > criteria.minimum_population_mean_advantage
        and cast(float, population["ci_lower"]) > criteria.minimum_population_ci_lower
        and cast(float, energy["ci_lower"]) >= criteria.minimum_energy_ci_lower
        and win_fraction >= criteria.minimum_seed_win_fraction
        and learning_extinction_fraction <= criteria.maximum_learning_extinction_fraction
        and control_extinction_fraction >= criteria.minimum_control_extinction_fraction
    )
    return {
        "confirmation_authorized": authorized,
        "control_extinction_fraction": control_extinction_fraction,
        "development_evidence_id": evidence.config_id,
        "energy_statistics": energy,
        "learning_extinction_fraction": learning_extinction_fraction,
        "population_statistics": population,
        "records": records,
        "survival_gate_config_id": config.config_id,
        "win_fraction": win_fraction,
        "zero_controls_identical": zero_controls_identical,
    }


def write_survival_gate_preregistration(
    config: SurvivalGateConfig,
    *,
    artifact_directory: Path,
    development_evidence_directory: Path,
) -> dict[str, JsonValue]:
    summary = verify_plasticity_sensitivity(development_evidence_directory)
    evidence = PlasticitySensitivityConfig.from_json(
        (development_evidence_directory / "sensitivity_config.json")
        .read_text(encoding="utf-8")
        .rstrip()
    )
    if (
        evidence.development_seeds != config.development_seeds
        or evidence.future_heldout_seeds != config.heldout_seeds
        or evidence.candidate_genome != config.founder_genome
        or evidence.founder_count != config.founder_count
        or evidence.step_count != config.step_count
        or evidence.eligibility_rule != config.eligibility_rule
    ):
        raise ValueError("survival gate does not match its development evidence")
    zero_controls_identical = summary.get("zero_controls_identical") is True
    authorization = _authorization(config, evidence, zero_controls_identical)
    artifact_directory.mkdir(parents=True, exist_ok=False)
    (artifact_directory / "survival_gate_config.json").write_text(
        config.to_json() + "\n", encoding="utf-8"
    )
    (artifact_directory / "development_authorization.json").write_text(
        json.dumps(authorization, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return authorization


def verify_survival_gate_preregistration(
    artifact_directory: Path, *, development_evidence_directory: Path
) -> dict[str, JsonValue]:
    config = SurvivalGateConfig.from_json(
        (artifact_directory / "survival_gate_config.json").read_text(encoding="utf-8").rstrip()
    )
    summary = verify_plasticity_sensitivity(development_evidence_directory)
    evidence = PlasticitySensitivityConfig.from_json(
        (development_evidence_directory / "sensitivity_config.json")
        .read_text(encoding="utf-8")
        .rstrip()
    )
    recomputed = _authorization(config, evidence, summary.get("zero_controls_identical") is True)
    stored: object = json.loads(
        (artifact_directory / "development_authorization.json").read_text(encoding="utf-8")
    )
    if recomputed != stored:
        raise ValueError("survival gate authorization replay diverged")
    return recomputed
