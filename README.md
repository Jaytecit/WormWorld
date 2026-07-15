# The Worm World

The Worm World is a deterministic, headless artificial-life research simulator. Phase 1
provides a single-organism survival sandbox with a segmented worm body, energy, hydration,
injury, finite food and water, weak sensors, movement, eating, drinking, resting, death, and
byte-verifiable replay. It contains no task rewards, learning, reproduction, or species rules.

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

## Run the fixed-step benchmark

```powershell
uv run python -m worm_world.benchmark --mode sandbox --steps 100000
```

The JSON result reports elapsed time and fixed steps per second. It is a local regression
measurement, not a cross-machine performance guarantee.
