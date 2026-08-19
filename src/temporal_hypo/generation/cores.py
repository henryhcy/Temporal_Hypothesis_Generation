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

import random

from dataclasses import dataclass, field
from itertools import combinations

from temporal_hypo.core.aggregation import (
    bool_verdict,
    direction_verdict,
)
from temporal_hypo.core.min_n import min_n_gate
from temporal_hypo.generation import corpus
from temporal_hypo.generation.confidence import (
    cohens_h,
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

# Modes whose cores are event TRIPLES rather than pairs. Since the 2026-08-14
# roster removal the multi tier is P-M2 alone (a pair), so only the
# single-cohort argmax modes remain triple-shaped.
_VACCINE_TRIPLE_MODES = {
    "seq_bool", "modal_choice",
    "first_choice", "last_choice", "first_bool",
}

# Per-group statistic + verdict mode. The single source of truth mapping each
# of the 30 groups to its gold computation.
MODE_BY_GROUP: dict[str, str] = {
    # pairwise -- precedes
    "P-R1": "rep_dir_bool",
    "P-R2": "rep_dir_choice",
    "P-V1": "dir_bool",
    # the 07-28 roster additions, implemented 2026-08-14 (decisions.md batch 2):
    # two within-cohort two-proportion contrasts -- both arms keep the full
    # denominator, unlike the multi tier, which splits the corpus.
    "P-V2": "antecedent_bool",
    "P-V3": "dir_choice",
    "P-V4": "pairpair_bool",
    "P-M2": "multi_dir_precedes",
    # pairwise -- co_occurs
    "C-R1": "rep_sym_bool",
    "C-V1": "sym_bool_cooccurs",
    "C-V2": "assoc_bool",
    # C-V3 moved to the argmax statistic its text asks (issue 13, 2026-08-14):
    # modal-vs-runner-up over the 3-cell relation distribution, named cell
    # co_exist. C-V1 keeps the majority statistic; the two are no longer twins.
    "C-V3": "cooc_modal_bool",
    # sequence
    "S-R1": "rep_seq_bool",
    "S-V1": "seq_bool",
    "S-V3": "modal_choice",
    # first / last
    "F-R1": "rep_first_choice",
    "F-R2": "rep_last_choice",
    "F-R3": "rep_first_bool",
    "F-V1": "first_choice",
    "F-V2": "last_choice",
    "F-V3": "first_bool",
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
    effect_size: float | None
    p_value: int | None
    negated: bool = False        # the instance asserts the claim's NEGATION
    gold_k: int | None = None    # the asserted claim's numerator count
    # two-cohort instances: the SECOND cohort as the claim orients it, not as the
    # core stores it. Taking these from the core described the wrong cohort
    # whenever the realization swapped them (found 2026-08-11).
    gold_n2: int | None = None
    gold_k2: int | None = None


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _ci_fields(k: int, n: int) -> tuple[float, float]:
    return wilson_ci(k, n)


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
    names = ("A", "B", "C", "D")          # D since P-V4 (4 events, 2026-08-14)
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
    # The two-arm modes have structured candidate shapes, not plain
    # combinations: P-V2 picks a CONSEQUENT and two antecedents (a < c
    # canonically -- swapping them is orientation, not identity); P-V4 picks two
    # DISJOINT pairs (swapping the pairs is orientation). A shared per-cohort
    # fraction cache keeps the pair scans linear in distinct pairs.
    if mode == "antecedent_bool":
        for vax in VACCINES:
            cohort = index.cohort(vax)
            terms = index.top_terms(cohort, K_TRIPLE)
            cache: dict = {}
            for b in terms:
                others = [t for t in terms if t != b]
                for a, c in combinations(others, 2):
                    core = _build_vaccine_core(index, group, mode, vax, cohort,
                                               (a, b, c), frac_cache=cache)
                    if core is not None:
                        cores.append(core)
        return cores
    if mode == "pairpair_bool":
        for vax in VACCINES:
            cohort = index.cohort(vax)
            terms = index.top_terms(cohort, K_TRIPLE)
            prs = list(combinations(terms, 2))
            cache = {}
            for i, p1 in enumerate(prs):
                for p2 in prs[i + 1:]:
                    if set(p1) & set(p2):
                        continue
                    core = _build_vaccine_core(index, group, mode, vax, cohort,
                                               p1 + p2, frac_cache=cache)
                    if core is not None:
                        cores.append(core)
        return cores
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


def _cached_precedes(index, a, b, cohort, cache):
    """precedes_fraction with an optional (a, b)-keyed memo for enumerators."""
    if cache is None:
        return corpus.precedes_fraction(index, a, b, cohort)
    key = (a, b)
    if key not in cache:
        cache[key] = corpus.precedes_fraction(index, a, b, cohort)
    return cache[key]


def _is_testable(n, family, *, n2=None) -> bool:
    """Does this conditioned denominator clear the SHARED family floor?

    Since 2026-08-11 this -- not "the corpus helper returned something" -- is what
    ``ViableCore.computable`` means. The helpers now always report n, so a core
    below the floor still carries its denominator and the labeler can name the
    insufficient sub-type: ``sparse`` when 0 < n < floor, ``not_locatable`` at 0.
    """
    return min_n_gate(n, family, n2=n2).testable


def _build_vaccine_core(index, group, mode, vax, cohort, combo,
                        frac_cache=None) -> ViableCore | None:
    base = dict(events=tuple(combo), vaccines=(vax,), cohort_ids=cohort,
               report_id=None)

    if mode == "antecedent_bool":
        # P-V2 (R3): "B follows A more often than it follows C". Arm 1 = the
        # (A, B) ordered denominator with k = A-before-B; arm 2 = same for
        # (C, B). Both arms live in ONE cohort; the Fisher 2x2 compares them.
        a, b, c = combo
        p1, n1 = _cached_precedes(index, a, b, cohort, frac_cache)
        p2, n2 = _cached_precedes(index, c, b, cohort, frac_cache)
        ok = _is_testable(n1, group.family, n2=n2)
        nv = direction_verdict(p1, p2) if (ok and p1 is not None
                                           and p2 is not None) else "insufficient"
        return _new_core(group, mode, computable=ok, natural_verdict=nv,
                         proportion=p1, n=n1,
                         k=round(p1 * n1) if p1 is not None else 0,
                         proportion2=p2, n2=n2,
                         k2=round(p2 * n2) if p2 is not None else 0, **base)

    if mode == "pairpair_bool":
        # P-V4 (R1): "A precedes B more often than C precedes D", four distinct
        # events, both directed rates in their alphabetical direction.
        a, b, c, d = combo
        p1, n1 = _cached_precedes(index, a, b, cohort, frac_cache)
        p2, n2 = _cached_precedes(index, c, d, cohort, frac_cache)
        ok = _is_testable(n1, group.family, n2=n2)
        nv = direction_verdict(p1, p2) if (ok and p1 is not None
                                           and p2 is not None) else "insufficient"
        return _new_core(group, mode, computable=ok, natural_verdict=nv,
                         proportion=p1, n=n1,
                         k=round(p1 * n1) if p1 is not None else 0,
                         proportion2=p2, n2=n2,
                         k2=round(p2 * n2) if p2 is not None else 0, **base)

    if mode == "assoc_bool":
        # C-V2 (R5): association vs independence, presence x presence. Arm 1 =
        # reports WITH A (k = also B), arm 2 = reports WITHOUT A (k = B).
        a, b = combo
        n1, k1, n2, k2 = corpus.presence_association(index, a, b, cohort)
        p1 = k1 / n1 if n1 else None
        p2 = k2 / n2 if n2 else None
        ok = _is_testable(n1, group.family, n2=n2)
        nv = direction_verdict(p1, p2) if (ok and p1 is not None
                                           and p2 is not None) else "insufficient"
        return _new_core(group, mode, computable=ok, natural_verdict=nv,
                         proportion=p1, n=n1, k=k1,
                         proportion2=p2, n2=n2, k2=k2, **base)

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

    if mode == "cooc_modal_bool":
        # C-V3 (issue 13): "co-occurrence is the DOMINANT relation" -- an argmax
        # over {before, after, co_exist}, tested modal-vs-runner-up with the
        # named cell fixed to co_exist by the template text. `proportion`/`k`
        # stay the DESCRIPTIVE co_exist share/count of the both-present
        # denominator; the tested two-cell quantity lives in `extra["counts"]`.
        a, b = combo
        dist = corpus.relation_distribution(index, a, b, cohort)
        n = dist["n"]
        counts = dist["counts"]
        k = counts["co_exist"]
        runner = max(counts["before"], counts["after"])
        ok = _is_testable(n, group.family)
        nv = ("supported" if k > runner else
              "refuted" if k < runner else "insufficient")
        return _new_core(group, mode, computable=ok,
                         natural_verdict=nv if ok else "insufficient",
                         proportion=(k / n) if n else None, n=n, k=k,
                         extra={"counts": dict(counts), "named": "co_exist"},
                         **base)

    if mode in ("seq_bool", "modal_choice"):
        # STRICT ordering over the ORDERABLE denominator (ordering_distribution
        # excludes co-occurrence).
        a, b, c = combo
        dist = corpus.ordering_distribution(index, [a, b, c], cohort)
        n = dist["n"]
        if not _is_testable(n, group.family):
            # carry k as well: a sub-floor core still has a numerator, and the
            # release promises every label is recomputable from the corpus
            return _new_core(group, mode, computable=False,
                             natural_verdict="insufficient", n=n,
                             k=dist["modal_count"], extra=dist, **base)
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
            # store `extra` even below the floor, so the insufficient realization
            # can NAME THE WINNER like the testable branch does. Without it the
            # claim named the alphabetically-first candidate while k described the
            # top one, and the two disagreed.
            fr0 = {t: res[t] for t in terms}
            top = max(terms, key=lambda t: ((fr0[t] or 0), t))
            maxes = [t for t in terms if (fr0[t] or 0) == (fr0[top] or 0)]
            return _new_core(group, mode, computable=False,
                             natural_verdict="insufficient", n=n,
                             k=round((fr0[top] or 0) * n),
                             extra={"fracs": fr0, "winner": top,
                                    "unique": len(maxes) == 1,
                                    "tie_rate": res.get("tie_rate"),
                                    "counts": res.get("counts", {})},
                             **base)
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
    # Every multi-tier group is pair-shaped since the 2026-08-14 removal.
    cores: list[ViableCore] = []
    for v1, v2 in VACCINE_PAIRS:
        c1, c2 = index.cohort(v1), index.cohort(v2)
        # intersect the two cohorts' top terms so cores are plausible in both
        shared = [t for t in index.top_terms(c1, K_PAIR)
                  if t in set(index.top_terms(c2, K_PAIR))]
        for combo in combinations(shared, 2):
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

    if mode == "multi_dir_precedes":
        p1, n1 = _single_fraction(index, mode, combo, c1)
        p2, n2 = _single_fraction(index, mode, combo, c2)
        if not _is_testable(n1, group.family, n2=n2):
            # n AND k on BOTH cohorts are kept: a two-cohort core is `sparse` when
            # one side is thin and `not_locatable` when a side is empty, and the
            # release promises every label is recomputable from the corpus.
            return _new_core(group, mode, computable=False,
                             natural_verdict="insufficient",
                             proportion=p1, n=n1,
                             k=round(p1 * n1) if p1 is not None else 0,
                             proportion2=p2, n2=n2,
                             k2=round(p2 * n2) if p2 is not None else 0, **base)
        k1, k2 = round(p1 * n1), round(p2 * n2)
        nv = direction_verdict(p1, p2)
        return _new_core(group, mode, computable=True, natural_verdict=nv,
                         proportion=p1, n=n1, k=k1,
                         proportion2=p2, n2=n2, k2=k2, **base)

    raise ValueError(f"unhandled multi mode: {mode}")


_REPORT_TRIPLE_MODES = ("rep_seq_bool", "rep_first_choice",
                        "rep_last_choice", "rep_first_bool")


def _report_combo(tmap: dict, present: list, mode: str) -> tuple | None:
    """The events a report-level question is posed about (2026-08-14, issues 6+7).

    Order-asking questions are NOT POSED on tied reports: the combo is the
    earliest fully-ORDERED pair/triple (all at distinct levels), scanned
    deterministically over the level-then-name ordering. This mirrors how every
    cohort family drops unresolvable reports from its denominator (co-exist for
    precedes, non-orderable triples for sequence, ties for first/last) -- and it
    makes report level strictly TWO-CLASS: with distinct levels, rel is always
    before/after, `holds` is decidable, and first/last winners are unique, so
    `insufficient` cannot arise. C-R1 (rep_sym_bool) keeps the earliest two
    events INCLUDING ties, because co-existence is its supported case and it is
    the report-level group that asks about exactly that.
    """
    if mode == "rep_sym_bool":
        return tuple(present[:2]) if len(present) >= 2 else None
    if mode in _REPORT_TRIPLE_MODES:
        m = len(present)
        for i in range(m):
            for j in range(i + 1, m):
                if tmap[present[i]] == tmap[present[j]]:
                    continue
                for k in range(j + 1, m):
                    if tmap[present[k]] not in (tmap[present[i]],
                                                tmap[present[j]]):
                        return (present[i], present[j], present[k])
        return None
    m = len(present)
    for i in range(m):
        for j in range(i + 1, m):
            if tmap[present[i]] != tmap[present[j]]:
                return (present[i], present[j])
    return None


def _enum_report(index: CorpusIndex, group: Group, mode: str) -> list[ViableCore]:
    cores: list[ViableCore] = []
    # iterate reports deterministically by id; bound total cores per group
    for vid in sorted(index.report_terms):
        if len(cores) >= MAX_REPORT_CORES:
            break
        tmap = index.report_terms[vid]
        present = sorted(tmap, key=lambda t: (tmap[t], t))
        combo = _report_combo(tmap, present, mode)
        if combo is None:
            continue
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
    if mode in ("antecedent_bool", "pairpair_bool"):
        # Candidates come from the ordered-viable pair set (ordered n >= floor
        # on the REAL corpus); a shared fraction cache keeps this linear in
        # distinct pairs rather than in candidate combinations.
        for vax in VACCINES:
            cohort = index.cohort(vax)
            cache: dict = {}
            viable = []
            for pr in _cooccurring_pairs(index, cohort):
                _p, n = _cached_precedes(index, pr[0], pr[1], cohort, cache)
                if n >= _MIN_N:
                    viable.append(pr)
            if mode == "pairpair_bool":
                for i, p1 in enumerate(viable):
                    for p2 in viable[i + 1:]:
                        if set(p1) & set(p2):
                            continue
                        core = _build_vaccine_core(index, group, mode, vax,
                                                   cohort, p1 + p2,
                                                   frac_cache=cache)
                        if core is not None:
                            cores.append(core)
            else:
                by_consequent: dict[str, list[str]] = {}
                for x, y in viable:
                    # each ordered-viable pair supplies BOTH directed arms
                    by_consequent.setdefault(y, []).append(x)
                    by_consequent.setdefault(x, []).append(y)
                for b, ants in sorted(by_consequent.items()):
                    for a, c in combinations(sorted(set(ants)), 2):
                        core = _build_vaccine_core(index, group, mode, vax,
                                                   cohort, (a, b, c),
                                                   frac_cache=cache)
                        if core is not None:
                            cores.append(core)
        return cores
    if mode == "assoc_bool":
        for vax in VACCINES:
            cohort = index.cohort(vax)
            freq = index.term_freq(cohort)
            n_cohort = len(cohort)
            terms = sorted(t for t, cnt in freq.items()
                           if cnt >= _MIN_N and n_cohort - cnt >= _MIN_N)
            for combo in combinations(terms, 2):
                core = _build_vaccine_core(index, group, mode, vax, cohort,
                                           combo)
                if core is not None:
                    cores.append(core)
        return cores
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
    # Every multi-tier group is pair-shaped since the 2026-08-14 removal.
    cores: list[ViableCore] = []
    for v1, v2 in VACCINE_PAIRS:
        c1, c2 = index.cohort(v1), index.cohort(v2)
        cand = set(_cooccurring_pairs(index, c1)) & set(_cooccurring_pairs(index, c2))
        for combo in sorted(cand):
            core = _build_multi_core(index, group, mode, (v1, v2), c1, c2, combo)
            if core is not None:
                cores.append(core)
    return cores


def _enum_report_full(index, group, mode) -> list[ViableCore]:
    # One core per report, no MAX_REPORT_CORES cap; same tie rule as capped.
    cores: list[ViableCore] = []
    for vid in sorted(index.report_terms):
        tmap = index.report_terms[vid]
        present = sorted(tmap, key=lambda t: (tmap[t], t))
        combo = _report_combo(tmap, present, mode)
        if combo is None:
            continue
        core = _build_report_core(index, group, mode, vid, tmap, combo)
        if core is not None:
            cores.append(core)
    return cores


# ---------------------------------------------------------------------------
# deliberately FALSE combinations: the not_locatable supply (issue 5)
# ---------------------------------------------------------------------------

def enumerate_false_cores(index: CorpusIndex, group: Group, *,
                          count: int, seed=0) -> list[ViableCore]:
    """Random combinations of REAL cohort terms with ZERO joint reports.

    decisions.md 2026-08-14 batch 2 (user): not_locatable instances "should
    never be generated from core because core is for successful pairs. I need
    the combination to be false and it could be randomly combined as long as
    there is no actual reports as so." Every event is a real term of the
    cohort's vocabulary, so the claim LOOKS answerable; only querying the store
    reveals an empty conditioned denominator -- which is exactly the capability
    the not_locatable sub-type tests. n = 0 makes `three_decision` label these
    insufficient/not_locatable with no special-casing anywhere downstream.

    Deterministic under `seed` (int or str). Vaccine-level groups sample per
    cohort; the multi tier samples per vaccine PAIR and requires joint zero in
    BOTH cohorts. Report-level groups have no insufficient class by design
    (2026-08-14) and are rejected.
    """
    if group.level == "report":
        raise ValueError("report-level groups have no insufficient class")
    mode = MODE_BY_GROUP[group.id]
    need = 3 if mode in _VACCINE_TRIPLE_MODES else 2
    rng = random.Random(seed)
    out: list[ViableCore] = []
    seen: set = set()

    def term_reports(cohort: list[int]) -> dict[str, set[int]]:
        m: dict[str, set[int]] = {}
        for vid in cohort:
            for t in index.report_terms[vid]:
                m.setdefault(t, set()).add(vid)
        return m

    scopes = ([(v,) for v in VACCINES] if group.level == "vaccine"
              else list(VACCINE_PAIRS))
    per_scope = -(-count // len(scopes))
    for vaxes in scopes:
        maps = [term_reports(index.cohort(v)) for v in vaxes]
        vocab = sorted(set(maps[0]).intersection(*[set(m) for m in maps[1:]])) \
            if len(maps) > 1 else sorted(maps[0])
        if len(vocab) < need:
            continue
        got = attempts = 0
        while got < per_scope and attempts < 200 * per_scope:
            attempts += 1
            combo = tuple(sorted(rng.sample(vocab, need)))
            if (vaxes, combo) in seen:
                continue
            if any(set.intersection(*[m[t] for t in combo]) for m in maps):
                continue                     # the combination actually occurs
            seen.add((vaxes, combo))
            got += 1
            kw = dict(events=combo, vaccines=tuple(vaxes),
                      cohort_ids=index.cohort(vaxes[0]), report_id=None,
                      computable=False, natural_verdict="insufficient",
                      proportion=None, n=0, k=0)
            if group.level == "multi":
                kw.update(proportion2=None, n2=0, k2=0)
            out.append(_new_core(group, mode, **kw))
    return out[:count]

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
    "multi_dir_precedes",
    # the 08-14 two-arm additions: swapping the two ARMS re-words the claim to
    # assert either side (antecedents A<->C; the two pairs). assoc_bool is NOT
    # here -- it is symmetric like C-V1 and orients by negation.
    "antecedent_bool", "pairpair_bool",
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
    if m == "cooc_modal_bool":
        return _realize_cooc_modal(core, polarity)
    if m in ("seq_bool", "modal_choice"):
        return _realize_modal_choice(core, polarity)
    if m in ("first_choice", "last_choice", "first_bool"):
        return _realize_extreme_choice(core, polarity)
    if m == "multi_dir_precedes":
        return _realize_multi_dir(core, polarity)
    if m in ("antecedent_bool", "pairpair_bool"):
        return _realize_two_arm(core, polarity)
    if m == "assoc_bool":
        return _realize_assoc(core, polarity)
    if m.startswith("rep_"):
        return _realize_report(core, polarity)
    raise ValueError(f"cannot realize mode {m}")


def _mk(core, polarity, flip_kind, events_assigned, *, verdict,
        proportion=None, n=None, k=None, n2=None, k2=None,
        p_value=None, null_ref=0.5,
        ci=None, effect="auto", vaccines=None):
    vacc = core.vaccines if vaccines is None else vaccines
    slot: dict[str, str] = {}
    slot.update(_slot_events(events_assigned))
    slot.update(_slot_vaccines(vacc))
    if core.report_id is not None:
        slot["r"] = report_ref(core.report_id)
    if p_value is not None:
        slot["p"] = str(p_value)
    if ci is None and k is not None and n:
        ci = _ci_fields(k, n)
    if effect == "auto":
        effect = cohens_h(proportion, null_ref) if proportion is not None else None
    return InstanceFacts(
        core=core, polarity=polarity, flip_kind=flip_kind, slot_values=slot,
        events_assigned=events_assigned, vaccines_assigned=vacc,
        gold_verdict=verdict, gold_proportion=proportion, gold_n=n, gold_k=k,
        gold_n2=n2, gold_k2=k2, ci=ci,
        effect_size=effect, p_value=p_value,
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


def _realize_cooc_modal(core, polarity):
    """C-V3 since 2026-08-14 (issue 13): the claim names the co_exist cell.

    The named cell is fixed by the template text, so slots and events never
    move; orientation is by NEGATION only (like the other symmetric claims).
    The reported proportion stays the descriptive co_exist share; the effect
    size is measured on the TESTED two-cell quantity, named vs runner-up
    against 0.5, matching the argmax modes (decisions.md 2026-08-11).
    """
    p, n, k = core.proportion, core.n, core.k
    return _mk(core, polarity, None, core.events, verdict=core.natural_verdict,
               proportion=p, n=n, k=k,
               effect=cohens_h(_two_cell(core.extra["counts"], "co_exist"), 0.5))


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


def _realize_two_arm(core, polarity):
    """P-V2 / P-V4: orientation swaps the two ARMS, mirroring _realize_multi_dir.

    Supported asserts the HIGHER-rate arm first; refuted the lower one. The
    emitted n/k/n2/k2 follow the asserted order, so gold_n always describes the
    arm the claim's text puts first -- the same invariant the 08-11 gold_n2 fix
    pinned for the two-cohort group.
    """
    p1, p2 = core.proportion, core.proportion2
    hi_first = p1 >= p2
    keep = (hi_first == (polarity == "supported"))
    if core.mode == "antecedent_bool":
        a, b, c = core.events
        ev = (a, b, c) if keep else (c, b, a)
    else:
        a, b, c, d = core.events
        ev = (a, b, c, d) if keep else (c, d, a, b)
    if keep:
        pp, n, k, pp2, n2, k2, fk = (p1, core.n, core.k,
                                     p2, core.n2, core.k2, None)
    else:
        pp, n, k, pp2, n2, k2, fk = (p2, core.n2, core.k2,
                                     p1, core.n, core.k, "arm_swap")
    ci = wilson_newcombe_diff_ci(k, n, k2, n2)
    return _mk(core, polarity, fk, ev, verdict=direction_verdict(pp, pp2),
               proportion=pp, n=n, k=k, n2=n2, k2=k2, ci=ci,
               effect=cohens_h(pp, pp2))


def _realize_assoc(core, polarity):
    """C-V2: symmetric, so events and arms never move; orientation is by
    NEGATION, derived in realize() exactly as for C-V1/C-V3."""
    ci = wilson_newcombe_diff_ci(core.k, core.n, core.k2, core.n2)
    return _mk(core, polarity, None, core.events, verdict=core.natural_verdict,
               proportion=core.proportion, n=core.n, k=core.k,
               n2=core.n2, k2=core.k2, ci=ci,
               effect=cohens_h(core.proportion, core.proportion2))


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
    ev = core.events
    verdict = direction_verdict(hp, ln and (lk / ln))
    return _mk(core, polarity, fk, ev, verdict=verdict, proportion=hp,
               n=hn, k=hk, n2=ln, k2=lk,
               ci=ci, effect=cohens_h(hp, lk / ln),
               vaccines=vacc)


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
               # k is 0 for an empty denominator, not unknown
               k=(core.k if core.k is not None else 0),
               # no re-orientation happens here, so the core's cohort order is the
               # asserted one and n2/k2 pass straight through
               n2=core.n2, k2=(core.k2 if core.k2 is not None else
                               (0 if core.n2 is not None else None)),
               effect=None)
