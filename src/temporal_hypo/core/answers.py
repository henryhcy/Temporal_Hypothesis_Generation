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
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import permutations
from typing import Sequence

from temporal_hypo.core import significance as sig
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
# "Most common" argmax BOOL modes -> modal-vs-runner-up: one-sided exact
# binomial of the top cell's count vs the runner-up's (null 0.5). Verifies the
# NAMED ordering/event is the mode (which GOF-vs-uniform cannot).
_MODAL_RUNNER = {"seq_bool", "first_bool"}
_MODAL_RUNNER_MIN_N = 5   # top+runner floor; exact binomial is valid at small n
# Two-proportion modes -> Fisher exact on the 2x2.
_FISHER = {
    "multi_differ_precedes", "multi_dir_precedes",
    "multi_differ_cooccurs", "multi_dir_cooccurs",
    "multi_differ_sequence", "multi_dir_sequence",
    "multi_dir_first",
}
# Distribution modes -> chi-square goodness-of-fit vs uniform.
_GOF = {"modal_choice", "consistency_bool", "first_choice", "last_choice"}
# Two-cohort distribution modes -> chi-square homogeneity.
_HOMO = {"multi_same_first", "multi_differ_first", "multi_same_modal_order"}
# Categorical multi modes (no proportion CI).
_MULTI_CATEGORICAL = {"multi_same_first", "multi_differ_first",
                      "multi_same_modal_order"}


@dataclass
class Significance:
    p_value: float | None
    significant: bool | None
    test: str | None
    details: dict = field(default_factory=dict)


def _perms(events: Sequence[str]) -> list[tuple[str, ...]]:
    return list(permutations(events))


def _gof_observed(core) -> list[int] | None:
    m = core.mode
    counts = core.extra.get("counts")
    if not counts:
        return None
    if m in ("modal_choice", "consistency_bool"):
        return [counts.get(p, 0) for p in _perms(core.events)]
    if m in ("first_choice", "last_choice"):
        return [counts.get(t, 0) for t in core.events]
    return None


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


def core_significance(core) -> Significance:
    """The significance test result for a viable core (None for report-level)."""
    # Report-level groups are a single deterministic observation -> no test.
    if core.report_id is not None:
        return Significance(None, None, None)
    if not core.computable or core.n is None:
        return Significance(None, None, None)
    m = core.mode

    if m in _BINOM_NULL:
        p0 = _BINOM_NULL[m]
        # One-sided in the observed direction: an effect on the supported side
        # tests "greater", one on the refuted side tests "less". This corroborates
        # whichever gold verdict the core carries and does not reward the reverse.
        phat = core.k / core.n if core.n else p0
        alt = "greater" if phat > p0 else ("less" if phat < p0 else "two-sided")
        p = sig.binom_exact_p(core.k, core.n, p0, alternative=alt)
        return Significance(p, sig.significance_verdict(p, core.n) == "significant",
                            "binom_exact", {"null": p0, "alternative": alt})

    if m in _MODAL_RUNNER:
        # modal-vs-runner-up: is the top ordering/event significantly ahead of
        # its nearest competitor? One-sided exact binomial of top vs top+runner.
        counts = sorted(core.extra.get("counts", {}).values(), reverse=True)
        top = counts[0] if counts else 0
        runner = counts[1] if len(counts) > 1 else 0
        nn = top + runner
        if nn == 0:
            return Significance(None, None, None)
        p = sig.binom_exact_p(top, nn, 0.5, alternative="greater")
        ok = sig.significance_verdict(p, nn, min_n=_MODAL_RUNNER_MIN_N) == "significant"
        return Significance(p, ok, "modal_runner",
                            {"null": 0.5, "alternative": "greater",
                             "top": top, "runner": runner})

    if m in _FISHER:
        if core.n2 is None or core.k2 is None:
            return Significance(None, None, None)
        # "differ" claims are inherently two-sided; directional multi_dir_* claims
        # are one-sided toward the cohort with the higher rate.
        if "differ" in m:
            alt = "two-sided"
        else:
            p1 = core.k / core.n if core.n else 0.0
            p2 = core.k2 / core.n2 if core.n2 else 0.0
            alt = "greater" if p1 > p2 else ("less" if p1 < p2 else "two-sided")
        p = sig.fisher_exact_2x2(core.k, core.n, core.k2, core.n2, alternative=alt)
        n = min(core.n, core.n2)
        return Significance(p, sig.significance_verdict(p, n) == "significant",
                            "fisher_exact", {"alternative": alt})

    if m in _GOF:
        observed = _gof_observed(core)
        if observed is None:
            return Significance(None, None, None)
        r = sig.multinomial_gof(observed)   # exact when sparse, else chi-square
        return Significance(r["p"], sig.significance_verdict(r["p"], core.n) == "significant",
                            f"multinomial_gof_{r['method']}", r)

    if m in _HOMO:
        table = _homo_table(core)
        if table is None:
            return Significance(None, None, None)
        r = sig.contingency_test(table)     # Fisher-Freeman-Halton when sparse
        n = min(core.n or 0, core.n2 or 0)
        return Significance(r["p"], sig.significance_verdict(r["p"], n) == "significant",
                            f"homogeneity_{r['method']}", r)

    return Significance(None, None, None)


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

    if m in ("multi_dir_precedes", "multi_dir_cooccurs", "multi_dir_sequence",
             "multi_dir_first"):
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


def _null_ref(mode: str) -> float:
    if mode in ("seq_bool", "modal_choice", "consistency_bool"):
        return 1 / 6
    if mode in ("first_bool", "first_choice", "last_choice"):
        return 1 / 3
    return 0.5


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
    return ci, ci_width(ci), confidence_tag(ci_width(ci)), \
        cohens_h(core.proportion, _null_ref(core.mode))


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
    )
