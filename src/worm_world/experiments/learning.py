"""Phase 3 headless learning experiment and diagnostic artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Self, cast

from worm_world.experiments.config import MAX_SEED, WorldConfig
from worm_world.genetics import LATEST_GENOME_SCHEMA_VERSION, Genome
from worm_world.learning import ControllerConfig, EligibilityRule, PopulationController
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

LEARNING_CONFIG_SCHEMA_VERSION = 1
LATEST_LEARNING_CONFIG_SCHEMA_VERSION = 2
LEARNING_EXPERIMENT_TYPE = "lifetime_learning_diagnostics"
TRAINING_FIXTURE_VERSION = 1


def _default_genome() -> Genome:
    return Genome.version2(
        Genome(
            basal_energy_rate=0.3,
            basal_hydration_rate=0.2,
            movement_energy_rate=0.3,
            mutation_scale=0.0,
        ),
        hidden_size=4,
        plasticity_rate=0.02,
        eligibility_trace_decay=0.9,
    )


@dataclass(frozen=True, slots=True)
class LearningExperimentConfig:
    """Complete matched input for one controller-driven diagnostic run."""

    seed: int
    plasticity_enabled: bool
    founder_positions: tuple[tuple[float, float], ...]
    step_count: int = 64
    snapshot_interval: int = 8
    world: WorldConfig = field(
        default_factory=lambda: WorldConfig(
            timestep_seconds=0.5, width_meters=10.0, height_meters=10.0
        )
    )
    resources: ResourceFieldConfig = field(
        default_factory=lambda: ResourceFieldConfig(
            food_x=5.0,
            food_y=5.0,
            food_energy=200.0,
            water_x=5.0,
            water_y=5.0,
            water_amount=200.0,
            eat_rate=0.5,
            drink_rate=0.5,
        )
    )
    reproduction: ReproductionConfig = field(
        default_factory=lambda: ReproductionConfig(
            mode="asexual",
            minimum_age_seconds=8.0,
            cooldown_seconds=8.0,
            maximum_population=16,
            mutation_enabled=False,
            heritability_enabled=True,
        )
    )
    founder_genome: Genome = field(default_factory=_default_genome)
    fixture_version: int = TRAINING_FIXTURE_VERSION
    experiment_type: str = LEARNING_EXPERIMENT_TYPE
    eligibility_rule: EligibilityRule = "legacy_tanh"
    schema_version: int = LEARNING_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not 0 <= self.seed <= MAX_SEED:
            raise ValueError(f"seed must be an integer from 0 to {MAX_SEED}")
        if isinstance(self.step_count, bool) or self.step_count < 1:
            raise ValueError("step_count must be positive")
        if isinstance(self.snapshot_interval, bool) or self.snapshot_interval < 1:
            raise ValueError("snapshot_interval must be positive")
        if not self.founder_positions:
            raise ValueError("at least one founder position is required")
        if len(self.founder_positions) > self.reproduction.maximum_population:
            raise ValueError("founders exceed maximum population")
        for x, y in self.founder_positions:
            if not 0.0 <= x <= self.world.width_meters or not 0.0 <= y <= self.world.height_meters:
                raise ValueError("founder positions must be inside the world")
        if self.founder_genome.schema_version != LATEST_GENOME_SCHEMA_VERSION:
            raise ValueError("learning experiments require version-2 founder genomes")
        if self.founder_genome.brain_hidden_size is None:
            raise ValueError("founder genome must define a brain hidden size")
        if not self.reproduction.heritability_enabled:
            raise ValueError("learning diagnostic requires inherited priors")
        if self.fixture_version != TRAINING_FIXTURE_VERSION:
            raise ValueError("unsupported training fixture version")
        if self.experiment_type != LEARNING_EXPERIMENT_TYPE:
            raise ValueError("unsupported learning experiment type")
        if self.schema_version not in (
            LEARNING_CONFIG_SCHEMA_VERSION,
            LATEST_LEARNING_CONFIG_SCHEMA_VERSION,
        ):
            raise ValueError("unsupported learning config schema version")
        if self.schema_version == LEARNING_CONFIG_SCHEMA_VERSION:
            if self.eligibility_rule != "legacy_tanh":
                raise ValueError("version-1 learning configs require the legacy eligibility rule")
        elif self.eligibility_rule not in ("legacy_tanh", "action_activation"):
            raise ValueError("unknown eligibility rule")

    @classmethod
    def training_fixture(
        cls,
        seed: int,
        *,
        plasticity_enabled: bool,
        founder_count: int = 4,
        step_count: int = 64,
        founder_genome: Genome | None = None,
        eligibility_rule: EligibilityRule = "legacy_tanh",
    ) -> LearningExperimentConfig:
        """Create a small varied world whose realized inputs are stored in the config."""
        if isinstance(founder_count, bool) or founder_count < 1:
            raise ValueError("founder_count must be positive")
        streams = NamedRandomStreams(seed)
        resource_rng = streams.stream("phase3-training-resource")
        food_x = resource_rng.uniform(2.0, 8.0)
        food_y = resource_rng.uniform(2.0, 8.0)
        water_x = resource_rng.uniform(2.0, 8.0)
        water_y = resource_rng.uniform(2.0, 8.0)
        founder_rng = streams.stream("phase3-training-founders")
        positions = tuple(
            (founder_rng.uniform(1.0, 9.0), founder_rng.uniform(1.0, 9.0))
            for _ in range(founder_count)
        )
        resources = ResourceFieldConfig(
            food_x=food_x,
            food_y=food_y,
            food_energy=200.0,
            water_x=water_x,
            water_y=water_y,
            water_amount=200.0,
            eat_rate=0.5,
            drink_rate=0.5,
        )
        return cls(
            seed,
            plasticity_enabled,
            positions,
            step_count=step_count,
            resources=resources,
            founder_genome=_default_genome() if founder_genome is None else founder_genome,
            eligibility_rule=eligibility_rule,
            schema_version=(
                LATEST_LEARNING_CONFIG_SCHEMA_VERSION
                if eligibility_rule != "legacy_tanh"
                else LEARNING_CONFIG_SCHEMA_VERSION
            ),
        )

    def to_json(self) -> str:
        values = asdict(self)
        values["founder_genome"] = self.founder_genome.to_dict()
        if self.schema_version == LEARNING_CONFIG_SCHEMA_VERSION:
            values.pop("eligibility_rule")
        return json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def config_id(self) -> str:
        return hashlib.sha256(self.to_json().encode()).hexdigest()

    @classmethod
    def from_json(cls, serialized: str) -> Self:
        decoded: object = json.loads(serialized)
        if not isinstance(decoded, dict):
            raise ValueError("learning configuration must be an object")
        raw = cast(dict[str, Any], decoded)
        if "schema_version" not in raw:
            raise ValueError("learning configuration has missing or unknown fields")
        version = raw.get("schema_version")
        expected = set(asdict(cls.training_fixture(0, plasticity_enabled=True)))
        if version == LEARNING_CONFIG_SCHEMA_VERSION:
            expected.remove("eligibility_rule")
        elif version != LATEST_LEARNING_CONFIG_SCHEMA_VERSION:
            raise ValueError("unsupported learning config schema version")
        if set(raw) != expected:
            raise ValueError("learning configuration has missing or unknown fields")
        reproduction = dict(raw["reproduction"])
        mode = reproduction.pop("mode")
        if mode not in ("asexual", "sexual"):
            raise ValueError("unknown reproduction mode")
        positions = tuple(
            (float(position[0]), float(position[1])) for position in raw["founder_positions"]
        )
        return cls(
            seed=raw["seed"],
            plasticity_enabled=raw["plasticity_enabled"],
            founder_positions=positions,
            step_count=raw["step_count"],
            snapshot_interval=raw["snapshot_interval"],
            world=WorldConfig.from_dict(raw["world"]),
            resources=ResourceFieldConfig.from_dict(raw["resources"]),
            reproduction=ReproductionConfig(mode=mode, **reproduction),
            founder_genome=Genome.from_json(json.dumps(raw["founder_genome"])),
            fixture_version=raw["fixture_version"],
            experiment_type=raw["experiment_type"],
            eligibility_rule=raw.get("eligibility_rule", "legacy_tanh"),
            schema_version=raw["schema_version"],
        )


@dataclass(frozen=True, slots=True)
class LearningRunReport:
    seed: int
    plasticity_enabled: bool
    births: int
    deaths: int
    final_population: int
    diagnostic_steps: int
    total_update_l1: float
    maximum_learned_weight_l1: float

    def to_dict(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], asdict(self))

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @classmethod
    def from_json(cls, serialized: str) -> LearningRunReport:
        decoded: object = json.loads(serialized)
        if not isinstance(decoded, dict):
            raise ValueError("learning report must be an object")
        values = cast(dict[str, Any], decoded)
        if set(values) != set(asdict(cls(0, False, 0, 0, 0, 0, 0.0, 0.0))):
            raise ValueError("learning report has missing or unknown fields")
        return cls(**values)


@dataclass(frozen=True, slots=True)
class LearningSimulation:
    events: tuple[SimulationEvent, ...]
    snapshots: tuple[WorldSnapshot, ...]
    report: LearningRunReport


def _founders(config: LearningExperimentConfig) -> list[Founder]:
    return [
        Founder(
            config.founder_genome,
            InitialOrganismConfig(x=x, y=y, energy=70.0, hydration=70.0),
            f"founder-{index}",
        )
        for index, (x, y) in enumerate(config.founder_positions)
    ]


def _resequenced(events: list[SimulationEvent]) -> tuple[SimulationEvent, ...]:
    return tuple(
        SimulationEvent(event.step_index, sequence, event.event_type, event.data)
        for sequence, event in enumerate(events)
    )


def simulate_learning(config: LearningExperimentConfig) -> LearningSimulation:
    """Run the controller against the world without a trainer or task reward."""
    hidden_size = config.founder_genome.brain_hidden_size
    assert hidden_size is not None
    world = PopulationWorld(
        seed=config.seed,
        world_config=config.world,
        resource_config=config.resources,
        reproduction_config=config.reproduction,
        founders=_founders(config),
    )
    controller = PopulationController(
        ControllerConfig(
            hidden_size=hidden_size,
            plasticity_enabled=config.plasticity_enabled,
            eligibility_rule=config.eligibility_rule,
        )
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
    diagnostic_steps = 0
    total_update_l1 = 0.0
    maximum_learned_weight_l1 = 0.0
    for _ in range(config.step_count):
        active = world.population.active_entity_ids()
        sensors = {entity_id: world.sense(entity_id) for entity_id in reversed(active)}
        genomes = {entity_id: world.genome(entity_id) for entity_id in reversed(active)}
        actions = controller.decide(sensors, genomes)
        step = world.step_index + 1
        for entity_id in sorted(active):
            diagnostic = controller.diagnostic(entity_id)
            diagnostic_steps += 1
            total_update_l1 += diagnostic.update_l1
            maximum_learned_weight_l1 = max(maximum_learned_weight_l1, diagnostic.learned_weight_l1)
            action = actions[entity_id]
            events.append(
                SimulationEvent(
                    step,
                    0,
                    "controller.step",
                    cast(
                        dict[str, JsonValue],
                        {
                            "action": {
                                "motion": action.motion.to_dict(),
                                "reproduce": action.reproduce,
                            },
                            "controller_outputs": list(controller.outputs(entity_id)),
                            "entity_id": entity_id,
                            "genome_id": genomes[entity_id].genome_id,
                            "homeostatic_changes": diagnostic.to_dict(),
                            "plasticity_enabled": config.plasticity_enabled,
                            "raw_homeostasis": {
                                "energy_fraction": sensors[entity_id].energy_fraction,
                                "hydration_fraction": sensors[entity_id].hydration_fraction,
                                "injury_fraction": sensors[entity_id].injury_fraction,
                            },
                        },
                    ),
                )
            )
        transition = world.advance(
            {
                entity_id: PopulationAction(action.motion, reproduce=action.reproduce)
                for entity_id, action in actions.items()
            }
        )
        events.extend(transition.events)
        controller.synchronize(set(world.population.active_entity_ids()))
        if world.step_index % config.snapshot_interval == 0:
            snapshots.append(world.snapshot())
    report = LearningRunReport(
        config.seed,
        config.plasticity_enabled,
        world.birth_count,
        world.death_count,
        len(world.population.active_entity_ids()),
        diagnostic_steps,
        total_update_l1,
        maximum_learned_weight_l1,
    )
    events.append(
        SimulationEvent(
            world.step_index,
            0,
            "run.completed",
            {"births": report.births, "final_population": report.final_population},
        )
    )
    if snapshots[-1].step_index != world.step_index:
        snapshots.append(world.snapshot())
    return LearningSimulation(_resequenced(events), tuple(snapshots), report)


def _json_lines(records: tuple[SimulationEvent, ...] | tuple[WorldSnapshot, ...]) -> bytes:
    return "".join(f"{record.to_json()}\n" for record in records).encode()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_learning_experiment(
    config: LearningExperimentConfig,
    *,
    artifact_directory: Path,
    project_root: Path,
) -> ReplayManifest:
    from worm_world.experiments.runner import code_revision

    simulation = simulate_learning(config)
    event_bytes = _json_lines(simulation.events)
    snapshot_bytes = _json_lines(simulation.snapshots)
    manifest = ReplayManifest(
        config.config_id,
        config.to_json(),
        config.seed,
        code_revision(project_root),
        _file_hash(project_root / "uv.lock"),
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


def verify_learning_replay(artifact_directory: Path) -> ReplayManifest:
    config = LearningExperimentConfig.from_json(
        (artifact_directory / "config.json").read_text(encoding="utf-8").rstrip()
    )
    manifest = ReplayManifest.from_json(
        (artifact_directory / "manifest.json").read_text(encoding="utf-8")
    )
    simulation = simulate_learning(config)
    event_bytes = _json_lines(simulation.events)
    snapshot_bytes = _json_lines(simulation.snapshots)
    if config.to_json() != manifest.config_json:
        raise ValueError("config does not match manifest")
    if event_bytes != (artifact_directory / "events.jsonl").read_bytes():
        raise ValueError("learning event replay diverged")
    if snapshot_bytes != (artifact_directory / "snapshots.jsonl").read_bytes():
        raise ValueError("learning snapshot replay diverged")
    if simulation.report.to_json() + "\n" != (artifact_directory / "report.json").read_text(
        encoding="utf-8"
    ):
        raise ValueError("learning report replay diverged")
    if hashlib.sha256(event_bytes).hexdigest() != manifest.event_hash:
        raise ValueError("learning event hash diverged")
    if (
        len(simulation.events),
        len(simulation.snapshots),
        config.step_count,
    ) != (manifest.event_count, manifest.snapshot_count, manifest.final_step):
        raise ValueError("learning replay counts do not match manifest")
    return manifest
