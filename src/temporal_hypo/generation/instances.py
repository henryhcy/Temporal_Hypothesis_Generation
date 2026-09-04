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
from temporal_hypo.generation.positional import positional_stats
from temporal_hypo.generation.templates import FORMATS, REGISTERS, Group, render


def core_id(facts: InstanceFacts) -> str:
    """Stable identifier for the underlying factual core (pre-orientation)."""
    c = facts.core
    ev = "+".join(c.events)
    vx = "+".join(c.vaccines) if c.vaccines else (f"R{c.report_id}")
    return f"{c.group_id}|{vx}|{ev}"


# Group-INDEPENDENT identity of the underlying fact (issue 14, decisions.md
# 2026-08-14). Answer-format twins (P-V1/P-V3, S-V1/S-V3, F-V1/F-V3) compute the
# identical statistic on identical cores under different group_ids, so a split
# keyed on `derived_from_core_id` -- which embeds the group -- would put the same
# fact on both sides. The later train/dev/test split MUST group by `fact_id`,
# and power/coverage claims must count DISTINCT fact_ids, not instances.
# C-V1 and C-V3 stopped being twins with the 08-14 argmax change, so they
# correctly map to different statistics here.
_STAT_BY_MODE = {
    "dir_bool": "precedes", "dir_choice": "precedes",
    "sym_bool_cooccurs": "cooc_majority",
    "cooc_modal_bool": "cooc_modal",
    "seq_bool": "seq_modal", "modal_choice": "seq_modal",
    "first_choice": "first_modal", "first_bool": "first_modal",
    "last_choice": "last_modal",
    "multi_dir_precedes": "precedes_2cohort",
    "antecedent_bool": "antecedent",
    "pairpair_bool": "pairpair",
    "assoc_bool": "assoc",
    "rep_dir_bool": "rep_precedes", "rep_dir_choice": "rep_precedes",
    "rep_sym_bool": "rep_cooc",
    "rep_seq_bool": "rep_seq",
    "rep_first_choice": "rep_first", "rep_first_bool": "rep_first",
    "rep_last_choice": "rep_last",
}


def fact_id(facts: InstanceFacts) -> str:
    """Group-independent identity: same statistic + cohort + events = same fact.

    Events are SORTED so the id is invariant under orientation and level order;
    which side of a fact an instance asserts is orientation, not identity.
    """
    c = facts.core
    ev = "+".join(sorted(c.events))
    vx = "+".join(c.vaccines) if c.vaccines else (f"R{c.report_id}")
    return f"{_STAT_BY_MODE[c.mode]}|{vx}|{ev}"


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
        # descriptive rank statistics (2026-08-14): NEVER a verdict driver --
        # the block says so itself via role=descriptive_only and its `method`
        "positional": positional_stats(index, facts) if index is not None else None,
        "ci": [_round(ci[0]), _round(ci[1])] if ci else None,
        "effect_size": _round(facts.effect_size),
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
        # the ASSERTED claim's verdict; must equal gold_verdict (asserted below).
        # Issue 25 fixed 2026-09-04: the report tier is now oriented too (v1
        # carried the CANONICAL verdict there on 1,800 mirrored refuted rows).
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
        # the split key and the honest supply-counting key (issue 14)
        "fact_id": fact_id(facts),
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
