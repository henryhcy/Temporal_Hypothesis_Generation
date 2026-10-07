"""Shared minimum-n gate -- the single source of truth for testability.

05_significance_tests.md mandates ONE standalone helper that BOTH dataset
creation and model evaluation call, so the threshold is defined and applied in
exactly one place. It is GATE-ONLY: it answers "is there enough conditioned data
to run a test", not "which test". An optional observed table enables the
expected-count >= 5 cell-adequacy check for the k-category distribution tests.

Thresholds (decisions.md 2026-08-11; recalibrated from the pilot):

- Family floor: 10 per cohort for pairwise/co-occurs and first/last -- aligned
  with the enumeration viability floor (``corpus._MIN_N``), so the test floor no
  longer discards cores the enumerator was willing to emit.
- Sequence stays at 5: strict order over the ORDERABLE denominator is a thinner
  denominator than the others, and the 5 is load-bearing (it is the only thing
  keeping S-V1 non-zero).

The floor is a QUALITY choice, not a validity one -- the tests are exact, so they
are valid at small n; the floor decides how thin the evidence behind a shipped
question may be.

The gate is FLOOR-ONLY. Every k-category table is handled by the EXACT
multinomial / Fisher-Freeman-Halton test, which needs no minimum expected cell,
so a low expected count never forces ``insufficient``.

The ``MIN_EXPECTED`` constant and the ``uses_exact`` / expected-cell helpers were
REMOVED on 2026-08-11: they existed only to choose between chi-square and exact,
and there is no longer a chi-square path to choose (decisions.md). Nothing needs
to report "which cores use the exact path" when the answer is all of them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

PAIRWISE_FLOOR = 10      # pairwise + co-occurs (per cohort)
SEQUENCE_FLOOR = 5       # sequence: strict order over the ORDERABLE denominator
FIRST_LAST_FLOOR = 10    # first/last (per cohort)

_FLOOR_BY_FAMILY = {
    "pairwise": PAIRWISE_FLOOR,
    "co_occurs": PAIRWISE_FLOOR,
    "sequence": SEQUENCE_FLOOR,
    "first_last": FIRST_LAST_FLOOR,
    # v1.2 families (decisions.md 2026-10-07): single-proportion claims on
    # pair- or term-shaped denominators, so they share the pairwise floor.
    "position": PAIRWISE_FLOOR,
    "proximity": PAIRWISE_FLOOR,
    "threshold": PAIRWISE_FLOOR,
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
