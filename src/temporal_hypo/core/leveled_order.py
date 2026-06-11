"""Per-report query functions over leveled-order representations.

A leveled order is a list[list[str]] where each inner list is a co-exist
cluster and the outer list is ordered from earliest to latest.

Example:
    levels = [["headache"], ["fever", "rash"], ["fatigue"]]
    # headache first; fever and rash co-occur next; fatigue last
"""

from __future__ import annotations

import sqlite3
from typing import Literal


def load_levels(conn: sqlite3.Connection, vaers_id: int) -> list[list[str]]:
    """Return the leveled order for one report, or [] if not found."""
    cur = conn.execute(
        """SELECT level_index, term
           FROM level_terms
           JOIN reports USING (report_id)
           WHERE vaers_id = ?
           ORDER BY level_index""",
        (vaers_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return []
    max_level = max(r[0] for r in rows)
    levels: list[list[str]] = [[] for _ in range(max_level + 1)]
    for level_index, term in rows:
        levels[level_index].append(term)
    return levels


def level_of(levels: list[list[str]], term: str) -> int | None:
    """Return the 0-based level index of term, or None if absent."""
    for i, cluster in enumerate(levels):
        if term in cluster:
            return i
    return None


def precedes(
    levels: list[list[str]], A: str, B: str
) -> Literal["before", "after", "co_exist", "missing"]:
    """Return the temporal relation of A relative to B.

    Returns:
        'before'   if level_of(A) < level_of(B)
        'after'    if level_of(A) > level_of(B)
        'co_exist' if level_of(A) == level_of(B)
        'missing'  if either term is absent
    """
    idx_a = level_of(levels, A)
    idx_b = level_of(levels, B)
    if idx_a is None or idx_b is None:
        return "missing"
    if idx_a < idx_b:
        return "before"
    if idx_a > idx_b:
        return "after"
    return "co_exist"


def first_among(
    levels: list[list[str]], terms: list[str]
) -> list[str] | Literal["missing"]:
    """Return the subset of terms that occur at the earliest level.

    Returns 'missing' if any term in the list is absent from levels.
    Returns a list with more than one element when multiple terms tie
    for the earliest position.
    """
    indices: dict[str, int] = {}
    for term in terms:
        idx = level_of(levels, term)
        if idx is None:
            return "missing"
        indices[term] = idx
    min_idx = min(indices.values())
    return [t for t, i in indices.items() if i == min_idx]


def sequence_holds(
    levels: list[list[str]], terms: list[str]
) -> bool | Literal["missing"]:
    """Return True iff terms appear in strictly increasing level order.

    Per decisions.md: strict inequalities required; co-occurrence within
    the sequence does not satisfy strict ordering.
    Returns 'missing' if any term is absent.
    """
    indices: list[int | None] = [level_of(levels, t) for t in terms]
    if any(i is None for i in indices):
        return "missing"
    for j in range(len(indices) - 1):
        if indices[j] >= indices[j + 1]:  # type: ignore[operator]
            return False
    return True
