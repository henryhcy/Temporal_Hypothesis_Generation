#!/usr/bin/env python3
"""Generate a LaTeX write-up: short intro, current pilot findings, and full
template tables (all 30 groups across all four registers).

Reads the canonical template YAML files in data/templates/ so the template
catalogue can never drift from the source of truth.
"""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "data" / "templates"
OUT = ROOT / "docs" / "reference" / "Findings_and_Templates.tex"

FAMILY_FILES = [
    ("Pairwise (precedes / co-occurs)", "pairwise.yaml"),
    ("Sequence (three-event ordering)", "sequence.yaml"),
    ("First / Last (superlative)", "first_last.yaml"),
]
REGISTER_ORDER = ["original", "research", "media", "clinical"]
REGISTER_LABEL = {
    "original": "Original",
    "research": "Research",
    "media": "Media",
    "clinical": "Clinical",
}


def esc(s: str) -> str:
    """Escape a plain string for LaTeX, mapping the few special glyphs used
    in the templates (braces, percent, arrow, ampersand, etc.)."""
    s = str(s)
    out = []
    for ch in s:
        if ch == "\\":
            out.append(r"\textbackslash{}")
        elif ch == "{":
            out.append(r"\{")
        elif ch == "}":
            out.append(r"\}")
        elif ch == "%":
            out.append(r"\%")
        elif ch == "&":
            out.append(r"\&")
        elif ch == "#":
            out.append(r"\#")
        elif ch == "$":
            out.append(r"\$")
        elif ch == "_":
            out.append(r"\_")
        elif ch == "~":
            out.append(r"\textasciitilde{}")
        elif ch == "^":
            out.append(r"\textasciicircum{}")
        elif ch == "<":
            out.append(r"$<$")
        elif ch == ">":
            out.append(r"$>$")
        elif ch == "→":  # →
            out.append(r"$\rightarrow$ ")
        else:
            out.append(ch)
    return "".join(out)


def load_family(fname):
    with open(TPL / fname) as f:
        return yaml.safe_load(f)


def family_catalogue(title, data):
    """Emit a longtable of every group x register for one family."""
    lines = []
    fam = data["family"]
    lines.append(r"\subsection{%s}" % esc(title))
    desc = data.get("description", "").strip()
    if desc:
        lines.append(r"\noindent\emph{%s}" % esc(desc))
        lines.append("")
    notes = data.get("notes", "").strip()
    if notes:
        lines.append(r"\noindent\textbf{Family rule.} " + esc(notes))
        lines.append("")
    for g in data["groups"]:
        gid = g["id"]
        meta = "Primitive: \\texttt{%s} \\quad Level: \\texttt{%s} \\quad Answer: \\texttt{%s} \\quad Slots: \\texttt{%s}" % (
            esc(g["primitive"]), esc(g["level"]), esc(g["answer_type"]),
            esc(", ".join(g["slots"])),
        )
        lines.append(r"\paragraph{\textbf{%s}}\mbox{}\\" % esc(gid))
        lines.append(meta + r"\\[2pt]")
        lines.append(r"\begin{tabularx}{\linewidth}{@{}l L L@{}}")
        lines.append(r"\toprule")
        lines.append(r"\textbf{Register} & \textbf{Question} & \textbf{Claim} \\")
        lines.append(r"\midrule")
        for reg in REGISTER_ORDER:
            v = g["variants"].get(reg)
            if not v:
                continue
            lines.append("%s & %s & %s \\\\" % (
                esc(REGISTER_LABEL[reg]), esc(v["question"]), esc(v["claim"]),
            ))
        lines.append(r"\bottomrule")
        lines.append(r"\end{tabularx}")
        lines.append(r"\vspace{4pt}")
        lines.append("")
    return "\n".join(lines)


def overview_table(families):
    """The 'how composed' structure summary, counted from the YAML."""
    rows = []
    tot_r = tot_v = tot_m = tot = 0
    for title, data in families:
        fam = data["family"]
        c = {"report": 0, "vaccine": 0, "multi": 0}
        for g in data["groups"]:
            c[g["level"]] += 1
        n = sum(c.values())
        tot_r += c["report"]; tot_v += c["vaccine"]; tot_m += c["multi"]; tot += n
        rows.append((fam, c["report"], c["vaccine"], c["multi"], n))
    out = [r"\begin{tabular}{@{}lcccc@{}}", r"\toprule",
           r"\textbf{Family} & \textbf{Report} & \textbf{Vaccine} & \textbf{Multi} & \textbf{Total} \\",
           r"\midrule"]
    for fam, r, v, m, n in rows:
        out.append("\\texttt{%s} & %d & %d & %d & %d \\\\" % (esc(fam), r, v, m, n))
    out.append(r"\midrule")
    out.append("\\textbf{Total} & \\textbf{%d} & \\textbf{%d} & \\textbf{%d} & \\textbf{%d} \\\\" % (tot_r, tot_v, tot_m, tot))
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    return "\n".join(out), tot


PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{amssymb}
\usepackage{amsmath}
\usepackage{microtype}
\usepackage{xcolor}
\usepackage[hidelinks]{hyperref}

% Wrapping left-aligned X column
\newcolumntype{L}{>{\raggedright\arraybackslash}X}

\title{Temporal Hypothesis Generation:\\Current Findings and Template Catalogue}
\author{Project working note}
\date{\today}

\begin{document}
\maketitle
"""


def main():
    families = [(title, load_family(fname)) for title, fname in FAMILY_FILES]
    struct_tbl, total_groups = overview_table(families)

    doc = [PREAMBLE]

    # ---- Introduction ----
    doc.append(r"\section{Introduction}")
    doc.append(
        r"""This project builds a benchmark and framework for \emph{temporal hypothesis
verification over clinical narratives}. Given a natural-language hypothesis about the
temporal pattern of vaccine adverse events together with the relevant report narratives,
the framework returns a verdict---\emph{supported}, \emph{refuted}, or \emph{insufficient}---grounded
in the temporal structure of the reports. The substrate is \textbf{MedTempo}: 3{,}166
expert-annotated VAERS reports for three vaccines (Pfizer, Moderna, Johnson), encoding
ordinal relations (\emph{before}, \emph{after}, \emph{co-exist}) with no timestamps.
MedTempo is private scaffolding used only to compute deterministic gold labels; the
framework sees narrative text plus the hypothesis at inference, nothing else.

The positioning is \textbf{agentic temporal claim verification with statistical grounding}:
distinct from temporal knowledge-graph QA (which assumes a clean timestamped graph), from
scientific claim verification (which lacks population-level aggregation), and from classical
pharmacovigilance signal detection (which is not driven by natural-language hypotheses).
The work is currently in its dataset-design and template-generation phase; the results below
come from a full enumeration \emph{pilot} whose job is to characterise the corpus and
recalibrate sampling before scaling to the target benchmark of 10{,}000--15{,}000 instances.""")

    # ---- Findings ----
    doc.append(r"\section{Current Findings (Pilot)}")
    doc.append(
        r"""The pilot enumerates every viable factual core in MedTempo across all %d template
groups and computes the deterministic gold label for each, before any verdict balancing.
The full-enumeration run produced \textbf{289{,}216} candidate instances over the 30 groups.
Key observations:""" % total_groups)
    doc.append(r"""\begin{itemize}
  \item \textbf{Coverage is healthy.} No group is starved: every group clears the
  provisional 50-viable-core target. Report-level groups draw on all 3{,}166 reports;
  vaccine-level groups on 575--959 cohorts; multi-vaccine groups on 322--579 cohorts.
  \item \textbf{Cohorts are small.} Median cohort size is $n=16$ (pairwise) and $n=14$
  (sequence, first/last), with a long thin tail---roughly 11--15\% of cohorts sit at or
  below the $n=10$ inclusion threshold.
  \item \textbf{Natural verdicts are skewed and group-dependent} (Table~\ref{tab:verdicts}),
  which is exactly why a balancing pass is required. Sequence claims are mostly
  \emph{refuted} under strict ordering (67\%), first/last claims are heavily
  \emph{insufficient} (47\%, driven by ties and missing candidates), and pairwise sits
  closest to balanced.
  \item \textbf{Estimates are wide.} Across single-proportion cores the median Wilson
  95\% CI width is 0.37, and \textbf{70\%} of cores are ``low-confidence'' (CI width
  $>0.30$)---a direct consequence of small cohorts, and the main input to recalibrating
  the low-band floor.
  \item \textbf{Multi-vaccine overlap is sufficient.} All three vaccine pairs yield enough
  jointly-computable cores (insufficiency 11--12\%); no Johnson fallback is triggered.
  \item \textbf{Representation integrity holds.} First/last tie rate is substantial
  (median 0.50) and 62\% of reports have a co-occurrence at the earliest level; only 7
  duplicate-term-across-levels anomalies were found. Cycles/disconnected components are
  not recoverable by construction (annotations are stored as acyclic leveled orders).
\end{itemize}""")

    doc.append(r"""\begin{table}[h]
\centering
\caption{Natural verdict distribution per family (no balancing), from the pilot
distribution report.}
\label{tab:verdicts}
\begin{tabular}{@{}lccc@{}}
\toprule
\textbf{Family} & \textbf{Supported} & \textbf{Refuted} & \textbf{Insufficient} \\
\midrule
pairwise   & 0.443 & 0.342 & 0.215 \\
sequence   & 0.264 & 0.674 & 0.062 \\
first/last & 0.435 & 0.097 & 0.468 \\
\bottomrule
\end{tabular}
\end{table}""")

    doc.append(r"""\noindent\textbf{Implication.} The pilot confirms the design is generative
across all 30 groups but that (i) small cohorts make many single-proportion estimates
imprecise, and (ii) natural verdict skew varies sharply by group, so the target
45/45/10 supported/refuted/insufficient balance must be enforced per group rather than
assumed. These numbers are the inputs to the second-pass sampling recalibration; the
benchmark is not scaled until the distribution report is reviewed.""")

    # ---- Templates: how composed ----
    doc.append(r"\section{Template Catalogue}")
    doc.append(r"\subsection{How the templates are composed}")
    doc.append(
        r"""Templates are the single source of truth in three YAML files under
\texttt{data/templates/} (\texttt{pairwise.yaml}, \texttt{sequence.yaml},
\texttt{first\_last.yaml}); the advisor-facing \texttt{.docx} is a generated artefact.
Each \textbf{group} is a typed temporal question with a fixed slot schema, and is composed
along four orthogonal axes:""")
    doc.append(r"""\begin{description}
  \item[Family / primitive] the temporal relation being tested:
  \texttt{precedes} or \texttt{co\_occurs} (pairwise, two events), \texttt{sequence}
  (strict ordering of three events), or \texttt{first\_last} (superlative argmax over a
  candidate set).
  \item[Level (cohort scope)] \texttt{report} (a single narrative), \texttt{vaccine}
  (aggregate over one vaccine's cohort), or \texttt{multi} (compare two vaccine cohorts).
  \item[Answer type] \texttt{BOOL} (yes/no), \texttt{CHOICE} (pick the correct option),
  or \texttt{PROP} (assert a proportion; supported if within 5 percentage points of truth).
  \item[Register (surface form)] each group is mechanically projected into four
  registers---\textbf{Original} (canonical seed), \textbf{Research}, \textbf{Media}, and
  \textbf{Clinical}---with no LLM rewriting. A negation modifier is additionally applied to
  a subset of BOOL instances at generation time (flipping both the assertion and the gold
  verdict); it is not stored in the YAML.
\end{description}""")
    doc.append(r"Every group instantiates both a \textbf{question} and a \textbf{claim} per register, so each group yields $4\times2$ surface forms before slot-filling and negation. The $30$ groups break down by family and level as follows:")
    doc.append(r"\begin{center}")
    doc.append(struct_tbl)
    doc.append(r"\end{center}")

    doc.append(r"""\paragraph{Slots.} Placeholders are filled mechanically from MedTempo
term types plus a manual synonym table:
\begin{center}
\begin{tabular}{@{}lll@{}}
\toprule
\textbf{Slot} & \textbf{Type} & \textbf{Meaning} \\
\midrule
\texttt{\{A\}}, \texttt{\{B\}}, \texttt{\{C\}} & event   & Event term type (+ synonyms) \\
\texttt{\{v\}}                                 & vaccine & Single vaccine \\
\texttt{\{v1\}}, \texttt{\{v2\}}               & vaccine & Two vaccines (multi-vaccine groups) \\
\texttt{\{r\}}                                 & context & Report identifier / contextual reference \\
\texttt{\{p\}}                                 & value   & Asserted proportion (PROP instances only) \\
\bottomrule
\end{tabular}
\end{center}""")

    doc.append(r"""\paragraph{Verdict mechanics.} \texttt{BOOL}: supported iff the assertion
matches the data. \texttt{CHOICE}: supported iff it names the correct option. \texttt{PROP}:
supported iff the asserted \texttt{\{p\}} is within 5 percentage points of the true
proportion. \texttt{Insufficient}: cohort below the $n=10$ threshold, indeterminable
ordering (ties, disconnected components), or required events missing from a cohort report.""")

    # ---- Full catalogue ----
    doc.append(r"\subsection*{}")
    doc.append(r"\subsection{Full template listing (all groups $\times$ all registers)}")
    doc.append(
        r"""The following enumerates every group with its metadata and all four register
variants of both the question and the claim. Slot placeholders are shown in braces.""")
    for title, data in families:
        doc.append(family_catalogue(title, data))

    # ---- Worked examples computed from MedTempo (optional; make_examples.py) ----
    examples = ROOT / "data" / "pilot" / "examples.tex"
    if examples.exists():
        doc.append(examples.read_text(encoding="utf-8"))

    doc.append(r"\end{document}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(doc))
    print("Wrote", OUT)
    print("Total groups:", total_groups)


if __name__ == "__main__":
    main()
