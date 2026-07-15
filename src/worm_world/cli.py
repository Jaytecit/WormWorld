"""Command-line entry points for reproducible headless experiments."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from worm_world.experiments import (
    EvolutionExperimentConfig,
    ExperimentConfig,
    SandboxExperimentConfig,
    run_evolution_experiment,
    run_noop_experiment,
    run_sandbox_experiment,
)
from worm_world.organisms import WormAction


def main(argv: Sequence[str] | None = None) -> int:
    """Create a deterministic no-op or single-organism replay artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("noop", "sandbox", "evolution"), default="noop")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--steps", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--forward", type=float, default=0.0)
    parser.add_argument("--turn", type=float, default=0.0)
    parser.add_argument("--eat", action="store_true")
    parser.add_argument("--drink", action="store_true")
    parser.add_argument("--rest", action="store_true")
    parser.add_argument("--disable-heritability", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.steps < 0:
        parser.error("--steps must be non-negative")

    if arguments.mode == "noop":
        artifacts = run_noop_experiment(
            ExperimentConfig(seed=arguments.seed),
            step_count=arguments.steps,
            artifact_directory=arguments.output.resolve(),
            project_root=arguments.project_root.resolve(),
        )
    elif arguments.mode == "sandbox":
        action = WormAction(
            forward=arguments.forward,
            turn=arguments.turn,
            eat=arguments.eat,
            drink=arguments.drink,
            rest=arguments.rest,
        )
        artifacts = run_sandbox_experiment(
            SandboxExperimentConfig(seed=arguments.seed, actions=(action,) * arguments.steps),
            artifact_directory=arguments.output.resolve(),
            project_root=arguments.project_root.resolve(),
        )
    else:
        manifest = run_evolution_experiment(
            EvolutionExperimentConfig(
                seed=arguments.seed,
                step_count=arguments.steps,
                heritability_enabled=not arguments.disable_heritability,
            ),
            artifact_directory=arguments.output.resolve(),
            project_root=arguments.project_root.resolve(),
        )
        print(arguments.output.resolve() / "manifest.json")
        print(f"event_hash={manifest.event_hash}")
        return 0
    print(artifacts.manifest_path)
    print(f"event_hash={artifacts.manifest.event_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
