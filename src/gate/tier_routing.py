"""
Tier-routing model for the access gate (Step 7, extended in Step 8 Part A).

Each intervention now has TWO routings kept SEPARATE (the honest core of Path B):
  * delivery_routing  — most-restrictive over its delivery_capabilities (day-to-day
    execution; local in Sihor wherever possible).
  * oversight_routing — routing for its oversight specialist consult (one-touch), or None
    if the intervention has no distinct specialist.

Reuses src/feasibility.py exactly for capability lookups. MOST-RESTRICTIVE-WINS applies
within each capability set.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.feasibility import FeasibilityStatus
from src.agents.types import govern_feasibility  # reuses feasibility.check_feasibility
from src.gate.intervention_capabilities import (
    INTERVENTION_CAPABILITIES,
    LEVER_DISPLAY,
)

# Backward-compatible alias: the Step-7 "lever -> capabilities" map is the delivery set.
LEVER_CAPABILITIES = {k: v["delivery"] for k, v in INTERVENTION_CAPABILITIES.items()}

CABG_CAPABILITY = "cabg"

# delivery status -> (routing_label, tier, flagged, is_access_barrier)
_ROUTING = {
    FeasibilityStatus.LOCAL: ("Do locally in Sihor", "local", False, False),
    FeasibilityStatus.PARTIAL_LOCAL: (
        "Likely local in Sihor, verify availability", "local", True, False),
    FeasibilityStatus.NEEDS_TERTIARY: ("Requires trip to Bhavnagar", "tertiary", False, False),
    FeasibilityStatus.PARTIAL_TERTIARY: ("Likely Bhavnagar, verify", "tertiary", True, False),
    FeasibilityStatus.UNAVAILABLE: (
        "ACCESS BARRIER — not available at Sihor or Bhavnagar", "none", True, True),
}

# oversight status -> consult-flavored label
_OVERSIGHT_ROUTING = {
    FeasibilityStatus.LOCAL: ("Specialist available locally in Sihor", "local", False, False),
    FeasibilityStatus.PARTIAL_LOCAL: (
        "Specialist may be available locally, verify", "local", True, False),
    FeasibilityStatus.NEEDS_TERTIARY: (
        "Specialist consult: one trip to Bhavnagar", "tertiary", False, False),
    FeasibilityStatus.PARTIAL_TERTIARY: (
        "Specialist consult: one trip to Bhavnagar (verify availability)", "tertiary", True, False),
    FeasibilityStatus.UNAVAILABLE: (
        "SPECIALIST ACCESS BARRIER — no specialist at Sihor or Bhavnagar", "none", True, True),
}


class UnknownInterventionError(KeyError):
    """Raised when a lever has no capability mapping in the gate."""


@dataclass
class RoutingDecision:
    status: FeasibilityStatus
    routing_label: str
    tier: str                 # "local" | "tertiary" | "none"
    flagged: bool
    is_access_barrier: bool
    governing_capability: str
    note: str


@dataclass
class RoutedIntervention:
    lever: str
    phase_number: int
    delivery_capabilities: list
    delivery_routing: RoutingDecision
    oversight_capability: str | None
    oversight_routing: RoutingDecision | None
    access_description: str


def route_from_feasibility(fr, table=_ROUTING) -> RoutingDecision:
    label, tier, flagged, barrier = table[fr.status]
    return RoutingDecision(
        status=fr.status, routing_label=label, tier=tier, flagged=flagged,
        is_access_barrier=barrier, governing_capability=fr.action_id, note=fr.note,
    )


def route_capabilities(capabilities, patient_tier, profile_path=None) -> RoutingDecision:
    """Most-restrictive delivery routing across `capabilities`. Raises if unknown."""
    fr = govern_feasibility(list(capabilities), patient_tier, profile_path)
    return route_from_feasibility(fr, _ROUTING)


def route_oversight(oversight_capability, patient_tier, profile_path=None) -> RoutingDecision:
    """Routing for a single specialist oversight consult (consult-flavored labels)."""
    fr = govern_feasibility([oversight_capability], patient_tier, profile_path)
    return route_from_feasibility(fr, _OVERSIGHT_ROUTING)


def _access_description(lever, delivery, oversight_cap, oversight) -> str:
    name = LEVER_DISPLAY.get(lever, lever)
    where = "locally in Sihor" if delivery.tier == "local" else (
        "at Bhavnagar (tertiary)" if delivery.tier == "tertiary" else "NOWHERE (access barrier)")
    parts = [f"{name} — delivered {where}"]
    if oversight is None:
        parts.append("overseen locally (general physician / physiotherapy); no specialist consult")
    elif oversight.is_access_barrier:
        parts.append(f"SPECIALIST ACCESS BARRIER: no {oversight_cap} at Sihor or Bhavnagar")
    elif oversight.tier == "tertiary":
        parts.append(f"requires one initial {oversight_cap} consult in Bhavnagar to set the plan")
    else:
        parts.append(f"{oversight_cap} available locally")
    return "; ".join(parts) + "."


def route_intervention(lever, phase_number, patient_tier, profile_path=None) -> RoutedIntervention:
    if lever not in INTERVENTION_CAPABILITIES:
        raise UnknownInterventionError(f"no capability mapping for lever {lever!r}")
    spec = INTERVENTION_CAPABILITIES[lever]
    delivery_caps = spec["delivery"]
    oversight_cap = spec["oversight"]
    delivery = route_capabilities(delivery_caps, patient_tier, profile_path)
    oversight = (
        route_oversight(oversight_cap, patient_tier, profile_path)
        if oversight_cap is not None else None
    )
    return RoutedIntervention(
        lever=lever,
        phase_number=phase_number,
        delivery_capabilities=delivery_caps,
        delivery_routing=delivery,
        oversight_capability=oversight_cap,
        oversight_routing=oversight,
        access_description=_access_description(lever, delivery, oversight_cap, oversight),
    )


def route_surgery(patient_tier, profile_path=None) -> RoutingDecision:
    """Route the CABG procedure itself (tertiary per the capability profile)."""
    return route_capabilities([CABG_CAPABILITY], patient_tier, profile_path)
