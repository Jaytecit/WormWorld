"""Small dependency-free benchmark for the headless fixed-step core."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from worm_world.experiments import WorldConfig
from worm_world.organisms import BodyConfig, PhysiologyConfig, WormAction
from worm_world.world import (
    InitialOrganismConfig,
    NoOpWorld,
    ResourceFieldConfig,
    SandboxWorld,
)


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Measured no-op fixed-step throughput."""

    steps: int
    elapsed_seconds: float
    steps_per_second: float

    def to_json(self) -> str:
        """Return a machine-readable one-line benchmark report."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def benchmark_noop(step_count: int = 100_000) -> BenchmarkResult:
    """Measure repeated public fixed-step calls without batching them away."""
    if isinstance(step_count, bool) or step_count <= 0:
        raise ValueError("step_count must be a positive integer")
    world = NoOpWorld(WorldConfig())
    started = time.perf_counter()
    for _ in range(step_count):
        world.advance()
    elapsed = time.perf_counter() - started
    return BenchmarkResult(
        steps=world.step_index,
        elapsed_seconds=elapsed,
        steps_per_second=step_count / elapsed,
    )


def benchmark_sandbox(step_count: int = 100_000) -> BenchmarkResult:
    """Measure public single-organism movement, sensing, and metabolism steps."""
    if isinstance(step_count, bool) or step_count <= 0:
        raise ValueError("step_count must be a positive integer")
    world_config = WorldConfig(width_meters=10.0, height_meters=10.0)
    world = SandboxWorld(
        world_config,
        BodyConfig(),
        PhysiologyConfig(
            max_energy=1_000_000.0,
            max_hydration=1_000_000.0,
            basal_energy_rate=0.0,
            basal_hydration_rate=0.0,
            movement_energy_rate=0.0,
        ),
        ResourceFieldConfig(),
        InitialOrganismConfig(x=5.0, y=5.0, energy=1_000_000.0, hydration=1_000_000.0),
    )
    action = WormAction(forward=0.25, turn=0.05)
    started = time.perf_counter()
    for _ in range(step_count):
        world.advance(action)
    elapsed = time.perf_counter() - started
    return BenchmarkResult(
        steps=world.step_index,
        elapsed_seconds=elapsed,
        steps_per_second=step_count / elapsed,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the benchmark CLI and print its JSON result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=100_000)
    parser.add_argument("--mode", choices=("noop", "sandbox"), default="sandbox")
    arguments = parser.parse_args(argv)
    benchmark = benchmark_sandbox if arguments.mode == "sandbox" else benchmark_noop
    print(benchmark(arguments.steps).to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
