#!/usr/bin/env python3
"""
Vignette score audit (Step 4.5, diagnostic).

For every vignette, prints baseline and optimized EuroSCORE II %, and whether it
satisfies its design_intent's score property against OPERABILITY_THRESHOLD:

  operable_at_baseline          : baseline < threshold
  reversible_with_optimization  : baseline >= threshold AND optimized < threshold
  fixed_high_risk               : baseline >= threshold AND optimized >= threshold

"Optimized" flips every euroscore_visible lever to its best realistic state using the
ONE shared convention in src/optimized_state.py (chronic_lung_disease/poor_mobility/
critical_preoperative_state -> false; nyha_class -> "I" if II/III else "II" for IV).

Run:  python3 scripts/vignette_score_audit.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.risk_calculator import compute_euroscore_ii            # noqa: E402
from src.decomposer import decompose                            # noqa: E402
from src.optimized_state import optimized_inputs                # noqa: E402
from src.config import get_operability_threshold                # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIGNETTES = json.load(open(os.path.join(REPO, "data", "vignettes.json")))["vignettes"]


def satisfies(design_intent: str, baseline: float, optimized: float, thr: float) -> bool:
    if design_intent == "operable_at_baseline":
        return baseline < thr
    if design_intent == "reversible_with_optimization":
        return baseline >= thr and optimized < thr
    if design_intent == "fixed_high_risk":
        return baseline >= thr and optimized >= thr
    raise ValueError(f"unknown design_intent {design_intent!r}")


def main() -> int:
    thr = get_operability_threshold()
    print(f"OPERABILITY_THRESHOLD = {thr:.1f}%\n")
    header = f"{'id':<11} {'design_intent':<30} {'baseline':>9} {'optimized':>10}  {'ok?':>4}"
    print(header)
    print("-" * len(header))
    all_ok = True
    by_intent = {}
    for v in VIGNETTES:
        di = v["design_intent"]
        base = compute_euroscore_ii(v["euroscore_inputs"])
        opt = compute_euroscore_ii(optimized_inputs(v, decompose(v)))
        ok = satisfies(di, base, opt, thr)
        all_ok = all_ok and ok
        by_intent.setdefault(di, [0, 0])
        by_intent[di][0] += 1
        by_intent[di][1] += 1 if ok else 0
        print(f"{v['id']:<11} {di:<30} {base:>8.2f}% {opt:>9.2f}%  {'OK' if ok else 'FAIL':>4}")
    print("-" * len(header))
    for di, (n, ok) in sorted(by_intent.items()):
        print(f"  {di:<30} {ok}/{n} satisfy score property")
    print(f"\nALL SATISFY: {all_ok}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
