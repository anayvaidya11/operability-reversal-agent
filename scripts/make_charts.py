#!/usr/bin/env python3
"""
Generate the two pitch-deck charts from REAL pipeline output (no hardcoded scores).

    python scripts/make_charts.py

Writes:
    deck_assets/grandmother_risk_descent.png
    deck_assets/three_case_outcomes.png
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.loop import run_reassessment_loop
from src.gate import apply_access_gate
from src.config import get_operability_threshold

# --- palette ---
INK = "#1A2E35"
PRIMARY = "#0B7A75"
DANGER = "#C1121F"
MUTED = "#9DB4B8"
WHITE = "#FFFFFF"

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "deck_assets")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 13,
    "text.color": INK,
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "figure.facecolor": WHITE,
    "axes.facecolor": WHITE,
    "savefig.facecolor": WHITE,
})


def load():
    return {v["id"]: v for v in json.loads(
        open(os.path.join(REPO, "data", "vignettes.json")).read())["vignettes"]}


def _clean(ax):
    ax.spines[["top", "right"]].set_visible(False)


def chart1(vignettes, threshold):
    """Grandmother's real risk descent across her applied phases."""
    loop = run_reassessment_loop(vignettes["SYNTH-006"])
    ys = [round(it.score_after, 2) for it in loop.trace]   # real: [7.38, 5.89]
    xs = list(range(len(ys)))
    labels = ["Baseline", "After Phase 1\n(prehab + glycemic)"]

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    # subtle operable zone below threshold
    ax.axhspan(0, threshold, color=PRIMARY, alpha=0.06, zorder=0)
    # threshold line
    ax.axhline(threshold, color=DANGER, linestyle="--", linewidth=1.6, zorder=1)
    ax.text(len(ys) - 1, threshold + 0.12, "Operability threshold (6%)",
            color=DANGER, fontsize=11, ha="right", va="bottom")
    # data line
    ax.plot(xs, ys, color=PRIMARY, linewidth=2.4, marker="o", markersize=9,
            markerfacecolor=PRIMARY, markeredgecolor=WHITE, zorder=3)
    # point value annotations
    ax.annotate(f"{ys[0]:.2f}%", (xs[0], ys[0]), textcoords="offset points",
                xytext=(0, 12), ha="center", fontsize=12, color=INK, fontweight="bold")
    ax.annotate(f"{ys[-1]:.2f}%", (xs[-1], ys[-1]), textcoords="offset points",
                xytext=(0, -20), ha="center", fontsize=12, color=PRIMARY, fontweight="bold")
    # crossing note
    ax.text(xs[-1], ys[-1] + 0.9, "Crosses to operable", color=PRIMARY, fontsize=11,
            ha="center", va="bottom")

    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_xlim(-0.35, len(ys) - 0.55)
    ax.set_ylim(0, 9)
    ax.set_ylabel("Predicted surgical mortality (%)", fontsize=13)
    _clean(ax)
    fig.tight_layout()
    path = os.path.join(OUT, "grandmother_risk_descent.png")
    fig.savefig(path, dpi=200, bbox_inches="tight", transparent=False, facecolor=WHITE)
    plt.close(fig)
    return path, ys


def chart2(vignettes, threshold):
    """Three demo cases, three honest outcomes (baseline vs final, grouped h-bars)."""
    specs = [
        ("SYNTH-006", "Grandmother", "Reversed to operable", False, False),
        ("SYNTH-008", "SYNTH-008", "Optimized hard, still declined; no time", True, False),
        ("SYNTH-019", "SYNTH-019", "Reversible, but not reachable", False, True),
    ]
    rows = []
    for vid, name, outcome, want_time, want_barrier in specs:
        loop = run_reassessment_loop(vignettes[vid])
        gate = apply_access_gate(loop)
        rows.append({
            "name": name, "outcome": outcome,
            "baseline": round(loop.baseline_score, 2),
            "final": round(loop.final_score, 2),
            "time_infeasible": loop.time_infeasible,
            "barrier": len(gate.access_barriers) > 0,
        })

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ys = [2, 1, 0]          # Grandmother top
    h = 0.30
    for y, r in zip(ys, rows):
        ax.barh(y + 0.19, r["baseline"], height=h, color=MUTED, zorder=2)
        ax.barh(y - 0.19, r["final"], height=h, color=PRIMARY, zorder=2)
        ax.text(r["baseline"] + 0.3, y + 0.19, f"{r['baseline']:.2f}%",
                va="center", ha="left", fontsize=10.5, color=INK)
        # final label; access-barrier case marked with a red asterisk
        star = " *" if r["barrier"] else ""
        ax.text(r["final"] + 0.3, y - 0.19, f"{r['final']:.2f}%{star}",
                va="center", ha="left", fontsize=10.5,
                color=(DANGER if r["barrier"] else PRIMARY),
                fontweight="bold" if r["barrier"] else "normal")
        # outcome label (right column)
        ax.text(24.3, y, r["outcome"], va="center", ha="left", fontsize=10.5, color=INK)

    # threshold
    ax.axvline(threshold, color=DANGER, linestyle="--", linewidth=1.6, zorder=3)
    ax.text(threshold + 0.3, 3.05, "Operability threshold (6%)", color=DANGER,
            fontsize=10.5, ha="left", va="top")

    # access-barrier footnote (aligned under the SYNTH-019 outcome)
    ax.text(24.3, -0.52, "* crosses clinically, but blocked on access", color=DANGER,
            fontsize=9.5, ha="left", va="center")

    # legend (proxy patches so palette colors render; placed above the axes)
    from matplotlib.patches import Patch
    handles = [Patch(color=MUTED, label="Baseline risk"),
               Patch(color=PRIMARY, label="After optimization")]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.02),
              ncol=2, frameon=False, fontsize=11)

    ax.set_yticks(ys)
    ax.set_yticklabels([r["name"] for r in rows], fontsize=11.5)
    ax.set_xlim(0, 44)
    ax.set_ylim(-0.85, 3.25)
    ax.set_xlabel("Predicted surgical mortality (%)", fontsize=13)
    ax.set_xticks([0, 6, 10, 20])
    _clean(ax)
    fig.tight_layout()
    path = os.path.join(OUT, "three_case_outcomes.png")
    fig.savefig(path, dpi=200, bbox_inches="tight", transparent=False, facecolor=WHITE)
    plt.close(fig)
    return path, rows


def main():
    vignettes = load()
    thr = get_operability_threshold()
    p1, ys = chart1(vignettes, thr)
    p2, rows = chart2(vignettes, thr)
    print(f"threshold = {thr}")
    print(f"chart1 {os.path.relpath(p1, REPO)}  grandmother stages = {ys}")
    print(f"chart2 {os.path.relpath(p2, REPO)}")
    for r in rows:
        print(f"  {r['name']:<12} {r['baseline']:.2f} -> {r['final']:.2f}  "
              f"time_infeasible={r['time_infeasible']} barrier={r['barrier']}  ({r['outcome']})")


if __name__ == "__main__":
    main()
