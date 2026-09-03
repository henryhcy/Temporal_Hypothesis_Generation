"""Tests for the read-only SQL sandbox (``framework/sql/executor.py``)."""

from __future__ import annotations

import json

import pytest

from temporal_hypo.framework.sql.build_eval_db import open_eval_db
from temporal_hypo.framework.sql.executor import (
    ExecResult,
    ReadOnlyExecutor,
    has_second_statement,
    is_select,
    strip_leading_comments,
)
from tests.framework.conftest import CORPUS

N_REPORTS = len(CORPUS)


@pytest.fixture
def log_path(tmp_path):
    return tmp_path / "sql_log.jsonl"


@pytest.fixture
def executor(eval_db_path, log_path):
    ex = ReadOnlyExecutor(eval_db_path, timeout_s=5.0, row_cap=10_000, log_path=log_path)
    yield ex
    ex.close()


def _report_count(eval_db_path) -> int:
    conn = open_eval_db(eval_db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------

def test_select_over_first_mention_with_named_params(executor):
    res = executor.execute(
        "SELECT vaers_id, level FROM first_mention WHERE term = :t AND vaers_id = :v",
        {"t": "Headache", "v": 1015},
    )
    assert isinstance(res, ExecResult)
    assert res.error is None and res.error_class is None
    assert res.rows == [(1015, 0)]
    assert res.columns == ["vaers_id", "level"]
    assert res.truncated is False
    assert res.ms >= 0.0


def test_positional_params_and_column_aliases(executor):
    res = executor.execute(
        "SELECT a.vaers_id, (a.level < b.level) AS in_numerator "
        "FROM first_mention a JOIN first_mention b USING (vaers_id) "
        "WHERE a.vaccine = ? AND a.term = ? AND b.term = ? ORDER BY a.vaers_id",
        ("Janssen", "Headache", "Fatigue"),
    )
    assert res.error is None
    assert res.columns == ["vaers_id", "in_numerator"]
    assert res.rows == [(3003, 1)]


def test_with_clause_and_leading_comments_are_allowed(executor):
    sql = """
    -- a leading line comment
    /* and a block
       comment */
    WITH hf AS (
        SELECT vaers_id FROM first_mention WHERE term = 'Headache'
    )
    SELECT COUNT(*) AS n FROM hf
    """
    res = executor.execute(sql)
    assert res.error is None
    assert res.columns == ["n"]
    expected = sum(1 for _, _, levels in CORPUS if any("Headache" in lvl for lvl in levels))
    assert res.rows == [(expected,)]


def test_trailing_semicolon_is_fine(executor):
    assert executor.execute("SELECT 1;").rows == [(1,)]
    assert executor.execute("SELECT 1 ;  \n").rows == [(1,)]
    assert executor.execute("SELECT 1; -- done").rows == [(1,)]


def test_semicolon_inside_literal_or_comment_is_not_a_statement_break(executor):
    assert executor.execute("SELECT ';' AS s").rows == [(";",)]
    assert executor.execute("SELECT 1 /* ; SELECT 2 */").rows == [(1,)]


# ---------------------------------------------------------------------------
# refusals
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sql", [
    "INSERT INTO reports (vaers_id, vaccine, num_stages) VALUES (1, 'Pfizer', 1)",
    "UPDATE reports SET vaccine = 'Moderna'",
    "DELETE FROM reports",
    "CREATE TABLE t (x)",
    "CREATE TEMP TABLE t (x)",
    "DROP TABLE reports",
    "DROP VIEW first_mention",
    "ATTACH DATABASE ':memory:' AS m",
    "PRAGMA table_info(reports)",
    "PRAGMA writable_schema = 1",
    "BEGIN",
    "VACUUM",
    "EXPLAIN SELECT 1",
    "SELECT * FROM sqlite_master",
    "SELECT * FROM sqlite_schema",
    "SELECT * FROM sqlite_temp_master",
    "SELECT * FROM pragma_table_info('reports')",
    # WITH-prefixed writes pass the keyword check and must be caught by the authorizer
    "WITH x AS (SELECT 1) INSERT INTO reports (vaers_id, vaccine, num_stages) SELECT 9, 'Pfizer', 1 FROM x",
    "WITH x AS (SELECT 1) DELETE FROM reports",
    "WITH x AS (SELECT 1) UPDATE reports SET vaccine = 'Moderna' WHERE vaers_id IN (SELECT * FROM x)",
])
def test_denied_statements(executor, eval_db_path, sql):
    res = executor.execute(sql)
    assert res.error is not None
    assert res.error_class in {"denied", "not_select"}, (sql, res.error_class, res.error)
    assert res.rows == [] and res.columns == []
    assert _report_count(eval_db_path) == N_REPORTS


def test_sqlite_master_is_denied_by_the_authorizer(executor):
    res = executor.execute("SELECT * FROM sqlite_master")
    assert res.error_class == "denied"


def test_with_prefixed_write_is_denied_by_the_authorizer(executor, eval_db_path):
    res = executor.execute(
        "WITH x AS (SELECT 1) INSERT INTO reports (vaers_id, vaccine, num_stages) "
        "SELECT 9, 'Pfizer', 1 FROM x"
    )
    assert res.error_class == "denied"
    assert _report_count(eval_db_path) == N_REPORTS


@pytest.mark.parametrize("sql", ["PRAGMA table_info(reports)", "EXPLAIN SELECT 1",
                                 "VALUES (1)", "", "   -- only a comment"])
def test_not_select(executor, sql):
    assert executor.execute(sql).error_class == "not_select"


def test_multi_statement_is_rejected(executor):
    res = executor.execute("SELECT 1; SELECT 2")
    assert res.error_class == "multi_statement"
    assert res.rows == []
    res = executor.execute("SELECT 1; DROP TABLE reports")
    assert res.error_class == "multi_statement"


def test_narrative_is_not_reachable(executor):
    res = executor.execute("SELECT narrative FROM reports")
    assert res.error is not None
    assert res.error_class == "sql_error"
    assert res.rows == []


def test_sql_error_class(executor):
    res = executor.execute("SELECT nonexistent_column FROM reports")
    assert res.error_class == "sql_error"
    assert "nonexistent_column" in res.error


# ---------------------------------------------------------------------------
# limits
# ---------------------------------------------------------------------------

def test_row_cap_marks_truncated(eval_db_path, log_path):
    with ReadOnlyExecutor(eval_db_path, row_cap=3, log_path=log_path) as ex:
        res = ex.execute("SELECT vaers_id FROM reports ORDER BY vaers_id")
        assert res.error is None
        assert res.truncated is True
        assert res.rows == [(1001,), (1002,), (1003,)]
        # exactly row_cap rows is not a truncation
        res = ex.execute("SELECT vaers_id FROM reports ORDER BY vaers_id LIMIT 3")
        assert res.truncated is False and len(res.rows) == 3


def test_timeout_on_expensive_query(eval_db_path, log_path):
    with ReadOnlyExecutor(eval_db_path, timeout_s=0.2, log_path=log_path) as ex:
        res = ex.execute(
            "SELECT COUNT(*) FROM level_terms a, level_terms b, level_terms c, "
            "level_terms d, level_terms e"
        )
        assert res.error_class == "timeout"
        assert res.rows == []
        # interrupted promptly after the 0.2 s deadline, not after the query finished
        assert res.ms < 2_000
        # the connection is still usable afterwards
        assert ex.execute("SELECT 1").rows == [(1,)]


# ---------------------------------------------------------------------------
# logging and lifecycle
# ---------------------------------------------------------------------------

def test_logs_one_json_line_per_call(executor, log_path):
    calls = [
        ("SELECT vaers_id FROM reports WHERE vaccine = :v", {"v": "Janssen"}),
        ("DELETE FROM reports", None),
        ("SELECT 1; SELECT 2", None),
        ("SELECT * FROM sqlite_master", None),
    ]
    for sql, params in calls:
        executor.execute(sql, params)
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(calls)
    entries = [json.loads(line) for line in lines]
    for entry in entries:
        assert {"sql", "params", "n_rows", "ms", "error", "error_class"} <= set(entry)
    assert entries[0]["sql"] == calls[0][0]
    assert entries[0]["params"] == {"v": "Janssen"}
    assert entries[0]["n_rows"] == 4 and entries[0]["error"] is None
    assert [e["error_class"] for e in entries] == [None, "not_select", "multi_statement", "denied"]


def test_no_log_without_log_path(eval_db_path, tmp_path):
    with ReadOnlyExecutor(eval_db_path) as ex:
        assert ex.execute("SELECT 1").rows == [(1,)]
    assert list(tmp_path.iterdir()) == []


def test_close_is_idempotent_and_execute_after_close_raises(eval_db_path):
    ex = ReadOnlyExecutor(eval_db_path)
    ex.close()
    ex.close()
    with pytest.raises(RuntimeError):
        ex.execute("SELECT 1")


# ---------------------------------------------------------------------------
# statement-text helpers
# ---------------------------------------------------------------------------

def test_strip_leading_comments():
    assert strip_leading_comments("  -- c\n /* b */ SELECT 1") == "SELECT 1"
    assert strip_leading_comments("/* unterminated") == ""
    assert strip_leading_comments("SELECT 1 -- trailing") == "SELECT 1 -- trailing"


def test_is_select():
    assert is_select("select 1")
    assert is_select("\n WITH x AS (SELECT 1) SELECT * FROM x")
    assert not is_select("SELECTION")
    assert not is_select("WITHOUT ROWID")
    assert not is_select("PRAGMA foo")


def test_has_second_statement():
    assert has_second_statement("SELECT 1; SELECT 2")
    assert has_second_statement("SELECT 1; ; SELECT 2")
    assert not has_second_statement("SELECT 1")
    assert not has_second_statement("SELECT 1; -- done")
    assert not has_second_statement("SELECT ';'")
    assert not has_second_statement("SELECT 1 /* ; */")
