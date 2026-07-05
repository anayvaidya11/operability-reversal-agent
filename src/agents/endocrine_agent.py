"""
Endocrine specialist agent (Step 4).

Domain: the `hba1c` lever ONLY (needs_risk_modifier — invisible to EuroSCORE II).
`diabetes_on_insulin` is a FIXED EuroSCORE II input (binary insulin status), flagged in
out_of_scope_flags. Contains NO EuroSCORE math.
"""

from __future__ import annotations

from pathlib import Path

from src.decomposer import DecompositionResult
from src.agents.types import SpecialistRecommendation
from src.agents.base import make_recommendation, modifier_by_name

SPECIALTY = "endocrine"

_COLD_CHAIN_WARNING = (
    "Insulin titration requires cold-chain storage and reliable supply — verify local "
    "availability before committing to this plan."
)
# Always emitted for this PoC when an hba1c recommendation is made.
_OPTION_B_WARNING = (
    "HbA1c improvement is currently invisible to the EuroSCORE II score "
    "(needs_risk_modifier, Option B deferred). This optimization is clinically real but "
    "does not move the predicted mortality in this PoC version."
)
_INSULIN_FIXED_FLAG = (
    "diabetes_on_insulin is a fixed EuroSCORE II input; glycemic CONTROL (HbA1c) is "
    "modifiable but is invisible to EuroSCORE II in this PoC (Option B deferred)."
)


def run(
    vignette: dict,
    decomposition: DecompositionResult,
    capability_profile_path: str | Path | None = None,
) -> SpecialistRecommendation:
    tier = vignette["location_tier"]
    inputs = vignette["euroscore_inputs"]
    on_insulin = inputs["diabetes_on_insulin"]
    modifiers = modifier_by_name(decomposition)
    result = SpecialistRecommendation(specialty=SPECIALTY)

    hba1c = modifiers.get("hba1c")
    if hba1c is not None and hba1c.status != "already_optimized":
        if on_insulin:
            action = (
                "Intensive pre-operative glycemic optimization: titrate a basal-bolus "
                "insulin regimen with daily glucose monitoring."
            )
            capabilities = ["insulin", "hba1c_test"]
        else:
            action = (
                "Intensive pre-operative glycemic optimization: add/intensify oral "
                "glucose-lowering therapy with monitoring."
            )
            capabilities = ["oral_hypoglycemics", "hba1c_test"]

        result.recommendations.append(
            make_recommendation(
                lever="hba1c",
                action=action,
                target="HbA1c < 7.5% (53 mmol/mol) [MODELING ASSUMPTION — exact pre-op target "
                       "is a modeling choice; clinician-verify]",
                euroscore_field=None,  # invisible to EuroSCORE II (Option B deferred)
                capabilities=capabilities,
                tier=tier,
                weeks_estimate=12,  # 8-12 weeks [MODELING ASSUMPTION]
                evidence_note=(
                    "Elevated pre-operative HbA1c is associated with deep sternal wound "
                    "infection after CABG [CITED — J Cardiothorac Surg 2024 meta-analysis, "
                    "OR 2.67, PubMed 38311780; clinician-verify]."
                ),
                profile_path=capability_profile_path,
            )
        )
        if on_insulin:
            result.warnings.append(_COLD_CHAIN_WARNING)
        result.warnings.append(_OPTION_B_WARNING)

    # diabetes_on_insulin is fixed — always flag when present
    if on_insulin:
        result.out_of_scope_flags.append(_INSULIN_FIXED_FLAG)

    return result
