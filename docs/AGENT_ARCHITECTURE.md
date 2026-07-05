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
