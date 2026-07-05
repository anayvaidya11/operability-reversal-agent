# data/

**Status: placeholder — populated in later steps.**

This folder will hold the *inputs* the agent reasons over. Nothing here is real
patient data; everything is synthetic and illustrative.

Planned contents:

- **Synthetic patient vignettes** (Step 3+) — hand-authored, de-identified,
  fictional multimorbid patients matching the scope in [`docs/SPEC.md`](../docs/SPEC.md)
  (coronary artery disease + type 2 diabetes + asthma). Each vignette carries the
  variables needed to compute a EuroSCORE II–style risk estimate plus modifiable-lever
  values (e.g. HbA1c, smoking status).
- **Local-capability profile** (Step 2) — a structured description of what the
  *Local* tier (Sihor CHC / small private hospitals) and the *Tertiary* tier
  (Bhavnagar) can and cannot do. This is the machine-readable version of the
  care-tier model defined in `docs/SPEC.md`.

See `docs/SPEC.md` for the clinical scope, care-tier model, and data assumptions
that constrain what goes here.
