"""Concept figures for the draft (2026-10-21, user): three nested figures, each contained in the next,
in three styles.

  level 1  contract      the plan -> harness lookup -> S2 prompt hand-off (and the prose ablation)
  level 2  framework     the ART pipeline: input, codebook, S1/S2 (model), contract, sandbox, verifiers,
                         S3 (harness), stage gold and metrics; the contract box is level 1 compressed
  level 3  whole         the benchmark generation (corpus -> templates -> cores -> gold -> screens ->
                         release) feeding the framework of level 2, drawn unchanged beneath it

Styles, after the conventions of this year's conference figures:
  distill    rounded blocks, blues with one warm-orange accent on the key idea, thin strokes, dashed
             stage groups, small glyph icons (the NeurIPS / ICML mainstream)
  blueprint  monochrome schematic: white boxes, hairline black strokes, square corners, monospace
             artifacts, numbered steps, one accent colour for ours (systems-paper style)
  lanes      swimlanes for Model / Harness / Gold with light tints in the paper's meadow palette,
             column headers per stage, coloured box edges by lane (ACL / Web Conference data papers)

Outputs docs/draft/Figures/concepts/<style>_<level>.pdf/png.

    PYTHONPATH=src .venv313/bin/python scripts/concept_figures.py
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

OUT = Path(__file__).resolve().parents[1] / "docs" / "draft" / "Figures" / "concepts"
OUT.mkdir(parents=True, exist_ok=True)
SANS, MONO = "DejaVu Sans", "DejaVu Sans Mono"


@dataclass
class Style:
    key: str
    fill: dict
    edge: dict                  # role -> edge colour (missing -> default)
    edge_default: str
    edge_lw: float
    rounding: float
    text: str
    muted: str
    arrow: str
    arrow_lw: float
    arrow_style: str
    accent: str
    mono_fill: str
    lanes: bool = False
    lane_fill: dict = field(default_factory=dict)
    numbered: bool = False
    icons: bool = False
    groups: bool = False
    title_weight: str = "bold"


DISTILL = Style(
    key="distill",
    fill={"input": "#F1F3F6", "codebook": "#ECE6F6", "model": "#DCE9F7", "harness": "#EDF0F3", "verify": "#F6F7F9",
          "contract": "#FBE2C9", "gold": "#FFF3D0", "output": "#DDF0E4", "generation": "#EAF0F7", "release": "#DCE9F7",
          "muted": "#F7F7F7"},
    edge={"contract": "#D9792F"}, edge_default="#8A94A6", edge_lw=0.7, rounding=1.1,
    text="#1F2933", muted="#6B7280", arrow="#4A5568", arrow_lw=0.9, arrow_style="-|>", accent="#D9792F",
    mono_fill="#FFFFFF", icons=True, groups=True)
BLUEPRINT = Style(
    key="blueprint",
    fill={r: "#FFFFFF" for r in ("input", "codebook", "model", "harness", "verify", "gold", "output", "generation", "release", "muted", "contract")},
    edge={"contract": "#386641", "gold": "#777777"}, edge_default="#222222", edge_lw=0.7, rounding=0.0,
    text="#111111", muted="#666666", arrow="#222222", arrow_lw=0.6, arrow_style="->", accent="#386641",
    mono_fill="#F2F2F2", numbered=True)
LANES = Style(
    key="lanes",
    fill={"input": "#FFFFFF", "codebook": "#FFFFFF", "model": "#FFFFFF", "harness": "#FFFFFF", "verify": "#FFFFFF",
          "contract": "#F9E4DE", "gold": "#FFFFFF", "output": "#FFFFFF", "generation": "#FFFFFF", "release": "#FFFFFF",
          "muted": "#F4F4F4"},
    edge={"model": "#6A994E", "input": "#6A994E", "output": "#6A994E", "harness": "#B8921C", "verify": "#B8921C",
          "codebook": "#B8921C", "contract": "#B5462F", "gold": "#2A3D66", "generation": "#6B5B95", "release": "#6B5B95"},
    edge_default="#555555", edge_lw=0.9, rounding=0.6,
    text="#1F2933", muted="#6B7280", arrow="#333333", arrow_lw=0.9, arrow_style="-|>", accent="#B5462F",
    mono_fill="#FAFAF7", lanes=True,
    lane_fill={"model": "#EEF3E6", "harness": "#FBF4DF", "gold": "#E8EBF2", "generation": "#EFEBF5"})
STYLES = [DISTILL, BLUEPRINT, LANES]
ICON = {"input": "▤", "codebook": "☰", "model": "✎", "harness": "⚙", "verify": "⟳",
        "contract": "⚑", "gold": "★", "output": "✓", "generation": "◆", "release": "▤", "muted": ""}
CIRCLED = "①②③④⑤⑥⑦⑧⑨"


class Canvas:
    def __init__(self, st: Style, W: float, H: float, width_in: float, title_fs: float, body_fs: float, xmin: float = -1.0):
        self.st, self.W, self.H = st, W, H
        self.unit = width_in / (W - xmin + 1.0)       # inches per unit
        self.fig, self.ax = plt.subplots(figsize=(width_in, width_in * (H + 2) / (W - xmin + 1.0)))
        self.ax.set_xlim(xmin, W + 1); self.ax.set_ylim(-1, H + 1); self.ax.set_aspect("equal"); self.ax.axis("off")
        self.fig.subplots_adjust(0, 0, 1, 1)
        self.tfs, self.bfs = title_fs, body_fs
        self.upp = 1.0 / (72.0 * self.unit)          # units per point

    def lh(self, fs: float, spacing: float = 1.22) -> float:
        return fs * spacing * self.upp

    # ------------------------------------------------------------------ primitives
    def lane(self, y0: float, y1: float, role: str, label: str, x0: float = -0.5, x1: float | None = None):
        st = self.st
        x1 = self.W + 0.5 if x1 is None else x1
        self.ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=st.lane_fill[role], edgecolor="none", zorder=0))
        self.ax.text(x0 - 0.8, (y0 + y1) / 2, label, rotation=90, ha="center", va="center", fontsize=self.bfs + 0.5,
                     fontweight="bold", color=st.edge.get(role, st.text), zorder=1)

    def group(self, x: float, y: float, w: float, h: float, label: str):
        st = self.st
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={max(st.rounding, 0.6)}",
                                         facecolor="none", edgecolor="#B8C0CC", linewidth=0.6, linestyle=(0, (3, 2)), zorder=0.5))
        self.ax.text(x + 1.0, y + h - 0.4, label, ha="left", va="top", fontsize=self.bfs, color="#7A8494", fontweight="bold", zorder=1)

    def header(self, x: float, y: float, label: str, color: str | None = None):
        self.ax.text(x, y, label, ha="center", va="bottom", fontsize=self.tfs, fontweight="bold", color=color or self.st.text)

    def box(self, x: float, y: float, w: float, h: float, role: str, title: str | None = None, body: str | None = None,
            mono: str | None = None, number: int | None = None, emph: bool = False, title_color: str | None = None,
            tag: str | None = None):
        st = self.st
        edge = st.accent if emph else st.edge.get(role, st.edge_default)
        lw = st.edge_lw * (1.6 if emph else 1.0)
        bs = f"round,pad=0,rounding_size={st.rounding}" if st.rounding > 0 else "square,pad=0"
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=bs, facecolor=st.fill[role], edgecolor=edge, linewidth=lw, zorder=2))
        cy = y + h - 0.9
        if title:
            prefix = ""
            if st.icons and ICON.get(role):
                prefix = ICON[role] + "  "
            if st.numbered and number is not None:
                prefix = CIRCLED[number - 1] + " "
            if st.numbered and tag:
                prefix = tag + " "
            self.ax.text(x + 0.9, cy, prefix + title, ha="left", va="top", fontsize=self.tfs, fontweight=st.title_weight,
                         color=title_color or (st.accent if emph else st.text), zorder=3, family=SANS)
            cy -= self.lh(self.tfs) + 0.3
        if body:
            self.ax.text(x + 0.9, cy, body, ha="left", va="top", fontsize=self.bfs, color=st.text, zorder=3, family=SANS, linespacing=1.22)
            cy -= self.lh(self.bfs) * (body.count("\n") + 1) + 0.6
        if mono:
            n = mono.count("\n") + 1
            mh = self.lh(self.bfs - 0.3, 1.3) * n + 1.2
            my = max(y + 0.7, cy - mh)
            self.ax.add_patch(Rectangle((x + 0.9, my), w - 1.8, mh, facecolor=st.mono_fill, edgecolor=st.edge_default,
                                        linewidth=0.4, zorder=2.5))
            self.ax.text(x + 1.4, my + mh - 0.5, mono, ha="left", va="top", fontsize=self.bfs - 0.3, color=st.text, zorder=3,
                         family=MONO, linespacing=1.3)

    def arrow(self, p, q, label: str | None = None, rad: float = 0.0, accent: bool = False, muted: bool = False,
              lpos: float = 0.5, loff=(0.0, 0.0), lw: float | None = None):
        st = self.st
        color = st.accent if accent else (st.muted if muted else st.arrow)
        a = FancyArrowPatch(p, q, arrowstyle=st.arrow_style, mutation_scale=7, color=color, linewidth=lw or st.arrow_lw,
                            connectionstyle=f"arc3,rad={rad}", zorder=4, shrinkA=0, shrinkB=0)
        self.ax.add_patch(a)
        if label:
            mx, my = p[0] + (q[0] - p[0]) * lpos + loff[0], p[1] + (q[1] - p[1]) * lpos + loff[1]
            self.ax.text(mx, my, label, ha="center", va="center", fontsize=self.bfs - 0.4, color=color, zorder=5,
                         style="italic", bbox=dict(boxstyle="square,pad=0.12", facecolor="white", edgecolor="none"))

    def dotted(self, p, q, label: str | None = None, loff=(0.0, 0.0)):
        st = self.st
        col = st.edge.get("gold", "#B38A1F") if st.key != "distill" else "#C9A227"
        self.ax.plot([p[0], q[0]], [p[1], q[1]], color=col, linewidth=0.8, linestyle=(0, (1.2, 1.4)), zorder=1.5)
        if label:
            self.ax.text((p[0] + q[0]) / 2 + loff[0], (p[1] + q[1]) / 2 + loff[1], label, ha="center", va="center",
                         fontsize=self.bfs - 0.6, color=col, zorder=5, bbox=dict(boxstyle="square,pad=0.1", facecolor="white", edgecolor="none"))

    def note(self, x: float, y: float, s: str, ha: str = "left", fs: float | None = None, color: str | None = None, weight: str = "normal"):
        self.ax.text(x, y, s, ha=ha, va="center", fontsize=fs or self.bfs, color=color or self.st.muted, zorder=5, fontweight=weight)

    def save(self, name: str):
        self.fig.savefig(OUT / f"{name}.pdf"); self.fig.savefig(OUT / f"{name}.png", dpi=220)
        plt.close(self.fig); print("wrote", OUT / f"{name}.png")


# ====================================================================== level 1: the contract
def draw_contract(c: Canvas, oy: float = 0.0):
    st = c.st
    y = lambda v: v + oy
    c.box(1, y(22), 30, 33, "model", "Plan (output of S1)", "a fixed vocabulary; the\ndenominator names a primitive:",
          mono="events Headache, Fatigue\nquantity order_of_pair\ndenominator ordered_pair\nnull symmetric p0=0.5\ntail greater\ntest binomial", number=1)
    c.box(37, y(13), 30, 42, "contract", "Harness lookup", None, number=2, emph=True)
    # the lookup table, the matching row highlighted
    rows = [("ordered_pair", "both present at distinct\nstages; same stage excluded;\nnumerator: A earlier", True),
            ("both_present", "both present at any stage;\nco-existence is the event", False),
            ("all_present_unique_first", "every candidate present;\na tie for first is excluded", False)]
    ry = y(13 + 42 - 0.9 - c.lh(c.tfs) - 0.6)
    for key, rule, hit in rows:
        rh = c.lh(c.bfs - 0.3, 1.3) * (rule.count("\n") + 2) + 1.0
        if hit:
            c.ax.add_patch(Rectangle((37.9, ry - rh), 28.2, rh, facecolor=("#FBE2C9" if st.key == "distill" else "#E6EFE0" if st.key == "blueprint" else "#FFFFFF"),
                                     edgecolor=st.accent, linewidth=0.8, zorder=2.4))
        c.ax.text(38.4, ry - 0.3, key, ha="left", va="top", fontsize=c.bfs - 0.3, family=MONO, color=st.accent if hit else st.text, zorder=3, fontweight="bold" if hit else "normal")
        c.ax.text(38.4, ry - 0.3 - c.lh(c.bfs - 0.3, 1.3), rule, ha="left", va="top", fontsize=c.bfs - 0.3, family=SANS, color=st.text, zorder=3, linespacing=1.25)
        ry -= rh + 0.8
    c.ax.text(38.4, ry - 0.2, "one definition per primitive:\nthe codebook's content in code", ha="left", va="top", fontsize=c.bfs - 0.5, color=st.muted, zorder=3, style="italic", linespacing=1.2)
    c.box(73, y(22), 26, 33, "model", "Prompt to S2", "schema (column listing)\ncontract: count a report\niff Headache and Fatigue\nare at distinct stages;\nsame stage excluded;\nnumerator: Headache\nearlier. One row per\nreport.", number=3)
    c.box(73, y(2), 26, 13, "verify", "Verifier (S2)", "checks the returned rows\nagainst the same rule", number=4)
    c.box(1, y(2), 30, 13, "muted", "Ablation: the plan as prose", "S2 gets the plan JSON and the\nwhole codebook; it must find and\ninterpret the stipulation itself")
    c.arrow((31, y(40)), (37, y(40)), "named\nprimitive", lpos=0.5, loff=(0, 3.2))
    c.arrow((67, y(40)), (73, y(40)), "exact\nrule", accent=True, loff=(0, 3.2))
    c.arrow((31, y(8.5)), (73, y(8.5)), "plan JSON + whole codebook", muted=True, lpos=0.5, loff=(0, 1.8))
    c.dotted((67, y(16)), (73, y(11)), "same rule", loff=(2.0, 2.0))


# ====================================================================== level 2: the framework
def draw_framework(c: Canvas, oy: float = 0.0, with_lanes: bool = True):
    st = c.st
    y = lambda v: v + oy
    if st.lanes and with_lanes:
        c.lane(y(0.5), y(15.5), "gold", "gold (released)")
        c.lane(y(16), y(30.5), "harness", "harness")
        c.lane(y(31), y(47.5), "model", "model (LLM)")
    if st.groups:
        for x0, x1, lab in ((17, 39.5, "S1  articulate"), (40.5, 70.5, "S2  retrieve"), (71.5, 99, "S3  test")):
            c.group(x0, y(0.5), x1 - x0, 47.3, lab)
    if st.lanes:
        for xc, lab, col in ((28.5, "S1  Articulate", "#6A994E"), (55.5, "S2  Retrieve", "#6A994E"), (85, "S3  Test", "#B8921C")):
            c.header(xc, y(47.9), lab, col)
    if st.numbered:
        c.note(1, y(47.5), "ART: ① articulate  ② the contract  ③ retrieve  ④ sandbox  ⑤ test;  dotted: compared with the released gold", fs=c.bfs, color=st.text, weight="bold")
    # model lane
    c.box(1, y(32), 15, 13.5, "input", "Input record", "claim: “After Pfizer,\nHeadache tends to\nprecede Fatigue.”\ncohort: Pfizer\nannotation DB: report,\nvaccine, term, first-\nmention stage (ids\npseudonymised)")
    c.box(18, y(32), 20.5, 13.5, "model", "S1 Articulate (LLM)", "told the codebook, not the\nmapping; composes a plan:", mono="events  Headache, Fatigue\ndenominator  ordered_pair\nnull symmetric p0=0.5\ntail greater  test binomial", number=1)
    c.box(41, y(32), 28.5, 13.5, "model", "S2 Retrieve (LLM writes SQL)", "told the schema and the contract;\none SQL per arm, one row per report:", mono="report_id | in_den | in_num | excl\n 0482913  |   1    |   1    |  0", number=3)
    c.box(72, y(32), 27, 13.5, "output", "Output", "verdict: supported / refuted /\ninsufficient (not-locatable,\nsparse, underpowered)\nevidence: report-id sets, n, k,\np on both tails, effect size")
    # harness lane
    c.box(1, y(17), 15, 12.5, "codebook", "Codebook", "the corpus stipulations\nas situation-phrased\ntext; null sources; test\ndefinitions; dataset\ncard. The claim-type\nmapping is withheld.")
    c.box(18, y(17), 10, 12.5, "verify", "Verify (S1)", "plan vs the\ncodebook:\nquantity, null\nkind, stated\nbar, test\nfamily; re-ask\nonce")
    c.box(29.5, y(17), 9.5, 12.5, "contract", "Contract", "the harness\nresolves the\nnamed primitive\ninto its exact\nrule (Fig. 1)", number=2, emph=True)
    c.box(41, y(17), 13, 12.5, "verify", "Verify (S2)", "rows vs the contract:\nrejected SQL, n = k,\nempty arm, co-exist /\ntie / adjacency leaks;\nup to two rounds")
    c.box(55.5, y(17), 14, 12.5, "harness", "Sandbox", "read-only execution;\nrows → (n, k) per arm\n+ report-id sets", number=4)
    c.box(72, y(17), 27, 12.5, "harness", "S3 Test (deterministic)", "exact binomial, Fisher or modal-\nvs-runner-up on (n, k); floor\nn ≥ 10; both tails; three-\ndecision verdict", number=5)
    # gold lane
    c.box(1, y(2), 15, 12.5, "gold", "Stage gold", "released with the\nbenchmark; any stage can\nbe filled with gold to\nisolate the others")
    c.box(18, y(2), 20.5, 12.5, "gold", "Gold plan", "→ plan EM\n(claim type, fields)")
    c.box(41, y(2), 28.5, 12.5, "gold", "Gold evidence sets", "→ evidence F1, co-exist / tie leak,\nfaithfulness P(evidence exact |\nverdict right)")
    c.box(72, y(2), 27, 12.5, "gold", "Gold p, verdict", "→ accuracy, macro P/R/F1,\nsub-type accuracy, overclaim,\nunderclaim")
    # flows
    c.arrow((16, y(38.5)), (18, y(38.5)))
    c.arrow((16, y(25)), (19.5, y(32)), rad=-0.25)
    c.arrow((21, y(32)), (21, y(29.5))); c.arrow((24.5, y(29.5)), (24.5, y(32)))
    c.arrow((34.5, y(32)), (34.5, y(29.5)), "plan", loff=(2.6, 0))
    c.arrow((39, y(24)), (41, y(33)), "contract", accent=True, rad=-0.3, loff=(-4.5, 2.5))
    c.arrow((44, y(32)), (44, y(29.5))); c.arrow((48, y(29.5)), (48, y(32)))
    c.arrow((62, y(32)), (62, y(29.5)), "SQL", loff=(2.4, 0))
    c.arrow((55.5, y(20)), (54, y(20)))
    c.arrow((69.5, y(23)), (72, y(23)), "(n, k)", loff=(0, 2.2))
    c.arrow((85.5, y(29.5)), (85.5, y(32)), "verdict", loff=(5.5, 0))
    c.dotted((28.75, y(32)), (28.75, y(14.5)), "plan EM", loff=(0, -8))
    c.dotted((62, y(17)), (62, y(14.5)))
    c.dotted((85.5, y(17)), (85.5, y(14.5)))
    c.note(22.6, y(30.6), "⟳ 1", fs=c.bfs - 0.6, color=st.arrow)
    c.note(46, y(30.6), "⟳ ≤ 2", fs=c.bfs - 0.6, color=st.arrow)


# ====================================================================== level 3: the whole
def draw_whole(c: Canvas):
    st = c.st
    draw_framework(c, oy=0.0)
    gy = 58.0
    if st.lanes:
        c.lane(gy - 1.5, gy + 17.5, "generation", "benchmark generation")
    if st.groups:
        c.group(0.2, gy - 1.5, 99.3, 19.5, "STRATA benchmark generation")
    if st.numbered:
        c.note(1, gy + 18.8, "Benchmark generation (STRATA): (a) corpus → (b) templates → (c) cores → (d) stage gold → (e) screens → (f) release", fs=c.bfs, color=st.text, weight="bold")
    if st.lanes:
        c.header(50, gy + 18.2, "STRATA benchmark generation", "#6B5B95")
    xs = [(1, 15), (17.5, 31.5), (34, 48), (50.5, 64.5), (67, 81), (83.5, 99)]
    items = [("input", "Corpus", "MedTempo: 3,166 VAERS\nreports; expert-\nannotated leveled order:\neach stage holds its\nevents; first mention\nfixes the stage"),
             ("generation", "Templates", "26 groups, 7 families,\n3 scopes; claim form in\n4 registers; slots filled\nfrom the corpus\nvocabulary, no model\nrewriting"),
             ("generation", "Cores", "every fact the corpus\nsupports; mirror pairs\n(supported / refuted);\nnot-locatable minted\nfrom zero-count pairs;\ncapped, class-balanced"),
             ("gold", "Stage gold", "plan; evidence sets;\nexact tests, both tails;\nthree-decision verdict\nwith sub-typed\nabstention"),
             ("harness", "Screens", "permutation null per\nclaim shape (2,000\nrounds); six invariant\nfamilies; a deterministic\noracle reproduces\nevery label"),
             ("release", "Release", "questions file (inputs\nonly); answers file\n(gold + evidence ids);\ncodebook; pseudonymised\nids; dev 200 / test\n1,500, fact-disjoint")]
    for (x0, x1), (role, t, b), tag in zip(xs, items, "abcdef"):
        c.box(x0, gy, x1 - x0, 15.5, role, t, b, tag=f"({tag})")
    for (a0, a1), (b0, b1) in zip(xs[:-1], xs[1:]):
        c.arrow((a1, gy + 7.75), (b0, gy + 7.75))
    # the release feeds the framework: claims + codebook to the input side, gold to the gold lane
    bus_y = 51.5
    c.ax.plot([91, 91], [gy, bus_y], color=st.arrow, linewidth=st.arrow_lw, zorder=4)
    c.ax.plot([91, 8.5], [bus_y, bus_y], color=st.arrow, linewidth=st.arrow_lw, zorder=4)
    c.arrow((8.5, bus_y), (8.5, 45.8), None)
    c.note(50, bus_y + 1.3, "claims and the codebook go to the input side", ha="center", fs=c.bfs - 0.2, color=st.arrow)
    gcol = st.edge.get("gold", "#B38A1F") if st.key != "distill" else "#C9A227"
    c.ax.plot([99.6, 99.6], [gy, 8.2], color=gcol, linewidth=0.8, linestyle=(0, (1.2, 1.4)), zorder=1.5)
    c.ax.plot([96, 99.6], [gy, gy], color=gcol, linewidth=0.8, linestyle=(0, (1.2, 1.4)), zorder=1.5)
    c.arrow((99.6, 8.2), (99.0, 8.2), None, lw=0.6)
    c.ax.text(100.4, 30, "stage gold → every gold box", rotation=90, ha="center", va="center", fontsize=c.bfs - 0.6, color=gcol)


def main() -> None:
    for st in STYLES:
        xmin = -3.2 if st.lanes else -1.0
        c = Canvas(st, 100, 57, 3.5, title_fs=6.2, body_fs=5.0, xmin=-1.0)
        draw_contract(c); c.save(f"{st.key}_1_contract")
        c = Canvas(st, 100, 49, 7.2, title_fs=7.0, body_fs=5.5, xmin=xmin)
        draw_framework(c); c.save(f"{st.key}_2_framework")
        c = Canvas(st, 100, 78, 7.2, title_fs=7.0, body_fs=5.5, xmin=xmin)
        c.ax.set_xlim(xmin, 102)
        draw_whole(c); c.save(f"{st.key}_3_whole")


if __name__ == "__main__":
    main()
