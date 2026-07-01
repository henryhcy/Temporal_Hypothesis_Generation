"""Tests for the public answer-retrieve pipeline (temporal_hypo.core.answers)."""

from __future__ import annotations

import sqlite3

import pytest

from temporal_hypo.core.answers import answer_key, compute_answer
from temporal_hypo.generation import cores
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.instances import build_records
from temporal_hypo.generation.templates import load_groups


def _make_index(reports: list[tuple]) -> CorpusIndex:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE reports (
            report_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            vaers_id   INTEGER UNIQUE NOT NULL,
            vaccine    TEXT NOT NULL,
            narrative  TEXT NOT NULL,
            num_groups INTEGER NOT NULL
        );
        CREATE TABLE level_terms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL, level_index INTEGER NOT NULL, term TEXT NOT NULL
        );
        """
    )
    for vaers_id, vaccine, levels in reports:
        conn.execute(
            "INSERT INTO reports (vaers_id, vaccine, narrative, num_groups) VALUES (?,?,?,?)",
            (vaers_id, vaccine, "n", len(levels)),
        )
        rid = conn.execute("SELECT report_id FROM reports WHERE vaers_id=?",
                           (vaers_id,)).fetchone()[0]
        for li, terms in enumerate(levels):
            for term in terms:
                conn.execute(
                    "INSERT INTO level_terms (report_id, level_index, term) VALUES (?,?,?)",
                    (rid, li, term),
                )
    conn.commit()
    return CorpusIndex.load(conn)


# 20 Pfizer: 16 with Headache before Fatigue before Pyrexia, 4 with Fatigue first.
# 20 Moderna: 11 Headache-first, 9 Fatigue-first.
def _corpus() -> CorpusIndex:
    reports = []
    vid = 1
    for _ in range(16):
        reports.append((vid, "Pfizer", [["Headache"], ["Fatigue"], ["Pyrexia"]])); vid += 1
    for _ in range(4):
        reports.append((vid, "Pfizer", [["Fatigue"], ["Headache"], ["Pyrexia"]])); vid += 1
    for _ in range(11):
        reports.append((vid, "Moderna", [["Headache"], ["Fatigue"], ["Pyrexia"]])); vid += 1
    for _ in range(9):
        reports.append((vid, "Moderna", [["Fatigue"], ["Headache"], ["Pyrexia"]])); vid += 1
    return _make_index(reports)


@pytest.fixture
def idx():
    return _corpus()


# ---- single-proportion (binomial) ----------------------------------------

def test_pv1_dir_bool(idx):
    r = compute_answer(idx, "P-V1", ("Headache", "Fatigue"), vaccines=("Pfizer",))
    assert r.verdict == "supported"
    assert r.n == 20 and r.k == 16 and abs(r.proportion - 0.8) < 1e-9
    assert r.sig_test == "binom_exact"
    assert r.significant is True and r.p_value < 0.05
    assert r.options is None and r.gold_answer is None   # BOOL has no choice key
    assert r.ci is not None and r.effect_size is not None


def test_pv3_dir_choice_answer_key(idx):
    r = compute_answer(idx, "P-V3", ("Headache", "Fatigue"), vaccines=("Pfizer",))
    assert r.answer_type == "CHOICE"
    assert r.options == ["Headache", "Fatigue"]
    assert r.gold_answer == "Headache"          # the earlier event, the correct pick


def test_prop_shares_binomial_significance(idx):
    bool_r = compute_answer(idx, "P-V1", ("Headache", "Fatigue"), vaccines=("Pfizer",))
    prop_r = compute_answer(idx, "P-V2", ("Headache", "Fatigue"), vaccines=("Pfizer",))
    # same underlying proportion -> same test result
    assert prop_r.p_value == bool_r.p_value


# ---- two-proportion (Fisher) ---------------------------------------------

def test_multi_dir_choice_picks_higher_vaccine(idx):
    r = compute_answer(idx, "P-M2", ("Headache", "Fatigue"),
                       vaccines=("Pfizer", "Moderna"))
    assert r.sig_test == "fisher_exact"
    assert r.options == ["Pfizer", "Moderna"]
    assert r.gold_answer == "Pfizer"            # 0.80 > 0.55
    assert abs(r.proportion - 0.8) < 1e-9 and abs(r.proportion2 - 0.55) < 1e-9


def test_multi_differ_verdict(idx):
    r = compute_answer(idx, "P-M1", ("Headache", "Fatigue"),
                       vaccines=("Pfizer", "Moderna"))
    # |0.80 - 0.55| = 0.25 > 0.10 -> differ supported
    assert r.verdict == "supported"


# ---- distribution (chi-square GoF) ---------------------------------------

def test_first_choice_winner(idx):
    r = compute_answer(idx, "F-V1", ("Headache", "Fatigue", "Pyrexia"),
                       vaccines=("Pfizer",))
    assert r.sig_test.startswith("multinomial_gof")   # exact or chi-square
    assert r.options == ["Headache", "Fatigue", "Pyrexia"]
    assert r.gold_answer == "Headache"          # first in 16/20


# ---- refuted CHOICE still carries the correct gold answer -----------------

def test_refuted_choice_keeps_correct_gold_answer(idx):
    groups = load_groups()
    core = cores._build_vaccine_core(
        idx, groups["F-V1"], "first_choice", "Pfizer",
        idx.cohort("Pfizer"), ("Headache", "Fatigue", "Pyrexia"),
    )
    facts = cores.realize(core, "refuted")
    recs = build_records(facts, groups["F-V1"], seq=0)
    # the text names a wrong option, but the answer key stays correct
    assert facts.events_assigned[0] != "Headache"
    assert all(r["gold_answer"] == "Headache" for r in recs)
    assert all(r["options"] == ["Headache", "Fatigue", "Pyrexia"] for r in recs)


# ---- insufficient cohort --------------------------------------------------

def test_insufficient_below_min_n():
    # only 5 ordered reports -> below the n>=10 threshold
    idx = _make_index([(i, "Pfizer", [["A"], ["B"]]) for i in range(5)])
    r = compute_answer(idx, "P-V1", ("A", "B"), vaccines=("Pfizer",))
    assert r.computable is False
    assert r.verdict == "insufficient"
    assert r.p_value is None and r.significant is None


# ---- generalization: same code path, brand-new corpus --------------------

def test_generalizes_to_new_corpus_without_code_change():
    # a different dataset in the same format computes with no special-casing
    idx = _make_index(
        [(i, "Janssen", [["X"], ["Y"]]) for i in range(18)]
        + [(100 + i, "Janssen", [["Y"], ["X"]]) for i in range(2)]
    )
    r = compute_answer(idx, "P-V1", ("X", "Y"), vaccines=("Janssen",))
    assert r.verdict == "supported" and r.n == 20 and r.k == 18
    assert r.significant is True
