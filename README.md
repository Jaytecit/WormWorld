# The Worm World

The Worm World is a deterministic, headless artificial-life research simulator. Phase 2 adds a
persistent population, immutable genomes, mutation/recombination, compatibility, sexual and
asexual reproduction, lineage storage, fair spatial resource competition, diversity reports,
and byte-verifiable multi-seed evolution experiments. It contains no task rewards, learning,
hard-coded fitness score, or species rules. Phase 3 work adds a lifetime-only recurrent controller,
heritable brain priors, local homeostasis-modulated plasticity, and replayable learning diagnostics.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Setup and checks

```powershell
uv sync
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

Enable the local hooks with:

```powershell
uv run pre-commit install
```

Run all quality checks before completing a ticket:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

## Create a deterministic sandbox replay

The output directory must not already exist:

```powershell
uv run python -m worm_world.cli --mode sandbox --seed 42 --steps 1000 `
  --forward 0.25 --turn 0.05 --output artifacts/phase1/example
```

The repeated action is part of canonical `config.json`; use `--eat`, `--drink`, or `--rest` to
set those action channels. The output also contains `events.jsonl`, `snapshots.jsonl`, and
`manifest.json`. The manifest binds the full action sequence, initial condition, world and
organism parameters, seed, code revision, `uv.lock` digest, schema versions, and event hash.

The Phase 0 runner remains available with `--mode noop`.

## Create a deterministic evolution replay

```powershell
uv run python -m worm_world.cli --mode evolution --seed 11 --steps 500 `
  --output artifacts/phase2/example
```

The fixed action protocol exposes the same raw resting, eating, drinking, and reproduction
channels to every organism. Selection remains actual survival and descendants. Add
`--disable-heritability` for the matched randomized-offspring control. Evolution runs add a
canonical `report.json` with descendant and genotype-diversity measures.

## Run the fixed-step benchmark

```powershell
uv run python -m worm_world.benchmark --mode sandbox --steps 100000
uv run python -m worm_world.benchmark --mode population --steps 1000
```

The JSON result reports elapsed time and fixed steps per second. It is a local regression
measurement, not a cross-machine performance guarantee.

## Create a deterministic learning diagnostic replay

```powershell
uv run python -m worm_world.cli --mode learning --seed 11 --steps 64 `
  --output artifacts/phase3/diagnostic
```

The generated fixture stores its procedurally varied resource and founder positions in canonical
`config.json`. Controller outputs, raw internal-state fractions, changes, neuromodulators, local
update magnitudes, and the plasticity flag are recorded in the hashed event stream. Add
`--disable-plasticity` for the matched plasticity-off condition; neither condition uses a task
reward or trainer.

## View a recorded population

Export any population artifact to a self-contained, read-only Canvas viewer:

```powershell
uv run python -m worm_world.viewer --replay artifacts/phase2/example `
  --output artifacts/viewer/example
```

Open the emitted `index.html` directly in a browser. Playback, frame scrubbing, organism
inspection, physiology readouts, resource fields, and optional tombstones all operate on embedded
`PopulationReplay` frames; the viewer cannot construct or advance the simulator.
