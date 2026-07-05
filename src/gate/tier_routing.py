"""
Tier-routing model for the access gate (Step 7).

Maps each intervention to a routing decision over the two-tier capability profile
(Sihor = local / Tier 1, Bhavnagar = tertiary / Tier 2). Reuses src/feasibility.py
EXACTLY for the capability lookups — no reimplementation.

MOST-RESTRICTIVE-WINS: an intervention may require several capabilities. It is gated on
ALL of them, and its routing is the most restrictive: if any one needs tertiary, the
intervention needs a Bhavnagar trip; if any one is unavailable at both tiers, the whole
intervention is an ACCESS BARRIER (never silently dropped).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.feasibility import FeasibilityStatus
from src.agents.types import govern_feasibility  # reuses feasibility.check_feasibility

# Lever -> the capability_id(s) its intervention requires (documented mapping). The gate
# gates on ALL of these (most-restrictive wins). These mirror the capabilities the Step-4
# agents already check; kept here as the gate's explicit lever->capability contract.
LEVER_CAPABILITIES: dict[str, list[str]] = {
    "mobility": ["prehabilitation"],
    "heart_failure_symptoms": ["general_physician", "antihypertensives"],
    "critical_preop_stabilization": ["cardiac_icu"],
    "hba1c": ["hba1c_test", "insulin", "oral_hypoglycemics"],
    "asthma_control": ["general_physician", "inhaled_corticosteroids", "inhaled_bronchodilators"],
    "smoking_status": ["smoking_cessation_support"],
}

# The surgical procedure itself.
CABG_CAPABILITY = "cabg"

# status -> (routing_label, tier, flagged, is_access_barrier)
_ROUTING = {
    FeasibilityStatus.LOCAL: ("Do locally in Sihor", "local", False, False),
    FeasibilityStatus.PARTIAL_LOCAL: (
        "Likely local in Sihor, verify availability", "local", True, False),
    FeasibilityStatus.NEEDS_TERTIARY: ("Requires trip to Bhavnagar", "tertiary", False, False),
    FeasibilityStatus.PARTIAL_TERTIARY: ("Likely Bhavnagar, verify", "tertiary", True, False),
    FeasibilityStatus.UNAVAILABLE: (
        "ACCESS BARRIER — not available at Sihor or Bhavnagar", "none", True, True),
}


class UnknownInterventionError(KeyError):
    """Raised when a lever has no capability mapping in the gate."""


@dataclass
class RoutingDecision:
    status: FeasibilityStatus
    routing_label: str
    tier: str                 # "local" | "tertiary" | "none"
    flagged: bool             # partial availability -> verify
    is_access_barrier: bool
    governing_capability: str
    note: str


@dataclass
class RoutedIntervention:
    lever: str
    phase_number: int
    capabilities: list
    routing: RoutingDecision


def route_from_feasibility(fr) -> RoutingDecision:
    """Map a governing FeasibilityResult to a RoutingDecision."""
    label, tier, flagged, barrier = _ROUTING[fr.status]
    return RoutingDecision(
        status=fr.status,
        routing_label=label,
        tier=tier,
        flagged=flagged,
        is_access_barrier=barrier,
        governing_capability=fr.action_id,
        note=fr.note,
    )


def route_capabilities(capabilities, patient_tier, profile_path=None) -> RoutingDecision:
    """Most-restrictive routing across `capabilities` (reuses govern_feasibility, which
    reuses feasibility.check_feasibility). Raises if a capability is unknown."""
    fr = govern_feasibility(list(capabilities), patient_tier, profile_path)
    return route_from_feasibility(fr)


def route_intervention(lever, phase_number, patient_tier, profile_path=None) -> RoutedIntervention:
    """Route one intervention (by lever) to a tier decision."""
    if lever not in LEVER_CAPABILITIES:
        raise UnknownInterventionError(f"no capability mapping for lever {lever!r}")
    caps = LEVER_CAPABILITIES[lever]
    return RoutedIntervention(
        lever=lever,
        phase_number=phase_number,
        capabilities=caps,
        routing=route_capabilities(caps, patient_tier, profile_path),
    )


def route_surgery(patient_tier, profile_path=None) -> RoutingDecision:
    """Route the CABG procedure itself (tertiary per the capability profile)."""
    return route_capabilities([CABG_CAPABILITY], patient_tier, profile_path)
