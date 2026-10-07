"""Tests for ``framework.run_test`` -- the Stage-3 oracle hookup.

Four layers: (1) release rows reproduced from their ``evidence_ids`` alone (no
SQL, no compiler), (2) ``report_rule`` against every report-tier gold row, (3)
procedure-honouring == gold-procedure on a stratified cohort sample with arms
rebuilt from the corpus, (4) unit cases for the causal procedure failures
(wrong tail, wrong floor, Fisher with one arm, unknown test), the
``underdetermined`` token, and the F-V1 named-cell trap.
"""

from __future__ import annotations

import gzip
import json
import random
import sqlite3
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import pytest

from temporal_hypo.core.answers import core_significance
from temporal_hypo.core.significance import binom_exact_p
from temporal_hypo.framework.claim_schema import (
    MODE_SPEC,
    RESPONSES,
    NullSpec,
    Procedure,
    build_claim,
    derive_procedure,
    from_gold,
)
from temporal_hypo.framework.run_test import (
    PROCEDURE_MODES,
    Prediction,
    report_rule,
    run_test,
    to_viable_core,
)
from temporal_hypo.framework.sql.aggregate import ArmCounts
from temporal_hypo.generation import evidence as ev
from temporal_hypo.generation.corpus import CorpusIndex, relation
from tests.framework.conftest import RELEASE_DIR, RELEASE_STEM, REPO_ROOT, needs_release

DB_PATH = REPO_ROOT / "data" / "medtempo.db"
needs_db = pytest.mark.skipif(not DB_PATH.exists(), reason="data/medtempo.db not present")

ARGMAX_MODES = {"seq_bool", "modal_choice", "first_choice", "first_bool",
                "last_choice", "cooc_modal_bool"}
COHORT = {"level": "vaccine", "vaccines": ["Pfizer"], "report_id": None}
REPORT = {"level": "report", "vaccines": [], "report_id": 1001}


# ---------------------------------------------------------------------------
# helpers: a Retrieval stand-in and arms rebuilt from evidence ids / the corpus
# ---------------------------------------------------------------------------

@dataclass
class _Retrieval:
    """Duck-typed stand-in for ``sql.retrieve.Retrieval`` (only .arms/.levels are read)."""

    arms: list = field(default_factory=list)
    levels: dict | None = None


def _arm(n: int, k: int, counts: dict | None = None, *, ids: bool = True) -> ArmCounts:
    den = set(range(1, n + 1)) if ids else set()
    num = set(range(1, k + 1)) if ids else set()
    return ArmCounts(n=n, k=k, denominator_ids=den, numerator_ids=num,
                     excluded_ids=set(), counts=dict(counts or {}))


@lru_cache(maxsize=None)
def _answers() -> list[dict]:
    gz = RELEASE_DIR / f"{RELEASE_STEM}_answers.jsonl.gz"
    plain = RELEASE_DIR / f"{RELEASE_STEM}_answers.jsonl"
    opener = (lambda: gzip.open(gz, "rt", encoding="utf-8")) if gz.exists() \
        else (lambda: open(plain, encoding="utf-8"))
    with opener() as f:
        return [json.loads(line) for line in f if line.strip()]


@lru_cache(maxsize=None)
def _index() -> CorpusIndex:
    return CorpusIndex.load(sqlite3.connect(str(DB_PATH)))


def _counts_for(index: CorpusIndex, mode: str, terms: tuple, den_ids) -> dict:
    """The argmax table over exactly the denominator reports (cells for denominator rows only)."""
    counts: dict[Any, int] = {}
    for vid in den_ids:
        tmap = index.report_terms[vid]
        if mode in ("seq_bool", "modal_choice"):
            key: Any = tuple(sorted(terms, key=lambda t: tmap[t]))
        elif mode in ("first_choice", "first_bool", "last_choice"):
            idxs = {t: tmap[t] for t in terms}
            target = max(idxs.values()) if mode == "last_choice" else min(idxs.values())
            winners = [t for t in terms if idxs[t] == target]
            assert len(winners) == 1, "a tie must not sit in a first/last denominator"
            key = winners[0]
        elif mode == "cooc_modal_bool":
            key = relation(tmap, terms[0], terms[1])
        else:
            return {}
        counts[key] = counts.get(key, 0) + 1
    return counts


def _arm_from_sets(sets: dict, counts: dict | None = None) -> ArmCounts:
    den, num, exc = (set(sets["denominator"]), set(sets["numerator"]),
                     set(sets.get("excluded", [])))
    return ArmCounts(n=len(den), k=len(num), denominator_ids=den, numerator_ids=num,
                     excluded_ids=exc, counts=dict(counts or {}), n_rows=len(den) + len(exc))


def _retrieval_from_gold(row: dict, index: CorpusIndex | None) -> _Retrieval:
    """Arms straight from the release's ``evidence_ids``; argmax counts from the corpus."""
    e = row["evidence_ids"]
    terms = tuple(row["factual_core"]["events"])
    if "report_id" in e:
        assert index is not None
        tmap = index.report_terms[e["report_id"]]
        return _Retrieval([], {t: tmap[t] for t in terms if t in tmap})
    if "cohort_1" in e:
        return _Retrieval([_arm_from_sets(e["cohort_1"]), _arm_from_sets(e["cohort_2"])], None)
    counts = _counts_for(index, row["mode"], terms, e["denominator"]) \
        if (index is not None and row["mode"] in ARGMAX_MODES) else {}
    return _Retrieval([_arm_from_sets(e, counts)], None)


def _arms_from_index(index: CorpusIndex, claim) -> list[ArmCounts]:
    """The reference conditioning for a claim, evaluated in memory over the corpus.

    Mirrors ``generation.evidence.evidence_ids`` on the claim's ORIENTED terms and
    cohorts, then adds the argmax table over the denominator -- what a correct
    Stage-2 retrieval hands Stage 3.
    """
    m, t = claim.mode, tuple(claim.terms)
    if m == "multi_dir_precedes":
        v1, v2 = claim.vaccines
        return [_arm_from_sets(ev._pair_sets(index, t[0], t[1], index.cohort(v1))),
                _arm_from_sets(ev._pair_sets(index, t[0], t[1], index.cohort(v2)))]
    cohort = index.cohort(claim.vaccines[0])
    if m in ("dir_bool", "dir_choice"):
        return [_arm_from_sets(ev._pair_sets(index, t[0], t[1], cohort))]
    if m in ("sym_bool_cooccurs", "cooc_modal_bool"):
        sets = ev._cooccur_sets(index, t[0], t[1], cohort)
        return [_arm_from_sets(sets, _counts_for(index, m, t, sets["denominator"]))]
    if m in ("seq_bool", "modal_choice"):
        sets = ev._ordering_sets(index, t, cohort)
        return [_arm_from_sets(sets, _counts_for(index, m, t, sets["denominator"]))]
    if m in ("first_choice", "first_bool", "last_choice"):
        sets = ev._extreme_sets(index, t, cohort, named=t[0], last=(m == "last_choice"))
        return [_arm_from_sets(sets, _counts_for(index, m, t, sets["denominator"]))]
    if m == "antecedent_bool":
        return [_arm_from_sets(ev._pair_sets(index, t[0], t[1], cohort)),
                _arm_from_sets(ev._pair_sets(index, t[2], t[1], cohort))]
    if m == "pairpair_bool":
        return [_arm_from_sets(ev._pair_sets(index, t[0], t[1], cohort)),
                _arm_from_sets(ev._pair_sets(index, t[2], t[3], cohort))]
    if m == "assoc_bool":
        with_a, without_a, both, b_only = [], [], [], []
        for vid in cohort:
            tm = index.report_terms[vid]
            if t[0] in tm:
                with_a.append(vid)
                if t[1] in tm:
                    both.append(vid)
            else:
                without_a.append(vid)
                if t[1] in tm:
                    b_only.append(vid)
        return [_arm_from_sets({"denominator": with_a, "numerator": both, "excluded": []}),
                _arm_from_sets({"denominator": without_a, "numerator": b_only, "excluded": []})]
    raise AssertionError(f"no in-memory conditioning for {m}")


def _ids_of(arms: list[ArmCounts]) -> list[tuple[set, set, set]]:
    return [(a.denominator_ids, a.numerator_ids, a.excluded_ids) for a in arms]


def _gold_ids(row: dict) -> list[tuple[set, set, set]]:
    e = row["evidence_ids"]
    blocks = [e["cohort_1"], e["cohort_2"]] if "cohort_1" in e else [e]
    return [(set(b["denominator"]), set(b["numerator"]), set(b.get("excluded", [])))
            for b in blocks]


def _assert_matches_gold(pred: Prediction, row: dict) -> None:
    assert pred.response == pred.verdict == row["gold_verdict"], row["instance_id"]
    assert pred.subtype == row["insufficient_subtype"], row["instance_id"]
    assert pred.test == row["sig_test"], row["instance_id"]
    for mine, gold in ((pred.p_claim, row["p_claim"]), (pred.p_opposite, row["p_opposite"])):
        if gold is None:
            assert mine is None, row["instance_id"]
        else:
            assert mine is not None and abs(mine - gold) < 1e-6, (row["instance_id"], mine, gold)
    assert (pred.n, pred.k, pred.n2, pred.k2) == (row["gold_n"], row["gold_k"],
                                                  row["gold_n2"], row["gold_k2"]), row["instance_id"]
    assert pred.answer == row["gold_answer"], row["instance_id"]
    assert pred.procedure_errors == [] and pred.notes == [], row["instance_id"]


# ---------------------------------------------------------------------------
# (1) release rows from their evidence ids, no DB query, no compiler
# ---------------------------------------------------------------------------

_RELEASE_CASES = ["P-V1", "P-V3", "P-M2", "P-V2", "P-V4", "C-V1", "C-V1:negated",
                  "C-V2", "C-V2:negated", "C-V3", "C-V3:negated", "F-V1", "F-V2",
                  "F-V3", "S-V1", "S-V3", "P-R1", "P-R2", "C-R1", "S-R1", "F-R1",
                  "F-R2", "F-R3"]


@needs_release
@pytest.mark.parametrize("case", _RELEASE_CASES)
def test_reproduces_release_row_from_evidence_ids(case):
    group, _, flag = case.partition(":")
    rows = [r for r in _answers() if r["group_id"] == group
            and (bool(r["negated"]) if flag == "negated" else True)]
    assert rows, case
    row = rows[0]
    needs_corpus = row["mode"] in ARGMAX_MODES or row["level"] == "report"
    if needs_corpus and not DB_PATH.exists():
        pytest.skip("argmax counts / report levels need data/medtempo.db")
    retrieval = _retrieval_from_gold(row, _index() if needs_corpus else None)
    pred = run_test(from_gold(row), retrieval, procedure_mode="gold")
    _assert_matches_gold(pred, row)
    # the reference procedure honoured gives the identical prediction
    assert run_test(from_gold(row), retrieval, procedure_mode="honouring") == pred


@needs_release
def test_release_negated_rows_exist_only_for_negatable_modes():
    negated_modes = {r["mode"] for r in _answers() if r["negated"]}
    assert negated_modes == {"sym_bool_cooccurs", "assoc_bool", "cooc_modal_bool"}


# ---------------------------------------------------------------------------
# (2) report tier: report_rule == gold_verdict on all 3,900 rows
# ---------------------------------------------------------------------------

@pytest.mark.slow
@needs_release
@needs_db
def test_report_rule_matches_every_report_row():
    index = _index()
    rows = [r for r in _answers() if r["level"] == "report"]
    assert len(rows) == 3900
    for row in rows:
        claim = from_gold(row)
        tmap = index.report_terms[row["cohort"]["report_id"]]
        levels = {t: tmap[t] for t in claim.terms if t in tmap}
        assert report_rule(claim, levels) == row["gold_verdict"], row["instance_id"]
        retrieval = _Retrieval([], levels)
        gold = run_test(claim, retrieval, procedure_mode="gold")
        assert gold.verdict == row["gold_verdict"], row["instance_id"]
        assert gold.subtype == "deterministic" == row["insufficient_subtype"]
        assert gold.answer == row["gold_answer"], row["instance_id"]
        assert gold.p_claim is None and gold.n is None
        assert run_test(claim, retrieval, procedure_mode="honouring") == gold


# ---------------------------------------------------------------------------
# (3) honouring == gold on a stratified cohort sample rebuilt from the corpus
# ---------------------------------------------------------------------------

def _cohort_sample(rows: list[dict], total: int = 400, per_mode: int = 30, seed: int = 0) -> list[dict]:
    """Seeded sample: up to ``per_mode`` per cohort mode (rare modes whole), topped up to ``total``."""
    rng = random.Random(seed)
    by_mode: dict[str, list[dict]] = {}
    for r in rows:
        by_mode.setdefault(r["mode"], []).append(r)
    chosen: list[dict] = []
    taken: set[str] = set()
    for mode in sorted(by_mode):
        pool = sorted(by_mode[mode], key=lambda r: r["instance_id"])
        for r in (pool if len(pool) <= per_mode else rng.sample(pool, per_mode)):
            chosen.append(r)
            taken.add(r["instance_id"])
    rest = sorted((r for r in rows if r["instance_id"] not in taken), key=lambda r: r["instance_id"])
    chosen.extend(rng.sample(rest, max(0, total - len(chosen))))
    return chosen[:total]


@pytest.mark.slow
@needs_release
@needs_db
def test_honouring_equals_gold_on_cohort_sample():
    index = _index()
    rows = _cohort_sample([r for r in _answers() if r["level"] != "report"])
    assert len(rows) == 400
    assert {r["mode"] for r in rows} == {m for m, s in MODE_SPEC.items() if not s.is_report}
    for row in rows:
        claim = from_gold(row)
        arms = _arms_from_index(index, claim)
        assert _ids_of(arms) == _gold_ids(row), row["instance_id"]   # the rebuilt arms ARE the evidence
        retrieval = _Retrieval(arms, None)
        gold = run_test(claim, retrieval, procedure_mode="gold")
        _assert_matches_gold(gold, row)
        assert run_test(claim, retrieval, procedure_mode="honouring") == gold, row["instance_id"]


# ---------------------------------------------------------------------------
# (4) unit: procedure failures are causal, underdetermined, the named-cell trap
# ---------------------------------------------------------------------------

def _claim(mode, terms, *, cohort=COHORT, negated=False, options=None, **proc_overrides):
    ref = derive_procedure(mode, negated=negated)
    proc = Procedure(**{**ref.__dict__, **proc_overrides}) if proc_overrides else None
    return build_claim(mode, terms, cohort, negated=negated, options=options, procedure=proc)


def test_wrong_claim_tail_flips_a_decisive_verdict():
    claim = _claim("dir_bool", ("Headache", "Fatigue"))
    retrieval = _Retrieval([_arm(15, 13)])
    ref = run_test(claim, retrieval, procedure_mode="gold")
    assert ref.verdict == "supported" and abs(ref.p_claim - binom_exact_p(13, 15, 0.5, "greater")) < 1e-12

    wrong = _claim("dir_bool", ("Headache", "Fatigue"), claim_tail="less")
    hon = run_test(wrong, retrieval, procedure_mode="honouring")
    assert hon.verdict == "refuted"
    assert (hon.p_claim, hon.p_opposite) == (ref.p_opposite, ref.p_claim)
    assert any("claim_tail" in e for e in hon.procedure_errors)
    # gold mode ignores the stated procedure (but still records the inconsistency)
    gold = run_test(wrong, retrieval, procedure_mode="gold")
    assert gold.verdict == "supported" and any("claim_tail" in e for e in gold.procedure_errors)


def test_wrong_min_n_floor_turns_sparse_into_a_tested_label():
    claim = _claim("dir_bool", ("Headache", "Fatigue"))
    retrieval = _Retrieval([_arm(7, 7)])
    ref = run_test(claim, retrieval, procedure_mode="gold")
    assert (ref.verdict, ref.subtype) == ("insufficient", "sparse")
    assert ref.p_claim is None and ref.test is None and "below pairwise floor 10" in ref.gate_reason

    loose = _claim("dir_bool", ("Headache", "Fatigue"), min_n_floor=5)
    hon = run_test(loose, retrieval, procedure_mode="honouring")
    assert hon.verdict == "supported" and hon.subtype is None
    assert abs(hon.p_claim - 0.5 ** 7) < 1e-12 and hon.test == "binom_exact"
    assert hon.gate_reason == "testable"
    assert any("min_n_floor" in e for e in hon.procedure_errors)
    # the sequence floor is honoured for a claim that (wrongly) says it is a sequence claim
    assert run_test(_claim("dir_bool", ("Headache", "Fatigue"), min_n_floor=5),
                    _Retrieval([_arm(4, 4)]), procedure_mode="honouring").subtype == "sparse"


def test_unknown_floor_records_error_and_uses_the_mode_family():
    odd = _claim("dir_bool", ("Headache", "Fatigue"), min_n_floor=7)
    hon = run_test(odd, _Retrieval([_arm(8, 8)]), procedure_mode="honouring")
    assert (hon.verdict, hon.subtype) == ("insufficient", "sparse")
    assert any("matches no family floor" in e for e in hon.procedure_errors)


def test_fisher_on_a_one_arm_claim_falls_back_to_reference():
    claim = _claim("dir_bool", ("Headache", "Fatigue"), test="fisher_exact",
                   null=NullSpec("two_arm_equality", None, "rate_arm1_vs_arm2"), arms=2)
    retrieval = _Retrieval([_arm(15, 13)])
    hon = run_test(claim, retrieval, procedure_mode="honouring")
    ref = run_test(_claim("dir_bool", ("Headache", "Fatigue")), retrieval, procedure_mode="gold")
    assert any("fisher_exact needs two arms" in e for e in hon.procedure_errors)
    assert (hon.verdict, hon.p_claim, hon.p_opposite, hon.test) == \
        (ref.verdict, ref.p_claim, ref.p_opposite, ref.test)


def test_unknown_test_and_missing_p0_fall_back_to_reference():
    retrieval = _Retrieval([_arm(15, 13)])
    ref = run_test(_claim("dir_bool", ("Headache", "Fatigue")), retrieval, procedure_mode="gold")
    bogus = _claim("dir_bool", ("Headache", "Fatigue"), test="chi_square")
    hon = run_test(bogus, retrieval, procedure_mode="honouring")
    assert hon.verdict == ref.verdict and any("chi_square" in e for e in hon.procedure_errors)
    no_p0 = _claim("dir_bool", ("Headache", "Fatigue"),
                   null=NullSpec("binomial", None, "conditioned_proportion"))
    hon2 = run_test(no_p0, retrieval, procedure_mode="honouring")
    assert hon2.verdict == ref.verdict and any("p0" in e for e in hon2.procedure_errors)


def test_wrong_null_p0_is_honoured_and_causal():
    # 13/15 is decisive against 0.5 but not against a 0.8 null
    claim = _claim("dir_bool", ("Headache", "Fatigue"),
                   null=NullSpec("binomial", 0.8, "conditioned_proportion"))
    hon = run_test(claim, _Retrieval([_arm(15, 13)]), procedure_mode="honouring")
    assert (hon.verdict, hon.subtype) == ("insufficient", "underpowered")
    assert abs(hon.p_claim - binom_exact_p(13, 15, 0.8, "greater")) < 1e-12
    assert any("null" in e for e in hon.procedure_errors)


def test_underdetermined_claim_answers_underdetermined():
    claim = build_claim("first_bool", (None, "Headache", "Fatigue"), COHORT)
    assert claim.is_underdetermined
    pred = run_test(claim, _Retrieval([_arm(20, 10)]))
    assert pred == Prediction("underdetermined", None, None, None, None, None,
                              None, None, None, None, None, None, [], [])
    assert pred.to_dict()["response"] == "underdetermined"


def test_named_cell_trap_refutes_a_claim_naming_a_non_winner():
    # F-V1: the claim names Fatigue first, but Headache is the true winner 10 to 3
    counts = {"Headache": 10, "Fatigue": 3, "Pyrexia": 1}
    retrieval = _Retrieval([_arm(14, 3, counts)])
    claim = _claim("first_choice", ("Fatigue", "Headache", "Pyrexia"),
                   options=["Headache", "Fatigue", "Pyrexia"])
    pred = run_test(claim, retrieval, procedure_mode="gold")
    assert pred.verdict == "refuted"
    assert abs(pred.p_claim - binom_exact_p(3, 13, 0.5, "greater")) < 1e-12
    assert abs(pred.p_opposite - binom_exact_p(3, 13, 0.5, "less")) < 1e-12
    assert pred.answer == "Headache"          # the gold answer is the winner, not the named option
    # what compute_answer would have done: re-derive the named cell from the argmax
    core = to_viable_core(claim, retrieval)
    assert core.extra["winner"] == "Headache"
    assert core_significance(core).decision.verdict == "supported"
    # honouring the (reference) procedure gives the same refutation
    assert run_test(claim, retrieval, procedure_mode="honouring") == pred


def test_negation_swaps_the_tails():
    # C-V1-0025 in the release: 11 of 36 co-exist, claim negated -> supported
    claim = _claim("sym_bool_cooccurs", ("Headache", "Asthenia"), negated=True)
    retrieval = _Retrieval([_arm(36, 11)])
    gold = run_test(claim, retrieval, procedure_mode="gold")
    assert gold.verdict == "supported"
    assert abs(gold.p_claim - binom_exact_p(11, 36, 0.5, "less")) < 1e-12
    assert abs(gold.p_opposite - binom_exact_p(11, 36, 0.5, "greater")) < 1e-12
    assert run_test(claim, retrieval, procedure_mode="honouring") == gold
    plain = run_test(_claim("sym_bool_cooccurs", ("Headache", "Asthenia")), retrieval, procedure_mode="gold")
    assert plain.verdict == "refuted" and plain.p_claim == gold.p_opposite


def test_no_rows_is_not_locatable_never_a_crash():
    for retrieval in (_Retrieval([]), None, _Retrieval([_arm(0, 0, ids=False)])):
        pred = run_test(_claim("dir_bool", ("Headache", "Fatigue")), retrieval)
        assert (pred.verdict, pred.subtype, pred.n, pred.k) == ("insufficient", "not_locatable", 0, 0)
        assert pred.p_claim is None and pred.test is None
    # a two-arm mode with the second arm missing
    pred = run_test(_claim("antecedent_bool", ("Headache", "Fatigue", "Pyrexia")),
                    _Retrieval([_arm(40, 30)]))
    assert (pred.verdict, pred.subtype, pred.n2, pred.k2) == ("insufficient", "not_locatable", 0, 0)
    # report tier: the report lacks an event
    pred = run_test(_claim("rep_dir_bool", ("Headache", "Fatigue"), cohort=REPORT),
                    _Retrieval([], {"Headache": 0}))
    assert (pred.verdict, pred.subtype) == ("insufficient", "not_locatable")
    assert report_rule(_claim("rep_dir_bool", ("Headache", "Fatigue"), cohort=REPORT), {"Headache": 0}) is None


def test_modal_runner_without_counts_uses_k_vs_n_minus_k():
    claim = _claim("dir_bool", ("Headache", "Fatigue"), test="modal_runner",
                   null=NullSpec("binomial", 0.5, "named_vs_runner_up"))
    hon = run_test(claim, _Retrieval([_arm(15, 13)]), procedure_mode="honouring")
    assert hon.test == "modal_runner" and hon.verdict == "supported"
    assert abs(hon.p_claim - binom_exact_p(13, 15, 0.5, "greater")) < 1e-12
    assert any("k vs n-k" in n for n in hon.notes)


def _decisive_case(mode: str) -> tuple[dict, _Retrieval, tuple]:
    """(cohort, retrieval, expected (n, k, n2, k2)) on which the plain claim is SUPPORTED."""
    spec = MODE_SPEC[mode]
    t = ("Headache", "Fatigue", "Pyrexia", "Nausea")[: spec.n_events]
    if spec.is_report:
        levels = {
            "rep_sym_bool": {"Headache": 0, "Fatigue": 0},
            "rep_last_choice": {"Headache": 2, "Fatigue": 1, "Pyrexia": 0},
        }.get(mode, {"Headache": 0, "Fatigue": 1, "Pyrexia": 2})
        return REPORT, _Retrieval([], levels), (None, None, None, None)
    if mode == "multi_dir_precedes":
        cohort = {"level": "multi", "vaccines": ["Pfizer", "Moderna"], "report_id": None}
        return cohort, _Retrieval([_arm(30, 24), _arm(30, 10)]), (30, 24, 30, 10)
    if mode in ("seq_bool", "modal_choice"):
        counts: dict = {t: 13, (t[1], t[0], t[2]): 2}
    elif mode in ("first_choice", "first_bool", "last_choice"):
        counts = {t[0]: 13, t[1]: 2, t[2]: 0}
    elif mode == "cooc_modal_bool":
        counts = {"before": 1, "after": 1, "co_exist": 13}
    else:
        counts = {}
    if spec.arms == 2:
        return COHORT, _Retrieval([_arm(15, 13), _arm(15, 4)]), (15, 13, 15, 4)
    # v1.2: a bar at 2/3 (or 1/2) needs a table that clears it decisively, and a
    # data-derived null needs the retriever's chance sum (here: p0 = 0.5).
    if mode in ("precedes_bar", "cooc_bar"):
        return COHORT, _Retrieval([_arm(30, 29)]), (30, 29, None, None)
    if mode == "first_bar":
        return COHORT, _Retrieval([_arm(30, 29, {t[0]: 29, t[1]: 1, t[2]: 0})]), (30, 29, None, None)
    if mode in ("early_bool", "adj_rate_bool"):
        arm = _arm(15, 13)
        arm.chance_sum = 7.5
        return COHORT, _Retrieval([arm]), (15, 13, None, None)
    return COHORT, _Retrieval([_arm(15, 13, counts)]), (15, 13, None, None)


@pytest.mark.parametrize("mode", sorted(MODE_SPEC))
def test_every_mode_builds_a_complete_core_and_predicts(mode):
    spec = MODE_SPEC[mode]
    terms = ("Headache", "Fatigue", "Pyrexia", "Nausea")[: spec.n_events]
    cohort, retrieval, nk = _decisive_case(mode)
    options = None
    if spec.answer_type == "CHOICE":
        options = list(terms[:2]) if spec.n_events == 2 else list(terms)
        if mode == "multi_dir_precedes":
            options = ["Pfizer", "Moderna"]
        if mode == "modal_choice":
            options = [" → ".join(terms)]
    claim = _claim(mode, terms, cohort=cohort, options=options)
    core = to_viable_core(claim, retrieval)

    assert core.mode == mode and core.events == terms and core.family == spec.family
    if spec.is_report:
        assert core.report_id == REPORT["report_id"] and core.computable and core.n is None
        assert core.natural_verdict == "supported"
    else:
        assert core.report_id is None and (core.n, core.k, core.n2, core.k2) == nk
        assert core.computable is True
    expected_keys = {
        "seq_bool": {"counts", "modal"}, "modal_choice": {"counts", "modal"},
        "first_choice": {"counts", "winner"}, "first_bool": {"counts", "winner"},
        "last_choice": {"counts", "winner"}, "cooc_modal_bool": {"counts", "named"},
        "rep_dir_bool": {"rel"}, "rep_dir_choice": {"rel"}, "rep_sym_bool": {"rel"},
        "rep_seq_bool": {"holds", "idxs"},
        "rep_first_choice": {"winner", "unique", "idxs"},
        "rep_last_choice": {"winner", "unique", "idxs"},
        "rep_first_bool": {"winner", "unique", "idxs"},
        # v1.2
        "rep_imm_bool": {"rel", "adjacent"}, "rep_early_bool": {"early", "rank", "L"},
        "early_bool": {"p0", "null_kind"}, "adj_rate_bool": {"p0", "null_kind"},
        "precedes_bar": {"p0", "null_kind"}, "cooc_bar": {"p0", "null_kind"},
        "first_bar": {"p0", "null_kind", "named"},
    }.get(mode, set())
    assert set(core.extra) == expected_keys, mode
    if mode in ("seq_bool", "modal_choice"):
        assert core.extra["modal"] == terms
    if mode in ("first_choice", "first_bool", "last_choice"):
        assert core.extra["winner"] == terms[0]

    for pm in PROCEDURE_MODES:
        pred = run_test(claim, retrieval, procedure_mode=pm)
        assert pred.response in RESPONSES and pred.response == pred.verdict
        assert pred.procedure_errors == [] and pred.notes == []
        assert (pred.n, pred.k, pred.n2, pred.k2) == nk
        if spec.answer_type == "CHOICE":
            assert pred.answer is not None
        else:
            assert pred.answer is None
        assert pred.verdict == "supported", (mode, pm)     # every table above is decisive
        if spec.is_report:
            assert pred.subtype == "deterministic" and pred.test is None
        else:
            assert pred.subtype is None and pred.test == spec.test and pred.p_claim < 0.05
    assert run_test(claim, retrieval, procedure_mode="honouring") == \
        run_test(claim, retrieval, procedure_mode="gold")


def test_report_rule_edge_cases():
    lv = {"A": 0, "B": 0, "C": 1}
    rep = {"level": "report", "vaccines": [], "report_id": 7}
    assert report_rule(_claim("rep_dir_bool", ("A", "B"), cohort=rep), lv) == "refuted"       # co-exist: A did not precede B
    assert report_rule(_claim("rep_dir_choice", ("A", "B"), cohort=rep), lv) == "insufficient"  # neither came first
    assert report_rule(_claim("rep_sym_bool", ("A", "B"), cohort=rep), lv) == "supported"
    assert report_rule(_claim("rep_sym_bool", ("A", "C"), cohort=rep), lv) == "refuted"
    assert report_rule(_claim("rep_seq_bool", ("A", "B", "C"), cohort=rep), lv) == "refuted"    # not strictly increasing
    assert report_rule(_claim("rep_seq_bool", ("A", "C", "B"), cohort=rep), {"A": 0, "B": 2, "C": 1}) == "supported"
    assert report_rule(_claim("rep_first_bool", ("A", "B", "C"), cohort=rep), lv) == "insufficient"  # tie for first
    assert report_rule(_claim("rep_first_choice", ("C", "A", "B"), cohort=rep), lv) == "insufficient"
    assert report_rule(_claim("rep_last_choice", ("C", "A", "B"), cohort=rep), lv) == "supported"
    assert report_rule(_claim("rep_last_choice", ("A", "B", "C"), cohort=rep), lv) == "refuted"
    assert report_rule(_claim("rep_first_bool", ("A", "B", "C"), cohort=rep), {"A": 0, "B": 1}) is None
    assert report_rule(_claim("dir_bool", ("A", "B")), lv) is None                                 # not a report mode
    # the CHOICE answer follows the rule: earlier event / winner, None on co-exist
    pred = run_test(_claim("rep_dir_choice", ("A", "B"), cohort=rep, options=["A", "B"]), _Retrieval([], lv))
    assert (pred.verdict, pred.answer) == ("insufficient", None)
    pred = run_test(_claim("rep_dir_choice", ("C", "A"), cohort=rep, options=["A", "C"]), _Retrieval([], lv))
    assert (pred.verdict, pred.answer, pred.subtype) == ("refuted", "A", "deterministic")


def test_winner_and_modal_tie_breaks_follow_the_generator():
    # first/last: highest count, then the alphabetically LAST candidate (cores._build_vaccine_core)
    claim = _claim("first_choice", ("Fatigue", "Headache", "Pyrexia"), options=["Fatigue", "Headache", "Pyrexia"])
    core = to_viable_core(claim, _Retrieval([_arm(6, 3, {"Fatigue": 3, "Headache": 3, "Pyrexia": 0})]))
    assert core.extra["winner"] == "Headache"
    core = to_viable_core(claim, _Retrieval([_arm(0, 0, ids=False)]))
    assert core.extra["counts"] == {"Fatigue": 0, "Headache": 0, "Pyrexia": 0}
    assert core.extra["winner"] == "Pyrexia"           # all-zero table: what gold_answer holds on not_locatable rows
    # ordering cells may arrive as 'A|B|C' strings (a JSON round trip) or tuples
    claim = _claim("modal_choice", ("A", "B", "C"), options=["A → B → C"])
    core = to_viable_core(claim, _Retrieval([_arm(5, 3, {"A|B|C": 3, ("B", "A", "C"): 2})]))
    assert core.extra["counts"] == {("A", "B", "C"): 3, ("B", "A", "C"): 2}
    assert core.extra["modal"] == ("A", "B", "C")
    assert to_viable_core(claim, _Retrieval([_arm(0, 0, ids=False)])).extra["modal"] is None


def test_invalid_arguments_raise():
    claim = _claim("dir_bool", ("Headache", "Fatigue"))
    with pytest.raises(ValueError):
        run_test(claim, _Retrieval([_arm(15, 13)]), procedure_mode="whatever")
    from dataclasses import replace
    with pytest.raises(ValueError):
        run_test(replace(claim, mode="no_such_mode"), _Retrieval([_arm(15, 13)]))


def test_synthetic_corpus_end_to_end(corpus_index):
    """Every cohort mode over the conftest CORPUS: arms rebuilt in memory, both procedures agree."""
    cases = {
        "dir_bool": (("Headache", "Fatigue"), "Pfizer"),
        "dir_choice": (("Headache", "Fatigue"), "Pfizer"),
        "sym_bool_cooccurs": (("Headache", "Fatigue"), "Pfizer"),
        "cooc_modal_bool": (("Headache", "Fatigue"), "Pfizer"),
        "seq_bool": (("Headache", "Fatigue", "Pyrexia"), "Moderna"),
        "modal_choice": (("Headache", "Fatigue", "Pyrexia"), "Moderna"),
        "first_choice": (("Headache", "Fatigue", "Pyrexia"), "Moderna"),
        "first_bool": (("Headache", "Fatigue", "Pyrexia"), "Moderna"),
        "last_choice": (("Pyrexia", "Headache", "Fatigue"), "Moderna"),
        "antecedent_bool": (("Headache", "Fatigue", "Pyrexia"), "Pfizer"),
        "pairpair_bool": (("Headache", "Fatigue", "Pyrexia", "Rash"), "Pfizer"),
        "assoc_bool": (("Headache", "Fatigue"), "Pfizer"),
    }
    for mode, (terms, vax) in cases.items():
        spec = MODE_SPEC[mode]
        options = None
        if spec.answer_type == "CHOICE":
            options = list(terms) if mode != "modal_choice" else [" → ".join(terms)]
        claim = _claim(mode, terms, cohort={"level": "vaccine", "vaccines": [vax], "report_id": None},
                       options=options)
        retrieval = _Retrieval(_arms_from_index(corpus_index, claim))
        gold = run_test(claim, retrieval, procedure_mode="gold")
        assert gold.response in RESPONSES and gold.procedure_errors == []
        assert run_test(claim, retrieval, procedure_mode="honouring") == gold, mode
    # Pfizer Headache/Fatigue: 7 before (1015 counts by FIRST mention), 2 after, 3 co-exist
    # -> n=9 is sparse under the 10 floor
    claim = _claim("dir_bool", ("Headache", "Fatigue"))
    pred = run_test(claim, _Retrieval(_arms_from_index(corpus_index, claim)))
    assert (pred.verdict, pred.subtype, pred.n, pred.k) == ("insufficient", "sparse", 9, 7)
    # Janssen Rash/Nausea never co-occur -> not_locatable
    claim = _claim("dir_bool", ("Rash", "Nausea"), cohort={"level": "vaccine", "vaccines": ["Janssen"], "report_id": None})
    pred = run_test(claim, _Retrieval(_arms_from_index(corpus_index, claim)))
    assert (pred.verdict, pred.subtype, pred.n) == ("insufficient", "not_locatable", 0)
    multi = _claim("multi_dir_precedes", ("Headache", "Fatigue"),
                   cohort={"level": "multi", "vaccines": ["Pfizer", "Moderna"], "report_id": None},
                   options=["Pfizer", "Moderna"])
    pred = run_test(multi, _Retrieval(_arms_from_index(corpus_index, multi)))
    # Pfizer 7/9 vs Moderna 8/10 (2003 and 2011 co-exist): arm 1 is below the floor -> sparse,
    # and the CHOICE answer still names the higher-rate cohort
    assert (pred.n, pred.k, pred.n2, pred.k2) == (9, 7, 10, 8)
    assert (pred.verdict, pred.subtype, pred.answer) == ("insufficient", "sparse", "Moderna")
