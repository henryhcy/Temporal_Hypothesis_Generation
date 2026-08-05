"""Cohort-level aggregation functions and verdict helpers.

All fraction functions return (fraction, n) or None when the denominator
is below the minimum threshold of 10 (locked in decisions.md).

None encodes the 'insufficient' verdict at the cohort level.
"""

from __future__ import annotations

import sqlite3
from typing import Literal

from temporal_hypo.core.leveled_order import (
    first_among,
    last_among,
    level_of,
    load_levels,
    precedes,
    sequence_holds,
)

_MIN_N = 10
# Sequence uses a smaller floor over the ORDERABLE denominator (see corpus.py).
SEQ_MIN_N = 5


def get_cohort(conn: sqlite3.Connection, vaccine: str | None = None) -> list[int]:
    """Return vaers_ids for the given vaccine, or all reports if vaccine is None."""
    if vaccine is None:
        rows = conn.execute("SELECT vaers_id FROM reports").fetchall()
    else:
        rows = conn.execute(
            "SELECT vaers_id FROM reports WHERE vaccine = ?", (vaccine,)
        ).fetchall()
    return [r[0] for r in rows]


def precedes_fraction(
    conn: sqlite3.Connection,
    A: str,
    B: str,
    cohort: list[int],
) -> tuple[float, int] | None:
    """Fraction of cohort reports where A precedes B (locked rule 1).

    Denominator: reports where both A and B appear AND the pair is ordered
    (co-exist pairs are excluded). Returns None if denominator < 10.
    """
    ordered = 0
    a_before_b = 0
    for vid in cohort:
        levels = load_levels(conn, vid)
        rel = precedes(levels, A, B)
        if rel in ("before", "after"):
            ordered += 1
            if rel == "before":
                a_before_b += 1
    if ordered < _MIN_N:
        return None
    return (a_before_b / ordered, ordered)


def co_occurs_fraction(
    conn: sqlite3.Connection,
    A: str,
    B: str,
    cohort: list[int],
) -> tuple[float, int] | None:
    """Fraction of cohort reports where A and B co-exist (locked rule 2).

    Denominator: reports where both A and B appear (co-exist pairs kept).
    Returns None if denominator < 10.
    """
    both_present = 0
    co_exist_count = 0
    for vid in cohort:
        levels = load_levels(conn, vid)
        rel = precedes(levels, A, B)
        if rel != "missing":
            both_present += 1
            if rel == "co_exist":
                co_exist_count += 1
    if both_present < _MIN_N:
        return None
    return (co_exist_count / both_present, both_present)


def sequence_fraction(
    conn: sqlite3.Connection,
    A: str,
    B: str,
    C: str,
    cohort: list[int],
) -> tuple[float, int] | None:
    """Fraction of ORDERABLE cohort reports where A→B→C holds strictly.

    Denominator: reports where A, B, C occur at DISTINCT levels (co-occurrence
    excluded, as in pairwise-precedes). Gaps are fine (a<b<d<e<c counts as
    a<b<c). Returns None below SEQ_MIN_N.
    """
    orderable = 0
    seq_count = 0
    for vid in cohort:
        levels = load_levels(conn, vid)
        ia = level_of(levels, A)
        ib = level_of(levels, B)
        ic = level_of(levels, C)
        if ia is None or ib is None or ic is None:
            continue
        if ia == ib or ib == ic or ia == ic:
            continue   # co-occurrence: triple not fully orderable, excluded
        orderable += 1
        if ia < ib < ic:
            seq_count += 1
    if orderable < SEQ_MIN_N:
        return None
    return (seq_count / orderable, orderable)


def first_among_fractions(
    conn: sqlite3.Connection,
    terms: list[str],
    cohort: list[int],
) -> dict[str, float] | None:
    """Per-term fraction of reports where the term occurs first (locked rule 4).

    Denominator: reports containing all named candidates. Tie-reports are
    excluded from per-term counts but tracked separately as 'tie_rate'.
    Returns None if denominator < 10.

    Return format: {term: fraction, ..., 'tie_rate': float, 'n': int}
    """
    denom = 0
    ties = 0
    term_counts: dict[str, int] = {t: 0 for t in terms}

    for vid in cohort:
        levels = load_levels(conn, vid)
        result = first_among(levels, terms)
        if result == "missing":
            continue
        denom += 1
        if len(result) > 1:
            ties += 1
        else:
            term_counts[result[0]] += 1

    if denom < _MIN_N:
        return None

    fracs: dict[str, float] = {t: term_counts[t] / denom for t in terms}
    fracs["tie_rate"] = ties / denom
    fracs["n"] = float(denom)
    return fracs


def last_among_fractions(
    conn: sqlite3.Connection,
    terms: list[str],
    cohort: list[int],
) -> dict[str, float] | None:
    """Per-term fraction of reports where the term occurs last.

    Mirror of first_among_fractions using last_among. Denominator: reports
    containing all named candidates. Tie-reports are excluded from per-term
    counts but tracked separately as 'tie_rate'. Returns None if denom < 10.

    Return format: {term: fraction, ..., 'tie_rate': float, 'n': int}
    """
    denom = 0
    ties = 0
    term_counts: dict[str, int] = {t: 0 for t in terms}

    for vid in cohort:
        levels = load_levels(conn, vid)
        result = last_among(levels, terms)
        if result == "missing":
            continue
        denom += 1
        if len(result) > 1:
            ties += 1
        else:
            term_counts[result[0]] += 1

    if denom < _MIN_N:
        return None

    fracs: dict[str, float] = {t: term_counts[t] / denom for t in terms}
    fracs["tie_rate"] = ties / denom
    fracs["n"] = float(denom)
    return fracs


def ordering_distribution(
    conn: sqlite3.Connection,
    terms: list[str],
    cohort: list[int],
) -> dict | None:
    """Distribution over strict orderings of `terms` across the cohort.

    Denominator (n): reports containing all of `terms`. Reports where any two
    of the terms share a level go to the 'tie' bucket (no strict total order
    among the three). Reports with all terms at distinct levels are counted
    under the permutation key giving their temporal order (a tuple of terms,
    earliest first). Returns None if n < 10.

    Used by the sequence modal/consistency groups (S-V3, S-V4, S-M3). The
    "modal ordering" is the argmax strict permutation; "consistency" is its
    share of n. This pins the otherwise-ambiguous definition: a single
    ordering dominates iff modal_share > 0.5 (mirrors the BOOL majority rule).

    Return format:
        {'counts': {perm_tuple: int, ...}, 'tie': int, 'n': int,
         'modal': perm_tuple | None, 'modal_count': int,
         'modal_share': float, 'modal_tie': bool}
    """
    # ORDERABLE denominator: n counts only distinct-level reports; co-occurrence
    # (tie) reports are excluded from n (mirrors pairwise-precedes).
    n_orderable = 0
    tie = 0
    counts: dict[tuple[str, ...], int] = {}
    for vid in cohort:
        levels = load_levels(conn, vid)
        idxs = [level_of(levels, t) for t in terms]
        if any(i is None for i in idxs):
            continue
        if len(set(idxs)) < len(idxs):
            tie += 1
            continue
        n_orderable += 1
        order = tuple(
            t for t, _ in sorted(zip(terms, idxs), key=lambda pair: pair[1])
        )
        counts[order] = counts.get(order, 0) + 1

    if n_orderable < SEQ_MIN_N:
        return None

    modal: tuple[str, ...] | None = None
    modal_count = 0
    modal_tie = False
    if counts:
        modal_count = max(counts.values())
        winners = [p for p, c in counts.items() if c == modal_count]
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
# Verdict helpers (pure functions, no DB)
# ---------------------------------------------------------------------------

def bool_verdict(
    fraction: float,
) -> Literal["supported", "refuted", "insufficient"]:
    """Majority rule per decisions.md rule 6: > 0.5 → supported."""
    if fraction > 0.5:
        return "supported"
    if fraction < 0.5:
        return "refuted"
    return "insufficient"


def differ_verdict(
    p1: float, p2: float
) -> Literal["supported", "refuted"]:
    """|p1 - p2| > 10 percentage points → supported (decisions.md rule 8)."""
    return "supported" if abs(p1 - p2) > 0.10 else "refuted"


def direction_verdict(
    p1: float, p2: float
) -> Literal["supported", "refuted", "insufficient"]:
    """Multi-vaccine CHOICE direction: claim asserts cohort 1 > cohort 2.

    Supported if p1 > p2, refuted if p1 < p2, insufficient on an exact tie.
    Used by P-M2 / C-M2 (which cohort shows the higher proportion).
    The confidence interval on the difference (Wilson-Newcombe) carries the
    uncertainty; this verdict only encodes the point-estimate direction.
    """
    if p1 > p2:
        return "supported"
    if p1 < p2:
        return "refuted"
    return "insufficient"
