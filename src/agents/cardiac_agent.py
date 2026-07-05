"""
Cardiac specialist agent (Step 4).

Domain: the "modifiable-but-cardiac" euroscore_visible levers (SPEC §f reconciliation):
  - mobility                     -> poor_mobility
  - heart_failure_symptoms       -> nyha_class
  - critical_preop_stabilization -> critical_preoperative_state

Also flags FIXED cardiac factors (coronary anatomy, prior events, LV function, recent MI)
as out_of_scope_flags. Contains NO EuroSCORE math; proposes optimizations only.
"""

from __future__ import annotations

from pathlib import Path

from src.decomposer import DecompositionResult
from src.agents.types import SpecialistRecommendation
from src.agents.base import make_recommendation, visible_by_name

SPECIALTY = "cardiac"
_MY_LEVERS = {"mobility", "heart_failure_symptoms", "critical_preop_stabilization"}

# Warning emitted whenever heart-failure therapy is proposed: beta-blocker titration is
# hazardous in asthma. (Cross-specialty concern observed, not resolved — see Step 5.)
_BETA_BLOCKER_WARNING = (
    "Beta-blocker titration in asthma requires pulmonary coordination — risk of "
    "bronchospasm. Do not initiate without pulmonologist sign-off."
)


def run(
    vignette: dict,
    decomposition: DecompositionResult,
    capability_profile_path: str | Path | None = None,
) -> SpecialistRecommendation:
    tier = vignette["location_tier"]
    inputs = vignette["euroscore_inputs"]
    visible = visible_by_name(decomposition)
    result = SpecialistRecommendation(specialty=SPECIALTY)

    # --- mobility -------------------------------------------------------------------
    if "mobility" in visible:
        result.recommendations.append(
            make_recommendation(
                lever="mobility",
                action=(
                    "Supervised prehabilitation: graduated walking plus breathing "
                    "exercises to reverse deconditioning before surgery."
                ),
                target="poor_mobility: false",
                euroscore_field="poor_mobility",
                capabilities=["prehabilitation"],
                tier=tier,
                weeks_estimate=8,  # 4-8 weeks [TO VERIFY against prehabilitation literature]
                evidence_note=(
                    "Prehabilitation before cardiac surgery improves functional capacity "
                    "and reduces post-operative complications [TO VERIFY — cite source]."
                ),
                profile_path=capability_profile_path,
            )
        )

    # --- heart failure symptoms -----------------------------------------------------
    if "heart_failure_symptoms" in visible:
        result.recommendations.append(
            make_recommendation(
                lever="heart_failure_symptoms",
                action=(
                    "Optimize medical heart-failure therapy: diuretics, ACE inhibitor/ARB, "
                    "and beta-blocker titration if tolerated."
                ),
                target="nyha_class: II (one-class improvement as a realistic target)",
                euroscore_field="nyha_class",
                capabilities=["general_physician", "antihypertensives"],
                tier=tier,
                weeks_estimate=8,  # 4-8 weeks [TO VERIFY]
                evidence_note=(
                    "Guideline-directed medical therapy can improve NYHA symptom class "
                    "pre-operatively [TO VERIFY — cite source]."
                ),
                profile_path=capability_profile_path,
                cross_specialty_flags=[
                    {
                        "interacts_with": "pulmonary",
                        "target_lever": "asthma_control",
                        "mechanism": "betablocker_bronchospasm",
                        "direction": "worsens",
                    }
                ],
            )
        )
        result.warnings.append(_BETA_BLOCKER_WARNING)

    # --- critical preoperative state ------------------------------------------------
    if "critical_preop_stabilization" in visible:
        result.recommendations.append(
            make_recommendation(
                lever="critical_preop_stabilization",
                action=(
                    "Inpatient stabilization at a tertiary centre before proceeding "
                    "(treat the acute decompensation)."
                ),
                target="critical_preoperative_state: false",
                euroscore_field="critical_preoperative_state",
                capabilities=["cardiac_icu"],
                tier=tier,
                weeks_estimate=2,  # 1-2 weeks inpatient [TO VERIFY]
                evidence_note=(
                    "A critical preoperative state is frequently reversible with "
                    "stabilization before an elective/urgent operation [TO VERIFY]."
                ),
                profile_path=capability_profile_path,
            )
        )

    # --- fixed cardiac factors (observed, cannot optimize) --------------------------
    coronary = vignette.get("clinical_context", {}).get("coronary_disease_extent")
    if coronary:
        result.out_of_scope_flags.append(
            f"coronary anatomy / disease extent ({coronary}): fixed — cannot optimize "
            f"(the surgery addresses it, optimization does not change baseline anatomy)."
        )
    result.out_of_scope_flags.append(
        f"lv_function={inputs['lv_function']}: fixed — cannot optimize."
    )
    if inputs["previous_cardiac_surgery"]:
        result.out_of_scope_flags.append("previous_cardiac_surgery: fixed — cannot optimize.")
    if inputs["recent_mi"]:
        result.out_of_scope_flags.append("recent_mi: fixed — cannot optimize.")
    if inputs["ccs_class4_angina"]:
        result.out_of_scope_flags.append("ccs_class4_angina: fixed — cannot optimize.")

    return result
