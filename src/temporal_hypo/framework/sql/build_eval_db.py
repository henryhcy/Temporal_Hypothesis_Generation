"""Build the narrative-free eval DB (``data/medtempo_eval.db``) from the raw MedTempo DB.

The harness must never be able to read ``reports.narrative`` (CLAUDE.md: the
framework reads ANNOTATIONS, not narratives), and every id it exposes must be
the public ``vaers_id`` -- ``evidence_ids`` in the release are VAERS ids, never
the raw DB's surrogate ``report_id``. Rather than trusting every query to avoid
those two columns, this module produces a separate database that simply does
not contain them: ``reports`` is re-keyed on ``vaers_id`` and ``level_terms``
references it directly. The full DDL, including the ``first_mention`` view that
encodes the first-mention rule (``MIN(level_index)`` per report and term --
exactly what ``generation.corpus.CorpusIndex.load`` does in Python), lives in
``views.sql`` so the text shown to text-to-SQL models and the schema actually
built are one and the same file.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_HERE = Path(__file__).resolve().parent
VIEWS_SQL_PATH = _HERE / "views.sql"

# The DDL shown to models verbatim and executed by `build_eval_db`.
EVAL_DDL: str = VIEWS_SQL_PATH.read_text(encoding="utf-8")

# `group_concat(x, sep ORDER BY x)` (used by the `report_terms` view) needs 3.44+.
MIN_SQLITE_VERSION = (3, 44, 0)

_SIDECAR_SUFFIXES = ("", "-journal", "-wal", "-shm")


def _require_sqlite() -> None:
    if sqlite3.sqlite_version_info < MIN_SQLITE_VERSION:
        want = ".".join(map(str, MIN_SQLITE_VERSION))
        raise RuntimeError(
            f"the eval DB views need SQLite >= {want} (ORDER BY inside group_concat); "
            f"this interpreter links SQLite {sqlite3.sqlite_version}"
        )


def _ro_uri(path: str | Path) -> str:
    """``file:`` URI that opens ``path`` read-only (fails if the file is missing)."""
    return Path(path).resolve().as_uri() + "?mode=ro"


def open_eval_db(path: str | Path, *, readonly: bool = True) -> sqlite3.Connection:
    """Open the eval DB. Read-only (``mode=ro`` URI) unless ``readonly=False``.

    A read-only open of a missing file raises ``sqlite3.OperationalError`` instead
    of silently creating an empty database.
    """
    _require_sqlite()
    if readonly:
        return sqlite3.connect(_ro_uri(path), uri=True)
    return sqlite3.connect(str(path))


def _remove_db_files(dst: Path) -> None:
    for suffix in _SIDECAR_SUFFIXES:
        p = Path(str(dst) + suffix)
        if p.exists():
            p.unlink()


def build_eval_db(src: sqlite3.Connection | str | Path, dst: str | Path) -> dict:
    """Create ``dst`` from the raw DB ``src`` (a connection or a path); overwrite if present.

    Copies ``reports(vaers_id, vaccine, num_groups AS num_stages)`` and
    ``level_terms`` re-keyed on ``vaers_id``; drops ``narrative`` and the surrogate
    ids. Returns ``{"reports", "level_terms", "terms", "first_mention"}`` row counts
    and raises ``RuntimeError`` if the copy does not reproduce the source counts.
    """
    _require_sqlite()
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    own_src = not isinstance(src, sqlite3.Connection)
    conn = sqlite3.connect(_ro_uri(src), uri=True) if own_src else src
    try:
        reports = conn.execute(
            "SELECT vaers_id, vaccine, num_groups FROM reports ORDER BY vaers_id"
        ).fetchall()
        level_terms = conn.execute(
            """
            SELECT r.vaers_id, lt.level_index, lt.term
            FROM level_terms lt
            JOIN reports r USING (report_id)
            ORDER BY r.vaers_id, lt.level_index, lt.term
            """
        ).fetchall()
        n_pairs_src = conn.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT report_id, term FROM level_terms)"
        ).fetchone()[0]
    finally:
        if own_src:
            conn.close()

    # Build into a sibling temp file and swap it in, so a failed build never
    # leaves a half-written eval DB at `dst`.
    _remove_db_files(dst)
    tmp = dst.with_name(dst.name + ".tmp")
    _remove_db_files(tmp)
    out = sqlite3.connect(str(tmp))
    try:
        out.execute("PRAGMA foreign_keys = ON")
        out.executescript(EVAL_DDL)
        with out:
            out.executemany(
                "INSERT INTO reports (vaers_id, vaccine, num_stages) VALUES (?, ?, ?)",
                reports,
            )
            out.executemany(
                "INSERT INTO level_terms (vaers_id, level_index, term) VALUES (?, ?, ?)",
                level_terms,
            )
        counts = {
            "reports": out.execute("SELECT COUNT(*) FROM reports").fetchone()[0],
            "level_terms": out.execute("SELECT COUNT(*) FROM level_terms").fetchone()[0],
            "terms": out.execute("SELECT COUNT(DISTINCT term) FROM level_terms").fetchone()[0],
            "first_mention": out.execute("SELECT COUNT(*) FROM first_mention").fetchone()[0],
        }
        cols = {row[1] for row in out.execute("PRAGMA table_info(reports)")}
        if "narrative" in cols or "report_id" in cols:
            raise RuntimeError(f"eval DB schema leaks raw columns: {sorted(cols)}")
        if counts["reports"] != len(reports) or counts["level_terms"] != len(level_terms):
            raise RuntimeError(f"eval DB row counts do not match the source: {counts}")
        if counts["first_mention"] != n_pairs_src:
            raise RuntimeError(
                f"first_mention has {counts['first_mention']} rows, source has "
                f"{n_pairs_src} distinct (report, term) pairs"
            )
    finally:
        out.close()
    os.replace(tmp, dst)
    return counts
