"""Authoritative headless world implementations."""

from worm_world.world.detritus import (
    DetritusConfig,
    DetritusDecay,
    DetritusPool,
    DetritusTransfer,
)
from worm_world.world.noop import NoOpWorld
from worm_world.world.plants import PlantGrowth, PlantPatch, PlantPatchConfig
from worm_world.world.population import (
    Founder,
    PopulationAction,
    PopulationTransition,
    PopulationWorld,
    ReproductionConfig,
)
from worm_world.world.sandbox import (
    EntityStepResult,
    InitialOrganismConfig,
    PopulationStepResult,
    ResourceFieldConfig,
    SandboxWorld,
    StepResult,
)

__all__ = [
    "DetritusConfig",
    "DetritusDecay",
    "DetritusPool",
    "DetritusTransfer",
    "EntityStepResult",
    "InitialOrganismConfig",
    "NoOpWorld",
    "Founder",
    "PopulationAction",
    "PopulationTransition",
    "PopulationWorld",
    "PlantGrowth",
    "PlantPatch",
    "PlantPatchConfig",
    "ReproductionConfig",
    "PopulationStepResult",
    "ResourceFieldConfig",
    "SandboxWorld",
    "StepResult",
]
