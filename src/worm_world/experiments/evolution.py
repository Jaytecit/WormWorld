"""Phase 2 evolution experiment configuration, execution, and reporting."""

from __future__ import annotations

import hashlib
import json
import math
import platform
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from statistics import median
from typing import Any, Self, cast

from worm_world.experiments.config import MAX_SEED, WorldConfig
from worm_world.genetics import Genome, genetic_distance
from worm_world.organisms import WormAction
from worm_world.rng import NamedRandomStreams
from worm_world.schemas import JsonValue, ReplayManifest, SimulationEvent, WorldSnapshot
from worm_world.world import (
    Founder,
    InitialOrganismConfig,
    PopulationAction,
    PopulationWorld,
    ReproductionConfig,
    ResourceFieldConfig,
)

EVOLUTION_CONFIG_SCHEMA_VERSION = 1
EVOLUTION_EXPERIMENT_TYPE = "persistent_population_evolution"


@dataclass(frozen=True, slots=True)
class EvolutionExperimentConfig:
    """Complete replay input for one neutral-action selection run."""

    seed: int
    heritability_enabled: bool
    step_count: int = 500
    founder_pairs: int = 4
    snapshot_interval: int = 20
    world: WorldConfig = field(
        default_factory=lambda: WorldConfig(
            timestep_seconds=0.5, width_meters=10.0, height_meters=10.0
        )
    )
    resources: ResourceFieldConfig = field(
        default_factory=lambda: ResourceFieldConfig(
            food_x=5.0,
            food_y=5.0,
            food_energy=10_000.0,
            water_x=5.0,
            water_y=5.0,
            water_amount=10_000.0,
            eat_rate=0.5,
            drink_rate=0.5,
        )
    )
    reproduction: ReproductionConfig = field(
        default_factory=lambda: ReproductionConfig(
            mode="asexual",
            minimum_age_seconds=1.0,
            cooldown_seconds=5.0,
            maximum_population=512,
            mutation_enabled=False,
        )
    )
    low_metabolism_genome: Genome = field(
        default_factory=lambda: Genome(
            basal_energy_rate=0.05,
            basal_hydration_rate=0.0,
            movement_energy_rate=0.0,
            mutation_scale=0.0,
        )
    )
    high_metabolism_genome: Genome = field(
        default_factory=lambda: Genome(
            basal_energy_rate=1.0,
            basal_hydration_rate=0.0,
            movement_energy_rate=0.0,
            mutation_scale=0.0,
        )
    )
    experiment_type: str = EVOLUTION_EXPERIMENT_TYPE
    schema_version: int = EVOLUTION_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.reproduction.heritability_enabled != self.heritability_enabled:
            object.__setattr__(
                self,
                "reproduction",
                replace(self.reproduction, heritability_enabled=self.heritability_enabled),
            )
        if isinstance(self.seed, bool) or not 0 <= self.seed <= MAX_SEED:
            raise ValueError(f"seed must be an integer from 0 to {MAX_SEED}")
        if isinstance(self.step_count, bool) or self.step_count < 1:
            raise ValueError("step_count must be positive")
        if isinstance(self.founder_pairs, bool) or self.founder_pairs < 1:
            raise ValueError("founder_pairs must be positive")
        if isinstance(self.snapshot_interval, bool) or self.snapshot_interval < 1:
            raise ValueError("snapshot_interval must be positive")
        if self.reproduction.mode != "asexual":
            raise ValueError("acceptance experiment requires asexual reproduction")
        if (
            self.low_metabolism_genome.basal_energy_rate
            >= self.high_metabolism_genome.basal_energy_rate
        ):
            raise ValueError("low metabolism genome must have the lower basal energy rate")
        if self.experiment_type != EVOLUTION_EXPERIMENT_TYPE:
            raise ValueError("unsupported evolution experiment type")
        if self.schema_version != EVOLUTION_CONFIG_SCHEMA_VERSION:
            raise ValueError("unsupported evolution config schema version")

    def to_json(self) -> str:
        values = asdict(self)
        values["reproduction"]["heritability_enabled"] = self.heritability_enabled
        values["low_metabolism_genome"] = self.low_metabolism_genome.to_dict()
        values["high_metabolism_genome"] = self.high_metabolism_genome.to_dict()
        return json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def config_id(self) -> str:
        return hashlib.sha256(self.to_json().encode()).hexdigest()

    @classmethod
    def from_json(cls, serialized: str) -> Self:
        decoded: object = json.loads(serialized)
        if not isinstance(decoded, dict):
            raise ValueError("evolution configuration must be an object")
        raw = cast(dict[str, Any], decoded)
        expected = set(asdict(cls(seed=0, heritability_enabled=True)))
        if set(raw) != expected:
            raise ValueError("evolution configuration has missing or unknown fields")
        reproduction = dict(raw["reproduction"])
        heritability = bool(raw["heritability_enabled"])
        if reproduction["heritability_enabled"] != heritability:
            raise ValueError("heritability fields disagree")
        mode = reproduction.pop("mode")
        if mode not in ("asexual", "sexual"):
            raise ValueError("unknown reproduction mode")
        return cls(
            seed=raw["seed"],
            heritability_enabled=heritability,
            step_count=raw["step_count"],
            founder_pairs=raw["founder_pairs"],
            snapshot_interval=raw["snapshot_interval"],
            world=WorldConfig.from_dict(raw["world"]),
            resources=ResourceFieldConfig.from_dict(raw["resources"]),
            reproduction=ReproductionConfig(
                mode=mode,
                minimum_age_seconds=float(reproduction["minimum_age_seconds"]),
                cooldown_seconds=float(reproduction["cooldown_seconds"]),
                interaction_radius=float(reproduction["interaction_radius"]),
                maximum_compatibility_distance=float(
                    reproduction["maximum_compatibility_distance"]
                ),
                maximum_population=int(reproduction["maximum_population"]),
                mutation_enabled=bool(reproduction["mutation_enabled"]),
                heritability_enabled=bool(reproduction["heritability_enabled"]),
            ),
            low_metabolism_genome=Genome.from_json(json.dumps(raw["low_metabolism_genome"])),
            high_metabolism_genome=Genome.from_json(json.dumps(raw["high_metabolism_genome"])),
            experiment_type=raw["experiment_type"],
            schema_version=raw["schema_version"],
        )


@dataclass(frozen=True, slots=True)
class EvolutionRunReport:
    seed: int
    heritability_enabled: bool
    births: int
    deaths: int
    final_population: int
    low_final_fraction: float
    low_late_birth_fraction: float
    low_founder_descendants: int
    high_founder_descendants: int
    surviving_low_founder_descendants: int
    surviving_high_founder_descendants: int
    parent_offspring_trait_match_fraction: float
    unique_genomes: int
    genome_shannon_diversity: float
    mean_pairwise_genetic_distance: float

    def to_dict(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], asdict(self))

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True, slots=True)
class EvolutionSimulation:
    events: tuple[SimulationEvent, ...]
    snapshots: tuple[WorldSnapshot, ...]
    report: EvolutionRunReport


def _founders(config: EvolutionExperimentConfig) -> list[Founder]:
    founders: list[Founder] = []
    for index in range(config.founder_pairs):
        for trait, genome in (
            ("low", config.low_metabolism_genome),
            ("high", config.high_metabolism_genome),
        ):
            founders.append(
                Founder(
                    genome,
                    InitialOrganismConfig(
                        x=config.resources.food_x,
                        y=config.resources.food_y,
                        energy=70.0,
                        hydration=90.0,
                    ),
                    f"{trait}-{index}",
                )
            )
    NamedRandomStreams(config.seed).stream("founder-order").shuffle(founders)
    return founders


def _trait(config: EvolutionExperimentConfig, genome: Genome) -> str:
    midpoint = (
        config.low_metabolism_genome.basal_energy_rate
        + config.high_metabolism_genome.basal_energy_rate
    ) / 2.0
    return "low" if genome.basal_energy_rate < midpoint else "high"


def _shannon(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum((count / total) * math.log(count / total) for count in counts.values())


def _report(config: EvolutionExperimentConfig, world: PopulationWorld) -> EvolutionRunReport:
    records = world.lineages.records()
    active = set(world.population.active_entity_ids())
    founder_ids = [record.entity_id for record in records if not record.parent_ids]
    low_founders = [
        entity_id for entity_id in founder_ids if _trait(config, world.genome(entity_id)) == "low"
    ]
    high_founders = [
        entity_id for entity_id in founder_ids if _trait(config, world.genome(entity_id)) == "high"
    ]
    low_desc = {child for founder in low_founders for child in world.lineages.descendants(founder)}
    high_desc = {
        child for founder in high_founders for child in world.lineages.descendants(founder)
    }
    final_low = sum(_trait(config, world.genome(entity_id)) == "low" for entity_id in active)
    late_step = config.step_count // 2
    late_births = [
        record for record in records if record.parent_ids and record.birth_step >= late_step
    ]
    late_low = sum(
        _trait(config, world.genome(record.entity_id)) == "low" for record in late_births
    )
    children = [record for record in records if record.parent_ids]
    matches = sum(
        _trait(config, world.genome(record.entity_id))
        == _trait(config, world.genome(record.parent_ids[0]))
        for record in children
    )
    genome_counts: dict[str, int] = {}
    for entity_id in active:
        genome_id = world.genome(entity_id).genome_id
        genome_counts[genome_id] = genome_counts.get(genome_id, 0) + 1
    active_genomes = [world.genome(entity_id) for entity_id in sorted(active)]
    distances = [
        genetic_distance(left, right)
        for index, left in enumerate(active_genomes)
        for right in active_genomes[index + 1 :]
    ]
    return EvolutionRunReport(
        seed=config.seed,
        heritability_enabled=config.heritability_enabled,
        births=world.birth_count,
        deaths=world.death_count,
        final_population=len(active),
        low_final_fraction=final_low / len(active) if active else 0.0,
        low_late_birth_fraction=late_low / len(late_births) if late_births else 0.0,
        low_founder_descendants=len(low_desc),
        high_founder_descendants=len(high_desc),
        surviving_low_founder_descendants=len(low_desc & active),
        surviving_high_founder_descendants=len(high_desc & active),
        parent_offspring_trait_match_fraction=matches / len(children) if children else 0.0,
        unique_genomes=len(genome_counts),
        genome_shannon_diversity=_shannon(genome_counts),
        mean_pairwise_genetic_distance=sum(distances) / len(distances) if distances else 0.0,
    )


def simulate_evolution(config: EvolutionExperimentConfig) -> EvolutionSimulation:
    world = PopulationWorld(
        seed=config.seed,
        world_config=config.world,
        resource_config=config.resources,
        reproduction_config=config.reproduction,
        founders=_founders(config),
        initial_event_sequence=1,
    )
    events: list[SimulationEvent] = [
        SimulationEvent(
            0,
            0,
            "run.started",
            {"config_id": config.config_id, "master_seed": config.seed},
        )
    ]
    snapshots = [world.snapshot()]
    for _ in range(config.step_count):
        actions = {
            entity_id: PopulationAction(WormAction(eat=True, drink=True, rest=True), reproduce=True)
            for entity_id in world.population.active_entity_ids()
        }
        transition = world.advance(actions)
        events.extend(transition.events)
        if world.step_index % config.snapshot_interval == 0:
            snapshots.append(world.snapshot())
    report = _report(config, world)
    events.append(
        SimulationEvent(
            world.step_index,
            world.next_event_sequence,
            "run.completed",
            {"final_population": report.final_population, "births": report.births},
        )
    )
    if snapshots[-1].step_index != world.step_index:
        snapshots.append(world.snapshot())
    return EvolutionSimulation(tuple(events), tuple(snapshots), report)


def _json_lines(records: tuple[SimulationEvent, ...] | tuple[WorldSnapshot, ...]) -> bytes:
    return "".join(f"{record.to_json()}\n" for record in records).encode()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_evolution_experiment(
    config: EvolutionExperimentConfig,
    *,
    artifact_directory: Path,
    project_root: Path,
) -> ReplayManifest:
    from worm_world.experiments.runner import code_revision

    simulation = simulate_evolution(config)
    event_bytes = _json_lines(simulation.events)
    snapshot_bytes = _json_lines(simulation.snapshots)
    lockfile = project_root / "uv.lock"
    manifest = ReplayManifest(
        config.config_id,
        config.to_json(),
        config.seed,
        code_revision(project_root),
        _file_hash(lockfile),
        hashlib.sha256(event_bytes).hexdigest(),
        len(simulation.events),
        len(simulation.snapshots),
        config.step_count,
    )
    artifact_directory.mkdir(parents=True, exist_ok=False)
    (artifact_directory / "config.json").write_text(config.to_json() + "\n", encoding="utf-8")
    (artifact_directory / "events.jsonl").write_bytes(event_bytes)
    (artifact_directory / "snapshots.jsonl").write_bytes(snapshot_bytes)
    (artifact_directory / "report.json").write_text(
        simulation.report.to_json() + "\n", encoding="utf-8"
    )
    (artifact_directory / "manifest.json").write_text(manifest.to_json() + "\n", encoding="utf-8")
    return manifest


def verify_evolution_replay(artifact_directory: Path) -> ReplayManifest:
    config = EvolutionExperimentConfig.from_json(
        (artifact_directory / "config.json").read_text(encoding="utf-8").rstrip()
    )
    manifest = ReplayManifest.from_json(
        (artifact_directory / "manifest.json").read_text(encoding="utf-8")
    )
    simulation = simulate_evolution(config)
    event_bytes = _json_lines(simulation.events)
    snapshot_bytes = _json_lines(simulation.snapshots)
    if config.to_json() != manifest.config_json:
        raise ValueError("config does not match manifest")
    if event_bytes != (artifact_directory / "events.jsonl").read_bytes():
        raise ValueError("evolution event replay diverged")
    if snapshot_bytes != (artifact_directory / "snapshots.jsonl").read_bytes():
        raise ValueError("evolution snapshot replay diverged")
    if simulation.report.to_json() + "\n" != (artifact_directory / "report.json").read_text(
        encoding="utf-8"
    ):
        raise ValueError("evolution report replay diverged")
    if hashlib.sha256(event_bytes).hexdigest() != manifest.event_hash:
        raise ValueError("evolution event hash diverged")
    return manifest


def run_phase2_acceptance_suite(
    seeds: tuple[int, ...], *, artifact_directory: Path, project_root: Path
) -> dict[str, JsonValue]:
    if len(seeds) < 3 or len(set(seeds)) != len(seeds):
        raise ValueError("acceptance suite requires at least three distinct seeds")
    artifact_directory.mkdir(parents=True, exist_ok=False)
    heritable: list[EvolutionRunReport] = []
    controls: list[EvolutionRunReport] = []
    for seed in seeds:
        for enabled, collection, label in (
            (True, heritable, "heritable"),
            (False, controls, "control"),
        ):
            config = EvolutionExperimentConfig(seed=seed, heritability_enabled=enabled)
            run_evolution_experiment(
                config,
                artifact_directory=artifact_directory / f"seed_{seed}_{label}",
                project_root=project_root,
            )
            collection.append(simulate_evolution(config).report)
    heritable_advantages = [
        report.surviving_low_founder_descendants - report.surviving_high_founder_descendants
        for report in heritable
    ]
    control_late_deviation = [abs(report.low_late_birth_fraction - 0.5) for report in controls]
    passed = (
        all(value > 0 for value in heritable_advantages)
        and median(report.low_late_birth_fraction for report in heritable) > 0.75
        and median(control_late_deviation) < 0.2
        and median(report.parent_offspring_trait_match_fraction for report in heritable) == 1.0
        and median(report.parent_offspring_trait_match_fraction for report in controls) < 0.7
    )
    summary: dict[str, JsonValue] = {
        "acceptance_passed": passed,
        "criteria": {
            "all_heritable_low_lineage_survival_advantages_positive": True,
            "control_median_late_birth_deviation_below": 0.2,
            "heritable_median_late_low_birth_fraction_above": 0.75,
            "parent_offspring_match_control_median_below": 0.7,
            "parent_offspring_match_heritable_median": 1.0,
        },
        "hardware": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "seeds": list(seeds),
        "heritable_reports": [report.to_dict() for report in heritable],
        "control_reports": [report.to_dict() for report in controls],
    }
    (artifact_directory / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary
