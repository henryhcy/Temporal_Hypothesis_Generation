"""Public answer-retrieve pipeline: compute the gold answer for any template.

Given a corpus (a ``CorpusIndex`` built from data in the MedTempo leveled-order
format) and a populated template (group id + the event/vaccine/report fillers),
``compute_answer`` returns the full gold answer: the verdict, the point estimate
and its 95% CI, the effect size, the significance test (p-value + significant
flag), and -- for CHOICE templates -- the explicit option set and the correct
option.

This is a thin facade over the locked computation in ``generation.cores`` (the
per-group handler table ``MODE_BY_GROUP`` and the ``_build_*_core`` functions);
it does not re-implement any threshold. It is **pure over the corpus**: a new
dataset in the same format plugs straight in, so nothing is hardcoded to the
current corpus.

Two helpers are also used by the generation emit path so every released instance
carries the same fields:

- ``core_significance(core)`` -- the p-value + significant flag for a core.
- ``answer_key(core)`` -- the CHOICE option set and correct option.

Since the 2026-07-28 three-decision decision every directional mode reports BOTH
one-sided tails (``p_claim`` / ``p_opposite``), because the claim direction alone
cannot separate ``refuted`` from ``insufficient``; ``core_decision`` turns the
pair into the labeled verdict via ``core.verdict.three_decision``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import permutations
from typing import Sequence

from temporal_hypo.core import significance as sig
from temporal_hypo.core import verdict as vd
from temporal_hypo.generation import cores as _cores
from temporal_hypo.generation.confidence import (
    ci_width,
    cohens_h,
    confidence_tag,
    wilson_ci,
    wilson_newcombe_diff_ci,
)
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.templates import Group, load_groups

_ARROW = " → "  # " -> " rendered as the templates render orderings


# ---------------------------------------------------------------------------
# significance dispatch -- which test each group's gold value gets
# ---------------------------------------------------------------------------

# Single-proportion modes -> one-sided exact binomial vs a 0.5 chance null
# (direction chosen from the observed proportion in core_significance).
_BINOM_NULL = {
    "dir_bool": 0.5, "dir_choice": 0.5,
    "sym_bool_cooccurs": 0.5,
}
# "Most common" argmax modes -> modal-vs-runner-up: one-sided exact binomial of
# the named cell's count vs the runner-up's (null 0.5). Verifies the NAMED
# ordering/event is the mode, which GOF-vs-uniform cannot.
#
# The three CHOICE modes joined the BOOL twins on 2026-08-11 (decisions.md). They
# were tested GOF-vs-uniform, which is significant for the WRONG REASON: e.g.
# F-V1 on (Chills, Headache, Pyrexia) in Janssen, n=116, has omnibus p=0.0002
# only because Pyrexia is almost never first (2/116), while the gold answer
# Headache leads Chills 22 to 21 -- a coin flip. GOF tests "is the distribution
# uniform"; the claim asks "does the named candidate beat its nearest rival".
_MODAL_RUNNER = {"seq_bool", "first_bool",
                 "modal_choice", "first_choice", "last_choice"}
# NOTE: the old private `_MODAL_RUNNER_MIN_N = 5` floor on (top + runner-up) is
# gone. Since 2026-07-28 every mode is gated by the SHARED family floor
# (core.min_n) on the CORE's conditioned denominator, which is what "is there
# enough data behind this question" actually means; the exact binomial itself
# needs no minimum.
# Two-proportion modes -> Fisher exact on the 2x2.
_FISHER = {
    "multi_differ_precedes", "multi_dir_precedes",
    "multi_differ_cooccurs", "multi_dir_cooccurs",
    "multi_differ_sequence",
    "multi_dir_first",
}
# Single-cohort omnibus GOF modes: NONE as of 2026-08-11. `modal_choice`,
# `first_choice` and `last_choice` moved to `_MODAL_RUNNER` (their claim is an
# argmax, not a distribution shape), and `consistency_bool` (S-V4) was removed
# outright -- "the ordering is consistent" IS the omnibus alternative restated,
# so its opposite is the null and it can never be refuted OR supported under the
# three-decision rule. See decisions.md 2026-08-11.
_GOF: set[str] = set()
# Two-cohort distribution modes -> exact Fisher-Freeman-Halton homogeneity.
_HOMO = {"multi_same_first", "multi_differ_first", "multi_same_modal_order"}
# Categorical multi modes (no proportion CI).
_MULTI_CATEGORICAL = {"multi_same_first", "multi_differ_first",
                      "multi_same_modal_order"}


# Modes with no directional alternative: the omnibus goodness-of-fit /
# homogeneity tests and the "differ"/"same" multi shapes. A three-decision
# verdict is undefined for these (decisions.md 2026-07-28) -- they are reported
# as `non_directional`, not forced into supported/refuted.
_NON_DIRECTIONAL = _GOF | _HOMO | {
    "multi_differ_precedes", "multi_differ_cooccurs", "multi_differ_sequence",
}
# ADOPTED 2026-08-11: the argmax CHOICE modes now USE modal-vs-runner-up as their
# label-driving test (they are in `_MODAL_RUNNER` above), so there is no longer a
# separate "candidate tail" reported alongside an omnibus label. The old
# `_MODAL_RUNNER_CANDIDATE` set and its `p_claim_modal_runner` /
# `p_opposite_modal_runner` detail keys are gone with the deferral.


@dataclass
class Significance:
    """A core's test result.

    ``p_value`` is the headline p for reporting: the claim-direction tail for a
    directional mode, the omnibus p for a non-directional one. ``p_claim`` and
    ``p_opposite`` are the LABELING inputs -- ``p_claim`` is None exactly when
    the mode has no directional alternative, which is what makes the labeler tag
    it ``non_directional`` instead of inventing a verdict.
    """

    p_value: float | None          # headline p (claim tail, or omnibus)
    significant: bool | None       # decisive either way, gate included
    test: str | None
    details: dict = field(default_factory=dict)
    p_claim: float | None = None       # one-sided tail in the claim's direction
    p_opposite: float | None = None    # one-sided tail in the reverse direction
    decision: "vd.Decision | None" = None


def _perms(events: Sequence[str]) -> list[tuple[str, ...]]:
    return list(permutations(events))


# NOTE: `_gof_observed` was removed on 2026-08-11 with the single-cohort omnibus
# branch it fed. The two-cohort tables are still built by `_homo_table` below.


def _homo_table(core) -> list[list[int]] | None:
    c1 = core.extra.get("counts1")
    c2 = core.extra.get("counts2")
    if c1 is None or c2 is None:
        return None
    if core.mode == "multi_same_modal_order":
        ps = _perms(core.events)
        return [[c1.get(p, 0) for p in ps], [c2.get(p, 0) for p in ps]]
    return [[c1.get(t, 0) for t in core.events],
            [c2.get(t, 0) for t in core.events]]


def _named_counts(core, named) -> tuple[int, int, object] | None:
    """(named cell count, best competitor count, the named cell) for argmax modes.

    ``named`` is the ordering/event the CLAIM asserts is the mode; it defaults to
    the observed argmax (the core's canonical orientation). A refuted instance
    names a non-modal cell, and then the best competitor is the true mode.
    """
    counts = core.extra.get("counts") or {}
    if not counts:
        return None
    if named is None:
        named = core.extra.get("modal") or core.extra.get("winner")
    if named is None:
        return None
    named_count = counts.get(named, 0)
    others = [c for cell, c in counts.items() if cell != named]
    best_other = max(others) if others else 0
    return named_count, best_other, named


def core_tails(core, *, named=None) -> Significance:
    """Both one-sided p-values for a core's claim, in the CLAIM's direction.

    ``p_claim`` is the tail for the direction the claim asserts and
    ``p_opposite`` the reverse tail; ``core_decision`` turns the pair into a
    three-decision verdict. For non-directional modes both are None -- the
    omnibus p is still reported as ``p_value`` / ``details["p_omnibus"]``, it
    just cannot label a direction.

    The claim direction defaults to the core's CANONICAL orientation ("A precedes
    B", "the modal ordering is the mode", "cohort 1's rate exceeds cohort 2's").
    Pass ``named=`` to label an argmax claim that names some other cell -- how a
    refuted instance is built.
    """
    # Report-level groups are a single deterministic observation -> no test.
    if core.report_id is not None:
        return Significance(None, None, None)
    if not core.computable or core.n is None:
        return Significance(None, None, None)
    m = core.mode

    if m in _BINOM_NULL:
        p0 = _BINOM_NULL[m]
        # The canonical claim asserts the rate is ABOVE the chance null, so its
        # tail is "greater" and the reverse claim's is "less". Both are computed:
        # the claim tail alone cannot tell refuted from insufficient.
        p_claim = sig.binom_exact_p(core.k, core.n, p0, alternative="greater")
        p_opp = sig.binom_exact_p(core.k, core.n, p0, alternative="less")
        return Significance(p_claim, None, "binom_exact",
                            {"null": p0, "alternative": "greater"},
                            p_claim=p_claim, p_opposite=p_opp)

    if m in _MODAL_RUNNER:
        # modal-vs-runner-up: is the NAMED ordering/event significantly ahead of
        # its nearest competitor? One-sided exact binomial on the 2-cell table.
        nc = _named_counts(core, named)
        if nc is None:
            return Significance(None, None, None)
        named_count, best_other, cell = nc
        nn = named_count + best_other
        if nn == 0:
            return Significance(None, None, None)
        p_claim = sig.binom_exact_p(named_count, nn, 0.5, alternative="greater")
        p_opp = sig.binom_exact_p(named_count, nn, 0.5, alternative="less")
        return Significance(p_claim, None, "modal_runner",
                            {"null": 0.5, "alternative": "greater",
                             "named": cell, "top": named_count,
                             "runner": best_other, "n_cells": nn},
                            p_claim=p_claim, p_opposite=p_opp)

    if m in _FISHER:
        if core.n2 is None or core.k2 is None:
            return Significance(None, None, None)
        if m in _NON_DIRECTIONAL:
            # "do they differ" -- H1 is existence, not direction. Significant can
            # only mean supported; not-significant can never mean refuted (that
            # would accept H0). No three-decision mapping exists; report the
            # omnibus p and let the labeler tag it non_directional.
            p = sig.fisher_exact_2x2(core.k, core.n, core.k2, core.n2,
                                     alternative="two-sided")
            return Significance(p, None, "fisher_exact_two_sided",
                                {"alternative": "two-sided", "p_omnibus": p})
        # directional multi_dir_*: the canonical claim is "cohort 1's rate is
        # higher than cohort 2's".
        p_claim = sig.fisher_exact_2x2(core.k, core.n, core.k2, core.n2,
                                       alternative="greater")
        p_opp = sig.fisher_exact_2x2(core.k, core.n, core.k2, core.n2,
                                     alternative="less")
        return Significance(p_claim, None, "fisher_exact",
                            {"alternative": "greater"},
                            p_claim=p_claim, p_opposite=p_opp)

    # No single-cohort omnibus GOF branch remains: `_GOF` is empty since
    # 2026-08-11 (see its definition). The exact multinomial GOF itself is still
    # used -- by the two-cohort `_HOMO` shapes below and available in
    # `core.significance` -- it just no longer produces any group's label.

    if m in _HOMO:
        table = _homo_table(core)
        if table is None:
            return Significance(None, None, None)
        r = sig.contingency_test(table)     # Fisher-Freeman-Halton when sparse
        details = dict(r)
        details["p_omnibus"] = r["p"]
        return Significance(r["p"], None, f"homogeneity_{r['method']}", details)

    return Significance(None, None, None)


def core_decision(core, *, named=None, alpha: float = sig.ALPHA) -> vd.Decision:
    """The three-decision verdict for a core's claim (decisions.md 2026-07-28).

    Report-level claims are exact single observations, so they keep their
    deterministic verdict. Every cohort-level claim is labeled from its two
    one-sided tails against the SHARED family min-n floor.
    """
    if core.report_id is not None:
        return vd.deterministic(core.natural_verdict)
    return core_significance(core, named=named, alpha=alpha).decision


def core_significance(core, *, named=None,
                      alpha: float = sig.ALPHA) -> Significance:
    """The significance test result for a viable core (None for report-level).

    ``core_tails`` plus the three-decision label; ``significant`` means "the data
    settled the claim either way", i.e. the verdict is supported or refuted
    rather than insufficient.
    """
    s = core_tails(core, named=named)
    if core.report_id is not None:
        # exact single observation: the deterministic verdict stands, no test
        s.decision = vd.deterministic(core.natural_verdict)
        return s
    # A core with no test still gets a LABEL: an unrunnable test is exactly the
    # insufficient class, and the sub-type (sparse / not-locatable) is part of
    # the required benchmark composition.
    s.decision = vd.three_decision(s.p_claim, s.p_opposite, core.n, core.family,
                                   n2=core.n2, alpha=alpha)
    if s.test is not None:
        s.significant = s.decision.decisive
    return s


def oriented_significance(facts, *, alpha: float = sig.ALPHA) -> Significance:
    """The statistics for the claim an INSTANCE actually asserts.

    ``core_significance`` describes the core's CANONICAL claim. A realized
    instance may assert the mirror of it -- reversed event order, a different named
    cell, swapped cohorts, or a negated predicate -- and then the canonical tails
    describe a different sentence than the one in the record. Emitting them side by
    side made 20% of cohort records self-contradictory (a `supported` instance
    whose own `p_claim` was 0.99), so the released fields are computed here on the
    asserted claim instead.

    Three cases, and the first two are exact rather than approximations:

    - **Reversed direction / swapped cohorts** -> the two tails SWAP. Under the
      0.5 null the assertion's count goes k -> n-k, and P(X >= n-k) = P(X <= k) by
      the binomial's symmetry about 0.5; Fisher's one-sided tails mirror the same
      way when the cohorts trade places.
    - **Negated predicate** (the symmetric co-occurs claims) -> also a swap: the
      negation asserts the other side of 0.5, so the other tail becomes the claim
      tail. This is exactly why negation works as an orientation operator.
    - **A different named cell** (the argmax modes) -> NOT a swap. Naming a
      non-modal event changes which 2-cell table is tested, so the tails are
      recomputed from scratch via ``named=``.
    """
    core = facts.core
    if core.report_id is not None:
        return core_significance(core, alpha=alpha)   # deterministic, no tails

    m = core.mode
    if m in _MODAL_RUNNER:
        named = (tuple(facts.events_assigned)
                 if m in ("seq_bool", "modal_choice")
                 else facts.events_assigned[0])
        return core_significance(core, named=named, alpha=alpha)

    s = core_significance(core, alpha=alpha)
    reversed_claim = (facts.flip_kind in ("direction", "option", "vaccine_swap")
                      or facts.negated)
    if not reversed_claim or s.p_claim is None:
        return s

    flipped = Significance(
        p_value=s.p_opposite,          # the headline p is the CLAIM's tail
        significant=None,
        test=s.test,
        details=dict(s.details, oriented="tails swapped for the asserted claim"),
        p_claim=s.p_opposite,
        p_opposite=s.p_claim,
    )
    flipped.decision = vd.three_decision(
        flipped.p_claim, flipped.p_opposite, core.n, core.family,
        n2=core.n2, alpha=alpha)
    if flipped.test is not None:
        flipped.significant = flipped.decision.decisive
    return flipped


# ---------------------------------------------------------------------------
# CHOICE answer key -- the option set and the correct option (gold answer)
# ---------------------------------------------------------------------------

def answer_key(core) -> tuple[list[str] | None, str | None]:
    """(options, gold_answer) for CHOICE cores; (None, None) otherwise.

    ``gold_answer`` is the temporally correct option, independent of how an
    instance was later oriented (supported vs refuted) -- so a refuted CHOICE,
    which names a wrong option in its text, still carries the right answer here.
    """
    if core.answer_type != "CHOICE":
        return None, None
    m = core.mode
    ev = list(core.events)

    if m == "dir_choice":  # "which of A, B occurs first?"
        if core.proportion is None or abs(core.proportion - 0.5) < 1e-12:
            return ev[:2], None
        return ev[:2], (ev[0] if core.proportion > 0.5 else ev[1])

    if m == "rep_dir_choice":
        rel = core.extra.get("rel")
        gold = ev[0] if rel == "before" else (ev[1] if rel == "after" else None)
        return ev[:2], gold

    if m in ("first_choice", "last_choice", "rep_first_choice", "rep_last_choice"):
        return ev, core.extra.get("winner")

    if m == "modal_choice":
        options = [_ARROW.join(p) for p in _perms(core.events)]
        modal = core.extra.get("modal")
        return options, (_ARROW.join(modal) if modal else None)

    if m in ("multi_dir_precedes", "multi_dir_cooccurs", "multi_dir_first"):
        v1, v2 = core.vaccines
        if core.proportion is None or core.proportion2 is None \
                or abs(core.proportion - core.proportion2) < 1e-12:
            return [v1, v2], None
        return [v1, v2], (v1 if core.proportion > core.proportion2 else v2)

    return None, None


# ---------------------------------------------------------------------------
# public single-instance answer record
# ---------------------------------------------------------------------------

@dataclass
class AnswerRecord:
    group_id: str
    family: str
    level: str
    answer_type: str
    primitive: str
    mode: str
    events: tuple[str, ...]
    vaccines: tuple[str, ...]
    report_id: int | None
    computable: bool
    verdict: str
    proportion: float | None
    n: int | None
    k: int | None
    proportion2: float | None
    n2: int | None
    ci: tuple[float, float] | None
    ci_width: float | None
    confidence_tag: str | None
    effect_size: float | None
    p_value: float | None
    significant: bool | None
    sig_test: str | None
    options: list[str] | None
    gold_answer: str | None
    # three-decision labeling (decisions.md 2026-07-28). `verdict` above is still
    # the legacy point-estimate rule from `generation.cores`; `test_verdict` is
    # the label the benchmark ships once the roster migration lands.
    p_claim: float | None = None
    p_opposite: float | None = None
    test_verdict: str | None = None
    insufficient_subtype: str | None = None


def _null_ref(mode: str) -> float:
    """The reference the EFFECT SIZE is measured against -- the tested null.

    2026-08-11: the argmax modes are tested modal-vs-runner-up on a 2-cell table
    with a 0.5 null, so their effect size is measured against 0.5 as well. It used
    to use the retired GOF-vs-uniform references (1/6 over orderings, 1/3 over
    candidates), which meant the p-value answered "does the named cell beat its
    rival?" while the effect size answered "how far above chance-uniform is this
    share?" -- the same claim/test mismatch the test swap fixed for the p-value.
    """
    return 0.5


def _two_cell_proportion(core) -> float | None:
    """named / (named + runner-up) -- the quantity the argmax test actually uses.

    The core's ``proportion`` is the named cell's share of the WHOLE denominator
    (modal share over all orderings, or first-rate over all reports), which is the
    right descriptive number to report but not what the test compares.
    """
    counts = core.extra.get("counts") or {}
    named = core.extra.get("modal") or core.extra.get("winner")
    if not counts or named is None:
        return None
    top = counts.get(named, 0)
    others = [c for cell, c in counts.items() if cell != named]
    best = max(others) if others else 0
    return top / (top + best) if (top + best) else None


def _ci_effect(core):
    """(ci, width, tag, effect_size) on the core's canonical proportion."""
    if core.proportion is None or core.report_id is not None:
        return None, None, None, None
    if core.mode in _MULTI_CATEGORICAL:
        return None, None, None, None
    if core.mode in _FISHER:
        if None in (core.k, core.n, core.k2, core.n2):
            return None, None, None, None
        ci = wilson_newcombe_diff_ci(core.k, core.n, core.k2, core.n2)
        return ci, ci_width(ci), confidence_tag(ci_width(ci)), \
            cohens_h(core.proportion, core.proportion2)
    if core.k is None or core.n is None:
        return None, None, None, None
    ci = wilson_ci(core.k, core.n)
    # The CI stays on the REPORTED proportion (the descriptive share of the whole
    # denominator); the EFFECT SIZE is measured on the quantity the test actually
    # compares, which for the argmax modes is named-vs-runner-up (2026-08-11).
    basis = core.proportion
    if core.mode in _MODAL_RUNNER:
        basis = _two_cell_proportion(core) or core.proportion
    return ci, ci_width(ci), confidence_tag(ci_width(ci)), \
        cohens_h(basis, _null_ref(core.mode))


_GROUPS: dict[str, Group] | None = None


def _groups() -> dict[str, Group]:
    global _GROUPS
    if _GROUPS is None:
        _GROUPS = load_groups()
    return _GROUPS


def _build_core(corpus: CorpusIndex, group: Group, mode: str, events,
                vaccines, report_id):
    ev = tuple(events)
    if group.level == "vaccine":
        if not vaccines:
            raise ValueError(f"{group.id} is vaccine-level; pass vaccines=(vax,)")
        vax = vaccines[0]
        return _cores._build_vaccine_core(corpus, group, mode, vax,
                                          corpus.cohort(vax), ev)
    if group.level == "multi":
        if len(vaccines) != 2:
            raise ValueError(f"{group.id} is multi-level; pass vaccines=(v1, v2)")
        v1, v2 = vaccines
        return _cores._build_multi_core(corpus, group, mode, (v1, v2),
                                        corpus.cohort(v1), corpus.cohort(v2), ev)
    if report_id is None:
        raise ValueError(f"{group.id} is report-level; pass report_id=...")
    return _cores._build_report_core(corpus, group, mode, report_id,
                                     corpus.report_terms[report_id], ev)


def compute_answer(corpus: CorpusIndex, group_id: str, events,
                   *, vaccines=(), report_id: int | None = None) -> AnswerRecord:
    """Compute the full gold answer for one populated template over the corpus.

    ``events`` is the (A, B[, C]) tuple; pass ``vaccines=(v,)`` for vaccine-level
    groups, ``vaccines=(v1, v2)`` for multi-level, or ``report_id=`` for
    report-level. Returns an ``AnswerRecord``; ``computable`` is False (and the
    verdict ``insufficient``) when the cohort is below the n>=10 threshold.
    """
    group = _groups()[group_id]
    mode = _cores.MODE_BY_GROUP[group_id]
    core = _build_core(corpus, group, mode, events, vaccines, report_id)
    if core is None:  # report-level: events not all present in the report
        raise ValueError(
            f"{group_id}: events {tuple(events)} not all present for the cohort")

    ci, width, tag, effect = _ci_effect(core)
    s = core_significance(core)
    options, gold = answer_key(core)
    return AnswerRecord(
        group_id=core.group_id, family=core.family, level=core.level,
        answer_type=core.answer_type, primitive=core.primitive, mode=core.mode,
        events=core.events, vaccines=core.vaccines, report_id=core.report_id,
        computable=core.computable, verdict=core.natural_verdict,
        proportion=core.proportion, n=core.n, k=core.k,
        proportion2=core.proportion2, n2=core.n2,
        ci=ci, ci_width=width, confidence_tag=tag, effect_size=effect,
        p_value=s.p_value, significant=s.significant, sig_test=s.test,
        options=options, gold_answer=gold,
        p_claim=s.p_claim, p_opposite=s.p_opposite,
        test_verdict=s.decision.verdict if s.decision else None,
        insufficient_subtype=s.decision.subtype if s.decision else None,
    )
