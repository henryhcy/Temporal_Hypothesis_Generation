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
                                          [--rounds 1000] [--floor 10]
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
from itertools import combinations
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
    # F-M3 is a SHIPPING group that had never been screened (added 2026-08-11).
    # Unlike M-B it conditions on a TRIPLE: reports containing all three
    # candidates, with tie reports excluded from the denominator per the 08-11
    # decision. The focal event is fixed from the real data so real and null are
    # counted over identical cores.
    ("[base] F-M3 first-of-triple  A is first among A,B,C | ties excluded",
     "triple", "first"),
    # Substitute candidates for F-M3, added 2026-08-11 after it failed. For TWO
    # events "first" IS "precedes", so a distinct first/last multi shape needs
    # three -- which is the conditioning that starved F-M3 (75 cores). The only
    # lever left is the DENOMINATOR: counting tie reports as "not uniquely first"
    # widens it, exactly the move that let M-F beat P-M2 on supply.
    ("M-G  first-of-triple WIDE     A is first among A,B,C | ties count as not-first",
     "triple", "first_wide"),
    ("M-I  last-of-triple          A is last among A,B,C | ties excluded",
     "triple", "last"),
    ("M-J  last-of-triple WIDE     A is last among A,B,C | ties count as not-last",
     "triple", "last_wide"),
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

    # TRIPLES (F-M3). Counted per report rather than over all C(65,3) triples,
    # which would be ~44k x 3166 scans; a report carries ~7 universe terms, so
    # this is ~35 increments per report instead.
    termset = set(terms)
    tri_count: dict[tuple[str, ...], int] = {}
    for rid, t in index.report_terms.items():
        present = sorted(x for x in t if x in termset)
        if len(present) < 3:
            continue
        for combo in combinations(present, 3):
            tri_count[combo] = tri_count.get(combo, 0) + 1

    triple = {}
    for combo, cnt in tri_count.items():
        if cnt < 2 * floor:
            continue
        rows = []
        wins_f = {x: 0 for x in combo}
        wins_l = {x: 0 for x in combo}
        for rid, t in index.report_terms.items():
            idxs = [t.get(x) for x in combo]
            if any(i is None for i in idxs):
                continue
            lo, hi = min(idxs), max(idxs)
            first = [x for x, i in zip(combo, idxs) if i == lo]
            last = [x for x, i in zip(combo, idxs) if i == hi]
            ftie, ltie = len(first) > 1, len(last) > 1
            rows.append((rid, None if ftie else first[0], ftie,
                         None if ltie else last[0], ltie))
            if not ftie:
                wins_f[first[0]] += 1
            if not ltie:
                wins_l[last[0]] += 1
        # focals fixed from the REAL data so real and null count identical cores
        triple[combo] = (max(combo, key=lambda x: (wins_f[x], x)),
                         max(combo, key=lambda x: (wins_l[x], x)),
                         rows)
    return terms, single, pair, triple


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
    """NOTE the tie convention differs from `_tally_triple` on purpose.

    The single-event candidates ask "is A AT the extreme level", so a report where
    A shares level 0 with another event still counts -- that is what "A is the
    report's first event" means for these shapes. F-M3 asks "is A UNIQUELY first
    among A, B, C", so its ties leave the denominator. The two are therefore not
    directly comparable; M-B and M-C are rejected candidates, so this only matters
    if someone revives them.
    """
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


def _tally_triple(entry, vax_of, sel):
    """First/last-among-triple, narrow or wide denominator.

    NARROW (`first` / `last`) drops tie reports, matching the shipped F-M3 and the
    2026-08-11 tie decision. WIDE (`*_wide`) keeps them and counts a tie as "not
    uniquely first/last" -- the same widening that let M-F outgrow P-M2. It is a
    different CLAIM, not a different gate: "A is first more often" where not-first
    includes "nobody was uniquely first".
    """
    focal_f, focal_l, rows = entry
    last = sel.startswith("last")
    wide = sel.endswith("_wide")
    focal = focal_l if last else focal_f
    n = {v: 0 for v in VACCINES}
    k = {v: 0 for v in VACCINES}
    for rid, fw, ftie, lw, ltie in rows:
        winner, tie = (lw, ltie) if last else (fw, ftie)
        if tie and not wide:
            continue                            # narrow: unresolvable leaves n
        v = vax_of[rid]
        n[v] += 1
        k[v] += int((not tie) and winner == focal)
    return n, k


def decisive(universe, vax_of, shape, sel, floor):
    """Cores the corpus labels supported or refuted, and the cores considered."""
    _, single, pair, triple = universe
    src, tally = ((pair, _tally_pair) if shape == "pair"
                  else (triple, _tally_triple) if shape == "triple"
                  else (single, _tally_single))
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
    ap.add_argument("--rounds", type=int, default=1000,
                    help="200 is TRIAGE ONLY -- it gave M-C 0.035 where "
                         "1000+ gives ~0.076. Never decide on 200.")
    ap.add_argument("--floor", type=int, default=10,
                    help="the locked pairwise/first-last floor "
                         "(decisions.md 2026-08-11); was 20")
    args = ap.parse_args()
    rows = run(args.db, args.rounds, args.floor)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "multi_inventory.json").write_text(
        json.dumps({"floor": args.floor, "rounds": args.rounds, "rows": rows},
                   indent=2), encoding="utf-8")
    print(f"\nWritten to {args.out / 'multi_inventory.json'}")


if __name__ == "__main__":
    main()
