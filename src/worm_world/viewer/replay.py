"""Read-only projection of recorded population snapshots for 2/2.5D viewers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from worm_world.experiments.evolution import (
    EVOLUTION_EXPERIMENT_TYPE,
    EvolutionExperimentConfig,
)
from worm_world.experiments.learning import LEARNING_EXPERIMENT_TYPE, LearningExperimentConfig
from worm_world.schemas import JsonValue, ReplayManifest, WorldSnapshot

VIEWER_FRAME_SCHEMA_VERSION = 1
ReplayConfig = EvolutionExperimentConfig | LearningExperimentConfig


def _number(value: JsonValue, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be numeric")
    return float(value)


def _integer(value: JsonValue, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _string(value: JsonValue, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class ViewerPoint:
    x: float
    y: float

    def to_dict(self) -> dict[str, JsonValue]:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True, slots=True)
class ViewerOrganism:
    entity_id: int
    active: bool
    genome_id: str
    lineage_id: str
    heading_radians: float
    energy: float
    hydration: float
    injury: float
    segments: tuple[ViewerPoint, ...]

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "active": self.active,
            "energy": self.energy,
            "entity_id": self.entity_id,
            "genome_id": self.genome_id,
            "heading_radians": self.heading_radians,
            "hydration": self.hydration,
            "injury": self.injury,
            "lineage_id": self.lineage_id,
            "segments": [point.to_dict() for point in self.segments],
        }


@dataclass(frozen=True, slots=True)
class ViewerResource:
    kind: str
    position: ViewerPoint
    amount: float
    interaction_radius: float

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "amount": self.amount,
            "interaction_radius": self.interaction_radius,
            "kind": self.kind,
            "position": self.position.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ViewerFrame:
    """Renderer-neutral frame; consumers cannot mutate simulator state through it."""

    step_index: int
    elapsed_seconds: float
    width_meters: float
    height_meters: float
    organisms: tuple[ViewerOrganism, ...]
    resources: tuple[ViewerResource, ...]
    schema_version: int = VIEWER_FRAME_SCHEMA_VERSION

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "elapsed_seconds": self.elapsed_seconds,
            "height_meters": self.height_meters,
            "organisms": [organism.to_dict() for organism in self.organisms],
            "resources": [resource.to_dict() for resource in self.resources],
            "schema_version": self.schema_version,
            "step_index": self.step_index,
            "width_meters": self.width_meters,
        }


class PopulationReplay:
    """Strict loader for a recorded Phase 2+ population replay."""

    def __init__(
        self,
        config: ReplayConfig,
        manifest: ReplayManifest,
        snapshots: tuple[WorldSnapshot, ...],
    ) -> None:
        if config.config_id != manifest.config_id or config.to_json() != manifest.config_json:
            raise ValueError("replay configuration does not match its manifest")
        if len(snapshots) != manifest.snapshot_count:
            raise ValueError("snapshot count does not match replay manifest")
        if not snapshots or snapshots[-1].step_index != manifest.final_step:
            raise ValueError("replay does not contain its declared final frame")
        if any(
            left.step_index >= right.step_index
            for left, right in zip(snapshots, snapshots[1:], strict=False)
        ):
            raise ValueError("snapshot steps must be strictly increasing")
        self.config = config
        self.manifest = manifest
        self._snapshots = snapshots

    @classmethod
    def from_directory(cls, artifact_directory: Path) -> PopulationReplay:
        """Read artifacts only; never re-run or advance the authoritative simulator."""
        serialized_config = (
            (artifact_directory / "config.json").read_text(encoding="utf-8").rstrip("\n")
        )
        decoded: object = json.loads(serialized_config)
        if not isinstance(decoded, dict):
            raise ValueError("viewer replay configuration must be an object")
        experiment_type = cast(dict[str, JsonValue], decoded).get("experiment_type")
        if experiment_type == EVOLUTION_EXPERIMENT_TYPE:
            config: ReplayConfig = EvolutionExperimentConfig.from_json(serialized_config)
        elif experiment_type == LEARNING_EXPERIMENT_TYPE:
            config = LearningExperimentConfig.from_json(serialized_config)
        else:
            raise ValueError("viewer replay has an unsupported experiment type")
        manifest = ReplayManifest.from_json(
            (artifact_directory / "manifest.json").read_text(encoding="utf-8").rstrip("\n")
        )
        lines = (artifact_directory / "snapshots.jsonl").read_text(encoding="utf-8").splitlines()
        snapshots = tuple(WorldSnapshot.from_json(line) for line in lines)
        return cls(config, manifest, snapshots)

    def __len__(self) -> int:
        return len(self._snapshots)

    def frame(self, index: int) -> ViewerFrame:
        snapshot = self._snapshots[index]
        organisms_value = snapshot.state.get("organisms")
        resources_value = snapshot.state.get("resources")
        if not isinstance(organisms_value, list) or not isinstance(resources_value, dict):
            raise ValueError("snapshot lacks population viewer state")
        organisms: list[ViewerOrganism] = []
        for value in organisms_value:
            if not isinstance(value, dict):
                raise ValueError("organism viewer state must be an object")
            record = cast(dict[str, JsonValue], value)
            active = record.get("active")
            segments_value = record.get("segments")
            if not isinstance(active, bool) or not isinstance(segments_value, list):
                raise ValueError("organism active flag and segments are required")
            segments: list[ViewerPoint] = []
            for point_value in segments_value:
                if not isinstance(point_value, dict):
                    raise ValueError("segment position must be an object")
                point = cast(dict[str, JsonValue], point_value)
                segments.append(
                    ViewerPoint(
                        _number(point.get("x"), "segment x"), _number(point.get("y"), "segment y")
                    )
                )
            organisms.append(
                ViewerOrganism(
                    entity_id=_integer(record.get("entity_id"), "entity_id"),
                    active=active,
                    genome_id=_string(record.get("genome_id"), "genome_id"),
                    lineage_id=_string(record.get("lineage_id"), "lineage_id"),
                    heading_radians=_number(record.get("heading_radians"), "heading_radians"),
                    energy=_number(record.get("energy"), "energy"),
                    hydration=_number(record.get("hydration"), "hydration"),
                    injury=_number(record.get("injury"), "injury"),
                    segments=tuple(segments),
                )
            )
        resource_config = self.config.resources
        resources = (
            ViewerResource(
                "food",
                ViewerPoint(resource_config.food_x, resource_config.food_y),
                _number(resources_value.get("food_energy"), "food energy"),
                resource_config.interaction_radius,
            ),
            ViewerResource(
                "water",
                ViewerPoint(resource_config.water_x, resource_config.water_y),
                _number(resources_value.get("water_amount"), "water amount"),
                resource_config.interaction_radius,
            ),
        )
        return ViewerFrame(
            snapshot.step_index,
            snapshot.elapsed_seconds,
            self.config.world.width_meters,
            self.config.world.height_meters,
            tuple(organisms),
            resources,
        )
