"""Unit tests for the Step 6 iterative re-assessment loop."""

import json
from pathlib import Path

import pytest

from src.loop import run_reassessment_loop, TerminalState, advance_phase
from src.config import get_operability_threshold

VIGNETTES = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "vignettes.json").read_text()
)["vignettes"]
BY_ID = {v["id"]: v for v in VIGNETTES}
THR = get_operability_threshold()


def _iter(result, phase_number):
    for it in result.trace:
        if it.phase_number == phase_number:
            return it
    return None


# --- (a) grandmother: OPERABLE_AFTER_OPTIMIZATION, invisible levers don't move score --

def test_grandmother_operable_after_optimization():
    r = run_reassessment_loop(BY_ID["SYNTH-006"])
    assert r.terminal_state is TerminalState.OPERABLE_AFTER_OPTIMIZATION

    # iteration 0 records the 7.38% baseline
    assert r.trace[0].phase_number == 0
    assert abs(r.trace[0].score_after - 7.3807) < 1e-2

    # a crossing is identified and the final score is below threshold
    assert r.crossing_phase is not None
    assert r.final_score < THR

    # the phase that flips a visible lever (mobility, phase 1) moves the score down
    it1 = _iter(r, 1)
    assert it1.score_after < it1.score_before

    # hba1c is recorded as optimized-but-invisible in that same phase
    assert "hba1c" in it1.invisible_levers_optimized

    # routing hint points CABG to tertiary
    assert r.routing_hint["cabg_tier_required"] == "tertiary"


def test_invisible_lever_phase_does_not_move_score():
    # SYNTH-015 (fixed_high_risk) has only an hba1c (invisible) recommendation. Applying
    # that phase must leave the score UNCHANGED — invisible levers contribute 0.
    r = run_reassessment_loop(BY_ID["SYNTH-015"])
    it1 = _iter(r, 1)
    assert it1 is not None
    assert "hba1c" in it1.invisible_levers_optimized
    assert it1.score_after == it1.score_before   # no movement whatsoever


# --- (b) SYNTH-008: OPTIMIZED_BUT_STILL_HIGH_RISK and time_infeasible ------------------

def test_synth008_optimized_but_still_high_and_time_infeasible():
    r = run_reassessment_loop(BY_ID["SYNTH-008"])
    assert r.terminal_state is TerminalState.OPTIMIZED_BUT_STILL_HIGH_RISK
    assert r.time_infeasible is True          # 20-week plan >> 4-week urgent window
    assert r.crossing_phase is None
    assert r.baseline_score > r.final_score    # optimization genuinely helped
    assert r.final_score >= THR                # ...but never crossed
    assert abs(r.final_score - 7.45) < 0.1


# --- (c) operable at baseline: no phases run -----------------------------------------

def test_operable_at_baseline_runs_no_phases():
    r = run_reassessment_loop(BY_ID["SYNTH-001"])
    assert r.terminal_state is TerminalState.OPERABLE_AT_BASELINE
    assert r.total_weeks == 0
    assert len(r.trace) == 1                    # only iteration 0
    assert r.crossing_phase is None
    assert r.routing_hint is not None


# --- (d) fixed_high_risk, no levers: no optimization attempted ------------------------

def test_fixed_high_risk_no_levers():
    r = run_reassessment_loop(BY_ID["SYNTH-016"])
    assert r.terminal_state is TerminalState.FIXED_HIGH_RISK
    assert r.plan.phases == []
    assert r.final_score == r.baseline_score    # nothing optimized
    assert r.final_score >= THR


# --- (e) early-stop: remaining phases not applied ------------------------------------

def test_early_stop_leaves_remaining_phases_unapplied():
    r = run_reassessment_loop(BY_ID["SYNTH-006"])
    # grandmother crosses at phase 1 but the plan has 3 phases
    assert len(r.plan.phases) == 3
    assert r.crossing_phase < len(r.plan.phases)
    assert r.remaining_phases_not_required == [2, 3]
    # the loop did NOT run phases 2 or 3
    applied = {it.phase_number for it in r.trace if it.phase_number > 0}
    assert applied == {1}


# --- (f) all-18 terminal-state mapping (end-to-end correctness) -----------------------

@pytest.mark.parametrize("vid", list(BY_ID))
def test_all_vignettes_terminal_state_matches_design_intent(vid):
    v = BY_ID[vid]
    r = run_reassessment_loop(v)
    di = v["design_intent"]
    if di == "operable_at_baseline":
        assert r.terminal_state is TerminalState.OPERABLE_AT_BASELINE
    elif di == "reversible_with_optimization":
        assert r.terminal_state is TerminalState.OPERABLE_AFTER_OPTIMIZATION
    elif di == "fixed_high_risk":
        # OPTIMIZED_BUT_STILL_HIGH_RISK if it has agent-addressable levers, else FIXED
        expected = (
            TerminalState.OPTIMIZED_BUT_STILL_HIGH_RISK
            if r.plan.phases
            else TerminalState.FIXED_HIGH_RISK
        )
        assert r.terminal_state is expected
    else:
        raise AssertionError(f"unknown design_intent {di!r}")


# --- simulation unit test ------------------------------------------------------------

def test_advance_phase_flips_visible_records_invisible():
    r = run_reassessment_loop(BY_ID["SYNTH-006"])
    phase1 = r.plan.phases[0]
    inputs = dict(BY_ID["SYNTH-006"]["euroscore_inputs"])
    updated, effect = advance_phase(inputs, phase1)
    # mobility (visible) flips poor_mobility -> False
    assert updated["poor_mobility"] is False
    assert "poor_mobility" in effect.fields_changed
    assert "mobility" in effect.visible_levers_optimized
    # hba1c (invisible) recorded, inputs untouched for it
    assert "hba1c" in effect.optimized_but_invisible
    # original dict not mutated
    assert inputs["poor_mobility"] is True
