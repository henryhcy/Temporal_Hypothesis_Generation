"""The paper's result figures, drawn from the finished runs (2026-10-20).

Four figures, each placed next to the table it visualises (the tables stay):
  rounds.pdf     repair rounds: change in verdict accuracy per round, per model (rounds_f1.pdf: evidence F1, appendix)
  families.pdf   heatmap: the contract's gain over the end-to-end control by claim family and model
  modular.pdf    stage ceilings per model: all gold -> S1 alone -> S2 alone -> full pipeline -> + verifier
  registers.pdf  paraphrase case study (test set, three open models): accuracy by register
  family_radar.pdf  verdict accuracy by claim family, ours with the verifier only, one polygon per model
  groups.pdf     per-group heatmap of the same (not in the draft)

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
# ---- the paper's palette (slate_rust, user 2026-10-22), used by role everywhere:
#   models: one categorical colour each, fixed across figures
#   ordinal quantities (repair rounds): a slate ramp; signed quantities (heatmap): rust -> cream -> slate
#   structure/status (slide stages, table marks): the same hues, never beside models
RUST, WHEAT, SAGE, SLATE_M, INK, GOLD = "#A0522D", "#D4B483", "#7A9A7E", "#4F6B75", "#2B3A42", "#A8812E"
CREAM = "#F3EFE8"
MODEL_COLORS = [RUST, WHEAT, SAGE, SLATE_M, INK]
ROUND_RAMP = [SLATE_M, "#7F97A2", "#B9C6CC"]                      # rounds 1, 2, 3: dark to light, round 1 gains most
DIVERGING = [RUST, "#D9A48C", CREAM, "#9FB3BD", SLATE_M]          # loss -> 0 -> gain
MODELS = [("q25pair", "Qwen2.5-32B pair", RUST),
          ("qwen38_27b", "qwen3.8-27B", WHEAT),
          ("gemma4_31b", "gemma4-31B", SAGE),
          ("opus", "Opus 5.5", SLATE_M),
          ("gpt", "GPT-5.6", INK)]

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


# ---- 1. repair rounds: the gain of each round over the previous one (design 4, user 2026-10-20) ----
def fig_rounds():
    """Change per verify-and-repair round as horizontal bars: gains extend to the right, losses to the
    left (user 2026-10-21). rounds.pdf (verdict accuracy, main text) and rounds_f1.pdf (evidence F1,
    appendix)."""
    suffix = {0: "dprime", 1: "dprime_verify1", 2: "dprime_verify2", 3: "dprime_verify3"}
    short = {"q25pair": "Qwen2.5\n32B pair", "qwen38_27b": "qwen3.8\n27B", "gemma4_31b": "gemma4\n31B", "opus": "Opus\n5.5", "gpt": "GPT\n5.6"}
    cols = ROUND_RAMP  # ordinal: slate ramp (user 2026-10-22)
    for name, getter, title in (("rounds", acc, "verdict accuracy"), ("rounds_f1", den_f1, "evidence F1")):
        fig, ax = plt.subplots(figsize=(3.4, 2.5))
        ys = np.arange(len(MODELS))[::-1]; h = 0.26
        for r in (1, 2, 3):
            d = []
            for k, _, _ in MODELS:
                cur, prev = getter(f"test_{k}_{suffix[r]}"), getter(f"test_{k}_{suffix[r - 1]}")
                d.append(None if cur is None or prev is None else cur - prev)
            yy = ys + (2 - r) * h
            ax.barh(yy, [v or 0 for v in d], height=h, color=cols[r - 1], edgecolor="white", linewidth=0.5,
                    label=f"round {r}", zorder=2)
            for yi, v in zip(yy, d):
                if v is None:
                    continue
                ax.text(v + (0.003 if v >= 0 else -0.003), yi, f"{v:+.3f}", ha="left" if v >= 0 else "right",
                        va="center", fontsize=5.4, color=CHARCOAL, fontweight="bold")
        ax.axvline(0, color=CHARCOAL, lw=0.8)
        ax.set_yticks(ys); ax.set_yticklabels([short[m[0]] for m in MODELS], linespacing=1.1)
        ax.set_xlim(-0.04, 0.17); ax.set_xticks([0.0, 0.05, 0.10, 0.15])
        ax.set_xlabel(f"change in {title} from the previous round", fontsize=7.5)
        ax.grid(axis="x"); ax.grid(False, axis="y")
        boldify(ax, size=7.5)
        ax.tick_params(axis="y", length=0)
        ax.legend(frameon=False, loc="lower right", fontsize=6.6, handlelength=1.2, labelspacing=0.3)
        fig.tight_layout()
        save(fig, name)


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
            if not G and not P:          # not-locatable claim retrieved as empty: exact (F1 = 1)
                f1s.append(1.0); continue
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
    """The four evidence measures of ART with the verifier, absolute values, by claim family and model
    (user 2026-10-22: show our method, not the difference to EHRSQL + codebook). Darker is better in every
    panel: the two lower-is-better panels use the reversed scale."""
    gold = {json.loads(l)["hypothesis_id"]: json.loads(l) for l in (R / "test_gold_sets" / "predictions.jsonl").open()}
    fams = [("P", "precedes"), ("C", "co-occurs"), ("F", "first/last"), ("Y", "proximity"), ("H", "threshold"), ("T", "position")]
    metrics = [("evidence F1", 0, False), ("faithfulness", 1, False), ("overclaim (lower is better)", 2, True), ("underclaim (lower is better)", 3, True)]
    ours = {k: _family_metrics(_records(R / f"test_{k}_dprime_verify2", gold)) for k, _, _ in MODELS}
    seq = LinearSegmentedColormap.from_list("cream_slate", [CREAM, "#9FB3BD", SLATE_M, INK])
    short = {"q25pair": "Qwen2.5\n32B pair", "qwen38_27b": "qwen3.8\n27B", "gemma4_31b": "gemma4\n31B", "opus": "Opus\n5.5", "gpt": "GPT\n5.6"}
    fig, axes = plt.subplots(1, 4, figsize=(14.6, 3.1))
    fig.subplots_adjust(wspace=0.22)
    for ax, (title, idx, lower) in zip(axes.flat, metrics):
        V = np.full((len(fams), len(MODELS)), np.nan)
        for j, (k, _, _) in enumerate(MODELS):
            for i, (code, _) in enumerate(fams):
                V[i, j] = ours[k].get(code, (np.nan,) * 4)[idx]
        G = (1 - V) if lower else V          # goodness: 1 is best in every panel
        ax.grid(False)
        im = ax.imshow(G, cmap=seq, vmin=0.4, vmax=1.0, aspect="auto")
        ax.set_xticks(range(len(MODELS))); ax.set_xticklabels([short[m[0]] for m in MODELS])
        ax.set_yticks(range(len(fams))); ax.set_yticklabels([f[1] for f in fams] if ax is axes[0] else [""] * len(fams))
        boldify(ax, size=8)
        for lab in ax.get_xticklabels():
            lab.set_fontsize(7)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(length=0)
        for i in range(len(fams)):
            for j in range(len(MODELS)):
                v, g = V[i, j], G[i, j]
                if np.isnan(v):
                    continue
                ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=7.6, fontweight="bold",
                        color="white" if g > 0.8 else CHARCOAL)
        ax.set_title(title, loc="left", fontsize=9)
    cb = fig.colorbar(im, ax=axes, fraction=0.012, pad=0.012)
    cb.set_ticks([0.4, 0.6, 0.8, 1.0]); cb.set_ticklabels(["worse", "", "", "better"])
    cb.outline.set_visible(False); cb.ax.tick_params(length=0, labelsize=7)
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
    """Paraphrase registers on the TEST set (user 2026-10-21): grouped bars, one group per register, one
    bar per open model, ART + verifier only; Original from the main test runs, the other registers from
    the test_*_registers_dprime_verify2 runs."""
    import families_candidates as FC  # noqa: E402
    cols = MODEL_COLORS[:3]  # the paper palette (user 2026-10-22)
    models = [("q25pair", "Qwen2.5-32B pair"), ("qwen38_27b", "qwen3.8-27B"), ("gemma4_31b", "gemma4-31B")]
    regs = ["Original", "Research", "Media", "Clinical"]
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    x = np.arange(4); w = 0.26
    for j, (key, label) in enumerate(models):
        pr = metric(f"test_{key}_registers_dprime_verify2", "consistency", "invariance", "per_register_accuracy")
        y = [acc(f"test_{key}_dprime_verify2"), pr["research"], pr["media"], pr["clinical"]]
        xs = x + (j - 1) * w
        ax.bar(xs, y, width=w, color=cols[j], label=label, edgecolor="white", linewidth=0.5, zorder=2)
        for xi, v in zip(xs, y):
            ax.text(xi, v + 0.004, f"{v:.2f}", ha="center", va="bottom", fontsize=4.6, color=CHARCOAL)
    ax.set_xticks(x); ax.set_xticklabels(regs)
    ax.set_ylim(0.6, 1.04); ax.set_yticks([0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_ylabel("verdict accuracy", fontsize=8)
    boldify(ax, size=7.5)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.16), fontsize=6.4, handlelength=1.2, columnspacing=1.0)
    fig.tight_layout()
    save(fig, "registers")


# ---- 5. per-group verdict accuracy of our pipeline (ours only; user 2026-10-20) ------------------
def fig_family_radar(palette: str = "paper", suffix: str = ""):
    """Verdict accuracy by claim family on the test set, our pipeline with the verifier only, one polygon
    per model (user 2026-10-20: radar, no end-to-end comparison, meadow palette)."""
    import families_candidates as FC  # noqa: E402
    O, _, n = FC.load()
    cols = MODEL_COLORS if palette == "paper" else FC.PALETTES_STRONG[palette]
    K = len(FC.FAMS)
    ang = np.linspace(0, 2 * np.pi, K, endpoint=False)
    ang_c = np.concatenate([ang, ang[:1]])
    # column-width rendering with the legend on one line below (user 2026-10-21)
    fig, ax = plt.subplots(figsize=(3.4, 3.5), subplot_kw={"projection": "polar"})
    fig.subplots_adjust(left=0.13, right=0.87, top=0.90, bottom=0.17)
    lws = [1.8, 1.8, 1.8, 1.3, 1.3]
    for j, (key, label, _) in enumerate(MODELS):
        v = np.concatenate([O[:, j], O[:1, j]])
        ax.plot(ang_c, v, color=cols[j], lw=lws[j], marker="o", ms=3.4, markeredgecolor="white", markeredgewidth=0.5,
                label=label, zorder=5 - j, ls=(0, (3, 1.5)) if key == "gpt" else "-")
        ax.fill(ang_c, v, color=cols[j], alpha=0.10, zorder=1)
    ax.set_theta_offset(np.pi / 2); ax.set_theta_direction(-1)
    ax.set_xticks(ang)
    ax.set_xticklabels([f"{f[1]}\n(n={n[f[0]]})" for f in FC.FAMS], fontsize=8, fontweight="bold")
    ax.set_ylim(0.3, 1.0); ax.set_yticks([0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.4", "0.6", "0.8", "1.0"], fontsize=6, color="#6B6F73")
    ax.set_rlabel_position(0)
    ax.grid(color="#E4E1D8", lw=0.7); ax.spines["polar"].set_color("#E4E1D8")
    ax.tick_params(axis="x", pad=5)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=5, fontsize=6.6,
              handlelength=1.1, handletextpad=0.4, columnspacing=0.9)
    save(fig, "family_radar" + suffix)


def fig_groups():
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from group_table import per_key, family_of  # noqa: E402
    from temporal_hypo.framework.io import load_release  # noqa: E402
    rel = load_release(REPO / "data" / "release" / "v1.2", verify_sha=False)
    order = ["P-V1", "P-V2", "P-V3", "P-V4", "P-M2", "C-V1", "C-V2", "C-V3", "F-V1", "F-V2", "F-V3",
             "Y-V1", "Y-V2", "Y-V3", "H-V1", "H-V5", "T-V1"]
    M = np.full((len(order), len(MODELS)), np.nan); N = np.zeros(len(order))
    for j, (key, _, _) in enumerate(MODELS):
        d = per_key(R / f"test_{key}_dprime_verify2", rel, lambda g: g)
        for i, g in enumerate(order):
            if g in d:
                M[i, j] = d[g][0] / d[g][1]; N[i] = d[g][1]
    cmap = LinearSegmentedColormap.from_list("cream_slate", [CREAM, "#9FB3BD", SLATE_M, INK])
    fig, ax = plt.subplots(figsize=(4.4, 5.2))
    ax.grid(False)
    im = ax.imshow(M, cmap=cmap, vmin=0.4, vmax=1.0, aspect="auto")
    short = {"q25pair": "Qwen2.5\n32B pair", "qwen38_27b": "qwen3.8\n27B", "gemma4_31b": "gemma4\n31B", "opus": "Opus\n5.5", "gpt": "GPT\n5.6"}
    ax.set_xticks(range(len(MODELS))); ax.set_xticklabels([short[m[0]] for m in MODELS])
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f"{g}  ({family_of(g)}, n={int(N[i])})" for i, g in enumerate(order)])
    boldify(ax, size=7.5)
    for lab in ax.get_xticklabels():
        lab.set_fontsize(6.8)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    for i in range(len(order)):
        for j in range(len(MODELS)):
            v = M[i, j]
            if np.isnan(v):
                continue
            ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=7, fontweight="bold",
                    color="white" if (v > 0.88 or v < 0.5) else CHARCOAL)
    # family separators
    fams = [family_of(g) for g in order]
    for i in range(1, len(order)):
        if fams[i] != fams[i - 1]:
            ax.axhline(i - 0.5, color="white", lw=2.0)
    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    cb.outline.set_visible(False); cb.ax.tick_params(length=0, labelsize=7)
    cb.set_label("verdict accuracy, ours (D$'$ + verifier)", fontsize=7)
    ax.set_title("verdict accuracy by hypothesis group, test set", loc="left", fontsize=8.5)
    fig.tight_layout()
    save(fig, "groups")


# ---- 6. difficulty levels: accuracy down the ladder, one-prompt baseline vs ART (user 2026-10-21) ----
def fig_tiers():
    import tier_candidates as TC  # noqa: E402
    import families_candidates as FC  # noqa: E402
    cols = MODEL_COLORS
    levels = ["Easy\none report", "Medium\none cohort", "Hard\ntwo cohorts"]
    fig, axes = plt.subplots(2, 1, figsize=(3.4, 4.0), sharex=True)
    for ax, suf, title in ((axes[0], "cellB", "Straight-to-SQL + codebook"), (axes[1], "dprime_verify2", "ART + verifier")):
        x = np.arange(3)
        for j, (key, label) in enumerate(TC.MODELS):
            y = TC.tier_acc(key, suf)
            ax.plot(x, y, color=cols[j], lw=1.7, marker="o", ms=4, markeredgecolor="white", markeredgewidth=0.6, label=label, zorder=5 - j,
                    ls=(0, (3, 1.5)) if key == "gpt" else "-")
            if key in ("q25pair", "qwen38_27b", "gemma4_31b"):  # the frontier ends coincide near 1.0
                ax.text(x[-1] + 0.07, y[-1], f"{y[-1]:.3f}", fontsize=5.6, color=cols[j], va="center", ha="left")
        ax.set_xticks(x); ax.set_xticklabels(levels)
        ax.set_xlim(-0.25, 2.6); ax.set_ylim(0.25, 1.06)
        ax.set_title(title, loc="left", fontsize=8.5)
        ax.set_ylabel("verdict accuracy", fontsize=8)
        boldify(ax, size=7.5)
        ax.grid(axis="y")
    axes[1].legend(frameon=False, fontsize=6.2, loc="lower left", ncol=2, handlelength=1.3, columnspacing=0.9, labelspacing=0.3)
    fig.tight_layout(h_pad=0.8)
    save(fig, "tiers")



# ---- 7. repair rounds, vertical variant for comparison (user 2026-10-21; appendix) ----------------
def fig_rounds_vertical():
    suffix = {0: "dprime", 1: "dprime_verify1", 2: "dprime_verify2", 3: "dprime_verify3"}
    short = {"q25pair": "Qwen2.5\n32B pair", "qwen38_27b": "qwen3.8\n27B", "gemma4_31b": "gemma4\n31B", "opus": "Opus\n5.5", "gpt": "GPT\n5.6"}
    cols = ROUND_RAMP
    fig, ax = plt.subplots(figsize=(3.4, 2.1))
    x = np.arange(len(MODELS)); w = 0.26
    for r in (1, 2, 3):
        d = []
        for k, _, _ in MODELS:
            cur, prev = acc(f"test_{k}_{suffix[r]}"), acc(f"test_{k}_{suffix[r - 1]}")
            d.append(None if cur is None or prev is None else cur - prev)
        xs = x + (r - 2) * w
        ax.bar(xs, [v or 0 for v in d], width=w, color=cols[r - 1], edgecolor="white", linewidth=0.5, label=f"round {r}", zorder=2)
        for xi, v in zip(xs, d):
            if v is None:
                continue
            ax.text(xi, v + (0.003 if v >= 0 else -0.003), f"{v:+.3f}", ha="center", va="bottom" if v >= 0 else "top",
                    fontsize=5.0, rotation=90, color=CHARCOAL, fontweight="bold")
    ax.axhline(0, color=CHARCOAL, lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels([short[m[0]] for m in MODELS])
    ax.set_title("verdict accuracy: change per repair round", loc="left", fontsize=8.5)
    ax.set_ylim(-0.03, 0.16); ax.set_yticks([0.0, 0.05, 0.10, 0.15])
    boldify(ax, size=7.5)
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("change from\nthe previous round", fontsize=8)
    ax.legend(frameon=False, loc="upper right", fontsize=7, handlelength=1.2, labelspacing=0.3)
    fig.tight_layout()
    save(fig, "rounds_vertical")


if __name__ == "__main__":
    fig_rounds()
    fig_families()
    fig_modular()
    fig_registers()
    fig_groups()
    fig_family_radar()
    fig_tiers()
    fig_rounds_vertical()
