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
            """
        ).fetchall()
        for vaers_id, vaccine, level_index, term in rows:
            report_vaccine[vaers_id] = vaccine
            report_terms.setdefault(vaers_id, {})[term] = level_index
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
# Cohort fraction functions (mirror core.aggregation; None below _MIN_N)
# ---------------------------------------------------------------------------

def precedes_fraction(
    index: CorpusIndex, a: str, b: str, cohort: list[int]
) -> tuple[float, int] | None:
    ordered = 0
    a_before_b = 0
    for vid in cohort:
        rel = relation(index.report_terms[vid], a, b)
        if rel in ("before", "after"):
            ordered += 1
            if rel == "before":
                a_before_b += 1
    if ordered < _MIN_N:
        return None
    return (a_before_b / ordered, ordered)


def co_occurs_fraction(
    index: CorpusIndex, a: str, b: str, cohort: list[int]
) -> tuple[float, int] | None:
    both = 0
    co = 0
    for vid in cohort:
        rel = relation(index.report_terms[vid], a, b)
        if rel != "missing":
            both += 1
            if rel == "co_exist":
                co += 1
    if both < _MIN_N:
        return None
    return (co / both, both)


def sequence_fraction(
    index: CorpusIndex, a: str, b: str, c: str, cohort: list[int]
) -> tuple[float, int] | None:
    all_present = 0
    seq = 0
    for vid in cohort:
        t = index.report_terms[vid]
        ia, ib, ic = t.get(a), t.get(b), t.get(c)
        if ia is None or ib is None or ic is None:
            continue
        all_present += 1
        if ia < ib < ic:
            seq += 1
    if all_present < _MIN_N:
        return None
    return (seq / all_present, all_present)


def _extreme_among_fractions(
    index: CorpusIndex, terms: list[str], cohort: list[int], *, last: bool
) -> dict | None:
    denom = 0
    ties = 0
    counts: dict[str, int] = {t: 0 for t in terms}
    for vid in cohort:
        tmap = index.report_terms[vid]
        idxs = [tmap.get(t) for t in terms]
        if any(i is None for i in idxs):
            continue
        denom += 1
        target = max(idxs) if last else min(idxs)
        winners = [t for t, i in zip(terms, idxs) if i == target]
        if len(winners) > 1:
            ties += 1
        else:
            counts[winners[0]] += 1
    if denom < _MIN_N:
        return None
    fracs: dict = {t: counts[t] / denom for t in terms}
    fracs["tie_rate"] = ties / denom
    fracs["n"] = denom
    fracs["counts"] = counts
    return fracs


def first_among_fractions(
    index: CorpusIndex, terms: list[str], cohort: list[int]
) -> dict | None:
    return _extreme_among_fractions(index, terms, cohort, last=False)


def last_among_fractions(
    index: CorpusIndex, terms: list[str], cohort: list[int]
) -> dict | None:
    return _extreme_among_fractions(index, terms, cohort, last=True)


def ordering_distribution(
    index: CorpusIndex, terms: list[str], cohort: list[int]
) -> dict | None:
    n = 0
    tie = 0
    counts: dict[tuple[str, ...], int] = {}
    for vid in cohort:
        tmap = index.report_terms[vid]
        idxs = [tmap.get(t) for t in terms]
        if any(i is None for i in idxs):
            continue
        n += 1
        if len(set(idxs)) < len(idxs):
            tie += 1
            continue
        order = tuple(t for t, _ in sorted(zip(terms, idxs), key=lambda kv: kv[1]))
        counts[order] = counts.get(order, 0) + 1
    if n < _MIN_N:
        return None
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
        "n": n,
        "modal": modal,
        "modal_count": modal_count,
        "modal_share": modal_count / n,
        "modal_tie": modal_tie,
    }
