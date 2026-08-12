"""ONE-OFF: three fully-annotated sample instances for showing the dataset.

Not part of the pipeline and not called by `run_pilot`. It reads the finished
generator and dumps, for three deliberately-chosen cores, everything the release
carries plus two things the release deliberately does NOT carry:

- the **positional / rank statistics** (`core.positions`), which are DESCRIPTIVE
  only. Lever 2 retired them as verdict drivers on 2026-08-11 because the
  Mann-Whitney normal approximation is anti-conservative on tie-heavy ordinal data
  (~11% decisive under shuffled labels vs a nominal 5%). They are shown here purely
  so a reader can compare them against the exact test that does produce the label.
- the mirror partner's verdict, so the supported/refuted pairing is visible.

The three cores are chosen to span every mechanism in the benchmark:

1. P-V1  BOOL, single cohort, exact binomial vs 0.5, co-exist reports EXCLUDED
2. F-V2  CHOICE, single cohort, modal-vs-runner-up, tie reports EXCLUDED, answer key
3. P-M2  CHOICE, two cohorts, Fisher exact 2x2, the only surviving multi group

    python scripts/make_sample_instances.py [--db data/medtempo.db]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from temporal_hypo.core import positions
from temporal_hypo.core.answers import oriented_significance
from temporal_hypo.generation import corpus as C
from temporal_hypo.generation import cores as Cs
from temporal_hypo.generation import instances as inst
from temporal_hypo.generation.cores import enumerate_group_full, realize
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.evidence import evidence_ids
from temporal_hypo.generation.templates import REGISTERS, load_groups, render

_REPO = Path(__file__).resolve().parent.parent

# (group, how to pick the core) -- picked for mechanism coverage, then for a
# mid-sized n so the id lists are readable rather than pathological
PICKS = [
    ("P-V1", "widest evidence spread: has co-exist reports EXCLUDED from n"),
    ("F-V2", "argmax CHOICE: per-candidate counts, ties excluded, answer key"),
    ("P-M2", "two-cohort: per-cohort denominators, the only surviving multi group"),
]


def _positional(index, core, facts):
    """Descriptive rank statistics. NOT label-producing -- see module docstring."""
    ev = facts.events_assigned
    out = {}
    if len(core.vaccines) == 1:
        cohort = index.cohort(core.vaccines[0])
        if len(ev) >= 2:
            d = C.pair_distances(index, ev[0], ev[1], cohort)
            if d:
                r = positions.wilcoxon_signed_rank(d)
                out["wilcoxon_signed_rank"] = {
                    "what": f"level({ev[0]}) - level({ev[1]}) per report, symmetric about 0?",
                    "n_present_reports": len(d),
                    "n_nonzero_pairs": r.get("n"),
                    "statistic_W_plus": r.get("stat"),
                    "p": r.get("p"), "method": r.get("method"),
                    "note": "keeps ALL both-present reports, including co-exist "
                            "(d=0), unlike the precedes denominator which drops them",
                }
        if len(ev) == 3:
            blocks = C.triple_positions(index, list(ev), cohort)
            if blocks:
                f = positions.friedman(blocks)
                k = positions.kendalls_w(blocks)
                out["friedman"] = {"what": "do the three events differ in position?",
                                   "n_reports": len(blocks), "Q": f.get("Q"),
                                   "df": f.get("df"), "p": f.get("p")}
                out["kendalls_w"] = {"what": "how consistent is the ordering across reports?",
                                     "W": k.get("W"), "p": k.get("p")}
    elif len(core.vaccines) == 2:
        v1, v2 = facts.vaccines_assigned
        x = C.pair_distances(index, ev[0], ev[1], index.cohort(v1))
        y = C.pair_distances(index, ev[0], ev[1], index.cohort(v2))
        if x and y:
            r = positions.mann_whitney_u(x, y)
            out["mann_whitney_u"] = {
                "what": f"is the {ev[0]}-{ev[1]} rank distance shifted between cohorts?",
                "n1": len(x), "n2": len(y), "U": r.get("stat", r.get("U")), "p": r.get("p"),
                "method": r.get("method"),
                "caveat": "anti-conservative on tie-heavy ordinal data; NOT a label",
            }
    return out


def build(index, groups, gid, why):
    g = groups[gid]
    decisive = [c for c in enumerate_group_full(index, g)
                if Cs.cohort_decision(c).decisive]
    # a mid-sized core: big enough to be interesting, small enough to print
    decisive.sort(key=lambda c: abs((c.n or 0) - 25))
    core = decisive[0]

    sup = realize(core, "supported")
    ref = realize(core, "refuted")
    recs = inst.build_records(sup, g, seq=0, index=index)
    rec = next(r for r in recs if r["register"] == "original" and r["format"] == "claim")

    ev = evidence_ids(index, sup)
    def _ids(block):
        return {k: {"count": len(v), "report_ids": v} for k, v in block.items()
                if isinstance(v, list)}

    return {
        "group_id": gid,
        "why_this_example": why,
        "mode": core.mode,
        "answer_type": core.answer_type,
        "level": core.level,
        "claim_all_registers": {
            r: render(g, r, "claim", sup.slot_values, negated=sup.negated)
            for r in REGISTERS
        },
        "question_original": render(g, "original", "question", sup.slot_values,
                                    negated=sup.negated),
        "gold": {k: rec[k] for k in (
            "gold_verdict", "test_verdict", "insufficient_subtype", "negated",
            "gold_proportion", "gold_n", "gold_k", "gold_n2", "gold_k2",
            "ci", "ci_width", "confidence_tag", "effect_size",
            "options", "gold_answer") if k in rec},
        "test": {k: rec[k] for k in (
            "sig_test", "p_value", "p_claim", "p_opposite", "significant",
            "alpha", "min_n_floor", "family") if k in rec},
        "covered_case_ids": (_ids(ev) if "denominator" in ev
                             else {ck: _ids(cv) for ck, cv in ev.items()
                                   if isinstance(cv, dict)}),
        "mirror_pair": {
            "note": "same core, opposite orientation; both share derived_from_core_id "
                    "and MUST stay on the same side of any train/test split",
            "derived_from_core_id": rec["derived_from_core_id"],
            "supported_text": render(g, "original", "claim", sup.slot_values,
                                     negated=sup.negated),
            "refuted_text": render(g, "original", "claim", ref.slot_values,
                                   negated=ref.negated),
            "refuted_verdict": ref.gold_verdict,
            "refuted_p_claim": round(oriented_significance(ref).p_claim, 6)
            if oriented_significance(ref).p_claim is not None else None,
            "refuted_p_opposite": round(oriented_significance(ref).p_opposite, 6)
            if oriented_significance(ref).p_opposite is not None else None,
        },
        "positional_statistics_DESCRIPTIVE_ONLY": _positional(index, core, sup),
        "extra_counts": {str(k): v for k, v in (core.extra or {}).items()
                         if k in ("counts", "fracs", "winner", "modal",
                                  "modal_count", "tie_rate", "ties", "n_present",
                                  "focal", "unique", "modal_tie")},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="One-off annotated sample instances.")
    ap.add_argument("--db", type=Path, default=_REPO / "data" / "medtempo.db")
    ap.add_argument("--out", type=Path, default=_REPO / "docs" / "reference")
    args = ap.parse_args()

    conn = sqlite3.connect(str(args.db))
    index = CorpusIndex.load(conn)
    groups = load_groups()
    samples = [build(index, groups, gid, why) for gid, why in PICKS]
    conn.close()

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "Sample_Instances.json").write_text(
        json.dumps(samples, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.out / 'Sample_Instances.json'}")
    for s in samples:
        cc = s["covered_case_ids"]
        n = (cc.get("denominator", {}).get("count")
             if "denominator" in cc
             else cc.get("cohort_1", {}).get("denominator", {}).get("count"))
        print(f"  {s['group_id']:<6} {s['mode']:<20} n={n} "
              f"verdict={s['gold']['gold_verdict']}")


if __name__ == "__main__":
    main()
