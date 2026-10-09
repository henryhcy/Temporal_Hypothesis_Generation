"""Stage 2 by prompting: a model writes the per-arm SQL instead of the compiler.

WHAT: ``LLMSQLRetriever.queries_for(claim)`` shows the model the eval-DB DDL
(``views.sql``), the row contract (``aggregate.ARM_COLUMNS`` for cohort claims,
``(term, level)`` at the report tier), the claim as JSON, the conditioning rule
prose for its mode (``pilot.RULE_BY_MODE`` / ``pilot._EXCLUSION_REASON``), the
arm plan (how many statements, their labels, what each arm is), and the
reminders that matter (first mention already applied by the view, ids are
``report_id``, ``cell`` NULL outside the denominator, what an argmax cell holds),
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
from temporal_hypo.framework.sql.compiler import WHOLE_REPORT_MODES
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


VIEW_LISTING = '''
-- VIEWS. Query them exactly like tables, with aliases YOU define (there is no
-- pre-defined alias such as lt, f or r):
--   first_mention(report_id, vaccine, term, level)
--     one row per (report_id, term): level = the term's FIRST mention in that report
--     (MIN(level_index) over the report's rows for the term); vaccine = the report's.
--   first_mention_rank(report_id, vaccine, term, level, rank, n_ranks)
--     first_mention plus rank = the number of DISTINCT first-mention levels of the
--     same report that are < level (0 = earliest stage; dense, so gaps between
--     levels do not matter) and n_ranks = the number of DISTINCT first-mention
--     levels in the report. Use it for CONSECUTIVE stages (|a.rank - b.rank| = 1)
--     and for the EARLIER HALF of a timeline (rank < (n_ranks - 1) / 2.0; a term on
--     the exact middle rank is in neither half).
--   report_terms(report_id, vaccine, level_index, terms)
--     browsing aid: one row per (report, level); the terms at that level joined by ' | '.
'''


def schema_listing(ddl: str | None = None) -> str:
    """The DDL as the model sees it under ``--ddl-style listing`` (issue 43):
    the header comments and the CREATE TABLE / INDEX statements verbatim, and the
    views as column LISTINGS with their semantics in comments -- no SELECT bodies,
    so there are no view aliases (``lt``, ``f``) to copy into a query where they
    are undefined. The schema built from ``views.sql`` is unchanged."""
    ddl = ddl if ddl is not None else load_eval_ddl()
    cut = ddl.find("\n-- First-mention position")
    if cut < 0:
        cut = ddl.find("CREATE VIEW")
    head = ddl[:cut].rstrip() if cut > 0 else ddl.rstrip()
    return head + "\n" + VIEW_LISTING


def load_eval_ddl(style: str = "definitions") -> str:
    """``build_eval_db.EVAL_DDL`` (lazy import), else ``views.sql`` next to this file.
    ``style='listing'`` returns ``schema_listing`` of it."""
    if style == "listing":
        return schema_listing(load_eval_ddl("definitions"))
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
        if claim.mode in WHOLE_REPORT_MODES:   # v1.2: rank claims need every stage
            return [{"label": "report",
                     "rows": "(term, level) -- the first-mention level of EVERY term in the one "
                             f"report report_id = {claim.report_id} (not only the claim's events "
                             f"{terms}): the claim is about stage RANKS, which depend on all of "
                             "the report's stages. One row per term present."}]
        return [{"label": "report",
                 "rows": "(term, level) -- the first-mention level of each of the claim's "
                         f"events in the one report report_id = {claim.report_id}; "
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
    if claim.mode == "adj_rate_bool":          # v1.2: ordered-pair denominator, ADJACENCY numerator
        rows = (f"reports of vaccine {v1} containing both {a} and {b} (use first_mention_rank); "
                f"in_denominator = (ranks differ); in_numerator = (|rank({a}) - rank({b})| = 1); "
                f"excluded = (same rank); cell NULL. The null (mean 2/L over the denominator) is "
                f"computed by the harness from the data; do not return it.")
    elif cond == "consecutive_pair":           # v1.2
        rows = (f"reports of vaccine {v1} containing both {a} and {b} (use first_mention_rank); "
                f"in_denominator = (|rank({a}) - rank({b})| = 1); in_numerator = (rank({a}) + 1 = "
                f"rank({b})); excluded = (ranks differ by 0 or by more than 1); cell NULL.")
    elif cond == "present_offmid":             # v1.2
        rows = (f"reports of vaccine {v1} containing {a} (use first_mention_rank: rank and "
                f"n_ranks); in_denominator = (n_ranks >= 2 AND 2*rank <> n_ranks - 1); "
                f"in_numerator = (n_ranks >= 2 AND 2*rank < n_ranks - 1); excluded = NOT "
                f"in_denominator; cell NULL. The structural early-rate null is computed by the "
                f"harness from the denominator reports; do not return it.")
    elif cond == "ordered_pair":
        rows = (f"reports of vaccine {v1} containing both {a} and {b}; in_denominator = (levels "
                f"differ); in_numerator = ({a} level < {b} level); excluded = (same level); cell NULL.")
    elif cond == "both_present" and claim.mode in ("sym_bool_cooccurs", "cooc_bar"):
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


def plan_payload(claim: StructuredClaim) -> dict:
    """The claim as a composed PLAN (cell D of the 2026-10-07 audit): the WHAT layer
    plus the plan's own fields -- no mode name, no per-mode rule, no arm rows."""
    from temporal_hypo.framework.claim_schema import derive_plan
    plan = dict(claim.plan) if claim.plan else derive_plan(claim.mode, negated=claim.negated)
    keep = ("quantity", "extreme", "arms", "denominator", "null_kind", "p0", "null_reference", "tail")
    return {
        "events": [{"role": e.role, "term": e.term} for e in claim.events],
        "cohorts": [{"vaccine": c.vaccine, "report_id": c.report_id} for c in claim.cohorts],
        "negated": claim.negated,
        "asserted_option": claim.asserted_option,
        "plan": {k: plan.get(k) for k in keep},
    }


def sql_messages(claim: StructuredClaim, ddl: str, *, frame: str = "catalogue",
                 conventions: str | None = None) -> list[dict]:
    """System + user messages asking for one statement per arm.

    ``frame="catalogue"`` (the default, every run before 2026-10-08) sends the
    claim JSON, the mode's CONDITIONING RULE, the EXCLUSION line and the ARM PLAN
    rows. ``frame="toolbox"`` sends the composed PLAN and the stated conventions
    instead: the model derives the rows from the plan's denominator primitive.
    """
    s = MODE_SPEC[claim.mode]
    plan = arm_plan(claim)
    labels = [p["label"] for p in plan]
    if s.is_report:
        which = ("EVERY term of the report" if claim.mode in WHOLE_REPORT_MODES
                 else "event term present in the report")
        contract = (f"Each statement returns rows with EXACTLY these columns, in this order: "
                    f"{', '.join(REPORT_COLUMNS)} -- one row per {which}, "
                    "level = its FIRST-mention level.")
    else:
        contract = (f"Each statement returns ONE ROW PER REPORT of the arm with EXACTLY these "
                    f"columns, in this order: {', '.join(ARM_COLUMNS)}. report_id INTEGER; "
                    "in_denominator / in_numerator / excluded are 0/1 integers; cell is TEXT or NULL.")
    reminders = [
        "The view first_mention(report_id, vaccine, term, level) ALREADY applies the first-mention "
        "rule (level = MIN(level_index) per report and term) -- join it, do not re-aggregate "
        "level_terms unless you need to.",
        "Report ids are report_id everywhere: the dataset's own pseudonymous 7-digit key, written "
        "MT-0001234 in a claim (= report_id 1234). They are not VAERS ids. There is no other id.",
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
        *(["CONVENTIONS OF THIS DATASET:", conventions.strip(), ""]
          if (frame == "toolbox" and conventions) else []),
        "ROW CONTRACT:",
        contract,
        "",
        "REMINDERS:",
        *[f"- {r}" for r in reminders],
    ])
    if frame == "toolbox":
        arm_note = ("one statement" if len(labels) == 1 else
                    "two statements: cohort_1 is the FIRST arm the claim names (the first pair, "
                    "the with-A group, or the first vaccine) and cohort_2 the second")
        user = "\n".join([
            "PLAN (JSON): the claim's events (roles A, B, ...), its cohort, and the composed plan -- "
            "the quantity measured, the denominator primitive (which reports count; see the "
            "conventions), how many arms, and the null. Derive each report's role from the plan.",
            json.dumps(plan_payload(claim), ensure_ascii=False),
            "",
            f"Return {len(labels)} {arm_note}; use exactly these labels in this order: "
            f"{', '.join(labels)}.",
            "",
            'Return {"arms": [...]} now.',
        ])
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]
    rule = RULE_BY_MODE.get(claim.mode, claim.mode)
    excl = _EXCLUSION_REASON.get(claim.mode, "")
    if not excl:
        excl = "n/a" if s.is_report or s.conditioning == "presence_split" else \
            "co-exist (same level) -- not ordered, so excluded from a PRECEDES denominator"
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
# plan consistency (cell E): checks that use the plan and the data, never the gold
# ---------------------------------------------------------------------------

_LEVEL_DENOMINATORS = ("ordered_pair", "orderable_triple", "consecutive_pair",
                       "all_present_unique_first", "all_present_unique_last")


def _arm_terms(claim: StructuredClaim) -> list[tuple]:
    t = [x for x in claim.terms if x is not None]
    if claim.mode == "antecedent_bool" and len(t) >= 3:
        return [(t[0], t[1]), (t[2], t[1])]
    if claim.mode == "pairpair_bool" and len(t) >= 4:
        return [(t[0], t[1]), (t[2], t[3])]
    if claim.mode == "multi_dir_precedes":
        return [tuple(t), tuple(t)]
    return [tuple(t)]


def _denominator_violations(executor: Any, cond: str, ev: tuple, ids: Any) -> int:
    """How many of ``ids`` fail the denominator primitive ``cond`` for events ``ev``."""
    from temporal_hypo.generation.corpus import rank_map
    ids = sorted(int(i) for i in ids)
    levels: dict[int, dict[str, int]] = {}
    for i in range(0, len(ids), 400):
        chunk = ids[i:i + 400]
        res = executor.execute(
            f"SELECT report_id, term, level FROM first_mention WHERE report_id IN ({','.join('?' * len(chunk))})",
            tuple(chunk))
        if res.error is not None:
            return 0
        for vid, term, level in res.rows:
            levels.setdefault(int(vid), {})[str(term)] = int(level)
    bad = 0
    for vid in ids:
        t = levels.get(vid, {})
        if any(e not in t for e in ev):
            bad += 1
            continue
        lv = [t[e] for e in ev]
        if cond in ("ordered_pair", "orderable_triple"):
            bad += int(len(set(lv)) < len(lv))
        elif cond == "consecutive_pair":
            ranks, _L = rank_map(t)
            bad += int(abs(ranks[ev[0]] - ranks[ev[1]]) != 1)
        elif cond == "all_present_unique_first":
            bad += int(lv.count(min(lv)) > 1)
        elif cond == "all_present_unique_last":
            bad += int(lv.count(max(lv)) > 1)
    return bad


def plan_consistency(claim: StructuredClaim, retrieval: Any, executor: Any) -> list[str]:
    """Violations of the claim's own plan by the executed arms (empty = consistent)."""
    s = MODE_SPEC[claim.mode]
    arms = list(getattr(retrieval, "arms", None) or [])
    problems: list[str] = []
    for i, a in enumerate(arms):
        if a.n and a.n == a.k:
            problems.append(f"arm {i + 1}: the denominator equals the numerator (n = k = {a.n}); "
                            "the denominator must also contain the reports where the asserted "
                            "relation does NOT hold")
    if s.arms == 2 and len(arms) == 2 and (arms[0].n == 0) != (arms[1].n == 0):
        problems.append("one arm is empty while the other is not; both arms are conditioned the "
                        "same way inside their own group")
    cond = claim.procedure.conditioning
    if cond in _LEVEL_DENOMINATORS:
        for i, (a, ev) in enumerate(zip(arms, _arm_terms(claim))):
            if not a.n or not ev:
                continue
            bad = _denominator_violations(executor, cond, ev, a.denominator_ids)
            if bad:
                what = {"consecutive_pair": "are not at consecutive ranks",
                        "all_present_unique_first": "tie for the earliest",
                        "all_present_unique_last": "tie for the latest"}.get(
                    cond, "share a first-mention level (co-exist) or lack an event")
                problems.append(f"arm {i + 1}: {bad} of the {a.n} denominator reports {what}; the "
                                f"plan's denominator ({cond}) excludes them")
    return problems


# ---------------------------------------------------------------------------
# the retriever
# ---------------------------------------------------------------------------

class LLMSQLRetriever:
    """A ``Provider`` writes the per-arm SQL; the executor runs it (module docstring)."""

    def __init__(self, client: Provider, model: str, executor: Any, *,
                 frame: str = "catalogue", conventions: str | None = None,
                 replan: bool = False, verify_rounds: int | None = None,
                 ddl: str | None = None, temperature: float = 0.0,
                 max_tokens: int = 1200) -> None:
        self.client = client
        self.model = model
        self.frame = frame
        self.conventions = conventions
        # issue 41: bounded verify-and-repair rounds at S2 (an executor error, or a
        # plan-consistency violation, each re-asked once per round). ``replan`` is the
        # one-round form used by the 10-08 cell-E runs.
        self.verify_rounds = int(verify_rounds) if verify_rounds is not None else (1 if replan else 0)
        self.replan = self.verify_rounds > 0
        self.last_rounds = 0
        self.name = (f"llm-sql{'' if frame == 'catalogue' else '@' + frame}"
                     f"{'+verify' + str(self.verify_rounds) if self.verify_rounds else ''}:{model}")
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
        return sql_messages(claim, self.ddl, frame=self.frame, conventions=self.conventions)

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
        return self._ask(claim, self.messages_for(claim))

    def _ask(self, claim: StructuredClaim, messages: list[dict]) -> list[ArmQuery]:
        """One completion over ``messages``, parsed and aligned to the arm plan."""
        want = expected_labels(claim)
        kind = MODE_SPEC[claim.mode].named_cell_kind
        try:
            c = self.client.complete(messages, schema=SQL_JSON_SCHEMA,
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
        """``framework.sql.retrieve.execute_queries`` over ``queries_for(claim)``.

        With ``replan`` (cell E of the 2026-10-07 audit) the executed arms are
        checked against the PLAN -- never against the gold -- and on a violation
        the model is asked once more with the violation named; the second
        retrieval replaces the first (both query logs are kept).
        """
        from temporal_hypo.framework.sql.retrieve import execute_queries

        messages = self.messages_for(claim)
        queries = self.queries_for(claim)
        ret = execute_queries(queries, self.executor, claim)
        self.last_rounds = 0
        if self.verify_rounds <= 0:
            return ret
        convo = list(messages)
        logs_so_far: list = []
        for rnd in range(1, self.verify_rounds + 1):
            problems = [f"statement for arm {q.label!r} failed: {q.error}"
                        for q in ret.queries if q.error]
            if not MODE_SPEC[claim.mode].is_report:
                problems += plan_consistency(claim, ret, self.executor)
            if not problems:
                break
            self.last_rounds = rnd
            self.last_notes.append(f"verify round {rnd}: " + " | ".join(problems))
            reply = json.dumps(self.last_raw, ensure_ascii=False) if self.last_raw else \
                json.dumps({"arms": [{"label": q.label, "sql": q.sql} for q in queries]})
            convo = convo + [
                {"role": "assistant", "content": reply},
                {"role": "user", "content": "\n".join([
                    "CHECK FAILED:",
                    *[f"- {x}" for x in problems],
                    "Revise the statement(s): a failed statement must execute under the DDL and the "
                    "row contract; the denominator must be exactly the reports the plan's denominator "
                    "primitive names (present-but-unusable reports get in_denominator = 0, excluded = "
                    "1) and the numerator the subset where the asserted relation holds.",
                    'Return {"arms": [...]} now.',
                ])},
            ]
            for q in ret.queries:
                q.label = f"{q.label} (pass {rnd})"
            logs_so_far += list(ret.queries)
            queries = self._ask(claim, convo)
            ret = execute_queries(queries, self.executor, claim)
        ret.queries = logs_so_far + list(ret.queries)
        return ret

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
