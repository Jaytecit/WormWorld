"""Package bootstrap checks."""

import worm_world


def test_package_imports() -> None:
    """The initial package is importable before simulation modules are added."""
    assert worm_world.__all__ == [
        "ExperimentConfig",
        "NamedRandomStreams",
        "ReplayManifest",
        "SimulationEvent",
        "WorldConfig",
        "WorldSnapshot",
    ]
