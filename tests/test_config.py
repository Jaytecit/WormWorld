"""Tests for canonical, versioned experiment configuration."""

import pytest

from worm_world.experiments import ExperimentConfig, WorldConfig


def test_configuration_serialization_is_canonical_and_round_trips() -> None:
    """Equivalent configurations have byte-identical JSON and identifiers."""
    config = ExperimentConfig(
        seed=42,
        world=WorldConfig(width_meters=12.5, height_meters=8.0, timestep_seconds=0.1),
    )

    expected = (
        '{"schema_version":1,"seed":42,"world":{"height_meters":8.0,'
        '"timestep_seconds":0.1,"width_meters":12.5}}'
    )
    assert config.to_json() == expected
    assert ExperimentConfig.from_json(expected) == config
    assert ExperimentConfig.from_json(expected).config_id == config.config_id


@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan")])
def test_world_dimensions_and_timestep_must_be_positive_and_finite(value: float) -> None:
    """Invalid physical dimensions never enter an experiment manifest."""
    with pytest.raises(ValueError):
        WorldConfig(width_meters=value)


def test_unknown_configuration_fields_are_rejected() -> None:
    """Typos and future schema fields cannot silently change an experiment."""
    serialized = (
        '{"schema_version":1,"seed":42,"unknown":true,'
        '"world":{"height_meters":8.0,"timestep_seconds":0.1,"width_meters":12.5}}'
    )
    with pytest.raises(ValueError, match="unknown experiment configuration fields"):
        ExperimentConfig.from_json(serialized)
