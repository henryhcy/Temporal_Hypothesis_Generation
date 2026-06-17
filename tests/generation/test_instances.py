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
