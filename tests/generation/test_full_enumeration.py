"""Tests for the whole-population enumeration path (scripts/run_pilot.py --full)."""

from __future__ import annotations

from temporal_hypo.generation import cores
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.instances import build_records
from temporal_hypo.generation.templates import load_groups


def test_cooccurring_pairs_threshold(make_db_fixture):
    # (A,B) together in 12 reports, (A,C) in only 3 -> only (A,B) clears n>=10
    reports = [(i, "Pfizer", [["A"], ["B"]]) for i in range(12)]
    reports += [(100 + i, "Pfizer", [["A"], ["C"]]) for i in range(3)]
    idx = CorpusIndex.load(make_db_fixture(reports))
    pairs = cores._cooccurring_pairs(idx, idx.cohort("Pfizer"))
    assert ("A", "B") in pairs
    assert ("A", "C") not in pairs


def test_cooccurring_triples_threshold(make_db_fixture):
    reports = [(i, "Pfizer", [["A"], ["B"], ["C"]]) for i in range(11)]
    reports += [(100 + i, "Pfizer", [["A"], ["B"], ["D"]]) for i in range(4)]
    idx = CorpusIndex.load(make_db_fixture(reports))
    triples = cores._cooccurring_triples(idx, idx.cohort("Pfizer"))
    assert ("A", "B", "C") in triples
    assert ("A", "B", "D") not in triples


def test_full_report_enum_has_no_cap(make_db_fixture):
    # one core per report, beyond the MAX_REPORT_CORES=300 cap of the pilot path
    reports = [(i, "Pfizer", [["A"], ["B"]]) for i in range(cores.MAX_REPORT_CORES + 25)]
    idx = CorpusIndex.load(make_db_fixture(reports))
    groups = load_groups()
    capped = cores.enumerate_group(idx, groups["P-R1"])
    full = cores.enumerate_group_full(idx, groups["P-R1"])
    assert len(capped) == cores.MAX_REPORT_CORES
    assert len(full) == cores.MAX_REPORT_CORES + 25


def test_full_enum_is_candidate_superset(make_db_fixture):
    # full enumeration covers every top-K core (and generally more)
    reports = []
    vid = 0
    # 30 distinct terms, each co-occurring with "Base" in >=10 reports
    for t in range(30):
        for _ in range(12):
            reports.append((vid, "Pfizer", [["Base"], [f"T{t}"]]))
            vid += 1
    idx = CorpusIndex.load(make_db_fixture(reports))
    groups = load_groups()
    # top-K builds combinations of the 25 most-frequent terms (many non-viable);
    # full draws every co-occurring pair. Compare the VIABLE (computable) cores.
    topk_comp = [c for c in cores.enumerate_group(idx, groups["P-V1"]) if c.computable]
    full_comp = [c for c in cores.enumerate_group_full(idx, groups["P-V1"]) if c.computable]
    assert len(full_comp) >= len(topk_comp)
    assert len(full_comp) == 30                              # all 30 viable pairs
    assert len(full_comp) > cores.K_PAIR                     # beyond the top-K cap


def test_full_emit_natural_verdict_builds_records(make_db_fixture):
    reports = [(i, "Pfizer", [["A"], ["B"]]) for i in range(16)]
    reports += [(100 + i, "Pfizer", [["B"], ["A"]]) for i in range(4)]
    idx = CorpusIndex.load(make_db_fixture(reports))
    groups = load_groups()
    cores_list = [c for c in cores.enumerate_group_full(idx, groups["P-V1"])
                  if c.computable]
    assert cores_list
    core = cores_list[0]
    facts = cores.realize(core, core.natural_verdict)
    recs = build_records(facts, groups["P-V1"], seq=0)
    assert len(recs) == 8
    assert {r["gold_verdict"] for r in recs} == {core.natural_verdict}
