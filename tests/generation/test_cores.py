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
        group_id="G", family="pairwise", primitive="precedes", level="vaccine",
        answer_type=answer_type, mode=mode, events=("A", "B"),
        vaccines=("Pfizer",), cohort_ids=[1], report_id=None, computable=True,
        natural_verdict="supported",
    )
    base.update(kw)
    return ViableCore(**base)


# -- realize: directional BOOL --------------------------------------------

def test_dir_bool_flip_changes_orientation_not_data():
    # 16/20 (one-sided p = 0.0059) is decisive; 14/20 would NOT be (p = 0.058),
    # which is the whole point of the 2026-08-11 gold-label flip.
    core = _core("dir_bool", "BOOL", proportion=0.8, n=20, k=16)
    assert feasible_polarities(core) == {"supported", "refuted"}

    sup = realize(core, "supported")
    assert sup.gold_verdict == "supported"
    assert sup.events_assigned == ("A", "B")
    assert abs(sup.gold_proportion - 0.8) < 1e-9

    ref = realize(core, "refuted")
    assert ref.gold_verdict == "refuted"
    assert ref.events_assigned == ("B", "A")     # flipped orientation
    assert abs(ref.gold_proportion - 0.2) < 1e-9
    assert ref.flip_kind == "direction"

    # the underlying core data is untouched by realization
    assert core.events == ("A", "B")
    assert core.proportion == 0.8


def test_a_near_coinflip_majority_is_no_longer_shippable():
    # THE case the flip exists for: 14/20 = 0.7 reads "supported" under the
    # retired point-estimate rule, but one-sided p = 0.058 settles nothing.
    core = _core("dir_bool", "BOOL", proportion=0.7, n=20, k=14)
    assert feasible_polarities(core) == {"insufficient"}
    assert realize(core, "supported").gold_verdict == "insufficient"


def test_dir_bool_tie_is_insufficient_only():
    core = _core("dir_bool", "BOOL", proportion=0.5, n=20, k=10)
    assert feasible_polarities(core) == {"insufficient"}


# -- realize: PROP value flip ----------------------------------------------

# -- realize: symmetric BOOL polarity fixed by data ------------------------

def test_symmetric_bool_polarity_by_data():
    # symmetric claim: nothing to flip, so a decisive core supplies exactly one
    # class -- and it must be DECISIVE (16/20, not 14/20) to supply any.
    hi = _core("sym_bool_cooccurs", "BOOL", family="co_occurs",
               proportion=0.8, n=20, k=16)
    lo = _core("sym_bool_cooccurs", "BOOL", family="co_occurs",
               proportion=0.2, n=20, k=4)
    assert feasible_polarities(hi) == {"supported"}
    assert feasible_polarities(lo) == {"refuted"}
    assert realize(hi, "supported").gold_verdict == "supported"
    assert realize(lo, "refuted").gold_verdict == "refuted"


# -- realize: multi direction swaps vaccines -------------------------------

def test_multi_dir_swaps_vaccines():
    # Fisher one-sided on 16/20 vs 4/20 is p = 0.0002; 14-vs-10 would not clear.
    core = _core("multi_dir_precedes", "CHOICE", level="multi",
                 vaccines=("Pfizer", "Moderna"), proportion=0.8, n=20, k=16,
                 proportion2=0.2, n2=20, k2=4)
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
    # "differ" is non-directional: significant can only mean supported and
    # not-significant can never mean refuted, so three_decision tags these
    # non_directional and they can ship NOTHING. These are exactly the multi
    # groups the 2026-07-28 roster decision retires.
    assert feasible_polarities(differ) == {"insufficient"}
    assert feasible_polarities(same) == {"insufficient"}


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


# -- negation: the orientation operator for symmetric claims ----------------

def test_negation_lets_a_symmetric_core_supply_either_class():
    """decisions.md 2026-08-11: C-V1/C-V3 are directional but NOT slot-orientable.

    Swapping A and B changes nothing, so the plain wording's class is fixed by the
    data. Negating the claim makes the other tail the claim tail, which is exactly
    what flipping the event order does for P-V1.
    """
    from temporal_hypo.generation.templates import load_groups
    groups = load_groups()
    # 4/20 co-existence: significantly BELOW 0.5, so the plain claim is refuted
    core = _core("sym_bool_cooccurs", "BOOL", family="co_occurs",
                 group_id="C-V1", proportion=0.2, n=20, k=4)

    # without the group, only the class the data falls on is offered
    assert feasible_polarities(core) == {"refuted"}
    # with it, negated wording unlocks the other class
    assert feasible_polarities(core, groups["C-V1"]) == {"supported", "refuted"}

    plain = realize(core, "refuted")
    assert plain.gold_verdict == "refuted" and plain.negated is False

    neg = realize(core, "supported")
    assert neg.gold_verdict == "supported" and neg.negated is True


def test_negation_is_unavailable_where_the_yaml_has_no_negated_wording():
    # P-V1 is slot-orientable, so it never needs negation and authors none.
    from temporal_hypo.generation.templates import load_groups, supports_negation
    groups = load_groups()
    assert supports_negation(groups["C-V1"]) and supports_negation(groups["C-V3"])
    assert not supports_negation(groups["P-V1"])


def test_negation_is_minimised_not_configurable():
    # Negation applies wherever the template YAML provides it -- there is no off
    # switch, because switching it off just costs C-V1/C-V3 894 items. What callers
    # control is HOW MUCH: prefer the class the data already falls on.
    from temporal_hypo.generation.templates import load_groups
    g = load_groups()["C-V1"]
    low = _core("sym_bool_cooccurs", "BOOL", family="co_occurs",
                group_id="C-V1", proportion=0.2, n=20, k=4)      # data -> refuted
    assert realize(low, "refuted").negated is False    # plain wording suffices
    assert realize(low, "supported").negated is True   # negate only when needed
    assert feasible_polarities(low, g) == {"supported", "refuted"}
