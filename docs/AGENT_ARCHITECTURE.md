# Specialist Agent Architecture (Step 4)

This document records the architecture decision for the three specialist reasoning
agents introduced in Step 4. It is the contract the Step-5 conflict resolver builds on.

## Position in the pipeline

```
vignette ──▶ risk_calculator (Step 3)  ─── owns ALL EuroSCORE math
        └──▶ decomposer (Step 3) ──▶ DecompositionResult
                                        │
                                        ▼
                    ┌───────────────────────────────────────┐
                    │  run_specialists.run_all_specialists   │  (Step 4)
                    │   ├─ cardiac_agent   (parallel)        │
                    │   ├─ endocrine_agent (parallel)        │
                    │   └─ pulmonary_agent (parallel)        │
                    └───────────────────────────────────────┘
                                        │
                                        ▼
              dict[specialty -> SpecialistRecommendation]
                                        │
                                        ▼
                     conflict resolver  (Step 5 — NOT here)
```

## Core decisions

1. **Domain isolation.** Each specialist operates on its **own lever domain only**:
   - **cardiac** → `mobility` (`poor_mobility`), `heart_failure_symptoms` (`nyha_class`),
     `critical_preop_stabilization` (`critical_preoperative_state`) — the
     "modifiable-but-cardiac" levers from the SPEC §f reconciliation (Step 3).
   - **endocrine** → `hba1c` only. (`diabetes_on_insulin` is a **fixed** EuroSCORE input,
     not a lever — the endocrine agent flags it, it does not optimize it.)
   - **pulmonary** → `asthma_control` (`chronic_lung_disease`), `smoking_status`.

2. **Parallel, not sequential.** Agents **do not see each other's output**. They are run
   concurrently (`ThreadPoolExecutor`) and each is a pure function of
   `(vignette, decomposition, capability_profile_path)`. This is safe because agents share
   no mutable state and perform read-only feasibility lookups.

3. **No EuroSCORE math in agents.** Agents propose optimizations only. All score
   computation stays in `src/risk_calculator.py` (Step 3). An agent may name the
   `euroscore_field` a lever maps to, but never computes a mortality number.

4. **Feasibility filtering.** Every `Recommendation` carries a `FeasibilityResult` from
   `src/feasibility.py`, resolved at the patient's current tier (`vignette.location_tier`).
   When an intervention needs several capabilities, the recommendation's feasibility is the
   **most-constraining** (governing) one, and `tier_required` follows it. Recommendations
   are annotated with feasibility, not silently dropped.

5. **Conflicts are deferred to Step 5.** Agents deliberately do **not** reconcile
   conflicting proposals. `Recommendation.conflicts_with` is always an empty list here;
   Step 5 fills it. Cross-specialty concerns an agent *observes but cannot resolve* go into
   the free-text `warnings` field (e.g. the pulmonary agent's "ICS dose increase will
   worsen glycemic control — endocrine coordination REQUIRED"). Warnings are observations,
   not resolutions.

## Data types

```python
@dataclass
class Recommendation:
    lever: str                 # SCHEMA.md §1.2 lever name
    action: str                # plain-text intervention
    target: str                # optimized state, e.g. "chronic_lung_disease: false"
    euroscore_field: str | None # EuroSCORE field this changes, or None (Option-B levers)
    tier_required: str         # "local" | "tertiary" (derived from feasibility)
    feasibility: FeasibilityResult
    weeks_estimate: int        # integer weeks (sourced or [TO VERIFY])
    conflicts_with: list       # [] here; Step 5 fills
    evidence_note: str         # one-sentence grounding or [TO VERIFY]

@dataclass
class SpecialistRecommendation:
    specialty: str                       # "cardiac" | "endocrine" | "pulmonary"
    recommendations: list[Recommendation]
    warnings: list[str]                  # cross-specialty concerns observed, not resolved
    out_of_scope_flags: list[str]        # factors noticed but this specialist cannot handle
```

## Governing-feasibility rule

For a recommendation needing capabilities `C1..Cn`, we take the most-constraining status:

```
UNAVAILABLE > PARTIAL_TERTIARY > NEEDS_TERTIARY > PARTIAL_LOCAL > LOCAL
```

`tier_required` = `"tertiary"` if the governing status is NEEDS_TERTIARY /
PARTIAL_TERTIARY / UNAVAILABLE, else `"local"`. (Rationale: if *any* required capability
forces tertiary, the whole intervention needs tertiary; "partial" is treated as more
constraining than a clean availability at the same tier because it must be verified.)

## Error handling

`run_all_specialists` catches each agent's exception, logs it with the specialty and
vignette id, and **re-raises with context** (never swallows). A malformed vignette or an
unknown capability surfaces loudly.

## What Step 5 will need from this (open items)

- A conflict model consuming `warnings` + overlapping `euroscore_field` / sequencing
  constraints to populate `conflicts_with`.
- A **sequencing** decision: several recommendations have `weeks_estimate` and implicit
  ordering constraints (e.g. "stabilize glycemia *before* ICS step-up"). Step 4 records the
  concern in warnings; Step 5 must decide ordering.
- A policy for recommendations whose governing feasibility is `PARTIAL_*` or `UNAVAILABLE`
  (escalate, substitute, or flag as blocking).

---

# Step 5: conflict detection + resolution + time-phased sequencing

The `src/planner/` package consumes the specialists' output (the dict from
`run_all_specialists`) and produces a time-phased `OptimizationPlan`. It is **fully
deterministic and rule-based — no LLM**. It does **not** recompute risk (Step 6), does
**not** hard-filter on feasibility (Step 6), and does **not** render prose (Step 8).

## Two detection signals (and only two) — `conflicts.py`

`detect_conflicts(specialist_outputs) -> list[Conflict]`:

1. **`euroscore_field_overlap`** — two recommendations from *different* specialties target
   the same EuroSCORE field → `resource_overlap` (severity `blocking`). The agents own
   disjoint fields, so this is normally empty; implemented for correctness.
2. **`agent_warning`** — a recommendation carries a **structured `cross_specialty_flag`**
   (e.g. `{"interacts_with": "endocrine", "target_lever": "hba1c",
   "mechanism": "steroid_hyperglycemia", "direction": "worsens"}`) that names a partner
   specialty + lever actually present in the plan → `clinical_interaction` (severity
   `ordering`). Detection matches these **structured markers**, never free-text — the
   agents were extended (Step 5) to attach the flag alongside the human-readable warning.

The two concrete interactions caught: **ICS↔glycemia** (pulmonary `asthma_control` ×
endocrine `hba1c`, mechanism `steroid_hyperglycemia`) and **beta-blocker↔asthma** (cardiac
`heart_failure_symptoms` × pulmonary `asthma_control`, mechanism `betablocker_bronchospasm`).

## Rule registry + resolver — `resolution_rules.py`

A registry of named `Rule`s, each with `applies_to` (kind + mechanism), an `ordering`
(`(first_lever, second_lever)` or `"parallel_with_monitoring"`), `rationale`, `source`
(citation or `[TO VERIFY]`), and `monitoring_note`:

- **`RULE_GLYCEMIA_BEFORE_ICS`** — glycemic optimization first, then ICS step-up with
  glucose monitoring. Ordering, not "drop one".
- **`RULE_BETABLOCKER_ASTHMA`** — establish pulmonary control before beta-blocker
  titration; cardioselective agent only with pulmonology sign-off; **conditional-blocking
  on the beta-blocker lever only** if asthma stays uncontrolled (the rest of the
  heart-failure plan proceeds). Modeled as `ordering` (asthma before heart_failure).

`resolve_conflicts(...) -> ResolutionResult` matches each conflict to a rule. **A conflict
with no matching rule is never guessed** — it is escalated as
`"UNRESOLVED — human review required"` and carried onto the plan.

## Sequencing algorithm — `sequencer.py`

`build_sequence(vignette, specialist_outputs, resolutions) -> OptimizationPlan`:

- Ordering edges come only from resolutions whose *both* levers are present. Levers are
  **longest-path layered** into phases: unconstrained levers share a phase (concurrent);
  a lever with predecessors lands one phase later.
- `duration_weeks` per phase = **max `weeks_estimate`** of its (concurrent) interventions.
  Total plan duration = sum of phase durations (phases are sequential).
- **Surgical-urgency constraint**: for a non-`elective` `urgency`, if total duration
  exceeds `config.MAX_URGENT_OPTIMIZATION_WEEKS` (default 4, `[TO VERIFY]`), emit an
  `urgency_warning` naming the phases that would overrun the budget — **phases are never
  silently dropped**, the tension is flagged for human review.
- The plan carries `unresolved_conflicts`, a `rationale_trace`, `total_duration_weeks`,
  and (where relevant) `urgency_warning`. It makes **no operability verdict** — that is
  Step 6.

## Worked example (grandmother, SYNTH-006, elective)

Conflicts: ICS↔glycemia and beta-blocker↔asthma (both resolved). Resulting phases:

| Phase | Weeks | Interventions | Why |
|-------|-------|---------------|-----|
| 1 | 12 | `hba1c`, `mobility` (concurrent) | glycemia has no predecessor; mobility unconstrained |
| 2 | 8 | `asthma_control` | after glycemia (RULE_GLYCEMIA_BEFORE_ICS) |
| 3 | 8 | `heart_failure_symptoms` | after pulmonary control (RULE_BETABLOCKER_ASTHMA) |

Total 28 weeks; elective → no urgency warning; glycemia (P1) strictly precedes ICS (P2).

---

# Step 6: iterative re-assessment loop (the agentic core)

`src/loop/` turns the static Step-5 plan into an agent: it simulates the patient advancing
through the plan phase by phase, recomputes EuroSCORE II after each phase (reusing
`src/risk_calculator.py` **exactly** — no new risk math), and **branches** on the result.
Deterministic, no LLM.

## Simulation model — `simulation.py`

`advance_phase(current_inputs, phase) -> (updated_inputs, PhaseEffect)`. For each
intervention in the phase: a **euroscore_visible** lever flips its mapped field to the
optimized value (shared `src/optimized_state.py` convention); a **needs_risk_modifier**
lever is recorded in `PhaseEffect.optimized_but_invisible` and **does not change the
inputs** (Option B deferred — invisible levers contribute 0 to the recomputed score).
`[TO VERIFY / MODELING ASSUMPTION — the loop assumes each phase reaches its lever target.]`

## Branching algorithm — `reassessment_loop.py`

`run_reassessment_loop(vignette) -> LoopResult`:

1. Compute baseline EuroSCORE II (iteration 0).
2. Build the plan (decompose → specialists → conflicts → resolve → sequence).
3. **If baseline `< OPERABILITY_THRESHOLD` → `OPERABLE_AT_BASELINE`** and stop — even if a
   (redundant, often score-invisible) plan exists. This short-circuit prevents mislabeling
   an already-operable patient as "operable *after* optimization."
4. Else if the plan has no phases → `FIXED_HIGH_RISK` (declined, nothing to optimize).
5. Else iterate phases in order. After each phase, recompute the score and branch:
   - score `< threshold` → `OPERABLE_AFTER_OPTIMIZATION`, record the **crossing phase**, and
     **early-stop** — remaining phases are listed in `remaining_phases_not_required` (not
     applied to the score; "not required for operability, may still be clinically advisable").
   - else continue.
6. All phases applied and still `>= threshold` → `OPTIMIZED_BUT_STILL_HIGH_RISK` (the
   honesty branch: real optimization done, still declined — e.g. SYNTH-008).

### Four terminal states + one orthogonal flag

`OPERABLE_AT_BASELINE`, `OPERABLE_AFTER_OPTIMIZATION`, `OPTIMIZED_BUT_STILL_HIGH_RISK`,
`FIXED_HIGH_RISK`. **`TIME_INFEASIBLE`** is an *orthogonal* boolean, not a state: for a
non-elective urgency, if the weeks to reach the terminal outcome exceed
`MAX_URGENT_OPTIMIZATION_WEEKS`, the flag is set. A case can be
`OPERABLE_AFTER_OPTIMIZATION` **and** `time_infeasible` — the fix would work but not within
the surgical deadline. These are never collapsed.

### Routing hint (light; the hard gate is Step 7)

On `OPERABLE_*` states the loop reads the `cabg` capability and attaches a `routing_hint`
(CABG routes to tertiary). This is a hint only — Step 7 owns the resource gate over *every*
step.

## End-to-end mapping (all 18 vignettes)

| design_intent | terminal state |
|---------------|----------------|
| operable_at_baseline (001–005) | `OPERABLE_AT_BASELINE` |
| reversible_with_optimization (006,007,009–013) | `OPERABLE_AFTER_OPTIMIZATION` |
| fixed_high_risk **with** an agent-addressable lever (008, 015) | `OPTIMIZED_BUT_STILL_HIGH_RISK` |
| fixed_high_risk **no** actionable lever (014,016,017,018) | `FIXED_HIGH_RISK` |

SYNTH-008 additionally carries `time_infeasible=True`. SYNTH-015 is fixed_high_risk with an
invisible-only `hba1c` lever: optimization is attempted but cannot move the score →
`OPTIMIZED_BUT_STILL_HIGH_RISK` (honest).

---

# Step 7: access gate (the accessibility core)

`src/gate/` applies the two-tier capability profile as a **hard gate** over the whole
pathway the loop produced, rewriting every step as **"do locally in Sihor" (Tier 1)** vs
**"trip to Bhavnagar" (Tier 2)** vs **"access barrier"**. It reuses `src/feasibility.py`
exactly. It **annotates and flags but never overrules the clinical verdict and never
drops an intervention.**

## Tier routing — `tier_routing.py`

Each lever maps to its required `capability_id`(s) (`LEVER_CAPABILITIES`). An intervention
is gated on **all** of them, **most-restrictive-wins** (reusing `govern_feasibility` →
`check_feasibility`):

| feasibility status | routing |
|--------------------|---------|
| `LOCAL` | Do locally in Sihor (Tier 1) |
| `PARTIAL_LOCAL` | Likely local in Sihor, verify (Tier 1, flagged) |
| `NEEDS_TERTIARY` | Requires trip to Bhavnagar (Tier 2) |
| `PARTIAL_TERTIARY` | Likely Bhavnagar, verify (Tier 2, flagged) |
| `UNAVAILABLE` | **ACCESS BARRIER** — not available at either tier (flagged, not dropped) |

A capability_id absent from the profile raises (never guessed). "partial" is carried
through explicitly, never coerced to yes/no.

## Trip accounting — `trip_accounting.py`

Minimizing travel from Sihor is the story. `trip_count` = (distinct loop **phases** that
contain a tertiary intervention) + (1 for the CABG, always tertiary). **Batching
assumption `[TO VERIFY]`:** tertiary interventions in the *same* loop phase share one
trip. `access_barriers` = any `UNAVAILABLE` intervention across the whole pathway. If
`trip_count > config.MAX_TERTIARY_TRIPS` (default 3, `[TO VERIFY]`), the **`access_strain`**
flag fires — an access concern **orthogonal** to clinical risk, exactly like
`TIME_INFEASIBLE`.

## The gated pathway — `access_gate.py`

`apply_access_gate(loop_result) -> GatedPathway`, carrying: the loop's `terminal_state` and
`time_infeasible` **unchanged**; the **required-for-operability** routed pathway; the
**designed-but-not-required** routed remainder (early-stop tail), clearly separated; the
CABG surgical routing (→ Bhavnagar); `trip_count`, `access_barriers`, `access_strain`, and
an `access_summary` (local vs tertiary-trip vs barrier counts).

The honest coupling: a patient stays `OPERABLE_AFTER_OPTIMIZATION` even under
`access_strain` — the output then reads *"clinically reversible, but logistically strained:
N trips to Bhavnagar required."*

## Worked example (grandmother, SYNTH-006)

Required (crosses at phase 1): `hba1c` and `mobility` → **both local in Sihor** (partial,
flagged). Designed-not-required tail: `asthma_control`, `heart_failure_symptoms` → local.
CABG → **Bhavnagar**. Every optimization step's *delivery* is local; the trips are
specialist consults + the operation (see Step 8).

---

# Step 8: specialist-scarcity layer (Path B) + clinician output

## Part A — initiation-vs-delivery (honest scarcity)

`src/gate/intervention_capabilities.py` splits each intervention into **delivery** (the
labs/meds/monitoring that execute it day-to-day — local in Sihor) and an **oversight**
specialist (endocrinologist / pulmonologist / cardiologist) whose input is needed **once**
to initiate the plan. The honesty note: a "needs endocrinologist" signal is a **one-touch
consult** (a single Bhavnagar trip), **not** "the infrastructure to manage diabetes is
missing." This keeps the thesis intact — the gap is **coordination, not machines** — and
avoids dishonestly converting a consult into a permanent infrastructure barrier.

`tier_routing.py` now produces **two separate routings** per intervention
(`delivery_routing`, `oversight_routing`) plus an `access_description`, e.g. *"Glycemic
optimization — delivered locally in Sihor; requires one initial endocrinologist consult in
Bhavnagar to set the plan."* Oversight can be a `SPECIALIST ACCESS BARRIER` (no/no),
flagged not dropped.

`trip_accounting.py` counts distinct Bhavnagar trips with two batching assumptions
(`[TO VERIFY]`): **(1)** cardiac-domain tertiary work (cardiologist, cardiac_icu, CABG)
folds into the single tertiary cardiac episode — no extra trip; **(2)** non-cardiac
consults/deliveries in the same loop phase share a trip. Grandmother's honest
`trip_count = 3`: endocrinology consult (phase 1) + pulmonology consult (phase 2) + CABG;
**all delivery local**. `access_strain` fires (orthogonally) if trips exceed
`MAX_TERTIARY_TRIPS`. The gate never overrules the clinical verdict.

## Part B — clinician report + audit trail

`src/output/clinician_report.py` runs the full pipeline and assembles a serializable
`ClinicianReport`: header (synthetic + decision-support-only + clinician-responsible,
per SPEC §g); patient summary; plain-language verdict + flags; risk decomposition
(fixed / visible / invisible-to-score); the ordered optimization pathway with delivery +
oversight routing, monitoring notes, and applied conflict-resolution rules + rationale +
source; required-vs-designed separation; access summary; **confirmation flags** (every
step that needs specialist sign-off); **surfaced `[TO VERIFY]` markers** (never hidden);
and a full **audit trail** (baseline → each agent → each conflict+resolution+source → each
loop iteration → gate decisions).

`src/output/render.py` renders a sectioned plain-text/markdown document with a "pathway at
a glance" up top and the audit trail at the bottom. Every `[TO VERIFY]` value is rendered
visibly — the renderer never presents an unsourced clinical number as confirmed. Decision
support only; it never speaks to a patient or issues an autonomous instruction.
