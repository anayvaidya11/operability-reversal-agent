# eval/

**Status: placeholder — populated in later steps.**

This folder will hold the evaluation harness. Nothing here yet.

Planned contents:

- **Rule-based evaluation harness** (Step 10) — deterministic checks that run the
  agent over the synthetic vignettes in [`data/`](../data/) and verify properties such
  as: only in-scope specialties are invoked; recommended interventions are available
  at the correct care tier; the plan targets *modifiable* levers and not *fixed* ones;
  and predicted risk moves in the expected direction after optimization.

The harness is intentionally rule-based (not another model) so that "did the agent do
the right thing?" stays auditable and honest, in keeping with the transparency goals in
`docs/SPEC.md`.
