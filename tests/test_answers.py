"""Tests for the public answer-retrieve pipeline (temporal_hypo.core.answers)."""

from __future__ import annotations

import sqlite3

import pytest

from temporal_hypo.core import verdict as V
from temporal_hypo.core.answers import (
    answer_key,
    compute_answer,
    core_decision,
    core_significance,
)
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
    assert r.sig_test == "modal_runner"   # was GOF-vs-uniform pre-08-11
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


# ---- three-decision labeling (decisions.md 2026-07-28) -------------------

def test_claim_direction_drives_the_label_not_the_observed_direction(idx):
    # Headache precedes Fatigue in 16/20 -> the claim in that direction is
    # supported; the SAME data refutes the reversed claim (4/20). Both verdicts
    # come from significance, in opposite tails.
    fwd = compute_answer(idx, "P-V1", ("Headache", "Fatigue"), vaccines=("Pfizer",))
    rev = compute_answer(idx, "P-V1", ("Fatigue", "Headache"), vaccines=("Pfizer",))
    assert fwd.test_verdict == "supported" and fwd.p_claim < 0.05
    assert rev.test_verdict == "refuted" and rev.p_opposite < 0.05
    assert rev.p_claim > 0.05          # the claim's own tail is nowhere near
    assert fwd.insufficient_subtype is None and rev.insufficient_subtype is None


def test_weak_effect_is_insufficient_not_refuted(idx):
    # Moderna: 11/20 Headache-first -- above 0.5 but nowhere near significant.
    r = compute_answer(idx, "P-V1", ("Headache", "Fatigue"), vaccines=("Moderna",))
    assert r.verdict == "supported"          # legacy point-estimate rule
    assert r.test_verdict == "insufficient"  # three-decision rule
    assert r.insufficient_subtype == V.UNDERPOWERED


def test_sparse_is_reachable_once_the_helpers_report_sub_floor_n():
    # 2026-08-11 step B: the corpus helpers no longer drop n below their old
    # private floor, so a core that IS conditioned but thinly conditioned lands in
    # `sparse` instead of an unnamed bucket. 15 clears the pairwise floor of 10...
    idx = _make_index([(i, "Pfizer", [["A"], ["B"]]) for i in range(15)])
    r = compute_answer(idx, "P-V1", ("A", "B"), vaccines=("Pfizer",))
    assert r.n == 15
    assert r.test_verdict == "supported"

    # ...and 6 does not, so it is SPARSE and carries its denominator.
    thin = _make_index([(i, "Pfizer", [["A"], ["B"]]) for i in range(6)])
    r2 = compute_answer(thin, "P-V1", ("A", "B"), vaccines=("Pfizer",))
    assert r2.n == 6
    assert r2.test_verdict == "insufficient"
    assert r2.insufficient_subtype == V.SPARSE


def test_not_locatable_when_the_events_never_co_occur():
    # n = 0: B is absent from every report, so there is nothing to condition on.
    # This is the sub-type that tests whether a framework says "insufficient"
    # instead of inventing a relationship.
    idx = _make_index([(i, "Pfizer", [["A"], ["Z"]]) for i in range(20)])
    r = compute_answer(idx, "P-V1", ("A", "B"), vaccines=("Pfizer",))
    assert r.n == 0
    assert r.test_verdict == "insufficient"
    assert r.insufficient_subtype == V.NOT_LOCATABLE


def test_argmax_choice_groups_are_directional_via_modal_vs_runner_up():
    # 2026-08-11: F-V1 was tested GOF-vs-uniform, which has no direction, so it
    # could only ever be tagged non_directional. It now runs modal-vs-runner-up
    # on the named candidate against its nearest rival, which HAS a direction.
    # H is first in 30/40 and F in 10/40 -> H beats its rival decisively.
    reports = ([(i, "Pfizer", [["H"], ["F"], ["P"]]) for i in range(30)]
               + [(100 + i, "Pfizer", [["F"], ["H"], ["P"]]) for i in range(10)])
    idx = _make_index(reports)
    r = compute_answer(idx, "F-V1", ("H", "F", "P"), vaccines=("Pfizer",))
    assert r.n == 40                                  # clears the first/last floor
    assert r.sig_test == "modal_runner"
    assert r.p_claim is not None and r.p_opposite is not None
    assert r.test_verdict == "supported"
    assert r.insufficient_subtype is None


def test_argmax_choice_is_insufficient_when_the_mode_barely_leads():
    # the case that motivated the change: an omnibus GOF is significant because
    # one candidate is RARE, while the gold answer leads its rival by a hair.
    # 20 H-first, 19 F-first, 1 P-first -> not uniform at all, but H vs F is a
    # coin flip, so the claim "H is most commonly first" must NOT be supported.
    reports = ([(i, "Pfizer", [["H"], ["F"], ["P"]]) for i in range(20)]
               + [(100 + i, "Pfizer", [["F"], ["H"], ["P"]]) for i in range(19)]
               + [(200, "Pfizer", [["P"], ["H"], ["F"]])])
    idx = _make_index(reports)
    r = compute_answer(idx, "F-V1", ("H", "F", "P"), vaccines=("Pfizer",))
    assert r.n == 40
    assert r.gold_answer == "H"                  # still the modal candidate
    assert r.test_verdict == "insufficient"      # but the data does not settle it
    assert r.insufficient_subtype == V.UNDERPOWERED


def test_argmax_bool_refutes_when_the_claim_names_a_non_modal_event():
    # F-V3 (first_bool) is modal-vs-runner-up. Naming the true mode is
    # supported; naming its beaten competitor is refuted -- that is how a
    # refuted instance is built from a real core.
    reports = ([(i, "Pfizer", [["H"], ["F"], ["P"]]) for i in range(30)]
               + [(100 + i, "Pfizer", [["F"], ["H"], ["P"]]) for i in range(10)])
    idx = _make_index(reports)
    groups = load_groups()
    core = cores._build_vaccine_core(idx, groups["F-V3"], "first_bool", "Pfizer",
                                     idx.cohort("Pfizer"), ("H", "F", "P"))
    assert core.n == 40 and core.extra["winner"] == "H"
    assert core_decision(core).verdict == "supported"           # names the mode
    assert core_decision(core, named="F").verdict == "refuted"  # names the loser
    s = core_significance(core, named="F")
    assert s.details["top"] == 10 and s.details["runner"] == 30


def test_report_level_claims_stay_deterministic(idx):
    r = compute_answer(idx, "P-R1", ("Headache", "Fatigue"), report_id=1)
    assert r.p_value is None and r.p_claim is None
    assert r.test_verdict == r.verdict          # exact, no test involved
    assert r.insufficient_subtype == V.DETERMINISTIC


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


# ---- the emit path and the labeler must agree (decisions.md 2026-08-11) ----

def test_emitted_gold_verdict_matches_the_three_decision_labeler(idx):
    """`realize` stamps the shipped label; `core_decision` is the labeler.

    These are separate code paths (generation.cores vs core.answers), so this
    pins them together: for a decisive core the realized polarity IS the label,
    and a non-decisive core can only ever emit `insufficient`.
    """
    groups = load_groups()
    decisive = cores._build_vaccine_core(          # 16/20 Headache-first
        idx, groups["P-V1"], "dir_bool", "Pfizer",
        idx.cohort("Pfizer"), ("Headache", "Fatigue"))
    dec = core_decision(decisive)
    assert dec.decisive
    for polarity in ("supported", "refuted"):
        assert polarity in cores.feasible_polarities(decisive)
        assert cores.realize(decisive, polarity).gold_verdict == polarity

    # Moderna is 11/20 -- the legacy rule calls it supported, the labeler does not
    weak = cores._build_vaccine_core(
        idx, groups["P-V1"], "dir_bool", "Moderna",
        idx.cohort("Moderna"), ("Headache", "Fatigue"))
    assert not core_decision(weak).decisive
    assert weak.natural_verdict == "supported"        # the retired rule
    assert cores.feasible_polarities(weak) == {"insufficient"}
    assert cores.realize(weak, "supported").gold_verdict == "insufficient"


def test_effect_size_is_measured_on_the_tested_quantity(idx):
    """2026-08-11: the argmax modes test named-vs-runner-up against 0.5, so the
    effect size uses that 2-cell proportion -- not the retired GOF-vs-uniform
    references (1/6 over orderings, 1/3 over candidates)."""
    from temporal_hypo.core.answers import _two_cell_proportion, _null_ref
    from temporal_hypo.generation.confidence import cohens_h
    groups = load_groups()
    core = cores._build_vaccine_core(
        idx, groups["F-V1"], "first_choice", "Pfizer",
        idx.cohort("Pfizer"), ("Headache", "Fatigue", "Pyrexia"))
    r = compute_answer(idx, "F-V1", ("Headache", "Fatigue", "Pyrexia"),
                       vaccines=("Pfizer",))
    two_cell = _two_cell_proportion(core)
    assert two_cell is not None
    # the reported proportion is the share of the WHOLE denominator...
    assert abs(r.proportion - 16 / 20) < 1e-9
    # ...while the effect size is on named-vs-runner-up against 0.5
    assert abs(r.effect_size - cohens_h(two_cell, 0.5)) < 1e-9
    assert _null_ref("first_choice") == 0.5


# ---- released statistics describe the INSTANCE's claim, not the core's -----

def test_oriented_statistics_follow_the_asserted_claim(idx):
    """A refuted realization asserts the mirror of the canonical claim, so its
    tails must be the mirror too. Emitting canonical tails beside an oriented
    verdict made 20% of cohort records self-contradictory (decisions.md 08-11)."""
    from temporal_hypo.core.answers import oriented_significance
    groups = load_groups()
    core = cores._build_vaccine_core(
        idx, groups["P-V1"], "dir_bool", "Pfizer",
        idx.cohort("Pfizer"), ("Headache", "Fatigue"))       # 16/20 -> decisive

    sup = cores.realize(core, "supported")
    ref = cores.realize(core, "refuted")
    s_sup = oriented_significance(sup)
    s_ref = oriented_significance(ref)

    # the refuted instance flipped the event order, so the tails swap exactly
    assert ref.flip_kind == "direction"
    assert s_ref.p_claim == s_sup.p_opposite
    assert s_ref.p_opposite == s_sup.p_claim
    # and each instance's own verdict follows its own claim tail
    assert s_sup.decision.verdict == "supported" and s_sup.p_claim < 0.05
    assert s_ref.decision.verdict == "refuted" and s_ref.p_opposite < 0.05


def test_insufficient_argmax_instance_names_the_modal_cell(idx):
    """_realize_insufficient used core.events verbatim, which for an argmax mode
    names whichever candidate sorts first alphabetically -- a different claim the
    data can decisively refute. It must name the mode, like the supported branch."""
    from temporal_hypo.core.answers import oriented_significance
    groups = load_groups()
    # Moderna is the weak cohort (11 Headache-first vs 9 Fatigue-first), so this
    # core is NOT decisive and `insufficient` is the only feasible polarity.
    core = cores._build_vaccine_core(
        idx, groups["F-V1"], "first_choice", "Moderna",
        idx.cohort("Moderna"), ("Headache", "Fatigue", "Pyrexia"))
    assert cores.feasible_polarities(core) == {"insufficient"}
    facts = cores.realize(core, "insufficient")
    assert facts.events_assigned[0] == core.extra["winner"]
    # so the asserted claim's verdict agrees with the shipped label
    assert oriented_significance(facts).decision.verdict == facts.gold_verdict ==         "insufficient"


# ---- evidence report ids (2026-08-11) --------------------------------------

def test_evidence_ids_reconstruct_the_counts_they_came_from(idx):
    """The benchmark ships report ids, not narratives, so the ids must be exactly
    the reports the statistic ran over -- otherwise a scorer cannot audit a label."""
    from temporal_hypo.generation.evidence import evidence_ids
    groups = load_groups()
    core = cores._build_vaccine_core(
        idx, groups["P-V1"], "dir_bool", "Pfizer",
        idx.cohort("Pfizer"), ("Headache", "Fatigue"))

    for polarity in ("supported", "refuted"):
        facts = cores.realize(core, polarity)
        ev = evidence_ids(idx, facts)
        assert len(ev["denominator"]) == facts.gold_n
        assert len(ev["numerator"]) == facts.gold_k
        # the ids are oriented: a refuted instance's numerator is the complement
        assert set(ev["numerator"]) <= set(ev["denominator"])


def test_excluded_ids_are_present_but_unusable(idx):
    """`excluded` is the report-level witness for "the events are there but this
    report cannot speak to the claim" -- a co-exist pair for a precedes claim."""
    from temporal_hypo.generation.evidence import evidence_ids
    groups = load_groups()
    # every report has Headache and Fatigue at DISTINCT levels, so nothing excluded
    core = cores._build_vaccine_core(
        idx, groups["P-V1"], "dir_bool", "Pfizer",
        idx.cohort("Pfizer"), ("Headache", "Fatigue"))
    ev = evidence_ids(idx, cores.realize(core, "supported"))
    assert ev["excluded"] == []

    # now a cohort where they always co-occur: denominator empty, all excluded
    tied = _make_index([(i, "Pfizer", [["A", "B"]]) for i in range(12)])
    tcore = cores._build_vaccine_core(
        tied, groups["P-V1"], "dir_bool", "Pfizer",
        tied.cohort("Pfizer"), ("A", "B"))
    tev = evidence_ids(tied, cores.realize(tcore, "insufficient"))
    assert tev["denominator"] == [] and len(tev["excluded"]) == 12


def test_questions_file_carries_no_gold_fields():
    from temporal_hypo.generation.instances import INPUT_FIELDS
    for leaked in ("gold_verdict", "gold_n", "gold_k", "evidence_ids",
                   "p_claim", "p_opposite", "gold_answer", "test_verdict"):
        assert leaked not in INPUT_FIELDS
