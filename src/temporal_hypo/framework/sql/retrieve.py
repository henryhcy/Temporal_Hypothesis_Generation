"""Run Stage-2 queries through the sandbox and aggregate them into a ``Retrieval``.

WHAT. ``execute_queries(queries, executor, claim)`` runs every ``ArmQuery``
through the ``ReadOnlyExecutor``, checks each result against the row contract
of the claim's tier (``aggregate.ARM_COLUMNS`` for a cohort arm,
``REPORT_COLUMNS`` at the report tier), aggregates arm rows with
``aggregate(rows, cell_kind=q.cell_kind)`` and report rows with
``report_levels``, and returns a ``Retrieval``: the per-arm ``ArmCounts``
(aligned by index with ``queries`` -- arm 1 then arm 2 in the claim's asserted
order), the report's first-mention ``levels`` (None on the cohort tiers), one
``QueryLog`` per statement, and ``ok``.

WHY one runner: the reference compiler and a model's text-to-SQL both produce
``ArmQuery`` lists, so they share execution, contract checking and aggregation;
the only thing that differs between retrieval methods is the SQL text, which is
what the evaluation wants to isolate.

Failure policy -- nothing raises, everything is recorded, because a model's bad
query is a measurement:

- an executor failure keeps the executor's ``error_class`` (``not_select``,
  ``multi_statement``, ``denied``, ``timeout``, ``sql_error``);
- a result whose columns are not exactly the contract's (case-insensitive,
  same order), or whose rows do not coerce (``vaers_id`` not an integer, wrong
  width, non-integer level), is a ``contract_violation``;
- a result cut off at the executor's row cap is a ``row_cap`` failure -- an
  aggregate over a truncated result would be silently wrong;
- an exception escaping the executor itself (e.g. it was closed) is an
  ``executor_error``;
- an arm the mode needs that no query covered is padded with an empty
  ``ArmCounts`` and a ``missing_arm`` log entry, so ``arms[0]`` / ``arms[1]``
  always exist for a cohort claim.

A failed cohort arm contributes an EMPTY ``ArmCounts`` (n = k = 0, no ids); a
failed report query leaves ``levels`` empty; ``ok`` is False whenever any query
failed, an arm is missing, or there were no queries at all. An empty result set
is NOT a failure: zero rows is exactly how a not_locatable claim looks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from temporal_hypo.framework.claim_schema import MODE_SPEC
from temporal_hypo.framework.sql.aggregate import (
    ARM_COLUMNS,
    REPORT_COLUMNS,
    ArmCounts,
    aggregate,
    report_levels,
    rows_from_records,
)
from temporal_hypo.framework.sql.compiler import ArmQuery, labels_for
from temporal_hypo.framework.sql.executor import ExecResult, ReadOnlyExecutor

# Error classes this module adds to the executor's ERROR_CLASSES.
CONTRACT_VIOLATION = "contract_violation"
ROW_CAP = "row_cap"
EXECUTOR_ERROR = "executor_error"
MISSING_ARM = "missing_arm"
RETRIEVAL_ERROR_CLASSES = (CONTRACT_VIOLATION, ROW_CAP, EXECUTOR_ERROR, MISSING_ARM)


@dataclass
class QueryLog:
    """What one statement did: the text, its bindings, and how it ended."""

    label: str
    sql: str
    params: dict
    n_rows: int
    ms: float
    error: str | None = None
    error_class: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class Retrieval:
    """Stage-2 output for one claim (module docstring for the alignment rules)."""

    arms: list[ArmCounts]
    levels: dict[str, int] | None
    queries: list[QueryLog]
    ok: bool

    @property
    def failures(self) -> list[QueryLog]:
        return [q for q in self.queries if q.error is not None]


def empty_arm() -> ArmCounts:
    """The ArmCounts of an arm that retrieved nothing (a failed or missing query)."""
    return ArmCounts(n=0, k=0, denominator_ids=set(), numerator_ids=set(),
                     excluded_ids=set(), counts={}, n_rows=0)


def columns_violation(columns: Sequence[str], want: Sequence[str]) -> str | None:
    """None when ``columns`` equal the contract (case-insensitive, same order), else the reason."""
    got = [str(c).lower() for c in columns]
    if got != [w.lower() for w in want]:
        return f"result columns {list(columns)!r} != contract {list(want)!r}"
    return None


# ---------------------------------------------------------------------------
# the runner
# ---------------------------------------------------------------------------

def _loggable_params(params: Any) -> dict:
    if params is None:
        return {}
    if isinstance(params, Mapping):
        return dict(params)
    return {"positional": list(params)}


def _execute_one(executor: ReadOnlyExecutor, q: ArmQuery) -> tuple[QueryLog, ExecResult | None]:
    """Run one statement; the result is None when the log already records a failure."""
    params = q.params if q.params is not None else {}
    try:
        res = executor.execute(q.sql, params)
    except Exception as exc:  # noqa: BLE001 -- the runner must never raise on a bad query
        return QueryLog(q.label, q.sql, _loggable_params(params), 0, 0.0,
                        f"{type(exc).__name__}: {exc}", EXECUTOR_ERROR), None
    log = QueryLog(q.label, q.sql, _loggable_params(params), n_rows=len(res.rows),
                   ms=float(res.ms), error=res.error, error_class=res.error_class)
    if res.error is not None:
        return log, None
    if res.truncated:
        log.error = (f"result truncated at the executor's row cap ({len(res.rows)} rows kept); "
                     "not aggregated")
        log.error_class = ROW_CAP
        return log, None
    return log, res


def _fail(log: QueryLog, error: str, error_class: str = CONTRACT_VIOLATION) -> None:
    log.error = error
    log.error_class = error_class


def _missing(label: str) -> QueryLog:
    return QueryLog(label, "", {}, 0, 0.0, f"no query supplied for arm {label!r}", MISSING_ARM)


def execute_queries(queries: Sequence[ArmQuery], executor: ReadOnlyExecutor, claim: Any) -> Retrieval:
    """Execute, contract-check and aggregate ``queries`` for ``claim`` (module docstring).

    ``claim`` decides the tier and therefore the contract every statement is
    held to: at the report tier all rows are ``(term, level)`` and are merged
    into ``levels`` (earliest level wins if a term repeats); on the cohort tiers
    each statement is one arm returning ``ARM_COLUMNS``. ``arms[i]`` always comes
    from ``queries[i]``; arms the mode needs beyond the supplied statements are
    padded with ``empty_arm()`` and a ``missing_arm`` log.
    """
    spec = MODE_SPEC.get(getattr(claim, "mode", None))
    is_report = spec.is_report if spec is not None else False
    arms: list[ArmCounts] = []
    logs: list[QueryLog] = []
    levels: dict[str, int] | None = {} if is_report else None
    ok = bool(queries)

    for q in queries:
        log, res = _execute_one(executor, q)
        logs.append(log)
        if res is None:
            ok = False
            if not is_report:
                arms.append(empty_arm())
            continue

        if is_report:
            problem = columns_violation(res.columns, REPORT_COLUMNS)
            if problem is None:
                try:
                    found = report_levels(res.rows)
                except (TypeError, ValueError) as exc:
                    problem = f"report rows do not fit {REPORT_COLUMNS}: {exc}"
            if problem is not None:
                _fail(log, problem)
                ok = False
                continue
            assert levels is not None
            for term, level in found.items():
                if term not in levels or level < levels[term]:
                    levels[term] = level
            continue

        problem = columns_violation(res.columns, ARM_COLUMNS)
        if problem is None:
            try:
                rows = rows_from_records(res.rows)
            except ValueError as exc:
                problem = f"arm rows do not fit {ARM_COLUMNS}: {exc}"
        if problem is not None:
            _fail(log, problem)
            ok = False
            arms.append(empty_arm())
            continue
        arms.append(aggregate(rows, cell_kind=q.cell_kind))

    # Pad the arms the mode needs but no statement covered.
    if spec is not None:
        want = labels_for(claim)
        if is_report:
            if not queries:
                logs.append(_missing(want[0]))
                ok = False
        else:
            while len(arms) < len(want):
                logs.append(_missing(want[len(arms)]))
                arms.append(empty_arm())
                ok = False

    return Retrieval(arms=arms, levels=levels, queries=logs, ok=ok)
