import json
from pathlib import Path

import pytest

from worm_world.experiments.evolution import EvolutionExperimentConfig, run_evolution_experiment
from worm_world.viewer import PopulationReplay, export_population_viewer
from worm_world.viewer.__main__ import main


def _population_artifact(directory: Path) -> Path:
    artifact_directory = directory / "run"
    run_evolution_experiment(
        EvolutionExperimentConfig(
            seed=7,
            heritability_enabled=True,
            step_count=2,
            founder_pairs=1,
            snapshot_interval=1,
        ),
        artifact_directory=artifact_directory,
        project_root=Path.cwd(),
    )
    return artifact_directory


def test_static_viewer_export_embeds_projected_frames_without_mutating_replay(
    tmp_path: Path,
) -> None:
    artifact_directory = _population_artifact(tmp_path)
    replay = PopulationReplay.from_directory(artifact_directory)
    expected_final_frame = replay.frame(-1).to_dict()

    entry_page = export_population_viewer(replay, tmp_path / "viewer")

    assert entry_page.name == "index.html"
    assert {path.name for path in entry_page.parent.iterdir()} == {
        "app.js",
        "index.html",
        "replay-data.js",
        "styles.css",
    }
    assignment = (entry_page.parent / "replay-data.js").read_text(encoding="utf-8")
    payload = json.loads(assignment.removeprefix("window.WORM_WORLD_REPLAY=").removesuffix(";\n"))
    assert payload["config_id"] == replay.manifest.config_id
    assert payload["event_hash"] == replay.manifest.event_hash
    assert payload["frames"][-1] == expected_final_frame
    assert replay.frame(-1).to_dict() == expected_final_frame

    with pytest.raises(FileExistsError):
        export_population_viewer(replay, entry_page.parent)


def test_viewer_module_cli_exports_entry_page(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact_directory = _population_artifact(tmp_path)
    output_directory = tmp_path / "viewer"

    assert main(["--replay", str(artifact_directory), "--output", str(output_directory)]) == 0

    assert Path(capsys.readouterr().out.strip()) == output_directory.resolve() / "index.html"
