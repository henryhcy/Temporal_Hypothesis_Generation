"""Candidate colour sets for the whole paper (user 2026-10-21): twelve five-colour sets, ordered for
the five models (2024 pair, qwen3.8, gemma4, Opus, GPT); the first three double as the three-model
set for the register bars. Each is previewed on real data: swatches, the register bars (three open
models) and the family radar (five models). Writes two sheets of six to Figures/candidates/.

    PYTHONPATH=src .venv313/bin/python scripts/palette_sheets.py
"""
from __future__ import annotations

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

PALETTES = {
    "slate_rust":  ["#A0522D", "#D4B483", "#7A9A7E", "#4F6B75", "#2B3A42"],  # rust, wheat, sage, slate, ink
    "meadow":      ["#B5462F", "#E6B422", "#6A994E", "#386641", "#2A3D66"],  # poppy, goldenrod, grass, pine, dusk
    "earthsky":    ["#7B2D26", "#D4A017", "#5B8C5A", "#3B6EA5", "#1F2F4A"],  # clay, ochre, moss, sky, night
    "canyon":      ["#9B2226", "#EE9B00", "#94D2BD", "#0A9396", "#005F73"],  # brick, amber, mint, teal, deep teal
    "tide":        ["#C44536", "#F4A259", "#8CB369", "#2A9D8F", "#264653"],  # brick, orange, leaf, sea, slate
    "avocado":     ["#8B6B4A", "#C9B38E", "#C8C46E", "#8A9A55", "#5C6B3A"],  # brown, tan, lime, avocado, olive
    "coast":       ["#8C7B5E", "#B9A98A", "#8FB3C9", "#5B7C99", "#2F3E4E"],  # drift, dune, sea, slate, deep
    "harvest":     ["#8C3B2A", "#C98B3F", "#9C9A3C", "#5E7B4C", "#3D5A6C"],  # rust, amber, straw, olive, steel
    "terracotta":  ["#B5553A", "#D9935B", "#A3B8A0", "#3F7D8A", "#2B4F60"],  # terracotta, clay, celadon, lake, deep
    "vineyard":    ["#6E2C3E", "#B86E5E", "#C9A66B", "#6B8E6B", "#3A5A6E"],  # wine, rose, straw, vine, slate
    "ember":       ["#9E3B2E", "#D1A05A", "#A7A28F", "#5E6F73", "#33424A"],  # ember, honey, stone, pewter, charcoal
    "heath":       ["#7A4E7E", "#B4789B", "#C5B358", "#6E9A6A", "#3F5F7A"],  # plum, heather, gorse, fern, loch
}
MODELS = [("q25pair", "Qwen2.5-32B pair"), ("qwen38_27b", "qwen3.8-27B"), ("gemma4_31b", "gemma4-31B"), ("opus", "Opus 5.5"), ("gpt", "GPT-5.6")]


def register_data():
    out = {}
    for key, _ in MODELS[:3]:
        pr = PF.metric(f"test_{key}_registers_dprime_verify2", "consistency", "invariance", "per_register_accuracy")
        out[key] = [PF.acc(f"test_{key}_dprime_verify2"), pr["research"], pr["media"], pr["clinical"]]
    return out


def sheet(names, path, O, n, regs):
    fig, axes = plt.subplots(len(names), 3, figsize=(10.5, 2.3 * len(names)),
                             gridspec_kw={"width_ratios": [1.0, 1.6, 1.3]})
    for row, name in enumerate(names):
        cols = PALETTES[name]
        # swatches
        ax = axes[row, 0]; ax.axis("off")
        for j, c in enumerate(cols):
            ax.add_patch(plt.Rectangle((j * 1.05, 0.25), 1.0, 1.0, color=c))
            ax.text(j * 1.05 + 0.5, 0.1, c, ha="center", va="top", fontsize=5.5, color="#444")
        ax.set_xlim(-0.1, 5.4); ax.set_ylim(-0.3, 1.6)
        ax.set_title(name, loc="left", fontsize=11, fontweight="bold")
        # register bars
        ax = axes[row, 1]
        x = np.arange(4); w = 0.26
        for j, (key, label) in enumerate(MODELS[:3]):
            xs = x + (j - 1) * w
            ax.bar(xs, regs[key], width=w, color=cols[j], label=label, edgecolor="white", linewidth=0.5, zorder=2)
        ax.set_xticks(x); ax.set_xticklabels(["Original", "Research", "Media", "Clinical"])
        ax.set_ylim(0.6, 1.02); ax.set_yticks([0.6, 0.7, 0.8, 0.9, 1.0]); ax.grid(axis="y")
        PF.boldify(ax, size=7)
        ax.legend(frameon=False, fontsize=6, loc="lower left", ncol=3, handlelength=1.0, columnspacing=0.8)
        # radar
        ax.remove()
        ax = axes[row, 1]
        ax = fig.add_subplot(len(names), 3, row * 3 + 2)
        for j, (key, label) in enumerate(MODELS[:3]):
            xs = x + (j - 1) * w
            ax.bar(xs, regs[key], width=w, color=cols[j], label=label, edgecolor="white", linewidth=0.5, zorder=2)
        ax.set_xticks(x); ax.set_xticklabels(["Original", "Research", "Media", "Clinical"])
        ax.set_ylim(0.6, 1.02); ax.set_yticks([0.6, 0.7, 0.8, 0.9, 1.0]); ax.grid(axis="y")
        PF.boldify(ax, size=7)
        ax.legend(frameon=False, fontsize=6, loc="lower left", ncol=3, handlelength=1.0, columnspacing=0.8)
        axr = axes[row, 2]; axr.remove()
        axr = fig.add_subplot(len(names), 3, row * 3 + 3, projection="polar")
        K = len(FC.FAMS); ang = np.linspace(0, 2 * np.pi, K, endpoint=False); ang_c = np.concatenate([ang, ang[:1]])
        for j, (key, label) in enumerate(MODELS):
            v = np.concatenate([O[:, j], O[:1, j]])
            axr.plot(ang_c, v, color=cols[j], lw=1.5, marker="o", ms=2.5, label=label, zorder=5 - j)
            axr.fill(ang_c, v, color=cols[j], alpha=0.08)
        axr.set_theta_offset(np.pi / 2); axr.set_theta_direction(-1)
        axr.set_xticks(ang); axr.set_xticklabels([f[1] for f in FC.FAMS], fontsize=6, fontweight="bold")
        axr.set_ylim(0.3, 1.0); axr.set_yticks([0.4, 0.6, 0.8, 1.0]); axr.set_yticklabels(["", "", "", ""])
        axr.grid(color="#E4E1D8", lw=0.6); axr.spines["polar"].set_color("#E4E1D8")
        axr.legend(frameon=False, fontsize=5.2, loc="upper left", bbox_to_anchor=(1.02, 1.05), handlelength=1.0)
    fig.tight_layout(h_pad=1.2)
    fig.savefig(path, dpi=150, bbox_inches="tight"); plt.close(fig); print("wrote", path)


def main():
    O, _, n = FC.load()
    regs = register_data()
    names = list(PALETTES)
    sheet(names[:6], OUT / "palettes_sheet_1.png", O, n, regs)
    sheet(names[6:], OUT / "palettes_sheet_2.png", O, n, regs)


if __name__ == "__main__":
    main()
