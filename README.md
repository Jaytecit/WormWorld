# The Worm World

The Worm World is a deterministic, headless artificial-life research simulator. Phase 0's
specification and reproducible project bootstrap are complete. The current runner
intentionally simulates no organisms yet; it verifies fixed-step timing, artifact capture,
and replay identity before Phase 1 adds survival behaviour.

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

After this workspace is initialized as a Git repository, enable the local hooks with:

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

## Create a deterministic no-op replay

The output directory must not already exist:

```powershell
uv run python -m worm_world.cli --seed 42 --steps 1000 --output artifacts/phase0/example
```

The directory contains canonical `config.json`, `events.jsonl`, `snapshots.jsonl`, and
`manifest.json`. The manifest binds the configuration ID, seed, code revision state,
`uv.lock` digest, schema versions, and deterministic event hash.

## Run the fixed-step benchmark

```powershell
uv run python -m worm_world.benchmark --steps 100000
```

The JSON result reports elapsed time and fixed steps per second. It is a local regression
measurement, not a cross-machine performance guarantee.
