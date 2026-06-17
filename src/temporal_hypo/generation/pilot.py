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
from temporal_hypo.generation.cores import enumerate_group, feasible_polarities, realize
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.sampling import balance_group
from temporal_hypo.generation.templates import load_groups, render

# Short description of the locked computation rule per mode (for Part C).
RULE_BY_MODE = {
    "dir_bool": "precedes denom = reports with both, ordered; supported if frac>0.5",
    "dir_choice": "precedes frac on ordered-pair denom; names higher-frac event",
    "prop_precedes": "precedes frac; claim supported if |p-actual|<=5pp",
    "prop_cooccurs": "co-occurs frac (both-present denom); 5pp tolerance",
    "prop_sequence": "sequence frac (all-three denom); 5pp tolerance",
    "sym_bool_cooccurs": "co-occurs frac (both-present denom); supported if >0.5",
    "seq_bool": "sequence frac of asserted order (all-three denom); >0.5",
    "modal_choice": "argmax strict ordering over all-three denom; modal != tie",
    "consistency_bool": "modal-ordering share over all-three denom; >0.5",
    "first_choice": "first_among frac (all-candidates denom); argmax term",
    "last_choice": "last_among frac (all-candidates denom); argmax term",
    "first_bool": "first_among frac for named event; >0.5",
    "multi_differ_precedes": "two precedes fracs; |p1-p2|>10pp",
    "multi_dir_precedes": "two precedes fracs; names higher cohort",
    "multi_differ_cooccurs": "two co-occurs fracs; |p1-p2|>10pp",
    "multi_dir_cooccurs": "two co-occurs fracs; names higher cohort",
    "multi_differ_sequence": "two sequence fracs; |p1-p2|>10pp",
    "multi_dir_sequence": "two sequence fracs; names higher cohort",
    "multi_same_modal_order": "modal ordering in each cohort; same?",
    "multi_same_first": "modal first event in each cohort; same?",
    "multi_differ_first": "modal first event in each cohort; differ?",
    "multi_dir_first": "first_among frac of focal event in each cohort; higher cohort",
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
    "F-V1", "F-V2", "F-V3", "P-M1", "P-M2", "C-M1", "C-M2", "S-M1",
    "S-M2", "S-M3", "F-M1", "F-M3", "P-R1", "C-R1", "S-R1", "F-R1",
]


def _pick_polarity(core) -> str:
    fp = feasible_polarities(core)
    for pol in ("supported", "refuted", "insufficient"):
        if pol in fp:
            return pol
    return "insufficient"


def _validation_entry(core, group, index) -> dict:
    pol = _pick_polarity(core)
    facts = realize(core, pol)
    claim = render(group, "original", "claim", facts.slot_values)
    entry = {
        "group_id": core.group_id,
        "mode": core.mode,
        "answer_type": core.answer_type,
        "claim": claim,
        "events": list(facts.events_assigned),
        "vaccines": list(facts.vaccines_assigned),
        "rule": RULE_BY_MODE.get(core.mode, core.mode),
        "n": facts.gold_n,
        "k": core.k,
        "proportion": None if facts.gold_proportion is None
        else round(facts.gold_proportion, 4),
        "verdict": facts.gold_verdict,
        "ci": [round(facts.ci[0], 4), round(facts.ci[1], 4)] if facts.ci else None,
        "ci_width": round(facts.ci[1] - facts.ci[0], 4) if facts.ci else None,
        "confidence_tag": facts.confidence_tag,
    }
    if core.level == "multi" and core.proportion2 is not None:
        entry["cohort2"] = {
            "proportion2": round(core.proportion2, 4),
            "n2": core.n2,
            "k2": core.k2,
        }
    # sample reports entering the denominator
    events = facts.events_assigned
    sample = []
    if core.report_id is not None:
        tmap = index.report_terms[core.report_id]
        sample.append((core.report_id, {e: tmap.get(e) for e in events}))
    else:
        shown = 0
        for vid in core.cohort_ids:
            tmap = index.report_terms[vid]
            if all(e in tmap for e in events):
                sample.append((vid, {e: tmap[e] for e in events}))
                shown += 1
                if shown >= 5:
                    break
    entry["sample_reports"] = sample
    return entry


def run_pilot(
    db_path: Path, out_dir: Path, *, seed: int = 0, t: int = 100
) -> dict:
    conn = sqlite3.connect(str(db_path))
    index = CorpusIndex.load(conn)
    groups = load_groups()

    # Enumerate the viable-core population once (canonical group order).
    cores_by_group = {gid: enumerate_group(index, g) for gid, g in groups.items()}

    # --- Part A ----------------------------------------------------------
    report = report_a.build_report(index, conn, groups, cores_by_group)
    writers.write_report(
        report,
        out_dir / "distribution_report.md",
        out_dir / "distribution_report.json",
    )

    # --- Part B ----------------------------------------------------------
    all_records: list[dict] = []
    b_summary: dict[str, dict] = {}
    for gid, group in groups.items():
        sel = balance_group(cores_by_group[gid], gid, t=t, seed=seed)
        b_summary[gid] = {
            "counts": sel.counts,
            "targets": sel.targets,
            "under_target": sel.under_target,
            "pool_sizes": sel.pool_sizes,
        }
        for seq, (core, polarity, band) in enumerate(sel.chosen):
            facts = realize(core, polarity)
            all_records.extend(
                inst_mod.build_records(facts, group, seq=seq, band=band)
            )
    writers.write_jsonl(all_records, out_dir / "pilot_instances.jsonl")

    # --- Part C ----------------------------------------------------------
    samples = []
    for gid in VALIDATION_GROUPS:
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
