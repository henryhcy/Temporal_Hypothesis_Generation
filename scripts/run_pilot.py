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

from temporal_hypo.core.pseudonym import Pseudonymizer
from temporal_hypo.generation.pilot import run_pilot

_REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the temporal-hypo pilot.")
    parser.add_argument("--db", type=Path, default=_REPO_ROOT / "data" / "medtempo.db")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output dir (default data/pilot, or data/pilot_full "
                        "with --full)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--target", type=int, default=100,
                        help="Provisional per-group target T (ignored with --full)")
    parser.add_argument("--cap", type=int, default=None,
                        help="Per-group instance cap (v1.2 composition: 600 = 200 "
                        "per class); default: no cap, S sets the budget")
    parser.add_argument("--full", action="store_true",
                        help="Whole-population diagnostic: every viable core at "
                        "its natural verdict, no top-K cap and no balancing.")
    args = parser.parse_args()

    if args.out is None:
        args.out = _REPO_ROOT / "data" / ("pilot_full" if args.full else "pilot")
    args.out.mkdir(parents=True, exist_ok=True)

    pz = Pseudonymizer.default()
    if pz.is_identity:
        parser.error("refusing to generate with identity report ids (unset "
                     "MEDTEMPO_PSEUDONYM_KEY=identity; the key lives in data/private/)")
    summary = run_pilot(args.db, args.out, seed=args.seed, t=args.target,
                        full=args.full, cap=args.cap)

    mode = "whole-population diagnostic" if args.full else "pilot"
    print(f"{mode} complete. Wrote artifacts to: {summary['out_dir']}")
    print(f"  records generated:   {summary['n_instances']}")
    print(f"  groups:              {summary['n_groups']}")
    print(f"  validation entries:  {summary['validation_entries']}")
    print()
    if args.full:
        print("Per-group natural-verdict counts (supported/refuted/insufficient "
              "| viable cores):")
    else:
        print("Part B per-group verdict counts (supported/refuted/insufficient):")
    for gid, d in summary["part_b"].items():
        c = d["counts"]
        if args.full:
            print(f"  {gid:5s} {c['supported']:4d}/{c['refuted']:4d}/"
                  f"{c['insufficient']:4d}  | {d['n_cores']:5d}")
        else:
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
