"""Editable PowerPoint version of the one-slide STRATA / ART framework figure (user 2026-10-21): the
uploaded slide carried a single PNG; this rebuilds the same three-band layout from native shapes,
text boxes, a table and connectors, so every element can be edited in PowerPoint. Wording follows
the paper draft (docs/draft/body.tex); where the PNG's text contradicted the paper (corpus, S3 as a
function, exact tests, the three verdicts, the difficulty levels) the paper's wording is used.

    .venv313/bin/python scripts/pptx_framework.py
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

OUT = Path(__file__).resolve().parents[1] / "docs" / "draft" / "Figures" / "STRATA_framework_editable.pptx"
FONT = "Arial"

C = dict(band1="EEF3F8", band2="F8F2E8", band3="F1F1F5", panel="FFFFFF", border="C9CFD6", card="F6F8FA",
         brown="8B3A2F", purple="4B3F63", grey="5F6B7A", text="1F2933", muted="6B7280",
         s1="2E7D4F", s1f="E8F4EC", s2="2B6CB0", s2f="E6F0FA", s3="6B4FBB", s3f="EFEAF8",
         accent="D9792F", accentf="FBE2C9", gold="C9A227", goldf="FFF6D9", badge="4A5568",
         ok="2E7D4F", bad="B5462F", mid="C9A227", icon="2B6CB0")


def rgb(h):
    return RGBColor.from_string(h)


prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
slide = prs.slides.add_slide(prs.slide_layouts[6])


def box(x, y, w, h, fill=C["panel"], line=C["border"], radius=0.06, lw=0.75):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.adjustments[0] = radius
    sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill)
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = rgb(line); sh.line.width = Pt(lw)
    sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def text(x, y, w, h, paras, size=8, color=C["text"], bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font=FONT, italic=False):
    """paras: list of str or list of (str, dict) runs per paragraph; a str starting with '• ' keeps its bullet."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.04); tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = anchor
    first = True
    for para in paras:
        p = tf.paragraphs[0] if first else tf.add_paragraph(); first = False
        p.alignment = align
        runs = para if isinstance(para, list) else [(para, {})]
        for s, kw in runs:
            r = p.add_run(); r.text = s
            f = r.font; f.name = font; f.size = Pt(kw.get("size", size)); f.bold = kw.get("bold", bold); f.italic = kw.get("italic", italic)
            f.color.rgb = rgb(kw.get("color", color))
    return tb


def circle(x, y, d, fill, label, size=12, color="FFFFFF", bold=True, sub=None):
    sh = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill); sh.line.fill.background(); sh.shadow.inherit = False
    tf = sh.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label; r.font.name = FONT; r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = rgb(color)
    if sub:
        p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run(); r2.text = sub; r2.font.name = FONT; r2.font.size = Pt(size * 0.55); r2.font.color.rgb = rgb(color)
    return sh


def badge(x, y, label, w=0.42, h=0.22, fill=C["badge"]):
    sh = box(x, y, w, h, fill=fill, line=None, radius=0.3)
    tf = sh.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label; r.font.name = FONT; r.font.size = Pt(8); r.font.bold = True; r.font.color.rgb = rgb("FFFFFF")
    return sh


def arrow(x1, y1, x2, y2, color=C["grey"], lw=1.5):
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    conn.line.color.rgb = rgb(color); conn.line.width = Pt(lw)
    ln = conn.line._get_or_add_ln()
    tail = etree.SubElement(ln, qn("a:tailEnd")); tail.set("type", "triangle"); tail.set("w", "med"); tail.set("len", "med")
    return conn


def icon(kind, x, y, w, h, color=C["icon"]):
    shape = {"doc": MSO_SHAPE.FLOWCHART_DOCUMENT, "db": MSO_SHAPE.CAN, "gear": MSO_SHAPE.GEAR_6, "chart": MSO_SHAPE.RECTANGLE}[kind]
    sh = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = rgb("FFFFFF"); sh.line.color.rgb = rgb(color); sh.line.width = Pt(1.25); sh.shadow.inherit = False
    return sh


def band(y, h, fill):
    return box(0.15, y, 13.03, h, fill=fill, line=None, radius=0.04)


def header(y, number, title, subtitle, color):
    circle(0.3, y, 0.42, color, number, size=14)
    text(0.8, y - 0.02, 4.9, 0.45, [title], size=16, bold=True, color=color, anchor=MSO_ANCHOR.MIDDLE)
    text(5.0, y - 0.02, 8.1, 0.45, [subtitle], size=9.5, color=C["muted"], anchor=MSO_ANCHOR.MIDDLE)


def panel(x, y, w, h, num, title, title_note=None, fill=C["panel"]):
    box(x, y, w, h, fill=fill)
    badge(x + 0.08, y + 0.08, num)
    runs = [(title, {"bold": True, "size": 9.5})]
    if title_note:
        runs.append((" " + title_note, {"size": 8, "color": C["muted"]}))
    text(x + 0.55, y + 0.04, w - 0.6, 0.3, [runs], anchor=MSO_ANCHOR.MIDDLE)


def bullets(x, y, w, h, items, size=7.5, color=C["text"]):
    return text(x, y, w, h, ["• " + it for it in items], size=size, color=color)


# ====================================================================== band 1: benchmark construction
band(0.15, 2.75, C["band1"])
header(0.25, "1", "STRATA Benchmark Construction", "From annotated clinical timelines to temporal–statistical claims with gold at every stage", C["brown"])
py, ph = 0.8, 1.95

# 1.1 timelines
panel(0.3, py, 3.15, ph, "1.1", "Annotated clinical timelines", "(MedTempo)")
icon("doc", 0.42, py + 0.5, 0.42, 0.5); icon("doc", 0.92, py + 0.5, 0.42, 0.5)
text(0.38, py + 1.05, 1.25, 0.85, ["3,166 VAERS adverse-event reports (Janssen, Pfizer, Moderna), expert-annotated as a leveled order of events"], size=7.2)
box(1.72, py + 0.42, 1.65, 1.45, fill=C["card"])
text(1.76, py + 0.46, 1.6, 0.25, [[("Example timeline", {"bold": True, "size": 7.5}), (" (report MT-0482913)", {"size": 6.5, "color": C["muted"]})]])
ty = py + 0.95
slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(1.85), Inches(ty), Inches(3.25), Inches(ty)).line.color.rgb = rgb(C["s2"])
for cx, lab, col in ((1.95, "Fever", C["s2"]), (2.47, "Headache", C["bad"]), (2.99, "Fatigue", C["s1"])):
    circle(cx - 0.07, ty - 0.07, 0.14, col, "")
    text(cx - 0.35, ty + 0.08, 0.7, 0.2, [lab], size=6.5, bold=True, color=col, align=PP_ALIGN.CENTER)
text(1.76, py + 1.3, 1.6, 0.55, ["stage → events; the first mention fixes the stage; events at one stage co-exist"], size=6.5, color=C["muted"], align=PP_ALIGN.CENTER)
arrow(3.5, py + 0.95, 3.75, py + 0.95)

# 1.2 templates (an editable table)
panel(3.8, py, 2.95, ph, "1.2", "Hypothesis templates")
rows = [("Precedes", "A tends to precede B"), ("Co-occurs", "A and B tend to co-occur"), ("Sequence", "A, then B, then C"),
        ("First / Last", "A is most often the first (last)"), ("Position", "A falls in the earlier half"),
        ("Proximity", "A occurs right before B"), ("Threshold", "A precedes B in ≥ 2/3 of reports")]
tbl = slide.shapes.add_table(len(rows), 2, Inches(3.9), Inches(py + 0.4), Inches(2.75), Inches(1.45)).table
tbl.columns[0].width = Inches(0.85); tbl.columns[1].width = Inches(1.9)
fills = ["E3EAF2", "E6F2EA", "EFEAF8", "FBE9DD", "E6F0FA", "FFF6D9", "F1E7E5"]
for i, (fam, tpl) in enumerate(rows):
    tbl.rows[i].height = Inches(1.45 / len(rows))
    for j, s in enumerate((fam, tpl)):
        cell = tbl.cell(i, j); cell.text = ""
        cell.margin_left = cell.margin_right = Inches(0.04); cell.margin_top = cell.margin_bottom = Inches(0.0)
        cell.fill.solid(); cell.fill.fore_color.rgb = rgb(fills[i] if j == 0 else "FFFFFF")
        p = cell.text_frame.paragraphs[0]; r = p.add_run(); r.text = s
        r.font.name = FONT; r.font.size = Pt(6.8); r.font.bold = (j == 0); r.font.color.rgb = rgb(C["text"])
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
arrow(6.8, py + 0.95, 7.05, py + 0.95)

# 1.3 groups / families / levels
panel(7.1, py, 2.75, ph, "1.3", "Groups, families, levels")
for k, (yy, title, body, fill) in enumerate(((py + 0.4, "26 groups", "template × scope: 9 report, 16 cohort, 1 two-cohort", "E6F0FA"),
                                             (py + 0.9, "7 claim families", "precedes, co-occurs, sequence, first/last, position, proximity, threshold", "E6F2EA"),
                                             (py + 1.4, "3 difficulty levels", "Easy: one report · Medium: one cohort · Hard: two cohorts", "F1F1F5"))):
    box(7.2, yy, 2.55, 0.46, fill=fill, line=None)
    text(7.26, yy + 0.01, 2.45, 0.44, [[(title, {"bold": True, "size": 8})], [(body, {"size": 6.6, "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE)
arrow(9.9, py + 0.95, 10.15, py + 0.95)

# 1.4 gold
panel(10.2, py, 2.93, ph, "1.4", "Gold annotations", "(computed mechanically)")
cards = [("Gold plan", ["events, quantity", "denominator primitive, arms", "null kind, p0, tail", "test family, floor"]),
         ("Gold evidence sets", ["denominator ids", "numerator ids", "excluded ids", "n, k per arm"]),
         ("Gold statistics & verdict", ["p, both tails", "Wilson CI, Cohen's h", "verdict: supported,", "refuted, insufficient"])]
for k, (title, items) in enumerate(cards):
    cx = 10.28 + k * 0.96
    box(cx, py + 0.4, 0.9, 1.2, fill=C["goldf"], line="E7DDB5")
    text(cx + 0.02, py + 0.42, 0.86, 0.3, [title], size=6.8, bold=True)
    bullets(cx + 0.02, py + 0.68, 0.86, 0.9, items, size=6.2)
text(10.28, py + 1.63, 2.8, 0.3, ["validated by six invariant families and a deterministic oracle; screened against permutation nulls"], size=6.3, color=C["muted"], italic=True)

# ====================================================================== band 2: ART pipeline
band(3.0, 2.95, C["band2"])
header(3.1, "2", "ART Verification Pipeline", "From a natural-language claim to a verified verdict with auditable evidence", C["brown"])
qy, qh = 3.65, 2.2

# inputs
box(0.3, qy, 2.3, qh)
text(0.38, qy + 0.05, 2.15, 0.25, ["Inputs to the system"], size=9, bold=True)
icon("doc", 0.4, qy + 0.35, 0.3, 0.36)
text(0.76, qy + 0.32, 1.8, 0.5, ["A claim in natural language, with its cohort and level"], size=7)
text(0.38, qy + 0.85, 2.15, 0.25, ["Auxiliary resources (to S1)"], size=9, bold=True)
icon("db", 0.4, qy + 1.15, 0.28, 0.34); text(0.76, qy + 1.1, 1.8, 0.5, ["Codebook: the corpus stipulations as text; null sources; test definitions; dataset card"], size=6.8)
icon("db", 0.4, qy + 1.68, 0.28, 0.34); text(0.76, qy + 1.63, 1.8, 0.5, ["Annotation DB: report, vaccine, term, first-mention stage (ids pseudonymised)"], size=6.8)
arrow(2.62, qy + 0.5, 2.85, qy + 0.5); arrow(2.62, qy + 1.4, 2.85, qy + 1.4)

# S1
box(2.9, qy, 4.75, qh, fill=C["s1f"], line="BFD9C8")
circle(2.98, qy + 0.06, 0.5, C["s1"], "S1", size=11, sub="LLM")
text(3.52, qy + 0.03, 4.1, 0.55, [[("Articulate", {"bold": True, "size": 12, "color": C["s1"]})], [("form a structured plan; the claim-type mapping is withheld", {"size": 8, "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE)
steps = [("1", "Parse the claim", ["events, cohort", "quantity, direction"]),
         ("2", "Choose the primitive", ["denominator rule", "number of arms"]),
         ("3", "Compose the plan", ["null kind and p0, tail", "test family, floor"]),
         ("4", "Verify ⟳ 1", ["plan vs the codebook", "re-ask once"])]
for k, (n, title, items) in enumerate(steps):
    sx = 3.0 + k * 1.14
    box(sx, qy + 0.62, 1.08, 1.05, fill=C["panel"], line="BFD9C8")
    circle(sx + 0.06, qy + 0.67, 0.24, C["s1"], n, size=8)
    text(sx + 0.32, qy + 0.64, 0.75, 0.3, [title], size=7.2, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    bullets(sx + 0.04, qy + 0.95, 1.0, 0.7, items, size=6.5)
    if k < 3:
        arrow(sx + 1.08, qy + 1.15, sx + 1.14, qy + 1.15, lw=1)
box(3.0, qy + 1.75, 4.5, 0.38, fill=C["accentf"], line=C["accent"], lw=1.25)
text(3.06, qy + 1.76, 4.4, 0.36, [[("Contract: ", {"bold": True, "color": C["accent"], "size": 7.5}), ("the harness resolves the plan's primitive into its exact rule and states it to S2, so S2 implements a definition rather than interpreting advice", {"size": 7.2})]], anchor=MSO_ANCHOR.MIDDLE)
arrow(7.67, qy + 1.1, 7.9, qy + 1.1, color=C["accent"], lw=2)

# S2
box(7.95, qy, 2.75, qh, fill=C["s2f"], line="B9CFE6")
circle(8.03, qy + 0.06, 0.5, C["s2"], "S2", size=11, sub="LLM")
text(8.57, qy + 0.03, 2.1, 0.55, [[("Retrieve", {"bold": True, "size": 12, "color": C["s2"]})], [("plan to evidence sets", {"size": 8, "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE)
bullets(8.02, qy + 0.62, 2.62, 1.55, ["told the schema (column listing) and the contract",
                                     "writes one SQL per arm, one row per report: in_den, in_num, excl",
                                     "sandbox: read-only execution → n, k and report-id sets",
                                     "Verify ⟳ ≤2: rejected SQL, n = k, empty arm, co-exist / tie / adjacency leaks"], size=7)
arrow(10.72, qy + 1.1, 10.95, qy + 1.1)

# S3
box(11.0, qy, 2.13, qh, fill=C["s3f"], line="CFC3E8")
circle(11.08, qy + 0.06, 0.5, C["s3"], "S3", size=11, sub="function")
text(11.62, qy + 0.03, 1.5, 0.55, [[("Test", {"bold": True, "size": 12, "color": C["s3"]})], [("exact, deterministic", {"size": 8, "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE)
bullets(11.06, qy + 0.62, 2.0, 1.1, ["exact binomial vs p0 (fixed, text-stated or data-derived)", "Fisher's exact test for two arms", "modal-vs-runner-up for argmax", "floor n ≥ 10; both tails, CI, effect size"], size=6.8)
for cx, lw_, lab, col, mark in ((11.06, 0.6, "Supported", C["ok"], "✓"), (11.76, 0.5, "Refuted", C["bad"], "✗"), (12.34, 0.78, "Insufficient", C["mid"], "?")):
    circle(cx, qy + 1.78, 0.2, col, mark, size=8)
    text(cx + 0.19, qy + 1.75, lw_, 0.26, [lab], size=6, bold=True, anchor=MSO_ANCHOR.MIDDLE)
text(11.06, qy + 1.98, 2.0, 0.2, ["insufficient = not-locatable / sparse / underpowered"], size=5.8, color=C["muted"])

# ====================================================================== band 3: stage-level evaluation
band(6.05, 1.3, C["band3"])
circle(0.3, 6.45, 0.42, C["purple"], "3", size=14)
text(0.8, 6.4, 2.5, 0.5, ["Stage-level Evaluation"], size=16, bold=True, color=C["purple"], anchor=MSO_ANCHOR.MIDDLE)
text(0.8, 6.85, 2.5, 0.4, ["any stage can be set to gold to isolate the others"], size=7.5, color=C["muted"])
evals = [("Plan correctness", "the plan against the gold plan", "plan EM, claim-type EM", "doc", C["s1"]),
         ("Evidence correctness", "the retrieved report sets against the gold sets", "evidence F1, co-exist / tie leak, faithfulness P(evidence exact | verdict right)", "db", C["s2"]),
         ("Verdict and abstention", "the test and verdict against the gold", "accuracy, macro P/R/F1, p-agreement, overclaim, underclaim, sub-type accuracy", "gear", C["s3"])]
for k, (title, sub, metrics, ic, col) in enumerate(evals):
    ex = 3.35 + k * 3.28
    box(ex, 6.17, 3.15, 1.08)
    icon(ic, ex + 0.1, 6.45, 0.38, 0.42, color=col)
    text(ex + 0.58, 6.2, 2.5, 1.0, [[(title, {"bold": True, "size": 9.5, "color": col})], [(sub, {"size": 7.2})], [(metrics, {"size": 7, "color": C["muted"]})]])

prs.save(OUT)
print("wrote", OUT)
