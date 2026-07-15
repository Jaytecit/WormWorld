# The Worm World — Agent Operating Guide

## Purpose

Build a reproducible artificial-life research platform in which worm-like organisms survive, learn during their lifetimes, reproduce, and pass heritable traits to descendants. This is not a conventional game-AI project: no agent may receive a hand-authored task such as "find food", "build a tool", or "win".

Read this file and [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) before changing the project. Read [docs/PROJECT_STATE.md](docs/PROJECT_STATE.md) next; it is the authoritative handoff record for the last completed phase.

## North-star rules

1. **Selection is reproduction.** An organism's evolutionary success is its surviving descendants, not a score function supplied by the experimenter.
2. **Learning is lifetime-only by default.** Offspring inherit genome-encoded priors and learning capacity but not learned synaptic state. Any exception needs an explicit experiment flag and an updated decision record.
3. **No hidden curriculum.** Milestones are engineering work, not lessons for organisms. Once a capability exists, evaluation worlds are procedurally varied from the start.
4. **The simulator is authoritative.** Viewers, dashboards, and AI assistants consume recorded state; they never drive world state.
5. **Reproducibility beats visual polish.** A deterministic headless 2.5D simulation and replayable experiments come before 3D rendering.
6. **Do not claim emergence without an ablation.** A purported learned or evolved behaviour must be tested against appropriate controls and reported across independent seeds.

## Current phase and resume protocol

The project is at **Phase 0 — specification and repository bootstrap**. No simulation implementation has been started.

At the start of every development session:

1. Read `docs/PROJECT_STATE.md`, this file, and the active phase in `docs/DEVELOPMENT_PLAN.md`.
2. Inspect the working tree and preserve unrelated user work.
3. Implement only one bounded ticket from the active phase unless the user explicitly changes scope.
4. Run the checks specified by that ticket.
5. Update `docs/PROJECT_STATE.md` in the same change with completed work, verification, changed files, decisions, and the exact next ticket.

Do not advance a phase merely because code exists. Advance only after all phase exit criteria are met and recorded in `PROJECT_STATE.md`.

## Engineering constraints

- Use Python 3.12 and a `uv`-managed environment for the initial implementation.
- Start with a deterministic, fixed-timestep 2.5D world. The training environment must run headless.
- Keep the simulation core independent of rendering, web frameworks, and ML-library-specific APIs.
- Use typed configuration and explicit seeded random-number streams. Never use global random state.
- Treat world configuration, code revision, dependency lockfile, and seed as experiment inputs; save all of them with every run.
- Prefer a structure-of-arrays data layout for large populations. Profile before introducing Rust/C++, GPU kernels, or a game engine.
- Use a PettingZoo-style simultaneous-action adapter and PyTorch/TorchRL only at the boundary. The organism controller and plasticity rule remain project code.
- Use `pytest`, formatting/linting, type checks, deterministic replay tests, and a small benchmark from the first code change.

## Scientific constraints

- The only primitive values available to an organism are its sensory and physiological signals: e.g. energy, hydration, injury, temperature stress, and reproductive state.
- Do not award direct rewards for finding resources, mating, offspring, species diversity, construction, novelty, or task completion.
- If a reinforcement signal is used, it must be a documented, genome-parameterized function of change in internal homeostasis. Keep the raw signals in experiment logs.
- Species are analysis labels, never hard-coded classes. Infer them from lineage, compatibility, genetics, morphology, and ecology.
- Materials expose general physical affordances (mass, friction, buoyancy, breakage, attachment); there must be no `craft_tool` action or scripted recipe.
- Keep a learning-off and a mutation-off/evolution-off control for every major claim.

## Architecture boundaries

| Area | Owns | Must not own |
| --- | --- | --- |
| `world` | time, fields, terrain, spatial queries, collisions, events | neural-network training, rendering |
| `organisms` | bodies, physiology, sensors, actions, reproduction interface | world scheduling, species labels |
| `genetics` | genome schema, mutation, recombination, compatibility, lineage IDs | learned lifetime state |
| `learning` | controller, recurrent state, plasticity, policy diagnostics | evolutionary selection decisions |
| `experiments` | configs, seeds, runners, artifacts, statistical reports | simulation rules |
| `viewer` | replay playback and inspection | mutable simulation state |

Keep the public interfaces small and version them deliberately. Any cross-boundary change needs tests on both sides.

## Phase gates

| Phase | Goal | Do not start the next phase until |
| --- | --- | --- |
| 0 | Specification and bootstrap | deterministic-config, event-schema, CI, and handoff structure exist |
| 1 | Single-organism survival sandbox | metabolism, sensing, movement, feeding, and replay invariants pass |
| 2 | Population evolution | descendants demonstrate heritable survival differences across seeds |
| 3 | Lifetime learning | learning-on beats learning-off in held-out worlds without task rewards |
| 4 | Stable ecology | diverse population survives resource and seasonal variation |
| 5 | Material interaction | material-use claims pass causal counterfactual tests |
| 6 | Embodied 3D | 3D view/physics preserves headless reproducibility and benchmarks |
| 7 | Research workbench | every result is reproducible from a saved experiment manifest |

## Required handoff record

`docs/PROJECT_STATE.md` must always state:

- Active phase and precise status.
- Last completed ticket and its acceptance evidence.
- Current code/experiment commands and their results.
- Artifact locations, config IDs, seeds, and known failures.
- Architectural or scientific decisions made this session.
- One exact next ticket, including tests to run.

If no work was performed, say so explicitly rather than guessing.

## Code-review checklist

Before declaring a ticket complete, check:

- Is seeded replay deterministic?
- Are energy, mass, and entity-lifecycle invariants tested where applicable?
- Did the change introduce a hidden objective, reward, recipe, or species rule?
- Can the feature run headlessly without the viewer?
- Is the change independently configurable and logged?
- Is a regression test or benchmark included?
- Was `PROJECT_STATE.md` updated?

## Collaboration rules

- Split work by the architecture boundaries above. Do not allow parallel agents to edit the simulation core or the same state/configuration files.
- Keep tickets small: one observable behaviour, one public interface, and one verification target.
- Do not overwrite, reset, or discard user changes.
- Do not introduce a heavyweight engine or distributed infrastructure until a profiler or experiment scale measurement demonstrates the need.
