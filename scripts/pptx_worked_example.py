"""Worked example figure (2026-10-22, user): one real test claim end to end, vertical, single column, in the
hand-drawn style of Figure 1 (Comic Sans MS body, Times New Roman titles; pastel panels; a failing system above
the working one with a red cross and a green check). Editable PowerPoint, exported to PDF for the paper.

Claim P-V1-0087 (test set): "After Moderna, Pain typically occurs before Asthenia." Every number below comes from
data/medtempo_eval.db and the runs results/test_gold_sets, test_qwen38_27b_cellB (EHRSQL-C) and
test_qwen38_27b_dprime_verify2 (ART); checked by the block at the bottom of this file.

    .venv313/bin/python scripts/pptx_worked_example.py
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
from collections import defaultdict
from math import comb
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
FIG = REPO / "docs" / "draft" / "Figures"
OUT = FIG / "worked_example.pptx"
ICONS = FIG / "icons"
FONT, TITLE_FONT, CODE_FONT = "Comic Sans MS", "Times New Roman", "Courier New"

C = dict(rust="A0522D", slate="4F6B75", sage="5E8263", gold="A8812E", text="2B2B2B", muted="66615B",
         border="C9C3B8", white="FFFFFF", banner="FBF3DC", grey_panel="EEF1F3", peach="F8EADF", green="E6EFE6",
         pill="FFFFFF", tag_ok="5E8263", tag_no="8A8A8A", tag_against="A8812E")
W = 4.8

# ------------------------------------------------------------------ data (all real; asserted below)
HID = "P-V1-0087-original-claim"
CLAIM = "After Moderna, Pain typically occurs before Asthenia."
EXAMPLES = [(9306105, "counted", "Pain first", C["tag_ok"]),
            (722607, "counted", "Asthenia first", C["tag_against"]),
            (1658567, "excluded", "same stage", C["tag_no"]),
            (1171286, "excluded", "no Asthenia", C["tag_no"])]


def load():
    con = sqlite3.connect(REPO / "data" / "medtempo_eval.db")
    fm, vac = defaultdict(dict), dict(con.execute("SELECT report_id, vaccine FROM reports"))
    for r, t, lv in con.execute("SELECT report_id, term, level FROM first_mention"):
        fm[r][t] = lv
    mod = [r for r in fm if vac.get(r) == "Moderna"]
    both = [r for r in mod if "Pain" in fm[r] and "Asthenia" in fm[r]]
    pb = [r for r in both if fm[r]["Pain"] < fm[r]["Asthenia"]]
    ap = [r for r in both if fm[r]["Pain"] > fm[r]["Asthenia"]]
    co = [r for r in both if fm[r]["Pain"] == fm[r]["Asthenia"]]

    def arm(run):
        for line in open(REPO / "results" / run / "predictions.jsonl"):
            x = json.loads(line)
            if x["hypothesis_id"] == HID:
                a = x["retrieval"]["arms"][0]
                return set(a["denominator_ids"]), set(a["numerator_ids"]), x["prediction"]["verdict"]
    gold, sql_c, art = arm("test_gold_sets"), arm("test_qwen38_27b_cellB"), arm("test_qwen38_27b_dprime_verify2")
    assert gold[0] == set(pb + ap) and gold[1] == set(pb) and gold[2] == "supported"
    assert sql_c[0] == set(pb) and sql_c[1] == set(pb) and sql_c[2] == "supported"
    assert art[0] == gold[0] and art[1] == gold[1] and art[2] == "supported"
    for r, kind, why, _ in EXAMPLES:
        assert (r in pb) if why == "Pain first" else (r in ap) if why == "Asthenia first" else (r in co) if why == "same stage" \
            else ("Pain" in fm[r] and "Asthenia" not in fm[r] and vac[r] == "Moderna")
    return dict(fm=fm, n_mod=len(mod), n_both=len(both), n_pb=len(pb), n_ap=len(ap), n_co=len(co))


def binom_tail(k, n, p=0.5):
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


D = load()
P_GOLD, P_SQLC = binom_tail(18, 22), binom_tail(18, 18)

# ------------------------------------------------------------------ drawing helpers
prs = Presentation()
H = 8.52
prs.slide_width, prs.slide_height = Inches(W), Inches(H)
slide = prs.slides.add_slide(prs.slide_layouts[6])
rgb = RGBColor.from_string


def _plain(sh):
    sh.shadow.inherit = False
    for ref in sh._element.iter(qn("a:effectRef")):
        ref.set("idx", "0")
    sppr = sh._element.find(qn("p:spPr"))
    if sppr is not None and sppr.find(qn("a:effectLst")) is None:
        etree.SubElement(sppr, qn("a:effectLst"))


def box(x, y, w, h, fill, line=None, radius=0.08, lw=0.75, dash=False):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.adjustments[0] = radius
    sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill)
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = rgb(line); sh.line.width = Pt(lw)
        if dash:
            sh.line.dash_style = 4
    _plain(sh); sh.text_frame.text = ""
    return sh


def text(x, y, w, h, paras, size=10, color=C["text"], align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.0):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.02); tf.margin_top = tf.margin_bottom = Inches(0.0)
    tf.vertical_anchor = anchor
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.line_spacing = spacing
        for s, kw in (para if isinstance(para, list) else [(para, {})]):
            r = p.add_run(); r.text = s; f = r.font
            f.name = kw.get("font", FONT); f.size = Pt(kw.get("size", size)); f.bold = kw.get("bold", False)
            f.italic = kw.get("italic", False); f.color.rgb = rgb(kw.get("color", color))
            if kw.get("sup"):
                f._rPr.set("baseline", "30000")
            if kw.get("sub"):
                f._rPr.set("baseline", "-25000")
    return tb


def title(x, y, label, color):
    text(x, y, W - 2 * x, 0.3, [[(label, {"font": TITLE_FONT, "bold": True, "size": 13, "color": color})]])


def arrow(x1, y1, x2, y2, color=C["muted"], lw=1.25, dashed=False):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color); c.line.width = Pt(lw)
    if dashed:
        c.line.dash_style = 4
    ln = c.line._get_or_add_ln()
    t = etree.SubElement(ln, qn("a:tailEnd")); t.set("type", "triangle"); t.set("w", "sm"); t.set("len", "sm")
    _plain(c)


def icon(name, x, y, size, color):
    svg = ICONS / f"{name}.svg"
    if not svg.exists():
        subprocess.run(["curl", "-sL", "-m", "30", "-o", str(svg), f"https://unpkg.com/lucide-static@latest/icons/{name}.svg"], check=True)
    png = ICONS / f"{name}_{color}.png"
    if not png.exists():
        src = svg.read_text().replace('stroke="currentColor"', f'stroke="#{color}"').replace('stroke-width="2"', 'stroke-width="2.25"')
        cairosvg.svg2png(bytestring=src.encode(), write_to=str(png), output_width=256, output_height=256)
    slide.shapes.add_picture(str(png), Inches(x), Inches(y), Inches(size), Inches(size))


def ev_runs(events, size):
    """Stage contents: Pain in rust, Asthenia in slate (bold), other events muted; at most two others shown."""
    key = [e for e in events if e in ("Pain", "Asthenia")]
    rest = [e for e in sorted(events) if e not in ("Pain", "Asthenia")]
    shown = key + rest[: max(0, 1 - len(key)) if key else 1]
    runs = []
    for i, e in enumerate(shown):
        if i:
            runs.append((", ", {"size": size, "color": C["muted"]}))
        col = C["rust"] if e == "Pain" else C["slate"] if e == "Asthenia" else C["muted"]
        runs.append((e, {"size": size, "bold": e in ("Pain", "Asthenia"), "color": col}))
    if len(shown) < len(events):
        runs.append((" …", {"size": size, "color": C["muted"]}))
    return [runs]


# ------------------------------------------------------------------ banner: the claim
y = 0.08
box(0.08, y, W - 0.16, 0.62, C["banner"], line="E3D3A6")
icon("message-square-quote", 0.17, y + 0.13, 0.36, C["gold"])
text(0.6, y + 0.04, W - 0.72, 0.56,
     [[("Claim (P-V1)  ", {"bold": True, "size": 10.5}), (CLAIM, {"size": 10.5})],
      [("gold: ", {"size": 9.5, "color": C["muted"]}), ("supported", {"size": 9.5, "bold": True, "color": C["sage"]}),
       (f"  (k = {D['n_pb']} of n = {D['n_pb'] + D['n_ap']}, p = {P_GOLD:.4f})", {"size": 9.5, "color": C["muted"]})]],
     anchor=MSO_ANCHOR.MIDDLE, spacing=1.05)

# ------------------------------------------------------------------ (a) which reports count
y = 0.8
ah = 3.34
box(0.08, y, W - 0.16, ah, C["grey_panel"])
title(0.16, y + 0.04, "(a) Which reports can witness the order?", C["slate"])
ry = y + 0.4
for rid, kind, why, col in EXAMPLES:
    t = D["fm"][rid]; levels = sorted(set(t.values()))[:3]
    text(0.16, ry + 0.0, 1.12, 0.22, [[(f"MT-{rid:07d}", {"size": 8.5, "bold": True, "color": C["text"]})]])
    text(0.16, ry + 0.2, 1.12, 0.3, [[(f"{kind}: ", {"size": 8.5, "bold": True, "color": col})], [(why, {"size": 8.5, "color": col})]], spacing=0.9)
    px = 1.3; pw = 1.04
    for j, lv in enumerate(levels):
        evs = [e for e, v in t.items() if v == lv]
        box(px, ry, pw, 0.44, C["pill"], line=C["border"], radius=0.18)
        text(px + 0.04, ry + 0.02, pw - 0.08, 0.4, ev_runs(evs, 8.5), align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=0.9)
        if j < len(levels) - 1:
            arrow(px + pw + 0.01, ry + 0.22, px + pw + 0.11, ry + 0.22, lw=1.0)
        px += pw + 0.11
    ry += 0.58
text(0.16, ry + 0.0, W - 0.32, 0.22, [[("Stages run left to right; events at one stage co-exist.", {"size": 8.5, "italic": True, "color": C["muted"]})]])
text(0.16, ry + 0.24, W - 0.32, 0.44,
     [[(f"Moderna: {D['n_mod']} reports, {D['n_both']} with both events; ", {"size": 9.5}),
       (f"{D['n_co']} at the same stage are excluded", {"size": 9.5, "bold": True}),
       (f", so n = {D['n_pb'] + D['n_ap']} and k = {D['n_pb']} (Pain first).", {"size": 9.5})]], spacing=1.0)

# ------------------------------------------------------------------ (b) EHRSQL-C: right verdict, wrong evidence
y = y + ah + 0.1
bh = 1.72
box(0.08, y, W - 0.16, bh, C["peach"])
title(0.16, y + 0.04, "(b) EHRSQL-C: one query", C["rust"])
box(0.18, y + 0.38, W - 0.36, 0.48, C["white"], line=C["border"], radius=0.06)
text(0.24, y + 0.41, W - 0.48, 0.44,
     [[("in_denominator = Pain.stage < Asthenia.stage", {"font": CODE_FONT, "size": 8.5, "bold": True, "color": C["rust"]})],
      [("in_numerator   = Pain.stage < Asthenia.stage", {"font": CODE_FONT, "size": 8.5})]], anchor=MSO_ANCHOR.MIDDLE)
text(0.18, y + 0.92, W - 0.36, 0.26,
     [[(f"n = {D['n_pb']}, k = {D['n_pb']}  →  p = 0.5", {"size": 9.5}), ("18", {"size": 9.5, "sup": True}),
       (" ≈ 4 × 10", {"size": 9.5}), ("−6", {"size": 9.5, "sup": True}),
       ("  →  ", {"size": 9.5}), ("supported", {"size": 9.5, "bold": True})]])
icon("circle-x", 0.18, y + 1.2, 0.3, C["rust"])
text(0.54, y + 1.17, W - 0.68, 0.5,
     [[("Right verdict, wrong evidence: ", {"size": 9.5, "bold": True, "color": C["rust"]}),
       (f"the {D['n_ap']} Asthenia-first reports are dropped, so n = k and the claim is supported whatever the data say.",
        {"size": 9.5})]], spacing=0.95)

# ------------------------------------------------------------------ (c) ART: right verdict on the gold evidence
y = y + bh + 0.1
ch = H - y - 0.08
box(0.08, y, W - 0.16, ch, C["green"])
title(0.16, y + 0.04, "(c) ART: articulate, retrieve, test", C["sage"])
rows = [("S1 Articulate", C["slate"], [[("denominator: both events at ", {"size": 9}), ("distinct", {"size": 9, "bold": True}),
                                        (" stages; null p", {"size": 9}), ("0", {"size": 9, "sub": True}),
                                        (" = 0.5; one-sided exact binomial; n ≥ 10", {"size": 9})]]),
        ("S2 Retrieve", C["rust"], [[("in_denominator = Pain.stage ≠ Asthenia.stage", {"font": CODE_FONT, "size": 8.5, "bold": True, "color": C["sage"]})],
                                    [("in_numerator   = Pain.stage < Asthenia.stage", {"font": CODE_FONT, "size": 8.5})]]),
        ("S3 Test", C["gold"], [[(f"n = {D['n_pb'] + D['n_ap']}, k = {D['n_pb']} (the gold sets);  P(X ≥ 18) = {P_GOLD:.4f}  →  ", {"size": 9}),
                                 ("supported", {"size": 9, "bold": True})]])]
ry = y + 0.38
for label, col, paras in rows:
    text(0.18, ry + 0.02, 1.02, 0.4, [[(label, {"size": 9.5, "bold": True, "color": col})]])
    box(1.2, ry, W - 1.38, 0.44, C["white"], line=C["border"], radius=0.06)
    text(1.26, ry + 0.01, W - 1.5, 0.42, paras, anchor=MSO_ANCHOR.MIDDLE, spacing=0.95)
    ry += 0.5
icon("circle-check", 0.18, ry + 0.04, 0.3, C["sage"])
text(0.54, ry + 0.02, W - 0.68, 0.36,
     [[("Right verdict on the right evidence: ", {"size": 9.5, "bold": True, "color": C["sage"]}),
       ("every counted report matches the gold set.", {"size": 9.5})]], spacing=0.95)

prs.save(OUT)
print("wrote", OUT, f"| gold p = {P_GOLD:.5f}, EHRSQL-C p = {P_SQLC:.2e}")
