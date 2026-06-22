"""Significance tests for population (cohort-level) gold values -- no scipy.

decisions.md locks both a p-value and a CI for every eligible gold value. The CIs
live in ``generation.confidence``; this module supplies the *tests* (the p-value
side), hand-rolled in stdlib only, matching the no-scipy constraint the repo
already follows.

Test families (exact tests preferred over normal approximations):

- One proportion vs a chance baseline -> two-sided exact **binomial** test.
  Nulls by family: ``0.5`` (pairwise precedes / co-occurs), ``1/6`` (sequence --
  one of 6 strict orderings), ``1/3`` (first-among-3).
- Two proportions (multi-vaccine) -> two-sided **Fisher** exact on the 2x2 table;
  ``chi2_contingency`` is the large-n equivalent.
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
import random
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
# binomial exact test (two-sided, Sterne's "sum of smaller probabilities")
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


def binom_exact_p(k: int, n: int, p0: float) -> float:
    """Two-sided exact binomial p-value for k successes in n trials vs null p0.

    Sterne's method: sum the probabilities of every outcome no more likely than
    the observed one. Matches the default two-sided ``scipy.stats.binomtest``.
    """
    if n <= 0:
        return 1.0
    k = max(0, min(n, k))
    p_obs = binom_pmf(k, n, p0)
    if p_obs == 0.0:
        return 0.0
    total = 0.0
    for i in range(n + 1):
        if binom_pmf(i, n, p0) <= p_obs * (1 + _REL_TOL):
            total += binom_pmf(i, n, p0)
    return min(1.0, total)


# ---------------------------------------------------------------------------
# Fisher exact test (two-sided) on a 2x2 table
# ---------------------------------------------------------------------------

def _hyper_logpmf(a: int, r1: int, r2: int, c1: int, total: int) -> float:
    # P(top-left = a) for a 2x2 with row sums r1,r2 and first col sum c1.
    return _log_choose(r1, a) + _log_choose(r2, c1 - a) - _log_choose(total, c1)


def fisher_exact_2x2(k1: int, n1: int, k2: int, n2: int) -> float:
    """Two-sided Fisher exact p-value for the 2x2 [[k1, n1-k1], [k2, n2-k2]].

    Sums the hypergeometric probabilities of all tables (fixed margins) no more
    likely than the observed one.
    """
    if n1 <= 0 or n2 <= 0:
        return 1.0
    k1 = max(0, min(n1, k1))
    k2 = max(0, min(n2, k2))
    r1, r2 = n1, n2
    c1 = k1 + k2
    total = n1 + n2
    p_obs = math.exp(_hyper_logpmf(k1, r1, r2, c1, total))
    lo = max(0, c1 - r2)
    hi = min(r1, c1)
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


def chi2_gof(
    observed: Sequence[int],
    expected: Sequence[float] | None = None,
    *,
    mc_b: int = 2000,
    seed: int = 0,
) -> dict:
    """Chi-square goodness-of-fit. expected defaults to uniform over the cells.

    Returns dict(stat, df, p, min_expected, method, n). When any expected cell is
    below MIN_EXPECTED, a seeded Monte-Carlo p-value replaces the asymptotic one.
    """
    obs = list(observed)
    total = sum(obs)
    cells = len(obs)
    if cells < 2 or total <= 0:
        return {"stat": 0.0, "df": max(0, cells - 1), "p": 1.0,
                "min_expected": 0.0, "method": "degenerate", "n": total}
    if expected is None:
        exp = [total / cells] * cells
    else:
        exp = list(expected)
    df = cells - 1
    stat = _chi2_gof_stat(obs, exp)
    min_exp = min(exp)
    if min_exp < MIN_EXPECTED:
        p = _mc_gof_p(obs, exp, stat, b=mc_b, seed=seed)
        method = "monte_carlo"
    else:
        p = chi2_sf(stat, df)
        method = "asymptotic"
    return {"stat": stat, "df": df, "p": p, "min_expected": min_exp,
            "method": method, "n": total}


def chi2_contingency(table: Sequence[Sequence[int]], *, mc_b: int = 5000,
                     seed: int = 0) -> dict:
    """Chi-square for an R x C contingency table (homogeneity / independence).

    Returns dict(stat, df, p, min_expected, method, n). Monte-Carlo fallback
    (resampling each row from the pooled column distribution) when any expected
    cell is below MIN_EXPECTED.
    """
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
    stat = 0.0
    for i in range(R):
        for j in range(C):
            if exp[i][j] > 0:
                stat += (rows[i][j] - exp[i][j]) ** 2 / exp[i][j]
    df = (R - 1) * (C - 1)
    min_exp = min(exp[i][j] for i in range(R) for j in range(C))
    if min_exp < MIN_EXPECTED:
        p = _mc_contingency_p(rows, row_sums, col_sums, total, stat,
                              b=mc_b, seed=seed)
        method = "monte_carlo"
    else:
        p = chi2_sf(stat, df)
        method = "asymptotic"
    return {"stat": stat, "df": df, "p": p, "min_expected": min_exp,
            "method": method, "n": total}


def _mc_gof_p(observed: Sequence[int], expected: Sequence[float], stat_obs: float,
              *, b: int, seed: int) -> float:
    total = int(round(sum(observed)))
    cells = len(observed)
    weights = [e / sum(expected) for e in expected]
    rng = random.Random(seed)
    idx = list(range(cells))
    ge = 0
    for _ in range(b):
        draw = rng.choices(idx, weights=weights, k=total)
        counts = [0] * cells
        for d in draw:
            counts[d] += 1
        if _chi2_gof_stat(counts, expected) >= stat_obs - 1e-12:
            ge += 1
    return (ge + 1) / (b + 1)


def _mc_contingency_p(rows, row_sums, col_sums, total, stat_obs, *, b, seed) -> float:
    R = len(rows)
    C = len(col_sums)
    pooled_w = [c / total for c in col_sums]
    exp = [[row_sums[i] * col_sums[j] / total for j in range(C)] for i in range(R)]
    rng = random.Random(seed)
    idx = list(range(C))
    ge = 0
    for _ in range(b):
        stat = 0.0
        sim = []
        for i in range(R):
            draw = rng.choices(idx, weights=pooled_w, k=row_sums[i])
            counts = [0] * C
            for d in draw:
                counts[d] += 1
            sim.append(counts)
        for i in range(R):
            for j in range(C):
                if exp[i][j] > 0:
                    stat += (sim[i][j] - exp[i][j]) ** 2 / exp[i][j]
        if stat >= stat_obs - 1e-12:
            ge += 1
    return (ge + 1) / (b + 1)


# ---------------------------------------------------------------------------
# verdict
# ---------------------------------------------------------------------------

def significance_verdict(p: float | None, n: int | None,
                         *, min_n: int = MIN_N, alpha: float = ALPHA) -> str:
    """'significant' if p < alpha AND n >= min_n, else 'insufficient'."""
    if p is None or n is None or n < min_n:
        return "insufficient"
    return "significant" if p < alpha else "insufficient"
