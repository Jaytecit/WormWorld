"""Development-only Phase 3 robustness screen across plasticity rates."""

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
from worm_world.experiments.learning_sensitivity import compare_action_divergence
from worm_world.experiments.learning_survival_gate import SurvivalGateConfig
from worm_world.genetics import Genome
from worm_world.schemas import JsonValue

ROBUSTNESS_SCREEN_SCHEMA_VERSION = 1
ROBUSTNESS_SCREEN_TYPE = "phase3_development_robustness_screen"
ROBUSTNESS_RATES = (0.25, 0.5, 1.0)
CONSUMED_HELDOUT_SEEDS = frozenset((*range(201, 206), *range(301, 306)))


@dataclass(frozen=True, slots=True)
class RobustnessScreenConfig:
    """Locked development inputs for a bounded semantic-plasticity rate screen."""

    development_seeds: tuple[int, ...]
    founder_genome: Genome
    rates: tuple[float, ...] = ROBUSTNESS_RATES
    founder_count: int = 4
    step_count: int = 384
    eligibility_rule: str = "action_activation"
    experiment_type: str = ROBUSTNESS_SCREEN_TYPE
    schema_version: int = ROBUSTNESS_SCREEN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if len(self.development_seeds) < 10 or len(set(self.development_seeds)) != len(
            self.development_seeds
        ):
            raise ValueError("development_seeds requires at least ten distinct seeds")
        if any(
            isinstance(seed, bool) or not 0 <= seed <= MAX_SEED for seed in self.development_seeds
        ):
            raise ValueError("development_seeds contains an invalid seed")
        if set(self.development_seeds) & CONSUMED_HELDOUT_SEEDS:
            raise ValueError("development_seeds reuses a consumed held-out seed")
        if self.rates != ROBUSTNESS_RATES:
            raise ValueError("rates must be exactly (0.25, 0.5, 1.0)")
        if self.founder_genome.schema_version != 2:
            raise ValueError("robustness screen requires a version-2 founder genome")
        if self.founder_genome.plasticity_rate is None:
            raise ValueError("founder genome must encode a plasticity rate")
        if isinstance(self.founder_count, bool) or not 1 <= self.founder_count <= 16:
            raise ValueError("founder_count must be in [1, 16]")
        if isinstance(self.step_count, bool) or self.step_count < 1:
            raise ValueError("step_count must be positive")
        if self.eligibility_rule != "action_activation":
            raise ValueError("robustness screen requires action-semantic eligibility")
        if self.experiment_type != ROBUSTNESS_SCREEN_TYPE:
            raise ValueError("unsupported robustness screen type")
        if self.schema_version != ROBUSTNESS_SCREEN_SCHEMA_VERSION:
            raise ValueError("unsupported robustness screen schema version")

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
            raise ValueError("robustness screen configuration must be an object")
        raw = cast(dict[str, Any], decoded)
        sample = cls(
            tuple(range(1, 11)),
            LearningExperimentConfig.training_fixture(0, plasticity_enabled=True).founder_genome,
        )
        if set(raw) != set(asdict(sample)):
            raise ValueError("robustness screen configuration has missing or unknown fields")
        return cls(
            development_seeds=tuple(raw["development_seeds"]),
            founder_genome=Genome.from_json(json.dumps(raw["founder_genome"])),
            rates=tuple(raw["rates"]),
            founder_count=raw["founder_count"],
            step_count=raw["step_count"],
            eligibility_rule=raw["eligibility_rule"],
            experiment_type=raw["experiment_type"],
            schema_version=raw["schema_version"],
        )


def _condition_config(
    config: RobustnessScreenConfig, rate: float, seed: int, condition: str
) -> LearningExperimentConfig:
    rate_genome = replace(config.founder_genome, plasticity_rate=rate)
    if condition == "on":
        genome, enabled = rate_genome, True
    elif condition == "off":
        genome, enabled = rate_genome, False
    elif condition == "zero":
        genome, enabled = replace(rate_genome, plasticity_rate=0.0), True
    else:
        raise ValueError("unknown robustness screen condition")
    return LearningExperimentConfig.training_fixture(
        seed,
        plasticity_enabled=enabled,
        founder_count=config.founder_count,
        step_count=config.step_count,
        founder_genome=genome,
        eligibility_rule="action_activation",
    )


def _outcomes(
    run_config: LearningExperimentConfig, simulation: LearningSimulation
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
    mean_energy_fraction = (
        sum(float(cast(int | float, value)) for value in energies)
        / len(energies)
        / run_config.founder_genome.max_energy
        if energies
        else 0.0
    )
    return {
        "births": simulation.report.births,
        "deaths": simulation.report.deaths,
        "extinct": not active,
        "final_population": len(active),
        "mean_energy_fraction": mean_energy_fraction,
        "surviving_descendants": len(descendants),
    }


def _reports_match_except_flag(first: LearningSimulation, second: LearningSimulation) -> bool:
    left = first.report.to_dict()
    right = second.report.to_dict()
    left.pop("plasticity_enabled")
    right.pop("plasticity_enabled")
    return left == right


def _controls_identical(first: LearningSimulation, second: LearningSimulation) -> bool:
    divergence = compare_action_divergence(first, second)
    return (
        divergence.maximum_output_delta == 0.0
        and divergence.continuous_motion_divergences == 0
        and divergence.eat_divergences == 0
        and divergence.drink_divergences == 0
        and divergence.rest_divergences == 0
        and divergence.reproduce_divergences == 0
        and _reports_match_except_flag(first, second)
    )


def select_robustness_candidate_rate(
    rate_records: list[dict[str, JsonValue]],
) -> float | None:
    """Choose the lowest qualified rate; input ordering cannot affect selection."""
    qualified = [
        float(cast(int | float, record["rate"]))
        for record in rate_records
        if record.get("qualified") is True
    ]
    return min(qualified) if qualified else None


def _summary(
    config: RobustnessScreenConfig,
    simulations: dict[tuple[float, int, str], LearningSimulation],
    identities: dict[tuple[float, int, str], tuple[str, str]],
) -> dict[str, JsonValue]:
    rate_records: list[dict[str, JsonValue]] = []
    for rate in config.rates:
        records: list[JsonValue] = []
        population_differences: list[int] = []
        all_controls_identical = True
        all_learning_survived = True
        for seed in config.development_seeds:
            on = simulations[(rate, seed, "on")]
            off = simulations[(rate, seed, "off")]
            zero = simulations[(rate, seed, "zero")]
            outcomes = {
                condition: _outcomes(_condition_config(config, rate, seed, condition), simulation)
                for condition, simulation in (("on", on), ("off", off), ("zero", zero))
            }
            on_outcomes = outcomes["on"]
            off_outcomes = outcomes["off"]
            population_difference = cast(int, on_outcomes["final_population"]) - cast(
                int, off_outcomes["final_population"]
            )
            controls_identical = _controls_identical(off, zero)
            population_differences.append(population_difference)
            all_controls_identical &= controls_identical
            all_learning_survived &= on_outcomes["extinct"] is False
            records.append(
                {
                    "conditions": {
                        condition: {
                            "config_id": identities[(rate, seed, condition)][0],
                            "event_hash": identities[(rate, seed, condition)][1],
                            "outcomes": outcome,
                        }
                        for condition, outcome in outcomes.items()
                    },
                    "off_zero_identical": controls_identical,
                    "population_difference": population_difference,
                    "seed": seed,
                }
            )
        qualified = (
            all_controls_identical
            and all_learning_survived
            and all(difference > 0 for difference in population_differences)
        )
        rate_records.append(
            {
                "all_learning_survived": all_learning_survived,
                "minimum_population_difference": min(population_differences),
                "population_differences": cast(list[JsonValue], population_differences),
                "population_mean_difference": sum(population_differences)
                / len(population_differences),
                "qualified": qualified,
                "rate": rate,
                "records": records,
                "zero_controls_identical": all_controls_identical,
            }
        )
    selected_rate = select_robustness_candidate_rate(rate_records)
    selected_genome = (
        replace(config.founder_genome, plasticity_rate=selected_rate)
        if selected_rate is not None
        else None
    )
    return {
        "candidate_found": selected_rate is not None,
        "candidate_genome_id": selected_genome.genome_id if selected_genome is not None else None,
        "rate_records": cast(list[JsonValue], rate_records),
        "robustness_screen_config_id": config.config_id,
        "selected_rate": selected_rate,
        "selection_rule": (
            "lowest rate with positive population difference and no learning extinction on every "
            "seed, with exact off/zero identity"
        ),
    }


def run_robustness_screen(
    config: RobustnessScreenConfig, *, artifact_directory: Path, project_root: Path
) -> dict[str, JsonValue]:
    """Run and retain every rate/seed/condition child artifact."""
    artifact_directory.mkdir(parents=True, exist_ok=False)
    simulations: dict[tuple[float, int, str], LearningSimulation] = {}
    identities: dict[tuple[float, int, str], tuple[str, str]] = {}
    for rate in config.rates:
        rate_label = str(rate).replace(".", "p")
        for seed in config.development_seeds:
            for condition in ("on", "off", "zero"):
                run_config = _condition_config(config, rate, seed, condition)
                manifest = run_learning_experiment(
                    run_config,
                    artifact_directory=artifact_directory
                    / f"rate_{rate_label}_seed_{seed}_{condition}",
                    project_root=project_root,
                )
                simulations[(rate, seed, condition)] = simulate_learning(run_config)
                identities[(rate, seed, condition)] = (manifest.config_id, manifest.event_hash)
    summary = _summary(config, simulations, identities)
    (artifact_directory / "robustness_screen_config.json").write_text(
        config.to_json() + "\n", encoding="utf-8"
    )
    (artifact_directory / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def verify_robustness_screen(artifact_directory: Path) -> dict[str, JsonValue]:
    """Replay every child and recompute the deterministic rate matrix and selection."""
    config = RobustnessScreenConfig.from_json(
        (artifact_directory / "robustness_screen_config.json").read_text(encoding="utf-8").rstrip()
    )
    simulations: dict[tuple[float, int, str], LearningSimulation] = {}
    identities: dict[tuple[float, int, str], tuple[str, str]] = {}
    for rate in config.rates:
        rate_label = str(rate).replace(".", "p")
        for seed in config.development_seeds:
            for condition in ("on", "off", "zero"):
                directory = artifact_directory / f"rate_{rate_label}_seed_{seed}_{condition}"
                manifest = verify_learning_replay(directory)
                run_config = _condition_config(config, rate, seed, condition)
                if manifest.config_id != run_config.config_id:
                    raise ValueError("robustness child config diverged")
                simulations[(rate, seed, condition)] = simulate_learning(run_config)
                identities[(rate, seed, condition)] = (manifest.config_id, manifest.event_hash)
    recomputed = _summary(config, simulations, identities)
    stored: object = json.loads((artifact_directory / "summary.json").read_text(encoding="utf-8"))
    if recomputed != stored:
        raise ValueError("robustness screen replay diverged")
    return recomputed


def write_robustness_survival_preregistration(
    *,
    robustness_directory: Path,
    artifact_directory: Path,
    heldout_seeds: tuple[int, ...],
) -> SurvivalGateConfig:
    """Bind a fresh, unexecuted held-out suite to a qualified robustness candidate."""
    summary = verify_robustness_screen(robustness_directory)
    screen = RobustnessScreenConfig.from_json(
        (robustness_directory / "robustness_screen_config.json")
        .read_text(encoding="utf-8")
        .rstrip()
    )
    selected = summary.get("selected_rate")
    if (
        summary.get("candidate_found") is not True
        or isinstance(selected, bool)
        or not isinstance(selected, int | float)
    ):
        raise ValueError("robustness screen did not qualify a candidate")
    if len(heldout_seeds) < 5 or len(set(heldout_seeds)) != len(heldout_seeds):
        raise ValueError("heldout_seeds requires at least five distinct seeds")
    if any(isinstance(seed, bool) or not 0 <= seed <= MAX_SEED for seed in heldout_seeds):
        raise ValueError("heldout_seeds contains an invalid seed")
    if set(heldout_seeds) & (set(screen.development_seeds) | CONSUMED_HELDOUT_SEEDS):
        raise ValueError("heldout_seeds must be fresh and disjoint")
    gate = SurvivalGateConfig(
        development_seeds=screen.development_seeds,
        heldout_seeds=heldout_seeds,
        founder_genome=replace(screen.founder_genome, plasticity_rate=float(selected)),
        development_evidence_id=screen.config_id,
        founder_count=screen.founder_count,
        step_count=screen.step_count,
    )
    artifact_directory.mkdir(parents=True, exist_ok=False)
    (artifact_directory / "survival_gate_config.json").write_text(
        gate.to_json() + "\n", encoding="utf-8"
    )
    (artifact_directory / "robustness_evidence.json").write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return gate


def verify_robustness_survival_preregistration(
    artifact_directory: Path, *, robustness_directory: Path
) -> SurvivalGateConfig:
    """Verify candidate evidence and the frozen held-out contract without executing it."""
    summary = verify_robustness_screen(robustness_directory)
    stored_evidence: object = json.loads(
        (artifact_directory / "robustness_evidence.json").read_text(encoding="utf-8")
    )
    if summary != stored_evidence:
        raise ValueError("robustness preregistration evidence diverged")
    screen = RobustnessScreenConfig.from_json(
        (robustness_directory / "robustness_screen_config.json")
        .read_text(encoding="utf-8")
        .rstrip()
    )
    gate = SurvivalGateConfig.from_json(
        (artifact_directory / "survival_gate_config.json").read_text(encoding="utf-8").rstrip()
    )
    selected = summary.get("selected_rate")
    if isinstance(selected, bool) or not isinstance(selected, int | float):
        raise ValueError("robustness preregistration has no selected rate")
    expected_genome = replace(screen.founder_genome, plasticity_rate=float(selected))
    if (
        summary.get("candidate_found") is not True
        or gate.development_seeds != screen.development_seeds
        or gate.founder_genome != expected_genome
        or gate.development_evidence_id != screen.config_id
        or gate.founder_count != screen.founder_count
        or gate.step_count != screen.step_count
        or set(gate.heldout_seeds) & (set(screen.development_seeds) | CONSUMED_HELDOUT_SEEDS)
    ):
        raise ValueError("robustness survival preregistration diverged")
    return gate
