"""
Threshold-sensitivity tests (Step 3) — the core of the reversal demo.

These prove the Option-A pathway: optimizing the EuroSCORE-VISIBLE levers moves the
predicted score DOWN, before any (deferred, Option-B) supplementary modifier layer
exists.

HONEST FINDING (see Step-3 report / a Step-4 decision):
With the real EuroSCORE II coefficients and the DEFAULT OPERABILITY_THRESHOLD (8.0%),
the grandmother's baseline (~7.38%) sits JUST BELOW the threshold — i.e. under the
default proxy she is not "declined at baseline". Optimization still nearly halves her
risk (~3.72%). SYNTH-008 is the vignette that both starts above the default threshold
and crosses below it on visible levers alone. Both facts are asserted below rather than
hidden.
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


def test_grandmother_starts_below_default_threshold_FINDING():
    # Documents the honest tension (not a fudge): at the DEFAULT 8.0% proxy the
    # grandmother is already sub-threshold. Flagged for a Step-4 decision.
    baseline = compute_euroscore_ii(BY_ID["SYNTH-006"]["euroscore_inputs"])
    assert baseline < get_operability_threshold()  # 7.38 < 8.0


def test_grandmother_crosses_a_high_risk_threshold_when_configured():
    # Threshold sensitivity: with the threshold set anywhere in the band between her
    # optimized and baseline scores (e.g. 7.0%, still a high-risk cutoff), the
    # grandmother is "declined at baseline" and becomes "operable" after visible-lever
    # optimization — demonstrating the crossing mechanism and the parameter's effect.
    g = BY_ID["SYNTH-006"]
    baseline = compute_euroscore_ii(g["euroscore_inputs"])
    optimized = compute_euroscore_ii(optimize_visible(g))
    demo_threshold = get_operability_threshold(threshold=7.0)
    assert baseline >= demo_threshold      # declined at baseline
    assert optimized < demo_threshold      # operable after optimization


# --- SYNTH-008: crosses the DEFAULT threshold on visible levers alone ----------------

def test_synth008_crosses_default_threshold_on_visible_levers():
    v = BY_ID["SYNTH-008"]
    baseline = compute_euroscore_ii(v["euroscore_inputs"])
    optimized = compute_euroscore_ii(optimize_visible(v))
    threshold = get_operability_threshold()  # default 8.0
    assert baseline >= threshold            # declined at baseline (~22.4%)
    assert optimized < threshold            # operable after optimization (~7.4%)
    assert optimized < baseline


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
