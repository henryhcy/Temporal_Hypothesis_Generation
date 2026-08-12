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

from temporal_hypo.core.answers import (
    answer_key,
    core_decision,
    oriented_significance,
)
from temporal_hypo.core.min_n import family_floor
from temporal_hypo.core.significance import ALPHA
from temporal_hypo.generation.cores import InstanceFacts
from temporal_hypo.generation.evidence import evidence_ids
from temporal_hypo.generation.templates import FORMATS, REGISTERS, Group, render


def core_id(facts: InstanceFacts) -> str:
    """Stable identifier for the underlying factual core (pre-orientation)."""
    c = facts.core
    ev = "+".join(c.events)
    vx = "+".join(c.vaccines) if c.vaccines else (f"R{c.report_id}")
    return f"{c.group_id}|{vx}|{ev}"


def _round(x, nd=4):
    return None if x is None else round(x, nd)


# The ONLY fields a framework may see at inference. Everything else in a record is
# gold or provenance -- in particular the evidence report ids, which are the answer
# to the localization step (finding ~19 relevant reports inside a ~1,000-report
# cohort). `writers.split_release` enforces this mechanically rather than by
# convention.
INPUT_FIELDS = (
    "hypothesis_id", "group_id", "level", "answer_type", "register", "format",
    "text", "options", "cohort",
)


def build_records(
    facts: InstanceFacts, group: Group, *, seq: int, band: str | None = None,
    index=None,
) -> list[dict]:
    """Expand one realized instance into register x format JSONL records."""
    c = facts.core
    ci = facts.ci
    # The statistics describe the claim THIS INSTANCE asserts, not the core's
    # canonical claim -- see oriented_significance. Emitting canonical tails
    # beside an oriented verdict made 20% of cohort records contradict
    # themselves.
    sig = oriented_significance(facts)
    options, gold_answer = answer_key(c)
    factual_core = {
        "primitive": c.primitive,
        "events": list(facts.events_assigned),
        "vaccines": list(facts.vaccines_assigned),
    }
    if c.report_id is not None:
        factual_core["report_id"] = c.report_id

    evidence = evidence_ids(index, facts) if index is not None else None
    common = {
        "group_id": c.group_id,
        "level": c.level,
        "answer_type": c.answer_type,
        "gold_verdict": facts.gold_verdict,
        # True when the text asserts the claim's NEGATION. Negation is the
        # orientation operator for symmetric claims (decisions.md 2026-08-11), so
        # a negated instance's gold verdict is the flip of the plain one. Reported
        # per instance so the negated fraction is measurable, not implicit.
        "negated": facts.negated,
        "gold_proportion": _round(facts.gold_proportion),
        "gold_n": facts.gold_n,
        # enough to RECOMPUTE the label from the corpus without re-deriving the
        # conditioning: the counts, the family floor that gated it, and the null
        "gold_k": facts.gold_k,
        "gold_n2": facts.gold_n2,
        "gold_k2": facts.gold_k2,
        "family": c.family,
        "mode": c.mode,
        "min_n_floor": (family_floor(c.family) if c.report_id is None else None),
        "alpha": ALPHA,
        # GOLD-SIDE: the report ids the statistic was computed over. Never input.
        "evidence_ids": evidence,
        "ci": [_round(ci[0]), _round(ci[1])] if ci else None,
        "ci_width": _round(ci[1] - ci[0]) if ci else None,
        "effect_size": _round(facts.effect_size),
        "confidence_tag": facts.confidence_tag,
        # significance test on the gold value (None for report-level / insufficient)
        "p_value": _round(sig.p_value, 6),
        "significant": sig.significant,
        "sig_test": sig.test,
        # three-decision labeling (decisions.md 2026-07-28) for THIS instance's
        # asserted claim. `core_test_verdict` below is the core's canonical-
        # orientation verdict, kept as provenance -- it is deliberately allowed to
        # differ, because a refuted instance asserts the mirror of the canonical
        # claim.
        "p_claim": _round(sig.p_claim, 6),
        "p_opposite": _round(sig.p_opposite, 6),
        # the ASSERTED claim's verdict; must equal gold_verdict (asserted below)
        "test_verdict": sig.decision.verdict if sig.decision else None,
        "insufficient_subtype": sig.decision.subtype if sig.decision else None,
        # provenance: the CORE's canonical-orientation verdict, deliberately
        # allowed to differ -- a refuted instance asserts the canonical claim's
        # mirror, so its canonical verdict is the opposite one.
        "core_test_verdict": core_decision(c).verdict,
        # explicit CHOICE answer key (None for BOOL/PROP)
        "options": options,
        "gold_answer": gold_answer,
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
            text = render(group, register, fmt, facts.slot_values,
                          negated=facts.negated)
            rec = dict(common)
            rec["hypothesis_id"] = (
                f"{c.group_id}-{seq:04d}-{register}-{fmt}"
            )
            rec["register"] = register
            rec["format"] = fmt
            rec["text"] = text
            records.append(rec)
    return records
