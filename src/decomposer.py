"""
Modifiable-vs-fixed risk decomposer (Step 3).

Separates a vignette's modifiable levers into:
  - euroscore_visible     : levers that CAN move the score today (mapped to an EuroSCORE
                            II input field), with the field and its current value exposed
                            so the loop (Step 5) knows what to flip.
  - needs_risk_modifier   : tracked but with ZERO effect on predicted mortality in this
                            step. Each is flagged MODIFIER_LAYER_NOT_YET_GROUNDED = True
                            (Option-B supplementary grounding is deferred; see
                            src/README.md).
  - fixed                 : the EuroSCORE inputs NOT associated with any modifiable lever
                            (age, sex, coronary-anatomy proxies, prior events, etc.).

This module ONLY decomposes and reports. It computes no new scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config import LEVER_TO_EUROSCORE_FIELD
from data.validate import EUROSCORE_FIELDS

_OPTION_B_NOTE = (
    "Non-EuroSCORE-visible lever: has ZERO effect on predicted mortality in Step 3. "
    "Grounding it requires the deferred Option-B supplementary risk-modifier layer "
    "(a sourced extension; see src/README.md)."
)


class DecompositionError(ValueError):
    """Raised when a vignette is malformed or a lever's declared euroscore_field does not
    match the single-source-of-truth mapping in src.config."""


@dataclass(frozen=True)
class VisibleLever:
    """A modifiable lever that maps to an EuroSCORE II input field."""
    lever: str
    euroscore_field: str
    current_value: object  # current value of that EuroSCORE field in the vignette
    status: str            # the lever's current-state descriptor from the vignette


@dataclass(frozen=True)
class ModifierLever:
    """A modifiable lever that EuroSCORE II cannot see (Option B, deferred)."""
    lever: str
    status: str
    MODIFIER_LAYER_NOT_YET_GROUNDED: bool = True
    note: str = _OPTION_B_NOTE


@dataclass
class DecompositionResult:
    vignette_id: str
    euroscore_visible: list[VisibleLever] = field(default_factory=list)
    needs_risk_modifier: list[ModifierLever] = field(default_factory=list)
    fixed: dict = field(default_factory=dict)


def decompose(vignette: dict) -> DecompositionResult:
    """Decompose a vignette's levers into euroscore_visible / needs_risk_modifier / fixed.

    Raises DecompositionError on malformed input. Does not compute scores."""
    if not isinstance(vignette, dict):
        raise DecompositionError(f"vignette must be a dict, got {type(vignette).__name__}")

    vid = vignette.get("id")
    inputs = vignette.get("euroscore_inputs")
    levers = vignette.get("modifiable_levers")
    if not isinstance(inputs, dict):
        raise DecompositionError(f"vignette {vid!r} missing euroscore_inputs dict")
    if not isinstance(levers, list):
        raise DecompositionError(f"vignette {vid!r} missing modifiable_levers list")

    result = DecompositionResult(vignette_id=vid)
    visible_fields: set[str] = set()

    for lev in levers:
        if not isinstance(lev, dict):
            raise DecompositionError(f"vignette {vid!r} has a non-object lever")
        name = lev.get("lever")
        coupling = lev.get("coupling")
        status = lev.get("status", "")

        if coupling == "euroscore_visible":
            expected_field = LEVER_TO_EUROSCORE_FIELD.get(name)
            if expected_field is None:
                raise DecompositionError(
                    f"vignette {vid!r}: euroscore_visible lever {name!r} has no mapping "
                    f"in src.config.LEVER_TO_EUROSCORE_FIELD"
                )
            declared = lev.get("euroscore_field")
            if declared != expected_field:
                raise DecompositionError(
                    f"vignette {vid!r}: lever {name!r} declares euroscore_field "
                    f"{declared!r} but config maps it to {expected_field!r}"
                )
            if expected_field not in inputs:
                raise DecompositionError(
                    f"vignette {vid!r}: mapped field {expected_field!r} absent from "
                    f"euroscore_inputs"
                )
            result.euroscore_visible.append(
                VisibleLever(
                    lever=name,
                    euroscore_field=expected_field,
                    current_value=inputs[expected_field],
                    status=status,
                )
            )
            visible_fields.add(expected_field)

        elif coupling == "needs_risk_modifier":
            result.needs_risk_modifier.append(ModifierLever(lever=name, status=status))

        else:
            raise DecompositionError(
                f"vignette {vid!r}: lever {name!r} has invalid coupling {coupling!r}"
            )

    # Fixed = every EuroSCORE input NOT touched by an euroscore_visible lever.
    result.fixed = {
        f: inputs[f] for f in EUROSCORE_FIELDS if f not in visible_fields
    }
    return result
