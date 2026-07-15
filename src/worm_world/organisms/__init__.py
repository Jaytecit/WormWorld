"""Organism-owned body, physiology, sensor, and action interfaces."""

from worm_world.organisms.core import (
    BodyConfig,
    PhysiologyConfig,
    PhysiologyDelta,
    PhysiologyState,
    SensorReadings,
    WormAction,
    WormState,
    apply_physiology,
)
from worm_world.organisms.population import PopulationStore

__all__ = [
    "BodyConfig",
    "PhysiologyConfig",
    "PhysiologyDelta",
    "PhysiologyState",
    "PopulationStore",
    "SensorReadings",
    "WormAction",
    "WormState",
    "apply_physiology",
]
