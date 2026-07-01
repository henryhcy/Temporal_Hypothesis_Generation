"""Tests for JSONL record assembly."""

from __future__ import annotations

from temporal_hypo.generation.cores import ViableCore, realize
from temporal_hypo.generation.instances import build_records
from temporal_hypo.generation.templates import FORMATS, REGISTERS, load_groups


def _core():
    return ViableCore(
        group_id="P-V1", family="pairwise", primitive="precedes", level="vaccine",
        answer_type="BOOL", mode="dir_bool", events=("Headache", "Fever"),
        vaccines=("Pfizer",), cohort_ids=[1, 2, 3], report_id=None,
        computable=True, natural_verdict="supported", proportion=0.7, n=20, k=14,
    )


def _prop_core():
    return ViableCore(
        group_id="P-V2", family="pairwise", primitive="precedes", level="vaccine",
        answer_type="PROP", mode="prop_precedes", events=("Headache", "Fever"),
        vaccines=("Pfizer",), cohort_ids=[1], report_id=None,
        computable=True, natural_verdict="supported", proportion=0.7, n=20, k=14,
    )


def _choice_core():
    return ViableCore(
        group_id="F-V1", family="first_last", primitive="first_last", level="vaccine",
        answer_type="CHOICE", mode="first_choice", events=("A", "B", "C"),
        vaccines=("Pfizer",), cohort_ids=[1], report_id=None, computable=True,
        natural_verdict="supported", proportion=0.6, n=20, k=12,
        extra={"fracs": {"A": 0.6, "B": 0.2, "C": 0.2}, "winner": "A",
               "unique": True, "tie_rate": 0.0, "counts": {"A": 12, "B": 4, "C": 4}},
    )


def test_build_records_expands_register_and_format():
    groups = load_groups()
    facts = realize(_core(), "supported")
    recs = build_records(facts, groups["P-V1"], seq=0, band="high")
    assert len(recs) == len(REGISTERS) * len(FORMATS)  # 8

    ids = {r["hypothesis_id"] for r in recs}
    assert len(ids) == 8  # unique per register/format
    for r in recs:
        assert r["register"] in REGISTERS
        assert r["format"] in FORMATS
        assert "{" not in r["text"]
        assert r["gold_verdict"] == "supported"
        assert r["group_id"] == "P-V1"
        assert r["gold_n"] == 20
        assert r["band"] == "high"
        assert r["factual_core"]["events"] == ["Headache", "Fever"]
        assert r["ci"] is not None and r["ci_width"] is not None


def test_records_carry_consistent_gold_across_variants():
    groups = load_groups()
    facts = realize(_core(), "refuted")
    recs = build_records(facts, groups["P-V1"], seq=3, band="low")
    verdicts = {r["gold_verdict"] for r in recs}
    proportions = {r["gold_proportion"] for r in recs}
    assert verdicts == {"refuted"}          # same gold across all 8 variants
    assert len(proportions) == 1


def test_bool_record_has_significance_no_choice_key():
    groups = load_groups()
    recs = build_records(realize(_core(), "supported"), groups["P-V1"], seq=0)
    for r in recs:
        assert "p_value" in r and "significant" in r and "sig_test" in r
        assert r["sig_test"] == "binom_exact"
        assert r["options"] is None and r["gold_answer"] is None
        assert r["claimed_p"] is None          # not a PROP claim


def test_prop_claimed_p_only_on_claim_format():
    groups = load_groups()
    recs = build_records(realize(_prop_core(), "supported"), groups["P-V2"], seq=0)
    claim = [r for r in recs if r["format"] == "claim"]
    question = [r for r in recs if r["format"] == "question"]
    assert all(r["claimed_p"] == 0.7 for r in claim)        # 70% asserted -> 0.70
    assert all(r["claimed_p"] is None for r in question)


def test_choice_record_carries_options_and_gold_answer():
    groups = load_groups()
    recs = build_records(realize(_choice_core(), "supported"), groups["F-V1"], seq=0)
    for r in recs:
        assert r["options"] == ["A", "B", "C"]
        assert r["gold_answer"] == "A"
        assert r["sig_test"].startswith("multinomial_gof")
