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
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
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
# avocado set for the heatmap (brown for losses, cream at zero, green for gains)
A_BROWN = "#8B6B4A"; A_TAN = "#C9B38E"; A_CREAM = "#F3F0E4"; A_LIME = "#C8C46E"; A_AVO = "#8A9A55"; A_OLIVE = "#5C6B3A"
MODELS = [("q25pair", "Qwen2.5-32B pair", DRIFT),
          ("qwen38_27b", "qwen3.8-27B", DUNE),
          ("gemma4_31b", "gemma4-31B", SLATE),
          ("opus", "Opus 5.5", CHARCOAL),
          ("gpt", "GPT-5.6", SEA)]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Liberation Sans", "DejaVu Sans"],
    "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.labelsize": 10, "axes.labelweight": "bold",
    "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 8,
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


def boldify(ax, size=9):
    """Bold, larger tick labels on both axes."""
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_fontweight("bold"); lab.set_fontsize(size)


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight", dpi=200)
    plt.close(fig)
    print("wrote", OUT / f"{name}.pdf")


# ---- 1. repair rounds: where the gain comes from -------------------------------------------
def fig_rounds():
    """Per model, a horizontal bar that starts at the 0-round value and adds the gain of each repair
    round as a segment (round 1 darkest). Losses (the frontier) extend to the left in brown. Two panels:
    verdict accuracy and denominator F1. The round-0 and round-3 values are printed at the ends."""
    suffix = {0: "dprime", 1: "dprime_verify1", 2: "dprime_verify2", 3: "dprime_verify3"}
    seg_cols = [SLATE, SEA, MIST]           # gains of rounds 1, 2, 3
    loss_cols = [A_BROWN, A_TAN, "#E0D3BF"]  # losses of rounds 1, 2, 3
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6), sharey=True)
    ys = np.arange(len(MODELS))[::-1]
    for ax, getter, title, lo in ((axes[0], acc, "verdict accuracy", 0.66), (axes[1], den_f1, "denominator F1", 0.66)):
        for y, (key, label, _) in zip(ys, MODELS):
            vals = [getter(f"test_{key}_{suffix[r]}") for r in range(4)]
            if any(v is None for v in vals):
                continue
            ax.plot([lo, vals[0]], [y, y], color="#D9D3C7", lw=6, solid_capstyle="butt", zorder=1)
            pos = vals[0]
            for r in (1, 2, 3):
                d = vals[r] - vals[r - 1]
                if d >= 0:
                    ax.barh(y, d, left=pos, height=0.56, color=seg_cols[r - 1], edgecolor="white", linewidth=0.4, zorder=2)
                    pos += d
                else:
                    ax.barh(y, d, left=pos, height=0.56, color=loss_cols[r - 1], edgecolor="white", linewidth=0.4, zorder=2)
                    pos += d
            ax.plot([vals[0]], [y], marker="|", ms=12, color=CHARCOAL, mew=1.4, zorder=3)
            if vals[3] - vals[0] < 0.03:   # tiny change: stack the two labels above and below the row
                ax.text(vals[0], y + 0.34, f"{vals[0]:.3f} $\\rightarrow$ {vals[3]:.3f}", ha="right", va="bottom",
                        fontsize=7, color=CHARCOAL, fontweight="bold")
            else:
                ax.text(vals[0] - 0.006, y, f"{vals[0]:.3f}", ha="right", va="center", fontsize=7, color=CHARCOAL, fontweight="bold")
                ax.text(max(vals[0], vals[3]) + 0.006, y, f"{vals[3]:.3f}", ha="left", va="center", fontsize=7, color=CHARCOAL, fontweight="bold")
        ax.set_yticks(ys)
        ax.set_yticklabels([m[1] for m in MODELS])
        ax.set_xlim(lo, 1.06)
        ax.set_xticks([0.7, 0.8, 0.9, 1.0])
        ax.set_ylim(-0.7, len(MODELS) - 0.3)
        ax.set_title(title, loc="left")
        ax.grid(axis="x"); ax.grid(False, axis="y")
        ax.set_xlabel("after 0 rounds  $\\rightarrow$  after 3 rounds")
        boldify(ax)
    from matplotlib.patches import Patch
    handles = [Patch(color=SLATE, label="gain, round 1"), Patch(color=SEA, label="gain, round 2"),
               Patch(color=MIST, label="gain, round 3"), Patch(color=A_BROWN, label="loss, round 1"),
               Patch(color=A_TAN, label="loss, round 2")]
    fig.legend(handles=handles, frameon=False, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.04),
               fontsize=7.5, handlelength=1.4, columnspacing=1.4)
    fig.tight_layout(w_pad=1.5, rect=(0, 0.07, 1, 1))
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
    cmap = LinearSegmentedColormap.from_list("avocado", [A_BROWN, A_TAN, A_CREAM, A_LIME, A_AVO, A_OLIVE])
    norm = TwoSlopeNorm(vmin=-0.12, vcenter=0.0, vmax=0.42)
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    ax.grid(False)
    im = ax.imshow(gain, cmap=cmap, norm=norm, aspect="auto")
    ax.set_xticks(range(len(MODELS)))
    short = {"q25pair": "Qwen2.5\n32B pair", "qwen38_27b": "qwen3.8\n27B", "gemma4_31b": "gemma4\n31B",
             "opus": "Opus\n5.5", "gpt": "GPT\n5.6"}
    ax.set_xticklabels([short[m[0]] for m in MODELS], rotation=0)
    ax.set_yticks(range(len(fams)))
    ax.set_yticklabels([f[1] for f in fams])
    boldify(ax, size=9)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    for i in range(len(fams)):
        for j in range(len(MODELS)):
            g = gain[i, j]
            dark = g > 0.25 or g < -0.07
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


# ---- 3. modular analysis: dot plot of the pipeline against its stage ceilings -------------------
def fig_modular():
    """One row per model on a verdict-accuracy axis: the end-to-end control (B), our pipeline without and
    with the verifier (joined by a line: what the contract and the verifier add), and the two stage
    ceilings as open markers (S1: model plan, gold retrieval; S2: gold plan, model retrieval); every
    stage at gold is the right edge, 1.000."""
    fig, ax = plt.subplots(figsize=(7.2, 3.1))
    ys = np.arange(len(MODELS))[::-1]
    for y, (key, label, _) in zip(ys, MODELS):
        b = acc(f"test_{key}_cellB"); o = acc(f"test_{key}_dprime"); ov = acc(f"test_{key}_dprime_verify2")
        s1 = acc(f"test_{key}_planner_verify2") or acc(f"test_{key}_planner_verify1")
        s2 = acc(f"test_{key}_sqlalone_verify2"); s2_bound = s2 is None and key in ("opus", "gpt")
        if s2_bound:
            s2 = 0.999
        ax.plot([min(b, o, ov), max(b, o, ov)], [y, y], color="#D9D3C7", lw=5, solid_capstyle="round", zorder=1)
        ax.plot([b], [y], marker="o", ms=8, color=SAND, markeredgecolor=DRIFT, mew=0.8, zorder=3, ls="none", label="B: end-to-end control" if y == ys[0] else None)
        ax.plot([o], [y], marker="o", ms=8, color=SEA, markeredgecolor="white", mew=0.6, zorder=3, ls="none", label="ours, no verifier" if y == ys[0] else None)
        ax.plot([ov], [y], marker="o", ms=9, color=SLATE, markeredgecolor="white", mew=0.6, zorder=4, ls="none", label="ours + verifier" if y == ys[0] else None)
        ax.plot([s1], [y], marker="|", ms=16, color=CHARCOAL, mew=1.6, zorder=5, ls="none", label="S1 ceiling: model plan, gold retrieval" if y == ys[0] else None)
        ax.plot([s2], [y], marker="|", ms=16, color=A_BROWN, mew=1.6, zorder=5, ls="none", label="S2 ceiling: gold plan, model retrieval" if y == ys[0] else None)
        spread = max(b, o, ov) - min(b, o, ov)
        if spread >= 0.03:   # room for point labels: B below, ours above, ours+verifier above
            ax.text(b, y - 0.3, f"{b:.3f}", ha="center", va="top", fontsize=6.8, color=DRIFT, fontweight="bold")
            ax.text(ov, y + 0.3, f"{ov:.3f}", ha="center", va="bottom", fontsize=6.8, color=SLATE, fontweight="bold")
            if abs(o - ov) > 0.04 and abs(o - b) > 0.04:
                ax.text(o, y + 0.3, f"{o:.3f}", ha="center", va="bottom", fontsize=6.8, color=SEA, fontweight="bold")
            elif abs(o - b) > 0.04:
                ax.text(o, y - 0.3, f"{o:.3f}", ha="center", va="top", fontsize=6.8, color=SEA, fontweight="bold")
        s2_txt = "$\\geq$.999" if s2_bound else f"{s2:.3f}"
        side = (f"B {b:.3f}  ours {o:.3f}  +ver {ov:.3f}\n" if spread < 0.03 else "") + f"ceilings  S1 {s1:.3f}  S2 {s2_txt}"
        ax.text(1.04, y, side, ha="left", va="center", fontsize=6.6, color="#6B6F73", linespacing=1.3)
    ax.axvline(1.0, color="#B8B2A6", lw=0.8, zorder=0)
    ax.set_yticks(ys); ax.set_yticklabels([m[1] for m in MODELS])
    ax.set_ylim(-0.75, len(MODELS) - 0.25)
    ax.set_xlim(0.52, 1.30); ax.set_xticks([0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_xlabel("verdict accuracy on the test set", loc="left")
    ax.grid(axis="x"); ax.grid(False, axis="y")
    ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
    boldify(ax)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, -0.22), ncol=3, fontsize=7.2,
              handlelength=1.6, columnspacing=1.2, markerscale=0.9)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
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
    boldify(ax)
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
