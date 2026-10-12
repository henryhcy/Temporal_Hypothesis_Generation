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
from temporal_hypo.framework.sql.compiler import WHOLE_REPORT_MODES
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


def e2e_messages(row: Mapping[str, Any], claim: StructuredClaim, ddl: str,
                 conventions: str | None = None) -> list[dict]:
    """System + user messages carrying the SENTENCE, not the structured claim.

    ``conventions`` (cell B of the 2026-10-07 audit): the situation-phrased
    stipulations of the toolbox frame are STATED, still with no claim JSON, no
    per-mode rule, no exclusion line and no arm plan -- so the gain over the
    plain sentence-to-SQL run is the value of being told the conventions in one
    call, and the gain of the plan pipeline over this is architecture.
    """
    s = MODE_SPEC[claim.mode]
    labels = expected_labels(claim)
    if s.is_report:
        # v1.2: a claim about stage RANKS (first half of the timeline; directly
        # before) needs every stage, so the whole report is returned.
        which = ("EVERY term present in the report (the claim is about stage ranks, which "
                 "depend on all of the report's stages)" if claim.mode in WHOLE_REPORT_MODES
                 else "event term the claim names that is present in the report")
        contract = (f"Each statement returns rows with EXACTLY these columns, in this order: "
                    f"{', '.join(REPORT_COLUMNS)} -- one row per {which}, "
                    "level = its FIRST-mention level.")
    else:
        contract = (f"Each statement returns ONE ROW PER REPORT of the arm with EXACTLY these "
                    f"columns, in this order: {', '.join(ARM_COLUMNS)}. report_id INTEGER; "
                    "in_denominator / in_numerator / excluded are 0/1 integers; cell is TEXT or "
                    "NULL." "When a statement joins two copies of first_mention (or first_mention_rank), write the id as "
                    "<alias>.report_id AS report_id -- an unqualified report_id in a self-join is ambiguous "
                    "in SQLite and the statement fails.")
    reminders = [
        "The view first_mention(report_id, vaccine, term, level) ALREADY applies the first-mention "
        "rule (level = MIN(level_index) per report and term) -- join it, do not re-aggregate "
        "level_terms unless you need to.",
        "Report ids are report_id everywhere: the dataset's own pseudonymous 7-digit key, written "
        "MT-0001234 in a claim (= report_id 1234). There is no other id.",
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
        *(["CONVENTIONS OF THIS DATASET:", conventions.strip(), ""] if conventions else []),
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

    def __init__(self, *args: Any, conventions: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.conventions = conventions
        self.name = f"e2e-sql{'+conventions' if conventions else ''}:{self.model}"
        self._row: Mapping[str, Any] | None = None

    def messages_for(self, claim: StructuredClaim) -> list[dict]:
        if self._row is None:
            raise RuntimeError("E2ESQLRetriever needs the question row: call "
                               "retrieve(claim, row=...) (Pipeline does this via wants_row)")
        return e2e_messages(self._row, claim, self.ddl, conventions=self.conventions)

    def retrieve(self, claim: StructuredClaim, *, row: Mapping[str, Any] | None = None):
        # the inherited loop: executor errors + the PLAN-FREE checks (2026-10-11), the
        # repair instruction phrased on the conventions, never on a plan
        self._row = row
        try:
            return super().retrieve(claim)
        finally:
            self._row = None

    def _consistency(self, claim: StructuredClaim, ret: Any) -> list[str]:
        from temporal_hypo.framework.sql.llm_sql import generic_consistency
        return generic_consistency(claim, ret)

    def _repair_instruction(self) -> str:
        return ("Revise the statement(s): a failed statement must execute under the DDL and the "
                "row contract; the denominator must be exactly the reports the hypothesis is about "
                "under the stated conventions (present-but-unusable reports get in_denominator = 0, "
                "excluded = 1) and the numerator the subset where the asserted relation holds.")
