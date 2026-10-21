"""Candidate designs for the family table (tab:families: verdict accuracy by claim family, our
pipeline with the verifier against the end-to-end control B, same model), 2026-10-20. Written to
docs/draft/Figures/candidates/families_<k>.png for the user to pick from. Values are recomputed
from the runs with the same readers as paper_figures.py; avocado palette; nothing here is
referenced by the draft."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import paper_figures as PF  # noqa: E402

OUT = REPO / "docs" / "draft" / "Figures" / "candidates"
OUT.mkdir(parents=True, exist_ok=True)
FAMS = [("P", "precedes"), ("C", "co-occurs"), ("F", "first/last"), ("Y", "proximity"), ("H", "threshold"), ("T", "position")]
SHORT = {"q25pair": "Qwen2.5 32B pair", "qwen38_27b": "qwen3.8 27B", "gemma4_31b": "gemma4 31B", "opus": "Opus 5.5", "gpt": "GPT-5.6"}
# five model colours drawn from the avocado palette, dark to light
MCOL = {"q25pair": PF.A_BROWN, "qwen38_27b": "#A8865E", "gemma4_31b": PF.A_LIME, "opus": PF.A_AVO, "gpt": PF.A_OLIVE}
OURS, CTRL = PF.A_OLIVE, PF.A_TAN


def family_acc(run: str, gold: dict) -> dict:
    by = defaultdict(list)
    for fam, gv, pv, _, _ in PF._records(PF.R / run, gold):
        by[fam].append(gv == pv)
    return {f: (sum(v) / len(v), len(v)) for f, v in by.items()}


def load():
    gold = {json.loads(l)["hypothesis_id"]: json.loads(l) for l in (PF.R / "test_gold_sets" / "predictions.jsonl").open()}
    ours = {k: family_acc(f"test_{k}_dprime_verify2", gold) for k, _, _ in PF.MODELS}
    ctrl = {k: family_acc(f"test_{k}_cellB", gold) for k, _, _ in PF.MODELS}
    n = {f: ours["q25pair"][f][1] for f, _ in FAMS}
    O = np.array([[ours[k][f][0] for k, _, _ in PF.MODELS] for f, _ in FAMS])
    C = np.array([[ctrl[k][f][0] for k, _, _ in PF.MODELS] for f, _ in FAMS])
    return O, C, n


def save(fig, k):
    fig.savefig(OUT / f"families_{k}.png", bbox_inches="tight", dpi=180)
    fig.savefig(OUT / f"families_{k}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / f"families_{k}.png")


# 1. dumbbells: one panel per model, families on y, B (open) -> ours (filled) ------------------
def c1(O, C, n):
    fig, axes = plt.subplots(1, 5, figsize=(10.5, 2.6), sharey=True)
    ys = np.arange(len(FAMS))[::-1]
    for ax, (j, (key, label, _)) in zip(axes, enumerate(PF.MODELS)):
        for y, i in zip(ys, range(len(FAMS))):
            o, c = O[i, j], C[i, j]
            ax.plot([c, o], [y, y], color=OURS if o >= c else PF.A_BROWN, lw=3.2, alpha=0.4, solid_capstyle="round", zorder=1)
            ax.plot([c], [y], marker="o", ms=7, color="white", markeredgecolor=PF.A_BROWN, markeredgewidth=1.5, ls="none", zorder=3)
            ax.plot([o], [y], marker="o", ms=7, color=OURS, markeredgecolor="white", markeredgewidth=0.7, ls="none", zorder=4)
            lo, hi = (c, o) if c <= o else (o, c)
            if hi - lo < 0.03:  # the two circles coincide: one label, ours, to the right
                ax.text(hi + 0.025, y, f"{o:.2f}" if abs(o - c) < 0.005 else f"{o:.2f} / {c:.2f}", ha="left", va="center",
                        fontsize=6.2, color=PF.CHARCOAL, fontweight="bold")
            else:
                ax.text(lo - 0.025, y, f"{lo:.2f}", ha="right", va="center", fontsize=6.2, color=PF.CHARCOAL)
                ax.text(hi + 0.025, y, f"{hi:.2f}", ha="left", va="center", fontsize=6.2, color=PF.CHARCOAL, fontweight="bold")
        ax.set_yticks(ys); ax.set_yticklabels([f"{f[1]} (n={n[f[0]]})" for f in FAMS])
        ax.set_xlim(0.12, 1.18); ax.set_xticks([0.3, 0.5, 0.7, 0.9]); ax.set_title(label, loc="left", fontsize=8.5)
        ax.grid(axis="x"); ax.grid(False, axis="y")
        ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
        PF.boldify(ax, size=7.5)
        ax.set_xlabel("verdict accuracy", fontsize=7.5)
    fig.text(0.5, -0.03, "open circle: end-to-end control (B)    filled circle: ours (D$'$ + verifier)    "
             "green link: ours higher, brown link: ours lower", ha="center", fontsize=7.5, color="#6B6F73")
    fig.tight_layout(w_pad=0.8, rect=(0, 0.02, 1, 1))
    save(fig, 1)


# 1b. dumbbells, single panel: families on y, the five models stacked within each family -------
def c1b(O, C, n):
    fig, ax = plt.subplots(figsize=(5.2, 5.0))
    step = 1.0; sub = 0.16
    base = np.arange(len(FAMS))[::-1] * step
    for j, (key, label, _) in enumerate(PF.MODELS):
        for i in range(len(FAMS)):
            y = base[i] + (2 - j) * sub
            o, c = O[i, j], C[i, j]
            ax.plot([c, o], [y, y], color=MCOL[key], lw=2.4, alpha=0.5, solid_capstyle="round", zorder=1)
            ax.plot([c], [y], marker="o", ms=5, color="white", markeredgecolor=MCOL[key], markeredgewidth=1.3, ls="none", zorder=3)
            ax.plot([o], [y], marker="o", ms=5, color=MCOL[key], markeredgecolor="white", markeredgewidth=0.5, ls="none", zorder=4,
                    label=label if i == 0 else None)
    for i in range(len(FAMS) - 1):
        ax.axhline(base[i] - step / 2, color="#E4E1D8", lw=0.8)
    ax.set_yticks(base); ax.set_yticklabels([f"{f[1]}\n(n={n[f[0]]})" for f in FAMS])
    ax.set_xlim(0.28, 1.02); ax.set_xlabel("verdict accuracy  (open: control B, filled: ours)")
    ax.grid(axis="x"); ax.grid(False, axis="y")
    ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
    PF.boldify(ax, size=8.5)
    ax.legend(frameon=False, fontsize=7.5, loc="lower left", ncol=1)
    fig.tight_layout()
    save(fig, "1b")


# 2. gain by family: grouped bars of ours - B, one bar per model ---------------------------------
def c2(O, C, n):
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    x = np.arange(len(FAMS)); w = 0.16
    for j, (key, label, _) in enumerate(PF.MODELS):
        d = O[:, j] - C[:, j]
        xs = x + (j - 2) * w
        ax.bar(xs, d, width=w, color=MCOL[key], edgecolor="white", linewidth=0.5, label=label, zorder=2)
        for xi, v in zip(xs, d):
            ax.text(xi, v + (0.008 if v >= 0 else -0.008), f"{v:+.2f}" if abs(v) >= 0.005 else "0.00", ha="center", va="bottom" if v >= 0 else "top",
                    fontsize=5.8, rotation=90, color=PF.CHARCOAL, fontweight="bold")
    ax.axhline(0, color=PF.CHARCOAL, lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels([f"{f[1]}\n(n={n[f[0]]})" for f in FAMS])
    ax.set_ylabel("verdict accuracy, ours $-$ control B")
    ax.set_ylim(-0.12, 0.52)
    PF.boldify(ax, size=8.5)
    ax.legend(frameon=False, loc="upper right", fontsize=7.5, ncol=2)
    fig.tight_layout()
    save(fig, 2)


# 2b. gain by family with the control level as a faint bar behind the gain --------------------
def c2b(O, C, n):
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    x = np.arange(len(FAMS)); w = 0.16
    for j, (key, label, _) in enumerate(PF.MODELS):
        xs = x + (j - 2) * w
        ax.bar(xs, C[:, j], width=w, color=MCOL[key], alpha=0.28, edgecolor="none", zorder=1)
        ax.bar(xs, O[:, j] - C[:, j], bottom=C[:, j], width=w, color=MCOL[key], edgecolor="white", linewidth=0.5, label=label, zorder=2)
        for xi, o in zip(xs, O[:, j]):
            ax.text(xi, o + 0.01, f"{o:.2f}", ha="center", va="bottom", fontsize=5.6, rotation=90, color=PF.CHARCOAL, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels([f"{f[1]}\n(n={n[f[0]]})" for f in FAMS])
    ax.set_ylabel("verdict accuracy"); ax.set_ylim(0.0, 1.18); ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    PF.boldify(ax, size=8.5)
    ax.legend(frameon=False, loc="upper left", fontsize=7, ncol=5, bbox_to_anchor=(0, 1.02))
    fig.text(0.5, -0.02, "faint bar: end-to-end control B; solid segment: the contract's gain up to ours (a downward segment where ours is lower)",
             ha="center", fontsize=7.5, color="#6B6F73")
    fig.tight_layout()
    save(fig, "2b")


# 3. radar: one chart per model, six family axes, ours vs B polygons ----------------------------
def c3(O, C, n):
    K = len(FAMS)
    ang = np.linspace(0, 2 * np.pi, K, endpoint=False)
    ang_c = np.concatenate([ang, ang[:1]])
    fig, axes = plt.subplots(1, 5, figsize=(11.0, 2.9), subplot_kw={"projection": "polar"})
    for ax, (j, (key, label, _)) in zip(axes, enumerate(PF.MODELS)):
        o = np.concatenate([O[:, j], O[:1, j]]); c = np.concatenate([C[:, j], C[:1, j]])
        ax.plot(ang_c, c, color=PF.A_BROWN, lw=1.4, ls=(0, (3, 2)), marker="o", ms=3, label="control B")
        ax.fill(ang_c, c, color=PF.A_TAN, alpha=0.25)
        ax.plot(ang_c, o, color=OURS, lw=1.8, marker="o", ms=3.5, label="ours")
        ax.fill(ang_c, o, color=PF.A_AVO, alpha=0.30)
        ax.set_theta_offset(np.pi / 2); ax.set_theta_direction(-1)
        ax.set_xticks(ang); ax.set_xticklabels([f[1] for f in FAMS], fontsize=7, fontweight="bold")
        ax.set_ylim(0.2, 1.0); ax.set_yticks([0.4, 0.6, 0.8, 1.0]); ax.set_yticklabels(["0.4", "0.6", "0.8", "1.0"], fontsize=5.5, color="#6B6F73")
        ax.set_rlabel_position(90)
        ax.grid(color="#E4E1D8", lw=0.7); ax.spines["polar"].set_color("#E4E1D8")
        ax.set_title(label, fontsize=8.5, fontweight="bold", pad=12)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.04), fontsize=8)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, 3)


# 3b. radar, two charts: ours (five model polygons) and control B (five model polygons) ----------
def c3b(O, C, n):
    K = len(FAMS)
    ang = np.linspace(0, 2 * np.pi, K, endpoint=False)
    ang_c = np.concatenate([ang, ang[:1]])
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.4), subplot_kw={"projection": "polar"})
    for ax, M, title in ((axes[0], O, "ours (D$'$ + verifier)"), (axes[1], C, "end-to-end control (B)")):
        for j, (key, label, _) in enumerate(PF.MODELS):
            v = np.concatenate([M[:, j], M[:1, j]])
            ax.plot(ang_c, v, color=MCOL[key], lw=1.6, marker="o", ms=3, label=label)
            ax.fill(ang_c, v, color=MCOL[key], alpha=0.10)
        ax.set_theta_offset(np.pi / 2); ax.set_theta_direction(-1)
        ax.set_xticks(ang); ax.set_xticklabels([f[1] for f in FAMS], fontsize=7.5, fontweight="bold")
        ax.set_ylim(0.2, 1.0); ax.set_yticks([0.4, 0.6, 0.8, 1.0]); ax.set_yticklabels(["0.4", "0.6", "0.8", "1.0"], fontsize=6, color="#6B6F73")
        ax.set_rlabel_position(90)
        ax.grid(color="#E4E1D8", lw=0.7); ax.spines["polar"].set_color("#E4E1D8")
        ax.set_title(title, fontsize=9, fontweight="bold", pad=12)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.04), fontsize=7.5)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    save(fig, "3b")


if __name__ == "__main__":
    O, C, n = load()
    print("n per family:", n)
    for i, (code, name) in enumerate(FAMS):
        print(f"{name:11s}", " ".join(f"{O[i, j]:.3f}/{C[i, j]:.3f}" for j in range(len(PF.MODELS))))
    c1(O, C, n); c1b(O, C, n); c2(O, C, n); c2b(O, C, n); c3(O, C, n); c3b(O, C, n)
