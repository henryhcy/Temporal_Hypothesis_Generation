"""Cost and latency per record for a set of runs (2026-10-14).

For every run directory: records, mean and median wall latency per record (the
harness is sequential, so for a local row the latency sum IS the GPU time),
prompt / completion tokens per record, and for API rows the dollar cost from the
real usage split (``api_cache_usage.json``) at the list prices below. Records
served entirely from the disk cache have ~0 latency; a row whose median latency
is under one second is marked ``cached`` (its live cost is in the row it was
cached from, e.g. the planner row after D').

    PYTHONPATH=src .venv313/bin/python scripts/cost_latency.py --runs results/dev_opus_* --tex
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

# USD per million tokens: (input, output, cache-read fraction of input, cache-write fraction)
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.05, 1.25),
    "claude-opus-5": (5.0, 25.0, 0.10, 1.25),
    "gpt-5.6-sol": (4.0, 20.0, 0.10, 0.0),
    "gpt-6-astra": (10.0, 50.0, 0.10, 0.0),
    "gpt-6.1-sol": (2.0, 10.0, 0.05, 0.0),
}


def _price(model: str) -> tuple[float, float, float, float] | None:
    for k, v in PRICES.items():
        if model.startswith(k):
            return v
    return None


def summarise(run: Path) -> dict:
    rows = [json.loads(l) for l in (run / "predictions.jsonl").open()]
    cfg = json.loads((run / "config.json").read_text())
    lat = [float(r.get("latency_ms") or 0.0) / 1000.0 for r in rows]
    toks = [r.get("tokens") or {} for r in rows]
    n = len(rows)
    out = {
        "run": run.name, "model": cfg.get("model"), "sql_model": cfg.get("sql_model"),
        "provider": cfg.get("provider"), "n": n,
        "latency_mean_s": statistics.fmean(lat) if lat else None,
        "latency_median_s": statistics.median(lat) if lat else None,
        "latency_total_s": sum(lat),
        "prompt_tok_per_rec": statistics.fmean(t.get("prompt", 0) or 0 for t in toks) if toks else None,
        "completion_tok_per_rec": statistics.fmean(t.get("completion", 0) or 0 for t in toks) if toks else None,
        "cached_row": bool(lat) and statistics.median(lat) < 1.0,
        "usd_total": None, "usd_per_rec": None,
    }
    usage_path = run / "api_cache_usage.json"
    price = _price(str(cfg.get("model") or ""))
    if usage_path.exists() and price:
        u = json.loads(usage_path.read_text())
        i, o, rf, wf = price
        usd = (u.get("uncached", 0) * i + u.get("cache_read", 0) * i * rf
               + u.get("cache_write", 0) * i * wf + u.get("output", 0) * o) / 1e6
        out["usd_total"] = usd
        out["usd_per_rec"] = usd / n if n else None
        out["reasoning_tok_per_rec"] = (u.get("reasoning", 0) / n) if n else None
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, nargs="+", required=True)
    ap.add_argument("--tex", action="store_true")
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()
    res = [summarise(r) for r in args.runs if (r / "predictions.jsonl").exists()]
    if args.json:
        args.json.write_text(json.dumps(res, indent=2), encoding="utf-8")
    hdr = f"{'run':52s} {'n':>4s} {'lat s/rec':>10s} {'GPU/wall s':>10s} {'tok/rec':>12s} {'USD/rec':>8s} {'USD':>7s}"
    print(hdr)
    for r in res:
        tag = " (cached)" if r["cached_row"] else ""
        tok = f"{r['prompt_tok_per_rec'] or 0:.0f}+{r['completion_tok_per_rec'] or 0:.0f}"
        usd_r = f"{r['usd_per_rec']:.4f}" if r["usd_per_rec"] is not None else "0"
        usd = f"{r['usd_total']:.2f}" if r["usd_total"] is not None else "0"
        print(f"{(r['run'] + tag)[:52]:52s} {r['n']:4d} {r['latency_mean_s'] or 0:10.1f} "
              f"{r['latency_total_s']:10.0f} {tok:>12s} {usd_r:>8s} {usd:>7s}")
    if args.tex:
        print("\n\\begin{tabular}{lrrrr}\n\\toprule\nrow & s / record & tokens / record & USD / record & USD / 200 \\\\\n\\midrule")
        for r in res:
            tok = f"{(r['prompt_tok_per_rec'] or 0) + (r['completion_tok_per_rec'] or 0):,.0f}"
            usd_r = f"{r['usd_per_rec']:.4f}" if r["usd_per_rec"] is not None else "0"
            usd = f"{r['usd_total']:.2f}" if r["usd_total"] is not None else "0"
            lat = "cached" if r["cached_row"] else f"{r['latency_mean_s']:.1f}"
            print(f"{r['run'].replace('_', ' ')} & {lat} & {tok} & {usd_r} & {usd} \\\\")
        print("\\bottomrule\n\\end{tabular}")


if __name__ == "__main__":
    main()
