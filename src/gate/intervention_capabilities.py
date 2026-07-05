"""
Intervention capability model (Step 8, Part A) — the honest specialist-scarcity layer.

Each intervention is split into TWO capability sets:

  * delivery_capabilities — the labs / meds / monitoring that EXECUTE the intervention
    day-to-day. In a rural setting these are overwhelmingly local (Sihor).
  * oversight_capability  — the specialist whose input is needed ONCE to INITIATE / set
    the plan (and periodically review). This is a one-touch consult, not co-location.

INITIATION-VS-DELIVERY PRINCIPLE (the honest core of Path B):
Rural chronic-disease management does not require a specialist to be co-located. A
patient's diabetes or asthma is *delivered* locally — the GP, the local labs, the local
pharmacy — while a specialist sets the regimen in an initial consult and reviews
periodically. So a "needs endocrinologist" signal is modeled as ONE oversight consult
(a single trip to Bhavnagar), NOT as "the infrastructure to manage diabetes is missing."
Representing scarcity this way keeps the thesis intact: the gap is COORDINATION, not
machines. It would be dishonest to convert a one-touch consult into a permanent
infrastructure barrier.

Some interventions have no distinct specialist — prehabilitation/mobility is
overseen by the general physician / physiotherapy locally; smoking cessation by the GP.
For those, oversight_capability is None (no specialist consult, no extra trip).
"""

from __future__ import annotations

# lever -> {"delivery": [capability_id, ...], "oversight": capability_id | None}
INTERVENTION_CAPABILITIES: dict[str, dict] = {
    "hba1c": {
        "delivery": ["hba1c_test", "insulin", "oral_hypoglycemics", "general_physician"],
        "oversight": "endocrinologist",
    },
    "asthma_control": {
        "delivery": ["general_physician", "inhaled_corticosteroids", "inhaled_bronchodilators"],
        "oversight": "pulmonologist",
    },
    "heart_failure_symptoms": {
        "delivery": ["general_physician", "antihypertensives"],
        "oversight": "cardiologist",
    },
    "critical_preop_stabilization": {
        "delivery": ["cardiac_icu"],
        "oversight": "cardiologist",
    },
    "mobility": {
        # prehabilitation delivered + overseen locally (GP / physiotherapy) — no specialist
        "delivery": ["prehabilitation"],
        "oversight": None,
    },
    "smoking_status": {
        "delivery": ["smoking_cessation_support"],
        "oversight": None,   # GP-led, no specialist consult
    },
}

# Capabilities that belong to the single tertiary CARDIAC care episode (the CABG). Cardiac
# oversight / cardiac ICU do NOT add a separate Bhavnagar trip — the patient is already at
# the tertiary cardiac unit for the operation. Non-cardiac specialists (endocrinology,
# pulmonology) are distinct consults. [TO VERIFY — trip batching; real scheduling differs.]
CARDIAC_DOMAIN_CAPABILITIES = frozenset(
    {"cardiologist", "cardiac_surgeon", "cardiac_icu", "cabg", "pci"}
)

# Human-readable name per lever, for the access description / report.
LEVER_DISPLAY = {
    "hba1c": "Glycemic optimization",
    "asthma_control": "Pulmonary / asthma optimization",
    "heart_failure_symptoms": "Heart-failure medical optimization",
    "critical_preop_stabilization": "Critical pre-operative stabilization",
    "mobility": "Prehabilitation / mobility",
    "smoking_status": "Smoking cessation",
}
