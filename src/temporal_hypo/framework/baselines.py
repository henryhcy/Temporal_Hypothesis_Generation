"""Trivial and shortcut baselines, emitted in the prediction-row schema.

These need no model and no retrieval; they exist so the report always shows
what a system scores with NO temporal reasoning:

- ``majority_per_group``  -- the most frequent gold verdict of each group
  (equal thirds make this ~33% on cohort groups; 50/50 report tier; C-R1 60/40).
  Uses the gold distribution of the SCORED set, which is the strongest form of
  this baseline and therefore the honest one to report.
- ``always_insufficient`` -- the cop-out.
- ``options_index(i)``    -- always pick ``options[i]`` as the CHOICE answer
  (the released F-R1/P-R2 gold is always index 0 and F-R2 index 2 -- the
  position leak the pipeline neutralises by shuffling). The response is
  ``supported`` so the verdict axis is scored as a constant guess.

The oracle baseline (rules -> compiler -> gold procedure) is not here: it is
just ``Pipeline`` with those components, see ``scripts/run_eval.py``.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping

from temporal_hypo.framework.pipeline import instance_id_of


def _row(question_row: Mapping, name: str, response: str, answer: str | None) -> dict:
    return {
        "hypothesis_id": question_row["hypothesis_id"],
        "instance_id": instance_id_of(question_row["hypothesis_id"]),
        "group_id": question_row["group_id"],
        "register": question_row["register"],
        "format": question_row["format"],
        "condition": "given-group",
        "pipeline": name,
        "model": None,
        "claim": None, "claim_problems": [], "retrieval": None,
        "prediction": {"response": response, "verdict": response, "subtype": None,
                       "p_claim": None, "p_opposite": None, "test": None,
                       "n": None, "k": None, "n2": None, "k2": None,
                       "answer": answer, "gate_reason": None, "procedure_errors": []},
        "latency_ms": 0.0, "tokens": None, "error": None,
    }


def majority_per_group(records: Iterable[Mapping], answers: Mapping[str, Mapping]) -> list[dict]:
    """Predict each group's most frequent gold verdict over the given records."""
    recs = list(records)
    counts: dict[str, Counter] = {}
    seen_inst: set[str] = set()
    for r in recs:
        iid = instance_id_of(r["hypothesis_id"])
        if iid in seen_inst:
            continue
        seen_inst.add(iid)
        counts.setdefault(r["group_id"], Counter())[answers[iid]["gold_verdict"]] += 1
    majority = {g: c.most_common(1)[0][0] for g, c in counts.items()}
    return [_row(r, "majority_per_group", majority[r["group_id"]], None) for r in recs]


def always_insufficient(records: Iterable[Mapping]) -> list[dict]:
    return [_row(r, "always_insufficient", "insufficient", None) for r in records]


def options_index(records: Iterable[Mapping], index: int) -> list[dict]:
    """Always answer ``options[index]`` (unshuffled release order) for CHOICE rows."""
    out = []
    for r in records:
        opts = r.get("options") or []
        ans = opts[index] if len(opts) > index else None
        out.append(_row(r, f"options[{index}]", "supported", ans))
    return out
