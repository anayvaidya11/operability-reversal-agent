"""
Trip accounting for the access gate (Step 7, extended Step 8 Part A).

Counts distinct trips to Bhavnagar (tertiary) implied by the pathway, now including
specialist oversight consults.

BATCHING ASSUMPTIONS [TO VERIFY — real scheduling may differ; conservative where unsure]:
  1. Cardiac-domain tertiary requirements (cardiologist oversight, cardiac_icu, the CABG)
     belong to the ONE tertiary cardiac-care episode — the patient is already at the
     Bhavnagar cardiac unit for the operation, so they do NOT add a separate trip.
  2. Non-cardiac specialist consults / tertiary deliveries in the SAME loop phase share one
     trip; consults in DIFFERENT phases are counted separately (conservative).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config import MAX_TERTIARY_TRIPS
from src.gate.intervention_capabilities import CARDIAC_DOMAIN_CAPABILITIES


@dataclass
class TripAccounting:
    local_only_interventions: list = field(default_factory=list)
    tertiary_delivery_interventions: list = field(default_factory=list)
    specialist_consult_interventions: list = field(default_factory=list)
    access_barriers: list = field(default_factory=list)   # (RoutedIntervention, "delivery"|"oversight")
    specialist_consult_trips: int = 0     # distinct non-cardiac consult trips (phase-batched)
    non_cardiac_delivery_trips: int = 0   # distinct non-cardiac tertiary-delivery trips
    surgery_trip: int = 0                 # 1 (CABG)
    trip_count: int = 0
    access_strain: bool = False


def _is_cardiac(cap) -> bool:
    return cap in CARDIAC_DOMAIN_CAPABILITIES


def account_trips(interventions, surgical_routing, max_tertiary_trips=None):
    """Compute trip accounting over `interventions` (the full designed pathway) plus the
    CABG. Cardiac-domain tertiary work folds into the CABG trip; non-cardiac tertiary work
    is phase-batched."""
    max_trips = MAX_TERTIARY_TRIPS if max_tertiary_trips is None else max_tertiary_trips
    acc = TripAccounting()

    non_cardiac_delivery_phases: set[int] = set()
    non_cardiac_consult_phases: set[int] = set()

    for ri in interventions:
        d = ri.delivery_routing
        # delivery
        if d.is_access_barrier:
            acc.access_barriers.append((ri, "delivery"))
        elif d.tier == "tertiary":
            acc.tertiary_delivery_interventions.append(ri)
            if not _is_cardiac(d.governing_capability):
                non_cardiac_delivery_phases.add(ri.phase_number)
        elif d.tier == "local":
            acc.local_only_interventions.append(ri)

        # oversight consult
        o = ri.oversight_routing
        if o is not None:
            if o.is_access_barrier:
                acc.access_barriers.append((ri, "oversight"))
            elif o.tier == "tertiary":
                acc.specialist_consult_interventions.append(ri)
                if not _is_cardiac(ri.oversight_capability):
                    non_cardiac_consult_phases.add(ri.phase_number)

    acc.non_cardiac_delivery_trips = len(non_cardiac_delivery_phases)
    acc.specialist_consult_trips = len(non_cardiac_consult_phases)
    acc.surgery_trip = 1 if surgical_routing.tier == "tertiary" else 0

    # distinct non-cardiac tertiary trips (delivery or consult) batched by phase
    non_cardiac_trips = len(non_cardiac_delivery_phases | non_cardiac_consult_phases)
    acc.trip_count = non_cardiac_trips + acc.surgery_trip
    acc.access_strain = acc.trip_count > max_trips
    return acc
