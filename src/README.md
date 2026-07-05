# src/

**Status: placeholder — populated in later steps.**

This folder will hold the agent implementation. No application code exists yet;
Step 1 is specification only.

Planned contents:

- **Risk tools** (Step 4) — a deterministic EuroSCORE II–style risk calculator used
  as the scoring backbone. Coefficients/logic must be verified against the published
  source before implementation (see the `[TO VERIFY ...]` markers in `docs/SPEC.md`).
- **Specialist agents** (Step 5–6) — cardiac, endocrine, and pulmonary reasoners that
  each propose optimizations within their domain.
- **Conflict resolution** (Step 7) — logic that reconciles competing recommendations
  between specialties.
- **Planner** (Step 8) — sequences a pre-op optimization plan, constrained to locally
  available capabilities.
- **Loop / orchestration** (Step 9) — the control loop tying tools, agents, and the
  planner together.

See `docs/SPEC.md` for the operability model and scope every module must respect.
