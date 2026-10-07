"""Tests for the reference SQL compiler and the shared retrieval runner.

Ground truth is ``generation.evidence.evidence_ids`` -- the function that
produced the release's ``evidence_ids`` -- driven through a minimal stand-in for
``InstanceFacts`` (it reads only ``core.mode`` / ``core.report_id`` /
``core.cohort_ids`` and ``events_assigned`` / ``vaccines_assigned``). Every one
of the 20 modes gets a claim over the synthetic corpus in ``conftest``; the slow
test repeats the comparison against the release itself.
"""

from __future__ import annotations

import itertools
import random
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass

import pytest

from temporal_hypo.framework.claim_schema import MODE_SPEC, MODES, build_claim, from_gold
from temporal_hypo.framework.sql.aggregate import ARM_COLUMNS, ArmCounts
from temporal_hypo.framework.sql.compiler import (
    WHOLE_REPORT_MODES,
    ARM_LABEL,
    REPORT_LABEL,
    TWO_ARM_LABELS,
    ArmQuery,
    compile_sql,
    labels_for,
)
from temporal_hypo.framework.sql.executor import ReadOnlyExecutor
from temporal_hypo.framework.sql.retrieve import (
    CONTRACT_VIOLATION,
    EXECUTOR_ERROR,
    MISSING_ARM,
    ROW_CAP,
    QueryLog,
    Retrieval,
    execute_queries,
)
from temporal_hypo.generation import corpus as corpus_mod
from temporal_hypo.generation.evidence import evidence_ids
from tests.framework.conftest import (
    C,
    CORPUS,
    F,
    H,
    N,
    P,
    R,
    RELEASE_DIR,
    REPO_ROOT,
    needs_release,
)

ARROW = " → "   # answers._ARROW: the joiner of modal_choice options


# ---------------------------------------------------------------------------
# fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def executor(eval_db_path):
    ex = ReadOnlyExecutor(eval_db_path)
    yield ex
    ex.close()


@dataclass
class _Core:
    mode: str
    report_id: int | None
    cohort_ids: list[int]


@dataclass
class _Facts:
    core: _Core
    events_assigned: tuple
    vaccines_assigned: tuple


def gold_ids(index, claim) -> dict:
    """``evidence_ids`` for a claim, through the InstanceFacts stand-in."""
    vax = tuple(claim.vaccines)
    cohort = index.cohort(vax[0]) if vax else []
    facts = _Facts(_Core(claim.mode, claim.report_id, cohort), tuple(claim.terms), vax)
    return evidence_ids(index, facts)


def _vax(v: str) -> dict:
    return {"level": "vaccine", "vaccines": [v], "report_id": None}


def _rep(r: int) -> dict:
    return {"level": "report", "vaccines": [], "report_id": r}


def _multi(v1: str, v2: str) -> dict:
    return {"level": "multi", "vaccines": [v1, v2], "report_id": None}


PERMS_HFP = [ARROW.join(p) for p in itertools.permutations((H, F, P))]

# (mode, terms in the asserted order, cohort block, options) -- one per mode.
CASES = [
    ("rep_dir_bool", (H, P), _rep(1015), None),            # H at levels 0 and 2 -> first mention 0
    ("rep_dir_choice", (F, H), _rep(1007), [F, H]),
    ("rep_sym_bool", (H, F), _rep(1010), None),
    ("rep_seq_bool", (H, F, P), _rep(1001), None),
    ("rep_first_choice", (H, F, P), _rep(2001), [H, F, P]),
    ("rep_last_choice", (P, H, F), _rep(2001), [H, F, P]),
    ("rep_first_bool", (H, F, P), _rep(1015), None),
    ("dir_bool", (H, F), _vax("Pfizer"), None),
    ("dir_choice", (F, H), _vax("Pfizer"), [F, H]),
    ("sym_bool_cooccurs", (H, F), _vax("Pfizer"), None),
    ("cooc_modal_bool", (H, F), _vax("Pfizer"), None),
    ("seq_bool", (H, F, P), _vax("Pfizer"), None),
    ("modal_choice", (H, F, P), _vax("Moderna"), PERMS_HFP),
    ("first_choice", (H, F, P), _vax("Moderna"), [H, F, P]),
    ("first_bool", (F, H, P), _vax("Moderna"), None),
    ("last_choice", (P, H, F), _vax("Moderna"), [H, F, P]),
    ("antecedent_bool", (H, F, P), _vax("Pfizer"), None),
    ("pairpair_bool", (H, F, P, F), _vax("Pfizer"), None),
    ("assoc_bool", (H, F), _vax("Pfizer"), None),
    ("multi_dir_precedes", (H, F), _multi("Pfizer", "Moderna"), ["Pfizer", "Moderna"]),
    # v1.2 families (decisions.md 2026-10-07)
    ("rep_early_bool", (H,), _rep(1001), None),           # H at rank 0 of 3 -> earlier half
    ("rep_imm_bool", (H, F), _rep(1001), None),            # ranks 0,1 -> consecutive
    ("early_bool", (H,), _vax("Pfizer"), None),
    ("imm_bool", (H, F), _vax("Pfizer"), None),
    ("imm_choice", (F, H), _vax("Pfizer"), [F, H]),
    ("adj_rate_bool", (H, F), _vax("Pfizer"), None),
    ("precedes_bar", (H, F), _vax("Pfizer"), None),
    ("cooc_bar", (H, F), _vax("Pfizer"), None),
    ("first_bar", (H, F, P), _vax("Moderna"), None),
]
CASE_IDS = [c[0] for c in CASES]
COHORT_CASES = [c for c in CASES if not MODE_SPEC[c[0]].is_report]


def make_claim(mode, terms, cohort, options=None):
    return build_claim(mode, terms, cohort, options=options, source="test")


def run(claim, executor) -> Retrieval:
    return execute_queries(compile_sql(claim), executor, claim)


def assert_arm_matches(arm: ArmCounts, block: dict) -> None:
    assert arm.denominator_ids == set(block["denominator"])
    assert arm.numerator_ids == set(block["numerator"])
    assert arm.excluded_ids == set(block["excluded"])
    if "ties" in block:
        assert arm.excluded_ids == set(block["ties"])
    assert arm.n == len(block["denominator"])
    assert arm.k == len(block["numerator"])
    assert arm.numerator_ids <= arm.denominator_ids
    assert not (arm.denominator_ids & arm.excluded_ids)


def test_cases_cover_every_mode():
    assert set(CASE_IDS) == set(MODES)
    assert len(CASE_IDS) == len(set(CASE_IDS)) == len(MODES) == 29


# ---------------------------------------------------------------------------
# compile_sql: shape
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode,terms,cohort,options", CASES, ids=CASE_IDS)
def test_labels_and_cell_kinds(mode, terms, cohort, options):
    claim = make_claim(mode, terms, cohort, options)
    queries = compile_sql(claim)
    spec = MODE_SPEC[mode]
    assert [q.label for q in queries] == labels_for(claim)
    if spec.is_report:
        assert [q.label for q in queries] == [REPORT_LABEL]
        assert queries[0].cell_kind is None
    else:
        assert [q.label for q in queries] == (list(TWO_ARM_LABELS) if spec.arms == 2 else [ARM_LABEL])
        assert all(q.cell_kind == spec.named_cell_kind for q in queries)
    assert all(isinstance(q, ArmQuery) and isinstance(q.params, dict) for q in queries)


@pytest.mark.parametrize("mode,terms,cohort,options", CASES, ids=CASE_IDS)
def test_sql_uses_only_the_eval_schema_and_bound_params(mode, terms, cohort, options):
    for q in compile_sql(make_claim(mode, terms, cohort, options)):
        low = q.sql.lower()
        assert "narrative" not in low and "report_id" not in low and "level_terms" not in low
        assert "first_mention" in low
        placeholders = set(re.findall(r":(\w+)", q.sql))
        assert placeholders == set(q.params), (placeholders, q.params)
        # every literal the claim supplies travels as a binding, never inline
        for t in terms:
            assert t not in q.sql
        for v in cohort["vaccines"]:
            assert v not in q.sql


# ---------------------------------------------------------------------------
# the main check: id sets == evidence_ids for every mode
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode,terms,cohort,options", CASES, ids=CASE_IDS)
def test_id_sets_match_evidence_ids(mode, terms, cohort, options, executor, corpus_index):
    claim = make_claim(mode, terms, cohort, options)
    ret = run(claim, executor)
    assert ret.ok, [(q.label, q.error_class, q.error) for q in ret.queries]
    assert all(q.error is None for q in ret.queries)
    gold = gold_ids(corpus_index, claim)
    spec = MODE_SPEC[mode]

    if spec.is_report:
        rid = claim.report_id
        assert gold == {"report_id": rid}
        assert ret.arms == []
        have = corpus_index.report_terms[rid]
        if mode in WHOLE_REPORT_MODES:          # v1.2 rank rules read the WHOLE report
            assert ret.levels == have
        else:
            assert ret.levels == {t: have[t] for t in terms if t in have}
        assert set(terms) <= set(ret.levels)      # every event of these cases is present
        return

    assert ret.levels is None
    blocks = [gold["cohort_1"], gold["cohort_2"]] if spec.arms == 2 else [gold]
    assert len(ret.arms) == len(blocks) == spec.arms
    for arm, block in zip(ret.arms, blocks):
        assert_arm_matches(arm, block)
        if spec.named_cell_kind is not None:
            assert sum(arm.counts.values()) == arm.n
            assert None not in arm.counts
        else:
            assert arm.counts == {}
    # the corpus was built so that every cohort case has a non-empty denominator
    assert ret.arms[0].n > 0


@pytest.mark.parametrize("mode,terms,cohort,options", COHORT_CASES, ids=[c[0] for c in COHORT_CASES])
def test_rows_obey_the_arm_contract(mode, terms, cohort, options, executor):
    """Raw rows: exact columns, 0/1 flags, cell NULL outside the denominator, one row per report."""
    for q in compile_sql(make_claim(mode, terms, cohort, options)):
        res = executor.execute(q.sql, q.params)
        assert res.error is None, res.error
        assert res.columns == list(ARM_COLUMNS)
        ids = [r[0] for r in res.rows]
        assert len(ids) == len(set(ids))
        for vid, den, num, exc, cell in res.rows:
            assert isinstance(vid, int)
            assert den in (0, 1) and num in (0, 1) and exc in (0, 1)
            assert not (num and not den)          # numerator implies denominator
            assert not (den and exc)              # excluded is outside the denominator
            if not den:
                assert cell is None
            elif q.cell_kind is not None:
                assert isinstance(cell, str) and cell


# ---------------------------------------------------------------------------
# the subtleties the corpus was built to catch
# ---------------------------------------------------------------------------

def test_first_mention_rule_at_the_report_tier(executor, corpus_index):
    # report 1015 lists Headache at levels 0 and 2; its position is 0
    claim = make_claim("rep_first_bool", (H, F, P), _rep(1015))
    ret = run(claim, executor)
    assert ret.levels == {H: 0, F: 1, P: 2}
    assert ret.levels == corpus_index.report_terms[1015]


def test_first_mention_rule_in_a_cohort(executor, corpus_index):
    # (Headache, Pyrexia) in 1015: first mention 0 < 2 -> ordered, Headache before;
    # the LAST mention (2 = 2) would have made it a co-exist exclusion
    claim = make_claim("dir_bool", (H, P), _vax("Pfizer"))
    ret = run(claim, executor)
    assert 1015 in ret.arms[0].numerator_ids
    assert 1015 not in ret.arms[0].excluded_ids
    assert_arm_matches(ret.arms[0], gold_ids(corpus_index, claim))
    sym = run(make_claim("sym_bool_cooccurs", (H, P), _vax("Pfizer")), executor)
    assert 1015 in sym.arms[0].denominator_ids and 1015 not in sym.arms[0].numerator_ids


def test_coexist_only_pair_is_excluded_for_precedes_and_counted_for_cooccurs(executor, corpus_index):
    # Pfizer (Headache, Rash): the only both-present report, 1003, has them at the same level
    dir_claim = make_claim("dir_bool", (H, R), _vax("Pfizer"))
    ret = run(dir_claim, executor)
    assert ret.ok
    arm = ret.arms[0]
    assert (arm.n, arm.k) == (0, 0)
    assert arm.denominator_ids == set() and arm.excluded_ids == {1003}
    assert arm.n_rows == 1
    assert_arm_matches(arm, gold_ids(corpus_index, dir_claim))
    for mode in ("dir_choice", "antecedent_bool", "pairpair_bool", "multi_dir_precedes"):
        spec = MODE_SPEC[mode]
        terms = {"dir_choice": (H, R), "antecedent_bool": (H, R, F), "pairpair_bool": (H, R, H, F),
                 "multi_dir_precedes": (H, R)}[mode]
        cohort = _multi("Pfizer", "Moderna") if mode == "multi_dir_precedes" else _vax("Pfizer")
        first = run(make_claim(mode, terms, cohort, [H, R] if spec.answer_type == "CHOICE" and mode == "dir_choice"
                               else (["Pfizer", "Moderna"] if mode == "multi_dir_precedes" else None)),
                    executor).arms[0]
        assert first.n == 0 and first.excluded_ids == {1003}, mode
    co = run(make_claim("sym_bool_cooccurs", (H, R), _vax("Pfizer")), executor).arms[0]
    assert (co.n, co.k, co.excluded_ids) == (1, 1, set())
    modal = run(make_claim("cooc_modal_bool", (H, R), _vax("Pfizer")), executor).arms[0]
    assert modal.counts == {"co_exist": 1}


def test_not_locatable_pair_yields_no_rows_and_is_not_an_error(executor, corpus_index):
    # Janssen: Rash (3001) and Nausea (3002) never share a report
    claim = make_claim("dir_bool", (R, N), _vax("Janssen"))
    ret = run(claim, executor)
    assert ret.ok and ret.queries[0].error is None
    arm = ret.arms[0]
    assert (arm.n, arm.k, arm.n_rows) == (0, 0, 0)
    assert arm.denominator_ids == arm.numerator_ids == arm.excluded_ids == set()
    assert gold_ids(corpus_index, claim) == {"denominator": [], "numerator": [], "excluded": []}
    assert ret.queries[0].n_rows == 0


def test_assoc_arms_partition_the_cohort(executor, corpus_index):
    claim = make_claim("assoc_bool", (H, F), _vax("Pfizer"))
    ret = run(claim, executor)
    with_a, without_a = ret.arms
    cohort = set(corpus_index.cohort("Pfizer"))
    assert len(cohort) == sum(1 for r in CORPUS if r[1] == "Pfizer") == 15
    assert with_a.denominator_ids | without_a.denominator_ids == cohort
    assert not (with_a.denominator_ids & without_a.denominator_ids)
    assert with_a.n + without_a.n == len(cohort)
    assert without_a.denominator_ids == {1014}            # the one Pfizer report without Headache
    assert without_a.numerator_ids == {1014}              # ... and it contains Fatigue
    assert with_a.excluded_ids == without_a.excluded_ids == set()
    gold = gold_ids(corpus_index, claim)
    assert_arm_matches(with_a, gold["cohort_1"])
    assert_arm_matches(without_a, gold["cohort_2"])


def test_argmax_cells_match_the_corpus_distributions(executor, corpus_index):
    pf = corpus_index.cohort("Pfizer")
    mo = corpus_index.cohort("Moderna")

    seq = run(make_claim("seq_bool", (H, F, P), _vax("Pfizer")), executor).arms[0]
    dist = corpus_mod.ordering_distribution(corpus_index, [H, F, P], pf)
    assert seq.counts == dist["counts"] and seq.n == dist["n"] and len(seq.excluded_ids) == dist["tie"]
    assert seq.counts == {(H, F, P): 3, (F, P, H): 1}
    assert seq.excluded_ids == {1002, 1009, 1011}

    modal = run(make_claim("modal_choice", (H, F, P), _vax("Moderna"), PERMS_HFP), executor).arms[0]
    assert modal.counts == corpus_mod.ordering_distribution(corpus_index, [H, F, P], mo)["counts"]

    first = run(make_claim("first_choice", (H, F, P), _vax("Moderna"), [H, F, P]), executor).arms[0]
    fr = corpus_mod.first_among_fractions(corpus_index, [H, F, P], mo)
    assert first.counts == {t: c for t, c in fr["counts"].items() if c}
    assert first.n == fr["n"] and len(first.excluded_ids) == fr["ties"] == 2
    assert first.excluded_ids == {2003, 2011}

    last = run(make_claim("last_choice", (P, H, F), _vax("Moderna"), [H, F, P]), executor).arms[0]
    la = corpus_mod.last_among_fractions(corpus_index, [P, H, F], mo)
    assert last.counts == {t: c for t, c in la["counts"].items() if c}
    assert last.excluded_ids == {2005, 2011}

    rel = run(make_claim("cooc_modal_bool", (H, F), _vax("Pfizer")), executor).arms[0]
    rd = corpus_mod.relation_distribution(corpus_index, H, F, pf)
    assert rel.counts == {k: v for k, v in rd["counts"].items() if v}
    assert rel.n == rd["n"] and rel.k == rd["counts"]["co_exist"]
    assert rel.counts == {"before": 7, "after": 2, "co_exist": 3}


def test_ordering_cell_is_the_terms_sorted_by_level(executor):
    # 1008 is F(0) P(1) H(2): the label must follow the LEVELS, not the asserted order
    q = compile_sql(make_claim("seq_bool", (H, F, P), _vax("Pfizer")))[0]
    rows = {r[0]: r for r in executor.execute(q.sql, q.params).rows}
    assert rows[1008][4] == f"{F}|{P}|{H}"
    assert rows[1001][4] == f"{H}|{F}|{P}"
    assert rows[1002][4] is None and rows[1002][1] == 0 and rows[1002][3] == 1


def test_two_arm_bindings_follow_the_asserted_order():
    ante = compile_sql(make_claim("antecedent_bool", (H, F, P), _vax("Pfizer")))
    assert [(q.params["a"], q.params["b"], q.params["vax"]) for q in ante] == \
        [(H, F, "Pfizer"), (P, F, "Pfizer")]
    assert ante[0].sql == ante[1].sql
    pp = compile_sql(make_claim("pairpair_bool", (H, F, P, R), _vax("Moderna")))
    assert [(q.params["a"], q.params["b"]) for q in pp] == [(H, F), (P, R)]
    multi = compile_sql(make_claim("multi_dir_precedes", (H, F), _multi("Janssen", "Pfizer"),
                                   ["Janssen", "Pfizer"]))
    assert [q.params for q in multi] == [{"vax": "Janssen", "a": H, "b": F},
                                         {"vax": "Pfizer", "a": H, "b": F}]
    assoc = compile_sql(make_claim("assoc_bool", (H, F), _vax("Pfizer")))
    assert assoc[0].sql != assoc[1].sql and assoc[0].params == assoc[1].params
    assert "IS NULL" in assoc[1].sql and "IS NULL" not in assoc[0].sql.split("AS in_numerator")[1]
    rep = compile_sql(make_claim("rep_seq_bool", (H, F, P), _rep(1001)))[0]
    assert rep.params == {"r": 1001, "a": H, "b": F, "c": P}


def test_underdetermined_claim_compiles_to_nothing(executor):
    claim = make_claim("dir_bool", (H, None), _vax("Pfizer"))
    assert claim.is_underdetermined
    assert compile_sql(claim) == []
    ret = execute_queries([], executor, claim)
    assert not ret.ok
    assert len(ret.arms) == 1 and ret.arms[0].n == 0 and ret.arms[0].denominator_ids == set()
    assert [q.error_class for q in ret.queries] == [MISSING_ARM]
    two = make_claim("pairpair_bool", (H, F, None, P), _vax("Pfizer"))
    assert compile_sql(two) == []
    ret2 = execute_queries([], executor, two)
    assert len(ret2.arms) == 2 and [q.label for q in ret2.queries] == list(TWO_ARM_LABELS)


def test_missing_cohort_compiles_to_nothing(executor):
    no_report = make_claim("rep_dir_bool", (H, F), {"level": "report", "vaccines": [], "report_id": None})
    assert compile_sql(no_report) == []
    ret = execute_queries([], executor, no_report)
    assert ret.levels == {} and ret.arms == [] and not ret.ok
    assert [q.error_class for q in ret.queries] == [MISSING_ARM]
    one_vax = make_claim("multi_dir_precedes", (H, F), _vax("Pfizer"), ["Pfizer", "Moderna"])
    assert compile_sql(one_vax) == []
    no_vax = make_claim("dir_bool", (H, F), {"level": "vaccine", "vaccines": [], "report_id": None})
    assert compile_sql(no_vax) == []


# ---------------------------------------------------------------------------
# execute_queries: failure classes (model-written SQL goes through here)
# ---------------------------------------------------------------------------

PFIZER = {"vax": "Pfizer"}


def _arm_q(sql: str, params: dict | None = None, cell_kind: str | None = None) -> ArmQuery:
    return ArmQuery(ARM_LABEL, sql, dict(params or {}), cell_kind)


def test_wrong_columns_are_a_contract_violation(executor):
    claim = make_claim("dir_bool", (H, F), _vax("Pfizer"))
    q = _arm_q("SELECT vaers_id, level FROM first_mention WHERE vaccine = :vax", PFIZER)
    ret = execute_queries([q], executor, claim)
    assert not ret.ok
    assert len(ret.arms) == 1 and ret.arms[0].n == 0 and ret.arms[0].n_rows == 0
    log = ret.queries[0]
    assert log.error_class == CONTRACT_VIOLATION and "in_denominator" in log.error
    assert log.n_rows > 0                      # the statement ran; its shape was wrong
    assert log.params == PFIZER and log.label == ARM_LABEL


def test_bad_vaers_id_is_a_contract_violation(executor):
    claim = make_claim("dir_bool", (H, F), _vax("Pfizer"))
    q = _arm_q("SELECT term AS vaers_id, 1 AS in_denominator, 0 AS in_numerator, 0 AS excluded, "
               "NULL AS cell FROM first_mention WHERE vaccine = :vax", PFIZER)
    ret = execute_queries([q], executor, claim)
    assert ret.queries[0].error_class == CONTRACT_VIOLATION
    assert "vaers_id" in ret.queries[0].error
    assert ret.arms[0].denominator_ids == set()


def test_column_names_are_matched_case_insensitively(executor, corpus_index):
    claim = make_claim("dir_bool", (H, F), _vax("Pfizer"))
    ref = compile_sql(claim)[0]
    sql = ref.sql.replace("AS in_denominator", "AS In_Denominator").replace("AS cell", "AS CELL")
    ret = execute_queries([ArmQuery(ARM_LABEL, sql, ref.params, None)], executor, claim)
    assert ret.ok
    assert_arm_matches(ret.arms[0], gold_ids(corpus_index, claim))


def test_executor_failures_pass_through(executor):
    claim = make_claim("dir_bool", (H, F), _vax("Pfizer"))
    ret = execute_queries([
        _arm_q("DELETE FROM reports"),
        _arm_q("SELECT no_such_column FROM first_mention"),
        _arm_q("SELECT vaers_id, 1, 0, 0, NULL FROM first_mention WHERE vaccine = :vax"),   # missing binding
    ], executor, claim)
    assert not ret.ok
    assert [q.error_class for q in ret.queries] == ["not_select", "sql_error", "sql_error"]
    assert len(ret.arms) == 3 and all(a.n == 0 for a in ret.arms)
    assert all(q.n_rows == 0 for q in ret.queries)


def test_partial_failure_keeps_the_good_arm(executor, corpus_index):
    claim = make_claim("antecedent_bool", (H, F, P), _vax("Pfizer"))
    good, bad = compile_sql(claim)
    bad = ArmQuery(bad.label, "SELECT 1 AS nope", {}, None)
    ret = execute_queries([good, bad], executor, claim)
    assert not ret.ok
    assert [q.label for q in ret.queries] == list(TWO_ARM_LABELS)
    assert ret.queries[0].error is None and ret.queries[1].error_class == CONTRACT_VIOLATION
    assert_arm_matches(ret.arms[0], gold_ids(corpus_index, claim)["cohort_1"])
    assert ret.arms[1].n == 0 and ret.arms[1].denominator_ids == set()


def test_too_few_statements_are_padded(executor):
    claim = make_claim("pairpair_bool", (H, F, P, F), _vax("Pfizer"))
    only_first = compile_sql(claim)[:1]
    ret = execute_queries(only_first, executor, claim)
    assert not ret.ok
    assert len(ret.arms) == 2 and len(ret.queries) == 2
    assert ret.arms[0].n > 0 and ret.arms[1].n == 0
    assert ret.queries[1].error_class == MISSING_ARM and ret.queries[1].label == "cohort_2"


def test_row_cap_truncation_is_a_failure(eval_db_path, corpus_index):
    claim = make_claim("dir_bool", (H, F), _vax("Pfizer"))
    ex = ReadOnlyExecutor(eval_db_path, row_cap=3)
    try:
        ret = execute_queries(compile_sql(claim), ex, claim)
    finally:
        ex.close()
    assert not ret.ok
    assert ret.queries[0].error_class == ROW_CAP
    assert ret.arms[0].n == 0 and ret.arms[0].denominator_ids == set()
    assert len(gold_ids(corpus_index, claim)["denominator"]) > 3     # it really was truncated


def test_report_tier_contract_violation(executor):
    claim = make_claim("rep_dir_bool", (H, F), _rep(1001))
    three_cols = ArmQuery(REPORT_LABEL, "SELECT vaers_id, term, level FROM first_mention WHERE vaers_id = :r",
                          {"r": 1001}, None)
    ret = execute_queries([three_cols], executor, claim)
    assert not ret.ok and ret.levels == {} and ret.arms == []
    assert ret.queries[0].error_class == CONTRACT_VIOLATION
    swapped = ArmQuery(REPORT_LABEL, "SELECT level, term FROM first_mention WHERE vaers_id = :r",
                       {"r": 1001}, None)
    assert execute_queries([swapped], executor, claim).queries[0].error_class == CONTRACT_VIOLATION
    # a model returning every term of the report is fine: levels is a superset
    wide = ArmQuery(REPORT_LABEL, "SELECT term, level FROM first_mention WHERE vaers_id = :r", {"r": 1001}, None)
    ok = execute_queries([wide], executor, claim)
    assert ok.ok and ok.levels == {H: 0, F: 1, P: 2}


def test_closed_executor_is_recorded_not_raised(eval_db_path):
    claim = make_claim("dir_bool", (H, F), _vax("Pfizer"))
    ex = ReadOnlyExecutor(eval_db_path)
    ex.close()
    ret = execute_queries(compile_sql(claim), ex, claim)
    assert not ret.ok and ret.queries[0].error_class == EXECUTOR_ERROR
    assert isinstance(ret.queries[0], QueryLog) and ret.arms[0].n == 0


def test_query_log_records_the_call(executor):
    claim = make_claim("dir_bool", (H, F), _vax("Pfizer"))
    q = compile_sql(claim)[0]
    ret = execute_queries([q], executor, claim)
    log = ret.queries[0]
    assert (log.label, log.sql, log.params) == (q.label, q.sql, q.params)
    assert log.n_rows == ret.arms[0].n_rows == 12       # 9 ordered + 3 co-exist Pfizer reports
    assert log.ms >= 0.0 and log.error is None and log.error_class is None and log.ok
    assert ret.failures == []


# ---------------------------------------------------------------------------
# release-wide (slow): gold claims -> compiler -> evidence_ids and (n, k, n2, k2)
# ---------------------------------------------------------------------------

RAW_DB = REPO_ROOT / "data" / "medtempo.db"
FOCUS_GROUPS = ("S-V1", "S-V3", "P-M2", "F-V1", "F-V2", "F-V3", "C-V3")
SAMPLE_SIZE = 600
SAMPLE_SEED = 20260901


def _compare_release_row(row: dict, ret: Retrieval, index) -> list[str]:
    problems: list[str] = []
    spec = MODE_SPEC[row["mode"]]
    if not ret.ok:
        problems.append("retrieval not ok: " + "; ".join(f"{q.label}:{q.error_class}" for q in ret.failures))
    if spec.is_report:
        rid = row["cohort"]["report_id"]
        if ret.arms:
            problems.append("report tier produced arms")
        have = index.report_terms[rid]
        levels = ret.levels or {}
        for t in row["factual_core"]["events"]:
            if t not in levels:
                problems.append(f"event {t!r} missing from levels")
            elif levels[t] != have[t]:
                problems.append(f"level of {t!r}: {levels[t]} != corpus {have[t]}")
        if row["evidence_ids"] != {"report_id": rid}:
            problems.append("release evidence_ids is not the report id")
        return problems

    ev = row["evidence_ids"]
    blocks = [ev["cohort_1"], ev["cohort_2"]] if spec.arms == 2 else [ev]
    if len(ret.arms) != len(blocks):
        return problems + [f"{len(ret.arms)} arms, gold has {len(blocks)}"]
    for i, (arm, block) in enumerate(zip(ret.arms, blocks)):
        for key, got in (("denominator", arm.denominator_ids), ("numerator", arm.numerator_ids),
                         ("excluded", arm.excluded_ids)):
            want = set(block[key])
            if got != want:
                problems.append(f"arm {i} {key}: +{sorted(got - want)[:5]} -{sorted(want - got)[:5]}")
        if "ties" in block and arm.excluded_ids != set(block["ties"]):
            problems.append(f"arm {i} ties differ")
        if spec.named_cell_kind is not None and sum(arm.counts.values()) != arm.n:
            problems.append(f"arm {i} counts sum {sum(arm.counts.values())} != n {arm.n}")
    n, k = ret.arms[0].n, ret.arms[0].k
    n2, k2 = (ret.arms[1].n, ret.arms[1].k) if spec.arms == 2 else (None, None)
    gold_nk = (row["gold_n"], row["gold_k"], row["gold_n2"], row["gold_k2"])
    if (n, k, n2, k2) != gold_nk:
        problems.append(f"(n,k,n2,k2) {(n, k, n2, k2)} != gold {gold_nk}")
    return problems


@pytest.mark.slow
@needs_release
def test_release_sample_matches_evidence_ids(tmp_path):
    if not RAW_DB.exists():
        pytest.skip("data/medtempo.db not present")
    from temporal_hypo.framework.io import load_release
    from temporal_hypo.framework.sql.build_eval_db import build_eval_db
    from temporal_hypo.generation.corpus import CorpusIndex

    eval_db = tmp_path / "medtempo_eval.db"
    build_eval_db(RAW_DB, eval_db)
    release = load_release(RELEASE_DIR, verify_sha=False)
    raw = sqlite3.connect(RAW_DB.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        index = CorpusIndex.load(raw)
    finally:
        raw.close()

    ids = sorted(release.answers)
    chosen = set(random.Random(SAMPLE_SEED).sample(ids, SAMPLE_SIZE))
    chosen |= {iid for iid in ids if release.answers[iid]["group_id"] in FOCUS_GROUPS}

    failures: list[tuple[str, list[str]]] = []
    per_mode: Counter = Counter()
    per_group: Counter = Counter()
    n_queries = 0
    ex = ReadOnlyExecutor(eval_db)
    try:
        for iid in sorted(chosen):
            row = release.answers[iid]
            claim = from_gold(row)
            assert not claim.is_underdetermined, iid
            queries = compile_sql(claim)
            n_queries += len(queries)
            ret = execute_queries(queries, ex, claim)
            per_mode[row["mode"]] += 1
            per_group[row["group_id"]] += 1
            problems = _compare_release_row(row, ret, index)
            if problems:
                failures.append((iid, problems))
    finally:
        ex.close()

    print(f"\ncompiler vs release: {len(chosen)} instances, {n_queries} queries, "
          f"{len(failures)} disagreements")
    print("per group:", dict(sorted(per_group.items())))
    print("per mode:", dict(sorted(per_mode.items())))
    for g in FOCUS_GROUPS:
        assert per_group[g] == sum(1 for r in release.answers.values() if r["group_id"] == g)
    assert not failures, f"{len(failures)} instances disagree with the release; first: {failures[:5]}"
