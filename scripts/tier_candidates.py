"""Candidate figure (2026-10-21): verdict accuracy down the three claim tiers (report -> cohort ->
two-cohort contrast) for the one-prompt baseline with the codebook and for ART with the verifier,
one line per model. Cohort/multi numbers come from the test runs' per_tier blocks; report-tier
numbers from the report case-study runs (testrep_*), falling back to the values in tab:report.

    PYTHONPATH=src .venv313/bin/python scripts/tier_candidates.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import paper_figures as PF  # noqa: E402
import families_candidates as FC  # noqa: E402

OUT = REPO / "docs" / "draft" / "Figures" / "candidates"
R = REPO / "results"
MODELS = [("q25pair", "Qwen2.5-32B pair"), ("qwen38_27b", "qwen3.8-27B"), ("gemma4_31b", "gemma4-31B"), ("opus", "Opus 5.5"), ("gpt", "GPT-5.6")]
COLS = FC.PALETTES_STRONG["meadow"]
TIERS = ["report\n(read one timeline)", "cohort\n(count, test)", "two cohorts\n(contrast)"]
REPORT_FALLBACK = {"cellB": {"q25pair": 0.750, "qwen38_27b": 1.000, "gemma4_31b": 1.000, "opus": 1.000, "gpt": 1.000},
                   "dprime_verify2": {"q25pair": 1.000, "qwen38_27b": 1.000, "gemma4_31b": 1.000, "opus": 0.983, "gpt": 1.000}}


def tier_acc(key: str, suf: str):
    m = json.loads((R / f"test_{key}_{suf}" / "metrics.json").read_text())["per_tier"]
    rep = R / f"testrep_{key}_{suf}" / "metrics.json"
    r = json.loads(rep.read_text())["verdict"]["accuracy"] if rep.exists() else REPORT_FALLBACK[suf][key]
    return [r, m["vaccine"]["accuracy"], m["multi"]["accuracy"]]


def main() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7), sharey=True)
    for ax, suf, title in ((axes[0], "cellB", "Straight-to-SQL + codebook"), (axes[1], "dprime_verify2", "ART + verifier")):
        x = np.arange(3)
        for j, (key, label) in enumerate(MODELS):
            y = tier_acc(key, suf)
            ax.plot(x, y, color=COLS[j], lw=1.8, marker="o", ms=4.5, markeredgecolor="white", markeredgewidth=0.6, label=label, zorder=5 - j)
            ax.text(x[-1] + 0.08, y[-1], f"{y[-1]:.3f}", fontsize=6, color=COLS[j], va="center", ha="left")
        ax.set_xticks(x); ax.set_xticklabels(TIERS)
        ax.set_xlim(-0.3, 2.7); ax.set_ylim(0.25, 1.05)
        ax.set_title(title, loc="left", fontsize=9)
        PF.boldify(ax, size=7.5)
        ax.grid(axis="y")
    axes[0].set_ylabel("verdict accuracy")
    axes[1].legend(frameon=False, fontsize=6.6, loc="lower left", ncol=2, handlelength=1.4, columnspacing=1.0)
    fig.tight_layout(w_pad=1.2)
    fig.savefig(OUT / "tiers_1.png", bbox_inches="tight", dpi=180); fig.savefig(OUT / "tiers_1.pdf", bbox_inches="tight")
    plt.close(fig); print("wrote", OUT / "tiers_1.png")
    for suf in ("cellB", "dprime_verify2"):
        print(suf, {k: [round(v, 3) for v in tier_acc(k, suf)] for k, _ in MODELS})


if __name__ == "__main__":
    main()
