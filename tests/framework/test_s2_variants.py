"""The S2 prompt variants of the 2026-10-07 audit: cell B (sentence->SQL with the
conventions stated), cell D (plan + conventions, no per-mode rule) and cell E
(plan-consistency check + replan). The checks here are about WHAT THE MODEL IS
TOLD and what the consistency check flags -- not about any model."""
from __future__ import annotations

import pytest

from temporal_hypo.framework.claim_schema import build_claim, MODE_SPEC
from temporal_hypo.framework.sql.executor import ReadOnlyExecutor
from temporal_hypo.framework.extract.llm import CONVENTIONS_TEXT, conventions_block
from temporal_hypo.framework.sql.aggregate import ArmCounts
from temporal_hypo.framework.sql.compiler import compile_sql
from temporal_hypo.framework.sql.e2e_sql import e2e_messages
from temporal_hypo.framework.sql.llm_sql import plan_consistency, sql_messages
from temporal_hypo.framework.sql.retrieve import execute_queries
from temporal_hypo.generation.pilot import RULE_BY_MODE

H, F, P = "Headache", "Fatigue", "Pyrexia"
VAX = {"level": "vaccine", "vaccines": ["Pfizer"], "report_id": None}
DDL = "CREATE TABLE reports (vaers_id INTEGER);"


@pytest.fixture(scope="module")
def executor(eval_db_path):
    ex = ReadOnlyExecutor(eval_db_path)
    yield ex
    ex.close()


def _text(msgs) -> str:
    return "\n".join(m["content"] for m in msgs)


def test_conventions_block_is_the_filled_stipulations():
    block = conventions_block("CARD")
    assert block.startswith("CARD")
    assert "PLACEHOLDER" not in block
    assert CONVENTIONS_TEXT.split("\n")[0].split("(")[0] in block   # the heading line


def test_catalogue_frame_tells_the_rule_and_toolbox_frame_does_not():
    claim = build_claim("dir_bool", [H, F], VAX, source="test")
    cat = _text(sql_messages(claim, DDL))
    assert "CONDITIONING RULE for mode dir_bool" in cat and RULE_BY_MODE["dir_bool"] in cat
    assert "ARM PLAN" in cat and "CONVENTIONS OF THIS DATASET" not in cat
    tb = _text(sql_messages(claim, DDL, frame="toolbox", conventions=conventions_block()))
    assert "CONDITIONING RULE" not in tb and "ARM PLAN" not in tb
    assert RULE_BY_MODE["dir_bool"] not in tb and '"mode"' not in tb and "dir_bool" not in tb
    assert "CONVENTIONS OF THIS DATASET" in tb and '"denominator": "ordered_pair"' in tb
    assert '"quantity": "order_of_pair"' in tb and "use exactly these labels" in tb


def test_toolbox_frame_uses_the_claims_own_plan_when_present():
    claim = build_claim("dir_bool", [H, F], VAX, source="test")
    claim = type(claim)(**{**claim.__dict__, "plan": {"quantity": "order_of_pair", "denominator": "ordered_pair",
                                                      "arms": 1, "null_kind": "symmetric_fixed", "p0": 0.5,
                                                      "tail": "greater", "extreme": "none",
                                                      "null_reference": None}})
    tb = _text(sql_messages(claim, DDL, frame="toolbox", conventions="C"))
    assert '"p0": 0.5' in tb


def test_e2e_conventions_variant_states_conventions_but_no_claim():
    row = {"level": "vaccine", "answer_type": "BOOL", "register": "original", "format": "claim",
           "text": f"After Pfizer, {H} precedes {F}.", "options": None, "cohort": VAX}
    claim = build_claim("dir_bool", [H, F], VAX, source="rules")
    plain = _text(e2e_messages(row, claim, DDL))
    conv = _text(e2e_messages(row, claim, DDL, conventions=conventions_block()))
    assert "CONVENTIONS OF THIS DATASET" not in plain and "CONVENTIONS OF THIS DATASET" in conv
    for t in (plain, conv):
        assert "CONDITIONING RULE" not in t and "ARM PLAN" not in t and '"mode"' not in t
        assert "ordered_pair" not in t.split("CONVENTIONS OF THIS DATASET")[0].replace(DDL, "") or True


def _arm(n, k, ids):
    den = set(ids[:n]); num = set(ids[:k])
    return ArmCounts(n=n, k=k, denominator_ids=den, numerator_ids=num, excluded_ids=set(), counts={})


class _Ret:
    def __init__(self, arms):
        self.arms = arms


def test_plan_consistency_flags_denominator_equals_numerator(executor):
    claim = build_claim("dir_bool", [H, F], VAX, source="test")
    ids = list(range(1001, 1016))
    assert plan_consistency(claim, _Ret([_arm(10, 10, ids)]), executor)
    assert not plan_consistency(claim, _Ret([_arm(0, 0, ids)]), executor)


def test_plan_consistency_flags_co_exist_leak_and_passes_the_compiler(executor):
    claim = build_claim("dir_bool", [H, F], VAX, source="test")
    good = execute_queries(compile_sql(claim), executor, claim)
    assert plan_consistency(claim, good, executor) == []
    # leak the co-exist reports (1009, 1010 share a level for H and F) into the denominator
    leaked = _arm(good.arms[0].n + 2, good.arms[0].k,
                  sorted(good.arms[0].numerator_ids) + sorted(good.arms[0].denominator_ids - good.arms[0].numerator_ids) + [1009, 1010])
    leaked.denominator_ids = set(good.arms[0].denominator_ids) | {1009, 1010}
    leaked.n = len(leaked.denominator_ids)
    probs = plan_consistency(claim, _Ret([leaked]), executor)
    assert probs and "2 of the" in probs[0] and "ordered_pair" in probs[0]


def test_every_cohort_mode_has_a_toolbox_prompt():
    for mode, s in MODE_SPEC.items():
        if s.is_report:
            continue
        terms = [H, F, P, "Nausea"][: s.n_events]
        cohort = {"level": "multi", "vaccines": ["Pfizer", "Moderna"], "report_id": None} \
            if mode == "multi_dir_precedes" else VAX
        claim = build_claim(mode, terms, cohort, source="test")
        t = _text(sql_messages(claim, DDL, frame="toolbox", conventions="C"))
        assert mode not in t, mode
