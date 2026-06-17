"""Term-frequency queries and candidate-event ranking over a cohort.

A cohort is a list of vaers_ids (as produced by ``get_cohort``). Frequencies
are report frequencies: because of the first-mention rule a term appears at
most once per report, so a row count per term equals the number of reports
containing it. We load cohort ids into a TEMP table to sidestep SQLite's
~999 bound-variable limit on large cohorts.
"""

from __future__ import annotations

import sqlite3


def _load_cohort_temp(conn: sqlite3.Connection, cohort: list[int]) -> None:
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS _cohort (vid INTEGER PRIMARY KEY)")
    conn.execute("DELETE FROM _cohort")
    conn.executemany(
        "INSERT OR IGNORE INTO _cohort (vid) VALUES (?)", [(v,) for v in cohort]
    )


def term_counts(conn: sqlite3.Connection, cohort: list[int]) -> dict[str, int]:
    """Report-frequency of each term within the cohort, descending."""
    if not cohort:
        return {}
    _load_cohort_temp(conn, cohort)
    rows = conn.execute(
        """
        SELECT lt.term, COUNT(*) AS c
        FROM level_terms lt
        JOIN reports r USING (report_id)
        WHERE r.vaers_id IN (SELECT vid FROM _cohort)
        GROUP BY lt.term
        ORDER BY c DESC, lt.term ASC
        """
    ).fetchall()
    return {term: count for term, count in rows}


def top_terms(conn: sqlite3.Connection, cohort: list[int], k: int) -> list[str]:
    """The k most frequent terms in the cohort (ties broken by term name)."""
    return list(term_counts(conn, cohort))[:k]
