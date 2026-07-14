"""Corpus inventory for the R1-R8 replacement-template candidates.

The template redesign (`decisions.md`, 2026-07-13) retires the PROP groups and
the redundant S-V1/S-V3, F-V3/F-V1 slots, and proposes a menu R1-R8 of
replacements. Before adopting any, we need to know whether each yields enough
*significant* cores (the supported ceiling under significance-as-verdict). This
script runs every candidate over the full corpus and reports, per candidate:

- viable cores: enumerated cores clearing the family floor (from the top-K most
  frequent events per cohort, to bound the combinatorics);
- significant cores: cores whose test is significant at alpha=0.05, one-sided in
  the observed direction for directional tests (the SUPPORTED ceiling);
- sig rate = significant / viable; median effective n.

Operationalizations (documented so the numbers are reproducible) are in
CANDIDATES below. Writes a LaTeX section to data/pilot/replacement_inventory.tex
(folded into Findings_and_Templates.tex as Section 5) and prints a summary.

    python scripts/replacement_inventory.py
"""

from __future__ import annotations

import sqlite3
from itertools import combinations, permutations
from pathlib import Path
from statistics import median

from temporal_hypo.core import significance as sig
from temporal_hypo.core.positions import mann_whitney_u
from temporal_hypo.generation import corpus
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.vaccines import VACCINES

_REPO = Path(__file__).resolve().parent.parent

ALPHA = 0.05
PAIR_FLOOR = 20      # precedes / co-occurs ordered-or-both n
FIRST_FLOOR = 15     # first-among decisive n (winner vs runner-up)
SEQ_FLOOR = 5        # orderable n (distinct-level triples)


def _sig(p):
    return p is not None and p < ALPHA


# --- R1: pair-vs-pair precedence -------------------------------------------
# "In {v}, A precedes B more often than C precedes D." Two independent
# precedes-fractions; one-sided Fisher (stronger pair = greater).
def r1(index):
    out = []
    for v in VACCINES:
        cohort = index.cohort(v)
        pairs = []
        for a, b in combinations(index.top_terms(cohort, 12), 2):
            r = corpus.precedes_fraction(index, a, b, cohort)
            if r is None or r[1] < PAIR_FLOOR:
                continue
            frac, n = r
            k = round(frac * n)
            # store majority-direction strength
            pairs.append((max(frac, 1 - frac), max(k, n - k), n))
        for (f1, k1, n1), (f2, k2, n2) in combinations(pairs, 2):
            hi, lo = ((k1, n1), (k2, n2)) if f1 >= f2 else ((k2, n2), (k1, n1))
            p = sig.fisher_exact_2x2(hi[0], hi[1], lo[0], lo[1], alternative="greater")
            out.append((_sig(p), min(n1, n2)))
    return out


# --- R2: event-vs-event first-rate -----------------------------------------
# "In {v}, A is first more often than B is." Among a triple, the two most-first
# events; one-sided binomial (A's first-count vs A+B, null 0.5).
def r2(index):
    out = []
    for v in VACCINES:
        cohort = index.cohort(v)
        for combo in combinations(index.top_terms(cohort, 14), 3):
            f = corpus.first_among_fractions(index, list(combo), cohort)
            if f is None:
                continue
            counts = f["counts"]
            a, b = sorted(combo, key=lambda t: -counts.get(t, 0))[:2]
            ka, kb = counts.get(a, 0), counts.get(b, 0)
            n = ka + kb
            if n < FIRST_FLOOR:
                continue
            out.append((_sig(sig.binom_exact_p(ka, n, 0.5, alternative="greater")), n))
    return out


# --- R3: conditional antecedent --------------------------------------------
# "In {v}, B follows A more often than B follows C." P(A before B) vs P(C before
# B); one-sided Fisher. One core per (triple, choice of consequent B).
def r3(index):
    out = []
    for v in VACCINES:
        cohort = index.cohort(v)
        for combo in combinations(index.top_terms(cohort, 14), 3):
            for b in combo:
                a, c = [t for t in combo if t != b]
                ra = corpus.precedes_fraction(index, a, b, cohort)
                rc = corpus.precedes_fraction(index, c, b, cohort)
                if ra is None or rc is None or ra[1] < PAIR_FLOOR or rc[1] < PAIR_FLOOR:
                    continue
                fa, na = ra
                fc, nc = rc
                ka, kc = round(fa * na), round(fc * nc)
                hi, lo = ((ka, na), (kc, nc)) if fa >= fc else ((kc, nc), (ka, na))
                p = sig.fisher_exact_2x2(hi[0], hi[1], lo[0], lo[1], alternative="greater")
                out.append((_sig(p), min(na, nc)))
    return out


# --- R4: temporal-gap magnitude --------------------------------------------
# "In {v}, A and B are farther apart than C and D." Mann-Whitney on the |level
# distance| distributions (position-based); one-sided ~ two-sided/2 in the
# observed direction.
def r4(index):
    out = []
    for v in VACCINES:
        cohort = index.cohort(v)
        pairs = []
        for a, b in combinations(index.top_terms(cohort, 12), 2):
            d = [abs(x) for x in corpus.pair_distances(index, a, b, cohort)]
            if len(d) >= PAIR_FLOOR:
                pairs.append(d)
        for d1, d2 in combinations(pairs, 2):
            x, y = (d1, d2) if (sum(d1) / len(d1)) >= (sum(d2) / len(d2)) else (d2, d1)
            r = mann_whitney_u(x, y)
            out.append((_sig(r["p"] / 2.0), min(len(d1), len(d2))))
    return out


# --- R5: association vs independence ---------------------------------------
# "In {v}, A and B co-occur more than if independent." 2x2 presence x presence
# over the whole cohort; one-sided Fisher (positive association). n ~ cohort.
def r5(index):
    out = []
    for v in VACCINES:
        cohort = index.cohort(v)
        N = len(cohort)
        present = {}
        for vid in cohort:
            for t in index.report_terms[vid]:
                present.setdefault(t, set()).add(vid)
        terms = [t for t in index.top_terms(cohort, 20) if len(present.get(t, ())) >= PAIR_FLOOR]
        for a, b in combinations(terms, 2):
            A, B = present[a], present[b]
            both = len(A & B)
            ca = len(A)
            b_not_a = len(B) - both
            p = sig.fisher_exact_2x2(both, ca, b_not_a, N - ca, alternative="greater")
            out.append((_sig(p), N))
    return out


# --- R6: concentration vs uniform (= a fixed S-V4) -------------------------
# "In {v}, the ordering of A, B, C is concentrated (not uniform)." Multinomial
# GOF vs uniform over the 6 orderings (omnibus, two-sided).
def r6(index):
    out = []
    for v in VACCINES:
        cohort = index.cohort(v)
        for combo in combinations(index.top_terms(cohort, 14), 3):
            d = corpus.ordering_distribution(index, list(combo), cohort)
            if d is None or d["n"] < SEQ_FLOOR:
                continue
            observed = [d["counts"].get(p, 0) for p in permutations(combo)]
            out.append((_sig(sig.multinomial_gof(observed)["p"]), d["n"]))
    return out


# --- R7: multiple-of-chance threshold --------------------------------------
# "A -> B -> C occurs at least twice the chance rate (>1/3)." One-sided binomial
# of the modal ordering count vs p0 = 2*(1/6) = 1/3.
def r7(index):
    out = []
    for v in VACCINES:
        cohort = index.cohort(v)
        for combo in combinations(index.top_terms(cohort, 14), 3):
            d = corpus.ordering_distribution(index, list(combo), cohort)
            if d is None or d["n"] < SEQ_FLOOR:
                continue
            p = sig.binom_exact_p(d["modal_count"], d["n"], 1 / 3, alternative="greater")
            out.append((_sig(p), d["n"]))
    return out


# --- R8: strongest-pair superlative ----------------------------------------
# "Among (A,B),(A,C),(A,D), A->B is the strongest ordering." Argmax over the
# anchor A's precedes-pairs; one-sided Fisher of the top vs the runner-up.
def r8(index):
    out = []
    for v in VACCINES:
        cohort = index.cohort(v)
        terms = index.top_terms(cohort, 15)
        for a in terms:
            cands = []
            for x in terms:
                if x == a:
                    continue
                r = corpus.precedes_fraction(index, a, x, cohort)
                if r is None or r[1] < PAIR_FLOOR:
                    continue
                frac, n = r
                cands.append((frac, round(frac * n), n))
            if len(cands) < 3:
                continue
            cands.sort(key=lambda c: -c[0])
            top, run = cands[0], cands[1]
            p = sig.fisher_exact_2x2(top[1], top[2], run[1], run[2], alternative="greater")
            out.append((_sig(p), min(top[2], run[2])))
    return out


CANDIDATES = [
    ("R1", "A precedes B more often than C precedes D", "two-prop Fisher (1-sided)",
     "P-V2", r1),
    ("R2", "A is first more often than B", "binomial (1-sided)", "-", r2),
    ("R3", "B follows A more often than B follows C", "two-prop Fisher (1-sided)",
     "P-V2", r3),
    ("R4", "A,B are farther apart than C,D", "Mann-Whitney (1-sided)", "-", r4),
    ("R5", "A and B co-occur more than if independent", "2x2 Fisher (1-sided)",
     "C-V2", r5),
    ("R6", "the ordering of A,B,C is concentrated (not uniform)",
     "multinomial GOF", "S-V4", r6),
    ("R7", "the ordering A,B,C occurs at least twice the chance rate",
     "binomial vs 1/3 (1-sided)", "S-V2", r7),
    ("R8", "among A's pairs, A-before-B is the strongest ordering",
     "argmax + Fisher (1-sided)", "-", r8),
]


def run():
    conn = sqlite3.connect(str(_REPO / "data" / "medtempo.db"))
    index = CorpusIndex.load(conn)
    rows = []
    for cid, claim, test, replaces, fn in CANDIDATES:
        res = fn(index)
        viable = len(res)
        nsig = sum(1 for s, _ in res if s)
        ns = [n for _, n in res]
        rows.append({
            "id": cid, "claim": claim, "test": test, "replaces": replaces,
            "viable": viable, "sig": nsig,
            "rate": (nsig / viable) if viable else 0.0,
            "median_n": int(median(ns)) if ns else 0,
        })
    conn.close()
    return rows


def _esc(s):
    for a, b in [("&", r"\&"), ("%", r"\%"), ("_", r"\_"), ("#", r"\#"),
                 ("->", r"$\rightarrow$"), (">=", r"$\geq$"), (">", r"$>$")]:
        s = str(s).replace(a, b)
    return s


def _render_tex(rows):
    out = [r"\section{Replacement Template Inventory (R1--R8, computed on MedTempo)}",
           r"Candidate replacements for the retired PROP groups and the redundant "
           r"S-V1/S-V3, F-V3/F-V1 slots (menu in \texttt{decisions.md}, 2026-07-13). "
           r"Each is run over the full corpus. \textbf{Viable} = enumerated cores "
           r"clearing the family floor, drawn from the top-$K$ most frequent events "
           r"per cohort to bound the combinatorics; \textbf{Sig.} = cores significant "
           r"at $\alpha=0.05$, one-sided in the observed direction for the directional "
           r"tests (the SUPPORTED ceiling); \textbf{Sig.\ rate} = Sig./Viable. Floors: "
           r"precedes/co-occurs $n\geq20$, first-among $n\geq15$, orderable $n\geq5$.",
           "",
           r"\begin{center}",
           r"\begin{tabular}{@{}llrrrr@{}}",
           r"\toprule",
           r"\textbf{ID} & \textbf{Test} & \textbf{Replaces} & \textbf{Viable} & "
           r"\textbf{Sig.} & \textbf{Sig.\ rate} \\",
           r"\midrule"]
    for r in rows:
        out.append(f"{r['id']} & {_esc(r['test'])} & {_esc(r['replaces'])} & "
                   f"{r['viable']} & {r['sig']} & {r['rate']*100:.1f}\\% \\\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{center}", ""]
    out.append(
        r"\noindent\textbf{Reading.} \textbf{R4} (temporal-gap magnitude) and "
        r"\textbf{R3} (conditional antecedent) are the richest ($\geq37\%$ "
        r"significant, hundreds--thousands of significant cores). \textbf{R5} "
        r"(association vs independence) is the strongest \emph{co-occurs} "
        r"replacement: each core rests on the whole cohort ($n\approx1{,}000$), so "
        r"a significant result is robust even though only $25\%$ of top-event pairs "
        r"are positively associated. \textbf{R1} is solid; \textbf{R2} is thin (few "
        r"viable cores). \textbf{R6} is essentially a fixed S-V4 ($\approx29$ "
        r"significant). \textbf{R7} (twice-chance) and \textbf{R8} "
        r"(strongest-pair) are too hard / degenerate ($\leq5\%$; R8 yields "
        r"\emph{zero}) and are not recommended. Suggested adoption: "
        r"$\text{P-V2}\to\text{R3}$, $\text{C-V2}\to\text{R5}$, with \textbf{R4} "
        r"and \textbf{R1} as additional well-powered groups; drop R7 and R8. "
        r"(Counts are ceilings from a top-$K$ enumeration, so absolute \emph{Viable} "
        r"values are not the final benchmark size.)")
    out.append("")
    out.append(r"\noindent Claim schemas (all conditioned on a vaccine $v$):")
    out.append(r"\begin{description}")
    for r in rows:
        out.append(r"\item[" + r["id"] + r"] \emph{``" + _esc(r["claim"])
                   + r"''} --- median $n\approx" + str(r["median_n"]) + r"$.")
    out.append(r"\end{description}")
    return "\n".join(out) + "\n"


def main():
    rows = run()
    print(f"{'ID':3} {'viable':>7} {'sig':>6} {'sig%':>6} {'medn':>5}  replaces  claim")
    for r in rows:
        print(f"{r['id']:3} {r['viable']:7} {r['sig']:6} {r['rate']*100:5.1f}% "
              f"{r['median_n']:5}  {r['replaces']:7}  {r['claim']}")
    out = _REPO / "data" / "pilot" / "replacement_inventory.tex"
    out.write_text(_render_tex(rows), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
