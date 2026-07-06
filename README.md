# Operability Reversal Agent

The Operability Reversal Agent is a clinician-facing decision-support **proof-of-concept**
that targets an underserved gap: a multimorbid patient in an under-resourced area who has
already been **declined for surgery as "too risky."** Where existing tools predict surgical
risk or triage referrals, this project aims to *own the reversal pathway* — decomposing a
declined patient's operative risk into fixable vs. fixed factors, resolving conflicts between
specialties, and sequencing a pre-operative optimization plan constrained to what is actually
available locally. The motivating case is an elderly patient in Sihor (Bhavnagar district,
Gujarat, India) with severe coronary artery disease requiring CABG, plus type 2 diabetes and
asthma, for whom nearby tertiary cardiac capability exists but the coordination of pre-op
optimization does not.

> **This is an early-stage, non-validated humanitarian proof-of-concept.** It is built for
> accessibility research and demonstration only. It uses synthetic data, is **not** clinically
> validated, is **not** a medical device, and must **not** be used for real clinical decisions.

## Repo map (start here)

What the system does, in order, and which folder each step lives in:

1. **Patients** — 19 synthetic patients with their risk inputs → `data/vignettes.json`
2. **Risk score** — predicted surgical mortality from the real EuroSCORE II model →
   `src/risk_calculator.py` (numbers in `src/euroscore_ii_coefficients.py`)
3. **Split the risk** — fixed vs. fixable factors → `src/decomposer.py`
4. **Specialists** — heart, diabetes, and lung agents each propose fixes → `src/agents/`
5. **Resolve + plan** — settle conflicts and order the fixes into phases → `src/planner/`
6. **Loop** — apply the plan phase by phase, re-score, decide the outcome → `src/loop/`
7. **Access gate** — rewrite every step as "do it in Sihor" vs. "trip to Bhavnagar" →
   `src/gate/`
8. **Report** — assemble the clinician-facing output → `src/output/`
9. **Evaluate** — the rule-based checks (6 checks × 19 patients = 114) → `eval/`

The "operable vs. not" line (6%) is `DEFAULT_OPERABILITY_THRESHOLD` in `src/config.py`.

**Need the exact file for a specific feature?** See **[`WHERE_IS_IT.md`](WHERE_IS_IT.md)** — a
plain-language lookup from "the thing someone asks about" to "the file and function where it
lives," plus an "If they ask..." quick-reference.

## Repository layout

| Path | Contents |
|------|----------|
| [`docs/`](docs/) | **`SPEC.md`** — the specification and single source of truth (Step 1 deliverable). |
| [`data/`](data/) | *(future)* synthetic patient vignettes + local-capability profile. |
| [`src/`](src/) | *(future)* risk tools, specialist agents, planner, orchestration loop. |
| [`eval/`](eval/) | *(future)* rule-based evaluation harness. |

Start with [`docs/SPEC.md`](docs/SPEC.md) for clinical scope, the care-tier model, the
operative risk model, and the assumptions/limitations that govern every later step.
