# Project State and Session Handoff

## Status

- **Active phase:** Phase 2 — persistent population and evolution.
- **Phase status:** Phase 1 complete and its exit gate passed; no Phase 2 implementation has
  started.
- **Last updated:** 2026-07-15.
- **Repository state at handoff:** Local Git repository on `main`. Phase 0 is commit `5bcb9d1`;
  the Phase 1 implementation is commits `84a85b8` and `80e7740`. No remote is configured and
  GitHub CLI is not installed. The retained Phase 1 artifact and this handoff update are the
  only expected post-implementation changes before the final handoff commit.

## Last completed work

- Completed **Phase 1 — single-organism survival sandbox** in bounded internal tickets:
  physiology/metabolism; segmented body and movement; finite food/water resources; sensing and
  actions; feeding, drinking, resting, and death; replay integration; benchmark and acceptance
  gate.
- Added a deterministic, headless fixed-step sandbox with one worm, a straight derived segment
  chain, bounded XY movement and turning, boundary contact, energy, hydration, injury, age, and
  an idempotent alive/dead lifecycle.
- Added weak food and water direction/intensity sensors plus energy, hydration, injury, and
  boundary-contact signals. No task reward or controller was added.
- Added finite food-energy and water patches. Eating and drinking transfer only available
  resources up to physiological capacity; food assimilation waste and metabolic losses are
  explicitly accounted for. Resources do not respawn.
- Added simultaneous `forward`, `turn`, `eat`, `drink`, and `rest` actions. Complete action
  sequences, initial conditions, physical parameters, resource parameters, world config, and
  seed are canonical experiment inputs.
- Added canonical Phase 1 artifacts and a verifier that re-simulates stored inputs and rejects
  any event or snapshot byte divergence.
- Added a sandbox CLI mode and full-transition benchmark while preserving the Phase 0 no-op CLI
  as the backward-compatible default.
- Initialized Git on `main`, installed the configured pre-commit hook, and preserved the Phase 0
  baseline before Phase 1 work.

Changed implementation and test files for Phase 1: `AGENTS.md`, `README.md`,
`src/worm_world/benchmark.py`, `src/worm_world/cli.py`,
`src/worm_world/experiments/__init__.py`, `src/worm_world/experiments/runner.py`,
`src/worm_world/experiments/sandbox_config.py`, `src/worm_world/organisms/__init__.py`,
`src/worm_world/organisms/core.py`, `src/worm_world/schemas.py`,
`src/worm_world/world/__init__.py`, `src/worm_world/world/sandbox.py`,
`tests/test_benchmark.py`, `tests/test_phase1_acceptance.py`, `tests/test_physiology.py`,
`tests/test_sandbox_runner.py`, `tests/test_sandbox_world.py`, the retained artifact under
`artifacts/phase1/acceptance_seed_42_actions_70/`, and this handoff record.

## Phase 1 acceptance evidence

The Phase 1 build items and exit criteria are covered by tests for deterministic metabolism and
timestep scaling; signal bounds; resting and movement costs; segmented-body snapshots;
predictable movement and boundary contact; food/energy and water conservation; mixed-action
conservation; sensor gradients and bounded interoception; resource capacity; death idempotence;
canonical configuration; changed-action replay identity; tamper detection; identical replay;
and an end-to-end movement/eating/drinking acceptance trajectory.

The following CI-equivalent commands passed on Windows with CPython 3.12.13 and `uv` 0.11.28
on 2026-07-15:

```powershell
python -m uv sync --locked             # resolved and checked 20 packages
python -m uv run ruff format --check . # 26 files already formatted
python -m uv run ruff check .          # All checks passed
python -m uv run pyright               # 0 errors, 0 warnings, 0 informations
python -m uv run pytest                # 41 passed in 1.09s
python -m uv run pre-commit validate-config
```

The full sandbox benchmark command and final measured result were:

```powershell
python -m uv run python -m worm_world.benchmark --mode sandbox --steps 100000
# 100000 steps in 0.6459040999179706 s; 154821.7452292065 steps/s
```

This is a local baseline, not a portable performance threshold. The implementation remains
dependency-free at runtime, runs headlessly, and introduces no reward, objective, recipe,
species rule, learning system, reproduction, or mutable viewer.

## Retained artifacts and replay identity

- Artifact directory: `artifacts/phase1/acceptance_seed_42_actions_70/`
- Files: `config.json`, `events.jsonl`, `snapshots.jsonl`, `manifest.json`
- Seed: `42`
- Fixed actions: `70`; final step: `70`; final simulated time and organism age: `3.5` seconds
- Trajectory: 20 forward actions, 5 eating actions, 40 reverse actions, 5 drinking actions
- Configuration ID: `848d1b90a3efca72d44b436301cc8651538eb7f9ce5263a7431a5daf0f47867c`
- Event hash: `2cef39d3dc584adafd45d5cb6da26c0ea002e20121ec172b3677818f1ad4ca21`
- Events: `72`; snapshots: `71`
- `uv.lock` SHA-256: `300db4d0a775ec3e1e908795a402d991b1b63e2691d3807fc4b22e9f2d309691`
- Code revision recorded by the artifact: `80e7740652cd82c87c91a5f35f02314d0d8a571a`
- Final organism: alive at approximately `(4.0, 5.0)`, energy `49.1`, hydration `50.9`,
  injury `0.0`
- Final finite resources: food energy `48.75`, water `48.75`
- Verification: `verify_sandbox_replay` re-simulated all 70 inputs and matched event and
  snapshot files byte-for-byte.
- Known replay failures: none.

## Decisions in force

1. The Phase 1 world is a flat deterministic 2.5D sandbox: authoritative motion is XY and the
   initial segment chain is deterministically derived behind the head pose. Articulated contact
   dynamics remain outside this phase.
2. Homeostatic values are raw organism signals, not a task score. There is no reward function,
   scripted foraging policy, learning state, reproduction, or species label.
3. Food energy and water are finite conserved stores. Energy assimilation waste, metabolic
   energy loss, and metabolic hydration loss are retained as explicit cumulative accounting.
4. The action for every fixed step is a simultaneous immutable input. The entire action sequence
   participates in the configuration ID and replay identity.
5. A death event is emitted exactly once on the alive-to-dead transition. Dead organisms cannot
   move, consume, age, or produce another death transition, although authoritative world steps
   may continue for replay completeness.
6. Simulation elapsed time and authoritative organism age derive from integer step count and the
   fixed timestep; they are not separate floating-point accumulators.
7. Phase 1 sensors are deliberately weak normalized directions and range-limited intensities,
   raw interoception, and contact. They do not identify tasks or prescribe actions.
8. Replay manifests validate any canonical JSON configuration by content hash and seed, allowing
   the Phase 0 and Phase 1 config schemas to coexist. The Phase 1 verifier additionally checks
   event and snapshot bytes by re-simulation.
9. The master seed remains a recorded experiment input even though the current Phase 1 sandbox
   transition contains no stochastic operation. Future randomness must use named RNG streams.
10. The Phase 0 no-op CLI remains the default; Phase 1 runs must explicitly use `--mode sandbox`.
11. Injury is represented, bounded, sensed, and lethal at its configured threshold, but Phase 1
   has no environmental injury source. Such hazards must be introduced as independently
   configurable general world dynamics, not task shaping.

## Exact next ticket

**P2-T01 — Structure-of-arrays population store and deterministic entity lifecycle**

Replace the single embedded organism ownership model at the Phase 2 boundary with a typed
population store that can hold multiple independently identified organism states in
structure-of-arrays form. Add deterministic monotonically allocated entity IDs, simultaneous
action lookup by ID, stable iteration order, insertion, exactly-once death removal/tombstoning,
and population snapshots/events. Keep reproduction, genomes, mutation, mating, compatibility,
selection metrics, and species analysis out of this ticket. Preserve the Phase 1 single-worm
adapter and replay bytes. Test stable ID allocation, action-order independence, simultaneous
stepping, lifecycle idempotence, snapshot ordering, Phase 1 replay regression, and deterministic
multi-organism replay. Run all canonical quality checks and the sandbox benchmark, then update
this handoff record.

## Known blockers and open questions

- No Git remote is configured, and GitHub CLI is not installed. Local Git history and hooks are
  working; connecting to a hosting repository requires its remote URL or repository name.
- Training hardware and budget are not specified; this does not block early Phase 2 work.
- The Phase 1 world has point resource fields and a flat height surface. Spatially distributed
  fields, terrain height, hazards, and resource dynamics should be added only by bounded future
  tickets with conservation and replay tests.
- Viewer presentation remains undecided and outside the authoritative simulator.
