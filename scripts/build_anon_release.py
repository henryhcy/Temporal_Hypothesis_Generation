"""Build the anonymous review release (2026-10-23, user): the 200-instance development set only, for an
Anonymous GitHub link. Writes a fresh directory with no history, no author names and no local paths.

Contents (claim form only, the paper's evaluation format):
  data/dev/dev_claims.jsonl       inputs: 800 records (200 instances x 4 registers)
  data/dev/dev_gold.jsonl         gold per instance (release answers, claim-form ids; test_verdict dropped)
  data/dev/dev_gold_stages.jsonl  gold per instance at every stage from the deterministic oracle:
                                  plan, evidence sets per arm, reference SQL, verdict
  data/codebook.txt, data/dataset_card.txt, data/schema.sql   the texts the models are given
  data/medtempo_eval.db           the timeline database (pseudonymous ids, no report text), fresh VACUUM copy
  data/dev/outputs/*.jsonl        ART's dev-set outputs (claim form, Original register) for the Qwen2.5 pair and
                                  GPT-5.6: plan, SQL, report sets, counts, verdict, repair-round counts. The repair
                                  messages, latency and token counts are left out.
  score.py (written by hand in the release repo) scores any of these files against the dev gold.

The gold-stage file is the rules+compiler run on the dev subset (no model calls):
    PYTHONPATH=src .venv313/bin/python scripts/run_eval.py --pipeline rules+compiler --condition blind-group \
        --procedure blind --registers original --formats claim --release data/release/v1.2 --ddl-style listing \
        --subset results/subsets/smoke_200_v1.2_s0.json --out <dir>
    PYTHONPATH=src .venv313/bin/python scripts/build_anon_release.py --gold-stages <dir> --out ~/strata-benchmark
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from temporal_hypo.framework.extract.llm import conventions_block  # noqa: E402
from temporal_hypo.framework.extract.task_card import dataset_card  # noqa: E402
from temporal_hypo.framework.sql import llm_sql  # noqa: E402

REL = REPO / "data" / "release" / "v1.2"
DEV = REPO / "results" / "subsets" / "smoke_200_v1.2_s0.json"
DROP_GOLD = {"test_verdict", "core_test_verdict"}       # test_verdict is the canonical, not the oriented, verdict (issue 25)
STAGE_KEYS = ("hypothesis_id", "instance_id", "group_id", "claim", "retrieval", "prediction")
OUTPUTS = {"art_qwen2.5-32b-pair.jsonl": ("v12f_smoke200_cellC2_catalogueS2_instruct32b_coder32b_verify2_final",
                                          "Qwen2.5-32B-Instruct (plan) + Qwen2.5-Coder-32B (SQL)"),
           "art_gpt-5.6.jsonl": ("dev_gpt_gpt-5_6-sol_dprime_verify2_claim", "GPT-5.6")}
FORBIDDEN = re.compile(r"henryhcy|chengyang|stevens|che14|/home/|vaers_id|gpt-5\.6-sol|\+toolbox", re.I)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold-stages", type=Path, required=True, help="rules+compiler run dir on the dev subset")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    ids = set(json.loads(DEV.read_text())["ids"])
    out = a.out / "data"
    (out / "dev").mkdir(parents=True, exist_ok=True)

    n = 0
    with open(out / "dev" / "dev_claims.jsonl", "w") as f:
        for line in open(REL / "pilot_instances_questions.jsonl"):
            x = json.loads(line)
            if x["format"] == "claim" and x["hypothesis_id"].rsplit("-", 2)[0] in ids:
                f.write(json.dumps(x) + "\n"); n += 1
    assert n == 4 * len(ids), n

    m = 0
    with open(out / "dev" / "dev_gold.jsonl", "w") as f:
        for line in open(REL / "pilot_instances_answers.jsonl"):
            x = json.loads(line)
            if x["instance_id"] in ids:
                x = {k: v for k, v in x.items() if k not in DROP_GOLD}
                x["hypothesis_ids"] = [h for h in x["hypothesis_ids"] if h.endswith("-claim")]
                f.write(json.dumps(x) + "\n"); m += 1
    assert m == len(ids), m

    k = 0
    with open(out / "dev" / "dev_gold_stages.jsonl", "w") as f:
        for line in open(a.gold_stages / "predictions.jsonl"):
            x = json.loads(line)
            assert (x.get("prediction") or {}).get("verdict") is not None
            y = {key: x[key] for key in STAGE_KEYS}
            y["retrieval"] = {kk: vv for kk, vv in (x["retrieval"] or {}).items() if kk in ("ok", "arms", "levels", "queries")}
            f.write(json.dumps(y) + "\n"); k += 1
    assert k == len(ids), k

    (out / "codebook.txt").write_text(conventions_block(None) + "\n")
    (out / "dataset_card.txt").write_text(dataset_card(sqlite3.connect(REPO / "data" / "medtempo_eval.db")) + "\n")
    (out / "schema.sql").write_text(llm_sql.load_eval_ddl() + "\n")

    db = out / "medtempo_eval.db"                   # timelines only; VACUUM INTO leaves no free pages behind
    db.unlink(missing_ok=True)
    sqlite3.connect(REPO / "data" / "medtempo_eval.db").execute(f"VACUUM INTO '{db}'")
    names = {r[0] for r in sqlite3.connect(db).execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    assert names == {"reports", "level_terms", "first_mention", "first_mention_rank", "report_terms"}, names

    (out / "dev" / "outputs").mkdir(exist_ok=True)
    for name, (run, label) in OUTPUTS.items():
        with open(out / "dev" / "outputs" / name, "w") as f:
            for line in open(REPO / "results" / run / "predictions.jsonl"):
                x = json.loads(line)
                if x["format"] != "claim" or x["register"] != "original":
                    continue
                rt, v = x.get("retrieval") or {}, x.get("verify") or {}
                if x.get("claim"):
                    x["claim"]["source"] = "model"      # the internal model id and frame name stay out
                f.write(json.dumps({"hypothesis_id": x["hypothesis_id"], "instance_id": x["instance_id"],
                                    "group_id": x["group_id"], "model": label, "claim": x.get("claim"),
                                    "retrieval": {k: rt.get(k) for k in ("ok", "arms", "levels", "queries") if k in rt},
                                    "prediction": x.get("prediction"),
                                    "repair_rounds": {"plan": v.get("s1_rounds"), "sql": v.get("s2_rounds")},
                                    "error": x.get("error")}) + "\n")

    for p in a.out.rglob("*"):                      # nothing identifying may leave
        if p.is_file() and ".git" not in p.parts:
            hit = FORBIDDEN.search(p.read_text(errors="ignore"))
            assert not hit, (p, hit.group(0))
    print(f"wrote {n} claim records, {m} gold rows, {k} gold-stage rows -> {a.out}")


if __name__ == "__main__":
    main()
