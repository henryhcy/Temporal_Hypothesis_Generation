"""Shipping-gate permutation screen for the v1.2 groups (decisions.md 2026-10-07).

CLAUDE.md rule: a group gets a roster slot only after clearing its permutation
null at >= 2000 rounds. The nine v1.2 groups are ORDER / POSITION claims, so the
null is the LEVEL SHUFFLE of the family-inventory method: inside each report the
term -> level assignment is permuted, which preserves report size, the stage-size
multiset, term frequencies and co-occurrence and destroys order and position.
(The structural early-rate and the adjacency chance 2/L depend only on the
stage-size multiset, so each core's data-derived null is unchanged by the shuffle
-- exactly the property that makes it the right null.)

The statistic is the SHIPPING statistic: the group's own enumerator
(``cores.enumerate_group``, the capped top-K universe the release draws from)
and ``cohort_decision`` (the three-decision rule with the family floor), so the
count screened is the decisive-core supply S that caps the group. Reported:
real S, the null mean, p_dec = P(null S >= real S) and p_sup (supported only).

    python scripts/screen_v12_groups.py --rounds 2000 [--groups Y-V1,T-V1]
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics as st
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))

from temporal_hypo.generation import cores as C  # noqa: E402
from temporal_hypo.generation.corpus import CorpusIndex  # noqa: E402
from temporal_hypo.generation.templates import load_groups  # noqa: E402

V12_GROUPS = ("Y-V1", "Y-V2", "T-V1", "Y-V3", "H-V1", "H-V3", "H-V5")   # cohort tier only
SEED = 20261007


def level_shuffle(index: CorpusIndex, rng: random.Random) -> CorpusIndex:
    """A new index whose per-report term -> level map is a random permutation of
    the real one (same terms, same multiset of levels)."""
    shuffled: dict[int, dict[str, int]] = {}
    for vid, terms in index.report_terms.items():
        names = list(terms)
        levels = [terms[t] for t in names]
        rng.shuffle(levels)
        shuffled[vid] = dict(zip(names, levels))
    return CorpusIndex(report_terms=shuffled, report_vaccine=index.report_vaccine)


def count(index: CorpusIndex, group) -> tuple[int, int, int]:
    """(decisive S, supported, refuted) over the group's shipping universe."""
    sup = ref = 0
    for core in C.enumerate_group(index, group):
        if not core.computable:
            continue
        d = C.cohort_decision(core)
        if d.verdict == "supported":
            sup += 1
        elif d.verdict == "refuted":
            ref += 1
    return sup + ref, sup, ref


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=_REPO / "data" / "medtempo.db")
    ap.add_argument("--rounds", type=int, default=2000)
    ap.add_argument("--groups", type=str, default=",".join(V12_GROUPS))
    ap.add_argument("--out", type=Path, default=_REPO / "data" / "pilot" / "v12_groups_screen.json")
    args = ap.parse_args()

    groups = load_groups()
    index = CorpusIndex.load(sqlite3.connect(args.db))
    ids = [g for g in args.groups.split(",") if g]
    real = {g: count(index, groups[g]) for g in ids}
    for g, (S, sup, ref) in real.items():
        print(f"{g}: real S={S} (supported {sup}, refuted {ref})", flush=True)

    rng = random.Random(SEED)
    null: dict[str, list[tuple[int, int, int]]] = {g: [] for g in ids}
    t0 = time.time()
    for r in range(args.rounds):
        sh = level_shuffle(index, rng)
        for g in ids:
            null[g].append(count(sh, groups[g]))
        if (r + 1) % 100 == 0:
            print(f"  round {r + 1}/{args.rounds} ({time.time() - t0:.0f}s)", flush=True)

    out = {"rounds": args.rounds, "seed": SEED, "groups": {}}
    for g in ids:
        S, sup, ref = real[g]
        ns = [x[0] for x in null[g]]
        nsup = [x[1] for x in null[g]]
        p_dec = sum(1 for x in ns if x >= S) / len(ns)
        p_sup = sum(1 for x in nsup if x >= sup) / len(nsup)
        out["groups"][g] = {"real": {"S": S, "supported": sup, "refuted": ref},
                            "null_mean_S": st.mean(ns), "null_sd_S": st.pstdev(ns),
                            "null_mean_supported": st.mean(nsup),
                            "p_dec": p_dec, "p_sup": p_sup,
                            "clears": (p_dec < 0.05) or (p_sup < 0.05)}
        print(f"{g}: S={S} null {st.mean(ns):.1f}±{st.pstdev(ns):.1f}  p_dec={p_dec:.4f}  "
              f"supported {sup} vs null {st.mean(nsup):.1f}  p_sup={p_sup:.4f}  "
              f"{'CLEARS' if out['groups'][g]['clears'] else 'FAILS'}", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=1))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
