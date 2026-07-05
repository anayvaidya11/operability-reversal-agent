# data/SCHEMA.md — schema for Step 2 data artifacts

This document defines the JSON schema for the two Step 2 data files and records how
their field names map to **`docs/SPEC.md` v0.1**. It is the contract that
[`validate.py`](validate.py) enforces structurally.

> **Scope of validation.** `validate.py` checks *structure and field-name alignment
> only*. It performs **no** risk math, no clinical logic, and no coefficient handling
> — those belong to later steps.

---

## 1. Field-name provenance (alignment with SPEC.md)

`docs/SPEC.md` describes the EuroSCORE II inputs and modifiable levers in **prose**, not
as machine field names. Step 2 fixes a canonical snake_case name for each, listed below.
This mapping is the definition of "field names match SPEC.md" that `validate.py` enforces.

### 1.1 EuroSCORE II input fields (SPEC.md §d)

Every vignette's `euroscore_inputs` object MUST contain **exactly** these keys — no
more, no fewer.

| Canonical field | SPEC.md §d source term | Group | Type / allowed values |
|-----------------|------------------------|-------|-----------------------|
| `age` | Age | patient | integer (years) |
| `sex` | Sex | patient | `"male"` \| `"female"` |
| `renal_impairment` | Renal function / impairment | patient | `"normal"` \| `"moderate"` \| `"severe"` \| `"on_dialysis"` — `[TO VERIFY — exact EuroSCORE II creatinine-clearance bands]` |
| `extracardiac_arteriopathy` | Extracardiac arteriopathy | patient | boolean |
| `poor_mobility` | Poor mobility | patient | boolean |
| `previous_cardiac_surgery` | Previous cardiac surgery | patient | boolean |
| `chronic_lung_disease` | Chronic lung disease | patient | boolean |
| `active_endocarditis` | Active endocarditis | patient | boolean |
| `critical_preoperative_state` | Critical preoperative state | patient | boolean |
| `diabetes_on_insulin` | Diabetes on insulin | patient | boolean |
| `nyha_class` | NYHA functional class | cardiac | `"I"` \| `"II"` \| `"III"` \| `"IV"` |
| `ccs_class4_angina` | CCS class 4 angina | cardiac | boolean |
| `lv_function` | Left ventricular function / EF category | cardiac | `"good"` \| `"moderate"` \| `"poor"` — `[TO VERIFY — exact EuroSCORE II EF bands]` |
| `recent_mi` | Recent myocardial infarction | cardiac | boolean |
| `pulmonary_hypertension` | Pulmonary hypertension | cardiac | `"none"` \| `"moderate"` \| `"severe"` — `[TO VERIFY — exact EuroSCORE II PH bands]` |
| `urgency` | Urgency | operation | `"elective"` \| `"urgent"` \| `"emergency"` \| `"salvage"` |
| `weight_of_intervention` | Weight/complexity of the intervention | operation | `"isolated_cabg"` \| `"cabg_plus_other"` — `[TO VERIFY — exact EuroSCORE II categories]` |
| `thoracic_aorta_surgery` | Surgery on the thoracic aorta | operation | boolean |

> The categorical *encodings/thresholds* above are placeholders pending
> `[TO VERIFY against Nashef et al., EuroSCORE II, 2012]`. Step 2 fixes the field
> *names and value vocabulary*; Step 4 binds them to the published model.

### 1.2 Modifiable-lever names (SPEC.md §f, plus Step 2 coupling extension)

| Lever `lever` value | SPEC.md §f source term | Default coupling | EuroSCORE field |
|---------------------|------------------------|------------------|-----------------|
| `hba1c` | Glycemic control (HbA1c) | `needs_risk_modifier` | `null` |
| `asthma_control` | Pulmonary / asthma optimization | `euroscore_visible` | `chronic_lung_disease` |
| `smoking_status` | Smoking status | `needs_risk_modifier` | `null` |
| `anemia` | Anemia | `needs_risk_modifier` | `null` |
| `albumin` | Nutrition / albumin | `needs_risk_modifier` | `null` |
| `blood_pressure` | Blood pressure | `needs_risk_modifier` | `null` |
| `mobility` | *(Step 2 extension)* | `euroscore_visible` | `poor_mobility` |
| `heart_failure_symptoms` | *(Step 2 extension)* | `euroscore_visible` | `nyha_class` |
| `critical_preop_stabilization` | *(Step 2 extension)* | `euroscore_visible` | `critical_preoperative_state` |

> **Extension note.** The last three levers are **not** in SPEC.md §f's six-lever table.
> They are added in Step 2 to satisfy the coupling requirement (reversible cases need
> euroscore-visible burden). SPEC.md currently treats NYHA/cardiac factors as "largely
> fixed"; this must be reconciled.
> `[TO VERIFY — reconcile modifiable-lever set between SPEC.md section f and Step 2 vignettes]`

---

## 2. `vignettes.json`

Top-level object with two keys: `_meta` and `vignettes`.

### 2.1 `_meta` (object)

| Field | Type | Notes |
|-------|------|-------|
| `synthetic` | boolean | MUST be `true`. |
| `warning` | string | Human-readable synthetic-data warning. |
| `spec_source` | string | Reference to SPEC.md version. |
| `design_intent_values` | array of string | The three allowed `design_intent` labels. |
| `euroscore_input_fields` | array of string | The canonical EuroSCORE field list (§1.1). |
| `modifiable_euroscore_visible_fields` | array of string | EuroSCORE fields treated as modifiable. |
| `coupling_design_note` | string | Explains euroscore_visible vs needs_risk_modifier and the reversible-burden constraint. |
| `supplementary_modifier_flag` | string | Contains `[TO VERIFY — define grounding for non-EuroSCORE factors in Step 3]`. |
| `verify_flags` | array of string | All `[TO VERIFY]` items raised by this file. |

### 2.2 `vignettes` (array of vignette objects)

Each vignette object:

| Field | Type | Allowed values / notes |
|-------|------|------------------------|
| `id` | string | Unique, e.g. `"SYNTH-001"`. |
| `synthetic` | boolean | MUST be `true`. |
| `design_intent` | string | `"operable_at_baseline"` \| `"reversible_with_optimization"` \| `"fixed_high_risk"` \| `"reversible_but_access_blocked"`. |
| `grandmother_analog` | boolean | Exactly one vignette in the file is `true`. |
| `rationale` | string | Plain-language reason for the design_intent label. |
| `location_tier` | string | `"local"` \| `"tertiary"`. |
| `clinical_context` | object | Free-form narrative context (see below). |
| `access_dependency` | object | Optional (Step 9). A patient-specific capability a required intervention hinges on, used to create an honest ACCESS BARRIER. Fields: `lever` (which intervention), `capability_id` (the required capability), `note`. |
| `euroscore_inputs` | object | Keys MUST equal the canonical set in §1.1 exactly. |
| `modifiable_levers` | array | Zero or more lever objects (§2.3). |

**`design_intent` = `reversible_but_access_blocked`** (Step 9): clinically identical score
property to `reversible_with_optimization` (baseline ≥ threshold AND optimized-visible <
threshold), but the pathway is blocked on ACCESS grounds — a required intervention depends
on a capability unavailable at both tiers (via `access_dependency`). The access barrier is a
**gate** outcome, NOT a score property, so the validator's score checks treat it exactly
like `reversible_with_optimization`; the clinical terminal_state stays
`OPERABLE_AFTER_OPTIMIZATION` and the barrier is reported as an orthogonal flag.

`clinical_context` object:

| Field | Type | Notes |
|-------|------|-------|
| `indication` | string | Always `"CABG"` for this PoC. |
| `coronary_disease_extent` | string | Synthetic narrative of coronary anatomy (a **fixed** factor). |
| `home_town` | string | Optional; present on the grandmother analog. |

### 2.3 `modifiable_levers[]` (lever object)

| Field | Type | Allowed values / notes |
|-------|------|------------------------|
| `lever` | string | One of the lever names in §1.2. |
| `coupling` | string | `"euroscore_visible"` \| `"needs_risk_modifier"`. |
| `euroscore_field` | string or null | If `euroscore_visible`: one of `modifiable_euroscore_visible_fields`. If `needs_risk_modifier`: MUST be `null`. |
| `status` | string | Free-text current state, e.g. `"poorly_controlled"`, `"deconditioned"`, `"already_optimized"`. |
| `optimizable` | boolean | Whether this lever still has headroom. |
| `note` | string | Plain-language note; carries `[TO VERIFY]` where a clinical specific is implied. |

### 2.4 Cross-field rules enforced by `validate.py`

1. `_meta.synthetic == true` and every `vignettes[].synthetic == true`.
2. Every `design_intent` is one of the three allowed values.
3. `euroscore_inputs` keys equal the canonical set exactly (no missing, no extra).
4. Each lever's `coupling` is valid; if `euroscore_visible`, `euroscore_field` is a
   member of `modifiable_euroscore_visible_fields`; if `needs_risk_modifier`,
   `euroscore_field` is `null`.
5. **Coupling constraint:** every `reversible_with_optimization` vignette carries
   **at least two** `euroscore_visible` levers (so the score can move pre-modifier).
6. **Exactly one** vignette has `grandmother_analog == true`, and its `design_intent`
   is `"reversible_with_optimization"`.
7. `vignette.id` values are unique.

---

## 3. `capability_profile.json`

Top-level object with keys `_meta`, `tiers`, `capabilities`.

### 3.1 `_meta` (object)

| Field | Type | Notes |
|-------|------|-------|
| `synthetic` | boolean | MUST be `true`. |
| `warning` | string | Working-assumption / `[TO VERIFY]` warning. |
| `spec_source` | string | Reference to SPEC.md §c. |
| `availability_values` | array of string | `["yes","no","partial","unknown"]`. |
| `category_values` | array of string | The four capability categories. |

### 3.2 `tiers` (object)

Exactly two keys: `local` and `tertiary`. Each is an object:

| Field | Type | Notes |
|-------|------|-------|
| `tier` | integer | `1` for local, `2` for tertiary. |
| `name` | string | Human-readable tier name. |
| `description` | string | Conceptual capabilities; carries `[TO VERIFY]`. |

### 3.3 `capabilities` (array of capability objects)

Mirrors the SPEC.md §c structure plus a `category` field:

| Field | Type | Allowed values / notes |
|-------|------|------------------------|
| `capability_id` | string | Unique stable id, e.g. `"cabg"`. |
| `category` | string | One of `category_values` (§3.1). |
| `description` | string | Plain-language description. |
| `local_available` | string | One of `availability_values`. |
| `tertiary_available` | string | One of `availability_values`. |
| `notes` | string | Caveats; **every real-world specific carries `[TO VERIFY]`**. |

### 3.4 Rules enforced by `validate.py`

1. `_meta.synthetic == true`.
2. `tiers` has exactly `local` and `tertiary`, with `tier` 1 and 2 respectively.
3. Every capability has all required fields with correct types.
4. `category` ∈ `category_values`; `local_available` / `tertiary_available` ∈
   `availability_values`.
5. `capability_id` values are unique.
6. Every capability `notes` string contains a `[TO VERIFY]` marker (real-world specifics
   must not be asserted as fact).

---

## 4. Running the validator

```bash
python3 data/validate.py
```

Exit code `0` = both files conform. Non-zero = one or more structural errors printed to
stderr. See the script header for details.
