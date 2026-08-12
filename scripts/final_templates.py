"""Final template design + whole-corpus evidence, for the advisor presentation.

This is the single, self-contained statement of the FINAL benchmark template
design after the significance redesign (see `docs/plan/decisions.md`,
2026-07-13/14/28). It encodes the locked 24-group roster and its design rules,
runs every testable group over the whole MedTempo corpus, and writes a short,
readable standalone LaTeX report:

    python scripts/final_templates.py   # -> docs/reference/Final_Template_Design.tex

Design rules encoded here (the "why" behind the roster):

1. Every cohort-level claim is a HYPOTHESIS TEST with a principled null -- a
   chance baseline (0.5, uniform, or a modal-vs-runner-up 0.5) or another group
   in the data. No claim is graded by matching the observed value (fact-check).
2. Significance-as-verdict: significant in the asserted direction -> supported,
   significant in the opposite direction -> refuted, not significant ->
   insufficient. So a template's "supported" ceiling IS its significant-core
   count.
3. Directional tests are ONE-SIDED in the observed direction.
4. No absolute-percentage (PROP) groups: an absolute rate has no principled
   null, so those were retired.
5. Two-cohort (multi) groups are DIRECTIONAL only ("higher after v1 than v2").
   The "differ" and "same" shapes were removed: NHST can reject the no-effect
   null but never accept it, so those shapes have no clean supported/refuted.
6. Report-level claims are exact single-narrative facts -> deterministic, no
   test.

Existing groups are scored with the live pipeline (whole-population enumeration).
The three NEW groups (P-V2, P-V4, C-V2), not yet wired into the pipeline, are
scored with the vetted candidate-inventory functions in
`scripts/replacement_inventory.py` (full corpus, top-K candidate enumeration);
those counts are ceilings, so their absolute size is footnoted.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path
from statistics import median

from temporal_hypo.core.answers import core_significance
from temporal_hypo.generation import cores as C
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.templates import load_groups

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from replacement_inventory import r1 as _r1, r3 as _r3, r5 as _r5  # noqa: E402

ALPHA = 0.05

# --------------------------------------------------------------------------
# The FINAL 24-group roster. `kind`: report = deterministic (no test);
# pipeline = existing testable group scored live; r1/r3/r5 = new group scored
# via the candidate inventory.
# --------------------------------------------------------------------------
ROSTER = [
    # id, family, scope, type, claim (concise), null / reference, test, kind
    # --- pairwise: precedes ---
    ("P-R1", "precedes", "report", "BOOL", "A occurred before B in this report", "-", "exact", "report"),
    ("P-R2", "precedes", "report", "CHOICE", "which came first in this report, A or B", "-", "exact", "report"),
    ("P-V1", "precedes", "vaccine", "BOOL", "A typically precedes B", "P = 0.5", "binomial (1-sided)", "pipeline"),
    ("P-V2", "precedes", "vaccine", "BOOL", "A precedes B more often than C precedes B", "P(A<B) = P(C<B)", "Fisher 2x2 (1-sided)", "r3"),
    ("P-V3", "precedes", "vaccine", "CHOICE", "which usually comes first, A or B", "P = 0.5", "binomial (1-sided)", "pipeline"),
    ("P-V4", "precedes", "vaccine", "BOOL", "A precedes B more often than C precedes D", "P(A<B) = P(C<D)", "Fisher 2x2 (1-sided)", "r1"),
    ("P-M2", "precedes", "multi", "CHOICE", "A precedes B more often after v1 than v2", "p1 = p2", "Fisher 2x2 (1-sided)", "pipeline"),
    # --- pairwise: co-occurs ---
    ("C-R1", "co-occurs", "report", "BOOL", "A and B co-occur in this report", "-", "exact", "report"),
    ("C-V1", "co-occurs", "vaccine", "BOOL", "A and B typically co-occur", "P = 0.5", "binomial (1-sided)", "pipeline"),
    ("C-V2", "co-occurs", "vaccine", "BOOL", "A and B occur together more than if independent", "independence", "Fisher 2x2 (1-sided)", "r5"),
    ("C-V3", "co-occurs", "vaccine", "BOOL", "co-occurrence is the dominant relation for A, B", "P = 0.5", "binomial (1-sided)", "pipeline"),
    ("C-M2", "co-occurs", "multi", "CHOICE", "A and B co-occur more often after v1 than v2", "p1 = p2", "Fisher 2x2 (1-sided)", "pipeline"),
    # --- sequence ---
    ("S-R1", "sequence", "report", "BOOL", "order is A -> B -> C in this report", "-", "exact", "report"),
    ("S-V1", "sequence", "vaccine", "BOOL", "A -> B -> C is the most common ordering", "modal = runner-up", "binomial modal-vs-runner-up (1-sided)", "pipeline"),
    ("S-V3", "sequence", "vaccine", "CHOICE", "the most common ordering of A, B, C", "modal = runner-up", "binomial modal-vs-runner-up (1-sided)", "pipeline"),
    # --- first / last ---
    ("F-R1", "first/last", "report", "CHOICE", "which occurs first in this report", "-", "exact", "report"),
    ("F-R2", "first/last", "report", "CHOICE", "which occurs last in this report", "-", "exact", "report"),
    ("F-R3", "first/last", "report", "BOOL", "A is the first of A, B, C in this report", "-", "exact", "report"),
    ("F-V1", "first/last", "vaccine", "CHOICE", "which is most commonly the first event", "modal = runner-up", "binomial modal-vs-runner-up (1-sided)", "pipeline"),
    ("F-V2", "first/last", "vaccine", "CHOICE", "which is most commonly the last event", "modal = runner-up", "binomial modal-vs-runner-up (1-sided)", "pipeline"),
    ("F-V3", "first/last", "vaccine", "BOOL", "A is the most common first event", "modal = runner-up", "binomial modal-vs-runner-up (1-sided)", "pipeline"),
]

# Groups retired in the redesign (shown in the report's "what changed" note).
RETIRED = [
    ("P-V2, C-V2, S-V2 (old)", "PROP", "absolute-rate fact-check -- no principled null (P-V2/C-V2 IDs reused below)"),
    ("P-M1, C-M1, S-M1", "rate differ", "\"differ\" has no clean refuted (can't accept H0)"),
    ("S-M3, F-M1", "same", "\"same\" is the null -- can never be supported"),
    ("F-M2", "differ-first", "same defect as the other differ groups"),
]


def _score_pipeline(index, group):
    """Whole-population: (testable cores, significant cores, median n)."""
    cores = C.enumerate_group_full(index, group)
    graded = []
    for c in cores:
        if c.report_id is not None or not c.computable or c.n is None:
            continue
        s = core_significance(c)
        if s.test is None:
            continue
        graded.append((c, s))
    ns = [c.n for c, _ in graded if c.n is not None]
    nsig = sum(1 for _, s in graded if s.significant)
    return len(graded), nsig, (int(median(ns)) if ns else 0)


def _score_new(fn, index):
    res = fn(index)          # list of (is_significant, n)
    ns = [n for _, n in res]
    return len(res), sum(1 for s, _ in res if s), (int(median(ns)) if ns else 0)


def _count_report(index, group):
    return len(C.enumerate_group_full(index, group))


def compute(index):
    groups = load_groups()
    rows = []
    for gid, fam, scope, typ, claim, null, test, kind in ROSTER:
        if kind == "report":
            cores, sig, medn = _count_report(index, groups[gid]), None, None
        elif kind == "pipeline":
            cores, sig, medn = _score_pipeline(index, groups[gid])
        else:
            cores, sig, medn = _score_new({"r1": _r1, "r3": _r3, "r5": _r5}[kind], index)
        rows.append({"id": gid, "family": fam, "scope": scope, "type": typ,
                     "claim": claim, "null": null, "test": test, "kind": kind,
                     "cores": cores, "sig": sig, "medn": medn})
    return rows


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def _rate(sig, cores):
    if sig is None or not cores:
        return "-"
    return f"{100 * sig / cores:.0f}%"


# --------------------------------------------------------------------------
# LaTeX rendering (standalone, compilable article; matches the repo style)
# --------------------------------------------------------------------------

_TEX_PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{amssymb}
\usepackage{amsmath}
\usepackage{microtype}
\usepackage[hidelinks]{hyperref}

% weighted wrapping columns for the template tables
\newcolumntype{W}{>{\hsize=1.7\hsize\raggedright\arraybackslash}X}
\newcolumntype{N}{>{\hsize=0.75\hsize\raggedright\arraybackslash}X}
\newcolumntype{T}{>{\hsize=0.55\hsize\raggedright\arraybackslash}X}
\newcolumntype{R}{>{\raggedright\arraybackslash}X}

\title{Temporal Hypothesis Benchmark:\\Final Template Design}
\author{Project working note}
\date{\today}

\begin{document}
\maketitle
"""


def _esc(s) -> str:
    s = re.sub(r'"([^"]*)"', r"``\1''", str(s))   # straight -> LaTeX quotes
    for a, b in [("->", r"$\rightarrow$ "), ("<", r"$<$"), (">", r"$>$"),
                 ("&", r"\&"), ("%", r"\%"), ("#", r"\#"), ("_", r"\_")]:
        s = s.replace(a, b)
    return s


def render_tex(rows):
    testable = [r for r in rows if r["kind"] != "report"]
    n_report = sum(1 for r in rows if r["kind"] == "report")
    live = [r for r in rows if r["kind"] == "pipeline"]
    live_cores = sum(r["cores"] for r in live)
    live_sig = sum(r["sig"] for r in live)
    overall = 100 * live_sig / live_cores if live_cores else 0.0

    by_fam: dict[str, list] = {}
    for r in rows:
        by_fam.setdefault(r["family"], []).append(r)

    d = [_TEX_PREAMBLE]

    d.append(r"\section*{What this benchmark is}")
    d.append(
        r"A benchmark for \emph{temporal hypothesis verification} over clinical "
        r"narratives (VAERS reports in the MedTempo corpus). Each item gives a "
        r"framework a set of raw narratives plus one natural-language hypothesis "
        r"about a temporal pattern; the framework must locate the evidence and "
        r"return \textbf{supported}, \textbf{refuted}, or \textbf{insufficient}. "
        r"Gold labels are computed deterministically from expert timelines. The "
        rf"design is \textbf{{{len(rows)} template groups}}: "
        rf"\textbf{{{len(testable)} hypothesis-test groups}} (scored over the "
        rf"whole corpus below) and \textbf{{{n_report} report-level groups}} "
        r"(single-narrative facts, deterministic---no test).")

    d.append(r"\section*{Design principles}")
    d.append(r"\begin{enumerate}\itemsep2pt")
    d += [
        r"\item \textbf{Every cohort-level claim is a hypothesis test with a "
        r"principled null}---a chance baseline (a coin-flip $0.5$, a uniform "
        r"distribution, or ``this ordering beats its nearest rival''), or a "
        r"comparison to another group. No claim is graded by matching an "
        r"observed number.",
        r"\item \textbf{Significance \emph{is} the verdict} (a three-decision "
        r"test). For a claim that names a direction: significant in that "
        r"direction $\rightarrow$ supported; significant in the \emph{opposite} "
        r"direction $\rightarrow$ refuted; not significant either way "
        r"$\rightarrow$ insufficient. Refuted always means significant "
        r"counter-evidence, never merely ``unproven.''",
        r"\item \textbf{Directional tests are one-sided at $\alpha=0.05$ per "
        r"side}, in the observed direction---chosen to maximize usable cases "
        r"(under a true null the chance of declaring \emph{some} direction is "
        r"${\approx}2\alpha$).",
        r"\item \textbf{No absolute-percentage claims.} ``In ${\sim}40\%$ of "
        r"reports\ldots'' is a fact-check with no null, so those groups were "
        r"retired.",
        r"\item \textbf{Two-cohort comparisons are directional only} (``higher "
        r"after $v_1$ than $v_2$''). ``Do they differ / are they the same'' was "
        r"removed: a test can reject the no-difference null but never confirm "
        r"it, so those shapes have no clean supported/refuted.",
        r"\item \textbf{Report-level claims are exact facts} about one "
        r"narrative---deterministic, no statistics.",
    ]
    d.append(r"\end{enumerate}")

    d.append(r"\section*{The " + str(len(rows)) + r" templates}")
    d.append(r"Scope: \textbf{report} = one narrative; \textbf{vaccine} = one "
             r"cohort; \textbf{multi} = two-cohort comparison. New groups are "
             r"marked $\star$.")
    fam_title = {"precedes": "Pairwise: precedes",
                 "co-occurs": "Pairwise: co-occurs",
                 "sequence": "Sequence", "first/last": "First / last"}
    for fam in ["precedes", "co-occurs", "sequence", "first/last"]:
        d.append(r"\subsection*{" + fam_title[fam] + r"}")
        d.append(r"\noindent\begin{tabularx}{\linewidth}{lllWNT}")
        d.append(r"\toprule")
        d.append(r"\textbf{ID} & \textbf{Scope} & \textbf{Type} & "
                 r"\textbf{Hypothesis} & \textbf{Null / reference} & "
                 r"\textbf{Test} \\")
        d.append(r"\midrule")
        for r in by_fam[fam]:
            star = r"$\star$" if r["kind"] in ("r1", "r3", "r5") else ""
            d.append(f"{r['id']}{star} & {r['scope']} & {r['type']} & "
                     f"{_esc(r['claim'])} & {_esc(r['null'])} & "
                     f"{_esc(r['test'])} \\\\")
        d.append(r"\bottomrule")
        d.append(r"\end{tabularx}")

    new_sig = sum(r["sig"] for r in rows if r["kind"] in ("r1", "r3", "r5"))
    total_dec = live_sig + new_sig
    balanced = round(1.5 * total_dec)
    half = round(total_dec / 2)
    d.append(r"\section*{Whole-corpus results}")
    d.append(
        r"For every \textbf{case}---one distinct event-combination asked about "
        r"in a cohort---we run its three-decision test over all 3{,}166 reports. "
        r"A case is \textbf{decisive} when the test is significant: it can then "
        r"be posed as a \emph{supported} claim (oriented with the effect) or a "
        r"\emph{refuted} one (oriented against it). An \textbf{indecisive} case "
        r"(not significant either way) can only be \emph{insufficient}. So the "
        r"number that matters per template is \textbf{S = decisive cases}---the "
        r"shared resource behind both supported and refuted. \textbf{Med.\ $n$} "
        r"= median reports behind one case.")
    d.append(
        rf"\medskip\noindent\textbf{{Headline:}} the cohort-level groups supply "
        rf"\textbf{{{total_dec:,} decisive cases}}. Sampled to an equal "
        rf"1/3 : 1/3 : 1/3 verdict mix (one claim per decisive case), that is a "
        rf"balanced benchmark of about \textbf{{{balanced:,}}} items---about "
        rf"{half:,} supported and {half:,} refuted from the decisive cases, plus "
        rf"an equal insufficient slice. Supply is dominated by the "
        rf"pairwise/co-occurs groups; sequence and multi groups are thin. "
        rf"New-group counts ($\star$) are candidate-inventory ceilings.")
    d.append(r"\medskip\noindent\begin{tabularx}{\linewidth}{llRrr}")
    d.append(r"\toprule")
    d.append(r"\textbf{ID} & \textbf{Scope} & \textbf{Test} & "
             r"\textbf{Decisive (S)} & \textbf{Bench.\ ${\approx}1.5S$} & "
             r"\textbf{Med.\ $n$} \\")
    d.append(r"\midrule")
    for r in testable:
        star = r"$\star$" if r["kind"] in ("r1", "r3", "r5") else ""
        ss = r["sig"]
        d.append(f"{r['id']}{star} & {r['scope']} & {_esc(r['test'])} & "
                 f"{ss:,} & {round(1.5*ss):,} & {r['medn']} \\\\")
    d.append(r"\bottomrule")
    d.append(r"\end{tabularx}")

    d.append(r"\subsection*{Decisive-case supply by family (live groups)}")
    d.append(r"\noindent\begin{tabular}{lrrr}")
    d.append(r"\toprule")
    d.append(r"\textbf{Family} & \textbf{Cases} & \textbf{Decisive (S)} & "
             r"\textbf{Decisive rate} \\ \midrule")
    for fam in ["precedes", "co-occurs", "sequence", "first/last"]:
        fl = [r for r in by_fam[fam] if r["kind"] == "pipeline"]
        cc = sum(r["cores"] for r in fl)
        ss = sum(r["sig"] for r in fl)
        if cc:
            d.append(f"{fam_title[fam]} & {cc:,} & {ss:,} & {100*ss/cc:.0f}\\% \\\\")
    d.append(r"\bottomrule\end{tabular}")
    d.append(
        r"\medskip\noindent\textbf{Reading the gradient.} Pairwise/co-occurs "
        r"questions rest on ${\sim}30$ reports each, so most cases are decisive; "
        r"sequence and two-cohort questions slice the corpus down to "
        r"${\sim}6$--$8$ reports, so most cases are indecisive---a property of "
        r"the corpus, not the tests, and what makes the verdicts non-trivial.")
    d.append(r"\subsection*{Benchmark composition (target)}")
    d.append(r"\begin{itemize}\itemsep2pt")
    d.append(
        r"\item \textbf{Verdict mix:} ${\approx}1/3$ supported, $1/3$ refuted, "
        r"$1/3$ insufficient per group---equal thirds, so every trivial policy "
        r"(always-supported ``yes-man,'' always-insufficient) scores only "
        r"${\approx}33\%$.")
    d.append(
        r"\item \textbf{Sourcing:} supported and refuted are drawn from the "
        r"decisive cases, one claim per case and from \emph{different} event "
        r"combinations (never the A$\rightarrow$B / B$\rightarrow$A mirror of a "
        r"single case). Budget per group ${\approx}1.5S$; groups with tiny $S$ "
        r"(sequence) are taken in full and flagged as starved.")
    d.append(
        r"\item \textbf{Insufficient spans three kinds:} \emph{underpowered} "
        r"(co-occur enough, no significant effect), \emph{sparse} (co-occur but "
        r"below the sample-size floor), and \emph{not-locatable} (events absent "
        r"or never co-occurring, $n=0$)---the last added deliberately, to test "
        r"that the framework answers ``insufficient'' instead of inventing a "
        r"relationship.")
    d.append(
        r"\item \textbf{Grading:} per-class precision/recall and macro-F1, not "
        r"bare accuracy.")
    d.append(r"\end{itemize}")

    d.append(r"\section*{What changed in the redesign}")
    d.append(r"The roster went from 30 to \textbf{" + str(len(rows))
             + r"} groups. Retired:")
    d.append(r"\noindent\begin{tabularx}{\linewidth}{llR}")
    d.append(r"\toprule")
    d.append(r"\textbf{Groups} & \textbf{Shape} & \textbf{Why removed} \\ \midrule")
    for grp, shape, why in RETIRED:
        d.append(f"{_esc(grp)} & {_esc(shape)} & {_esc(why)} \\\\")
    d.append(r"\bottomrule\end{tabularx}")
    d.append(
        r"\medskip\noindent Added three single-cohort groups with principled "
        r"nulls: \textbf{P-V2} (does $A$ precede $B$ more than $C$ does?), "
        r"\textbf{P-V4} (does one pair's ordering beat another's?), "
        r"\textbf{C-V2} (are $A$ and $B$ associated beyond chance?). The freed "
        r"\textbf{P-V2}/\textbf{C-V2} IDs are reassigned to these new groups "
        r"(the retired PROP claims no longer exist); \textbf{P-V4} is a new ID. "
        r"Reworded \textbf{S-V1}/\textbf{F-V3} from vague ``typically'' to a "
        r"testable ``most common'' (verified against the nearest rival).")
    d.append(
        r"\medskip\noindent\emph{Note.} New-group counts (P-V2, P-V4, C-V2) come "
        r"from the candidate inventory (full corpus, most-frequent-events "
        r"enumeration) and are ceilings pending pipeline integration; their "
        r"\textbf{decidable rates} are the comparable figure. C-V2's association test "
        r"spans the entire cohort (${\sim}1{,}000$ reports), hence its large "
        r"median $n$.")

    d.append(r"\end{document}")
    return "\n".join(d) + "\n"


def main():
    conn = sqlite3.connect(str(_REPO / "data" / "medtempo.db"))
    index = CorpusIndex.load(conn)
    rows = compute(index)
    conn.close()

    ref = _REPO / "docs" / "reference"
    out_tex = ref / "Final_Template_Design.tex"
    out_tex.write_text(render_tex(rows), encoding="utf-8")

    print(f"{'ID':6}{'scope':8}{'cases':>8}{'sig':>7}{'rate':>7}{'medn':>6}")
    for r in rows:
        rate = _rate(r["sig"], r["cores"])
        medn = "-" if r["medn"] is None else r["medn"]
        print(f"{r['id']:6}{r['scope']:8}{r['cores']:8,}"
              f"{(r['sig'] if r['sig'] is not None else 0):7,}{rate:>7}{medn:>6}")
    print(f"\nWrote {out_tex}")


if __name__ == "__main__":
    main()
