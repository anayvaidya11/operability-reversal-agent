"""
Phase-application simulation for the re-assessment loop (Step 6).

Applying a phase means: every euroscore_visible intervention in the phase flips its mapped
EuroSCORE field to its optimized value (via the shared convention in
src/optimized_state.py); needs_risk_modifier interventions are RECORDED as
optimized-but-invisible and do NOT change the inputs (Option B remains deferred).

[TO VERIFY / MODELING ASSUMPTION — the loop assumes each phase reaches its lever target.
Real patients may not respond; this is a deterministic simulation of expected optimization
success, not a prediction of individual response.]
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from src.optimized_state import optimized_field_value


@dataclass
class PhaseEffect:
    phase_number: int
    fields_changed: dict = field(default_factory=dict)        # field -> {"from":.., "to":..}
    visible_levers_optimized: list = field(default_factory=list)
    optimized_but_invisible: list = field(default_factory=list)  # levers with no score effect


def advance_phase(current_inputs: dict, phase, optimized_state_convention=optimized_field_value):
    """Apply `phase` to `current_inputs`; return (updated_inputs, PhaseEffect).

    `optimized_state_convention(field, current) -> optimized_value` defaults to the shared
    src/optimized_state convention.
    """
    updated = copy.deepcopy(current_inputs)
    effect = PhaseEffect(phase_number=phase.phase_number)

    for rec in phase.interventions:
        if rec.euroscore_field is not None:
            f = rec.euroscore_field
            old = updated[f]
            new = optimized_state_convention(f, old)
            effect.visible_levers_optimized.append(rec.lever)
            if new != old:
                updated[f] = new
                effect.fields_changed[f] = {"from": old, "to": new}
        else:
            # needs_risk_modifier: tracked, but zero effect on EuroSCORE II (Option B).
            effect.optimized_but_invisible.append(rec.lever)

    return updated, effect
