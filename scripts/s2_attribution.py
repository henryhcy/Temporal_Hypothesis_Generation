"""Attribute every S2 denominator failure to a named conditioning rule, and
compute the faithfulness score P(stages right | verdict right).

For each cohort-tier record the prediction stores the report ids it put in each
arm's denominator; the compiler run (``--pipeline rules+compiler``, S1 and S2 at
gold) stores the gold ids.  Every wrongly-included report is checked against the
claim's own rule in the eval DB (cohort, event presence, co-existence, ties) and
every wrongly-dropped report against the rules that forbid dropping it; a record
takes its dominant cause.  "denominator = numerator" is the query that defines the
eligible set as the supporting set (n = k), so the claim is supported for free.

    python scripts/s2_attribution.py --gold results/v11_smoke200_gold_sets \
        --runs results/v11_smoke200_rules_llmsql_coder32b ... [--tex]
"""
from __future__ import annotations

import argparse
import collections
import json
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CAUSES = ["no plan (S2 not run)", "no valid SQL", "denominator = numerator", "event absent", "co-exist leak",
          "wrong cohort", "tie leak", "split narrowed to co-occurrence",
          "co-exist wrongly dropped", "other omission", "other over-inclusion"]


def load_db(path: Path):
    con = sqlite3.connect(path)
    fm: dict[int, dict[str, int]] = collections.defaultdict(dict)
    vac = dict(con.execute("SELECT vaers_id, vaccine FROM reports"))
    for vid, t, l in con.execute("SELECT vaers_id, term, level FROM first_mention"):
        fm[vid][t] = l
    return fm, vac


def read(run: Path) -> list[dict]:
    return [json.loads(l) for l in open(run / "predictions.jsonl")]


def is_report_tier(x: dict) -> bool:
    return x["group_id"].split("-")[1].startswith("R")


def attribute(run: Path, gold: dict[str, dict], fm, vac):
    rows = read(run)
    n_coh = bad = lucky = verdict_right = faithful = 0
    causes: collections.Counter = collections.Counter()
    for x in rows:
        if is_report_tier(x):
            continue
        g = gold.get(x["hypothesis_id"])
        if not g or not g.get("retrieval", {}).get("arms"):
            continue
        n_coh += 1
        cl = g["claim"]
        ev = [e["term"] for e in cl["events"]]
        cond = cl["procedure"]["conditioning"]
        v = (cl.get("cohorts") or [{}])[0].get("vaccine")
        gold_verdict = g["prediction"]["verdict"]
        right = (x.get("prediction") or {}).get("verdict") == gold_verdict
        verdict_right += right
        rt = x.get("retrieval") or {}
        parms = rt.get("arms") or []
        if not parms:                      # S1 produced no usable plan; S2 never ran
            bad += 1
            causes["no plan (S2 not run)"] += 1
            continue
        if rt.get("ok") is False:          # a statement failed to execute; arms are empty placeholders
            bad += 1
            causes["no valid SQL"] += 1
            continue
        rc: collections.Counter = collections.Counter()
        for ga, pa in zip(g["retrieval"]["arms"], parms):
            G, P = set(ga["denominator_ids"]), set(pa.get("denominator_ids") or [])
            gnum = set(ga.get("numerator_ids") or [])
            if pa.get("n") and pa.get("n") == pa.get("k") and G - P:
                rc["denominator = numerator"] += len(G - P)
                continue
            for r in P - G:
                rc[_over(r, ev, cond, v, fm, vac)] += 1
            miss = G - P
            if miss and all(r not in gnum for r in miss):
                rc["denominator = numerator"] += len(miss)   # only the non-supporting reports dropped
            else:
                for r in miss:
                    rc[_under(r, ev, cond, fm)] += 1
        if rc:
            bad += 1
            causes[rc.most_common(1)[0][0]] += 1
            lucky += right
        elif right:
            faithful += 1
    return {"run": run.name, "n": n_coh, "bad": bad, "lucky": lucky, "verdict_right": verdict_right,
            "faithfulness": (faithful / verdict_right) if verdict_right else None, "causes": causes}


def _over(r, ev, cond, v, fm, vac):
    terms = fm.get(r, {})
    if v and vac.get(r) != v:
        return "wrong cohort"
    if any(e not in terms for e in ev):
        return "event absent"
    if cond in ("ordered_pair", "orderable_triple") and len({terms[e] for e in ev}) < len(ev):
        return "co-exist leak"
    if cond.startswith("all_present_unique"):
        lv = [terms[e] for e in ev]
        ext = min(lv) if "first" in cond else max(lv)
        if lv.count(ext) > 1:
            return "tie leak"
    return "other over-inclusion"


def _under(r, ev, cond, fm):
    terms = fm.get(r, {})
    if cond == "both_present" and all(e in terms for e in ev) and len({terms[e] for e in ev}) < len(ev):
        return "co-exist wrongly dropped"
    if cond == "presence_split" and any(e not in terms for e in ev):
        return "split narrowed to co-occurrence"
    return "other omission"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, required=True, help="rules+compiler run dir (gold sets)")
    ap.add_argument("--runs", type=Path, nargs="+", required=True)
    ap.add_argument("--db", type=Path, default=REPO / "data" / "medtempo_eval.db")
    ap.add_argument("--tex", action="store_true", help="also print a LaTeX tabular")
    args = ap.parse_args()
    fm, vac = load_db(args.db)
    gold = {x["hypothesis_id"]: x for x in read(args.gold)}
    res = [attribute(r, gold, fm, vac) for r in args.runs]
    for r in res:
        print(f"{r['run']}: n={r['n']} wrong-denominator={r['bad']} lucky={r['lucky']} "
              f"faithfulness={r['faithfulness']:.3f}  " + ", ".join(f"{c}={r['causes'][c]}" for c in CAUSES if r['causes'][c]))
    if args.tex:
        print("\\begin{tabular}{l" + "r" * len(res) + "}\n\\toprule\ncause & " + " & ".join(r["run"].replace("v11_smoke200_", "").replace("_", "\\_") for r in res) + " \\\\\n\\midrule")
        for c in CAUSES:
            if any(r["causes"][c] for r in res):
                print(c + " & " + " & ".join(str(r["causes"][c]) for r in res) + " \\\\")
        print("\\midrule\nwrong denominators & " + " & ".join(str(r["bad"]) for r in res) + " \\\\")
        print("\\quad of which verdict still right & " + " & ".join(str(r["lucky"]) for r in res) + " \\\\")
        print("faithfulness $P(\\text{denominator exact} \\mid \\text{verdict right})$ & " + " & ".join(f"{r['faithfulness']:.2f}" for r in res) + " \\\\\n\\bottomrule\n\\end{tabular}")


if __name__ == "__main__":
    main()
