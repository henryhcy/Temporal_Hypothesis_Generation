"""Editable PowerPoint version of the one-slide STRATA / ART framework figure (user 2026-10-21): the
uploaded slide carried a single PNG; this rebuilds the same three-band layout from native shapes,
text boxes, a table, connectors and line icons, so every element can be edited in PowerPoint.

Revision (user 2026-10-21 evening): icons like the original (Lucide line icons, ISC licence, fetched
into docs/draft/Figures/icons/ and recoloured), one font family with a fixed size scale, no shadows,
solid muted colours in the slate_rust style, and a tighter layout with less white space. Wording
follows the paper draft (docs/draft/body.tex).

    .venv313/bin/python scripts/pptx_framework.py
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import cairosvg
from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "draft" / "Figures" / "STRATA_framework_editable.pptx"
ICONS = REPO / "docs" / "draft" / "Figures" / "icons"
ICONS.mkdir(parents=True, exist_ok=True)
FONT = "Arial"

# slate_rust style: three solid hues plus neutral text, and light solid tints for bands and cards
C = dict(rust="A0522D", wheat="D4B483", slate="4F6B75", gold="A8812E",
         text="2B2B2B", muted="6B6B6B", border="B8BEC4", panel="FFFFFF",
         band1="E7ECEF", band2="F1E9DF", band3="ECEAE7",
         tint_slate="E3EAED", tint_wheat="F3EBDD", tint_rust="F1E2DA", tint_grey="F2F2F2",
         ok="4F6B75", bad="A0522D", mid="A8812E")
SZ = dict(band=15, bandsub=9, panel=9, stage=11, stagesub=7.5, body=7, small=6.2, badge=7.5)


# ------------------------------------------------------------------ icons (Lucide, ISC)
def icon_png(name: str, color: str, px: int = 256) -> Path:
    svg = ICONS / f"{name}.svg"
    if not svg.exists():
        subprocess.run(["curl", "-sL", "-m", "30", "-o", str(svg), f"https://unpkg.com/lucide-static@latest/icons/{name}.svg"], check=True)
    png = ICONS / f"{name}_{color}.png"
    if not png.exists():
        src = svg.read_text()
        src = src.replace('stroke="currentColor"', f'stroke="#{color}"').replace('stroke-width="2"', 'stroke-width="1.75"')
        cairosvg.svg2png(bytestring=src.encode(), write_to=str(png), output_width=px, output_height=px)
    return png


prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(6.85)  # canvas trimmed to the content
slide = prs.slides.add_slide(prs.slide_layouts[6])


def rgb(h):
    return RGBColor.from_string(h)


def _no_style_effects(sh):
    """Point the shape style's effect reference at the theme's empty slot, so no renderer draws a shadow."""
    for ref in sh._element.iter(qn("a:effectRef")):
        ref.set("idx", "0")


def box(x, y, w, h, fill=C["panel"], line=C["border"], radius=0.05, lw=0.75):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.adjustments[0] = radius
    sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill)
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = rgb(line); sh.line.width = Pt(lw)
    sh.shadow.inherit = False
    _no_style_effects(sh)
    sh.text_frame.text = ""
    return sh


def text(x, y, w, h, paras, size=None, color=C["text"], bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False, spacing=1.0):
    size = size or SZ["body"]
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.03); tf.margin_top = tf.margin_bottom = Inches(0.01)
    tf.vertical_anchor = anchor
    first = True
    for para in paras:
        p = tf.paragraphs[0] if first else tf.add_paragraph(); first = False
        p.alignment = align; p.line_spacing = spacing
        runs = para if isinstance(para, list) else [(para, {})]
        for s, kw in runs:
            r = p.add_run(); r.text = s
            f = r.font; f.name = FONT; f.size = Pt(kw.get("size", size)); f.bold = kw.get("bold", bold); f.italic = kw.get("italic", italic)
            f.color.rgb = rgb(kw.get("color", color))
    return tb


def bullets(x, y, w, h, items, size=None, color=C["text"]):
    return text(x, y, w, h, ["• " + it for it in items], size=size or SZ["body"], color=color)


def circle(x, y, d, fill, label, size=12, color="FFFFFF", sub=None):
    sh = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill); sh.line.fill.background(); sh.shadow.inherit = False
    _no_style_effects(sh)
    tf = sh.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label; r.font.name = FONT; r.font.size = Pt(size); r.font.bold = True; r.font.color.rgb = rgb(color)
    if sub:
        p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run(); r2.text = sub; r2.font.name = FONT; r2.font.size = Pt(max(size * 0.5, 5)); r2.font.color.rgb = rgb(color)
    return sh


def badge(x, y, label, w=0.4, h=0.2, fill=C["slate"]):
    sh = box(x, y, w, h, fill=fill, line=None, radius=0.3)
    tf = sh.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label; r.font.name = FONT; r.font.size = Pt(SZ["badge"]); r.font.bold = True; r.font.color.rgb = rgb("FFFFFF")
    return sh


def arrow(x1, y1, x2, y2, color=C["muted"], lw=1.5):
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    conn.line.color.rgb = rgb(color); conn.line.width = Pt(lw)
    ln = conn.line._get_or_add_ln()
    tail = etree.SubElement(ln, qn("a:tailEnd")); tail.set("type", "triangle"); tail.set("w", "med"); tail.set("len", "med")
    return conn


def icon(name, x, y, size=0.34, color=None):
    pic = slide.shapes.add_picture(str(icon_png(name, color or C["slate"])), Inches(x), Inches(y), Inches(size), Inches(size))
    return pic


def band(y, h, fill):
    return box(0.12, y, 13.09, h, fill=fill, line=None, radius=0.03)


def header(y, number, title, subtitle, color):
    circle(0.24, y, 0.4, color, number, size=13)
    text(0.7, y - 0.03, 4.4, 0.46, [title], size=SZ["band"], bold=True, color=color, anchor=MSO_ANCHOR.MIDDLE)
    text(4.7, y - 0.03, 8.4, 0.46, [subtitle], size=SZ["bandsub"], color=C["muted"], anchor=MSO_ANCHOR.MIDDLE)


def panel(x, y, w, h, num, title, note=None):
    box(x, y, w, h)
    badge(x + 0.07, y + 0.07, num)
    runs = [(title, {"bold": True, "size": SZ["panel"]})]
    if note:
        runs.append((" " + note, {"size": SZ["small"], "color": C["muted"]}))
    text(x + 0.5, y + 0.03, w - 0.55, 0.28, [runs], anchor=MSO_ANCHOR.MIDDLE)


# ====================================================================== band 1: benchmark construction
band(0.1, 2.5, C["band1"])
header(0.17, "1", "STRATA Benchmark Construction", "from annotated clinical timelines to temporal–statistical claims with gold at every stage", C["rust"])
py, ph = 0.68, 1.84

# 1.1 timelines
panel(0.24, py, 3.1, ph, "1.1", "Annotated clinical timelines", "(MedTempo)")
icon("clipboard-plus", 0.34, py + 0.42, 0.42, C["rust"]); icon("file-text", 0.84, py + 0.42, 0.42)
text(0.3, py + 0.92, 1.35, 0.85, ["3,166 VAERS adverse-event reports (Janssen, Pfizer, Moderna), expert-annotated as a leveled order of events"], size=SZ["body"])
box(1.7, py + 0.38, 1.56, 1.38, fill=C["tint_grey"], line=None)
text(1.74, py + 0.41, 1.5, 0.24, [[("Example timeline", {"bold": True, "size": SZ["body"]}), (" (report MT-0482913)", {"size": SZ["small"], "color": C["muted"]})]])
ty = py + 0.88
ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(1.84), Inches(ty), Inches(3.14), Inches(ty)); ln.line.color.rgb = rgb(C["slate"]); ln.line.width = Pt(1.5)
for cx, lab, col in ((1.94, "Fever", C["slate"]), (2.47, "Headache", C["rust"]), (3.0, "Fatigue", C["gold"])):
    circle(cx - 0.065, ty - 0.065, 0.13, col, "")
    text(cx - 0.35, ty + 0.07, 0.7, 0.18, [lab], size=SZ["small"], bold=True, color=col, align=PP_ALIGN.CENTER)
text(1.74, py + 1.2, 1.5, 0.52, ["stage → events; the first mention fixes the stage; events at one stage co-exist"], size=SZ["small"], color=C["muted"], align=PP_ALIGN.CENTER)
arrow(3.38, py + 0.9, 3.6, py + 0.9)

# 1.2 templates (editable table)
panel(3.64, py, 2.9, ph, "1.2", "Hypothesis templates")
rows = [("Precedes", "A tends to precede B"), ("Co-occurs", "A and B tend to co-occur"), ("Sequence", "A, then B, then C"),
        ("First / Last", "A is most often first (last)"), ("Position", "A falls in the earlier half"),
        ("Proximity", "A occurs right before B"), ("Threshold", "A precedes B in ≥ 2/3 of reports")]
tbl = slide.shapes.add_table(len(rows), 2, Inches(3.72), Inches(py + 0.36), Inches(2.74), Inches(1.4)).table
tbl.columns[0].width = Inches(0.82); tbl.columns[1].width = Inches(1.92)
tints = [C["tint_slate"], C["tint_wheat"], C["tint_rust"]] * 3
for i, (fam, tpl) in enumerate(rows):
    tbl.rows[i].height = Inches(1.4 / len(rows))
    for j, s in enumerate((fam, tpl)):
        cell = tbl.cell(i, j); cell.text = ""
        cell.margin_left = cell.margin_right = Inches(0.04); cell.margin_top = cell.margin_bottom = Inches(0.0)
        cell.fill.solid(); cell.fill.fore_color.rgb = rgb(tints[i] if j == 0 else "FFFFFF")
        p = cell.text_frame.paragraphs[0]; r = p.add_run(); r.text = s
        r.font.name = FONT; r.font.size = Pt(SZ["small"] + 0.4); r.font.bold = (j == 0); r.font.color.rgb = rgb(C["text"])
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
arrow(6.58, py + 0.9, 6.8, py + 0.9)

# 1.3 groups / families / levels
panel(6.84, py, 2.95, ph, "1.3", "Groups, families, levels")
for yy, ic, title, body, fill in ((py + 0.36, "brain", "26 groups", "template × scope: 9 report, 16 cohort, 1 two-cohort", C["tint_slate"]),
                                  (py + 0.84, "network", "7 claim families", "precedes, co-occurs, sequence, first/last, position, proximity, threshold", C["tint_wheat"]),
                                  (py + 1.32, "chart-no-axes-column", "3 difficulty levels", "Easy: one report · Medium: one cohort · Hard: two cohorts", C["tint_rust"])):
    box(6.92, yy, 2.79, 0.44, fill=fill, line=None, radius=0.1)
    icon(ic, 6.98, yy + 0.06, 0.32, C["slate"] if fill != C["tint_rust"] else C["rust"])
    text(7.34, yy + 0.01, 2.35, 0.42, [[(title, {"bold": True, "size": SZ["body"] + 0.8})], [(body, {"size": SZ["small"], "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE)
arrow(9.83, py + 0.9, 10.05, py + 0.9)

# 1.4 gold
panel(10.09, py, 3.12, ph, "1.4", "Gold annotations", "(computed mechanically)")
cards = [("file-check", "Plan", ["events, quantity", "denominator primitive, arms", "null kind, p0, tail", "test family, floor"]),
         ("database", "Evidence sets", ["denominator ids", "numerator ids", "excluded ids", "n, k per arm"]),
         ("chart-bar", "Statistics, verdict", ["p on both tails", "Wilson CI, Cohen's h", "supported / refuted /", "insufficient (sub-typed)"])]
for k, (ic, title, items) in enumerate(cards):
    cx = 10.17 + k * 1.0
    box(cx, py + 0.36, 0.96, 1.2, fill=C["tint_wheat"], line=None, radius=0.1)
    icon(ic, cx + 0.04, py + 0.4, 0.26, C["gold"])
    text(cx + 0.3, py + 0.38, 0.66, 0.3, [title], size=SZ["small"] + 0.4, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    bullets(cx + 0.03, py + 0.66, 0.92, 0.9, items, size=SZ["small"])
text(10.17, py + 1.58, 2.98, 0.24, ["validated by six invariant families and a deterministic oracle; screened against permutation nulls"], size=SZ["small"], color=C["muted"], italic=True)

# ====================================================================== band 2: ART pipeline
band(2.68, 2.76, C["band2"])
header(2.75, "2", "ART Verification Pipeline", "from a natural-language claim to a verified verdict with auditable evidence", C["rust"])
qy, qh = 3.25, 2.1

# inputs
box(0.24, qy, 2.3, qh)
text(0.3, qy + 0.04, 2.2, 0.24, ["Inputs to the system"], size=SZ["panel"], bold=True)
icon("file-text", 0.32, qy + 0.32, 0.34); text(0.72, qy + 0.3, 1.78, 0.44, ["a claim in natural language, with its cohort and level"], size=SZ["body"])
text(0.3, qy + 0.8, 2.2, 0.24, ["Auxiliary resources (to S1)"], size=SZ["panel"], bold=True)
icon("list-checks", 0.32, qy + 1.08, 0.34); text(0.72, qy + 1.04, 1.78, 0.5, ["codebook: the corpus stipulations as text; null sources; test definitions; dataset card"], size=SZ["body"])
icon("database", 0.32, qy + 1.6, 0.34); text(0.72, qy + 1.56, 1.78, 0.5, ["annotation DB: report, vaccine, term, first-mention stage (ids pseudonymised)"], size=SZ["body"])
arrow(2.56, qy + 0.5, 2.78, qy + 0.5); arrow(2.56, qy + 1.3, 2.78, qy + 1.3)

# S1
box(2.82, qy, 4.8, qh, fill=C["tint_slate"], line=None)
circle(2.9, qy + 0.06, 0.48, C["slate"], "S1", size=11, sub="LLM")
text(3.42, qy + 0.03, 4.15, 0.52, [[("Articulate", {"bold": True, "size": SZ["stage"], "color": C["slate"]})], [("form a structured plan; the claim-type mapping is withheld", {"size": SZ["stagesub"], "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE)
steps = [("1", "file-search", "Parse the claim", ["events, cohort", "quantity, direction"]),
         ("2", "git-branch", "Choose the primitive", ["denominator rule", "number of arms"]),
         ("3", "sigma", "Compose the plan", ["null kind, p0, tail", "test family, floor"]),
         ("4", "timer-reset", "Verify, 1 round", ["plan vs the codebook", "re-ask once"])]
for k, (n, ic, title, items) in enumerate(steps):
    sx = 2.9 + k * 1.16
    box(sx, qy + 0.58, 1.1, 0.98, fill=C["panel"], line=None, radius=0.08)
    circle(sx + 0.05, qy + 0.63, 0.22, C["slate"], n, size=7.5)
    text(sx + 0.3, qy + 0.6, 0.8, 0.28, [title], size=SZ["body"], bold=True, anchor=MSO_ANCHOR.MIDDLE)
    icon(ic, sx + 0.06, qy + 0.9, 0.26)
    bullets(sx + 0.34, qy + 0.88, 0.76, 0.66, items, size=SZ["small"])
    if k < 3:
        arrow(sx + 1.1, qy + 1.07, sx + 1.16, qy + 1.07, lw=1)
box(2.9, qy + 1.63, 4.64, 0.4, fill=C["tint_rust"], line=C["rust"], lw=1.0, radius=0.1)
text(2.96, qy + 1.64, 4.54, 0.38, [[("Contract: ", {"bold": True, "color": C["rust"], "size": SZ["body"]}), ("the harness resolves the plan's primitive into its exact rule and states it to S2, so S2 implements a definition rather than interpreting advice", {"size": SZ["body"]})]], anchor=MSO_ANCHOR.MIDDLE)
arrow(7.64, qy + 1.05, 7.86, qy + 1.05, color=C["rust"], lw=2)

# S2
box(7.9, qy, 2.78, qh, fill=C["tint_wheat"], line=None)
circle(7.98, qy + 0.06, 0.48, C["rust"], "S2", size=11, sub="LLM")
text(8.5, qy + 0.03, 2.15, 0.52, [[("Retrieve", {"bold": True, "size": SZ["stage"], "color": C["rust"]})], [("plan to evidence sets", {"size": SZ["stagesub"], "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE)
for yy, ic, lab in ((qy + 0.6, "code", "told the schema (column listing) and the contract; writes one SQL per arm, one row per report: in_den, in_num, excl"),
                    (qy + 1.1, "table-2", "sandbox: read-only execution → n, k and report-id sets per arm"),
                    (qy + 1.55, "timer-reset", "verify, up to 2 rounds: rejected SQL, n = k, empty arm, co-exist / tie / adjacency leaks")):
    icon(ic, 7.98, yy + 0.02, 0.3, C["rust"]); text(8.34, yy, 2.3, 0.5, [lab], size=SZ["body"])
arrow(10.7, qy + 1.05, 10.92, qy + 1.05)

# S3
box(10.96, qy, 2.25, qh, fill=C["tint_slate"], line=None)
circle(11.04, qy + 0.06, 0.48, C["gold"], "S3", size=11, sub="function")
text(11.56, qy + 0.03, 1.62, 0.52, [[("Test", {"bold": True, "size": SZ["stage"], "color": C["gold"]})], [("exact, deterministic", {"size": SZ["stagesub"], "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE)
icon("settings", 11.04, qy + 0.62, 0.3, C["gold"])
bullets(11.4, qy + 0.58, 1.78, 1.0, ["exact binomial vs p0 (fixed, text-stated or data-derived)", "Fisher's exact test, two arms", "modal-vs-runner-up, argmax", "floor n ≥ 10; both tails"], size=SZ["small"])
for cx, w_, lab, ic, col in ((11.02, 0.66, "Supported", "circle-check", C["ok"]), (11.74, 0.56, "Refuted", "circle-x", C["bad"]), (12.36, 0.8, "Insufficient", "circle-help", C["mid"])):
    icon(ic, cx, qy + 1.64, 0.24, col)
    text(cx + 0.24, qy + 1.63, w_, 0.26, [lab], size=SZ["small"], bold=True, anchor=MSO_ANCHOR.MIDDLE)
text(11.02, qy + 1.88, 2.15, 0.2, ["insufficient: not-locatable / sparse / underpowered"], size=SZ["small"] - 0.6, color=C["muted"])

# ====================================================================== band 3: stage-level evaluation
band(5.52, 1.22, C["band3"])
circle(0.24, 5.78, 0.4, C["slate"], "3", size=13)
text(0.7, 5.72, 2.5, 0.5, ["Stage-level Evaluation"], size=SZ["band"], bold=True, color=C["slate"], anchor=MSO_ANCHOR.MIDDLE)
text(0.7, 6.18, 2.5, 0.45, ["any stage can be set to gold to isolate the others"], size=SZ["body"], color=C["muted"])
evals = [("file-check", "Plan correctness", "the plan against the gold plan", "plan EM, claim-type EM", C["slate"]),
         ("database", "Evidence correctness", "the retrieved report sets against the gold sets", "evidence F1, co-exist / tie leak, faithfulness P(evidence exact | verdict right)", C["rust"]),
         ("scale", "Verdict and abstention", "the test and verdict against the gold", "accuracy, macro P/R/F1, p-agreement, overclaim, underclaim, sub-type accuracy", C["gold"])]
for k, (ic, title, sub, metrics, col) in enumerate(evals):
    ex = 3.3 + k * 3.32
    box(ex, 5.62, 3.22, 1.02)
    icon(ic, ex + 0.1, 5.9, 0.44, col)
    text(ex + 0.62, 5.66, 2.55, 0.96, [[(title, {"bold": True, "size": SZ["panel"], "color": col})], [(sub, {"size": SZ["body"]})], [(metrics, {"size": SZ["small"], "color": C["muted"]})]], spacing=1.05, anchor=MSO_ANCHOR.MIDDLE)

prs.save(OUT)
print("wrote", OUT)
