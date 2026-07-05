"""
Shared types for the specialist agents (Step 4).

Contains the Recommendation / SpecialistRecommendation dataclasses and the
governing-feasibility helper. No clinical logic, no EuroSCORE math.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.feasibility import FeasibilityResult, FeasibilityStatus, check_feasibility

SPECIALTIES = ("cardiac", "endocrine", "pulmonary")


@dataclass
class Recommendation:
    lever: str                      # SCHEMA.md §1.2 lever name
    action: str                     # plain-text intervention
    target: str                     # optimized state, e.g. "chronic_lung_disease: false"
    euroscore_field: str | None     # EuroSCORE field changed, or None (Option-B levers)
    tier_required: str              # "local" | "tertiary"
    feasibility: FeasibilityResult  # governing feasibility across required capabilities
    weeks_estimate: int             # integer weeks (sourced or [TO VERIFY])
    evidence_note: str              # one-sentence grounding or [TO VERIFY]
    conflicts_with: list = field(default_factory=list)  # [] here; Step 5 fills
    # Structured cross-specialty interaction markers (Step 5). Each item, e.g.
    # {"interacts_with": "endocrine", "target_lever": "hba1c",
    #  "mechanism": "steroid_hyperglycemia", "direction": "worsens"}, mirrors a
    # human-readable warning and lets the conflict detector work structurally, not by NLP.
    cross_specialty_flags: list = field(default_factory=list)


@dataclass
class SpecialistRecommendation:
    specialty: str
    recommendations: list[Recommendation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    out_of_scope_flags: list[str] = field(default_factory=list)


# Most-constraining first. Higher rank = harder to achieve / more escalation.
_SEVERITY = {
    FeasibilityStatus.LOCAL: 0,
    FeasibilityStatus.PARTIAL_LOCAL: 1,
    FeasibilityStatus.NEEDS_TERTIARY: 2,
    FeasibilityStatus.PARTIAL_TERTIARY: 3,
    FeasibilityStatus.UNAVAILABLE: 4,
}

_TERTIARY_STATUSES = {
    FeasibilityStatus.NEEDS_TERTIARY,
    FeasibilityStatus.PARTIAL_TERTIARY,
    FeasibilityStatus.UNAVAILABLE,
}


def govern_feasibility(
    capabilities: list[str], tier: str, profile_path: str | Path | None
) -> FeasibilityResult:
    """Return the most-constraining FeasibilityResult across `capabilities` at `tier`.

    Raises if `capabilities` is empty (an agent must name at least one capability for any
    recommendation) or if any capability is unknown (propagated from check_feasibility)."""
    if not capabilities:
        raise ValueError("govern_feasibility requires at least one capability")
    results = [check_feasibility(cap, tier, profile_path) for cap in capabilities]
    return max(results, key=lambda r: _SEVERITY[r.status])


def tier_required_from(feasibility: FeasibilityResult) -> str:
    """Derive tier_required ('local'/'tertiary') from a governing feasibility result."""
    return "tertiary" if feasibility.status in _TERTIARY_STATUSES else "local"
