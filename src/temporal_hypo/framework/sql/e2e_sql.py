"""End-to-end text-to-SQL: the hypothesis SENTENCE straight to retrieval SQL.

WHAT. ``E2ESQLRetriever`` asks the model for the same per-arm statements
``llm_sql.LLMSQLRetriever`` asks for -- same DDL, same row contract, same
executor, same scorer -- but the user message carries the **question row** (the
sentence plus the visible input fields) instead of a ``StructuredClaim``. The
model is told nothing about the mode, the conditioning rule, or what each arm
should contain.

WHY. This is the baseline a practitioner would reach for before building stage
1: "why not just hand the sentence to a text-to-SQL model?" Answering it is the
evidence that the structured intermediate earns its place. The comparison is to
`rules+llm-sql` (smoke-2/smoke-4), which differs in exactly three prompt blocks:

    | prompt block            | rules+llm-sql | e2e-llm-sql |
    | claim JSON (mode, ...)  | given         | ABSENT -- the sentence instead |
    | CONDITIONING RULE prose | given         | ABSENT |
    | ARM PLAN per arm        | given         | ABSENT (labels only, see below) |

so the delta between the two runs is "does the model DERIVE the conditioning
from the claim, or only transcribe a rule it was handed".

Two deliberate choices, both of which make this measurement narrower and
therefore more interpretable:

- **Arm labels ARE given.** They are an output-format contract, like the column
  list -- the alternative is that a model returning one statement where the plan
  wanted two scores zero for a reason that has nothing to do with conditioning.
  Arm COUNT is therefore not under test here; the claim's shape is.
- **Stage 1 is gold-forced.** The claim handed in comes from the rules parser
  (exact on template text) and supplies only the output contract and the
  downstream test. So a wrong verdict here is a RETRIEVAL failure, never an
  extraction one -- the same gold-forcing that makes smoke-2/smoke-4 readable.

What the model is given is exactly what a deployed system would have: the
sentence, the tier, the answer type, the options and the cohort (all released
input fields), plus the schema and the row contract. What it must supply is the
conditioning -- which reports enter the denominator, which are the numerator,
and which are present-but-excluded.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from temporal_hypo.framework.claim_schema import MODE_SPEC, StructuredClaim
from temporal_hypo.framework.sql.aggregate import ARM_COLUMNS, ORDERING_SEP, REPORT_COLUMNS
from temporal_hypo.framework.sql.llm_sql import (
    LLMSQLRetriever,
    expected_labels,
    load_eval_ddl,
)

# Input fields the sentence is shown with. `group_id` is never included: it names
# the template family and would hand back the mode this baseline withholds.
SHOWN_FIELDS = ("level", "answer_type", "register", "format", "text", "options", "cohort")


def row_payload(row: Mapping[str, Any]) -> dict:
    return {k: row[k] for k in SHOWN_FIELDS if k in row}


def e2e_messages(row: Mapping[str, Any], claim: StructuredClaim, ddl: str) -> list[dict]:
    """System + user messages carrying the SENTENCE, not the structured claim."""
    s = MODE_SPEC[claim.mode]
    labels = expected_labels(claim)
    if s.is_report:
        contract = (f"Each statement returns rows with EXACTLY these columns, in this order: "
                    f"{', '.join(REPORT_COLUMNS)} -- one row per event term the claim names that "
                    "is present in the report, level = its FIRST-mention level.")
    else:
        contract = (f"Each statement returns ONE ROW PER REPORT of the arm with EXACTLY these "
                    f"columns, in this order: {', '.join(ARM_COLUMNS)}. vaers_id INTEGER; "
                    "in_denominator / in_numerator / excluded are 0/1 integers; cell is TEXT or "
                    "NULL.")
    reminders = [
        "The view first_mention(vaers_id, vaccine, term, level) ALREADY applies the first-mention "
        "rule (level = MIN(level_index) per report and term) -- join it, do not re-aggregate "
        "level_terms unless you need to.",
        "Report ids are vaers_id everywhere. There is no other id.",
        "Restrict to the cohort named in the input (first_mention carries vaccine).",
        "Event terms are MedDRA terms spelled exactly as they appear in the sentence.",
        "Inline every literal (single-quoted strings, '' to escape a quote). Do not use bind "
        "parameters. One SELECT (or WITH ... SELECT) per arm; no other statements.",
    ]
    if not s.is_report:
        reminders += [
            "in_denominator marks the reports the claim's statistic is computed OVER; "
            "in_numerator marks those where the asserted relation holds.",
            "A report that contains the events but CANNOT settle the claim is "
            "present-but-unusable: give it in_denominator = 0 and excluded = 1. It is scored, so "
            "decide deliberately which reports those are for THIS claim.",
            "cell MUST be NULL for every row with in_denominator = 0.",
        ]
        if s.named_cell_kind == "ordering":
            reminders.append("This claim is about which ORDERING is most common: set cell to the "
                             f"terms sorted by level, joined with '{ORDERING_SEP}'.")
        elif s.named_cell_kind == "event":
            reminders.append("This claim is about which EVENT is most common: set cell to the "
                             "winning term's exact spelling.")
        elif s.named_cell_kind == "relation":
            reminders.append("This claim is about which RELATION is most common: set cell to "
                             "exactly 'before', 'after' or 'co_exist'.")
        else:
            reminders.append("cell may be NULL for every row (this claim has no argmax table).")
        reminders.append("Never expose or read any column other than those in the DDL.")
    system = "\n".join([
        "You write SQLite SQL over a read-only database of VAERS reports annotated as leveled "
        "orders of MedDRA event terms. You are given a natural-language hypothesis about the "
        "temporal pattern of adverse events. Work out for yourself which reports the hypothesis "
        "is a claim ABOUT, then write the query (or queries) that retrieve them and flag each "
        "report's role. Answer with ONE JSON object of the form "
        '{"arms": [{"label": "<label>", "sql": "<statement>"}, ...]} and nothing else.',
        "",
        "DATABASE (DDL shown verbatim):",
        ddl.strip(),
        "",
        "ROW CONTRACT:",
        contract,
        "",
        "REMINDERS:",
        *[f"- {r}" for r in reminders],
    ])
    user = "\n".join([
        "HYPOTHESIS (the released input row):",
        json.dumps(row_payload(row), ensure_ascii=False),
        "",
        f"Return {len(labels)} statement{'s' if len(labels) != 1 else ''}, using exactly these "
        f"labels in this order: {', '.join(labels)}.",
        "",
        'Return {"arms": [...]} now.',
    ])
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


class E2ESQLRetriever(LLMSQLRetriever):
    """``LLMSQLRetriever`` with the sentence in place of the structured claim.

    Everything after the prompt is inherited unchanged -- the same JSON parsing,
    label alignment, placeholder-on-failure behaviour, executor and token
    accounting -- so the two runs differ only in what the model was told.
    """

    wants_row = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.name = f"e2e-sql:{self.model}"
        self._row: Mapping[str, Any] | None = None

    def messages_for(self, claim: StructuredClaim) -> list[dict]:
        if self._row is None:
            raise RuntimeError("E2ESQLRetriever needs the question row: call "
                               "retrieve(claim, row=...) (Pipeline does this via wants_row)")
        return e2e_messages(self._row, claim, self.ddl)

    def retrieve(self, claim: StructuredClaim, *, row: Mapping[str, Any] | None = None):
        from temporal_hypo.framework.sql.retrieve import execute_queries

        self._row = row
        try:
            return execute_queries(self.queries_for(claim), self.executor, claim)
        finally:
            self._row = None
