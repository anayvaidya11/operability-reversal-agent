"""
Single source of truth for the "fully optimized" EuroSCORE state (Step 4.5).

Given a vignette + its DecompositionResult, produce the euroscore_inputs that result from
driving EVERY euroscore_visible lever to its best realistic optimized value. The audit
script, the data validator's score-property check, the threshold tests, and (later) the
Step-5 planner and the eval harness all import this so they never diverge.

OPTIMIZED-VALUE CONVENTION (Task 1 decision):
  chronic_lung_disease        -> False   (asthma well-controlled)
  poor_mobility               -> False   (prehabilitated)
  critical_preoperative_state -> False   (stabilized)
  nyha_class                  -> "I"  if baseline is "II" or "III"
                                 "II" if baseline is "IV"   (a two-class jump in one
                                                             pre-op window is unrealistic)
Rationale: NYHA is a symptom state that improves with medical optimization, but a patient
in class IV (symptoms at rest) realistically reaches class II, not class I, within a
pre-operative window. Classes II/III can realistically reach I. This is the ONE convention;
the cardiac agent's per-recommendation *target* ("II", one-class improvement) is a
conservative planning label and may differ from this best-case reversibility ceiling — see
docs/SPEC.md §e.
"""

from __future__ import annotations

import copy

from src.decomposer import DecompositionResult

# Non-NYHA fields collapse to a single optimized value.
_OPTIMIZED_BOOL_FIELD = {
    "chronic_lung_disease": False,
    "poor_mobility": False,
    "critical_preoperative_state": False,
}


def optimized_field_value(field: str, current):
    """The best realistic optimized value for a single euroscore_visible field."""
    if field == "nyha_class":
        return "II" if current == "IV" else "I"
    if field in _OPTIMIZED_BOOL_FIELD:
        return _OPTIMIZED_BOOL_FIELD[field]
    raise KeyError(f"no optimized-value convention for field {field!r}")


def optimized_inputs(vignette: dict, decomposition: DecompositionResult) -> dict:
    """Return a copy of the vignette's euroscore_inputs with every euroscore_visible
    lever's mapped field driven to its optimized value."""
    inputs = copy.deepcopy(vignette["euroscore_inputs"])
    for lever in decomposition.euroscore_visible:
        inputs[lever.euroscore_field] = optimized_field_value(
            lever.euroscore_field, inputs[lever.euroscore_field]
        )
    return inputs
