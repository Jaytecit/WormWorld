# Project State and Session Handoff

## Status

- **Active phase:** Phase 3 — lifetime learning.
- **Phase status:** Phase 2 is complete and its exit gate passed on 2026-07-15. Phase 3 is in
  progress; its scientific exit gate has not passed.
- **Last completed ticket:** P3-T02 — versioned heritable brain priors and local three-factor
  plasticity. This establishes the learning mechanism and ablation contract; it does not claim a
  population benefit or advance the Phase 3 scientific gate.
- **Repository state:** Local Git repository on `main`. The completed Phase 2, P3-T01, viewer
  contract, and Canvas viewer build was committed as `dd23200` on 2026-07-15. P3-T02 and this
  handoff are uncommitted. No remote is configured and GitHub CLI is not installed.

## Completed viewer scope

**V-T01 — read-only static Canvas population replay viewer:**

- Added a dependency-free responsive Canvas frontend backed exclusively by detached
  `PopulationReplay` frame dictionaries. It never constructs or advances a simulator in the
  browser.
- Added play/pause, speed selection, frame scrubbing, recorded step/time and active-population
  readouts, world bounds and meter grid, food/water fields, genome-colored segment chains,
  organism physiology/identity inspection, and optional retained tombstones.
- Added `python -m worm_world.viewer --replay <artifact> --output <new-directory>` to generate a
  self-contained static export. Frame data are embedded in `replay-data.js`, so the entry page does
  not require a web server or external JavaScript dependency.
- Added exporter and CLI regression tests that compare embedded frames with the immutable replay
  projection and reject overwriting an existing output directory.
- Changed files for this bounded ticket: `src/worm_world/viewer/__init__.py`,
  `src/worm_world/viewer/__main__.py`, `src/worm_world/viewer/web.py`,
  `src/worm_world/viewer/static/index.html`, `src/worm_world/viewer/static/styles.css`,
  `src/worm_world/viewer/static/app.js`, `tests/test_viewer_web.py`, `README.md`,
  `docs/VIEWER_CONTRACT.md`, and this handoff.

## Completed Phase 3 scope

**P3-T02 — versioned heritable brain priors and local three-factor plasticity:**

- Added a strict version-2 genome that contains explicit flattened recurrent-controller priors,
  hidden width, plasticity rate, eligibility-trace decay, and genome-parameterized energy,
  hydration, and injury modulation coefficients. Version-1 JSON, genome IDs, Phase 2 experiment
  configuration bytes, and retained replay bytes remain unchanged.
- Added seeded recombination and bounded mutation for all version-2 brain values. Parents must use
  the same schema and brain width; offspring inherit only initial priors and learning coefficients.
- Added deterministic local output-synapse updates of the form `rate × homeostatic change × prior
  eligibility trace`. The modulator uses only changes in the three existing raw internal sensor
  fractions. No task reward, trainer, new sensor, action, objective, or learned-state inheritance
  was added.
- Added lifetime-only learned weight deltas, eligibility traces, previous homeostatic readings, and
  per-entity diagnostics. These are clean for founders and births, removed with inactive entities,
  and absent from genomes, lineage records, authoritative snapshots, and reproduction.
- Added a plasticity-off runtime ablation that is action/output-identical to a matched zero-rate
  control while retaining the same priors, recurrence, sensors, and trace arithmetic.
- Changed files for this bounded ticket: `src/worm_world/genetics/genome.py`,
  `src/worm_world/genetics/__init__.py`, `src/worm_world/learning/controller.py`,
  `src/worm_world/learning/__init__.py`, `src/worm_world/experiments/evolution.py`,
  `tests/test_genetics.py`, `tests/test_learning_controller.py`, and this handoff.

**P3-T01 — deterministic recurrent controller contract and clean lifetime initialization:**

- Added a learning-owned recurrent controller that maps the existing ten raw sensor values to the
  existing movement, ingestion, rest, and reproduction action channels.
- Initial weights are a deterministic, platform-independent projection of the existing canonical
  genome ID. This preserves every Phase 2 genome ID and replay byte while establishing the
  controller contract. Explicit independently evolvable brain genes remain P3-T02 work.
- Controller state is lifetime-only, isolated by entity ID, initialized to zero for every founder
  and newly observed birth, removed for inactive entities, and absent from genomes, lineages, and
  authoritative snapshots.
- The learning-off control disables recurrent history and resets hidden output state to zero. It is
  a contract control only; no plasticity or learning-benefit claim exists yet.
- Added read-only population sensing using the retained Phase 1 `SensorReadings` contract. Sensing
  has no world mutation and adds no new primitive signals or actions.

The user also requested advancement to a point where a 2/2.5D presentation can be implemented.
That boundary is now ready through `worm_world.viewer.PopulationReplay` and
`docs/VIEWER_CONTRACT.md`. It strictly projects recorded population artifacts into immutable,
renderer-neutral frames with world bounds, resource patches, organism identity/physiology, heading,
and full segment chains. It neither constructs nor advances a simulator.

## Completed Phase 2 scope

Phase 2 was completed as six bounded internal tickets after the user explicitly requested the
remaining phase rather than one ticket:

1. **P2-T01 — population storage and lifecycle:** structure-of-arrays state, monotonic entity IDs,
   stable simultaneous action resolution, retained tombstones, and exactly-once deaths. The
   Phase 1 single-worm API remains a compatibility adapter.
2. **P2-T02 — genomes and founder phenotypes:** strict versioned canonical genomes, content-derived
   genome IDs, pure genome-to-body/physiology mapping, and immutable entity/genome associations.
3. **P2-T03 — inheritance and compatibility:** deterministic seeded recombination and bounded
   mutation, normalized genetic compatibility, configurable mutation-off behavior, and no learned
   state in inheritance.
4. **P2-T04 — persistent reproduction and lineages:** configurable sexual or asexual reproduction,
   mutual mate requests and spatial/compatibility checks for sex, energy/water-funded offspring,
   maturity/cooldown/population limits, deterministic lineage IDs, parent records, descendant
   traversal, and birth/death steps.
5. **P2-T05 — spatial competition and reporting:** stable movement, fair simultaneous water-fill
   allocation of finite shared food/water, genome-specific metabolism, population snapshots,
   descendant survival measures, genotype Shannon diversity, unique-genome count, and mean
   pairwise genetic distance. Species remain analysis-only and no species classes were added.
6. **P2-T06 — acceptance and controls:** canonical Phase 2 configs, raw events, snapshots, reports,
   replay manifests, byte-for-byte verifier, CLI mode, population benchmark, and a paired
   heritable/randomized-offspring suite across three independent seeds.

The Phase 2 experiment uses the same fixed raw action protocol for every organism: rest, eat,
drink, and request reproduction. It supplies no reward, fitness score, task label, controller,
learning state, curriculum, or species rule. Selection is measured only through survival and
actual descendants.

## Phase 2 exit-gate evidence

Retained suite: `artifacts/phase2/acceptance_seeds_11_22_33/`

- Seeds: `11`, `22`, `33`; 500 fixed steps per condition; heritable and matched
  randomized-offspring control for every seed.
- Every heritable run produced 52 births and 4 deaths, finishing with 56 organisms.
- In every heritable run, low-metabolism founders had 48 surviving descendants and
  high-metabolism founders had 0. Late births were 100% low-metabolism; the final population was
  92.86% low-metabolism; parent/offspring trait matching was 100%.
- Control runs produced 39–46 births and 6–8 deaths, finishing with 39–48 organisms. Their late
  low-metabolism birth fractions were 0.3333, 0.4762, and 0.5185; the median absolute deviation
  from the randomized 0.5 expectation was below the predeclared 0.2 limit. Parent/offspring match
  fractions were 0.4103, 0.5250, and 0.5870, all below the predeclared median limit of 0.7.
- The suite's predeclared aggregate gate is `acceptance_passed: true`. The heritable condition
  therefore demonstrates repeatable inherited descendant-survival differences, while randomized
  offspring remove the cross-generation trait-concentration trend.
- Mutation is deliberately disabled in the matched gate so it isolates heritability. Mutation-on,
  mutation-off, recombination, sexual compatibility, and asexual behavior are separately covered
  by deterministic unit/integration tests.

Each of the six run directories contains `config.json`, `events.jsonl`, `snapshots.jsonl`,
`report.json`, and `manifest.json`. `summary.json` records the criteria, hardware, seeds, and all
aggregate reports. All six runs independently replayed byte-for-byte.

| Run | Config ID | Event hash |
| --- | --- | --- |
| seed 11, heritable | `d2494a2fa85433903efbca4697956e5a460cebffcab52736bc161cee6267f09c` | `1f17a03efc012877aa7100ed8f198869acb82a09c297bb1731485a040ddf462a` |
| seed 11, control | `01e5bacd4758d8aa251fa85a20f1543bc3b68c08755284929bfa4944aa134f64` | `bfb58a03d38c780e61494726b2458d2ddb3ef5cb438c0154586c5e7f29b8c158` |
| seed 22, heritable | `edf4a27fb1fb138bbfbb123191772c3774bb6f3ea0eb9a65df92114ce16930f2` | `0f3429d25842cedd1f6253dbf656e280ee482299a156dc6e090a7fe2f4e7dd7b` |
| seed 22, control | `ec5e8a5d76cdc67b53a7bbae7de268ae1de5ee5b4d31c855b27fa3c0c257790e` | `558b84c45bc4e9159acbd881706fd762887af79cdb96bef20abdaf1006169569` |
| seed 33, heritable | `14a1f16cf35723244c74a09e7bda0ef746f1b57db123e3326f7be531c55857e2` | `44550930ecb476d4b4edfacafdc7e582b64546cf777e130036ab3a287a7cd453` |
| seed 33, control | `b0a63f96d7e0180480ae081cb5b97fa4b0dcab3bfbe47ddfb8bf342824f81a9f` | `8a617fc5650ee7d3a42d2c001e5afdfc5bc73da4df8e2a651576032c05e858ab` |

The table values must remain synchronized with the retained manifests. The dependency lock digest
for every run is `300db4d0a775ec3e1e908795a402d991b1b63e2691d3807fc4b22e9f2d309691`.
Artifacts record revision `1fdeb5439f303a65410eb3d8433c8317dcd4531c+dirty`, accurately reflecting
that the Phase 2 work was uncommitted when generated.

## Verification and performance

The final CI-equivalent checks passed on Windows 11 with CPython 3.12.13 and `uv` 0.11.28:

```powershell
python -m uv sync --locked
python -m uv run ruff format --check .
python -m uv run ruff check .
python -m uv run pyright
python -m uv run pytest
python -m uv run pre-commit validate-config
```

Final expected test result: `73 passed`. Coverage includes genome validation/round trips and IDs;
pure phenotype identity/differences; seeded inheritance; compatibility; transitive ancestry;
asexual and sexual births; reproduction conservation; fair shared-resource competition; stable
entity/genome snapshots; exactly-once deaths; deterministic event ordering; strict config identity;
multi-seed acceptance; artifact tamper/replay checks; and every retained Phase 0/1 test.

Phase 3 additions cover frozen version-1 identity, strict version-2 brain round trips, bounded brain
inheritance/mutation, controller prior/state shape and finite-value validation, deterministic bounded
transitions, exact three-factor update arithmetic, plasticity-off identity, learning-off history
independence, diagnostic projection, per-entity state isolation, action mapping order independence,
clean birth initialization, read-only population sensing, strict replay frame loading, immutable
viewer projection, final-frame identity, and static Canvas export/CLI fidelity.

Measured local benchmarks on 2026-07-15:

```powershell
python -m uv run python -m worm_world.benchmark --mode sandbox --steps 100000
# 100000 steps in 0.7975576999597251 s; 125382.77795456024 steps/s

python -m uv run python -m worm_world.benchmark --mode population --steps 1000
# 1000 steps with 64 organisms in 1.6043343999190256 s; 623.3114493153499 world steps/s
```

These are local regression measurements, not portable thresholds. The Phase 1 retained replay was
also re-simulated byte-for-byte with unchanged event hash
`2cef39d3dc584adafd45d5cb6da26c0ea002e20121ec172b3677818f1ad4ca21`.

## Decisions in force

1. Genome IDs are SHA-256 hashes of strict canonical version-1 genome JSON. Genomes contain only
   inherited body, physiology, fertility, offspring allocation, and mutation priors—never lifetime
   physiology, recurrent state, or learned weights.
2. Reproduction transfers energy and hydration from parent(s) to offspring. It does not create a
   fitness score or free organism biomass. Sexual reproduction requires reciprocal requests,
   proximity, maturity, energy, cooldown, and genetic compatibility.
3. Resource claims are resolved simultaneously by deterministic water filling. Mapping insertion
   order and entity ID do not grant priority when a finite patch is contested.
4. The heritability-off control draws each offspring genome from the founder genome distribution
   using its own named seeded stream. Parentage is retained, so loss of cross-generation trait
   concentration can be measured without changing resource physics or actions.
5. Diversity measures are genotype/lineage analyses only. No species labels, objectives, rewards,
   learning, or viewer-driven state exist in Phase 2.
6. Phase 1's public single-organism adapter and replay wire bytes remain unchanged. Phase 2 uses a
   separate explicit `PopulationWorld` and versioned experiment config.
7. Controller recurrent state is owned by `learning`, keyed by stable entity ID, and never enters
   genomes, lineage records, snapshots, or reproduction. P3-T01 priors derive from the canonical
   genome ID so legacy genome/replay identity remains exact until a deliberate schema-v2 change.
8. Viewer clients consume immutable projections of saved artifacts. The viewer boundary is
   renderer-neutral and cannot mutate or advance authoritative simulation state.
9. The version-1 graphical viewer uses the browser's Canvas 2D API with no runtime dependency or
   server. Export is explicit and refuses an existing directory, preserving recorded artifacts and
   prior viewer exports.
10. Genome version 2 stores concrete initial controller weights and plasticity coefficients.
    Learned output-weight deltas, eligibility traces, recurrent activations, and prior homeostatic
    readings are lifetime state owned by `learning` and can never enter inheritance. The local
    neuromodulator is a logged genome-weighted sum of energy, hydration, and injury-fraction change.

## Known blockers and limitations

- No Git remote is configured, and GitHub CLI is not installed. This does not affect local replay.
- The retained acceptance suite isolates two metabolism genotypes in a deliberately small fixed
  world. It establishes the Phase 2 inheritance gate but is not evidence of open-ended evolution,
  speciation, learning, or ecological stability.
- Resource patches remain finite point fields on flat 2.5D terrain. Richer resource dynamics and
  ecology remain Phase 4 work.
- The Phase 2 fixed action protocol is an experiment input, not an autonomous controller. Phase 3
  now has lifetime-only recurrent state but still needs local plasticity, evolvable brain priors,
  diagnostics, and matched held-out learning-on/off evidence without direct task rewards.
- P3-T02 supplies a plastic learning mechanism, not demonstrated adaptive benefit. It currently
  updates only hidden-to-output synapses. No learning-benefit or emergence claim is warranted until
  the matched held-out Phase 3 acceptance suite passes.
- The Canvas viewer is replay-only: it has no live streaming, terrain height, dynamic ecology, or
  materials. Those require backward-compatible later viewer schemas. Automated direct-file visual
  QA was unavailable because the in-app browser disallows `file:` navigation; exporter fidelity,
  JavaScript syntax, and browser-facing assets were verified, but a manual browser appearance check
  remains advisable.

## Exact next ticket

**P3-T03 — deterministic learning-on/off experiment and diagnostic artifacts**

Add one versioned Phase 3 experiment configuration and headless runner that couples the existing
`PopulationController` to `PopulationWorld`, records raw energy/hydration/injury changes,
neuromodulators, update magnitudes, controller outputs, and the plasticity-enabled flag, and writes
replay-verifiable artifacts. Define matched learning-on and plasticity-off conditions with identical
version-2 founder genomes, world configuration, named RNG streams, and action interface. Use a small
procedurally varied training-world fixture but do not tune or claim held-out benefit yet. Do not add
task rewards, a trainer, new sensors/actions, learned-state inheritance, or modify the retained Phase
2 experiment. Test strict config identity, learning-on/off matching, diagnostic event ordering,
action mapping order independence, clean birth/death controller lifecycle, deterministic artifact
bytes, tamper detection, and every retained replay. Run formatting, lint, strict types, the full
suite, pre-commit validation, and both benchmarks; then update this handoff.
