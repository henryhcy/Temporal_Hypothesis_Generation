"""Confidence quantification for gold proportions -- hand-rolled, no scipy.

95% throughout (alpha = 0.05); the only constant needed is the standard-normal
quantile z = 1.959963985. Methods (per decisions.md):

- Wilson score interval for a single proportion.
- Wilson-Newcombe (Newcombe method 10) for a difference of proportions.
- Seeded percentile bootstrap for statistics without a clean closed form
  (sequence/modal/multi).

The confidence TAG (high/moderate/low width cuts) was REMOVED on 2026-08-14
(decisions.md batch 2, issue 4): the cuts were never calibrated and at this
corpus's sample sizes the tag was near-constant. The interval and its width
remain reportable; the bucketing does not.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Sequence

# Standard-normal two-sided 95% quantile.
Z_95 = 1.959963985

def wilson_ci(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for k successes out of n trials.

    Closed form; correct at the boundaries k=0 and k=n. Raises on n<=0.
    """
    if n <= 0:
        raise ValueError("wilson_ci requires n > 0")
    p_hat = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p_hat + z2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))
    lo = max(0.0, center - half)
    hi = min(1.0, center + half)
    return (lo, hi)


def wilson_newcombe_diff_ci(
    k1: int, n1: int, k2: int, n2: int, z: float = Z_95
) -> tuple[float, float]:
    """Newcombe method 10 CI for the difference p1 - p2.

    Combines the two single-proportion Wilson intervals; pure arithmetic.
    """
    p1 = k1 / n1
    p2 = k2 / n2
    l1, u1 = wilson_ci(k1, n1, z)
    l2, u2 = wilson_ci(k2, n2, z)
    diff = p1 - p2
    lower = diff - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    upper = diff + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (max(-1.0, lower), min(1.0, upper))


def percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile of an already-sorted sequence.

    q in [0, 1]. Matches the common 'linear' method.
    """
    if not sorted_values:
        raise ValueError("percentile of empty sequence")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[int(pos)]
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def bootstrap_ci(
    samples: Sequence,
    statistic: Callable[[Sequence], float],
    *,
    b: int = 2000,
    seed: int = 0,
    z: float = Z_95,  # accepted for signature symmetry; alpha fixed at 95%
) -> tuple[float, float]:
    """Seeded percentile bootstrap 95% CI of statistic over samples.

    `samples` is the observation list; `statistic` maps a resample (same length)
    to a scalar. Deterministic given `seed`. Uses stdlib random only.
    """
    n = len(samples)
    if n == 0:
        raise ValueError("bootstrap_ci requires at least one sample")
    rng = random.Random(seed)
    stats = []
    for _ in range(b):
        resample = [samples[rng.randrange(n)] for _ in range(n)]
        stats.append(statistic(resample))
    stats.sort()
    return (percentile(stats, 0.025), percentile(stats, 0.975))


def ci_width(ci: tuple[float, float]) -> float:
    """Width of a confidence interval."""
    return ci[1] - ci[0]


def cohens_h(p1: float, p2: float) -> float:
    """Cohen's h effect size between two proportions (arcsine transform).

    For single-proportion BOOL groups the natural reference is p2 = 0.5
    (the majority threshold); for multi-vaccine groups it is the two cohort
    proportions. Sign follows p1 - p2.
    """
    phi1 = 2 * math.asin(math.sqrt(p1))
    phi2 = 2 * math.asin(math.sqrt(p2))
    return phi1 - phi2
