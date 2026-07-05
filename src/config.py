"""
Central configuration for the Operability Reversal Agent (Step 3+).

Holds the single source of truth for:
  - OPERABILITY_THRESHOLD (the configurable operability proxy, SPEC.md §e)
  - the modifiable-lever <-> EuroSCORE-field mapping (SPEC.md §f / data/SCHEMA.md §1.2)

Nothing elsewhere in the codebase may hard-code these values; import them from here.
"""

import os

# =============================================================================
# Operability threshold (SPEC.md §e, Simplifying Assumption OP-1)
# =============================================================================
# Predicted in-hospital mortality (%) at/above which a patient is treated as
# "declined at baseline". This is a CONFIGURABLE MODELING PROXY, not a clinical
# clearance line.
#
# Default = 6.0% (changed from 8.0% in Step 4; see below and the Step-3 report).
#
# Rationale / grounding:
#   - EuroSCORE II (Nashef et al., Eur J Cardiothorac Surg 2012;41:734-745) frames
#     predicted in-hospital mortality in risk bands; roughly, >4% is intermediate risk
#     and higher values are high / very-high risk.
#   - The 2014 ESC/EACTS Guidelines on myocardial revascularisation (Windecker et al.,
#     Eur Heart J 2014;35:2541-2619) use EuroSCORE II >= ~4% as an entry criterion for
#     Heart-Team discussion rather than routine listing.
#   - Many cardiac programs use a pragmatic 5-6% "multidisciplinary review required"
#     line before proceeding with elective CABG in complex patients. A 6% proxy sits in
#     the defensible intermediate-to-high band.
#   This is a CONFIGURABLE MODELING PROXY, not a clinical clearance line.
#   [TO VERIFY — exact program-specific cutoff convention with clinical input; the
#    numeric line is a modeling choice, not a validated boundary. SPEC.md §e records that
#    no single clinically-validated default exists.]
#
# WHY CHANGED FROM 8.0 -> 6.0 (Step 4): the Step-3 report found that with the real
# EuroSCORE II coefficients, isolated *elective* CABG scores lower than the synthetic
# vignettes assumed. The grandmother analog (SYNTH-006) baselines at 7.38% — under an
# 8.0% proxy she was NOT "declined at baseline", defeating the reversal demo. At 6.0%
# she is correctly "declined at baseline" (7.38% >= 6.0%) and becomes "potentially
# operable" after visible-lever optimization (3.72% < 6.0%).
#
# Override precedence (highest first):
#   1. explicit `threshold=` argument to get_operability_threshold()
#   2. environment variable OPERABILITY_THRESHOLD
#   3. this default
DEFAULT_OPERABILITY_THRESHOLD: float = 6.0

# Public default name other modules read. Do NOT compare against a literal number
# anywhere; call get_operability_threshold() or read this name.
OPERABILITY_THRESHOLD: float = DEFAULT_OPERABILITY_THRESHOLD

_ENV_VAR = "OPERABILITY_THRESHOLD"


def get_operability_threshold(threshold: float | None = None) -> float:
    """Resolve the operability threshold, honoring (1) an explicit arg, (2) the
    OPERABILITY_THRESHOLD env var, (3) the module default.

    Raises ValueError on a non-positive or unparseable value (fail loud, never a
    silent default)."""
    if threshold is not None:
        value = threshold
    elif _ENV_VAR in os.environ and os.environ[_ENV_VAR].strip() != "":
        raw = os.environ[_ENV_VAR]
        try:
            value = float(raw)
        except ValueError as exc:
            raise ValueError(
                f"{_ENV_VAR} env var is not a valid float: {raw!r}"
            ) from exc
    else:
        value = DEFAULT_OPERABILITY_THRESHOLD

    if not (0.0 < value <= 100.0):
        raise ValueError(
            f"operability threshold must be in (0, 100], got {value!r}"
        )
    return float(value)


# =============================================================================
# Surgical-urgency optimization budget (Step 5)
# =============================================================================
# For a non-elective (e.g. "urgent") case, how many weeks of pre-operative optimization
# the pathway can realistically afford before the plan should be flagged for human review
# as too slow. This is a MODELING PROXY, not a clinical rule: real urgency windows are a
# case-by-case surgical judgement.
# [TO VERIFY — realistic urgent pre-op optimization window with clinical input.]
MAX_URGENT_OPTIMIZATION_WEEKS: int = 4


# =============================================================================
# Modifiable-lever <-> EuroSCORE-field mapping (single source of truth)
# =============================================================================
# The EuroSCORE II input fields that are ALSO modifiable levers ("euroscore_visible" /
# "Modifiable-but-cardiac" per SPEC.md §f). Improving one of these changes the mapped
# EuroSCORE field and therefore the predicted score directly.
#
# lever name (data/SCHEMA.md §1.2)  ->  EuroSCORE II input field it maps to
LEVER_TO_EUROSCORE_FIELD: dict[str, str] = {
    "asthma_control": "chronic_lung_disease",
    "mobility": "poor_mobility",
    "heart_failure_symptoms": "nyha_class",
    "critical_preop_stabilization": "critical_preoperative_state",
}

# The set of EuroSCORE fields that are treated as modifiable (mirror of the data's
# _meta.modifiable_euroscore_visible_fields). Derived from the mapping above so there is
# exactly one source of truth.
MODIFIABLE_EUROSCORE_VISIBLE_FIELDS: frozenset[str] = frozenset(
    LEVER_TO_EUROSCORE_FIELD.values()
)

# "needs_risk_modifier" levers (non-EuroSCORE-visible). Tracked but with ZERO effect on
# predicted mortality in Step 3. See src/README.md (Option A vs Option B).
NEEDS_RISK_MODIFIER_LEVERS: frozenset[str] = frozenset(
    {"hba1c", "smoking_status", "anemia", "albumin", "blood_pressure"}
)
