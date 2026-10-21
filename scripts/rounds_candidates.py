"""Five candidate designs for the repair-round figure (2026-10-20), written to
docs/draft/Figures/candidates/rounds_<k>.png for the user to pick from. Same data and palette as
paper_figures.py; nothing here is referenced by the draft."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import paper_figures as PF  # noqa: E402  (palette, rcParams, acc/den_f1 readers, MODELS, boldify)

OUT = REPO / "docs" / "draft" / "Figures" / "candidates"
OUT.mkdir(parents=True, exist_ok=True)
SUF = {0: "dprime", 1: "dprime_verify1", 2: "dprime_verify2", 3: "dprime_verify3"}
ROUNDS = [0, 1, 2, 3]
SHORT = {"q25pair": "Qwen2.5 32B pair", "qwen38_27b": "qwen3.8 27B", "gemma4_31b": "gemma4 31B", "opus": "Opus 5.5", "gpt": "GPT-5.6"}
MARK = {"q25pair": "o", "qwen38_27b": "s", "gemma4_31b": "^", "opus": "D", "gpt": "v"}


def series(getter, key):
    return [getter(f"test_{key}_{SUF[r]}") for r in ROUNDS]


def save(fig, k):
    fig.savefig(OUT / f"rounds_{k}.png", bbox_inches="tight", dpi=180)
    plt.close(fig)
    print("wrote", OUT / f"rounds_{k}.png")


# 1. slope graph with value labels at every node ------------------------------------------------
def c1():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2))
    for ax, getter, title in ((axes[0], PF.acc, "verdict accuracy"), (axes[1], PF.den_f1, "evidence F1")):
        for key, label, col in PF.MODELS:
            y = series(getter, key)
            ax.plot(ROUNDS, y, color=col, lw=1.4, marker=MARK[key], ms=6, markeredgecolor="white", markeredgewidth=0.8, label=label)
            for r, v in zip(ROUNDS, y):
                dy = 0.012 if key not in ("opus", "gpt") else -0.02
                ax.text(r, v + dy, f"{v:.3f}", ha="center", va="bottom" if dy > 0 else "top", fontsize=6, color=col, fontweight="bold")
        ax.set_xticks(ROUNDS); ax.set_xticklabels(["0", "1", "2", "3"])
        ax.set_xlabel("verify-and-repair rounds"); ax.set_title(title, loc="left"); ax.set_ylim(0.70, 1.03)
        PF.boldify(ax)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.04), fontsize=7.5)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    save(fig, 1)


# 2. small multiples: one panel per model, both metrics, gain shaded ---------------------------
def c2():
    fig, axes = plt.subplots(1, 5, figsize=(7.4, 2.4), sharey=True)
    for ax, (key, label, col) in zip(axes, PF.MODELS):
        a = series(PF.acc, key); f = series(PF.den_f1, key)
        ax.fill_between(ROUNDS, a[0], a, color=col, alpha=0.18, lw=0)
        ax.plot(ROUNDS, a, color=col, lw=1.8, marker="o", ms=4, label="verdict accuracy")
        ax.plot(ROUNDS, f, color=PF.CHARCOAL, lw=1.2, ls=(0, (3, 2)), marker="s", ms=3.5, label="evidence F1")
        ax.text(3.05, a[3], f"{a[3]:.3f}", fontsize=6.5, va="center", color=col, fontweight="bold")
        ax.text(3.05, f[3], f"{f[3]:.3f}", fontsize=6.5, va="center", color=PF.CHARCOAL, fontweight="bold")
        ax.text(-0.05, a[0], f"{a[0]:.3f}", fontsize=6.5, va="center", ha="right", color=col, fontweight="bold")
        ax.set_title(label, loc="left", fontsize=8.5); ax.set_xticks(ROUNDS); ax.set_xlim(-0.6, 3.9); ax.set_ylim(0.70, 1.02)
        ax.set_xlabel("rounds", fontsize=8)
        PF.boldify(ax, size=8)
        ax.spines["left"].set_visible(ax is axes[0])
        if ax is not axes[0]:
            ax.tick_params(axis="y", length=0)
    axes[0].set_ylabel("score")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.06), fontsize=7.5)
    fig.tight_layout(w_pad=0.6, rect=(0, 0.08, 1, 1))
    save(fig, 2)


# 3. dumbbells: round 0 -> round 2 (operating point), rounds 1 and 3 as ticks --------------------
def c3():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6), sharey=True)
    ys = np.arange(len(PF.MODELS))[::-1]
    for ax, getter, title in ((axes[0], PF.acc, "verdict accuracy"), (axes[1], PF.den_f1, "evidence F1")):
        for y, (key, label, col) in zip(ys, PF.MODELS):
            v = series(getter, key)
            ax.plot([v[0], v[2]], [y, y], color=col, lw=3, alpha=0.45, solid_capstyle="round", zorder=1)
            ax.plot([v[0]], [y], marker="o", ms=8, color="white", markeredgecolor=col, markeredgewidth=1.6, zorder=3, ls="none")
            ax.plot([v[2]], [y], marker="o", ms=8, color=col, markeredgecolor="white", markeredgewidth=0.8, zorder=4, ls="none")
            ax.plot([v[1], v[3]], [y, y], marker="|", ms=10, color=col, mew=1.4, ls="none", zorder=5)
            ax.text(v[0], y + 0.32, f"{v[0]:.3f}", ha="center", fontsize=6.3, color=col)
            ax.text(v[2], y - 0.32, f"{v[2]:.3f}", ha="center", va="top", fontsize=6.3, color=col, fontweight="bold")
        ax.set_yticks(ys); ax.set_yticklabels([SHORT[m[0]] for m in PF.MODELS])
        ax.set_xlim(0.70, 1.03); ax.set_title(title, loc="left"); ax.grid(axis="x"); ax.grid(False, axis="y")
        ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
        PF.boldify(ax)
    fig.text(0.5, -0.02, "open circle: 0 rounds   filled circle: 2 rounds (the operating point)   ticks: 1 and 3 rounds", ha="center", fontsize=7.5, color="#6B6F73")
    fig.tight_layout(w_pad=1.5, rect=(0, 0.03, 1, 1))
    save(fig, 3)


# 4. delta bars: the gain of each round, positive up, negative down ---------------------------
def c4():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8))
    cols = [PF.SLATE, PF.SEA, PF.MIST]
    for ax, getter, title in ((axes[0], PF.acc, "verdict accuracy"), (axes[1], PF.den_f1, "evidence F1")):
        x = np.arange(len(PF.MODELS)); w = 0.26
        for r in (1, 2, 3):
            d = [series(getter, k)[r] - series(getter, k)[r - 1] for k, _, _ in PF.MODELS]
            xs = x + (r - 2) * w
            ax.bar(xs, d, width=w, color=cols[r - 1], edgecolor="white", linewidth=0.5, label=f"round {r}", zorder=2)
            for xi, v in zip(xs, d):
                ax.text(xi, v + (0.003 if v >= 0 else -0.003), f"{v:+.3f}", ha="center", va="bottom" if v >= 0 else "top",
                        fontsize=5.6, rotation=90, color=PF.CHARCOAL, fontweight="bold")
        ax.axhline(0, color=PF.CHARCOAL, lw=0.8)
        ax.set_xticks(x); ax.set_xticklabels([SHORT[m[0]].replace(" ", "\n", 1) for m in PF.MODELS])
        ax.set_title(f"gain per repair round, {title}", loc="left"); ax.set_ylim(-0.03, 0.16)
        PF.boldify(ax, size=8.5)
    axes[0].set_ylabel("change from the previous round")
    axes[0].legend(frameon=False, loc="upper right", fontsize=7.5)
    fig.tight_layout(w_pad=1.5)
    save(fig, 4)


# 5. heat strips: models x rounds, value-coloured, with the total gain beside -------------------
def c5():
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("coast_seq", [PF.SAND, "#F3EFE6", PF.MIST, PF.SEA, PF.SLATE])
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6), sharey=True)
    for ax, getter, title in ((axes[0], PF.acc, "verdict accuracy"), (axes[1], PF.den_f1, "evidence F1")):
        M = np.array([series(getter, k) for k, _, _ in PF.MODELS])
        ax.grid(False)
        ax.imshow(M, cmap=cmap, vmin=0.7, vmax=1.0, aspect="auto")
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                ax.text(j, i, f"{M[i, j]:.3f}", ha="center", va="center", fontsize=7.5, fontweight="bold",
                        color="white" if M[i, j] > 0.93 else PF.CHARCOAL)
            g = M[i, 3] - M[i, 0]
            ax.text(3.65, i, f"{g:+.3f}", ha="left", va="center", fontsize=7.5, fontweight="bold",
                    color=PF.A_OLIVE if g > 0 else PF.A_BROWN)
        ax.set_xticks(range(4)); ax.set_xticklabels(["0", "1", "2", "3"]); ax.set_xlim(-0.5, 4.4)
        ax.set_yticks(range(len(PF.MODELS))); ax.set_yticklabels([SHORT[m[0]] for m in PF.MODELS])
        ax.set_xlabel("verify-and-repair rounds"); ax.set_title(title, loc="left")
        ax.text(3.65, -0.75, "gain 0$\\rightarrow$3", ha="left", fontsize=7, color="#6B6F73")
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(length=0)
        PF.boldify(ax, size=8.5)
    fig.tight_layout(w_pad=1.0)
    save(fig, 5)


if __name__ == "__main__":
    c1(); c2(); c3(); c4(); c5()
