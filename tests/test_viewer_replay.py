from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from worm_world.experiments.evolution import EvolutionExperimentConfig, run_evolution_experiment
from worm_world.viewer import PopulationReplay


def test_population_replay_projects_immutable_renderer_neutral_frames(tmp_path: Path) -> None:
    artifact_directory = tmp_path / "run"
    config = EvolutionExperimentConfig(
        seed=9,
        heritability_enabled=True,
        step_count=2,
        founder_pairs=1,
        snapshot_interval=1,
    )
    run_evolution_experiment(config, artifact_directory=artifact_directory, project_root=Path.cwd())
    replay = PopulationReplay.from_directory(artifact_directory)
    first = replay.frame(0)
    final = replay.frame(-1)
    assert (first.width_meters, first.height_meters) == (10.0, 10.0)
    assert [resource.kind for resource in first.resources] == ["food", "water"]
    assert first.organisms[0].segments
    assert final.step_index == replay.manifest.final_step == 2
    with pytest.raises(FrozenInstanceError):
        first.width_meters = 20.0  # type: ignore[misc]
