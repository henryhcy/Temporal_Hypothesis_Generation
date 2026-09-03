"""End-to-end tests of the wired pipeline (rules -> compiler -> oracle -> evaluate).

The unit suites pin each stage against the generator; these pin the WIRING: the
prediction-row schema, the option shuffle happening before the parser, the
first/last candidate-set canonicalisation in the scorer, and the B0 contract
(the oracle pipeline reproduces the gold verdict).
"""

from __future__ import annotations

import json
import random

import pytest

from temporal_hypo.framework import baselines
from temporal_hypo.framework.evaluate import (
    canonical_terms, canonical_what_key, evaluate, shuffle_options,
)
from temporal_hypo.framework.extract.rules import RulesExtractor, vocabulary_from_db
from temporal_hypo.framework.pipeline import (
    CompilerRetriever, Pipeline, PREDICTION_FIELDS, blind_row, instance_id_of,
)
from temporal_hypo.framework.pipeline import shuffle_options as pipeline_shuffle
from temporal_hypo.framework.sql.build_eval_db import open_eval_db
from temporal_hypo.framework.sql.executor import ReadOnlyExecutor
from tests.framework.conftest import RELEASE_DIR, RELEASE_STEM, needs_release


class _Release:
    """Minimal duck-typed release for the scorer."""

    def __init__(self, questions, answers):
        self.questions = questions
        self.answers = answers

    def answer_for(self, hid):
        return self.answers[instance_id_of(hid)]


def _load_release_rows(groups, max_per_group=6, predicate=None, include_mirrors=False):
    """A small release slice: up to ``max_per_group`` instances per group that pass
    ``predicate``; with ``include_mirrors`` every instance sharing a selected
    instance's ``derived_from_core_id`` (its mirror) is pulled in as well."""
    import gzip
    from pathlib import Path

    def _open(stem):
        p = RELEASE_DIR / f"{RELEASE_STEM}_{stem}.jsonl"
        if p.exists():
            return open(p, encoding="utf-8")
        return gzip.open(RELEASE_DIR / f"{RELEASE_STEM}_{stem}.jsonl.gz", "rt", encoding="utf-8")

    answers, count = {}, {}
    all_rows = []
    with _open("answers") as fh:
        for line in fh:
            a = json.loads(line)
            a.pop("test_verdict", None)
            if include_mirrors:
                all_rows.append(a)
            g = a["group_id"]
            if predicate is not None and not predicate(a):
                continue
            if g in groups and count.get(g, 0) < max_per_group:
                answers[a["instance_id"]] = a
                count[g] = count.get(g, 0) + 1
    if include_mirrors:
        # fact_id is group-independent and shared by mirrors AND answer-format twins
        facts = {a["fact_id"] for a in answers.values()}
        for a in all_rows:
            if a["fact_id"] in facts:
                answers.setdefault(a["instance_id"], a)
    questions = []
    with _open("questions") as fh:
        for line in fh:
            q = json.loads(line)
            if instance_id_of(q["hypothesis_id"]) in answers:
                questions.append(q)
    return _Release(questions, answers)


def test_canonical_terms_only_touches_candidate_set_modes():
    assert canonical_terms("first_choice", ("A", "C", "B")) == ("A", "B", "C")
    assert canonical_terms("rep_last_choice", ("Z", "Y", "X")) == ("Z", "X", "Y")
    assert canonical_terms("seq_bool", ("A", "C", "B")) == ("A", "C", "B")
    assert canonical_terms("dir_bool", ("B", "A")) == ("B", "A")
    assert canonical_terms("first_bool", ("A", None, "B")) == ("A", "B", None)


def test_pipeline_shuffle_is_evaluate_shuffle():
    row = {"hypothesis_id": "F-R1-0001-media-claim", "options": ["x", "y", "z"]}
    for seed in (0, 1, 7):
        assert pipeline_shuffle(row, seed)["options"] == shuffle_options(row["options"], row["hypothesis_id"], seed)
    assert pipeline_shuffle({"hypothesis_id": "P-V1-0000-original-question", "options": None}, 0)["options"] is None


def test_blind_row_hides_group():
    row = {"hypothesis_id": "P-V1-0000-original-question", "group_id": "P-V1", "text": "t"}
    b = blind_row(row)
    assert "group_id" not in b and b["hypothesis_id"] == "masked" and b["text"] == "t"


@pytest.fixture(scope="module")
def eval_exec(tmp_path_factory):
    from tests.framework.conftest import CORPUS
    from tests.generation.conftest import make_db
    from temporal_hypo.framework.sql.build_eval_db import build_eval_db

    dst = tmp_path_factory.mktemp("pipe") / "eval.db"
    build_eval_db(make_db(CORPUS), dst)
    return ReadOnlyExecutor(dst), dst


def test_prediction_row_schema_on_synthetic_corpus(eval_exec):
    executor, dst = eval_exec
    vocab = vocabulary_from_db(open_eval_db(dst))
    pipe = Pipeline(name="oracle", extractor=RulesExtractor(vocabulary=vocab),
                    retriever=CompilerRetriever(executor), procedure_mode="gold")
    row = {"hypothesis_id": "P-V1-0000-original-question", "group_id": "P-V1", "level": "vaccine",
           "answer_type": "BOOL", "register": "original", "format": "question",
           "text": "Does Headache typically occur before Fatigue after Pfizer?", "options": None,
           "cohort": {"level": "vaccine", "vaccines": ["Pfizer"], "report_id": None}}
    out = pipe.run_record(row)
    assert tuple(out) == PREDICTION_FIELDS
    assert out["error"] is None and out["claim"]["mode"] == "dir_bool"
    arm = out["retrieval"]["arms"][0]
    # Pfizer H/F in the conftest corpus: 7 before, 2 after, 3 co-exist (first-mention on 1015)
    assert (arm["n"], arm["k"]) == (9, 7) and sorted(arm["excluded_ids"]) == [1009, 1010, 1011]
    assert out["prediction"]["response"] == "insufficient" and out["prediction"]["subtype"] == "sparse"


@needs_release
def test_oracle_reproduces_gold_and_first_last_canonicalisation():
    """B0 on a release slice incl. the lossy first/last CHOICE claims, with shuffled options."""
    from pathlib import Path

    eval_db = Path(__file__).resolve().parents[2] / "data" / "medtempo_eval.db"
    if not eval_db.exists():
        pytest.skip("data/medtempo_eval.db not built")
    release = _load_release_rows({"F-V1", "F-V2", "F-R1", "F-R2", "P-V1", "P-M2", "C-V3", "P-V4"})
    executor = ReadOnlyExecutor(eval_db)
    vocab = vocabulary_from_db(open_eval_db(eval_db))
    pipe = Pipeline(name="oracle", extractor=RulesExtractor(vocabulary=vocab),
                    retriever=CompilerRetriever(executor), procedure_mode="gold",
                    options_seed=3)
    rows = pipe.run(release.questions)
    # the shuffle really changed the presented order for some CHOICE rows
    changed = sum(1 for q in release.questions if q["options"]
                  and shuffle_options(q["options"], q["hypothesis_id"], 3) != q["options"])
    assert changed > 0
    m = evaluate(rows, release, options_seed=3, min_group_size=1, bootstrap=10)
    und = m["n"]["underdetermined"]
    scored = m["n"]["records"] - und
    assert m["verdict"]["accuracy"] == 1.0, m["verdict"]
    assert m["extraction"]["claim_em"] == 1.0, m["extraction"]
    assert m["retrieval"]["denominator"]["em"] == 1.0, m["retrieval"]
    assert m["retrieval"]["report"]["report_hit"] == 1.0, m["retrieval"]["report"]
    assert m["choice"]["answer_acc"] == 1.0, m["choice"]
    assert und == sum(1 for q in release.questions
                      if q["group_id"] == "C-V3" and q["register"] in ("research", "clinical"))
    assert scored > 0


def test_trivial_baselines_shape():
    recs = [{"hypothesis_id": "P-R2-0000-original-question", "group_id": "P-R2", "register": "original",
             "format": "question", "options": ["a", "b"]}]
    answers = {"P-R2-0000": {"gold_verdict": "supported"}}
    for rows in (baselines.majority_per_group(recs, answers), baselines.always_insufficient(recs),
                 baselines.options_index(recs, 0), baselines.options_index(recs, 2)):
        assert tuple(rows[0]) == PREDICTION_FIELDS
    assert baselines.options_index(recs, 0)[0]["prediction"]["answer"] == "a"
    assert baselines.options_index(recs, 2)[0]["prediction"]["answer"] is None


@needs_release
def test_scorer_twins_and_not_locatable_fpr_on_oracle():
    """Regression for two scorer definitions found on the B0 run.

    - Twin consistency must key on the ASSERTED claim (events + negation + cohort
      order): negation-oriented mirrors (C-V1/C-V2/C-V3) and vaccine-swap mirrors
      (P-M2) share fact_id and events but legitimately carry opposite verdicts.
    - The not_locatable false-positive rate is PER ARM: a two-arm claim with one
      empty gold arm has a legitimately non-empty other arm.
    The oracle reproduces gold exactly, so both must read 1.0 / 0.0 on it.
    """
    from pathlib import Path

    eval_db = Path(__file__).resolve().parents[2] / "data" / "medtempo_eval.db"
    if not eval_db.exists():
        pytest.skip("data/medtempo_eval.db not built")
    def _one_arm_empty(a):
        ev = a["evidence_ids"]
        return ("cohort_1" in ev and a["insufficient_subtype"] == "not_locatable"
                and bool(ev["cohort_1"]["denominator"]) != bool(ev["cohort_2"]["denominator"]))

    # negated C-* rows and vaccine-swapped P-M2 rows (plus their mirrors, which share
    # fact_id AND events), and one-arm-empty not_locatable rows from P-V2/P-V4
    release = _load_release_rows(
        {"C-V1", "C-V2", "C-V3", "P-M2", "P-V4", "P-V2", "P-V1"}, max_per_group=12, include_mirrors=True,
        predicate=lambda a: ((a["group_id"] in ("C-V1", "C-V2", "C-V3") and a["negated"])
                             or (a["group_id"] == "P-M2" and a["flip_kind"] == "vaccine_swap")
                             or a["group_id"] == "P-V1"          # P-V3 twins arrive via fact_id
                             or _one_arm_empty(a)))
    assert any(a["group_id"] == "P-V3" for a in release.answers.values()), "no P-V1/P-V3 twins pulled"
    executor = ReadOnlyExecutor(eval_db)
    vocab = vocabulary_from_db(open_eval_db(eval_db))
    pipe = Pipeline(name="oracle", extractor=RulesExtractor(vocabulary=vocab),
                    retriever=CompilerRetriever(executor), procedure_mode="gold")
    rows = pipe.run(release.questions)
    m = evaluate(rows, release, min_group_size=1, bootstrap=5)
    # the slice really contains negated mirrors and one-arm-empty not_locatable rows
    assert any(a["negated"] for a in release.answers.values())
    one_arm_empty = [a for a in release.answers.values()
                     if a["insufficient_subtype"] == "not_locatable"
                     and "cohort_1" in a["evidence_ids"]
                     and bool(a["evidence_ids"]["cohort_1"]["denominator"]) != bool(a["evidence_ids"]["cohort_2"]["denominator"])]
    assert one_arm_empty, "slice lost its one-arm-empty not_locatable rows"
    assert m["verdict"]["accuracy"] == 1.0
    assert m["consistency"]["twins"]["n_groups"] > 0, m["consistency"]["twins"]
    assert m["consistency"]["twins"]["consistent_rate"] == 1.0, m["consistency"]["twins"]
    assert m["retrieval"]["not_locatable_fpr"]["rate"] == 0.0, m["retrieval"]["not_locatable_fpr"]
