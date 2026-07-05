"""
The access gate (Step 7) — the accessibility core.

apply_access_gate(loop_result) -> GatedPathway. Rewrites the loop's pathway as
"do locally in Sihor" vs "trip to Bhavnagar" vs "access barrier", accounts for trips, and
flags logistic strain — WITHOUT overruling the clinical verdict or dropping any
intervention. Access concerns (barriers, strain) are orthogonal to the clinical
terminal_state, exactly as TIME_INFEASIBLE is.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.gate.tier_routing import route_intervention, route_surgery, RoutingDecision
from src.gate.trip_accounting import account_trips


@dataclass
class GatedPathway:
    # clinical verdict carried through UNCHANGED
    terminal_state: object
    time_infeasible: bool
    # access-annotated pathway
    required_pathway: list = field(default_factory=list)              # RoutedIntervention
    designed_not_required_pathway: list = field(default_factory=list)  # RoutedIntervention
    surgical_routing: RoutingDecision = None
    # trip / access accounting
    trip_count: int = 0
    access_barriers: list = field(default_factory=list)
    access_strain: bool = False
    access_summary: dict = field(default_factory=dict)


def _routed_from_phases(plan, phase_numbers, patient_tier, profile_path):
    routed = []
    for phase in plan.phases:
        if phase.phase_number in phase_numbers:
            for rec in phase.interventions:
                routed.append(
                    route_intervention(rec.lever, phase.phase_number, patient_tier, profile_path)
                )
    return routed


def apply_access_gate(loop_result, profile_path=None, max_tertiary_trips=None) -> GatedPathway:
    plan = loop_result.plan
    patient_tier = loop_result.patient_tier

    # Which phases were actually executed to reach the terminal outcome.
    executed = {it.phase_number for it in loop_result.trace if it.phase_number > 0}
    designed_only = {p.phase_number for p in plan.phases} - executed

    required = _routed_from_phases(plan, executed, patient_tier, profile_path)
    designed_not_required = _routed_from_phases(plan, designed_only, patient_tier, profile_path)

    surgical_routing = route_surgery(patient_tier, profile_path)

    all_interventions = required + designed_not_required
    trips = account_trips(
        required, all_interventions, surgical_routing, max_tertiary_trips=max_tertiary_trips
    )

    access_summary = {
        "required_local": sum(1 for r in required if r.routing.tier == "local" and not r.routing.is_access_barrier),
        "required_tertiary_trip": len(trips.tertiary_trip_interventions),
        "required_barrier": sum(1 for r in required if r.routing.is_access_barrier),
        "designed_not_required": len(designed_not_required),
        "access_barriers_total": len(trips.access_barriers),
        "trip_count": trips.trip_count,
        "surgery_tier": surgical_routing.tier,
    }

    return GatedPathway(
        terminal_state=loop_result.terminal_state,     # UNCHANGED by the gate
        time_infeasible=loop_result.time_infeasible,   # UNCHANGED by the gate
        required_pathway=required,
        designed_not_required_pathway=designed_not_required,
        surgical_routing=surgical_routing,
        trip_count=trips.trip_count,
        access_barriers=trips.access_barriers,
        access_strain=trips.access_strain,
        access_summary=access_summary,
    )
