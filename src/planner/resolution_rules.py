"""
Named, sourced sequencing rules and the resolver (Step 5).

Deterministic. Each rule cites a reason. A conflict with no matching rule is NEVER
guessed — it surfaces as "UNRESOLVED — human review required".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.planner.conflicts import Conflict

UNRESOLVED = "UNRESOLVED — human review required"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    applies_to: dict           # {"kind": ..., "mechanism": ...}
    ordering: object           # (first_lever, second_lever) tuple, or "parallel_with_monitoring"
    rationale: str
    source: str                # citation or [TO VERIFY — ...]
    monitoring_note: str


# ICS <-> glycemia: do glycemic optimization FIRST, then step up ICS with glucose
# monitoring. Both interventions happen — this is ordering, not "drop one".
RULE_GLYCEMIA_BEFORE_ICS = Rule(
    rule_id="RULE_GLYCEMIA_BEFORE_ICS",
    applies_to={"kind": "clinical_interaction", "mechanism": "steroid_hyperglycemia"},
    ordering=("hba1c", "asthma_control"),  # glycemia before ICS step-up
    rationale=(
        "Inhaled/systemic corticosteroids raise blood glucose; stepping up ICS into "
        "uncontrolled diabetes compounds hyperglycemia and surgical-site infection risk. "
        "Establish a glycemic-control trend first, then step up ICS."
    ),
    source="[TO VERIFY — corticosteroid hyperglycemia in perioperative optimization; cite source]",
    monitoring_note=(
        "Monitor blood glucose closely during ICS titration; expect a transient rise and "
        "adjust glycemic therapy accordingly."
    ),
)

# beta-blocker <-> asthma: establish/confirm pulmonary control BEFORE any beta-blocker
# titration; prefer a cardioselective agent only with pulmonology sign-off. Treated as
# ORDERING (pulmonary before beta-blocker), with CONDITIONAL deferral of the beta-blocker
# sub-intervention if asthma remains poorly controlled — the deferral is on the
# beta-blocker lever only, NOT on the whole cardiac plan.
RULE_BETABLOCKER_ASTHMA = Rule(
    rule_id="RULE_BETABLOCKER_ASTHMA",
    applies_to={"kind": "clinical_interaction", "mechanism": "betablocker_bronchospasm"},
    ordering=("asthma_control", "heart_failure_symptoms"),  # pulmonary control before beta-blocker
    rationale=(
        "Non-selective beta-blockade risks bronchospasm in asthma. Establish pulmonary "
        "control first; then titrate only a cardioselective beta-blocker with pulmonology "
        "sign-off. If asthma remains poorly controlled, DEFER the beta-blocker "
        "sub-intervention (conditional-blocking on that lever only) — the rest of the "
        "heart-failure optimization (diuretics, ACEi/ARB) proceeds."
    ),
    source="[TO VERIFY — cardioselective beta-blockers in asthma; cite source]",
    monitoring_note=(
        "Confirm asthma control before initiating a cardioselective beta-blocker; watch "
        "for bronchospasm on initiation and after each up-titration."
    ),
)

REGISTRY: list[Rule] = [RULE_GLYCEMIA_BEFORE_ICS, RULE_BETABLOCKER_ASTHMA]


@dataclass
class Resolution:
    conflict: Conflict
    rule_id: str
    ordering: object           # mirror of the rule's ordering
    monitoring_note: str
    rationale: str


@dataclass
class ResolutionResult:
    resolutions: list = field(default_factory=list)   # list[Resolution]
    unresolved: list = field(default_factory=list)    # list[Conflict]


def _match(conflict: Conflict) -> Rule | None:
    for rule in REGISTRY:
        if (
            rule.applies_to.get("kind") == conflict.kind
            and rule.applies_to.get("mechanism") == conflict.mechanism
        ):
            return rule
    return None


def resolve_conflicts(conflicts: list[Conflict], specialist_outputs: dict) -> ResolutionResult:
    """Apply the rule registry to each conflict. Unmatched conflicts are escalated, never
    guessed."""
    result = ResolutionResult()
    for conflict in conflicts:
        rule = _match(conflict)
        if rule is None:
            conflict.resolution = UNRESOLVED
            result.unresolved.append(conflict)
            continue
        conflict.resolution = f"{rule.rule_id}: {rule.ordering}"
        result.resolutions.append(
            Resolution(
                conflict=conflict,
                rule_id=rule.rule_id,
                ordering=rule.ordering,
                monitoring_note=rule.monitoring_note,
                rationale=rule.rationale,
            )
        )
    return result
