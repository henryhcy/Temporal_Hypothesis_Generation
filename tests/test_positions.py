"""Tests for the position-based (rank) tests (temporal_hypo.core.positions)."""

from temporal_hypo.core import positions as P


def approx(a, b, t=1e-3):
    return abs(a - b) <= t


def test_wilcoxon_exact_all_positive():
    # all-positive ranks 1..5: only all-+ and all-- are as extreme -> 2/32
    r = P.wilcoxon_signed_rank([1, 2, 3, 4, 5])
    assert r["method"] == "exact"
    assert approx(r["p"], 0.0625)


def test_wilcoxon_no_effect():
    assert approx(P.wilcoxon_signed_rank([1, -1, 2, -2, 3, -3])["p"], 1.0)
    # zeros (co-exist) are dropped
    assert P.wilcoxon_signed_rank([0, 0, 0])["n"] == 0


def test_mann_whitney_separation_and_null():
    r = P.mann_whitney_u([1, 2, 3], [4, 5, 6])
    assert r["U"] == 0.0 and r["p"] < 0.06
    assert approx(P.mann_whitney_u([1, 2, 3, 4], [1, 2, 3, 4])["p"], 1.0)


def test_friedman_perfect_agreement():
    # every report ranks the three events in the same order -> Q=16 (n=8,k=3)
    r = P.friedman([(0, 1, 2)] * 8)
    assert approx(r["Q"], 16.0) and r["df"] == 2 and r["p"] < 0.001


def test_kendalls_w_bounds():
    assert approx(P.kendalls_w([(0, 1, 2)] * 8)["W"], 1.0)      # perfect concordance
    # symmetric disagreement -> W ~ 0
    w = P.kendalls_w([(0, 1, 2), (2, 1, 0), (1, 0, 2),
                      (2, 0, 1), (0, 2, 1), (1, 2, 0)])["W"]
    assert approx(w, 0.0)


def test_friedman_uniform_not_significant():
    p = P.friedman([(0, 1, 2), (2, 1, 0), (1, 0, 2),
                    (2, 0, 1), (0, 2, 1), (1, 2, 0)])["p"]
    assert p > 0.5
