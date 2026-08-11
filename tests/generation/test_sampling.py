"""Tests for equal-thirds verdict balancing, banding, and sub-type spread."""

from __future__ import annotations

from temporal_hypo.generation.cores import ViableCore
from temporal_hypo.generation.sampling import (
    _water_fill,
    assign_bands,
    balance_group,
)


def _core(idx, proportion, n, mode="dir_bool"):
    return ViableCore(
        group_id="G", family="pairwise", primitive="precedes", level="vaccine",
        answer_type="BOOL", mode=mode, events=(f"E{idx}", "B"),
        vaccines=("Pfizer",), cohort_ids=[1], report_id=None, computable=True,
        natural_verdict="supported", proportion=proportion, n=n,
        k=round(proportion * n),
    )


def test_bands_partition_by_n():
    cores = [_core(i, 0.7, n) for i, n in enumerate([10, 12, 15, 40, 80, 200])]
    band = assign_bands(cores)
    labels = {band[id(c)] for c in cores}
    assert labels <= {"low", "medium", "high"}
    # smallest n is low, largest is high
    assert band[id(cores[0])] == "low"
    assert band[id(cores[-1])] == "high"


# ---- equal thirds ---------------------------------------------------------

def test_supported_and_refuted_are_equal_and_sized_from_S():
    # 100 decisive cores (16/20 or 4/20, both significant) -> S = 100, so each
    # class targets S // 2 = 50. No insufficient cores exist here, so that third
    # is flagged under-target rather than silently shrinking the other two.
    cores = [_core(i, 0.8 if i % 2 else 0.2, 20) for i in range(100)]
    sel = balance_group(cores, "G", seed=1)
    assert sel.S == 100
    assert sel.targets == {"supported": 50, "refuted": 50, "insufficient": 50}
    assert sel.counts["supported"] == sel.counts["refuted"] == 50
    assert sel.counts["insufficient"] == 0
    assert sel.under_target["insufficient"] is True


def test_no_core_is_used_as_both_supported_and_refuted():
    """The 07-28 rule: never ship the A->B / B->A mirror of one case both ways."""
    cores = [_core(i, 0.8 if i % 2 else 0.2, 20) for i in range(60)]
    sel = balance_group(cores, "G", seed=3)
    ids = [id(c) for c, _, _ in sel.chosen]
    assert len(ids) == len(set(ids))


def test_reorientation_is_minimised():
    # 40 cores whose data says supported, 60 whose data says refuted. Targets are
    # 50/50, so 10 of the supported class must be borrowed from the refuted side
    # and nothing else needs re-orienting.
    cores = ([_core(i, 0.8, 20) for i in range(40)]
             + [_core(100 + i, 0.2, 20) for i in range(60)])
    sel = balance_group(cores, "G", seed=5)
    assert sel.counts["supported"] == 50 and sel.counts["refuted"] == 50
    assert sel.reoriented == 10


def test_insufficient_third_spreads_over_subtypes():
    # 30 decisive -> per-class target 15; insufficient supply is deliberately
    # lopsided, so the even split must spill from the short sub-types to the deep one
    decisive = [_core(i, 0.8 if i % 2 else 0.2, 20) for i in range(30)]
    underpowered = [_core(500 + i, 0.55, 20) for i in range(40)]     # not decisive
    sparse = [_core(700 + i, 1.0, 6) for i in range(3)]              # below floor
    sel = balance_group(decisive + underpowered + sparse, "G", seed=7)

    assert sel.targets["insufficient"] == 15
    assert sel.counts["insufficient"] == 15
    assert sel.subtype_counts.get("sparse") == 3        # only 3 exist -> take all
    assert sel.subtype_counts.get("underpowered") == 12  # the rest spills here


def test_water_fill_is_even_then_spills():
    # even split when everyone can pay
    assert _water_fill({"a": 10, "b": 10, "c": 10}, 9) == {"a": 3, "b": 3, "c": 3}
    # a short pool takes all it has and the remainder goes to the others
    assert _water_fill({"a": 1, "b": 10, "c": 10}, 9) == {"a": 1, "b": 4, "c": 4}
    # cannot exceed total capacity
    assert sum(_water_fill({"a": 2, "b": 2}, 99).values()) == 4


def test_optional_hard_cap_still_applies():
    cores = [_core(i, 0.8 if i % 2 else 0.2, 20) for i in range(500)]
    sel = balance_group(cores, "G", t=60, seed=2)
    assert sel.targets == {"supported": 20, "refuted": 20, "insufficient": 20}
