"""CLI entry point: build data/medtempo.db from the two source CSVs.

Usage:
    python scripts/build_db.py
    python scripts/build_db.py --annot data/o4mini_annotation_final.csv \\
                                --vaers data/VAERS_Sampled_Data_v4.csv   \\
                                --db    data/medtempo.db
"""

from __future__ import annotations

import argparse
from pathlib import Path

from temporal_hypo.db.build import build

_REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the MedTempo SQLite database.")
    parser.add_argument(
        "--annot",
        type=Path,
        default=_REPO_ROOT / "data" / "o4mini_annotation_final.csv",
        help="Path to o4mini_annotation_final.csv",
    )
    parser.add_argument(
        "--vaers",
        type=Path,
        default=_REPO_ROOT / "data" / "VAERS_Sampled_Data_v4.csv",
        help="Path to VAERS_Sampled_Data_v4.csv",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=_REPO_ROOT / "data" / "medtempo.db",
        help="Output SQLite database path",
    )
    args = parser.parse_args()

    for p in (args.annot, args.vaers):
        if not p.exists():
            parser.error(f"Input file not found: {p}")

    args.db.parent.mkdir(parents=True, exist_ok=True)

    print(f"Building {args.db} ...")
    counts = build(args.annot, args.vaers, args.db)

    print(f"\nRows joined (inner):     {counts['total_joined']:>6}")
    print(f"Inserted into DB:        {counts['inserted']:>6}")
    print(f"  Pfizer:                {counts['vaccine_Pfizer']:>6}")
    print(f"  Moderna:               {counts['vaccine_Moderna']:>6}")
    print(f"  Janssen:               {counts['vaccine_Janssen']:>6}")
    print(f"Skipped (no vaers match):{counts['skipped_no_match']:>6}")
    print(f"Skipped (final_result≠0/1):{counts['skipped_filter']:>4}")
    print(f"Skipped (non-array JSON):{counts['skipped_no_json']:>6}")
    print(f"\nDone. Database written to: {args.db}")


if __name__ == "__main__":
    main()
