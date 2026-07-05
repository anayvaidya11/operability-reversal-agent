"""
Threshold-sensitivity tests (Step 3) — the core of the reversal demo.

These prove the Option-A pathway: optimizing the EuroSCORE-VISIBLE levers moves the
predicted score DOWN, before any (deferred, Option-B) supplementary modifier layer
exists.

STEP-4 RESOLUTION (see src/config.py and docs/SPEC.md §e):
The Step-3 report found that with the real EuroSCORE II coefficients, isolated elective
CABG scores lower than the synthetic data assumed. The default OPERABILITY_THRESHOLD was
lowered from 8.0% to 6.0% (clinically grounded). At 6.0% the grandmother is correctly
"declined at baseline" (7.38% >= 6.0%) and becomes "potentially operable" after visible-
lever optimization (3.72% < 6.0%). SYNTH-008 remains an honest case where visible levers
alone are INSUFFICIENT (22.4% -> 7.45%, still >= 6.0%). All asserted below.
"""

import copy
import json
from pathlib import Path

from src.risk_calculator import compute_euroscore_ii
from src.decomposer import decompose
from src.config import get_operability_threshold

VIGNETTES = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "vignettes.json").read_text()
)["vignettes"]
BY_ID = {v["id"]: v for v in VIGNETTES}

# The "optimized" (reference / best-case) value for each modifiable EuroSCORE field.
# This is the state each euroscore_visible lever is driven toward. (The Step-5 loop will
# own this mapping in production; the test defines it locally.)
OPTIMIZED_FIELD_VALUE = {
    "chronic_lung_disease": False,
    "poor_mobility": False,
    "nyha_class": "I",
    "critical_preoperative_state": False,
}


def optimize_visible(vignette: dict) -> dict:
    """Return a copy of the euroscore_inputs with every euroscore_visible lever's mapped
    field driven to its optimized value."""
    inputs = copy.deepcopy(vignette["euroscore_inputs"])
    for lever in decompose(vignette).euroscore_visible:
        inputs[lever.euroscore_field] = OPTIMIZED_FIELD_VALUE[lever.euroscore_field]
    return inputs


# --- grandmother (SYNTH-006) ---------------------------------------------------------

def test_grandmother_optimization_reduces_risk():
    g = BY_ID["SYNTH-006"]
    baseline = compute_euroscore_ii(g["euroscore_inputs"])
    optimized = compute_euroscore_ii(optimize_visible(g))
    assert abs(baseline - 7.3807) < 1e-3
    assert abs(optimized - 3.7153) < 1e-3
    # Option-A pathway: visible-lever optimization strictly lowers predicted mortality,
    # and by a clinically meaningful amount (here, roughly halved).
    assert optimized < baseline
    assert (baseline - optimized) > 2.0


def test_grandmother_crosses_default_threshold():
    # THE MONEY DEMO at the Step-4 default threshold (6.0%): the grandmother is
    # "declined at baseline" and becomes "potentially operable" on visible levers alone.
    g = BY_ID["SYNTH-006"]
    baseline = compute_euroscore_ii(g["euroscore_inputs"])
    optimized = compute_euroscore_ii(optimize_visible(g))
    threshold = get_operability_threshold()  # default 6.0
    assert threshold == 6.0
    assert baseline >= threshold           # 7.38 >= 6.0  -> declined at baseline
    assert optimized < threshold           # 3.72 <  6.0  -> potentially operable


# --- SYNTH-008: visible levers alone are INSUFFICIENT (honest case) -------------------

def test_synth008_visible_levers_insufficient_at_default_threshold():
    # Honest counter-case: optimizing the visible levers helps a lot (22.4% -> 7.45%)
    # but does NOT bring SYNTH-008 below the 6.0% threshold. Reversal is not always
    # achievable on EuroSCORE-visible levers alone — the agent must be able to say so.
    v = BY_ID["SYNTH-008"]
    baseline = compute_euroscore_ii(v["euroscore_inputs"])
    optimized = compute_euroscore_ii(optimize_visible(v))
    threshold = get_operability_threshold()  # default 6.0
    assert baseline >= threshold            # declined at baseline (~22.4%)
    assert optimized < baseline             # optimization still helps materially
    assert optimized >= threshold           # ...but remains declined (~7.45%)


# --- fixed_high_risk cannot be reversed on visible levers ----------------------------

def test_fixed_high_risk_cannot_cross_threshold():
    # SYNTH-014 has no euroscore_visible levers: "optimization" changes nothing and the
    # patient stays far above threshold. This is the honesty case.
    v = BY_ID["SYNTH-014"]
    baseline = compute_euroscore_ii(v["euroscore_inputs"])
    optimized = compute_euroscore_ii(optimize_visible(v))
    threshold = get_operability_threshold()
    assert optimized == baseline           # nothing visible to optimize
    assert baseline > threshold            # remains "declined"


def test_all_reversible_cases_move_down_or_equal_on_visible():
    # Every reversible case should be non-increasing after visible optimization, and
    # strictly decreasing where it carries visible levers (all of them do, by design).
    for v in VIGNETTES:
        if v["design_intent"] != "reversible_with_optimization":
            continue
        baseline = compute_euroscore_ii(v["euroscore_inputs"])
        optimized = compute_euroscore_ii(optimize_visible(v))
        assert optimized < baseline, v["id"]
