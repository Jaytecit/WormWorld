"""Static Canvas viewer export for recorded population replays."""

from __future__ import annotations

import json
import shutil
from importlib.resources import files
from pathlib import Path

from worm_world.viewer.replay import PopulationReplay


def export_population_viewer(replay: PopulationReplay, output_directory: Path) -> Path:
    """Write a self-contained, read-only browser viewer and return its entry page."""
    if output_directory.exists():
        raise FileExistsError(f"viewer output already exists: {output_directory}")

    output_directory.mkdir(parents=True)
    static = files("worm_world.viewer").joinpath("static")
    for name in ("index.html", "styles.css", "app.js"):
        source = static.joinpath(name)
        with source.open("rb") as source_file, (output_directory / name).open("wb") as target_file:
            shutil.copyfileobj(source_file, target_file)

    payload = {
        "config_id": replay.manifest.config_id,
        "event_hash": replay.manifest.event_hash,
        "frames": [replay.frame(index).to_dict() for index in range(len(replay))],
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    (output_directory / "replay-data.js").write_text(
        f"window.WORM_WORLD_REPLAY={encoded};\n", encoding="utf-8", newline="\n"
    )
    return output_directory / "index.html"
