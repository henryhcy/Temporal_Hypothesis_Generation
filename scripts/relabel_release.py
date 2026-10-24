"""Recompute the gold statistics of an existing release IN PLACE (2026-10-24, user).

Two gold-procedure changes keep every instance, text and evidence set fixed and move only labels:
  1. argmax tests (first/last, C-V3, sequence): the "a competitor beats the named cell" tail is
     Bonferroni-adjusted over the competitors (core.answers._modal_runner_tails);
  2. the adjacency null (Y-V3) uses each report's stage-size-aware chance (corpus.adjacency_chance)
     instead of the flat 2/L.
The instance set is NOT re-sampled (the seeded verdict-balanced draw would move instances); so a
group's thirds may be slightly unequal afterwards. Report-tier rows are untouched.

For every cohort-tier row the core is re-enumerated from the corpus, realized at the row's polarity
and negation, and the statistics rebuilt exactly as generation.instances.build_records does; the row
must reproduce its own events/flip_kind first (a mismatch is an error, not a relabel).

    PYTHONPATH=src .venv313/bin/python scripts/relabel_release.py              # dry run: report diffs
    PYTHONPATH=src .venv313/bin/python scripts/relabel_release.py --write      # rewrite answers + stats
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from temporal_hypo.core.answers import answer_key, core_decision, oriented_significance  # noqa: E402
from temporal_hypo.generation.cores import enumerate_group, realize  # noqa: E402
from temporal_hypo.generation.corpus import CorpusIndex  # noqa: E402
from temporal_hypo.generation.instances import _round, core_id  # noqa: E402
from temporal_hypo.generation.templates import load_groups  # noqa: E402

STAT_FIELDS = ("gold_verdict", "polarity", "gold_proportion", "ci", "effect_size", "p_value", "significant",
               "sig_test", "p_claim", "p_opposite", "test_verdict", "insufficient_subtype", "core_test_verdict")


def rebuild(row: dict, core) -> dict:
    """The statistical fields build_records would write for this row's assertion."""
    pol = row["polarity"]
    facts = realize(core, pol, negated=row["negated"]) if pol != "insufficient" else realize(core, "insufficient")
    if tuple(facts.events_assigned) != tuple(row["factual_core"]["events"]) or facts.flip_kind != row["flip_kind"] \
            or bool(facts.negated) != bool(row["negated"]):
        raise ValueError(f"{row['instance_id']}: re-realization does not reproduce the row "
                         f"(events {facts.events_assigned} vs {row['factual_core']['events']}, "
                         f"flip {facts.flip_kind} vs {row['flip_kind']}, negated {facts.negated} vs {row['negated']})")
    sig = oriented_significance(facts)
    ci = facts.ci
    return {
        "gold_verdict": facts.gold_verdict,
        "polarity": facts.gold_verdict,          # the label; the asserted orientation stays in flip_kind/negated
        "gold_proportion": _round(facts.gold_proportion),
        "ci": [_round(ci[0]), _round(ci[1])] if ci else None,
        "effect_size": _round(facts.effect_size),
        "p_value": _round(sig.p_value, 6),
        "significant": sig.significant,
        "sig_test": sig.test,
        "p_claim": _round(sig.p_claim, 6),
        "p_opposite": _round(sig.p_opposite, 6),
        "test_verdict": sig.decision.verdict if sig.decision else None,
        "insufficient_subtype": sig.decision.subtype if sig.decision else None,
        "core_test_verdict": core_decision(core).verdict,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", type=Path, default=REPO / "data" / "release" / "v1.2")
    ap.add_argument("--db", type=Path, default=REPO / "data" / "medtempo.db")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    ans_gz = a.release / "pilot_instances_answers.jsonl.gz"
    rows = [json.loads(l) for l in gzip.open(ans_gz, "rt")]
    index = CorpusIndex.load(sqlite3.connect(str(a.db)))
    groups = load_groups()
    gids = sorted({r["group_id"] for r in rows if r["level"] != "report"})
    cores = {}
    for gid in gids:
        for c in enumerate_group(index, groups[gid]):
            cores[f"{gid}|{'+'.join(c.vaccines)}|{'+'.join(c.events)}"] = c
    print(f"{len(rows)} rows; {len(gids)} cohort groups; {len(cores)} cores enumerated")

    changed, by_group, verdict_moves, errors = [], defaultdict(Counter), Counter(), []
    for r in rows:
        if r["level"] == "report":
            continue
        core = cores.get(r["derived_from_core_id"])
        if core is None:
            if r.get("insufficient_subtype") == "not_locatable":
                continue        # minted from a zero-joint-count vocabulary pair: no core, no test, no change
            errors.append(f"{r['instance_id']}: core {r['derived_from_core_id']} not found"); continue
        try:
            new = rebuild(r, core)
        except ValueError as e:
            errors.append(str(e)); continue
        diff = {k: (r.get(k), new[k]) for k in STAT_FIELDS if r.get(k) != new[k]}
        if diff:
            changed.append((r["instance_id"], diff))
            by_group[r["group_id"]][("verdict" if "gold_verdict" in diff else "stats only")] += 1
            if "gold_verdict" in diff:
                verdict_moves[(r["group_id"], r["gold_verdict"], new["gold_verdict"])] += 1
            if a.write:
                r.update(new)
    print(f"\nrows with any change: {len(changed)}; errors: {len(errors)}")
    for e in errors[:10]:
        print("  ERROR", e)
    for gid in sorted(by_group):
        print(f"  {gid}: {dict(by_group[gid])}")
    print("\nverdict moves (group, old -> new):")
    for (gid, o, n), v in sorted(verdict_moves.items()):
        print(f"  {gid}: {o} -> {n}: {v}")
    if errors:
        raise SystemExit("not writing: re-realization errors")
    if not a.write:
        return
    log = {"date": "2026-10-24", "reason": "argmax competitor-tail Bonferroni; stage-size-aware adjacency chance",
           "changed_instances": [{"instance_id": i, "changes": {k: list(v) for k, v in d.items()}} for i, d in changed]}
    (a.release / "relabel_2026-10-24.json").write_text(json.dumps(log, indent=1))
    plain = a.release / "pilot_instances_answers.jsonl"
    with open(plain, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    with open(plain, "rb") as src, gzip.open(ans_gz, "wb", compresslevel=9) as dst:
        shutil.copyfileobj(src, dst)
    subprocess.run([sys.executable, str(REPO / "scripts" / "dataset_stats.py"), "--dir", str(a.release),
                    "--stem", "pilot_instances"], check=True, env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"})
    print(f"wrote {plain.name}, {ans_gz.name}, relabel_2026-10-24.json and dataset_statistics.*")


if __name__ == "__main__":
    main()
