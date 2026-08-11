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

def test_both_ways_doubles_the_decisive_half():
    # per_core=2 (the default): every decisive core is posed BOTH ways, so
    # supported = refuted = S rather than S // 2.
    cores = [_core(i, 0.8 if i % 2 else 0.2, 20) for i in range(100)]
    sel = balance_group(cores, "G", seed=1)
    assert sel.S == 100
    assert sel.targets == {"supported": 100, "refuted": 100, "insufficient": 100}
    assert sel.counts["supported"] == sel.counts["refuted"] == 100
    assert sel.mirror_pairs == 100
    # no insufficient cores exist here, so that third is flagged rather than
    # silently shrinking the other two
    assert sel.counts["insufficient"] == 0
    assert sel.under_target["insufficient"] is True


def test_one_way_halves_it_and_makes_no_mirror_pairs():
    cores = [_core(i, 0.8 if i % 2 else 0.2, 20) for i in range(100)]
    sel = balance_group(cores, "G", seed=1, per_core=1)
    assert sel.targets["supported"] == 50
    assert sel.counts["supported"] == sel.counts["refuted"] == 50
    assert sel.mirror_pairs == 0
    ids = [id(c) for c, _, _ in sel.chosen]
    assert len(ids) == len(set(ids))       # each core used at most once


def test_a_core_is_never_reused_within_one_class():
    # both-ways allows a core in supported AND refuted, never twice in the same one
    cores = [_core(i, 0.8 if i % 2 else 0.2, 20) for i in range(60)]
    sel = balance_group(cores, "G", seed=3)
    seen = [(id(c), pol) for c, pol, _ in sel.chosen]
    assert len(seen) == len(set(seen))


def test_reorientation_is_minimised_when_one_way():
    # 40 cores whose data says supported, 60 whose data says refuted. One-way
    # targets are 50/50, so exactly 10 supported must be borrowed from the
    # refuted side and nothing else needs re-orienting.
    cores = ([_core(i, 0.8, 20) for i in range(40)]
             + [_core(100 + i, 0.2, 20) for i in range(60)])
    sel = balance_group(cores, "G", seed=5, per_core=1)
    assert sel.counts["supported"] == 50 and sel.counts["refuted"] == 50
    assert sel.reoriented == 10


def test_both_ways_forces_exactly_one_reorientation_per_pair():
    # posing every core both ways means exactly one of the two instances is
    # re-oriented, so `reoriented` == S. For C-V1/C-V3 that is what pins the
    # negated share at 50% rather than the one-way minimum of 39%.
    cores = ([_core(i, 0.8, 20) for i in range(40)]
             + [_core(100 + i, 0.2, 20) for i in range(60)])
    sel = balance_group(cores, "G", seed=5)
    assert sel.counts["supported"] == sel.counts["refuted"] == 100
    assert sel.reoriented == 100


def test_insufficient_third_spreads_over_subtypes():
    # 30 decisive -> per-class target 15; insufficient supply is deliberately
    # lopsided, so the even split must spill from the short sub-types to the deep one
    decisive = [_core(i, 0.8 if i % 2 else 0.2, 20) for i in range(30)]
    underpowered = [_core(500 + i, 0.55, 20) for i in range(40)]     # not decisive
    sparse = [_core(700 + i, 1.0, 6) for i in range(3)]              # below floor
    sel = balance_group(decisive + underpowered + sparse, "G", seed=7, per_core=1)

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


def test_mirror_pairs_share_a_core_so_a_split_can_keep_them_together():
    from temporal_hypo.generation.instances import core_id
    from temporal_hypo.generation.cores import realize
    cores = [_core(0, 0.8, 20)]
    sel = balance_group(cores, "G", seed=0)
    ids = {core_id(realize(c, pol)) for c, pol, _ in sel.chosen}
    assert len(sel.chosen) == 2 and len(ids) == 1
