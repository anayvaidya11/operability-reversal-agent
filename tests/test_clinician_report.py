"""Tests for the Step 8 Part B clinician report + renderer."""

import json
from pathlib import Path

import pytest

from src.output import build_clinician_report, render_report_text

VIGNETTES = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "vignettes.json").read_text()
)["vignettes"]
BY_ID = {v["id"]: v for v in VIGNETTES}


# --- (a) grandmother ------------------------------------------------------------------

def test_grandmother_report():
    report = build_clinician_report(BY_ID["SYNTH-006"])
    text = render_report_text(report)

    # verdict
    assert report.verdict["terminal_state"] == "OPERABLE_AFTER_OPTIMIZATION"
    assert "PREDICTED OPERABLE AFTER OPTIMIZATION" in text

    # required crosses phase 1; designed remainder separated
    assert report.required_vs_designed["required_phases"] == [1]
    assert report.required_vs_designed["designed_not_required_phases"] == [2, 3]
    assert "DESIGNED, NOT REQUIRED FOR OPERABILITY" in text

    # glycemia-before-ICS resolution WITH rationale, in the report + audit trail
    assert any(r["rule_id"] == "RULE_GLYCEMIA_BEFORE_ICS" for r in report.applied_rules)
    assert any("RULE_GLYCEMIA_BEFORE_ICS" in a and "glucose" in a for a in report.audit_trail)

    # two-part routing: delivery local, oversight = Bhavnagar consult
    assert "delivered locally in Sihor" in text
    assert "endocrinologist consult in Bhavnagar" in text

    # trip count present
    assert report.access_summary["trip_count"] == 3
    assert "trip(s) to Bhavnagar" in text

    # header + decision-support framing
    assert "DECISION SUPPORT ONLY" in text
    assert "SYNTHETIC DATA" in text

    # [TO VERIFY] / MODELING ASSUMPTIONS visibly rendered
    assert "[TO VERIFY]" in text
    assert "MODELING ASSUMPTIONS" in text
    assert len(report.to_verify_markers) > 0

    # Step-9 sourcing: CITED claims rendered as sourced (clinician-verify)
    assert "CLINICAL SOURCING — CITED" in text
    assert len(report.sourced_citations) > 0
    assert any("[CITED" in c for c in report.sourced_citations)


# --- (b) SYNTH-008: no operability claim ---------------------------------------------

def test_synth008_report_no_operability_claim():
    report = build_clinician_report(BY_ID["SYNTH-008"])
    text = render_report_text(report)

    assert report.verdict["terminal_state"] == "OPTIMIZED_BUT_STILL_HIGH_RISK"
    assert "NOT operable on this pathway" in text
    # never claims operability
    assert "PREDICTED OPERABLE AFTER OPTIMIZATION" not in text
    assert "OPERABLE AT BASELINE" not in text
    # both flags + tier routing present
    assert any("TIME_INFEASIBLE" in f for f in report.verdict["flags"])
    assert "Requires trip to Bhavnagar" in text
    assert report.access_summary["trip_count"] == 3


# --- (c) FIXED_HIGH_RISK: honest "no pathway" ----------------------------------------

def test_fixed_high_risk_report_no_fabricated_pathway():
    report = build_clinician_report(BY_ID["SYNTH-016"])
    text = render_report_text(report)
    assert report.verdict["terminal_state"] == "FIXED_HIGH_RISK"
    assert "NO MODIFIABLE PATHWAY" in text
    assert report.optimization_pathway == []          # nothing fabricated
    assert "no optimization pathway" in text


# --- (d) renders on all 18 without error ---------------------------------------------

@pytest.mark.parametrize("vid", list(BY_ID))
def test_report_renders_on_every_vignette(vid):
    report = build_clinician_report(BY_ID[vid])
    text = render_report_text(report)
    assert "DECISION SUPPORT ONLY" in text          # header always present
    assert "AUDIT TRAIL" in text                    # audit trail always present
    assert report.audit_trail
    assert isinstance(report.to_dict(), dict)
