"""Appendix table: retrieval failures on the test set attributed to the rule violated (2026-10-22).

Re-uses scripts/s2_attribution.py (no model calls) on the test runs and prints the LaTeX tabular pasted
into docs/draft/appendix.tex (app:attribution). Columns are system blocks; rows the dominant cause per
record. Runs that have not finished are skipped, so re-run when the queue completes.

    PYTHONPATH=src .venv313/bin/python scripts/test_attribution_table.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import s2_attribution as S2  # noqa: E402

R = HERE.parent / "results"
MODELS = [("q25pair", "pair"), ("qwen38_27b", "qwen3.8"), ("gemma4_31b", "gemma4"), ("opus", "Opus"), ("gpt", "GPT")]
# 2026-10-23 (user): the three systems the main text compares, every model; EHRSQL is the source of the
# per-rule counts in RQ1. The repaired-baseline and no-repair blocks were dropped (not discussed in the text).
BLOCKS = [("EHRSQL", "cellA", [m for m, _ in MODELS]),
          ("EHRSQL-C", "cellB", [m for m, _ in MODELS]),
          ("\\art{}", "dprime_verify2", [m for m, _ in MODELS])]
ROWS = [("no plan (S2 not run)", "no plan from S1 (S2 not run)"),
        ("no valid SQL", "SQL failed to execute"),
        ("denominator = numerator", "denominator $=$ numerator ($n = k$)"),
        ("event absent", "event absent from the report"),
        ("wrong cohort", "report from the wrong cohort"),
        ("co-exist leak", "\\emph{co-exist} leak into an order denominator"),
        ("non-consecutive pair leak", "gapped pair in an \\emph{immediate} denominator"),
        ("no-half report leak", "unsplittable report in a position denominator"),
        ("tie leak", "tie leak into a first/last denominator"),
        ("split narrowed to co-occurrence", "presence split narrowed to co-occurrence"),
        ("co-exist wrongly dropped", "\\emph{co-exist} report wrongly dropped"),
        ("other omission", "other omission"),
        ("other over-inclusion", "other over-inclusion")]


def main() -> None:
    fm, vac = S2.load_db(HERE.parent / "data" / "medtempo_eval.db")
    gold = {x["hypothesis_id"]: x for x in S2.read(R / "test_gold_sets")}
    cols = []
    for block, suf, keys in BLOCKS:
        for k in keys:
            run = R / f"test_{k}_{suf}"
            if (run / "metrics.json").exists():          # finished runs only
                cols.append((block, dict(MODELS)[k], S2.attribute(run, gold, fm, vac)))
    print("\\begin{tabular}{@{}l" + "r" * len(cols) + "@{}}\n\\toprule")
    head, i = [], 2
    for block, _, _ in BLOCKS:
        n = sum(1 for b, _, _ in cols if b == block)
        if n:
            head.append(f"\\multicolumn{{{n}}}{{c}}{{{block}}}")
    print(" & " + " & ".join(head) + " \\\\")
    rules, i = [], 2
    for block, _, _ in BLOCKS:
        n = sum(1 for b, _, _ in cols if b == block)
        if n:
            rules.append(f"\\cmidrule(lr){{{i}-{i + n - 1}}}"); i += n
    print("".join(rules))
    print("dominant cause per record & " + " & ".join(m for _, m, _ in cols) + " \\\\\n\\midrule")
    for key, label in ROWS:
        if any(c["causes"][key] for _, _, c in cols):
            print(label + " & " + " & ".join(str(c["causes"][key]) for _, _, c in cols) + " \\\\")
    print("\\midrule\nwrong or missing denominators & " + " & ".join(str(c["bad"]) for _, _, c in cols) + " \\\\")
    print("\\quad of which verdict still right & " + " & ".join(str(c["lucky"]) for _, _, c in cols) + " \\\\")
    print("\\textbf{faithfulness} & " + " & ".join(f"{c['faithfulness']:.2f}" for _, _, c in cols) + " \\\\\n\\bottomrule\n\\end{tabular}")


if __name__ == "__main__":
    main()
