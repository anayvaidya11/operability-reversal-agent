# src/

**Status: Step 3 complete — deterministic tool layer (no LLM).**

This folder holds the pure, deterministic, fully-unit-tested tool layer. No LLM calls,
no agent logic, no network at runtime. Deterministic in → deterministic out.

## Modules (Step 3)

| Module | Purpose |
|--------|---------|
| `euroscore_ii_coefficients.py` | Sourced EuroSCORE II constants ONLY (cites Nashef et al. 2012, Table 6). No logic, no magic numbers elsewhere import from here. |
| `risk_calculator.py` | `compute_euroscore_ii(inputs) -> %` and `euroscore_inputs_to_linear_predictor(inputs) -> y`. Validates all 18 fields; raises `EuroscoreInputError`. 100% line coverage. |
| `decomposer.py` | `decompose(vignette) -> DecompositionResult`: splits levers into `euroscore_visible` / `needs_risk_modifier` / `fixed`. |
| `feasibility.py` | `check_feasibility(action_id, tier) -> FeasibilityResult` against `data/capability_profile.json`. |
| `config.py` | `OPERABILITY_THRESHOLD` (default 8.0%, configurable) and the lever↔EuroSCORE-field mapping (single source of truth). |

Run the tests: `python -m pytest` (see `tests/`). Coverage on the calculator is 100%.

## The Option-A / Option-B decision (explicit)

Some modifiable levers map directly to EuroSCORE II inputs; others do not. We handle this
in two stages and are explicit about which is built:

### Option A — implemented now (Step 3)
Optimize the **euroscore_visible** levers — asthma control → `chronic_lung_disease`,
mobility → `poor_mobility`, heart-failure symptoms → `nyha_class`, critical-preop
stabilization → `critical_preoperative_state`. Improving any of these changes a real
EuroSCORE II input, so the predicted score moves **today**, with no invented mapping.
`decomposer.py` exposes exactly which field each visible lever flips, and
`test_threshold_sensitivity.py` demonstrates the score moving down the pathway.

### Option B — deferred (a later step), a *grounded* supplementary modifier layer
The **needs_risk_modifier** levers — HbA1c, anemia/hemoglobin, albumin, smoking,
blood pressure — are **invisible to EuroSCORE II**. In Step 3 they are tracked and
reported with **zero effect** on predicted mortality, each flagged
`MODIFIER_LAYER_NOT_YET_GROUNDED = True`. We deliberately do **not** invent a
lever→risk mapping. When Option B is built, it must be a **sourced** supplementary layer,
not a guess.

> **Intended grounding basis for Option B (named, not yet implemented):** the King Hussein
> Cancer Center / multidisciplinary pre-operative optimization evidence, under which
> un-optimized patients carried on the order of **~2.2× the odds of peri-operative
> complications** relative to optimized patients. This is the *intended* anchor for a
> supplementary modifier, recorded here so the grounding is chosen deliberately.
> **`[TO VERIFY — locate and cite the exact King Hussein / multidisciplinary optimization
> figure and its applicability before Option B uses any number]`**

## Step-3 finding → Step-4 resolution (threshold lowered 8.0% → 6.0%)

The Step-3 report found that with the real EuroSCORE II coefficients, isolated **elective**
CABG is genuinely low-risk, so the grandmother analog (SYNTH-006) baselines at **~7.38%** —
*below* the 8.0% proxy trialed in Step 3, defeating the reversal demo.

**Step 4 lowered the default `OPERABILITY_THRESHOLD` to 6.0%** (clinically grounded; see
`src/config.py` and `docs/SPEC.md §e`). At 6.0% the grandmother is correctly **declined at
baseline (7.38% ≥ 6.0%)** and becomes **potentially operable after visible-lever
optimization (3.72% < 6.0%)**.

Honest caveats that remain (surfaced, not hidden):
- **SYNTH-008** (~22.4% → ~7.45%): visible-lever optimization helps materially but is
  **insufficient** to clear 6.0% — reversal is not always achievable on EuroSCORE-visible
  levers alone.
- Several reversible vignettes (SYNTH-007/009/011/013) baseline at ~2–3%, i.e. below 6.0%,
  so under this proxy they read as "operable at baseline." Adding fixed burden to those
  vignettes remains a possible future data refinement (the data was not modified in Step 4).
See `tests/test_threshold_sensitivity.py` for the exact, pinned numbers.
