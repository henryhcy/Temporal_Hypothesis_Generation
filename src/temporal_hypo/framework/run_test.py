"""Stage 3 -- the oracle hookup: retrieved counts (or levels) -> exact test -> verdict.

WHAT. ``to_viable_core`` turns a ``StructuredClaim`` plus its Stage-2 retrieval
(per-arm ``ArmCounts``, or the one report's first-mention levels) into the
``ViableCore`` shape the locked oracle in ``core.answers`` reads, with ``extra``
complete for all 20 modes; ``report_rule`` is the deterministic report-tier rule
on the ORIENTED events; ``run_test`` produces a ``Prediction`` -- the harness's
answer for one claim.

WHY two procedure modes. ``"gold"`` runs the reference procedure --
``core_significance(core, named=claim.named_cell())`` plus the negation tail
swap of ``answers.oriented_significance`` -- so it isolates WHAT-layer and
retrieval errors. ``"honouring"`` (the default) runs the CLAIM's own stated
procedure -- test, null p0, claim tail, min-n floor -- on the same counts, so a
model that names the wrong test, null or tail gets the verdict that procedure
yields: the null-choice / test-tail / gate failure modes become causal rather
than merely recorded. With the reference procedure the two modes agree on every
mode (tested release-wide), which is what makes the split meaningful. A
procedure that cannot run on the data at all (Fisher with one arm, an unknown
test, a floor no family has) is recorded in ``procedure_errors`` and the
reference computation is used instead -- never a crash, never a silent fix.

Never ``compute_answer``: it re-derives the named cell from the observed argmax
and therefore reports the WINNER's tail. A claim naming a non-winner (the F-V1
trap) must be refuted, which ``core_significance(named=...)`` does.

Ties and empty data follow the generator so the oracle pipeline reproduces
``gold_answer`` exactly: the first/last ``winner`` is ``max(terms, key=(count,
term))`` over zero-filled counts (``cores._build_vaccine_core``), the modal
ordering is the argmax of the ordering counts (None when there are none), and at
the report tier a co-exist pair on ``rep_dir_choice`` or a tie on the first/last
modes is ``insufficient`` (``cores._build_report_core``). ``n`` is never None on
the cohort tier: no rows means ``n = 0``, which the labeler calls ``not_locatable``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Mapping

from temporal_hypo.core import significance as sig
from temporal_hypo.core import verdict as vd
from temporal_hypo.core.answers import Significance, answer_key, competitor_count, core_significance
from temporal_hypo.core.min_n import family_floor, min_n_gate
from temporal_hypo.framework.claim_schema import (
    DATA_DERIVED_MODES,
    MODE_P0,
    FAMILIES,
    GROUP_BY_MODE,
    MODE_SPEC,
    TAILS,
    UNDERDETERMINED,
    StructuredClaim,
    validate,
)
from temporal_hypo.framework.sql.aggregate import ORDERING_SEP
from temporal_hypo.generation.cores import ViableCore
from temporal_hypo.generation.corpus import relation

if TYPE_CHECKING:  # the retrieval module may not exist yet; duck-typed at runtime
    from temporal_hypo.framework.sql.retrieve import Retrieval

__all__ = ["PROCEDURE_MODES", "Prediction", "report_rule", "run_test", "to_viable_core"]

PROCEDURE_MODES = ("honouring", "gold")

_SEQUENCE_MODES = ("seq_bool", "modal_choice")
_EXTREME_MODES = ("first_choice", "first_bool", "last_choice")
_REP_PAIR_MODES = ("rep_dir_bool", "rep_dir_choice", "rep_sym_bool", "rep_imm_bool")
_REP_EXTREME_MODES = ("rep_first_choice", "rep_first_bool", "rep_last_choice")


@dataclass
class Prediction:
    """The harness's answer for one claim (what ``pipeline.py`` writes per row).

    ``response`` is the four-way token (``supported`` / ``refuted`` /
    ``insufficient`` / ``underdetermined``); ``verdict`` repeats it for answerable
    claims and is None when the input did not determine the claim. ``subtype`` is
    the insufficient sub-type (or ``deterministic`` at the report tier), ``test``
    the test that actually produced the tails (None when none ran), ``answer`` the
    CHOICE option the data selects (None for BOOL and for ties). ``procedure_errors``
    lists the claim's HOW-layer inconsistencies (``claim_schema.validate``) plus
    anything that forced a fallback to the reference procedure; ``notes`` records
    non-error deviations (for instance an argmax test run on k vs n-k).
    """

    response: str
    verdict: str | None
    subtype: str | None
    p_claim: float | None
    p_opposite: float | None
    test: str | None
    n: int | None
    k: int | None
    n2: int | None
    k2: int | None
    answer: str | None
    gate_reason: str | None
    procedure_errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# report tier: the deterministic rule on the oriented events
# ---------------------------------------------------------------------------

def report_rule(claim: StructuredClaim, levels: Mapping[str, int] | None) -> str | None:
    """Verdict of a report-tier claim from the report's first-mention levels.

    ``levels`` maps term -> first-mention level for the one report; the claim's
    events are ORIENTED as the text names them (A is the asserted-earlier /
    asserted-first event). Returns None when any event is missing from the report
    (or ``levels`` is None) -- the caller labels that ``not_locatable`` -- and for
    a non-report mode. Mirrors ``cores._build_report_core``: co-exist is
    ``refuted`` for ``rep_dir_bool`` (A did not precede B) but ``insufficient``
    for ``rep_dir_choice`` (neither option is correct), and a tie for the unique
    earliest/latest is ``insufficient`` on the first/last modes.
    """
    m = claim.mode
    spec = MODE_SPEC.get(m)
    if spec is None or not spec.is_report or levels is None:
        return None
    terms = claim.terms
    if any(t is None or t not in levels for t in terms):
        return None
    lv = [int(levels[t]) for t in terms]  # type: ignore[index]

    # v1.2 rank rules need the WHOLE report (every term's first-mention level).
    if m == "rep_early_bool":
        from temporal_hypo.generation.corpus import report_half
        ranks, L, mid, p_early = report_half({str(t): int(l) for t, l in levels.items()})
        r = ranks.get(str(terms[0]))
        if r is None or p_early is None or r == mid:
            return vd.INSUFFICIENT          # one stage, or A on the middle rank: no half
        return vd.SUPPORTED if r < mid else vd.REFUTED
    if m == "rep_imm_bool":
        from temporal_hypo.generation.corpus import rank_map
        ranks, _L = rank_map({str(t): int(l) for t, l in levels.items()})
        ra, rb = ranks[str(terms[0])], ranks[str(terms[1])]
        return vd.SUPPORTED if ra + 1 == rb else vd.REFUTED

    if m == "rep_dir_bool":
        return vd.SUPPORTED if lv[0] < lv[1] else vd.REFUTED
    if m == "rep_dir_choice":
        if lv[0] < lv[1]:
            return vd.SUPPORTED
        return vd.REFUTED if lv[0] > lv[1] else vd.INSUFFICIENT
    if m == "rep_sym_bool":
        return vd.SUPPORTED if lv[0] == lv[1] else vd.REFUTED
    if m == "rep_seq_bool":
        return vd.SUPPORTED if lv[0] < lv[1] < lv[2] else vd.REFUTED
    if m in _REP_EXTREME_MODES:
        target = max(lv) if m == "rep_last_choice" else min(lv)
        winners = [t for t, l in zip(terms, lv) if l == target]
        if len(winners) != 1:
            return vd.INSUFFICIENT
        return vd.SUPPORTED if winners[0] == terms[0] else vd.REFUTED
    return None


def _report_extra(mode: str, terms: tuple, levels: Mapping[str, int] | None) -> dict:
    """The ``extra`` a report-tier ViableCore carries (what ``answer_key`` reads)."""
    lv: dict[str, int] = {} if levels is None else {str(t): int(l) for t, l in levels.items()}
    if mode in _REP_PAIR_MODES:
        a, b = (tuple(terms) + (None, None))[:2]
        rel = relation(lv, a, b) if (a is not None and b is not None) else "missing"
        out = {"rel": None if rel == "missing" else rel}
        if mode == "rep_imm_bool" and rel != "missing":
            from temporal_hypo.generation.corpus import rank_map
            ranks, _L = rank_map(lv)
            out["adjacent"] = abs(ranks[a] - ranks[b]) == 1
        return out
    if mode == "rep_early_bool":
        from temporal_hypo.generation.corpus import report_half
        a = terms[0] if terms else None
        ranks, L, mid, _p = report_half(lv) if lv else ({}, 0, 0.0, None)
        r = ranks.get(a) if a is not None else None
        return {"early": (r is not None and r < mid), "rank": r, "L": L}
    idxs = {t: lv.get(t) for t in terms if t is not None}
    if mode == "rep_seq_bool":
        vals = [idxs.get(t) for t in terms]
        holds = (None not in vals and len(vals) == 3 and vals[0] < vals[1] < vals[2])
        return {"holds": holds, "idxs": idxs}
    if mode in _REP_EXTREME_MODES:
        vals = [idxs.get(t) for t in terms]
        if None in vals or not vals:
            return {"winner": None, "unique": False, "idxs": idxs}
        target = max(vals) if mode == "rep_last_choice" else min(vals)
        winners = [t for t, l in zip(terms, vals) if l == target]
        unique = len(winners) == 1
        return {"winner": winners[0] if unique else None, "unique": unique, "idxs": idxs}
    return {}


# ---------------------------------------------------------------------------
# cohort tier: the argmax tables the oracle reads
# ---------------------------------------------------------------------------

def _as_ordering(key: Any) -> tuple[str, ...]:
    """Normalise an ordering cell to the ``tuple[str, ...]`` key the oracle expects."""
    if isinstance(key, tuple):
        return tuple(str(x) for x in key)
    if isinstance(key, str):
        return tuple(key.split(ORDERING_SEP))
    return (str(key),)


def _argmax(counts: Mapping[Any, int]):
    """Argmax with the generator's tie-break: highest count, then the largest key."""
    if not counts:
        return None
    return max(counts, key=lambda c: (counts[c], c))


def _cohort_extra(mode: str, terms: tuple, counts: Mapping[Any, int]) -> dict:
    """``extra`` for a cohort-tier core; counts are denominator-row cells only."""
    if mode in _SEQUENCE_MODES:
        table: dict[tuple[str, ...], int] = {}
        for key, c in counts.items():
            k = _as_ordering(key)
            table[k] = table.get(k, 0) + int(c)
        return {"counts": table, "modal": _argmax(table)}
    if mode in _EXTREME_MODES:
        # zero-fill over the claim's candidates: the generator's counts are zero-
        # filled too, and the winner on an all-zero table is what gold_answer holds
        full: dict[str, int] = {str(t): 0 for t in terms if t is not None}
        for key, c in counts.items():
            full[str(key)] = full.get(str(key), 0) + int(c)
        return {"counts": full, "winner": _argmax(full)}
    if mode == "cooc_modal_bool":
        full = {"before": 0, "after": 0, "co_exist": 0}
        for key, c in counts.items():
            full[str(key)] = full.get(str(key), 0) + int(c)
        return {"counts": full, "named": "co_exist"}
    return {}


def _arm_fields(arm: Any) -> tuple[int, int, dict, set[int]]:
    """(n, k, counts, denominator_ids) from an ArmCounts-like object; zeros when absent."""
    if arm is None:
        return 0, 0, {}, set()
    n = int(getattr(arm, "n", 0) or 0)
    k = int(getattr(arm, "k", 0) or 0)
    counts = dict(getattr(arm, "counts", None) or {})
    den = set(getattr(arm, "denominator_ids", None) or ())
    return n, k, counts, den


def to_viable_core(claim: StructuredClaim, retrieval: "Retrieval | Any") -> ViableCore:
    """Build the ViableCore the oracle reads from a claim and its retrieval.

    ``retrieval`` is any object with ``.arms`` (list of ``ArmCounts``, arm 1 then
    arm 2 in the claim's asserted order) and ``.levels`` (term -> level for the
    report tier, else None); None is accepted and means nothing was retrieved.
    Events stay ORIENTED as the claim names them; ``n``/``k`` come from arm 1 and
    ``n2``/``k2`` from arm 2 for the two-arm modes (a missing second arm is
    ``n2 = k2 = 0`` so the labeler says ``not_locatable`` instead of crashing).
    ``computable`` is ``min_n_gate(n, family, n2=n2).testable`` on the cohort tier
    and True at the report tier, where ``natural_verdict`` is ``report_rule``.
    The core's ``family`` is the MODE's family (the gold gate); a claim's own
    family/floor only matter in honouring mode.
    """
    spec = MODE_SPEC.get(claim.mode)
    if spec is None:
        raise ValueError(f"unknown mode {claim.mode!r}; cannot build a core")
    terms = tuple(claim.terms)
    arms = list(getattr(retrieval, "arms", None) or [])
    levels = getattr(retrieval, "levels", None)
    common = dict(group_id=GROUP_BY_MODE[claim.mode], family=spec.family,
                  primitive=spec.primitive, level=spec.tier,
                  answer_type=spec.answer_type, mode=claim.mode, events=terms,
                  vaccines=tuple(claim.vaccines))

    if spec.is_report:
        rid = claim.report_id
        return ViableCore(cohort_ids=[rid] if rid is not None else [], report_id=rid,
                          computable=True, natural_verdict=report_rule(claim, levels) or "",
                          proportion=None, n=None, k=None,
                          extra=_report_extra(claim.mode, terms, levels), **common)

    n, k, counts, den = _arm_fields(arms[0] if arms else None)
    extra = _cohort_extra(claim.mode, terms, counts)
    # v1.2: the tested null travels on the core (as the generator stores it):
    # a text-stated bar is the mode's constant; a data-derived null is the
    # retriever's per-report chance sum over the denominator, divided by n.
    if claim.mode in MODE_P0:
        extra["p0"] = MODE_P0[claim.mode]
        extra["null_kind"] = "text_stated"
        if claim.mode == "first_bar":
            extra["named"] = str(terms[0]) if terms else None
    elif claim.mode in DATA_DERIVED_MODES:
        cs = getattr(arms[0], "chance_sum", None) if arms else None
        extra["p0"] = (cs / n) if (cs is not None and n) else None
        extra["null_kind"] = "data_derived"
    if spec.arms == 2:
        n2, k2, _, _ = _arm_fields(arms[1] if len(arms) > 1 else None)
        proportion2: float | None = (k2 / n2) if n2 else None
    else:
        n2 = k2 = None
        proportion2 = None
    return ViableCore(cohort_ids=sorted(den), report_id=None,
                      computable=min_n_gate(n, spec.family, n2=n2).testable,
                      natural_verdict="",
                      proportion=(k / n) if n else None, n=n, k=k,
                      proportion2=proportion2, n2=n2, k2=k2,
                      extra=extra, **common)


# ---------------------------------------------------------------------------
# the two procedures
# ---------------------------------------------------------------------------

def _swap_tails(s: Significance, core: ViableCore, why: str) -> Significance:
    """The negation swap of ``answers.oriented_significance``: the other tail is the claim tail."""
    flipped = Significance(p_value=s.p_opposite, significant=None, test=s.test,
                           details=dict(s.details, oriented=why),
                           p_claim=s.p_opposite, p_opposite=s.p_claim)
    flipped.decision = vd.three_decision(flipped.p_claim, flipped.p_opposite,
                                         core.n, core.family, n2=core.n2)
    if flipped.test is not None:
        flipped.significant = flipped.decision.decisive
    return flipped


def _reference(core: ViableCore, claim: StructuredClaim) -> Significance:
    """The gold procedure: ``core_significance`` on the named cell, tails swapped when negated."""
    s = core_significance(core, named=claim.named_cell())
    if claim.negated and s.p_claim is not None:
        s = _swap_tails(s, core, "tails swapped for the negated claim")
    return s


def _family_for_floor(claim: StructuredClaim, errors: list[str]) -> str:
    """The family whose floor equals the claim's ``min_n_floor`` (10 -> pairwise-like, 5 -> sequence).

    Prefers the claim's own family, then the mode's, so the reference procedure
    reproduces the reference gate reason verbatim; a floor no family has is a
    procedure error and the gate falls back to the claim's family when that is a
    known one, else the mode's.
    """
    spec = claim.spec
    floor = claim.procedure.min_n_floor
    for fam in (claim.family, spec.family, *FAMILIES):
        try:
            if family_floor(fam) == floor:
                return fam
        except ValueError:
            continue
    try:
        family_floor(claim.family)
        fallback = claim.family
    except ValueError:
        fallback = spec.family
    errors.append(f"min_n_floor {floor!r} matches no family floor; gate uses the "
                  f"{fallback!r} floor {family_floor(fallback)}")
    return fallback


def _honour(core: ViableCore, claim: StructuredClaim, errors: list[str],
            notes: list[str]) -> Significance | None:
    """Run the CLAIM's stated procedure on the counts; None means "fall back to the reference"."""
    p = claim.procedure
    test_name = p.test
    tail = p.claim_tail
    if tail not in TAILS:
        errors.append(f"claim_tail {tail!r} is not one of {TAILS}; reference procedure used")
        return None
    opp = "less" if tail == "greater" else "greater"
    n, k, n2, k2 = core.n, core.k, core.n2, core.k2
    n = 0 if n is None else n
    k = 0 if k is None else k
    two_arm = False

    if p.test == "binom_exact":
        p0 = p.null.p0
        plan_nk = (claim.plan or {}).get("null_kind") if claim.plan else None
        if p0 is None and (plan_nk == "data_derived" or claim.mode in DATA_DERIVED_MODES):
            # v1.2: the claim states a RECIPE ("the structural rate over the
            # denominator reports"); S3 resolves it on the retrieved data. The
            # reference procedure carries no p0 for these modes either, so the
            # resolution is only noted when a composed plan asked for it.
            p0 = (core.extra or {}).get("p0")
            if p0 is None and n == 0:
                # an EMPTY denominator has no chance rate to resolve and nothing
                # to test (the verdict is insufficient / not_locatable either
                # way): not a procedure error, the reference procedure decides
                return None
            if plan_nk == "data_derived":
                notes.append(f"data-derived null resolved on the retrieved denominator: p0={p0}")
        if p0 is None or not (0.0 < float(p0) < 1.0):
            errors.append(f"binom_exact needs a null p0 in (0, 1), got {p0!r}; reference procedure used")
            return None

        def tails() -> tuple[float, float]:
            return (sig.binom_exact_p(k, n, float(p0), alternative=tail),
                    sig.binom_exact_p(k, n, float(p0), alternative=opp))

    elif p.test == "modal_runner":
        counts = core.extra.get("counts") or {}
        named = claim.named_cell()
        has_table = sum(int(c) for c in counts.values()) > 0
        if named is not None and (has_table or n == 0):
            # (an all-zero table with n == 0 is simply an empty denominator)
            top = int(counts.get(named, 0))
            others = [int(c) for cell, c in counts.items() if cell != named]
            runner = max(others) if others else 0
        else:
            # no argmax table for this mode (or none was retrieved although the
            # denominator is not empty): the only two cells available are the
            # numerator and its complement
            top, runner = k, n - k
            notes.append("modal_runner: no argmax counts available; tested k vs n-k as the two cells")
        nn = top + runner
        p0m = 0.5 if p.null.p0 is None else float(p.null.p0)

        # The "competitor beats the named cell" direction (alternative "less" on
        # the named count) is a union over the competitors, so its p is
        # Bonferroni-adjusted by their number, as in the reference procedure
        # (core.answers._modal_runner_tails, 2026-10-24).
        comp = competitor_count(claim.mode, len(claim.terms))

        def tails() -> tuple[float | None, float | None]:
            if nn == 0:
                return None, None
            p_gt = sig.binom_exact_p(top, nn, p0m, alternative="greater")
            p_lt = min(1.0, comp * sig.binom_exact_p(top, nn, p0m, alternative="less"))
            return (p_gt, p_lt) if tail == "greater" else (p_lt, p_gt)

    elif p.test == "fisher_exact":
        if n2 is None or k2 is None:
            errors.append("fisher_exact needs two arms but the retrieval has one; reference procedure used")
            return None
        two_arm = True
        # A composed plan (toolbox frame) states a RULE, resolved here on the
        # actual table (11 §13.3/13.4): exact when any expected cell < 5, else
        # the asymptotic branch if the rule allows it.
        rule = (claim.plan or {}).get("test_rule") if claim.plan else None
        min_exp = sig.min_expected_cell_2x2(k, n, k2, n2)
        asymptotic = rule == "exact_if_small_else_asymptotic" and min_exp >= 5.0
        if rule is not None:
            notes.append(f"test_rule {rule} resolved: "
                         f"{'asymptotic' if asymptotic else 'exact'} (min expected cell {min_exp:.1f})")
        if asymptotic:
            test_name = "chi_square_1sided"

            def tails() -> tuple[float | None, float | None]:
                return (sig.two_proportion_z_p(k, n, k2, n2, alternative=tail),
                        sig.two_proportion_z_p(k, n, k2, n2, alternative=opp))
        else:
            def tails() -> tuple[float, float]:
                return (sig.fisher_exact_2x2(k, n, k2, n2, alternative=tail),
                        sig.fisher_exact_2x2(k, n, k2, n2, alternative=opp))

    else:
        errors.append(f"test {p.test!r} cannot be run on a cohort-tier claim; reference procedure used")
        return None

    family = _family_for_floor(claim, errors)
    n2_gate = n2 if two_arm else None
    # Like the reference (which only tests a `computable` core), the tails exist
    # only when the claim's own gate passes; below it they are None and the
    # labeler names the insufficient sub-type from n alone.
    if n == 0 or n2_gate == 0 or not min_n_gate(n, family, n2=n2_gate).testable:
        p_claim: float | None = None
        p_opp: float | None = None
    else:
        p_claim, p_opp = tails()
    test_run = test_name if p_claim is not None else None
    s = Significance(p_claim, None, test_run,
                     {"null": p.null.p0, "alternative": tail, "gate_family": family},
                     p_claim=p_claim, p_opposite=p_opp)
    s.decision = vd.three_decision(p_claim, p_opp, n, family, n2=n2_gate, alpha=p.alpha)
    if test_run is not None:
        s.significant = s.decision.decisive
    return s


def _answer(core: ViableCore) -> str | None:
    """``answer_key(core)[1]`` guarded against a malformed two-cohort claim."""
    if core.answer_type != "CHOICE":
        return None
    if core.mode == "multi_dir_precedes" and len(core.vaccines) != 2:
        return None
    return answer_key(core)[1]


# ---------------------------------------------------------------------------
# public entry point
# ---------------------------------------------------------------------------

def run_test(claim: StructuredClaim, retrieval: "Retrieval | Any", *,
             procedure_mode: str = "honouring") -> Prediction:
    """Stage 3 for one claim: counts -> test -> three-decision verdict -> Prediction.

    ``procedure_mode`` is ``"honouring"`` (run the claim's own stated procedure;
    incompatible choices are recorded and the reference used) or ``"gold"`` (the
    reference procedure regardless of what the claim says). An underdetermined
    claim answers ``underdetermined`` with every other field None/empty. The
    report tier is a single exact observation in both modes: ``report_rule`` via
    ``verdict.deterministic``, or ``not_locatable`` when the report lacks an event.
    """
    if procedure_mode not in PROCEDURE_MODES:
        raise ValueError(f"procedure_mode must be one of {PROCEDURE_MODES}, got {procedure_mode!r}")
    if claim.mode not in MODE_SPEC:
        raise ValueError(f"unknown mode {claim.mode!r}; Stage 1 must yield a known mode (or no parse)")
    if claim.is_underdetermined:
        return Prediction(UNDERDETERMINED, None, None, None, None, None,
                          None, None, None, None, None, None, [], [])

    errors = validate(claim)
    notes: list[str] = []
    core = to_viable_core(claim, retrieval)

    if claim.spec.is_report:
        rule = report_rule(claim, getattr(retrieval, "levels", None))
        if rule is None:
            dec = vd.Decision(vd.INSUFFICIENT, vd.NOT_LOCATABLE, None, None, None,
                              "not locatable: the report lacks one or more of the claim's events")
        else:
            dec = vd.deterministic(rule)
        return Prediction(dec.verdict, dec.verdict, dec.subtype, None, None, None,
                          None, None, None, None, _answer(core), dec.gate, errors, notes)

    s: Significance | None = None
    if procedure_mode == "honouring":
        s = _honour(core, claim, errors, notes)
    if s is None:
        s = _reference(core, claim)
    dec = s.decision
    assert dec is not None  # core_significance always labels a cohort-tier core
    return Prediction(dec.verdict, dec.verdict, dec.subtype, s.p_claim, s.p_opposite,
                      s.test, core.n, core.k, core.n2, core.k2, _answer(core),
                      dec.gate, errors, notes)
