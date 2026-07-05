"""
Deterministic EuroSCORE II risk calculator (Step 3).

Pure functions, no LLM, no network, no clinical logic beyond the published EuroSCORE II
logistic model. Every numeric constant is imported from
`src.euroscore_ii_coefficients` (which cites its source); this file contains ZERO magic
numbers.

Public API:
    compute_euroscore_ii(euroscore_inputs) -> float   # predicted mortality %, 0..100
    euroscore_inputs_to_linear_predictor(euroscore_inputs) -> float   # the y term

Invalid inputs raise EuroscoreInputError (fail loud; never a silent default).
"""

from __future__ import annotations

import math

from src import euroscore_ii_coefficients as C
# Reuse the canonical field set defined in data/validate.py (single source of truth,
# aligned with docs/SPEC.md §d / data/SCHEMA.md §1.1) rather than redefining it here.
from data.validate import EUROSCORE_FIELDS


class EuroscoreInputError(ValueError):
    """Raised when euroscore_inputs is missing a field, has an extra field, or a field
    has an invalid type or value."""


# --- Schema-value -> coefficient encodings -------------------------------------------
# Each maps an allowed schema string (data/SCHEMA.md §1.1) to its published EuroSCORE II
# beta. Reference categories map to 0.0.
_RENAL_MAP = {
    "normal": 0.0,                       # CC > 85 ml/min (reference)
    "moderate": C.BETA_RENAL_CC_51_85,   # CC 51-85 ml/min
    "severe": C.BETA_RENAL_CC_LE_50,     # CC <= 50 ml/min (not dialysis)
    "on_dialysis": C.BETA_RENAL_ON_DIALYSIS,
}
# [TO VERIFY] Our schema's coarse renal categories (normal/moderate/severe/on_dialysis)
# are MAPPED onto EuroSCORE II's Cockcroft-Gault creatinine-clearance bands
# (>85 / 51-85 / <=50 / dialysis). We do not carry raw creatinine clearance, so the
# normal->CC>85, moderate->CC51-85, severe->CC<=50 correspondence is an explicit modeling
# assumption to confirm when real CC values are available.

_NYHA_MAP = {
    "I": 0.0,                 # reference
    "II": C.BETA_NYHA_II,
    "III": C.BETA_NYHA_III,
    "IV": C.BETA_NYHA_IV,
}

_LV_MAP = {
    "good": 0.0,                  # LVEF > 51% (reference)
    "moderate": C.BETA_LV_MODERATE,  # 31-50%
    "poor": C.BETA_LV_POOR,          # 21-30%
    # NOTE: our schema (SCHEMA.md §1.1) has only good/moderate/poor. EuroSCORE II also
    # has "very poor" (<=20%, BETA_LV_VERY_POOR); we do NOT emit it because the data
    # never encodes it. It remains available in the coefficients module and is added
    # here if the schema gains a "very_poor" value. [TO VERIFY — whether the archetype
    # ever needs the very-poor band.]
}

_PA_MAP = {
    "none": 0.0,                        # < 31 mmHg (reference)
    "moderate": C.BETA_PA_MODERATE_31_55,  # 31-55 mmHg
    "severe": C.BETA_PA_SEVERE_GE_55,      # >= 55 mmHg
}

_URGENCY_MAP = {
    "elective": 0.0,   # reference
    "urgent": C.BETA_URGENCY_URGENT,
    "emergency": C.BETA_URGENCY_EMERGENCY,
    "salvage": C.BETA_URGENCY_SALVAGE,
}

_WEIGHT_MAP = {
    "isolated_cabg": 0.0,  # reference
    # [TO VERIFY] Our schema has only isolated_cabg / cabg_plus_other. We map
    # cabg_plus_other onto EuroSCORE II's "two major procedures" band. EuroSCORE II also
    # distinguishes "single non-CABG" and "three+ procedures", which our schema does not
    # encode. Confirm the intended mapping if the schema gains finer categories.
    "cabg_plus_other": C.BETA_WEIGHT_TWO_PROCEDURES,
}

# Boolean fields -> the beta applied when the field is True.
_BOOLEAN_BETAS = {
    "extracardiac_arteriopathy": C.BETA_EXTRACARDIAC_ARTERIOPATHY,
    "poor_mobility": C.BETA_POOR_MOBILITY,
    "previous_cardiac_surgery": C.BETA_PREVIOUS_CARDIAC_SURGERY,
    "chronic_lung_disease": C.BETA_CHRONIC_LUNG_DISEASE,
    "active_endocarditis": C.BETA_ACTIVE_ENDOCARDITIS,
    "critical_preoperative_state": C.BETA_CRITICAL_PREOP_STATE,
    "diabetes_on_insulin": C.BETA_INSULIN_DIABETES,
    "ccs_class4_angina": C.BETA_CCS4_ANGINA,
    "recent_mi": C.BETA_RECENT_MI,
    "thoracic_aorta_surgery": C.BETA_THORACIC_AORTA,
}

_CATEGORICAL_MAPS = {
    "renal_impairment": _RENAL_MAP,
    "nyha_class": _NYHA_MAP,
    "lv_function": _LV_MAP,
    "pulmonary_hypertension": _PA_MAP,
    "urgency": _URGENCY_MAP,
    "weight_of_intervention": _WEIGHT_MAP,
}


def _validate(inputs: dict) -> None:
    """Validate that `inputs` has exactly the canonical field set with correct types and
    allowed values. Raise EuroscoreInputError otherwise."""
    if not isinstance(inputs, dict):
        raise EuroscoreInputError(f"euroscore_inputs must be a dict, got {type(inputs).__name__}")

    keys = set(inputs.keys())
    missing = EUROSCORE_FIELDS - keys
    extra = keys - EUROSCORE_FIELDS
    if missing:
        raise EuroscoreInputError(f"missing EuroSCORE fields: {sorted(missing)}")
    if extra:
        raise EuroscoreInputError(f"unexpected EuroSCORE fields: {sorted(extra)}")

    # age: an int (not bool), plausibly positive
    age = inputs["age"]
    if isinstance(age, bool) or not isinstance(age, int):
        raise EuroscoreInputError(f"age must be an int, got {age!r}")
    if not (0 < age < 130):
        raise EuroscoreInputError(f"age out of plausible range (0,130): {age!r}")

    # sex
    if inputs["sex"] not in ("male", "female"):
        raise EuroscoreInputError(f"sex must be 'male' or 'female', got {inputs['sex']!r}")

    # booleans
    for field in _BOOLEAN_BETAS:
        val = inputs[field]
        if not isinstance(val, bool):
            raise EuroscoreInputError(f"{field} must be a bool, got {val!r}")

    # categoricals
    for field, mapping in _CATEGORICAL_MAPS.items():
        val = inputs[field]
        if val not in mapping:
            raise EuroscoreInputError(
                f"{field} must be one of {sorted(mapping)}, got {val!r}"
            )


def _age_term(age: int) -> float:
    """EuroSCORE II age contribution: x = 1 for age <= 60, +1 per year above 60."""
    x = 1 if age <= C.AGE_BASELINE else age - (C.AGE_BASELINE - 1)
    return C.BETA_AGE * x


def euroscore_inputs_to_linear_predictor(euroscore_inputs: dict) -> float:
    """Return the linear predictor y = CONSTANT + Σ(beta_i * x_i). Validates inputs."""
    _validate(euroscore_inputs)

    y = C.CONSTANT
    y += _age_term(euroscore_inputs["age"])
    if euroscore_inputs["sex"] == "female":
        y += C.BETA_FEMALE
    for field, beta in _BOOLEAN_BETAS.items():
        if euroscore_inputs[field]:
            y += beta
    for field, mapping in _CATEGORICAL_MAPS.items():
        y += mapping[euroscore_inputs[field]]
    return y


def compute_euroscore_ii(euroscore_inputs: dict) -> float:
    """Predicted in-hospital mortality as a percentage in [0, 100].

    mortality = e^y / (1 + e^y), returned * 100.
    """
    y = euroscore_inputs_to_linear_predictor(euroscore_inputs)
    probability = math.exp(y) / (1.0 + math.exp(y))
    return probability * 100.0
