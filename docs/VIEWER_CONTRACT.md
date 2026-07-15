# 2/2.5D Viewer Contract

The simulator is ready for a separate read-only 2/2.5D replay viewer. The viewer must consume
recorded artifacts and must never call `PopulationWorld.advance` or otherwise drive authoritative
state.

## Public interface

```python
from pathlib import Path

from worm_world.viewer import PopulationReplay

replay = PopulationReplay.from_directory(Path("artifacts/phase2/run"))
frame = replay.frame(0)
wire_value = frame.to_dict()
```

`PopulationReplay` strictly reads `config.json`, `manifest.json`, and `snapshots.jsonl`. It checks
configuration identity, snapshot count, final step, and increasing snapshot order. Loading and
projecting frames never imports, creates, or advances an authoritative world.

`ViewerFrame` schema version 1 exposes:

- world width and height in meters;
- fixed step index and elapsed simulation seconds;
- food and water positions, remaining amounts, and interaction radii;
- stable organism entity, genome, and lineage identities;
- active/tombstoned state and energy, hydration, and injury values;
- heading and the complete ordered XY segment chain for each worm.

Frames and their nested records are frozen dataclasses containing tuples. `to_dict()` creates a
detached JSON-compatible value suitable for a browser bridge or file export.

## Canvas viewer

The packaged exporter projects every recorded frame through `PopulationReplay` and writes a
self-contained static Canvas viewer:

```powershell
uv run python -m worm_world.viewer --replay artifacts/phase2/example `
  --output artifacts/viewer/example
```

The output embeds detached frame values in `replay-data.js`, so `index.html` can be opened directly
without a web server. It provides play/pause, speed and frame controls, active-population counts,
resource rendering, organism inspection, and optional tombstones. Canvas interpolation and
interaction remain presentation-only.

## Rendering conventions

- XY is the authoritative movement plane. The origin is `(0, 0)` and bounds are inclusive through
  `(width_meters, height_meters)`.
- Segment index zero is the head. Remaining segments extend down the body in order.
- A 2D viewer may draw the XY chain directly. A 2.5D viewer may map scalar terrain or presentation
  height onto Z later, but must not feed that result back into replay state.
- Interpolate only for presentation between recorded frames. Selection, inspection, event timing,
  and displayed measurements must remain anchored to recorded fixed steps.
- Tombstones may be hidden by default but should remain inspectable for lineage playback.

## Current limitations

The version-1 projection loads persistent-population evolution artifacts. It does not yet define
terrain height, camera controls, live simulation streaming, seasonal fields, or material entities.
Those additions require new backward-compatible viewer schema versions as the headless world gains
the corresponding authoritative state.
