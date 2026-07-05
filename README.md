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

## Repository layout

| Path | Contents |
|------|----------|
| [`docs/`](docs/) | **`SPEC.md`** — the specification and single source of truth (Step 1 deliverable). |
| [`data/`](data/) | *(future)* synthetic patient vignettes + local-capability profile. |
| [`src/`](src/) | *(future)* risk tools, specialist agents, planner, orchestration loop. |
| [`eval/`](eval/) | *(future)* rule-based evaluation harness. |

Start with [`docs/SPEC.md`](docs/SPEC.md) for clinical scope, the care-tier model, the
operative risk model, and the assumptions/limitations that govern every later step.
