"""Tests for hand-rolled confidence functions."""

from __future__ import annotations

from temporal_hypo.generation.confidence import (
    bootstrap_ci,
    cohens_h,
    ci_width,
    percentile,
    wilson_ci,
    wilson_newcombe_diff_ci,
)


def test_wilson_known_value():
    lo, hi = wilson_ci(8, 12)
    assert abs(lo - 0.3906) < 1e-3
    assert abs(hi - 0.8619) < 1e-3


def test_wilson_boundaries():
    lo, hi = wilson_ci(0, 10)
    assert lo == 0.0
    assert 0.25 < hi < 0.31
    lo, hi = wilson_ci(10, 10)
    assert hi == 1.0
    assert 0.69 < lo < 0.73


def test_wilson_newcombe_diff():
    lo, hi = wilson_newcombe_diff_ci(60, 100, 40, 100)
    # diff = 0.2; interval is positive and excludes 0
    assert lo > 0
    assert abs(lo - 0.0614) < 1e-3
    assert abs(hi - 0.3281) < 1e-3


def test_bootstrap_reproducible_and_centered():
    samples = [1.0] * 7 + [0.0] * 3  # mean 0.7
    a = bootstrap_ci(samples, lambda s: sum(s) / len(s), b=500, seed=42)
    b = bootstrap_ci(samples, lambda s: sum(s) / len(s), b=500, seed=42)
    assert a == b  # deterministic given seed
    assert a[0] < 0.7 < a[1] or abs(a[1] - 0.7) < 0.2


def test_ci_width_and_percentile():
    assert abs(ci_width((0.2, 0.5)) - 0.3) < 1e-12
    assert percentile([0, 1, 2, 3, 4], 0.5) == 2
    assert percentile([10], 0.9) == 10


def test_cohens_h_sign():
    assert cohens_h(0.7, 0.5) > 0
    assert cohens_h(0.3, 0.5) < 0
    assert abs(cohens_h(0.5, 0.5)) < 1e-12
