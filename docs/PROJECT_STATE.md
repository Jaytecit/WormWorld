# Project State and Session Handoff

## Status

- **Active phase:** Phase 1 — single-organism survival sandbox.
- **Phase status:** Phase 0 complete; no Phase 1 implementation has started.
- **Last updated:** 2026-07-15.
- **Repository state at handoff:** Phase 0 reproducibility infrastructure and a retained
  acceptance replay exist. No Git repository has been initialized. The world remains no-op:
  there are no organisms, resources, learning systems, or rendering components.

## Last completed work

- Completed **P0-T05 — Benchmark harness and Phase 0 acceptance test** and passed the Phase 0
  exit gate.
- Added an executable dependency-free fixed-step benchmark that calls the public world step
  once per measured tick.
- Added a CLI that creates no-op replay artifacts from explicit seed, step count, output path,
  and project root inputs without overwriting an existing artifact directory.
- Added an end-to-end acceptance test that verifies the complete artifact set and binds the
  configuration, seed, revision state, `uv.lock`, schema versions, and event bytes to the
  replay manifest.
- Updated the README with the replay and benchmark commands and aligned CI's `uv` version with
  the locally verified version.
- Changed files for P0-T05: `.github/workflows/ci.yml`, `README.md`,
  `src/worm_world/benchmark.py`, `src/worm_world/cli.py`,
  `src/worm_world/experiments/runner.py`, `tests/test_benchmark.py`,
  `tests/test_phase0_acceptance.py`, `tests/test_runner.py`, the retained artifact files under
  `artifacts/phase0/acceptance_seed_42_steps_1000/`, and this handoff record.

## Phase 0 acceptance evidence

All Phase 0 build items now exist: the Python/`uv` scaffold, locked dependencies, local and CI
quality gates, versioned typed configuration, deterministic named RNG streams, versioned event,
snapshot, and manifest schemas, a fixed-timestep no-op world, deterministic replay hashing, a
benchmark, a retained artifact, and this handoff record.

The following CI-equivalent commands passed on Windows with CPython 3.12.13 and `uv` 0.11.28
on 2026-07-15:

```powershell
python -m uv sync --locked             # resolved and checked 20 packages
python -m uv run ruff format --check . # 18 files already formatted
python -m uv run ruff check .          # All checks passed
python -m uv run pyright               # 0 errors, 0 warnings, 0 informations
python -m uv run pytest                # 24 passed in 0.29s
python -m uv run pre-commit validate-config
```

The benchmark command and result were:

```powershell
python -m uv run python -m worm_world.benchmark --steps 100000
# 100000 steps in 0.01039179996587336 s; 9622971.990261523 steps/s
```

This is a local baseline, not a portable performance threshold. Energy, mass, and entity
lifecycle invariants are not applicable to the no-op world. The Phase 0 implementation is
headless and introduces no reward, objective, recipe, species rule, or mutable viewer.

## Retained artifacts and replay identity

- Artifact directory: `artifacts/phase0/acceptance_seed_42_steps_1000/`
- Files: `config.json`, `events.jsonl`, `snapshots.jsonl`, `manifest.json`
- Seed: `42`
- Fixed steps: `1000`; final simulated time: `50.0` seconds
- Configuration ID: `ccf7fd21914520a430d8fc8fb6221c9c402098f5f3bcdb44ce0ba5ee0e3eee14`
- Event hash: `bc6489a95e8b0c36bcbe465e895ebc3406c8e21522db3d5f8a603fb75caa7f12`
- `uv.lock` SHA-256: `300db4d0a775ec3e1e908795a402d991b1b63e2691d3807fc4b22e9f2d309691`
- Code revision: `unavailable:not-a-git-repository` (truthful current workspace state)
- Known failures: none in the local Phase 0 checks.

## Decisions in force

1. The simulator is a custom deterministic headless 2.5D system; rendering is read-only.
2. Python is pinned to 3.12 and dependencies are managed by `uv`; optimize only after
   profiling and keep ML libraries at the learning boundary.
3. Organisms receive no task rewards, scripted tools, or hard-coded species. Production
   learning will be evolved lifetime-only local plasticity.
4. Configuration and replay schemas use strict canonical JSON, explicit versions, exact field
   sets, and SHA-256 identities.
5. Randomness is owned by deterministic named streams; module-global random state is forbidden.
6. Simulation time is an integer step index. Elapsed seconds derive from the integer and fixed
   timestep rather than a separately accumulated clock.
7. Replay event hashing covers canonical UTF-8 JSON Lines including the terminal newline.
8. Artifact directories must be new, preventing silent overwrite or mixed runs.
9. Until Git exists, manifests use `unavailable:not-a-git-repository`; when Git exists, they
   record the commit plus dirty-worktree state. Python 3.12's PRNG algorithm is part of the
   runtime input, so cross-runtime replay compatibility is not promised.

## Exact next ticket

**P1-T01 — Baseline organism physiology and deterministic metabolism**

Add an `organisms` module with a small typed physiology configuration and state for energy,
hydration, injury, age, and alive/dead status. Implement one fixed-step metabolism transition
that consumes energy and hydration from explicit rates, advances age, clamps bounded signals,
and emits exactly one death transition when a physiological limit is reached. Keep this module
independent of world scheduling, sensors, actions, learning, reproduction, and species labels.
Add tests for deterministic depletion, timestep scaling, signal bounds, death idempotence, and
canonical snapshot/event representation; add the transition to the existing benchmark without
weakening replay tests. Run all canonical checks and update this handoff record.

## Known blockers and open questions

- The workspace is not a Git repository, so remote CI has not executed. The complete workflow's
  locked commands pass locally, and manifests truthfully record revision unavailability.
- Training hardware and budget are not specified; this does not block early Phase 1 work.
- Viewer presentation style is undecided; it remains outside the authoritative simulator.
