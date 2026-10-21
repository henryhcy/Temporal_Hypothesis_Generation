"""Error analysis of the insufficient class on the test set (2026-10-20, for the Results section).

For every system x model: on the 505 gold-insufficient claims, how often a decisive verdict was
returned (overclaim), split by the gold sub-type, and how often the sub-type was right when the
system did abstain; on the 995 decisive claims, how often the system abstained (underclaim) and
why, read off the prediction: no plan (no answer), the query failed, the query returned no
qualifying report (claimed not-locatable), too few (claimed sparse), or a testable denominator
whose tail was not significant (claimed underpowered), the last split by whether that denominator
was the gold set. EHRAgent returns a bare verdict, so only its over- and underclaim are given.

    PYTHONPATH=src .venv313/bin/python scripts/insufficient_analysis.py [--tex]
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

R = Path(__file__).resolve().parents[1] / "results"
E = Path.home() / "ehragent_baseline"
MODELS = [("q25pair", "Qwen2.5-32B pair"), ("qwen38_27b", "qwen3.8-27B"), ("gemma4_31b", "gemma4-31B"),
          ("opus", "Opus 5.5"), ("gpt", "GPT-5.6")]
SYSTEMS = [("cellB", "B: Straight-to-SQL + codebook"), ("dprime_verify2", "ours: ART with the verifier")]
# the frontier rows of the main table are D' without the verifier at 0.999; the verifier rows are what
# the paper reports for every model, so the same suffix is used throughout
EHRAGENT = [("Qwen2.5-32B pair", E / "logs_testcohort_e2e_32b_min/predictions.jsonl"),
            ("qwen3.8-27B", E / "logs_testcohort_e2e_qwen38/predictions.jsonl"),
            ("GPT-5.6", E / "logs_testcohort_e2e_gpt56/predictions.jsonl")]


def load_gold():
    gold = {}
    for l in (R / "test_gold_sets" / "predictions.jsonl").open():
        x = json.loads(l)
        p = x["prediction"]
        arms = (x.get("retrieval") or {}).get("arms") or []
        gold[x["hypothesis_id"]] = (p["verdict"], p.get("subtype"), [set(a["denominator_ids"]) for a in arms])
    return gold


def analyse(run: Path, gold: dict) -> dict:
    c = Counter()
    for l in (run / "predictions.jsonl").open():
        x = json.loads(l)
        gv, gs, garms = gold[x["hypothesis_id"]]
        p = x.get("prediction") or {}
        resp = p.get("response")
        rt = x.get("retrieval") or {}
        if gv == "insufficient":
            c["ins_n"] += 1
            if resp in ("supported", "refuted"):
                c["over"] += 1; c[f"over_{gs}"] += 1
            elif resp == "insufficient":
                c["abstain"] += 1; c["sub_ok"] += (p.get("subtype") == gs)
            else:
                c["ins_none"] += 1
        else:
            c["dec_n"] += 1
            if resp is None or resp == "underdetermined":
                c["dec_none"] += 1
            elif resp == "insufficient":
                c["under"] += 1
                arms = rt.get("arms") or []
                failed = rt.get("ok") is False or any((q.get("error") for q in (rt.get("queries") or [])))
                if failed:
                    c["u_failed"] += 1
                else:
                    sub = p.get("subtype")
                    if sub == "not_locatable":
                        c["u_empty"] += 1
                    elif sub == "sparse":
                        c["u_thin"] += 1
                    else:
                        exact = bool(arms) and len(arms) == len(garms) and all(set(a.get("denominator_ids") or []) == g for a, g in zip(arms, garms))
                        c["u_power_exact" if exact else "u_power_wrong"] += 1
    return c


def analyse_ehragent(path: Path, gold: dict) -> dict | None:
    if not path.exists():
        return None
    c = Counter()
    for l in path.open():
        x = json.loads(l)
        gv, gs, _ = gold[x["id"]]
        resp = x.get("pred_raw")
        if gv == "insufficient":
            c["ins_n"] += 1
            if resp in ("supported", "refuted"):
                c["over"] += 1; c[f"over_{gs}"] += 1
            elif resp == "insufficient":
                c["abstain"] += 1
            else:
                c["ins_none"] += 1
        else:
            c["dec_n"] += 1
            if resp == "insufficient":
                c["under"] += 1
            elif resp not in ("supported", "refuted"):
                c["dec_none"] += 1
    c["partial"] = c["ins_n"] + c["dec_n"] < 1500
    return c


def fmt(c: dict, ehr=False) -> str:
    f = lambda a, b: f"{a / b:.3f}" if b else "---"
    over = f(c["over"], c["ins_n"])
    o_nl = f(c["over_not_locatable"], 176) if not ehr or True else "---"
    o_sp = f(c["over_sparse"], 157)
    o_up = f(c["over_underpowered"], 172)
    sub = f(c["sub_ok"], c["abstain"]) if not ehr else "---"
    under = f(c["under"], c["dec_n"])
    none = f(c["dec_none"] + c["ins_none"], c["ins_n"] + c["dec_n"])
    if ehr:
        causes = "--- & --- & --- & --- & ---"
    else:
        causes = " & ".join(f(c[k], c["dec_n"]) for k in ("u_failed", "u_empty", "u_thin", "u_power_wrong", "u_power_exact"))
    return f"{over} & {o_nl} & {o_sp} & {o_up} & {sub} & {under} & {causes} & {none}"


def main():
    gold = load_gold()
    tex = "--tex" in sys.argv
    rows = []
    for suf, sname in SYSTEMS:
        for key, mname in MODELS:
            run = R / f"test_{key}_{suf}"
            if not run.exists():
                continue
            c = analyse(run, gold)
            rows.append((sname, mname, c, False))
    for mname, path in EHRAGENT:
        c = analyse_ehragent(path, gold)
        if c:
            rows.append(("EHRAgent, own test", mname + (" (partial)" if c["partial"] else ""), c, True))
    if tex:
        last = None
        for sname, mname, c, ehr in rows:
            if sname != last:
                print(f"\\multicolumn{{13}}{{@{{}}l}}{{\\textit{{{sname}}}}} \\\\")
                last = sname
            print(f"\\quad {mname} & {fmt(c, ehr)} \\\\")
    else:
        print(f"{'system':28s} {'model':18s} over  o_nl  o_sp  o_up  subok under fail  empty thin  pwrW  pwrE  none")
        for sname, mname, c, ehr in rows:
            print(f"{sname:28s} {mname:18s} " + fmt(c, ehr).replace(" & ", " ").replace("---", " ---"))
            if not ehr:
                print(f"{'':48s} counts: over {c['over']}/{c['ins_n']} (nl {c['over_not_locatable']}, sp {c['over_sparse']}, up {c['over_underpowered']}), "
                      f"sub_ok {c['sub_ok']}/{c['abstain']}, under {c['under']}/{c['dec_n']} = failed {c['u_failed']} empty {c['u_empty']} thin {c['u_thin']} "
                      f"pwr-wrong {c['u_power_wrong']} pwr-exact {c['u_power_exact']}, none {c['dec_none']}+{c['ins_none']}")
            else:
                print(f"{'':48s} counts: over {c['over']}/{c['ins_n']} (nl {c['over_not_locatable']}, sp {c['over_sparse']}, up {c['over_underpowered']}), under {c['under']}/{c['dec_n']}, none {c['dec_none']}+{c['ins_none']}")


if __name__ == "__main__":
    main()
