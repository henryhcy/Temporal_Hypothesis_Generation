"""CLI entry point: run the pilot (Part A report, Part B dataset, Part C sample).

Usage:
    python scripts/run_pilot.py
    python scripts/run_pilot.py --db data/medtempo.db --out data/pilot \\
                                --seed 0 --target 100
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from temporal_hypo.generation.pilot import run_pilot

_REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the temporal-hypo pilot.")
    parser.add_argument("--db", type=Path, default=_REPO_ROOT / "data" / "medtempo.db")
    parser.add_argument("--out", type=Path, default=_REPO_ROOT / "data" / "pilot")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--target", type=int, default=100,
                        help="Provisional per-group target T")
    args = parser.parse_args()

    summary = run_pilot(args.db, args.out, seed=args.seed, t=args.target)

    print(f"Pilot complete. Wrote artifacts to: {summary['out_dir']}")
    print(f"  instances generated: {summary['n_instances']}")
    print(f"  groups:              {summary['n_groups']}")
    print(f"  validation entries:  {summary['validation_entries']}")
    print()
    print("Part B per-group verdict counts (supported/refuted/insufficient):")
    for gid, d in summary["part_b"].items():
        c = d["counts"]
        flags = [k for k, v in d["under_target"].items() if v]
        flag_str = f"  under-target: {','.join(flags)}" if flags else ""
        print(f"  {gid:5s} {c['supported']:3d}/{c['refuted']:3d}/"
              f"{c['insufficient']:3d}{flag_str}")

    # also dump the run summary for inspection
    (args.out / "run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
