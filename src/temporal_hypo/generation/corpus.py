"""In-memory corpus index for fast cohort enumeration.

The cohort-aggregation functions in ``core.aggregation`` call ``load_levels``
(a DB round-trip) once per report per query. Enumerating thousands of event
pairs/triples over thousand-report cohorts would issue millions of round-trips.
This module preloads the whole corpus once into dictionaries and provides
fraction functions that mirror the LOCKED computation rules exactly, reading
only memory.

Equivalence with ``core.aggregation`` is asserted in the tests
(``tests/generation/test_corpus.py``) so the two implementations cannot drift.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

_MIN_N = 10
# Sequence groups use STRICT ordering over an ORDERABLE denominator (reports
# where the three events occur at distinct levels; co-occurrence excluded, as in
# pairwise-precedes). Because fully-ordered triples are rare in a co-occurrence-
# heavy corpus, the sequence viability floor is smaller (decisions.md).
SEQ_MIN_N = 5


@dataclass
class CorpusIndex:
    """Preloaded view of the MedTempo DB keyed for in-memory aggregation."""

    # vaers_id -> {term: level_index}
    report_terms: dict[int, dict[str, int]]
    # vaers_id -> vaccine name
    report_vaccine: dict[int, str]

    @classmethod
    def load(cls, conn: sqlite3.Connection) -> "CorpusIndex":
        report_terms: dict[int, dict[str, int]] = {}
        report_vaccine: dict[int, str] = {}
        rows = conn.execute(
            """
            SELECT r.vaers_id, r.vaccine, lt.level_index, lt.term
            FROM reports r
            JOIN level_terms lt USING (report_id)
            ORDER BY r.vaers_id, lt.level_index
            """
        ).fetchall()
        for vaers_id, vaccine, level_index, term in rows:
            report_vaccine[vaers_id] = vaccine
            terms = report_terms.setdefault(vaers_id, {})
            # FIRST-MENTION RULE (decisions.md seed): when a term appears at more
            # than one level, only the earliest is recorded. This used to assign
            # unconditionally, so the LAST row won -- and with no ORDER BY, which row
            # that was depended on SQLite's plan, making gold labels
            # non-reproducible. Caught by the Part C cross-check on 2026-08-11,
            # where the DB-backed mirror (which reads the levels list and is
            # first-mention by construction) disagreed with this index.
            if term not in terms or level_index < terms[term]:
                terms[term] = level_index
        # reports with no level_terms still need a vaccine entry
        for (vaers_id, vaccine) in conn.execute(
            "SELECT vaers_id, vaccine FROM reports"
        ).fetchall():
            report_vaccine.setdefault(vaers_id, vaccine)
            report_terms.setdefault(vaers_id, {})
        return cls(report_terms=report_terms, report_vaccine=report_vaccine)

    # -- cohorts and frequencies -------------------------------------------

    def cohort(self, vaccine: str | None = None) -> list[int]:
        if vaccine is None:
            return list(self.report_vaccine)
        return [v for v, vax in self.report_vaccine.items() if vax == vaccine]

    def term_freq(self, cohort: list[int]) -> dict[str, int]:
        freq: dict[str, int] = {}
        for vid in cohort:
            for term in self.report_terms.get(vid, ()):  # keys = terms
                freq[term] = freq.get(term, 0) + 1
        return freq

    def top_terms(self, cohort: list[int], k: int) -> list[str]:
        freq = self.term_freq(cohort)
        # frequency desc, then term asc for determinism
        return [t for t, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))][:k]


# ---------------------------------------------------------------------------
# Per-report relations (dict-based mirrors of leveled_order primitives)
# ---------------------------------------------------------------------------

def relation(terms: dict[str, int], a: str, b: str) -> str:
    """'before' | 'after' | 'co_exist' | 'missing' for a relative to b."""
    ia = terms.get(a)
    ib = terms.get(b)
    if ia is None or ib is None:
        return "missing"
    if ia < ib:
        return "before"
    if ia > ib:
        return "after"
    return "co_exist"


# ---------------------------------------------------------------------------
# Cohort fraction functions (mirror core.aggregation)
#
# These MEASURE; they do not gate (2026-08-11, decisions.md step B). Each returns
# its conditioned denominator `n` whatever its size, including 0, and leaves the
# floor to the single shared gate in `core.min_n`. They used to return None below
# a private floor, which threw n away -- and that made `sparse` (0 < n < floor)
# indistinguishable from `not_locatable` (n = 0) downstream, so the labeler could
# not name either sub-type. The fraction is None exactly when n = 0, since a
# proportion over an empty denominator does not exist.
# ---------------------------------------------------------------------------

def precedes_fraction(
    index: CorpusIndex, a: str, b: str, cohort: list[int]
) -> tuple[float | None, int]:
    ordered = 0
    a_before_b = 0
    for vid in cohort:
        rel = relation(index.report_terms[vid], a, b)
        if rel in ("before", "after"):
            ordered += 1
            if rel == "before":
                a_before_b += 1
    if ordered == 0:
        return (None, 0)
    return (a_before_b / ordered, ordered)


def co_occurs_fraction(
    index: CorpusIndex, a: str, b: str, cohort: list[int]
) -> tuple[float | None, int]:
    both = 0
    co = 0
    for vid in cohort:
        rel = relation(index.report_terms[vid], a, b)
        if rel != "missing":
            both += 1
            if rel == "co_exist":
                co += 1
    if both == 0:
        return (None, 0)
    return (co / both, both)


def sequence_fraction(
    index: CorpusIndex, a: str, b: str, c: str, cohort: list[int]
) -> tuple[float | None, int]:
    """Strict A<B<C over the ORDERABLE denominator (distinct levels; gaps ok).

    Denominator counts only reports where all three occur at distinct levels, so
    co-occurrence is excluded (not counted as evidence for or against the order),
    mirroring how pairwise-precedes excludes co-exist. Gaps are fine: a<b<d<e<c
    still counts as a<b<c. Reports n always; the fraction is None when n = 0.
    """
    orderable = 0
    seq = 0
    for vid in cohort:
        t = index.report_terms[vid]
        ia, ib, ic = t.get(a), t.get(b), t.get(c)
        if ia is None or ib is None or ic is None:
            continue
        if ia == ib or ib == ic or ia == ic:
            continue   # co-occurrence: triple not fully orderable, excluded
        orderable += 1
        if ia < ib < ic:
            seq += 1
    if orderable == 0:
        return (None, 0)
    return (seq / orderable, orderable)


def relation_distribution(
    index: CorpusIndex, a: str, b: str, cohort: list[int]
) -> dict:
    """Counts of {before, after, co_exist} for A vs B over both-present reports.

    Same conditioning as ``co_occurs_fraction`` (denominator = both present),
    but the full 3-cell distribution instead of only the co_exist share. Added
    2026-08-14 for C-V3's modal-vs-runner-up statistic (decisions.md issue 13):
    "co-occurrence is the dominant relation" is an ARGMAX over the three cells,
    so its gold computation needs all three counts. Reports n always; callers
    gate on the shared family floor.
    """
    counts = {"before": 0, "after": 0, "co_exist": 0}
    for vid in cohort:
        rel = relation(index.report_terms[vid], a, b)
        if rel != "missing":
            counts[rel] += 1
    return {"counts": counts, "n": sum(counts.values())}


def presence_association(
    index: CorpusIndex, a: str, b: str, cohort: list[int]
) -> tuple[int, int, int, int]:
    """(n1, k1, n2, k2) for the association-vs-independence 2x2 (C-V2, R5).

    Arm 1 = reports containing A (k1 of them also contain B); arm 2 = reports
    NOT containing A (k2 contain B). "A and B occur together more often than
    their separate rates predict" is P(B | A) > P(B | not A), a one-sided
    Fisher on this table. Symmetric in A and B (the transposed table gives the
    same association direction), so orientation is by NEGATION, like C-V1.
    """
    n1 = k1 = n2 = k2 = 0
    for vid in cohort:
        t = index.report_terms[vid]
        if a in t:
            n1 += 1
            k1 += int(b in t)
        else:
            n2 += 1
            k2 += int(b in t)
    return n1, k1, n2, k2


def pair_distances(
    index: CorpusIndex, a: str, b: str, cohort: list[int]
) -> list[int]:
    """Per-report rank-distance d = level(a) - level(b) for reports containing
    both (co-exist -> d=0). The position track keeps ALL present reports."""
    out: list[int] = []
    for vid in cohort:
        t = index.report_terms[vid]
        ia, ib = t.get(a), t.get(b)
        if ia is None or ib is None:
            continue
        out.append(ia - ib)
    return out


def triple_positions(
    index: CorpusIndex, terms: list[str], cohort: list[int]
) -> list[tuple[int, ...]]:
    """Per-report tuple of level indices for reports containing all terms
    (co-occurrence kept -> tied ranks downstream)."""
    out: list[tuple[int, ...]] = []
    for vid in cohort:
        t = index.report_terms[vid]
        vals = [t.get(x) for x in terms]
        if any(v is None for v in vals):
            continue
        out.append(tuple(vals))
    return out


def _extreme_among_fractions(
    index: CorpusIndex, terms: list[str], cohort: list[int], *, last: bool
) -> dict:
    denom = 0      # reports with a UNIQUE first/last event
    present = 0    # reports containing all candidates (denom + ties)
    ties = 0
    counts: dict[str, int] = {t: 0 for t in terms}
    for vid in cohort:
        tmap = index.report_terms[vid]
        idxs = [tmap.get(t) for t in terms]
        if any(i is None for i in idxs):
            continue
        present += 1
        target = max(idxs) if last else min(idxs)
        winners = [t for t, i in zip(terms, idxs) if i == target]
        if len(winners) > 1:
            ties += 1          # unresolvable: leaves the denominator (2026-08-11)
        else:
            denom += 1
            counts[winners[0]] += 1
    if denom == 0:
        return {"n": 0, "n_present": present, "ties": ties, "counts": counts,
                "tie_rate": (ties / present if present else None),
                **{t: None for t in terms}}
    fracs: dict = {t: counts[t] / denom for t in terms}
    # tie_rate is over reports where all candidates were PRESENT, since ties are
    # no longer part of n -- otherwise the rate would be relative to a denominator
    # that excludes them and could exceed 1.
    fracs["tie_rate"] = ties / present if present else None
    fracs["n"] = denom
    fracs["n_present"] = present
    fracs["ties"] = ties
    fracs["counts"] = counts
    return fracs


def first_among_fractions(
    index: CorpusIndex, terms: list[str], cohort: list[int]
) -> dict:
    return _extreme_among_fractions(index, terms, cohort, last=False)


def last_among_fractions(
    index: CorpusIndex, terms: list[str], cohort: list[int]
) -> dict:
    return _extreme_among_fractions(index, terms, cohort, last=True)


def ordering_distribution(
    index: CorpusIndex, terms: list[str], cohort: list[int]
) -> dict:
    # ORDERABLE denominator: n counts only reports where all terms are at
    # distinct levels; co-occurrence (tie) reports are excluded from n.
    n_orderable = 0
    tie = 0
    counts: dict[tuple[str, ...], int] = {}
    for vid in cohort:
        tmap = index.report_terms[vid]
        idxs = [tmap.get(t) for t in terms]
        if any(i is None for i in idxs):
            continue
        if len(set(idxs)) < len(idxs):
            tie += 1
            continue
        n_orderable += 1
        order = tuple(t for t, _ in sorted(zip(terms, idxs), key=lambda kv: kv[1]))
        counts[order] = counts.get(order, 0) + 1
    if n_orderable == 0:
        return {"counts": {}, "tie": tie, "n": 0, "modal": None,
                "modal_count": 0, "modal_share": None, "modal_tie": False}
    modal = None
    modal_count = 0
    modal_tie = False
    if counts:
        modal_count = max(counts.values())
        winners = [p for p, cc in counts.items() if cc == modal_count]
        modal = winners[0]
        modal_tie = len(winners) > 1
    return {
        "counts": counts,
        "tie": tie,
        "n": n_orderable,
        "modal": modal,
        "modal_count": modal_count,
        "modal_share": modal_count / n_orderable,
        "modal_tie": modal_tie,
    }


# ---------------------------------------------------------------------------
# v1.2 families (decisions.md 2026-10-07): report GEOMETRY on first-mention
# RANKS, and the four new measurements. Ported from
# scripts/run_family_inventory.py (tally / rank_map) so the gold matches what
# the 2,000-round screens measured.
# ---------------------------------------------------------------------------

def rank_map(terms: dict[str, int]) -> tuple[dict[str, int], int]:
    """term -> rank among the report's OCCUPIED first-mention levels, and L.

    Ranks, not raw level indices: a report with first mentions at levels
    {0, 2, 5} has three stages, and "the middle stage" is level 2 whatever
    the numbering. The half-timeline null depends on this.
    """
    levels = sorted(set(terms.values()))
    pos = {lv: i for i, lv in enumerate(levels)}
    return {t: pos[lv] for t, lv in terms.items()}, len(levels)


def report_half(terms: dict[str, int]) -> tuple[dict[str, int], int, float, float | None]:
    """(ranks, L, mid, p_early) for one report.

    ``p_early`` is the report's CHANCE rate of an event landing in the earlier
    half: early slots / (early + late slots) over ALL its first-mention terms,
    the exact-middle rank counting for neither. None when L < 2 (no halves).
    Earlier stages hold more terms (2.45 at rank 0 vs ~1.74 from rank 3), so this
    is above 0.5 corpus-wide (0.5327) and varies per report -- which is why a
    single-event position claim cannot be tested against 0.5 (doc 10 s4.3).
    """
    ranks, L = rank_map(terms)
    if L < 2:
        return ranks, L, 0.0, None
    mid = (L - 1) / 2
    n_early = sum(1 for r in ranks.values() if r < mid)
    n_late = sum(1 for r in ranks.values() if r > mid)
    p_early = n_early / (n_early + n_late) if (n_early + n_late) else None
    return ranks, L, mid, p_early


def early_half_fraction(
    index: CorpusIndex, a: str, cohort: list[int]
) -> tuple[float | None, int, int, float]:
    """N1 position: (frac, n, k, exp_sum) for "A falls in the earlier half".

    Denominator: reports containing A with L >= 2 whose A is NOT on the exact
    middle rank (a middle event is in neither half). Numerator: rank(A) < mid.
    ``exp_sum`` accumulates each denominator report's p_early; the core's
    data-derived null is p0 = exp_sum / n.
    """
    n = k = 0
    exp = 0.0
    for vid in cohort:
        t = index.report_terms[vid]
        if a not in t:
            continue
        ranks, L, mid, p_early = report_half(t)
        if p_early is None or ranks[a] == mid:
            continue
        n += 1
        k += int(ranks[a] < mid)
        exp += p_early
    return ((k / n) if n else None), n, k, exp


def immediate_fraction(
    index: CorpusIndex, a: str, b: str, cohort: list[int]
) -> tuple[float | None, int]:
    """N2 immediate succession: among reports where A and B occupy CONSECUTIVE
    ranks (|rank(A) - rank(B)| == 1), the share with A first. Null 0.5."""
    n = k = 0
    for vid in cohort:
        t = index.report_terms[vid]
        if a not in t or b not in t:
            continue
        ranks, _L = rank_map(t)
        ra, rb = ranks[a], ranks[b]
        if abs(ra - rb) != 1:
            continue
        n += 1
        k += int(ra < rb)
    return ((k / n) if n else None), n


def adjacency_rate(
    index: CorpusIndex, a: str, b: str, cohort: list[int]
) -> tuple[float | None, int, int, float]:
    """N3 adjacency vs chance: (frac, n, k, exp_sum).

    Denominator: reports with A and B at DISTINCT ranks (the ordered-pair
    denominator). Numerator: the two are adjacent. Each report's chance of
    adjacency for a distinct pair is 2/L (L(L-1) ordered placements, 2(L-1)
    adjacent), so the core's null is p0 = exp_sum / n.
    """
    n = k = 0
    exp = 0.0
    for vid in cohort:
        t = index.report_terms[vid]
        if a not in t or b not in t:
            continue
        ranks, L = rank_map(t)
        ra, rb = ranks[a], ranks[b]
        if ra == rb:
            continue
        n += 1
        k += int(abs(ra - rb) == 1)
        exp += 2.0 / L
    return ((k / n) if n else None), n, k, exp
