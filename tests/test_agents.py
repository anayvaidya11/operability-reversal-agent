"""Unit tests for the three specialist agents and the runner (Step 4)."""

import json
from pathlib import Path

import pytest

from src.decomposer import decompose
from src.feasibility import FeasibilityStatus
from src.agents import cardiac_agent, endocrine_agent, pulmonary_agent
from src.agents.run_specialists import run_all_specialists

VIGNETTES = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "vignettes.json").read_text()
)["vignettes"]
BY_ID = {v["id"]: v for v in VIGNETTES}


def _levers(rec):
    return {r.lever for r in rec.recommendations}


def _has(warnings, needle):
    return any(needle in w for w in warnings)


# --- (a) grandmother through all three agents ----------------------------------------

def test_grandmother_cardiac():
    v = BY_ID["SYNTH-006"]
    r = cardiac_agent.run(v, decompose(v))
    assert _levers(r) == {"mobility", "heart_failure_symptoms"}
    assert _has(r.warnings, "Beta-blocker titration in asthma")
    # flags fixed cardiac factors
    assert any("coronary anatomy" in f for f in r.out_of_scope_flags)
    assert any("lv_function" in f for f in r.out_of_scope_flags)


def test_grandmother_endocrine():
    v = BY_ID["SYNTH-006"]
    r = endocrine_agent.run(v, decompose(v))
    assert _levers(r) == {"hba1c"}
    assert _has(r.warnings, "cold-chain")           # insulin cold-chain warning
    assert _has(r.warnings, "Option B deferred")    # Option-B invisibility warning
    assert any("diabetes_on_insulin is a fixed" in f for f in r.out_of_scope_flags)
    # hba1c does not move the EuroSCORE score
    assert r.recommendations[0].euroscore_field is None


def test_grandmother_pulmonary():
    v = BY_ID["SYNTH-006"]
    r = pulmonary_agent.run(v, decompose(v))
    assert _levers(r) == {"asthma_control"}          # grandmother does not smoke
    assert _has(r.warnings, "ICS dose increase will worsen glycemic control")
    assert r.recommendations[0].euroscore_field == "chronic_lung_disease"


# --- (b) SYNTH-001 operable at baseline: all agents empty ----------------------------

def test_synth001_all_agents_empty():
    v = BY_ID["SYNTH-001"]
    d = decompose(v)
    assert cardiac_agent.run(v, d).recommendations == []
    assert endocrine_agent.run(v, d).recommendations == []
    assert pulmonary_agent.run(v, d).recommendations == []


# --- (c) SYNTH-009 smoker + asthma: pulmonary returns both ---------------------------

def test_synth009_pulmonary_both_levers():
    v = BY_ID["SYNTH-009"]
    r = pulmonary_agent.run(v, decompose(v))
    assert _levers(r) == {"asthma_control", "smoking_status"}
    assert _has(r.warnings, "Nicotine replacement therapy")


# --- (d) SYNTH-014 fixed_high_risk: all empty, fixed factors flagged ------------------

def test_synth014_all_empty_fixed_flagged():
    v = BY_ID["SYNTH-014"]
    d = decompose(v)
    cardiac = cardiac_agent.run(v, d)
    endocrine = endocrine_agent.run(v, d)
    pulmonary = pulmonary_agent.run(v, d)
    assert cardiac.recommendations == []
    assert endocrine.recommendations == []
    assert pulmonary.recommendations == []
    # cardiac notes the fixed factors it observed
    assert cardiac.out_of_scope_flags
    assert any("previous_cardiac_surgery" in f for f in cardiac.out_of_scope_flags)
    assert any("recent_mi" in f for f in cardiac.out_of_scope_flags)


# --- (e) feasibility integration: grandmother recs are never UNAVAILABLE --------------

def test_grandmother_recommendations_are_reachable():
    v = BY_ID["SYNTH-006"]
    results = run_all_specialists(v, decompose(v))
    all_recs = [r for sr in results.values() for r in sr.recommendations]
    assert all_recs  # she has recommendations
    for rec in all_recs:
        assert rec.feasibility.status is not FeasibilityStatus.UNAVAILABLE
        assert rec.tier_required in ("local", "tertiary")


# --- (f) runner returns all three keys and completes on every vignette ----------------

@pytest.mark.parametrize("vid", list(BY_ID))
def test_run_all_specialists_on_every_vignette(vid):
    v = BY_ID[vid]
    results = run_all_specialists(v, decompose(v))
    assert set(results) == {"cardiac", "endocrine", "pulmonary"}
    for sr in results.values():
        assert sr.specialty in ("cardiac", "endocrine", "pulmonary")


def test_runner_reraises_with_context_on_bad_vignette():
    from src.agents.run_specialists import SpecialistAgentError
    bad = {"id": "BAD", "location_tier": "local"}  # missing euroscore_inputs
    with pytest.raises(SpecialistAgentError, match="BAD"):
        # decompose would also fail, so hand it a minimally-valid decomposition-like call:
        from src.decomposer import DecompositionResult
        run_all_specialists(bad, DecompositionResult(vignette_id="BAD"))
