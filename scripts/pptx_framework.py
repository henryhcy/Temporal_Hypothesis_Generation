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
# Figure 1 style (user 2026-10-22, swapped in the same day): Comic Sans MS body with Times New Roman titles.
# SLIDE_STYLE=verdana rebuilds the earlier Verdana version as a candidate file.
STYLE = os.environ.get("SLIDE_STYLE", "comic")
OUT = REPO / "docs" / "draft" / "Figures" / ("STRATA_framework_editable.pptx" if STYLE == "comic" else f"candidates/STRATA_framework_{STYLE}.pptx")
ICONS = REPO / "docs" / "draft" / "Figures" / "icons"
ICONS.mkdir(parents=True, exist_ok=True)
FONT, TITLE_FONT = {"comic": ("Comic Sans MS", "Times New Roman")}.get(STYLE, ("Verdana", "Verdana"))
# Rendering on Linux: ~/.config/fontconfig/conf.d/60-comic-sans-alias.conf maps Comic Sans MS to Comic Neue (OFL).

C = dict(rust="A0522D", wheat="D4B483", slate="4F6B75", gold="A8812E",
         text="2B2B2B", muted="5F5F5F", border="B8BEC4", panel="FFFFFF",
         band1="E7ECEF", band2="F1E9DF", band3="ECEAE7",
         tint_slate="E3EAED", tint_wheat="F3EBDD", tint_rust="F1E2DA", tint_grey="F2F2F2")
SZ = dict(band=16, panel=12, stage=14, stagesub=10.5, body=10, small=9, badge=10)
W, H = 11.0, 5.34     # compact (user 2026-10-23): narrower canvas so the same point sizes print ~20% larger; flatter panels


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
band(0.08, 2.2, C["band1"])
header(0.13, "1", "STRATA Benchmark Construction", C["rust"])
py, ph = 0.62, 1.58
X = [(0.2, 2.15), (2.57, 3.15), (5.94, 2.3), (8.46, 2.34)]

# 1.1 timelines
x, w = X[0]
panel(x, py, w, ph, "1.1", "Clinical timelines")
icon("clipboard-plus", x + 0.1, py + 0.44, 0.36, C["rust"]); icon("file-text", x + 0.5, py + 0.44, 0.36)
text(x + 0.92, py + 0.4, w - 0.98, 0.5, ["3,166 VAERS reports, 3 vaccines (MedTempo)"], size=SZ["small"], spacing=0.95)
ty = py + 1.12
ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x + 0.22), Inches(ty), Inches(x + w - 0.22), Inches(ty)); ln.line.color.rgb = rgb(C["slate"]); ln.line.width = Pt(1.75); _no_style_effects(ln)
for k, (lab, col) in enumerate((("Fever", C["slate"]), ("Headache", C["rust"]), ("Fatigue", C["gold"]))):
    cx = x + 0.32 + k * (w - 0.64) / 2
    circle(cx - 0.08, ty - 0.08, 0.16, col, "")
    text(cx - 0.5, ty + 0.1, 1.0, 0.24, [lab], size=SZ["small"], bold=True, color=col, align=PP_ALIGN.CENTER)
text(x + 0.1, py + 0.86, w - 0.2, 0.2, ["a leveled order: one stage per circle"], size=SZ["small"] - 1, color=C["muted"], align=PP_ALIGN.CENTER)
arrow(x + w + 0.02, py + ph / 2, x + w + 0.2, py + ph / 2)

# 1.2 templates (editable table)
x, w = X[1]
panel(x, py, w, ph, "1.2", "Hypothesis templates")
trows = [("Precedes", "A tends to precede B"), ("Co-occurs", "A and B tend to co-occur"), ("Sequence", "A, then B, then C"),
         ("First / Last", "A is most often first (last)"), ("Position", "A falls in the earlier half"),
         ("Proximity", "A occurs right before B"), ("Threshold", "A precedes B in ≥ 2/3")]
TH = 1.12
tbl = slide.shapes.add_table(len(trows), 2, Inches(x + 0.08), Inches(py + 0.42), Inches(w - 0.16), Inches(TH)).table
tbl.columns[0].width = Inches(1.0); tbl.columns[1].width = Inches(w - 1.16)
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
arrow(x + w + 0.02, py + ph / 2, x + w + 0.2, py + ph / 2)


def items(x, w, rows_, fill, icol):
    for k, (ic, title, body) in enumerate(rows_):
        yy = py + 0.42 + k * 0.38
        box(x + 0.08, yy, w - 0.16, 0.35, fill=fill, line=None, radius=0.12)
        icon(ic, x + 0.13, yy + 0.04, 0.27, icol)
        text(x + 0.46, yy + 0.0, w - 0.56, 0.35, [[(title, {"bold": True, "size": SZ["body"]})], [(body, {"size": SZ["small"] - 0.5, "color": C["muted"]})]],
             anchor=MSO_ANCHOR.MIDDLE, spacing=0.85)


# 1.3 groups / families / levels
x, w = X[2]
panel(x, py, w, ph, "1.3", "Groups and levels")
items(x, w, [("brain", "26 groups", "9 report, 16 cohort, 1 two-cohort"),
             ("network", "7 claim families", "order, timing and position"),
             ("chart-no-axes-column", "3 difficulty levels", "Easy, Medium, Hard")], C["tint_slate"], C["slate"])
arrow(x + w + 0.02, py + ph / 2, x + w + 0.2, py + ph / 2)

# 1.4 gold
x, w = X[3]
panel(x, py, w, ph, "1.4", "Gold at every stage")
items(x, w, [("file-check", "Plan", "rule, null, tail, test, floor"),
             ("database", "Evidence", "report ids per arm; n, k"),
             ("chart-bar", "Statistics, verdict", "p, Wilson CI, Cohen's h")], C["tint_wheat"], C["gold"])

# ====================================================================== band 2: ART pipeline + evaluation
B2 = 2.36
qy, qh = B2 + 0.5, 1.62
ey, eh = qy + qh + 0.08, 0.6
band(B2, ey + eh + 0.08 - B2, C["band2"])
header(B2 + 0.05, "2", "ART Verification Pipeline", C["rust"])
CX = [(0.2, 1.5), (1.92, 4.0), (6.14, 2.5), (8.86, 1.94)]

# inputs
x, w = CX[0]
box(x, qy, w, qh)
text(x + 0.06, qy + 0.04, w - 0.12, 0.3, ["Inputs"], size=SZ["panel"], bold=True)
for k, (ic, lab) in enumerate((("file-text", "claim, cohort"), ("list-checks", "codebook"), ("database", "timeline DB"))):
    yy = qy + 0.44 + k * 0.38
    icon(ic, x + 0.08, yy, 0.3); text(x + 0.44, yy - 0.02, w - 0.5, 0.34, [lab], size=SZ["body"], anchor=MSO_ANCHOR.MIDDLE)
arrow(x + w + 0.02, qy + qh / 2, x + w + 0.2, qy + qh / 2)

# S1
x, w = CX[1]
box(x, qy, w, qh, fill=C["tint_slate"], line=None)
circle(x + 0.08, qy + 0.07, 0.46, C["slate"], "S1", size=12, sub="LLM")
text(x + 0.62, qy + 0.04, w - 0.68, 0.52, [[("Articulate", {"bold": True, "size": SZ["stage"], "color": C["slate"]})], [("a structured plan; the mapping is withheld", {"size": SZ["small"], "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE, spacing=0.9)
steps = [("1", "Parse", "events, cohort"), ("2", "Primitive", "denominator rule"), ("3", "Compose", "null, p0, test"), ("4", "Verify", "1 round")]
sw_ = (w - 0.16 - 3 * 0.06) / 4
for k, (n, title, body) in enumerate(steps):
    sx = x + 0.08 + k * (sw_ + 0.06)
    box(sx, qy + 0.62, sw_, 0.62, fill=C["panel"], line=None, radius=0.1)
    circle(sx + 0.04, qy + 0.68, 0.2, C["slate"], n, size=8)
    text(sx + 0.25, qy + 0.645, sw_ - 0.26, 0.26, [title], size=SZ["body"], bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(sx + 0.05, qy + 0.92, sw_ - 0.08, 0.3, [body], size=SZ["small"], spacing=0.9)
    if k < 3:
        arrow(sx + sw_, qy + 0.93, sx + sw_ + 0.06, qy + 0.93, lw=1.0)
box(x + 0.08, qy + 1.3, w - 0.16, 0.26, fill=C["tint_rust"], line=C["rust"], lw=0.8, radius=0.12)
text(x + 0.12, qy + 1.3, w - 0.24, 0.26, [[("Contract: ", {"bold": True, "color": C["rust"], "size": SZ["small"]}), ("the harness resolves the primitive into its exact rule", {"size": SZ["small"]})]], anchor=MSO_ANCHOR.MIDDLE)
arrow(x + w + 0.02, qy + qh / 2, x + w + 0.2, qy + qh / 2, color=C["rust"], lw=2.0)

# S2
x, w = CX[2]
box(x, qy, w, qh, fill=C["tint_wheat"], line=None)
circle(x + 0.08, qy + 0.07, 0.46, C["rust"], "S2", size=12, sub="LLM")
text(x + 0.62, qy + 0.04, w - 0.68, 0.52, [[("Retrieve", {"bold": True, "size": SZ["stage"], "color": C["rust"]})], [("plan to evidence sets", {"size": SZ["small"], "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE, spacing=0.9)
for k, (ic, lab) in enumerate((("code", "one SQL per arm"), ("table-2", "sandbox: n, k, report ids"), ("timer-reset", "repair: up to 2 rounds"))):
    yy = qy + 0.66 + k * 0.31
    icon(ic, x + 0.1, yy, 0.26, C["rust"]); text(x + 0.42, yy - 0.02, w - 0.48, 0.3, [lab], size=SZ["small"], anchor=MSO_ANCHOR.MIDDLE)
arrow(x + w + 0.02, qy + qh / 2, x + w + 0.2, qy + qh / 2)

# S3
x, w = CX[3]
box(x, qy, w, qh, fill=C["tint_slate"], line=None)
circle(x + 0.08, qy + 0.07, 0.46, C["gold"], "S3", size=12, sub="function")
text(x + 0.62, qy + 0.04, w - 0.68, 0.52, [[("Test", {"bold": True, "size": SZ["stage"], "color": C["gold"]})], [("exact, deterministic", {"size": SZ["small"], "color": C["muted"]})]], anchor=MSO_ANCHOR.MIDDLE, spacing=0.9)
text(x + 0.1, qy + 0.6, w - 0.16, 0.42, ["binomial, Fisher or modal vs runner-up; floor n ≥ 10"], size=SZ["small"], spacing=0.9)
for k, (lab, ic, col) in enumerate((("supported", "circle-check", C["slate"]), ("refuted", "circle-x", C["rust"]), ("insufficient", "circle-help", C["gold"]))):
    yy = qy + 1.04 + k * 0.19
    icon(ic, x + 0.12, yy, 0.17, col)
    text(x + 0.34, yy - 0.04, w - 0.4, 0.24, [lab], size=SZ["small"], bold=True, anchor=MSO_ANCHOR.MIDDLE)

# 3: stage-level evaluation, under the stage each measure scores
circle(0.24, ey + 0.08, 0.42, C["slate"], "3", size=14)
text(0.74, ey + 0.02, 1.2, 0.3, ["Evaluation"], size=SZ["panel"], bold=True, color=C["slate"], anchor=MSO_ANCHOR.MIDDLE)
text(0.74, ey + 0.3, 1.25, 0.3, ["any stage can be set to gold"], size=SZ["small"] - 1, color=C["muted"], spacing=0.9)
for (x0, w0), (ic, title, metrics, col) in zip(CX[1:], (("file-check", "Plan correctness", "plan EM, claim-type EM", C["slate"]),
                                                       ("database", "Evidence correctness", "evidence F1, leaks, faithfulness", C["rust"]),
                                                       ("scale", "Verdict", "accuracy, P/R/F1, abstention", C["gold"]))):
    box(x0, ey, w0, eh)
    icon(ic, x0 + 0.08, ey + (eh - 0.32) / 2, 0.32, col)
    text(x0 + 0.46, ey + 0.02, w0 - 0.5, eh - 0.04, [[(title, {"bold": True, "size": SZ["body"], "color": col})], [(metrics, {"size": SZ["small"], "color": C["muted"]})]], spacing=0.9, anchor=MSO_ANCHOR.MIDDLE)

prs.save(OUT)
print("wrote", OUT)
