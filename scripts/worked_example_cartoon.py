"""Worked example in three cartoon styles (2026-10-22, user: "more cartoonish ... three different styles ... avoid
large white space with small texts"). Drawn directly as SVG at printed size (one column, 240 pt wide), so every
font size below is the size in the paper; rendered to PDF/PNG with cairosvg.

Styles: sketch (hand-drawn wobbly outlines, handwriting font), flat (thick outlines, offset sticker shadows, robot
mascots with speech bubbles), comic (bordered comic-strip panels, caption boxes, speech bubbles, a burst).
Characters are Microsoft Fluent Emoji (MIT licence, docs/draft/Figures/emoji/LICENSE_fluentui_emoji.txt); fonts are
OFL (Patrick Hand, Kalam, Fredoka, Bangers, Comic Neue). All numbers are real and asserted against the database and
the test runs (same checks as scripts/pptx_worked_example.py).

    .venv313/bin/python scripts/worked_example_cartoon.py
"""
from __future__ import annotations

import base64
import io
import json
import math
import random
import sqlite3
from collections import defaultdict
from math import comb
from pathlib import Path

import cairosvg
from PIL import ImageFont

REPO = Path(__file__).resolve().parents[1]
FIG = REPO / "docs" / "draft" / "Figures"
OUTD = FIG / "candidates"
EMOJI = FIG / "emoji"
FONTDIR = Path.home() / ".local" / "share" / "fonts"
W = 240.0

# ------------------------------------------------------------------ data (real, asserted)
HID = "P-V1-0087-original-claim"
CLAIM = "After Moderna, Pain typically occurs before Asthenia."
ROWS = [(9306105, True, "Pain first"), (722607, True, "Asthenia first"), (1658567, False, "same stage"), (1171286, False, "no Asthenia")]


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
    g, b, a = arm("test_gold_sets"), arm("test_qwen38_27b_cellB"), arm("test_qwen38_27b_dprime_verify2")
    assert g == (set(pb + ap), set(pb), "supported") and b == (set(pb), set(pb), "supported") and a == g
    checks = {"Pain first": pb, "Asthenia first": ap, "same stage": co}
    for r, _, why in ROWS:
        assert r in checks[why] if why in checks else ("Pain" in fm[r] and "Asthenia" not in fm[r] and vac[r] == "Moderna")
    p = lambda k, n: sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n
    return dict(fm=fm, mod=len(mod), both=len(both), pb=len(pb), ap=len(ap), co=len(co), p_gold=p(18, 22), p_sqlc=p(18, 18))


D = load()


def stages(rid):
    t = D["fm"][rid]
    out = []
    for lv in sorted(set(t.values()))[:3]:
        evs = [e for e, v in t.items() if v == lv]
        out.append(([e for e in ("Pain", "Asthenia") if e in evs], len([e for e in evs if e not in ("Pain", "Asthenia")])))
    return out


# ------------------------------------------------------------------ SVG canvas
FONTFILES = {("Patrick Hand", 400): "PatrickHand-Regular.ttf", ("Patrick Hand", 700): "PatrickHand-Regular.ttf",
             ("Kalam", 400): "Kalam-Regular.ttf", ("Kalam", 700): "Kalam-Bold.ttf",
             ("Comic Neue", 400): "ComicNeue-Regular.ttf", ("Comic Neue", 700): "ComicNeue-Bold.ttf",
             ("Bangers", 400): "Bangers-Regular.ttf", ("Fredoka", 400): "Fredoka[wdth,wght].ttf", ("Fredoka", 600): "Fredoka[wdth,wght].ttf"}
_font_cache = {}


def measure(s, family, size, weight=400):
    key = (family, weight, size)
    if key not in _font_cache:
        f = ImageFont.truetype(str(FONTDIR / FONTFILES[(family, weight)]), size=int(size * 10))
        if family == "Fredoka":
            try:
                f.set_variation_by_axes([weight, 100])   # Fredoka axes: weight, then width
            except Exception:
                pass
        _font_cache[key] = f
    return _font_cache[key].getlength(s) / 10.0


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Canvas:
    def __init__(self, bg):
        self.el, self.bg, self.defs = [], bg, []

    def add(self, s):
        self.el.append(s)

    # --- shapes
    def rect(self, x, y, w, h, r=6, fill="none", stroke="none", sw=1.0, sketch=False, seed=0, dash=None, opacity=1.0):
        if sketch:
            if fill != "none":
                self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" fill="{fill}" opacity="{opacity}"/>')
            for k in range(2):
                self.add(f'<path d="{wobbly_rect(x, y, w, h, r, seed * 7 + k)}" fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>')
            return
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d} opacity="{opacity}"/>')

    def circle(self, cx, cy, r, fill, stroke="none", sw=0.8, sketch=False, seed=0):
        if sketch:
            self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"/>')
            self.add(f'<path d="{wobbly_circle(cx, cy, r, seed)}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>')
        else:
            self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def path(self, d, fill="none", stroke="#000", sw=1.0, extra=""):
        self.add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round" {extra}/>')

    def arrow(self, x1, y1, x2, y2, color, sw=1.2, sketch=False, seed=0, head=4.0):
        if sketch:
            rnd = random.Random(seed)
            mx, my = (x1 + x2) / 2 + rnd.uniform(-1.2, 1.2), (y1 + y2) / 2 + rnd.uniform(-1.2, 1.2)
            self.path(f"M{x1:.1f},{y1:.1f} Q{mx:.1f},{my:.1f} {x2:.1f},{y2:.1f}", stroke=color, sw=sw)
        else:
            self.path(f"M{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f}", stroke=color, sw=sw)
        a = math.atan2(y2 - y1, x2 - x1)
        p1 = (x2 - head * math.cos(a - 0.45), y2 - head * math.sin(a - 0.45))
        p2 = (x2 - head * math.cos(a + 0.45), y2 - head * math.sin(a + 0.45))
        self.path(f"M{p1[0]:.1f},{p1[1]:.1f} L{x2:.1f},{y2:.1f} L{p2[0]:.1f},{p2[1]:.1f}", stroke=color, sw=sw)

    def text(self, x, y, s, family, size, fill, weight=400, anchor="start", italic=False, spacing=0):
        st = ' font-style="italic"' if italic else ""
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{st}{ls}>{esc(s)}</text>')

    def line(self, x, y, runs, family, size, anchor="start"):
        spans = "".join(f'<tspan fill="{fill}" font-weight="{wt}">{esc(t)}</tspan>' for t, fill, wt in runs)
        self.add(f'<text xml:space="preserve" x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" text-anchor="{anchor}">{spans}</text>')

    def runs_line(self, x, y, runs, family, size):
        """runs: [(text, fill, weight)] on one line; returns the measured end x."""
        self.line(x, y, runs, family, size)
        return x + sum(measure(t, family, size, wt) for t, _, wt in runs)

    def para(self, x, y, w, runs, family, size, lh=1.18):
        """Word-wrapped multi-run paragraph (breaks from measured widths with a safety margin, spacing left to the
        renderer); y is the first baseline; returns the last baseline."""
        words = []
        for s_, fill, wt in runs:
            toks = s_.split(" ")
            for i, tok in enumerate(toks):
                if tok:
                    words.append((tok, fill, wt, i > 0 or (words and s_.startswith(" "))))
        lines, cur, cw = [], [], 0.0
        sp = measure(" ", family, size, 400)
        for tok, fill, wt, gap in words:
            tw = measure(tok, family, size, wt) * 1.06
            if cur and gap and cw + sp + tw > w:
                lines.append(cur); cur, cw = [], 0.0
            cur.append([tok, fill, wt, gap]); cw += (sp if len(cur) > 1 else 0) + tw
        if cur:
            lines.append(cur)
        yy = y
        for ln in lines:
            runs_out = []
            for i, (tok, fill, wt, gap) in enumerate(ln):
                runs_out.append(((" " if i and gap else "") + tok, fill, wt))
            self.line(x, yy, runs_out, family, size)
            yy += size * lh
        return yy - size * lh

    def image(self, name, x, y, s):
        png = cairosvg.svg2png(url=str(EMOJI / f"{name}.svg"), output_width=256, output_height=256)
        b64 = base64.b64encode(png).decode()
        self.add(f'<image x="{x:.1f}" y="{y:.1f}" width="{s}" height="{s}" href="data:image/png;base64,{b64}"/>')

    def bubble(self, x, y, w, h, tail, fill, stroke, sw=1.0, r=7, sketch=False, seed=0):
        """Speech bubble with a tail pointing to (tx, ty) on the left."""
        tx, ty = tail
        y1, y2 = y + h * 0.35, y + h * 0.65
        d = (f"M{x + r},{y} H{x + w - r} Q{x + w},{y} {x + w},{y + r} V{y + h - r} Q{x + w},{y + h} {x + w - r},{y + h} "
             f"H{x + r} Q{x},{y + h} {x},{y + h - r} V{y2} L{tx},{ty} L{x},{y1} V{y + r} Q{x},{y} {x + r},{y} Z")
        if sketch:
            self.path(d, fill=fill, stroke="none")
            rnd = random.Random(seed)
            for k in range(2):
                jd = " ".join(f"{float(v) + rnd.uniform(-0.5, 0.5):.1f}" if _isnum(v) else v for v in d.replace(",", " , ").split())
                self.path(jd.replace(" , ", ","), stroke=stroke, sw=sw * 0.9)
        else:
            self.path(d, fill=fill, stroke=stroke, sw=sw)

    def burst(self, cx, cy, r1, r2, n, fill, stroke, sw=1.2, rot=0.0):
        pts = []
        for i in range(2 * n):
            r = r1 if i % 2 == 0 else r2
            a = rot + math.pi * i / n
            pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
        self.path("M" + " L".join(pts) + " Z", fill=fill, stroke=stroke, sw=sw)

    def save(self, name, H):
        body = "\n".join(self.el)
        defs = "\n".join(self.defs)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}pt" height="{H:.1f}pt" '
               f'viewBox="0 0 {W} {H:.1f}"><defs>{defs}</defs><rect width="100%" height="100%" fill="{self.bg}"/>\n{body}\n</svg>')
        (OUTD / f"{name}.svg").write_text(svg)
        cairosvg.svg2pdf(bytestring=svg.encode(), write_to=str(OUTD / f"{name}.pdf"))
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(OUTD / f"{name}.png"), scale=3.5)
        print("wrote", OUTD / f"{name}.pdf", f"({W:.0f} x {H:.0f} pt)")


def _isnum(v):
    try:
        float(v); return True
    except ValueError:
        return False


def wobbly_rect(x, y, w, h, r, seed):
    """Hand-drawn rounded rectangle: perimeter sampled densely, displaced by smooth low-frequency noise."""
    rnd = random.Random(seed)
    pts = []
    corners = [(x + w - r, y + r, -math.pi / 2), (x + w - r, y + h - r, 0), (x + r, y + h - r, math.pi / 2), (x + r, y + r, math.pi)]
    edges = [((x + r, y), (x + w - r, y)), ((x + w, y + r), (x + w, y + h - r)), ((x + w - r, y + h), (x + r, y + h)), ((x, y + h - r), (x, y + r))]
    for (p, q), (cx, cy, a0) in zip(edges, corners):
        L = math.hypot(q[0] - p[0], q[1] - p[1]); n = max(4, int(L / 6))
        for i in range(n):
            t = i / n
            pts.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
        for i in range(5):
            a = a0 + (math.pi / 2) * i / 5
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    ph = [rnd.uniform(0, 6.28) for _ in range(3)]
    amp = 0.55
    out = []
    N = len(pts)
    for i, (px, py) in enumerate(pts):
        t = i / N * 2 * math.pi
        dx = amp * (math.sin(3 * t + ph[0]) + 0.6 * math.sin(7 * t + ph[1]))
        dy = amp * (math.cos(4 * t + ph[2]) + 0.6 * math.sin(5 * t + ph[0]))
        out.append((px + dx, py + dy))
    out.append((out[0][0] + rnd.uniform(0.6, 1.6), out[0][1] + rnd.uniform(-0.5, 0.5)))   # overshoot at the join
    return "M" + " L".join(f"{a:.2f},{b:.2f}" for a, b in out)


def wobbly_circle(cx, cy, r, seed):
    rnd = random.Random(seed); ph = rnd.uniform(0, 6.28)
    pts = [(cx + (r + 0.35 * math.sin(3 * t + ph)) * math.cos(t), cy + (r + 0.35 * math.sin(3 * t + ph)) * math.sin(t))
           for t in [i * 2 * math.pi / 28 for i in range(30)]]
    return "M" + " L".join(f"{a:.2f},{b:.2f}" for a, b in pts)


# ------------------------------------------------------------------ styles
STYLES = {
    "sketch": dict(bg="#FFFCF3", ink="#34302A", title=("Kalam", 700), body=("Patrick Hand", 400), bold=400, size=9.2, tsize=10.5,
                   claim="#FFEFA8", pa="#DCEBF6", pb="#FBDCCB", pc="#D9EFD7", pill="#FFFFFF", P="#C2552D", A="#3F6E86",
                   ok="#3E8E4F", no="#C0392B", dot="#9C968C", sw=1.05, sketch=True, shadow=False),
    "flat": dict(bg="#FFFFFF", ink="#1F2A44", title=("Fredoka", 600), body=("Fredoka", 400), bold=600, size=8.6, tsize=10.5,
                 claim="#FFE07A", pa="#CDE5FF", pb="#FFCFBE", pc="#C6EFCF", pill="#FFFFFF", P="#E2572B", A="#2F6FB2",
                 ok="#2E9B4F", no="#D93A2B", dot="#A7AFBF", sw=1.6, sketch=False, shadow=True),
    "comic": dict(bg="#FFFFFF", ink="#111111", title=("Bangers", 400), body=("Comic Neue", 400), bold=700, size=8.6, tsize=11.5,
                  claim="#FFE066", pa="#E8F4FF", pb="#FFE9DF", pc="#E7F8E7", pill="#FFFFFF", P="#E0432B", A="#2563B0",
                  ok="#1E9E4A", no="#E0302B", dot="#8D8D8D", sw=2.0, sketch=False, shadow=False),
}


def panel(cv, S, x, y, w, h, fill, seed):
    if S["shadow"]:
        cv.rect(x + 2.4, y + 2.4, w, h, r=9, fill=S["ink"])
    if S is STYLES["comic"]:
        cv.rect(x, y, w, h, r=0, fill=fill, stroke=S["ink"], sw=S["sw"])
        dots = f"dots{seed}"
        cv.defs.append(f'<pattern id="{dots}" width="5" height="5" patternUnits="userSpaceOnUse"><circle cx="1.2" cy="1.2" r="0.55" fill="#000" opacity="0.08"/></pattern>')
        cv.rect(x, y, w, h, r=0, fill=f"url(#{dots})")
    else:
        cv.rect(x, y, w, h, r=9, fill=fill, stroke=S["ink"], sw=S["sw"], sketch=S["sketch"], seed=seed)


def heading(cv, S, x, y, label, color, w=None):
    fam, wt = S["title"]
    if S is STYLES["comic"]:
        tw = measure(label.upper(), fam, S["tsize"], wt) * 1.08 + 0.4 * len(label) + 12
        cv.rect(x - 1, y - S["tsize"] - 3.5, tw, S["tsize"] + 7, r=0, fill="#FFE066", stroke=S["ink"], sw=1.4)
        cv.text(x + 4, y, label.upper(), fam, S["tsize"], S["ink"], wt, spacing=0.4)
    else:
        cv.text(x, y, label, fam, S["tsize"], color, wt)


def chip(cv, S, x, y, s, fill, color, wt=None, size=None, pad=4.0, h=13.0):
    size = size or S["size"]; wt = wt or S["bold"]
    fam = S["body"][0]
    w = measure(s, fam, size, wt) * (1.07 if wt >= 600 else 1.03) + 2 * pad
    if S["shadow"]:
        cv.rect(x + 1.2, y + 1.2, w, h, r=6, fill=S["ink"])
    cv.rect(x, y, w, h, r=6, fill=fill, stroke=S["ink"], sw=S["sw"] * 0.7, sketch=S["sketch"], seed=int(x * 7 + y))
    cv.text(x + pad, y + h / 2 + size * 0.36, s, fam, size, color, wt)
    return x + w


def draw(style):
    S = STYLES[style]; cv = Canvas(S["bg"]); ink = S["ink"]; fam = S["body"][0]; sz = S["size"]; bw = S["bold"]
    M = 6.0; PW = W - 2 * M

    # ---------------- claim banner
    y = M
    bh = 46
    panel(cv, S, M, y, PW, bh, S["claim"], 1)
    cv.image("syringe", M + 6, y + 8, 30)
    cv.para(M + 42, y + 15, PW - 48, [(CLAIM, ink, bw)], fam, sz + 1.0, lh=1.12)
    cv.runs_line(M + 42, y + 39.5, [("gold: ", ink, 400), ("supported", S["ok"], bw),
                                   (f",  k = {D['pb']} of n = {D['pb'] + D['ap']},  p = {D['p_gold']:.3f}", ink, 400)], fam, sz - 0.6)

    # ---------------- (a) which reports count
    y += bh + 7
    ah = 158
    panel(cv, S, M, y, PW, ah, S["pa"], 2)
    heading(cv, S, M + 8, y + 15, "1  Which reports count?", S["A"])
    cv.image("magnifying_glass_tilted_left", M + PW - 30, y + 3, 24)
    ry = y + 24
    for i, (rid, counted, why) in enumerate(ROWS):
        rowh = 22
        cv.image("check_mark_button" if counted else "cross_mark", M + 7, ry + 4, 13)
        cv.text(M + 23, ry + 9.5, "counted" if counted else "excluded", fam, sz - 0.6, S["ok"] if counted else S["no"], bw)
        cv.text(M + 23, ry + 19, why, fam, sz - 0.9, ink, 400)
        px = M + 84
        st = stages(rid)
        for j, (keys, nother) in enumerate(st):
            pw = 36
            if S["shadow"]:
                cv.rect(px + 1, ry + 3 + 1, pw, 16, r=8, fill=ink)
            cv.rect(px, ry + 3, pw, 16, r=8, fill=S["pill"], stroke=ink, sw=S["sw"] * 0.7, sketch=S["sketch"], seed=i * 10 + j)
            cx = px + 7
            for k in keys:
                col = S["P"] if k == "Pain" else S["A"]
                cv.circle(cx, ry + 11, 5.6, col, stroke=ink, sw=0.7, sketch=S["sketch"], seed=i * 31 + j)
                cv.text(cx, ry + 13.8, k[0], "Fredoka" if style == "flat" else fam, 7.6, "#FFFFFF", 700 if style != "sketch" else 400, anchor="middle")
                cx += 12.5
            for d in range(min(nother, 3 - len(keys) if len(keys) < 3 else 0) if nother else 0):
                cv.circle(cx - 2, ry + 11, 2.0, S["dot"])
                cx += 6
            if j < len(st) - 1:
                cv.arrow(px + pw + 1.5, ry + 11, px + pw + 8.5, ry + 11, ink, sw=1.0, sketch=S["sketch"], seed=i + j, head=3)
            px += pw + 10
        ry += rowh + 2
    # legend line
    lx = M + 9; ly = ry + 8
    cv.circle(lx + 3, ly - 2.8, 4.6, S["P"], stroke=ink, sw=0.6); cv.text(lx + 3, ly - 0.4, "P", fam, 6.6, "#FFFFFF", 700, anchor="middle")
    lx = cv.runs_line(lx + 10, ly, [("Pain  ", ink, 400)], fam, sz - 0.8)
    cv.circle(lx + 3, ly - 2.8, 4.6, S["A"], stroke=ink, sw=0.6); cv.text(lx + 3, ly - 0.4, "A", fam, 6.6, "#FFFFFF", 700, anchor="middle")
    lx = cv.runs_line(lx + 10, ly, [("Asthenia  ", ink, 400)], fam, sz - 0.8)
    cv.circle(lx + 2, ly - 2.8, 2.0, S["dot"])
    cv.runs_line(lx + 7, ly, [("other event;  one box = one stage", ink, 400)], fam, sz - 0.8)
    # funnel
    fy = ly + 8
    x2 = chip(cv, S, M + 8, fy, f"{D['mod']} Moderna", "#FFFFFF", ink)
    cv.arrow(x2 + 2, fy + 6.5, x2 + 9, fy + 6.5, ink, sw=1.0, head=3)
    x3 = chip(cv, S, x2 + 11, fy, f"{D['both']} with both", "#FFFFFF", ink)
    cv.arrow(x3 + 2, fy + 6.5, x3 + 9, fy + 6.5, ink, sw=1.0, head=3)
    chip(cv, S, x3 + 11, fy, f"n = {D['pb'] + D['ap']}, k = {D['pb']}", "#FFF6C9" if style != "comic" else "#FFE066", ink)

    # ---------------- (b) EHRSQL-C
    y += ah + 7
    bhh = 97
    panel(cv, S, M, y, PW, bhh, S["pb"], 3)
    heading(cv, S, M + 8, y + 15, "2  EHRSQL-C: one query", S["P"])
    cv.image("robot", M + 7, y + 22, 30)
    cv.bubble(M + 44, y + 21, PW - 52, 25, (M + 37, y + 34), "#FFFFFF", ink, sw=S["sw"] * 0.8, sketch=S["sketch"], seed=5)
    cv.para(M + 52, y + 31, PW - 66, [("“I count a report only if", ink, 400), (" Pain comes first", S["P"], bw), (".”", ink, 400)], fam, sz)
    ry = y + 52
    x2 = chip(cv, S, M + 8, ry, f"n = {D['pb']}, k = {D['pb']}", "#FFFFFF", S["no"])
    cv.arrow(x2 + 2, ry + 6.5, x2 + 9, ry + 6.5, ink, sw=1.0, head=3)
    x3 = chip(cv, S, x2 + 11, ry, "p < 0.0001", "#FFFFFF", ink)
    cv.arrow(x3 + 2, ry + 6.5, x3 + 9, ry + 6.5, ink, sw=1.0, head=3)
    chip(cv, S, x3 + 11, ry, "supported", "#FFFFFF", ink)
    if style == "comic":
        cv.burst(M + PW - 21, y + 58.5, 15, 9.5, 11, "#FFE066", ink, sw=1.3, rot=0.2)
        cv.text(M + PW - 21, y + 61.5, "n = k!", "Bangers", 8.4, S["no"], 400, anchor="middle")
    else:
        cv.image("cross_mark", M + PW - 26, y + 50, 18)
    cv.image("warning", M + 7, y + 69, 12)
    cv.para(M + 22, y + 77.5, PW - 30, [("Right verdict, wrong evidence:", S["no"], bw),
                                       (f" the {D['ap']} Asthenia-first reports vanish, so n = k.", ink, 400)], fam, sz - 0.4)

    # ---------------- (c) ART
    y += bhh + 7
    chh = 100
    panel(cv, S, M, y, PW, chh, S["pc"], 4)
    heading(cv, S, M + 8, y + 15, "3  ART: articulate, retrieve, test", S["ok"])
    cv.image("robot", M + 7, y + 22, 30)
    cv.bubble(M + 44, y + 21, PW - 52, 25, (M + 37, y + 34), "#FFFFFF", ink, sw=S["sw"] * 0.8, sketch=S["sketch"], seed=6)
    cv.para(M + 52, y + 31, PW - 66, [("“Count reports with both at", ink, 400), (" different stages", S["ok"], bw),
                                     ("; test against 0.5.”", ink, 400)], fam, sz)
    ry = y + 52
    x2 = chip(cv, S, M + 8, ry, f"n = {D['pb'] + D['ap']}, k = {D['pb']}", "#FFFFFF", S["ok"])
    cv.arrow(x2 + 2, ry + 6.5, x2 + 9, ry + 6.5, ink, sw=1.0, head=3)
    x3 = chip(cv, S, x2 + 11, ry, f"p = {D['p_gold']:.3f}", "#FFFFFF", ink)
    cv.arrow(x3 + 2, ry + 6.5, x3 + 9, ry + 6.5, ink, sw=1.0, head=3)
    chip(cv, S, x3 + 11, ry, "supported", "#FFFFFF", ink)
    cv.image("check_mark_button", M + PW - 26, y + 50, 18)
    cv.image("party_popper", M + 7, y + 69, 12)
    cv.para(M + 22, y + 77.5, PW - 30, [("Right verdict on the gold evidence:", S["ok"], bw),
                                       (" all 22 eligible reports, nothing else.", ink, 400)], fam, sz - 0.4)
    H = y + chh + M
    cv.save(f"worked_example_{style}", H)


if __name__ == "__main__":
    for st in ("sketch", "flat", "comic"):
        draw(st)
