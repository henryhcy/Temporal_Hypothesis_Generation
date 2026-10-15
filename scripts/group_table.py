"""Per-group and per-family verdict accuracy for a set of finished runs (2026-10-15).

Reads each run's predictions.jsonl, joins the gold verdict from the release,
and prints accuracy by hypothesis group (C-V1, P-M2, ...) and by claim family
(precedes, co-occurs, sequence, first/last, position, proximity, threshold),
one column per run. ``--tex`` also prints a LaTeX tabular. Nothing is re-run.

    PYTHONPATH=src .venv313/bin/python scripts/group_table.py \
        --runs results/test_q25pair_dprime_verify2 results/test_gemma4_31b_dprime_verify2 \
        --labels "Q2.5 pair D'+2" "gemma4 D'+2" --by family --tex
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from temporal_hypo.framework.io import load_release

FAMILY = {"P": "precedes", "C": "co-occurs", "S": "sequence", "F": "first/last",
          "T": "position", "Y": "proximity", "H": "threshold"}


def family_of(group: str) -> str:
    return FAMILY.get(group.split("-")[0], group.split("-")[0])


def tier_of(group: str) -> str:
    t = group.split("-")[1][0]
    return {"R": "report", "V": "cohort", "M": "multi"}.get(t, t)


def per_key(run: Path, release, key) -> dict[str, tuple[int, int]]:
    """{key: (right, n)} over the run's records; key is a function of group_id."""
    acc: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for line in (run / "predictions.jsonl").open():
        r = json.loads(line)
        gold = release.answer_for(r["hypothesis_id"])["gold_verdict"]
        pred = (r.get("prediction") or {}).get("response")
        k = key(r["group_id"])
        acc[k][1] += 1
        acc[k][0] += int(pred == gold)
    return {k: (v[0], v[1]) for k, v in acc.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, nargs="+", required=True)
    ap.add_argument("--labels", nargs="*", default=None)
    ap.add_argument("--by", choices=("group", "family", "tier"), default="group")
    ap.add_argument("--release", type=Path, default=Path("data/release/v1.2"))
    ap.add_argument("--tex", action="store_true")
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()
    rel = load_release(args.release, verify_sha=False)
    key = {"group": (lambda g: g), "family": family_of, "tier": tier_of}[args.by]
    labels = args.labels or [r.name for r in args.runs]
    tables = [per_key(r, rel, key) for r in args.runs]
    keys = sorted({k for t in tables for k in t}, key=lambda k: (family_of(k) if args.by == "group" else k, k))
    w = max(len(k) for k in keys) + 2
    print(f"{args.by:{w}s}" + "".join(f"{l[:16]:>18s}" for l in labels))
    rows = {}
    for k in keys:
        cells = []
        for t in tables:
            r, n = t.get(k, (0, 0))
            cells.append((r / n if n else None, n))
        rows[k] = cells
        print(f"{k:{w}s}" + "".join(f"{(f'{a:.3f} (n={n})' if a is not None else '---'):>18s}" for a, n in cells))
    if args.json:
        args.json.write_text(json.dumps({k: [{"acc": a, "n": n} for a, n in v] for k, v in rows.items()}, indent=2))
    if args.tex:
        print("\n\\begin{tabular}{l" + "r" * len(labels) + "}\n\\toprule")
        print(f"{args.by} & " + " & ".join(labels) + " \\\\\n\\midrule")
        for k in keys:
            print(f"{k} & " + " & ".join(f"{a:.3f}" if a is not None else "---" for a, _ in rows[k]) + " \\\\")
        print("\\bottomrule\n\\end{tabular}")


if __name__ == "__main__":
    main()
