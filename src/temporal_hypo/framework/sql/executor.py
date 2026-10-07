"""Sandboxed, read-only SQL execution against the eval DB.

Model-written SQL runs here, so the sandbox is layered rather than trusted to a
single check:

1. the connection is opened with the ``file:...?mode=ro`` URI (SQLite itself
   refuses writes to the main database);
2. an authorizer allows only ``SELECT``, reads of the five eval-schema relations
   (``reports``, ``level_terms``, ``first_mention``, ``report_terms``, ``first_mention_rank``) and scalar
   function calls -- everything else (writes, ``CREATE``/``DROP``, ``ATTACH``,
   ``PRAGMA``, transactions, recursive CTEs, table-valued functions, the
   ``sqlite_master`` catalogue) is denied at prepare time;
3. the statement text must begin with ``SELECT`` or ``WITH`` after leading
   whitespace and SQL comments, and must be a single statement;
4. a progress handler interrupts anything running past ``timeout_s`` and a row
   cap bounds what is fetched (``truncated`` flags a cap hit, so an accidental
   cartesian product is reported instead of aggregated as if complete).

Every call is appended to a JSONL log when ``log_path`` is given, so a run's
SQL can be replayed and its failure classes tallied after the fact. Failures are
returned in ``ExecResult.error_class`` rather than raised: a model's bad SQL is a
measurement, not a crash.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from temporal_hypo.framework.sql.build_eval_db import open_eval_db

# Relations a query may read. Anything else (sqlite_master, pragma_* and other
# table-valued functions, temp tables, attached DBs) is denied.
READABLE_TABLES = frozenset({"reports", "level_terms", "first_mention", "report_terms",
                             "first_mention_rank"})   # v1.2 rank view

ERROR_CLASSES = ("not_select", "multi_statement", "denied", "timeout", "sql_error")

# VM instructions between progress-handler calls; small enough that a 0.2 s
# timeout is honoured within a few milliseconds.
_PROGRESS_EVERY_N_OPS = 1000

_LEADING_KEYWORD = re.compile(r"(SELECT|WITH)\b", re.IGNORECASE)
_MULTI_STATEMENT_MSG = "You can only execute one statement at a time"


@dataclass
class ExecResult:
    rows: list[tuple]
    columns: list[str]
    ms: float
    error: str | None = None
    error_class: str | None = None
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def n_rows(self) -> int:
        return len(self.rows)


# ---------------------------------------------------------------------------
# statement-text checks
# ---------------------------------------------------------------------------

def strip_leading_comments(sql: str) -> str:
    """Drop leading whitespace and SQL comments (``-- ...`` and ``/* ... */``)."""
    i, n = 0, len(sql)
    while i < n:
        if sql[i].isspace():
            i += 1
        elif sql.startswith("--", i):
            nl = sql.find("\n", i)
            i = n if nl < 0 else nl + 1
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end < 0 else end + 2
        else:
            break
    return sql[i:]


def normalise_statement(sql: str) -> str:
    """Trim surrounding whitespace and any trailing semicolons (``SELECT 1;`` is fine)."""
    body = sql.strip()
    while body.endswith(";"):
        body = body[:-1].rstrip()
    return body


def is_select(sql: str) -> bool:
    """True when the statement begins with SELECT or WITH (comments/whitespace skipped)."""
    return _LEADING_KEYWORD.match(strip_leading_comments(sql)) is not None


def has_second_statement(sql: str) -> bool:
    """True when a complete statement is followed by anything but comments/whitespace.

    ``sqlite3.complete_statement`` on each ``;``-terminated prefix is false while
    the semicolon sits inside a string literal or a comment, so those never
    count as statement boundaries.
    """
    for i, ch in enumerate(sql):
        if ch == ";" and sqlite3.complete_statement(sql[: i + 1]):
            tail = strip_leading_comments(sql[i + 1:])
            return tail.strip(" \t\r\n;") != ""
    return False


# ---------------------------------------------------------------------------
# the executor
# ---------------------------------------------------------------------------

class ReadOnlyExecutor:
    """Run one SELECT at a time against the eval DB under the sandbox described above."""

    def __init__(self, db_path: str | Path, *, timeout_s: float | None = 5.0,
                 row_cap: int = 10_000, log_path: Path | None = None) -> None:
        self.db_path = Path(db_path)
        self.timeout_s = timeout_s
        self.row_cap = int(row_cap)
        self.log_path = Path(log_path) if log_path is not None else None
        self._deadline: float | None = None
        self._conn: sqlite3.Connection | None = open_eval_db(self.db_path, readonly=True)
        self._conn.set_authorizer(self._authorize)
        self._conn.set_progress_handler(self._on_progress, _PROGRESS_EVERY_N_OPS)

    # -- sandbox callbacks ---------------------------------------------------

    @staticmethod
    def _authorize(action: int, arg1, arg2, db_name, trigger_or_view) -> int:
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            return sqlite3.SQLITE_OK if arg1 in READABLE_TABLES else sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    def _on_progress(self) -> int:
        # Same clock as `execute` (perf_counter); mixing clocks silently breaks the
        # deadline because they have different epochs on Windows.
        if self._deadline is not None and time.perf_counter() > self._deadline:
            return 1   # non-zero => sqlite3.OperationalError: interrupted
        return 0

    # -- public API ----------------------------------------------------------

    def execute(self, sql: str, params: Mapping | Sequence | None = None) -> ExecResult:
        """Run ``sql`` with bound ``params``; failures come back in ``error_class``."""
        if self._conn is None:
            raise RuntimeError("ReadOnlyExecutor is closed")
        t0 = time.perf_counter()
        bound = _coerce_params(params)
        result = self._run(sql, bound, t0)
        result.ms = (time.perf_counter() - t0) * 1000.0
        self._log(sql, bound, result)
        return result

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "ReadOnlyExecutor":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- internals -----------------------------------------------------------

    def _run(self, sql: str, params, t0: float) -> ExecResult:
        body = normalise_statement(sql)
        if not is_select(body):
            return _failure("not_select", "statement must begin with SELECT or WITH")
        if has_second_statement(body):
            return _failure("multi_statement", "only one statement per call")

        conn = self._conn
        self._deadline = None if self.timeout_s is None else t0 + float(self.timeout_s)
        cur = None
        try:
            cur = conn.execute(body, params) if params is not None else conn.execute(body)
            fetched = cur.fetchmany(self.row_cap + 1)
            columns = [d[0] for d in (cur.description or ())]
        except sqlite3.Error as e:
            return _failure(*self._classify(e))
        finally:
            self._deadline = None
            if cur is not None:
                cur.close()
        truncated = len(fetched) > self.row_cap
        rows = [tuple(r) for r in fetched[: self.row_cap]]
        return ExecResult(rows=rows, columns=columns, ms=0.0, truncated=truncated)

    def _classify(self, e: sqlite3.Error) -> tuple[str, str]:
        msg = str(e)
        code = getattr(e, "sqlite_errorcode", None)
        if isinstance(e, sqlite3.ProgrammingError) and _MULTI_STATEMENT_MSG in msg:
            return "multi_statement", "only one statement per call"
        if code == sqlite3.SQLITE_AUTH or "not authorized" in msg or "prohibited" in msg:
            return "denied", f"denied by the read-only sandbox: {msg}"
        if isinstance(e, sqlite3.OperationalError) and "interrupted" in msg:
            return "timeout", f"query exceeded {self.timeout_s} s and was interrupted"
        return "sql_error", f"{type(e).__name__}: {msg}"

    def _log(self, sql: str, params, result: ExecResult) -> None:
        if self.log_path is None:
            return
        entry = {
            "sql": sql,
            "params": params if params is None or isinstance(params, dict) else list(params),
            "n_rows": len(result.rows),
            "ms": round(result.ms, 3),
            "error": result.error,
            "error_class": result.error_class,
            "truncated": result.truncated,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def _failure(error_class: str, error: str) -> ExecResult:
    return ExecResult(rows=[], columns=[], ms=0.0, error=error, error_class=error_class)


def _coerce_params(params: Mapping | Sequence | None):
    """sqlite3 wants a dict (named) or a tuple (positional); accept any Mapping/Sequence."""
    if params is None:
        return None
    if isinstance(params, Mapping):
        return dict(params)
    if isinstance(params, (str, bytes)):
        raise TypeError("params must be a Mapping or a Sequence of values, not a string")
    return tuple(params)
