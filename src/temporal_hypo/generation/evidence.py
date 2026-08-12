"""Which REPORT IDS stand behind an instance's gold label.

The benchmark does not ship narratives -- the framework reads the corpus itself --
so an instance references its evidence by report id. This module recovers those ids
for a realized instance, in the ORIENTATION THE INSTANCE ASSERTS (matching
``answers.oriented_significance``), so the ids describe the claim in the record's
text rather than the core's canonical claim.

Three sets per cohort, and the third is the interesting one:

- ``denominator`` -- reports that satisfy the claim's conditioning. This is ``n``,
  the denominator the test ran on.
- ``numerator`` -- the subset that supports the asserted direction. This is ``k``.
- ``excluded`` -- reports the conditioning removes from the denominator entirely: a
  co-exist pair for a precedes claim, a non-orderable triple for a sequence claim.
  These separate "present but unusable" from "absent entirely" and are the
  report-level witness for `not_locatable`.
- ``ties`` -- first/last only, and the same reports as ``excluded`` there: kept as a
  separate key because the tie RATE is a reported diagnostic. Ties left the
  denominator on 2026-08-11; before that they were inside it, which made the gate
  pass on reports the test never sees.

**These are GOLD-SIDE fields.** The denominator ids are the answer to the hardest
part of the task -- locating ~19 relevant reports inside a ~1,000-report cohort, a
55x search -- so they must never appear in what the framework reads. See
``instances.INPUT_FIELDS``.
"""

from __future__ import annotations

from temporal_hypo.generation import corpus


def _pair_sets(index, a: str, b: str, cohort: list[int]) -> dict:
    """Precedes conditioning: ordered pairs only; co-exist is present-but-excluded."""
    denom, num, excl = [], [], []
    for vid in cohort:
        rel = corpus.relation(index.report_terms[vid], a, b)
        if rel == "missing":
            continue
        if rel == "co_exist":
            excl.append(vid)
            continue
        denom.append(vid)
        if rel == "before":
            num.append(vid)
    return {"denominator": denom, "numerator": num, "excluded": excl}


def _cooccur_sets(index, a: str, b: str, cohort: list[int]) -> dict:
    """Co-occurs conditioning: every both-present report counts."""
    denom, num = [], []
    for vid in cohort:
        rel = corpus.relation(index.report_terms[vid], a, b)
        if rel == "missing":
            continue
        denom.append(vid)
        if rel == "co_exist":
            num.append(vid)
    return {"denominator": denom, "numerator": num, "excluded": []}


def _ordering_sets(index, terms: tuple[str, ...], cohort: list[int]) -> dict:
    """Sequence conditioning: all three present AND at distinct levels."""
    denom, num, excl = [], [], []
    for vid in cohort:
        t = index.report_terms[vid]
        idxs = [t.get(x) for x in terms]
        if any(i is None for i in idxs):
            continue
        if len(set(idxs)) < len(idxs):
            excl.append(vid)          # present but not orderable
            continue
        denom.append(vid)
        if idxs == sorted(idxs):
            num.append(vid)           # matches the ASSERTED ordering
    return {"denominator": denom, "numerator": num, "excluded": excl}


def _extreme_sets(index, terms: tuple[str, ...], cohort: list[int], *,
                  named: str, last: bool) -> dict:
    """First/last conditioning: every report containing all candidates.

    A tie leaves the denominator (2026-08-11, superseding seed rule 4), exactly as a
    co-exist pair does for precedes and a non-orderable triple does for sequence:
    all four families now treat an unresolvable report the same way.
    """
    denom, num, ties = [], [], []
    for vid in cohort:
        t = index.report_terms[vid]
        idxs = [t.get(x) for x in terms]
        if any(i is None for i in idxs):
            continue
        target = max(idxs) if last else min(idxs)
        winners = [x for x, i in zip(terms, idxs) if i == target]
        if len(winners) > 1:
            ties.append(vid)          # unresolvable -> out of the denominator
            continue
        denom.append(vid)
        if winners[0] == named:
            num.append(vid)
    return {"denominator": denom, "numerator": num, "excluded": ties,
            "ties": ties}


def evidence_ids(index, facts) -> dict:
    """Report ids behind ``facts``, oriented to the claim it asserts.

    Returns ``{}`` for shapes with no id-level witness (the non-directional
    two-cohort modes). Two-cohort modes return ``cohort_1`` / ``cohort_2`` blocks.
    """
    core = facts.core
    m = core.mode
    ev = facts.events_assigned

    if core.report_id is not None:
        return {"report_id": core.report_id}

    if m in ("dir_bool", "dir_choice"):
        return _pair_sets(index, ev[0], ev[1], core.cohort_ids)
    if m == "sym_bool_cooccurs":
        return _cooccur_sets(index, ev[0], ev[1], core.cohort_ids)
    if m in ("seq_bool", "modal_choice"):
        return _ordering_sets(index, tuple(ev), core.cohort_ids)
    if m in ("first_choice", "first_bool"):
        return _extreme_sets(index, tuple(ev), core.cohort_ids,
                             named=ev[0], last=False)
    if m == "last_choice":
        return _extreme_sets(index, tuple(ev), core.cohort_ids,
                             named=ev[0], last=True)

    if m in ("multi_dir_precedes", "multi_dir_cooccurs"):
        v1, v2 = facts.vaccines_assigned
        c1, c2 = index.cohort(v1), index.cohort(v2)
        if m == "multi_dir_precedes":
            a, b = ev[0], ev[1]
            return {"cohort_1": _pair_sets(index, a, b, c1),
                    "cohort_2": _pair_sets(index, a, b, c2)}
        if m == "multi_dir_cooccurs":
            a, b = ev[0], ev[1]
            return {"cohort_1": _cooccur_sets(index, a, b, c1),
                    "cohort_2": _cooccur_sets(index, a, b, c2)}
    return {}
