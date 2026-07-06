# WHERE IS IT? — a plain-language map of this repo

You are looking for "where does X happen?" This page maps the thing someone would ask
about (left) to the exact file and function where it lives (right). Everything below was
read directly from the code; the names are real.

A quick mental model of the whole pipeline, in order:

1. **Patients** live in a data file (`data/vignettes.json`).
2. A **risk calculator** scores each patient (`src/risk_calculator.py`).
3. **Three specialist agents** each suggest fixes (`src/agents/`).
4. A **conflict resolver + planner** orders those fixes into phases (`src/planner/`).
5. A **loop** applies the plan step by step, re-scores after each step, and decides the
   outcome (`src/loop/`).
6. An **access gate** rewrites every step as "do it in Sihor" vs "trip to Bhavnagar"
   (`src/gate/`).
7. An **output builder** turns all of it into a clinician-readable report
   (`src/output/`).
8. An **evaluation harness** checks the whole thing behaves correctly (`eval/`).

---

## The 19 synthetic patients

| You would ask... | File | What's in it | Point at |
|---|---|---|---|
| "Where are the fake patients?" | `data/vignettes.json` | All 19 synthetic patients (their heart-surgery risk inputs, their fixable problems, and a design label). | Patient ids `SYNTH-001` through `SYNTH-019` |
| "The grandmother case?" | `data/vignettes.json` | The motivating patient: elderly woman from Sihor, ~90% blocked artery, diabetes, asthma. | Id `SYNTH-006` (search the file for `"SYNTH-006"`; `grandmother_analog` is `true`) |
| "The honest-decline case?" | `data/vignettes.json` | Patient who improves a lot with optimization but still stays too high-risk, and would not fit the surgical time window. | Id `SYNTH-008` |
| "The access-blocked case?" | `data/vignettes.json` | Patient who is fixable on paper, but a required step is not available at either hospital. | Id `SYNTH-019` (see its `access_dependency` field) |
| "What do those patient fields mean?" | `data/SCHEMA.md` | Plain-English dictionary of every field in the patient file. | — |
| "How do you know the patients are valid?" | `data/validate.py` | Checks the patient file is well-formed AND that each patient's label matches its real computed score. | Run: `python3 data/validate.py` |

---

## The 114 checks (the evaluation harness)

The number 114 is **6 checks x 19 patients**.

| You would ask... | File | What's in it | Point at |
|---|---|---|---|
| "Where did the 114 come from?" | `eval/harness.py` | Runs six checks on every patient. `evaluate_vignette` does the six checks for one patient; `evaluate_all` runs it across all 19. Six x nineteen = 114. | `evaluate_vignette(...)`, `evaluate_all(...)` |
| "What are the 6 checks?" | `eval/harness.py` | The six check names, each with a pass/fail and a reason. | `guideline_concordance`, `conflict_resolution_correctness`, `resource_feasibility`, `operability_threshold_correctness`, `thesis_property_delivery_local`, `honesty_properties` |
| "Where's the metrics summary / slide numbers?" | `eval/metrics_report.py` | Turns the check results into a summary (pass rates, outcome tally, trip counts). | `build_metrics(...)`, `render_metrics_text(...)` |
| "How do I prove all 114 pass?" | `tests/test_eval.py` | The test that fails loudly if any check fails on any patient. | `test_all_checks_pass_over_all_vignettes` |
| "How do I run the checks?" | — | Run the eval test. | `.venv/bin/python -m pytest tests/test_eval.py -q` |
| "How do I print the metrics table?" | — | One-line command. | `.venv/bin/python -c "from eval import evaluate_all, build_metrics, render_metrics_text; print(render_metrics_text(build_metrics(evaluate_all())))"` |

---

## The risk model (EuroSCORE II)

| You would ask... | File | What's in it | Point at |
|---|---|---|---|
| "Where's the actual risk math?" | `src/risk_calculator.py` | Computes the predicted surgical-death percentage for a patient. | `compute_euroscore_ii(...)`; the raw linear step is `euroscore_inputs_to_linear_predictor(...)` |
| "Where are the published coefficients?" | `src/euroscore_ii_coefficients.py` | Only the real EuroSCORE II numbers (from Nashef et al. 2012), each with a source note. No math, just the constants. | The intercept `CONSTANT` (= `CALCULATOR_CONSTANT`, -4.789594); the individual `BETA_*` values |
| "Fixed vs fixable factors?" | `src/decomposer.py` | Splits a patient's risk into things you cannot change (age, anatomy) vs things you can (asthma control, mobility, blood sugar). | `decompose(...)` |
| "What does 'fully optimized' mean?" | `src/optimized_state.py` | The single rule for what each fixable factor looks like once treated. | `optimized_inputs(...)` |

---

## The operability threshold (the 6% line)

| You would ask... | File | What's in it | Point at |
|---|---|---|---|
| "Where do you decide operable vs not?" | `src/config.py` | The 6% cutoff and its overrides live here. Above 6% predicted mortality = "declined"; below = "potentially operable". | `DEFAULT_OPERABILITY_THRESHOLD = 6.0`; read it via `get_operability_threshold(...)` |
| "Where are the other tunable numbers?" | `src/config.py` | The urgent-surgery time budget and the max trips-to-Bhavnagar budget. | `MAX_URGENT_OPTIMIZATION_WEEKS = 4`, `MAX_TERTIARY_TRIPS = 3` |

---

## The three specialist agents

Each agent is one file. Each has a `run(...)` function that looks at the patient and
proposes fixes only in its own area.

| You would ask... | File | What's in it | Point at |
|---|---|---|---|
| "The heart specialist?" | `src/agents/cardiac_agent.py` | Proposes mobility (prehab), heart-failure medicine, and stabilization. | `run(...)`, `SPECIALTY = "cardiac"` |
| "The diabetes specialist?" | `src/agents/endocrine_agent.py` | Proposes blood-sugar (HbA1c) optimization. | `run(...)`, `SPECIALTY = "endocrine"` |
| "The lung specialist?" | `src/agents/pulmonary_agent.py` | Proposes asthma control and smoking cessation. | `run(...)`, `SPECIALTY = "pulmonary"` |
| "Where are all three run together?" | `src/agents/run_specialists.py` | Runs the three agents and collects their suggestions. | `run_all_specialists(...)` |

---

## The conflict resolver and the sequencing planner

| You would ask... | File | What's in it | Point at |
|---|---|---|---|
| "Where do you spot conflicts?" | `src/planner/conflicts.py` | Finds where two specialists' fixes clash (for example, an asthma steroid raising blood sugar). | `detect_conflicts(...)` |
| "The steroid vs blood-sugar rule?" | `src/planner/resolution_rules.py` | The named rules that say which fix goes first. The steroid/blood-sugar one says: get blood sugar under control first, then step up the asthma steroid. | `RULE_GLYCEMIA_BEFORE_ICS` (steroid vs blood sugar); `RULE_BETABLOCKER_ASTHMA` (heart-rate drug vs asthma); resolver `resolve_conflicts(...)` |
| "Where do you order the plan into steps?" | `src/planner/sequencer.py` | Turns the fixes plus the ordering rules into time-phased steps. | `build_sequence(...)` |

---

## The iterative re-assessment loop (the "agentic core")

| You would ask... | File | What's in it | Point at |
|---|---|---|---|
| "The core loop that re-checks risk?" | `src/loop/reassessment_loop.py` | Applies the plan one phase at a time, re-scores after each phase, and stops early the moment the patient crosses below 6%. Picks one of four outcomes. | `run_reassessment_loop(...)`; the four outcomes are in `class TerminalState` |
| "How does applying one step work?" | `src/loop/simulation.py` | Applies a single phase to the patient's numbers (fixable-but-visible factors move the score; invisible ones are tracked but do not). | `advance_phase(...)` |

The four outcomes (in `TerminalState`): `OPERABLE_AT_BASELINE`, `OPERABLE_AFTER_OPTIMIZATION`,
`OPTIMIZED_BUT_STILL_HIGH_RISK`, `FIXED_HIGH_RISK`.

---

## The access gate (Sihor vs Bhavnagar) and specialist scarcity

| You would ask... | File | What's in it | Point at |
|---|---|---|---|
| "Where do you check what's available in Sihor?" | `src/gate/access_gate.py` | Rewrites every step of the plan as "do it locally in Sihor", "one trip to Bhavnagar", or "not available anywhere (barrier)". | `apply_access_gate(...)` |
| "What does each hospital actually have?" | `data/capability_profile.json` | The list of what the local hospital (Sihor) and the tertiary hospital (Bhavnagar) can and cannot do. | Availability values `yes` / `no` / `partial` |
| "The raw availability lookup?" | `src/feasibility.py` | Looks up a single capability at a tier and says local / tertiary / unavailable. | `check_feasibility(...)` |
| "How is each step routed to a tier?" | `src/gate/tier_routing.py` | Turns availability into a routing decision for one step. | `route_intervention(...)` |
| "The specialist-scarcity honesty layer?" | `src/gate/intervention_capabilities.py` | Splits each step into local day-to-day delivery vs a one-time specialist consult, so "needs a specialist" is modeled as one trip, not missing infrastructure. | `INTERVENTION_CAPABILITIES` |
| "How are trips to Bhavnagar counted?" | `src/gate/trip_accounting.py` | Counts distinct trips, batching the ones that can share a visit. | `account_trips(...)` |

---

## The clinician-facing report (the output)

| You would ask... | File | What's in it | Point at |
|---|---|---|---|
| "What does the agent actually produce?" | `src/output/clinician_report.py` | Runs the whole pipeline and assembles a structured report: the verdict, the plan, the access routing, the confirmation flags, and a full audit trail. | `build_clinician_report(...)` |
| "The readable text version?" | `src/output/render.py` | Turns that report into a clean sectioned text document a clinician could read. | `render_report_text(...)` |

---

## The clinical sources (cited medicine vs assumptions)

| You would ask... | File | What's in it |
|---|---|---|
| "What's actually cited vs assumed?" | `docs/CLINICAL_SOURCES.md` | A table of every clinical claim, marked either CITED (with a real, locatable source) or MODELING ASSUMPTION (honestly labeled, needs clinician review). Nothing was invented. |

---

## The two pitch-deck charts

| You would ask... | File | What's in it | Point at |
|---|---|---|---|
| "The risk-descent chart (grandmother crossing the line)?" | `deck_assets/grandmother_risk_descent.png` | The image. | — |
| "The three-outcomes chart?" | `deck_assets/three_case_outcomes.png` | The image. | — |
| "What made the charts?" | `scripts/make_charts.py` | The script that pulls the real numbers from the pipeline and draws both charts. | Run: `.venv/bin/python scripts/make_charts.py` |

---

## Background documents (the "why")

| You would ask... | File |
|---|---|
| "The clinical specification / single source of truth?" | `docs/SPEC.md` |
| "How the pieces fit together, step by step?" | `docs/AGENT_ARCHITECTURE.md` |

---

## If they ask... (quick reference under pressure)

- **"Where did the 114 come from?"** -> `eval/harness.py`. Six checks (`evaluate_vignette`)
  times nineteen patients (`evaluate_all`) = 114. The six check names are the
  `CheckResult(...)` labels in that file.
- **"Where are the fake patients?"** -> `data/vignettes.json` (all 19; grandmother is
  `SYNTH-006`, honest-decline is `SYNTH-008`, access-blocked is `SYNTH-019`).
- **"Where's the actual risk math?"** -> `src/euroscore_ii_coefficients.py` holds the real
  published numbers; `src/risk_calculator.py` (`compute_euroscore_ii`) does the calculation.
- **"Where do you decide operable vs not?"** -> the 6% line is
  `DEFAULT_OPERABILITY_THRESHOLD` in `src/config.py`; the decision is made in
  `src/loop/reassessment_loop.py` (`run_reassessment_loop`).
- **"Where do you handle the steroid / blood-sugar conflict?"** -> detected in
  `src/planner/conflicts.py`; the rule is `RULE_GLYCEMIA_BEFORE_ICS` in
  `src/planner/resolution_rules.py` (do blood sugar first, then step up the steroid).
- **"Where do you check what's available in Sihor?"** -> `src/gate/access_gate.py`
  (`apply_access_gate`), reading `data/capability_profile.json`.
- **"Where's the report the agent produces?"** -> `src/output/clinician_report.py` builds it,
  `src/output/render.py` prints it.
- **"How do I run the tests?"** -> `.venv/bin/python -m pytest -q` (the whole suite, ~205
  tests). Just the 114 checks: `.venv/bin/python -m pytest tests/test_eval.py -q`.
- **"How do I run the data validator?"** -> `python3 data/validate.py` (add
  `--structure-only` to skip the score checks).
