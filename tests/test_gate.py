"""Unit tests for the Step 7 access gate."""

import json
from pathlib import Path

import pytest

from src.loop import run_reassessment_loop, TerminalState
from src.gate import (
    apply_access_gate,
    route_capabilities,
    route_intervention,
    account_trips,
    RoutedIntervention,
    RoutingDecision,
)
from src.gate.trip_accounting import account_trips as _account
from src.feasibility import FeasibilityStatus

VIGNETTES = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "vignettes.json").read_text()
)["vignettes"]
BY_ID = {v["id"]: v for v in VIGNETTES}


def _levers(routed):
    return {r.lever for r in routed}


# --- (a) grandmother -----------------------------------------------------------------

def test_grandmother_gated_pathway():
    r = run_reassessment_loop(BY_ID["SYNTH-006"])
    g = apply_access_gate(r)

    # clinical verdict unchanged by gating
    assert g.terminal_state is TerminalState.OPERABLE_AFTER_OPTIMIZATION

    # required-for-operability set = phase 1 (mobility crossing), both local
    assert _levers(g.required_pathway) == {"hba1c", "mobility"}
    for ri in g.required_pathway:
        assert ri.routing.tier == "local"
    # prehabilitation is "partial" at both tiers -> flagged
    mob = [ri for ri in g.required_pathway if ri.lever == "mobility"][0]
    assert mob.routing.status is FeasibilityStatus.PARTIAL_LOCAL
    assert mob.routing.flagged is True

    # designed-but-not-required remainder clearly separated
    assert _levers(g.designed_not_required_pathway) == {"asthma_control", "heart_failure_symptoms"}

    # CABG -> tertiary (Bhavnagar); one trip total
    assert g.surgical_routing.tier == "tertiary"
    assert g.trip_count == 1
    assert g.access_summary["required_tertiary_trip"] == 0
    assert g.access_strain is False


# --- (b) SYNTH-008 -------------------------------------------------------------------

def test_synth008_gated_pathway_preserves_flags():
    r = run_reassessment_loop(BY_ID["SYNTH-008"])
    g = apply_access_gate(r)

    crit = [ri for ri in g.required_pathway if ri.lever == "critical_preop_stabilization"][0]
    assert crit.routing.tier == "tertiary"                 # cardiac_icu is tertiary-only

    # clinical flags survive gating
    assert g.terminal_state is TerminalState.OPTIMIZED_BUT_STILL_HIGH_RISK
    assert g.time_infeasible is True
    assert g.surgical_routing.tier == "tertiary"
    assert g.trip_count == 2                                # critical_preop stage + CABG


# --- (c) access barrier: unavailable at both tiers, flagged not dropped ---------------

def test_access_barrier_flagged_not_dropped(tmp_path):
    profile = {
        "_meta": {"synthetic": True},
        "tiers": {"local": {"tier": 1}, "tertiary": {"tier": 2}},
        "capabilities": [
            {
                "capability_id": "blocked_capability",
                "category": "procedures",
                "description": "synthetic no/no capability",
                "local_available": "no",
                "tertiary_available": "no",
                "notes": "[TO VERIFY] synthetic",
            }
        ],
    }
    f = tmp_path / "profile.json"
    f.write_text(json.dumps(profile))

    decision = route_capabilities(["blocked_capability"], "local", profile_path=str(f))
    assert decision.status is FeasibilityStatus.UNAVAILABLE
    assert decision.is_access_barrier is True
    assert "ACCESS BARRIER" in decision.routing_label

    # in trip accounting it is surfaced, not dropped
    barrier = RoutedIntervention("x", 1, ["blocked_capability"], decision)
    acc = account_trips([barrier], [barrier], _local_surgery())
    assert barrier in acc.access_barriers
    assert barrier not in acc.tertiary_trip_interventions
    assert barrier not in acc.local_only_interventions


def _local_surgery():
    return RoutingDecision(
        FeasibilityStatus.LOCAL, "local", "local", False, False, "x", "n")


# --- (d) most-restrictive-wins -------------------------------------------------------

def test_most_restrictive_wins():
    # ecg is local (yes); cabg needs tertiary. The intervention routes to tertiary.
    decision = route_capabilities(["ecg", "cabg"], "local")
    assert decision.tier == "tertiary"
    assert decision.status is FeasibilityStatus.NEEDS_TERTIARY


# --- (e) trip accounting: batching within a phase; CABG adds its own trip -------------

def _tertiary(lever, phase):
    dec = RoutingDecision(
        FeasibilityStatus.NEEDS_TERTIARY, "Requires trip to Bhavnagar", "tertiary",
        False, False, "cardiac_icu", "n")
    return RoutedIntervention(lever, phase, ["cardiac_icu"], dec)


def _tertiary_surgery():
    return RoutingDecision(
        FeasibilityStatus.NEEDS_TERTIARY, "Requires trip to Bhavnagar", "tertiary",
        False, False, "cabg", "n")


def test_two_tertiary_same_phase_share_one_trip():
    a = _tertiary("t1", 1)
    b = _tertiary("t2", 1)   # same phase -> batched
    acc = account_trips([a, b], [a, b], _tertiary_surgery())
    assert acc.intervention_trips == 1     # batched into one visit
    assert acc.surgery_trip == 1
    assert acc.trip_count == 2             # one intervention trip + CABG trip


def test_two_tertiary_different_phases_two_trips():
    a = _tertiary("t1", 1)
    b = _tertiary("t2", 2)   # different phases -> two visits
    acc = account_trips([a, b], [a, b], _tertiary_surgery())
    assert acc.intervention_trips == 2
    assert acc.trip_count == 3


# --- (f) access_strain fires orthogonally, does not change clinical verdict -----------

def test_access_strain_orthogonal_to_clinical_state():
    r = run_reassessment_loop(BY_ID["SYNTH-008"])   # trip_count == 2
    g = apply_access_gate(r, max_tertiary_trips=1)   # budget of 1 -> strained
    assert g.access_strain is True
    assert g.terminal_state is TerminalState.OPTIMIZED_BUT_STILL_HIGH_RISK  # unchanged
    assert g.time_infeasible is True                                        # unchanged


# --- (g) full-suite: completes on all 18 with a coherent summary ----------------------

@pytest.mark.parametrize("vid", list(BY_ID))
def test_gate_completes_on_every_vignette(vid):
    g = apply_access_gate(run_reassessment_loop(BY_ID[vid]))
    s = g.access_summary
    assert set(s) >= {"required_local", "required_tertiary_trip", "required_barrier",
                      "designed_not_required", "access_barriers_total", "trip_count"}
    # summary internally consistent
    assert s["required_tertiary_trip"] == len(
        [r for r in g.required_pathway if r.routing.tier == "tertiary"])
    assert s["trip_count"] == g.trip_count
    assert g.surgical_routing is not None
