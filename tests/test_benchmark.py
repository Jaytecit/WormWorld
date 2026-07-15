"""Smoke test for the executable fixed-step benchmark."""

from worm_world.benchmark import (
    benchmark_noop,
    benchmark_plants,
    benchmark_population,
    benchmark_sandbox,
)


def test_noop_benchmark_measures_each_requested_step() -> None:
    """The benchmark exercises repeated ticks and returns coherent measurements."""
    result = benchmark_noop(1_000)

    assert result.steps == 1_000
    assert result.elapsed_seconds > 0.0
    assert result.steps_per_second > 0.0


def test_sandbox_benchmark_measures_each_requested_step() -> None:
    """The Phase 1 benchmark exercises the complete public transition."""
    result = benchmark_sandbox(1_000)

    assert result.steps == 1_000
    assert result.elapsed_seconds > 0.0
    assert result.steps_per_second > 0.0


def test_population_benchmark_measures_each_requested_step() -> None:
    """The Phase 2 benchmark exercises simultaneous population transitions."""
    result = benchmark_population(2, population_size=4)

    assert result.steps == 2
    assert result.elapsed_seconds > 0.0
    assert result.steps_per_second > 0.0


def test_plant_benchmark_measures_each_requested_step() -> None:
    result = benchmark_plants(2, population_size=4)

    assert result.steps == 2
    assert result.elapsed_seconds > 0.0
    assert result.steps_per_second > 0.0
