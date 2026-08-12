"""Position-based (rank) tests -- the second test track of 05_significance_tests.

These operate on event LEVEL indices rather than outcome-label counts, and are
complementary to the categorical tests: co-occurrence is kept (rank-distance
d=0 / tied ranks) instead of excluded. All are non-parametric and closed-form
(no scipy, no permutation): exact for small Wilcoxon samples, else a normal
approximation with tie/continuity corrections; Friedman / Kendall's W use the
chi-square approximation (via ``significance.chi2_sf``).

- Wilcoxon signed-rank (one cohort, paired events): is the median rank-distance
  A-B non-zero (A systematically earlier/later than B by a margin)?
- Mann-Whitney U (two cohorts): is one cohort's positions systematically earlier?
- Friedman (one cohort, k events ranked within report): do the events differ in
  typical position? Kendall's W is its normalised concordance (0..1).

RETIRED as a verdict driver (decisions.md 2026-08-11, "§6 lever 2"). Nothing here
produces a benchmark label, and nothing here should: a permutation null showed the
Mann-Whitney normal approximation is ANTI-CONSERVATIVE on tie-heavy small-integer
ordinal data -- shuffled labels yield ~11% decisive cores against a nominal 5%, so
the lever manufactured false positives rather than recovering signal. The two
rank-based multi candidates built on it (M-E' 0.333, M-A 0.381) are noise.

These functions survive only as DESCRIPTIVE diagnostics for the advisor-facing
worked examples (`scripts/make_examples.py`) and the design-time candidate inventory
(`scripts/replacement_inventory.py`). `core.answers` does not import this module, and
must not: any p-value from here is not a gold label.
"""

from __future__ import annotations

import math
from collections import Counter
from itertools import product
from typing import Sequence

from temporal_hypo.core.significance import chi2_sf


def _normal_sf(z: float) -> float:
    """Upper-tail standard-normal survival function via erfc."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def _avg_ranks(values: Sequence[float]) -> list[float]:
    """1-based ranks of values, ties assigned the average of their rank block."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0   # mean of ranks (i+1)..(j+1)
        for m in range(i, j + 1):
            ranks[order[m]] = avg
        i = j + 1
    return ranks


# ---------------------------------------------------------------------------
# Wilcoxon signed-rank (one-sample, H0: median difference = 0)
# ---------------------------------------------------------------------------

def wilcoxon_signed_rank(d: Sequence[float], *, exact_max: int = 15) -> dict:
    nz = [x for x in d if x != 0]
    n = len(nz)
    if n == 0:
        return {"stat": 0.0, "p": 1.0, "n": 0, "method": "degenerate"}
    ranks = _avg_ranks([abs(x) for x in nz])
    w_plus = sum(r for r, x in zip(ranks, nz) if x > 0)
    mean = sum(ranks) / 2.0

    if n <= exact_max:
        obs = abs(w_plus - mean)
        ge = tot = 0
        for signs in product((0, 1), repeat=n):
            wp = sum(r for r, s in zip(ranks, signs) if s)
            tot += 1
            if abs(wp - mean) >= obs - 1e-9:
                ge += 1
        return {"stat": w_plus, "p": ge / tot, "n": n, "method": "exact"}

    tie_term = sum(t ** 3 - t for t in Counter(abs(x) for x in nz).values())
    var = (n * (n + 1) * (2 * n + 1) - tie_term / 2.0) / 24.0
    if var <= 0:
        return {"stat": w_plus, "p": 1.0, "n": n, "method": "degenerate"}
    z = (w_plus - mean) / math.sqrt(var)
    return {"stat": w_plus, "p": min(1.0, 2 * _normal_sf(abs(z))),
            "n": n, "method": "normal"}


# ---------------------------------------------------------------------------
# Mann-Whitney U (two independent samples)
# ---------------------------------------------------------------------------

def mann_whitney_u(x: Sequence[float], y: Sequence[float]) -> dict:
    nx, ny = len(x), len(y)
    if nx == 0 or ny == 0:
        return {"U": 0.0, "p": 1.0, "n1": nx, "n2": ny, "method": "degenerate"}
    combined = list(x) + list(y)
    ranks = _avg_ranks(combined)
    rx = sum(ranks[:nx])
    ux = rx - nx * (nx + 1) / 2.0
    u = min(ux, nx * ny - ux)
    mean = nx * ny / 2.0
    N = nx + ny
    tie_term = sum(t ** 3 - t for t in Counter(combined).values())
    var = (nx * ny / 12.0) * ((N + 1) - tie_term / (N * (N - 1))) if N > 1 else 0.0
    if var <= 0:
        return {"U": u, "p": 1.0, "n1": nx, "n2": ny, "method": "degenerate"}
    z = (u - mean) / math.sqrt(var)
    return {"U": u, "p": min(1.0, 2 * _normal_sf(abs(z))),
            "n1": nx, "n2": ny, "method": "normal"}


# ---------------------------------------------------------------------------
# Friedman + Kendall's W (one cohort, k events ranked within each report)
# ---------------------------------------------------------------------------

def _rank_sums(blocks: Sequence[Sequence[float]]) -> tuple[int, int, list[float], float]:
    n = len(blocks)
    k = len(blocks[0])
    rj = [0.0] * k
    tie_term = 0.0
    for b in blocks:
        r = _avg_ranks(list(b))
        for j in range(k):
            rj[j] += r[j]
        tie_term += sum(t ** 3 - t for t in Counter(b).values())
    return n, k, rj, tie_term


def friedman(blocks: Sequence[Sequence[float]]) -> dict:
    if len(blocks) < 2 or len(blocks[0]) < 2:
        return {"Q": 0.0, "df": 0, "p": 1.0, "method": "degenerate"}
    n, k, rj, tie = _rank_sums(blocks)
    q = (12.0 / (n * k * (k + 1))) * sum(r * r for r in rj) - 3.0 * n * (k + 1)
    denom = 1.0 - tie / (n * (k ** 3 - k))
    if denom > 0:
        q = q / denom
    df = k - 1
    return {"Q": q, "df": df, "p": chi2_sf(q, df), "method": "chi2"}


def kendalls_w(blocks: Sequence[Sequence[float]]) -> dict:
    if len(blocks) < 2 or len(blocks[0]) < 2:
        return {"W": 0.0, "Q": 0.0, "df": 0, "p": 1.0, "method": "degenerate"}
    n, k, rj, tie = _rank_sums(blocks)
    rbar = sum(rj) / k
    s = sum((r - rbar) ** 2 for r in rj)
    denom = n * n * (k ** 3 - k) - n * tie
    w = 12.0 * s / denom if denom > 0 else 0.0
    q = n * (k - 1) * w
    df = k - 1
    return {"W": w, "Q": q, "df": df, "p": chi2_sf(q, df), "method": "chi2"}
