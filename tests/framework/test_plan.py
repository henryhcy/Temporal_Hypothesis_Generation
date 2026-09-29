"""Tests for the toolbox frame: the Plan, derive_mode, and a leak-free prompt."""

from __future__ import annotations

import json

import pytest

from temporal_hypo.framework.claim_schema import (
    GROUP_BY_MODE,
    MODE_SPEC,
    MODES,
    PLAN_JSON_SCHEMA,
    build_claim,
    claim_from_plan,
    derive_mode,
    derive_plan,
    derive_procedure,
    plan_from_claim,
)
from temporal_hypo.framework.extract.llm import toolbox_system_prompt


def _row_for(mode: str) -> dict:
    s = MODE_SPEC[mode]
    terms = ["Fatigue", "Headache", "Nausea", "Chills"][: s.n_events]
    if s.is_report:
        cohort = {"level": "report", "vaccines": [], "report_id": 941886}
    elif mode == "multi_dir_precedes":
        cohort = {"level": "multi", "vaccines": ["Pfizer", "Moderna"], "report_id": None}
    else:
        cohort = {"level": "vaccine", "vaccines": ["Moderna"], "report_id": None}
    options = None
    if s.answer_type == "CHOICE":
        options = ["Pfizer", "Moderna"] if mode == "multi_dir_precedes" else list(terms)
    return {"level": s.tier, "answer_type": s.answer_type, "cohort": cohort,
            "options": options, "format": "claim"}, terms


@pytest.mark.parametrize("mode", MODES)
def test_derive_mode_inverts_derive_plan(mode):
    s = MODE_SPEC[mode]
    p = derive_plan(mode)
    assert derive_mode(s.tier, s.answer_type, s.n_events, p["arms"], p["denominator"],
                       p["quantity"], p["extreme"]) == mode


@pytest.mark.parametrize("mode", MODES)
def test_plan_round_trips_the_claim(mode):
    row, terms = _row_for(mode)
    gold = build_claim(mode, terms, row["cohort"], options=row["options"], source="gold")
    plan = plan_from_claim(gold)
    back = claim_from_plan(plan, row, source="test")
    assert back.mode == mode
    assert back.what_key() == gold.what_key()
    assert back.procedure == derive_procedure(mode)
    assert back.to_dict()["plan"]["quantity"] == plan["quantity"]
    assert type(back).from_dict(back.to_dict()).plan == plan


def test_plan_schema_is_self_consistent():
    props = PLAN_JSON_SCHEMA["properties"]
    for key in PLAN_JSON_SCHEMA["required"]:
        assert key in props
    for mode in MODES:
        p = derive_plan(mode)
        for k, v in p.items():
            spec = props[k]
            if "enum" in spec:
                assert v in spec["enum"], (mode, k, v)


def test_plan_with_no_matching_shape_raises():
    row, terms = _row_for("dir_bool")
    plan = dict(derive_plan("dir_bool"), events=terms, negated=False,
                quantity="extreme_of_set", extreme="earliest")   # 2 events cannot be a set extreme
    with pytest.raises(ValueError, match="no mode for plan shape"):
        claim_from_plan(plan, row, source="test")


def test_toolbox_prompt_leaks_no_mode_or_group_names():
    text = toolbox_system_prompt(dataset_card="DATASET: test card", blind_group=True)
    lowered = text.lower()
    for mode in MODES:
        assert mode not in lowered, mode
    for gid in GROUP_BY_MODE.values():
        assert gid not in text, gid
    assert "H0:" not in text                      # no per-mode null strings
    assert "binom_exact with null_kind" not in text  # no mapping sentence
    # the primitives and the toolbox ARE there
    for needle in ("ordered_pair", "presence_split", "data_derived", "two_proportions",
                   "STAGE POPULATION", "PROCEDURE"):
        assert needle in text, needle
    json.loads(text.split("no code fences):\n", 1)[1].split("\n\nFIELD RULES", 1)[0])
