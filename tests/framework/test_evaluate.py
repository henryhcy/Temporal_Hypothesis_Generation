"""Hand-checkable tests for ``framework.evaluate``.

A tiny synthetic gold (seven instances: a mirror pair, a fact twin, a not_locatable
row with empty evidence, a report-tier BOOL row, a report-tier CHOICE row, a
negated row, and an underdetermined C-V3 research row) and sixteen hand-crafted
prediction rows -- perfect, wrong at S1 (parse and procedure), wrong at S2
(co-exist leaked into the denominator; a dropped numerator), wrong at S3, and a
lucky one -- with every metric asserted as an exact fraction.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from temporal_hypo.framework.claim_schema import EventSlot, build_claim, from_gold
from temporal_hypo.framework.evaluate import (
    STAGES, classify_test, evaluate, set_prf, shuffle_options, write_report,
)

# ---------------------------------------------------------------------------
# synthetic gold
# ---------------------------------------------------------------------------

DEN = list(range(1, 13))          # 12 reports with both events, ordered
NUM_HF = list(range(1, 11))       # Headache before Fatigue in 10 of them
NUM_FH = [11, 12]                 # Fatigue before Headache in 2
EXC = [101, 102]                  # co-exist -> excluded from a precedes denominator
P_HI, P_LO = 0.019287, 0.996826   # P(X>=10 | 12, .5) and P(X<=10 | 12, .5)


def _gold(iid, group, mode, events, *, verdict, family="pairwise", subtype=None,
          vaccines=(), report_id=None, negated=False, options=None, gold_answer=None,
          n=None, k=None, n2=None, k2=None, p_claim=None, p_opposite=None, sig_test=None,
          evidence=None, core_id=None, fact_id=None):
    level = "report" if report_id is not None else ("multi" if len(vaccines) == 2 else "vaccine")
    return {
        "instance_id": iid, "group_id": group, "level": level, "mode": mode, "family": family,
        "answer_type": "CHOICE" if options is not None else "BOOL",
        "gold_verdict": verdict, "insufficient_subtype": subtype, "negated": negated,
        "options": options, "gold_answer": gold_answer,
        "gold_n": n, "gold_k": k, "gold_n2": n2, "gold_k2": k2,
        "p_claim": p_claim, "p_opposite": p_opposite, "sig_test": sig_test,
        "evidence_ids": evidence,
        "cohort": {"level": level, "vaccines": list(vaccines), "report_id": report_id},
        "factual_core": {"events": list(events), "vaccines": list(vaccines), "report_id": report_id},
        "derived_from_core_id": core_id, "fact_id": fact_id,
        "test_verdict": "never-read",
    }


GOLD = {g["instance_id"]: g for g in [
    _gold("P-V1-0000", "P-V1", "dir_bool", ["Headache", "Fatigue"], verdict="supported",
          vaccines=["Pfizer"], n=12, k=10, p_claim=P_HI, p_opposite=P_LO, sig_test="binom_exact",
          evidence={"denominator": DEN, "numerator": NUM_HF, "excluded": EXC},
          core_id="P-V1|Pfizer|Headache+Fatigue", fact_id="precedes|Pfizer|Fatigue+Headache"),
    _gold("P-V1-0001", "P-V1", "dir_bool", ["Fatigue", "Headache"], verdict="refuted",
          vaccines=["Pfizer"], n=12, k=2, p_claim=P_LO, p_opposite=P_HI, sig_test="binom_exact",
          evidence={"denominator": DEN, "numerator": NUM_FH, "excluded": EXC},
          core_id="P-V1|Pfizer|Headache+Fatigue", fact_id="precedes|Pfizer|Fatigue+Headache"),
    _gold("P-V1-0002", "P-V1", "dir_bool", ["Rash", "Nausea"], verdict="insufficient",
          subtype="not_locatable", vaccines=["Pfizer"], n=0, k=0,
          evidence={"denominator": [], "numerator": [], "excluded": []},
          core_id="P-V1|Pfizer|Rash+Nausea", fact_id="precedes|Pfizer|Nausea+Rash"),
    # fact twin of P-V1-0000 (same fact_id, identical oriented events), CHOICE
    _gold("P-V3-0000", "P-V3", "dir_choice", ["Headache", "Fatigue"], verdict="supported",
          vaccines=["Pfizer"], options=["Headache", "Fatigue"], gold_answer="Headache",
          n=12, k=10, p_claim=P_HI, p_opposite=P_LO, sig_test="binom_exact",
          evidence={"denominator": DEN, "numerator": NUM_HF, "excluded": EXC},
          core_id="P-V3|Pfizer|Headache+Fatigue", fact_id="precedes|Pfizer|Fatigue+Headache"),
    _gold("P-R1-0000", "P-R1", "rep_dir_bool", ["Chest discomfort", "Back pain"], verdict="supported",
          report_id=956032, evidence={"report_id": 956032},
          core_id="P-R1|R956032|Chest discomfort+Back pain",
          fact_id="rep_precedes|R956032|Back pain+Chest discomfort"),
    _gold("F-R1-0000", "F-R1", "rep_first_choice", ["Dizziness", "Headache", "Eye pruritus"],
          verdict="supported", family="first_last", report_id=981131,
          options=["Dizziness", "Headache", "Eye pruritus"], gold_answer="Dizziness",
          evidence={"report_id": 981131}, core_id="F-R1|R981131|Dizziness+Headache+Eye pruritus",
          fact_id="rep_first|R981131|Dizziness+Eye pruritus+Headache"),
    _gold("C-V1-0000", "C-V1", "sym_bool_cooccurs", ["Arthralgia", "Myalgia"], verdict="refuted",
          vaccines=["Moderna"], negated=True, n=12, k=10, p_claim=P_LO, p_opposite=P_HI,
          sig_test="binom_exact",
          evidence={"denominator": list(range(201, 213)), "numerator": list(range(201, 211)),
                    "excluded": []},
          core_id="C-V1|Moderna|Arthralgia+Myalgia", fact_id="cooc_majority|Moderna|Arthralgia+Myalgia"),
    _gold("C-V3-0001", "C-V3", "cooc_modal_bool", ["Pyrexia", "Chills"], verdict="supported",
          vaccines=["Moderna"], n=20, k=12, p_claim=0.001, p_opposite=0.999, sig_test="modal_runner",
          evidence={"denominator": list(range(301, 321)), "numerator": list(range(301, 313)),
                    "excluded": []},
          core_id="C-V3|Moderna|Pyrexia+Chills", fact_id="cooc_modal|Moderna|Chills+Pyrexia"),
]}


class StubRelease:
    """Duck-typed stand-in for ``framework.io.Release`` (which another agent owns)."""

    def __init__(self, answers, questions=()):
        self.answers = answers
        self.questions = list(questions)

    def answer_for(self, hypothesis_id):
        return self.answers[hypothesis_id.rsplit("-", 2)[0]]


# ---------------------------------------------------------------------------
# prediction rows
# ---------------------------------------------------------------------------

def _arm(den, num, exc, label="arm"):
    return {"label": label, "n": len(den), "k": len(num), "denominator_ids": list(den),
            "numerator_ids": list(num), "excluded_ids": list(exc), "counts": {}}


def _row(hid, claim, *, arms=None, levels=None, response=None, subtype=None, p_claim=None,
         p_opposite=None, test=None, n=None, k=None, n2=None, k2=None, answer=None,
         retrieval=True, error=None):
    parts = hid.split("-")
    return {
        "hypothesis_id": hid, "instance_id": hid.rsplit("-", 2)[0], "group_id": "-".join(parts[:2]),
        "register": parts[3], "format": parts[4], "condition": "given-group",
        "pipeline": "handmade", "model": None,
        "claim": claim.to_dict() if claim is not None else None, "claim_problems": [],
        "retrieval": ({"ok": True, "arms": arms or [], "levels": levels, "queries": []}
                      if retrieval else None),
        "prediction": {"response": response, "verdict": response if response in ("supported", "refuted", "insufficient") else None,
                       "subtype": subtype, "p_claim": p_claim, "p_opposite": p_opposite,
                       "test": test, "n": n, "k": k, "n2": n2, "k2": k2, "answer": answer,
                       "gate_reason": None, "procedure_errors": []},
        "latency_ms": 1.0, "tokens": None, "error": error,
    }


def _claim(iid, **changes):
    c = from_gold(GOLD[iid])
    return replace(c, **changes) if changes else c


def build_rows():
    g = GOLD
    perfect_hf = dict(arms=[_arm(DEN, NUM_HF, EXC)], response="supported", p_claim=P_HI,
                      p_opposite=P_LO, test="binom_exact", n=12, k=10)
    rows = [
        # 1-2 perfect
        _row("P-V1-0000-original-question", _claim("P-V1-0000"), **perfect_hf),
        _row("P-V1-0000-original-claim", _claim("P-V1-0000"), **perfect_hf),
        # 3 S2-aggregation: numerator dropped two reports -> underpowered
        _row("P-V1-0000-research-question", _claim("P-V1-0000"),
             arms=[_arm(DEN, list(range(1, 9)), EXC)], response="insufficient", subtype="underpowered",
             p_claim=0.193848, p_opposite=0.927002, test="binom_exact", n=12, k=8),
        # 4 lucky: co-exist reports leaked into the denominator, verdict still right
        _row("P-V1-0001-original-question", _claim("P-V1-0001"),
             arms=[_arm(DEN + EXC, NUM_FH, [])], response="refuted",
             p_claim=0.99939, p_opposite=0.00647, test="binom_exact", n=14, k=2),
        # 5 S3-test: tails swapped (synonym test name)
        _row("P-V1-0001-original-claim", _claim("P-V1-0001"),
             arms=[_arm(DEN, NUM_FH, EXC)], response="supported",
             p_claim=P_HI, p_opposite=P_LO, test="binomial", n=12, k=2),
        # 6 S1-parse: events swapped; fabricated denominator on a not_locatable gold
        _row("P-V1-0002-original-question",
             _claim("P-V1-0002", events=(EventSlot("A", "Nausea"), EventSlot("B", "Rash"))),
             arms=[_arm([1, 2, 3], [1, 2], [])], response="supported",
             p_claim=0.5, p_opposite=0.875, test="binom_exact", n=3, k=2),
        # 7 correct not_locatable (0/0 convention)
        _row("P-V1-0002-original-claim", _claim("P-V1-0002"),
             arms=[_arm([], [], [])], response="insufficient", subtype="not_locatable", n=0, k=0),
        # 8 twin, CHOICE, perfect (options presented shuffled)
        _row("P-V3-0000-original-question", _claim("P-V3-0000", options=("Fatigue", "Headache")),
             answer="Headache", **perfect_hf),
        # 9 S1-procedure (gate): floor 20 -> sparse
        _row("P-V3-0000-original-claim",
             _claim("P-V3-0000", options=("Fatigue", "Headache")).with_procedure(
                 replace(from_gold(g["P-V3-0000"]).procedure, min_n_floor=20)),
             arms=[_arm(DEN, NUM_HF, EXC)], response="insufficient", subtype="sparse", n=12, k=10),
        # 10 report tier perfect
        _row("P-R1-0000-original-question", _claim("P-R1-0000"),
             levels={"Chest discomfort": 0, "Back pain": 1}, response="supported"),
        # 11 report tier: one event missing from the levels -> wrong
        _row("P-R1-0000-original-claim", _claim("P-R1-0000"),
             levels={"Chest discomfort": 0}, response="refuted"),
        # 12, 15 report CHOICE perfect (options presented shuffled)
        _row("F-R1-0000-original-question",
             _claim("F-R1-0000", options=("Headache", "Dizziness", "Eye pruritus")),
             levels={"Dizziness": 0, "Headache": 1, "Eye pruritus": 2}, response="supported",
             answer="Dizziness"),
        _row("F-R1-0000-original-claim",
             _claim("F-R1-0000", options=("Headache", "Dizziness", "Eye pruritus")),
             levels={"Dizziness": 0, "Headache": 1, "Eye pruritus": 2}, response="supported",
             answer="Dizziness"),
        # 13 negated perfect
        _row("C-V1-0000-original-question", _claim("C-V1-0000"),
             arms=[_arm(range(201, 213), range(201, 211), [])], response="refuted",
             p_claim=P_LO, p_opposite=P_HI, test="binom_exact", n=12, k=10),
        # 14 S1-parse: negation missed
        _row("C-V1-0000-original-claim",
             build_claim("sym_bool_cooccurs", ["Arthralgia", "Myalgia"], g["C-V1-0000"]["cohort"],
                         negated=False, source="rules"),
             arms=[_arm(range(201, 213), range(201, 211), [])], response="supported",
             p_claim=P_HI, p_opposite=P_LO, test="binom_exact", n=12, k=10),
        # 16 underdetermined input (C-V3 research never names the events)
        _row("C-V3-0001-research-claim",
             build_claim("cooc_modal_bool", [None, None], g["C-V3-0001"]["cohort"], source="rules"),
             retrieval=False, response="underdetermined"),
    ]
    return rows


QUESTIONS = [{"hypothesis_id": r["hypothesis_id"], "text": f"TEXT<{r['hypothesis_id']}>"}
             for r in build_rows()]


@pytest.fixture(scope="module")
def release():
    return StubRelease(GOLD, QUESTIONS)


@pytest.fixture(scope="module")
def rows():
    return build_rows()


@pytest.fixture(scope="module")
def metrics(rows, release):
    return evaluate(rows, release, min_group_size=2, bootstrap=50, seed=0)


A = pytest.approx


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------

def test_set_prf_zero_zero_convention():
    assert set_prf([], []) == {"precision": 1.0, "recall": 1.0, "f1": 1.0, "em": 1.0}
    assert set_prf([1, 2], []) == {"precision": 0.0, "recall": 0.0, "f1": 0.0, "em": 0.0}
    assert set_prf([], [1, 2]) == {"precision": 0.0, "recall": 0.0, "f1": 0.0, "em": 0.0}
    r = set_prf([1, 2, 3, 4], [1, 2, 5])
    assert r["precision"] == A(0.5) and r["recall"] == A(2 / 3)
    assert r["f1"] == A(2 * 0.5 * (2 / 3) / (0.5 + 2 / 3)) and r["em"] == 0.0
    assert set_prf([2, 1], [1, 2])["em"] == 1.0


def test_classify_test():
    assert classify_test("binom_exact", "binom_exact") == "gold"
    assert classify_test("Binomial", "binom_exact") == "synonym"
    assert classify_test("hypergeometric", "fisher_exact") == "synonym"
    assert classify_test("fisher_exact", "binom_exact") == "other_exact"
    assert classify_test("chi-square", "fisher_exact") == "approximate"
    assert classify_test("two-proportion z test", "fisher_exact") == "approximate"
    assert classify_test(None, "fisher_exact") == "none"
    assert classify_test("mystery", "fisher_exact") == "unknown"


def test_shuffle_options_is_seeded_permutation():
    opts = ["a", "b", "c", "d", "e"]
    s1 = shuffle_options(opts, "X-0000-original-question", 0)
    assert sorted(s1) == opts
    assert s1 == shuffle_options(opts, "X-0000-original-question", 0)
    assert any(shuffle_options(opts, f"X-{i:04d}-original-question", 0) != opts for i in range(20))
    assert shuffle_options(None, "x", 0) is None


# ---------------------------------------------------------------------------
# headline counts and verdict metrics
# ---------------------------------------------------------------------------

def test_n_block(metrics):
    assert metrics["n"] == {"total_rows": 16, "records": 15, "instances": 7, "facts": 5,
                            "underdetermined": 1, "errors": 0, "no_response": 0}


def test_verdict_micro_and_per_class(metrics):
    v = metrics["verdict"]
    assert v["n"] == 15 and v["accuracy"] == A(9 / 15)
    pc = v["per_class"]
    assert pc["supported"]["gold_n"] == 9 and pc["supported"]["pred_n"] == 9
    assert pc["supported"]["f1"] == A(2 / 3)
    assert pc["refuted"]["precision"] == A(2 / 3) and pc["refuted"]["recall"] == A(0.5)
    assert pc["refuted"]["f1"] == A(4 / 7)
    assert pc["insufficient"]["precision"] == A(1 / 3) and pc["insufficient"]["recall"] == A(0.5)
    assert pc["insufficient"]["f1"] == A(0.4)
    assert v["class_macro_f1"] == A(172 / 315)
    assert v["fact_weighted_accuracy"] == A(43 / 70) and v["n_facts"] == 5
    assert v["subtype_accuracy"] == A(0.5) and v["n_gold_insufficient"] == 2
    assert v["response_counts"] == {"insufficient": 3, "refuted": 3, "supported": 9}


def test_group_macro_exclusion_and_ci(metrics, rows, release):
    gm = metrics["verdict"]["group_macro"]
    assert gm["groups"] == ["P-V1"]
    assert [e["group"] for e in gm["excluded_groups"]] == ["C-V1", "F-R1", "P-R1", "P-V3"]
    assert all(e["n_instances"] == 1 for e in gm["excluded_groups"])
    assert metrics["excluded_groups"] == ["C-V1", "F-R1", "P-R1", "P-V3"]
    assert gm["f1"] == A(73 / 126)
    lo, hi = gm["ci95"]
    assert 0.0 <= lo <= hi <= 1.0
    again = evaluate(rows, release, min_group_size=2, bootstrap=50, seed=0)
    assert again["verdict"]["group_macro"]["ci95"] == gm["ci95"]
    # every group in: the small ones count too
    all_in = evaluate(rows, release, min_group_size=1, bootstrap=0)["verdict"]["group_macro"]
    assert all_in["excluded_groups"] == [] and all_in["ci95"] is None
    assert all_in["per_group_f1"] == {"C-V1": A(1 / 3), "F-R1": A(1.0), "P-R1": A(1 / 3),
                                      "P-V1": A(73 / 126), "P-V3": A(1 / 3)}
    assert all_in["f1"] == A((73 / 126 + 1 / 3 + 1 / 3 + 1 + 1 / 3) / 5)


def test_breakdowns(metrics):
    pg = metrics["per_group"]
    assert pg["P-V1"]["n"] == 7 and pg["P-V1"]["accuracy"] == A(4 / 7)
    assert pg["P-V1"]["class_macro_f1"] == A(73 / 126) and pg["P-V1"]["tier"] == "vaccine"
    assert pg["P-V1"]["s1_claim_em"] == A(6 / 7) and pg["P-V1"]["n_wrong"] == 3
    assert pg["P-V1"]["coexist_leak"] == A(1 / 5)          # 5 rows with gold exclusions, one leaked
    assert pg["P-V1"]["attribution_top"]["count"] == 1     # three different stages, tie
    assert pg["P-R1"]["report_hit"] == A(0.5) and pg["P-R1"]["s2_denominator_f1"] is None
    assert pg["P-R1"]["attribution_top"] == {"stage": "S2-conditioning", "count": 1}
    assert pg["F-R1"]["class_macro_f1"] == A(1.0) and pg["F-R1"]["n_wrong"] == 0
    assert pg["F-R1"]["attribution_top"] is None
    t = metrics["per_tier"]
    assert t["report"]["n"] == 4 and t["report"]["accuracy"] == A(0.75)
    assert t["report"]["class_macro_f1"] == A(3 / 7)          # over {supported, refuted} only
    assert t["vaccine"]["n"] == 11 and t["vaccine"]["accuracy"] == A(6 / 11)
    r = metrics["per_register"]
    assert r["original"]["n"] == 14 and r["original"]["accuracy"] == A(9 / 14)
    assert r["research"] == {"n": 1, "n_instances": 1, "accuracy": 0.0, "class_macro_f1": A(0.0),
                             "classes": ["supported", "refuted", "insufficient"]}
    f = metrics["per_format"]
    assert f["question"]["accuracy"] == A(0.75) and f["claim"]["accuracy"] == A(3 / 7)
    ng = metrics["per_negated"]
    assert ng["True"]["n"] == 2 and ng["True"]["accuracy"] == A(0.5)
    assert ng["False"]["n"] == 13 and ng["False"]["accuracy"] == A(8 / 13)
    fam = metrics["per_family"]
    assert fam["first_last"]["accuracy"] == A(1.0) and fam["pairwise"]["accuracy"] == A(7 / 13)
    st = metrics["per_subtype"]
    assert list(st) == ["not_locatable"]
    assert st["not_locatable"]["n"] == 2 and st["not_locatable"]["accuracy"] == A(0.5)
    assert st["not_locatable"]["subtype_acc"] == A(0.5)


# ---------------------------------------------------------------------------
# stage metrics
# ---------------------------------------------------------------------------

def test_extraction(metrics):
    e = metrics["extraction"]
    assert e["n"] == 15 and e["n_no_claim"] == 0 and e["n_claim_invalid"] == 0
    assert e["mode_acc"] == A(1.0)
    assert e["events_ordered_em"] == A(14 / 15) and e["events_set_em"] == A(1.0)
    assert e["per_role"] == {"A": A(14 / 15), "B": A(14 / 15), "C": A(1.0)}
    assert e["cohort_em"] == A(1.0) and e["negated_acc"] == A(14 / 15)
    assert e["asserted_option_acc"] == A(1.0) and e["n_choice"] == 4
    assert e["claim_em"] == A(13 / 15)
    p = e["procedure"]
    assert p["claim_tail"] == A(14 / 15) and p["min_n_floor"] == A(14 / 15)
    for f in ("test", "null.kind", "null.p0", "null.statistic", "alpha", "arms", "conditioning"):
        assert p[f] == A(1.0), f
    assert e["procedure_em"] == A(13 / 15)
    c = e["mode_confusion"]
    assert len(c) == 29 and all(len(row) == 30 for row in c.values())   # 29 modes since v1.2
    assert c["dir_bool"]["dir_bool"] == 7 and c["dir_choice"]["dir_choice"] == 2
    assert c["rep_dir_bool"]["rep_dir_bool"] == 2 and c["rep_first_choice"]["rep_first_choice"] == 2
    assert c["sym_bool_cooccurs"]["sym_bool_cooccurs"] == 2
    assert sum(v for row in c.values() for v in row.values()) == 15


def test_retrieval(metrics):
    r = metrics["retrieval"]
    assert r["n"] == 11 and r["n_report"] == 4
    d = r["denominator"]
    assert d["precision"] == A((9 + 12 / 14) / 11) and d["recall"] == A(10 / 11)
    assert d["f1"] == A((9 + 12 / 13) / 11) and d["em"] == A(9 / 11)
    nm = r["numerator"]
    assert nm["precision"] == A(10 / 11) and nm["recall"] == A(9.8 / 11)
    assert nm["f1"] == A((9 + 8 / 9) / 11) and nm["em"] == A(9 / 11)
    ex = r["excluded"]
    assert ex == {"precision": A(10 / 11), "recall": A(10 / 11), "f1": A(10 / 11), "em": A(10 / 11)}
    assert r["all_sets_em"] == A(8 / 11) and r["arms_nk_em"] == A(8 / 11)
    assert r["coexist_leak"] == {"n": 7, "mean": A(1 / 7), "any_leak_rate": A(1 / 7)}
    assert r["not_locatable_fpr"] == {"n": 2, "rate": A(0.5)}
    assert r["report"] == {"n": 4, "report_hit": A(0.75)}
    assert r["by_label"]["arm"]["n"] == 11


def test_counts_and_pvalues(metrics):
    assert metrics["counts"] == {"n": 11, "nk_em": A(8 / 11)}
    p = metrics["pvalues"]
    assert p["n_with_gold_p"] == 9
    assert p["p_claim_agree"] == A(4 / 9) and p["p_opposite_agree"] == A(4 / 9)
    assert p["n_none_agreement"] == 15 and p["none_agreement"] == A(13 / 15)
    assert p["n_test_bucket"] == 9
    assert p["test_bucket"] == {"gold": 7, "synonym": 1, "other_exact": 0, "approximate": 0,
                                "none": 1, "unknown": 0}


def test_attribution_ordering_and_denominators(metrics):
    a = metrics["attribution"]
    assert a["order"] == list(STAGES)
    assert a["n_wrong"] == 6 and a["n_correct"] == 9
    s = a["stages"]
    assert {k: v["wrong"] for k, v in s.items()} == {
        "S1-parse": 2, "S1-procedure": 1, "S2-conditioning": 1, "S2-aggregation": 1,
        "S3-test": 1, "S3-gate": 0, "S3-verdict": 0}
    assert {k: v["reached"] for k, v in s.items()} == {
        "S1-parse": 15, "S1-procedure": 13, "S2-conditioning": 12, "S2-aggregation": 10,
        "S3-test": 9, "S3-gate": 8, "S3-verdict": 8}
    assert s["S1-parse"]["rate_wrong"] == A(2 / 15) and s["S2-aggregation"]["rate_wrong"] == A(0.1)
    assert s["S2-conditioning"]["lucky"] == 1 and s["S2-conditioning"]["rate_any"] == A(2 / 12)
    assert a["procedure_subbuckets"]["gate"] == {"wrong": 1, "lucky": 0}
    assert a["procedure_subbuckets"]["null"] == {"wrong": 0, "lucky": 0}
    assert a["lucky"] == {"count": 1, "rate": A(1 / 9), "by_stage": {"S2-conditioning": 1}}
    gf = a["gold_forced"]
    assert gf["S1"] == {"n": 15, "errors": 3, "rate": A(3 / 15)}
    assert gf["S2"] == {"n": 12, "errors": 3, "rate": A(3 / 12)}
    assert gf["S3"] == {"n": 9, "errors": 1, "rate": A(1 / 9)}


def test_consistency(metrics):
    c = metrics["consistency"]
    assert c["pairs"] == {"n_cores": 1, "n_pairs": 2, "contradiction_rate": A(0.5),
                          "correct_rate": A(0.5)}
    assert c["twins"] == {"n_groups": 1, "n": 2, "consistent_rate": A(0.5)}
    inv = c["invariance"]
    assert inv["n_instances"] == 7 and inv["invariant_rate"] == A(1 / 7)
    assert inv["per_register_accuracy"] == {"original": A(9 / 14), "research": A(0.0)}
    assert inv["per_register_delta"] == {"original": A(0.0), "research": A(-9 / 14)}


def test_choice(metrics):
    ch = metrics["choice"]
    assert ch["n"] == 4 and ch["answer_acc"] == A(0.75) and ch["n_gold_none"] == 0
    assert ch["baselines_gold_order"] == {"options_0": A(1.0), "options_2": A(0.0)}
    assert ch["baselines_presented"] == {"options_0": A(0.0), "options_2": A(0.0)}
    assert ch["by_group"]["F-R1"]["options_0_gold_order"] == A(1.0)
    assert ch["by_group"]["P-V3"]["answer_acc"] == A(0.5)


def test_underdetermined_block(metrics):
    u = metrics["underdetermined"]
    assert u["n"] == 1 and u["n_response_underdetermined"] == 1 and u["rate"] == A(1.0)
    assert u["by_group_register"] == {"C-V3|research": 1}
    assert u["expected_by_template"] == 1 and u["unexpected"] == 0


def test_underdetermined_response_on_determined_input_is_wrong(release):
    # Policy (2026-09-01): only rows whose TEMPLATE never names the events are set
    # aside. A determined input answered `underdetermined` stays in the scored set
    # as a wrong verdict, and is visible in the block as `unexpected` -- so the
    # token cannot be used to opt out of hard items.
    row = _row("P-V1-0000-original-question", _claim("P-V1-0000"), response="underdetermined")
    m = evaluate([row], release, min_group_size=1, bootstrap=0)
    assert m["n"]["records"] == 1 and m["n"]["underdetermined"] == 0
    assert m["underdetermined"]["n"] == 1 and m["underdetermined"]["unexpected"] == 1
    assert m["underdetermined"]["n_excluded"] == 0
    assert m["verdict"]["accuracy"] == 0.0


def test_missing_prediction_is_wrong_not_crash(release):
    row = _row("P-V1-0000-original-question", None, retrieval=False, error="boom")
    row["prediction"] = None
    m = evaluate([row], release, min_group_size=1, bootstrap=0)
    assert m["n"] == {"total_rows": 1, "records": 1, "instances": 1, "facts": 1,
                      "underdetermined": 0, "errors": 1, "no_response": 1}
    assert m["verdict"]["accuracy"] == 0.0
    assert m["extraction"]["n_no_claim"] == 1 and m["extraction"]["claim_em"] == 0.0
    assert m["attribution"]["stages"]["S1-parse"]["wrong"] == 1
    assert m["retrieval"]["denominator"]["f1"] == 0.0


def test_config(metrics):
    cfg = metrics["config"]
    assert cfg["min_group_size"] == 2 and cfg["bootstrap"] == 50 and cfg["seed"] == 0
    assert cfg["options_seed"] == 0 and cfg["p_tol"] == 1e-4
    assert cfg["pipelines"] == ["handmade"] and cfg["conditions"] == ["given-group"]


# ---------------------------------------------------------------------------
# report writers
# ---------------------------------------------------------------------------

def test_write_report(metrics, rows, release, tmp_path):
    paths = write_report(metrics, tmp_path, rows=rows, release=release)
    assert set(paths) == {"metrics", "report", "failures"}
    assert all(p.exists() for p in paths.values())

    loaded = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert loaded == metrics
    text = (tmp_path / "metrics.json").read_text(encoding="utf-8")
    assert text.index('"attribution"') < text.index('"verdict"')      # sorted keys

    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    for heading in ("# Evaluation report", "## Headline", "## Per group", "## Attribution",
                    "## Consistency", "## Underdetermined", "## Retrieval",
                    "## Extraction (S1)", "## Counts and p-values (S3)", "## Breakdowns"):
        assert heading in report, heading
    assert "| group | tier | n | acc | macro-F1 | S1 claim_em | S2 den F1 | coexist_leak | attribution top |" in report
    assert "| stage | wrong | lucky | reached | wrong rate | failure rate |" in report
    assert "verdict micro accuracy | 0.600" in report
    assert "C-V1 (1), F-R1 (1), P-R1 (1), P-V3 (1)" in report

    failures = (tmp_path / "failures.md").read_text(encoding="utf-8")
    assert failures.startswith("# Failures (worst wrong records)")
    assert "6 wrong of 15 scored records; showing 6." in failures
    assert "## 6. " in failures and "## 7. " not in failures
    # worst first: a supported<->refuted flip charged to S1-parse leads
    first = failures.split("## 1. ")[1].split("\n")[0]
    assert first.startswith("C-V1-0000-original-claim") and "[NEGATED wording]" in first
    assert 'text: "TEXT<C-V1-0000-original-claim>"' in failures
    assert "- attribution: **S2-conditioning**  (coexist_leak = 1.000)" not in failures  # lucky row is not a failure
    assert "- attribution: **S1-procedure [gate]**" in failures
    assert "- attribution: **S2-aggregation**" in failures
    assert "missing ids: 9, 10" in failures                         # dropped numerator reports
    assert "**n/k: gold 12/10, predicted 12/8**" in failures
    assert "extra ids: 1, 2, 3" in failures                         # fabricated denominator
    assert "report levels predicted: {'Chest discomfort': 0}" in failures
    assert "procedure differs: min_n_floor: gold 10 vs predicted 20" in failures


def test_write_report_without_rows(metrics, tmp_path):
    write_report(metrics, tmp_path / "bare")
    failures = (tmp_path / "bare" / "failures.md").read_text(encoding="utf-8")
    assert "prediction rows not supplied" in failures
    assert (tmp_path / "bare" / "report.md").exists()


def test_instance_bootstrap_ci_brackets_the_point_estimate(metrics, rows, release):
    v = metrics["verdict"]
    lo, hi = v["accuracy_ci95"]
    assert lo <= v["accuracy"] <= hi and 0.0 <= lo < hi <= 1.0
    flo, fhi = v["class_macro_f1_ci95"]
    assert flo <= v["class_macro_f1"] <= fhi
    assert v["n_instances_resampled"] == metrics["n"]["instances"]
    # seeded: the same seed reproduces the interval, another seed need not
    again = evaluate(rows, release, min_group_size=2, bootstrap=50, seed=0)["verdict"]
    assert again["accuracy_ci95"] == v["accuracy_ci95"]
    assert evaluate(rows, release, bootstrap=0)["verdict"]["accuracy_ci95"] is None
