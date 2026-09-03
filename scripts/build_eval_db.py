"""CLI entry point: build the narrative-free eval DB from data/medtempo.db.

Usage:
    python scripts/build_eval_db.py
    python scripts/build_eval_db.py --db data/medtempo.db --out data/medtempo_eval.db

The eval DB is what the harness (and any text-to-SQL model) queries: it has no
`narrative` column and no surrogate ids, and its `first_mention` view already
applies the first-mention rule. See `src/temporal_hypo/framework/sql/views.sql`.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from temporal_hypo.framework.sql.build_eval_db import build_eval_db, open_eval_db

_REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the narrative-free MedTempo eval database.")
    parser.add_argument(
        "--db",
        type=Path,
        default=_REPO_ROOT / "data" / "medtempo.db",
        help="Raw MedTempo SQLite database (input)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_REPO_ROOT / "data" / "medtempo_eval.db",
        help="Eval SQLite database to write (overwritten if present)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        parser.error(f"Input database not found: {args.db}")

    print(f"Building {args.out} from {args.db} (SQLite {sqlite3.sqlite_version}) ...")
    counts = build_eval_db(args.db, args.out)

    conn = open_eval_db(args.out, readonly=True)
    try:
        report_cols = [row[1] for row in conn.execute("PRAGMA table_info(reports)")]
        by_vaccine = conn.execute(
            "SELECT vaccine, COUNT(*) FROM reports GROUP BY vaccine ORDER BY vaccine"
        ).fetchall()
    finally:
        conn.close()

    print(f"\nReports:                 {counts['reports']:>6}")
    for vaccine, n in by_vaccine:
        print(f"  {vaccine + ':':<22} {n:>6}")
    print(f"level_terms rows:        {counts['level_terms']:>6}")
    print(f"first_mention rows:      {counts['first_mention']:>6}")
    print(f"Distinct terms:          {counts['terms']:>6}")
    print(f"reports columns:         {', '.join(report_cols)}")
    print(f"\nDone. Eval database written to: {args.out}")


if __name__ == "__main__":
    main()
