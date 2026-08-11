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
    # 1 ordered report: reported, not discarded (2026-08-11). The FLOOR is the
    # shared gate's job now, so the helper's contract is "measure and report n".
    conn, ids = _make_db(reports)
    assert precedes_fraction(conn, "A", "B", ids) == (1.0, 1)
    conn.close()


def test_precedes_fraction_reports_sub_floor_n():
    # 9 ordered reports is below the pairwise floor of 10, but n must survive:
    # it is what lets the labeler say `sparse` rather than dropping the core into
    # an unnamed bucket.
    reports = _pfizer_reports(9, A_before_B=5)
    conn, ids = _make_db(reports)
    frac, n = precedes_fraction(conn, "A", "B", ids)
    assert n == 9 and abs(frac - 5 / 9) < 1e-9
    conn.close()


def test_fraction_is_none_only_when_the_denominator_is_empty():
    # n = 0 is `not_locatable`, and a proportion over nothing does not exist.
    reports = [(1, "Pfizer", [["A"], ["Z"]])]      # B never appears
    conn, ids = _make_db(reports)
    assert precedes_fraction(conn, "A", "B", ids) == (None, 0)
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


def test_co_occurs_fraction_reports_sub_floor_n():
    reports = [(i + 1, "Pfizer", [["A", "B"]]) for i in range(9)]
    conn, ids = _make_db(reports)
    assert co_occurs_fraction(conn, "A", "B", ids) == (1.0, 9)
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


def test_sequence_fraction_gapped_subsequence():
    """Strict ordering captures a<b<c from a longer chain with GAPS (a<b<d<e<c),
    and EXCLUDES co-occurrence (no weak ordering)."""
    # 8 reports A<B<D<E<C: a<b<c holds via the gapped subsequence
    reports = [(i + 1, "Pfizer", [["A"], ["B"], ["D"], ["E"], ["C"]]) for i in range(8)]
    # 4 reports where B,C co-occur: not orderable, excluded from the denominator
    reports += [(i + 9, "Pfizer", [["A"], ["B", "C"]]) for i in range(4)]
    conn, ids = _make_db(reports)
    frac, n = sequence_fraction(conn, "A", "B", "C", ids)
    assert n == 8                      # only the orderable reports count
    assert abs(frac - 1.0) < 1e-9      # a<b<c holds in all 8 (gaps ignored)
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


def test_first_among_fractions_reports_sub_floor_n():
    reports = [(i + 1, "Pfizer", [["A"], ["B"]]) for i in range(9)]
    conn, ids = _make_db(reports)
    r = first_among_fractions(conn, ["A", "B"], ids)
    assert r["n"] == 9 and r["A"] == 1.0 and r["B"] == 0.0


# ---------------------------------------------------------------------------
# Verdict helpers
# ---------------------------------------------------------------------------

def test_bool_verdict():
    assert bool_verdict(0.6) == "supported"
    assert bool_verdict(0.4) == "refuted"
    assert bool_verdict(0.5) == "insufficient"


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


def test_last_among_fractions_reports_sub_floor_n():
    reports = [(i + 1, "Pfizer", [["A"], ["B"]]) for i in range(9)]
    conn, ids = _make_db(reports)
    r = last_among_fractions(conn, ["A", "B"], ids)
    assert r["n"] == 9 and r["B"] == 1.0 and r["A"] == 0.0


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
    assert dist["n"] == 11          # ORDERABLE denominator: tie report excluded
    assert dist["tie"] == 1
    assert dist["modal_count"] == 11
    assert abs(dist["modal_share"] - 11 / 11) < 1e-9
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


def test_ordering_distribution_reports_sub_floor_n():
    # 4 orderable reports is below the sequence floor of 5, but n survives
    reports = [(i + 1, "Pfizer", [["A"], ["B"], ["C"]]) for i in range(4)]
    conn, ids = _make_db(reports)
    d = ordering_distribution(conn, ["A", "B", "C"], ids)
    assert d["n"] == 4 and d["modal"] == ("A", "B", "C")
    conn.close()


def test_ordering_distribution_with_no_orderable_reports():
    # every report has all three at the SAME level -> orderable n = 0
    reports = [(i + 1, "Pfizer", [["A", "B", "C"]]) for i in range(6)]
    conn, ids = _make_db(reports)
    d = ordering_distribution(conn, ["A", "B", "C"], ids)
    assert d["n"] == 0 and d["modal"] is None and d["modal_share"] is None
    assert d["tie"] == 6
    conn.close()
