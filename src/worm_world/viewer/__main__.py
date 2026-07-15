"""Export a recorded population artifact as a static Canvas replay viewer."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from worm_world.viewer import PopulationReplay, export_population_viewer


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, required=True, help="recorded population directory")
    parser.add_argument("--output", type=Path, required=True, help="new viewer output directory")
    arguments = parser.parse_args(argv)
    entry_page = export_population_viewer(
        PopulationReplay.from_directory(arguments.replay.resolve()), arguments.output.resolve()
    )
    print(entry_page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
