"""
Metrics report (Step 9, Part B) — the slide-ready summary over all vignettes.
Deterministic aggregation of the rule-based harness results.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from eval.harness import evaluate_all


def build_metrics(evals=None) -> dict:
    evals = evals if evals is not None else evaluate_all()
    total = len(evals)

    check_names = [c.check for c in evals[0].results] if evals else []
    per_check = {}
    for name in check_names:
        passed = sum(1 for e in evals for c in e.results if c.check == name and c.passed)
        per_check[name] = {"passed": passed, "total": total,
                           "rate": round(passed / total, 3) if total else 0.0}

    overall_checks = sum(len(e.results) for e in evals)
    overall_passed = sum(1 for e in evals for c in e.results if c.passed)

    # per-design-intent terminal-state accuracy (operability_threshold_correctness)
    per_intent = defaultdict(lambda: {"passed": 0, "total": 0})
    for e in evals:
        chk = next(c for c in e.results if c.check == "operability_threshold_correctness")
        per_intent[e.design_intent]["total"] += 1
        per_intent[e.design_intent]["passed"] += 1 if chk.passed else 0

    terminal_tally = Counter(e.terminal_state for e in evals)
    trip_distribution = Counter(e.trip_count for e in evals)

    conflicts_detected = sum(e.conflicts_detected for e in evals)
    conflicts_resolved = sum(e.conflicts_resolved for e in evals)
    conflicts_escalated = sum(e.conflicts_escalated for e in evals)

    return {
        "total_vignettes": total,
        "checks_run": overall_checks,
        "checks_passed": overall_passed,
        "overall_pass_rate": round(overall_passed / overall_checks, 3) if overall_checks else 0.0,
        "per_check": per_check,
        "per_design_intent_terminal_accuracy": dict(per_intent),
        "terminal_state_tally": dict(terminal_tally),
        "trip_count_distribution": dict(sorted(trip_distribution.items())),
        "conflicts": {"detected": conflicts_detected, "resolved": conflicts_resolved,
                      "escalated": conflicts_escalated},
        "flags": {
            "time_infeasible": sum(1 for e in evals if e.time_infeasible),
            "access_barrier": sum(1 for e in evals if e.access_barrier_count > 0),
        },
    }


def render_metrics_text(metrics: dict) -> str:
    L = []
    L.append("=" * 70)
    L.append("OPERABILITY REVERSAL AGENT — EVALUATION METRICS")
    L.append("=" * 70)
    L.append(f"Vignettes: {metrics['total_vignettes']}   "
             f"Checks: {metrics['checks_passed']}/{metrics['checks_run']} passed "
             f"({metrics['overall_pass_rate'] * 100:.1f}%)")

    L.append("\nPass rate per check:")
    for name, s in metrics["per_check"].items():
        L.append(f"  {name:<34} {s['passed']}/{s['total']}  ({s['rate'] * 100:.0f}%)")

    L.append("\nTerminal-state accuracy per design_intent:")
    for di, s in metrics["per_design_intent_terminal_accuracy"].items():
        L.append(f"  {di:<32} {s['passed']}/{s['total']}")

    L.append("\nTerminal-state tally (should sum to total):")
    for st, n in metrics["terminal_state_tally"].items():
        L.append(f"  {st:<32} {n}")

    L.append("\nConflicts:")
    c = metrics["conflicts"]
    L.append(f"  detected={c['detected']}  resolved={c['resolved']}  escalated={c['escalated']}")

    L.append("\nTrip-count distribution (trips to Bhavnagar):")
    for trips, n in metrics["trip_count_distribution"].items():
        L.append(f"  {trips} trip(s): {n} vignette(s)")

    L.append("\nOrthogonal flags:")
    L.append(f"  time_infeasible: {metrics['flags']['time_infeasible']}   "
             f"access_barrier: {metrics['flags']['access_barrier']}")
    return "\n".join(L)
