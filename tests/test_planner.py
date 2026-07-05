"""Unit tests for the Step 5 planner: conflicts, resolution, sequencing."""

import copy
import json
from pathlib import Path

import pytest

from src.decomposer import decompose
from src.agents.run_specialists import run_all_specialists
from src.planner import detect_conflicts, resolve_conflicts, build_sequence
from src.planner.conflicts import Conflict
from src.planner.resolution_rules import UNRESOLVED

VIGNETTES = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "vignettes.json").read_text()
)["vignettes"]
BY_ID = {v["id"]: v for v in VIGNETTES}


def _pipeline(vignette):
    outs = run_all_specialists(vignette, decompose(vignette))
    conflicts = detect_conflicts(outs)
    resolutions = resolve_conflicts(conflicts, outs)
    plan = build_sequence(vignette, outs, resolutions)
    return outs, conflicts, resolutions, plan


def _phase_of_lever(plan, lever):
    for p in plan.phases:
        if any(r.lever == lever for r in p.interventions):
            return p.phase_number
    return None


# --- (a) grandmother: ICS<->glycemia detected, resolved, sequenced glycemia-first -----

def test_grandmother_ics_glycemia_detected_and_sequenced():
    v = BY_ID["SYNTH-006"]
    outs, conflicts, resolutions, plan = _pipeline(v)

    ics = [c for c in conflicts if c.mechanism == "steroid_hyperglycemia"]
    assert len(ics) == 1
    c = ics[0]
    assert c.kind == "clinical_interaction"
    assert c.severity == "ordering"
    assert set(c.parties) == {("endocrine", "hba1c"), ("pulmonary", "asthma_control")}

    assert any(r.rule_id == "RULE_GLYCEMIA_BEFORE_ICS" for r in resolutions.resolutions)
    assert resolutions.unresolved == []

    # glycemia phase strictly precedes ICS phase
    assert _phase_of_lever(plan, "hba1c") < _phase_of_lever(plan, "asthma_control")
    # mobility and NYHA optimization are placed somewhere
    assert _phase_of_lever(plan, "mobility") is not None
    assert _phase_of_lever(plan, "heart_failure_symptoms") is not None
    assert plan.total_duration_weeks > 0
    assert plan.urgency == "elective"
    assert plan.urgency_warning is None


def test_grandmother_detects_betablocker_asthma_too():
    v = BY_ID["SYNTH-006"]
    _, conflicts, resolutions, plan = _pipeline(v)
    bb = [c for c in conflicts if c.mechanism == "betablocker_bronchospasm"]
    assert len(bb) == 1
    assert set(bb[0].parties) == {("cardiac", "heart_failure_symptoms"), ("pulmonary", "asthma_control")}
    # pulmonary control precedes the beta-blocker (heart_failure) phase
    assert _phase_of_lever(plan, "asthma_control") < _phase_of_lever(plan, "heart_failure_symptoms")


def test_grandmother_structural_flag_not_text():
    # The ICS<->glycemia detection is driven by a STRUCTURED cross_specialty_flag, not NLP.
    outs = run_all_specialists(BY_ID["SYNTH-006"], decompose(BY_ID["SYNTH-006"]))
    asthma = [r for r in outs["pulmonary"].recommendations if r.lever == "asthma_control"][0]
    assert {"interacts_with": "endocrine", "target_lever": "hba1c",
            "mechanism": "steroid_hyperglycemia", "direction": "worsens"} in asthma.cross_specialty_flags


# --- (b) SYNTH-008: real plan produced, no operability claim --------------------------

def test_synth008_plan_produced_without_operability_claim():
    v = BY_ID["SYNTH-008"]
    _, conflicts, resolutions, plan = _pipeline(v)
    assert plan.phases                       # a real sequence exists
    all_levers = {r.lever for p in plan.phases for r in p.interventions}
    assert {"critical_preop_stabilization", "asthma_control", "hba1c"} <= all_levers
    # the planner sequences only — it makes no operability verdict
    fields = set(vars(plan))
    assert not any(k in fields for k in ("operable", "crosses_threshold", "operability"))


# --- (c) no-conflict case ------------------------------------------------------------

def test_no_conflict_operable_baseline_empty_plan():
    v = BY_ID["SYNTH-001"]
    outs, conflicts, resolutions, plan = _pipeline(v)
    assert conflicts == []
    assert plan.phases == []
    assert plan.total_duration_weeks == 0
    assert plan.urgency_warning is None


# --- (d) urgency stress test ---------------------------------------------------------

def test_urgency_warning_fires_and_names_truncated_phases():
    v = BY_ID["SYNTH-006"]
    outs = run_all_specialists(v, decompose(v))
    resolutions = resolve_conflicts(detect_conflicts(outs), outs)
    # synthetic urgent copy — do NOT edit vignettes.json
    urgent = copy.deepcopy(v)
    urgent["euroscore_inputs"]["urgency"] = "urgent"
    plan = build_sequence(urgent, outs, resolutions)
    assert plan.total_duration_weeks > 4
    assert plan.urgency_warning is not None
    assert "truncated" in plan.urgency_warning
    # names specific phase numbers
    assert any(str(p.phase_number) in plan.urgency_warning for p in plan.phases)


# --- (e) UNRESOLVED path -------------------------------------------------------------

def test_unresolved_conflict_is_escalated_not_dropped():
    bogus = Conflict(
        conflict_id="clinical_interaction|made_up|x",
        kind="clinical_interaction",
        parties=[("cardiac", "mobility"), ("pulmonary", "asthma_control")],
        description="synthetic conflict with no matching rule",
        source_signal="agent_warning",
        severity="ordering",
        mechanism="made_up_mechanism",
    )
    result = resolve_conflicts([bogus], {})
    assert result.resolutions == []
    assert len(result.unresolved) == 1
    assert bogus.resolution == UNRESOLVED


# --- runner-wide: no real vignette produces an UNRESOLVED conflict --------------------

@pytest.mark.parametrize("vid", list(BY_ID))
def test_no_unresolved_conflicts_on_real_vignettes(vid):
    _, _, resolutions, _ = _pipeline(BY_ID[vid])
    assert resolutions.unresolved == [], (vid, [c.conflict_id for c in resolutions.unresolved])
