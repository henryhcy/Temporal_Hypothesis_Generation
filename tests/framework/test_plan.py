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
from tests.framework.conftest import RELEASE_DIR, RELEASE_STEM, needs_release


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



@needs_release
def test_fewshot_pool_excludes_held_out_groups():
    from temporal_hypo.framework.io import load_release
    from temporal_hypo.framework.subsets import fewshot_pool
    release = load_release(RELEASE_DIR, RELEASE_STEM, verify_sha=False)
    pool = fewshot_pool(release, (), k_per_mode=1, seed=0, exclude_groups={"P-R2", "F-R1"})
    groups = {a["group_id"] for a in pool}
    assert "P-R2" not in groups and "F-R1" not in groups
    assert len(groups) == 18



def test_two_proportion_z_matches_fisher_direction_and_is_valid_only_when_cells_large():
    from temporal_hypo.core import significance as sig
    # big balanced table: z and Fisher agree on the side of alpha
    pz = sig.two_proportion_z_p(60, 100, 40, 100, alternative="greater")
    pf = sig.fisher_exact_2x2(60, 100, 40, 100, alternative="greater")
    assert pz < 0.05 and pf < 0.05 and abs(pz - pf) < 0.01
    assert sig.min_expected_cell_2x2(60, 100, 40, 100) >= 5
    # tiny table: the guard says exact only
    assert sig.min_expected_cell_2x2(3, 10, 1, 10) < 5


def test_honouring_resolves_the_rule_on_the_counts():
    from temporal_hypo.framework.run_test import run_test
    from temporal_hypo.framework.sql.aggregate import ArmCounts

    class _Ret:
        def __init__(self, arms):
            self.arms = arms
            self.levels = None
            self.ok = True

    row, terms = _row_for("assoc_bool")
    gold = build_claim("assoc_bool", terms, row["cohort"], source="gold")
    plan = plan_from_claim(gold)
    assert plan["test_rule"] == "exact_if_small_else_asymptotic"
    claim = claim_from_plan(plan, row, source="test")
    def _ac(n, k):
        return ArmCounts(n=n, k=k, denominator_ids=set(range(n)), numerator_ids=set(range(k)),
                         excluded_ids=set())
    big = _Ret([_ac(200, 120), _ac(200, 80)])
    pred = run_test(claim, big, procedure_mode="honouring")
    assert pred.test == "chi_square_1sided"
    assert any("resolved: asymptotic" in n for n in pred.notes)
    small = _Ret([_ac(10, 8), _ac(10, 1)])   # min expected cell 4.5 < 5 -> exact
    pred2 = run_test(claim, small, procedure_mode="honouring")
    assert pred2.test == "fisher_exact"
    assert any("resolved: exact" in n for n in pred2.notes)


@pytest.mark.parametrize("shape,expected", [
    (("vaccine", "BOOL", 3, 2, "ordered_pair", "rate_across_two_arms", None), "antecedent_bool"),
    (("multi", "CHOICE", 2, 2, "ordered_pair", "order_of_pair", None), "multi_dir_precedes"),
    (("vaccine", "BOOL", 2, 1, "presence_split", "co_occurrence_of_pair", None), "assoc_bool"),
    (("vaccine", "CHOICE", 3, 1, "all_present_unique_last", "extreme_of_set", "none"), "last_choice"),
    (("report", "CHOICE", 3, 1, "single_report", "extreme_of_set", "latest"), "rep_last_choice"),
    (("report", "BOOL", 2, 2, "single_report", "order_of_pair", None), "rep_dir_bool"),
    (("report", "CHOICE", 3, 1, "single_report", "extreme_of_set", None), None),
])
def test_normalization_fills_only_implied_fields(shape, expected):
    assert derive_mode(*shape) == expected


def test_extreme_has_no_null_escape_in_the_schema():
    spec = PLAN_JSON_SCHEMA["properties"]["extreme"]
    assert spec["type"] == "string" and None not in spec["enum"] and "none" in spec["enum"]
    assert "extreme" in PLAN_JSON_SCHEMA["required"]
    assert derive_plan("dir_bool")["extreme"] == "none"


def test_normalize_plan_fills_the_implied_p0_only():
    from temporal_hypo.framework.claim_schema import normalize_plan
    assert normalize_plan({"null_kind": "symmetric_fixed", "p0": None, "quantity": "order_of_pair"})["p0"] == 0.5
    assert normalize_plan({"null_kind": "text_stated", "p0": None, "quantity": "order_of_pair"})["p0"] is None
    assert normalize_plan({"null_kind": "data_derived", "p0": None, "quantity": "order_of_pair"})["p0"] is None
    assert normalize_plan({"null_kind": "two_arm_equality", "p0": 0.5, "quantity": "order_of_pair"})["p0"] is None
