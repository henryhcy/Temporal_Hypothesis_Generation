"""Three-decision directional verdict labeler (decisions.md, 2026-07-28).

The gold verdict for a cohort-level claim is a **three-decision (directional)
test**, not the textbook two-outcome NHST. The null is nondirectional (no
effect); the CLAIM asserts a direction; the decision is::

    p(claim direction)    < alpha           -> supported
    else p(opposite dir.) < alpha           -> refuted
    else                                    -> insufficient

Both supported and refuted therefore require significance, in opposite
directions. ``refuted`` NEVER means "not significant, therefore false" (that
would be accepting H0) -- it means positive counter-evidence. A single
claim-direction p-value cannot separate refuted from insufficient; the opposite
tail must be checked, which is why every caller supplies BOTH tails.

Alpha is 0.05 **per side** (decisions.md): the directional tests run one-sided in
the asserted direction. Documented property: choosing the direction after seeing
the data makes P(declare SOME direction | true null) ~ 2*alpha = 0.10, while the
wrong-SIGN error stays <= alpha/2.

The two tails are mutually exclusive at any alpha < 0.5, so at most one of
supported/refuted can fire; the order of the checks above is for clarity, not
precedence.

Insufficient sub-types
----------------------
The 2026-07-28 decision requires the insufficient class to span, and be LABELED
by, all three of its failure modes -- they test different framework behaviours:

- ``underpowered``   -- enough conditioned data (n clears the floor) but neither
                        direction is significant;
- ``sparse``         -- the events co-occur but n is below the family floor;
- ``not_locatable``  -- one or both events absent / never co-occur, so the
                        conditioned n is 0 (tests whether the framework says
                        "insufficient" instead of hallucinating a relationship).

A fourth label, ``non_directional``, is NOT an insufficient sub-type for the
benchmark: it marks a mode whose claim shape has no direction (omnibus
goodness-of-fit / homogeneity, and the "differ"/"same" multi shapes), so the
three-decision test does not apply to it at all. These are exactly the shapes
the 2026-07-28 roster decision retires; the labeler reports them rather than
forcing a verdict.

The minimum-n gate is the SHARED one (``core.min_n``), per 05_significance_tests:
one helper, applied in one place, by both dataset creation and evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass

from temporal_hypo.core.min_n import min_n_gate
from temporal_hypo.core.significance import ALPHA

SUPPORTED = "supported"
REFUTED = "refuted"
INSUFFICIENT = "insufficient"

# insufficient sub-types (all three must appear in the shipped benchmark)
UNDERPOWERED = "underpowered"
SPARSE = "sparse"
NOT_LOCATABLE = "not_locatable"
# not an insufficient sub-type: the claim shape has no direction to test
NON_DIRECTIONAL = "non_directional"
# report-level groups: a single deterministic observation, no test
DETERMINISTIC = "deterministic"


@dataclass(frozen=True)
class Decision:
    """A three-decision verdict plus everything needed to justify it."""

    verdict: str                  # supported | refuted | insufficient
    subtype: str | None           # insufficient sub-type, or a non-test marker
    p_claim: float | None         # one-sided p in the CLAIM's direction
    p_opposite: float | None      # one-sided p in the opposite direction
    n: int | None                 # conditioned denominator the gate saw
    gate: str                     # min_n gate reason ("testable" | why not)
    alpha: float = ALPHA

    @property
    def decisive(self) -> bool:
        """True when the data settled the claim either way (not insufficient)."""
        return self.verdict != INSUFFICIENT


def three_decision(p_claim: float | None, p_opposite: float | None,
                   n: int | None, family: str, *, n2: int | None = None,
                   alpha: float = ALPHA) -> Decision:
    """Label one claim from its two one-sided p-values and its denominator.

    ``p_claim`` is the p-value for the direction the claim asserts and
    ``p_opposite`` the p-value for the reverse direction; pass ``p_claim=None``
    for a mode with no directional alternative (omnibus / "differ" / "same"),
    which yields ``insufficient`` tagged ``non_directional``.

    ``family`` selects the min-n floor from the shared gate (``core.min_n``);
    ``n2`` is the second cohort's denominator for two-cohort tests, which must
    clear the floor as well.
    """
    if n == 0 or n2 == 0:
        return Decision(INSUFFICIENT, NOT_LOCATABLE, p_claim, p_opposite,
                        n, "not locatable: conditioned n is 0", alpha)
    if n is None:
        # KNOWN GAP: the corpus fraction helpers return None (dropping n) for any
        # core below the enumeration viability floor, so a sparse core and a
        # not-locatable one are indistinguishable here. Generating the deliberate
        # `not_locatable` third requires those helpers to report n even below the
        # floor; until then the sub-type is left unlabeled rather than guessed.
        return Decision(INSUFFICIENT, None, p_claim, p_opposite, None,
                        "n unavailable: core below the viability floor", alpha)

    gate = min_n_gate(n, family, n2=n2)
    if not gate.testable:
        return Decision(INSUFFICIENT, SPARSE, p_claim, p_opposite,
                        n, gate.reason, alpha)

    if p_claim is None:
        return Decision(INSUFFICIENT, NON_DIRECTIONAL, None, p_opposite,
                        n, gate.reason, alpha)

    if p_claim < alpha:
        return Decision(SUPPORTED, None, p_claim, p_opposite, n,
                        gate.reason, alpha)
    if p_opposite is not None and p_opposite < alpha:
        return Decision(REFUTED, None, p_claim, p_opposite, n,
                        gate.reason, alpha)
    return Decision(INSUFFICIENT, UNDERPOWERED, p_claim, p_opposite, n,
                    gate.reason, alpha)


def deterministic(verdict: str) -> Decision:
    """The verdict for a report-level claim: exact, single observation, no test."""
    return Decision(verdict, DETERMINISTIC, None, None, None, DETERMINISTIC)
