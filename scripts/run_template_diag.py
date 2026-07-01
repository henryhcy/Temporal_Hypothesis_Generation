"""Per-template diagnostics (06_pilot_examples.md, Step 3) under the new gate.

For each of the 30 template groups, enumerate the whole viable-core population,
apply the SHARED min-n gate (temporal_hypo.core.min_n) with the updated family
floors (20 pairwise/co-occurs, 30 sequence/first-last) and the expected-cell>=5
guard for the k-category distribution groups, and report:

- viable (testable) core count and the n-distribution;
- the fraction falling to `insufficient` and why (below floor vs sparse cells);
- for the chi-square-referenced distribution groups, the expected>=5 pass rate;
- a flag for any group under ~50 viable cores (under-target for T=100);
- whether the group can yield BOTH a supported and a refuted example.

Outputs data/pilot/template_diagnostics.{md,json} and prints a problem summary.
This is a diagnosis only -- it changes no gold-label code.

    python scripts/run_template_diag.py [--db data/medtempo.db] [--out data/pilot]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from itertools import permutations
from pathlib import Path

from temporal_hypo.core.min_n import min_n_gate, uses_exact
from temporal_hypo.generation.cores import enumerate_group_full, feasible_polarities
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.templates import load_groups

_REPO = Path(__file__).resolve().parent.parent

# mode -> how the k-category table is built for the expected-cell guard
_GOF_ORDERING = {"modal_choice", "consistency_bool"}      # 1x6 over orderings
_GOF_CANDIDATE = {"first_choice", "last_choice"}          # 1x3 over candidates
_FFH_ORDERING = {"multi_same_modal_order"}                # 2x6
_FFH_CANDIDATE = {"multi_same_first", "multi_differ_first"}  # 2x3
_DISTRIBUTION_GROUPS = {"S-V3", "S-V4", "F-V1", "F-V2", "S-M3", "F-M1", "F-M2"}


def _observed(core):
    """The k-category table for a distribution core, else None."""
    m = core.mode
    if m in _GOF_ORDERING:
        c = core.extra.get("counts", {})
        return [c.get(p, 0) for p in permutations(core.events)]
    if m in _GOF_CANDIDATE:
        c = core.extra.get("counts", {})
        return [c.get(t, 0) for t in core.events]
    if m in _FFH_ORDERING:
        c1, c2 = core.extra.get("counts1", {}), core.extra.get("counts2", {})
        ps = list(permutations(core.events))
        return [[c1.get(p, 0) for p in ps], [c2.get(p, 0) for p in ps]]
    if m in _FFH_CANDIDATE:
        c1, c2 = core.extra.get("counts1", {}), core.extra.get("counts2", {})
        return [[c1.get(t, 0) for t in core.events],
                [c2.get(t, 0) for t in core.events]]
    return None


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def diagnose_group(group, cores) -> dict:
    eligible = group.level != "report"   # report-level groups carry no test
    testable, below_floor, exact_cores = [], 0, 0
    verdicts = {"supported": 0, "refuted": 0, "insufficient": 0}
    feas_sup = feas_ref = False
    for c in cores:
        if not eligible:
            continue
        # FLOOR-ONLY gate: sparse k-category tables are handled by the exact test
        if not min_n_gate(c.n, c.family, n2=c.n2).testable:
            below_floor += 1
            continue
        testable.append(c)
        verdicts[c.natural_verdict] = verdicts.get(c.natural_verdict, 0) + 1
        # refuted examples are built by flipping a real core, so use
        # flip-feasibility (06 Step 4), not just the natural verdict.
        fp = feasible_polarities(c)
        feas_sup = feas_sup or "supported" in fp
        feas_ref = feas_ref or "refuted" in fp
        if group.id in _DISTRIBUTION_GROUPS:
            obs = _observed(c)
            if obs is not None and uses_exact(obs):
                exact_cores += 1
    ns = [c.n for c in testable if c.n is not None]
    n_testable = len(testable)
    # informational: fraction of testable distribution cores that use the EXACT
    # test (expected cell < 5) rather than the chi-square approximation
    exact_rate = (round(exact_cores / n_testable, 3)
                  if group.id in _DISTRIBUTION_GROUPS and n_testable > 0 else None)
    return {
        "group": group.id, "family": group.family, "level": group.level,
        "eligible": eligible,
        "enumerated": len(cores),
        "testable": n_testable,
        "insufficient_below_floor": below_floor,
        "n_min": min(ns) if ns else None,
        "n_median": _median(ns),
        "n_max": max(ns) if ns else None,
        "exact_test_rate": exact_rate,
        "verdicts_among_testable": verdicts,
        "under_target": eligible and n_testable < 50,
        "can_supported": feas_sup,
        "can_refuted": feas_ref,
    }


def run(db_path: Path, out_dir: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    index = CorpusIndex.load(conn)
    groups = load_groups()
    rows = [diagnose_group(g, enumerate_group_full(index, g))
            for g in groups.values()]
    conn.close()

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "template_diagnostics.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8")
    (out_dir / "template_diagnostics.md").write_text(_render_md(rows),
                                                     encoding="utf-8")
    return {"rows": rows, "out_dir": str(out_dir)}


def _render_md(rows) -> str:
    out = ["# Per-Template Diagnostics (06 Step 3): weak-order + exact tests", "",
           "Floor-only gate: 20 pairwise/co-occurs, 30 sequence/first-last. "
           "Sequence specific-ordering groups use WEAK ordering (co-occurrence "
           "satisfies). Sparse k-category tables use the EXACT test (no gate).",
           "Report-level groups (P-R*/C-R1/S-R1/F-R*) carry no significance test.",
           "",
           "| group | fam | lvl | viable | <floor | n min/med/max "
           "| exact% | sup/ref/insuf | flags |",
           "|---|---|---|--:|--:|---|--:|---|---|"]
    for r in rows:
        if not r["eligible"]:
            out.append(f"| {r['group']} | {r['family'][:4]} | {r['level'][:3]} "
                       f"| - | - | (not eligible) | - | - | report-level |")
            continue
        v = r["verdicts_among_testable"]
        flags = []
        if r["under_target"]:
            flags.append("UNDER-50")
        if not r["can_supported"]:
            flags.append("no-SUP")
        if not r["can_refuted"]:
            flags.append("no-REF")
        nd = f"{r['n_min']}/{r['n_median']}/{r['n_max']}"
        ex = "-" if r["exact_test_rate"] is None else f"{r['exact_test_rate']:.2f}"
        out.append(
            f"| {r['group']} | {r['family'][:4]} | {r['level'][:3]} "
            f"| {r['testable']} | {r['insufficient_below_floor']} "
            f"| {nd} | {ex} "
            f"| {v['supported']}/{v['refuted']}/{v['insufficient']} "
            f"| {' '.join(flags) or 'ok'} |")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Per-template viability diagnostics.")
    ap.add_argument("--db", type=Path, default=_REPO / "data" / "medtempo.db")
    ap.add_argument("--out", type=Path, default=_REPO / "data" / "pilot")
    args = ap.parse_args()
    res = run(args.db, args.out)
    rows = res["rows"]

    print(f"Template diagnostics written to {res['out_dir']}\n")
    elig = [r for r in rows if r["eligible"]]
    print(f"Eligible groups (non-report): {len(elig)}/{len(rows)}\n")
    zero_viable = [r["group"] for r in elig if r["testable"] == 0]
    no_live = [r["group"] for r in elig
               if not (r["can_supported"] or r["can_refuted"])]
    under = [r["group"] for r in elig if r["under_target"]]
    no_sup = [r["group"] for r in elig if not r["can_supported"]]
    no_ref = [r["group"] for r in elig if not r["can_refuted"]]
    live = len(elig) - len(no_live)
    print(f"LIVE-EXAMPLE COVERAGE: {live}/{len(elig)} eligible groups have >=1 "
          f"live example (report-level groups always do).\n")
    print("REMAINING NOTES:")
    print(f"  groups with 0 viable cores:  {zero_viable or 'none'}")
    print(f"  no live example at all:      {no_live or 'none'}")
    print(f"  under-target (<50 viable):   {under or 'none'}")
    print(f"  cannot produce SUPPORTED:    {no_sup or 'none'}")
    print(f"  cannot produce REFUTED:      {no_ref or 'none'}")


if __name__ == "__main__":
    main()
