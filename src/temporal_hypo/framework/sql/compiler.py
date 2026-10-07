"""Reference SQL per mode -- Stage 2's deterministic retrieval and its upper bound.

WHAT. ``compile_sql(claim)`` turns a ``StructuredClaim`` into the ``ArmQuery``
list Stage 2 executes: one statement per arm, each returning exactly
``aggregate.ARM_COLUMNS`` -- ``(vaers_id, in_denominator, in_numerator,
excluded, cell)`` -- over the eval DB's ``first_mention`` view; at the report
tier, one statement returning ``(term, level)`` for the claim's events in the one
report. Everything the claim supplies (terms, vaccine, report id) is bound as a
named parameter (``:a``, ``:b``, ``:c``, ``:d``, ``:vax``, ``:r``); the SQL text
itself depends only on the mode, so a query log reads as "this template, these
bindings".

WHY. The compiler is the retrieval upper bound of plan 11 s5. It encodes each
family's conditioning rule -- co-exist EXCLUDED from a precedes denominator,
co-exist as the numerator (or a cell) for co-occurs, three pairwise-distinct
levels for sequence, a unique extreme for first/last with ties dropped, the whole
cohort split on presence for association -- exactly as
``generation.evidence.evidence_ids`` does in Python, so its id sets equal the
release's ``evidence_ids`` (asserted on the synthetic corpus for every mode and
release-wide in the slow test). Model-written SQL is scored against the same
rows, so this module is also the worked answer to the text-to-SQL task.

Conventions shared with ``aggregate``:

- a term's position is its FIRST mention; ``first_mention`` already applies
  ``MIN(level_index)``, so no query here touches ``level_terms``;
- ``cell`` is NULL for every row with ``in_denominator = 0`` and non-NULL for
  every denominator row of an argmax mode (so ``sum(counts) == n``): an ordering
  label ``A|B|C`` of the TERMS sorted by level (``aggregate.ORDERING_SEP``), the
  winning term for first/last, ``before``/``after``/``co_exist`` for C-V3;
- two-arm labels are ``cohort_1`` / ``cohort_2`` in the claim's ASSERTED order:
  antecedent (A,B) then (C,B); pairpair (A,B) then (C,D); multi the same pair
  over vaccine v1 then v2; assoc reports WITH A then WITHOUT A;
- the mode's spec (``MODE_SPEC``) decides the conditioning, not the claim's own
  ``procedure`` -- this is the REFERENCE retrieval; a claim whose HOW layer names
  the wrong conditioning is scored by ``claim_schema.validate``, not here.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from temporal_hypo.framework.claim_schema import MODE_SPEC, StructuredClaim
from temporal_hypo.framework.sql.aggregate import ORDERING_SEP

# Labels the retrieval runner and the evaluation key on.
ARM_LABEL = "arm"
TWO_ARM_LABELS = ("cohort_1", "cohort_2")
REPORT_LABEL = "report"

# Bind-parameter names for the event slots A, B, C, D (in the claim's asserted order).
TERM_PARAMS = ("a", "b", "c", "d")


@dataclass
class ArmQuery:
    """One statement to execute: its arm label, SQL, named bindings and cell kind.

    ``cell_kind`` is the mode's ``named_cell_kind`` (``None`` | ``"event"`` |
    ``"ordering"`` | ``"relation"``) and tells ``aggregate`` how to key the
    ``cell`` column; it rides on the query so a model-written statement is
    aggregated exactly like the reference one.
    """

    label: str
    sql: str
    params: dict = field(default_factory=dict)
    cell_kind: str | None = None


# ---------------------------------------------------------------------------
# SQL templates (bind parameters only; the text is fixed per conditioning)
# ---------------------------------------------------------------------------

def _sql_literal(s: str) -> str:
    """A single-quoted SQL string literal (used only for the fixed ORDERING_SEP)."""
    return "'" + s.replace("'", "''") + "'"


# ordered_pair: both present; denominator = distinct levels; co-exist excluded.
ORDERED_PAIR_SQL = """\
SELECT a.vaers_id,
       (a.level <> b.level) AS in_denominator,
       (a.level <  b.level) AS in_numerator,
       (a.level =  b.level) AS excluded,
       NULL                 AS cell
FROM first_mention a
JOIN first_mention b ON b.vaers_id = a.vaers_id
WHERE a.vaccine = :vax AND a.term = :a AND b.term = :b
ORDER BY a.vaers_id"""

# both_present: every both-present report is in the denominator and co-exist is
# the numerator. `{cell}` is NULL for sym_bool_cooccurs and the 3-way relation
# for cooc_modal_bool (whose named cell, co_exist, is that same numerator).
_BOTH_PRESENT_TEMPLATE = """\
SELECT a.vaers_id,
       1                   AS in_denominator,
       (a.level = b.level) AS in_numerator,
       0                   AS excluded,
       {cell} AS cell
FROM first_mention a
JOIN first_mention b ON b.vaers_id = a.vaers_id
WHERE a.vaccine = :vax AND a.term = :a AND b.term = :b
ORDER BY a.vaers_id"""

RELATION_CELL_SQL = ("CASE WHEN a.level < b.level THEN 'before' "
                     "WHEN a.level > b.level THEN 'after' ELSE 'co_exist' END")

BOTH_PRESENT_SQL = _BOTH_PRESENT_TEMPLATE.format(cell="NULL")
RELATION_SQL = _BOTH_PRESENT_TEMPLATE.format(cell=RELATION_CELL_SQL)

# All three events present, with their first-mention levels side by side.
_TRIPLE_CTE = """\
WITH t AS (
    SELECT a.vaers_id, a.level AS la, b.level AS lb, c.level AS lc
    FROM first_mention a
    JOIN first_mention b ON b.vaers_id = a.vaers_id
    JOIN first_mention c ON c.vaers_id = a.vaers_id
    WHERE a.vaccine = :vax AND a.term = :a AND b.term = :b AND c.term = :c
)"""


def _ordering_case() -> str:
    """CASE over the 6 strict orderings -> the TERMS sorted by level, joined by ORDERING_SEP.

    Built from the bound term parameters so the label uses the claim's exact
    spelling; a tie matches no branch and the CASE yields NULL (the row is not in
    the denominator, so its cell must be NULL).
    """
    sep = _sql_literal(ORDERING_SEP)
    branches = []
    for x, y, z in itertools.permutations(TERM_PARAMS[:3]):
        label = f" || {sep} || ".join(f":{p}" for p in (x, y, z))
        branches.append(f"            WHEN l{x} < l{y} AND l{y} < l{z} THEN {label}")
    return "CASE\n" + "\n".join(branches) + "\n       END"


# orderable_triple: denominator = pairwise-distinct levels; numerator = A<B<C.
ORDERABLE_TRIPLE_SQL = _TRIPLE_CTE + f"""
SELECT vaers_id,
       (la <> lb AND lb <> lc AND la <> lc)     AS in_denominator,
       (la < lb AND lb < lc)                    AS in_numerator,
       NOT (la <> lb AND lb <> lc AND la <> lc) AS excluded,
       {_ordering_case()} AS cell
FROM t
ORDER BY vaers_id"""

# all_present_unique_first / _last: m = MIN / MAX of the three levels; n_win = how
# many events sit at m. A unique extreme -> denominator (cell = the winner); a
# tie -> excluded, out of the denominator entirely (2026-08-11 rule).
_EXTREME_TEMPLATE = _TRIPLE_CTE + """,
u AS (SELECT vaers_id, la, lb, lc, {agg}(la, lb, lc) AS m FROM t),
w AS (SELECT vaers_id, la, lb, lc, m, (la = m) + (lb = m) + (lc = m) AS n_win FROM u)
SELECT vaers_id,
       (n_win = 1)            AS in_denominator,
       (n_win = 1 AND la = m) AS in_numerator,
       (n_win > 1)            AS excluded,
       CASE WHEN n_win = 1
            THEN CASE WHEN la = m THEN :a WHEN lb = m THEN :b ELSE :c END
       END AS cell
FROM w
ORDER BY vaers_id"""

UNIQUE_FIRST_SQL = _EXTREME_TEMPLATE.format(agg="MIN")
UNIQUE_LAST_SQL = _EXTREME_TEMPLATE.format(agg="MAX")

# presence_split: arm 1 = cohort reports containing A, arm 2 = the rest; every
# row is in the denominator, the numerator is "contains B", nothing is excluded.
PRESENCE_WITH_SQL = """\
SELECT r.vaers_id,
       1                        AS in_denominator,
       (b.vaers_id IS NOT NULL) AS in_numerator,
       0                        AS excluded,
       NULL                     AS cell
FROM reports r
JOIN first_mention a      ON a.vaers_id = r.vaers_id AND a.term = :a
LEFT JOIN first_mention b ON b.vaers_id = r.vaers_id AND b.term = :b
WHERE r.vaccine = :vax
ORDER BY r.vaers_id"""

PRESENCE_WITHOUT_SQL = """\
SELECT r.vaers_id,
       1                        AS in_denominator,
       (b.vaers_id IS NOT NULL) AS in_numerator,
       0                        AS excluded,
       NULL                     AS cell
FROM reports r
LEFT JOIN first_mention a ON a.vaers_id = r.vaers_id AND a.term = :a
LEFT JOIN first_mention b ON b.vaers_id = r.vaers_id AND b.term = :b
WHERE r.vaccine = :vax AND a.vaers_id IS NULL
ORDER BY r.vaers_id"""


# v1.2 consecutive_pair: both present; denominator = CONSECUTIVE first-mention
# ranks; numerator = A at the rank directly before B; co-exist and gapped pairs
# are present-but-excluded.
CONSECUTIVE_PAIR_SQL = """\
SELECT a.vaers_id,
       (ABS(a.rank - b.rank) = 1) AS in_denominator,
       (a.rank + 1 = b.rank)      AS in_numerator,
       (ABS(a.rank - b.rank) <> 1) AS excluded,
       NULL                       AS cell
FROM first_mention_rank a
JOIN first_mention_rank b ON b.vaers_id = a.vaers_id
WHERE a.vaccine = :vax AND a.term = :a AND b.term = :b
ORDER BY a.vaers_id"""

# v1.2 adjacency (adj_rate_bool): the ordered-pair denominator; numerator = the
# two ranks are consecutive (either order). The null (mean 2/L) is computed by
# S3 from the denominator reports' n_ranks, not returned here.
ADJACENT_PAIR_SQL = """\
SELECT a.vaers_id,
       (a.rank <> b.rank)         AS in_denominator,
       (ABS(a.rank - b.rank) = 1) AS in_numerator,
       (a.rank = b.rank)          AS excluded,
       NULL                       AS cell
FROM first_mention_rank a
JOIN first_mention_rank b ON b.vaers_id = a.vaers_id
WHERE a.vaccine = :vax AND a.term = :a AND b.term = :b
ORDER BY a.vaers_id"""

# v1.2 present_offmid (early_bool): reports containing A with >= 2 stages whose A
# is not on the exact middle rank; numerator = A in the earlier half.
PRESENT_OFFMID_SQL = """\
SELECT a.vaers_id,
       (a.n_ranks >= 2 AND 2 * a.rank <> a.n_ranks - 1) AS in_denominator,
       (a.n_ranks >= 2 AND 2 * a.rank <  a.n_ranks - 1) AS in_numerator,
       (a.n_ranks <  2 OR  2 * a.rank =  a.n_ranks - 1) AS excluded,
       NULL                                              AS cell
FROM first_mention_rank a
WHERE a.vaccine = :vax AND a.term = :a
ORDER BY a.vaers_id"""

# Report-tier modes whose rule needs the WHOLE report (ranks depend on every
# stage, not only on the claim's events).
WHOLE_REPORT_MODES = frozenset({"rep_early_bool", "rep_imm_bool"})


def report_sql(n_events: int, *, whole_report: bool = False) -> str:
    """single_report: ``(term, level)`` of the claim's events in report ``:r``
    (or of EVERY term of the report when ``whole_report``: v1.2 rank claims)."""
    if whole_report:
        return ("SELECT term, level\n"
                "FROM first_mention\n"
                "WHERE vaers_id = :r\n"
                "ORDER BY level, term")
    placeholders = ", ".join(f":{p}" for p in TERM_PARAMS[:n_events])
    return ("SELECT term, level\n"
            "FROM first_mention\n"
            f"WHERE vaers_id = :r AND term IN ({placeholders})\n"
            "ORDER BY level, term")


# ---------------------------------------------------------------------------
# compilation
# ---------------------------------------------------------------------------

def labels_for(claim: StructuredClaim) -> list[str]:
    """The arm labels a claim's mode needs, in order: ``[report]`` | ``[arm]`` | ``[cohort_1, cohort_2]``."""
    spec = MODE_SPEC[claim.mode]
    if spec.is_report:
        return [REPORT_LABEL]
    return list(TWO_ARM_LABELS) if spec.arms == 2 else [ARM_LABEL]


def compile_sql(claim: StructuredClaim) -> list[ArmQuery]:
    """The reference queries for ``claim``: one ``ArmQuery`` per arm (module docstring).

    Returns ``[]`` when the claim does not determine a query -- an
    underdetermined claim (a term is None), a cohort claim without a vaccine, a
    report claim without a report id, a multi claim with fewer than two
    vaccines -- so the caller records "nothing retrieved" rather than crashing.
    Raises ``ValueError`` only for a mode the harness does not know.
    """
    spec = MODE_SPEC.get(claim.mode)
    if spec is None:
        raise ValueError(f"unknown mode {claim.mode!r}")
    if claim.is_underdetermined or len(claim.events) != spec.n_events:
        return []
    terms = [str(t) for t in claim.terms]
    kind = spec.named_cell_kind

    # -- report tier ----------------------------------------------------------
    if spec.is_report:
        rid = claim.report_id
        if rid is None:
            return []
        whole = claim.mode in WHOLE_REPORT_MODES
        params = {"r": int(rid)} if whole else {"r": int(rid), **dict(zip(TERM_PARAMS, terms))}
        return [ArmQuery(REPORT_LABEL, report_sql(len(terms), whole_report=whole), params, None)]

    # -- cohort tiers ---------------------------------------------------------
    vaccines = list(claim.vaccines)
    if len(vaccines) < (2 if claim.mode == "multi_dir_precedes" else 1):
        return []
    vax = vaccines[0]
    a, b, c, d = (terms + [None] * 4)[:4]
    c1, c2 = TWO_ARM_LABELS

    def pair(label: str, x: str, y: str, v: str) -> ArmQuery:
        return ArmQuery(label, ORDERED_PAIR_SQL, {"vax": v, "a": x, "b": y}, kind)

    if claim.mode == "antecedent_bool":                      # (A,B) vs (C,B), one cohort
        return [pair(c1, a, b, vax), pair(c2, c, b, vax)]
    if claim.mode == "pairpair_bool":                        # (A,B) vs (C,D), one cohort
        return [pair(c1, a, b, vax), pair(c2, c, d, vax)]
    if claim.mode == "multi_dir_precedes":                   # (A,B) over v1 vs v2
        return [pair(c1, a, b, vaccines[0]), pair(c2, a, b, vaccines[1])]
    if claim.mode == "assoc_bool":                           # with-A vs without-A
        params = {"vax": vax, "a": a, "b": b}
        return [ArmQuery(c1, PRESENCE_WITH_SQL, dict(params), kind),
                ArmQuery(c2, PRESENCE_WITHOUT_SQL, dict(params), kind)]

    cond = spec.conditioning
    # v1.2: adjacency shares the ordered-pair denominator but not its numerator
    if claim.mode == "adj_rate_bool":
        return [ArmQuery(ARM_LABEL, ADJACENT_PAIR_SQL, {"vax": vax, "a": a, "b": b}, kind)]
    if cond == "consecutive_pair":
        return [ArmQuery(ARM_LABEL, CONSECUTIVE_PAIR_SQL, {"vax": vax, "a": a, "b": b}, kind)]
    if cond == "present_offmid":
        return [ArmQuery(ARM_LABEL, PRESENT_OFFMID_SQL, {"vax": vax, "a": a}, kind)]
    if cond == "ordered_pair":
        return [pair(ARM_LABEL, a, b, vax)]
    if cond == "both_present":
        sql = RELATION_SQL if kind == "relation" else BOTH_PRESENT_SQL
        return [ArmQuery(ARM_LABEL, sql, {"vax": vax, "a": a, "b": b}, kind)]
    triple = {"vax": vax, "a": a, "b": b, "c": c}
    if cond == "orderable_triple":
        return [ArmQuery(ARM_LABEL, ORDERABLE_TRIPLE_SQL, triple, kind)]
    if cond == "all_present_unique_first":
        return [ArmQuery(ARM_LABEL, UNIQUE_FIRST_SQL, triple, kind)]
    if cond == "all_present_unique_last":
        return [ArmQuery(ARM_LABEL, UNIQUE_LAST_SQL, triple, kind)]
    raise ValueError(f"no reference SQL for conditioning {cond!r} (mode {claim.mode})")
