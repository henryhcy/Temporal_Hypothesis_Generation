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


# ---- 1. repair rounds: grouped bars, one group per model, one bar per round ----------------------
def fig_rounds():
    suffix = {0: "dprime", 1: "dprime_verify1", 2: "dprime_verify2", 3: "dprime_verify3"}
    cols = [SAND, MIST, SEA, SLATE]            # rounds 0..3, light to dark
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8))
    for ax, getter, title in ((axes[0], acc, "verdict accuracy"), (axes[1], den_f1, "denominator F1")):
        x = np.arange(len(MODELS)); w = 0.2
        for r in range(4):
            vals = [getter(f"test_{k}_{suffix[r]}") for k, _, _ in MODELS]
            xs = x + (r - 1.5) * w
            ax.bar(xs, [v or 0 for v in vals], width=w, color=cols[r], edgecolor="white", linewidth=0.5,
                   label=f"{r} round{'s' if r != 1 else ''}", zorder=2)
            for xi, v in zip(xs, vals):
                if v is not None:
                    ax.text(xi, v + 0.004, f"{v:.3f}", ha="center", va="bottom", fontsize=5.6, rotation=90,
                            color=CHARCOAL, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(["Qwen2.5\n32B pair", "qwen3.8\n27B", "gemma4\n31B", "Opus\n5.5", "GPT\n5.6"])
        ax.set_ylim(0.70, 1.06)
        ax.set_yticks([0.7, 0.8, 0.9, 1.0])
        ax.set_title(title, loc="left")
        boldify(ax, size=8.5)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, [l.replace("round", "verify-and-repair round", 1) if l.startswith("0") else l for l in labels],
               frameon=False, loc="lower center", ncol=4, fontsize=7.5, handlelength=1.4, columnspacing=1.6,
               bbox_to_anchor=(0.5, -0.03))
    fig.tight_layout(w_pad=1.5, rect=(0, 0.06, 1, 1))
    save(fig, "rounds")


# ---- 2. heatmap: faithfulness by claim family -----------------------------------------------
def _exact_flags(run: Path, gold: dict):
    """Per cohort-tier record: (family, verdict right, denominator exact in every arm)."""
    out = []
    for line in (run / "predictions.jsonl").open():
        x = json.loads(line)
        g = gold.get(x["hypothesis_id"])
        if not g or not g.get("retrieval", {}).get("arms"):
            continue
        right = (x.get("prediction") or {}).get("verdict") == g["prediction"]["verdict"]
        rt = x.get("retrieval") or {}
        parms = rt.get("arms") or []
        exact = bool(parms) and rt.get("ok") is not False and all(
            set(pa.get("denominator_ids") or []) == set(ga["denominator_ids"])
            for ga, pa in zip(g["retrieval"]["arms"], parms))
        out.append((x["group_id"].split("-")[0], right, exact))
    return out


def fig_families():
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from group_table import FAMILY  # noqa: E402
    gold = {json.loads(l)["hypothesis_id"]: json.loads(l) for l in (R / "test_gold_sets" / "predictions.jsonl").open()}
    fams = [("P", "precedes"), ("C", "co-occurs"), ("F", "first/last"), ("Y", "proximity"), ("H", "threshold"), ("T", "position")]
    panels = [("ours: D$'$ + verifier", "dprime_verify2"), ("B: end-to-end + conventions", "cellB")]
    mats = []
    for _, suffix in panels:
        M = np.full((len(fams), len(MODELS)), np.nan); N = np.zeros_like(M)
        for j, (key, _, _) in enumerate(MODELS):
            flags = _exact_flags(R / f"test_{key}_{suffix}", gold)
            for i, (code, _) in enumerate(fams):
                right = [e for c, r, e in flags if c == code and r]
                if right:
                    M[i, j] = sum(right) / len(right); N[i, j] = len(right)
        mats.append((M, N))
    cmap = LinearSegmentedColormap.from_list("avocado_seq", [A_BROWN, A_TAN, A_CREAM, A_LIME, A_AVO, A_OLIVE])
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.1), sharey=True)
    short = {"q25pair": "Qwen2.5\n32B pair", "qwen38_27b": "qwen3.8\n27B", "gemma4_31b": "gemma4\n31B", "opus": "Opus\n5.5", "gpt": "GPT\n5.6"}
    for ax, (title, _), (M, N) in zip(axes, panels, mats):
        ax.grid(False)
        im = ax.imshow(M, cmap=cmap, vmin=0.3, vmax=1.0, aspect="auto")
        ax.set_xticks(range(len(MODELS))); ax.set_xticklabels([short[m[0]] for m in MODELS])
        ax.set_yticks(range(len(fams))); ax.set_yticklabels([f[1] for f in fams])
        boldify(ax, size=8.5)
        for lab in ax.get_xticklabels():
            lab.set_fontsize(7.4)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(length=0)
        for i in range(len(fams)):
            for j in range(len(MODELS)):
                v = M[i, j]
                if np.isnan(v):
                    continue
                dark = v > 0.85 or v < 0.45
                ax.text(j, i - 0.12, f"{v:.3f}", ha="center", va="center", fontsize=8, fontweight="bold",
                        color="white" if dark else CHARCOAL)
                ax.text(j, i + 0.22, f"n = {int(N[i, j])}", ha="center", va="center", fontsize=6,
                        color="white" if dark else "#6B6F73")
        ax.set_title(title, loc="left")
    cb = fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02)
    cb.outline.set_visible(False); cb.ax.tick_params(length=0, labelsize=7)
    cb.set_label("faithfulness: P(denominator exact | verdict right)", fontsize=7)
    save(fig, "families")


# ---- 3. modular analysis: grouped bars, ceilings as outlined bars ---------------------------------
def fig_modular():
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    spec = [("B: end-to-end control", lambda k: acc(f"test_{k}_cellB"), dict(color=SAND)),
            ("ours, no verifier", lambda k: acc(f"test_{k}_dprime"), dict(color=SEA)),
            ("ours + verifier", lambda k: acc(f"test_{k}_dprime_verify2"), dict(color=SLATE)),
            ("S2 ceiling: gold plan, model retrieval", lambda k: acc(f"test_{k}_sqlalone_verify2") or (0.999 if k in ("opus", "gpt") else None),
             dict(color="white", edgecolor=A_BROWN, hatch="//", linewidth=0.8)),
            ("S1 ceiling: model plan, gold retrieval", lambda k: acc(f"test_{k}_planner_verify2") or acc(f"test_{k}_planner_verify1"),
             dict(color="white", edgecolor=CHARCOAL, hatch="//", linewidth=0.8))]
    x = np.arange(len(MODELS)); w = 0.16
    for i, (label, fn, style) in enumerate(spec):
        vals = [fn(k) for k, _, _ in MODELS]
        xs = x + (i - 2) * w
        ax.bar(xs, [v or 0 for v in vals], width=w, label=label, zorder=2, **({"edgecolor": "white", "linewidth": 0.5} | style))
        for xi, v, (k, _, _) in zip(xs, vals, MODELS):
            if v is None:
                continue
            txt = "$\\geq$.999" if (i == 3 and k in ("opus", "gpt")) else f"{v:.3f}"
            ax.text(xi, v + 0.004, txt, ha="center", va="bottom", fontsize=5.6, rotation=90, color=CHARCOAL, fontweight="bold")
    ax.axhline(1.0, color="#B8B2A6", lw=0.8, zorder=1)
    ax.text(-0.45, 1.004, "every stage at gold: 1.000", ha="left", va="bottom", fontsize=6.5, color="#6B6F73")
    ax.set_xticks(x)
    ax.set_xticklabels(["Qwen2.5\n32B pair", "qwen3.8\n27B", "gemma4\n31B", "Opus\n5.5", "GPT\n5.6"])
    ax.set_ylim(0.5, 1.09); ax.set_yticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_ylabel("verdict accuracy")
    boldify(ax, size=8.5)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, fontsize=7, handlelength=1.4, columnspacing=1.2)
    fig.tight_layout()
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
