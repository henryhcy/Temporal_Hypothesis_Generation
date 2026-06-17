"""Shared fixtures for generation tests."""

from __future__ import annotations

import sqlite3

import pytest


def make_db(reports: list[tuple]) -> sqlite3.Connection:
    """Build an in-memory DB from (vaers_id, vaccine, levels) tuples.

    levels is a list[list[str]] leveled order. Mirrors the fixture used in
    tests/test_aggregation.py.
    """
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
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
        """
    )
    for vaers_id, vaccine, levels in reports:
        conn.execute(
            "INSERT INTO reports (vaers_id, vaccine, narrative, num_groups) "
            "VALUES (?,?,?,?)",
            (vaers_id, vaccine, "narrative", len(levels)),
        )
        rid = conn.execute(
            "SELECT report_id FROM reports WHERE vaers_id=?", (vaers_id,)
        ).fetchone()[0]
        for li, terms in enumerate(levels):
            for term in terms:
                conn.execute(
                    "INSERT INTO level_terms (report_id, level_index, term) "
                    "VALUES (?,?,?)",
                    (rid, li, term),
                )
    conn.commit()
    return conn


@pytest.fixture
def make_db_fixture():
    return make_db
