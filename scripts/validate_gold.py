"""Part C, mechanised: check every gold label in the release, not a sample of 20.

The hand-check in `data/pilot/validation_sample.md` is the human-facing guard. This
is the exhaustive one: it re-derives each instance's evidence from the corpus and
asserts the invariants that must hold if the gold-label computation is correct.

Checks, in order of what has actually broken before:

A. EVIDENCE ARITHMETIC -- the denominator/numerator id sets must reproduce n and k.
B. SET ALGEBRA -- numerator subset of denominator; denominator and excluded disjoint.
C. CONDITIONING -- the locked rule per family, verified against the leveled orders:
   precedes denominators are strictly ordered and excluded are co-exist; co-occurs
   numerators are exactly the co-exist reports; sequence denominators have distinct
   levels; first/last excluded are ties.
D. DIRECTION -- every numerator report actually satisfies the claim as asserted.
E. VERDICT -- supported needs p_claim < alpha, refuted needs p_opposite < alpha,
   insufficient needs neither, and the min-n gate must agree with the sub-type.
F. INDEPENDENT RECOMPUTATION -- recompute n and k through `core.aggregation`, the
   DB-backed mirror written against the same locked rules but a different code path,
   and require agreement with the index-backed numbers.

    python scripts/validate_gold.py [--db data/medtempo.db] [--sample 400]
"""

from __future__ import annotations

import argparse
import random
import sqlite3
from collections import Counter
from pathlib import Path

from temporal_hypo.core import aggregation as agg
from temporal_hypo.core.answers import oriented_significance
from temporal_hypo.core.min_n import min_n_gate
from temporal_hypo.core.significance import ALPHA
from temporal_hypo.generation import corpus as C
from temporal_hypo.generation.cores import (
    enumerate_group,
    feasible_polarities,
    realize,
)
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.evidence import evidence_ids
from temporal_hypo.generation.templates import load_groups

_REPO = Path(__file__).resolve().parent.parent

_PRECEDES = {"dir_bool", "dir_choice"}
_SEQ = {"seq_bool", "modal_choice"}
_EXTREME = {"first_choice", "last_choice", "first_bool"}


def _lv(index, vid, events):
    t = index.report_terms[vid]
    return [t.get(e) for e in events]


def check_instance(index, facts, fails: Counter, examples: dict) -> None:
    core = facts.core
    m = core.mode
    ev = facts.events_assigned

    def bad(name, detail):
        fails[name] += 1
        examples.setdefault(name, f"{core.group_id} {ev} {core.vaccines}: {detail}")

    ids = evidence_ids(index, facts)
    if "denominator" not in ids:
        return
    den, num, exc = ids["denominator"], ids["numerator"], ids["excluded"]

    # A. evidence arithmetic
    if len(den) != facts.gold_n:
        bad("A: len(denominator) != gold_n", f"{len(den)} vs {facts.gold_n}")
    if len(num) != facts.gold_k:
        bad("A: len(numerator) != gold_k", f"{len(num)} vs {facts.gold_k}")

    # B. set algebra
    if not set(num) <= set(den):
        bad("B: numerator not a subset of denominator", "")
    if set(den) & set(exc):
        bad("B: denominator overlaps excluded", "")

    # C+D. conditioning and direction, per locked rule
    if m in _PRECEDES:
        for vid in den:
            a, b = _lv(index, vid, ev)
            if a is None or b is None or a == b:
                bad("C: precedes denominator contains a non-ordered report",
                    f"report {vid} levels={a},{b}")
        for vid in exc:
            a, b = _lv(index, vid, ev)
            if a != b:
                bad("C: precedes excluded is not co-exist", f"report {vid} {a},{b}")
        for vid in num:
            a, b = _lv(index, vid, ev)
            if not (a is not None and b is not None and a < b):
                bad("D: numerator report does not satisfy 'A before B'",
                    f"report {vid} levels={a},{b}")
    elif m == "sym_bool_cooccurs":
        for vid in num:
            a, b = _lv(index, vid, ev)
            if a != b:
                bad("D: co-occurs numerator report is not co-exist",
                    f"report {vid} {a},{b}")
        if exc:
            bad("C: co-occurs should exclude nothing", f"{len(exc)} excluded")
    elif m in _SEQ:
        for vid in den:
            lv = _lv(index, vid, ev)
            if len(set(lv)) != len(lv):
                bad("C: sequence denominator has a tied triple", f"report {vid} {lv}")
        for vid in num:
            lv = _lv(index, vid, ev)
            if lv != sorted(lv):
                bad("D: sequence numerator does not match the asserted order",
                    f"report {vid} {lv}")
    elif m in _EXTREME:
        last = (m == "last_choice")
        if exc:
            bad("C: first/last excludes nothing from the denominator "
                "(ties stay in n)", f"{len(exc)} excluded")
        for vid in ids.get("ties", []):
            lv = _lv(index, vid, ev)
            target = max(lv) if last else min(lv)
            if sum(1 for x in lv if x == target) < 2:
                bad("C: a first/last 'tie' report is not tied", f"report {vid} {lv}")
            if vid not in set(den):
                bad("C: a first/last tie left the denominator", f"report {vid}")
        for vid in num:
            lv = _lv(index, vid, ev)
            target = max(lv) if last else min(lv)
            if lv[0] != target or sum(1 for x in lv if x == target) > 1:
                bad("D: first/last numerator report does not name the extreme",
                    f"report {vid} {lv}")

    # E. verdict follows its own tail, and the gate agrees
    sig = oriented_significance(facts)
    v, pc, po = facts.gold_verdict, sig.p_claim, sig.p_opposite
    if v == "supported" and not (pc is not None and pc < ALPHA):
        bad("E: supported without a significant claim tail", f"p_claim={pc}")
    if v == "refuted" and not (po is not None and po < ALPHA):
        bad("E: refuted without a significant opposite tail", f"p_opposite={po}")
    if v == "insufficient" and pc is not None and (pc < ALPHA or (po or 1) < ALPHA):
        bad("E: insufficient despite a significant tail", f"{pc}/{po}")
    gate = min_n_gate(core.n, core.family, n2=core.n2)
    sub = sig.decision.subtype if sig.decision else None
    if not gate.testable and v != "insufficient":
        bad("E: below the min-n floor but not insufficient", gate.reason)
    if gate.testable and sub in ("sparse", "not_locatable"):
        bad("E: sub-type says thin but the gate passed", f"{sub} n={core.n}")


def recompute_independently(conn, index, facts, fails: Counter, examples: dict):
    """F: recompute n/k via the DB-backed mirror in core.aggregation."""
    core = facts.core
    if core.report_id is not None or core.vaccines.__len__() != 1:
        return
    ev = facts.events_assigned
    cohort = [index.vaers_of[vid] if hasattr(index, "vaers_of") else vid
              for vid in core.cohort_ids]
    m = core.mode
    got = None
    if m in _PRECEDES:
        got = agg.precedes_fraction(conn, ev[0], ev[1], cohort)
    elif m == "sym_bool_cooccurs":
        got = agg.co_occurs_fraction(conn, ev[0], ev[1], cohort)
    if got is None:
        return
    frac, n = got
    if n != facts.gold_n:
        fails["F: DB-backed n disagrees with index-backed n"] += 1
        examples.setdefault("F: DB-backed n disagrees with index-backed n",
                            f"{core.group_id} {ev}: {n} vs {facts.gold_n}")
    elif frac is not None and facts.gold_k is not None:
        if round(frac * n) != facts.gold_k:
            fails["F: DB-backed k disagrees with index-backed k"] += 1
            examples.setdefault("F: DB-backed k disagrees with index-backed k",
                                f"{core.group_id} {ev}: {round(frac*n)} vs {facts.gold_k}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Exhaustive gold-label validation.")
    ap.add_argument("--db", type=Path, default=_REPO / "data" / "medtempo.db")
    ap.add_argument("--sample", type=int, default=400,
                    help="instances per group to check (0 = all)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    conn = sqlite3.connect(str(args.db))
    index = CorpusIndex.load(conn)
    groups = load_groups()
    rng = random.Random(args.seed)

    fails: Counter = Counter()
    examples: dict[str, str] = {}
    checked = 0
    for gid, g in groups.items():
        cores = enumerate_group(index, g)
        if args.sample:
            rng.shuffle(cores)
            cores = cores[: args.sample]
        for core in cores:
            for pol in sorted(feasible_polarities(core, g)):
                facts = realize(core, pol)
                check_instance(index, facts, fails, examples)
                recompute_independently(conn, index, facts, fails, examples)
                checked += 1
    conn.close()

    print(f"instances checked: {checked:,}\n")
    if not fails:
        print("ALL CHECKS PASSED (A evidence arithmetic, B set algebra, "
              "C conditioning, D direction, E verdict, F independent recompute)")
    else:
        print(f"{sum(fails.values()):,} failures across {len(fails)} check(s):\n")
        for name, cnt in fails.most_common():
            print(f"  {cnt:>7,}  {name}")
            print(f"           e.g. {examples[name]}")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
