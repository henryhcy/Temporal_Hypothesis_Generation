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


# ---- 2. heatmaps: the four evidence metrics by claim family, as the contract's change over B ----
def _records(run: Path, gold: dict):
    """Per cohort-tier record: family code, gold verdict, predicted verdict, denominator F1 (mean over
    arms), denominator exact (every arm)."""
    out = []
    for line in (run / "predictions.jsonl").open():
        x = json.loads(line)
        g = gold.get(x["hypothesis_id"])
        if not g or not g.get("retrieval", {}).get("arms"):
            continue
        gv = g["prediction"]["verdict"]; pv = (x.get("prediction") or {}).get("verdict")
        rt = x.get("retrieval") or {}
        parms = rt.get("arms") or []
        f1s, exact = [], bool(parms) and rt.get("ok") is not False
        for ga, pa in zip(g["retrieval"]["arms"], parms):
            G = set(ga["denominator_ids"]); P = set(pa.get("denominator_ids") or [])
            tp = len(G & P); prec = tp / len(P) if P else 0.0; rec = tp / len(G) if G else 0.0
            f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
            exact = exact and (G == P)
        if not parms or rt.get("ok") is False:
            f1s, exact = [0.0], False
        out.append((x["group_id"].split("-")[0], gv, pv, sum(f1s) / len(f1s), exact))
    return out


def _family_metrics(recs):
    """{family: (den_f1, faithfulness, false_decisiveness, over_abstention)}"""
    from collections import defaultdict
    by = defaultdict(list)
    for r in recs:
        by[r[0]].append(r)
    out = {}
    for fam, rs in by.items():
        den = sum(r[3] for r in rs) / len(rs)
        right = [r for r in rs if r[1] == r[2]]
        faith = (sum(1 for r in right if r[4]) / len(right)) if right else float("nan")
        insuf = [r for r in rs if r[1] == "insufficient"]
        fdec = (sum(1 for r in insuf if r[2] in ("supported", "refuted")) / len(insuf)) if insuf else float("nan")
        dec = [r for r in rs if r[1] != "insufficient"]
        oabs = (sum(1 for r in dec if r[2] == "insufficient") / len(dec)) if dec else float("nan")
        out[fam] = (den, faith, fdec, oabs)
    return out


def fig_families():
    gold = {json.loads(l)["hypothesis_id"]: json.loads(l) for l in (R / "test_gold_sets" / "predictions.jsonl").open()}
    fams = [("P", "precedes"), ("C", "co-occurs"), ("F", "first/last"), ("Y", "proximity"), ("H", "threshold"), ("T", "position")]
    metrics = [("denominator F1", 0, +1), ("faithfulness", 1, +1),
               ("false-decisiveness (lower is better)", 2, -1), ("over-abstention (lower is better)", 3, -1)]
    ours = {k: _family_metrics(_records(R / f"test_{k}_dprime_verify2", gold)) for k, _, _ in MODELS}
    ctrl = {k: _family_metrics(_records(R / f"test_{k}_cellB", gold)) for k, _, _ in MODELS}
    cmap = LinearSegmentedColormap.from_list("avocado", [A_BROWN, A_TAN, A_CREAM, A_LIME, A_AVO, A_OLIVE])
    norm = TwoSlopeNorm(vmin=-0.25, vcenter=0.0, vmax=0.8)
    short = {"q25pair": "Qwen2.5\n32B pair", "qwen38_27b": "qwen3.8\n27B", "gemma4_31b": "gemma4\n31B", "opus": "Opus\n5.5", "gpt": "GPT\n5.6"}
    fig, axes = plt.subplots(2, 2, figsize=(7.4, 5.8))
    fig.subplots_adjust(hspace=0.32, wspace=0.28)
    for ax, (title, idx, sign) in zip(axes.flat, metrics):
        D = np.full((len(fams), len(MODELS)), np.nan); O = D.copy(); C = D.copy()
        for j, (k, _, _) in enumerate(MODELS):
            for i, (code, _) in enumerate(fams):
                o = ours[k].get(code, (np.nan,) * 4)[idx]; c = ctrl[k].get(code, (np.nan,) * 4)[idx]
                O[i, j], C[i, j] = o, c
                D[i, j] = sign * (o - c)
        ax.grid(False)
        im = ax.imshow(D, cmap=cmap, norm=norm, aspect="auto")
        ax.set_xticks(range(len(MODELS)))
        ax.set_xticklabels([short[m[0]] for m in MODELS] if ax in axes[1] else [""] * len(MODELS))
        ax.set_yticks(range(len(fams))); ax.set_yticklabels([f[1] for f in fams] if ax in axes[:, 0] else [""] * len(fams))
        boldify(ax, size=8)
        for lab in ax.get_xticklabels():
            lab.set_fontsize(7)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(length=0)
        for i in range(len(fams)):
            for j in range(len(MODELS)):
                d = D[i, j]
                if np.isnan(d):
                    continue
                dark = d > 0.45 or d < -0.15
                dtxt = f"{d:+.3f}" if abs(d) >= 0.0005 else "0.000"
                ax.text(j, i - 0.14, dtxt, ha="center", va="center", fontsize=7.2, fontweight="bold",
                        color="white" if dark else CHARCOAL)
                ax.text(j, i + 0.22, f"{O[i, j]:.2f} vs {C[i, j]:.2f}", ha="center", va="center", fontsize=5.6,
                        color="white" if dark else "#6B6F73")
        ax.set_title(title, loc="left", fontsize=9)
    cb = fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02)
    cb.outline.set_visible(False); cb.ax.tick_params(length=0, labelsize=7)
    cb.set_label("improvement of the contract over the end-to-end control\n(ours $-$ B; sign flipped for the two lower-is-better metrics)", fontsize=7)
    fig.savefig(OUT / "families.pdf", bbox_inches="tight"); fig.savefig(OUT / "families.png", bbox_inches="tight", dpi=200)
    plt.close(fig); print("wrote", OUT / "families.pdf")


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
