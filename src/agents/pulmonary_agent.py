"""
Pulmonary specialist agent (Step 4).

Domain: the `asthma_control` lever (chronic_lung_disease) and the `smoking_status` lever.
Contains NO EuroSCORE math. Emits the KEY cross-specialty warning (ICS <-> glycemia) that
Step 5's conflict resolver will consume.
"""

from __future__ import annotations

from pathlib import Path

from src.decomposer import DecompositionResult
from src.agents.types import SpecialistRecommendation
from src.agents.base import make_recommendation, modifier_by_name, visible_by_name

SPECIALTY = "pulmonary"

# THE KEY CONFLICT (money warning for Step 5).
_ICS_GLYCEMIA_WARNING = (
    "ICS dose increase will worsen glycemic control in insulin-dependent patients — "
    "endocrine coordination REQUIRED before finalizing ICS dose. Sequence glycemic "
    "stabilization before ICS step-up, or monitor glucose closely during ICS titration."
)
_SYSTEMIC_STEROID_WARNING = (
    "Systemic steroids for an acute exacerbation will significantly worsen glycemic "
    "control — do not use systemic steroids without an endocrine plan."
)
_EXACERBATION_WARNING = (
    "Confirm no acute asthma exacerbation before surgery — defer operating if an "
    "exacerbation is present."
)
_NRT_WARNING = (
    "Nicotine replacement therapy (NRT) has cardiovascular effects — the cardiac team "
    "should be aware if NRT is used."
)


def run(
    vignette: dict,
    decomposition: DecompositionResult,
    capability_profile_path: str | Path | None = None,
) -> SpecialistRecommendation:
    tier = vignette["location_tier"]
    visible = visible_by_name(decomposition)
    modifiers = modifier_by_name(decomposition)
    result = SpecialistRecommendation(specialty=SPECIALTY)

    # --- asthma control -------------------------------------------------------------
    asthma = visible.get("asthma_control")
    if asthma is not None and asthma.status == "poorly_controlled":
        result.recommendations.append(
            make_recommendation(
                lever="asthma_control",
                action=(
                    "Step up inhaled therapy per GINA: (1) confirm/correct inhaler "
                    "technique, (2) titrate inhaled corticosteroid (ICS) dose, "
                    "(3) add long-acting beta-agonist (LABA) if needed."
                ),
                target=(
                    "chronic_lung_disease: false (asthma well-controlled, FEV1 >=70% "
                    "predicted [TO VERIFY — FEV1 threshold for anaesthetic clearance])"
                ),
                euroscore_field="chronic_lung_disease",
                capabilities=[
                    "general_physician",
                    "inhaled_corticosteroids",
                    "inhaled_bronchodilators",
                ],
                tier=tier,
                weeks_estimate=8,  # 6-8 weeks controller optimization [TO VERIFY]
                evidence_note=(
                    "Pre-operative pulmonary optimization reduces post-CABG respiratory "
                    "complications [TO VERIFY — cite source]."
                ),
                profile_path=capability_profile_path,
            )
        )
        result.warnings.append(_ICS_GLYCEMIA_WARNING)
        result.warnings.append(_SYSTEMIC_STEROID_WARNING)
        result.warnings.append(_EXACERBATION_WARNING)

    # --- smoking status -------------------------------------------------------------
    smoking = modifiers.get("smoking_status")
    if smoking is not None and smoking.status == "active_smoker":
        result.recommendations.append(
            make_recommendation(
                lever="smoking_status",
                action="Smoking cessation support (counselling +/- pharmacotherapy).",
                target=(
                    "smoking stopped for >=4 weeks pre-operatively "
                    "[TO VERIFY — cessation interval for CABG]"
                ),
                euroscore_field=None,  # not a EuroSCORE II input
                capabilities=["smoking_cessation_support"],
                tier=tier,
                weeks_estimate=4,  # 4-8 weeks minimum [TO VERIFY]
                evidence_note=(
                    "Smoking cessation >=4 weeks before surgery reduces pulmonary and "
                    "wound complications [TO VERIFY — cite source]."
                ),
                profile_path=capability_profile_path,
            )
        )
        result.warnings.append(_NRT_WARNING)

    return result
