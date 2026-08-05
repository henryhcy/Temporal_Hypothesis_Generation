"""Tests for the three-decision verdict labeler (temporal_hypo.core.verdict)."""

from __future__ import annotations

from temporal_hypo.core import verdict as V
from temporal_hypo.core.significance import binom_exact_p


# ---- the three decisions --------------------------------------------------

def test_supported_requires_significance_in_the_claim_direction():
    d = V.three_decision(0.01, 0.99, 50, "pairwise")
    assert d.verdict == V.SUPPORTED and d.subtype is None and d.decisive


def test_refuted_requires_significance_in_the_OPPOSITE_direction():
    d = V.three_decision(0.99, 0.01, 50, "pairwise")
    assert d.verdict == V.REFUTED and d.decisive


def test_not_significant_either_way_is_insufficient_never_refuted():
    # the whole point of the three-decision rule: failing to reject H0 is NOT
    # evidence for its negation, so this may not come back `refuted`.
    d = V.three_decision(0.30, 0.75, 50, "pairwise")
    assert d.verdict == V.INSUFFICIENT and d.subtype == V.UNDERPOWERED


def test_a_single_claim_tail_cannot_separate_refuted_from_insufficient():
    # identical p_claim, opposite tails -> different verdicts. This is why both
    # tails are required inputs.
    assert V.three_decision(0.9, 0.01, 50, "pairwise").verdict == V.REFUTED
    assert V.three_decision(0.9, 0.30, 50, "pairwise").verdict == V.INSUFFICIENT


def test_tails_are_mutually_exclusive_at_alpha_below_half():
    # both tails of a real one-sided pair can never both clear alpha, so the
    # order of the supported/refuted checks cannot matter.
    for k in range(0, 41):
        lo = binom_exact_p(k, 40, 0.5, alternative="less")
        hi = binom_exact_p(k, 40, 0.5, alternative="greater")
        assert not (lo < V.ALPHA and hi < V.ALPHA)


# ---- insufficient sub-types ----------------------------------------------

def test_subtype_sparse_below_the_family_floor():
    d = V.three_decision(0.001, 0.999, 15, "pairwise")   # floor is 20
    assert d.verdict == V.INSUFFICIENT and d.subtype == V.SPARSE
    assert "20" in d.gate


def test_subtype_not_locatable_at_zero_n():
    d = V.three_decision(None, None, 0, "pairwise")
    assert d.verdict == V.INSUFFICIENT and d.subtype == V.NOT_LOCATABLE
    d2 = V.three_decision(0.01, 0.99, 40, "pairwise", n2=0)
    assert d2.subtype == V.NOT_LOCATABLE   # the second cohort is empty


def test_subtype_unknown_when_n_was_dropped_below_the_viability_floor():
    d = V.three_decision(None, None, None, "pairwise")
    assert d.verdict == V.INSUFFICIENT and d.subtype is None


def test_non_directional_modes_are_flagged_not_forced():
    d = V.three_decision(None, None, 50, "sequence")
    assert d.verdict == V.INSUFFICIENT and d.subtype == V.NON_DIRECTIONAL


# ---- the gate is the SHARED family floor, not a blanket 10 ---------------

def test_sequence_floor_is_5_so_small_exact_tests_are_no_longer_gated_out():
    # 07_significance_findings.md sec.5: 114 sequence cores had p < 0.05 but were
    # blocked by the old blanket n >= 10. The family floor is 5.
    d = V.three_decision(0.001, 0.999, 6, "sequence")
    assert d.verdict == V.SUPPORTED


def test_first_last_floor_is_30_which_is_stricter_than_the_old_blanket():
    assert V.three_decision(0.001, 0.999, 25, "first_last").subtype == V.SPARSE
    assert V.three_decision(0.001, 0.999, 30, "first_last").verdict == V.SUPPORTED


def test_two_cohort_gate_applies_to_both_cohorts():
    assert V.three_decision(0.001, 0.9, 40, "pairwise", n2=40).verdict == V.SUPPORTED
    assert V.three_decision(0.001, 0.9, 40, "pairwise", n2=15).subtype == V.SPARSE


# ---- report-level ---------------------------------------------------------

def test_report_level_is_deterministic_and_keeps_its_verdict():
    d = V.deterministic("refuted")
    assert d.verdict == "refuted" and d.subtype == V.DETERMINISTIC
    assert d.p_claim is None and d.p_opposite is None


# ---- alpha ----------------------------------------------------------------

def test_alpha_is_0_05_per_side():
    assert V.ALPHA == 0.05
    assert V.three_decision(0.049, 0.95, 50, "pairwise").verdict == V.SUPPORTED
    assert V.three_decision(0.051, 0.95, 50, "pairwise").verdict == V.INSUFFICIENT
