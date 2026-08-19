"""2000-round permutation screen for C-V3's new argmax statistic (issue 13).

The 2026-08-14 decision moved C-V3 from "co-occurrence rate > 0.5" to
modal-vs-runner-up over the 3-cell relation distribution, and the standing rule
(08_multi_tier_inventory / decisions.md) is that any group with a CHANGED
statistic must clear a >= 2000-round permutation null before it ships; if it
fails, C-V3 is dropped instead.

Null model: LEVEL SHUFFLE -- permute which term sits at which occupied stage
inside each report, preserving report size, the multiset of stage sizes, term
frequencies and every co-occurrence. That destroys exactly what the claim
asserts (whether A and B tend to land on the SAME stage more than either
ordered arrangement) while keeping the stage-size geometry that makes same-stage
placement likely by chance. A vaccine-label shuffle would be the wrong null
here: C-V3 is a single-cohort claim and never contrasts cohorts.

Scope: the three vaccine cohorts summed -- what the shipped group actually asks
("After {v}, ..."). Universe and floor exactly match the shipped enumeration:
all pairs with both-present n >= 10 in the cohort, fixed from the REAL corpus
so every round counts the same cores.

    python scripts/screen_cv3.py [--rounds 2000]
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics as st
from itertools import combinations
from pathlib import Path

from temporal_hypo.core.significance import ALPHA, binom_exact_p
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.vaccines import VACCINES

_REPO = Path(__file__).resolve().parent.parent
FLOOR = 10          # pairwise family floor on the both-present denominator
SEED = 20260814


def universe(index: CorpusIndex) -> dict[str, list[tuple[str, str]]]:
    """Per cohort: every pair with both-present n >= FLOOR, from the real data.

    Both-present count is invariant under the level shuffle, so the universe is
    identical in every round and real vs null are counted over the same cores.
    """
    out = {}
    for vax in VACCINES:
        cnt: dict[tuple[str, str], int] = {}
        for vid in index.cohort(vax):
            terms = sorted(index.report_terms[vid])
            for pr in combinations(terms, 2):
                cnt[pr] = cnt.get(pr, 0) + 1
        out[vax] = sorted(p for p, c in cnt.items() if c >= FLOOR)
    return out


def tally(report_terms, index, univ):
    """{(vax, pair): [before, after, co_exist]} under one corpus state."""
    counts = {(v, p): [0, 0, 0] for v, ps in univ.items() for p in ps}
    pairsets = {v: set(ps) for v, ps in univ.items()}
    for vax in VACCINES:
        ps = pairsets[vax]
        for vid in index.cohort(vax):
            t = report_terms[vid]
            present = sorted(x for x in t)
            for pr in combinations(present, 2):
                if pr not in ps:
                    continue
                la, lb = t[pr[0]], t[pr[1]]
                row = counts[(vax, pr)]
                if la < lb:
                    row[0] += 1
                elif la > lb:
                    row[1] += 1
                else:
                    row[2] += 1
    return counts


def decisive(counts):
    sup = ref = tot = 0
    for (before, after, co) in counts.values():
        n = before + after + co
        if n < FLOOR:
            continue
        runner = max(before, after)
        nn = co + runner
        if nn == 0:
            continue
        tot += 1
        if binom_exact_p(co, nn, 0.5, alternative="greater") < ALPHA:
            sup += 1
        elif binom_exact_p(co, nn, 0.5, alternative="less") < ALPHA:
            ref += 1
    return sup, ref, tot


def level_shuffle(report_terms, rng):
    out = {}
    for rid, tmap in report_terms.items():
        terms = list(tmap)
        levels = list(tmap.values())
        rng.shuffle(levels)
        out[rid] = dict(zip(terms, levels))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=_REPO / "data" / "medtempo.db")
    ap.add_argument("--rounds", type=int, default=2000)
    args = ap.parse_args()

    conn = sqlite3.connect(str(args.db))
    index = CorpusIndex.load(conn)
    conn.close()
    univ = universe(index)
    print("universe:", {v: len(ps) for v, ps in univ.items()})

    sup, ref, tot = decisive(tally(index.report_terms, index, univ))
    real = sup + ref
    print(f"real: {sup} supported + {ref} refuted = {real} decisive / {tot} cores")

    rng = random.Random(SEED)
    null = []
    for i in range(args.rounds):
        sh = level_shuffle(index.report_terms, rng)
        s2, r2, _ = decisive(tally(sh, index, univ))
        null.append(s2 + r2)
        if (i + 1) % 500 == 0:
            print(f"  round {i + 1}/{args.rounds}: null mean so far "
                  f"{st.mean(null):.1f}")
    null.sort()
    beat = sum(1 for x in null if x >= real)
    p_perm = (beat + 1) / (args.rounds + 1)
    print(f"\nnull mean {st.mean(null):.1f}, p95 {null[int(0.95 * len(null))]}, "
          f"max {null[-1]}")
    print(f"p_perm = {p_perm:.4f}  ->  "
          f"{'CLEARS: C-V3 ships as argmax' if p_perm <= 0.05 else 'FAILS: drop C-V3 per the 08-14 decision'}")
    out = {"rounds": args.rounds, "floor": FLOOR, "seed": SEED,
           "supported": sup, "refuted": ref, "decisive": real, "cores": tot,
           "null_mean": round(st.mean(null), 2),
           "null_p95": null[int(0.95 * len(null))],
           "p_perm": round(p_perm, 4)}
    dest = _REPO / "data" / "pilot" / "cv3_screen.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"written to {dest}")


if __name__ == "__main__":
    main()
