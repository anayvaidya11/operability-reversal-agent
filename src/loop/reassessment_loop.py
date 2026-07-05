"""
Iterative re-assessment loop — the agentic core (Step 6).

Simulates the patient advancing through the Step-5 OptimizationPlan phase by phase,
recomputes EuroSCORE II after each phase (reusing src/risk_calculator EXACTLY), and
branches into terminal states. Deterministic, no LLM. Never fabricates a favorable
outcome: if optimization does not cross the threshold, it says so.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum

from src.risk_calculator import compute_euroscore_ii
from src.decomposer import decompose
from src.agents.run_specialists import run_all_specialists
from src.planner import detect_conflicts, resolve_conflicts, build_sequence
from src.config import get_operability_threshold, MAX_URGENT_OPTIMIZATION_WEEKS
from src.feasibility import check_feasibility, FeasibilityStatus
from src.loop.simulation import advance_phase

_URGENT_LEVELS = {"urgent", "emergency", "salvage"}
_TERTIARY_STATUSES = {
    FeasibilityStatus.NEEDS_TERTIARY,
    FeasibilityStatus.PARTIAL_TERTIARY,
    FeasibilityStatus.UNAVAILABLE,
}


class TerminalState(Enum):
    OPERABLE_AT_BASELINE = "OPERABLE_AT_BASELINE"
    OPERABLE_AFTER_OPTIMIZATION = "OPERABLE_AFTER_OPTIMIZATION"
    OPTIMIZED_BUT_STILL_HIGH_RISK = "OPTIMIZED_BUT_STILL_HIGH_RISK"
    FIXED_HIGH_RISK = "FIXED_HIGH_RISK"


@dataclass
class IterationRecord:
    phase_number: int          # 0 = baseline
    cumulative_weeks: int
    interventions: list        # lever names applied this phase
    score_before: float
    score_after: float
    invisible_levers_optimized: list = field(default_factory=list)
    note: str = ""


@dataclass
class LoopResult:
    terminal_state: TerminalState
    time_infeasible: bool
    baseline_score: float
    final_score: float
    crossing_phase: int | None
    trace: list                      # list[IterationRecord], includes iteration 0
    total_weeks: int
    plan: object                     # the OptimizationPlan
    patient_tier: str = "local"      # patient's home care tier (for the Step-7 access gate)
    unresolved_conflicts: list = field(default_factory=list)
    remaining_phases_not_required: list = field(default_factory=list)
    routing_hint: dict | None = None


def _routing_hint(vignette: dict) -> dict:
    """Light routing hint (NOT the Step-7 hard gate): where the actual CABG must happen."""
    fr = check_feasibility("cabg", vignette["location_tier"])
    tier = "tertiary" if fr.status in _TERTIARY_STATUSES else "local"
    return {
        "cabg_tier_required": tier,
        "cabg_feasibility": fr.status.value,
        "note": f"Surgery (CABG) routes to the nearest capable center ({tier}).",
    }


def run_reassessment_loop(vignette: dict, threshold=None, max_urgent_weeks=None) -> LoopResult:
    thr = get_operability_threshold(threshold)
    maxw = MAX_URGENT_OPTIMIZATION_WEEKS if max_urgent_weeks is None else max_urgent_weeks

    inputs0 = vignette["euroscore_inputs"]
    urgency = inputs0["urgency"]
    baseline = compute_euroscore_ii(inputs0)
    trace = [IterationRecord(0, 0, [], baseline, baseline, [], "baseline")]

    # Build the plan (Step 5 pipeline).
    decomposition = decompose(vignette)
    outputs = run_all_specialists(vignette, decomposition)
    resolutions = resolve_conflicts(detect_conflicts(outputs), outputs)
    plan = build_sequence(vignette, outputs, resolutions, max_urgent_weeks=maxw)
    unresolved = list(resolutions.unresolved)

    # Already operable at baseline: no optimization is NEEDED, even if agents proposed a
    # minor (often score-invisible) tweak. Short-circuit before iterating so a patient who
    # was operable *before* optimization is never mislabeled OPERABLE_AFTER_OPTIMIZATION.
    if baseline < thr:
        return LoopResult(
            terminal_state=TerminalState.OPERABLE_AT_BASELINE,
            time_infeasible=False,
            baseline_score=baseline,
            final_score=baseline,
            crossing_phase=None,
            trace=trace,
            total_weeks=0,
            plan=plan,
            patient_tier=vignette["location_tier"],
            unresolved_conflicts=unresolved,
            remaining_phases_not_required=[],
            routing_hint=_routing_hint(vignette),
        )

    # Declined, and no agent-addressable levers to optimize: genuinely fixed.
    if not plan.phases:
        return LoopResult(
            terminal_state=TerminalState.FIXED_HIGH_RISK,
            time_infeasible=False,
            baseline_score=baseline,
            final_score=baseline,
            crossing_phase=None,
            trace=trace,
            total_weeks=0,
            plan=plan,
            patient_tier=vignette["location_tier"],
            unresolved_conflicts=unresolved,
            remaining_phases_not_required=[],
            routing_hint=None,
        )

    # Iterate phases in order, recomputing after each.
    current = copy.deepcopy(inputs0)
    cumulative = 0
    crossing = None
    state = None
    final = baseline
    for phase in plan.phases:
        before = compute_euroscore_ii(current)
        updated, effect = advance_phase(current, phase)
        after = compute_euroscore_ii(updated)
        cumulative += phase.duration_weeks
        trace.append(
            IterationRecord(
                phase_number=phase.phase_number,
                cumulative_weeks=cumulative,
                interventions=[r.lever for r in phase.interventions],
                score_before=before,
                score_after=after,
                invisible_levers_optimized=list(effect.optimized_but_invisible),
            )
        )
        current = updated
        final = after
        if after < thr:
            crossing = phase.phase_number
            state = TerminalState.OPERABLE_AFTER_OPTIMIZATION
            break  # early stop — patient now operable

    if state is None:
        # All phases applied; still declined. The honesty branch (e.g. SYNTH-008).
        state = TerminalState.OPTIMIZED_BUT_STILL_HIGH_RISK

    applied = {r.phase_number for r in trace if r.phase_number > 0}
    remaining = [p.phase_number for p in plan.phases if p.phase_number not in applied]

    # Urgency overlay: orthogonal TIME_INFEASIBLE flag (the fix exists but not in time).
    time_infeasible = urgency in _URGENT_LEVELS and cumulative > maxw

    hint = (
        _routing_hint(vignette)
        if state in (TerminalState.OPERABLE_AT_BASELINE, TerminalState.OPERABLE_AFTER_OPTIMIZATION)
        else None
    )

    return LoopResult(
        terminal_state=state,
        time_infeasible=time_infeasible,
        baseline_score=baseline,
        final_score=final,
        crossing_phase=crossing,
        trace=trace,
        total_weeks=cumulative,
        plan=plan,
        unresolved_conflicts=unresolved,
        remaining_phases_not_required=remaining,
        routing_hint=hint,
    )
