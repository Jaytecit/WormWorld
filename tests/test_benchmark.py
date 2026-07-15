"""Smoke test for the executable fixed-step benchmark."""

from worm_world.benchmark import benchmark_noop


def test_noop_benchmark_measures_each_requested_step() -> None:
    """The benchmark exercises repeated ticks and returns coherent measurements."""
    result = benchmark_noop(1_000)

    assert result.steps == 1_000
    assert result.elapsed_seconds > 0.0
    assert result.steps_per_second > 0.0
