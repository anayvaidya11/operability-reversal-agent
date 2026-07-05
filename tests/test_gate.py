"""Unit tests for the Step 7 access gate + Step 8 Part A specialist-scarcity layer."""

import json
from pathlib import Path

import pytest

from src.loop import run_reassessment_loop, TerminalState
from src.gate import (
    apply_access_gate,
    route_capabilities,
    route_oversight,
    account_trips,
    RoutedIntervention,
    RoutingDecision,
)
from src.feasibility import FeasibilityStatus

VIGNETTES = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "vignettes.json").read_text()
)["vignettes"]
BY_ID = {v["id"]: v for v in VIGNETTES}


def _by_lever(pathway):
    return {r.lever: r for r in pathway}


def _write_profile(tmp_path, cap_id, local, tertiary):
    profile = {
        "_meta": {"synthetic": True},
        "tiers": {"local": {"tier": 1}, "tertiary": {"tier": 2}},
        "capabilities": [{
            "capability_id": cap_id, "category": "specialist_availability",
            "description": "synthetic", "local_available": local,
            "tertiary_available": tertiary, "notes": "[TO VERIFY] synthetic",
        }],
    }
    f = tmp_path / f"{cap_id}.json"
    f.write_text(json.dumps(profile))
    return str(f)


# --- grandmother: two-part routing, thesis property ----------------------------------

def test_grandmother_delivery_local_oversight_specialist():
    g = apply_access_gate(run_reassessment_loop(BY_ID["SYNTH-006"]))
    assert g.terminal_state is TerminalState.OPERABLE_AFTER_OPTIMIZATION  # A4b: unchanged

    req = _by_lever(g.required_pathway)
    des = _by_lever(g.designed_not_required_pathway)

    # glycemic: delivery local, oversight endocrinologist consult in Bhavnagar
    hba1c = req["hba1c"]
    assert hba1c.delivery_routing.tier == "local"
    assert hba1c.oversight_capability == "endocrinologist"
    assert hba1c.oversight_routing.tier == "tertiary"
    assert "endocrinologist consult in Bhavnagar" in hba1c.access_description

    # pulmonary (in the designed-not-required tail): delivery local, oversight pulmonologist
    asthma = des["asthma_control"]
    assert asthma.delivery_routing.tier == "local"
    assert asthma.oversight_capability == "pulmonologist"
    assert asthma.oversight_routing.tier == "tertiary"

    # mobility has no specialist
    assert req["mobility"].oversight_capability is None
    assert req["mobility"].oversight_routing is None


def test_grandmother_thesis_property_all_delivery_local():
    # A4d: ALL delivery is local (Sihor). Only specialist consults + surgery need Bhavnagar.
    g = apply_access_gate(run_reassessment_loop(BY_ID["SYNTH-006"]))
    for ri in g.required_pathway + g.designed_not_required_pathway:
        assert ri.delivery_routing.tier == "local", ri.lever
    assert g.surgical_routing.tier == "tertiary"


def test_grandmother_trip_count_consults_plus_cabg():
    # A4a: endocrinology (P1) + pulmonology (P2) consults + CABG; cardiac oversight folds
    # into the CABG episode. 2 consult trips + 1 surgery = 3.
    g = apply_access_gate(run_reassessment_loop(BY_ID["SYNTH-006"]))
    assert g.specialist_consult_trips == 2
    assert g.trip_count == 3
    assert g.access_strain is False


# --- SYNTH-008 ------------------------------------------------------------------------

def test_synth008_gated_preserves_flags():
    g = apply_access_gate(run_reassessment_loop(BY_ID["SYNTH-008"]))
    crit = _by_lever(g.required_pathway)["critical_preop_stabilization"]
    assert crit.delivery_routing.tier == "tertiary"     # cardiac_icu tertiary-only
    assert g.terminal_state is TerminalState.OPTIMIZED_BUT_STILL_HIGH_RISK
    assert g.time_infeasible is True
    assert g.trip_count == 3


# --- specialist access barrier (A4c) -------------------------------------------------

def test_specialist_access_barrier_flagged(tmp_path):
    profile = _write_profile(tmp_path, "endocrinologist", "no", "no")
    decision = route_oversight("endocrinologist", "local", profile_path=profile)
    assert decision.status is FeasibilityStatus.UNAVAILABLE
    assert decision.is_access_barrier is True
    assert "SPECIALIST ACCESS BARRIER" in decision.routing_label


# --- delivery access barrier flagged, not dropped ------------------------------------

def test_delivery_access_barrier_flagged_not_dropped(tmp_path):
    profile = _write_profile(tmp_path, "blocked", "no", "no")
    d = route_capabilities(["blocked"], "local", profile_path=profile)
    assert d.status is FeasibilityStatus.UNAVAILABLE
    assert d.is_access_barrier is True
    barrier = RoutedIntervention("x", 1, ["blocked"], d, None, None, "desc")
    acc = account_trips([barrier], _tertiary_surgery())
    assert (barrier, "delivery") in acc.access_barriers


# --- most-restrictive-wins -----------------------------------------------------------

def test_most_restrictive_wins():
    d = route_capabilities(["ecg", "cabg"], "local")   # ecg local, cabg tertiary
    assert d.tier == "tertiary"
    assert d.status is FeasibilityStatus.NEEDS_TERTIARY


# --- trip accounting: batching + cardiac fold ----------------------------------------

def _local():
    return RoutingDecision(FeasibilityStatus.LOCAL, "loc", "local", False, False, "gp", "n")


def _consult(cap):
    return RoutingDecision(FeasibilityStatus.NEEDS_TERTIARY, "consult", "tertiary", False, False, cap, "n")


def _ri(lever, phase, oversight_cap):
    ov = _consult(oversight_cap) if oversight_cap else None
    return RoutedIntervention(lever, phase, ["gp"], _local(), oversight_cap, ov, "d")


def _tertiary_surgery():
    return RoutingDecision(FeasibilityStatus.NEEDS_TERTIARY, "Requires trip to Bhavnagar",
                           "tertiary", False, False, "cabg", "n")


def test_two_noncardiac_consults_same_phase_batch():
    a = _ri("hba1c", 1, "endocrinologist")
    b = _ri("asthma_control", 1, "pulmonologist")   # same phase -> batched
    acc = account_trips([a, b], _tertiary_surgery())
    assert acc.specialist_consult_trips == 1
    assert acc.trip_count == 2                        # one consult trip + CABG


def test_two_noncardiac_consults_diff_phase_two_trips():
    a = _ri("hba1c", 1, "endocrinologist")
    b = _ri("asthma_control", 2, "pulmonologist")
    acc = account_trips([a, b], _tertiary_surgery())
    assert acc.specialist_consult_trips == 2
    assert acc.trip_count == 3


def test_cardiac_oversight_folds_into_cabg_trip():
    a = _ri("heart_failure_symptoms", 3, "cardiologist")  # cardiac -> folds into CABG
    acc = account_trips([a], _tertiary_surgery())
    assert acc.specialist_consult_trips == 0
    assert acc.trip_count == 1                             # just the CABG


# --- access_strain orthogonal --------------------------------------------------------

def test_access_strain_orthogonal_to_clinical_state():
    r = run_reassessment_loop(BY_ID["SYNTH-008"])   # trip_count == 3
    g = apply_access_gate(r, max_tertiary_trips=1)   # budget 1 -> strained
    assert g.access_strain is True
    assert g.terminal_state is TerminalState.OPTIMIZED_BUT_STILL_HIGH_RISK  # unchanged
    assert g.time_infeasible is True


# --- full suite ----------------------------------------------------------------------

@pytest.mark.parametrize("vid", list(BY_ID))
def test_gate_completes_on_every_vignette(vid):
    g = apply_access_gate(run_reassessment_loop(BY_ID[vid]))
    s = g.access_summary
    assert set(s) >= {"delivery_local", "delivery_tertiary", "specialist_consult_trips",
                      "trip_count", "access_barriers_total"}
    assert s["trip_count"] == g.trip_count
    assert g.surgical_routing is not None
