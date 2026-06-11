"""Cohort-level aggregation functions and verdict helpers.

All fraction functions return (fraction, n) or None when the denominator
is below the minimum threshold of 10 (locked in decisions.md).

None encodes the 'insufficient' verdict at the cohort level.
"""

from __future__ import annotations

import sqlite3
from typing import Literal

from temporal_hypo.core.leveled_order import first_among, load_levels, precedes, sequence_holds

_MIN_N = 10


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
    """Fraction of cohort reports where A→B→C holds strictly (locked rule 3).

    Denominator: reports containing all three events.
    Returns None if denominator < 10.
    """
    all_present = 0
    seq_count = 0
    for vid in cohort:
        levels = load_levels(conn, vid)
        result = sequence_holds(levels, [A, B, C])
        if result != "missing":
            all_present += 1
            if result is True:
                seq_count += 1
    if all_present < _MIN_N:
        return None
    return (seq_count / all_present, all_present)


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


def prop_verdict(
    claimed: float, actual: float
) -> Literal["supported", "refuted"]:
    """Within 5 percentage points → supported (decisions.md rule 7)."""
    return "supported" if abs(claimed - actual) <= 0.05 else "refuted"


def differ_verdict(
    p1: float, p2: float
) -> Literal["supported", "refuted"]:
    """|p1 - p2| > 10 percentage points → supported (decisions.md rule 8)."""
    return "supported" if abs(p1 - p2) > 0.10 else "refuted"
