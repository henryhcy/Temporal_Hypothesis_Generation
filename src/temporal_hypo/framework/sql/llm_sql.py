"""Stage 2 by prompting: a model writes the per-arm SQL instead of the compiler.

WHAT: ``LLMSQLRetriever.queries_for(claim)`` shows the model the eval-DB DDL
(``views.sql``), the row contract (``aggregate.ARM_COLUMNS`` for cohort claims,
``(term, level)`` at the report tier), the claim as JSON, the conditioning rule
prose for its mode (``pilot.RULE_BY_MODE`` / ``pilot._EXCLUSION_REASON``), the
arm plan (how many statements, their labels, what each arm is), and the
reminders that matter (first mention already applied by the view, ids are
``vaers_id``, ``cell`` NULL outside the denominator, what an argmax cell holds),
and asks for ``{"arms": [{"label", "sql"}]}``. ``retrieve(claim)`` executes them
through the read-only executor via ``framework.sql.retrieve.execute_queries`` so
the model's rows flow into the same ``aggregate`` as the reference compiler's.

WHY: this is the "LLM text-to-SQL" S2 method of plan 11 §5 -- the capability
under test is whether a model can realise the family's conditioning rule
(co-exist excluded for precedes, ties dropped for first/last, ...) as SQL. The
retriever therefore does NOT post-process the SQL: the model inlines its own
literals (``params`` is always ``{}``), and a wrong or malformed statement is
executed as written so the failure lands in the right class
(``sql_error`` / ``contract_violation`` / ``empty_result`` / ``timeout``).

The DDL default is resolved lazily from ``build_eval_db.EVAL_DDL`` (another
module of this harness) so this module imports even before that one exists;
pass ``ddl=`` to override.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from temporal_hypo.framework.claim_schema import MODE_SPEC, StructuredClaim
from temporal_hypo.framework.extract.llm_client import Completion, Provider, parse_json_object
from temporal_hypo.framework.sql.aggregate import ARM_COLUMNS, ORDERING_SEP, REPORT_COLUMNS
from temporal_hypo.generation.pilot import RULE_BY_MODE, _EXCLUSION_REASON

try:  # the reference compiler owns ArmQuery; fall back to the same shape if it is not built yet
    from temporal_hypo.framework.sql.compiler import ArmQuery
except ImportError:  # pragma: no cover - only before compiler.py lands
    @dataclass
    class ArmQuery:  # type: ignore[no-redef]
        label: str
        sql: str
        params: dict
        cell_kind: str | None


_VIEWS_SQL = Path(__file__).with_name("views.sql")

SQL_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "arms": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {"label": {"type": "string"}, "sql": {"type": "string"}},
                "required": ["label", "sql"],
            },
        },
    },
    "required": ["arms"],
}


def load_eval_ddl() -> str:
    """``build_eval_db.EVAL_DDL`` (lazy import), else ``views.sql`` next to this file."""
    try:
        mod = importlib.import_module("temporal_hypo.framework.sql.build_eval_db")
        ddl = getattr(mod, "EVAL_DDL", None)
        if isinstance(ddl, str) and ddl.strip():
            return ddl
    except ImportError:
        pass
    if _VIEWS_SQL.exists():
        return _VIEWS_SQL.read_text(encoding="utf-8")
    raise RuntimeError("eval DDL unavailable: neither framework.sql.build_eval_db.EVAL_DDL "
                       f"nor {_VIEWS_SQL} exists; pass ddl= explicitly")


# ---------------------------------------------------------------------------
# the arm plan (what each statement must return)
# ---------------------------------------------------------------------------

def expected_labels(claim: StructuredClaim) -> list[str]:
    """``["report"]`` | ``["arm"]`` | ``["cohort_1", "cohort_2"]`` -- the compiler's labels."""
    s = MODE_SPEC[claim.mode]
    if s.is_report:
        return ["report"]
    if s.arms == 2:
        return ["cohort_1", "cohort_2"]
    return ["arm"]


def _q(term: str | None) -> str:
    """A term as a SQL string literal for the prose ('?' when the slot is unknown)."""
    return "?" if term is None else "'" + str(term).replace("'", "''") + "'"


def arm_plan(claim: StructuredClaim) -> list[dict]:
    """One entry per statement: label + what its rows must describe."""
    s = MODE_SPEC[claim.mode]
    t = list(claim.terms) + [None] * 4
    a, b, c, d = (_q(x) for x in t[:4])
    vax = claim.vaccines
    v1 = f"'{vax[0]}'" if len(vax) > 0 else "?"
    v2 = f"'{vax[1]}'" if len(vax) > 1 else "?"
    if s.is_report:
        terms = ", ".join(_q(x) for x in claim.terms)
        return [{"label": "report",
                 "rows": "(term, level) -- the first-mention level of each of the claim's "
                         f"events in the one report vaers_id = {claim.report_id}; "
                         f"terms: {terms}. One row per event present; absent events simply "
                         "produce no row."}]
    if claim.mode == "antecedent_bool":
        return [
            {"label": "cohort_1", "rows": f"ordered pair ({a}, {b}) over vaccine {v1}: reports "
                                          f"containing both; denominator = distinct first-mention "
                                          f"levels; numerator = {a} before {b}; excluded = same level."},
            {"label": "cohort_2", "rows": f"ordered pair ({c}, {b}) over vaccine {v1}: same rule; "
                                          f"numerator = {c} before {b}."},
        ]
    if claim.mode == "pairpair_bool":
        return [
            {"label": "cohort_1", "rows": f"ordered pair ({a}, {b}) over vaccine {v1}; numerator = "
                                          f"{a} before {b}; co-existing pairs excluded."},
            {"label": "cohort_2", "rows": f"ordered pair ({c}, {d}) over vaccine {v1}; numerator = "
                                          f"{c} before {d}; co-existing pairs excluded."},
        ]
    if claim.mode == "assoc_bool":
        return [
            {"label": "cohort_1", "rows": f"every vaccine-{v1} report that CONTAINS {a}: "
                                          f"in_denominator = 1, in_numerator = (contains {b}), "
                                          "excluded = 0, cell NULL."},
            {"label": "cohort_2", "rows": f"every vaccine-{v1} report that does NOT contain {a}: "
                                          f"in_denominator = 1, in_numerator = (contains {b}), "
                                          "excluded = 0, cell NULL."},
        ]
    if claim.mode == "multi_dir_precedes":
        return [
            {"label": "cohort_1", "rows": f"ordered pair ({a}, {b}) over vaccine {v1}; numerator = "
                                          f"{a} before {b}; co-existing pairs excluded."},
            {"label": "cohort_2", "rows": f"the same ordered pair ({a}, {b}) over vaccine {v2}."},
        ]
    # single arm
    cond = s.conditioning
    if cond == "ordered_pair":
        rows = (f"reports of vaccine {v1} containing both {a} and {b}; in_denominator = (levels "
                f"differ); in_numerator = ({a} level < {b} level); excluded = (same level); cell NULL.")
    elif cond == "both_present" and claim.mode == "sym_bool_cooccurs":
        rows = (f"reports of vaccine {v1} containing both {a} and {b}; in_denominator = 1 for all; "
                f"in_numerator = (same level, i.e. co-exist); excluded = 0; cell NULL.")
    elif cond == "both_present":   # cooc_modal_bool
        rows = (f"reports of vaccine {v1} containing both {a} and {b}; in_denominator = 1 for all; "
                f"in_numerator = (same level); excluded = 0; cell = 'before' when {a} is earlier, "
                f"'after' when later, 'co_exist' when at the same level.")
    elif cond == "orderable_triple":
        rows = (f"reports of vaccine {v1} containing all of {a}, {b}, {c}; in_denominator = (the "
                f"three levels are pairwise distinct); in_numerator = ({a} < {b} < {c}); excluded = "
                f"NOT in_denominator; cell = the three TERMS sorted by level, joined with "
                f"'{ORDERING_SEP}' (e.g. {a} || '{ORDERING_SEP}' || {b} || '{ORDERING_SEP}' || {c} "
                f"when {a} < {b} < {c}), NULL when not orderable.")
    elif cond == "all_present_unique_first":
        rows = (f"reports of vaccine {v1} containing all of {a}, {b}, {c}; let m = MIN of the three "
                f"levels and w = how many of the three equal m; in_denominator = (w = 1); "
                f"in_numerator = (w = 1 AND {a} level = m); excluded = (w > 1); cell = the winning "
                f"term ({a}, {b} or {c}) when w = 1, NULL otherwise.")
    elif cond == "all_present_unique_last":
        rows = (f"reports of vaccine {v1} containing all of {a}, {b}, {c}; let m = MAX of the three "
                f"levels and w = how many equal m; in_denominator = (w = 1); in_numerator = (w = 1 "
                f"AND {a} level = m); excluded = (w > 1); cell = the winning term when w = 1, "
                f"NULL otherwise.")
    else:  # pragma: no cover - every cohort conditioning is handled above
        rows = f"conditioning {cond}"
    return [{"label": "arm", "rows": rows}]


def claim_payload(claim: StructuredClaim) -> dict:
    """The claim as the model sees it (WHAT layer + the conditioning it implies)."""
    s = MODE_SPEC[claim.mode]
    return {
        "mode": claim.mode,
        "tier": s.tier,
        "family": s.family,
        "events": [{"role": e.role, "term": e.term} for e in claim.events],
        "cohorts": [{"vaccine": c.vaccine, "report_id": c.report_id} for c in claim.cohorts],
        "negated": claim.negated,
        "asserted_option": claim.asserted_option,
        "conditioning": claim.procedure.conditioning,
        "arms": claim.procedure.arms,
        "named_cell_kind": s.named_cell_kind,
    }


def sql_messages(claim: StructuredClaim, ddl: str) -> list[dict]:
    """System + user messages asking for one statement per arm."""
    s = MODE_SPEC[claim.mode]
    plan = arm_plan(claim)
    labels = [p["label"] for p in plan]
    if s.is_report:
        contract = (f"Each statement returns rows with EXACTLY these columns, in this order: "
                    f"{', '.join(REPORT_COLUMNS)} -- one row per event term present in the report, "
                    "level = its FIRST-mention level.")
    else:
        contract = (f"Each statement returns ONE ROW PER REPORT of the arm with EXACTLY these "
                    f"columns, in this order: {', '.join(ARM_COLUMNS)}. vaers_id INTEGER; "
                    "in_denominator / in_numerator / excluded are 0/1 integers; cell is TEXT or NULL.")
    reminders = [
        "The view first_mention(vaers_id, vaccine, term, level) ALREADY applies the first-mention "
        "rule (level = MIN(level_index) per report and term) -- join it, do not re-aggregate "
        "level_terms unless you need to.",
        "Report ids are vaers_id everywhere (the release's report ids). There is no other id.",
        "Restrict to the cohort: vaccine = '<name>' (first_mention carries vaccine).",
        "Inline every literal (single-quoted strings, '' to escape a quote). Do not use bind "
        "parameters. One SELECT (or WITH ... SELECT) per arm; no other statements.",
    ]
    if not s.is_report:
        reminders += [
            "Reports that fail the conditioning but are present-but-unusable (co-existing pair for "
            "a precedes claim, non-orderable triple, tie for first/last) MUST appear with "
            "in_denominator = 0 and excluded = 1 -- they are scored.",
            "cell MUST be NULL for every row with in_denominator = 0.",
        ]
        if s.named_cell_kind == "ordering":
            reminders.append(f"cell (argmax mode): the three terms sorted by level, joined with "
                             f"'{ORDERING_SEP}', using the exact term spelling.")
        elif s.named_cell_kind == "event":
            reminders.append("cell (argmax mode): the winning term's exact spelling.")
        elif s.named_cell_kind == "relation":
            reminders.append("cell (argmax mode): exactly 'before', 'after' or 'co_exist'.")
        else:
            reminders.append("cell may be NULL for every row (this mode has no argmax table).")
        reminders.append("Never expose or read any column other than those in the DDL.")
    rule = RULE_BY_MODE.get(claim.mode, claim.mode)
    excl = _EXCLUSION_REASON.get(claim.mode, "")
    if not excl:
        excl = "n/a" if s.is_report or s.conditioning == "presence_split" else \
            "co-exist (same level) -- not ordered, so excluded from a PRECEDES denominator"
    system = "\n".join([
        "You write SQLite SQL over a read-only database of VAERS reports annotated as leveled "
        "orders of MedDRA event terms. Given a structured temporal claim, write the query (or "
        "queries) that retrieve the reports the claim's statistic is computed over, one statement "
        "per arm, flagging each report's role. Answer with ONE JSON object of the form "
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
        "CLAIM (JSON):",
        json.dumps(claim_payload(claim), ensure_ascii=False),
        "",
        f"CONDITIONING RULE for mode {claim.mode}: {rule}",
        f"EXCLUSION (present-but-unusable reports): {excl}",
        "",
        f"ARM PLAN ({len(plan)} statement{'s' if len(plan) != 1 else ''}; use exactly these "
        f"labels in this order: {', '.join(labels)}):",
        *[f"- {p['label']}: {p['rows']}" for p in plan],
        "",
        'Return {"arms": [...]} now.',
    ])
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# ---------------------------------------------------------------------------
# the retriever
# ---------------------------------------------------------------------------

class LLMSQLRetriever:
    """A ``Provider`` writes the per-arm SQL; the executor runs it (module docstring)."""

    def __init__(self, client: Provider, model: str, executor: Any, *,
                 ddl: str | None = None, temperature: float = 0.0,
                 max_tokens: int = 1200) -> None:
        self.client = client
        self.model = model
        self.name = f"llm-sql:{model}"
        self.executor = executor
        self._ddl = ddl
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self.last_error: str | None = None
        self.last_completions: list[Completion] = []
        self.last_raw: dict | None = None
        self.last_notes: list[str] = []

    @property
    def ddl(self) -> str:
        if self._ddl is None:
            self._ddl = load_eval_ddl()
        return self._ddl

    def messages_for(self, claim: StructuredClaim) -> list[dict]:
        return sql_messages(claim, self.ddl)

    def _placeholder_queries(self, claim: StructuredClaim, reason: str) -> list[ArmQuery]:
        """One non-executable statement per planned arm so the failure is logged per arm."""
        kind = MODE_SPEC[claim.mode].named_cell_kind
        return [ArmQuery(label=lbl, sql=f"-- no SQL produced: {reason}", params={}, cell_kind=kind)
                for lbl in expected_labels(claim)]

    def queries_for(self, claim: StructuredClaim) -> list[ArmQuery]:
        """Ask once, parse ``{"arms": [...]}``, align labels to the arm plan.

        Never raises: on any failure the planned arms come back with a
        non-executable placeholder statement and ``last_error`` is set, so the
        executor logs a ``not_select`` failure per arm instead of the pipeline
        skipping the row.
        """
        self.last_error = None
        self.last_completions = []
        self.last_raw = None
        self.last_notes = []
        want = expected_labels(claim)
        kind = MODE_SPEC[claim.mode].named_cell_kind
        try:
            c = self.client.complete(self.messages_for(claim), schema=SQL_JSON_SCHEMA,
                                     model=self.model, temperature=self.temperature,
                                     max_tokens=self.max_tokens)
            self.last_completions.append(c)
            raw = parse_json_object(c.text)
            self.last_raw = raw
            arms = raw.get("arms")
            if not isinstance(arms, list) or not arms:
                raise ValueError("reply has no non-empty 'arms' list")
            got: list[tuple[str, str]] = []
            for i, arm in enumerate(arms):
                if not isinstance(arm, Mapping) or not isinstance(arm.get("sql"), str):
                    raise ValueError(f"arm {i} is not an object with a string 'sql'")
                got.append((str(arm.get("label") or f"arm_{i + 1}"), arm["sql"].strip()))
        except Exception as exc:  # noqa: BLE001 - provider/parse failures are logged, not raised
            self.last_error = f"{type(exc).__name__}: {exc}"
            return self._placeholder_queries(claim, self.last_error)

        by_label = {lbl: sql for lbl, sql in got}
        if set(by_label) == set(want) and len(got) == len(want):
            ordered = [(lbl, by_label[lbl]) for lbl in want]           # model used our labels
        else:
            self.last_notes.append(f"labels {[l for l, _ in got]} != plan {want}; aligned by position")
            ordered = [(want[i], sql) for i, (_lbl, sql) in enumerate(got[:len(want)])]
            for i in range(len(ordered), len(want)):                   # too few statements
                ordered.append((want[i], f"-- no SQL produced for {want[i]}"))
                self.last_notes.append(f"missing statement for {want[i]}")
            if len(got) > len(want):
                self.last_notes.append(f"{len(got) - len(want)} extra statement(s) dropped")
        return [ArmQuery(label=lbl, sql=sql, params={}, cell_kind=kind) for lbl, sql in ordered]

    def retrieve(self, claim: StructuredClaim):
        """``framework.sql.retrieve.execute_queries`` over ``queries_for(claim)``."""
        from temporal_hypo.framework.sql.retrieve import execute_queries

        return execute_queries(self.queries_for(claim), self.executor, claim)

    # -- accounting ----------------------------------------------------------

    @property
    def last_usage(self) -> dict | None:
        if not self.last_completions:
            return None
        p = [c.prompt_tokens for c in self.last_completions]
        k = [c.completion_tokens for c in self.last_completions]
        if any(x is None for x in p) or any(x is None for x in k):
            return None
        return {"prompt": sum(p), "completion": sum(k)}

    @property
    def last_tokens(self) -> dict | None:
        """Alias of ``last_usage`` in the prediction row's ``tokens`` shape."""
        return self.last_usage

    @property
    def last_ms(self) -> float:
        return sum(c.ms for c in self.last_completions)
