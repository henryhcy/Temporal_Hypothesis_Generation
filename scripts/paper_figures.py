"""The paper's result figures, drawn from the finished runs (2026-10-20).

Four figures, each placed next to the table it visualises (the tables stay):
  rounds.pdf     repair-round curves: verdict accuracy and denominator F1 vs rounds 0-3, per model
  families.pdf   heatmap: the contract's gain over the end-to-end control by claim family and model
  modular.pdf    stage ceilings per model: all gold -> S1 alone -> S2 alone -> full pipeline -> + verifier
  registers.pdf  paraphrase case study (development set, 32B pair): accuracy by register

Numbers come from results/<run>/metrics.json (test set) and the registers runs (dev), so the
figures match the tables. Palette: a muted coastal set (charcoal, slate, sea blue, sand).

    PYTHONPATH=src .venv313/bin/python scripts/paper_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

REPO = Path(__file__).resolve().parents[1]
R = REPO / "results"
OUT = REPO / "docs" / "draft" / "Figures"
OUT.mkdir(parents=True, exist_ok=True)

# ---- palette: coast ----------------------------------------------------------
CHARCOAL = "#3A3F44"
SLATE = "#5B7C99"
SEA = "#8FB3C9"
MIST = "#C9D8E2"
SAND = "#E6DCC8"
DUNE = "#B9A98A"
DRIFT = "#8C7B5E"
PAPER = "#FBFAF7"
MODELS = [("q25pair", "Qwen2.5-32B pair", DRIFT),
          ("qwen38_27b", "qwen3.8-27B", DUNE),
          ("gemma4_31b", "gemma4-31B", SLATE),
          ("opus", "Opus 5.5", CHARCOAL),
          ("gpt", "GPT-5.6", SEA)]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Liberation Sans", "DejaVu Sans"],
    "font.size": 8.5, "axes.titlesize": 9, "axes.labelsize": 8.5,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 7.5,
    "axes.edgecolor": CHARCOAL, "axes.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": CHARCOAL, "ytick.color": CHARCOAL, "text.color": CHARCOAL, "axes.labelcolor": CHARCOAL,
    "grid.color": "#DDD8CF", "grid.linewidth": 0.5, "axes.grid": True, "axes.grid.axis": "y",
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "pdf.fonttype": 42,
})


def metric(run: str, *keys, default=None):
    p = R / run / "metrics.json"
    if not p.exists():
        return default
    d = json.loads(p.read_text())
    for k in keys:
        d = d.get(k, {}) if isinstance(d, dict) else {}
    return d if d != {} else default


def acc(run: str):
    return metric(run, "verdict", "accuracy")


def den_f1(run: str):
    return metric(run, "retrieval", "denominator", "f1")


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight", dpi=200)
    plt.close(fig)
    print("wrote", OUT / f"{name}.pdf")


# ---- 1. repair-round curves ----------------------------------------------------
def fig_rounds():
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.5), sharex=True)
    rounds = [0, 1, 2, 3]
    suffix = {0: "dprime", 1: "dprime_verify1", 2: "dprime_verify2", 3: "dprime_verify3"}
    for key, label, col in MODELS:
        a = [acc(f"test_{key}_{suffix[r]}") for r in rounds]
        f = [den_f1(f"test_{key}_{suffix[r]}") for r in rounds]
        for ax, y in ((axes[0], a), (axes[1], f)):
            xs = [r for r, v in zip(rounds, y) if v is not None]
            ys = [v for v in y if v is not None]
            ax.plot(xs, ys, marker="o", ms=4, lw=1.6, color=col, label=label, solid_capstyle="round")
    axes[0].set_title("verdict accuracy", loc="left")
    axes[1].set_title("denominator F1", loc="left")
    for ax in axes:
        ax.set_xticks(rounds)
        ax.set_xlabel("verify-and-repair rounds")
        ax.set_ylim(0.70, 1.005)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="lower center", ncol=5, handlelength=1.6,
               bbox_to_anchor=(0.5, -0.04), columnspacing=1.6)
    fig.tight_layout(w_pad=2.0, rect=(0, 0.06, 1, 1))
    save(fig, "rounds")


# ---- 2. family heatmap ---------------------------------------------------------
def fig_families():
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from group_table import per_key, family_of  # noqa: E402
    from temporal_hypo.framework.io import load_release  # noqa: E402
    rel = load_release(REPO / "data" / "release" / "v1.2", verify_sha=False)
    fams = [("precedes", "precedes"), ("co-occurs", "co-occurs"), ("first/last", "first/last"),
            ("proximity", "proximity"), ("threshold", "threshold"), ("position", "position")]
    ours = np.full((len(fams), len(MODELS)), np.nan)
    ctrl = np.full((len(fams), len(MODELS)), np.nan)
    for j, (key, label, _) in enumerate(MODELS):
        d = per_key(R / f"test_{key}_dprime_verify2", rel, family_of)
        b = per_key(R / f"test_{key}_cellB", rel, family_of)
        for i, (f, _) in enumerate(fams):
            if f in d:
                ours[i, j] = d[f][0] / d[f][1]
            if f in b:
                ctrl[i, j] = b[f][0] / b[f][1]
    gain = ours - ctrl
    cmap = LinearSegmentedColormap.from_list("coast", [SAND, "#F3EFE6", MIST, SEA, SLATE])
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    ax.grid(False)
    im = ax.imshow(gain, cmap=cmap, vmin=-0.05, vmax=0.45, aspect="auto")
    ax.set_xticks(range(len(MODELS)))
    short = {"q25pair": "Qwen2.5\n32B pair", "qwen38_27b": "qwen3.8\n27B", "gemma4_31b": "gemma4\n31B",
             "opus": "Opus\n5.5", "gpt": "GPT\n5.6"}
    ax.set_xticklabels([short[m[0]] for m in MODELS], rotation=0)
    ax.set_yticks(range(len(fams)))
    ax.set_yticklabels([f[1] for f in fams])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    for i in range(len(fams)):
        for j in range(len(MODELS)):
            g = gain[i, j]
            dark = g > 0.22
            gtxt = f"{g:+.3f}" if abs(g) >= 0.0005 else "0.000"
            ax.text(j, i - 0.14, gtxt, ha="center", va="center", fontsize=8,
                    color="white" if dark else CHARCOAL, fontweight="bold")
            ax.text(j, i + 0.2, f"{ours[i, j]:.3f} vs {ctrl[i, j]:.3f}", ha="center", va="center",
                    fontsize=6.0, color="white" if dark else "#6B6F73")
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.outline.set_visible(False)
    cb.ax.tick_params(length=0, labelsize=7)
    cb.set_label("gain of the contract over\nthe end-to-end control", fontsize=7)
    ax.set_title("verdict accuracy by claim family: ours (D$'$ + verifier) vs B", loc="left", fontsize=8.5)
    fig.tight_layout()
    save(fig, "families")


# ---- 3. modular stage ceilings -------------------------------------------------
def fig_modular():
    steps = [("all stages at gold", lambda k: 1.0),
             ("S1 alone", lambda k: acc(f"test_{k}_planner_verify2") or acc(f"test_{k}_planner_verify1")),
             ("S2 alone", lambda k: acc(f"test_{k}_sqlalone_verify2")),
             ("S1 + S2 + S3, no verifier", lambda k: acc(f"test_{k}_dprime")),
             ("+ verifier (ours)", lambda k: acc(f"test_{k}_dprime_verify2"))]
    colors = [MIST, SEA, SLATE, DUNE, CHARCOAL]
    fig, axes = plt.subplots(1, len(MODELS), figsize=(7.0, 2.6), sharey=True)
    for ax, (key, label, _) in zip(axes, MODELS):
        vals = []
        for name, fn in steps:
            v = fn(key)
            if v is None and name == "S2 alone" and key in ("opus", "gpt"):
                v = 0.999  # bounded below by the D' denominator F1 of 1.000 (see the table caption)
            vals.append(v)
        xs = np.arange(len(steps))
        bars = ax.bar(xs, [v if v is not None else 0 for v in vals], color=colors, width=0.72,
                      edgecolor="white", linewidth=0.5)
        for x, v, name in zip(xs, vals, [s[0] for s in steps]):
            if v is None:
                continue
            txt = f"{v:.3f}" if not (name == "S2 alone" and key in ("opus", "gpt")) else "$\\geq$.999"
            ax.text(x, v + 0.012, txt, ha="center", va="bottom", fontsize=6.2, color=CHARCOAL, rotation=90)
        ax.set_title(label, loc="left", fontsize=8.5)
        ax.set_xticks(xs)
        ax.set_xticklabels(["gold", "S1", "S2", "full", "+ver"], fontsize=7)
        ax.set_ylim(0.5, 1.12)
        ax.set_yticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        ax.spines["left"].set_visible(ax is axes[0])
        if ax is not axes[0]:
            ax.tick_params(axis="y", length=0)
    axes[0].set_ylabel("verdict accuracy")
    fig.text(0.0, 0.0, "gold: every stage at gold.  S1 / S2: the model fills that stage only.  "
             "full: model plan, model retrieval, exact test (ours).  +ver: with the verifier.",
             fontsize=6.6, color="#6B6F73", ha="left", va="bottom")
    fig.tight_layout(w_pad=0.6, rect=(0, 0.05, 1, 1))
    save(fig, "modular")


# ---- 4. paraphrase registers (dev, 32B pair) -------------------------------------
def fig_registers():
    regs = ["Original", "Research", "Media", "Clinical"]
    # from Table tab:registers (development set, claim form; planner row at one round)
    rows = [("planner alone (S2, S3 at gold)", [0.955, 0.838, 0.877, 0.935], MIST),
            ("D$'$", [0.865, 0.790, 0.755, 0.825], SEA),
            ("D$'$ + verifier", [0.870, 0.815, 0.770, 0.840], SLATE),
            ("B (end-to-end control)", [0.640, 0.587, 0.600, 0.557], DUNE)]
    fig, ax = plt.subplots(figsize=(4.6, 2.5))
    x = np.arange(len(regs)); w = 0.2
    for i, (label, vals, col) in enumerate(rows):
        ax.bar(x + (i - 1.5) * w, vals, width=w, color=col, label=label, edgecolor="white", linewidth=0.5)
        for xi, v in zip(x + (i - 1.5) * w, vals):
            ax.text(xi, v + 0.008, f"{v:.3f}", ha="center", va="bottom", fontsize=5.6, color=CHARCOAL, rotation=90)
    ax.set_xticks(x)
    ax.set_xticklabels(regs)
    ax.set_ylim(0.4, 1.08)
    ax.set_ylabel("verdict accuracy")
    ax.set_title("paraphrase registers, development set, Qwen2.5-32B pair", loc="left", fontsize=8.5)
    ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.14), fontsize=6.6,
              handlelength=1.2, columnspacing=1.0)
    fig.tight_layout()
    save(fig, "registers")


if __name__ == "__main__":
    fig_rounds()
    fig_families()
    fig_modular()
    fig_registers()
