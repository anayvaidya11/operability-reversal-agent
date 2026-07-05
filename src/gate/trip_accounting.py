"""
Trip accounting for the access gate (Step 7).

The accessibility story is about minimizing travel from Sihor. Given the routed
interventions of the required-for-operability pathway plus the surgical routing, count how
many distinct trips to Bhavnagar (tertiary) the pathway implies.

BATCHING ASSUMPTION [TO VERIFY — real scheduling may differ]: interventions in the SAME
loop phase that both need tertiary can share ONE trip (they can be done on the same
visit). The final CABG is always its own tertiary trip.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config import MAX_TERTIARY_TRIPS


@dataclass
class TripAccounting:
    local_only_interventions: list = field(default_factory=list)     # RoutedIntervention
    tertiary_trip_interventions: list = field(default_factory=list)  # RoutedIntervention
    access_barriers: list = field(default_factory=list)              # RoutedIntervention
    trip_count: int = 0
    surgery_trip: int = 0            # 1 if CABG is tertiary
    intervention_trips: int = 0      # distinct tertiary phases among interventions
    access_strain: bool = False


def account_trips(required, all_interventions, surgical_routing, max_tertiary_trips=None):
    """Compute trip accounting.

    `required`: RoutedInterventions in the required-for-operability pathway (drives trips).
    `all_interventions`: required + designed-not-required (drives access-barrier scan).
    `surgical_routing`: RoutingDecision for CABG.
    """
    max_trips = MAX_TERTIARY_TRIPS if max_tertiary_trips is None else max_tertiary_trips
    acc = TripAccounting()

    for ri in required:
        if ri.routing.is_access_barrier:
            continue  # barriers are not counted as achievable trips
        if ri.routing.tier == "tertiary":
            acc.tertiary_trip_interventions.append(ri)
        elif ri.routing.tier == "local":
            acc.local_only_interventions.append(ri)

    # Access barriers scanned across the WHOLE pathway (required + designed), never dropped.
    acc.access_barriers = [ri for ri in all_interventions if ri.routing.is_access_barrier]

    # Batching: interventions sharing a loop phase that both need tertiary = one trip.
    tertiary_phases = {ri.phase_number for ri in acc.tertiary_trip_interventions}
    acc.intervention_trips = len(tertiary_phases)

    acc.surgery_trip = 1 if surgical_routing.tier == "tertiary" else 0
    acc.trip_count = acc.intervention_trips + acc.surgery_trip

    acc.access_strain = acc.trip_count > max_trips
    return acc
