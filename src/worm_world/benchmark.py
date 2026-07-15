"""Small dependency-free benchmark for the headless fixed-step core."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from worm_world.experiments import WorldConfig
from worm_world.world import NoOpWorld


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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the benchmark CLI and print its JSON result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=100_000)
    arguments = parser.parse_args(argv)
    print(benchmark_noop(arguments.steps).to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
