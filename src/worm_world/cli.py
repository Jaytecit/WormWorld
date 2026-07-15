"""Command-line entry points for reproducible headless experiments."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from worm_world.experiments import ExperimentConfig, run_noop_experiment


def main(argv: Sequence[str] | None = None) -> int:
    """Create a Phase 0 no-op replay artifact from explicit inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--steps", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args(argv)

    artifacts = run_noop_experiment(
        ExperimentConfig(seed=arguments.seed),
        step_count=arguments.steps,
        artifact_directory=arguments.output.resolve(),
        project_root=arguments.project_root.resolve(),
    )
    print(artifacts.manifest_path)
    print(f"event_hash={artifacts.manifest.event_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
