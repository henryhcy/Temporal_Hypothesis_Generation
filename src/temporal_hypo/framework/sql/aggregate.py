"""The Stage-2 row contract and its aggregation into counts.

Every retrieval method -- the reference compiler and a model's SQL alike -- must
return, per ARM, rows of exactly this shape::

    (vaers_id, in_denominator, in_numerator, excluded, cell)

- ``vaers_id``        the report (the release's report id; NOT the DB surrogate)
- ``in_denominator``  1 if the report satisfies the claim's conditioning (counts in n)
- ``in_numerator``    1 if it also satisfies the asserted direction (counts in k)
- ``excluded``        1 if the report is present-but-unusable (co-exist for a
                      precedes claim, a non-orderable triple, a first/last tie)
- ``cell``            the report's cell in the argmax table (a winner term, an
                      ordering label, or before/after/co_exist) -- **NULL for every
                      row with in_denominator = 0**. The oracle takes ``max`` over
                      every non-named key of ``counts``, so a tie bucket leaking in
                      as a cell corrupts every argmax p-value.

Report-tier retrieval has a different shape: ``(term, level)`` rows for the one
report, aggregated by ``report_levels``.

``aggregate`` is deliberately dumb: it trusts the flags and only builds sets and
counts. Whether the flags are RIGHT is what the evaluation scores against
``evidence_ids``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

ARM_COLUMNS = ("vaers_id", "in_denominator", "in_numerator", "excluded", "cell")
REPORT_COLUMNS = ("term", "level")

# how a `cell` string is turned into the key the oracle's counts dict expects
ORDERING_SEP = "|"   # ordering cells are 'A|B|C' in the asserted-term spelling


@dataclass(frozen=True)
class ArmRow:
    vaers_id: int
    in_denominator: bool
    in_numerator: bool
    excluded: bool
    cell: str | None


@dataclass
class ArmCounts:
    n: int
    k: int
    denominator_ids: set[int]
    numerator_ids: set[int]
    excluded_ids: set[int]
    counts: dict[Any, int] = field(default_factory=dict)   # cell -> count, denominator rows only
    n_rows: int = 0

    @property
    def proportion(self) -> float | None:
        return self.k / self.n if self.n else None


def rows_from_records(records: Iterable[Sequence[Any]]) -> list[ArmRow]:
    """Coerce raw SQL result tuples (in ARM_COLUMNS order) into ArmRows.

    Raises ``ValueError`` on a malformed row -- that is the ``contract_violation``
    failure class for model-written SQL.
    """
    out: list[ArmRow] = []
    for r in records:
        if len(r) != len(ARM_COLUMNS):
            raise ValueError(f"arm row has {len(r)} columns, expected {ARM_COLUMNS}: {r!r}")
        vid, den, num, exc, cell = r
        try:
            vid = int(vid)
        except (TypeError, ValueError):
            raise ValueError(f"vaers_id is not an integer: {vid!r}") from None
        out.append(ArmRow(vid, bool(den), bool(num), bool(exc),
                          None if cell is None else str(cell)))
    return out


def cell_key(cell: str | None, kind: str | None):
    """Turn a cell label into the oracle's counts key for the mode's cell kind."""
    if cell is None:
        return None
    if kind == "ordering":
        return tuple(cell.split(ORDERING_SEP))
    return cell


def aggregate(rows: Iterable[ArmRow], *, cell_kind: str | None = None) -> ArmCounts:
    """Sets and counts from an arm's rows. ``counts`` uses denominator rows only."""
    den: set[int] = set()
    num: set[int] = set()
    exc: set[int] = set()
    counts: dict[Any, int] = {}
    n_rows = 0
    for r in rows:
        n_rows += 1
        if r.in_denominator:
            den.add(r.vaers_id)
            if r.in_numerator:
                num.add(r.vaers_id)
            if cell_kind is not None and r.cell is not None:
                key = cell_key(r.cell, cell_kind)
                counts[key] = counts.get(key, 0) + 1
        elif r.excluded:
            exc.add(r.vaers_id)
    return ArmCounts(n=len(den), k=len(num), denominator_ids=den,
                     numerator_ids=num, excluded_ids=exc, counts=counts,
                     n_rows=n_rows)


def report_levels(records: Iterable[Sequence[Any]]) -> dict[str, int]:
    """Report-tier rows ``(term, level)`` -> ``{term: first-mention level}``."""
    out: dict[str, int] = {}
    for r in records:
        if len(r) != 2:
            raise ValueError(f"report row has {len(r)} columns, expected {REPORT_COLUMNS}: {r!r}")
        term, level = r
        if level is None:
            continue
        level = int(level)
        if term not in out or level < out[term]:
            out[str(term)] = level
    return out
