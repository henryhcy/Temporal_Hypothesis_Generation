"""Tests for temporal_hypo.core.leveled_order."""

import sqlite3

import pytest

from temporal_hypo.core.leveled_order import (
    first_among,
    last_among,
    level_of,
    load_levels,
    precedes,
    sequence_holds,
)

# Sample: headache first; fever+rash co-occur next; fatigue last
LEVELS = [["headache"], ["fever", "rash"], ["fatigue"]]


# ---------------------------------------------------------------------------
# level_of
# ---------------------------------------------------------------------------

def test_level_of_present():
    assert level_of(LEVELS, "headache") == 0
    assert level_of(LEVELS, "fever") == 1
    assert level_of(LEVELS, "rash") == 1
    assert level_of(LEVELS, "fatigue") == 2


def test_level_of_absent():
    assert level_of(LEVELS, "nausea") is None


def test_level_of_empty_levels():
    assert level_of([], "headache") is None


# ---------------------------------------------------------------------------
# precedes
# ---------------------------------------------------------------------------

def test_precedes_before():
    assert precedes(LEVELS, "headache", "fever") == "before"
    assert precedes(LEVELS, "headache", "fatigue") == "before"
    assert precedes(LEVELS, "fever", "fatigue") == "before"


def test_precedes_after():
    assert precedes(LEVELS, "fatigue", "headache") == "after"
    assert precedes(LEVELS, "rash", "headache") == "after"


def test_precedes_co_exist():
    assert precedes(LEVELS, "fever", "rash") == "co_exist"
    assert precedes(LEVELS, "rash", "fever") == "co_exist"


def test_precedes_missing_a():
    assert precedes(LEVELS, "nausea", "fever") == "missing"


def test_precedes_missing_b():
    assert precedes(LEVELS, "fever", "nausea") == "missing"


def test_precedes_both_missing():
    assert precedes(LEVELS, "nausea", "vomiting") == "missing"


# ---------------------------------------------------------------------------
# first_among
# ---------------------------------------------------------------------------

def test_first_among_single_winner():
    assert first_among(LEVELS, ["headache", "fever", "fatigue"]) == ["headache"]


def test_first_among_tie():
    result = first_among(LEVELS, ["fever", "rash"])
    assert set(result) == {"fever", "rash"}
    assert len(result) == 2


def test_first_among_absent_term():
    assert first_among(LEVELS, ["headache", "nausea"]) == "missing"


def test_first_among_all_absent():
    assert first_among(LEVELS, ["nausea", "vomiting"]) == "missing"


def test_first_among_single_term():
    assert first_among(LEVELS, ["fatigue"]) == ["fatigue"]


# ---------------------------------------------------------------------------
# last_among (mirror of first_among)
# ---------------------------------------------------------------------------

def test_last_among_single_winner():
    assert last_among(LEVELS, ["headache", "fever", "fatigue"]) == ["fatigue"]


def test_last_among_tie():
    result = last_among(LEVELS, ["fever", "rash"])
    assert set(result) == {"fever", "rash"}
    assert len(result) == 2


def test_last_among_absent_term():
    assert last_among(LEVELS, ["fatigue", "nausea"]) == "missing"


def test_last_among_single_term():
    assert last_among(LEVELS, ["headache"]) == ["headache"]


# ---------------------------------------------------------------------------
# sequence_holds
# ---------------------------------------------------------------------------

def test_sequence_holds_true():
    assert sequence_holds(LEVELS, ["headache", "fever", "fatigue"]) is True
    assert sequence_holds(LEVELS, ["headache", "fatigue"]) is True


def test_sequence_holds_false_wrong_order():
    assert sequence_holds(LEVELS, ["fatigue", "fever", "headache"]) is False


def test_sequence_holds_false_co_exist_in_chain():
    # fever and rash are co-exist; strict order not satisfied
    assert sequence_holds(LEVELS, ["headache", "fever", "rash"]) is False
    assert sequence_holds(LEVELS, ["fever", "rash", "fatigue"]) is False


def test_sequence_holds_missing():
    assert sequence_holds(LEVELS, ["headache", "nausea", "fatigue"]) == "missing"


def test_sequence_holds_single():
    assert sequence_holds(LEVELS, ["headache"]) is True


# ---------------------------------------------------------------------------
# load_levels (uses a tiny in-memory SQLite DB)
# ---------------------------------------------------------------------------

def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            vaers_id  INTEGER UNIQUE NOT NULL,
            vaccine   TEXT NOT NULL,
            narrative TEXT NOT NULL,
            num_groups INTEGER NOT NULL
        );
        CREATE TABLE level_terms (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id  INTEGER NOT NULL,
            level_index INTEGER NOT NULL,
            term        TEXT NOT NULL
        );
    """)
    conn.execute(
        "INSERT INTO reports (vaers_id, vaccine, narrative, num_groups) VALUES (1, 'Pfizer', 'test', 3)"
    )
    for level_index, terms in enumerate(LEVELS):
        for term in terms:
            conn.execute(
                "INSERT INTO level_terms (report_id, level_index, term) VALUES (1, ?, ?)",
                (level_index, term),
            )
    conn.commit()
    return conn


def test_load_levels_correct():
    conn = _make_db()
    loaded = load_levels(conn, 1)
    assert len(loaded) == 3
    assert loaded[0] == ["headache"]
    assert set(loaded[1]) == {"fever", "rash"}
    assert loaded[2] == ["fatigue"]
    conn.close()


def test_load_levels_missing_report():
    conn = _make_db()
    assert load_levels(conn, 999) == []
    conn.close()
