"""Tests for the Phase 0 fixed-timestep no-op world."""

import pytest

from worm_world.experiments import WorldConfig
from worm_world.world import NoOpWorld


def test_noop_world_derives_time_from_integer_steps() -> None:
    """Fixed-step time has no separate accumulator that can drift."""
    world = NoOpWorld(WorldConfig(timestep_seconds=0.125))
    world.advance(8)

    assert world.step_index == 8
    assert world.elapsed_seconds == 1.0
    assert world.snapshot().step_index == 8
    assert world.snapshot().state == {}


def test_noop_world_rejects_negative_advance() -> None:
    """Simulation time cannot run backwards."""
    with pytest.raises(ValueError, match="non-negative"):
        NoOpWorld(WorldConfig()).advance(-1)
