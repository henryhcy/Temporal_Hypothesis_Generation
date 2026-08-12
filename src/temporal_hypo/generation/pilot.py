"""Pilot driver: enumerate cores, emit Part A report, Part B dataset, Part C sample.

Run via ``scripts/run_pilot.py``. Produces, under ``data/pilot/``:
- distribution_report.md / .json   (Part A)
- pilot_instances.jsonl            (Part B)
- validation_sample.md             (Part C)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from temporal_hypo.generation import cores as cores_mod
from temporal_hypo.generation import instances as inst_mod
from temporal_hypo.generation import report_a, writers
from temporal_hypo.generation.cores import (
    enumerate_group,
    enumerate_group_full,
    feasible_polarities,
    realize,
)
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.sampling import balance_group
from temporal_hypo.core.answers import oriented_significance
from temporal_hypo.core.min_n import family_floor
from temporal_hypo.core.significance import ALPHA
from temporal_hypo.generation.evidence import evidence_ids
from temporal_hypo.generation.templates import load_groups, render

# Short description of the locked computation rule per mode (for Part C).
RULE_BY_MODE = {
    "dir_bool": "precedes denom = reports with both, ordered; supported if frac>0.5",
    "dir_choice": "precedes frac on ordered-pair denom; names higher-frac event",
    "sym_bool_cooccurs": "co-occurs frac (both-present denom); supported if >0.5",
    "seq_bool": "most-common ordering (orderable denom); unique modal; modal-vs-runner-up test",
    "modal_choice": "argmax strict ordering over orderable denom; modal-vs-runner-up test",
    "first_choice": "first_among argmax (all-candidates denom); modal-vs-runner-up test",
    "last_choice": "last_among argmax (all-candidates denom); modal-vs-runner-up test",
    "first_bool": "most-common first event (all-candidates denom); unique winner; modal-vs-runner-up test",
    "multi_differ_precedes": "two precedes fracs; |p1-p2|>10pp",
    "multi_dir_precedes": "two precedes fracs; names higher cohort",
    "multi_differ_cooccurs": "two co-occurs fracs; |p1-p2|>10pp",
    "multi_differ_sequence": "two sequence fracs; |p1-p2|>10pp",
    "multi_same_modal_order": "modal ordering in each cohort; same?",
    "multi_same_first": "modal first event in each cohort; same?",
    "multi_differ_first": "modal first event in each cohort; differ?",
    "rep_dir_bool": "per-report relation; before => supported",
    "rep_dir_choice": "per-report relation; names earlier event",
    "rep_sym_bool": "per-report relation; co_exist => supported",
    "rep_seq_bool": "per-report strict order A<B<C",
    "rep_first_choice": "per-report first_among single winner",
    "rep_last_choice": "per-report last_among single winner",
    "rep_first_bool": "per-report: is named event the unique earliest?",
}

# Groups sampled for Part C (spans families, answer types, levels).
VALIDATION_GROUPS = [
    "P-V1", "P-V2", "P-V3", "C-V1", "C-V2", "C-V3", "S-V2", "S-V3",
    "F-V1", "F-V2", "F-V3", "P-M1", "P-M2", "C-M1", "S-M1",
    "S-M3", "F-M1", "P-R1", "C-R1", "S-R1", "F-R1",
]


def _natural_verdict_counts(chosen) -> dict:
    """Summarise the natural-verdict distribution of a full-mode group."""
    counts = {"supported": 0, "refuted": 0, "insufficient": 0}
    for _core, verdict, _band in chosen:
        counts[verdict] = counts.get(verdict, 0) + 1
    return {"counts": counts, "n_cores": len(chosen)}


def _pick_polarity(core) -> str:
    fp = feasible_polarities(core)
    for pol in ("supported", "refuted", "insufficient"):
        if pol in fp:
            return pol
    return "insufficient"


def _levels_of(index, vid, events) -> dict:
    tmap = index.report_terms[vid]
    return {e: tmap.get(e) for e in events}


_EXCLUSION_REASON = {
    "dir_bool": "co-exist (same level) -- not ordered, so excluded from a "
                "PRECEDES denominator",
    "dir_choice": "co-exist (same level) -- not ordered, so excluded from a "
                  "PRECEDES denominator",
    "sym_bool_cooccurs": "n/a -- every both-present report counts for CO-OCCURS",
    "seq_bool": "two or more of the three share a level -- triple not orderable",
    "modal_choice": "two or more of the three share a level -- triple not orderable",
    "first_choice": "tie for first -- no single earliest event",
    "last_choice": "tie for last -- no single latest event",
    "first_bool": "tie for first -- no single earliest event",
}


def _validation_entry(core, group, index, polarity=None) -> dict:
    """One hand-checkable entry: the claim, its evidence ids, and the arithmetic.

    Rewritten 2026-08-11. The previous version listed "reports entering the
    denominator" by testing only that both events were PRESENT, which for a
    precedes claim wrongly included co-exist pairs -- reports the locked rule
    EXCLUDES. A hand-checker following it would either reject correct code or
    validate against the wrong evidence, so the guard could not do its job. The
    sets now come from ``evidence.evidence_ids``, which applies each mode's real
    conditioning in the orientation the instance asserts.
    """
    pol = polarity or _pick_polarity(core)
    facts = realize(core, pol)
    claim = render(group, "original", "claim", facts.slot_values,
                   negated=facts.negated)
    sig = oriented_significance(facts)
    ev = evidence_ids(index, facts)
    events = facts.events_assigned

    entry = {
        "group_id": core.group_id,
        "mode": core.mode,
        "answer_type": core.answer_type,
        "polarity": pol,
        "negated": facts.negated,
        "claim": claim,
        "events": list(events),
        "vaccines": list(facts.vaccines_assigned),
        "rule": RULE_BY_MODE.get(core.mode, core.mode),
        "exclusion_reason": _EXCLUSION_REASON.get(core.mode, ""),
        "n": facts.gold_n,
        "k": facts.gold_k,
        "proportion": (round(facts.gold_proportion, 4)
                       if facts.gold_proportion is not None else None),
        "verdict": facts.gold_verdict,
        "subtype": sig.decision.subtype if sig.decision else None,
        "test": sig.test,
        "p_claim": None if sig.p_claim is None else round(sig.p_claim, 6),
        "p_opposite": None if sig.p_opposite is None else round(sig.p_opposite, 6),
        "alpha": ALPHA,
        "min_n_floor": (family_floor(core.family)
                        if core.report_id is None else None),
        "ci": facts.ci, "ci_width": None, "confidence_tag": facts.confidence_tag,
    }
    if facts.ci:
        entry["ci"] = [round(facts.ci[0], 4), round(facts.ci[1], 4)]
        entry["ci_width"] = round(facts.ci[1] - facts.ci[0], 4)
    if core.n2 is not None:
        entry["cohort2"] = {"proportion2": (round(core.proportion2, 4)
                                           if core.proportion2 is not None else None),
                            "n2": core.n2, "k2": core.k2}

    # the three id sets, with levels, so the counts can be recomputed by eye
    def _rows(ids, cap=6):
        return [(vid, _levels_of(index, vid, events)) for vid in ids[:cap]]

    if "denominator" in ev:
        num = set(ev["numerator"])
        entry["supports"] = _rows([v for v in ev["denominator"] if v in num])
        entry["against"] = _rows([v for v in ev["denominator"] if v not in num])
        entry["excluded"] = _rows(ev["excluded"])
        entry["counts_check"] = {
            "denominator_ids": len(ev["denominator"]),
            "numerator_ids": len(ev["numerator"]),
            "excluded_ids": len(ev["excluded"]),
            "matches_gold_n": len(ev["denominator"]) == facts.gold_n,
            "matches_gold_k": len(ev["numerator"]) == facts.gold_k,
        }
    elif "report_id" in ev:
        entry["supports"] = _rows([ev["report_id"]])
    elif "cohort_1" in ev:
        for key in ("cohort_1", "cohort_2"):
            blk = ev[key]
            entry[key] = {
                "denominator": len(blk["denominator"]),
                "numerator": len(blk["numerator"]),
                "excluded": len(blk["excluded"]),
                "sample": _rows(blk["denominator"], 4),
            }
    return entry


def run_pilot(
    db_path: Path, out_dir: Path, *, seed: int = 0, t: int = 100,
    full: bool = False
) -> dict:
    conn = sqlite3.connect(str(db_path))
    index = CorpusIndex.load(conn)
    groups = load_groups()

    # Enumerate the viable-core population once (canonical group order).
    # full=True draws the whole viable population (no top-K cap); otherwise the
    # provisional top-K breadth used for the balanced pilot.
    enum = enumerate_group_full if full else enumerate_group
    cores_by_group = {gid: enum(index, g) for gid, g in groups.items()}

    # --- Part A ----------------------------------------------------------
    report = report_a.build_report(index, conn, groups, cores_by_group)
    writers.write_report(
        report,
        out_dir / "distribution_report.md",
        out_dir / "distribution_report.json",
    )

    # --- Part B ----------------------------------------------------------
    out_name = "instances.jsonl" if full else "pilot_instances.jsonl"
    all_records: list[dict] = []
    b_summary: dict[str, dict] = {}
    for gid, group in groups.items():
        if full:
            # whole-population: emit every viable core once at its natural
            # verdict -- no balancing, no refuted-by-flip, no insufficient cap.
            chosen = [(c, c.natural_verdict, None)
                      for c in cores_by_group[gid] if c.computable]
            b_summary[gid] = _natural_verdict_counts(chosen)
        else:
            # `group` is passed so feasible_polarities can see negated wording;
            # `t=None` lets the group's own S set the budget (equal thirds).
            sel = balance_group(cores_by_group[gid], gid, group, t=None, seed=seed)
            chosen = sel.chosen
            b_summary[gid] = {
                "S": sel.S,
                "counts": sel.counts,
                "targets": sel.targets,
                "under_target": sel.under_target,
                "pool_sizes": sel.pool_sizes,
                "insufficient_subtypes": sel.subtype_counts,
                "insufficient_subtype_pools": sel.subtype_pools,
                "reoriented": sel.reoriented,
                "mirror_pairs": sel.mirror_pairs,
            }
        for seq, (core, polarity, band) in enumerate(chosen):
            facts = realize(core, polarity)
            all_records.extend(
                inst_mod.build_records(facts, group, seq=seq, band=band,
                                       index=index)
            )
    writers.write_jsonl(all_records, out_dir / out_name)
    # also emit the input/gold split so the leakage boundary is enforced
    release = writers.split_release(all_records, out_dir, stem=out_name.split(".")[0])

    # --- Part C ----------------------------------------------------------
    samples = []
    # Skip ids that no longer exist: VALIDATION_GROUPS is a hand-written span of
    # families/answer-types/levels, and groups have been retired since it was
    # written (the PROP groups on 07-14, S-M2 on 08-04, S-V4 on 08-11).
    for gid in (g for g in VALIDATION_GROUPS if g in cores_by_group):
        comp = [c for c in cores_by_group[gid] if c.computable]
        if comp:
            samples.append(_validation_entry(comp[0], groups[gid], index))
    writers.write_validation_sample(samples, out_dir / "validation_sample.md")

    conn.close()
    return {
        "n_instances": len(all_records),
        "n_groups": len(groups),
        "part_b": b_summary,
        "validation_entries": len(samples),
        "out_dir": str(out_dir),
    }
