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
# Default = 8.0%. Rationale: EuroSCORE II predicted mortality above ~8% falls in the
# high / very-high risk bands that are commonly flagged for multidisciplinary (heart-
# team) review rather than routine listing. The specific numeric cutoff is a defensible
# convention, NOT a validated clinical boundary.
# [TO VERIFY — exact high-risk band cutoff convention with clinical input; SPEC.md §e
#  records that no clinically-validated default exists.]
#
# Override precedence (highest first):
#   1. explicit `threshold=` argument to get_operability_threshold()
#   2. environment variable OPERABILITY_THRESHOLD
#   3. this default
DEFAULT_OPERABILITY_THRESHOLD: float = 8.0

# Public default name other modules read. Do NOT compare against a literal 8.0 anywhere;
# call get_operability_threshold() or read this name.
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
