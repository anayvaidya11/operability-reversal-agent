"""
The access gate (Step 7, extended Step 8 Part A) — the accessibility core.

apply_access_gate(loop_result) -> GatedPathway. Rewrites the loop's pathway as
"delivered locally in Sihor" vs "specialist consult / surgery in Bhavnagar" vs
"access barrier", keeping delivery and oversight SEPARATE, accounting for trips, and
flagging logistic strain — WITHOUT overruling the clinical verdict or dropping any
intervention.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.gate.tier_routing import route_intervention, route_surgery, RoutingDecision
from src.gate.trip_accounting import account_trips


@dataclass
class GatedPathway:
    terminal_state: object                 # clinical verdict — UNCHANGED by the gate
    time_infeasible: bool                  # UNCHANGED by the gate
    required_pathway: list = field(default_factory=list)
    designed_not_required_pathway: list = field(default_factory=list)
    surgical_routing: RoutingDecision = None
    trip_count: int = 0
    specialist_consult_trips: int = 0
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

    executed = {it.phase_number for it in loop_result.trace if it.phase_number > 0}
    designed_only = {p.phase_number for p in plan.phases} - executed

    required = _routed_from_phases(plan, executed, patient_tier, profile_path)
    designed_not_required = _routed_from_phases(plan, designed_only, patient_tier, profile_path)
    all_interventions = required + designed_not_required

    surgical_routing = route_surgery(patient_tier, profile_path)
    trips = account_trips(all_interventions, surgical_routing, max_tertiary_trips=max_tertiary_trips)

    def _count(pathway, tier, barrier=False):
        return sum(
            1 for r in pathway
            if r.delivery_routing.tier == tier and r.delivery_routing.is_access_barrier == barrier
        )

    access_summary = {
        "delivery_local": _count(all_interventions, "local"),
        "delivery_tertiary": _count(all_interventions, "tertiary"),
        "specialist_consult_trips": trips.specialist_consult_trips,
        "trip_count": trips.trip_count,
        "access_barriers_total": len(trips.access_barriers),
        "required_interventions": len(required),
        "designed_not_required": len(designed_not_required),
        "surgery_tier": surgical_routing.tier,
    }

    return GatedPathway(
        terminal_state=loop_result.terminal_state,   # UNCHANGED
        time_infeasible=loop_result.time_infeasible,  # UNCHANGED
        required_pathway=required,
        designed_not_required_pathway=designed_not_required,
        surgical_routing=surgical_routing,
        trip_count=trips.trip_count,
        specialist_consult_trips=trips.specialist_consult_trips,
        access_barriers=trips.access_barriers,
        access_strain=trips.access_strain,
        access_summary=access_summary,
    )
