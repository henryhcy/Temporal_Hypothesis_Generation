"""Tests for the shared minimum-n gate (temporal_hypo.core.min_n)."""

import pytest

from temporal_hypo.core import min_n as M


def test_family_floors():
    assert M.family_floor("pairwise") == 20
    assert M.family_floor("co_occurs") == 20
    assert M.family_floor("sequence") == 5       # strict order / orderable denom
    assert M.family_floor("first_last") == 30
    with pytest.raises(ValueError):
        M.family_floor("nope")


def test_floor_two_category():
    assert M.min_n_gate(20, "pairwise").testable      # at floor
    assert not M.min_n_gate(19, "pairwise").testable  # below floor
    assert M.min_n_gate(5, "sequence").testable        # sequence floor is 5
    assert not M.min_n_gate(4, "sequence").testable
    assert M.min_n_gate(30, "first_last").testable
    assert not M.min_n_gate(29, "first_last").testable
    assert not M.min_n_gate(None, "pairwise").testable


def test_two_cohort_floor():
    assert M.min_n_gate(25, "pairwise", n2=25).testable
    g = M.min_n_gate(25, "pairwise", n2=15)
    assert not g.testable and "n2=15" in g.reason


def test_gate_is_floor_only():
    # sparse distributions no longer gate to insufficient -- exact test handles them
    assert M.min_n_gate(30, "sequence").testable
    assert M.min_n_gate(30, "first_last", n2=30).testable


def test_uses_exact_flags_sparse_tables():
    # 1xk goodness-of-fit: exact when any expected cell (total/k) < 5
    assert M.uses_exact([5, 5, 4])                 # exp 4.67
    assert not M.uses_exact([10, 10, 10])          # exp 10
    assert M.uses_exact([4, 4, 4, 4, 4, 4])        # sum 24 over 6 -> exp 4
    assert not M.uses_exact([5, 5, 5, 5, 5, 5])    # exp 5
    # 2xk homogeneity: exact when a margin-implied expected cell < 5
    assert M.uses_exact([[1, 1, 28], [1, 1, 28]])
    assert not M.uses_exact([[10, 10, 10], [10, 10, 10]])


def test_reason_is_populated():
    assert M.min_n_gate(10, "pairwise").reason
    assert M.min_n_gate(50, "pairwise").reason == "testable"
