"""Significance tests for population (cohort-level) gold values -- no scipy.

decisions.md locks both a p-value and a CI for every eligible gold value. The CIs
live in ``generation.confidence``; this module supplies the *tests* (the p-value
side), hand-rolled in stdlib only, matching the no-scipy constraint the repo
already follows.

**EXACT TESTS ONLY** (decisions.md 2026-08-11). Every benchmark label comes from
an exact test at every n; there is no asymptotic branch and no expected-cell
chooser. Current practice favours exact inference well past the n this corpus
reaches, and a single test per claim shape removes a whole class of
"which test ran here?" ambiguity from the gold labels.

Test families:

- One proportion vs a chance baseline -> exact **binomial** test, run
  **one-sided in the observed direction** for directional claims (the callers in
  ``core.answers`` pick ``greater``/``less``). Nulls by family: ``0.5``
  (pairwise precedes / co-occurs), ``1/6`` (sequence -- one of 6 strict
  orderings), ``1/3`` (first-among-3). The two-sided Sterne form is still the
  default for direction-agnostic use.
- Two proportions (multi-vaccine) -> **Fisher** exact on the 2x2 table:
  one-sided for the directional ``multi_dir_*`` modes, two-sided for the
  ``multi_differ_*`` "do they differ" modes.
- Multinomial / distribution (modal ordering, first-event distribution, "same
  across cohorts") -> **exact multinomial GOF** (vs uniform) or **exact
  Fisher-Freeman-Halton** homogeneity.

Exactness has a cost the approximation did not: the k-category tests enumerate
every table with the observed margins, which is ``C(n+k-1, k-1)`` for GOF. That
is trivial for the 3-candidate first/last tests and for the sequence tests at
their real n (median 6), but it grows fast in k. Past ``EXACT_MAX_TABLES`` the
test raises ``ExactTestTooLarge`` rather than quietly reverting to chi-square --
an infeasible table is a design signal (coarsen the categories or gate the core
out), not something to approximate.

``chi2_sf`` survives ONLY as a distribution function for the rank diagnostics in
``core.positions``, which are not label-producing (and are themselves under
review -- the normal approximation there is anti-conservative on tie-heavy data).

This module supplies p-values only. The benchmark LABEL is produced by
``core.verdict.three_decision``, which takes both one-sided tails and applies the
shared family min-n gate (``core.min_n``) to return
supported / refuted / insufficient. Alpha = 0.05 per side throughout.
"""

from __future__ import annotations

import math
from typing import Sequence

ALPHA = 0.05           # per SIDE: the directional tests are one-sided
# Legacy blanket floor. Superseded for labeling by the shared family floors in
# `core.min_n` (10 everywhere except sequence's thinner orderable denominator at
# 5), which `core.verdict.three_decision` applies. Kept only for the raw
# `significance_verdict` helper below and its callers outside the label path.
MIN_N = 10
# Feasibility cap for the k-category exact enumerations. Not a statistical
# threshold -- exceeding it raises rather than approximating (see module docs).
EXACT_MAX_TABLES = 5_000_000
_REL_TOL = 1e-7     # tolerance when comparing pmf tails for exact tests


# ---------------------------------------------------------------------------
# combinatorial helpers (log space; n up to a few thousand stays exact enough)
# ---------------------------------------------------------------------------

def _log_fact(n: int) -> float:
    return math.lgamma(n + 1)


def _log_choose(n: int, k: int) -> float:
    if k < 0 or k > n:
        return -math.inf
    return _log_fact(n) - _log_fact(k) - _log_fact(n - k)


# ---------------------------------------------------------------------------
# binomial exact test (Sterne two-sided, or one-sided greater/less)
# ---------------------------------------------------------------------------

def binom_pmf(k: int, n: int, p: float) -> float:
    if k < 0 or k > n:
        return 0.0
    if p <= 0.0:
        return 1.0 if k == 0 else 0.0
    if p >= 1.0:
        return 1.0 if k == n else 0.0
    logp = _log_choose(n, k) + k * math.log(p) + (n - k) * math.log1p(-p)
    return math.exp(logp)


def binom_exact_p(k: int, n: int, p0: float,
                  alternative: str = "two-sided") -> float:
    """Exact binomial p-value for k successes in n trials vs null p0.

    ``alternative`` selects the tail(s), matching ``scipy.stats.binomtest``:

    - ``"two-sided"`` (default): Sterne's method -- sum the probabilities of
      every outcome no more likely than the observed one. This is
      relabel-invariant: the p-value is a property of the data and does not
      depend on the claim direction (k and n-k give the same p at p0=0.5).
    - ``"greater"``: H1 that the true rate exceeds p0; p = P(X >= k).
    - ``"less"``:    H1 that the true rate is below  p0; p = P(X <= k).

    The one-sided forms make the p-value direction-aware. An effect in the
    asserted direction gets ~half the two-sided p, so borderline cores clear
    alpha, while the reverse direction gets a large p -- the mechanism behind
    the one-sided significance-as-verdict decision (see decisions.md).
    """
    if n <= 0:
        return 1.0
    k = max(0, min(n, k))
    if alternative == "greater":
        return min(1.0, sum(binom_pmf(i, n, p0) for i in range(k, n + 1)))
    if alternative == "less":
        return min(1.0, sum(binom_pmf(i, n, p0) for i in range(0, k + 1)))
    if alternative != "two-sided":
        raise ValueError(f"unknown alternative: {alternative!r}")
    p_obs = binom_pmf(k, n, p0)
    if p_obs == 0.0:
        return 0.0
    total = 0.0
    for i in range(n + 1):
        if binom_pmf(i, n, p0) <= p_obs * (1 + _REL_TOL):
            total += binom_pmf(i, n, p0)
    return min(1.0, total)


# ---------------------------------------------------------------------------
# Fisher exact test (two-sided by probability, or one-sided greater/less)
# on a 2x2 table
# ---------------------------------------------------------------------------

def _hyper_logpmf(a: int, r1: int, r2: int, c1: int, total: int) -> float:
    # P(top-left = a) for a 2x2 with row sums r1,r2 and first col sum c1.
    return _log_choose(r1, a) + _log_choose(r2, c1 - a) - _log_choose(total, c1)


def fisher_exact_2x2(k1: int, n1: int, k2: int, n2: int,
                     alternative: str = "two-sided") -> float:
    """Fisher exact p-value for the 2x2 [[k1, n1-k1], [k2, n2-k2]].

    ``alternative`` selects the tail(s), matching ``scipy.stats.fisher_exact``
    on the same table (the top-left cell a = k1 is the hypergeometric variable):

    - ``"two-sided"`` (default): sum the hypergeometric probabilities of all
      tables (fixed margins) no more likely than the observed one. Symmetric
      under swapping the two cohorts, so direction-blind.
    - ``"greater"``: H1 that p1 > p2 (odds ratio > 1); p = P(A >= k1).
    - ``"less"``:    H1 that p1 < p2 (odds ratio < 1); p = P(A <= k1).

    Used one-sided for the directional multi-vaccine modes (multi_dir_*) and
    two-sided for the "do they differ" modes (multi_differ_*).
    """
    if n1 <= 0 or n2 <= 0:
        return 1.0
    k1 = max(0, min(n1, k1))
    k2 = max(0, min(n2, k2))
    r1, r2 = n1, n2
    c1 = k1 + k2
    total = n1 + n2
    lo = max(0, c1 - r2)
    hi = min(r1, c1)
    if alternative == "greater":
        return min(1.0, sum(math.exp(_hyper_logpmf(a, r1, r2, c1, total))
                            for a in range(k1, hi + 1)))
    if alternative == "less":
        return min(1.0, sum(math.exp(_hyper_logpmf(a, r1, r2, c1, total))
                            for a in range(lo, k1 + 1)))
    if alternative != "two-sided":
        raise ValueError(f"unknown alternative: {alternative!r}")
    p_obs = math.exp(_hyper_logpmf(k1, r1, r2, c1, total))
    acc = 0.0
    for a in range(lo, hi + 1):
        pa = math.exp(_hyper_logpmf(a, r1, r2, c1, total))
        if pa <= p_obs * (1 + _REL_TOL):
            acc += pa
    return min(1.0, acc)


# ---------------------------------------------------------------------------
# chi-square survival function via the regularized upper incomplete gamma Q
# (Numerical Recipes gser / gcf), so no scipy dependency.
# ---------------------------------------------------------------------------

def _gser(s: float, x: float) -> float:
    """Regularized lower incomplete gamma P(s, x) by series (for x < s+1)."""
    if x <= 0.0:
        return 0.0
    ap = s
    total = 1.0 / s
    delta = total
    for _ in range(1000):
        ap += 1.0
        delta *= x / ap
        total += delta
        if abs(delta) < abs(total) * 1e-14:
            break
    return total * math.exp(-x + s * math.log(x) - math.lgamma(s))


def _gcf(s: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(s, x) by continued fraction."""
    tiny = 1e-300
    b = x + 1.0 - s
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - s)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return math.exp(-x + s * math.log(x) - math.lgamma(s)) * h


def gammq(s: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(s, x) = 1 - P(s, x)."""
    if x < 0.0 or s <= 0.0:
        raise ValueError("gammq requires x >= 0 and s > 0")
    if x < s + 1.0:
        return 1.0 - _gser(s, x)
    return _gcf(s, x)


def chi2_sf(x: float, df: int) -> float:
    """Upper-tail (survival) probability of the chi-square distribution."""
    if x <= 0.0:
        return 1.0
    if df <= 0:
        return 1.0
    return gammq(df / 2.0, x / 2.0)


# ---------------------------------------------------------------------------
# chi-square goodness-of-fit and contingency (homogeneity / independence)
# ---------------------------------------------------------------------------

def _chi2_gof_stat(observed: Sequence[float], expected: Sequence[float]) -> float:
    stat = 0.0
    for o, e in zip(observed, expected):
        if e > 0:
            stat += (o - e) ** 2 / e
    return stat


#
# NOTE: `chi2_gof` and `chi2_contingency` were REMOVED on 2026-08-11 -- no
# benchmark label may come from an asymptotic test. `_chi2_gof_stat` above stays
# because the EXACT multinomial GOF uses it purely as a discrepancy measure to
# order tables; no chi-square distribution is consulted. `chi2_sf` stays only for
# the non-label rank diagnostics in `core.positions`.


# ---------------------------------------------------------------------------
# exact tests (no permutation / Monte-Carlo; feasible because the conditioned
# multinomial samples are small once co-exist reports thin the strict orderings)
# ---------------------------------------------------------------------------

class ExactTestTooLarge(RuntimeError):
    """The exact enumeration for this table exceeds ``EXACT_MAX_TABLES``.

    Raised instead of silently falling back to chi-square: the 2026-08-11
    decision removed the asymptotic path entirely, so an infeasible table is a
    design problem to surface (coarsen the categories, or gate the core out),
    not something to approximate away.
    """


def _n_compositions(n: int, k: int) -> int:
    """How many length-k compositions of n exist: C(n+k-1, k-1)."""
    return math.comb(n + k - 1, k - 1)


def _compositions(n: int, k: int):
    """Yield every length-k non-negative integer tuple summing to n."""
    if k == 1:
        yield (n,)
        return
    for first in range(n + 1):
        for rest in _compositions(n - first, k - 1):
            yield (first,) + rest


def multinomial_gof_exact(observed: Sequence[int],
                          expected: Sequence[float] | None = None) -> dict:
    """Exact multinomial goodness-of-fit: sum the probabilities of all tables
    (same n) whose chi-square statistic is at least the observed one."""
    obs = list(observed)
    n = sum(obs)
    k = len(obs)
    if k < 2 or n <= 0:
        return {"stat": 0.0, "df": max(0, k - 1), "p": 1.0,
                "method": "exact", "n": n}
    n_tables = _n_compositions(n, k)
    if n_tables > EXACT_MAX_TABLES:
        raise ExactTestTooLarge(
            f"exact multinomial GOF over k={k} cells at n={n} needs "
            f"{n_tables:,} tables (cap {EXACT_MAX_TABLES:,})")
    p = [1.0 / k] * k if expected is None else [e / sum(expected) for e in expected]
    exp = [pi * n for pi in p]
    stat_obs = _chi2_gof_stat(obs, exp)
    log_n_fact = math.lgamma(n + 1)
    logp = [math.log(pi) if pi > 0 else -math.inf for pi in p]
    total = 0.0
    for comp in _compositions(n, k):
        if _chi2_gof_stat(comp, exp) >= stat_obs * (1 - 1e-9):
            lp = log_n_fact
            for ci, lpi in zip(comp, logp):
                lp += ci * lpi - math.lgamma(ci + 1)
            total += math.exp(lp)
    return {"stat": stat_obs, "df": k - 1, "p": min(1.0, total),
            "method": "exact", "n": n}


def fisher_freeman_halton(table: Sequence[Sequence[int]]) -> dict:
    """Exact test for a 2xk contingency table (Fisher-Freeman-Halton),
    two-sided by the probability criterion, with margins held fixed."""
    rows = [list(r) for r in table]
    if len(rows) != 2:
        raise ValueError("FFH expects a 2xk table")
    C = len(rows[0])
    r1, r2 = sum(rows[0]), sum(rows[1])
    total = r1 + r2
    col = [rows[0][j] + rows[1][j] for j in range(C)]
    if total <= 0:
        return {"p": 1.0, "method": "exact", "n": total}

    # upper bound on the tables `rec` will walk: one factor per column
    bound = 1
    for j in range(C - 1):
        bound *= min(col[j], r1) + 1
        if bound > EXACT_MAX_TABLES:
            raise ExactTestTooLarge(
                f"exact 2x{C} FFH at n={total} exceeds the "
                f"{EXACT_MAX_TABLES:,}-table cap")

    def logprob(a):
        lp = math.lgamma(r1 + 1) + math.lgamma(r2 + 1) - math.lgamma(total + 1)
        for j in range(C):
            lp += (math.lgamma(col[j] + 1) - math.lgamma(a[j] + 1)
                   - math.lgamma(col[j] - a[j] + 1))
        return lp

    p_obs = logprob(rows[0])
    acc = 0.0

    def rec(j, remaining, cur):
        nonlocal acc
        if j == C - 1:
            if 0 <= remaining <= col[j]:
                lp = logprob(cur + [remaining])
                if lp <= p_obs + 1e-9:
                    acc += math.exp(lp)
            return
        for v in range(0, min(col[j], remaining) + 1):
            rec(j + 1, remaining - v, cur + [v])

    rec(0, r1, [])
    return {"p": min(1.0, acc), "method": "exact", "n": total}


def multinomial_gof(observed: Sequence[int],
                    expected: Sequence[float] | None = None) -> dict:
    """Multinomial GOF -- ALWAYS the exact test (decisions.md 2026-08-11).

    There is no longer a chi-square branch: the asymptotic approximation is not
    used for any benchmark label at any n. See the module docstring.
    """
    return multinomial_gof_exact(observed, expected)


def contingency_test(table: Sequence[Sequence[int]]) -> dict:
    """2xk homogeneity -- ALWAYS Fisher-Freeman-Halton exact (2026-08-11).

    No chi-square branch, at any n.
    """
    return fisher_freeman_halton(table)


# ---------------------------------------------------------------------------
# verdict
# ---------------------------------------------------------------------------

def significance_verdict(p: float | None, n: int | None,
                         *, min_n: int = MIN_N, alpha: float = ALPHA) -> str:
    """'significant' if p < alpha AND n >= min_n, else 'insufficient'.

    Raw two-outcome check on a single p-value. This is NOT the benchmark label:
    one p-value cannot separate ``refuted`` (significant counter-evidence) from
    ``insufficient`` (no significant effect either way). Use
    ``core.verdict.three_decision`` for anything that labels an instance.
    """
    if p is None or n is None or n < min_n:
        return "insufficient"
    return "significant" if p < alpha else "insufficient"
