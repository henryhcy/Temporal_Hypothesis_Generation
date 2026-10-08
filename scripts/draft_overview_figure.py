"""The draft's overview figure (docs/draft Figure 1): task, dataset, the instrumented
reference framework and the baseline families on the stages they replace.

    python scripts/draft_overview_figure.py docs/draft/Figures

Every number in the boxes is a v1.2 release statistic (decisions.md 2026-10-08).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

W, H = 100, 58
fig = plt.figure(figsize=(7.0, 4.06))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

C_TASK, C_DATA, C_STAGE, C_GOLD, C_OURS, C_BASE, C_EXT = "#f3f0e8", "#eef3ea", "#e4ecf7", "#fbf1d9", "#d9e8f5", "#efefef", "#f0e4ec"
EDGE = "#555555"

def box(x, y, w, h, fc, title=None, body=None, tsize=7.2, bsize=5.6, pad=0.9, ec=EDGE, lw=0.8, title_dx=0.0, round_=True):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={0.9 if round_ else 0}",
                       fc=fc, ec=ec, lw=lw); ax.add_patch(p)
    ty = y + h - pad
    if title:
        ax.text(x + pad + title_dx, ty, title, fontsize=tsize, fontweight="bold", va="top", ha="left")
        ty -= tsize * 0.34
    if body:
        ax.text(x + pad, ty, body, fontsize=bsize, va="top", ha="left", linespacing=1.25)

def arrow(x0, y0, x1, y1, style="-|>", lw=0.9, color="#333333", conn="arc3,rad=0", ls="-"):
    a = FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=7, lw=lw,
                        color=color, connectionstyle=conn, linestyle=ls); ax.add_patch(a)

# ---------------- left column: task and dataset ----------------
box(0.8, 35.0, 18.6, 22.0, C_TASK, "Task",
    "Temporal-statistical claim\nverification over annotated\ntimelines.\n"
    "Input: a claim (4 registers x\n2 formats) + the eval DB:\nreport_id (pseudonymised),\nvaccine, first-mention levels;\nnever narrative text.\n"
    "Output: supported / refuted /\ninsufficient (not_locatable /\nsparse / underpowered)\n+ n, k, p.")
box(0.8, 1.0, 18.6, 32.5, C_DATA, "Dataset (v1.2)",
    "MedTempo: 3,166 expert-\nannotated reports (Pfizer,\nModerna, Janssen).\n"
    "29 groups, 7 families: precedes,\nco-occurs, sequence, first/last,\nposition, proximity, threshold.\n"
    "3 tiers: report, cohort,\ntwo-cohort.\n"
    "Nulls: symmetric 0.5, text-\nstated bar, data-derived,\ntwo-arm equality, none.\n"
    "8,763 instances (equal thirds\nper group, mirror pairs) x 8\nrenderings = 70,104 records.\n"
    "Gold at every stage; exact\ntests only; 6 validity screens;\nB0 oracle = 1.000.")

# ---------------- band A: the reference framework ----------------
XS = [(21.5, 22.0), (45.5, 22.0), (69.5, 17.0)]   # (x, w) of S1, S2, S3
YA, HA = 38.5, 12.0
box(XS[0][0], YA, XS[0][1], HA, C_STAGE, "S1  Plan",
    "claim -> conditional plan: events,\nquantity, denominator, null kind,\np0, tail, test family / rule.\n"
    "Toolbox frame: conventions stated,\nmapping withheld (catalogue frame =\nlookup upper bound). Zero-shot headline.")
box(XS[1][0], YA, XS[1][1], HA, C_STAGE, "S2  Retrieve",
    "plan -> SQL over first_mention /\nfirst_mention_rank -> per-report\nrole rows: denominator, numerator,\nexcluded (co-exist, ties, gaps).\n"
    "Data-derived null = chance sum\nover the retrieved denominator.")
box(XS[2][0], YA, XS[2][1], HA, C_STAGE, "S3  Test",
    "exact test vs the null\n(binomial / Fisher / named\nvs runner-up), min-n floor,\n"
    "alpha 0.05 one-sided ->\nthree-decision verdict\nwith subtype.")
box(88.5, YA + 2.0, 10.7, 8.0, "#ffffff", "Verdict", "supported\nrefuted\ninsufficient\n+ n, k, p", bsize=5.6)
# stage arrows
arrow(19.4, 46.0, XS[0][0], 46.0)
arrow(XS[0][0] + XS[0][1], 42.5, XS[1][0], 42.5)
arrow(XS[1][0] + XS[1][1], 42.5, XS[2][0], 42.5)
arrow(XS[2][0] + XS[2][1], 42.5, 88.5, 42.5)
# verify-and-repair loops
for (x, w), lab in zip(XS, ["verify & repair (1 round):\nconventions consistency",
                            "verify & repair (2 rounds):\nexecutor error, plan consistency",
                            "rule validity check"]):
    arrow(x + w * 0.72, YA + HA, x + w * 0.28, YA + HA, conn="arc3,rad=0.55", lw=0.8, color="#8a5a00")
    ax.text(x + w / 2, YA + HA + 3.9, lab, fontsize=4.9, ha="center", va="bottom", color="#8a5a00", linespacing=1.15)
ax.text(21.5, 58.0, "Reference framework (instrumented): every stage has a contract, a gold answer and a verifier",
        fontsize=6.6, fontweight="bold", va="top", ha="left")

# ---------------- band B: stage-level ground truth and metrics ----------------
YB, HB = 27.0, 9.5
box(XS[0][0], YB, XS[0][1], HB, C_GOLD, "Gold plan -> metrics",
    "plan EM (one field per miss),\nclaim EM, rule validity,\nS1-only verdict")
box(XS[1][0], YB, XS[1][1], HB, C_GOLD, "Gold evidence -> metrics",
    "denominator set F1, co-exist leak,\nnot-locatable FPR, n/k agreement,\nS2 failure attribution")
box(XS[2][0], YB, 99.2 - XS[2][0], HB, C_GOLD, "Gold p, verdict -> metrics",
    "verdict accuracy (cohort tiers), p-agreement,\nfaithfulness P(stages right | verdict right),\nabstention: false-decisiveness, over-abstention,\nsubtype accuracy")
for x, w in XS:
    arrow(x + w / 2, YA, x + w / 2, YB + HB, style="-", lw=0.6, color="#999999", ls=(0, (2, 2)))
arrow(19.4, 20.0, 21.0, 20.0, style="-", lw=0.0, color="#ffffff")
ax.text(20.3, YB + HB / 2, "stage-level gold", fontsize=5.2, rotation=90, ha="center", va="center", color="#7a5a00")

# ---------------- band C: baseline families as stage spans ----------------
ax.text(21.5, 25.3, "Baseline families, placed on the stages they replace (A-E: the architecture-vs-information grid)",
        fontsize=6.6, fontweight="bold", va="top", ha="left")
s1, s2, s3 = XS[0][0], XS[1][0], XS[2][0]
e1, e2, e3 = s1 + XS[0][1], s2 + XS[1][1], s3 + XS[2][1]
rows = [
    (C_OURS, [(s1, e3)], "Ours (reference decomposition):  C catalogue rule   D plan + conventions   E + plan-consistency re-ask   + verify & repair rounds"),
    (C_BASE, [(s1, e2)], "End-to-end sentence -> SQL (one query; S3 by the harness):  A schema only   B + conventions stated"),
    (C_BASE, [(s1, e3)], "Agentic (EHRAgent): one tool loop over all three stages; variant B hands retrieval to the oracle"),
    (C_EXT,  [(s2, e2), (s3, e3)], "External protocols at their native stage:        EHRSQL at S2 (flat answer SQL, abstention)        StatQA at S3 (test selection)"),
    (C_BASE, [(s3, e3)], "Counts-given judgment (counts-llm): gold n, k handed over; the model names test and verdict"),
]
y = 21.6; rh = 3.7
for fc, spans, lab in rows:
    for (xa, xb) in spans:
        box(xa, y - rh, xb - xa, rh - 0.5, fc, round_=False, lw=0.6)
    ax.text(s1 + 0.7, y - rh / 2 - 0.25, lab, fontsize=5.3, va="center", ha="left")
    y -= rh
# column guides
for x, w, lab in [(s1, XS[0][1], "S1"), (s2, XS[1][1], "S2"), (s3, XS[2][1], "S3")]:
    ax.text(x + w / 2, 1.0, lab, fontsize=6.0, ha="center", va="bottom", color="#555555", fontweight="bold")
import sys
out = sys.argv[1] if len(sys.argv) > 1 else "."
fig.savefig(f"{out}/overview.pdf"); fig.savefig(f"{out}/overview.png", dpi=220)
print("ok")
