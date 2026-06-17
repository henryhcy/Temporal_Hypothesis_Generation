"""Assemble release-format JSONL records from realized instance facts.

One ``InstanceFacts`` (a core realized at a polarity) expands into
register x format records (4 registers x 2 formats = 8 text variants), each a
JSON object following the per-instance schema in 02_dataset_design.md, extended
with the confidence fields (decisions.md) and pilot bookkeeping.

Cohort report-id lists are NOT dumped per record (a vaccine cohort is ~1000
ids; that would bloat the file and is not needed for pilot inspection). Instead
each record carries the cohort spec (level + vaccines) and ``gold_n`` (the
statistical denominator). This is a deliberate, documented pilot deviation.
"""

from __future__ import annotations

from temporal_hypo.generation.cores import InstanceFacts
from temporal_hypo.generation.templates import FORMATS, REGISTERS, Group, render


def core_id(facts: InstanceFacts) -> str:
    """Stable identifier for the underlying factual core (pre-orientation)."""
    c = facts.core
    ev = "+".join(c.events)
    vx = "+".join(c.vaccines) if c.vaccines else (f"R{c.report_id}")
    return f"{c.group_id}|{vx}|{ev}"


def _round(x, nd=4):
    return None if x is None else round(x, nd)


def build_records(
    facts: InstanceFacts, group: Group, *, seq: int, band: str | None = None
) -> list[dict]:
    """Expand one realized instance into register x format JSONL records."""
    c = facts.core
    ci = facts.ci
    factual_core = {
        "primitive": c.primitive,
        "events": list(facts.events_assigned),
        "vaccines": list(facts.vaccines_assigned),
    }
    if c.report_id is not None:
        factual_core["report_id"] = c.report_id

    common = {
        "group_id": c.group_id,
        "level": c.level,
        "answer_type": c.answer_type,
        "gold_verdict": facts.gold_verdict,
        "gold_proportion": _round(facts.gold_proportion),
        "gold_n": c.n,
        "ci": [_round(ci[0]), _round(ci[1])] if ci else None,
        "ci_width": _round(ci[1] - ci[0]) if ci else None,
        "effect_size": _round(facts.effect_size),
        "confidence_tag": facts.confidence_tag,
        "cohort": {
            "level": c.level,
            "vaccines": list(facts.vaccines_assigned),
            "report_id": c.report_id,
        },
        "polarity": facts.polarity,
        "flip_kind": facts.flip_kind,
        "band": band,
        "derived_from_core_id": core_id(facts),
        "synonym_used": list(facts.events_assigned),
        "factual_core": factual_core,
    }

    records: list[dict] = []
    for register in REGISTERS:
        for fmt in FORMATS:
            text = render(group, register, fmt, facts.slot_values)
            rec = dict(common)
            rec["hypothesis_id"] = (
                f"{c.group_id}-{seq:04d}-{register}-{fmt}"
            )
            rec["register"] = register
            rec["format"] = fmt
            rec["text"] = text
            records.append(rec)
    return records
