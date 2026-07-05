"""
Plain-text / markdown renderer for a ClinicianReport (Step 8, Part B).

render_report_text(report) -> str. Clean, sectioned, readable. A compact
"pathway at a glance" sits near the top; the full audit trail at the bottom. Every
[TO VERIFY] clinical value is rendered visibly — unsourced numbers are never presented
as if confirmed.
"""

from __future__ import annotations


def _hr(title: str) -> str:
    return f"\n{'=' * 78}\n{title}\n{'=' * 78}"


def render_report_text(report) -> str:
    L: list[str] = []

    L.append(f"OPERABILITY REVERSAL AGENT — CLINICIAN DECISION-SUPPORT REPORT")
    L.append(f"Patient (synthetic): {report.vignette_id}")
    for h in report.header:
        L.append(f"  ⚠ {h}")

    # --- pathway at a glance ---
    v = report.verdict
    acc = report.access_summary
    L.append(_hr("PATHWAY AT A GLANCE"))
    L.append(f"Verdict     : {v['plain_language']}")
    L.append(f"Risk        : baseline {v['baseline_pct']}%  ->  final {v['final_pct']}%  "
             f"(threshold {report.patient_summary['operability_threshold_pct']}%)")
    if v.get("crossing_phase") is not None:
        L.append(f"Crossing    : predicted operable at phase {v['crossing_phase']}")
    L.append(f"Access      : {acc.get('trip_count')} trip(s) to Bhavnagar "
             f"({acc.get('specialist_consult_trips')} specialist consult(s) + surgery); "
             f"delivery local x{acc.get('delivery_local')}")
    if v["flags"]:
        for f in v["flags"]:
            L.append(f"FLAG        : {f}")

    # --- patient summary ---
    ps = report.patient_summary
    L.append(_hr("PATIENT SUMMARY"))
    L.append(f"Indication  : {ps['indication']}")
    L.append(f"Coronary    : {ps['coronary_disease_extent']}")
    L.append(f"Age / sex   : {ps['age']} / {ps['sex']}")
    L.append(f"Comorbid.   : {', '.join(ps['comorbidities_present']) or 'none recorded'}")
    L.append(f"Baseline    : EuroSCORE II {ps['baseline_euroscore_ii_pct']}%  "
             f"(declined at baseline: {ps['declined_at_baseline']})")

    # --- risk decomposition ---
    rd = report.risk_decomposition
    L.append(_hr("RISK DECOMPOSITION"))
    L.append("Fixed factors (cannot change):")
    L.append("  " + ", ".join(f"{k}={rd['fixed_factors_cannot_change'][k]}"
                              for k in sorted(rd['fixed_factors_cannot_change'])))
    L.append("Modifiable, visible to score:")
    for m in rd["modifiable_visible_to_score"]:
        L.append(f"  - {m['lever']} (EuroSCORE field {m['euroscore_field']}, currently {m['current']})")
    L.append("Modifiable, INVISIBLE to score (Option B deferred):")
    L.append("  " + (", ".join(rd["modifiable_invisible_to_score_option_b"]) or "none"))
    L.append(f"  {rd['note']}")

    # --- optimization pathway ---
    L.append(_hr("OPTIMIZATION PATHWAY"))
    if not report.optimization_pathway:
        L.append("  (no optimization pathway — see verdict)")
    for ph in report.optimization_pathway:
        tag = "REQUIRED FOR OPERABILITY" if ph["status"] == "required" else "DESIGNED, NOT REQUIRED FOR OPERABILITY"
        L.append(f"\nPhase {ph['phase_number']}  ({ph['duration_weeks']} weeks)  [{tag}]")
        for iv in ph["interventions"]:
            L.append(f"  • {iv['access_description']}")
        for mn in ph["monitoring_notes"]:
            L.append(f"    monitor: {mn}")

    # applied conflict-resolution rules
    if report.applied_rules:
        L.append("\nApplied conflict-resolution rules:")
        for r in report.applied_rules:
            L.append(f"  - {r['rule_id']} (order {r['ordering']}): {r['rationale']}")
            L.append(f"      SOURCE: {r['source']}")

    # --- required vs designed ---
    rvd = report.required_vs_designed
    L.append(_hr("REQUIRED vs DESIGNED"))
    L.append(f"Required phases (to reach operability) : {rvd['required_phases']}")
    L.append(f"Designed but not required             : {rvd['designed_not_required_phases']}")
    L.append(f"  {rvd['remaining_not_required_note']}")

    # --- access summary ---
    L.append(_hr("ACCESS SUMMARY (Sihor vs Bhavnagar)"))
    L.append(f"Delivery local (Sihor)     : {acc.get('delivery_local')} intervention(s)")
    L.append(f"Delivery tertiary          : {acc.get('delivery_tertiary')} intervention(s)")
    L.append(f"Specialist consult trips   : {acc.get('specialist_consult_trips')}")
    L.append(f"Surgery routing            : {acc.get('surgical_routing')}")
    L.append(f"Total trips to Bhavnagar   : {acc.get('trip_count')}")
    L.append(f"Access barriers            : {acc.get('access_barriers_total')}")
    L.append(f"Access strain              : {acc.get('access_strain')}")

    # --- confirmation flags ---
    L.append(_hr("CONFIRMATION REQUIRED (decision support only)"))
    for c in report.confirmation_flags:
        L.append(f"  ☐ {c}")

    # --- clinical sourcing (Step 9) ---
    L.append(_hr("CLINICAL SOURCING — CITED (clinician-verify before real use)"))
    if report.sourced_citations:
        for c in report.sourced_citations:
            L.append(f"  ✓ {c}")
    else:
        L.append("  (no cited clinical claims used for this patient)")

    L.append(_hr("[TO VERIFY] / MODELING ASSUMPTIONS — SURFACED (not confirmed)"))
    for t in report.to_verify_markers:
        L.append(f"  ! {t}")

    # --- audit trail ---
    L.append(_hr("AUDIT TRAIL (show your work)"))
    for a in report.audit_trail:
        L.append(f"  {a}")

    return "\n".join(L)
