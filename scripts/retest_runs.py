"""Re-run Stage 3 (the deterministic test) on finished runs from their stored plans and report sets,
then re-score against the current release (2026-10-24; no model calls).

Used after a gold-procedure change (argmax competitor-tail Bonferroni; stage-size-aware adjacency
chance): a run's plan (S1) and report sets (S2) are model outputs and stay as stored; its verdict is
what the harness computes from them, so it is recomputed here exactly as pipeline.run_record would.
Runs whose verdict is the MODEL's (counts-llm, the s3llm rows) keep their predictions and are only
re-scored. The previous metrics.json is kept as metrics.pre_relabel.json.

    PYTHONPATH=src .venv313/bin/python scripts/retest_runs.py results/test_*            # dirs
    PYTHONPATH=src .venv313/bin/python scripts/retest_runs.py --dry results/test_q25pair_dprime_verify2
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from temporal_hypo.framework.claim_schema import DATA_DERIVED_MODES, StructuredClaim  # noqa: E402
from temporal_hypo.framework.evaluate import evaluate, write_report  # noqa: E402
from temporal_hypo.framework.io import load_release  # noqa: E402
from temporal_hypo.framework.pipeline import _prediction_to_dict, load_predictions  # noqa: E402
from temporal_hypo.framework.run_test import run_test  # noqa: E402
from temporal_hypo.framework.sql.aggregate import ArmCounts, cell_key  # noqa: E402
from temporal_hypo.framework.sql.executor import ReadOnlyExecutor  # noqa: E402
from temporal_hypo.framework.sql.retrieve import Retrieval, derived_null_chance_sum  # noqa: E402

MODEL_VERDICT_PIPELINES = {"counts-llm"}


def retrieval_from_row(rt: dict | None, claim: StructuredClaim, executor: ReadOnlyExecutor) -> Retrieval | None:
    if rt is None:
        return None
    kind = claim.spec.named_cell_kind
    arms = []
    for a in rt.get("arms") or []:
        arm = ArmCounts(n=int(a.get("n") or 0), k=int(a.get("k") or 0),
                        denominator_ids={int(x) for x in a.get("denominator_ids") or []},
                        numerator_ids={int(x) for x in a.get("numerator_ids") or []},
                        excluded_ids={int(x) for x in a.get("excluded_ids") or []},
                        counts={cell_key(c, kind): v for c, v in (a.get("counts") or {}).items()})
        arms.append(arm)
    if arms and claim.mode in DATA_DERIVED_MODES:
        arms[0].chance_sum = derived_null_chance_sum(executor, claim.mode, arms[0].denominator_ids)
    return Retrieval(arms=arms, levels=rt.get("levels"), queries=[], ok=bool(rt.get("ok", True)))


def retest(run: Path, executor: ReadOnlyExecutor, *, dry: bool) -> dict:
    cfg = json.loads((run / "config.json").read_text())
    rows = load_predictions(run / "predictions.jsonl")
    recompute = cfg.get("pipeline") not in MODEL_VERDICT_PIPELINES and not run.name.endswith("_s3llm")
    changed = 0
    if recompute:
        for row in rows:
            if not row.get("claim") or row.get("prediction") is None:
                continue
            claim = StructuredClaim.from_dict(row["claim"])
            if claim.is_underdetermined:
                continue
            rt = retrieval_from_row(row.get("retrieval"), claim, executor)
            if rt is None:
                continue
            pred = _prediction_to_dict(run_test(claim, rt, procedure_mode=cfg.get("procedure_mode", "honouring")))
            if pred["verdict"] != row["prediction"].get("verdict"):
                changed += 1
            row["prediction"] = pred
    release = load_release(Path(cfg["release"]), "pilot_instances", verify_sha=False)
    seed = int(cfg.get("seed", 0))
    old = json.loads((run / "metrics.json").read_text())["verdict"]["accuracy"] if (run / "metrics.json").exists() else None
    metrics = evaluate(rows, release, options_seed=seed, seed=seed, min_group_size=30)
    out = {"run": run.name, "recomputed": recompute, "verdicts_changed": changed,
           "acc_before": old, "acc_after": metrics["verdict"]["accuracy"]}
    if not dry:
        if (run / "metrics.json").exists() and not (run / "metrics.pre_relabel.json").exists():
            shutil.copy(run / "metrics.json", run / "metrics.pre_relabel.json")
        if recompute:
            with open(run / "predictions.jsonl", "w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row) + "\n")
        metrics["run_config"] = cfg
        metrics["retested"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        write_report(metrics, run, rows=rows, release=release)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--db", type=Path, default=REPO / "data" / "medtempo_eval.db")
    a = ap.parse_args()
    executor = ReadOnlyExecutor(a.db, timeout_s=30.0, row_cap=100_000)
    for run in a.runs:
        if not (run / "predictions.jsonl").exists() or not (run / "config.json").exists():
            print(f"skip {run.name}: no predictions/config"); continue
        r = retest(run, executor, dry=a.dry)
        d = (r["acc_after"] - r["acc_before"]) if r["acc_before"] is not None else float("nan")
        print(f"{r['run']:58s} recomputed={str(r['recomputed']):5s} verdicts_changed={r['verdicts_changed']:4d} "
              f"acc {r['acc_before'] if r['acc_before'] is not None else 'n/a'} -> {r['acc_after']:.4f} ({d:+.4f})")


if __name__ == "__main__":
    main()
