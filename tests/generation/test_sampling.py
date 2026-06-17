"""Tests for verdict balancing, banding, and the insufficient cap."""

from __future__ import annotations

from temporal_hypo.generation.cores import ViableCore
from temporal_hypo.generation.sampling import (
    INSUFFICIENT_FRAC,
    assign_bands,
    balance_group,
)


def _core(idx, proportion, n, mode="dir_bool"):
    return ViableCore(
        group_id="G", family="f", primitive="precedes", level="vaccine",
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


def test_insufficient_capped_and_targets():
    # 200 flippable directional cores -> plenty of supported/refuted, no insufficient
    cores = [_core(i, 0.7 if i % 2 else 0.3, 20 + i) for i in range(200)]
    sel = balance_group(cores, "G", t=100, seed=1)
    assert sel.counts["supported"] == 45
    assert sel.counts["refuted"] == 45
    # no genuinely-insufficient cores available -> insufficient under target
    assert sel.counts["insufficient"] <= round(100 * INSUFFICIENT_FRAC)
    assert sel.under_target["insufficient"] is True
    total = sum(sel.counts.values())
    assert total <= 100


def test_under_target_supported_flag():
    # only 5 supported-feasible cores (all symmetric, prop>0.5)
    cores = [_core(i, 0.7, 20, mode="sym_bool_cooccurs") for i in range(5)]
    sel = balance_group(cores, "G", t=100, seed=0)
    assert sel.counts["supported"] == 5
    assert sel.under_target["supported"] is True


def test_chosen_within_target_cap():
    cores = [_core(i, 0.7 if i % 2 else 0.3, 20 + i) for i in range(500)]
    sel = balance_group(cores, "G", t=60, seed=2)
    assert len(sel.chosen) <= 60
    assert sel.targets == {"supported": 27, "refuted": 27, "insufficient": 6}
