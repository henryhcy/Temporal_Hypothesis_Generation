"""Interim score of a running EHRAgent run against our pipeline on the SAME claims (2026-10-20).

For each EHRAgent predictions file: accuracy on the claims finished so far, with a bootstrap interval,
and our D'+verifier row (same model family) restricted to those claims, so the comparison is paired.
"""
import json, random, sys
from pathlib import Path
R = Path("/home/henryhcy/Temporal_Hypothesis_Generation/results")
E = Path("/home/henryhcy/ehragent_baseline")
gold = json.load(open(E / "medtempo_data/gold_map_test_cohort_v1.2.json"))
PAIRS = [("EHRAgent qwen3.8", E / "logs_testcohort_e2e_qwen38/predictions.jsonl", "ours qwen3.8 D'+2", R / "test_qwen38_27b_dprime_verify2/predictions.jsonl", None),
         ("EHRAgent GPT-5.6", E / "logs_testcohort_e2e_gpt56/predictions.jsonl", "ours GPT-5.6 D'", R / "test_gpt_dprime/predictions.jsonl", E / "api_usage_gpt56.jsonl"),
         ("EHRAgent Coder-32B (done)", E / "logs_testcohort_e2e_32b_min/predictions.jsonl", "ours Q2.5 pair D'+2", R / "test_q25pair_dprime_verify2/predictions.jsonl", None)]
def ci(c):
    rng = random.Random(0); d = sorted(sum(rng.choices(c, k=len(c))) / len(c) for _ in range(1000)); return d[25], d[974]
for name, ep, oname, op, usage in PAIRS:
    if not ep.exists(): continue
    er = [json.loads(l) for l in open(ep)]; done = {r["id"]: r for r in er}
    if not done: continue
    ec = [1 if r.get("pred_raw") == gold[r["id"]]["gold_verdict"] else 0 for r in er]
    ours = {}
    for l in open(op):
        r = json.loads(l); ours[r["hypothesis_id"]] = (r.get("prediction") or {}).get("response")
    oc = [1 if ours.get(i) == gold[i]["gold_verdict"] else 0 for i in done]
    lo, hi = ci(ec); olo, ohi = ci(oc)
    unp = sum(1 for r in er if not r.get("pred_raw"))
    line = (f"{name}: {sum(ec)}/{len(ec)} = {sum(ec)/len(ec):.3f} [{lo:.3f}, {hi:.3f}] (unparseable {unp}) | "
            f"{oname} on the same {len(oc)} claims: {sum(oc)/len(oc):.3f} [{olo:.3f}, {ohi:.3f}]")
    if usage and usage.exists():
        u = [json.loads(l) for l in open(usage)]; P = sum(x["prompt"] for x in u); C = sum(x["completion"] for x in u); K = sum(x.get("cached") or 0 for x in u)
        line += f" | cost so far ${((P-K)*4+K*0.4+C*20)/1e6:.2f}"
    print(line)
