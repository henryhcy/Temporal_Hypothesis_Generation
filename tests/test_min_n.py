"""Tests for the shared minimum-n gate (temporal_hypo.core.min_n)."""

import pytest

from temporal_hypo.core import min_n as M


def test_family_floors():
    # 2026-08-11: pairwise and first/last align with the enumeration viability
    # floor of 10; sequence keeps its own 5 (thinner orderable denominator).
    assert M.family_floor("pairwise") == 10
    assert M.family_floor("co_occurs") == 10
    assert M.family_floor("sequence") == 5       # strict order / orderable denom
    assert M.family_floor("first_last") == 10
    with pytest.raises(ValueError):
        M.family_floor("nope")


def test_floor_two_category():
    assert M.min_n_gate(10, "pairwise").testable      # at floor
    assert not M.min_n_gate(9, "pairwise").testable   # below floor
    assert M.min_n_gate(5, "sequence").testable        # sequence floor is 5
    assert not M.min_n_gate(4, "sequence").testable
    assert M.min_n_gate(10, "first_last").testable
    assert not M.min_n_gate(9, "first_last").testable
    assert not M.min_n_gate(None, "pairwise").testable


def test_two_cohort_floor():
    assert M.min_n_gate(25, "pairwise", n2=25).testable
    g = M.min_n_gate(25, "pairwise", n2=8)
    assert not g.testable and "n2=8" in g.reason


def test_gate_is_floor_only():
    # sparse distributions no longer gate to insufficient -- exact test handles them
    assert M.min_n_gate(30, "sequence").testable
    assert M.min_n_gate(30, "first_last", n2=30).testable


def test_expected_cell_chooser_is_gone():
    # 2026-08-11: every test is exact at every n, so there is nothing to choose
    # between and no cell-adequacy guard. These names must not come back.
    assert not hasattr(M, "uses_exact")
    assert not hasattr(M, "MIN_EXPECTED")


def test_reason_is_populated():
    assert M.min_n_gate(10, "pairwise").reason
    assert M.min_n_gate(50, "pairwise").reason == "testable"
