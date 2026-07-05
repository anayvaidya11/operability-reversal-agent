"""
Resource-feasibility checker (Step 3).

Given a capability_id and the patient's current care tier ("local"/"tertiary"), reports
whether an action is available locally, only at tertiary, or nowhere — using
data/capability_profile.json (SPEC.md §c). "partial" availability is surfaced explicitly
as PARTIAL_LOCAL / PARTIAL_TERTIARY, never collapsed to yes/no.

Pure/deterministic: the capability profile is loaded once and cached.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

_DEFAULT_PROFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "capability_profile.json"

_VALID_TIERS = ("local", "tertiary")


class UnknownCapabilityError(KeyError):
    """Raised when an action_id is not present in the capability profile."""


class FeasibilityStatus(Enum):
    LOCAL = "LOCAL"                      # available at the local tier
    PARTIAL_LOCAL = "PARTIAL_LOCAL"      # local availability is "partial"
    NEEDS_TERTIARY = "NEEDS_TERTIARY"    # available only at tertiary
    PARTIAL_TERTIARY = "PARTIAL_TERTIARY"  # tertiary availability is "partial", not local
    UNAVAILABLE = "UNAVAILABLE"          # available at neither tier


@dataclass(frozen=True)
class FeasibilityResult:
    status: FeasibilityStatus
    action_id: str
    tier: str            # the patient's current tier that was queried
    local_available: str
    tertiary_available: str
    note: str


# Cache keyed by resolved profile path so different profiles don't collide.
_capabilities_cache: dict[str, dict[str, dict]] = {}


def _load_capabilities(profile_path: Path) -> dict[str, dict]:
    """Load and cache the capability profile as {capability_id: capability_dict}."""
    key = str(profile_path.resolve())
    if key not in _capabilities_cache:
        data = json.loads(profile_path.read_text())
        _capabilities_cache[key] = {c["capability_id"]: c for c in data["capabilities"]}
    return _capabilities_cache[key]


def check_feasibility(
    action_id: str, tier: str, profile_path: str | Path | None = None
) -> FeasibilityResult:
    """Return a FeasibilityResult for `action_id` given the patient's current `tier`.

    `profile_path` defaults to data/capability_profile.json. Raises
    UnknownCapabilityError for an unrecognized action_id, and ValueError for an invalid
    tier (fail loud)."""
    if tier not in _VALID_TIERS:
        raise ValueError(f"tier must be one of {_VALID_TIERS}, got {tier!r}")

    path = Path(profile_path) if profile_path is not None else _DEFAULT_PROFILE_PATH
    caps = _load_capabilities(path)
    if action_id not in caps:
        raise UnknownCapabilityError(
            f"unknown capability_id {action_id!r} (not in {path.name})"
        )

    cap = caps[action_id]
    la = cap["local_available"]
    ta = cap["tertiary_available"]

    if la == "yes":
        status = FeasibilityStatus.LOCAL
        note = "Available at the local tier."
    elif la == "partial":
        status = FeasibilityStatus.PARTIAL_LOCAL
        note = "Local availability is PARTIAL — do not assume; verify before relying on it."
    elif ta == "yes":
        status = FeasibilityStatus.NEEDS_TERTIARY
        note = (
            "Not available locally; available at tertiary — "
            + ("patient is already at tertiary." if tier == "tertiary"
               else "patient must travel to tertiary.")
        )
    elif ta == "partial":
        status = FeasibilityStatus.PARTIAL_TERTIARY
        note = "Not available locally; tertiary availability is PARTIAL — verify."
    else:
        status = FeasibilityStatus.UNAVAILABLE
        note = "Available at neither tier in this profile."

    return FeasibilityResult(
        status=status,
        action_id=action_id,
        tier=tier,
        local_available=la,
        tertiary_available=ta,
        note=note,
    )
