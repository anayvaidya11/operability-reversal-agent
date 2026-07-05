"""
Shared helpers for specialist agents (Step 4). No clinical content lives here — each
agent supplies its own domain knowledge.
"""

from __future__ import annotations

from pathlib import Path

from src.decomposer import DecompositionResult
from src.agents.types import (
    Recommendation,
    govern_feasibility,
    tier_required_from,
)


def visible_by_name(decomposition: DecompositionResult) -> dict:
    """Map lever name -> VisibleLever for euroscore_visible levers."""
    return {lev.lever: lev for lev in decomposition.euroscore_visible}


def modifier_by_name(decomposition: DecompositionResult) -> dict:
    """Map lever name -> ModifierLever for needs_risk_modifier levers."""
    return {lev.lever: lev for lev in decomposition.needs_risk_modifier}


def make_recommendation(
    *,
    lever: str,
    action: str,
    target: str,
    euroscore_field: str | None,
    capabilities: list[str],
    tier: str,
    weeks_estimate: int,
    evidence_note: str,
    profile_path: str | Path | None,
) -> Recommendation:
    """Build a Recommendation, resolving the governing feasibility across `capabilities`
    at the patient's `tier`."""
    feasibility = govern_feasibility(capabilities, tier, profile_path)
    return Recommendation(
        lever=lever,
        action=action,
        target=target,
        euroscore_field=euroscore_field,
        tier_required=tier_required_from(feasibility),
        feasibility=feasibility,
        weeks_estimate=weeks_estimate,
        evidence_note=evidence_note,
    )
