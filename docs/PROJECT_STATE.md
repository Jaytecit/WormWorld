# Project State and Session Handoff

## Status

- **Active phase:** Phase 4 — stable ecology.
- **Phase status:** Phase 3 completed and its frozen lifetime-learning exit gate passed on
  2026-07-15. Phase 4 is in progress: its first bounded world mechanism is complete, but no stable
  ecology or population-persistence gate has yet been run.
- **Last completed ticket:** P4-T01 — deterministic resource-limited plant biomass field. An
  opt-in world-owned plant patch now converts explicitly deducted finite light, water, and
  nutrients into bounded edible biomass and uses the existing fair simultaneous feeding path.
- **Repository state:** Local Git repository on `main`, eleven commits ahead of configured
  `origin`. P3-T10, P3-T11, and the Phase 3 viewer follow-up were committed as `0315ffa`; P4-T01
  is the current commit, both completed on 2026-07-15. GitHub CLI is not installed; no push was
  attempted.

## Completed Phase 4 scope

**P4-T01 — deterministic resource-limited plant biomass field:**

- Added strict canonical `PlantPatchConfig` identity and a world-owned `PlantPatch` with finite
  biomass, light, local water, and nutrient state. Fixed-step growth is limited simultaneously by
  growth rate, biomass capacity, and every required input, and deducts the exact uptake.
- Integrated the patch as an opt-in `PopulationWorld` food source. Enabled plant biomass uses the
  existing position sensor, eat action, assimilation efficiency, and order-independent fair claim
  allocator; ambiguous simultaneous static and plant food pools are rejected.
- Added one auditable `plant.step` event per enabled step with biomass before/after, growth,
  consumption, and each input uptake. Enabled snapshots include a detached plant state projection;
  disabled configurations add no fields or events and preserve historical bytes.
- Added deterministic tests for no-input growth, bounded growth/uptake, fair feeding, energy and
  plant lifecycle accounting, strict configuration identity, disabled historical identity,
  detached snapshot projection, and invalid mixed food sources. Added a matching plant-enabled
  population benchmark.
- This is only a plant mechanism. Its input stores are finite and it does not establish resource
  cycling, descendant replacement, viable ecology, diversity, or seasonal robustness.
- Changed files: `src/worm_world/world/plants.py`, `src/worm_world/world/population.py`,
  `src/worm_world/world/__init__.py`, `src/worm_world/benchmark.py`, `tests/test_plants.py`,
  `tests/test_benchmark.py`, and this handoff.

## Completed viewer scope

**V-T02 — Phase 3 learning-replay compatibility and visual QA:**

- Extended the strict read-only loader to dispatch by the stored versioned experiment type and
  accept current `LearningExperimentConfig` artifacts as well as Phase 2 evolution artifacts. It
  still validates config/manifest identity and never simulates or mutates world state.
- Added a learning-artifact regression test and exported the confirmed seed-501 learning-on replay
  to `artifacts/viewer/p3t11_seed_501_on/`. The in-app Canvas viewer was opened over localhost,
  playback and final-frame scrubbing were exercised, and browser logs contained no warnings/errors.
- Visual QA confirmed step `384`, time `192.00 s`, and two active organisms at the final frame,
  matching the authoritative P3-T11 summary. The open interface remains a replay, not a live
  simulation controller.
- Changed files: `src/worm_world/viewer/replay.py`, `tests/test_viewer_replay.py`, the two retained
  Phase 3 viewer exports, and this handoff.

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

**P3-T11 — frozen rate-0.25 survival reconfirmation:**

- Extended confirmation authorization to accept exactly one evidence source and bind the P3-T10
  robustness verifier's returned config byte-for-byte. Added mismatch rejection while preserving
  the original P3-T08/P3-T09 authorization path and artifact identity.
- Executed exactly preregistration config ID
  `2ce5947b237602de545c4893c18087bc2b4ecee4dac8b14c2547a0d71a9ae070` on held-out seeds
  `501, 502, 503, 504, 505`, rate `0.25`, four founders, 384 steps, with semantic on, off, zero-rate,
  and legacy controls. Retained all 20 children at `artifacts/phase3/survival_confirmation_v2/`.
- Learning-on final-population advantages were `[2,4,3,3,2]`, mean `2.8`, 95% CI `[2.2,3.4]`.
  Energy-fraction advantage mean was `0.017126347492499628`, 95% CI
  `[0.008212209694103906,0.02560086408894993]`. Learning extinction was `0.0`, control extinction
  `0.4`, win fraction `1.0`, and off/zero identity was exact.
- Every frozen predicate passed and the retained result is `acceptance_passed: true`; Phase 3's
  lifetime-learning gate is complete. Learning-on births were `[2,0,0,0,1]`, but every
  surviving-descendant count was zero, so no reproductive/evolutionary-success claim is made.
- Every P3-T11 child and all retained Phase 1–3 artifacts replayed byte-for-byte after the change.
  Changed files for this ticket: `src/worm_world/experiments/learning_survival_gate.py`,
  `tests/test_learning_survival_gate.py`, the retained confirmation suite, and this handoff.

**P3-T10 — expanded development-only robustness screen:**

- Added strict canonical `RobustnessScreenConfig`, fixed rates `0.25, 0.5, 1.0`, consumed-held-out
  seed exclusion, matched semantic on/off/zero children, deterministic lowest-qualified-rate
  selection, explicit birth/surviving-descendant matrices, and full child replay/tamper verification.
- Locked fresh development seeds `401`–`410`, four founders, the unchanged 384-step fixture/world,
  action-semantic eligibility, and the P3-T09 founder genome. Retained 90 child runs at
  `artifacts/phase3/development_robustness_v1/` under config ID
  `09a8f79e63e8e57531343e77302912ef21163246dcd3d479dc04c2fb90afbcc7`.
- Final-population advantages were `[3,4,2,3,2,1,3,3,3,3]` at rate `0.25`,
  `[3,4,2,3,2,1,3,3,4,3]` at `0.5`, and `[3,4,2,3,2,1,3,3,4,4]` at `1.0`; means were
  `2.7`, `2.8`, and `2.9`. Learning-on avoided extinction on every seed and off/zero outputs,
  actions, and reports were exactly identical at every rate.
- All rates qualified. The predeclared conservative rule selected the lowest, rate `0.25`, genome
  ID `888710e6cd982b741edee8b0c64e25edfb62d41d2a241f52896458d763944154`. Learning-on births
  were `[1,0,2,0,2,2,0,0,0,1]`, but surviving descendants were zero in every rate/seed condition;
  the evidence remains lifetime-survival evidence only.
- Added a robustness-evidence-bound preregistration writer/verifier. Fresh held-out seeds
  `501`–`505` are frozen but unexecuted at
  `artifacts/phase3/survival_gate_preregistration_v2/`, config ID
  `2ce5947b237602de545c4893c18087bc2b4ecee4dac8b14c2547a0d71a9ae070`, with all P3-T09
  thresholds unchanged. No held-out result was inspected during candidate selection.
- Changed files for this bounded ticket: `src/worm_world/experiments/learning_robustness.py`,
  `src/worm_world/experiments/__init__.py`, `tests/test_learning_robustness.py`, both retained P3-T10
  artifact directories, and this handoff.

**P3-T09 — frozen survival confirmation suite:**

- Added an authorization-enforcing confirmation runner and verifier. It refuses any config that
  differs from the committed preregistration and runs semantic plasticity-on, plasticity-off,
  zero-rate, and legacy-rule conditions for each frozen held-out seed.
- Added replay verification for every child config/event/snapshot/report/manifest, exact off/zero
  output/action identity, paired seeded population/energy intervals, extinction fractions, win
  fraction, and explicit birth/surviving-descendant outcomes.
- Executed exactly config ID `49aa29a2c93825536789a87625f3df873bd653dece1f157554c9b16233d63f9a`
  on seeds `301, 302, 303, 304, 305` at 384 steps. Retained all 20 child runs and summary at
  `artifacts/phase3/survival_confirmation_v1/`; every artifact replayed byte-for-byte.
- Learning-on versus off final-population differences were `[3, 4, 3, 0, 3]`, mean `2.6`, 95% CI
  `[1.2, 3.6]`. Energy-fraction difference mean was `0.06125324743180214`, 95% CI
  `[0.03033166261088103, 0.08017710520173542]`. Off/zero identity passed on all seeds.
- Seed 304 went extinct in every condition. Learning extinction was therefore `0.2` and paired win
  fraction `0.8`, violating the frozen `0.0` maximum and `1.0` minimum despite control extinction
  `0.8`. The stored result is `acceptance_passed: false`; Phase 3 does not advance.
- Learning-on births were `0, 0, 1, 4, 1`; every learning-on surviving-descendant count was zero.
  The result supports a repeatable but not universal lifetime-survival effect, not enhanced
  reproductive/evolutionary success.
- Changed files for this bounded ticket: `src/worm_world/experiments/learning_survival_gate.py`,
  `src/worm_world/experiments/__init__.py`, `tests/test_learning_survival_gate.py`, the retained
  confirmation suite, and this handoff.

**P3-T08 — explicit survival-gate protocol amendment and preregistration:**

- Added separate strict versioned `SurvivalGateCriteria` and `SurvivalGateConfig` contracts. The
  new protocol evaluates a lifetime controller by viable final population, extinction avoidance,
  and final energy non-harm; it does not change simulator selection or provide a reward.
- Births, deaths, and surviving descendants remain explicit outcomes. They do not enter the new
  pass predicate because a fixed-horizon lifetime-learning comparison need not increase raw birth
  count; evolutionary success remains actual surviving descendants in evolutionary experiments.
- Added deterministic paired bootstrap intervals and a development authorization artifact that
  binds the candidate genome, semantic rule, horizon, seed partitions, zero-control identity, and
  exact P3-T07 sensitivity evidence ID before any held-out execution.
- Retained `artifacts/phase3/survival_gate_preregistration_v1/` has config ID
  `49aa29a2c93825536789a87625f3df873bd653dece1f157554c9b16233d63f9a`, development seeds
  `101, 102, 103`, frozen held-out seeds `301, 302, 303, 304, 305`, 384 steps, rate `1.0`, semantic
  eligibility, 2,000 bootstrap samples, and unchanged founder/world generation.
- Development final-population differences are `[2, 2, 4]`, mean `2.6666666666666665`, 95% CI
  `[2.0, 4.0]`, and win fraction `1.0`. Energy-fraction difference mean is
  `0.06975988612170268`, 95% CI `[0.056305838195795384, 0.07999224043084271]`; learning extinction
  is `0.0` versus control `0.6666666666666666`. `confirmation_authorized` is true.
- Development births are `0, 2, 0` on versus `0, 2, 1` off. Surviving-descendant counts are zero in
  every condition; this limitation is reported and prevents any evolutionary-success claim.
- Changed files for this bounded ticket: `src/worm_world/experiments/learning_survival_gate.py`,
  `src/worm_world/experiments/__init__.py`, `tests/test_learning_survival_gate.py`, the retained
  preregistration artifacts, and this handoff.

**P3-T07 — development-only action-semantic eligibility traces:**

- Added a versioned eligibility rule. Continuous forward/turn channels retain `tanh(raw_output)`;
  binary eat/drink/rest/reproduce channels use their already-computed sigmoid activation. The
  legacy all-`tanh` rule remains the schema-v1 default and an explicit ablation.
- Added schema-v2 learning experiment, suite, and sensitivity configs that serialize the rule.
  Schema-v1 JSON omits the new field, retains canonical IDs/bytes, and replayed every retained
  Phase 3 artifact without divergence.
- Extended development sensitivity runs with a matched legacy-rule condition when the v2 semantic
  rule is active. Plasticity-off and zero-rate controls remain exactly output/action identical.
- Retained `artifacts/phase3/development_action_eligibility_v2/` uses rate `1.0`, 384 steps, four
  founders, seeds `101, 102, 103`, sensitivity config ID
  `49b807b35215ac693fc87ca5739d9ef7ef5df905d8fdb886c82da410aa99196b`, and 12 verified child
  artifacts (semantic on/off/zero plus legacy on for each seed).
- Semantic plasticity-on produced births/deaths/final populations of `0/0/4`, `2/4/2`, and `0/0/4`.
  Matched off/zero controls produced `0/2/2`, `2/6/0`, and `1/5/0`. Final-population advantages
  were `2, 2, 4`, mean `2.6666666666666665`, and learning-on avoided extinction on all three seeds.
- Birth differences were `0, 0, -1` (mean `-0.3333333333333333`), so the unchanged gate correctly
  kept `candidate_development_passed` and `future_confirmatory_authorized` false. Seeds `301`–`305`
  were not executed; stored future-suite ID is
  `d52b59ba1021a69997000b34c0c8e7a88a0a0cd3b9d9220d5b50ad41df9cb1fd`.
- Changed files for this bounded ticket: `src/worm_world/learning/controller.py`,
  `src/worm_world/learning/__init__.py`, `src/worm_world/experiments/learning.py`,
  `src/worm_world/experiments/learning_suite.py`,
  `src/worm_world/experiments/learning_sensitivity.py`, the four learning test modules, the retained
  action-eligibility artifacts, and this handoff.

**P3-T06 — development-only neutral action-margin priors:**

- Added an exact version-2 prior transformation that sets only the four binary output biases to the
  neutral zero logit. Every input/recurrent/output weight, motion bias, plasticity coefficient,
  sensor, action, and world rule remains unchanged; no action direction is favored from outcomes.
- Added deterministic signed/absolute margin analysis for eat, drink, rest, and reproduce logits,
  plus generation and replay verification of a stored `margin_analysis.json` beside the existing
  sensitivity artifact contract.
- Retained `artifacts/phase3/development_neutral_margins_v1/` uses rate `1.0`, 128 steps, four
  founders, development seeds `101, 102, 103`, exactly zero binary output biases, and sensitivity
  config ID `bf302b3301a00cb047c886611c8cf341c4e9ee3ba2e6306c54378d565fd862a3`.
- All nine on/off/zero child runs and the margin analysis replayed. Off and zero-rate outputs/actions
  remained exactly identical. Plasticity-on changed continuous motion on 508/512 matched steps for
  every seed, but caused only three rest decisions on seed 102 and no eat, drink, or reproduce
  divergence on any seed.
- Every condition produced zero births, zero deaths, and four final organisms. Development birth,
  population, and win advantages were zero, so the candidate and future confirmation remain
  blocked. Seeds `301`–`305` were not executed.
- Changed files for this bounded ticket: `src/worm_world/experiments/learning_sensitivity.py`,
  `src/worm_world/experiments/__init__.py`, `tests/test_learning_sensitivity.py`, the retained
  neutral-margin artifacts, and this handoff.

**P3-T05 — development-only plasticity sensitivity and causal action divergence:**

- Analyzed only development seeds `101, 102, 103`. At the previous maximum rate `0.1`, learned
  weights changed continuous motion from step two but produced no eat/drink/rest divergence, only
  four reproduction-decision divergences, and zero birth/final-population advantage.
- Widened the existing genome-encoded plasticity-rate bound from `[0, 0.1]` to `[0, 1.0]`; no new
  parameter, sensor, action, signal, objective, or inheritance path was added. Retained version-1
  and version-2 JSON values and replays remain valid and byte-identical.
- Added a strict `PlasticitySensitivityConfig`, deterministic paired action-divergence analysis,
  development-only on/off/zero-rate runner, child replay verification, and an authorization gate
  that prevents confirmatory execution unless development birth/population criteria pass.
- Retained `artifacts/phase3/development_sensitivity_v1/` uses rate `1.0`, 128 steps, four founders,
  development seeds `101, 102, 103`, sensitivity config ID
  `3d92e50aaf1e29e6345405c73ea845c87069cb964bc48fbfa60e16e161bef72e`, and nine independently
  replayed child artifacts.
- Plasticity-on diverged in continuous motion on 508/512, 722/726, and 618/622 matched entity steps;
  reproduction diverged 25, 116, and 33 times, and drinking diverged ten times on seed 102. The
  plasticity-off and zero-rate controls had exactly zero output/action divergence on every seed.
- The candidate still had zero birth and final-population advantage on all development seeds, so
  `candidate_development_passed` and `future_confirmatory_authorized` are false. Fresh seeds
  `301`–`305` and unchanged criteria are stored in unexecuted suite config ID
  `ec53929b02d90314ca1f4af32d70067ff145c2c0ff8c388d1b0880e487e85b2b`.
- Changed files for this bounded ticket: `src/worm_world/experiments/learning_sensitivity.py`,
  `src/worm_world/experiments/__init__.py`, `src/worm_world/genetics/genome.py`,
  `src/worm_world/learning/controller.py`, `tests/test_learning_sensitivity.py`,
  `tests/test_genetics.py`, the retained development artifacts, and this handoff.

**P3-T04 — predeclared matched held-out evaluation harness:**

- Added strict versioned `LearningSuiteConfig` and `LearningGateCriteria` contracts. Development
  and held-out seeds must be unique and disjoint; the stored founder genome, step/population sizes,
  bootstrap seed/sample count, confidence level, and pass thresholds are suite inputs.
- Added paired plasticity-on/off execution for both partitions. Each pair has identical realized
  world inputs, version-2 founder genome, named RNG streams, sensors/actions, physiology, and
  reproduction; only `plasticity_enabled` differs.
- Added deterministic seeded bootstrap intervals for births, final population, final energy,
  hydration, and injury fractions. Positive differences favor plasticity-on (injury reverses the
  subtraction direction). The aggregate gate additionally requires paired birth/population wins.
- Added suite replay verification that verifies every child run byte-for-byte, binds each child
  manifest back to its locked suite input, recomputes outcomes/statistics, and rejects summary or
  child-artifact divergence.
- Retained suite `artifacts/phase3/heldout_evaluation_v1/` uses development seeds `101, 102, 103`,
  held-out seeds `201, 202, 203, 204, 205`, 64 steps, four founders, 2,000 bootstrap samples, and
  suite config ID `e7a06719c861ecc099e06117982aabb52aa530811c1006aee75adeddedc69b68`.
  All 16 child runs replayed byte-for-byte.
- The predeclared gate result is `acceptance_passed: false`. Held-out birth and final-population
  paired differences were all zero, with means and 95% intervals `[0.0, 0.0]`; paired win fraction
  was zero. Mean final energy-fraction advantage was `0.00011296014339794436`, with 95% interval
  `[0.00008107815248297179, 0.0001391097293124144]`. This small physiological difference is not a
  survival or descendant benefit and does not pass Phase 3.
- Changed files for this bounded ticket: `src/worm_world/experiments/learning_suite.py`,
  `src/worm_world/experiments/learning.py`, `src/worm_world/experiments/__init__.py`,
  `tests/test_learning_suite.py`, the retained evaluation suite, and this handoff.

**P3-T03 — deterministic learning-on/off experiment and diagnostic artifacts:**

- Added a strict versioned `LearningExperimentConfig`, a seeded procedural training-fixture
  constructor whose realized resource/founder positions are stored in canonical configuration,
  and a headless CLI mode that couples `PopulationController` to `PopulationWorld`.
- Added matched plasticity-on/off conditions that differ only in the runtime ablation flag. They
  retain identical version-2 founder genomes, world inputs, named streams, recurrent state,
  eligibility arithmetic, sensors, actions, physiology, and reproduction rules.
- Added ordered `controller.step` events containing raw internal-state fractions, their changes,
  neuromodulators, update and learned-weight magnitudes, controller outputs, chosen actions, genome
  IDs, and the plasticity flag. These events are part of the replay manifest's event hash.
- Added byte-for-byte verification of configuration, events, population snapshots, diagnostic
  report, manifest identity/counts, and tamper rejection. Controller state is synchronized after
  deaths; births receive clean lifetime state on first observation.
- Retained matched seed-11, 64-step diagnostic runs at
  `artifacts/phase3/diagnostic_seed_11_on/` and
  `artifacts/phase3/diagnostic_seed_11_off/`. Both produced three births, no deaths, and a final
  population of seven. The on config/event hashes are
  `f3d8821d6301e253ffea552bf93c9fd1ec973146c4e72713a004be380c91a2da` /
  `aed154d20fb944fc4f4c46326532fd3fd8d86f3c42d7e631fe9af09cd6bd98a8`; the off hashes are
  `2ff5d4e167296d5317f6e739ff1a1146de014e6cc459905b4cdc85cbcaa12f78` /
  `63efee757dbcfe25950a0da5c33b38022696df77cde476d2ebfba15f7c32ec13`. This equality is
  diagnostic only and is not evidence of learning benefit.
- Changed files for this bounded ticket: `src/worm_world/experiments/learning.py`,
  `src/worm_world/experiments/__init__.py`, `src/worm_world/learning/controller.py`,
  `src/worm_world/genetics/__init__.py`, `src/worm_world/cli.py`,
  `tests/test_learning_experiment.py`, `README.md`, the retained Phase 3 artifacts, and this
  handoff.

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

Final test result: `102 passed` in 31.37 seconds. Coverage includes genome validation/round trips and IDs;
pure phenotype identity/differences; seeded inheritance; compatibility; transitive ancestry;
asexual and sexual births; reproduction conservation; fair shared-resource competition; stable
entity/genome snapshots; exactly-once deaths; deterministic event ordering; strict config identity;
multi-seed acceptance; artifact tamper/replay checks; and every retained Phase 0/1 test.

Phase 3 additions cover frozen version-1 identity, strict version-2 brain round trips, bounded brain
inheritance/mutation, controller prior/state shape and finite-value validation, deterministic bounded
transitions, exact three-factor update arithmetic, plasticity-off identity, learning-off history
independence, diagnostic projection, per-entity state isolation, action mapping order independence,
clean birth initialization, read-only population sensing, strict replay frame loading, immutable
viewer projection, final-frame identity, static Canvas export/CLI fidelity, strict learning-config
identity, matched procedural fixtures, diagnostic ordering/completeness, controller lifecycle,
deterministic learning artifacts, and tamper detection.
P3-T04 additions cover locked/disjoint seed partitions, strict suite identity, exact condition
matching, deterministic paired bootstrap intervals, honest failed-gate reporting, child-manifest
binding, full-suite replay, and tamper rejection.
P3-T05 additions cover the widened bounded rate, deterministic causal action comparison,
development-only partition enforcement, exact off/zero control identity, confirmatory authorization,
future-suite preregistration without execution, full child replay, and tamper rejection.
P3-T06 additions cover exact neutral-bias construction, per-channel binary logit margins, stored
margin-analysis replay, preserved off/zero identity, and blocked confirmation after a failed
development screen.
P3-T07 additions cover exact mixed-activation trace arithmetic, schema-v1 canonical identity,
schema-v2 rule round trips, matched legacy-rule ablation, semantic/off/zero lifecycle, all retained
Phase 3 replay artifacts, and blocked confirmation under unchanged criteria.
P3-T08 additions cover canonical survival-gate identity, evidence/config binding, strict seed
partitions, deterministic authorization CIs, extinction criteria, explicit birth/descendant
reporting, honest unauthorized fixtures, authorization replay, and tamper rejection.
P3-T09 additions cover exact preregistration enforcement, all four confirmatory controls, held-out
child replay, paired survival statistics, off/zero identity, explicit descendant outcomes, honest
failed-gate persistence, and summary tamper rejection.
P3-T10 additions cover a strict ten-seed development bank, consumed-seed rejection, exact bounded
rate set, deterministic lowest-qualified selection and no-candidate reporting, rate-by-seed outcome
matrices, exact off/zero identity, all 90 child replays, summary tamper rejection, and a fresh
evidence-bound held-out preregistration that cannot be written before a candidate qualifies.
P3-T11 additions cover exclusive evidence-source selection, exact robustness authorization/config
binding, all four frozen confirmation controls, complete child replay, honest pass persistence, and
unchanged statistical predicates. Viewer additions cover strict learning-config dispatch, immutable
Phase 3 frame projection, browser playback/final-state visual QA, and clean browser logs.
P4-T01 additions cover strict plant config identity, no-input/no-growth, capacity and input-limited
growth, explicit uptake, fair simultaneous consumption, energy/lifecycle accounting, default-off
historical identity, detached snapshot projection, invalid mixed food-source rejection, and a
plant-enabled benchmark. Production-code strict type checking reports zero errors. All 186 retained
replays re-simulated byte-for-byte: 1 no-op, 1 sandbox, 6 evolution, and 178 learning runs.
The current desktop shell did not expose `uv` on `PATH`, so the locked existing `.venv` executables
were used directly for this session's checks; the repository lockfile was not changed.

Measured local benchmarks on 2026-07-15:

```powershell
python -m uv run python -m worm_world.benchmark --mode sandbox --steps 100000
# 100000 steps in 1.0305192999076098 s; 97038.45431033208 steps/s

python -m uv run python -m worm_world.benchmark --mode population --steps 1000
# 1000 steps with 64 organisms in 1.8505469999508932 s; 540.3807631076305 world steps/s

python -m uv run python -m worm_world.benchmark --mode plants --steps 1000
# 1000 plant-enabled steps with 64 organisms in 1.739423600025475 s;
# 574.9030885779372 world steps/s
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
11. Phase 3 experiment events are resequenced after composing controller diagnostics with
    authoritative world events. This preserves a single deterministic total order without giving
    the controller authority over world state. Realized procedural inputs are stored in config.
12. Phase 3 evaluation uses development seeds only for mechanism work. Once a held-out seed is run,
    it remains reported evidence and cannot be reused for tuning. Gate thresholds and bootstrap
    settings are serialized before evaluation; a failed gate is a valid engineering outcome.
13. Plasticity rate remains genome encoded and inherited, but its allowed upper bound is `1.0` after
    development diagnostics showed that the prior `0.1` bound changed continuous motion while
    almost never crossing discrete action thresholds. Learned per-synapse deltas remain clipped to
    `[-2, 2]`, lifetime-only, and excluded from genomes and snapshots.
14. Neutral binary action priors mean a zero inherited output bias, not a prescribed action. The
    failed centered-bias candidate is retained rather than selected: it suppressed reproduction
    divergence and did not improve any population outcome.
15. Eligibility rule `action_activation` uses each controller channel's actual activation. It does
    not change the homeostatic neuromodulator or introduce a reward. The rule is schema-v2 and
    independently ablatable; schema-v1 remains `legacy_tanh` for exact historical replay.
16. The Phase 3 confirmatory outcome is viable final population, with extinction and energy as
    supporting measures. This protocol change is versioned and made before fresh seeds execute.
    Births and surviving descendants remain reported; they are not converted into rewards or hidden
    objectives, and evolutionary claims still require descendants.
17. Confirmatory thresholds are hard gates, not suggestions. A positive mean/CI does not compensate
    for failing the frozen every-seed win or zero-learning-extinction criteria. Consumed seeds
    `301`–`305` remain evidence and cannot be used for subsequent tuning.
18. The P3-T10 candidate rule is deterministic and conservative: a rate qualifies only with a
    strictly positive final-population difference, no learning-on extinction, and exact off/zero
    identity on every development seed; the lowest qualifying rate is selected. Rates `0.25`,
    `0.5`, and `1.0` all qualified, so `0.25` is frozen for confirmation without selecting on a
    held-out result.
19. Phase 3 passed on the preregistered lifetime-survival predicate. This authorizes ecology work
    but does not establish learning-enhanced reproductive success: zero descendants survived the
    confirmation horizon. Phase 4 population-persistence claims must require actual replacement of
    founders by surviving descendants rather than treating founder survival as stable ecology.
20. The replay viewer may parse both evolution and lifetime-learning configs only through their
    explicit stored experiment type. Its frame inputs remain immutable saved snapshots; browser
    playback, inspection, and visual QA cannot advance or influence the simulator.
21. Plant dynamics are world-owned, fixed-step, and opt-in. Disabled plant configuration is not
    serialized into historical experiment types and therefore cannot change retained config IDs,
    events, snapshots, or replay bytes.
22. An enabled plant patch is the sole food pool for that population world. It exposes biomass
    through the existing sensing/eating interface and fair allocator; combining it with legacy
    static food is rejected until a future version defines multiple-patch sensing and allocation.

## Known blockers and limitations

- No Git remote is configured, and GitHub CLI is not installed. This does not affect local replay.
- The retained acceptance suite isolates two metabolism genotypes in a deliberately small fixed
  world. It establishes the Phase 2 inheritance gate but is not evidence of open-ended evolution,
  speciation, learning, or ecological stability.
- Resource patches remain finite point fields on flat 2.5D terrain. Richer resource dynamics and
  ecology remain Phase 4 work. P4-T01 plants grow from finite local stores with no replenishment,
  decay, recycling, light cycle, or seasonal forcing, so persistence is not yet expected.
- The Phase 2 fixed action protocol remains an experiment input; Phase 3 separately established a
  held-out lifetime-survival advantage for the autonomous recurrent/plastic controller. Plasticity
  currently updates only hidden-to-output synapses; broader learning or emergence claims remain
  unwarranted without separate evidence.
- Earlier held-out seeds `201`–`205` and `301`–`305` are consumed evidence and must never be reused
  for tuning or a later gate. Their failures remain retained history, not candidate inputs.
- Development and confirmatory surviving-descendant counts remain zero, including all 30 P3-T10
  learning-on rate/seed conditions. Current evidence is a lifetime-survival effect only and cannot
  support a learning-enhanced reproductive/evolutionary-success claim.
- The first survival confirmation failed because seed 304 extinguished every condition. The other
  four seeds strongly favored learning-on, but thresholds forbid a phase advance. Seeds `301`–`305`
  are consumed and must not inform mechanism tuning beyond this recorded failure classification.
- Rate `0.25` passed the frozen held-out lifetime-survival gate on seeds `501`–`505`. Those seeds are
  now consumed evidence and must not be reused for Phase 4 tuning.
- The Canvas viewer is replay-only: it has no live streaming, terrain height, dynamic ecology, or
  materials. Those require backward-compatible later viewer schemas. Automated direct-file visual
  QA was unavailable because the in-app browser disallows `file:` navigation; exporter fidelity,
  JavaScript syntax, and browser-facing assets were verified, but a manual browser appearance check
  remains advisable.

## Exact next ticket

**P4-T02 — deterministic detritus and nutrient recycling**

Add one independently configurable world-owned detritus pool that receives the documented physical
biomass fraction of newly dead organisms and converts it into the P4-T01 plant patch's local nutrient
store at a bounded fixed-step decay rate. Default it off so every Phase 1–P4-T01 configuration and
replay remains byte-identical. Do not create energy, revive organisms, add scavenger behavior,
controller inputs, rewards, fitness scores, arbitrary respawn, seasons, or viewer authority. Record
death-to-detritus transfer, decay loss, and nutrient return so the full lifecycle is auditable. Add
deterministic tests for no-death/no-detritus, exactly-once death transfer, bounded decay, nutrient
return, mass/energy accounting, simultaneous deaths, strict config identity, default-off replay,
snapshot projection, and benchmark comparison. Run formatting, lint, strict types, the full suite,
pre-commit validation, population/ecology benchmarks, and every retained replay; update this handoff
without claiming a stable ecology until descendant replacement passes a later multi-seed gate.
