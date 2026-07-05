"""
Agent runner (Step 4).

Runs the three specialist agents in parallel (they are pure functions with no shared
mutable state, so threads are safe) and returns a dict keyed by specialty. Agent failures
are logged and re-raised WITH context — never silently swallowed.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.decomposer import DecompositionResult
from src.agents.types import SpecialistRecommendation
from src.agents import cardiac_agent, endocrine_agent, pulmonary_agent

logger = logging.getLogger(__name__)

_AGENTS = {
    "cardiac": cardiac_agent.run,
    "endocrine": endocrine_agent.run,
    "pulmonary": pulmonary_agent.run,
}


class SpecialistAgentError(RuntimeError):
    """Raised when a specialist agent fails, carrying the specialty + vignette id."""


def _run_one(specialty, fn, vignette, decomposition, capability_profile_path):
    try:
        return fn(vignette, decomposition, capability_profile_path)
    except Exception as exc:  # noqa: BLE001 - re-raised with context below
        vid = vignette.get("id") if isinstance(vignette, dict) else "<unknown>"
        logger.exception("specialist agent %r failed on vignette %s", specialty, vid)
        raise SpecialistAgentError(
            f"{specialty} agent failed on vignette {vid!r}: {exc}"
        ) from exc


def run_all_specialists(
    vignette: dict,
    decomposition: DecompositionResult,
    capability_profile_path: str | Path | None = None,
) -> dict[str, SpecialistRecommendation]:
    """Run all three specialists concurrently; return {specialty: SpecialistRecommendation}."""
    results: dict[str, SpecialistRecommendation] = {}
    with ThreadPoolExecutor(max_workers=len(_AGENTS)) as pool:
        futures = {
            pool.submit(
                _run_one, specialty, fn, vignette, decomposition, capability_profile_path
            ): specialty
            for specialty, fn in _AGENTS.items()
        }
        for future, specialty in futures.items():
            results[specialty] = future.result()  # re-raises SpecialistAgentError
    return results
