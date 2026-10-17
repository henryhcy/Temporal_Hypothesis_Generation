"""Every number in the paper's test-set tables, from the finished runs (2026-10-16).

Reads metrics.json (verdict accuracy, 95% CI, denominator F1), the gold-sets
run (faithfulness via scripts/s2_attribution, abstention via
scripts/abstention_metrics) and the per-family accuracies (scripts/group_table),
and prints the LaTeX tabulars: main (systems x models, ours at the bottom),
evidence (den-F1 / faithfulness / false-decisiveness / over-abstention),
families, modular analysis vs gold, verifier rounds, report-tier case study.
Nothing is re-run; ``--json`` dumps the raw numbers.

    PYTHONPATH=src .venv313/bin/python scripts/paper_tables.py --json results/paper_tables_test.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import s2_attribution as S2  # noqa: E402
import abstention_metrics as AB  # noqa: E402
from group_table import family_of  # noqa: E402

R = REPO / "results"
MODELS = [("q25pair", "Qwen2.5-32B pair"), ("qwen38_27b", "qwen3.8-27B"), ("gemma4_31b", "gemma4-31B"),
          ("opus", "Opus 5.5"), ("gpt", "GPT-5.6")]
# row key -> (label, run suffix, is_ours)
ROWS = [("counts", "counts-given judgment (gold $n,k$; S3 alone)", "counts", False),
        ("cellA", "A: sentence $\\rightarrow$ SQL, schema only", "cellA", False),
        ("cellB", "B: \\quad + conventions stated", "cellB", False),
        ("dprime", "D$'$: plan as contract, no verifier", "dprime", True),
        ("dprime_verify2", "\\textbf{D$'$ + verifier} (2 rounds)", "dprime_verify2", True)]
MODULAR = [("planner_verify1", "S1 alone: model plan, gold S2/S3 (1 round)"),
           ("sqlalone_verify2", "S2 alone: gold plan, model SQL (2 rounds)"),
           ("counts", "S3 alone: gold counts, model test"),
           ("dprime", "S1 + S2 + S3, plan as contract"),
           ("dprime_verify2", "\\quad + verifier (2 rounds)")]
ROUNDS = ["dprime", "dprime_verify1", "dprime_verify2", "dprime_verify3"]


def run_dir(model: str, suffix: str, prefix: str = "test") -> Path | None:
    p = R / f"{prefix}_{model}_{suffix}"
    return p if (p / "metrics.json").exists() else None


def acc(p: Path | None) -> tuple[float | None, list | None, float | None]:
    if p is None:
        return None, None, None
    m = json.loads((p / "metrics.json").read_text())
    v = m["verdict"]
    return v.get("accuracy"), v.get("accuracy_ci95"), (m.get("retrieval", {}).get("denominator", {}) or {}).get("f1")


def fmt(a, bold=False):
    if a is None:
        return "---"
    s = f"{a:.3f}"
    return f"\\textbf{{{s}}}" if bold else s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--gold", type=Path, default=R / "test_gold_sets")
    ap.add_argument("--db", type=Path, default=REPO / "data" / "medtempo_eval.db")
    args = ap.parse_args()
    gold = {x["hypothesis_id"]: x for x in S2.read(args.gold)}
    fm, vac = S2.load_db(args.db)
    out: dict = {"main": {}, "evidence": {}, "families": {}, "modular": {}, "rounds": {}, "report": {}}

    # --- main: systems x models -------------------------------------------
    print("% ===== tab:main (test set, 1,500 cohort claims) =====")
    print("\\begin{tabular}{l" + "r" * len(MODELS) + "}\n\\toprule")
    print("system & " + " & ".join(l for _, l in MODELS) + " \\\\\n\\midrule")
    for key, label, suffix, ours in ROWS:
        if key == "dprime":
            print("\\midrule")
        cells = []
        for m, _ in MODELS:
            a, ci, _ = acc(run_dir(m, suffix))
            out["main"].setdefault(key, {})[m] = {"acc": a, "ci95": ci}
            cells.append(fmt(a, bold=(key == "dprime_verify2" and a is not None)))
        print(f"{label} & " + " & ".join(cells) + " \\\\")
    print("\\bottomrule\n\\end{tabular}\n")

    # --- evidence: den-F1, faithfulness, false-dec, over-abst for B and D'+2 --
    print("% ===== tab:evidence =====")
    print("\\begin{tabular}{ll" + "r" * len(MODELS) + "}\n\\toprule")
    print("metric & system & " + " & ".join(l for _, l in MODELS) + " \\\\\n\\midrule")
    ev_rows = [("cellB", "B"), ("dprime_verify2", "D$'$ + verifier")]
    metrics_cache: dict[tuple, dict] = {}
    for m, _ in MODELS:
        for suffix, _lab in ev_rows:
            p = run_dir(m, suffix)
            if p is None:
                continue
            a, ci, den = acc(p)
            at = S2.attribute(p, gold, fm, vac)
            ab = AB.metrics(p, gold)
            metrics_cache[(m, suffix)] = {"den_f1": den, "faithfulness": at["faithfulness"],
                                          "false_decisiveness": ab["false_decisiveness"],
                                          "over_abstention": ab["over_abstention"],
                                          "no_answer": ab["no_answer_rate"], "lucky": at["lucky"], "bad": at["bad"]}
            out["evidence"][f"{m}/{suffix}"] = metrics_cache[(m, suffix)]
    for metric, mlabel, nd in [("den_f1", "denominator F1", 3), ("faithfulness", "faithfulness", 2),
                               ("false_decisiveness", "false-decisiveness", 3), ("over_abstention", "over-abstention", 3)]:
        for suffix, slab in ev_rows:
            cells = []
            for m, _ in MODELS:
                v = metrics_cache.get((m, suffix), {}).get(metric)
                cells.append("---" if v is None else f"{v:.{nd}f}")
            print(f"{mlabel if suffix == 'cellB' else ''} & {slab} & " + " & ".join(cells) + " \\\\")
    print("\\bottomrule\n\\end{tabular}\n")

    # --- families -----------------------------------------------------------
    print("% ===== tab:families (test set; D'+2 / B per model) =====")
    from group_table import per_key  # noqa: E402
    from temporal_hypo.framework.io import load_release  # noqa: E402
    rel = load_release(REPO / "data" / "release" / "v1.2", verify_sha=False)
    fam_tables: dict[tuple, dict] = {}
    for m, _ in MODELS:
        for suffix in ("dprime_verify2", "cellB"):
            p = run_dir(m, suffix)
            if p is not None:
                fam_tables[(m, suffix)] = per_key(p, rel, family_of)
    fams = sorted({k for t in fam_tables.values() for k in t})
    print("\\begin{tabular}{lr" + "r" * len(MODELS) + "}\n\\toprule")
    print("family (D$'$ + verifier / B) & $n$ & " + " & ".join(l for _, l in MODELS) + " \\\\\n\\midrule")
    for f in fams:
        n = next((t[f][1] for t in fam_tables.values() if f in t), 0)
        cells = []
        for m, _ in MODELS:
            d = fam_tables.get((m, "dprime_verify2"), {}).get(f)
            b = fam_tables.get((m, "cellB"), {}).get(f)
            out["families"].setdefault(f, {})[m] = {"dprime_verify2": (d[0] / d[1]) if d else None, "cellB": (b[0] / b[1]) if b else None}
            cells.append((f"{d[0]/d[1]:.2f}" if d else "---") + " / " + (f"{b[0]/b[1]:.2f}" if b else "---"))
        print(f"{f} & {n} & " + " & ".join(cells) + " \\\\")
    print("\\bottomrule\n\\end{tabular}\n")

    # --- modular analysis vs gold ----------------------------------------------
    print("% ===== tab:modular (each stage alone vs gold; gold everywhere = 1.000) =====")
    print("\\begin{tabular}{l" + "r" * len(MODELS) + "}\n\\toprule")
    print("stages filled by the model (others at gold) & " + " & ".join(l for _, l in MODELS) + " \\\\\n\\midrule")
    print("none (deterministic oracle) & " + " & ".join(["1.000"] * len(MODELS)) + " \\\\")
    for suffix, label in MODULAR:
        cells = []
        for m, _ in MODELS:
            a, ci, _ = acc(run_dir(m, suffix))
            out["modular"].setdefault(suffix, {})[m] = a
            cells.append(fmt(a))
        print(f"{label} & " + " & ".join(cells) + " \\\\")
    print("\\bottomrule\n\\end{tabular}\n")

    # --- rounds ----------------------------------------------------------------
    print("% ===== tab:rounds (D' with 0/1/2/3 verify rounds; acc and den-F1) =====")
    print("\\begin{tabular}{l" + "r" * len(MODELS) + "}\n\\toprule")
    print("rounds & " + " & ".join(l for _, l in MODELS) + " \\\\\n\\midrule")
    for i, suffix in enumerate(ROUNDS):
        cells = []
        for m, _ in MODELS:
            a, ci, den = acc(run_dir(m, suffix))
            out["rounds"].setdefault(str(i), {})[m] = {"acc": a, "den_f1": den}
            cells.append("---" if a is None else f"{a:.3f} / {den:.2f}" if den is not None else f"{a:.3f}")
        print(f"{i} & " + " & ".join(cells) + " \\\\")
    print("\\bottomrule\n\\end{tabular}\n")

    # --- report-tier case study -------------------------------------------------
    print("% ===== tab:report (180 single-report claims) =====")
    rep_rows = [("cellA", "A: schema only"), ("cellB", "B: + conventions"), ("cellB_verify2", "B + repair"),
                ("planner_verify1", "planner alone"), ("dprime_verify2", "D$'$ + verifier")]
    print("\\begin{tabular}{l" + "r" * len(MODELS) + "}\n\\toprule")
    print("system (report tier) & " + " & ".join(l for _, l in MODELS) + " \\\\\n\\midrule")
    for suffix, label in rep_rows:
        cells = []
        for m, _ in MODELS:
            a, ci, _ = acc(run_dir(m, suffix, prefix="testrep"))
            out["report"].setdefault(suffix, {})[m] = a
            cells.append(fmt(a))
        if any(c != "---" for c in cells):
            print(f"{label} & " + " & ".join(cells) + " \\\\")
    print("\\bottomrule\n\\end{tabular}")

    if args.json:
        args.json.write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
