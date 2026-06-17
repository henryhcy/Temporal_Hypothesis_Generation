"""Tests for temporal_hypo.core.aggregation."""

import sqlite3

import pytest

from temporal_hypo.core.aggregation import (
    bool_verdict,
    co_occurs_fraction,
    differ_verdict,
    direction_verdict,
    first_among_fractions,
    get_cohort,
    last_among_fractions,
    ordering_distribution,
    precedes_fraction,
    prop_verdict,
    sequence_fraction,
)


# ---------------------------------------------------------------------------
# Minimal in-memory DB fixture
# ---------------------------------------------------------------------------

def _make_db(reports: list[tuple]) -> tuple[sqlite3.Connection, list[int]]:
    """Build an in-memory DB from a list of (vaers_id, vaccine, levels) tuples.

    levels is a list[list[str]] leveled order.
    Returns (conn, vaers_ids).
    """
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE reports (
            report_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            vaers_id   INTEGER UNIQUE NOT NULL,
            vaccine    TEXT NOT NULL,
            narrative  TEXT NOT NULL,
            num_groups INTEGER NOT NULL
        );
        CREATE TABLE level_terms (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id   INTEGER NOT NULL,
            level_index INTEGER NOT NULL,
            term        TEXT NOT NULL
        );
    """)
    vaers_ids = []
    for vaers_id, vaccine, levels in reports:
        conn.execute(
            "INSERT INTO reports (vaers_id, vaccine, narrative, num_groups) VALUES (?,?,?,?)",
            (vaers_id, vaccine, "narrative", len(levels)),
        )
        rid = conn.execute(
            "SELECT report_id FROM reports WHERE vaers_id=?", (vaers_id,)
        ).fetchone()[0]
        for li, terms in enumerate(levels):
            for term in terms:
                conn.execute(
                    "INSERT INTO level_terms (report_id, level_index, term) VALUES (?,?,?)",
                    (rid, li, term),
                )
        vaers_ids.append(vaers_id)
    conn.commit()
    return conn, vaers_ids


def _pfizer_reports(n: int, *, A_before_B: int) -> list[tuple]:
    """Create n synthetic Pfizer reports; A_before_B of them have A before B."""
    reports = []
    for i in range(n):
        if i < A_before_B:
            levels = [["A"], ["B"]]
        else:
            levels = [["B"], ["A"]]
        reports.append((i + 1, "Pfizer", levels))
    return reports


# ---------------------------------------------------------------------------
# get_cohort
# ---------------------------------------------------------------------------

def test_get_cohort_all():
    reports = [(1, "Pfizer", [["A"]]), (2, "Moderna", [["B"]])]
    conn, ids = _make_db(reports)
    assert set(get_cohort(conn)) == {1, 2}
    conn.close()


def test_get_cohort_by_vaccine():
    reports = [(1, "Pfizer", [["A"]]), (2, "Moderna", [["B"]]), (3, "Pfizer", [["C"]])]
    conn, _ = _make_db(reports)
    assert set(get_cohort(conn, "Pfizer")) == {1, 3}
    assert get_cohort(conn, "Janssen") == []
    conn.close()


# ---------------------------------------------------------------------------
# precedes_fraction (locked rule 1)
# ---------------------------------------------------------------------------

def test_precedes_fraction_basic():
    reports = _pfizer_reports(12, A_before_B=8)
    conn, ids = _make_db(reports)
    result = precedes_fraction(conn, "A", "B", ids)
    assert result is not None
    frac, n = result
    assert n == 12
    assert abs(frac - 8 / 12) < 1e-9
    conn.close()


def test_precedes_fraction_excludes_co_exist():
    """Co-exist pairs must not be in denominator (locked rule 1)."""
    reports = [
        (1, "Pfizer", [["A"], ["B"]]),   # A before B
        (2, "Pfizer", [["A", "B"]]),      # co-exist — excluded from denom
    ]
    # Only 1 ordered report, below threshold → None
    conn, ids = _make_db(reports)
    assert precedes_fraction(conn, "A", "B", ids) is None
    conn.close()


def test_precedes_fraction_insufficient():
    reports = _pfizer_reports(9, A_before_B=5)
    conn, ids = _make_db(reports)
    assert precedes_fraction(conn, "A", "B", ids) is None
    conn.close()


# ---------------------------------------------------------------------------
# co_occurs_fraction (locked rule 2)
# ---------------------------------------------------------------------------

def test_co_occurs_fraction_includes_co_exist():
    """Co-exist pairs ARE the event of interest and stay in denominator."""
    reports = [
        (i + 1, "Pfizer", [["A", "B"]] if i < 7 else [["A"], ["B"]])
        for i in range(12)
    ]
    conn, ids = _make_db(reports)
    result = co_occurs_fraction(conn, "A", "B", ids)
    assert result is not None
    frac, n = result
    assert n == 12
    assert abs(frac - 7 / 12) < 1e-9
    conn.close()


def test_co_occurs_fraction_insufficient():
    reports = [(i + 1, "Pfizer", [["A", "B"]]) for i in range(9)]
    conn, ids = _make_db(reports)
    assert co_occurs_fraction(conn, "A", "B", ids) is None
    conn.close()


# ---------------------------------------------------------------------------
# sequence_fraction (locked rule 3)
# ---------------------------------------------------------------------------

def test_sequence_fraction_basic():
    reports = [
        (i + 1, "Pfizer", [["A"], ["B"], ["C"]] if i < 6 else [["A"], ["C"], ["B"]])
        for i in range(12)
    ]
    conn, ids = _make_db(reports)
    result = sequence_fraction(conn, "A", "B", "C", ids)
    assert result is not None
    frac, n = result
    assert n == 12
    assert abs(frac - 6 / 12) < 1e-9
    conn.close()


def test_sequence_fraction_excludes_missing():
    """Reports missing any of the three events are not counted."""
    reports = [
        (1, "Pfizer", [["A"], ["B"]]),  # missing C — excluded
    ] + [
        (i + 2, "Pfizer", [["A"], ["B"], ["C"]]) for i in range(11)
    ]
    conn, ids = _make_db(reports)
    result = sequence_fraction(conn, "A", "B", "C", ids)
    assert result is not None
    _, n = result
    assert n == 11
    conn.close()


# ---------------------------------------------------------------------------
# first_among_fractions (locked rule 4)
# ---------------------------------------------------------------------------

def test_first_among_fractions_basic():
    reports = [
        (i + 1, "Pfizer", [["A"], ["B"], ["C"]] if i < 6 else [["B"], ["A"], ["C"]])
        for i in range(12)
    ]
    conn, ids = _make_db(reports)
    result = first_among_fractions(conn, ["A", "B", "C"], ids)
    assert result is not None
    assert abs(result["A"] - 6 / 12) < 1e-9
    assert abs(result["B"] - 6 / 12) < 1e-9
    assert result["C"] == 0.0
    assert result["tie_rate"] == 0.0
    conn.close()


def test_first_among_fractions_ties_excluded():
    """Tie-reports are excluded from per-term counts (locked rule 4)."""
    reports = [
        (1, "Pfizer", [["A", "B"], ["C"]]),   # tie between A and B
    ] + [
        (i + 2, "Pfizer", [["A"], ["B"], ["C"]]) for i in range(11)
    ]
    conn, ids = _make_db(reports)
    result = first_among_fractions(conn, ["A", "B", "C"], ids)
    assert result is not None
    assert int(result["n"]) == 12
    assert abs(result["tie_rate"] - 1 / 12) < 1e-9
    # 11 non-tie reports, A is first in all 11
    assert abs(result["A"] - 11 / 12) < 1e-9
    conn.close()


def test_first_among_fractions_insufficient():
    reports = [(i + 1, "Pfizer", [["A"], ["B"]]) for i in range(9)]
    conn, ids = _make_db(reports)
    assert first_among_fractions(conn, ["A", "B"], ids) is None
    conn.close()


# ---------------------------------------------------------------------------
# Verdict helpers
# ---------------------------------------------------------------------------

def test_bool_verdict():
    assert bool_verdict(0.6) == "supported"
    assert bool_verdict(0.4) == "refuted"
    assert bool_verdict(0.5) == "insufficient"


def test_prop_verdict():
    assert prop_verdict(0.60, 0.63) == "supported"   # within 5pp
    assert prop_verdict(0.60, 0.66) == "refuted"     # just over 5pp
    # Avoid testing exact floating-point boundary (0.65-0.60 is not exactly 0.05)
    assert prop_verdict(0.60, 0.645) == "supported"  # 4.5pp — clearly inside
    assert prop_verdict(0.60, 0.656) == "refuted"    # 5.6pp — clearly outside


def test_differ_verdict():
    assert differ_verdict(0.70, 0.55) == "supported"  # 15pp > 10pp
    assert differ_verdict(0.70, 0.62) == "refuted"    # 8pp ≤ 10pp
    assert differ_verdict(0.70, 0.60) == "refuted"    # exactly 10pp — not strictly greater


def test_direction_verdict():
    assert direction_verdict(0.60, 0.40) == "supported"   # cohort 1 higher
    assert direction_verdict(0.40, 0.60) == "refuted"     # cohort 1 lower
    assert direction_verdict(0.50, 0.50) == "insufficient"  # exact tie


# ---------------------------------------------------------------------------
# last_among_fractions (mirror of first_among, locked rule 4 by symmetry)
# ---------------------------------------------------------------------------

def test_last_among_fractions_basic():
    reports = [
        (i + 1, "Pfizer", [["A"], ["B"], ["C"]] if i < 6 else [["A"], ["C"], ["B"]])
        for i in range(12)
    ]
    conn, ids = _make_db(reports)
    result = last_among_fractions(conn, ["A", "B", "C"], ids)
    assert result is not None
    assert abs(result["C"] - 6 / 12) < 1e-9   # C last in first 6
    assert abs(result["B"] - 6 / 12) < 1e-9   # B last in last 6
    assert result["A"] == 0.0
    assert result["tie_rate"] == 0.0
    conn.close()


def test_last_among_fractions_ties_excluded():
    reports = [
        (1, "Pfizer", [["A"], ["B", "C"]]),   # tie between B and C for last
    ] + [
        (i + 2, "Pfizer", [["A"], ["B"], ["C"]]) for i in range(11)
    ]
    conn, ids = _make_db(reports)
    result = last_among_fractions(conn, ["A", "B", "C"], ids)
    assert result is not None
    assert int(result["n"]) == 12
    assert abs(result["tie_rate"] - 1 / 12) < 1e-9
    assert abs(result["C"] - 11 / 12) < 1e-9   # C last in the 11 strict reports
    conn.close()


def test_last_among_fractions_insufficient():
    reports = [(i + 1, "Pfizer", [["A"], ["B"]]) for i in range(9)]
    conn, ids = _make_db(reports)
    assert last_among_fractions(conn, ["A", "B"], ids) is None
    conn.close()


# ---------------------------------------------------------------------------
# ordering_distribution (sequence modal / consistency)
# ---------------------------------------------------------------------------

def test_ordering_distribution_modal():
    # 8 reports A→B→C, 4 reports A→C→B
    reports = [
        (i + 1, "Pfizer", [["A"], ["B"], ["C"]] if i < 8 else [["A"], ["C"], ["B"]])
        for i in range(12)
    ]
    conn, ids = _make_db(reports)
    dist = ordering_distribution(conn, ["A", "B", "C"], ids)
    assert dist is not None
    assert dist["n"] == 12
    assert dist["tie"] == 0
    assert dist["modal"] == ("A", "B", "C")
    assert dist["modal_count"] == 8
    assert abs(dist["modal_share"] - 8 / 12) < 1e-9
    assert dist["modal_tie"] is False
    conn.close()


def test_ordering_distribution_ties_bucket():
    # reports where two of the three co-occur go to the tie bucket
    reports = [
        (1, "Pfizer", [["A", "B"], ["C"]]),   # A,B co-occur — tie bucket
    ] + [
        (i + 2, "Pfizer", [["A"], ["B"], ["C"]]) for i in range(11)
    ]
    conn, ids = _make_db(reports)
    dist = ordering_distribution(conn, ["A", "B", "C"], ids)
    assert dist is not None
    assert dist["n"] == 12
    assert dist["tie"] == 1
    assert dist["modal_count"] == 11
    assert abs(dist["modal_share"] - 11 / 12) < 1e-9
    conn.close()


def test_ordering_distribution_modal_tie_flag():
    # equal split between two orderings → modal_tie True
    reports = [
        (i + 1, "Pfizer", [["A"], ["B"], ["C"]] if i < 6 else [["C"], ["B"], ["A"]])
        for i in range(12)
    ]
    conn, ids = _make_db(reports)
    dist = ordering_distribution(conn, ["A", "B", "C"], ids)
    assert dist is not None
    assert dist["modal_count"] == 6
    assert dist["modal_tie"] is True
    conn.close()


def test_ordering_distribution_insufficient():
    reports = [(i + 1, "Pfizer", [["A"], ["B"], ["C"]]) for i in range(9)]
    conn, ids = _make_db(reports)
    assert ordering_distribution(conn, ["A", "B", "C"], ids) is None
    conn.close()
