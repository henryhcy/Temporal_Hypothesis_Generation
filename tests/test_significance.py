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


# ---- binomial exact (one-sided) ------------------------------------------

def test_binom_one_sided_known_values():
    # vs scipy.stats.binomtest(8, 10, 0.5, alternative=...)
    assert approx(S.binom_exact_p(8, 10, 0.5, "greater"), 0.0546875)
    assert approx(S.binom_exact_p(8, 10, 0.5, "less"), 0.9892578125)
    # a "greater" tail against a chance null rejects hard when all succeed
    assert S.binom_exact_p(10, 10, 0.5, "greater") < 1e-2


def test_binom_one_sided_halves_borderline():
    # the whole point: a supported-side effect that is NOT two-sided significant
    # becomes one-sided significant. 29/46 vs 0.5 is p~0.104 two-sided.
    two = S.binom_exact_p(29, 46, 0.5)
    grt = S.binom_exact_p(29, 46, 0.5, "greater")
    assert two > 0.05          # two-sided fails
    assert grt < two           # one-sided is the smaller (upper) tail
    # and the reverse direction on the SAME data is nowhere near significant
    assert S.binom_exact_p(29, 46, 0.5, "less") > 0.9


def test_binom_reverse_means_differently():
    # two-sided is relabel-invariant: 29/46 and 17/46 give the same p...
    assert approx(S.binom_exact_p(29, 46, 0.5), S.binom_exact_p(17, 46, 0.5))
    # ...but one-sided "greater" separates them (the reverse now means something)
    assert S.binom_exact_p(29, 46, 0.5, "greater") \
        != S.binom_exact_p(17, 46, 0.5, "greater")


def test_binom_alternative_validation():
    import pytest
    with pytest.raises(ValueError):
        S.binom_exact_p(5, 10, 0.5, "bogus")


# ---- Fisher exact (two-sided) --------------------------------------------

def test_fisher_known_value():
    # scipy.stats.fisher_exact([[8,2],[1,5]]) -> 0.03497
    assert approx(S.fisher_exact_2x2(8, 10, 1, 6), 0.03497)


def test_fisher_identical_rows_is_one():
    assert approx(S.fisher_exact_2x2(5, 10, 5, 10), 1.0, 1e-9)


def test_fisher_strong_difference_significant():
    assert S.fisher_exact_2x2(18, 20, 2, 20) < 0.001


# ---- Fisher exact (one-sided) --------------------------------------------

def test_fisher_one_sided_known_values():
    # vs scipy.stats.fisher_exact([[8,2],[1,5]], alternative=...)
    assert approx(S.fisher_exact_2x2(8, 10, 1, 6, "greater"), 0.0244755, 1e-5)
    assert approx(S.fisher_exact_2x2(8, 10, 1, 6, "less"), 0.9991259, 1e-5)


def test_fisher_one_sided_direction_separates():
    # p1 > p2: "greater" is the smaller tail, "less" is large
    assert S.fisher_exact_2x2(8, 10, 1, 6, "greater") \
        < S.fisher_exact_2x2(8, 10, 1, 6, "less")


def test_fisher_alternative_validation():
    import pytest
    with pytest.raises(ValueError):
        S.fisher_exact_2x2(8, 10, 1, 6, "bogus")


# ---- exact k-category tests (chi-square removed 2026-08-11) --------------

def test_chi2_sf_critical_values():
    assert approx(S.chi2_sf(3.84146, 1), 0.05)
    assert approx(S.chi2_sf(5.99146, 2), 0.05)
    assert approx(S.chi2_sf(11.0705, 5), 0.05)
    assert S.chi2_sf(0.0, 3) == 1.0


def test_chi2_test_wrappers_are_gone():
    # 2026-08-11: no benchmark label may come from an asymptotic test, so the
    # chi-square GOF / contingency wrappers were removed outright.
    assert not hasattr(S, "chi2_gof")
    assert not hasattr(S, "chi2_contingency")


def test_multinomial_gof_exact():
    # uniform observed -> p = 1
    assert approx(S.multinomial_gof_exact([10, 10, 10])["p"], 1.0)
    # a known small case; exact p is deterministic (no Monte-Carlo)
    r = S.multinomial_gof_exact([8, 1, 1])
    assert r["method"] == "exact" and 0.0 < r["p"] < 0.05
    assert r["p"] == S.multinomial_gof_exact([8, 1, 1])["p"]  # deterministic


def test_gof_is_always_exact_even_when_cells_are_ample():
    # the old chooser flipped to chi-square once every expected cell hit 5;
    # both of these must now report the exact method.
    assert S.multinomial_gof([8, 1, 1])["method"] == "exact"
    assert S.multinomial_gof([30, 30, 30])["method"] == "exact"
    assert S.contingency_test([[20, 20, 20], [20, 20, 20]])["method"] == "exact"


def test_exact_enumeration_raises_instead_of_approximating():
    # an infeasible table must surface as a design problem, never silently fall
    # back to the asymptotic test
    import pytest
    with pytest.raises(S.ExactTestTooLarge):
        S.multinomial_gof([2000] * 6)


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


def test_contingency_homogeneity_via_exact_ffh():
    same = S.contingency_test([[20, 20, 20], [20, 20, 20]])
    assert approx(same["p"], 1.0)
    diff = S.contingency_test([[40, 5, 5], [5, 5, 40]])
    assert diff["p"] < 0.001


# ---- verdict --------------------------------------------------------------

def test_significance_verdict():
    assert S.significance_verdict(0.01, 50) == "significant"
    assert S.significance_verdict(0.20, 50) == "insufficient"
    assert S.significance_verdict(0.01, 5) == "insufficient"   # n below min
    assert S.significance_verdict(None, 50) == "insufficient"
    assert S.significance_verdict(0.049, 10) == "significant"   # boundary n
