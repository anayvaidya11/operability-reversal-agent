"""
Rule-based evaluation harness (Step 9, Part B).

Runs deterministic checks over ALL vignettes and reports pass/fail PER vignette with a
reason. This is NOT another model — every check is an auditable rule, so "did the agent do
the right thing" stays inspectable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.decomposer import decompose
from src.agents.run_specialists import run_all_specialists
from src.planner import detect_conflicts, resolve_conflicts
from src.planner.resolution_rules import UNRESOLVED
from src.loop import run_reassessment_loop, TerminalState
from src.gate import apply_access_gate
from src.output import build_clinician_report, render_report_text

_DATA = Path(__file__).resolve().parent.parent / "data" / "vignettes.json"

DOMAIN_LEVERS = {
    "cardiac": {"mobility", "heart_failure_symptoms", "critical_preop_stabilization"},
    "endocrine": {"hba1c"},
    "pulmonary": {"asthma_control", "smoking_status"},
}

_MECHANISM_RULE = {
    "steroid_hyperglycemia": "RULE_GLYCEMIA_BEFORE_ICS",
    "betablocker_bronchospasm": "RULE_BETABLOCKER_ASTHMA",
}

_OPERABLE_STATES = {TerminalState.OPERABLE_AT_BASELINE, TerminalState.OPERABLE_AFTER_OPTIMIZATION}


@dataclass
class CheckResult:
    check: str
    passed: bool
    reason: str


@dataclass
class VignetteEval:
    vignette_id: str
    design_intent: str
    terminal_state: str
    time_infeasible: bool
    access_barrier_count: int
    trip_count: int
    conflicts_detected: int
    conflicts_resolved: int
    conflicts_escalated: int
    results: list = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)


def load_vignettes():
    return json.loads(_DATA.read_text())["vignettes"]


def _expected_terminal(vignette, loop):
    di = vignette["design_intent"]
    if di == "operable_at_baseline":
        return TerminalState.OPERABLE_AT_BASELINE
    if di in ("reversible_with_optimization", "reversible_but_access_blocked"):
        return TerminalState.OPERABLE_AFTER_OPTIMIZATION
    if di == "fixed_high_risk":
        return (TerminalState.OPTIMIZED_BUT_STILL_HIGH_RISK
                if loop.plan.phases else TerminalState.FIXED_HIGH_RISK)
    return None


def evaluate_vignette(vignette) -> VignetteEval:
    decomposition = decompose(vignette)
    outputs = run_all_specialists(vignette, decomposition)
    conflicts = detect_conflicts(outputs)
    resolutions = resolve_conflicts(conflicts, outputs)
    loop = run_reassessment_loop(vignette)
    gated = apply_access_gate(loop)
    report = build_clinician_report(vignette)
    text = render_report_text(report)

    checks: list[CheckResult] = []

    # 1. guideline concordance — agents stay in their own lever domain
    off = []
    for specialty, sr in outputs.items():
        for rec in sr.recommendations:
            if rec.lever not in DOMAIN_LEVERS[specialty]:
                off.append(f"{specialty}:{rec.lever}")
    checks.append(CheckResult(
        "guideline_concordance", not off,
        "all recommendations in-domain" if not off else f"out-of-domain: {off}"))

    # 2. conflict-resolution correctness — resolved-by-rule or escalated; never dropped
    bad = []
    for c in conflicts:
        if c.resolution is None:
            bad.append(f"{c.conflict_id}: silently dropped")
        elif c.resolution != UNRESOLVED and c.mechanism in _MECHANISM_RULE:
            if _MECHANISM_RULE[c.mechanism] not in c.resolution:
                bad.append(f"{c.conflict_id}: wrong rule for {c.mechanism}")
    checks.append(CheckResult(
        "conflict_resolution_correctness", not bad,
        "all conflicts resolved-by-rule or escalated" if not bad else f"{bad}"))

    # 3. resource feasibility — UNAVAILABLE only when flagged an ACCESS BARRIER; routing coherent
    incoherent = []
    for ri in gated.required_pathway:
        d = ri.delivery_routing
        if d.tier == "none" and not d.is_access_barrier:
            incoherent.append(f"{ri.lever}: none-tier without barrier flag")
        if d.tier not in ("local", "tertiary", "none"):
            incoherent.append(f"{ri.lever}: bad tier {d.tier}")
    checks.append(CheckResult(
        "resource_feasibility", not incoherent,
        "required routing coherent" if not incoherent else f"{incoherent}"))

    # 4. operability-threshold correctness — terminal matches the score relationship
    expected = _expected_terminal(vignette, loop)
    ok4 = loop.terminal_state is expected
    checks.append(CheckResult(
        "operability_threshold_correctness", ok4,
        f"terminal={loop.terminal_state.value}" if ok4
        else f"terminal={loop.terminal_state.value} expected={expected.value}"))

    # 5. thesis property — reversible: all delivery local except a legitimate access barrier
    if vignette["design_intent"] in ("reversible_with_optimization", "reversible_but_access_blocked"):
        offenders = []
        for ri in gated.required_pathway + gated.designed_not_required_pathway:
            if ri.delivery_routing.tier != "local" and not ri.delivery_routing.is_access_barrier:
                offenders.append(ri.lever)
        checks.append(CheckResult(
            "thesis_property_delivery_local", not offenders,
            "all delivery local (or access-barriered)" if not offenders
            else f"non-local delivery: {offenders}"))
    else:
        checks.append(CheckResult("thesis_property_delivery_local", True, "n/a (not reversible)"))

    # 6. honesty — no operability claim for a non-crossing case; [TO VERIFY] surfaced
    problems = []
    if loop.terminal_state not in _OPERABLE_STATES:
        if "PREDICTED OPERABLE AFTER OPTIMIZATION" in text or "OPERABLE AT BASELINE" in text:
            problems.append("operability claimed for a non-operable case")
    if not report.to_verify_markers or "[TO VERIFY]" not in text:
        problems.append("[TO VERIFY] markers not surfaced")
    checks.append(CheckResult(
        "honesty_properties", not problems,
        "honest" if not problems else f"{problems}"))

    resolved = len(resolutions.resolutions)
    escalated = len(resolutions.unresolved)
    return VignetteEval(
        vignette_id=vignette["id"],
        design_intent=vignette["design_intent"],
        terminal_state=loop.terminal_state.value,
        time_infeasible=loop.time_infeasible,
        access_barrier_count=len(gated.access_barriers),
        trip_count=gated.trip_count,
        conflicts_detected=len(conflicts),
        conflicts_resolved=resolved,
        conflicts_escalated=escalated,
        results=checks,
    )


def evaluate_all(vignettes=None) -> list:
    vignettes = vignettes if vignettes is not None else load_vignettes()
    return [evaluate_vignette(v) for v in vignettes]
