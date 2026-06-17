"""Tests for core enumeration, feasibility, and realization."""

from __future__ import annotations

from temporal_hypo.generation import cores
from temporal_hypo.generation.cores import (
    ViableCore,
    enumerate_group,
    feasible_polarities,
    realize,
)
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.templates import load_groups

from .conftest import make_db


def _core(mode, answer_type, **kw):
    base = dict(
        group_id="G", family="f", primitive="precedes", level="vaccine",
        answer_type=answer_type, mode=mode, events=("A", "B"),
        vaccines=("Pfizer",), cohort_ids=[1], report_id=None, computable=True,
        natural_verdict="supported",
    )
    base.update(kw)
    return ViableCore(**base)


# -- realize: directional BOOL --------------------------------------------

def test_dir_bool_flip_changes_orientation_not_data():
    core = _core("dir_bool", "BOOL", proportion=0.7, n=20, k=14)
    assert feasible_polarities(core) == {"supported", "refuted"}

    sup = realize(core, "supported")
    assert sup.gold_verdict == "supported"
    assert sup.events_assigned == ("A", "B")
    assert abs(sup.gold_proportion - 0.7) < 1e-9

    ref = realize(core, "refuted")
    assert ref.gold_verdict == "refuted"
    assert ref.events_assigned == ("B", "A")     # flipped orientation
    assert abs(ref.gold_proportion - 0.3) < 1e-9
    assert ref.flip_kind == "direction"

    # the underlying core data is untouched by realization
    assert core.events == ("A", "B")
    assert core.proportion == 0.7


def test_dir_bool_tie_is_insufficient_only():
    core = _core("dir_bool", "BOOL", proportion=0.5, n=20, k=10)
    assert feasible_polarities(core) == {"insufficient"}


# -- realize: PROP value flip ----------------------------------------------

def test_prop_value_flip():
    core = _core("prop_precedes", "PROP", proportion=0.70, n=30, k=21)
    sup = realize(core, "supported")
    assert sup.gold_verdict == "supported"
    assert sup.p_value == 70
    ref = realize(core, "refuted")
    assert ref.gold_verdict == "refuted"
    assert abs(ref.p_value / 100 - 0.70) > 0.05    # off by > 5pp
    assert ref.flip_kind == "value"


# -- realize: symmetric BOOL polarity fixed by data ------------------------

def test_symmetric_bool_polarity_by_data():
    hi = _core("sym_bool_cooccurs", "BOOL", proportion=0.7, n=20, k=14)
    lo = _core("sym_bool_cooccurs", "BOOL", proportion=0.3, n=20, k=6)
    assert feasible_polarities(hi) == {"supported"}
    assert feasible_polarities(lo) == {"refuted"}
    assert realize(hi, "supported").gold_verdict == "supported"
    assert realize(lo, "refuted").gold_verdict == "refuted"


# -- realize: multi direction swaps vaccines -------------------------------

def test_multi_dir_swaps_vaccines():
    core = _core("multi_dir_precedes", "CHOICE", level="multi",
                 vaccines=("Pfizer", "Moderna"), proportion=0.7, n=20, k=14,
                 proportion2=0.5, n2=20, k2=10)
    assert feasible_polarities(core) == {"supported", "refuted"}
    sup = realize(core, "supported")
    assert sup.gold_verdict == "supported"
    assert sup.vaccines_assigned == ("Pfizer", "Moderna")  # higher cohort first
    ref = realize(core, "refuted")
    assert ref.gold_verdict == "refuted"
    assert ref.vaccines_assigned == ("Moderna", "Pfizer")  # swapped
    assert ref.flip_kind == "vaccine_swap"


def test_multi_differ_polarity_by_data():
    differ = _core("multi_differ_precedes", "BOOL", level="multi",
                   vaccines=("Pfizer", "Moderna"), proportion=0.8, n=20, k=16,
                   proportion2=0.5, n2=20, k2=10, natural_verdict="supported")
    same = _core("multi_differ_precedes", "BOOL", level="multi",
                 vaccines=("Pfizer", "Moderna"), proportion=0.55, n=20, k=11,
                 proportion2=0.5, n2=20, k2=10, natural_verdict="refuted")
    assert feasible_polarities(differ) == {"supported"}
    assert feasible_polarities(same) == {"refuted"}


# -- enumeration integration: n>=10 gating ---------------------------------

def test_enumeration_respects_min_n():
    # X before Y in 8 reports, Y before X in 4 -> 12 ordered (>=10) -> computable
    reports = []
    for i in range(8):
        reports.append((i + 1, "Pfizer", [["X"], ["Y"]]))
    for i in range(4):
        reports.append((100 + i, "Pfizer", [["Y"], ["X"]]))
    # Z appears with X in only 5 reports -> pair (X,Z) below threshold
    for i in range(5):
        reports.append((200 + i, "Pfizer", [["X"], ["Z"]]))
    conn = make_db(reports)
    index = CorpusIndex.load(conn)
    groups = load_groups()

    cs = enumerate_group(index, groups["P-V1"])
    by_events = {frozenset(c.events): c for c in cs}

    xy = by_events[frozenset({"X", "Y"})]
    assert xy.computable
    assert xy.n == 12
    assert abs(xy.proportion - 8 / 12) < 1e-9   # canonical (X,Y) order

    xz = by_events[frozenset({"X", "Z"})]
    assert not xz.computable                     # only 5 ordered, below 10
    conn.close()


def test_report_cores_are_deterministic_no_ci():
    reports = [(1, "Pfizer", [["X"], ["Y"], ["Z"]])]
    conn = make_db(reports)
    index = CorpusIndex.load(conn)
    groups = load_groups()
    cs = enumerate_group(index, groups["P-R1"])
    assert cs
    c = cs[0]
    assert c.report_id == 1
    assert c.n is None            # deterministic single observation, no CI
    inst = realize(c, "supported")
    assert inst.ci is None
    conn.close()
