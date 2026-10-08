"""Tests for ``framework.extract.llm`` with a stub provider (no network)."""

from __future__ import annotations

import json

import pytest

from temporal_hypo.framework.claim_schema import (
    FLAT_JSON_SCHEMA,
    MODES,
    MODE_SPEC,
    StructuredClaim,
    claim_from_flat,
    derive_procedure,
    from_gold,
)
from temporal_hypo.framework.extract.llm import (
    H0_BY_MODE,
    ROLES_BY_MODE,
    WHAT_JSON_SCHEMA,
    LLMExtractor,
    fewshot_pairs,
    flat_from_claim,
    h0_for,
    mode_catalogue,
    question_row_from_answer,
    snap_terms,
    system_prompt,
)
from temporal_hypo.framework.extract.llm_client import Completion, ollama_available
from temporal_hypo.generation.pilot import RULE_BY_MODE
from tests.framework.conftest import CORPUS, H, F, P, R, N, C  # noqa: F401

VOCAB = {H, F, P, R, N, C}


class StubProvider:
    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = []

    def complete(self, messages, *, schema, model, temperature=0.0, max_tokens=800):
        self.calls.append({"messages": messages, "schema": schema, "model": model})
        text = self.texts.pop(0) if self.texts else "{}"
        return Completion(text=text, prompt_tokens=100, completion_tokens=20, ms=2.0, cached=False)


# ---------------------------------------------------------------------------
# synthetic release-shaped rows
# ---------------------------------------------------------------------------

def q_row(group_id, text, *, level="vaccine", answer_type="BOOL", vaccines=("Pfizer",),
          report_id=None, options=None, register="original", fmt="claim"):
    cohort = {"level": level, "vaccines": list(vaccines) if report_id is None else [],
              "report_id": report_id}
    return {"hypothesis_id": f"{group_id}-0000-{register}-{fmt}", "group_id": group_id,
            "level": level, "answer_type": answer_type, "register": register, "format": fmt,
            "text": text, "options": options, "cohort": cohort}


def a_row(mode, events, *, vaccines=("Pfizer",), report_id=None, negated=False, options=None):
    s = MODE_SPEC[mode]
    level = "report" if report_id is not None else s.tier
    return {"mode": mode, "family": s.family, "negated": negated,
            "cohort": {"level": level, "vaccines": [] if report_id else list(vaccines),
                       "report_id": report_id},
            "options": options,
            "factual_core": {"primitive": s.primitive, "events": list(events),
                             "vaccines": [] if report_id else list(vaccines),
                             "report_id": report_id}}


ANSWER_ROWS = [
    a_row("dir_bool", [H, F]),
    a_row("rep_dir_choice", [H, F], report_id=1001, options=[H, F]),
    a_row("sym_bool_cooccurs", [H, F], vaccines=("Moderna",), negated=True),
    a_row("modal_choice", [H, F, P], vaccines=("Moderna",),
          options=[f"{a} → {b} → {c}" for a, b, c in
                   [(H, F, P), (H, P, F), (F, H, P), (F, P, H), (P, H, F), (P, F, H)]]),
    a_row("multi_dir_precedes", [H, F], vaccines=("Pfizer", "Moderna"), options=["Pfizer", "Moderna"]),
    a_row("pairpair_bool", [H, F, P, R], vaccines=("Janssen",)),
    a_row("first_choice", [P, H, F], vaccines=("Moderna",), options=[H, P, F]),
    a_row("rep_seq_bool", [H, F, P], report_id=2001),
    a_row("assoc_bool", [R, N], vaccines=("Janssen",)),
    a_row("cooc_modal_bool", [H, F], vaccines=("Pfizer",), negated=True),
]

DIR_ROW = q_row("P-V1", "After Pfizer, Headache typically occurs before Fatigue.")
FLAT_DIR = {"mode": "dir_bool", "events": [H, F], "negated": False, "asserted_option": None,
            "test": "binom_exact", "null_kind": "binomial", "p0": 0.5, "claim_tail": "greater",
            "arms": 1, "conditioning": "ordered_pair", "min_n_floor": 10}


# ---------------------------------------------------------------------------
# catalogue / prompt
# ---------------------------------------------------------------------------

def test_h0_and_roles_cover_all_20_modes():
    assert set(H0_BY_MODE) == set(MODES) == set(ROLES_BY_MODE) == set(RULE_BY_MODE)
    for mode in MODES:
        assert H0_BY_MODE[mode].startswith("H0:")
        filled = h0_for(mode, [H, F, P, R], ["Pfizer", "Moderna"])
        assert "{" not in filled and "}" not in filled
    assert h0_for("dir_bool", [H, F]) == \
        f"H0: P({H} precedes {F}) = 0.5 (no directional preference among ordered reports)"
    assert h0_for("multi_dir_precedes", [H, F], ["Pfizer", "Moderna"]).endswith(
        "is equal for Pfizer and Moderna (p1 = p2)")
    assert h0_for("seq_bool") == ("H0: the A -> B -> C ordering and the runner-up ordering are "
                                  "equally frequent (P = 0.5; no unique mode)")
    assert h0_for("rep_dir_bool").startswith("H0: none")


def test_mode_catalogue_has_one_line_per_mode_with_rule_and_h0():
    cat = mode_catalogue(show_groups=True)
    lines = cat.splitlines()
    assert len(lines) == 1 + len(MODES)
    for mode in MODES:
        line = next(l for l in lines[1:] if l.startswith(mode + " |"))
        assert RULE_BY_MODE[mode] in line and H0_BY_MODE[mode] in line
        assert MODE_SPEC[mode].conditioning in line
    assert "P-V1" in cat and "P-V1" not in mode_catalogue(show_groups=False)
    assert "fisher_exact" in cat and "fisher_exact" not in mode_catalogue(include_procedure=False)


def test_system_prompt_states_constants_and_schema():
    sp = system_prompt(procedure_given=False, blind_group=False)
    for needle in ("0.05", "10 for pairwise", "5 for", "sequence", "VERBATIM", "ORDER THE CLAIM ASSERTS",
                   "negated", "asserted_option", "FIRST mention", "group_id"):
        assert needle in sp
    assert json.dumps(FLAT_JSON_SCHEMA, ensure_ascii=False) in sp
    blind = system_prompt(procedure_given=True, blind_group=True)
    assert json.dumps(WHAT_JSON_SCHEMA, ensure_ascii=False) in blind
    assert "and group_id" not in blind
    assert "derived by the harness" in blind
    assert set(WHAT_JSON_SCHEMA["properties"]) == {"mode", "events", "negated", "asserted_option"}


# ---------------------------------------------------------------------------
# flat <-> claim round trip
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("row", ANSWER_ROWS, ids=[r["mode"] for r in ANSWER_ROWS])
def test_flat_from_claim_round_trips_through_claim_from_flat(row):
    gold = from_gold(row)
    flat = flat_from_claim(gold)
    assert set(flat) >= {"mode", "events", "negated", "asserted_option", "test", "null_kind",
                         "p0", "claim_tail", "arms", "conditioning", "min_n_floor"}
    assert set(flat) <= set(FLAT_JSON_SCHEMA["properties"])
    json.dumps(flat)  # serialisable
    qrow = question_row_from_answer(row)
    back = claim_from_flat(flat, qrow, source="gold")
    assert back.what_key() == gold.what_key()
    assert back.procedure == gold.procedure
    assert back.options == gold.options
    assert back.underdetermined == gold.underdetermined == ()
    assert back.to_dict() == gold.to_dict()
    # WHAT-only flat (procedure-given) still round-trips when the procedure is derived
    what = flat_from_claim(gold, include_procedure=False)
    assert set(what) == {"mode", "events", "negated", "asserted_option"}
    back2 = claim_from_flat(what, qrow, source="gold", procedure_given=True)
    assert back2.to_dict() == gold.to_dict()


def test_question_row_from_answer_renders_the_original_claim_text():
    qrow = question_row_from_answer(ANSWER_ROWS[0])
    assert qrow["text"] == "After Pfizer, Headache typically occurs before Fatigue."
    assert qrow["group_id"] == "P-V1" and qrow["level"] == "vaccine"
    qrow = question_row_from_answer(ANSWER_ROWS[1])
    assert qrow["text"] == "In report MT-0001001, Headache came first, before Fatigue."
    neg = question_row_from_answer(ANSWER_ROWS[2])   # negated C-V1 wording exists
    assert "not" in neg["text"].lower()
    multi = question_row_from_answer(ANSWER_ROWS[4])
    assert "Pfizer" in multi["text"] and "Moderna" in multi["text"]


def test_fewshot_pairs_accepts_tuples_answer_rows_dict_pairs_and_merged_rows():
    tup = (DIR_ROW, ANSWER_ROWS[0])                    # what scripts/run_eval.py passes
    pair = {"question": DIR_ROW, "answer": ANSWER_ROWS[0]}
    merged = {**DIR_ROW, **ANSWER_ROWS[0]}
    pairs = fewshot_pairs([tup, ANSWER_ROWS[1], pair, merged, {"junk": 1}, ("x",), 42], k=10)
    assert len(pairs) == 4
    assert pairs[0][0] is not DIR_ROW and pairs[0] == (DIR_ROW, ANSWER_ROWS[0])
    assert pairs[1][0]["text"].startswith("In report MT-0001001")
    assert pairs[2][0]["text"] == DIR_ROW["text"]
    assert pairs[3][0]["text"] == DIR_ROW["text"] and pairs[3][1]["mode"] == "dir_bool"
    assert len(fewshot_pairs(ANSWER_ROWS, k=2)) == 2
    assert fewshot_pairs(ANSWER_ROWS, k=0) == []


# ---------------------------------------------------------------------------
# the extractor
# ---------------------------------------------------------------------------

def test_extract_builds_a_claim_from_canned_flat_json():
    stub = StubProvider([json.dumps(FLAT_DIR)])
    ex = LLMExtractor(stub, "stub-model", vocabulary=VOCAB, k_shot=0)
    assert ex.name == "llm:stub-model"
    claim = ex.extract(DIR_ROW)
    assert isinstance(claim, StructuredClaim)
    assert claim.mode == "dir_bool" and claim.terms == (H, F)
    assert claim.cohorts[0].vaccine == "Pfizer" and claim.negated is False
    assert claim.source == "llm:stub-model"
    assert claim.procedure == derive_procedure("dir_bool")
    assert claim.raw["mode"] == "dir_bool"
    assert ex.last_error is None and ex.last_flat == FLAT_DIR
    assert ex.last_usage == {"prompt": 100, "completion": 20} and ex.last_ms == 2.0
    assert ex.last_tokens == ex.last_usage and ex.last_cached is False
    assert len(stub.calls) == 1
    call = stub.calls[0]
    assert call["schema"] is FLAT_JSON_SCHEMA and call["model"] == "stub-model"
    assert call["messages"][0]["role"] == "system"
    user = json.loads(call["messages"][-1]["content"])
    assert user["group_id"] == "P-V1" and user["text"] == DIR_ROW["text"]
    assert "hypothesis_id" not in user


def test_extract_blind_group_hides_group_id_in_every_user_turn():
    stub = StubProvider([json.dumps(FLAT_DIR)])
    ex = LLMExtractor(stub, "m", fewshot=ANSWER_ROWS[:3], k_shot=3)
    claim = ex.extract(DIR_ROW, blind_group=True)
    assert claim is not None
    msgs = stub.calls[0]["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user", "assistant",
                                         "user", "assistant", "user"]
    for m in msgs:
        if m["role"] == "user":
            d = json.loads(m["content"])
            assert "group_id" not in d and "hypothesis_id" not in d
            assert {"level", "answer_type", "text", "cohort"} <= set(d)
    # the assistant turns are valid flat JSON for the gold claim of each example
    shot = json.loads(msgs[2]["content"])
    assert shot["mode"] == "dir_bool" and shot["events"] == [H, F] and "test" in shot
    assert "P-V1" not in msgs[0]["content"]          # blind catalogue shows no group ids


def test_extract_given_group_fewshot_shows_group_and_neutral_question_asserts_nothing():
    q = q_row("P-R2", "Which came first in report MT-0001001, Headache or Fatigue?",
              level="report", answer_type="CHOICE", report_id=1001, options=[H, F], fmt="question")
    stub = StubProvider([json.dumps(FLAT_DIR)])
    ex = LLMExtractor(stub, "m", fewshot=[{"question": q, "answer": ANSWER_ROWS[1]}], k_shot=1,
                      procedure_given=True)
    ex.extract(DIR_ROW)
    msgs = stub.calls[0]["messages"]
    assert json.loads(msgs[1]["content"])["group_id"] == "P-R2"
    shot = json.loads(msgs[2]["content"])
    assert shot == {"mode": "rep_dir_choice", "events": [H, F], "negated": False,
                    "asserted_option": None}
    assert stub.calls[0]["schema"] is WHAT_JSON_SCHEMA


def test_extract_honours_procedure_given_over_a_wrong_stated_procedure():
    wrong = dict(FLAT_DIR, test="fisher_exact", null_kind="two_arm_equality", p0=None,
                 claim_tail="less", arms=2, conditioning="presence_split", min_n_floor=5)
    blind = LLMExtractor(StubProvider([json.dumps(wrong)]), "m", k_shot=0).extract(DIR_ROW)
    assert blind is not None
    assert blind.procedure.test == "fisher_exact" and blind.procedure.arms == 2
    assert blind.procedure.claim_tail == "less" and blind.procedure.min_n_floor == 5
    given = LLMExtractor(StubProvider([json.dumps(wrong)]), "m", k_shot=0,
                         procedure_given=True).extract(DIR_ROW)
    assert given is not None
    assert given.procedure == derive_procedure("dir_bool")
    assert given.what_key() == blind.what_key()


def test_extract_retries_once_on_garbage_then_returns_none():
    stub = StubProvider(["I cannot do that.", "still not json"])
    ex = LLMExtractor(stub, "m", k_shot=0)
    assert ex.extract(DIR_ROW) is None
    assert len(stub.calls) == 2
    assert ex.last_error is not None and "ValueError" in ex.last_error
    repair = stub.calls[1]["messages"]
    assert repair[-2] == {"role": "assistant", "content": "I cannot do that."}
    assert repair[-1]["role"] == "user" and "ONLY one JSON object" in repair[-1]["content"]
    assert ex.last_usage == {"prompt": 200, "completion": 40}


def test_extract_repair_retry_recovers():
    stub = StubProvider(['{"mode": "nonsense", "events": [], "negated": false}',
                         "```json\n" + json.dumps(FLAT_DIR) + "\n```"])
    ex = LLMExtractor(stub, "m", k_shot=0)
    claim = ex.extract(DIR_ROW)
    assert claim is not None and claim.mode == "dir_bool"
    assert len(stub.calls) == 2
    assert "unknown mode 'nonsense'" in stub.calls[1]["messages"][-1]["content"]
    assert any("repair retry" in n for n in ex.last_notes)
    assert claim.raw["notes"] == ex.last_notes


def test_extract_returns_none_when_the_provider_raises():
    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("server down at http://localhost:11434/api/chat")

    ex = LLMExtractor(Boom(), "m", k_shot=0)
    assert ex.extract(DIR_ROW) is None
    assert "server down" in ex.last_error


def test_extract_pads_arity_and_records_oov_without_correcting():
    flat = dict(FLAT_DIR, mode="seq_bool", events=[" Headache ", "Fatigu"])
    ex = LLMExtractor(StubProvider([json.dumps(flat)]), "m", k_shot=0, vocabulary=VOCAB)
    claim = ex.extract(q_row("S-V1", "x"))
    assert claim is not None and claim.mode == "seq_bool"
    assert claim.terms == (H, "Fatigu", None)          # stripped, not corrected, padded
    assert claim.is_underdetermined
    assert any("'Fatigu'" in n for n in ex.last_notes) and not any(H in n for n in ex.last_notes)


def test_snap_terms_is_exact_match_only():
    terms, oov = snap_terms([" Headache", "headache", None, "Rash"], VOCAB)
    assert terms == [H, "headache", None, R] and oov == ["headache"]
    assert snap_terms(["x"], None) == (["x"], [])


def test_extract_choice_asserted_option_from_model_wins_over_default():
    q = q_row("F-V1", "After Moderna, which of Headache, Pyrexia, Fatigue is most commonly the first event?",
              answer_type="CHOICE", vaccines=("Moderna",), options=[H, P, F], fmt="question")
    flat = {"mode": "first_choice", "events": [H, P, F], "negated": False, "asserted_option": P}
    claim = LLMExtractor(StubProvider([json.dumps(flat)]), "m", k_shot=0,
                         procedure_given=True).extract(q)
    assert claim is not None and claim.asserted_option == P and claim.options == (H, P, F)
    flat_null = dict(flat, asserted_option=None)
    claim2 = LLMExtractor(StubProvider([json.dumps(flat_null)]), "m", k_shot=0,
                          procedure_given=True).extract(q)
    assert claim2.asserted_option == H                # claim_from_flat's default: first-named


# ---------------------------------------------------------------------------
# live (skipped unless a local Ollama answers)
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.skipif(not ollama_available(), reason="no Ollama at localhost:11434")
def test_live_llm_extractor_parses_a_plain_claim(tmp_path):
    from temporal_hypo.framework.extract.llm_client import CacheDir, OllamaClient

    client = OllamaClient(cache=CacheDir(tmp_path))
    models = client.models()
    if not models:
        pytest.skip("Ollama is running but has no models pulled")
    ex = LLMExtractor(client, models[0], fewshot=ANSWER_ROWS, k_shot=3, vocabulary=VOCAB)
    claim = ex.extract(DIR_ROW)
    assert claim is not None, ex.last_error
    assert claim.mode in MODES and len(claim.events) == MODE_SPEC[claim.mode].n_events
