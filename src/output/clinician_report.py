"""
Clinician-facing report assembly (Step 8, Part B).

build_clinician_report(vignette) runs the full deterministic pipeline
(decompose -> specialists -> conflicts -> sequence -> loop -> gate + scarcity) and
assembles a structured, serializable ClinicianReport with a full audit trail. Decision
SUPPORT only — never autonomous advice; every clinical step is flagged for specialist
confirmation and every [TO VERIFY] value is surfaced, not hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

from src.config import get_operability_threshold
from src.decomposer import decompose
from src.agents.run_specialists import run_all_specialists
from src.planner import detect_conflicts, resolve_conflicts
from src.planner.resolution_rules import REGISTRY
from src.loop import run_reassessment_loop, TerminalState
from src.gate import apply_access_gate
from src.gate.intervention_capabilities import LEVER_DISPLAY

_RULE_SOURCE = {r.rule_id: r.source for r in REGISTRY}

HEADER = [
    "SYNTHETIC DATA — this patient is fictional. No real patient data is used or represented.",
    "DECISION SUPPORT ONLY — not a medical device, not clinically validated, "
    "not a substitute for clinical judgement.",
    "The responsible clinician must confirm every step before any action. This tool never "
    "speaks to a patient and never issues an autonomous clinical instruction.",
]

_VERDICT_TEXT = {
    TerminalState.OPERABLE_AT_BASELINE:
        "OPERABLE AT BASELINE — predicted risk is already below the operability threshold; "
        "no reversal pathway is required.",
    TerminalState.OPERABLE_AFTER_OPTIMIZATION:
        "DECLINED AT BASELINE, PREDICTED OPERABLE AFTER OPTIMIZATION — predicted risk crosses "
        "below the operability threshold along the pathway below.",
    TerminalState.OPTIMIZED_BUT_STILL_HIGH_RISK:
        "DECLINED — OPTIMIZATION HELPS BUT DOES NOT CROSS THE THRESHOLD — real optimization "
        "reduces predicted risk but the patient remains high risk. NOT operable on this pathway.",
    TerminalState.FIXED_HIGH_RISK:
        "DECLINED — NO MODIFIABLE PATHWAY — predicted risk is dominated by fixed factors. "
        "Not operable; there is no optimization pathway to offer.",
}


@dataclass
class ClinicianReport:
    vignette_id: str
    header: list = field(default_factory=list)
    patient_summary: dict = field(default_factory=dict)
    verdict: dict = field(default_factory=dict)
    risk_decomposition: dict = field(default_factory=dict)
    optimization_pathway: list = field(default_factory=list)   # per-phase dicts
    applied_rules: list = field(default_factory=list)          # conflict-resolution rules
    required_vs_designed: dict = field(default_factory=dict)
    access_summary: dict = field(default_factory=dict)
    confirmation_flags: list = field(default_factory=list)
    to_verify_markers: list = field(default_factory=list)
    audit_trail: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _collect_to_verify(*texts) -> list:
    found = []
    for t in texts:
        if t and ("[TO VERIFY" in t or "MODELING ASSUMPTION" in t):
            found.append(t)
    return found


def build_clinician_report(vignette: dict) -> ClinicianReport:
    thr = get_operability_threshold()
    decomposition = decompose(vignette)
    outputs = run_all_specialists(vignette, decomposition)
    conflicts = detect_conflicts(outputs)
    resolutions = resolve_conflicts(conflicts, outputs)
    loop = run_reassessment_loop(vignette)
    gated = apply_access_gate(loop)

    inputs = vignette["euroscore_inputs"]
    report = ClinicianReport(vignette_id=vignette.get("id", "?"), header=list(HEADER))

    # --- patient summary ---
    report.patient_summary = {
        "indication": vignette.get("clinical_context", {}).get("indication", "CABG"),
        "coronary_disease_extent": vignette.get("clinical_context", {}).get("coronary_disease_extent", ""),
        "age": inputs["age"],
        "sex": inputs["sex"],
        "comorbidities_present": [
            name for name, present in (
                ("insulin-treated diabetes", inputs["diabetes_on_insulin"]),
                ("chronic lung disease / asthma", inputs["chronic_lung_disease"]),
            ) if present
        ],
        "baseline_euroscore_ii_pct": round(loop.baseline_score, 2),
        "operability_threshold_pct": thr,
        "declined_at_baseline": loop.baseline_score >= thr,
    }

    # --- verdict ---
    flags = []
    if loop.time_infeasible:
        flags.append("TIME_INFEASIBLE — optimization would not fit the surgical urgency window.")
    if gated.access_strain:
        flags.append(f"ACCESS_STRAIN — {gated.trip_count} trips to Bhavnagar exceed the travel budget.")
    if gated.access_barriers:
        flags.append(f"ACCESS_BARRIER(S) — {len(gated.access_barriers)} step(s) unavailable at either tier.")
    report.verdict = {
        "terminal_state": loop.terminal_state.value,
        "plain_language": _VERDICT_TEXT[loop.terminal_state],
        "baseline_pct": round(loop.baseline_score, 2),
        "final_pct": round(loop.final_score, 2),
        "crossing_phase": loop.crossing_phase,
        "flags": flags,
    }

    # --- risk decomposition ---
    report.risk_decomposition = {
        "fixed_factors_cannot_change": decomposition.fixed,
        "modifiable_visible_to_score": [
            {"lever": v.lever, "euroscore_field": v.euroscore_field, "current": v.current_value}
            for v in decomposition.euroscore_visible
        ],
        "modifiable_invisible_to_score_option_b": [
            m.lever for m in decomposition.needs_risk_modifier
        ],
        "note": "Invisible levers are clinically real but do NOT move the EuroSCORE II score "
                "in this PoC (Option B deferred).",
    }

    # --- optimization pathway (phases with gate routing) ---
    routed_by_phase = {}
    for ri in gated.required_pathway:
        routed_by_phase.setdefault(ri.phase_number, ("required", []))[1].append(ri)
    for ri in gated.designed_not_required_pathway:
        routed_by_phase.setdefault(ri.phase_number, ("designed_not_required", []))[1].append(ri)

    plan = loop.plan
    for phase in plan.phases:
        kind, routed = routed_by_phase.get(phase.phase_number, ("designed_not_required", []))
        report.optimization_pathway.append({
            "phase_number": phase.phase_number,
            "duration_weeks": phase.duration_weeks,
            "status": kind,   # required | designed_not_required
            "interventions": [
                {
                    "lever": ri.lever,
                    "name": LEVER_DISPLAY.get(ri.lever, ri.lever),
                    "delivery_tier": ri.delivery_routing.tier,
                    "delivery_label": ri.delivery_routing.routing_label,
                    "oversight_specialist": ri.oversight_capability,
                    "oversight_label": (ri.oversight_routing.routing_label
                                        if ri.oversight_routing else "overseen locally (GP / physiotherapy)"),
                    "access_description": ri.access_description,
                }
                for ri in routed
            ],
            "monitoring_notes": phase.monitoring_notes,
        })

    # applied conflict-resolution rules with rationale + source
    report.applied_rules = [
        {
            "rule_id": r.rule_id,
            "ordering": str(r.ordering),
            "rationale": r.rationale,
            "source": _RULE_SOURCE.get(r.rule_id),
            "monitoring_note": r.monitoring_note,
        }
        for r in resolutions.resolutions
    ]

    # --- required vs designed ---
    report.required_vs_designed = {
        "crossing_phase": loop.crossing_phase,
        "required_phases": sorted({ri.phase_number for ri in gated.required_pathway}),
        "designed_not_required_phases": sorted({ri.phase_number for ri in gated.designed_not_required_pathway}),
        "remaining_not_required_note": "Phases beyond the crossing are clinically advisable "
                                       "but NOT required to reach predicted operability.",
    }

    # --- access summary ---
    report.access_summary = dict(gated.access_summary)
    report.access_summary["surgical_routing"] = gated.surgical_routing.routing_label
    report.access_summary["access_strain"] = gated.access_strain

    # --- confirmation flags ---
    report.confirmation_flags.append(
        "All recommendations are decision support; a qualified clinician must confirm each "
        "before any action."
    )
    for ri in gated.required_pathway + gated.designed_not_required_pathway:
        if ri.oversight_capability:
            report.confirmation_flags.append(
                f"{LEVER_DISPLAY.get(ri.lever, ri.lever)} needs {ri.oversight_capability} "
                f"confirmation before initiation."
            )
    for ri, kind in gated.access_barriers:
        report.confirmation_flags.append(
            f"ACCESS BARRIER on {ri.lever} ({kind}) — flagged for human review; not dropped."
        )

    # --- [TO VERIFY] markers surfaced ---
    tv = []
    for sr in outputs.values():
        for rec in sr.recommendations:
            tv += _collect_to_verify(rec.target, rec.evidence_note)
    for r in resolutions.resolutions:
        tv += _collect_to_verify(_RULE_SOURCE.get(r.rule_id))
    tv += [
        "OPERABILITY_THRESHOLD default 6.0% is a configurable modeling proxy "
        "[TO VERIFY — program-specific cutoff].",
        "MAX_URGENT_OPTIMIZATION_WEEKS / MAX_TERTIARY_TRIPS are modeling proxies "
        "[TO VERIFY — real windows/budgets].",
        "Trip batching (cardiac oversight folds into the CABG episode; same-phase consults "
        "share a trip) is a MODELING ASSUMPTION [TO VERIFY — real scheduling differs].",
        "The loop assumes each phase reaches its lever target [TO VERIFY / MODELING ASSUMPTION].",
    ]
    # de-duplicate, preserve order
    seen = set()
    report.to_verify_markers = [x for x in tv if not (x in seen or seen.add(x))]

    # --- audit trail ---
    at = report.audit_trail
    at.append(f"Baseline EuroSCORE II = {loop.baseline_score:.2f}% "
              f"(threshold {thr:.1f}%; declined={loop.baseline_score >= thr}).")
    for specialty in sorted(outputs):
        sr = outputs[specialty]
        for rec in sr.recommendations:
            at.append(f"[agent:{specialty}] recommend {rec.lever} -> target {rec.target} "
                      f"({rec.weeks_estimate}w).")
        for w in sr.warnings:
            at.append(f"[agent:{specialty}] warning: {w}")
    for c in conflicts:
        at.append(f"[conflict] {c.description} (severity {c.severity}) -> {c.resolution}")
    for r in resolutions.resolutions:
        at.append(f"[resolution] {r.rule_id}: {r.rationale} SOURCE {_RULE_SOURCE.get(r.rule_id)}")
    for c in resolutions.unresolved:
        at.append(f"[resolution] UNRESOLVED conflict {c.conflict_id} — human review required.")
    for it in loop.trace:
        at.append(f"[loop] phase {it.phase_number} (wk {it.cumulative_weeks}): "
                  f"{it.score_before:.2f}% -> {it.score_after:.2f}% "
                  f"applied={it.interventions} invisible={it.invisible_levers_optimized}")
    at.append(f"[loop] terminal={loop.terminal_state.value} time_infeasible={loop.time_infeasible} "
              f"final={loop.final_score:.2f}%")
    at.append(f"[gate] trip_count={gated.trip_count} "
              f"(specialist_consult_trips={gated.specialist_consult_trips}, "
              f"surgery={gated.surgical_routing.tier}) access_strain={gated.access_strain} "
              f"barriers={len(gated.access_barriers)}")

    return report
