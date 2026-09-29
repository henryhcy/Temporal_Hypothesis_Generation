"""Candidate-family inventory: what the benchmark does NOT currently ask.

The shipped roster asks four temporal primitives -- precedes, co-occurs,
strict 3-event sequence, first/last-among-a-set -- at three scopes (report,
one vaccine cohort, two vaccine cohorts). This script measures candidate
families OUTSIDE that box, each against a permutation null, so a family is
adopted on evidence rather than on it sounding interesting.

Two null models, because the families need different ones:

- LEVEL SHUFFLE (single-cohort and within-cohort families). Permute which term
  sits at which occupied level, INSIDE each report. Preserves report size, the
  multiset of level sizes, term frequencies and every co-occurrence; destroys
  only the association between a specific term and a specific timeline position.
  That is exactly the signal an order/position claim asserts, so it is the
  honest null. Shuffling vaccine labels would do nothing here: these claims
  never mention a cohort contrast.
- LABEL SHUFFLE (cohort-contrast families). Permute the cohort labels,
  preserving cohort sizes -- the method already used in
  `08_multi_tier_inventory.md`.

CONTROLS are measured alongside the candidates, and they are the reason to
trust the rest of the table: `[ctl]` rows are shipped groups whose answer is
already known (P-V1 should look strong, P-M2 should land near 0.023). A null
model that failed the controls would invalidate every candidate score.

`p_perm` is reported TWICE on purpose:
  p_dec  -- rounds whose DECISIVE count (supported + refuted) matched or beat real
  p_sup  -- rounds whose SUPPORTED count matched or beat real
For a symmetric 0.5 null the two agree. For a THRESHOLD null (e.g. "at least
two thirds") they diverge violently, and that divergence is the finding: data
sitting at chance is significantly BELOW a 2/3 bar, so `refuted` becomes free
and only `p_sup` measures whether the family carries signal.

    python scripts/run_family_inventory.py [--rounds 1000] [--floor 10]
                                           [--only pos-half,imm-dir]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
import statistics as st
import time
from itertools import combinations
from pathlib import Path

from temporal_hypo.core.significance import (
    ALPHA,
    binom_exact_p,
    fisher_exact_2x2,
)
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.vaccines import VACCINES, VACCINE_PAIRS

_REPO = Path(__file__).resolve().parent.parent
TERM_MIN = 20        # a term enters the universe at >= this many reports in scope
SEED = 20260814
TOP_PAIRS_W = 40     # within-cohort two-proportion families compare the top-N pairs
TOP_TERMS_W = 60     # ... and the top-N terms, for the term-vs-term shapes
CSV_PATH = _REPO / "data" / "VAERS_Sampled_Data_v4.csv"


# ---------------------------------------------------------------------------
# report geometry
# ---------------------------------------------------------------------------

def rank_map(terms: dict[str, int]) -> tuple[dict[str, int], int]:
    """Term -> rank among OCCUPIED levels, plus the number of occupied levels.

    Ranks, not raw level indices: a report with levels {0, 2, 5} has three
    stages, and "the middle stage" is level 2 whatever the numbering. Using raw
    indices would make the half-timeline null wrong, because the chance of
    landing early would depend on the gaps.
    """
    levels = sorted(set(terms.values()))
    pos = {lv: i for i, lv in enumerate(levels)}
    return {t: pos[lv] for t, lv in terms.items()}, len(levels)


def pos_rank(level: int, terms: dict[str, int]) -> int:
    return sorted(set(terms.values())).index(level)


def covariates() -> tuple[dict[int, str], dict[int, str], dict[int, str]]:
    """vaers_id -> sex, -> median age band, -> age QUARTILE-EXTREME band.

    Read straight from the sampled VAERS csv, which the DB build dropped. Both
    are UNUSED by the shipped benchmark and both split the corpus more evenly
    than vaccine does, which is the point of testing them.
    """
    sex: dict[int, str] = {}
    age: dict[int, str] = {}
    age4: dict[int, str] = {}
    with open(CSV_PATH, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                vid = int(float(row["vaers_id"]))
            except (TypeError, ValueError):
                continue
            if row["sex"] in ("F", "M"):
                sex[vid] = row["sex"]
            try:
                yrs = float(row["age_yrs"])
            except (TypeError, ValueError):
                continue
            age[vid] = "<50" if yrs < 50 else ">=50"
            # corpus quartiles, measured: q1 = 35, median = 50, q3 = 63
            if yrs <= 35:
                age4[vid] = "<=35"
            elif yrs >= 63:
                age4[vid] = ">=63"
    return sex, age, age4


# ---------------------------------------------------------------------------
# universe
# ---------------------------------------------------------------------------

def build_universe(index: CorpusIndex, floor: int):
    """Scopes, their term universes, and the pair universe -- all from REAL data.

    Presence is invariant under the level shuffle, so a universe keyed on
    presence counts is identical in every round; only the ORDERED denominators
    move. That is what lets real and null be counted over the same cores.
    """
    scopes = {v: set(index.cohort(v)) for v in VACCINES}
    scopes["ALL"] = set(index.report_vaccine)

    universe = {}
    for scope, ids in scopes.items():
        freq: dict[str, int] = {}
        for rid in ids:
            for t in index.report_terms[rid]:
                freq[t] = freq.get(t, 0) + 1
        terms = sorted(t for t, n in freq.items() if n >= TERM_MIN)
        tset = set(terms)
        co: dict[tuple[str, str], int] = {}
        for rid in ids:
            present = sorted(t for t in index.report_terms[rid] if t in tset)
            for pr in combinations(present, 2):
                co[pr] = co.get(pr, 0) + 1
        pairs = sorted(p for p, n in co.items() if n >= floor)
        universe[scope] = {"ids": ids, "terms": terms, "tset": tset,
                           "pairs": pairs, "co": co}
    return universe


# ---------------------------------------------------------------------------
# one pass over a corpus state -> every counter the single-cohort families need
# ---------------------------------------------------------------------------

def tally(report_terms, universe, scope):
    """Counters for one scope under one corpus state (real or level-shuffled).

    term[t]  = [n_present, k_first, n_half, k_early, n_multi, exp_early]
    pair[p]  = [n_ordered, k_before, n_adj, k_a_first, n_diff, k_adj, exp_adj]

    `exp_early` accumulates the per-report CHANCE probability that an event lands
    in the earlier half. It is NOT 0.5: earlier stages hold more terms (measured
    means 2.45 terms at rank 0 against 1.74 at rank 3+), so a term drawn at random
    from a report's slots is more likely to be early. Corpus-wide the structural
    rate is 0.5327, so testing a position claim against 0.5 over-reports support by
    ~3.3pp of rate. Pair-ORDER claims are unaffected -- swapping A and B is a
    symmetry of the shuffle, so precedes really is 0.5 exactly.

    `exp_adj` accumulates the per-report CHANCE probability that two events at
    different stages land at ADJACENT stages. In a report with L occupied
    stages there are L(L-1) ordered placements of a distinct pair and 2(L-1)
    of them are adjacent, so that chance is 2/L -- report-dependent, which is
    why the adjacency family cannot be tested against a constant.
    """
    ids = universe[scope]["ids"]
    tset = universe[scope]["tset"]
    term: dict[str, list[int]] = {}
    pair: dict[tuple[str, str], list[float]] = {}
    for rid in ids:
        tmap = report_terms[rid]
        ranks, L = rank_map(tmap)
        if L < 2:
            continue
        present = sorted(t for t in tmap if t in tset)
        mid = (L - 1) / 2
        n_early = sum(1 for x in tmap.values() if pos_rank(x, tmap) < mid)
        n_late = sum(1 for x in tmap.values() if pos_rank(x, tmap) > mid)
        p_early = n_early / (n_early + n_late) if n_early + n_late else 0.0
        for t in present:
            row = term.get(t)
            if row is None:
                row = term[t] = [0, 0, 0, 0, 0, 0.0]
            r = ranks[t]
            row[0] += 1
            row[1] += int(r == 0)
            if r != mid:                       # the exact middle stage has no half
                row[2] += 1
                row[3] += int(r < mid)
                row[5] += p_early
            row[4] += int(L >= 3)
        p_adj = 2.0 / L
        for a, b in combinations(present, 2):
            row = pair.get((a, b))
            if row is None:
                row = pair[(a, b)] = [0, 0, 0, 0, 0, 0, 0.0]
            ra, rb = ranks[a], ranks[b]
            if ra == rb:
                continue                       # co-exist: no order, no distance
            row[0] += 1
            row[1] += int(ra < rb)
            row[4] += 1
            row[6] += p_adj
            if abs(ra - rb) == 1:
                row[2] += 1
                row[3] += int(ra < rb)
                row[5] += 1
    return term, pair


def contrast_term_rows(report_terms, universe, scope="ALL"):
    """Per-TERM report rows, for contrasting a single-event position across cohorts.

    The pair-based contrast rows cannot express a position claim: "does A appear
    earlier for younger patients" conditions on ONE event, which is the whole
    supply advantage of the position family. Rows carry both position statistics
    so `early` and `first` share one build.
    """
    rows: dict[str, list[tuple[int, bool, bool, bool]]] = {}
    tset = universe[scope]["tset"]
    for rid in universe[scope]["ids"]:
        tmap = report_terms[rid]
        ranks, L = rank_map(tmap)
        if L < 2:
            continue
        mid = (L - 1) / 2
        for t in tmap:
            if t not in tset:
                continue
            r = ranks[t]
            rows.setdefault(t, []).append(
                (rid, r < mid, r != mid, r == 0))
    return rows


def _contrast_term(rows, label_of, groups, floor, sel):
    """Two-cohort Fisher on a single-event position rate."""
    sup = ref = tot = 0
    for term_rows in rows.values():
        n = {g: 0 for g in groups}
        k = {g: 0 for g in groups}
        for rid, early, has_half, is_first in term_rows:
            g = label_of.get(rid)
            if g is None:
                continue
            if sel == "early":
                if not has_half:
                    continue
                n[g] += 1
                k[g] += int(early)
            else:
                n[g] += 1
                k[g] += int(is_first)
        for g1, g2 in combinations(groups, 2):
            if min(n[g1], n[g2]) < floor:
                continue
            tot += 1
            d = _decide(
                fisher_exact_2x2(k[g1], n[g1], k[g2], n[g2], alternative="greater"),
                fisher_exact_2x2(k[g1], n[g1], k[g2], n[g2], alternative="less"))
            sup += int(d == 1)
            ref += int(d == -1)
    return sup, ref, tot


def contrast_rows(report_terms, universe, scope="ALL"):
    """Per-pair report rows for the cohort-contrast families.

    Levels never move under a label shuffle, so these rows are built ONCE and
    only re-tallied per round -- the same trick `run_multi_inventory.py` uses.
    """
    rows: dict[tuple[str, str], list[tuple[int, bool, bool]]] = {}
    tset = universe[scope]["tset"]
    for rid in universe[scope]["ids"]:
        tmap = report_terms[rid]
        present = sorted(t for t in tmap if t in tset)
        for a, b in combinations(present, 2):
            rows.setdefault((a, b), []).append(
                (rid, tmap[a] < tmap[b], tmap[a] == tmap[b]))
    return rows


# ---------------------------------------------------------------------------
# families: each returns (supported, refuted, cores) for one corpus state
# ---------------------------------------------------------------------------

def _decide(p_for: float, p_against: float) -> int:
    """+1 supported, -1 refuted, 0 insufficient-by-power (three-decision rule)."""
    if p_for < ALPHA:
        return 1
    if p_against < ALPHA:
        return -1
    return 0


def _binom_family(term, pair, floor, unit, n_i, k_i, null, exp_i=None):
    """Single-cohort proportion family: one binomial per core against `null`.

    `null` is either a constant (0.5, 2/3, 0.75) or the string "chance", which
    means "use this core's own accumulated chance rate" -- the adjacency case.
    """
    src = term if unit == "term" else pair
    sup = ref = tot = 0
    for row in src.values():
        n, k = int(row[n_i]), int(row[k_i])
        if n < floor:
            continue
        p0 = row[exp_i] / n if null == "chance" else null
        if not 0.0 < p0 < 1.0:
            continue
        tot += 1
        d = _decide(binom_exact_p(k, n, p0, alternative="greater"),
                    binom_exact_p(k, n, p0, alternative="less"))
        sup += int(d == 1)
        ref += int(d == -1)
    return sup, ref, tot


def _pair_vs_pair(pair, floor, top, mode):
    """Within-cohort two-proportion families (the R1/R3 menu, never measured).

    mode 'disjoint' = R1, "A precedes B more often than C precedes D" over four
    distinct events. mode 'shared'  = R3, "B follows A more often than B follows
    C", which shares the consequent and is the conditional-antecedent claim.

    Restricted to the `top` best-supplied pairs: the full universe would be
    O(P^2) per round and the point is a screen, not a census. The cap is
    reported so the coverage is not overstated.
    """
    ok = [(p, row) for p, row in pair.items() if int(row[0]) >= floor]
    ok.sort(key=lambda kv: (-kv[1][0], kv[0]))
    ok = ok[:top]
    sup = ref = tot = 0
    for (p1, r1), (p2, r2) in combinations(ok, 2):
        shared = set(p1) & set(p2)
        if mode == "disjoint" and shared:
            continue
        if mode == "shared" and len(shared) != 1:
            continue
        n1, k1, n2, k2 = int(r1[0]), int(r1[1]), int(r2[0]), int(r2[1])
        tot += 1
        d = _decide(fisher_exact_2x2(k1, n1, k2, n2, alternative="greater"),
                    fisher_exact_2x2(k1, n1, k2, n2, alternative="less"))
        sup += int(d == 1)
        ref += int(d == -1)
    return sup, ref, tot


def _term_vs_term(term, floor, n_i, k_i, top):
    """R2: "A is the first event more often than B is", within one cohort.

    Capped at the `top` best-supplied terms for the same reason `_pair_vs_pair`
    is capped: the uncapped universe is C(176,2) = 15,400 cores per round, which
    is both slow and a misleading denominator to quote.
    """
    ok = [(t, row) for t, row in term.items() if int(row[n_i]) >= floor]
    ok.sort(key=lambda kv: (-kv[1][n_i], kv[0]))
    ok = ok[:top]
    sup = ref = tot = 0
    for (a, r1), (b, r2) in combinations(sorted(ok), 2):
        n1, k1, n2, k2 = int(r1[n_i]), int(r1[k_i]), int(r2[n_i]), int(r2[k_i])
        tot += 1
        d = _decide(fisher_exact_2x2(k1, n1, k2, n2, alternative="greater"),
                    fisher_exact_2x2(k1, n1, k2, n2, alternative="less"))
        sup += int(d == 1)
        ref += int(d == -1)
    return sup, ref, tot


def _presence_pairs(pair, floor):
    """R5: "A and B co-occur more than independence predicts", within a cohort.

    Fisher on presence x presence: P(B | A present) against P(B | A absent).
    Rows are [n_both, n_a, n_b, N]. This is the one candidate that is NOT a
    temporal claim -- it is the co-occurs replacement from the 07-13 menu, kept
    in the screen because the roster migration plans to adopt it as C-V2.
    """
    sup = ref = tot = 0
    for row in pair.values():
        both, n_a, n_b, N = (int(x) for x in row[:4])
        if min(n_a, n_b) < floor or N - n_a < floor:
            continue
        tot += 1
        d = _decide(
            fisher_exact_2x2(both, n_a, n_b - both, N - n_a, alternative="greater"),
            fisher_exact_2x2(both, n_a, n_b - both, N - n_a, alternative="less"))
        sup += int(d == 1)
        ref += int(d == -1)
    return sup, ref, tot


def _contrast(rows, label_of, groups, floor, sel):
    """Two-cohort Fisher over an arbitrary labelling (vaccine, sex, age band)."""
    sup = ref = tot = 0
    for pair_rows in rows.values():
        n = {g: 0 for g in groups}
        k = {g: 0 for g in groups}
        for rid, before, equal in pair_rows:
            g = label_of.get(rid)
            if g is None:
                continue
            if sel == "precedes":
                if equal:
                    continue
                n[g] += 1
                k[g] += int(before)
            else:
                n[g] += 1
                k[g] += int(equal)
        for g1, g2 in combinations(groups, 2):
            if min(n[g1], n[g2]) < floor:
                continue
            tot += 1
            d = _decide(
                fisher_exact_2x2(k[g1], n[g1], k[g2], n[g2], alternative="greater"),
                fisher_exact_2x2(k[g1], n[g1], k[g2], n[g2], alternative="less"))
            sup += int(d == 1)
            ref += int(d == -1)
    return sup, ref, tot


# ---------------------------------------------------------------------------
# family registry
# ---------------------------------------------------------------------------
# (key, label, null model, scope, callable(state) -> (sup, ref, tot))
#
# `state` is (term, pair) counters for level-shuffle families, and
# (rows, label_of) for label-shuffle families.

SINGLE = [
    ("ctl-precedes", "[ctl] P-V1 precedes vs 0.5          shipped baseline",
     "pair", lambda t, p, f: _binom_family(t, p, f, "pair", 0, 1, 0.5)),
    ("pos-half", "N1 half-timeline position          A is in the earlier half",
     "term", lambda t, p, f: _binom_family(t, p, f, "term", 2, 3, 0.5)),
    ("pos-half-struct", "N1b half-timeline vs STRUCTURAL rate  bias-corrected null",
     "term", lambda t, p, f: _binom_family(t, p, f, "term", 2, 3, "chance", 5)),
    ("imm-dir", "N2 immediate-succession direction  A right before B, not after",
     "pair", lambda t, p, f: _binom_family(t, p, f, "pair", 2, 3, 0.5)),
    ("adj-rate", "N3 adjacency vs chance             A,B consecutive > chance 2/L",
     "pair", lambda t, p, f: _binom_family(t, p, f, "pair", 4, 5, "chance", 6)),
    ("dom-two-thirds", "N4 dominance threshold >= 2/3      A precedes B in >= 2/3",
     "pair", lambda t, p, f: _binom_family(t, p, f, "pair", 0, 1, 2 / 3)),
    ("dom-three-quarters", "N4b dominance threshold >= 3/4     A precedes B in >= 3/4",
     "pair", lambda t, p, f: _binom_family(t, p, f, "pair", 0, 1, 0.75)),
    ("r1-pair-vs-pair", "R1 pair-vs-pair precedence         A<B more than C<D",
     "pair", lambda t, p, f: _pair_vs_pair(p, f, TOP_PAIRS_W, "disjoint")),
    ("r3-antecedent", "R3 conditional antecedent          B follows A more than C",
     "pair", lambda t, p, f: _pair_vs_pair(p, f, TOP_PAIRS_W, "shared")),
    ("r2-first-rate", "R2 event-vs-event first rate       A is first more than B",
     "term", lambda t, p, f: _term_vs_term(t, f, 0, 1, TOP_TERMS_W)),
]

# Families whose statistic depends only on PRESENCE, not on position. The level
# shuffle is the WRONG null for these -- it leaves presence untouched, so the
# null count equals the real count by construction (measured: burden came back
# 3881 real against a null mean of 3881.0). They need a degree-preserving
# bipartite edge swap instead, which rewires which report contains which term
# while holding both report size and term frequency fixed.
PRESENCE = [
    ("r5-association", "R5 presence association            A,B co-occur > independent",
     lambda t, p, f: _presence_pairs(p, f)),
    ("burden", "N5 timeline burden                 A in >=3-stage reports more than B",
     lambda t, p, f: _term_vs_term(t, f, 0, 4, TOP_TERMS_W)),
]

CONTRAST = [
    ("ctl-vaccine-prec", "[ctl] P-M2 vaccine precedes        shipped baseline",
     "vaccine", "precedes"),
    ("ctl-vaccine-cooc", "[ctl] C-M2 vaccine co-occurs       dropped 08-11",
     "vaccine", "cooc"),
    ("age-prec", "X1 age-band precedes               <50 vs >=50",
     "age", "precedes"),
    ("age-cooc", "X2 age-band co-occurs              <50 vs >=50",
     "age", "cooc"),
    ("sex-prec", "X3 sex precedes                    F vs M",
     "sex", "precedes"),
    ("sex-cooc", "X4 sex co-occurs                   F vs M",
     "sex", "cooc"),
    # Quartile extremes rather than a median split: if age shifts symptom order at
    # all, the biggest available contrast is where it should show. It costs
    # denominator (each band is ~a quarter of the corpus), so a null result here is
    # ambiguous between "no effect" and "no power" -- but a POSITIVE result would
    # have been unambiguous, which is what makes the shape worth running.
    ("age4-prec", "X5 age-quartile precedes           <=35 vs >=63",
     "age4", "precedes"),
    # Single-event position contrasts. These condition on ONE event, so they keep
    # the position family's supply advantage: the denominator is every report
    # containing A, not every report ordering A against a second named event.
    ("age-pos", "X6 age-band position               A earlier for <50?",
     "age", "term:early"),
    ("sex-pos", "X7 sex position                    A earlier for F?",
     "sex", "term:early"),
    ("vax-pos", "[ctl] M-H vaccine position         failed 08-11 at 0.120",
     "vaccine", "term:early"),
]


def level_shuffle(report_terms, rng):
    """Permute term -> level WITHIN each report, preserving the level multiset."""
    out = {}
    for rid, tmap in report_terms.items():
        terms = list(tmap)
        levels = list(tmap.values())
        rng.shuffle(levels)
        out[rid] = dict(zip(terms, levels))
    return out


# ---------------------------------------------------------------------------
# presence null: degree-preserving bipartite edge swap
# ---------------------------------------------------------------------------

def presence_tally(presence, universe, scope, levels_of, top_terms):
    """Presence-only counters, shaped to reuse the two-proportion helpers."""
    tset = universe[scope]["tset"]
    ids = universe[scope]["ids"]
    term: dict[str, list[int]] = {t: [0, 0, 0, 0, 0] for t in tset}
    n_scope = 0
    freq: dict[str, int] = {}
    both: dict[tuple[str, str], int] = {}
    for rid in ids:
        present = sorted(t for t in presence[rid] if t in tset)
        if len(present) == 0:
            continue
        n_scope += 1
        multi = levels_of[rid] >= 3
        for t in present:
            freq[t] = freq.get(t, 0) + 1
            row = term[t]
            row[0] += 1
            row[4] += int(multi)
        for pr in combinations(present, 2):
            both[pr] = both.get(pr, 0) + 1
    pair = {pr: [n, freq.get(pr[0], 0), freq.get(pr[1], 0), n_scope]
            for pr, n in both.items()}
    return term, pair


def edge_swap(presence, rng, passes=2):
    """Randomise which report contains which term, preserving BOTH degrees.

    Standard double-edge swap on the report-term bipartite graph: report size
    and term frequency are exactly preserved, so the shuffled corpus has the
    same number of reports of each length and the same term prevalences -- only
    the pairing is random. That makes it the right null for a presence claim,
    where the whole question is whether two terms co-occur more than their
    marginals imply.
    """
    sets = {rid: set(ts) for rid, ts in presence.items()}
    edges = [(rid, t) for rid, ts in sets.items() for t in ts]
    for _ in range(passes * len(edges)):
        i = rng.randrange(len(edges))
        j = rng.randrange(len(edges))
        (r1, t1), (r2, t2) = edges[i], edges[j]
        if r1 == r2 or t1 == t2:
            continue
        if t2 in sets[r1] or t1 in sets[r2]:
            continue
        sets[r1].discard(t1); sets[r1].add(t2)
        sets[r2].discard(t2); sets[r2].add(t1)
        edges[i] = (r1, t2)
        edges[j] = (r2, t1)
    return sets


def label_permutations(ids, sizes, rounds, rng):
    out = []
    ids = list(ids)
    for _ in range(rounds):
        s = ids[:]
        rng.shuffle(s)
        m, i = {}, 0
        for g, cnt in sizes:
            for rid in s[i:i + cnt]:
                m[rid] = g
            i += cnt
        out.append(m)
    return out


def _report(name, sup, ref, tot, nulls_dec, nulls_sup, rounds):
    dec = sup + ref
    nd = sorted(nulls_dec)
    ns = sorted(nulls_sup)
    p_dec = (sum(1 for x in nd if x >= dec) + 1) / (rounds + 1)
    p_sup = (sum(1 for x in ns if x >= sup) + 1) / (rounds + 1)
    print(f"{name:52s} {sup:5d} {ref:5d} {dec:5d}/{tot:<6d} "
          f"{st.mean(nd):8.1f} {p_dec:6.3f} {p_sup:6.3f}")
    return {"family": name, "supported": sup, "refuted": ref, "decisive": dec,
            "cores": tot, "null_dec_mean": round(st.mean(nd), 1),
            "null_sup_mean": round(st.mean(ns), 1),
            "null_dec_p95": nd[int(0.95 * len(nd))],
            "p_dec": round(p_dec, 4), "p_sup": round(p_sup, 4)}


def run(db: Path, rounds: int, floor: int, only: set[str] | None,
        scopes_wanted: set[str]) -> dict:
    conn = sqlite3.connect(str(db))
    index = CorpusIndex.load(conn)
    conn.close()
    universe = build_universe(index, floor)
    print(f"universe (>= {TERM_MIN} reports in scope, pair co-occurrence >= {floor}):")
    for scope in ("ALL", *VACCINES):
        u = universe[scope]
        print(f"  {scope:8s} {len(u['ids']):5d} reports  {len(u['terms']):4d} terms"
              f"  {len(u['pairs']):5d} pairs")
    rng = random.Random(SEED)
    print(f"\n{rounds}-round permutation null, floor {floor}, alpha {ALPHA} per side")
    print(f"{'family':52s} {'sup':>5s} {'ref':>5s} {'decisive':>12s} "
          f"{'null':>8s} {'p_dec':>6s} {'p_sup':>6s}")
    print("-" * 104)

    out: dict[str, list[dict]] = {"single": [], "contrast": []}

    # ---- level-shuffle families, per scope ---------------------------------
    # Two scopes are measured because they are two different CLAIMS, not two
    # views of one. "ALL" pools every report ("across COVID-19 vaccine reports")
    # and is §6 lever 4; "VACCINE" sums the three per-cohort scopes and is what
    # the shipped V groups actually ask ("After {v}, ..."). Pooling roughly
    # triples each denominator, so the gap between the two rows is the price the
    # benchmark pays for naming a vaccine.
    todo = [f for f in SINGLE if only is None or f[0] in only]
    for scope_name, scope_keys in (("ALL", ["ALL"]), ("VACCINE", list(VACCINES))):
        if not todo or scope_name not in scopes_wanted:
            continue
        t0 = time.time()
        real = [tally(index.report_terms, universe, s) for s in scope_keys]
        nulls = []
        for _ in range(rounds):
            sh = level_shuffle(index.report_terms, rng)
            nulls.append([tally(sh, universe, s) for s in scope_keys])
        print(f"  (level-shuffle null for scope {scope_name} built in "
              f"{time.time() - t0:.0f}s)")
        for key, label, _unit, fn in todo:
            sup = ref = tot = 0
            for term, pair in real:
                s2, r2, t2 = fn(term, pair, floor)
                sup += s2; ref += r2; tot += t2
            nd, ns = [], []
            for state in nulls:
                s2 = r2 = 0
                for term, pair in state:
                    a, b, _ = fn(term, pair, floor)
                    s2 += a; r2 += b
                nd.append(s2 + r2)
                ns.append(s2)
            row = _report(f"{label}  [{scope_name}]", sup, ref, tot, nd, ns, rounds)
            row["scope"] = scope_name
            out["single"].append(row)

    # ---- presence families (edge-swap null) --------------------------------
    todo_p = [f for f in PRESENCE if only is None or f[0] in only]
    if todo_p:
        levels_of = {rid: len(set(t.values())) if t else 0
                     for rid, t in index.report_terms.items()}
        presence = {rid: set(t) for rid, t in index.report_terms.items()}
        t0 = time.time()
        real_p = presence_tally(presence, universe, "ALL", levels_of, TOP_TERMS_W)
        p_rounds = max(1, rounds // 4)      # the swap is ~4x the cost of a shuffle
        nulls_p = [presence_tally(edge_swap(presence, rng), universe, "ALL",
                                  levels_of, TOP_TERMS_W)
                   for _ in range(p_rounds)]
        print(f"  (edge-swap null built in {time.time() - t0:.0f}s, "
              f"{p_rounds} rounds)")
        for key, label, fn in todo_p:
            sup, ref, tot = fn(*real_p, floor)
            nd, ns = [], []
            for term, pair in nulls_p:
                s2, r2, _ = fn(term, pair, floor)
                nd.append(s2 + r2)
                ns.append(s2)
            row = _report(f"{label}  [ALL]", sup, ref, tot, nd, ns, p_rounds)
            row["scope"] = "ALL"
            row["rounds"] = p_rounds
            out["presence"] = out.get("presence", []) + [row]

    # ---- label-shuffle families -------------------------------------------
    todo_c = [f for f in CONTRAST if only is None or f[0] in only]
    if todo_c:
        rows = contrast_rows(index.report_terms, universe, "ALL")
        trows = contrast_term_rows(index.report_terms, universe, "ALL")
        sex, age, age4 = covariates()
        axes = {
            "vaccine": (dict(index.report_vaccine), list(VACCINES)),
            "sex": (sex, ["F", "M"]),
            "age": (age, ["<50", ">=50"]),
            "age4": (age4, ["<=35", ">=63"]),
        }
        perms: dict[str, list] = {}
        for axis, (label_of, groups) in axes.items():
            ids = [r for r in label_of if r in universe["ALL"]["ids"]]
            sizes = [(g, sum(1 for r in ids if label_of[r] == g)) for g in groups]
            perms[axis] = label_permutations(ids, sizes, rounds, rng)
        for key, label, axis, sel in todo_c:
            label_of, groups = axes[axis]
            if sel.startswith("term:"):
                fn = lambda lo, s=sel: _contrast_term(
                    trows, lo, groups, floor, s.split(":", 1)[1])
            else:
                fn = lambda lo, s=sel: _contrast(rows, lo, groups, floor, s)
            sup, ref, tot = fn(label_of)
            nd, ns = [], []
            for p in perms[axis]:
                s2, r2, _ = fn(p)
                nd.append(s2 + r2)
                ns.append(s2)
            out["contrast"].append(_report(label, sup, ref, tot, nd, ns, rounds))

    print("\np_sup <= 0.05: the family's SUPPORTED labels carry more signal than "
          "shuffled data.\nFor threshold nulls read p_sup, not p_dec: at-chance "
          "data is significantly BELOW a 2/3 bar,\nso `refuted` is free and p_dec "
          "is meaningless.")
    print(f"\nNOTE vaccine contrast counts {len(VACCINE_PAIRS)} comparisons per "
          "pair, sex/age count 1.")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=_REPO / "data" / "medtempo.db")
    ap.add_argument("--out", type=Path, default=_REPO / "data" / "pilot")
    ap.add_argument("--rounds", type=int, default=1000)
    ap.add_argument("--floor", type=int, default=10)
    ap.add_argument("--scopes", type=str, default="ALL,VACCINE",
                    help="ALL pools the corpus (lever 4); VACCINE sums the "
                         "three per-cohort scopes, which is what P-V1 asks")
    ap.add_argument("--only", type=str, default=None,
                    help="comma-separated family keys, for iterating fast")
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else None
    rows = run(args.db, args.rounds, args.floor, only,
               set(args.scopes.split(",")))
    args.out.mkdir(parents=True, exist_ok=True)
    dest = args.out / "family_inventory.json"
    dest.write_text(json.dumps({"rounds": args.rounds, "floor": args.floor,
                                "term_min": TERM_MIN, **rows}, indent=2),
                    encoding="utf-8")
    print(f"\nWritten to {dest}")


if __name__ == "__main__":
    main()
