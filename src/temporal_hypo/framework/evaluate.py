"""Stage 4: score prediction rows against the release gold; write the reports.

What: ``evaluate(rows, release)`` turns the prediction rows ``pipeline.py`` writes
(one per hypothesis text; schema in ``11_model_pipeline.md`` and the harness
brief) into the ``metrics.json`` content, and ``write_report`` renders
``metrics.json``, ``report.md`` and ``failures.md`` (the ``validation_sample.md``
supports / against / excluded style, worst 25 records).

Why one module: the pipeline only records what each stage produced; the scoring
rules live here so every pipeline (oracle, rules+compiler, LLM extractor, LLM
SQL, agent) is graded identically.

- The verdict is scored on ``prediction.response``: micro accuracy, per-class
  P/R/F1 and class-macro-F1 (``decisions.md`` 2026-07-28 "Metrics"; the report
  tier has no ``insufficient`` class, so its macro runs over {supported,
  refuted}); a group-macro companion (mean of per-group class-macro-F1 over
  groups with at least ``min_group_size`` scored instances, bootstrap CI by
  resampling instances within group, the small groups listed rather than
  silently averaged in); a fact-weighted companion (every ``fact_id`` weighs the
  same, so the 8,571-instance P-V4 cannot swamp the number).
- Stage 1 is scored against ``claim_schema.from_gold`` -- the WHAT layer as exact
  matches, the HOW layer field by field -- so "wrong null" and "wrong tail" are
  measurable, not folded into a wrong verdict.
- Stage 2 is scored against ``evidence_ids`` per arm and per set with the 0/0
  convention (P=R=F1=1 iff both sets are empty; 0 if the gold is empty and the
  prediction is not -- the fabrication case) plus the two probes the design
  singles out: ``coexist_leak`` (share of the gold-excluded co-exist reports
  that leaked into the predicted denominator) and the ``not_locatable`` false
  positive rate. The report tier has no denominator; it gets ``report_hit`` and
  stays out of the set averages.
- Stage 3 is scored on counts and p-values: agreement within ``P_TOL`` only
  where the gold has a p-value (3,135 insufficient rows have none), None-ness as
  its own binary, and the named test bucketed gold / synonym / other-exact /
  approximate / none -- approximate is never "valid" (CLAUDE.md).
- ``underdetermined`` inputs (C-V3 research/clinical, F-V3 research: the text
  never names the events) are scored ONLY in their own block and excluded from
  everything else. They are a property of the INPUT; ``insufficient`` is a
  property of the DATA.
- Attribution walks S1-parse -> S1-procedure -> S2-conditioning ->
  S2-aggregation -> S3-test -> S3-gate -> S3-verdict and charges each wrong
  verdict to the EARLIEST failing stage, prints each stage's denominator (rows
  that reached it), flags ``lucky`` rows (right verdict despite an earlier
  failure) and gives the gold-forced marginals (S2 errors among rows with a
  correct S1, S3 errors among rows with correct S1 and S2) so the failure modes
  read as marginal rates, the way the docs describe them.
- Consistency: mirror-pair contradictions over ``derived_from_core_id`` (the
  detector promised in the paper), twin agreement over ``fact_id`` (identical
  event tuples only -- a mirror shares the fact but reverses the events), and
  register/format invariance per instance.

``release`` is duck-typed: anything with ``answer_for(hypothesis_id) -> gold row``
(``framework.io.Release``; the tests use a stub). Stdlib only.
"""

from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from temporal_hypo.framework.claim_schema import (
    MODE_SPEC, MODES, UNDERDETERMINED, VERDICTS, Procedure, StructuredClaim, from_gold,
    derive_plan,
)

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

P_TOL = 1e-4                       # p-value agreement tolerance (plan section 7)
INSUFFICIENT = "insufficient"
DECISIVE = ("supported", "refuted")
REPORT_CLASSES = ("supported", "refuted")   # the report tier has no insufficient class
STAGES = ("S1-parse", "S1-procedure", "S2-conditioning", "S2-aggregation",
          "S3-test", "S3-gate", "S3-verdict")
S1_STAGES = STAGES[:2]
S2_STAGES = STAGES[2:4]
S3_STAGES = STAGES[4:]
PROCEDURE_SUBBUCKETS = ("null", "test_tail", "gate", "other")
PROCEDURE_FIELDS = ("test", "null.kind", "null.p0", "null.statistic", "claim_tail",
                    "alpha", "arms", "conditioning", "min_n_floor")
# The composed plan (toolbox frame, 11 §13.3); the reference is derive_plan(gold mode).
PLAN_FIELDS = ("quantity", "extreme", "denominator", "arms", "null_kind", "p0",
               "tail", "test_family", "test_rule", "min_n_floor")
# Test rules that are VALID for a family at every n it can meet (11 §13.4).
VALID_RULES = {"two_proportions": {"exact_always", "exact_if_small_else_asymptotic"},
               "proportion_vs_p0": {"exact_always"},
               "named_vs_runner_up": {"exact_always"},
               "none": {"exact_always", "exact_if_small_else_asymptotic"}}
SET_NAMES = ("denominator", "numerator", "excluded")
S1_FLAGS = ("mode_acc", "events_ordered_em", "events_set_em", "cohort_em",
            "negated_acc", "claim_em")
TEST_BUCKETS = ("gold", "synonym", "other_exact", "approximate", "none", "unknown")
# (group, register) pairs whose templates never name the events -- the 2,292
# release rows the rules parser marks `underdetermined`. Only rows from these
# templates are set aside from scoring; an `underdetermined` prediction on any
# other row is scored as a wrong response (and counted under `unexpected`).
TEMPLATE_UNDERDETERMINED = frozenset({("C-V3", "research"), ("C-V3", "clinical"),
                                      ("F-V3", "research")})

# Alternative-test adjudication (plan section 6): names a model may use for the
# reference tests, and markers of approximate tests. Normalised lower-case with
# '_' for '-' and ' '.
_TEST_SYNONYMS: dict[str, frozenset[str]] = {
    "binom_exact": frozenset({"binom_exact", "binomial", "binom", "binomial_exact",
                              "exact_binomial", "binom_test", "binomial_test",
                              "exact_binom", "sign", "sign_test"}),
    "fisher_exact": frozenset({"fisher_exact", "fisher", "fishers_exact",
                               "fisher_exact_2x2", "fisher_test", "fisher_exact_test",
                               "hypergeometric"}),
    "modal_runner": frozenset({"modal_runner", "modal_vs_runner_up", "named_vs_runner_up",
                               "modal_runner_up", "runner_up", "modal_vs_runnerup"}),
}
_EXACT_TESTS = frozenset().union(*_TEST_SYNONYMS.values()) | frozenset({
    "multinomial_exact", "exact_multinomial", "permutation", "permutation_test",
    "barnard", "boschloo", "mcnemar_exact", "fisher_freeman_halton", "exact"})
_APPROX_MARKERS = ("chi", "z_test", "ztest", "normal", "wald", "t_test", "ttest",
                   "welch", "mann_whitney", "wilcoxon", "friedman", "kruskal", "anova",
                   "asymptotic", "approx", "score_test", "likelihood", "g_test",
                   "logistic", "regression", "proportion_z", "two_proportion")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _mean(xs: Iterable[Any]) -> float | None:
    vals = [float(x) for x in xs if x is not None]
    return sum(vals) / len(vals) if vals else None


def _rate(num: int, den: int) -> float | None:
    return num / den if den else None


def _num_eq(a: Any, b: Any, tol: float = 1e-12) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return a == b


def set_prf(pred: Iterable[int], gold: Iterable[int]) -> dict[str, float]:
    """Set precision / recall / F1 / exact match with the 0/0 convention.

    Both empty -> P = R = F1 = EM = 1.0 (the retriever correctly found nothing);
    gold empty and prediction not -> 0.0 everywhere (fabrication); gold non-empty
    and prediction empty -> 0.0 (nothing found).
    """
    p, g = set(pred), set(gold)
    if not p and not g:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "em": 1.0}
    tp = len(p & g)
    precision = tp / len(p) if p else 0.0
    recall = tp / len(g) if g else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1,
            "em": 1.0 if p == g else 0.0}


# Modes whose roles B.. form an UNORDERED candidate set around the named event A.
CANDIDATE_SET_MODES = frozenset({
    "first_choice", "first_bool", "last_choice",
    "rep_first_choice", "rep_last_choice", "rep_first_bool",
})


def canonical_terms(mode: str, terms: Sequence[str | None]) -> tuple:
    """Terms in the order the claim's semantics fix: A, then sorted candidates
    for the first/last modes; unchanged for every other mode (order IS the claim)."""
    terms = tuple(terms)
    if mode in CANDIDATE_SET_MODES and len(terms) > 1:
        return (terms[0],) + tuple(sorted(terms[1:], key=lambda t: (t is None, str(t))))
    return terms


def canonical_what_key(claim: StructuredClaim) -> tuple:
    """``StructuredClaim.what_key`` with the candidate-set canonicalisation."""
    return (claim.mode, canonical_terms(claim.mode, claim.terms),
            tuple((c.vaccine, c.report_id) for c in claim.cohorts),
            claim.negated, claim.asserted_option)


def shuffle_options(options: Sequence[str] | None, hypothesis_id: str,
                    seed: int = 0) -> list[str] | None:
    """The seeded per-record option shuffle (plan section 7).

    Deterministic in ``(seed, hypothesis_id)`` so the pipeline can apply it before
    any parser reads the row and the evaluator can reproduce the presented order
    for the ``options[i]`` trivial baselines when the claim does not record it.
    """
    if options is None:
        return None
    rng = random.Random(f"{seed}:{hypothesis_id}")
    out = list(options)
    rng.shuffle(out)
    return out


def classify_test(pred_test: str | None, gold_test: str | None) -> str:
    """Bucket a named test against the gold one (see ``TEST_BUCKETS``)."""
    if pred_test is None:
        return "none"
    norm = str(pred_test).strip().lower().replace("-", "_").replace(" ", "_")
    if gold_test is not None and norm == gold_test:
        return "gold"
    if gold_test is not None and norm in _TEST_SYNONYMS.get(gold_test, ()):
        return "synonym"
    if norm in _EXACT_TESTS:
        return "other_exact"
    if any(m in norm for m in _APPROX_MARKERS):
        return "approximate"
    return "unknown"


def _classes_for(recs: Sequence["_Rec"]) -> tuple[str, ...]:
    """Verdict classes a block is macro-averaged over (report-only blocks: 2)."""
    if recs and all(r.tier == "report" for r in recs):
        return REPORT_CLASSES
    return VERDICTS


# ---------------------------------------------------------------------------
# per-record scoring
# ---------------------------------------------------------------------------

@dataclass
class _ArmScore:
    label: str
    prf: dict[str, dict[str, float]]        # set name -> P/R/F1/EM
    pred: dict[str, set[int]]
    gold: dict[str, set[int]]
    leak_hit: int                           # |pred denominator & gold excluded|
    leak_total: int                         # |gold excluded|
    n: int | None
    k: int | None
    gold_n: int | None
    gold_k: int | None

    @property
    def nk_ok(self) -> bool:
        return self.n == self.gold_n and self.k == self.gold_k


@dataclass
class _Rec:
    """One prediction row joined to its gold, with every per-row judgement."""

    hid: str
    iid: str
    group: str
    register: str | None
    fmt: str | None
    tier: str
    family: str
    mode: str
    answer_type: str
    negated: bool
    fact_id: str | None
    core_id: str | None
    gold_events: tuple[str, ...]
    gold_verdict: str
    gold_subtype: str | None
    response: str | None
    pred_subtype: str | None
    correct: bool
    underdetermined: bool
    gold_claim: StructuredClaim
    pred_claim: StructuredClaim | None
    claim_invalid: bool
    s1: dict[str, bool | None]
    roles: dict[str, bool]
    proc_ok: dict[str, bool]
    procedure_em: bool
    procedure_bucket: str | None
    arms: list[_ArmScore]
    levels: dict[str, int] | None
    report_hit: bool | None
    den_ok: bool
    num_ok: bool
    arms_nk_ok: bool
    coexist_leak: float | None
    not_locatable_fp: bool | None
    counts_nk_em: bool | None
    pred_nk: tuple
    gold_nk: tuple
    gold_p: tuple[float | None, float | None]
    pred_p: tuple[float | None, float | None]
    p_claim_ok: bool | None
    p_opposite_ok: bool | None
    none_ok: bool
    p_ok: bool
    gold_test: str | None
    pred_test: str | None
    test_bucket: str | None
    gold_answer: str | None
    pred_answer: str | None
    gold_options: list[str] | None
    pred_options: list[str] | None
    first_failure: str | None
    error: str | None
    procedure_errors: list[str] = field(default_factory=list)
    plan_ok: dict[str, bool] | None = None      # toolbox frame only
    plan_em: bool | None = None
    rule_valid: bool | None = None               # family right AND rule valid for it


def _sets(block: Mapping[str, Any]) -> dict[str, set[int]]:
    return {name: {int(x) for x in (block.get(name) or [])} for name in SET_NAMES}


def _gold_arms(ev: Mapping[str, Any] | None) -> list[tuple[str, dict[str, set[int]]]]:
    """``evidence_ids`` -> ordered (label, sets) arms; empty at the report tier."""
    if not ev or "report_id" in ev:
        return []
    if "cohort_1" in ev:
        return [(lab, _sets(ev.get(lab) or {})) for lab in ("cohort_1", "cohort_2")]
    return [("arm", _sets(ev))]


def _match_arm(pred_arms: Sequence[Mapping[str, Any]], label: str, index: int
               ) -> Mapping[str, Any] | None:
    """The predicted arm for a gold arm: by label when possible, else by position."""
    for a in pred_arms:
        if a.get("label") == label:
            return a
    if index < len(pred_arms):
        return pred_arms[index]
    return None


def _procedure_ok(pred: Procedure, ref: Procedure) -> dict[str, bool]:
    return {
        "test": pred.test == ref.test,
        "null.kind": pred.null.kind == ref.null.kind,
        "null.p0": _num_eq(pred.null.p0, ref.null.p0),
        "null.statistic": pred.null.statistic == ref.null.statistic,
        "claim_tail": pred.claim_tail == ref.claim_tail,
        "alpha": _num_eq(pred.alpha, ref.alpha),
        "arms": pred.arms == ref.arms,
        "conditioning": pred.conditioning == ref.conditioning,
        "min_n_floor": pred.min_n_floor == ref.min_n_floor,
    }


def _procedure_bucket(ok: Mapping[str, bool]) -> str | None:
    """The S1-procedure sub-bucket: null choice, test/tail, gate, other."""
    if not (ok["null.kind"] and ok["null.p0"] and ok["null.statistic"]):
        return "null"
    if not (ok["test"] and ok["claim_tail"]):
        return "test_tail"
    if not ok["min_n_floor"]:
        return "gate"
    if not (ok["arms"] and ok["conditioning"] and ok["alpha"]):
        return "other"
    return None


def _score_row(row: Mapping[str, Any], gold: Mapping[str, Any], *,
               options_seed: int = 0) -> _Rec:
    hid = row["hypothesis_id"]
    iid = row.get("instance_id") or hid.rsplit("-", 2)[0]
    pred = row.get("prediction") or {}
    response = pred.get("response")
    gold_claim = from_gold(gold)
    gold_terms = tuple(str(t) for t in gold_claim.terms)
    spec = MODE_SPEC.get(gold["mode"])
    tier = spec.tier if spec else str(gold.get("level"))
    is_report = tier == "report"

    pred_claim: StructuredClaim | None = None
    claim_invalid = False
    if row.get("claim") is not None:
        try:
            pred_claim = StructuredClaim.from_dict(row["claim"])
        except (KeyError, TypeError, ValueError):
            claim_invalid = True
    pc = pred_claim
    underdetermined = (pc is not None and bool(pc.underdetermined)) or response == UNDERDETERMINED

    gold_verdict = gold["gold_verdict"]
    gold_subtype = gold.get("insufficient_subtype") if gold_verdict == INSUFFICIENT else None
    pred_subtype = pred.get("subtype")
    correct = response == gold_verdict

    # --- S1 ---------------------------------------------------------------
    # First/last claims name ONE event (role A) against an unordered candidate
    # set (roles B, C): "which of A, B, C is first" is the same claim under any
    # order of B and C. The release happens to list them in options order, and
    # the pipeline shuffles options before parsing, so B/C are compared as a set
    # for those modes (canonical form = A followed by sorted candidates).
    gold_ct = canonical_terms(gold_claim.mode, gold_claim.terms)
    pc_ct = canonical_terms(pc.mode, pc.terms) if pc is not None else None
    s1: dict[str, bool | None] = {
        "mode_acc": pc is not None and pc.mode == gold_claim.mode,
        "events_ordered_em": pc is not None and pc_ct == gold_ct,
        "events_set_em": pc is not None and sorted(map(str, pc.terms)) == sorted(gold_terms),
        "cohort_em": pc is not None and pc.cohorts == gold_claim.cohorts,
        "negated_acc": pc is not None and pc.negated == gold_claim.negated,
        "claim_em": pc is not None and canonical_what_key(pc) == canonical_what_key(gold_claim),
        "asserted_option_acc": (pc is not None and pc.asserted_option == gold_claim.asserted_option)
        if gold_claim.answer_type == "CHOICE" else None,
    }
    roles = {e.role: (pc is not None and i < len(pc.events) and pc.events[i].term == e.term)
             for i, e in enumerate(gold_claim.events)}
    if (gold_claim.mode in CANDIDATE_SET_MODES and pc is not None
            and len(pc.events) == len(gold_claim.events) and len(gold_claim.events) > 1):
        cand_ok = sorted(map(str, pc.terms[1:])) == sorted(map(str, gold_terms[1:]))
        for e in gold_claim.events[1:]:
            roles[e.role] = cand_ok
    if pc is not None:
        proc_ok = _procedure_ok(pc.procedure, gold_claim.procedure)
    else:
        proc_ok = {f: False for f in PROCEDURE_FIELDS}
    procedure_em = all(proc_ok.values())
    procedure_bucket = None if procedure_em else (_procedure_bucket(proc_ok) if pc is not None else "other")
    plan_ok: dict[str, bool] | None = None
    plan_em: bool | None = None
    rule_valid: bool | None = None
    pplan = pc.plan if pc is not None else None
    if pplan:
        ref_plan = derive_plan(gold_claim.mode, negated=gold_claim.negated)
        plan_ok = {}
        for f in PLAN_FIELDS:
            pv, gv = pplan.get(f), ref_plan.get(f)
            plan_ok[f] = _num_eq(pv, gv) if f == "p0" else (pv == gv)
        plan_em = all(plan_ok.values())
        fam = pplan.get("test_family")
        rule_valid = (fam == ref_plan["test_family"]
                      and pplan.get("test_rule") in VALID_RULES.get(fam, set()))

    # --- S2 ---------------------------------------------------------------
    retrieval = row.get("retrieval") or {}
    pred_arms = retrieval.get("arms") or []
    arms: list[_ArmScore] = []
    for i, (label, gsets) in enumerate(_gold_arms(gold.get("evidence_ids"))):
        parm = _match_arm(pred_arms, label, i)
        psets = ({name: {int(x) for x in (parm.get(f"{name}_ids") or [])} for name in SET_NAMES}
                 if parm is not None else {name: set() for name in SET_NAMES})
        gold_n, gold_k = ((gold.get("gold_n"), gold.get("gold_k")) if i == 0
                          else (gold.get("gold_n2"), gold.get("gold_k2")))
        arms.append(_ArmScore(
            label=label,
            prf={name: set_prf(psets[name], gsets[name]) for name in SET_NAMES},
            pred=psets, gold=gsets,
            leak_hit=len(psets["denominator"] & gsets["excluded"]),
            leak_total=len(gsets["excluded"]),
            n=parm.get("n") if parm is not None else None,
            k=parm.get("k") if parm is not None else None,
            gold_n=gold_n, gold_k=gold_k))
    den_ok = all(a.prf["denominator"]["em"] == 1.0 for a in arms)
    num_ok = all(a.prf["numerator"]["em"] == 1.0 for a in arms)
    arms_nk_ok = all(a.nk_ok for a in arms)
    leak_total = sum(a.leak_total for a in arms)
    coexist_leak = (sum(a.leak_hit for a in arms) / leak_total) if leak_total else None
    # Fabrication probe, PER ARM: a not_locatable instance is one whose gold
    # denominator is empty in at least one arm; the false positive is a
    # non-empty predicted denominator for such an arm. (A two-arm claim with
    # one empty arm legitimately has a non-empty other arm.)
    not_locatable_fp = (any(a.pred["denominator"] and not a.gold["denominator"] for a in arms)
                        if gold_subtype == "not_locatable" else None)
    levels = retrieval.get("levels") if is_report else None
    report_hit: bool | None = None
    if is_report:
        lv = levels or {}
        report_hit = bool(lv) and all(t in lv for t in gold_terms) and (
            pc is None or pc.report_id is None or pc.report_id == gold_claim.report_id)

    # --- S3 ---------------------------------------------------------------
    gold_nk = (gold.get("gold_n"), gold.get("gold_k"), gold.get("gold_n2"), gold.get("gold_k2"))
    pred_nk = (pred.get("n"), pred.get("k"), pred.get("n2"), pred.get("k2"))
    counts_nk_em = None if is_report else pred_nk == gold_nk
    gold_p = (gold.get("p_claim"), gold.get("p_opposite"))
    pred_p = (pred.get("p_claim"), pred.get("p_opposite"))

    def _agree(g, p):
        if g is None:
            return None
        return p is not None and abs(float(p) - float(g)) <= P_TOL

    p_claim_ok = _agree(gold_p[0], pred_p[0])
    p_opposite_ok = _agree(gold_p[1], pred_p[1])
    none_ok = (pred_p[0] is None) == (gold_p[0] is None) and (pred_p[1] is None) == (gold_p[1] is None)
    p_ok = none_ok and p_claim_ok is not False and p_opposite_ok is not False
    gold_test = gold.get("sig_test")
    pred_test = pred.get("test")
    bucket = classify_test(pred_test, gold_test) if gold_test is not None else None

    # --- CHOICE -----------------------------------------------------------
    gold_options = list(gold["options"]) if gold.get("options") is not None else None
    if pc is not None and pc.options is not None:
        pred_options: list[str] | None = list(pc.options)
    else:
        pred_options = shuffle_options(gold_options, hid, options_seed)

    # --- attribution: the earliest failing stage --------------------------
    subtype_ok = gold_verdict != INSUFFICIENT or response != INSUFFICIENT or pred_subtype == gold_subtype
    if not s1["claim_em"]:
        first = "S1-parse"
    elif not procedure_em:
        first = "S1-procedure"
    elif is_report and not report_hit:
        first = "S2-conditioning"
    elif not is_report and not den_ok:
        first = "S2-conditioning"
    elif not is_report and not (num_ok and arms_nk_ok):
        first = "S2-aggregation"
    elif not p_ok:
        first = "S3-test"
    elif not correct or not subtype_ok:
        first = "S3-gate" if (gold_verdict == INSUFFICIENT or response == INSUFFICIENT) else "S3-verdict"
    else:
        first = None

    return _Rec(
        hid=hid, iid=iid, group=gold.get("group_id") or row.get("group_id"),
        register=row.get("register"), fmt=row.get("format"), tier=tier,
        family=gold.get("family"), mode=gold["mode"], answer_type=gold_claim.answer_type,
        negated=bool(gold.get("negated", False)), fact_id=gold.get("fact_id"),
        core_id=gold.get("derived_from_core_id"), gold_events=gold_terms,
        gold_verdict=gold_verdict, gold_subtype=gold_subtype, response=response,
        pred_subtype=pred_subtype, correct=correct, underdetermined=underdetermined,
        gold_claim=gold_claim, pred_claim=pc, claim_invalid=claim_invalid,
        s1=s1, roles=roles, proc_ok=proc_ok, procedure_em=procedure_em,
        procedure_bucket=procedure_bucket, arms=arms, levels=levels, report_hit=report_hit,
        den_ok=den_ok, num_ok=num_ok, arms_nk_ok=arms_nk_ok, coexist_leak=coexist_leak,
        not_locatable_fp=not_locatable_fp, counts_nk_em=counts_nk_em, pred_nk=pred_nk,
        gold_nk=gold_nk, gold_p=gold_p, pred_p=pred_p, p_claim_ok=p_claim_ok,
        p_opposite_ok=p_opposite_ok, none_ok=none_ok, p_ok=p_ok, gold_test=gold_test,
        pred_test=pred_test, test_bucket=bucket, gold_answer=gold.get("gold_answer"),
        pred_answer=pred.get("answer"), gold_options=gold_options, pred_options=pred_options,
        first_failure=first, error=row.get("error"),
        procedure_errors=list(pred.get("procedure_errors") or []),
        plan_ok=plan_ok, plan_em=plan_em, rule_valid=rule_valid,
    )


# ---------------------------------------------------------------------------
# verdict metrics
# ---------------------------------------------------------------------------

def _confusion(recs: Iterable[_Rec]) -> Counter:
    return Counter((r.gold_verdict, r.response) for r in recs)


def _prf_from_confusion(conf: Mapping[tuple, int], classes: Sequence[str]
                        ) -> tuple[dict[str, dict], float | None]:
    """Per-class P/R/F1 and their macro. A class with no gold AND no predicted
    rows is undefined in this block and left out of the macro."""
    per: dict[str, dict] = {}
    f1s: list[float] = []
    for c in classes:
        tp = conf.get((c, c), 0)
        gold_n = sum(v for (g, _), v in conf.items() if g == c)
        pred_n = sum(v for (_, p), v in conf.items() if p == c)
        if gold_n == 0 and pred_n == 0:
            per[c] = {"precision": None, "recall": None, "f1": None, "gold_n": 0, "pred_n": 0}
            continue
        precision = tp / pred_n if pred_n else 0.0
        recall = tp / gold_n if gold_n else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per[c] = {"precision": precision, "recall": recall, "f1": f1,
                  "gold_n": gold_n, "pred_n": pred_n}
        f1s.append(f1)
    return per, _mean(f1s)


def _verdict_summary(recs: Sequence[_Rec], classes: Sequence[str]) -> dict:
    per, macro = _prf_from_confusion(_confusion(recs), classes)
    return {"n": len(recs), "n_instances": len({r.iid for r in recs}),
            "accuracy": _mean(r.correct for r in recs),
            "class_macro_f1": macro, "per_class": per, "classes": list(classes)}


def _breakdown(recs: Sequence[_Rec], key: Callable[[_Rec], Any]) -> dict[str, dict]:
    groups: dict[Any, list[_Rec]] = defaultdict(list)
    for r in recs:
        groups[key(r)].append(r)
    out = {}
    for k, rs in groups.items():
        block = _verdict_summary(rs, _classes_for(rs))
        block.pop("per_class")
        out[str(k)] = block
    return dict(sorted(out.items()))


def _group_macro(recs: Sequence[_Rec], *, min_group_size: int, bootstrap: int,
                 seed: int) -> dict:
    by_group: dict[str, list[_Rec]] = defaultdict(list)
    for r in recs:
        by_group[r.group].append(r)
    included: list[str] = []
    excluded: list[dict] = []
    per_group_f1: dict[str, float] = {}
    classes_by_group: dict[str, tuple[str, ...]] = {}
    for g, rs in sorted(by_group.items()):
        n_inst = len({r.iid for r in rs})
        classes = _classes_for(rs)
        _, macro = _prf_from_confusion(_confusion(rs), classes)
        if n_inst < min_group_size or macro is None:
            excluded.append({"group": g, "n_instances": n_inst})
            continue
        included.append(g)
        per_group_f1[g] = macro
        classes_by_group[g] = classes
    point = _mean(per_group_f1.values())
    ci = None
    if bootstrap and included:
        rng = random.Random(seed)
        inst_conf: dict[str, list[Counter]] = {}
        for g in included:
            per_inst: dict[str, Counter] = defaultdict(Counter)
            for r in by_group[g]:
                per_inst[r.iid][(r.gold_verdict, r.response)] += 1
            inst_conf[g] = [per_inst[i] for i in sorted(per_inst)]
        draws: list[float] = []
        for _ in range(bootstrap):
            f1s = []
            for g in included:
                insts = inst_conf[g]
                conf: Counter = Counter()
                for c in rng.choices(insts, k=len(insts)):
                    conf.update(c)
                _, m = _prf_from_confusion(conf, classes_by_group[g])
                if m is not None:
                    f1s.append(m)
            draws.append(_mean(f1s) or 0.0)
        draws.sort()
        last = len(draws) - 1
        ci = [draws[int(math.floor(0.025 * last))], draws[int(math.ceil(0.975 * last))]]
    return {"f1": point, "ci95": ci, "groups": included, "per_group_f1": per_group_f1,
            "excluded_groups": excluded, "min_group_size": min_group_size,
            "bootstrap": bootstrap, "seed": seed}


def _verdict_block(recs: Sequence[_Rec], *, min_group_size: int, bootstrap: int,
                   seed: int) -> dict:
    out = _verdict_summary(recs, VERDICTS)
    out["group_macro"] = _group_macro(recs, min_group_size=min_group_size,
                                      bootstrap=bootstrap, seed=seed)
    by_fact: dict[str, list[bool]] = defaultdict(list)
    for r in recs:
        by_fact[r.fact_id or r.iid].append(r.correct)
    out["fact_weighted_accuracy"] = _mean(_mean(v) for v in by_fact.values())
    out["n_facts"] = len(by_fact)
    insuf = [r for r in recs if r.gold_verdict == INSUFFICIENT]
    out["subtype_accuracy"] = _mean(r.pred_subtype == r.gold_subtype for r in insuf)
    out["n_gold_insufficient"] = len(insuf)
    sub_conf: dict[str, Counter] = defaultdict(Counter)
    for r in insuf:
        sub_conf[str(r.gold_subtype)][str(r.pred_subtype) if r.response == INSUFFICIENT
                                      else f"verdict:{r.response}"] += 1
    out["subtype_confusion"] = {g: dict(sorted(c.items())) for g, c in sorted(sub_conf.items())}
    out["response_counts"] = dict(sorted(Counter(str(r.response) for r in recs).items()))
    return out


# ---------------------------------------------------------------------------
# stage metrics
# ---------------------------------------------------------------------------

def _extraction_block(recs: Sequence[_Rec]) -> dict:
    out: dict[str, Any] = {"n": len(recs),
                           "n_no_claim": sum(r.pred_claim is None for r in recs),
                           "n_claim_invalid": sum(r.claim_invalid for r in recs)}
    for flag in S1_FLAGS + ("asserted_option_acc",):
        out[flag] = _mean(r.s1[flag] for r in recs)
    out["n_choice"] = sum(r.answer_type == "CHOICE" for r in recs)
    roles: dict[str, list[bool]] = defaultdict(list)
    for r in recs:
        for role, ok in r.roles.items():
            roles[role].append(ok)
    out["per_role"] = {role: _mean(v) for role, v in sorted(roles.items())}
    out["procedure"] = {f: _mean(r.proc_ok[f] for r in recs) for f in PROCEDURE_FIELDS}
    out["procedure_em"] = _mean(r.procedure_em for r in recs)
    conf: dict[str, dict[str, int]] = {g: {p: 0 for p in MODES} for g in MODES}
    for g in conf:
        conf[g]["none"] = 0
    for r in recs:
        p = r.pred_claim.mode if r.pred_claim is not None else "none"
        row = conf.setdefault(r.mode, {m: 0 for m in list(MODES) + ["none"]})
        row[p] = row.get(p, 0) + 1
    out["mode_confusion"] = conf
    planned = [r for r in recs if r.plan_ok is not None]
    if planned:
        out["plan"] = {
            "n": len(planned),
            "fields": {f: _mean(r.plan_ok[f] for r in planned) for f in PLAN_FIELDS},
            "plan_em": _mean(r.plan_em for r in planned),
            "rule_valid": _mean(r.rule_valid for r in planned),
            "n_no_shape": sum(1 for r in recs if r.pred_claim is None
                              and r.error and "no mode for plan shape" in str(r.error)),
        }
    return out


def _retrieval_block(recs: Sequence[_Rec]) -> dict:
    arm_recs = [r for r in recs if r.tier != "report"]
    report_recs = [r for r in recs if r.tier == "report"]
    out: dict[str, Any] = {"n": len(arm_recs), "n_report": len(report_recs)}
    for name in SET_NAMES:
        out[name] = {m: _mean(_mean(a.prf[name][m] for a in r.arms) for r in arm_recs)
                     for m in ("precision", "recall", "f1", "em")}
    out["all_sets_em"] = _mean(all(a.prf[n]["em"] == 1.0 for a in r.arms for n in SET_NAMES)
                               for r in arm_recs)
    out["arms_nk_em"] = _mean(r.arms_nk_ok for r in arm_recs)
    leak = [r.coexist_leak for r in arm_recs if r.coexist_leak is not None]
    out["coexist_leak"] = {"n": len(leak), "mean": _mean(leak),
                           "any_leak_rate": _mean(x > 0 for x in leak)}
    nl = [r.not_locatable_fp for r in arm_recs if r.not_locatable_fp is not None]
    out["not_locatable_fpr"] = {"n": len(nl), "rate": _mean(nl)}
    out["report"] = {"n": len(report_recs), "report_hit": _mean(r.report_hit for r in report_recs)}
    by_label: dict[str, list[_ArmScore]] = defaultdict(list)
    for r in arm_recs:
        for a in r.arms:
            by_label[a.label].append(a)
    out["by_label"] = {lab: {"n": len(arms), **{f"{n}_f1": _mean(a.prf[n]["f1"] for a in arms)
                                                 for n in SET_NAMES}}
                       for lab, arms in sorted(by_label.items())}
    return out


def _counts_block(recs: Sequence[_Rec]) -> dict:
    arm_recs = [r for r in recs if r.tier != "report"]
    return {"n": len(arm_recs), "nk_em": _mean(r.counts_nk_em for r in arm_recs)}


def _pvalues_block(recs: Sequence[_Rec]) -> dict:
    with_p = [r for r in recs if r.gold_p[0] is not None]
    with_test = [r for r in recs if r.test_bucket is not None]
    buckets = Counter(r.test_bucket for r in with_test)
    return {"n_with_gold_p": len(with_p),
            "p_claim_agree": _mean(r.p_claim_ok for r in with_p),
            "p_opposite_agree": _mean(r.p_opposite_ok for r in with_p),
            "n_none_agreement": len(recs),
            "none_agreement": _mean(r.none_ok for r in recs),
            "tol": P_TOL,
            "n_test_bucket": len(with_test),
            "test_bucket": {b: buckets.get(b, 0) for b in TEST_BUCKETS}}


def _attribution_block(recs: Sequence[_Rec]) -> dict:
    reached = Counter()
    wrong = Counter()
    lucky = Counter()
    sub_wrong = Counter()
    sub_lucky = Counter()
    for r in recs:
        stop = STAGES.index(r.first_failure) + 1 if r.first_failure else len(STAGES)
        for s in STAGES[:stop]:
            reached[s] += 1
        if r.first_failure:
            (lucky if r.correct else wrong)[r.first_failure] += 1
            if r.first_failure == "S1-procedure" and r.procedure_bucket:
                (sub_lucky if r.correct else sub_wrong)[r.procedure_bucket] += 1
    stages = {s: {"wrong": wrong[s], "lucky": lucky[s], "reached": reached[s],
                  "rate_wrong": _rate(wrong[s], reached[s]),
                  "rate_any": _rate(wrong[s] + lucky[s], reached[s])} for s in STAGES}
    n_wrong = sum(not r.correct for r in recs)
    n_correct = len(recs) - n_wrong
    s1_ok = [r for r in recs if r.first_failure not in S1_STAGES]
    s12_ok = [r for r in s1_ok if r.first_failure not in S2_STAGES]
    gold_forced = {
        "S1": {"n": len(recs), "errors": len(recs) - len(s1_ok),
               "rate": _rate(len(recs) - len(s1_ok), len(recs))},
        "S2": {"n": len(s1_ok), "errors": len(s1_ok) - len(s12_ok),
               "rate": _rate(len(s1_ok) - len(s12_ok), len(s1_ok))},
        "S3": {"n": len(s12_ok), "errors": sum(r.first_failure in S3_STAGES for r in s12_ok),
               "rate": _rate(sum(r.first_failure in S3_STAGES for r in s12_ok), len(s12_ok))},
    }
    return {"order": list(STAGES), "n_wrong": n_wrong, "n_correct": n_correct,
            "stages": stages,
            "procedure_subbuckets": {b: {"wrong": sub_wrong[b], "lucky": sub_lucky[b]}
                                     for b in PROCEDURE_SUBBUCKETS},
            "lucky": {"count": sum(lucky.values()), "rate": _rate(sum(lucky.values()), n_correct),
                      "by_stage": {s: lucky[s] for s in STAGES if lucky[s]}},
            "gold_forced": gold_forced}


def _consistency_block(recs: Sequence[_Rec]) -> dict:
    # mirror pairs: cores with exactly two scored instances, records paired by (register, format)
    by_core: dict[str, dict[str, dict[tuple, _Rec]]] = defaultdict(lambda: defaultdict(dict))
    for r in recs:
        if r.core_id:
            by_core[r.core_id][r.iid][(r.register, r.fmt)] = r
    n_pairs = n_contra = n_pair_correct = n_cores = 0
    for core, insts in by_core.items():
        if len(insts) != 2:
            continue
        n_cores += 1
        a, b = insts.values()
        for key in sorted(set(a) & set(b), key=str):
            ra, rb = a[key], b[key]
            n_pairs += 1
            if ra.response in DECISIVE and ra.response == rb.response:
                n_contra += 1
            if ra.correct and rb.correct:
                n_pair_correct += 1
    # twins: same fact_id AND the same ASSERTED claim -- identical oriented events,
    # same negation and same cohort order -- across distinct instances. Negation
    # (C-V1/C-V2/C-V3) and the vaccine swap (P-M2) orient a claim without moving
    # its events, so a key on events alone would pair every such mirror with its
    # own opposite and report the gold itself as 29% inconsistent.
    by_twin: dict[tuple, dict[tuple, dict[str, _Rec]]] = defaultdict(lambda: defaultdict(dict))
    for r in recs:
        if r.fact_id:
            twin_key = (r.fact_id, r.gold_events, r.negated,
                        tuple(c.vaccine for c in r.gold_claim.cohorts))
            by_twin[twin_key][(r.register, r.fmt)][r.iid] = r
    n_twin = n_twin_ok = 0
    n_twin_groups = 0
    for key, slices in by_twin.items():
        if len({iid for s in slices.values() for iid in s}) < 2:
            continue
        n_twin_groups += 1
        for s in slices.values():
            if len(s) < 2:
                continue
            n_twin += 1
            if len({r.response for r in s.values()}) == 1:
                n_twin_ok += 1
    # register / format invariance per instance
    by_inst: dict[str, list[_Rec]] = defaultdict(list)
    for r in recs:
        by_inst[r.iid].append(r)
    multi = [rs for rs in by_inst.values() if len(rs) >= 2]
    invariant = sum(len({r.response for r in rs}) == 1 for rs in multi)
    by_reg: dict[str, list[bool]] = defaultdict(list)
    for r in recs:
        by_reg[str(r.register)].append(r.correct)
    acc_reg = {k: _mean(v) for k, v in sorted(by_reg.items())}
    base = acc_reg.get("original")
    delta = {k: (v - base if (base is not None and v is not None) else None)
             for k, v in acc_reg.items()}
    return {
        "pairs": {"n_cores": n_cores, "n_pairs": n_pairs,
                  "contradiction_rate": _rate(n_contra, n_pairs),
                  "correct_rate": _rate(n_pair_correct, n_pairs)},
        "twins": {"n_groups": n_twin_groups, "n": n_twin, "consistent_rate": _rate(n_twin_ok, n_twin)},
        "invariance": {"n_instances": len(multi), "invariant_rate": _rate(invariant, len(multi)),
                       "per_register_accuracy": acc_reg, "per_register_delta": delta},
    }


def _choice_block(recs: Sequence[_Rec]) -> dict:
    ch = [r for r in recs if r.answer_type == "CHOICE"]

    def opt(options, i):
        return options[i] if options is not None and len(options) > i else None

    def baselines(rs, attr):
        return {"options_0": _mean(opt(getattr(r, attr), 0) == r.gold_answer for r in rs),
                "options_2": _mean(opt(getattr(r, attr), 2) == r.gold_answer for r in rs)}

    by_group: dict[str, list[_Rec]] = defaultdict(list)
    for r in ch:
        by_group[r.group].append(r)
    return {
        "n": len(ch),
        "answer_acc": _mean(r.pred_answer == r.gold_answer for r in ch),
        "n_gold_none": sum(r.gold_answer is None for r in ch),
        "none_acc": _mean((r.pred_answer is None) == (r.gold_answer is None) for r in ch),
        "baselines_presented": baselines(ch, "pred_options"),
        "baselines_gold_order": baselines(ch, "gold_options"),
        "by_group": {g: {"n": len(rs), "answer_acc": _mean(r.pred_answer == r.gold_answer for r in rs),
                         **{f"{k}_gold_order": v for k, v in baselines(rs, "gold_options").items()}}
                     for g, rs in sorted(by_group.items())},
    }


def _underdetermined_block(und: Sequence[_Rec], all_recs: Sequence[_Rec]) -> dict:
    """``und`` = the rows set aside (template-underdetermined); ``flagged`` = every
    row the prediction marked underdetermined, including model-induced ones that
    stayed in the scored set (reported as ``unexpected``)."""
    flagged = [r for r in all_recs if r.underdetermined]
    by = Counter(f"{r.group}|{r.register}" for r in flagged)
    return {"n": len(flagged),
            "n_excluded": len(und),
            "n_response_underdetermined": sum(r.response == UNDERDETERMINED for r in flagged),
            # recovery rate on the rows the template really leaves underdetermined
            "rate": _mean(r.response == UNDERDETERMINED for r in und),
            "by_group_register": dict(sorted(by.items())),
            "expected_by_template": sum((r.group, r.register) in TEMPLATE_UNDERDETERMINED
                                        for r in all_recs),
            "unexpected": sum((r.group, r.register) not in TEMPLATE_UNDERDETERMINED
                              for r in flagged)}


def _per_group_block(recs: Sequence[_Rec]) -> dict:
    by_group: dict[str, list[_Rec]] = defaultdict(list)
    for r in recs:
        by_group[r.group].append(r)
    out = {}
    for g, rs in sorted(by_group.items()):
        block = _verdict_summary(rs, _classes_for(rs))
        block.pop("per_class")
        arm_rs = [r for r in rs if r.tier != "report"]
        rep_rs = [r for r in rs if r.tier == "report"]
        wrong = Counter(r.first_failure for r in rs if not r.correct)
        top = wrong.most_common(1)
        block.update({
            "tier": rs[0].tier,
            "s1_claim_em": _mean(r.s1["claim_em"] for r in rs),
            "s2_denominator_f1": _mean(_mean(a.prf["denominator"]["f1"] for a in r.arms)
                                       for r in arm_rs),
            "report_hit": _mean(r.report_hit for r in rep_rs),
            "coexist_leak": _mean(r.coexist_leak for r in arm_rs),
            "n_wrong": sum(not r.correct for r in rs),
            "attribution_top": {"stage": top[0][0], "count": top[0][1]} if top else None,
        })
        out[g] = block
    return out


# ---------------------------------------------------------------------------
# the entry point
# ---------------------------------------------------------------------------

def _score_all(rows: Iterable[Mapping[str, Any]], release: Any, *, options_seed: int
               ) -> tuple[list[_Rec], list[_Rec]]:
    scored: list[_Rec] = []
    und: list[_Rec] = []
    for row in rows:
        gold = release.answer_for(row["hypothesis_id"])
        rec = _score_row(row, gold, options_seed=options_seed)
        # Only rows whose TEMPLATE never names the events are set aside (the
        # 2,292 C-V3 research/clinical + F-V3 research rows). A model that
        # answers `underdetermined` -- or emits a claim with missing events --
        # on a fully specified input is scored like any other wrong response,
        # so the token cannot be used to opt out of hard items.
        if rec.underdetermined and (rec.group, rec.register) in TEMPLATE_UNDERDETERMINED:
            und.append(rec)
        else:
            scored.append(rec)
    return scored, und


def evaluate(rows: Iterable[Mapping[str, Any]], release: Any, *, options_seed: int = 0,
             min_group_size: int = 30, bootstrap: int = 200, seed: int = 0) -> dict:
    """Score prediction rows against the gold ``release.answer_for`` returns.

    Returns the ``metrics.json`` content (JSON-serialisable; all keys strings).
    Underdetermined rows (``claim.underdetermined`` non-empty or
    ``response == "underdetermined"``) appear only in ``underdetermined``.
    """
    rows = list(rows)
    recs, und = _score_all(rows, release, options_seed=options_seed)
    verdict = _verdict_block(recs, min_group_size=min_group_size, bootstrap=bootstrap, seed=seed)
    return {
        "n": {"total_rows": len(rows), "records": len(recs),
              "instances": len({r.iid for r in recs}),
              "facts": len({r.fact_id or r.iid for r in recs}),
              "underdetermined": len(und),
              "errors": sum(r.error is not None for r in recs),
              "no_response": sum(r.response is None for r in recs)},
        "verdict": verdict,
        "extraction": _extraction_block(recs),
        "retrieval": _retrieval_block(recs),
        "counts": _counts_block(recs),
        "pvalues": _pvalues_block(recs),
        "consistency": _consistency_block(recs),
        "attribution": _attribution_block(recs),
        "choice": _choice_block(recs),
        "underdetermined": _underdetermined_block(und, recs + und),
        "per_group": _per_group_block(recs),
        "per_tier": _breakdown(recs, lambda r: r.tier),
        "per_family": _breakdown(recs, lambda r: r.family),
        "per_register": _breakdown(recs, lambda r: r.register),
        "per_format": _breakdown(recs, lambda r: r.fmt),
        "per_negated": _breakdown(recs, lambda r: r.negated),
        "per_subtype": _per_subtype(recs),
        "excluded_groups": [e["group"] for e in verdict["group_macro"]["excluded_groups"]],
        "config": {"options_seed": options_seed, "min_group_size": min_group_size,
                   "bootstrap": bootstrap, "seed": seed, "p_tol": P_TOL,
                   "pipelines": sorted({str(r.get("pipeline")) for r in rows}),
                   "models": sorted({str(r.get("model")) for r in rows}),
                   "conditions": sorted({str(r.get("condition")) for r in rows})},
    }


def _per_subtype(recs: Sequence[_Rec]) -> dict:
    insuf = [r for r in recs if r.gold_verdict == INSUFFICIENT]
    out = _breakdown(insuf, lambda r: r.gold_subtype)
    for sub, block in out.items():
        rs = [r for r in insuf if str(r.gold_subtype) == sub]
        block["subtype_acc"] = _mean(r.pred_subtype == r.gold_subtype for r in rs)
        block["recall"] = block["accuracy"]      # verdict recall of the insufficient class
    return out


# ---------------------------------------------------------------------------
# report writers
# ---------------------------------------------------------------------------

def _f(x: Any, nd: int = 3) -> str:
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def _table(header: Sequence[str], rows: Iterable[Sequence[Any]], align: str | None = None) -> list[str]:
    align = align or ("|---" + "|--:" * (len(header) - 1) + "|")
    out = ["| " + " | ".join(header) + " |", align]
    for r in rows:
        out.append("| " + " | ".join(_f(c) for c in r) + " |")
    return out


def render_report_md(m: Mapping[str, Any]) -> str:
    """``report.md``: headline block, per-group table, attribution, consistency,
    underdetermined, retrieval, extraction, p-values, breakdowns."""
    n, v, gm = m["n"], m["verdict"], m["verdict"]["group_macro"]
    cfg = m["config"]
    ci = f" [95% CI {_f(gm['ci95'][0])}–{_f(gm['ci95'][1])}]" if gm.get("ci95") else ""
    excluded = ", ".join(f"{e['group']} ({e['n_instances']})" for e in gm["excluded_groups"]) or "none"
    out = ["# Evaluation report", "",
           f"- pipeline: {', '.join(cfg['pipelines'])}; model: {', '.join(cfg['models'])}; "
           f"condition: {', '.join(cfg['conditions'])}",
           f"- scored records: {n['records']} ({n['instances']} instances, {n['facts']} distinct facts); "
           f"underdetermined rows: {n['underdetermined']}; total rows: {n['total_rows']}; "
           f"rows with errors: {n['errors']}", "",
           "## Headline", ""]
    ch = m["choice"]
    out += _table(["metric", "value"], [
        ("verdict micro accuracy", v["accuracy"]),
        ("class-macro-F1 (supported / refuted / insufficient)", v["class_macro_f1"]),
        (f"group-macro-F1 (groups with >= {gm['min_group_size']} instances; {len(gm['groups'])} group(s))",
         f"{_f(gm['f1'])}{ci}"),
        ("excluded groups (instances)", excluded),
        ("fact-weighted accuracy", v["fact_weighted_accuracy"]),
        (f"insufficient sub-type accuracy (n={v['n_gold_insufficient']})", v["subtype_accuracy"]),
        (f"CHOICE answer accuracy (n={ch['n']}; None is a class)", ch["answer_acc"]),
        ("CHOICE trivial baselines options[0] / options[2] (as presented)",
         f"{_f(ch['baselines_presented']['options_0'])} / {_f(ch['baselines_presented']['options_2'])}"),
        ("CHOICE trivial baselines options[0] / options[2] (gold order)",
         f"{_f(ch['baselines_gold_order']['options_0'])} / {_f(ch['baselines_gold_order']['options_2'])}"),
    ])
    out += ["", "Per class:", ""]
    out += _table(["class", "gold n", "pred n", "precision", "recall", "F1"],
                  [(c, d["gold_n"], d["pred_n"], d["precision"], d["recall"], d["f1"])
                   for c, d in v["per_class"].items()])
    out += ["", "## Per group", ""]
    out += _table(["group", "tier", "n", "acc", "macro-F1", "S1 claim_em", "S2 den F1",
                   "coexist_leak", "attribution top"],
                  [(g, b["tier"], b["n"], b["accuracy"], b["class_macro_f1"], b["s1_claim_em"],
                    (f"hit {_f(b['report_hit'])}" if b["tier"] == "report" else b["s2_denominator_f1"]),
                    b["coexist_leak"],
                    (f"{b['attribution_top']['stage']} ({b['attribution_top']['count']})"
                     if b["attribution_top"] else "—"))
                   for g, b in m["per_group"].items()],
                  align="|---|---|--:|--:|--:|--:|--:|--:|---|")
    out += ["", "Report-tier groups show `report_hit` in the S2 column (no denominator). "
            "Groups below the minimum size are listed above and left out of the group-macro.", ""]
    a = m["attribution"]
    out += ["## Attribution", "",
            f"Wrong verdicts: {a['n_wrong']}; correct: {a['n_correct']}; lucky (correct despite an "
            f"earlier failure): {a['lucky']['count']} ({_f(a['lucky']['rate'])} of correct). "
            "Each wrong verdict is charged to the EARLIEST failing stage; `reached` is the stage's "
            "denominator (rows with no earlier failure).", ""]
    out += _table(["stage", "wrong", "lucky", "reached", "wrong rate", "failure rate"],
                  [(s, d["wrong"], d["lucky"], d["reached"], d["rate_wrong"], d["rate_any"])
                   for s, d in a["stages"].items()], align="|---|--:|--:|--:|--:|--:|")
    subs = ", ".join(f"{b}: {d['wrong']} wrong / {d['lucky']} lucky"
                     for b, d in a["procedure_subbuckets"].items())
    out += ["", f"S1-procedure sub-buckets: {subs}.", "",
            "Gold-forced marginals (S2 among rows with a correct S1; S3 among rows with correct S1 and S2):", ""]
    out += _table(["stage", "n", "errors", "rate"],
                  [(s, d["n"], d["errors"], d["rate"]) for s, d in a["gold_forced"].items()],
                  align="|---|--:|--:|--:|")
    c = m["consistency"]
    out += ["", "## Consistency", ""]
    out += _table(["metric", "n", "value"], [
        ("mirror-pair contradiction rate (same decisive response to both)", c["pairs"]["n_pairs"],
         c["pairs"]["contradiction_rate"]),
        ("mirror-pair both-correct rate", c["pairs"]["n_pairs"], c["pairs"]["correct_rate"]),
        ("twin consistency (same fact_id, identical asserted claim)", c["twins"]["n"], c["twins"]["consistent_rate"]),
        ("register/format invariance (instances with >= 2 scored texts)",
         c["invariance"]["n_instances"], c["invariance"]["invariant_rate"]),
    ], align="|---|--:|--:|")
    out += ["", "Per-register accuracy (delta vs `original`):", ""]
    out += _table(["register", "accuracy", "delta"],
                  [(r, acc, c["invariance"]["per_register_delta"].get(r))
                   for r, acc in c["invariance"]["per_register_accuracy"].items()],
                  align="|---|--:|--:|")
    out += ["", "Caveat: P-V2/P-V4 register invariance is confounded by issue 24 "
            "(count-vs-rate wording differs across registers).", ""]
    u = m["underdetermined"]
    out += ["## Underdetermined", "",
            f"- rows classified underdetermined (claim.underdetermined non-empty or response "
            f"`underdetermined`): {u['n']}; responded `underdetermined`: {u['n_response_underdetermined']} "
            f"(rate {_f(u['rate'])})",
            f"- expected from the templates (C-V3 research/clinical, F-V3 research): "
            f"{u['expected_by_template']}; classified rows outside those templates: {u['unexpected']}",
            f"- by group|register: {u['by_group_register'] or '{}'}", ""]
    r = m["retrieval"]
    out += ["## Retrieval", "",
            f"Scored over {r['n']} non-report records ({r['n_report']} report-tier records scored as "
            "`report_hit`, kept out of the set averages). 0/0 convention: P=R=F1=1 iff both sets are "
            "empty, 0 if the gold is empty and the prediction is not.", ""]
    out += _table(["set", "precision", "recall", "F1", "EM"],
                  [(s, r[s]["precision"], r[s]["recall"], r[s]["f1"], r[s]["em"]) for s in SET_NAMES],
                  align="|---|--:|--:|--:|--:|")
    out += ["",
            f"- all sets exact: {_f(r['all_sets_em'])}; (n, k) from the arms exact: {_f(r['arms_nk_em'])}",
            f"- coexist_leak (n={r['coexist_leak']['n']} records with gold exclusions): mean "
            f"{_f(r['coexist_leak']['mean'])}, any-leak rate {_f(r['coexist_leak']['any_leak_rate'])}",
            f"- not_locatable false-positive rate (n={r['not_locatable_fpr']['n']}): "
            f"{_f(r['not_locatable_fpr']['rate'])}",
            f"- report_hit (n={r['report']['n']}): {_f(r['report']['report_hit'])}", ""]
    e = m["extraction"]
    out += ["## Extraction (S1)", "",
            f"- n={e['n']}; no claim: {e['n_no_claim']}; invalid claim: {e['n_claim_invalid']}",
            f"- mode_acc {_f(e['mode_acc'])}; events ordered EM {_f(e['events_ordered_em'])}; "
            f"events set EM {_f(e['events_set_em'])}; cohort EM {_f(e['cohort_em'])}; "
            f"negated_acc {_f(e['negated_acc'])}; asserted_option_acc {_f(e['asserted_option_acc'])} "
            f"(n_choice={e['n_choice']}); claim_em {_f(e['claim_em'])}",
            f"- per role: " + ", ".join(f"{k} {_f(v)}" for k, v in e["per_role"].items()),
            f"- procedure per field: " + ", ".join(f"{k} {_f(v)}" for k, v in e["procedure"].items())
            + f"; procedure_em {_f(e['procedure_em'])}", ""]
    p, k = m["pvalues"], m["counts"]
    out += ["## Counts and p-values (S3)", "",
            f"- (n, k[, n2, k2]) exact match: {_f(k['nk_em'])} (n={k['n']})",
            f"- p_claim agreement within {p['tol']}: {_f(p['p_claim_agree'])}; p_opposite: "
            f"{_f(p['p_opposite_agree'])} (n={p['n_with_gold_p']} with a gold p)",
            f"- None-ness agreement: {_f(p['none_agreement'])} (n={p['n_none_agreement']})",
            f"- test bucket (n={p['n_test_bucket']}): " + ", ".join(f"{b} {c}" for b, c in p["test_bucket"].items()),
            ""]
    out += ["## Breakdowns", ""]
    for key, title in (("per_tier", "tier"), ("per_family", "family"), ("per_register", "register"),
                       ("per_format", "format"), ("per_negated", "negated"), ("per_subtype", "gold sub-type")):
        block = m[key]
        if not block:
            continue
        out += [f"### by {title}", ""]
        extra = ["subtype acc"] if key == "per_subtype" else []
        out += _table([title, "n", "instances", "acc", "macro-F1"] + extra,
                      [(kk, b["n"], b["n_instances"], b["accuracy"], b["class_macro_f1"])
                       + ((b.get("subtype_acc"),) if extra else ())
                       for kk, b in block.items()],
                      align="|---" + "|--:" * (4 + len(extra)) + "|")
        out.append("")
    return "\n".join(out)


def _question_text(release: Any, hid: str, cache: dict) -> str | None:
    """Best-effort lookup of the hypothesis text (the prediction row has none)."""
    q = getattr(release, "question_for", None)
    if callable(q):
        try:
            return q(hid).get("text")
        except (KeyError, AttributeError, TypeError):
            return None
    if "index" not in cache:
        idx = {}
        for row in getattr(release, "questions", None) or ():
            if isinstance(row, Mapping) and "hypothesis_id" in row:
                idx[row["hypothesis_id"]] = row.get("text")
        cache["index"] = idx
    return cache["index"].get(hid)


def _severity(rec: _Rec) -> tuple:
    """Sort key: worst first. No response, then a supported<->refuted flip, then
    the rest; earlier failing stage, then larger set errors."""
    if rec.response is None:
        flip = 3
    elif rec.gold_verdict in DECISIVE and rec.response in DECISIVE:
        flip = 2
    else:
        flip = 1
    stage = STAGES.index(rec.first_failure) if rec.first_failure else len(STAGES)
    set_err = sum(len(a.pred[n] ^ a.gold[n]) for a in rec.arms for n in SET_NAMES)
    return (-flip, stage, -set_err, rec.hid)


def _describe_claim(c: StructuredClaim | None) -> str:
    if c is None:
        return "no parse"
    cohort = ", ".join(f"VAERS-{co.report_id}" if co.report_id is not None else str(co.vaccine)
                       for co in c.cohorts)
    s = (f"mode={c.mode}  events={list(c.terms)}  cohort=[{cohort}]  negated={c.negated}"
         f"  asserted_option={c.asserted_option!r}")
    if c.underdetermined:
        s += f"  underdetermined={list(c.underdetermined)}"
    return s


def _ids(ids: Iterable[int], limit: int = 5) -> str:
    ids = sorted(ids)
    s = ", ".join(str(i) for i in ids[:limit])
    return s + (f", … (+{len(ids) - limit})" if len(ids) > limit else "")


def _failure_entry(i: int, rec: _Rec, text: str | None) -> list[str]:
    gsub = f" ({rec.gold_subtype})" if rec.gold_subtype else ""
    psub = f" ({rec.pred_subtype})" if rec.pred_subtype else ""
    neg = "  [NEGATED wording]" if rec.negated else ""
    out = [f"## {i}. {rec.hid} ({rec.group}, {rec.mode}, {rec.answer_type}) -- gold "
           f"**{rec.gold_verdict}{gsub}**, predicted **{rec.response}{psub}**{neg}"]
    out.append(f"- text: \"{text}\"" if text else "- text: (not available -- pass rows= and a release "
               "with `questions` to write_report)")
    out.append(f"- register/format: {rec.register} / {rec.fmt}")
    attr = rec.first_failure or "none"
    if rec.first_failure == "S1-procedure" and rec.procedure_bucket:
        attr += f" [{rec.procedure_bucket}]"
    if rec.coexist_leak:
        attr += f"  (coexist_leak = {rec.coexist_leak:.3f})"
    out.append(f"- attribution: **{attr}**")
    if rec.error:
        out.append(f"- pipeline error: {rec.error}")
    if rec.procedure_errors:
        out.append(f"- procedure errors: {rec.procedure_errors}")
    out.append(f"- gold claim:      {_describe_claim(rec.gold_claim)}")
    out.append(f"- predicted claim: {_describe_claim(rec.pred_claim)}")
    bad = [f for f, ok in rec.proc_ok.items() if not ok]
    if bad and rec.pred_claim is not None:
        gp, pp = rec.gold_claim.procedure, rec.pred_claim.procedure
        diffs = []
        for f_ in bad:
            g_val = _proc_field(gp, f_)
            p_val = _proc_field(pp, f_)
            diffs.append(f"{f_}: gold {g_val!r} vs predicted {p_val!r}")
        out.append("- procedure differs: " + "; ".join(diffs))
    if rec.tier != "report":
        gn, gk, gn2, gk2 = rec.gold_nk
        pn, pk, pn2, pk2 = rec.pred_nk
        two = gn2 is not None or pn2 is not None
        nk = f"- **n/k: gold {gn}/{gk}, predicted {pn}/{pk}**"
        if two:
            nk += f"   n2/k2: gold {gn2}/{gk2}, predicted {pn2}/{pk2}"
        out.append(nk)
    out.append(f"- test: gold {rec.gold_test}  p_claim={rec.gold_p[0]}  p_opposite={rec.gold_p[1]}"
               f"   |   predicted {rec.pred_test}  p_claim={rec.pred_p[0]}  p_opposite={rec.pred_p[1]}")
    if rec.answer_type == "CHOICE":
        out.append(f"- CHOICE answer: gold {rec.gold_answer!r}, predicted {rec.pred_answer!r}"
                   f"   options (gold order) {rec.gold_options}")
    if rec.tier == "report":
        out.append(f"  - report levels predicted: {rec.levels if rec.levels is not None else 'none'}"
                   f"   claim events: {list(rec.gold_events)}   report_hit: {_f(rec.report_hit)}")
    for a in rec.arms:
        label = f"{a.label} " if len(rec.arms) > 1 else ""
        for name in SET_NAMES:
            g, p = a.gold[name], a.pred[name]
            missing, extra = g - p, p - g
            line = (f"  - {label}{name}: gold {len(g)}, predicted {len(p)}, missing {len(missing)}, "
                    f"extra {len(extra)}  (P={_f(a.prf[name]['precision'])} R={_f(a.prf[name]['recall'])} "
                    f"F1={_f(a.prf[name]['f1'])})")
            out.append(line)
            if missing:
                out.append(f"      - missing ids: {_ids(missing)}")
            if extra:
                out.append(f"      - extra ids: {_ids(extra)}")
        if a.leak_total:
            out.append(f"  - {label}co-exist leak: {a.leak_hit} of {a.leak_total} gold-excluded reports "
                       f"in the predicted denominator")
    out.append("")
    return out


def _proc_field(p: Procedure, name: str) -> Any:
    if name.startswith("null."):
        return getattr(p.null, name.split(".", 1)[1])
    return getattr(p, name)


def render_failures_md(metrics: Mapping[str, Any], rows: Iterable[Mapping[str, Any]] | None,
                       release: Any, *, limit: int = 25) -> str:
    """``failures.md``: the worst ``limit`` wrong records in the ``validation_sample.md``
    style -- the text, gold vs predicted claim, n/k, the sets' sizes and up to five
    example ids from each difference, and the attributed stage."""
    out = ["# Failures (worst wrong records)", "",
           "For each entry: the hypothesis text, the gold claim against the predicted claim, "
           "the counts, the predicted evidence sets against `evidence_ids` (missing = gold ids the "
           "retrieval did not return; extra = returned ids not in the gold), the p-values, and "
           "the stage the wrong verdict is charged to (the EARLIEST failing stage).", "",
           "Ordering: no response first, then supported<->refuted flips, then the rest; within a "
           "class the earlier failing stage and the larger set error rank worse.", ""]
    if rows is None or release is None:
        out.append("(prediction rows not supplied -- call `write_report(..., rows=, release=)` "
                   "to list the failing records)")
        return "\n".join(out)
    seed = int((metrics.get("config") or {}).get("options_seed", 0))
    recs, _ = _score_all(list(rows), release, options_seed=seed)
    wrong = sorted((r for r in recs if not r.correct), key=_severity)
    out.append(f"{len(wrong)} wrong of {len(recs)} scored records; showing {min(limit, len(wrong))}.")
    out.append("")
    cache: dict = {}
    for i, rec in enumerate(wrong[:limit], 1):
        out += _failure_entry(i, rec, _question_text(release, rec.hid, cache))
    return "\n".join(out)


def _json_default(o: Any) -> Any:
    if isinstance(o, (set, frozenset, tuple)):
        return sorted(o) if isinstance(o, (set, frozenset)) else list(o)
    raise TypeError(f"not JSON serialisable: {type(o).__name__}")


def write_report(metrics: Mapping[str, Any], out_dir: Path, *,
                 rows: Iterable[Mapping[str, Any]] | None = None,
                 release: Any = None) -> dict[str, Path]:
    """Write ``metrics.json`` (sorted keys, indent 2), ``report.md`` and ``failures.md``.

    ``failures.md`` needs the prediction ``rows`` and the ``release`` to rescore
    the wrong records; without them it carries a note instead of entries.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = list(rows) if rows is not None else None
    paths = {"metrics": out_dir / "metrics.json", "report": out_dir / "report.md",
             "failures": out_dir / "failures.md"}
    paths["metrics"].write_text(json.dumps(metrics, indent=2, sort_keys=True, ensure_ascii=False,
                                           default=_json_default) + "\n", encoding="utf-8")
    paths["report"].write_text(render_report_md(metrics) + "\n", encoding="utf-8")
    paths["failures"].write_text(render_failures_md(metrics, rows, release) + "\n", encoding="utf-8")
    return paths
