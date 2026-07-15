"""Minimal fixed-timestep world used to establish replay infrastructure."""

from __future__ import annotations

from worm_world.experiments.config import WorldConfig
from worm_world.schemas import WorldSnapshot


class NoOpWorld:
    """A headless world whose only mutable state is its integer step index."""

    def __init__(self, config: WorldConfig) -> None:
        self._config = config
        self._step_index = 0

    @property
    def step_index(self) -> int:
        """Return the number of fixed steps completed."""
        return self._step_index

    @property
    def elapsed_seconds(self) -> float:
        """Derive simulation time from integer steps to avoid accumulated drift."""
        return self._step_index * self._config.timestep_seconds

    def advance(self, steps: int = 1) -> None:
        """Advance by a non-negative number of fixed no-op steps."""
        if isinstance(steps, bool) or steps < 0:
            raise ValueError("steps must be a non-negative integer")
        self._step_index += steps

    def snapshot(self) -> WorldSnapshot:
        """Capture the complete no-op world state for replay."""
        return WorldSnapshot(
            step_index=self._step_index,
            elapsed_seconds=self.elapsed_seconds,
            state={},
        )
