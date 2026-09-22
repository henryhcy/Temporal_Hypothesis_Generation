"""The two 2026-09-22 baselines: end-to-end text-to-SQL, and counts-only verdict.

What these pin down is the thing that makes each baseline INTERPRETABLE:

- ``e2e-llm-sql`` must withhold the mode, the conditioning rule and the arm plan.
  If any of those leaked back into the prompt the run would silently become
  ``rules+llm-sql`` and the comparison between them would measure nothing.
- ``counts-llm`` must take the verdict from the MODEL and the counts from the
  reference, and must leave the report tier deterministic (it has no counts).
"""

from __future__ import annotations

import json

import pytest

from temporal_hypo.framework.counts_llm import CountsVerdictTester, counts_messages
from temporal_hypo.framework.extract.llm_client import Completion
from temporal_hypo.framework.sql.e2e_sql import E2ESQLRetriever, e2e_messages
from temporal_hypo.framework.sql.llm_sql import sql_messages


def _completion(text: str) -> Completion:
    return Completion(text=text, prompt_tokens=10, completion_tokens=5, ms=1.0, cached=False)


class _Say:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.seen: list[list[dict]] = []

    def complete(self, messages, **kw):
        self.seen.append(messages)
        return _completion(json.dumps(self.payload))


# -- e2e prompt: what it must NOT contain ----------------------------------

def test_e2e_prompt_withholds_mode_conditioning_and_arm_plan(claim_and_row, eval_ddl):
    claim, row = claim_and_row
    blob = "".join(m["content"] for m in e2e_messages(row, claim, eval_ddl))
    assert claim.mode not in blob                    # the mode name
    assert "CONDITIONING RULE" not in blob
    assert "ARM PLAN" not in blob
    assert "EXCLUSION (" not in blob
    assert '"events"' not in blob                    # no claim JSON
    assert row["text"] in blob                       # the sentence IS given


def test_e2e_prompt_keeps_what_rules_llm_sql_also_gives(claim_and_row, eval_ddl):
    """DDL, row contract and arm labels are an output spec, not the capability."""
    claim, row = claim_and_row
    e2e = "".join(m["content"] for m in e2e_messages(row, claim, eval_ddl))
    old = "".join(m["content"] for m in sql_messages(claim, eval_ddl))
    for shared in ("first_mention", "ROW CONTRACT", "in_denominator"):
        assert shared in e2e and shared in old
    assert len(e2e) < len(old)                       # strictly less is told


def test_e2e_never_reads_group_id(claim_and_row, eval_ddl):
    claim, row = claim_and_row
    row = dict(row, group_id="P-V1")
    assert "P-V1" not in "".join(m["content"] for m in e2e_messages(row, claim, eval_ddl))


def test_e2e_requires_the_row(claim_and_row, executor):
    claim, _row = claim_and_row
    r = E2ESQLRetriever(_Say({"arms": []}), "fake", executor)
    with pytest.raises(RuntimeError, match="needs the question row"):
        r.messages_for(claim)


def test_e2e_declares_wants_row_so_the_pipeline_feeds_it():
    assert E2ESQLRetriever.wants_row is True


# -- counts-only: the model supplies the verdict, nothing else -------------

def test_counts_prompt_has_the_numbers_and_the_rule(claim_and_row, gold_retrieval):
    claim, _ = claim_and_row
    blob = "".join(m["content"] for m in counts_messages(claim, gold_retrieval[1]))
    assert "three-decision" in blob and "OPPOSITE" in blob
    assert '"n":' in blob and '"k":' in blob
    assert "alpha" in blob and "min_n_floor" in blob


def test_counts_verdict_comes_from_the_model(claim_and_row, gold_retrieval):
    claim, _ = claim_and_row
    retrieval, core = gold_retrieval
    for said in ("supported", "refuted", "insufficient"):
        pred = CountsVerdictTester(_Say({"verdict": said}), "fake")(claim, retrieval)
        assert pred.verdict == said and pred.response == said
        assert (pred.n, pred.k) == (core.n, core.k)   # counts are INPUT, not predicted


def test_counts_bad_reply_falls_into_the_punished_class(claim_and_row, gold_retrieval):
    claim, _ = claim_and_row
    t = CountsVerdictTester(_Say({"verdict": "probably"}), "fake")
    pred = t(claim, gold_retrieval[0])
    assert pred.verdict == "insufficient"
    assert t.last_error and "probably" in t.last_error


def test_counts_leaves_the_report_tier_deterministic(report_claim_and_retrieval):
    claim, retrieval = report_claim_and_retrieval
    say = _Say({"verdict": "refuted"})
    pred = CountsVerdictTester(say, "fake")(claim, retrieval)
    assert say.seen == []                             # the model was never asked
    assert pred.subtype == "deterministic" or pred.verdict in ("supported", "refuted")


# -- fixtures --------------------------------------------------------------
# Built on the synthetic corpus so these never touch the release or the API.

@pytest.fixture(scope="module")
def eval_ddl():
    from temporal_hypo.framework.sql.llm_sql import load_eval_ddl
    return load_eval_ddl()


@pytest.fixture(scope="module")
def executor(eval_db_path):
    from temporal_hypo.framework.sql.executor import ReadOnlyExecutor
    ex = ReadOnlyExecutor(str(eval_db_path))
    yield ex
    ex.close()


@pytest.fixture(scope="module")
def claim_and_row():
    """A cohort-tier precedes claim plus the question row it was rendered from."""
    from temporal_hypo.framework.claim_schema import build_claim
    cohort = {"level": "vaccine", "vaccines": ["Pfizer"], "report_id": None}
    claim = build_claim("dir_bool", ("Headache", "Fatigue"), cohort, source="test")
    row = {"level": "vaccine", "answer_type": "BOOL", "register": "original",
           "format": "claim", "options": None, "cohort": cohort,
           "text": "After Pfizer, Headache typically occurs before Fatigue."}
    return claim, row


@pytest.fixture(scope="module")
def gold_retrieval(claim_and_row, executor):
    from temporal_hypo.framework.pipeline import CompilerRetriever
    from temporal_hypo.framework.run_test import to_viable_core
    claim, _ = claim_and_row
    r = CompilerRetriever(executor).retrieve(claim)
    return r, to_viable_core(claim, r)


@pytest.fixture(scope="module")
def report_claim_and_retrieval(executor):
    from temporal_hypo.framework.claim_schema import build_claim
    from temporal_hypo.framework.pipeline import CompilerRetriever
    cohort = {"level": "report", "vaccines": [], "report_id": 1001}
    claim = build_claim("rep_dir_bool", ("Headache", "Fatigue"), cohort, source="test")
    return claim, CompilerRetriever(executor).retrieve(claim)
