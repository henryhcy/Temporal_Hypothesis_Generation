"""Re-score a finished run from its predictions.jsonl (no model calls, no retrieval).

Usage:
    PYTHONPATH=src python scripts/rescore.py --run results/smoke200_llm-s1_compiler
    PYTHONPATH=src python scripts/rescore.py --run results/oracle_v1 --release data/release/v1

Use after a scorer fix: `framework.evaluate` is a pure function of the prediction
rows and the gold, so metrics.json / report.md / failures.md can be regenerated
without re-running the pipeline. Retrieval set metrics need the id lists, so runs
written with `--no-ids` re-score everything EXCEPT the set precision/recall.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from temporal_hypo.framework.evaluate import evaluate, write_report
from temporal_hypo.framework.io import load_release
from temporal_hypo.framework.pipeline import load_predictions

_REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    p = argparse.ArgumentParser(description="Re-score a run directory from its predictions.jsonl.")
    p.add_argument("--run", type=Path, required=True, help="run directory containing predictions.jsonl")
    p.add_argument("--release", type=Path, default=_REPO_ROOT / "data" / "release" / "v1")
    p.add_argument("--stem", default="pilot_instances")
    p.add_argument("--seed", type=int, default=None, help="defaults to the run's config seed")
    p.add_argument("--min-group-size", type=int, default=30,
                   help="groups with fewer scored instances are left out of the group-macro (smoke runs: use 6)")
    args = p.parse_args()

    t0 = time.time()
    rows = load_predictions(args.run / "predictions.jsonl")
    release = load_release(args.release, args.stem, verify_sha=False)
    cfg_path = args.run / "config.json"
    run_config = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    seed = args.seed if args.seed is not None else int(run_config.get("seed", 0))
    metrics = evaluate(rows, release, options_seed=seed, seed=seed,
                       min_group_size=args.min_group_size)
    metrics["run_config"] = run_config
    metrics["rescored"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    write_report(metrics, args.run, rows=rows, release=release)
    v = metrics["verdict"]
    print(f"rescored {len(rows)} rows: acc={v['accuracy']} class-macro-F1={v['class_macro_f1']} "
          f"group-macro-F1={v['group_macro']['f1']} twins={metrics['consistency']['twins']['consistent_rate']} "
          f"not_loc_fpr={metrics['retrieval']['not_locatable_fpr']['rate']} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
