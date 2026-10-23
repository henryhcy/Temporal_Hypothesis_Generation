"""Figure 2, the worked example (2026-10-22, user revision of the comic-strip candidate): comic panels kept, but in
the paper's slate_rust palette with lowered contrast, Figure 1's line icons (Lucide, ISC) instead of emoji, a
count bar that shows how 30 -> n = 22 -> k = 18, and our three stages in the last panel. Printed size, one column.

Reuses the canvas and the verified data of scripts/worked_example_cartoon.py (every number asserted there).

    .venv313/bin/python scripts/worked_example_figure.py
"""
from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

import cairosvg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from worked_example_cartoon import CLAIM, D, ROWS, Canvas, measure, stages  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
FIG = REPO / "docs" / "draft" / "Figures"
ICONS = FIG / "icons"
W = 240.0

# paper palette (scripts/paper_figures.py): slate_rust, softened for panel fills
INK, RUST, SLATE, SAGE, GOLD, WHEAT = "#2B3A42", "#A0522D", "#4F6B75", "#5E8263", "#A8812E", "#D4B483"
FILL = dict(banner="#F6F0E2", p1="#EEF2F4", p2="#F6ECE6", p3="#EDF2EC", cap="#EBDDBE", pill="#FFFFFF", chip="#FFFFFF")
GREY = "#A9A39A"
TITLE, BODY = ("Bangers", 400), "Comic Neue"
SZ, TS = 8.2, 9.6          # body and caption sizes, in printed points
BW = 1.1                   # panel border width


def icon(cv, name, x, y, s, color):
    svg = ICONS / f"{name}.svg"
    if not svg.exists():
        subprocess.run(["curl", "-sL", "-m", "30", "-o", str(svg), f"https://unpkg.com/lucide-static@latest/icons/{name}.svg"], check=True)
    src = svg.read_text().replace('stroke="currentColor"', f'stroke="{color}"').replace('stroke-width="2"', 'stroke-width="2.1"')
    png = cairosvg.svg2png(bytestring=src.encode(), output_width=256, output_height=256)
    if hasattr(cv, "picture"):          # editable PowerPoint canvas (scripts/pptx_worked_example_comic.py)
        cv.picture(png, x, y, s); return
    cv.add(f'<image x="{x:.1f}" y="{y:.1f}" width="{s}" height="{s}" href="data:image/png;base64,{base64.b64encode(png).decode()}"/>')


def panel(cv, x, y, w, h, fill, seed):
    cv.rect(x, y, w, h, r=0, fill=fill, stroke=INK, sw=BW)
    pid = f"dots{seed}"
    cv.defs.append(f'<pattern id="{pid}" width="5" height="5" patternUnits="userSpaceOnUse"><circle cx="1.2" cy="1.2" r="0.5" fill="{INK}" opacity="0.045"/></pattern>')
    cv.rect(x, y, w, h, r=0, fill=f"url(#{pid})")


def caption(cv, x, y, label):
    fam, wt = TITLE
    tw = measure(label.upper(), fam, TS, wt) * 1.08 + 0.4 * len(label) + 10
    cv.rect(x - 1, y - TS - 2.5, tw, TS + 5.5, r=0, fill=FILL["cap"], stroke=INK, sw=0.8)
    cv.text(x + 3.5, y, label.upper(), fam, TS, INK, wt, spacing=0.4)


def chip(cv, x, y, s, color=INK, wt=400, fill=None, h=12.0, size=None):
    size = size or SZ
    w = measure(s, BODY, size, wt) * (1.07 if wt >= 600 else 1.03) + 8
    cv.rect(x, y, w, h, r=6, fill=fill or FILL["chip"], stroke=INK, sw=0.75)
    cv.text(x + 4, y + h / 2 + size * 0.36, s, BODY, size, color, wt)
    return x + w


def arrow(cv, x1, y, x2, color=INK):
    cv.arrow(x1, y, x2, y, color, sw=0.9, head=2.8)


def draw(make=Canvas):
    cv = make("#FFFFFF")
    M, PW = 5.0, W - 10.0
    y = M

    # ---------------- claim
    bh = 27
    cv.rect(M, y, PW, bh, r=0, fill=FILL["banner"], stroke=INK, sw=BW)
    icon(cv, "message-square-quote", M + 6, y + 6, 18, GOLD)
    cv.para(M + 30, y + 12.5, PW - 36, [("Claim:", GOLD, 700), (" " + CLAIM, INK, 700)], BODY, SZ + 0.4, lh=1.2)

    # ---------------- 1: which reports count
    y += bh + 4
    h1 = 150
    panel(cv, M, y, PW, h1, FILL["p1"], 1)
    caption(cv, M + 6, y + 13, "1  Which reports count?")
    icon(cv, "search", M + PW - 22, y + 4, 15, SLATE)
    ry = y + 20
    for i, (rid, counted, why) in enumerate(ROWS):
        icon(cv, "circle-check" if counted else "circle-x", M + 6, ry + 3, 11, SAGE if counted else RUST)
        cv.text(M + 20, ry + 8.6, "counted" if counted else "excluded", BODY, SZ - 0.6, SAGE if counted else RUST, 700)
        cv.text(M + 20, ry + 16.0, why, BODY, SZ - 0.9, INK, 400)
        px = M + 80
        st = stages(rid)
        for j, (keys, nother) in enumerate(st):
            pw = 36
            cv.rect(px, ry + 3, pw, 14, r=7, fill=FILL["pill"], stroke=INK, sw=0.75)
            cx = px + 7
            for k in keys:
                cv.circle(cx, ry + 10, 5.0, RUST if k == "Pain" else SLATE, stroke=INK, sw=0.5)
                cv.text(cx, ry + 12.5, k[0], BODY, 6.9, "#FFFFFF", 700, anchor="middle")
                cx += 11.5
            for _ in range(min(nother, 3 - len(keys))):
                cv.circle(cx - 2, ry + 10, 1.8, GREY)
                cx += 5.5
            if j < len(st) - 1:
                arrow(cv, px + pw + 1.2, ry + 10, px + pw + 7.8)
            px += pw + 9
        ry += 17.5
    # legend
    ly = ry + 8
    cv.circle(M + 10, ly - 2.6, 4.2, RUST, stroke=INK, sw=0.5); cv.text(M + 10, ly - 0.3, "P", BODY, 6.2, "#FFFFFF", 700, anchor="middle")
    lx = cv.runs_line(M + 17, ly, [("Pain   ", INK, 400)], BODY, SZ - 0.9)
    cv.circle(lx + 3, ly - 2.6, 4.2, SLATE, stroke=INK, sw=0.5); cv.text(lx + 3, ly - 0.3, "A", BODY, 6.2, "#FFFFFF", 700, anchor="middle")
    lx = cv.runs_line(lx + 10, ly, [("Asthenia   ", INK, 400)], BODY, SZ - 0.9)
    cv.circle(lx + 2, ly - 2.6, 1.8, GREY)
    cv.runs_line(lx + 7, ly, [("other event;  one box = one stage", INK, 400)], BODY, SZ - 0.9)
    # count bar: the 30 Moderna reports with both events
    by = ly + 7
    n_both, n, k, co = D["both"], D["pb"] + D["ap"], D["pb"], D["co"]
    cv.line(M + 6, by + 6.5, [(f"{D['mod']} Moderna reports; ", INK, 400), (f"{n_both} mention both events:", INK, 700)], BODY, SZ - 0.4)
    bx, cw, bh2 = M + 6, (PW - 12) / n_both, 9.0
    bar_y = by + 20
    for i in range(n_both):
        col = RUST if i < k else SLATE if i < n else "#E3DED6"
        cv.rect(bx + i * cw, bar_y, cw, bh2, r=0, fill=col, stroke="#FFFFFF", sw=0.5)
    cv.rect(bx, bar_y, cw * n_both, bh2, r=0, fill="none", stroke=INK, sw=0.75)
    # braces: n over the first 22, k under the first 18, excluded over the last 8
    def brace(x1, x2, yb, up, label, color, wt=700):
        d = 2.6 if up else -2.6
        cv.path(f"M{x1 + 0.6:.1f},{yb:.1f} L{x1 + 0.6:.1f},{yb - d:.1f} L{x2 - 0.6:.1f},{yb - d:.1f} L{x2 - 0.6:.1f},{yb:.1f}", stroke=color, sw=0.8)
        cv.text((x1 + x2) / 2, yb - d - (2.2 if up else -7.6), label, BODY, SZ - 1.0, color, wt, anchor="middle")
    brace(bx, bx + cw * n, bar_y - 1.2, True, f"n = {n}: different stages", INK)
    brace(bx + cw * n, bx + cw * n_both, bar_y - 1.2, True, f"{co} same stage", "#857F75")
    brace(bx, bx + cw * k, bar_y + bh2 + 1.2, False, f"k = {k}: Pain first", RUST)
    brace(bx + cw * k, bx + cw * n, bar_y + bh2 + 1.2, False, f"{n - k}: A first", SLATE)

    # ---------------- 2: a single-query baseline
    y += h1 + 4
    h2 = 61
    panel(cv, M, y, PW, h2, FILL["p2"], 2)
    caption(cv, M + 6, y + 13, "2  A single-query baseline")
    icon(cv, "bot", M + 6, y + 19, 20, RUST)
    cv.bubble(M + 32, y + 19, PW - 38, 16, (M + 27, y + 27.5), "#FFFFFF", INK, sw=0.8)
    cv.line(M + 39, y + 29.7, [("“I count a report only if ", INK, 400), ("Pain comes first", RUST, 700), (".”", INK, 400)], BODY, SZ)
    ry = y + 38
    x2 = chip(cv, M + 6, ry, f"n = {D['pb']}, k = {D['pb']}", RUST, 700)
    arrow(cv, x2 + 1.5, ry + 6, x2 + 7.5)
    x3 = chip(cv, x2 + 9, ry, "p < 0.0001")
    arrow(cv, x3 + 1.5, ry + 6, x3 + 7.5)
    chip(cv, x3 + 9, ry, "supported")
    cv.burst(M + PW - 19, y + 44, 13.5, 8.5, 11, FILL["cap"], INK, sw=0.9, rot=0.2)
    cv.text(M + PW - 19, y + 47, "n = k!", "Bangers", 7.8, RUST, 400, anchor="middle")
    cv.line(M + 6, y + 57.5, [("The ", INK, 400), (f"{D['ap']} Asthenia-first reports", SLATE, 700), (" vanish, so n = k.", INK, 400)], BODY, SZ - 0.4)

    # ---------------- 3: our staged pipeline (S1, S2, S3)
    y += h2 + 4
    h3 = 65
    panel(cv, M, y, PW, h3, FILL["p3"], 3)
    caption(cv, M + 6, y + 13, "3  Our staged pipeline")
    icon(cv, "bot", M + PW - 23, y + 3, 16, SAGE)
    stages3 = [("S1", "Articulate", SLATE, ["both at different", "stages; null 0.5;", "exact binomial"]),
               ("S2", "Retrieve", RUST, ["SQL under that", "rule returns", f"n = {n}, k = {k}"]),
               ("S3", "Test", GOLD, ["exact binomial", f"p = {D['p_gold']:.3f}", "verdict: supported"])]
    sw_ = (PW - 12 - 2 * 8) / 3
    sx = M + 6
    for i, (tag, name, col, lines) in enumerate(stages3):
        cv.rect(sx, y + 19, sw_, 42, r=5, fill="#FFFFFF", stroke=INK, sw=0.75)
        cv.circle(sx + 9, y + 27.5, 6.2, col)
        cv.text(sx + 9, y + 30.0, tag, BODY, 6.6, "#FFFFFF", 700, anchor="middle")
        cv.text(sx + 18.5, y + 30.3, name, BODY, SZ - 0.2, col, 700)
        for j, ln in enumerate(lines):
            cv.text(sx + 5, y + 40.6 + j * 8.2, ln, BODY, SZ - 1.0, INK, 700 if (i and j == 2) else 400)
        if i < 2:
            arrow(cv, sx + sw_ + 1.2, y + 40, sx + sw_ + 6.8)
        sx += sw_ + 8
    H = y + h3 + M
    cv.save_to = None
    return cv, H


if __name__ == "__main__":
    import worked_example_cartoon as wc
    cv, H = draw()
    wc.OUTD = FIG / "candidates"
    cv.save("worked_example_comic_soft", H)
