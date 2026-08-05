"""Multi-tier candidate inventory with a permutation null (08_multi_tier_inventory).

Measures, for each candidate two-cohort hypothesis shape, how many cores the
corpus can label decisively (supported or refuted under the three-decision rule)
-- and validates that count against a PERMUTATION NULL rather than the
"cores x alpha" analytic baseline, which is wrong in both directions here:

- cores are dependent (each event pair contributes three vaccine-pair
  comparisons over overlapping cohorts), which inflates the null above alpha;
- the exact tests are conservative on sparse tables and the rank tests are
  ANTI-conservative on tie-heavy ordinal data.

Shuffling the vaccine labels destroys any real cohort difference while
preserving all of that structure, so the shuffled decisive count is the honest
null. `p_perm` is the fraction of rounds matching or beating the real count.

This is a DESIGN-TIME diagnostic. It is not a labeling method: decisions.md
excludes permutation from gold-label computation because the model must be able
to run whatever test produces the label.

    python scripts/run_multi_inventory.py [--db data/medtempo.db]
                                          [--rounds 200] [--floor 20]
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics as st
from pathlib import Path

from temporal_hypo.core.significance import ALPHA, fisher_exact_2x2
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.vaccines import VACCINES, VACCINE_PAIRS

_REPO = Path(__file__).resolve().parent.parent
TERM_MIN = 20          # a term must clear this in >= 2 cohorts to enter the universe
SEED = 20260804

# (label, shape, selector) -- see 08_multi_tier_inventory.md for the claim texts
CANDIDATES = [
    ("[base] P-M2 precedes-strict  A<B | both present AND ordered", "pair", "strict"),
    ("M-F  precedes-wide           A<B | both present", "pair", "wide"),
    ("[base] C-M2 co-occurs        A==B | both present", "pair", "cooc"),
    ("M-H  early-half              A in the timeline's first half", "single", "early"),
    ("M-C  last-overall            A is the report's last event", "single", "last"),
    ("M-B  first-overall           A is the report's first event", "single", "first"),
]


def build_universe(index: CorpusIndex, floor: int):
    """Fixed core universe from the REAL cohorts, reused for every permuted round
    so real and null are counted over exactly the same cores."""
    maxlvl = {v: (max(t.values()) if t else 0)
              for v, t in index.report_terms.items()}
    freq = {v: index.term_freq(index.cohort(v)) for v in VACCINES}
    terms = sorted({t for v in VACCINES for t in freq[v]
                    if sum(freq[w].get(t, 0) >= TERM_MIN for w in VACCINES) >= 2})

    single = {}
    for a in terms:
        rows = []
        for rid, t in index.report_terms.items():
            if a in t:
                m = maxlvl[rid]
                rows.append((rid, t[a] == 0, m > 0 and t[a] == m,
                             m > 0 and t[a] / m < 0.5, m > 0))
        single[a] = rows

    pair = {}
    for i, a in enumerate(terms):
        for b in terms[i + 1:]:
            rows = [(rid, t[a] < t[b], t[a] == t[b])
                    for rid, t in index.report_terms.items() if a in t and b in t]
            if len(rows) >= 2 * floor:          # cheap prefilter
                pair[(a, b)] = rows
    return terms, single, pair


def _tally_pair(rows, vax_of, sel):
    n = {v: 0 for v in VACCINES}
    k = {v: 0 for v in VACCINES}
    for rid, before, equal in rows:
        v = vax_of[rid]
        if sel == "strict":
            if not equal:                       # ordered denominator: ties dropped
                n[v] += 1
                k[v] += int(before)
            continue
        n[v] += 1
        k[v] += int(before) if sel == "wide" else int(equal)
    return n, k


def _tally_single(rows, vax_of, sel):
    n = {v: 0 for v in VACCINES}
    k = {v: 0 for v in VACCINES}
    for rid, is_first, is_last, is_early, multi in rows:
        if sel in ("last", "early") and not multi:
            continue
        v = vax_of[rid]
        n[v] += 1
        k[v] += int(is_first if sel == "first"
                    else is_last if sel == "last" else is_early)
    return n, k


def decisive(universe, vax_of, shape, sel, floor):
    """Cores the corpus labels supported or refuted, and the cores considered."""
    _, single, pair = universe
    src, tally = (pair, _tally_pair) if shape == "pair" else (single, _tally_single)
    dec = tot = 0
    for rows in src.values():
        n, k = tally(rows, vax_of, sel)
        for v1, v2 in VACCINE_PAIRS:
            if min(n[v1], n[v2]) < floor:
                continue
            tot += 1
            p = min(fisher_exact_2x2(k[v1], n[v1], k[v2], n[v2], alternative="greater"),
                    fisher_exact_2x2(k[v1], n[v1], k[v2], n[v2], alternative="less"))
            dec += int(p < ALPHA)
    return dec, tot


def make_permutations(index: CorpusIndex, rounds: int):
    ids = list(index.report_vaccine)
    sizes = [(v, len(index.cohort(v))) for v in VACCINES]
    rng = random.Random(SEED)
    out = []
    for _ in range(rounds):
        s = ids[:]
        rng.shuffle(s)
        m, i = {}, 0
        for v, cnt in sizes:
            for rid in s[i:i + cnt]:
                m[rid] = v
            i += cnt
        out.append(m)
    return out


def run(db_path: Path, rounds: int, floor: int) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    index = CorpusIndex.load(conn)
    conn.close()
    universe = build_universe(index, floor)
    print(f"term universe: {len(universe[0])} terms (>= {TERM_MIN} reports in "
          f">= 2 cohorts); pair universe: {len(universe[2])} pairs\n")
    perms = make_permutations(index, rounds)
    real_vax = dict(index.report_vaccine)

    print(f"{rounds}-round permutation null, floor {floor}, alpha {ALPHA} per side")
    print(f"{'candidate':62s} {'real':>11s} {'null mean':>9s} "
          f"{'null p95':>8s} {'p_perm':>7s}")
    print("-" * 102)
    rows = []
    for name, shape, sel in CANDIDATES:
        real, tot = decisive(universe, real_vax, shape, sel, floor)
        null = sorted(decisive(universe, p, shape, sel, floor)[0] for p in perms)
        beat = sum(1 for x in null if x >= real)
        p_perm = (beat + 1) / (rounds + 1)
        rows.append({"candidate": name, "shape": shape, "cores": tot,
                     "decisive": real, "null_mean": round(st.mean(null), 1),
                     "null_p95": null[int(0.95 * len(null))], "p_perm": p_perm})
        print(f"{name:62s} {real:4d}/{tot:<6d} {st.mean(null):9.1f} "
              f"{null[int(0.95 * len(null))]:8d} {p_perm:7.3f}")
    print("\np_perm <= 0.05: the group carries more signal than shuffled labels.")
    print("A group that fails this ships supported/refuted labels that are "
          "mostly noise.")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Multi-tier candidate inventory.")
    ap.add_argument("--db", type=Path, default=_REPO / "data" / "medtempo.db")
    ap.add_argument("--out", type=Path, default=_REPO / "data" / "pilot")
    ap.add_argument("--rounds", type=int, default=200)
    ap.add_argument("--floor", type=int, default=20)
    args = ap.parse_args()
    rows = run(args.db, args.rounds, args.floor)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "multi_inventory.json").write_text(
        json.dumps({"floor": args.floor, "rounds": args.rounds, "rows": rows},
                   indent=2), encoding="utf-8")
    print(f"\nWritten to {args.out / 'multi_inventory.json'}")


if __name__ == "__main__":
    main()
