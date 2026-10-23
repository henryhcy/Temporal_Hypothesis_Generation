"""Editable PowerPoint version of the one-slide STRATA / ART framework figure (user 2026-10-21): the
uploaded slide carried a single PNG; this rebuilds the same three-band layout from native shapes,
text boxes, a table, connectors and line icons, so every element can be edited in PowerPoint.

Revisions: Lucide line icons (ISC licence, docs/draft/Figures/icons/), one font scale, no shadows,
solid slate_rust colours, tight layout. 2026-10-22 (user): no bullet lists, every size +3 pt, band
subtitles removed, Verdana (heavier at small sizes; DejaVu Sans stands in when rendering on Linux),
canvas height grown to fit the larger text. Wording follows the paper draft (docs/draft/body.tex).

    .venv313/bin/python scripts/pptx_framework.py
"""
from __future__ import annotations

import os
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
# SLIDE_STYLE=comic: Comic Sans MS body with Times New Roman titles, as in the hand-drawn figure style the
# user shared (2026-10-22); written to a separate candidate file. Default: Verdana throughout (Figure 1).
STYLE = os.environ.get("SLIDE_STYLE", "")
OUT = REPO / "docs" / "draft" / "Figures" / ("STRATA_framework_editable.pptx" if not STYLE else f"candidates/STRATA_framework_{STYLE}.pptx")
ICONS = REPO / "docs" / "draft" / "Figures" / "icons"
ICONS.mkdir(parents=True, exist_ok=True)
FONT, TITLE_FONT = {"comic": ("Comic Sans MS", "Times New Roman")}.get(STYLE, ("Verdana", "Verdana"))

C = dict(rust="A0522D", wheat="D4B483", slate="4F6B75", gold="A8812E",
         text="2B2B2B", muted="5F5F5F", border="B8BEC4", panel="FFFFFF",
         band1="E7ECEF", band2="F1E9DF", band3="ECEAE7",
         tint_slate="E3EAED", tint_wheat="F3EBDD", tint_rust="F1E2DA", tint_grey="F2F2F2")
SZ = dict(band=16, panel=12, stage=14, stagesub=10.5, body=10, small=9, badge=10)
W, H = 13.333, 6.96   # flatter (user 2026-10-22): evaluation folded into band 2, panels tightened


def icon_png(name: str, color: str, px: int = 256) -> Path:
    svg = ICONS / f"{name}.svg"
    if not svg.exists():
        subprocess.run(["curl", "-sL", "-m", "30", "-o", str(svg), f"https://unpkg.com/lucide-static@latest/icons/{name}.svg"], check=True)
    png = ICONS / f"{name}_{color}.png"
    if not png.exists():
        src = svg.read_text().replace('stroke="currentColor"', f'stroke="#{color}"').replace('stroke-width="2"', 'stroke-width="1.75"')
        cairosvg.svg2png(bytestring=src.encode(), write_to=str(png), output_width=px, output_height=px)
    return png


prs = Presentation()
prs.slide_width, prs.slide_height = Inches(W), Inches(H)
slide = prs.slides.add_slide(prs.slide_layouts[6])


def rgb(h):
    return RGBColor.from_string(h)


def _no_style_effects(sh):
    for ref in sh._element.iter(qn("a:effectRef")):
        ref.set("idx", "0")
    sppr = sh._element.find(qn("p:spPr"))
    if sppr is not None and sppr.find(qn("a:effectLst")) is None:
        etree.SubElement(sppr, qn("a:effectLst"))


def box(x, y, w, h, fill=C["panel"], line=C["border"], radius=0.05, lw=0.75):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.adjustments[0] = radius
    sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill)
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = rgb(line); sh.line.width = Pt(lw)
    sh.shadow.inherit = False; _no_style_effects(sh)
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
            is_title = kw.get("bold", bold) and kw.get("size", size) >= SZ["panel"]   # band, panel and stage titles
            f = r.font; f.name = TITLE_FONT if is_title else FONT; f.size = Pt(kw.get("size", size)); f.bold = kw.get("bold", bold); f.italic = kw.get("italic", italic)
            f.color.rgb = rgb(kw.get("color", color))
    return tb


def circle(x, y, d, fill, label, size=14, color="FFFFFF", sub=None):
    sh = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill); sh.line.fill.background(); sh.shadow.inherit = False; _no_style_effects(sh)
    tf = sh.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label; r.font.name = FONT; r.font.size = Pt(size); r.font.bold = True; r.font.color.rgb = rgb(color)
    if sub:
        p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run(); r2.text = sub; r2.font.name = FONT; r2.font.size = Pt(max(size * 0.5, 6)); r2.font.color.rgb = rgb(color)
    return sh


def badge(x, y, label, w=0.5, h=0.26, fill=C["slate"]):
    sh = box(x, y, w, h, fill=fill, line=None, radius=0.3)
    tf = sh.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label; r.font.name = FONT; r.font.size = Pt(SZ["badge"]); r.font.bold = True; r.font.color.rgb = rgb("FFFFFF")
    return sh


def arrow(x1, y1, x2, y2, color=C["muted"], lw=1.75):
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    conn.line.color.rgb = rgb(color); conn.line.width = Pt(lw)
    ln = conn.line._get_or_add_ln()
    tail = etree.SubElement(ln, qn("a:tailEnd")); tail.set("type", "triangle"); tail.set("w", "med"); tail.set("len", "med")
    _no_style_effects(conn)
    return conn


def icon(name, x, y, size=0.36, color=None):
    return slide.shapes.add_picture(str(icon_png(name, color or C["slate"])), Inches(x), Inches(y), Inches(size), Inches(size))


def band(y, h, fill):
    return box(0.1, y, W - 0.2, h, fill=fill, line=None, radius=0.03)


def header(y, number, title, color):
    circle(0.26, y, 0.46, color, number, size=15)
    text(0.8, y - 0.03, 7.0, 0.52, [title], size=SZ["band"], bold=True, color=color, anchor=MSO_ANCHOR.MIDDLE)


def panel(x, y, w, h, num, title, note=None):
    box(x, y, w, h)
    badge(x + 0.08, y + 0.08, num)
    runs = [(title, {"bold": True, "size": SZ["panel"]})]
    if note:
        runs.append((" " + note, {"size": SZ["small"], "color": C["muted"]}))
    text(x + 0.62, y + 0.04, w - 0.68, 0.34, [runs], anchor=MSO_ANCHOR.MIDDLE)


def rows(x, y, w, items, size=None, color=C["text"], spacing=1.0):
    return text(x, y, w, 0.3 * len(items) + 0.2, items, size=size or SZ["body"], color=color, spacing=spacing)


# ====================================================================== band 1: benchmark construction
band(0.1, 3.0, C["band1"])
header(0.17, "1", "STRATA Benchmark Construction", C["rust"])
py, ph = 0.68, 2.3

# 1.1 timelines
panel(0.24, py, 3.1, ph, "1.1", "Clinical timelines", "(MedTempo)")
icon("clipboard-plus", 0.34, py + 0.46, 0.46, C["rust"]); icon("file-text", 0.88, py + 0.46, 0.46)
text(0.3, py + 0.98, 1.4, 1.2, ["3,166 VAERS reports, three vaccines, each a leveled order of events"], size=SZ["body"])
box(1.72, py + 0.42, 1.54, 1.8, fill=C["tint_grey"], line=None)
text(1.76, py + 0.45, 1.48, 0.5, [[("Example timeline", {"bold": True, "size": SZ["small"]})], [("report MT-0482913", {"size": SZ["small"], "color": C["muted"]})]])
ty = py + 1.08
ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(1.86), Inches(ty), Inches(3.12), Inches(ty)); ln.line.color.rgb = rgb(C["slate"]); ln.line.width = Pt(1.75); _no_style_effects(ln)
for cx, lab, col in ((1.94, "Fever", C["slate"]), (2.49, "Headache", C["rust"]), (3.04, "Fatigue", C["gold"])):
    circle(cx - 0.07, ty - 0.07, 0.14, col, "")
    text(cx - 0.4, ty + 0.08, 0.8, 0.22, [lab], size=7, bold=True, color=col, align=PP_ALIGN.CENTER)
text(1.76, py + 1.4, 1.48, 0.8, ["stage → events; the first mention fixes the stage; events at one stage co-exist"], size=SZ["small"], color=C["muted"], align=PP_ALIGN.CENTER)
arrow(3.38, py + 1.1, 3.62, py + 1.1)

# 1.2 templates (editable table)
panel(3.66, py, 3.1, ph, "1.2", "Hypothesis templates")
trows = [("Precedes", "A tends to precede B"), ("Co-occurs", "A and B tend to co-occur"), ("Sequence", "A, then B, then C"),
         ("First / Last", "A is most often first (last)"), ("Position", "A falls in the earlier half"),
         ("Proximity", "A occurs right before B"), ("Threshold", "A precedes B in ≥ 2/3")]
TH = 1.78
tbl = slide.shapes.add_table(len(trows), 2, Inches(3.74), Inches(py + 0.42), Inches(2.94), Inches(TH)).table
tbl.columns[0].width = Inches(0.98); tbl.columns[1].width = Inches(1.96)
tints = [C["tint_slate"], C["tint_wheat"], C["tint_rust"]] * 3
for i, (fam, tpl) in enumerate(trows):
    tbl.rows[i].height = Inches(TH / len(trows))
    for j, s_ in enumerate((fam, tpl)):
        cell = tbl.cell(i, j); cell.text = ""
        cell.margin_left = cell.margin_right = Inches(0.04); cell.margin_top = cell.margin_bottom = Inches(0.0)
        cell.fill.solid(); cell.fill.fore_color.rgb = rgb(tints[i] if j == 0 else "FFFFFF")
        p_ = cell.text_frame.paragraphs[0]; r = p_.add_run(); r.text = s_
        r.font.name = FONT; r.font.size = Pt(SZ["small"]); r.font.bold = (j == 0); r.font.color.rgb = rgb(C["text"])
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
arrow(6.8, py + 1.1, 7.04, py + 1.1)

# 1.3 groups / families / levels
panel(7.08, py, 3.0, ph, "1.3", "Groups, families, levels")
for yy, hh, ic, title, body, fill in ((py + 0.42, 0.54, "brain", "26 groups", "9 report, 16 cohort, 1 two-cohort", C["tint_slate"]),
                                      (py + 1.02, 0.66, "network", "7 claim families", "precedes, co-occurs, sequence, first/last, position, proximity, threshold", C["tint_wheat"]),
                                      (py + 1.74, 0.5, "chart-no-axes-column", "3 difficulty levels", "Easy one report; Medium one cohort; Hard two cohorts", C["tint_rust"])):
    box(7.16, yy, 2.84, hh, fill=fill, line=None, radius=0.1)
    icon(ic, 7.22, yy + (hh - 0.36) / 2, 0.36, C["slate"] if fill != C["tint_rust"] else C["rust"])
    text(7.62, yy + 0.02, 2.36, hh - 0.04, [[(title, {"bold": True, "size": SZ["body"] + 1})], [(body, {"size": SZ["small"], "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE, spacing=0.95)
arrow(10.12, py + 1.1, 10.36, py + 1.1)

# 1.4 gold
panel(10.4, py, 2.69, ph, "1.4", "Gold at every stage")
for yy, hh, ic, title, body in ((py + 0.42, 0.62, "file-check", "Plan", "events, quantity, denominator primitive, arms, null, p0, tail, test, floor"),
                                (py + 1.1, 0.52, "database", "Evidence sets", "denominator, numerator and excluded ids; n, k per arm"),
                                (py + 1.68, 0.56, "chart-bar", "Statistics, verdict", "p on both tails, Wilson CI, Cohen's h; three-way verdict")):
    box(10.48, yy, 2.53, hh, fill=C["tint_wheat"], line=None, radius=0.1)
    icon(ic, 10.54, yy + (hh - 0.34) / 2, 0.34, C["gold"])
    text(10.92, yy + 0.02, 2.08, hh - 0.04, [[(title, {"bold": True, "size": SZ["body"] + 1})], [(body, {"size": SZ["small"], "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE, spacing=0.95)

# ====================================================================== band 2: ART pipeline + stage-level evaluation
B2 = 3.18
qy, qh = B2 + 0.58, 2.3
ey, eh = qy + qh + 0.1, 0.68            # evaluation row, aligned under the stage each measure scores
band(B2, ey + eh + 0.1 - B2, C["band2"])
header(B2 + 0.07, "2", "ART Verification Pipeline", C["rust"])

# inputs
box(0.24, qy, 2.42, qh)
text(0.3, qy + 0.05, 2.3, 0.3, ["Inputs"], size=SZ["panel"], bold=True)
icon("file-text", 0.32, qy + 0.4, 0.36); text(0.74, qy + 0.36, 1.9, 0.5, ["a claim in natural language, with its cohort and level"], size=SZ["body"], spacing=0.95)
text(0.3, qy + 0.9, 2.3, 0.3, ["Resources (to S1)"], size=SZ["panel"], bold=True)
icon("list-checks", 0.32, qy + 1.26, 0.36); text(0.74, qy + 1.2, 1.9, 0.6, ["codebook: the corpus stipulations as text; null sources; test definitions"], size=SZ["body"], spacing=0.95)
icon("database", 0.32, qy + 1.82, 0.36); text(0.74, qy + 1.76, 1.9, 0.52, ["timeline DB: report, vaccine, term, first-mention stage"], size=SZ["body"], spacing=0.95)
arrow(2.68, qy + 0.55, 2.92, qy + 0.55); arrow(2.68, qy + 1.45, 2.92, qy + 1.45)

# S1
box(2.96, qy, 4.86, qh, fill=C["tint_slate"], line=None)
circle(3.04, qy + 0.07, 0.54, C["slate"], "S1", size=13, sub="LLM")
text(3.64, qy + 0.04, 4.15, 0.6, [[("Articulate", {"bold": True, "size": SZ["stage"], "color": C["slate"]})], [("form a structured plan; the claim-type mapping is withheld", {"size": SZ["stagesub"], "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE, spacing=0.95)
steps = [("1", "file-search", "Parse the claim", "events, cohort, quantity, direction"),
         ("2", "git-branch", "Choose the primitive", "denominator rule; arms"),
         ("3", "sigma", "Compose the plan", "null, p0, tail, test family, floor"),
         ("4", "timer-reset", "Verify, 1 round", "plan vs the codebook; re-ask once")]
for k, (n, ic, title, body) in enumerate(steps):
    sx = 3.04 + k * 1.185
    box(sx, qy + 0.68, 1.13, 1.1, fill=C["panel"], line=None, radius=0.08)
    circle(sx + 0.06, qy + 0.74, 0.26, C["slate"], n, size=9)
    text(sx + 0.34, qy + 0.7, 0.78, 0.5, [title], size=SZ["body"], bold=True, anchor=MSO_ANCHOR.MIDDLE, spacing=0.9)
    icon(ic, sx + 0.07, qy + 1.24, 0.3)
    text(sx + 0.39, qy + 1.18, 0.74, 0.6, [body], size=SZ["small"] - 0.5, spacing=0.95)
    if k < 3:
        arrow(sx + 1.13, qy + 1.23, sx + 1.185, qy + 1.23, lw=1.25)
box(3.04, qy + 1.84, 4.7, 0.4, fill=C["tint_rust"], line=C["rust"], lw=1.0, radius=0.1)
text(3.1, qy + 1.84, 4.6, 0.4, [[("Contract: ", {"bold": True, "color": C["rust"], "size": SZ["small"]}), ("the harness resolves the plan's primitive into its exact rule and states it to S2", {"size": SZ["small"]})]], anchor=MSO_ANCHOR.MIDDLE, spacing=0.95)
arrow(7.84, qy + 1.15, 8.08, qy + 1.15, color=C["rust"], lw=2.25)

# S2
box(8.12, qy, 2.76, qh, fill=C["tint_wheat"], line=None)
circle(8.2, qy + 0.07, 0.54, C["rust"], "S2", size=13, sub="LLM")
text(8.8, qy + 0.04, 2.05, 0.6, [[("Retrieve", {"bold": True, "size": SZ["stage"], "color": C["rust"]})], [("plan to evidence sets", {"size": SZ["stagesub"], "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE)
for yy, ic, lab in ((qy + 0.68, "code", "told the schema and the contract; one SQL per arm, one row per report"),
                    (qy + 1.22, "table-2", "sandbox: read-only execution → n, k and report ids per arm"),
                    (qy + 1.74, "timer-reset", "verify, up to 2 rounds: rejected SQL, n = k, empty arm, rule leaks")):
    icon(ic, 8.2, yy + 0.04, 0.32, C["rust"]); text(8.58, yy, 2.28, 0.56, [lab], size=SZ["small"], spacing=0.95)
arrow(10.9, qy + 1.15, 11.14, qy + 1.15)

# S3
box(11.18, qy, 1.91, qh, fill=C["tint_slate"], line=None)
circle(11.26, qy + 0.07, 0.54, C["gold"], "S3", size=13, sub="function")
text(11.86, qy + 0.04, 1.21, 0.6, [[("Test", {"bold": True, "size": SZ["stage"], "color": C["gold"]})], [("exact, deterministic", {"size": SZ["stagesub"], "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE, spacing=0.95)
icon("settings", 11.26, qy + 0.72, 0.32, C["gold"])
text(11.62, qy + 0.66, 1.45, 0.9, ["exact binomial vs p0; Fisher's test, two arms; modal-vs-runner-up, argmax; floor n ≥ 10"], size=SZ["small"], spacing=0.95)
for k, (lab, ic, col) in enumerate((("Supported", "circle-check", C["slate"]), ("Refuted", "circle-x", C["rust"]), ("Insufficient", "circle-help", C["gold"]))):
    yy = qy + 1.56 + k * 0.24
    icon(ic, 11.26, yy, 0.22, col)
    text(11.52, yy - 0.03, 1.5, 0.28, [lab], size=SZ["small"], bold=True, anchor=MSO_ANCHOR.MIDDLE)

# 3: stage-level evaluation, one row under the stages (was a separate band)
circle(0.26, ey + 0.08, 0.46, C["slate"], "3", size=15)
text(0.8, ey + 0.02, 1.9, 0.32, ["Evaluation"], size=SZ["panel"], bold=True, color=C["slate"], anchor=MSO_ANCHOR.MIDDLE)
text(0.8, ey + 0.3, 1.86, 0.4, ["per stage; any stage can be set to gold"], size=SZ["small"], color=C["muted"], spacing=0.92)
for (x0, w0), (ic, title, metrics, col) in zip(((2.96, 4.86), (8.12, 2.76), (11.18, 1.91)),
                                              (("file-check", "Plan correctness", "plan EM, claim-type EM", C["slate"]),
                                               ("database", "Evidence correctness", "evidence F1, co-exist / tie leak, faithfulness", C["rust"]),
                                               ("scale", "Verdict", "accuracy, P/R/F1, over- and underclaim", C["gold"]))):
    box(x0, ey, w0, eh)
    icon(ic, x0 + 0.08, ey + (eh - 0.36) / 2, 0.36, col)
    text(x0 + 0.5, ey + 0.01, w0 - 0.54, eh - 0.02, [[(title, {"bold": True, "size": SZ["body"] + 1, "color": col})], [(metrics, {"size": SZ["small"], "color": C["muted"]})]], spacing=0.92, anchor=MSO_ANCHOR.MIDDLE)

prs.save(OUT)
print("wrote", OUT)
