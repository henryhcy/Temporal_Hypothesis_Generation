"""Tests for the narrative-free eval DB builder (``framework/sql/build_eval_db.py``).

Fast tests run on the synthetic ``CORPUS`` from ``conftest``; the slow test
rebuilds from the real ``data/medtempo.db`` and checks that ``first_mention``
reproduces ``CorpusIndex.report_terms`` exactly (the first-mention rule).
"""

from __future__ import annotations

import sqlite3

import pytest

from temporal_hypo.framework.sql.build_eval_db import (
    EVAL_DDL,
    build_eval_db,
    open_eval_db,
)
from temporal_hypo.generation.corpus import CorpusIndex
from tests.framework.conftest import CORPUS, REPO_ROOT
from tests.generation.conftest import make_db

RAW_DB = REPO_ROOT / "data" / "medtempo.db"
needs_db = pytest.mark.skipif(not RAW_DB.exists(), reason="data/medtempo.db not present")

N_REPORTS = len(CORPUS)
N_LEVEL_TERMS = sum(len(level) for _, _, levels in CORPUS for level in levels)
N_TERMS = len({t for _, _, levels in CORPUS for level in levels for t in level})


def _columns(conn: sqlite3.Connection, table: str) -> list[tuple]:
    return conn.execute(f"PRAGMA table_info({table})").fetchall()


def _first_mention_map(conn: sqlite3.Connection) -> dict[int, dict[str, int]]:
    out: dict[int, dict[str, int]] = {}
    for vid, term, level in conn.execute("SELECT report_id, term, level FROM first_mention"):
        out.setdefault(vid, {})[term] = level
    for (vid,) in conn.execute("SELECT report_id FROM reports"):
        out.setdefault(vid, {})
    return out


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------

def test_schema_has_no_narrative_and_no_surrogate_ids(eval_db_path):
    conn = open_eval_db(eval_db_path)
    try:
        report_cols = [c[1] for c in _columns(conn, "reports")]
        lt_cols = [c[1] for c in _columns(conn, "level_terms")]
    finally:
        conn.close()
    assert report_cols == ["report_id", "vaccine", "num_stages"]
    assert lt_cols == ["report_id", "level_index", "term"]
    assert "narrative" not in report_cols + lt_cols
    assert "vaers_id" not in report_cols + lt_cols


def test_reports_keyed_by_report_id(eval_db_path):
    conn = open_eval_db(eval_db_path)
    try:
        pk = [c[1] for c in _columns(conn, "reports") if c[5] == 1]
        ids = sorted(v for (v,) in conn.execute("SELECT report_id FROM reports"))
        lt_ids = {v for (v,) in conn.execute("SELECT DISTINCT report_id FROM level_terms")}
    finally:
        conn.close()
    assert pk == ["report_id"]
    assert ids == sorted(vid for vid, _, _ in CORPUS)
    assert lt_ids <= set(ids)


def test_schema_objects_and_indices(eval_db_path):
    conn = open_eval_db(eval_db_path)
    try:
        objs = {(t, n) for t, n in conn.execute("SELECT type, name FROM sqlite_master")}
    finally:
        conn.close()
    assert ("table", "reports") in objs and ("table", "level_terms") in objs
    assert ("view", "first_mention") in objs and ("view", "report_terms") in objs
    assert {("index", "idx_lt_vid"), ("index", "idx_lt_term"), ("index", "idx_r_vax")} <= objs


def test_ddl_header_tells_models_the_rules():
    header = EVAL_DDL.split("CREATE TABLE", 1)[0]
    assert "pseudonymous" in header and "NOT a VAERS id" in header
    assert "FIRST mention" in header or "first mention" in header.lower()
    assert "first_mention" in header
    # no `narrative` anywhere in the executable statements the model could query
    statements = EVAL_DDL.split("CREATE TABLE", 1)[1]
    assert "narrative" not in statements.lower()


# ---------------------------------------------------------------------------
# contents
# ---------------------------------------------------------------------------

def test_build_returns_counts_and_overwrites(tmp_path):
    dst = tmp_path / "eval.db"
    counts = build_eval_db(make_db(CORPUS), dst)
    assert counts["reports"] == N_REPORTS
    assert counts["level_terms"] == N_LEVEL_TERMS
    assert counts["terms"] == N_TERMS
    # Headache is at two levels in 1015, so first_mention has one row fewer
    assert counts["first_mention"] == N_LEVEL_TERMS - 1
    # rebuilding onto an existing file overwrites rather than appending
    again = build_eval_db(make_db(CORPUS), dst)
    assert again == counts
    conn = open_eval_db(dst)
    try:
        assert conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == N_REPORTS
    finally:
        conn.close()


def test_build_from_a_path(tmp_path):
    raw_path = tmp_path / "raw.db"
    disk = sqlite3.connect(str(raw_path))
    make_db(CORPUS).backup(disk)
    disk.close()
    counts = build_eval_db(raw_path, tmp_path / "eval.db")
    assert counts["reports"] == N_REPORTS and counts["level_terms"] == N_LEVEL_TERMS


def test_num_stages_equals_len_levels(eval_db_path):
    conn = open_eval_db(eval_db_path)
    try:
        got = dict(conn.execute("SELECT report_id, num_stages FROM reports"))
        vax = dict(conn.execute("SELECT report_id, vaccine FROM reports"))
    finally:
        conn.close()
    assert got == {vid: len(levels) for vid, _, levels in CORPUS}
    assert vax == {vid: vaccine for vid, vaccine, _ in CORPUS}


def test_first_mention_applies_first_mention_rule(eval_db_path):
    conn = open_eval_db(eval_db_path)
    try:
        rows = conn.execute(
            "SELECT level FROM first_mention WHERE report_id = 1015 AND term = 'Headache'"
        ).fetchall()
        raw = conn.execute(
            "SELECT level_index FROM level_terms WHERE report_id = 1015 AND term = 'Headache' "
            "ORDER BY level_index"
        ).fetchall()
        vaccine = conn.execute(
            "SELECT DISTINCT vaccine FROM first_mention WHERE report_id = 1015"
        ).fetchall()
    finally:
        conn.close()
    assert raw == [(0,), (2,)]          # the raw table keeps both mentions
    assert rows == [(0,)]               # the view keeps exactly one row: the first
    assert vaccine == [("Pfizer",)]


def test_first_mention_matches_corpus_index_on_synthetic_corpus(eval_db_path, corpus_index):
    conn = open_eval_db(eval_db_path)
    try:
        got = _first_mention_map(conn)
    finally:
        conn.close()
    assert got == corpus_index.report_terms


def test_report_terms_is_sorted_and_deterministic(eval_db_path):
    conn = open_eval_db(eval_db_path)
    try:
        rows = conn.execute(
            "SELECT level_index, terms FROM report_terms WHERE report_id = 1015 ORDER BY level_index"
        ).fetchall()
        r1003 = conn.execute(
            "SELECT terms FROM report_terms WHERE report_id = 1003 AND level_index = 0"
        ).fetchone()
    finally:
        conn.close()
    assert rows == [(0, "Headache"), (1, "Fatigue"), (2, "Headache | Pyrexia")]
    assert r1003 == ("Headache | Rash",)


def test_report_terms_order_does_not_depend_on_insertion_order(tmp_path):
    # the same level inserted in two different orders must render identically
    a = build_eval_db(make_db([(1, "Pfizer", [["Rash", "Headache", "Chills"]])]), tmp_path / "a.db")
    b = build_eval_db(make_db([(1, "Pfizer", [["Chills", "Rash", "Headache"]])]), tmp_path / "b.db")
    assert a == b
    out = []
    for name in ("a.db", "b.db"):
        conn = open_eval_db(tmp_path / name)
        try:
            out.append(conn.execute("SELECT terms FROM report_terms").fetchall())
        finally:
            conn.close()
    assert out[0] == out[1] == [("Chills | Headache | Rash",)]


def test_open_eval_db_readonly_refuses_writes(eval_db_path):
    conn = open_eval_db(eval_db_path, readonly=True)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("INSERT INTO reports (report_id, vaccine, num_stages) VALUES (1, 'Pfizer', 1)")
    finally:
        conn.close()


def test_open_eval_db_readonly_does_not_create_missing_file(tmp_path):
    missing = tmp_path / "nope.db"
    with pytest.raises(sqlite3.OperationalError):
        open_eval_db(missing, readonly=True)
    assert not missing.exists()


# ---------------------------------------------------------------------------
# real data
# ---------------------------------------------------------------------------

@pytest.mark.slow
@needs_db
def test_first_mention_reproduces_corpus_index_on_real_db(tmp_path):
    raw = sqlite3.connect(f"{RAW_DB.resolve().as_uri()}?mode=ro", uri=True)
    try:
        expected = CorpusIndex.load(raw)
        counts = build_eval_db(raw, tmp_path / "medtempo_eval.db")
    finally:
        raw.close()
    assert counts["reports"] == 3166
    assert counts["level_terms"] == 22681
    assert counts["terms"] == 1660
    conn = open_eval_db(tmp_path / "medtempo_eval.db")
    try:
        got = _first_mention_map(conn)
        vax = dict(conn.execute("SELECT report_id, vaccine FROM reports"))
        assert "narrative" not in [c[1] for c in _columns(conn, "reports")]
    finally:
        conn.close()
    assert got == expected.report_terms
    assert vax == expected.report_vaccine
