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
    design1(D); design2(D); design3(D); sheet()
