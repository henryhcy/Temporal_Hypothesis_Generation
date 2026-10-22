"""Rows for the 204-claim agentic subsample (tab:subsample) and the DiscoveryBench cells of tab:main
(2026-10-22). No model calls: reads finished predictions. DiscoveryBench verdicts are parsed by
~/discoverybench_baseline/score.py.

    PYTHONPATH=src .venv313/bin/python scripts/subsample_rows.py
"""
import json, random, sys
from pathlib import Path

R = Path(__file__).resolve().parents[1] / "results"
DB = Path.home() / "discoverybench_baseline"
sys.path.insert(0, str(DB))
from score import verdict  # noqa: E402

SUB = [json.loads(l)["id"] for l in open(DB / "claims_subsample.jsonl")]
S = set(SUB)
CLASSES = ("supported", "refuted", "insufficient")


def boot(pairs, n=2000, seed=0):
    rng = random.Random(seed); xs = [g == p for g, p in pairs]; k = len(xs)
    accs = sorted(sum(rng.choice(xs) for _ in range(k)) / k for _ in range(n))
    return sum(xs) / k, accs[int(0.025 * n)], accs[int(0.975 * n) - 1]


def prf(pairs):
    ps, rs, fs = [], [], []
    for c in CLASSES:
        tp = sum(g == c and p == c for g, p in pairs); fp = sum(g != c and p == c for g, p in pairs); fn = sum(g == c and p != c for g, p in pairs)
        pr = tp / (tp + fp) if tp + fp else 0.0; rc = tp / (tp + fn) if tp + fn else 0.0
        ps.append(pr); rs.append(rc); fs.append(2 * pr * rc / (pr + rc) if pr + rc else 0.0)
    return sum(ps) / 3, sum(rs) / 3, sum(fs) / 3


def harness_pairs(run):
    out = []
    for l in open(R / run / "predictions.jsonl"):
        x = json.loads(l)
        if x["hypothesis_id"] in S:
            g = x.get("gold", {}).get("verdict") if isinstance(x.get("gold"), dict) else None
            out.append((x["hypothesis_id"], (x.get("prediction") or {}).get("verdict") or "none"))
    return out


def main():
    gold = {json.loads(l)["id"]: json.loads(l)["gold"] for l in open(DB / "claims.jsonl")}
    rows = []
    for m, label in (("qwen38", "qwen3.8-27B"), ("gemma4", "gemma4-31B")):
        r = [json.loads(l) for l in open(DB / "runs" / m / "predictions.jsonl")]
        sub = {x["id"]: (verdict(x["output"])[0] or "none") for x in r if x["id"] in S}
        full = {x["id"]: (verdict(x["output"])[0] or "none") for x in r}
        pairs = [(gold[i], sub[i]) for i in SUB if i in sub]
        a, lo, hi = boot(pairs); p, rc, f = prf(pairs)
        print(f"DiscoveryBench + codebook ({label}): n={len(pairs)}  {a:.3f} [{lo:.3f}, {hi:.3f}]  main-cell {a:.3f}\\,{{\\scriptsize({p:.3f}/{rc:.3f}/{f:.3f})}}  (full-test rows so far: {len(full)})")
    for run, label in (("test_qwen38_27b_cellB", "EHRSQL-C (qwen3.8-27B)"), ("test_gemma4_31b_cellB", "EHRSQL-C (gemma4-31B)"),
                       ("test_q25pair_cellB", "EHRSQL-C (pair, check 0.593)")):
        hp = dict(harness_pairs(run)); pairs = [(gold[i], hp[i]) for i in SUB]
        a, lo, hi = boot(pairs)
        fullp = [(gold[json.loads(l)["hypothesis_id"]], (json.loads(l).get("prediction") or {}).get("verdict") or "none") for l in open(R / run / "predictions.jsonl")]
        fa, flo, fhi = boot(fullp)
        print(f"{label}: full {fa:.3f} [{flo:.3f}, {fhi:.3f}]  same-204 {a:.3f} [{lo:.3f}, {hi:.3f}]")


if __name__ == "__main__":
    main()
