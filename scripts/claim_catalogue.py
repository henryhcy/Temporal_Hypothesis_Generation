"""Appendix claim catalogue (2026-10-22): one row per shipping group with its original-register claim template,
which reports count, the null, the exact test and the release size. Merges the former roster, per-group
composition and tests-by-shape tables. No model calls.

Sources: templates from data/templates/*.yaml (the single source of truth), conditioning / null / test from the
gold plans of the test run (results/test_gold_sets, report tier from a testrep run), instance counts and median
denominators from the per-group table in docs/draft/appendix.tex.

    .venv313/bin/python scripts/claim_catalogue.py > /tmp/catalogue.tex
"""
import glob
import json
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
LEVELS = [("report", "read off one report (Easy)", "P-R1 P-R2 C-R1 S-R1 F-R1 F-R2 F-R3 T-R1 Y-R1"),
          ("cohort", "tested in one cohort (Medium)", "P-V1 P-V3 P-V2 P-V4 C-V1 C-V2 C-V3 F-V1 F-V2 F-V3 T-V1 Y-V1 Y-V2 Y-V3 H-V1 H-V5"),
          ("multi", "compared across two cohorts (Hard)", "P-M2")]
COUNTED = {"single_report": "the named report",
           "ordered_pair": "both events, at distinct stages",
           "both_present": "both events present",
           "presence_split": "whole cohort, split on presence of $A$",
           "all_present_unique_first": "all candidates present, a unique first",
           "all_present_unique_last": "all candidates present, a unique last",
           "consecutive_pair": "both events, at consecutive stages",
           "present_offmid": "$A$ present, off the middle stage"}
TEST = {"binom_exact": "binomial", "fisher_exact": "Fisher", "modal_runner": "modal vs.\\ runner-up", None: "none"}


def templates():
    out = {}
    for f in glob.glob(str(REPO / "data" / "templates" / "*.yaml")):
        for g in yaml.safe_load(open(f)).get("groups", []):
            out[g["id"]] = g["variants"]["original"]["claim"]
    return out


def tex_template(t):
    t = t.replace("→", "$\\rightarrow$")
    t = re.sub(r"\{(v1|v2)\}", lambda m: "$v_" + m.group(1)[1] + "$", t)
    return re.sub(r"\{([A-Za-z])\}", lambda m: f"${m.group(1)}$", t)


def plans():
    seen = {}
    for f in ("results/test_gold_sets/predictions.jsonl", "results/testrep_gemma4_31b_dprime_verify2/predictions.jsonl"):
        for line in open(REPO / f):
            x = json.loads(line)
            if x["group_id"] not in seen:
                pr = (x.get("claim") or {}).get("procedure") or {}
                seen[x["group_id"]] = pr
    return seen


def null_text(g, pr):
    n = pr.get("null") or {}
    k, p0, stat = n.get("kind"), n.get("p0"), n.get("statistic")
    if k == "none":
        return "---"
    if k == "two_arm_equality":
        return "two rates equal"
    if stat == "named_vs_runner_up":
        return "runner-up"
    if p0 is None:
        return "data-derived"
    if g.startswith("H-"):
        return f"bar in text, ${p0:g}$".replace("0.667", "2/3")
    return f"${p0:g}$"


def counts():
    a = (REPO / "docs" / "draft" / "appendix.tex").read_text()
    out = {}
    for line in a.splitlines():
        m = re.match(r"^([A-Z]-[A-Z]\d) & [RCM] & .* & (\d+) & \d+ & \d+ & \d+ & [^&]+ & \d+ & ([0-9.]+|---) \\\\", line)
        if m:
            out[m.group(1)] = (m.group(2), m.group(3))
    return out


def main():
    T, P, N = templates(), plans(), counts()
    print("\\begin{tabularx}{\\textwidth}{@{}l X p{3.1cm} p{1.6cm} p{2.25cm} rr@{}}")
    print("\\toprule")
    print("group & claim template (original register) & reports counted & null & exact test & inst. & med.\\ $n$ \\\\")
    for lvl, label, gs in LEVELS:
        print("\\midrule")
        print(f"\\multicolumn{{7}}{{@{{}}l}}{{\\textit{{{label}}}}} \\\\")
        for g in gs.split():
            pr = P[g]
            inst, med = N.get(g, ("?", "?"))
            print(f"{g} & {tex_template(T[g])} & {COUNTED[pr.get('conditioning')]} & {null_text(g, pr)} & "
                  f"{TEST[pr.get('test')]} & {inst} & {med} \\\\")
    print("\\bottomrule")
    print("\\end{tabularx}")


if __name__ == "__main__":
    main()
