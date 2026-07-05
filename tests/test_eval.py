"""Tests for the Step 9 evaluation harness + metrics report."""

from eval import evaluate_all, build_metrics, render_metrics_text


def test_harness_runs_over_all_19():
    evals = evaluate_all()
    assert len(evals) == 19


def test_all_checks_pass_over_all_vignettes():
    evals = evaluate_all()
    failures = [(e.vignette_id, c.check, c.reason)
                for e in evals for c in e.results if not c.passed]
    assert failures == [], failures   # if this ever fails, it is a REAL finding


def test_metrics_render_and_internally_consistent():
    evals = evaluate_all()
    metrics = build_metrics(evals)
    text = render_metrics_text(metrics)

    assert metrics["total_vignettes"] == 19
    # terminal-state tally sums to 19
    assert sum(metrics["terminal_state_tally"].values()) == 19
    # trip distribution sums to 19
    assert sum(metrics["trip_count_distribution"].values()) == 19
    # per-check totals are all 19
    for name, s in metrics["per_check"].items():
        assert s["total"] == 19
    # conflicts: none escalated (all resolved) in current data
    assert metrics["conflicts"]["detected"] == metrics["conflicts"]["resolved"]
    assert metrics["conflicts"]["escalated"] == 0
    assert "EVALUATION METRICS" in text


def test_three_demo_cases_distinct_profiles():
    by_id = {e.vignette_id: e for e in evaluate_all()}

    # grandmother — clean reversal: operable after optimization, no barriers, no time issue
    g = by_id["SYNTH-006"]
    assert g.terminal_state == "OPERABLE_AFTER_OPTIMIZATION"
    assert g.access_barrier_count == 0
    assert g.time_infeasible is False

    # SYNTH-008 — clinical + time honesty: optimized-but-high AND time-infeasible
    s8 = by_id["SYNTH-008"]
    assert s8.terminal_state == "OPTIMIZED_BUT_STILL_HIGH_RISK"
    assert s8.time_infeasible is True
    assert s8.access_barrier_count == 0

    # SYNTH-019 — access honesty: clinically operable-after-optimization BUT access-barriered
    s19 = by_id["SYNTH-019"]
    assert s19.terminal_state == "OPERABLE_AFTER_OPTIMIZATION"
    assert s19.access_barrier_count == 1
