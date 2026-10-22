"""Three candidate designs for Figure 3, the matched difficulty analysis (2026-10-22, user: "the figure looks
ugly, try three more designs"). Same data as paper_figures.fig_tiers: one claim shape (A precedes B) at
Easy (P-R1, one report), Medium (P-V1, one cohort) and Hard (P-M2, two cohorts), ART and EHRSQL-C.

    PYTHONPATH=src .venv313/bin/python scripts/tier_designs.py
Writes docs/draft/Figures/candidates/tiers_design{1,2,3}.{pdf,png} and a side-by-side sheet.
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, PowerNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_figures as PF  # noqa: E402

OUT = PF.OUT / "candidates"
OUT.mkdir(exist_ok=True)
SHORT = {"q25pair": "Qwen2.5 pair", "qwen38_27b": "qwen3.8", "gemma4_31b": "gemma4", "opus": "Opus 5.5", "gpt": "GPT-5.6"}
LV = ["Easy", "Medium", "Hard"]
GREY = "#A9A39A"


def data():
    return {s: {k: [a for a, _ in PF.ladder_acc(k, s)] for k, _, _ in PF.MODELS} for s in ("cellB", "dprime_verify2")}


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight"); fig.savefig(OUT / f"{name}.png", bbox_inches="tight", dpi=220)
    plt.close(fig); print("wrote", OUT / f"{name}.png")


def design1(D):
    """Small multiples: one panel per model, ART (model colour) against EHRSQL-C (grey, dashed)."""
    fig, axes = plt.subplots(1, 5, figsize=(3.45, 1.75), sharey=True)
    x = np.arange(3)
    for ax, (k, _, c) in zip(axes, PF.MODELS):
        b, a = D["cellB"][k], D["dprime_verify2"][k]
        ax.plot(x, b, color=GREY, lw=1.3, ls=(0, (2.5, 1.5)), marker="o", ms=2.8, markeredgecolor="white", markeredgewidth=0.4)
        ax.plot(x, a, color=c, lw=1.8, marker="o", ms=3.2, markeredgecolor="white", markeredgewidth=0.4)
        ax.fill_between(x, b, a, color=c, alpha=0.12, lw=0)
        ax.set_title(SHORT[k], fontsize=6.4, pad=3)
        ax.set_xticks(x); ax.set_xticklabels(["E", "M", "H"], fontsize=6.2)
        ax.set_ylim(0.25, 1.06); ax.set_xlim(-0.35, 2.35)
        ax.tick_params(axis="y", labelsize=6, length=2); ax.tick_params(axis="x", length=0)
        ax.grid(axis="y", lw=0.4)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    axes[0].set_ylabel("verdict accuracy", fontsize=6.8)
    axes[0].set_yticks([0.4, 0.6, 0.8, 1.0])
    h = [Line2D([], [], color=PF.SLATE_M, lw=1.8, marker="o", ms=3, label="ART (model colour)"),
         Line2D([], [], color=GREY, lw=1.3, ls=(0, (2.5, 1.5)), marker="o", ms=3, label="EHRSQL-C"),
         Patch(color=PF.SLATE_M, alpha=0.15, label="what the contract recovers")]
    fig.legend(handles=h, loc="lower center", bbox_to_anchor=(0.5, -0.02), ncol=3, frameon=False, fontsize=5.8,
               handlelength=1.6, columnspacing=1.0)
    fig.subplots_adjust(wspace=0.12, bottom=0.25, top=0.88, left=0.13, right=0.99)
    save(fig, "tiers_design1")


def design2(D):
    """Cost of difficulty: accuracy lost from Easy to Hard per model, EHRSQL-C (outlined) beside ART (filled)."""
    fig, ax = plt.subplots(figsize=(3.4, 2.05))
    ys = np.arange(len(PF.MODELS))[::-1]; h = 0.36
    for y, (k, _, c) in zip(ys, PF.MODELS):
        lb = D["cellB"][k][0] - D["cellB"][k][2]; la = D["dprime_verify2"][k][0] - D["dprime_verify2"][k][2]
        ax.barh(y + h / 2, lb, height=h, color="white", edgecolor=c, hatch="////", lw=0.9, zorder=2)
        ax.barh(y - h / 2, la, height=h, color=c, edgecolor="white", lw=0.5, zorder=2)
        ax.text(lb + 0.012, y + h / 2, f"{lb:.2f}", va="center", fontsize=5.8, color=PF.CHARCOAL)
        ax.text(la + 0.012, y - h / 2, f"{la:.2f}", va="center", fontsize=5.8, color=PF.CHARCOAL, fontweight="bold")
    ax.set_yticks(ys); ax.set_yticklabels([SHORT[k] for k, _, _ in PF.MODELS])
    ax.set_xlim(0, 0.78); ax.set_xticks([0, 0.2, 0.4, 0.6])
    ax.set_xlabel("accuracy lost from Easy to Hard (same claim shape)", fontsize=7.2)
    ax.grid(axis="x"); ax.grid(False, axis="y"); ax.tick_params(axis="y", length=0)
    PF.boldify(ax, size=7)
    hd = [Patch(facecolor="white", edgecolor=PF.CHARCOAL, hatch="////", label="EHRSQL-C"),
          Patch(color=PF.CHARCOAL, label="ART")]
    ax.legend(handles=hd, frameon=False, fontsize=6.4, loc="lower right", handlelength=1.4)
    fig.tight_layout()
    save(fig, "tiers_design2")


def design3(D):
    """Annotated grid: models x levels, EHRSQL-C block beside ART block, shaded by error."""
    fig, axes = plt.subplots(1, 2, figsize=(3.4, 1.85), sharey=True)
    cmap = LinearSegmentedColormap.from_list("cream_rust", ["#FBF8F3", "#EBD3BF", "#D9A48C", PF.RUST, "#6E3519"])
    norm = PowerNorm(gamma=0.5, vmin=0, vmax=0.7)
    for ax, (s, title) in zip(axes, (("cellB", "EHRSQL-C"), ("dprime_verify2", "ART"))):
        A = np.array([D[s][k] for k, _, _ in PF.MODELS])
        ax.imshow(1 - A, cmap=cmap, norm=norm, aspect="auto")
        for i in range(A.shape[0]):
            for j in range(3):
                e = 1 - A[i, j]
                ax.text(j, i, f"{A[i, j]:.2f}", ha="center", va="center", fontsize=6.4,
                        color="white" if e > 0.35 else PF.CHARCOAL, fontweight="bold" if s == "dprime_verify2" else "normal")
        ax.set_xticks(range(3)); ax.set_xticklabels(LV, fontsize=6.4)
        ax.set_yticks(range(len(PF.MODELS))); ax.set_yticklabels([SHORT[k] for k, _, _ in PF.MODELS], fontsize=6.6)
        ax.set_title(title, fontsize=7.4, loc="left", pad=3)
        ax.tick_params(length=0); ax.grid(False)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_xticks(np.arange(-0.5, 3, 1), minor=True); ax.set_yticks(np.arange(-0.5, 5, 1), minor=True)
        ax.grid(which="minor", color="white", lw=1.2); ax.tick_params(which="minor", length=0)
    fig.tight_layout(w_pad=0.6)
    save(fig, "tiers_design3")


EHR = Path.home() / "ehragent_baseline"
EHR_RUNS = {"q25pair": "logs_testcohort_e2e_32b_min", "qwen38_27b": "logs_testcohort_e2e_qwen38", "gpt": "logs_testcohort_e2e_gpt56"}


def ehragent_ladder(key):
    """EHRAgent on the matched shape: Medium (P-V1) and Hard (P-M2) only. Its single-report run used other
    P-R1 claims (and the question form), so it has no comparable Easy point; gemma4 and Opus were not run."""
    if key not in EHR_RUNS:
        return None
    import json
    gold = json.load(open(EHR / "medtempo_data" / "gold_map_test_cohort_v1.2.json"))
    rows = [json.loads(l) for l in open(EHR / EHR_RUNS[key] / "predictions.jsonl")]
    out = [None]
    for g in ("P-V1", "P-M2"):
        sel = [r for r in rows if r["group_id"] == g]
        out.append(sum(r.get("pred_raw") == gold[r["id"]]["gold_verdict"] for r in sel) / len(sel))
    return out


def design1b(D):
    """Small multiples with EHRAgent added: ART (model colour), EHRSQL-C (grey dashed), EHRAgent (gold dotted)."""
    fig, axes = plt.subplots(1, 5, figsize=(3.45, 1.8), sharey=True)
    x = np.arange(3)
    for ax, (k, _, c) in zip(axes, PF.MODELS):
        b, a, e = D["cellB"][k], D["dprime_verify2"][k], ehragent_ladder(k)
        ax.plot(x, b, color=GREY, lw=1.2, ls=(0, (2.5, 1.5)), marker="o", ms=2.6, markeredgecolor="white", markeredgewidth=0.4, zorder=2)
        if e:
            ax.plot(x[1:], e[1:], color=PF.GOLD, lw=1.2, ls=(0, (1, 1.2)), marker="s", ms=2.6, markeredgecolor="white", markeredgewidth=0.4, zorder=3)
        ax.plot(x, a, color=c, lw=1.9, marker="o", ms=3.2, markeredgecolor="white", markeredgewidth=0.4, zorder=4)
        ax.set_title(SHORT[k], fontsize=6.4, pad=3)
        ax.set_xticks(x); ax.set_xticklabels(["E", "M", "H"], fontsize=6.2)
        ax.set_ylim(0.25, 1.06); ax.set_xlim(-0.35, 2.35)
        ax.tick_params(axis="y", labelsize=6, length=2); ax.tick_params(axis="x", length=0)
        ax.grid(axis="y", lw=0.4)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    axes[0].set_ylabel("verdict accuracy", fontsize=6.8)
    axes[0].set_yticks([0.4, 0.6, 0.8, 1.0])
    h = [Line2D([], [], color=PF.SLATE_M, lw=1.9, marker="o", ms=3, label="ART (model colour)"),
         Line2D([], [], color=GREY, lw=1.2, ls=(0, (2.5, 1.5)), marker="o", ms=3, label="EHRSQL-C"),
         Line2D([], [], color=PF.GOLD, lw=1.2, ls=(0, (1, 1.2)), marker="s", ms=3, label="EHRAgent")]
    fig.legend(handles=h, loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=3, frameon=False, fontsize=5.8,
               handlelength=1.8, columnspacing=1.0)
    fig.subplots_adjust(wspace=0.12, bottom=0.21, top=0.88, left=0.13, right=0.99)
    save(fig, "tiers_design1b")
    for k, _, _ in PF.MODELS:
        e = ehragent_ladder(k)
        print(k, "ART", [round(v, 3) for v in D["dprime_verify2"][k]], "EHRSQL-C", [round(v, 3) for v in D["cellB"][k]],
              "EHRAgent", [None if v is None else round(v, 3) for v in e] if e else None)


SYS = [("cellB", "EHRSQL-C"), ("ehragent", "EHRAgent"), ("dprime_verify2", "ART")]


def series(D, sysk, k):
    if sysk == "ehragent":
        return ehragent_ladder(k)
    return D[sysk][k]


def design4(D):
    """Drop lines: one row per system and model, a line from Easy (open tick) through Medium (hollow) to Hard
    (filled); the line's length is what difficulty costs."""
    rows = []
    for k, _, c in PF.MODELS:
        for sk, sn in SYS:
            v = series(D, sk, k)
            if v:
                rows.append((k, c, sk, sn, v))
    fig, ax = plt.subplots(figsize=(3.4, 3.3))
    y, ticks, labels, seps = 0, [], [], []
    last = None
    for k, c, sk, sn, v in rows:
        if last and k != last:
            y += 0.6; seps.append(y - 0.8)
        col = c if sk == "dprime_verify2" else (PF.GOLD if sk == "ehragent" else GREY)
        pts = [(i, a) for i, a in enumerate(v) if a is not None]
        xs = [a for _, a in pts]
        ax.plot([min(xs), max(xs)], [y, y], color=col, lw=2.2 if sk == "dprime_verify2" else 1.4, alpha=0.9, solid_capstyle="round", zorder=2)
        for i, a in pts:
            if i == 0:
                ax.plot(a, y, marker="|", ms=7, color=col, mew=1.4, zorder=3)
            elif i == 1:
                ax.plot(a, y, marker="o", ms=4.2, mfc="white", mec=col, mew=1.2, zorder=4)
            else:
                ax.plot(a, y, marker="o", ms=4.6, color=col, mec="white", mew=0.5, zorder=5)
                ax.text(a - 0.015, y, f"{a:.2f}", ha="right", va="center", fontsize=5.4, color=PF.CHARCOAL)
        ticks.append(y); labels.append(f"{SHORT[k]} · {sn}" if sn == "EHRSQL-C" or last != k else sn)
        last = k; y += 1
    ax.set_yticks(ticks); ax.set_yticklabels([("" if " · " not in l else "") + l for l in labels], fontsize=5.8)
    ax.invert_yaxis()
    ax.set_xlim(0.25, 1.04); ax.set_xticks([0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel("verdict accuracy (| Easy, ○ Medium, ● Hard)", fontsize=6.8)
    ax.grid(axis="x", lw=0.4); ax.grid(False, axis="y"); ax.tick_params(axis="y", length=0)
    for sy in seps:
        ax.axhline(sy, color="#E4E1D8", lw=0.6)
    PF.boldify(ax, size=6.2)
    fig.tight_layout()
    save(fig, "tiers_design4")


def _labels_no_overlap(ends, gap=0.05):
    """ends: list of (y, name, colour). Models ending at the same value share one label ("Opus, GPT 1.00");
    the remaining labels are spread so they do not overlap."""
    ends = sorted(ends, key=lambda t: -t[0])
    groups = []
    for y, n, c in ends:
        if groups and abs(groups[-1][0] - y) < 0.012:
            groups[-1][1].append(n); groups[-1][2] = PF.CHARCOAL
        else:
            groups.append([y, [n], c])
    out, prev = [], None
    for y, ns, c in groups:
        yy = y if prev is None or prev - y >= gap else prev - gap
        out.append((yy, f"{', '.join(ns)} {y:.2f}", c)); prev = yy
    return out


def design5(D):
    """Slopegraph in three panels (EHRSQL-C, EHRAgent, ART), one line per model, direct labels, no legend."""
    fig, axes = plt.subplots(1, 3, figsize=(3.45, 2.2), sharey=True, gridspec_kw={"wspace": 0.55})
    x = np.arange(3)
    for ax, (sk, sn) in zip(axes, SYS):
        ends = []
        for k, _, c in PF.MODELS:
            v = series(D, sk, k)
            if not v:
                continue
            xs = [i for i, a in enumerate(v) if a is not None]; ys = [a for a in v if a is not None]
            ax.plot(xs, ys, color=c, lw=1.5, clip_on=False, marker="o", ms=2.8, markeredgecolor="white", markeredgewidth=0.4,
                    ls=(0, (3, 1.5)) if k == "gpt" else "-")
            ends.append((ys[-1], {"q25pair": "pair", "qwen38_27b": "qwen3.8", "gemma4_31b": "gemma4", "opus": "Opus", "gpt": "GPT"}[k], c))
        for y, t, c in _labels_no_overlap(ends):
            ax.text(2.15, y, t, fontsize=4.7, color=c, va="center", ha="left", clip_on=False, zorder=10)
        ax.set_title(sn, fontsize=7, loc="left", pad=3)
        ax.set_facecolor("none")
        ax.set_xticks(x); ax.set_xticklabels(["E", "M", "H"], fontsize=6.2)
        ax.set_xlim(-0.2, 2.15); ax.set_ylim(0.28, 1.05)
        ax.tick_params(axis="y", labelsize=6, length=2); ax.tick_params(axis="x", length=0)
        ax.grid(axis="y", lw=0.4)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    axes[0].set_ylabel("verdict accuracy", fontsize=6.8); axes[0].set_yticks([0.4, 0.6, 0.8, 1.0])
    fig.subplots_adjust(wspace=0.95, left=0.12, right=0.84, top=0.88, bottom=0.12)
    save(fig, "tiers_design5")


def design6(D):
    """Heatmap with every system: rows models, column blocks EHRSQL-C | EHRAgent | ART x Easy, Medium, Hard;
    runs not made are hatched."""
    cmap = LinearSegmentedColormap.from_list("cream_rust", ["#FBF8F3", "#EBD3BF", "#D9A48C", PF.RUST, "#6E3519"])
    norm = PowerNorm(gamma=0.5, vmin=0, vmax=0.7)
    fig, axes = plt.subplots(1, 3, figsize=(3.45, 1.95), sharey=True)
    for ax, (sk, sn) in zip(axes, SYS):
        A = np.full((len(PF.MODELS), 3), np.nan)
        for i, (k, _, _) in enumerate(PF.MODELS):
            v = series(D, sk, k)
            if v:
                A[i] = [np.nan if a is None else a for a in v]
        ax.imshow(np.ma.masked_invalid(1 - A), cmap=cmap, norm=norm, aspect="auto")
        for i in range(A.shape[0]):
            for j in range(3):
                if np.isnan(A[i, j]):
                    ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor="#F4F2EE", edgecolor="#D8D3C8", hatch="////", lw=0))
                else:
                    e = 1 - A[i, j]
                    ax.text(j, i, f"{A[i, j]:.2f}", ha="center", va="center", fontsize=5.4,
                            color="white" if e > 0.35 else PF.CHARCOAL, fontweight="bold" if sk == "dprime_verify2" else "normal")
        ax.set_xticks(range(3)); ax.set_xticklabels(["E", "M", "H"], fontsize=6)
        ax.set_yticks(range(len(PF.MODELS))); ax.set_yticklabels([SHORT[k] for k, _, _ in PF.MODELS], fontsize=6.2)
        ax.set_title(sn, fontsize=7, loc="left", pad=3)
        ax.tick_params(length=0); ax.grid(False)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_xticks(np.arange(-0.5, 3, 1), minor=True); ax.set_yticks(np.arange(-0.5, 5, 1), minor=True)
        ax.grid(which="minor", color="white", lw=1.0); ax.tick_params(which="minor", length=0)
    fig.text(0.99, 0.01, "hatched: not run", fontsize=5.2, ha="right", color="#6B6F73")
    fig.subplots_adjust(wspace=0.06, left=0.2, right=0.99, top=0.88, bottom=0.12)
    save(fig, "tiers_design6")


def sheet2():
    import matplotlib.image as mpimg
    names = [("tiers_design1b", "1b: small multiples + EHRAgent"), ("tiers_design4", "4: drop lines"),
             ("tiers_design5", "5: slopegraph by system"), ("tiers_design6", "6: heatmap, all systems")]
    fig, axes = plt.subplots(2, 2, figsize=(9, 7))
    for ax, (n, t) in zip(axes.flat, names):
        ax.imshow(mpimg.imread(OUT / f"{n}.png")); ax.set_title(t, fontsize=10); ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "tiers_designs_sheet2.png", dpi=170); plt.close(fig); print("wrote", OUT / "tiers_designs_sheet2.png")


def wilson(p, n, z=1.96):
    if not n:
        return (np.nan, np.nan)
    d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def design7(D):
    """Where the loss happens: per model, accuracy lost at the Medium step and at the Hard step, stacked;
    EHRSQL-C (hatched) above ART (solid)."""
    fig, ax = plt.subplots(figsize=(3.4, 2.3))
    ys = np.arange(len(PF.MODELS))[::-1]; h = 0.36
    for y, (k, _, c) in zip(ys, PF.MODELS):
        for off, sk, solid in ((h / 2, "cellB", False), (-h / 2, "dprime_verify2", True)):
            e, m, hh = D[sk][k]
            s1, s2 = max(e - m, 0), max(m - hh, 0)
            kw = dict(height=h, lw=0.6, zorder=2)
            if solid:
                ax.barh(y + off, s1, color=c, alpha=0.55, edgecolor="white", **kw)
                ax.barh(y + off, s2, left=s1, color=c, edgecolor="white", **kw)
            else:
                ax.barh(y + off, s1, color="white", edgecolor=c, hatch="....", **kw)
                ax.barh(y + off, s2, left=s1, color="white", edgecolor=c, hatch="////", **kw)
            tot = s1 + s2
            ax.text(tot + 0.012, y + off, f"{tot:.2f}", va="center", fontsize=5.6, color=PF.CHARCOAL,
                    fontweight="bold" if solid else "normal")
    ax.set_yticks(ys); ax.set_yticklabels([SHORT[k] for k, _, _ in PF.MODELS])
    ax.set_xlim(0, 0.78); ax.set_xticks([0, 0.2, 0.4, 0.6])
    ax.set_xlabel("accuracy lost: Easy→Medium (light) + Medium→Hard (dark)", fontsize=6.6)
    ax.grid(axis="x"); ax.grid(False, axis="y"); ax.tick_params(axis="y", length=0)
    PF.boldify(ax, size=6.8)
    hd = [Patch(facecolor="white", edgecolor=PF.CHARCOAL, hatch="////", label="EHRSQL-C (upper bar)"),
          Patch(color=PF.CHARCOAL, label="ART (lower bar)")]
    ax.legend(handles=hd, frameon=False, fontsize=6, loc="lower right", handlelength=1.4)
    fig.tight_layout()
    save(fig, "tiers_design7")


def design8(D):
    """Trajectory plot: each model is a path Easy -> Medium -> Hard in the plane (EHRSQL-C accuracy, ART
    accuracy). Paths that run left along the top are losses the contract prevents."""
    fig, ax = plt.subplots(figsize=(3.4, 3.0))
    ax.plot([0.25, 1.02], [0.25, 1.02], color="#D8D3C8", lw=0.8, ls=(0, (3, 2)), zorder=1)
    for k, _, c in PF.MODELS:
        xs, ys = D["cellB"][k], D["dprime_verify2"][k]
        if k in ("opus", "gpt"):
            jit = 0.006 if k == "gpt" else -0.006
            xs = [x + jit for x in xs]
        for i in range(2):
            if abs(xs[i + 1] - xs[i]) + abs(ys[i + 1] - ys[i]) > 0.004:
                ax.annotate("", xy=(xs[i + 1], ys[i + 1]), xytext=(xs[i], ys[i]),
                            arrowprops=dict(arrowstyle="-|>", color=c, lw=1.4, mutation_scale=7, shrinkA=2, shrinkB=2), zorder=3)
        ax.scatter(xs, ys, s=[14, 14, 26], color=[c, c, c], edgecolor="white", lw=0.5, zorder=4)
        if k in ("q25pair", "qwen38_27b", "gemma4_31b"):
            ax.text(xs[-1], ys[-1] - 0.035, SHORT[k], fontsize=5.8, color=c, ha="center", va="top", fontweight="bold")
    ax.text(1.0, 1.035, "Opus, GPT stay here", fontsize=5.6, color=PF.CHARCOAL, ha="right", va="bottom")
    ax.set_xlim(0.25, 1.04); ax.set_ylim(0.7, 1.06)
    ax.set_xlabel("EHRSQL-C accuracy", fontsize=7.2); ax.set_ylabel("ART accuracy", fontsize=7.2)
    ax.grid(True, lw=0.4)
    PF.boldify(ax, size=6.6)
    ax.text(0.27, 0.715, "each path: Easy → Medium → Hard\n(larger dot = Hard)", fontsize=5.6, color="#6B6F73", va="bottom")
    fig.tight_layout()
    save(fig, "tiers_design8")


def design9(D):
    """Small multiples with 95% Wilson intervals: ART (model colour) and EHRSQL-C (grey), shaded bands."""
    ns = [n for _, n in PF.ladder_acc("gemma4_31b", "dprime_verify2")]
    fig, axes = plt.subplots(1, 5, figsize=(3.45, 1.85), sharey=True)
    x = np.arange(3)
    for ax, (k, _, c) in zip(axes, PF.MODELS):
        for sk, col, lw, ls in (("cellB", GREY, 1.2, (0, (2.5, 1.5))), ("dprime_verify2", c, 1.8, "-")):
            v = np.array(D[sk][k]); lo, hi = zip(*[wilson(a, n) for a, n in zip(v, ns)])
            ax.fill_between(x, lo, hi, color=col, alpha=0.16, lw=0)
            ax.plot(x, v, color=col, lw=lw, ls=ls, marker="o", ms=2.8, markeredgecolor="white", markeredgewidth=0.4)
        ax.set_title(SHORT[k], fontsize=6.4, pad=3)
        ax.set_xticks(x); ax.set_xticklabels(["E", "M", "H"], fontsize=6.2)
        ax.set_ylim(0.15, 1.04); ax.set_xlim(-0.3, 2.3)
        ax.tick_params(axis="y", labelsize=6, length=2); ax.tick_params(axis="x", length=0)
        ax.grid(axis="y", lw=0.4)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    axes[0].set_ylabel("verdict accuracy", fontsize=6.8); axes[0].set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    h = [Line2D([], [], color=PF.SLATE_M, lw=1.8, marker="o", ms=3, label="ART (model colour)"),
         Line2D([], [], color=GREY, lw=1.2, ls=(0, (2.5, 1.5)), marker="o", ms=3, label="EHRSQL-C"),
         Patch(color=GREY, alpha=0.3, label="95% interval")]
    fig.legend(handles=h, loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=3, frameon=False, fontsize=5.8, handlelength=1.6)
    fig.subplots_adjust(wspace=0.12, bottom=0.22, top=0.88, left=0.13, right=0.99)
    save(fig, "tiers_design9")


def sheet3():
    import matplotlib.image as mpimg
    names = [("tiers_design7", "7: where the loss happens"), ("tiers_design8", "8: trajectories"),
             ("tiers_design9", "9: small multiples with 95% intervals"), ("tiers_design6", "6: heatmap (for reference)")]
    fig, axes = plt.subplots(2, 2, figsize=(9, 7))
    for ax, (n, t) in zip(axes.flat, names):
        ax.imshow(mpimg.imread(OUT / f"{n}.png")); ax.set_title(t, fontsize=10); ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "tiers_designs_sheet3.png", dpi=170); plt.close(fig); print("wrote", OUT / "tiers_designs_sheet3.png")


def sheet():
    import matplotlib.image as mpimg
    names = ["tiers", "tiers_design1", "tiers_design2", "tiers_design3"]
    paths = [PF.OUT / "tiers.png"] + [OUT / f"{n}.png" for n in names[1:]]
    titles = ["current", "design 1: small multiples", "design 2: cost of difficulty", "design 3: annotated grid"]
    fig, axes = plt.subplots(2, 2, figsize=(9, 6.2))
    for ax, p, t in zip(axes.flat, paths, titles):
        ax.imshow(mpimg.imread(p)); ax.set_title(t, fontsize=10); ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "tiers_designs_sheet.png", dpi=170); plt.close(fig); print("wrote", OUT / "tiers_designs_sheet.png")


if __name__ == "__main__":
    D = data()
    design1(D); design1b(D); design2(D); design3(D); sheet()
    design4(D); design5(D); design6(D); sheet2()
    design7(D); design8(D); design9(D); sheet3()
