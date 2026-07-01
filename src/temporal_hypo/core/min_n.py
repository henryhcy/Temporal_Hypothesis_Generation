"""Shared minimum-n gate -- the single source of truth for testability.

05_significance_tests.md mandates ONE standalone helper that BOTH dataset
creation and model evaluation call, so the threshold is defined and applied in
exactly one place. It is GATE-ONLY: it answers "is there enough conditioned data
to run a test", not "which test". An optional observed table enables the
expected-count >= 5 cell-adequacy check for the k-category distribution tests.

Provisional thresholds (05_significance_tests.md; recalibrated from the pilot):

- Family floor: 20 per cohort for pairwise/co-occurs, 30 per cohort for sequence
  and first/last.

The gate is FLOOR-ONLY. Under the weak-order + exact-test decision, sparse
k-category tables are handled by the EXACT multinomial / Fisher-Freeman-Halton
tests (which need no minimum expected cell), so a low expected count no longer
forces ``insufficient``; the chi-square-vs-exact choice is made inside the test
(``significance.multinomial_gof`` / ``contingency_test``) using MIN_EXPECTED. The
expected-cell helpers here remain for reporting which cores use the exact path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

PAIRWISE_FLOOR = 20      # pairwise + co-occurs (per cohort)
SEQUENCE_FLOOR = 5       # sequence: strict order over the ORDERABLE denominator
FIRST_LAST_FLOOR = 30    # first/last (per cohort)
MIN_EXPECTED = 5         # cell-adequacy guard for k-category tests

_FLOOR_BY_FAMILY = {
    "pairwise": PAIRWISE_FLOOR,
    "co_occurs": PAIRWISE_FLOOR,
    "sequence": SEQUENCE_FLOOR,
    "first_last": FIRST_LAST_FLOOR,
}


@dataclass(frozen=True)
class Gate:
    """A gate decision: testable yes/no plus a human-readable reason."""

    testable: bool
    reason: str


def family_floor(family: str) -> int:
    try:
        return _FLOOR_BY_FAMILY[family]
    except KeyError:
        raise ValueError(f"unknown family: {family!r}")


def _min_expected_gof(observed: Sequence[int]) -> float:
    """Minimum expected cell for a 1xk goodness-of-fit vs uniform (= total/k)."""
    total = sum(observed)
    k = len(observed)
    return total / k if k else 0.0


def _min_expected_contingency(table: Sequence[Sequence[int]]) -> float:
    """Minimum expected cell for an RxC table from its margins (row*col/total)."""
    rows = [list(r) for r in table]
    R = len(rows)
    C = len(rows[0]) if rows else 0
    total = sum(sum(r) for r in rows)
    if total <= 0 or R == 0 or C == 0:
        return 0.0
    row_sums = [sum(r) for r in rows]
    col_sums = [sum(rows[i][j] for i in range(R)) for j in range(C)]
    return min(row_sums[i] * col_sums[j] / total
               for i in range(R) for j in range(C))


def min_n_gate(n: int | None, family: str, *, n2: int | None = None) -> Gate:
    """Decide whether a conditioned sample is testable (floor-only).

    ``n`` (and ``n2`` for two-cohort tests) is checked against the family floor.
    Sparse k-category tables are NOT gated here -- the exact test handles them.
    """
    floor = family_floor(family)
    if n is None or n < floor:
        return Gate(False, f"n={n} below {family} floor {floor}")
    if n2 is not None and n2 < floor:
        return Gate(False, f"n2={n2} below {family} floor {floor}")
    return Gate(True, "testable")


def uses_exact(observed: Sequence) -> bool:
    """True if a k-category table is sparse enough to need the exact test
    (any expected cell < MIN_EXPECTED). ``observed`` is a 1xk list or 2xk list."""
    if not observed:
        return False
    if isinstance(observed[0], (list, tuple)):
        return _min_expected_contingency(observed) < MIN_EXPECTED
    return _min_expected_gof(observed) < MIN_EXPECTED
