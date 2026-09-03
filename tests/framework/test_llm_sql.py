"""Tests for ``framework.sql.llm_sql`` with a stub provider (no network)."""

from __future__ import annotations

import json

import pytest

from temporal_hypo.framework.claim_schema import MODE_SPEC, MODES, build_claim
from temporal_hypo.framework.extract.llm_client import Completion, ollama_available
from temporal_hypo.framework.sql.aggregate import ARM_COLUMNS, ORDERING_SEP, REPORT_COLUMNS
from temporal_hypo.framework.sql.llm_sql import (
    SQL_JSON_SCHEMA,
    LLMSQLRetriever,
    arm_plan,
    claim_payload,
    expected_labels,
    load_eval_ddl,
    sql_messages,
)
from temporal_hypo.generation.pilot import RULE_BY_MODE, _EXCLUSION_REASON
from tests.framework.conftest import H, F, P, R, N

DDL = """
CREATE TABLE reports (vaers_id INTEGER PRIMARY KEY, vaccine TEXT NOT NULL, num_stages INTEGER NOT NULL);
CREATE TABLE level_terms (vaers_id INTEGER NOT NULL REFERENCES reports(vaers_id), level_index INTEGER NOT NULL, term TEXT NOT NULL);
CREATE VIEW first_mention AS
  SELECT lt.vaers_id, r.vaccine, lt.term, MIN(lt.level_index) AS level
  FROM level_terms lt JOIN reports r USING (vaers_id) GROUP BY lt.vaers_id, lt.term;
"""

VAX = {"level": "vaccine", "vaccines": ["Pfizer"], "report_id": None}
MOD = {"level": "vaccine", "vaccines": ["Moderna"], "report_id": None}
REP = {"level": "report", "vaccines": [], "report_id": 1001}

DIR = build_claim("dir_bool", [H, F], VAX)
SEQ = build_claim("seq_bool", [H, F, P], MOD)
ANTE = build_claim("antecedent_bool", [H, F, P], VAX)
MULTI = build_claim("multi_dir_precedes", [H, F], {"level": "multi", "vaccines": ["Pfizer", "Moderna"],
                                                   "report_id": None}, options=["Pfizer", "Moderna"])
REPORT = build_claim("rep_dir_bool", [H, F], REP)

PAIR_SQL = ("SELECT a.vaers_id, (a.level<>b.level) AS in_denominator, (a.level<b.level) AS in_numerator, "
            "(a.level=b.level) AS excluded, NULL AS cell FROM first_mention a JOIN first_mention b "
            "USING (vaers_id) WHERE a.vaccine='Pfizer' AND a.term='Headache' AND b.term='Fatigue'")


class StubProvider:
    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = []

    def complete(self, messages, *, schema, model, temperature=0.0, max_tokens=800):
        self.calls.append({"messages": messages, "schema": schema, "model": model})
        text = self.texts.pop(0) if self.texts else "{}"
        return Completion(text=text, prompt_tokens=500, completion_tokens=80, ms=3.0, cached=False)


def arms_json(*pairs):
    return json.dumps({"arms": [{"label": l, "sql": s} for l, s in pairs]})


# ---------------------------------------------------------------------------
# plan / prompt
# ---------------------------------------------------------------------------

def test_expected_labels_match_the_compiler_convention():
    assert expected_labels(DIR) == ["arm"]
    assert expected_labels(SEQ) == ["arm"]
    assert expected_labels(ANTE) == ["cohort_1", "cohort_2"]
    assert expected_labels(MULTI) == ["cohort_1", "cohort_2"]
    assert expected_labels(REPORT) == ["report"]


def test_arm_plan_covers_every_mode_and_names_the_arms():
    for mode in MODES:
        s = MODE_SPEC[mode]
        n = s.n_events
        cohort = REP if s.is_report else ({"level": "multi", "vaccines": ["Pfizer", "Moderna"],
                                           "report_id": None} if s.tier == "multi" else VAX)
        claim = build_claim(mode, [H, F, P, R][:n], cohort)
        plan = arm_plan(claim)
        assert [p["label"] for p in plan] == expected_labels(claim)
        assert len(plan) == s.arms
        assert all(p["rows"] for p in plan)
    ante = arm_plan(ANTE)
    assert f"'{H}', '{F}'" in ante[0]["rows"] and f"'{P}', '{F}'" in ante[1]["rows"]
    multi = arm_plan(MULTI)
    assert "'Pfizer'" in multi[0]["rows"] and "'Moderna'" in multi[1]["rows"]
    assert "1001" in arm_plan(REPORT)[0]["rows"]
    assert ORDERING_SEP in arm_plan(SEQ)[0]["rows"]


def test_sql_messages_carry_ddl_contract_claim_rule_and_reminders():
    msgs = sql_messages(DIR, DDL)
    assert [m["role"] for m in msgs] == ["system", "user"]
    system, user = msgs[0]["content"], msgs[1]["content"]
    assert DDL.strip() in system
    assert ", ".join(ARM_COLUMNS) in system
    assert "first-mention" in system and "vaers_id" in system
    assert "cell MUST be NULL" in system and "Inline every literal" in system
    payload = json.loads(user.split("CLAIM (JSON):\n", 1)[1].split("\n", 1)[0])
    assert payload == claim_payload(DIR)
    assert payload["events"] == [{"role": "A", "term": H}, {"role": "B", "term": F}]
    assert payload["cohorts"] == [{"vaccine": "Pfizer", "report_id": None}]
    assert RULE_BY_MODE["dir_bool"] in user and _EXCLUSION_REASON["dir_bool"] in user
    assert "1 statement;" in user and "- arm:" in user

    rep = sql_messages(REPORT, DDL)[0]["content"]
    assert ", ".join(REPORT_COLUMNS) in rep and ", ".join(ARM_COLUMNS) not in rep

    seq_sys = sql_messages(SEQ, DDL)[0]["content"]
    assert f"joined with '{ORDERING_SEP}'" in seq_sys
    assert "'before', 'after' or 'co_exist'" in sql_messages(
        build_claim("cooc_modal_bool", [H, F], VAX), DDL)[0]["content"]
    two = sql_messages(ANTE, DDL)[1]["content"]
    assert "2 statements;" in two and "cohort_1, cohort_2" in two


# ---------------------------------------------------------------------------
# queries_for
# ---------------------------------------------------------------------------

def test_queries_for_parses_canned_arms_into_armqueries():
    stub = StubProvider([arms_json(("arm", PAIR_SQL + ";"))])
    r = LLMSQLRetriever(stub, "stub-sql", executor=None, ddl=DDL)
    assert r.name == "llm-sql:stub-sql"
    qs = r.queries_for(DIR)
    assert len(qs) == 1
    q = qs[0]
    assert q.label == "arm" and q.sql == PAIR_SQL + ";" and q.params == {} and q.cell_kind is None
    assert r.last_error is None and r.last_notes == []
    assert r.last_usage == {"prompt": 500, "completion": 80} and r.last_ms == 3.0
    assert r.last_tokens == r.last_usage
    assert stub.calls[0]["schema"] is SQL_JSON_SCHEMA and stub.calls[0]["model"] == "stub-sql"


def test_queries_for_sets_cell_kind_from_mode_spec():
    r = LLMSQLRetriever(StubProvider([arms_json(("arm", "SELECT 1"))] * 4), "m", None, ddl=DDL)
    assert r.queries_for(SEQ)[0].cell_kind == "ordering"
    assert r.queries_for(build_claim("first_choice", [H, F, P], MOD, options=[H, F, P]))[0].cell_kind == "event"
    assert r.queries_for(build_claim("cooc_modal_bool", [H, F], VAX))[0].cell_kind == "relation"
    assert r.queries_for(REPORT)[0].cell_kind is None


def test_queries_for_two_arms_keeps_model_labels_when_they_match_the_plan():
    stub = StubProvider([arms_json(("cohort_2", "SELECT 2"), ("cohort_1", "SELECT 1"))])
    qs = LLMSQLRetriever(stub, "m", None, ddl=DDL).queries_for(ANTE)
    assert [(q.label, q.sql) for q in qs] == [("cohort_1", "SELECT 1"), ("cohort_2", "SELECT 2")]


def test_queries_for_aligns_foreign_labels_by_position_and_pads_missing():
    stub = StubProvider([arms_json(("first", "SELECT 1"))])
    r = LLMSQLRetriever(stub, "m", None, ddl=DDL)
    qs = r.queries_for(MULTI)
    assert [q.label for q in qs] == ["cohort_1", "cohort_2"]
    assert qs[0].sql == "SELECT 1" and qs[1].sql.startswith("--")
    assert any("aligned by position" in n for n in r.last_notes)
    assert any("missing statement for cohort_2" in n for n in r.last_notes)
    assert r.last_error is None

    stub = StubProvider([arms_json(("x", "SELECT 1"), ("y", "SELECT 2"))])
    r = LLMSQLRetriever(stub, "m", None, ddl=DDL)
    qs = r.queries_for(DIR)
    assert len(qs) == 1 and qs[0].label == "arm" and qs[0].sql == "SELECT 1"
    assert any("extra statement" in n for n in r.last_notes)


def test_queries_for_garbage_or_provider_failure_yields_placeholders_not_exceptions():
    r = LLMSQLRetriever(StubProvider(["not json at all"]), "m", None, ddl=DDL)
    qs = r.queries_for(ANTE)
    assert [q.label for q in qs] == ["cohort_1", "cohort_2"]
    assert all(q.sql.startswith("-- no SQL produced") for q in qs)
    assert r.last_error and "ValueError" in r.last_error

    r = LLMSQLRetriever(StubProvider(['{"arms": []}']), "m", None, ddl=DDL)
    assert r.queries_for(DIR)[0].sql.startswith("--") and "arms" in r.last_error

    r = LLMSQLRetriever(StubProvider(['{"arms": [{"label": "arm", "sql": 5}]}']), "m", None, ddl=DDL)
    assert r.queries_for(DIR)[0].sql.startswith("--") and "string 'sql'" in r.last_error

    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("unreachable at http://localhost:11434/api/chat")

    r = LLMSQLRetriever(Boom(), "m", None, ddl=DDL)
    assert r.queries_for(REPORT)[0].label == "report" and "unreachable" in r.last_error


def test_ddl_is_resolved_lazily():
    r = LLMSQLRetriever(StubProvider([]), "m", None)          # no ddl, no import-time failure
    try:
        ddl = load_eval_ddl()
    except RuntimeError as exc:
        assert "eval DDL unavailable" in str(exc)
        pytest.skip("build_eval_db / views.sql not built yet")
    assert "first_mention" in ddl
    assert r.ddl == ddl


# ---------------------------------------------------------------------------
# retrieve() end-to-end over the synthetic eval DB (needs the other agents' modules)
# ---------------------------------------------------------------------------

def test_retrieve_runs_the_model_sql_through_execute_queries(eval_db_path):
    executor_mod = pytest.importorskip("temporal_hypo.framework.sql.executor")
    pytest.importorskip("temporal_hypo.framework.sql.retrieve")
    executor = executor_mod.ReadOnlyExecutor(eval_db_path)
    try:
        stub = StubProvider([arms_json(("arm", PAIR_SQL))])
        r = LLMSQLRetriever(stub, "m", executor, ddl=DDL)
        ret = r.retrieve(DIR)
        assert ret.ok is True
        assert len(ret.arms) == 1
        arm = ret.arms[0]
        # CORPUS Pfizer: H before F in 7 (1001-1006 and the 1015 first-mention trap),
        # F before H in 2 (1007, 1008), co-exist in 3 (1009-1011) -> n = 9, k = 7
        assert arm.n == 9 and arm.k == 7
        assert arm.numerator_ids == {1001, 1002, 1003, 1004, 1005, 1006, 1015}
        assert arm.denominator_ids == arm.numerator_ids | {1007, 1008}
        assert arm.excluded_ids == {1009, 1010, 1011}
        assert ret.queries[0].label == "arm" and ret.queries[0].error is None
        # a placeholder statement is executed and logged as a failure, never raised
        bad = LLMSQLRetriever(StubProvider(["garbage"]), "m", executor, ddl=DDL).retrieve(DIR)
        assert bad.ok is False and bad.arms[0].n == 0 and bad.queries[0].error_class is not None
    finally:
        executor.close()


# ---------------------------------------------------------------------------
# live (skipped unless a local Ollama answers)
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.skipif(not ollama_available(), reason="no Ollama at localhost:11434")
def test_live_llm_sql_writes_one_statement_per_arm(tmp_path):
    from temporal_hypo.framework.extract.llm_client import CacheDir, OllamaClient

    client = OllamaClient(cache=CacheDir(tmp_path))
    models = client.models()
    if not models:
        pytest.skip("Ollama is running but has no models pulled")
    r = LLMSQLRetriever(client, models[0], executor=None, ddl=DDL)
    qs = r.queries_for(ANTE)
    assert r.last_error is None, r.last_error
    assert [q.label for q in qs] == ["cohort_1", "cohort_2"]
    assert all(q.sql.lstrip().upper().startswith(("SELECT", "WITH")) for q in qs)
