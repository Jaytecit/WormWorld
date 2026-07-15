"""Canonical complete inputs for a Phase 1 single-organism sandbox run."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Self, cast

from worm_world.experiments.config import MAX_SEED, WorldConfig
from worm_world.organisms import BodyConfig, PhysiologyConfig, WormAction
from worm_world.world.sandbox import InitialOrganismConfig, ResourceFieldConfig

SANDBOX_CONFIG_SCHEMA_VERSION = 1
SANDBOX_EXPERIMENT_TYPE = "single_organism_sandbox"


@dataclass(frozen=True, slots=True)
class SandboxExperimentConfig:
    """All inputs required to replay one deterministic action sequence."""

    seed: int
    actions: tuple[WormAction, ...]
    world: WorldConfig = field(
        default_factory=lambda: WorldConfig(width_meters=10.0, height_meters=10.0)
    )
    body: BodyConfig = field(default_factory=BodyConfig)
    physiology: PhysiologyConfig = field(default_factory=PhysiologyConfig)
    resources: ResourceFieldConfig = field(default_factory=ResourceFieldConfig)
    initial_organism: InitialOrganismConfig = field(default_factory=InitialOrganismConfig)
    experiment_type: str = SANDBOX_EXPERIMENT_TYPE
    schema_version: int = SANDBOX_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not 0 <= self.seed <= MAX_SEED:
            raise ValueError(f"seed must be an integer from 0 to {MAX_SEED}")
        if self.experiment_type != SANDBOX_EXPERIMENT_TYPE:
            raise ValueError(f"experiment_type must be {SANDBOX_EXPERIMENT_TYPE!r}")
        if self.schema_version != SANDBOX_CONFIG_SCHEMA_VERSION:
            raise ValueError("unsupported sandbox configuration schema version")

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def config_id(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, serialized: str) -> Self:
        """Strictly reconstruct a stored sandbox configuration."""
        decoded: object = json.loads(serialized)
        if not isinstance(decoded, dict):
            raise ValueError("sandbox configuration must be a JSON object")
        raw = cast(dict[str, Any], decoded)
        expected = {
            "actions",
            "body",
            "experiment_type",
            "initial_organism",
            "physiology",
            "resources",
            "schema_version",
            "seed",
            "world",
        }
        if set(raw) != expected:
            raise ValueError("sandbox configuration has missing or unknown fields")
        actions = raw["actions"]
        if not isinstance(actions, list):
            raise ValueError("actions must be a JSON array")
        parsed_actions: list[WormAction] = []
        for value in cast(list[object], actions):
            if not isinstance(value, dict):
                raise ValueError("each action must be a JSON object")
            parsed_actions.append(WormAction.from_dict(cast(dict[str, Any], value)))
        return cls(
            seed=raw["seed"],
            actions=tuple(parsed_actions),
            world=WorldConfig.from_dict(raw["world"]),
            body=BodyConfig.from_dict(raw["body"]),
            physiology=PhysiologyConfig.from_dict(raw["physiology"]),
            resources=ResourceFieldConfig.from_dict(raw["resources"]),
            initial_organism=InitialOrganismConfig.from_dict(raw["initial_organism"]),
            experiment_type=raw["experiment_type"],
            schema_version=raw["schema_version"],
        )
