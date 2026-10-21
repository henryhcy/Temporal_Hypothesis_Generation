"""Re-score the development-set runs on their claim-form records only (2026-10-21, user: the paper
presents the claim form only; no model calls, the existing predictions are filtered and re-scored
with the same evaluator and the same attribution code).

Writes results/dev_claim_rescore.json and prints the LaTeX rows for the appendix planning table
(tab:toolbox) and the attribution table (tab:attribution), the numbers behind the prose-versus-contract
paragraph, the register figure, and the one-change-at-a-time paragraph.

    PYTHONPATH=src .venv313/bin/python scripts/dev_claim_rescore.py
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))
import s2_attribution as S2  # noqa: E402
from temporal_hypo.framework.evaluate import evaluate  # noqa: E402
from temporal_hypo.framework.io import load_release  # noqa: E402

R = REPO / "results"
TMP = Path("/tmp/claude-1001/-home-henryhcy/b272bfa2-9f10-4a1a-9eb0-149619ec2d38/scratchpad/claimruns")
TMP.mkdir(parents=True, exist_ok=True)
P = "v12f_smoke200_"
RUNS = {
    # planning table
    "cat32": P + "catalogue_instruct32b",
    "tb32": P + "toolbox_instruct32b_zs_conv22", "tb32_v1": P + "toolbox_instruct32b_zs_conv22_verify1",
    "tb7": P + "toolbox_7b_zs_conv22", "tb7_v1": P + "toolbox_7b_zs_conv22_verify1",
    "tb32_old": P + "toolbox_instruct32b_zs",   # before the association bridge
    # attribution table columns
    "rules7": P + "rules_llmsql_coder7b_final", "rules32": P + "rules_llmsql_coder32b_final",
    "rules32_r2": P + "rules_llmsql_coder32b_r2_final",
    "A": P + "cellA_e2e_coder32b_final", "B": P + "cellB_e2e_conventions_coder32b_final",
    "B_v2": P + "cellB_e2e_conventions_coder32b_verify2_final",
    "Dp": P + "cellC2_catalogueS2_instruct32b_coder32b_final", "Dp_v2": P + "cellC2_catalogueS2_instruct32b_coder32b_verify2_final",
    # prose versus contract
    "D": P + "cellD_instruct32b_coder32b_final", "D_v2": P + "cellD_instruct32b_coder32b_verify2_final",
    # schema presentation history (cell A and the SQL stage with the gold plan)
    "A_ddl": P + "cellA_e2e_coder32b", "A_list": P + "cellA_e2e_coder32b_ddl_listing",
    "rules32_ddl": P + "rules_llmsql_coder32b", "rules32_list": P + "rules_llmsql_coder32b_ddl_listing",
    # registers (research, media, clinical)
    "tb32_reg": P + "toolbox_instruct32b_zs_conv22_registers",
    "Dp_reg": P + "dprime_registers_final", "Dp_v2_reg": P + "dprime_registers_verify2_final",
    "B_reg": P + "cellB_registers_final", "B_v2_reg": P + "cellB_registers_verify2_final",
}


def claim_rows(run: str, register: str | None = None) -> list[dict]:
    rows = [json.loads(l) for l in open(R / run / "predictions.jsonl")]
    rows = [x for x in rows if x.get("format") == "claim" and (register is None or x.get("register") == register)]
    return rows


def tmp_run(name: str, rows: list[dict]) -> Path:
    d = TMP / name
    d.mkdir(exist_ok=True)
    with open(d / "predictions.jsonl", "w") as f:
        for x in rows:
            f.write(json.dumps(x) + "\n")
    return d


def score(release, gold, fm, vac, key: str, register: str | None = None, attribution: bool = True) -> dict:
    run = RUNS[key]
    rows = claim_rows(run, register)
    m = evaluate(rows, release)
    v = m["verdict"]
    pt = m.get("per_tier", {})
    coh_n = sum(pt[t]["n"] for t in ("vaccine", "multi") if t in pt)
    coh_acc = (sum(pt[t]["accuracy"] * pt[t]["n"] for t in ("vaccine", "multi") if t in pt) / coh_n) if coh_n else None
    out = {"run": run, "n": len(rows), "acc": v["accuracy"], "cohort_acc": coh_acc, "cohort_n": coh_n,
           "evidence_f1": (m.get("retrieval", {}).get("denominator", {}) or {}).get("f1"),
           "per_group": {g: d["accuracy"] for g, d in (m.get("per_group") or {}).items()} if isinstance(m.get("per_group"), dict) else None}
    # rejected statements (schema-presentation history)
    nq = nerr = 0
    for x in rows:
        for q in ((x.get("retrieval") or {}).get("queries") or []):
            nq += 1; nerr += 1 if q.get("error") else 0
    out["queries"], out["rejected"] = nq, nerr
    if attribution:
        a = S2.attribute(tmp_run(key + (f"_{register}" if register else ""), rows), gold, fm, vac)
        out["attribution"] = {"n": a["n"], "bad": a["bad"], "lucky": a["lucky"], "verdict_right": a["verdict_right"],
                              "faithfulness": a["faithfulness"], "causes": dict(a["causes"])}
    return out


def main() -> None:
    release = load_release(REPO / "data" / "release" / "v1.2")
    gold = {x["hypothesis_id"]: x for x in S2.read(R / (P + "gold_sets"))}
    fm, vac = S2.load_db(REPO / "data" / "medtempo_eval.db")
    res: dict = {}
    for key in RUNS:
        if key.endswith("_reg"):
            for reg in ("research", "media", "clinical"):
                res[f"{key}:{reg}"] = score(release, gold, fm, vac, key, reg, attribution=False)
        else:
            res[key] = score(release, gold, fm, vac, key)
        r = res[key] if key in res else None
        if r:
            print(f"{key:12s} n={r['n']:4d} acc={r['acc']:.3f} cohort={r['cohort_acc']:.3f} (n={r['cohort_n']}) evF1={r['evidence_f1'] if r['evidence_f1'] is None else round(r['evidence_f1'],3)} "
                  f"faith={r['attribution']['faithfulness'] if r['attribution']['faithfulness'] is None else round(r['attribution']['faithfulness'],2)} rejected={r['rejected']}/{r['queries']}")
    for k in sorted(res):
        if ":" in k:
            r = res[k]; print(f"{k:22s} n={r['n']:4d} acc={r['acc']:.3f}")
    (R / "dev_claim_rescore.json").write_text(json.dumps(res, indent=1))

    f3 = lambda x: "---" if x is None else f"{x:.3f}"
    print("\n% ===== tab:toolbox (claim form) =====")
    print(f"Catalogue (answer-injected upper bound) & {f3(res['cat32']['acc'])} & {f3(res['cat32']['cohort_acc'])} & --- & --- \\\\")
    print(f"\\textbf{{Toolbox, zero-shot}} & {f3(res['tb32']['acc'])} & {f3(res['tb32']['cohort_acc'])} & {f3(res['tb7']['acc'])} & {f3(res['tb7']['cohort_acc'])} \\\\")
    print(f"\\quad + one verify-and-repair round & \\textbf{{{f3(res['tb32_v1']['acc'])}}} & \\textbf{{{f3(res['tb32_v1']['cohort_acc'])}}} & {f3(res['tb7_v1']['acc'])} & {f3(res['tb7_v1']['cohort_acc'])} \\\\")
    print("\n% ===== tab:attribution (claim form) =====")
    cols = ["rules7", "rules32", "rules32_r2", "A", "B", "B_v2", "Dp", "Dp_v2"]
    print("% cohort records per column:", [res[c]["attribution"]["n"] for c in cols])
    for cause in S2.CAUSES:
        print(f"{cause} & " + " & ".join(str(res[c]["attribution"]["causes"].get(cause, 0)) for c in cols) + " \\\\")
    print("wrong or missing denominators & " + " & ".join(str(res[c]["attribution"]["bad"]) for c in cols) + " \\\\")
    print("\\quad of which verdict still right & " + " & ".join(str(res[c]["attribution"]["lucky"]) for c in cols) + " \\\\")
    print("\\textbf{faithfulness} & " + " & ".join(f"{res[c]['attribution']['faithfulness']:.2f}" for c in cols) + " \\\\")
    print("\n% ===== prose versus contract (all / cohort) =====")
    for k in ("B", "B_v2", "D", "D_v2", "Dp", "Dp_v2", "A"):
        print(f"{k}: all {f3(res[k]['acc'])} cohort {f3(res[k]['cohort_acc'])} evF1 {f3(res[k]['evidence_f1'])} faith {res[k]['attribution']['faithfulness']:.2f}")
    print("\n% ===== registers (Original from the 200 claim records; others from the register runs) =====")
    for label, orig, regkey in (("planner alone, 1 round", "tb32_v1", "tb32_reg"), ("D'", "Dp", "Dp_reg"), ("D' + verifier", "Dp_v2", "Dp_v2_reg"), ("B", "B", "B_reg")):
        vals = [res[orig]["acc"]] + [res[f"{regkey}:{reg}"]["acc"] for reg in ("research", "media", "clinical")]
        print(f"{label:24s} " + " ".join(f"{v:.3f}" for v in vals))
    print("\n% ===== one change at a time =====")
    print(f"planner before/after the association bridge: {res['tb32_old']['acc']:.3f} -> {res['tb32']['acc']:.3f}")
    pg0, pg1 = res["tb32_old"]["per_group"] or {}, res["tb32"]["per_group"] or {}
    changed = {g: (pg0.get(g), pg1.get(g)) for g in sorted(set(pg0) | set(pg1)) if pg0.get(g) != pg1.get(g)}
    print("groups changed:", {g: (round(a, 2) if a is not None else None, round(b, 2) if b is not None else None) for g, (a, b) in changed.items()}, "of", len(set(pg0) | set(pg1)))
    print(f"cell A schema presentation: {res['A_ddl']['acc']:.3f} -> {res['A_list']['acc']:.3f} -> {res['A']['acc']:.3f}; rejected "
          f"{res['A_ddl']['rejected']}/{res['A_ddl']['queries']} -> {res['A_list']['rejected']}/{res['A_list']['queries']} -> {res['A']['rejected']}/{res['A']['queries']}")
    print(f"SQL stage with the gold plan: {res['rules32_ddl']['acc']:.3f} -> {res['rules32_list']['acc']:.3f} -> {res['rules32']['acc']:.3f}")


if __name__ == "__main__":
    main()
