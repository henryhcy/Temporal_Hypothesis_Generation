"""Full-enumeration 2000-round permutation screens for P-V2, P-V4, C-V2.

decisions.md 2026-08-14 batch 2: each roster addition must clear its own
>= 2000-round permutation screen AT FULL ENUMERATION before it ships. The
capped screening on the expansion branch (top-40 pairs, `10_family_expansion`)
was the adoption evidence; this is the shipping gate.

Null models, per the family-inventory method:

- P-V2 / P-V4 are ORDER claims -> LEVEL SHUFFLE (permute term->level inside
  each report; preserves report size, stage-size multiset, term frequencies,
  co-occurrence; destroys order). A label shuffle would be wrong: these claims
  never contrast cohorts.
- C-V2 is a PRESENCE claim -> degree-preserving bipartite EDGE SWAP. The level
  shuffle leaves presence untouched -- measured on the expansion branch, it
  returns a null identical to the real data for presence statistics.

Core universes are FIXED from the real corpus (P-V2/P-V4: ordered-viable pairs,
n_ord >= 10; C-V2: both arms >= 10, which depends only on invariant term
frequencies); the min-n gate is applied per shuffled state as well, matching
run_multi_inventory / run_family_inventory.

    python scripts/screen_new_groups.py [--rounds 2000]
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics as st
import time
from itertools import combinations
from pathlib import Path

from temporal_hypo.core.significance import ALPHA, fisher_exact_2x2
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.vaccines import VACCINES

_REPO = Path(__file__).resolve().parent.parent
FLOOR = 10
SEED = 20260814


# ---------------------------------------------------------------------------
# shared: per-state ordered-pair table (level-shuffle phase)
# ---------------------------------------------------------------------------

def pair_universe(index: CorpusIndex) -> dict[str, list[tuple[str, str]]]:
    """Per cohort: pairs with both-present >= FLOOR (invariant under shuffle)."""
    out = {}
    for vax in VACCINES:
        cnt: dict[tuple[str, str], int] = {}
        for vid in index.cohort(vax):
            terms = sorted(index.report_terms[vid])
            for pr in combinations(terms, 2):
                cnt[pr] = cnt.get(pr, 0) + 1
        out[vax] = sorted(p for p, c in cnt.items() if c >= FLOOR)
    return out


def ordered_table(report_terms, index, univ):
    """{(vax, pair): (n_ordered, k_first_before_second)} under one state."""
    table = {}
    pairsets = {v: set(ps) for v, ps in univ.items()}
    for vax in VACCINES:
        ps = pairsets[vax]
        for vid in index.cohort(vax):
            t = report_terms[vid]
            for pr in combinations(sorted(t), 2):
                if pr not in ps:
                    continue
                la, lb = t[pr[0]], t[pr[1]]
                if la == lb:
                    continue
                n, k = table.get((vax, pr), (0, 0))
                table[(vax, pr)] = (n + 1, k + (1 if la < lb else 0))
    return table


def arm(table, vax, x, y):
    """(n_ordered, k_x_before_y) for the DIRECTED arm x -> y."""
    if x < y:
        r = table.get((vax, (x, y)))
        return r if r else (0, 0)
    r = table.get((vax, (y, x)))
    return (r[0], r[0] - r[1]) if r else (0, 0)


def _decide(k1, n1, k2, n2):
    if min(n1, n2) < FLOOR:
        return 0
    if fisher_exact_2x2(k1, n1, k2, n2, alternative="greater") < ALPHA:
        return 1
    if fisher_exact_2x2(k1, n1, k2, n2, alternative="less") < ALPHA:
        return -1
    return 0


def build_candidates(index, univ):
    """Fixed candidate combos from REAL ordered viability."""
    real = ordered_table(index.report_terms, index, univ)
    pv4, pv2 = {}, {}
    for vax in VACCINES:
        viable = [p for p in univ[vax]
                  if real.get((vax, p), (0, 0))[0] >= FLOOR]
        combos4 = [(p1, p2) for i, p1 in enumerate(viable)
                   for p2 in viable[i + 1:] if not set(p1) & set(p2)]
        pv4[vax] = combos4
        by_b: dict[str, set] = {}
        for x, y in viable:
            by_b.setdefault(y, set()).add(x)
            by_b.setdefault(x, set()).add(y)
        pv2[vax] = [(a, b, c) for b, ants in sorted(by_b.items())
                    for a, c in combinations(sorted(ants), 2)]
    return pv4, pv2


def count_level_phase(table, pv4, pv2):
    s4 = r4 = s2 = r2 = 0
    for vax in VACCINES:
        for (a, b), (c, d) in pv4[vax]:
            n1, k1 = table.get((vax, (a, b)), (0, 0))
            n2, k2 = table.get((vax, (c, d)), (0, 0))
            d_ = _decide(k1, n1, k2, n2)
            s4 += d_ == 1
            r4 += d_ == -1
        for a, b, c in pv2[vax]:
            n1, k1 = arm(table, vax, a, b)
            n2, k2 = arm(table, vax, c, b)
            d_ = _decide(k1, n1, k2, n2)
            s2 += d_ == 1
            r2 += d_ == -1
    return (s2, r2), (s4, r4)


def level_shuffle(report_terms, rng):
    out = {}
    for rid, tmap in report_terms.items():
        terms = list(tmap)
        levels = list(tmap.values())
        rng.shuffle(levels)
        out[rid] = dict(zip(terms, levels))
    return out


# ---------------------------------------------------------------------------
# C-V2: presence universe + edge swap
# ---------------------------------------------------------------------------

def assoc_universe(index):
    """Per cohort: (pairs, freq, N). Both arms' floors depend only on term
    frequency, which the edge swap preserves, so the universe is invariant."""
    out = {}
    for vax in VACCINES:
        cohort = index.cohort(vax)
        freq = index.term_freq(cohort)
        n_cohort = len(cohort)
        terms = sorted(t for t, c in freq.items()
                       if c >= FLOOR and n_cohort - c >= FLOOR)
        out[vax] = (list(combinations(terms, 2)), freq, n_cohort)
    return out


def count_assoc(presence_by_vax, auniv):
    sup = ref = 0
    for vax in VACCINES:
        pairs, freq, n_cohort = auniv[vax]
        pairset = set(pairs)
        both: dict[tuple[str, str], int] = {}
        for terms in presence_by_vax[vax]:
            ts = sorted(terms)
            for pr in combinations(ts, 2):
                if pr in pairset:
                    both[pr] = both.get(pr, 0) + 1
        for a, b in pairs:
            k1 = both.get((a, b), 0)
            n1 = freq[a]
            n2 = n_cohort - n1
            k2 = freq[b] - k1
            d_ = _decide(k1, n1, k2, n2)
            sup += d_ == 1
            ref += d_ == -1
    return sup, ref


def edge_swap(presence: list[set], rng, passes=2):
    sets = [set(s) for s in presence]
    edges = [(i, t) for i, s in enumerate(sets) for t in s]
    for _ in range(passes * len(edges)):
        i = rng.randrange(len(edges))
        j = rng.randrange(len(edges))
        (r1, t1), (r2, t2) = edges[i], edges[j]
        if r1 == r2 or t1 == t2:
            continue
        if t2 in sets[r1] or t1 in sets[r2]:
            continue
        sets[r1].discard(t1); sets[r1].add(t2)
        sets[r2].discard(t2); sets[r2].add(t1)
        edges[i] = (r1, t2)
        edges[j] = (r2, t1)
    return sets


def p_perm(null_counts, real, rounds):
    return (sum(1 for x in null_counts if x >= real) + 1) / (rounds + 1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=_REPO / "data" / "medtempo.db")
    ap.add_argument("--rounds", type=int, default=2000)
    args = ap.parse_args()

    conn = sqlite3.connect(str(args.db))
    index = CorpusIndex.load(conn)
    conn.close()
    rng = random.Random(SEED)
    results = {}

    # ---- level-shuffle phase: P-V2 + P-V4 ---------------------------------
    univ = pair_universe(index)
    pv4, pv2 = build_candidates(index, univ)
    n4 = {v: len(pv4[v]) for v in VACCINES}
    n2_ = {v: len(pv2[v]) for v in VACCINES}
    print(f"P-V4 candidate combos per cohort: {n4} (total {sum(n4.values())})")
    print(f"P-V2 candidate triples per cohort: {n2_} (total {sum(n2_.values())})")

    real_table = ordered_table(index.report_terms, index, univ)
    (s2, r2), (s4, r4) = count_level_phase(real_table, pv4, pv2)
    print(f"real  P-V2: {s2}+{r2}={s2 + r2} decisive   "
          f"P-V4: {s4}+{r4}={s4 + r4} decisive")

    null2, null4 = [], []
    t0 = time.time()
    for i in range(args.rounds):
        sh = level_shuffle(index.report_terms, rng)
        tab = ordered_table(sh, index, univ)
        (a2, b2), (a4, b4) = count_level_phase(tab, pv4, pv2)
        null2.append(a2 + b2)
        null4.append(a4 + b4)
        if (i + 1) % 250 == 0:
            print(f"  level round {i + 1}/{args.rounds} "
                  f"({time.time() - t0:.0f}s) null2~{st.mean(null2):.1f} "
                  f"null4~{st.mean(null4):.1f}", flush=True)
    for name, real_sr, null in (("P-V2", (s2, r2), null2),
                                ("P-V4", (s4, r4), null4)):
        real = sum(real_sr)
        p = p_perm(null, real, args.rounds)
        results[name] = {
            "supported": real_sr[0], "refuted": real_sr[1], "decisive": real,
            "cores": sum((n2_ if name == "P-V2" else n4).values()),
            "null_mean": round(st.mean(null), 1),
            "null_p95": sorted(null)[int(0.95 * len(null))],
            "p_perm": round(p, 4), "null_model": "level_shuffle",
        }
        print(f"{name}: p_perm={p:.4f} "
              f"({'CLEARS' if p <= 0.05 else 'FAILS -- do not ship'})")

    # ---- edge-swap phase: C-V2 --------------------------------------------
    auniv = assoc_universe(index)
    npairs = {v: len(auniv[v][0]) for v in VACCINES}
    print(f"\nC-V2 pair universe per cohort: {npairs} "
          f"(total {sum(npairs.values())})")
    presence = {v: [set(index.report_terms[vid]) for vid in index.cohort(v)]
                for v in VACCINES}
    sA, rA = count_assoc(presence, auniv)
    print(f"real  C-V2: {sA}+{rA}={sA + rA} decisive")
    nullA = []
    t0 = time.time()
    for i in range(args.rounds):
        swapped = {v: edge_swap(presence[v], rng) for v in VACCINES}
        a, b = count_assoc(swapped, auniv)
        nullA.append(a + b)
        if (i + 1) % 250 == 0:
            print(f"  swap round {i + 1}/{args.rounds} "
                  f"({time.time() - t0:.0f}s) null~{st.mean(nullA):.1f}",
                  flush=True)
    realA = sA + rA
    pA = p_perm(nullA, realA, args.rounds)
    results["C-V2"] = {
        "supported": sA, "refuted": rA, "decisive": realA,
        "cores": sum(npairs.values()),
        "null_mean": round(st.mean(nullA), 1),
        "null_p95": sorted(nullA)[int(0.95 * len(nullA))],
        "p_perm": round(pA, 4), "null_model": "edge_swap",
    }
    print(f"C-V2: p_perm={pA:.4f} "
          f"({'CLEARS' if pA <= 0.05 else 'FAILS -- do not ship'})")

    dest = _REPO / "data" / "pilot" / "new_groups_screen.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"rounds": args.rounds, "floor": FLOOR,
                                "seed": SEED, **results}, indent=2),
                    encoding="utf-8")
    print(f"\nwritten to {dest}")


if __name__ == "__main__":
    main()
