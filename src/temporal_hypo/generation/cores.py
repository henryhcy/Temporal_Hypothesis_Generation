"""Viable-core enumeration and instance realization -- the correctness heart.

This module pins, per template group, exactly which statistic and verdict rule
produces the gold label (the "handler table", ``MODE_BY_GROUP``), enumerates the
viable factual cores from the corpus, and realizes supported/refuted/insufficient
instances from them.

Two-stage design:

1. ``enumerate_group`` returns a list of ``ViableCore`` -- the statistical
   population for a group, each with a canonical-orientation natural verdict.
   Part A (distribution report) reads these directly.
2. ``feasible_polarities`` / ``realize`` turn a core into a concrete
   ``InstanceFacts`` (oriented slot values + recomputed gold) for a requested
   polarity. Part B (pilot dataset) drives the 45/45/10 balance through these.

The gold verdict is always recomputed on the realized assertion -- never
hardcoded -- so it cannot drift from the claim text.

**Which rule produces it changed on 2026-08-11.** For cohort-level claims the
shipped label is now the THREE-DECISION verdict (``core.verdict.three_decision``,
reached via ``cohort_decision`` here): supported and refuted both require
significance, in opposite directions. The retired point-estimate rule
(``aggregation.bool_verdict`` and friends) called anything off 0.5 a verdict, so
an 11/20 coin flip shipped as ``supported`` and a framework answering
``insufficient`` -- the correct answer -- was scored wrong.

The ``_realize_*`` functions below still compute a point estimate, because the
proportion, CI and effect size are all reported alongside the label; their
``verdict=`` argument is superseded in ``realize``. Report-level cores are exact
single observations with no test, so they keep their deterministic verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from temporal_hypo.core.aggregation import (
    bool_verdict,
    differ_verdict,
    direction_verdict,
)
from temporal_hypo.core.min_n import min_n_gate
from temporal_hypo.generation import corpus
from temporal_hypo.generation.confidence import (
    Z_95,
    cohens_h,
    confidence_tag,
    ci_width,
    wilson_ci,
    wilson_newcombe_diff_ci,
)
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.templates import Group, supports_negation
from temporal_hypo.generation.vaccines import VACCINES, VACCINE_PAIRS

# Provisional enumeration breadth (logged pilot knobs; see 04_corpus_survey).
K_PAIR = 25
K_TRIPLE = 16
MAX_REPORT_CORES = 300

# Locked viability threshold (mirrors corpus._MIN_N).
_MIN_N = 10

# Modes whose cores are event TRIPLES rather than pairs.
_VACCINE_TRIPLE_MODES = {
    "seq_bool", "modal_choice",
    "first_choice", "last_choice", "first_bool",
}
_MULTI_TRIPLE_MODES = {
    "multi_differ_sequence", "multi_same_modal_order",
    "multi_same_first", "multi_differ_first", "multi_dir_first",
}

# Per-group statistic + verdict mode. The single source of truth mapping each
# of the 30 groups to its gold computation.
MODE_BY_GROUP: dict[str, str] = {
    # pairwise -- precedes
    "P-R1": "rep_dir_bool",
    "P-R2": "rep_dir_choice",
    "P-V1": "dir_bool",
    "P-V3": "dir_choice",
    "P-M1": "multi_differ_precedes",
    "P-M2": "multi_dir_precedes",
    # pairwise -- co_occurs
    "C-R1": "rep_sym_bool",
    "C-V1": "sym_bool_cooccurs",
    "C-V3": "sym_bool_cooccurs",
    "C-M1": "multi_differ_cooccurs",
    "C-M2": "multi_dir_cooccurs",
    # sequence
    "S-R1": "rep_seq_bool",
    "S-V1": "seq_bool",
    "S-V3": "modal_choice",
    "S-M1": "multi_differ_sequence",
    "S-M3": "multi_same_modal_order",
    # first / last
    "F-R1": "rep_first_choice",
    "F-R2": "rep_last_choice",
    "F-R3": "rep_first_bool",
    "F-V1": "first_choice",
    "F-V2": "last_choice",
    "F-V3": "first_bool",
    "F-M1": "multi_same_first",
    "F-M2": "multi_differ_first",
    "F-M3": "multi_dir_first",
}


@dataclass
class ViableCore:
    group_id: str
    family: str
    primitive: str
    level: str
    answer_type: str
    mode: str
    events: tuple[str, ...]          # canonical event order (A, B[, C])
    vaccines: tuple[str, ...]        # () | (v,) | (v1, v2)
    cohort_ids: list[int]            # statistical denominator (or [report_id])
    report_id: int | None
    computable: bool
    natural_verdict: str             # canonical-orientation verdict (for A3)
    proportion: float | None = None  # canonical point estimate
    n: int | None = None
    k: int | None = None
    proportion2: float | None = None
    n2: int | None = None
    k2: int | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class InstanceFacts:
    core: ViableCore
    polarity: str
    flip_kind: str | None
    slot_values: dict[str, str]
    events_assigned: tuple[str, ...]
    vaccines_assigned: tuple[str, ...]
    gold_verdict: str
    gold_proportion: float | None
    gold_n: int | None
    ci: tuple[float, float] | None
    confidence_tag: str | None
    effect_size: float | None
    p_value: int | None
    negated: bool = False        # the instance asserts the claim's NEGATION


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _ci_fields(k: int, n: int) -> tuple[tuple[float, float], str]:
    ci = wilson_ci(k, n)
    return ci, confidence_tag(ci_width(ci))


def _two_cell(counts: dict, named) -> float | None:
    """named / (named + runner-up): the proportion the argmax test compares.

    The reported `proportion` is the named cell's share of the whole denominator,
    which is the better descriptive number; this is the tested one, so it is what
    the effect size is measured on (decisions.md 2026-08-11).
    """
    if not counts:
        return None
    top = counts.get(named, 0)
    others = [c for cell, c in counts.items() if cell != named]
    best = max(others) if others else 0
    return top / (top + best) if (top + best) else None


def _other_permutation(modal: tuple[str, ...], counts: dict) -> tuple[str, ...]:
    """Pick a non-modal strict ordering: the 2nd-most-common, else any swap."""
    alts = sorted(
        (p for p in counts if p != modal),
        key=lambda p: (-counts[p], p),
    )
    if alts:
        return alts[0]
    # no other observed ordering: swap the first two of modal
    lst = list(modal)
    lst[0], lst[1] = lst[1], lst[0]
    return tuple(lst)


def _slot_events(events: tuple[str, ...]) -> dict[str, str]:
    names = ("A", "B", "C")
    return {names[i]: ev for i, ev in enumerate(events)}


def _slot_vaccines(vaccines: tuple[str, ...]) -> dict[str, str]:
    if len(vaccines) == 1:
        return {"v": vaccines[0]}
    if len(vaccines) == 2:
        return {"v1": vaccines[0], "v2": vaccines[1]}
    return {}


def report_ref(report_id: int) -> str:
    return f"VAERS-{report_id}"


# ---------------------------------------------------------------------------
# enumeration
# ---------------------------------------------------------------------------

def enumerate_group(index: CorpusIndex, group: Group) -> list[ViableCore]:
    mode = MODE_BY_GROUP[group.id]
    if group.level == "vaccine":
        return _enum_vaccine(index, group, mode)
    if group.level == "multi":
        return _enum_multi(index, group, mode)
    return _enum_report(index, group, mode)


def _new_core(group: Group, mode: str, **kw) -> ViableCore:
    return ViableCore(
        group_id=group.id,
        family=group.family,
        primitive=group.primitive,
        level=group.level,
        answer_type=group.answer_type,
        mode=mode,
        **kw,
    )


def _enum_vaccine(index: CorpusIndex, group: Group, mode: str) -> list[ViableCore]:
    cores: list[ViableCore] = []
    is_triple = mode in _VACCINE_TRIPLE_MODES
    for vax in VACCINES:
        cohort = index.cohort(vax)
        k = K_TRIPLE if is_triple else K_PAIR
        terms = index.top_terms(cohort, k)
        if is_triple:
            sets = combinations(terms, 3)
        else:
            sets = combinations(terms, 2)
        for combo in sets:
            core = _build_vaccine_core(index, group, mode, vax, cohort, combo)
            if core is not None:
                cores.append(core)
    return cores


def _is_testable(n, family, *, n2=None) -> bool:
    """Does this conditioned denominator clear the SHARED family floor?

    Since 2026-08-11 this -- not "the corpus helper returned something" -- is what
    ``ViableCore.computable`` means. The helpers now always report n, so a core
    below the floor still carries its denominator and the labeler can name the
    insufficient sub-type: ``sparse`` when 0 < n < floor, ``not_locatable`` at 0.
    """
    return min_n_gate(n, family, n2=n2).testable


def _build_vaccine_core(index, group, mode, vax, cohort, combo) -> ViableCore | None:
    base = dict(events=tuple(combo), vaccines=(vax,), cohort_ids=cohort,
               report_id=None)

    if mode in ("dir_bool", "dir_choice"):
        a, b = combo
        frac, n = corpus.precedes_fraction(index, a, b, cohort)
        ok = _is_testable(n, group.family)
        return _new_core(group, mode, computable=ok,
                         natural_verdict=bool_verdict(frac) if ok else "insufficient",
                         proportion=frac, n=n,
                         k=round(frac * n) if frac is not None else 0, **base)

    if mode == "sym_bool_cooccurs":
        a, b = combo
        frac, n = corpus.co_occurs_fraction(index, a, b, cohort)
        ok = _is_testable(n, group.family)
        return _new_core(group, mode, computable=ok,
                         natural_verdict=bool_verdict(frac) if ok else "insufficient",
                         proportion=frac, n=n,
                         k=round(frac * n) if frac is not None else 0, **base)

    if mode in ("seq_bool", "modal_choice"):
        # STRICT ordering over the ORDERABLE denominator (ordering_distribution
        # excludes co-occurrence).
        a, b, c = combo
        dist = corpus.ordering_distribution(index, [a, b, c], cohort)
        n = dist["n"]
        if not _is_testable(n, group.family):
            return _new_core(group, mode, computable=False,
                             natural_verdict="insufficient", n=n,
                             extra=dist, **base)
        # seq_bool ("most common" BOOL) + modal_choice (CHOICE): supported iff a
        # UNIQUE modal ordering exists (an argmax claim). seq_bool is tested
        # modal-vs-runner-up (see core_significance); modal_choice keeps GOF.
        nv = "supported" if (dist["modal"] is not None and not dist["modal_tie"]) \
            else "insufficient"
        return _new_core(group, mode, computable=True, natural_verdict=nv,
                         proportion=dist["modal_share"], n=n,
                         k=dist["modal_count"], extra=dist, **base)

    if mode in ("first_choice", "last_choice", "first_bool"):
        terms = list(combo)
        fn = corpus.last_among_fractions if mode == "last_choice" \
            else corpus.first_among_fractions
        res = fn(index, terms, cohort)
        n = int(res["n"])
        if not _is_testable(n, group.family):
            return _new_core(group, mode, computable=False,
                             natural_verdict="insufficient", n=n, **base)
        fracs = {t: res[t] for t in terms}
        winner = max(terms, key=lambda t: (fracs[t], t))
        wfrac = fracs[winner]
        # unique argmax? "most common first/last event" is supported iff so.
        max_terms = [t for t in terms if abs(fracs[t] - wfrac) < 1e-12]
        unique = len(max_terms) == 1
        nv = "supported" if unique else "insufficient"
        extra = {"fracs": fracs, "winner": winner, "unique": unique,
                 "tie_rate": res["tie_rate"], "counts": res["counts"]}
        return _new_core(group, mode, computable=True, natural_verdict=nv,
                         proportion=wfrac, n=n, k=round(wfrac * n),
                         extra=extra, **base)

    raise ValueError(f"unhandled vaccine mode: {mode}")


def _enum_multi(index: CorpusIndex, group: Group, mode: str) -> list[ViableCore]:
    cores: list[ViableCore] = []
    triple = mode in _MULTI_TRIPLE_MODES
    for v1, v2 in VACCINE_PAIRS:
        c1, c2 = index.cohort(v1), index.cohort(v2)
        k = K_TRIPLE if triple else K_PAIR
        # intersect the two cohorts' top terms so cores are plausible in both
        shared = [t for t in index.top_terms(c1, k) if t in set(index.top_terms(c2, k))]
        sets = combinations(shared, 3) if triple else combinations(shared, 2)
        for combo in sets:
            core = _build_multi_core(index, group, mode, (v1, v2), c1, c2, combo)
            if core is not None:
                cores.append(core)
    return cores


def _single_fraction(index, primitive_mode, combo, cohort):
    if "precedes" in primitive_mode:
        return corpus.precedes_fraction(index, combo[0], combo[1], cohort)
    if "cooccurs" in primitive_mode:
        return corpus.co_occurs_fraction(index, combo[0], combo[1], cohort)
    if "sequence" in primitive_mode:
        return corpus.sequence_fraction(index, combo[0], combo[1], combo[2], cohort)
    return (None, 0)


def _build_multi_core(index, group, mode, vaxes, c1, c2, combo) -> ViableCore | None:
    base = dict(events=tuple(combo), vaccines=vaxes, cohort_ids=c1, report_id=None)
    v1, v2 = vaxes

    if mode in ("multi_differ_precedes", "multi_dir_precedes",
                "multi_differ_cooccurs", "multi_dir_cooccurs",
                "multi_differ_sequence"):
        p1, n1 = _single_fraction(index, mode, combo, c1)
        p2, n2 = _single_fraction(index, mode, combo, c2)
        if not _is_testable(n1, group.family, n2=n2):
            # n on BOTH cohorts is kept: a two-cohort core is `sparse` when one
            # side is thin and `not_locatable` when a side is empty.
            return _new_core(group, mode, computable=False,
                             natural_verdict="insufficient",
                             proportion=p1, n=n1, proportion2=p2, n2=n2, **base)
        k1, k2 = round(p1 * n1), round(p2 * n2)
        if "differ" in mode:
            nv = differ_verdict(p1, p2)
        else:
            nv = direction_verdict(p1, p2)
        return _new_core(group, mode, computable=True, natural_verdict=nv,
                         proportion=p1, n=n1, k=k1,
                         proportion2=p2, n2=n2, k2=k2, **base)

    if mode in ("multi_same_modal_order",):
        d1 = corpus.ordering_distribution(index, list(combo), c1)
        d2 = corpus.ordering_distribution(index, list(combo), c2)
        if (not _is_testable(d1["n"], group.family, n2=d2["n"])
                or d1["modal"] is None or d2["modal"] is None):
            return _new_core(group, mode, computable=False,
                             natural_verdict="insufficient",
                             n=d1["n"], n2=d2["n"], **base)
        same = d1["modal"] == d2["modal"]
        nv = "supported" if same else "refuted"
        return _new_core(group, mode, computable=True, natural_verdict=nv,
                         proportion=d1["modal_share"], n=d1["n"], k=d1["modal_count"],
                         proportion2=d2["modal_share"], n2=d2["n"], k2=d2["modal_count"],
                         extra={"modal1": d1["modal"], "modal2": d2["modal"],
                                "counts1": d1["counts"], "counts2": d2["counts"]}, **base)

    if mode in ("multi_same_first", "multi_differ_first", "multi_dir_first"):
        f1 = corpus.first_among_fractions(index, list(combo), c1)
        f2 = corpus.first_among_fractions(index, list(combo), c2)
        if not _is_testable(int(f1["n"]), group.family, n2=int(f2["n"])):
            return _new_core(group, mode, computable=False,
                             natural_verdict="insufficient",
                             n=int(f1["n"]), n2=int(f2["n"]), **base)
        terms = list(combo)
        w1 = max(terms, key=lambda t: (f1[t], t))
        w2 = max(terms, key=lambda t: (f2[t], t))
        if mode == "multi_dir_first":
            # focal A = the term with higher combined first-rate
            focal = max(terms, key=lambda t: (f1[t] + f2[t], t))
            p1, p2 = f1[focal], f2[focal]
            nv = direction_verdict(p1, p2)
            n1, n2 = int(f1["n"]), int(f2["n"])
            return _new_core(group, mode, computable=True, natural_verdict=nv,
                             proportion=p1, n=n1, k=round(p1 * n1),
                             proportion2=p2, n2=n2, k2=round(p2 * n2),
                             extra={"focal": focal}, **base)
        same = w1 == w2
        if mode == "multi_same_first":
            nv = "supported" if same else "refuted"
        else:  # multi_differ_first
            nv = "supported" if not same else "refuted"
        return _new_core(group, mode, computable=True, natural_verdict=nv,
                         proportion=f1[w1], n=int(f1["n"]), k=round(f1[w1] * int(f1["n"])),
                         proportion2=f2[w2], n2=int(f2["n"]),
                         extra={"w1": w1, "w2": w2,
                                "counts1": f1["counts"], "counts2": f2["counts"]},
                         **base)

    raise ValueError(f"unhandled multi mode: {mode}")


def _enum_report(index: CorpusIndex, group: Group, mode: str) -> list[ViableCore]:
    cores: list[ViableCore] = []
    triple = mode in ("rep_seq_bool", "rep_first_choice", "rep_last_choice",
                       "rep_first_bool")
    # iterate reports deterministically by id; bound total cores per group
    for vid in sorted(index.report_terms):
        if len(cores) >= MAX_REPORT_CORES:
            break
        tmap = index.report_terms[vid]
        present = sorted(tmap, key=lambda t: (tmap[t], t))
        if triple:
            if len(present) < 3:
                continue
            combo = tuple(present[:3])  # earliest three by level then name
            core = _build_report_core(index, group, mode, vid, tmap, combo)
            if core is not None:
                cores.append(core)
        else:
            if len(present) < 2:
                continue
            combo = tuple(present[:2])
            core = _build_report_core(index, group, mode, vid, tmap, combo)
            if core is not None:
                cores.append(core)
    return cores


def _build_report_core(index, group, mode, vid, tmap, combo) -> ViableCore | None:
    base = dict(events=tuple(combo), vaccines=(), cohort_ids=[vid], report_id=vid,
               computable=True, proportion=None, n=None, k=None)

    if mode == "rep_dir_bool":
        rel = corpus.relation(tmap, combo[0], combo[1])
        if rel == "missing":
            return None
        nv = "supported" if rel == "before" else "refuted"
        return _new_core(group, mode, natural_verdict=nv,
                         extra={"rel": rel}, **base)

    if mode == "rep_dir_choice":
        rel = corpus.relation(tmap, combo[0], combo[1])
        if rel == "missing":
            return None
        nv = "insufficient" if rel == "co_exist" else "supported"
        return _new_core(group, mode, natural_verdict=nv,
                         extra={"rel": rel}, **base)

    if mode == "rep_sym_bool":
        rel = corpus.relation(tmap, combo[0], combo[1])
        if rel == "missing":
            return None
        nv = "supported" if rel == "co_exist" else "refuted"
        return _new_core(group, mode, natural_verdict=nv,
                         extra={"rel": rel}, **base)

    if mode == "rep_seq_bool":
        a, b, c = combo
        ia, ib, ic = tmap.get(a), tmap.get(b), tmap.get(c)
        if None in (ia, ib, ic):
            return None
        holds = ia < ib < ic
        nv = "supported" if holds else "refuted"
        return _new_core(group, mode, natural_verdict=nv,
                         extra={"holds": holds, "idxs": {a: ia, b: ib, c: ic}},
                         **base)

    if mode in ("rep_first_choice", "rep_last_choice", "rep_first_bool"):
        a, b, c = combo
        idxs = {t: tmap.get(t) for t in combo}
        if any(v is None for v in idxs.values()):
            return None
        target = max(idxs.values()) if mode == "rep_last_choice" else min(idxs.values())
        winners = [t for t in combo if idxs[t] == target]
        unique = len(winners) == 1
        if mode == "rep_first_bool":
            nv = "supported" if (unique and winners[0] == a) else \
                ("insufficient" if not unique else "refuted")
        else:
            nv = "supported" if unique else "insufficient"
        return _new_core(group, mode, natural_verdict=nv,
                         extra={"winner": winners[0] if unique else None,
                                "unique": unique, "idxs": idxs}, **base)

    raise ValueError(f"unhandled report mode: {mode}")


# ---------------------------------------------------------------------------
# whole-population enumeration (no top-K cap): every viable core
# ---------------------------------------------------------------------------

def _cooccurring_pairs(index: CorpusIndex, cohort: list[int]) -> list[tuple[str, str]]:
    """All ordered (a<b name) term pairs co-occurring in >= _MIN_N cohort reports.

    Co-occurrence in >= _MIN_N reports is necessary for any pair core to be
    viable (the ordered/both-present denominators are subsets of it), so this is
    the exact candidate set -- enumerated in one cohort pass, not by testing all
    O(T^2) term combinations.
    """
    cnt: dict[tuple[str, str], int] = {}
    for vid in cohort:
        terms = sorted(index.report_terms[vid])
        for pair in combinations(terms, 2):
            cnt[pair] = cnt.get(pair, 0) + 1
    return sorted(p for p, c in cnt.items() if c >= _MIN_N)


def _cooccurring_triples(
    index: CorpusIndex, cohort: list[int]
) -> list[tuple[str, str, str]]:
    """All term triples present together in >= _MIN_N cohort reports."""
    cnt: dict[tuple[str, str, str], int] = {}
    for vid in cohort:
        terms = sorted(index.report_terms[vid])
        if len(terms) < 3:
            continue
        for combo in combinations(terms, 3):
            cnt[combo] = cnt.get(combo, 0) + 1
    return sorted(c for c, k in cnt.items() if k >= _MIN_N)


def enumerate_group_full(index: CorpusIndex, group: Group) -> list[ViableCore]:
    """Whole-population enumeration for a group: every viable core, no top-K cap.

    Mirrors ``enumerate_group`` but draws candidates from the full co-occurrence
    set (pairs/triples clearing _MIN_N) instead of the top-K most-frequent terms,
    and lifts the report-level core cap. Used by the full diagnostic run.
    """
    mode = MODE_BY_GROUP[group.id]
    if group.level == "vaccine":
        return _enum_vaccine_full(index, group, mode)
    if group.level == "multi":
        return _enum_multi_full(index, group, mode)
    return _enum_report_full(index, group, mode)


def _enum_vaccine_full(index, group, mode) -> list[ViableCore]:
    cores: list[ViableCore] = []
    is_triple = mode in _VACCINE_TRIPLE_MODES
    for vax in VACCINES:
        cohort = index.cohort(vax)
        combos = (_cooccurring_triples(index, cohort) if is_triple
                  else _cooccurring_pairs(index, cohort))
        for combo in combos:
            core = _build_vaccine_core(index, group, mode, vax, cohort, combo)
            if core is not None:
                cores.append(core)
    return cores


def _enum_multi_full(index, group, mode) -> list[ViableCore]:
    cores: list[ViableCore] = []
    triple = mode in _MULTI_TRIPLE_MODES
    for v1, v2 in VACCINE_PAIRS:
        c1, c2 = index.cohort(v1), index.cohort(v2)
        if triple:
            cand = set(_cooccurring_triples(index, c1)) & set(_cooccurring_triples(index, c2))
        else:
            cand = set(_cooccurring_pairs(index, c1)) & set(_cooccurring_pairs(index, c2))
        for combo in sorted(cand):
            core = _build_multi_core(index, group, mode, (v1, v2), c1, c2, combo)
            if core is not None:
                cores.append(core)
    return cores


def _enum_report_full(index, group, mode) -> list[ViableCore]:
    # One core per report (earliest two/three events), no MAX_REPORT_CORES cap.
    cores: list[ViableCore] = []
    triple = mode in ("rep_seq_bool", "rep_first_choice", "rep_last_choice",
                       "rep_first_bool")
    need = 3 if triple else 2
    for vid in sorted(index.report_terms):
        tmap = index.report_terms[vid]
        present = sorted(tmap, key=lambda t: (tmap[t], t))
        if len(present) < need:
            continue
        core = _build_report_core(index, group, mode, vid, tmap,
                                  tuple(present[:need]))
        if core is not None:
            cores.append(core)
    return cores


# ---------------------------------------------------------------------------
# feasibility + realization
# ---------------------------------------------------------------------------

_HALF = 1e-12


# Modes reorientable BY SLOT REASSIGNMENT: the same decisive core yields
# `supported` posed one way and `refuted` the other, by flipping the event order
# (dir_*), naming a non-modal cell (the argmax modes), or swapping the two cohorts
# (multi_dir_*).
#
# This is about WORDING, not about whether a reversed hypothesis exists. Keep the
# two apart (decisions.md 2026-08-11):
#
#   DIRECTIONAL  -- the negation of the claim is a REGION of parameter space, so it
#                   can be confirmed by evidence. This is what licenses `refuted`.
#   SLOT-ORIENTABLE -- the claim can be re-worded from one core to assert either
#                   side. This is what makes a group's supply BALANCED.
#
# `sym_bool_cooccurs` is directional but NOT slot-orientable: "A and B typically
# co-occur" has a real opposite (they are usually recorded at different stages,
# rate < 0.5, which 0/10 confirms), so refuted is sound -- but swapping A and B
# changes nothing, since the relation is symmetric. So which class a core supplies
# is fixed by the data, which is why C-V1/C-V3 come out 40 supported / 338
# refuted. The fix is NEGATION, the orientation operator for symmetric claims.
#
# Contrast the genuinely non-directional shapes (multi_differ_*, multi_same_*, and
# the retired GOF modes): their negation is a POINT null (p1 = p2, "exactly
# uniform"), which no evidence can establish, so they can never be refuted.
_SLOT_ORIENTABLE = {
    "dir_bool", "dir_choice",
    "seq_bool", "modal_choice",
    "first_choice", "last_choice", "first_bool",
    "multi_dir_precedes", "multi_dir_cooccurs", "multi_dir_first",
}


_FLIP = {"supported": "refuted", "refuted": "supported"}


def cohort_decision(core: ViableCore):
    """The three-decision Decision for a cohort-level core's canonical claim.

    Imported lazily: ``core.answers`` imports THIS module, so a module-level
    import would be circular. Everything about which test runs for which mode
    lives in ``core.answers`` -- this module must not re-implement that dispatch.
    """
    from temporal_hypo.core.answers import core_decision
    return core_decision(core)


def feasible_polarities(core: ViableCore, group: Group | None = None) -> set[str]:
    """Which instance polarities this core can produce.

    Cohort-level (2026-08-11): the answer is decided by SIGNIFICANCE, not by the
    point estimate. A **decisive** core can be posed either way -- oriented with
    the effect it is ``supported``, oriented against it ``refuted`` -- and a core
    that is not decisive can only be ``insufficient``. This is exactly why S (the
    decisive-core count) caps both the supported and the refuted class.

    The retired point-estimate rule admitted supported/refuted whenever the
    proportion sat off 0.5 by 1e-12, which let a 11/20 coin flip ship as a
    ``supported`` gold label.

    Report-level cores keep their own rules below: they are single exact
    observations with no test, so significance does not apply.

    Negation is ALWAYS available where the template YAML provides it, which today
    is C-V1/C-V3 -- the only two groups that need it, since every other cohort
    group is slot-orientable. It is not a configurable option: without it those two
    groups cap at 3 x min(supported, refuted) = 120 items instead of 567, which is
    a 894-item hole in the benchmark for no benefit.

    Callers must still PREFER PLAIN WORDING -- take the class the data already
    falls on and negate only to fill the remaining deficit. For C-V1 that is 149
    negated of 378 cores (39%), so 61% keep their original wording; a naive
    alternating assignment wastes ~48 needless negations.
    """
    if not core.computable and core.report_id is None:
        return {"insufficient"}
    m = core.mode
    out: set[str] = set()

    if core.report_id is None:
        dec = cohort_decision(core)
        if not dec.decisive:
            return {"insufficient"}
        if m in _SLOT_ORIENTABLE:
            return {"supported", "refuted"}
        # Not slot-orientable: the data fixes which class the PLAIN wording gives.
        # NEGATION is the orientation operator for these claims -- asserting the
        # negation makes the other tail the claim tail -- so when the group has
        # negated wording, one core can still supply either class.
        if group is not None and supports_negation(group):
            return {"supported", "refuted"}
        return {dec.verdict}

    if m == "rep_dir_bool":
        rel = core.extra["rel"]
        out |= {"refuted"}
        if rel in ("before", "after"):
            out |= {"supported"}
    elif m == "rep_dir_choice":
        rel = core.extra["rel"]
        out |= {"insufficient"} if rel == "co_exist" else {"supported", "refuted"}
    elif m == "rep_sym_bool":
        out |= {core.natural_verdict}
    elif m == "rep_seq_bool":
        out |= {"supported", "refuted"} if core.extra["holds"] else {"refuted"}
    elif m in ("rep_first_choice", "rep_last_choice"):
        out |= {"refuted"}
        if core.extra["unique"]:
            out |= {"supported"}
    elif m == "rep_first_bool":
        if core.extra["unique"]:
            out |= {"supported", "refuted"}
        else:
            out |= {"insufficient"}
    else:
        out |= {"insufficient"}
    return out


def realize(core: ViableCore, polarity: str, *,
            negated: bool | None = None) -> InstanceFacts:
    """Build a concrete instance of the requested polarity from the core.

    The gold verdict is recomputed by the locked verdict functions on the
    realized assertion. Caller must request a polarity in feasible_polarities.
    """
    if polarity == "insufficient":
        return _realize_insufficient(core)
    facts = _realize(core, polarity)
    if core.report_id is None:
        # THE GOLD LABEL (2026-08-11). Each `_realize_*` below orients the claim
        # and stamps a point-estimate verdict; for cohort-level claims that label
        # is superseded by the three-decision rule here.
        #
        # Orienting a DECISIVE core with its effect yields `supported` and against
        # it `refuted` -- so the realized verdict is just the requested polarity.
        # A core that is not decisive yields `insufficient` in either orientation,
        # which is what makes shipping it as supported/refuted wrong. Callers are
        # required to request a polarity from `feasible_polarities`, so this only
        # ever downgrades a caller that ignored that contract.
        dec = cohort_decision(core)
        if not dec.decisive:
            facts.gold_verdict = "insufficient"
        elif core.mode in _SLOT_ORIENTABLE:
            facts.gold_verdict = polarity
        else:
            # Not slot-orientable: the data fixes the PLAIN verdict, and negating
            # the claim swaps it because the asserted direction becomes the other
            # tail. So negation is DERIVED from the requested polarity rather than
            # left to the caller -- passing the two independently would let them
            # disagree, and `feasible_polarities` promises both classes whenever
            # the group has negated wording.
            if negated is None:
                negated = polarity != dec.verdict
            facts.gold_verdict = _FLIP[dec.verdict] if negated else dec.verdict
        facts.negated = bool(negated)
    return facts


def _realize(core: ViableCore, polarity: str) -> InstanceFacts:
    m = core.mode
    if m in ("dir_bool", "dir_choice"):
        return _realize_directional(core, polarity)
    if m == "sym_bool_cooccurs":
        return _realize_symmetric_bool(core, polarity)
    if m in ("seq_bool", "modal_choice"):
        return _realize_modal_choice(core, polarity)
    if m in ("first_choice", "last_choice", "first_bool"):
        return _realize_extreme_choice(core, polarity)
    if m in ("multi_differ_precedes", "multi_differ_cooccurs",
             "multi_differ_sequence"):
        return _realize_multi_differ(core, polarity)
    if m in ("multi_dir_precedes", "multi_dir_cooccurs", "multi_dir_first"):
        return _realize_multi_dir(core, polarity)
    if m in ("multi_same_first", "multi_differ_first", "multi_same_modal_order"):
        return _realize_multi_categorical(core, polarity)
    if m.startswith("rep_"):
        return _realize_report(core, polarity)
    raise ValueError(f"cannot realize mode {m}")


def _mk(core, polarity, flip_kind, events_assigned, *, verdict,
        proportion=None, n=None, k=None, p_value=None, null_ref=0.5,
        ci=None, tag=None, effect="auto", vaccines=None):
    vacc = core.vaccines if vaccines is None else vaccines
    slot: dict[str, str] = {}
    slot.update(_slot_events(events_assigned))
    slot.update(_slot_vaccines(vacc))
    if core.report_id is not None:
        slot["r"] = report_ref(core.report_id)
    if p_value is not None:
        slot["p"] = str(p_value)
    if ci is None and k is not None and n:
        ci, tag = _ci_fields(k, n)
    if effect == "auto":
        effect = cohens_h(proportion, null_ref) if proportion is not None else None
    return InstanceFacts(
        core=core, polarity=polarity, flip_kind=flip_kind, slot_values=slot,
        events_assigned=events_assigned, vaccines_assigned=vacc,
        gold_verdict=verdict, gold_proportion=proportion, gold_n=n, ci=ci,
        confidence_tag=tag, effect_size=effect, p_value=p_value,
    )


def _realize_directional(core, polarity):
    a, b = core.events
    frac, n, k = core.proportion, core.n, core.k
    flip = "option" if core.mode == "dir_choice" else "direction"
    if polarity == "supported":
        if frac > 0.5:
            ev, p, kk, fk = (a, b), frac, k, None
        else:
            ev, p, kk, fk = (b, a), 1 - frac, n - k, flip
    else:  # refuted
        if frac < 0.5:
            ev, p, kk, fk = (a, b), frac, k, None
        else:
            ev, p, kk, fk = (b, a), 1 - frac, n - k, flip
    return _mk(core, polarity, fk, ev, verdict=bool_verdict(p),
               proportion=p, n=n, k=kk)


def _realize_symmetric_bool(core, polarity):
    p, n, k = core.proportion, core.n, core.k
    return _mk(core, polarity, None, core.events, verdict=bool_verdict(p),
               proportion=p, n=n, k=k)


def _realize_modal_choice(core, polarity):
    d = core.extra
    n = core.n
    modal = d["modal"]
    if polarity == "supported":
        order, cnt, fk = modal, d["modal_count"], None
        verdict = "supported"
    else:
        order = _other_permutation(modal, d["counts"])
        cnt, fk, verdict = d["counts"].get(order, 0), "modal", "refuted"
    p = cnt / n
    # effect size on the TESTED quantity: named vs runner-up, null 0.5 (2026-08-11)
    return _mk(core, polarity, fk, order, verdict=verdict,
               proportion=p, n=n, k=cnt, null_ref=0.5,
               effect=cohens_h(_two_cell(d["counts"], order), 0.5))


def _realize_extreme_choice(core, polarity):
    fr = core.extra["fracs"]
    winner = core.extra["winner"]
    terms = list(core.events)
    n = core.n
    if polarity == "supported":
        named, fk, verdict = winner, None, "supported"
    else:
        losers = [t for t in terms if t != winner]
        named, fk, verdict = sorted(losers, key=lambda t: (fr[t], t))[0], \
            "option", "refuted"
    others = [t for t in terms if t != named]
    ev = (named, others[0], others[1])
    p = fr[named]
    return _mk(core, polarity, fk, ev, verdict=verdict,
               proportion=p, n=n, k=round(p * n), null_ref=1 / 3)


def _diff_ci(core):
    ci = wilson_newcombe_diff_ci(core.k, core.n, core.k2, core.n2)
    return ci, confidence_tag(ci_width(ci))


def _realize_multi_differ(core, polarity):
    p1, p2 = core.proportion, core.proportion2
    ci, tag = _diff_ci(core)
    return _mk(core, polarity, None, core.events,
               verdict=differ_verdict(p1, p2), proportion=p1, n=core.n,
               ci=ci, tag=tag, effect=cohens_h(p1, p2))


def _realize_multi_dir(core, polarity):
    p1, p2 = core.proportion, core.proportion2
    v1, v2 = core.vaccines
    k1, n1, k2, n2 = core.k, core.n, core.k2, core.n2
    high_is_1 = p1 >= p2
    if polarity == "supported":
        # orient v1 = higher
        if high_is_1:
            vacc, hp, hk, hn, lk, ln = (v1, v2), p1, k1, n1, k2, n2
        else:
            vacc, hp, hk, hn, lk, ln = (v2, v1), p2, k2, n2, k1, n1
        fk = None if high_is_1 else "vaccine_swap"
    else:  # refuted: orient v1 = lower
        if high_is_1:
            vacc, hp, hk, hn, lk, ln = (v2, v1), p2, k2, n2, k1, n1
            fk = "vaccine_swap"
        else:
            vacc, hp, hk, hn, lk, ln = (v1, v2), p1, k1, n1, k2, n2
            fk = None
    ci = wilson_newcombe_diff_ci(hk, hn, lk, ln)
    tag = confidence_tag(ci_width(ci))
    # focal event for multi_dir_first
    if core.mode == "multi_dir_first":
        focal = core.extra["focal"]
        others = [t for t in core.events if t != focal]
        ev = (focal, others[0], others[1])
    else:
        ev = core.events
    verdict = direction_verdict(hp, ln and (lk / ln))
    return _mk(core, polarity, fk, ev, verdict=verdict, proportion=hp,
               n=hn, ci=ci, tag=tag, effect=cohens_h(hp, lk / ln),
               vaccines=vacc)


def _realize_multi_categorical(core, polarity):
    # same/differ first or modal-order: categorical comparison, no CI
    if core.mode == "multi_same_modal_order":
        same = core.extra["modal1"] == core.extra["modal2"]
        verdict = "supported" if same else "refuted"
    elif core.mode == "multi_same_first":
        same = core.extra["w1"] == core.extra["w2"]
        verdict = "supported" if same else "refuted"
    else:  # multi_differ_first
        same = core.extra["w1"] == core.extra["w2"]
        verdict = "supported" if not same else "refuted"
    return _mk(core, polarity, None, core.events, verdict=verdict)


def _realize_report(core, polarity):
    m = core.mode
    a, b = (core.events + (None, None))[:2]
    if m == "rep_dir_bool":
        rel = core.extra["rel"]
        if polarity == "supported":
            ev = (a, b) if rel == "before" else (b, a)
            fk = None if rel == "before" else "direction"
            verdict = "supported"
        else:  # refuted
            if rel == "co_exist":
                ev, fk = (a, b), None
            else:
                ev = (b, a) if rel == "before" else (a, b)
                fk = "direction"
            verdict = "refuted"
        return _mk(core, polarity, fk, ev, verdict=verdict)

    if m == "rep_dir_choice":
        rel = core.extra["rel"]
        # claim asserts events_assigned[0] came first
        if polarity == "supported":
            ev = (a, b) if rel == "before" else (b, a)
            fk = None if rel == "before" else "option"
        else:
            ev = (b, a) if rel == "before" else (a, b)
            fk = "option"
        verdict = "supported" if polarity == "supported" else "refuted"
        return _mk(core, polarity, fk, ev, verdict=verdict)

    if m == "rep_sym_bool":
        # symmetric; polarity fixed by relation
        verdict = core.natural_verdict
        return _mk(core, polarity, None, core.events, verdict=verdict)

    if m == "rep_seq_bool":
        idxs = core.extra["idxs"]
        terms = list(core.events)
        if polarity == "supported":
            ev = tuple(sorted(terms, key=lambda t: idxs[t]))
            verdict = "supported"
            fk = None
        else:
            # order that breaks strict increase: reverse the sorted order
            ev = tuple(sorted(terms, key=lambda t: -idxs[t]))
            verdict = "refuted"
            fk = "order"
        return _mk(core, polarity, fk, ev, verdict=verdict)

    if m in ("rep_first_choice", "rep_last_choice"):
        idxs = core.extra["idxs"]
        winner = core.extra["winner"]
        terms = list(core.events)
        if polarity == "supported":
            named, fk, verdict = winner, None, "supported"
        else:
            losers = [t for t in terms if t != winner]
            named, fk, verdict = losers[0], "option", "refuted"
        others = [t for t in terms if t != named]
        ev = (named, others[0], others[1])
        return _mk(core, polarity, fk, ev, verdict=verdict)

    if m == "rep_first_bool":
        idxs = core.extra["idxs"]
        winner = core.extra["winner"]
        terms = list(core.events)
        if polarity == "supported":
            named, fk, verdict = winner, None, "supported"
        else:
            losers = [t for t in terms if t != winner]
            named, fk, verdict = losers[0], "option", "refuted"
        others = [t for t in terms if t != named]
        ev = (named, others[0], others[1])
        return _mk(core, polarity, fk, ev, verdict=verdict)

    raise ValueError(f"cannot realize report mode {m}")


def _realize_insufficient(core: ViableCore) -> InstanceFacts:
    """Assert the canonical positive claim; gold verdict is insufficient.

    For the argmax modes the canonical claim NAMES THE MODAL CELL, so the slots
    must be oriented the same way the supported branch orients them. Using
    ``core.events`` verbatim would assert "the alphabetically first candidate is
    the most common one", a different claim the data can decisively refute -- which
    is exactly how 24 records ended up labelled `insufficient` while their own
    statistics said `refuted`.
    """
    events = core.events
    m = core.mode
    if m in ("seq_bool", "modal_choice"):
        modal = core.extra.get("modal")
        if modal is not None:
            events = modal
    elif m in ("first_choice", "last_choice", "first_bool"):
        winner = core.extra.get("winner")
        if winner is not None:
            others = [t for t in core.events if t != winner]
            events = (winner, *others)
    return _mk(core, "insufficient", None, events, verdict="insufficient",
               proportion=core.proportion, n=core.n,
               k=core.k if core.n else None, effect=None)
