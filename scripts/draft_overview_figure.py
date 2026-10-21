"""Overview figure (docs/draft Figure 1), framework-detailed version (2026-10-13):
the worked example flows through the three stage contracts; the harness's
resolution of the plan (D'), the row contract, the deterministic test, the
verify-and-repair checks per stage, the stage-level gold and metrics, and the
baseline families on the stages they replace.

    python scripts/draft_overview_figure.py docs/draft/Figures
"""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

W, H = 100, 73
fig = plt.figure(figsize=(7.0, 5.11))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
C_TASK, C_STAGE, C_HARN, C_GOLD, C_OURS, C_BASE, C_EXT, C_VER = "#f3f0e8", "#e4ecf7", "#e9f2e4", "#fbf1d9", "#d9e8f5", "#efefef", "#f0e4ec", "#fff4e0"
EDGE = "#555555"; BROWN = "#8a5a00"; MONO = "DejaVu Sans Mono"

def box(x, y, w, h, fc, title=None, body=None, tsize=6.8, bsize=5.1, pad=0.8, lw=0.8, mono=False, round_=True, tcolor="black"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={0.8 if round_ else 0}", fc=fc, ec=EDGE, lw=lw))
    ty = y + h - pad
    if title:
        ax.text(x + pad, ty, title, fontsize=tsize, fontweight="bold", va="top", ha="left", color=tcolor); ty -= tsize * 0.33
    if body:
        ax.text(x + pad, ty, body, fontsize=bsize, va="top", ha="left", linespacing=1.22, family=(MONO if mono else None))

def arrow(x0, y0, x1, y1, style="-|>", lw=0.9, color="#333333", conn="arc3,rad=0", ls="-"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=7, lw=lw, color=color, connectionstyle=conn, linestyle=ls))

# ---- left: the record and the data ----------------------------------------
box(0.8, 40.0, 17.6, 28.5, C_TASK, "Input record",
    "claim (4 registers):\n\"After Pfizer, Headache\n tends to precede Fatigue.\"\n"
    "cohort: Pfizer   tier: cohort\n\nAnnotations (eval DB; no text):\nreports(report_id, vaccine)\n"
    "first_mention(report_id,\n  term, level)  = each term's\n  FIRST-mention stage\nfirst_mention_rank(.., rank,\n  n_ranks)\n"
    "report ids are pseudonyms\n(MT-0482913)")
box(0.8, 26.0, 17.6, 13.0, C_TASK, "Output: verdict",
    "supported / refuted /\ninsufficient {not_locatable,\n sparse, underpowered}\n"
    "refuted = significant in the\nOPPOSITE direction, never\n\"failed to prove\"; alpha 0.05\none-sided; min-n floor")

# ---- top band: the three stages -------------------------------------------
XS = [(21.0, 25.0), (48.5, 25.0), (76.0, 23.2)]; YA, HA = 40.5, 20.5
box(XS[0][0], YA, XS[0][1], HA, C_STAGE, "S1  Articulate  (LLM, toolbox frame)",
    "told: codebook by situation,\nnull sources, test definitions,\ndataset card -- the claim-type\nmapping is WITHHELD; zero-shot.\n"
    "composes:", bsize=5.1)
ax.text(XS[0][0] + 1.2, YA + 7.6, "events      [Headache, Fatigue]\nquantity    order_of_pair\ndenominator ordered_pair\narms 1  null symmetric p0=.5\ntail greater  test binomial",
        fontsize=4.7, va="top", ha="left", family=MONO, linespacing=1.25)
box(XS[1][0], YA, XS[1][1], HA, C_STAGE, "S2  Retrieve  (LLM writes SQL)",
    "told: schema (column listing),\nthe plan's primitive RESOLVED\nto its rule (the contract):\n\"both present at DISTINCT\n stages; same stage = excluded\"\n"
    "returns one row per report:", bsize=5.1)
ax.text(XS[1][0] + 1.2, YA + 5.6, "report_id | in_den | in_num | excl\n 0482913  |   1    |   1    |  0\n 1730052  |   0    |   0    |  1",
        fontsize=4.6, va="top", ha="left", family=MONO, linespacing=1.25)
box(XS[2][0], YA, XS[2][1], HA, C_STAGE, "S3  Test  (a function)",
    "exact test on the counts:\nbinomial(k=83, n=118, p0=.5)\nFisher for two arms; named-\nvs-runner-up for argmax;\ndata-derived p0 from the\nretrieved denominator\n"
    "floor n>=10  ->  verdict,\nboth tails, p, CI, effect",
    bsize=5.1)
arrow(18.4, 54.0, XS[0][0], 50.5)
arrow(XS[0][0] + XS[0][1], 50.5, XS[1][0], 50.5); arrow(XS[1][0] + XS[1][1], 50.5, XS[2][0], 50.5)
ax.text((XS[0][0] + XS[0][1] + XS[1][0]) / 2, 51.1, "plan", fontsize=4.0, ha="center", va="bottom", color="#333333")
ax.text((XS[1][0] + XS[1][1] + XS[2][0]) / 2, 51.1, "n,k,ids", fontsize=3.9, ha="center", va="bottom", color="#333333")
# harness resolution arrow (the contract)
ax.text(XS[1][0] + XS[1][1] / 2, YA + HA + 0.7, "harness resolves the plan -> its claim type -> that type's rule (the contract, D')",
        fontsize=4.4, ha="center", va="bottom", color="#2f5f2f", style="italic")

# ---- verify-and-repair loops --------------------------------------------------
for (x, w), lab in zip(XS, ["verify & repair, 1 round:\nquantity vs denominator; null kind vs\nsituation; stated bar; test family",
                            "verify & repair, 2 rounds: rejected SQL;\nn = k; empty arm; rows violating the\nprimitive (co-exist, tie, non-adjacent)",
                            "rule validity:\nfamily x rule, p0 in (0,1)"]):
    arrow(x + w * 0.75, YA + HA + 3.0, x + w * 0.25, YA + HA + 3.0, conn="arc3,rad=0.5", lw=0.8, color=BROWN)
    ax.text(x + w / 2, YA + HA + 5.7, lab, fontsize=4.5, ha="center", va="bottom", color=BROWN, linespacing=1.15)
ax.text(21.0, 72.6, "ART reference pipeline (articulate, retrieve, test): each stage has a contract, a verifier (contract, codebook and data only) and a gold answer",
        fontsize=5.9, fontweight="bold", va="top", ha="left")

# ---- gold and metrics band -------------------------------------------------
YB, HB = 29.5, 9.3
box(XS[0][0], YB, XS[0][1], HB, C_GOLD, "Gold plan -> metrics", "plan EM (one field per miss), claim EM,\nrule validity, S1-only verdict", bsize=4.9)
box(XS[1][0], YB, XS[1][1], HB, C_GOLD, "Gold evidence sets -> metrics", "denominator F1, co-exist / tie leak,\nnot-locatable FPR, failure attribution\nby the rule violated", bsize=4.9)
box(XS[2][0], YB, XS[2][1], HB, C_GOLD, "Gold p, verdict -> metrics", "verdict acc. (cohort / report tier),\np-agreement, faithfulness\nP(evidence exact | verdict right),\nfalse-decisiveness, over-abstention", bsize=4.9)
for x, w in XS:
    arrow(x + w / 2, YA, x + w / 2, YB + HB, style="-", lw=0.6, color="#999999", ls=(0, (2, 2)))
ax.text(19.9, YB + HB / 2, "stage-level gold", fontsize=5.0, rotation=90, ha="center", va="center", color="#7a5a00")

# ---- baselines on the stages they replace ------------------------------------
ax.text(21.0, 27.7, "Baseline families, on the stages they replace (A-E: the architecture-vs-information grid)", fontsize=6.0, fontweight="bold", va="top", ha="left")
s1, s2, s3 = XS[0][0], XS[1][0], XS[2][0]; e1, e2, e3 = s1 + XS[0][1], s2 + XS[1][1], s3 + XS[2][1]
rows = [
    (C_OURS, [(s1, e3)], "D'  ours: plan -> resolved rule -> SQL -> exact test; +2 repair rounds with the plan's checks"),
    (C_BASE, [(s1, e3)], "D   ablation: the plan handed to S2 as prose + the whole codebook"),
    (C_BASE, [(s1, e2)], "A / B  Straight-to-SQL, one prompt from claim to query (schema only / + codebook); +2 plan-free repair rounds; S3 by the harness"),
    (C_EXT,  [(s1, e3)], "agentic: EHRAgent (code agent, own retries), VERITAS (plan / statistics / interpretation agents); our test functions available"),
    (C_BASE, [("gold", s1, e2), (s3, e3)], "model as statistician: S1 and S2 at gold, n and k handed over; the model names the test and makes the judgment call"),
    (C_HARN, [(s1, e1), (s2, e2)], "ceilings: planner alone (gold S2/S3)                       SQL stage alone (gold plan)"),
]
y = 24.4; rh = 3.55
for fc, spans, lab in rows:
    for span in spans:
        if len(span) == 3:  # stages handed over at gold: a faint box
            _, xa, xb = span; box(xa, y - rh, xb - xa, rh - 0.5, "#F7F6F2", round_=False, lw=0.4)
        else:
            xa, xb = span; box(xa, y - rh, xb - xa, rh - 0.5, fc, round_=False, lw=0.6)
    ax.text(s1 + 0.7, y - rh / 2 - 0.25, lab, fontsize=5.0, va="center", ha="left")
    y -= rh
for x, w, lab in [(s1, XS[0][1], "S1 articulate"), (s2, XS[1][1], "S2 retrieve"), (s3, XS[2][1], "S3 test")]:
    ax.text(x + w / 2, 0.8, lab, fontsize=5.6, ha="center", va="bottom", color="#555555", fontweight="bold")

out = sys.argv[1] if len(sys.argv) > 1 else "."
fig.savefig(f"{out}/overview.pdf"); fig.savefig(f"{out}/overview.png", dpi=220)
print("ok")
