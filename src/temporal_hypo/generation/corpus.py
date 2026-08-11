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
