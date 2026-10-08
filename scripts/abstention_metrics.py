"""Abstention metrics (decisions.md 2026-10-06): does a system refuse to decide
exactly when the data cannot decide, and does it know why?

On the cohort tiers (the report tier has no insufficient class by design):

- false-decisiveness  = P(pred in {supported, refuted} | gold insufficient)
                        -- the system invented a result the data cannot support
- over-abstention     = P(pred == insufficient | gold decisive)
- subtype accuracy    = P(pred subtype == gold subtype | gold insufficient and
                        pred insufficient)  over not_locatable / sparse / underpowered
- no-answer rate      = P(pred is underdetermined / missing | any gold)

Gold comes from a ``rules+compiler`` run on the same slice (the oracle's
verdict and subtype), exactly as ``s2_attribution.py`` takes it.

    python scripts/abstention_metrics.py --gold results/v12_smoke200_gold_sets \
        --runs results/v12_smoke200_toolbox_instruct32b_zeroshot_c2f ...
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

DECISIVE = ("supported", "refuted")
SUBTYPES = ("not_locatable", "sparse", "underpowered")


def read(run: Path) -> list[dict]:
    return [json.loads(l) for l in open(run / "predictions.jsonl")]


def is_report(x: dict) -> bool:
    return x["group_id"].split("-")[1].startswith("R")


def metrics(run: Path, gold: dict[str, dict]) -> dict:
    n_insuf = n_dec = n_total = 0
    false_dec = over_abst = no_answer = 0
    sub_n = sub_ok = 0
    sub_conf: collections.Counter = collections.Counter()
    for x in read(run):
        if is_report(x):
            continue
        g = gold.get(x["hypothesis_id"])
        if not g:
            continue
        gp = g.get("prediction") or {}
        gv, gs = gp.get("verdict"), gp.get("subtype")
        if gv is None:
            continue
        n_total += 1
        pp = x.get("prediction") or {}
        pv, ps = pp.get("verdict"), pp.get("subtype")
        if pv is None or pp.get("response") == "underdetermined":
            no_answer += 1
            continue
        if gv == "insufficient":
            n_insuf += 1
            if pv in DECISIVE:
                false_dec += 1
            elif gs in SUBTYPES:
                sub_n += 1
                sub_ok += int(ps == gs)
                sub_conf[(gs, ps)] += 1
        elif gv in DECISIVE:
            n_dec += 1
            if pv == "insufficient":
                over_abst += 1
    r = lambda a, b: (a / b) if b else None
    return {"run": run.name, "n": n_total, "n_gold_insufficient": n_insuf, "n_gold_decisive": n_dec,
            "false_decisiveness": r(false_dec, n_insuf), "over_abstention": r(over_abst, n_dec),
            "subtype_accuracy": r(sub_ok, sub_n), "no_answer_rate": r(no_answer, n_total),
            "subtype_confusion": {f"{g}->{p}": c for (g, p), c in sub_conf.items()}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, required=True)
    ap.add_argument("--runs", type=Path, nargs="+", required=True)
    ap.add_argument("--json", type=Path, default=None, help="also write the rows here")
    args = ap.parse_args()
    gold = {x["hypothesis_id"]: x for x in read(args.gold)}
    rows = [metrics(r, gold) for r in args.runs]
    f = lambda v: "   -  " if v is None else f"{v:6.3f}"
    print(f"{'run':52s} {'n':>4} {'insuf':>5} {'falseDec':>8} {'overAbst':>8} {'subtype':>7} {'noAns':>6}")
    for m in rows:
        print(f"{m['run'][:52]:52s} {m['n']:4d} {m['n_gold_insufficient']:5d} {f(m['false_decisiveness']):>8} "
              f"{f(m['over_abstention']):>8} {f(m['subtype_accuracy']):>7} {f(m['no_answer_rate']):>6}")
    if args.json:
        args.json.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
