"""Significance tests for population (cohort-level) gold values -- no scipy.

decisions.md locks both a p-value and a CI for every eligible gold value. The CIs
live in ``generation.confidence``; this module supplies the *tests* (the p-value
side), hand-rolled in stdlib only, matching the no-scipy constraint the repo
already follows.

Test families (exact tests preferred over normal approximations):

- One proportion vs a chance baseline -> exact **binomial** test, run
  **one-sided in the observed direction** for directional claims (the callers in
  ``core.answers`` pick ``greater``/``less``). Nulls by family: ``0.5``
  (pairwise precedes / co-occurs), ``1/6`` (sequence -- one of 6 strict
  orderings), ``1/3`` (first-among-3). The two-sided Sterne form is still the
  default for direction-agnostic use.
- Two proportions (multi-vaccine) -> **Fisher** exact on the 2x2 table:
  one-sided for the directional ``multi_dir_*`` modes, two-sided for the
  ``multi_differ_*`` "do they differ" modes; ``chi2_contingency`` is the large-n
  equivalent.
- Multinomial / distribution (modal ordering, first-event distribution, "same
  across cohorts") -> **chi-square** goodness-of-fit (vs uniform) or homogeneity.
  Guard: expected cell counts >= 5; when violated, a seeded Monte-Carlo p-value
  is used instead of the asymptotic chi-square.

The significance *verdict* is ``"significant"`` if ``p < 0.05`` AND the minimum-n
threshold is met, else ``"insufficient"``. Alpha = 0.05 throughout.

These are annotations on the gold value; the benchmark label stays the
``gold_verdict`` computed by the locked verdict rules in ``core.aggregation``.
"""

from __future__ import annotations

import math
from typing import Sequence

ALPHA = 0.05
MIN_N = 10
MIN_EXPECTED = 5.0  # asymptotic chi-square guard; below this, Monte-Carlo
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


def chi2_gof(observed: Sequence[int],
             expected: Sequence[float] | None = None) -> dict:
    """Asymptotic chi-square goodness-of-fit (large-n approximation only).

    Per 05_significance_tests.md this is used only when every expected cell >= 5;
    the exact multinomial GOF is primary otherwise. No Monte-Carlo.
    """
    obs = list(observed)
    total = sum(obs)
    cells = len(obs)
    if cells < 2 or total <= 0:
        return {"stat": 0.0, "df": max(0, cells - 1), "p": 1.0,
                "min_expected": 0.0, "method": "degenerate", "n": total}
    exp = [total / cells] * cells if expected is None else list(expected)
    df = cells - 1
    stat = _chi2_gof_stat(obs, exp)
    return {"stat": stat, "df": df, "p": chi2_sf(stat, df),
            "min_expected": min(exp), "method": "asymptotic", "n": total}


def chi2_contingency(table: Sequence[Sequence[int]]) -> dict:
    """Asymptotic chi-square for an R x C contingency table. No Monte-Carlo."""
    rows = [list(r) for r in table]
    R = len(rows)
    C = len(rows[0]) if rows else 0
    total = sum(sum(r) for r in rows)
    if R < 2 or C < 2 or total <= 0:
        return {"stat": 0.0, "df": 0, "p": 1.0, "min_expected": 0.0,
                "method": "degenerate", "n": total}
    row_sums = [sum(r) for r in rows]
    col_sums = [sum(rows[i][j] for i in range(R)) for j in range(C)]
    exp = [[row_sums[i] * col_sums[j] / total for j in range(C)] for i in range(R)]
    stat = sum((rows[i][j] - exp[i][j]) ** 2 / exp[i][j]
               for i in range(R) for j in range(C) if exp[i][j] > 0)
    df = (R - 1) * (C - 1)
    min_exp = min(exp[i][j] for i in range(R) for j in range(C))
    return {"stat": stat, "df": df, "p": chi2_sf(stat, df),
            "min_expected": min_exp, "method": "asymptotic", "n": total}


# ---------------------------------------------------------------------------
# exact tests (no permutation / Monte-Carlo; feasible because the conditioned
# multinomial samples are small once co-exist reports thin the strict orderings)
# ---------------------------------------------------------------------------

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
                    expected: Sequence[float] | None = None,
                    *, min_expected: float = MIN_EXPECTED) -> dict:
    """Multinomial GOF: chi-square when every expected cell >= min_expected,
    else the exact test (05: exact is primary, chi-square is the >=5 shortcut)."""
    r = chi2_gof(observed, expected)
    if r["min_expected"] < min_expected:
        return multinomial_gof_exact(observed, expected)
    return r


def contingency_test(table: Sequence[Sequence[int]],
                     *, min_expected: float = MIN_EXPECTED) -> dict:
    """2xk homogeneity: chi-square when every expected cell >= min_expected,
    else Fisher-Freeman-Halton exact."""
    r = chi2_contingency(table)
    if r["min_expected"] < min_expected:
        return fisher_freeman_halton(table)
    return r


# ---------------------------------------------------------------------------
# verdict
# ---------------------------------------------------------------------------

def significance_verdict(p: float | None, n: int | None,
                         *, min_n: int = MIN_N, alpha: float = ALPHA) -> str:
    """'significant' if p < alpha AND n >= min_n, else 'insufficient'."""
    if p is None or n is None or n < min_n:
        return "insufficient"
    return "significant" if p < alpha else "insufficient"
