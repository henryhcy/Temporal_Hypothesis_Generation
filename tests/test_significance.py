"""Tests for temporal_hypo.core.significance (hand-rolled, scipy-free)."""

from temporal_hypo.core import significance as S


def approx(a, b, t=1e-3):
    return abs(a - b) <= t


# ---- binomial exact (two-sided) ------------------------------------------

def test_binom_exact_known_values():
    # vs scipy.stats.binomtest two-sided
    assert approx(S.binom_exact_p(8, 10, 0.5), 0.109375)
    assert approx(S.binom_exact_p(10, 10, 0.5), 0.001953125)
    assert approx(S.binom_exact_p(5, 10, 0.5), 1.0)


def test_binom_exact_nonhalf_null():
    # 10/10 successes against a 1/6 chance baseline is astronomically unlikely
    assert S.binom_exact_p(10, 10, 1 / 6) < 1e-6
    # right at the null rate the p-value is large
    assert S.binom_exact_p(2, 12, 1 / 6) > 0.5


def test_binom_exact_bounds():
    for k in range(0, 21):
        assert 0.0 <= S.binom_exact_p(k, 20, 0.5) <= 1.0


# ---- Fisher exact (two-sided) --------------------------------------------

def test_fisher_known_value():
    # scipy.stats.fisher_exact([[8,2],[1,5]]) -> 0.03497
    assert approx(S.fisher_exact_2x2(8, 10, 1, 6), 0.03497)


def test_fisher_identical_rows_is_one():
    assert approx(S.fisher_exact_2x2(5, 10, 5, 10), 1.0, 1e-9)


def test_fisher_strong_difference_significant():
    assert S.fisher_exact_2x2(18, 20, 2, 20) < 0.001


# ---- chi-square survival + GoF + contingency -----------------------------

def test_chi2_sf_critical_values():
    assert approx(S.chi2_sf(3.84146, 1), 0.05)
    assert approx(S.chi2_sf(5.99146, 2), 0.05)
    assert approx(S.chi2_sf(11.0705, 5), 0.05)
    assert S.chi2_sf(0.0, 3) == 1.0


def test_chi2_gof_uniform_and_skew():
    r = S.chi2_gof([20, 20, 20])
    assert r["stat"] == 0.0 and approx(r["p"], 1.0)
    r2 = S.chi2_gof([40, 10, 10])  # n=60, expected 20 each
    assert r2["method"] == "asymptotic" and r2["p"] < 0.001


def test_multinomial_gof_exact():
    # uniform observed -> p = 1
    assert approx(S.multinomial_gof_exact([10, 10, 10])["p"], 1.0)
    # a known small case; exact p is deterministic (no Monte-Carlo)
    r = S.multinomial_gof_exact([8, 1, 1])
    assert r["method"] == "exact" and 0.0 < r["p"] < 0.05
    assert r["p"] == S.multinomial_gof_exact([8, 1, 1])["p"]  # deterministic


def test_gof_chooser_exact_when_sparse_else_chi2():
    assert S.multinomial_gof([8, 1, 1])["method"] == "exact"        # expected 3.3 < 5
    assert S.multinomial_gof([30, 30, 30])["method"] == "asymptotic"  # expected 30


def test_fisher_freeman_halton():
    # 2x2 FFH must equal the 2x2 Fisher exact test
    ffh = S.fisher_freeman_halton([[8, 2], [1, 5]])["p"]
    assert approx(ffh, S.fisher_exact_2x2(8, 10, 1, 6), 1e-9)
    # identical rows -> p = 1
    assert approx(S.fisher_freeman_halton([[5, 5, 5], [5, 5, 5]])["p"], 1.0)
    # strong 2x3 divergence -> small p
    assert S.fisher_freeman_halton([[10, 0, 0], [0, 0, 10]])["p"] < 0.001


def test_no_monte_carlo_anywhere():
    # 05 forbids permutation/Monte-Carlo; the module must not expose it
    assert not hasattr(S, "_mc_gof_p")
    assert not hasattr(S, "_mc_contingency_p")


def test_chi2_contingency_homogeneity():
    same = S.chi2_contingency([[20, 20, 20], [20, 20, 20]])
    assert approx(same["p"], 1.0)
    diff = S.chi2_contingency([[40, 5, 5], [5, 5, 40]])
    assert diff["p"] < 0.001


# ---- verdict --------------------------------------------------------------

def test_significance_verdict():
    assert S.significance_verdict(0.01, 50) == "significant"
    assert S.significance_verdict(0.20, 50) == "insufficient"
    assert S.significance_verdict(0.01, 5) == "insufficient"   # n below min
    assert S.significance_verdict(None, 50) == "insufficient"
    assert S.significance_verdict(0.049, 10) == "significant"   # boundary n
