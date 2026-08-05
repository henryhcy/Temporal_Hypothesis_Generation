"""Per-group three-decision label distribution + the delta from the old regime.

Runs the 2026-07-28 verdict framework (`core.verdict.three_decision`) over every
enumerated core in the corpus and reports, per template group:

- the three-decision split of the CANONICAL claim: supported / refuted /
  insufficient, with the insufficient sub-type broken out;
- **S = decisive cores** (supported + refuted). This is the supply that caps the
  group's supported and refuted classes, so the equal-thirds budget is ~1.5 * S;
- the delta from the old regime (blanket n >= 10 gate, observed-direction
  p-value) -- separating cores GAINED by the sequence floor dropping 10 -> 5
  from cores LOST to the pairwise (20) and first/last (30) floors;
- for the omnibus CHOICE groups, what they WOULD yield if the deferred
  modal-vs-runner-up test replaced GOF-vs-uniform (decisions.md 2026-07-14).

This is a measurement only -- it writes no dataset and changes no gold label.

    python scripts/run_verdict_labels.py [--db data/medtempo.db] [--out data/pilot]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from temporal_hypo.core import verdict as V
from temporal_hypo.core.answers import core_significance
from temporal_hypo.core.significance import ALPHA
from temporal_hypo.generation.cores import enumerate_group_full
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.templates import load_groups

_REPO = Path(__file__).resolve().parent.parent
_OLD_MIN_N = 10          # the retired blanket gate
_OLD_MODAL_MIN_N = 5     # the retired private floor on (top + runner-up)


def _old_significant(core, s) -> bool:
    """Reproduce the pre-2026-07-28 'significant' flag for the delta table."""
    if core.report_id is not None or not core.computable or core.n is None:
        return False
    if s.test is None:
        return False
    if s.test == "modal_runner":
        p = min(s.p_claim, s.p_opposite)
        return p < ALPHA and s.details.get("n_cells", 0) >= _OLD_MODAL_MIN_N
    if s.p_claim is not None:            # directional: observed-direction tail
        p = min(s.p_claim, s.p_opposite)
    else:                                # omnibus
        p = s.details.get("p_omnibus")
    if p is None:
        return False
    n = core.n if core.n2 is None else min(core.n, core.n2)
    return p < ALPHA and n >= _OLD_MIN_N


def _modal_runner_would_be(s) -> str | None:
    """The verdict the deferred modal-vs-runner-up test would give a GOF core."""
    pc = s.details.get("p_claim_modal_runner")
    po = s.details.get("p_opposite_modal_runner")
    if pc is None:
        return None
    if pc < ALPHA:
        return V.SUPPORTED
    if po is not None and po < ALPHA:
        return V.REFUTED
    return V.INSUFFICIENT


_SWEEP_FLOORS = (5, 10, 15, 20, 25, 30, 40)


def _sweep_row(group, samples) -> dict:
    """S (decisive cores) for this group at each candidate min-n floor.

    Only the FLOOR moves; the tests and alpha are unchanged. Answers "what does
    the floor cost us", which is the whole gate-reconciliation question --
    exact tests are valid at small n, so the floor is a quality choice about how
    thin the evidence behind a shipped question may be, not a validity one.
    """
    out = {"group": group.id, "family": group.family, "directional": len(samples)}
    for floor in _SWEEP_FLOORS:
        s = 0
        for n, n2, p_best in samples:
            if n is None or n < floor or (n2 is not None and n2 < floor):
                continue
            s += int(p_best < ALPHA)
        out[f"S@{floor}"] = s
    return out


def label_group(group, cores) -> dict:
    row = {
        "group": group.id, "family": group.family, "level": group.level,
        "mode": None, "enumerated": len(cores),
        "supported": 0, "refuted": 0, "insufficient": 0,
        "sub_underpowered": 0, "sub_sparse": 0, "sub_not_locatable": 0,
        "sub_non_directional": 0, "sub_unknown": 0, "deterministic": 0,
        "old_significant": 0, "new_decisive": 0,
        "gained_vs_old": 0, "lost_vs_old": 0,
        # the two INDEPENDENT causes of a loss, never to be reported as one
        # number: a tightened min-n floor is a data-supply question, a
        # non-directional claim shape is a template-design question.
        "lost_to_gate": 0, "lost_to_non_directional": 0, "lost_other": 0,
        "modal_runner_would_decide": 0,
    }
    samples = []      # (n, n2, best directional tail) for the floor sweep
    for c in cores:
        row["mode"] = c.mode
        s = core_significance(c)
        d = s.decision
        if d is None:
            continue
        if d.subtype == V.DETERMINISTIC:
            row["deterministic"] += 1
            continue
        row[d.verdict] += 1
        if d.verdict == V.INSUFFICIENT:
            key = {V.UNDERPOWERED: "sub_underpowered", V.SPARSE: "sub_sparse",
                   V.NOT_LOCATABLE: "sub_not_locatable",
                   V.NON_DIRECTIONAL: "sub_non_directional"}.get(
                       d.subtype, "sub_unknown")
            row[key] += 1
        if s.p_claim is not None and s.p_opposite is not None:
            samples.append((c.n, c.n2, min(s.p_claim, s.p_opposite)))
        old = _old_significant(c, s)
        new = d.decisive
        row["old_significant"] += int(old)
        row["new_decisive"] += int(new)
        row["gained_vs_old"] += int(new and not old)
        row["lost_vs_old"] += int(old and not new)
        if old and not new:
            if d.subtype == V.SPARSE:
                row["lost_to_gate"] += 1
            elif d.subtype == V.NON_DIRECTIONAL:
                row["lost_to_non_directional"] += 1
            else:
                row["lost_other"] += 1
        if d.subtype == V.NON_DIRECTIONAL:
            would = _modal_runner_would_be(s)
            if would in (V.SUPPORTED, V.REFUTED):
                row["modal_runner_would_decide"] += 1
    s_pool = row["supported"] + row["refuted"]
    row["S"] = s_pool
    row["budget_1_5_S"] = round(1.5 * s_pool)
    return row, samples


def run(db_path: Path, out_dir: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    index = CorpusIndex.load(conn)
    groups = load_groups()
    labeled = [(g, label_group(g, enumerate_group_full(index, g)))
               for g in groups.values()]
    rows = [r for _, (r, _) in labeled]
    sweep = [_sweep_row(g, sm) for g, (_, sm) in labeled if sm]
    conn.close()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verdict_labels.json").write_text(
        json.dumps({"groups": rows, "floor_sweep": sweep}, indent=2),
        encoding="utf-8")
    (out_dir / "verdict_labels.md").write_text(_render_md(rows, sweep),
                                               encoding="utf-8")
    return {"rows": rows, "sweep": sweep, "out_dir": str(out_dir)}


def _render_md(rows, sweep) -> str:
    out = [
        "# Three-decision label distribution (decisions.md 2026-07-28)",
        "",
        "Canonical-orientation claim per enumerated core. `S` = decisive cores "
        "(supported + refuted); the equal-thirds budget is ~1.5*S.",
        "Gate = the shared family floor (pairwise/co-occurs 20, sequence 5, "
        "first/last 30), replacing the blanket n>=10.",
        "",
        "| group | mode | cores | sup | ref | insuf | S | ~1.5S | "
        "underpow | sparse | non-dir | old sig | new dec | +gain | -lost |",
        "|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for r in rows:
        if r["deterministic"]:
            out.append(f"| {r['group']} | {r['mode']} | {r['enumerated']} | "
                       f"(report-level: {r['deterministic']} deterministic) "
                       "| | | | | | | | | | | |")
            continue
        out.append(
            f"| {r['group']} | {r['mode']} | {r['enumerated']} | {r['supported']} "
            f"| {r['refuted']} | {r['insufficient']} | {r['S']} "
            f"| {r['budget_1_5_S']} | {r['sub_underpowered']} | {r['sub_sparse']} "
            f"| {r['sub_non_directional']} | {r['old_significant']} "
            f"| {r['new_decisive']} | {r['gained_vs_old']} | {r['lost_vs_old']} |")
    nd = [r for r in rows if r["sub_non_directional"]]
    if nd:
        out += ["", "## Non-directional groups (no three-decision mapping)", "",
                "These carry an omnibus / 'differ' / 'same' claim shape. The last "
                "column is what the deferred modal-vs-runner-up test would "
                "decide if adopted (decisions.md 2026-07-14, still open).", "",
                "| group | mode | non-directional cores | would be decisive |",
                "|---|---|--:|--:|"]
        for r in nd:
            out.append(f"| {r['group']} | {r['mode']} | {r['sub_non_directional']} "
                       f"| {r['modal_runner_would_decide'] or '-'} |")
    if sweep:
        out += ["", "## Min-n floor sensitivity (directional cores only)", "",
                "S = decisive cores at each candidate floor; tests and alpha "
                "unchanged. The locked family floors are 20 pairwise/co-occurs, "
                "5 sequence, 30 first/last.", "",
                "| group | fam | dir. cores | "
                + " | ".join(f"S@{f}" for f in _SWEEP_FLOORS) + " |",
                "|---|---|--:|" + "--:|" * len(_SWEEP_FLOORS)]
        for r in sweep:
            out.append(f"| {r['group']} | {r['family'][:4]} | {r['directional']} | "
                       + " | ".join(str(r[f"S@{f}"]) for f in _SWEEP_FLOORS) + " |")
        fams = sorted({r["family"] for r in sweep})
        out += ["", "| family | " + " | ".join(f"S@{f}" for f in _SWEEP_FLOORS) + " |",
                "|---|" + "--:|" * len(_SWEEP_FLOORS)]
        for fam in fams:
            fr = [r for r in sweep if r["family"] == fam]
            out.append(f"| **{fam}** | " + " | ".join(
                str(sum(r[f"S@{f}"] for r in fr)) for f in _SWEEP_FLOORS) + " |")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Three-decision label distribution.")
    ap.add_argument("--db", type=Path, default=_REPO / "data" / "medtempo.db")
    ap.add_argument("--out", type=Path, default=_REPO / "data" / "pilot")
    args = ap.parse_args()
    res = run(args.db, args.out)
    rows = res["rows"]
    print(f"Verdict labels written to {res['out_dir']}\n")

    live = [r for r in rows if not r["deterministic"]]
    tot_sup = sum(r["supported"] for r in live)
    tot_ref = sum(r["refuted"] for r in live)
    tot_ins = sum(r["insufficient"] for r in live)
    tot = tot_sup + tot_ref + tot_ins
    print(f"Cohort-level cores labeled: {tot}")
    if tot:
        print(f"  supported     {tot_sup:6d}  ({tot_sup/tot:.1%})")
        print(f"  refuted       {tot_ref:6d}  ({tot_ref/tot:.1%})")
        print(f"  insufficient  {tot_ins:6d}  ({tot_ins/tot:.1%})")
    print("\nInsufficient sub-types:")
    for key, label in (("sub_underpowered", "underpowered"),
                       ("sub_sparse", "sparse (below family floor)"),
                       ("sub_not_locatable", "not locatable (n=0)"),
                       ("sub_non_directional", "non-directional (no mapping)"),
                       ("sub_unknown", "unknown (n dropped below viability)")):
        print(f"  {label:38s} {sum(r[key] for r in live):6d}")
    print("\nDelta vs the old regime (blanket n>=10, observed-direction p):")
    print(f"  gained (now decisive, was not) {sum(r['gained_vs_old'] for r in live):6d}")
    print(f"  lost   (was decisive, now not) {sum(r['lost_vs_old'] for r in live):6d}")
    print(f"    ...to the tightened min-n floor {sum(r['lost_to_gate'] for r in live):6d}"
          "   (data supply)")
    print(f"    ...to non-directional shapes    {sum(r['lost_to_non_directional'] for r in live):6d}"
          "   (template design)")
    print(f"    ...other                        {sum(r['lost_other'] for r in live):6d}")
    print("  by family (gained / lost-to-gate / lost-to-non-directional):")
    for fam in ("pairwise", "sequence", "first_last"):
        f = [r for r in live if r["family"] == fam]
        print(f"    {fam:11s} +{sum(r['gained_vs_old'] for r in f):5d} "
              f" -{sum(r['lost_to_gate'] for r in f):5d} "
              f" -{sum(r['lost_to_non_directional'] for r in f):5d}")
    starved = [r["group"] for r in live if r["S"] == 0]
    print(f"\nGroups with S = 0 (cannot ship supported OR refuted): "
          f"{starved or 'none'}")


if __name__ == "__main__":
    main()
