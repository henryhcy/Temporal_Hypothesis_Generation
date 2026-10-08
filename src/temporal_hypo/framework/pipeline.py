"""Wire the stages into one runnable pipeline and emit prediction rows.

A ``Pipeline`` is an extractor (S1), a retriever (S2) and a procedure mode for
the oracle tail (S3). ``run_record`` turns ONE question row into ONE prediction
row in the schema ``framework.evaluate`` consumes (see ``11_model_pipeline.md``
§7 and the field list in ``PREDICTION_FIELDS``). The pipeline is gold-blind: it
sees only ``instances.INPUT_FIELDS`` and never opens the answers file.

Two optional hooks keep the baseline pipelines from needing their own runner
(both default to off, so every existing pipeline is unchanged):

- a retriever may set ``wants_row = True`` and take ``retrieve(claim, row=...)``.
  The END-TO-END text-to-SQL baseline needs the hypothesis SENTENCE, not the
  structured claim, and the claim it is handed supplies only the output contract
  (arm labels, ``cell_kind``) -- which is why that baseline is an S2 measurement
  with S1 gold-forced, not a joint one.
- ``tester`` replaces stage 3. ``run_test`` is the deterministic exact test; the
  counts-only baseline swaps in a model that must produce the verdict from the
  counts alone, which is what isolates "does it know the three-decision rule"
  from "can it retrieve".

Input conditions
----------------
``given-group`` passes the row as released; ``blind-group`` drops ``group_id``
and masks ``hypothesis_id`` (which embeds the group prefix) before the
extractor sees it. Options are shuffled under a per-row seed BEFORE any stage
reads the row, so the released ``options[0]``/``options[2]`` position leak on
the report-tier CHOICE groups cannot be exploited; the rules parser is
order-invariant by contract.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol

from temporal_hypo.framework.claim_schema import StructuredClaim, validate
from temporal_hypo.framework.run_test import Prediction, run_test
from temporal_hypo.framework.sql.retrieve import Retrieval, execute_queries

CONDITIONS = ("given-group", "blind-group")
PROCEDURE_MODES = ("honouring", "gold")

PREDICTION_FIELDS = (
    "hypothesis_id", "instance_id", "group_id", "register", "format", "condition",
    "pipeline", "model", "claim", "claim_problems", "retrieval", "prediction",
    "latency_ms", "tokens", "error", "verify",)


class Retriever(Protocol):
    name: str

    def retrieve(self, claim: StructuredClaim) -> Retrieval: ...


class CompilerRetriever:
    """The reference retriever: deterministic SQL per mode over the eval DB."""

    name = "compiler"

    def __init__(self, executor):
        self.executor = executor

    def retrieve(self, claim: StructuredClaim) -> Retrieval:
        from temporal_hypo.framework.sql.compiler import compile_sql

        return execute_queries(compile_sql(claim), self.executor, claim)


def instance_id_of(hypothesis_id: str) -> str:
    return hypothesis_id.rsplit("-", 2)[0]


def shuffle_options(row: Mapping[str, Any], seed: int) -> dict:
    """Return a copy of the row with ``options`` shuffled under a per-row seed.

    Delegates to ``evaluate.shuffle_options`` so the presented order the
    pipeline used and the order the evaluator reconstructs for the
    ``options[i]`` baselines are one and the same function.
    """
    from temporal_hypo.framework.evaluate import shuffle_options as _shuffle

    out = dict(row)
    opts = row.get("options")
    if opts:
        out["options"] = _shuffle(opts, row["hypothesis_id"], seed)
    return out


def blind_row(row: Mapping[str, Any]) -> dict:
    """The blind-group view: no ``group_id``; ``hypothesis_id`` masked."""
    out = {k: v for k, v in row.items() if k != "group_id"}
    out["hypothesis_id"] = "masked"
    return out


def _retrieval_to_dict(r: Retrieval | None, *, keep_ids: bool) -> dict | None:
    if r is None:
        return None
    arms = []
    for i, a in enumerate(r.arms):
        d = {"label": (r.queries[i].label if i < len(r.queries) else f"arm_{i}"),
             "n": a.n, "k": a.k,
             "counts": {("|".join(k) if isinstance(k, tuple) else str(k)): v
                        for k, v in a.counts.items()}}
        if keep_ids:
            d["denominator_ids"] = sorted(a.denominator_ids)
            d["numerator_ids"] = sorted(a.numerator_ids)
            d["excluded_ids"] = sorted(a.excluded_ids)
        arms.append(d)
    return {
        "ok": r.ok,
        "arms": arms,
        "levels": r.levels,
        "queries": [{"label": q.label, "sql": q.sql, "params": q.params,
                     "n_rows": q.n_rows, "ms": q.ms, "error": q.error,
                     "error_class": q.error_class} for q in r.queries],
    }


def _prediction_to_dict(p: Prediction | None) -> dict | None:
    if p is None:
        return None
    return {
        "response": p.response, "verdict": p.verdict, "subtype": p.subtype,
        "p_claim": p.p_claim, "p_opposite": p.p_opposite, "test": p.test,
        "n": p.n, "k": p.k, "n2": p.n2, "k2": p.k2, "answer": p.answer,
        "gate_reason": p.gate_reason, "procedure_errors": list(p.procedure_errors),
    }


@dataclass
class Pipeline:
    name: str
    extractor: Any                     # framework.extract.Extractor
    retriever: Retriever | None        # None => no retrieval (extraction-only runs)
    procedure_mode: str = "honouring"
    condition: str = "given-group"
    model: str | None = None
    options_seed: int = 0
    keep_ids: bool = True
    tokens_of: Callable[[Any], dict | None] | None = None   # extractor-specific token accounting
    extra_tokens: Callable[[], dict | None] | None = None   # retriever-specific token accounting
    tester: Callable[..., Prediction] | None = None         # stage 3; None => run_test

    def __post_init__(self) -> None:
        if self.condition not in CONDITIONS:
            raise ValueError(f"condition must be one of {CONDITIONS}")
        if self.procedure_mode not in PROCEDURE_MODES:
            raise ValueError(f"procedure_mode must be one of {PROCEDURE_MODES}")

    # -- one record -----------------------------------------------------------

    def run_record(self, question_row: Mapping[str, Any]) -> dict:
        t0 = time.perf_counter()
        row = shuffle_options(question_row, self.options_seed)
        visible = blind_row(row) if self.condition == "blind-group" else dict(row)
        out: dict[str, Any] = {
            "hypothesis_id": question_row["hypothesis_id"],
            "instance_id": instance_id_of(question_row["hypothesis_id"]),
            "group_id": question_row["group_id"],
            "register": question_row["register"],
            "format": question_row["format"],
            "condition": self.condition,
            "pipeline": self.name,
            "model": self.model,
            "claim": None, "claim_problems": [], "retrieval": None,
            "prediction": None, "latency_ms": 0.0, "tokens": None, "error": None,
        }
        claim = None
        retrieval = None
        pred = None
        try:
            claim = self.extractor.extract(
                visible, blind_group=(self.condition == "blind-group"))
            if claim is None:
                out["error"] = getattr(self.extractor, "last_error", None) or "no parse"
            else:
                out["claim"] = claim.to_dict()
                out["claim_problems"] = validate(claim)
                if claim.is_underdetermined:
                    pred = (self.tester or run_test)(
                        claim, None, procedure_mode=self.procedure_mode)
                elif self.retriever is not None:
                    retrieval = (self.retriever.retrieve(claim, row=visible)
                                 if getattr(self.retriever, "wants_row", False)
                                 else self.retriever.retrieve(claim))
                    test = self.tester or run_test
                    pred = test(claim, retrieval, procedure_mode=self.procedure_mode)
        except Exception as exc:  # noqa: BLE001 -- a run must survive one bad record
            out["error"] = f"{type(exc).__name__}: {exc}"
        # ids are always kept in memory (the scorer needs them); `keep_ids` only
        # decides whether they are written to predictions.jsonl (see `run`).
        out["retrieval"] = _retrieval_to_dict(retrieval, keep_ids=True)
        out["prediction"] = _prediction_to_dict(pred)
        # issue 41: verify-and-repair rounds actually used at S1 and S2 (0 = none)
        out["verify"] = {"s1_rounds": int(getattr(self.extractor, "last_rounds", 0) or 0),
                         "s2_rounds": int(getattr(self.retriever, "last_rounds", 0) or 0),
                         "s1_notes": [n for n in (getattr(self.extractor, "last_notes", None) or [])
                                      if str(n).startswith("verify")],
                         "s2_notes": [n for n in (getattr(self.retriever, "last_notes", None) or [])
                                      if str(n).startswith("verify")]}
        tokens = None
        if self.tokens_of is not None:
            tokens = self.tokens_of(self.extractor)
        if self.extra_tokens is not None:
            more = self.extra_tokens()
            if more:
                tokens = {k: (tokens or {}).get(k, 0) + v for k, v in more.items()} \
                    if tokens else more
        out["tokens"] = tokens
        out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        return out

    # -- many records ---------------------------------------------------------

    def run(self, records: Iterable[Mapping[str, Any]], *,
            out_path: Path | None = None,
            progress: Callable[[int, dict], None] | None = None) -> list[dict]:
        """Run every record; optionally stream rows to ``out_path`` as JSONL."""
        rows: list[dict] = []
        fh = None
        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            fh = open(out_path, "w", encoding="utf-8")
        try:
            for i, rec in enumerate(records):
                row = self.run_record(rec)
                rows.append(row)
                if fh is not None:
                    fh.write(json.dumps(row if self.keep_ids else strip_ids(row),
                                        ensure_ascii=False) + "\n")
                    fh.flush()
                if progress is not None:
                    progress(i, row)
        finally:
            if fh is not None:
                fh.close()
        return rows


def strip_ids(row: Mapping[str, Any]) -> dict:
    """A copy of a prediction row without the per-arm report-id lists (compact JSONL)."""
    out = dict(row)
    r = row.get("retrieval")
    if r:
        r = dict(r)
        r["arms"] = [{k: v for k, v in a.items() if not k.endswith("_ids")} for a in r.get("arms", [])]
        out["retrieval"] = r
    return out


def load_predictions(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
