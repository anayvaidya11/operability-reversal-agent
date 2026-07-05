"""
Time-phased optimization sequencer (Step 5).

Turns the specialists' recommendations + the resolved ordering constraints into an ordered
list of Phases. Deterministic. Does NOT recompute risk (Step 6), does NOT hard-filter on
feasibility (Step 6), does NOT render prose (Step 8). Feasibility is carried as metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config import MAX_URGENT_OPTIMIZATION_WEEKS


class PlannerError(RuntimeError):
    """Raised on an impossible sequence (e.g. a cyclic ordering constraint)."""


@dataclass
class Phase:
    phase_number: int
    duration_weeks: int
    interventions: list            # list[Recommendation], concurrent within the phase
    rationale: str
    monitoring_notes: list = field(default_factory=list)


@dataclass
class OptimizationPlan:
    phases: list = field(default_factory=list)             # list[Phase]
    total_duration_weeks: int = 0
    unresolved_conflicts: list = field(default_factory=list)
    rationale_trace: list = field(default_factory=list)    # ordered list[str]
    urgency: str = "elective"
    urgency_warning: str | None = None                     # None unless urgent+overrun


def _collect_recs(specialist_outputs: dict) -> dict:
    """lever -> Recommendation across all specialists (levers are disjoint by design)."""
    recs = {}
    for specialty in sorted(specialist_outputs):
        for rec in specialist_outputs[specialty].recommendations:
            recs[rec.lever] = rec
    return recs


def _layer(levers: list[str], edges: set[tuple[str, str]]) -> dict[str, int]:
    """Longest-path layering: phase(l) = 1 + max(phase(pred)); no-pred levers -> phase 1.
    Deterministic; raises PlannerError on a cycle."""
    preds: dict[str, set[str]] = {l: set() for l in levers}
    for before, after in edges:
        if before in preds and after in preds:
            preds[after].add(before)

    phase: dict[str, int] = {}
    for _ in range(len(levers) + 1):
        progressed = False
        for lever in sorted(levers):
            if lever in phase:
                continue
            if all(p in phase for p in preds[lever]):
                phase[lever] = 1 + max((phase[p] for p in preds[lever]), default=0)
                progressed = True
        if len(phase) == len(levers):
            return phase
        if not progressed:
            break
    raise PlannerError(f"cyclic ordering constraint among levers: {sorted(set(levers) - set(phase))}")


def build_sequence(
    vignette: dict,
    specialist_outputs: dict,
    resolutions,
    max_urgent_weeks: int | None = None,
) -> OptimizationPlan:
    """Build the time-phased OptimizationPlan.

    `resolutions` is a ResolutionResult (from resolve_conflicts). Ordering constraints come
    from its resolutions; unresolved conflicts are carried onto the plan for human review.
    """
    max_urgent_weeks = (
        MAX_URGENT_OPTIMIZATION_WEEKS if max_urgent_weeks is None else max_urgent_weeks
    )
    recs = _collect_recs(specialist_outputs)
    plan = OptimizationPlan(
        urgency=vignette["euroscore_inputs"]["urgency"],
        unresolved_conflicts=list(getattr(resolutions, "unresolved", [])),
    )

    if not recs:
        plan.rationale_trace.append("No modifiable-lever recommendations; empty plan.")
        return plan

    # Ordering edges + per-phase monitoring notes, from resolutions whose BOTH levers are
    # present in this vignette's recommendation set.
    edges: set[tuple[str, str]] = set()
    monitoring_for_lever: dict[str, list[str]] = {}
    for res in getattr(resolutions, "resolutions", []):
        ordering = res.ordering
        if isinstance(ordering, tuple) and len(ordering) == 2:
            first, second = ordering
            if first in recs and second in recs:
                edges.add((first, second))
                monitoring_for_lever.setdefault(second, []).append(res.monitoring_note)

    phase_of = _layer(list(recs), edges)

    # Group levers into phases.
    max_phase = max(phase_of.values())
    for n in range(1, max_phase + 1):
        levers = sorted(l for l, p in phase_of.items() if p == n)
        interventions = [recs[l] for l in levers]
        duration = max(r.weeks_estimate for r in interventions)
        monitoring = [note for l in levers for note in monitoring_for_lever.get(l, [])]
        rationale = (
            f"Phase {n}: "
            + ", ".join(f"{r.lever} ({r.weeks_estimate}w, {r.tier_required})" for r in interventions)
            + (" — concurrent." if len(interventions) > 1 else ".")
        )
        plan.phases.append(
            Phase(
                phase_number=n,
                duration_weeks=duration,
                interventions=interventions,
                rationale=rationale,
                monitoring_notes=monitoring,
            )
        )

    plan.total_duration_weeks = sum(p.duration_weeks for p in plan.phases)

    # Rationale trace: ordering rules applied, then per-phase lines.
    for res in getattr(resolutions, "resolutions", []):
        plan.rationale_trace.append(f"Applied {res.rule_id}: {res.rationale}")
    for p in plan.phases:
        plan.rationale_trace.append(p.rationale)
    for c in plan.unresolved_conflicts:
        plan.rationale_trace.append(f"UNRESOLVED conflict {c.conflict_id}: {c.description}")

    # Surgical-urgency constraint.
    if plan.urgency != "elective" and plan.total_duration_weeks > max_urgent_weeks:
        cumulative = 0
        truncated = []
        for p in plan.phases:
            cumulative += p.duration_weeks
            if cumulative > max_urgent_weeks:
                truncated.append(p.phase_number)
        plan.urgency_warning = (
            f"Urgency '{plan.urgency}': planned optimization is {plan.total_duration_weeks} "
            f"weeks, exceeding MAX_URGENT_OPTIMIZATION_WEEKS={max_urgent_weeks}. Phases "
            f"{truncated} would be truncated — human review required (phases NOT dropped)."
        )
        plan.rationale_trace.append(plan.urgency_warning)

    return plan
