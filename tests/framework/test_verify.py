"""Issue 41 verifiers: they read the plan, the input row and the stated conventions only."""
from temporal_hypo.framework.verify import all_plan_problems, procedure_problems, s1_plan_problems, stated_bar

VAX = {"level": "vaccine", "text": "After Pfizer, Headache precedes Fatigue."}
REP = {"level": "report", "text": "In report MT-0000001, Headache occurred in the first half of the timeline."}


def _plan(**kw):
    base = {"events": ["Headache", "Fatigue"], "quantity": "order_of_pair", "extreme": "none", "arms": 1,
            "denominator": "ordered_pair", "null_kind": "symmetric_fixed", "p0": 0.5, "tail": "greater",
            "test_family": "proportion_vs_p0", "test_rule": "exact_always", "min_n_floor": 10}
    base.update(kw)
    return base


def test_clean_plans_pass():
    assert all_plan_problems(_plan(), VAX) == []
    assert all_plan_problems(_plan(events=["Headache"], quantity="position_of_event", denominator="present_offmid",
                                   null_kind="data_derived", p0=None), VAX) == []
    assert all_plan_problems(_plan(events=["Headache"], quantity="position_of_event", denominator="single_report",
                                   null_kind="none", p0=None, test_family="none"), REP) == []


def test_report_tier_is_not_verified():
    # review item 6: the harness fills the report tier's denominator / arms / null
    assert s1_plan_problems(_plan(events=["Headache"], quantity="position_of_event", denominator="present_offmid",
                                  null_kind="data_derived"), REP) == []


def test_quantity_denominator_and_null_rules():
    assert any("adjacency" in x or "denominator the conventions name" in x
               for x in s1_plan_problems(_plan(quantity="adjacency_of_pair", denominator="consecutive_pair",
                                                null_kind="data_derived", p0=None), VAX))
    assert any("data-derived null exists only" in x
               for x in s1_plan_problems(_plan(quantity="co_occurrence_of_pair", denominator="both_present",
                                                null_kind="data_derived", p0=None), VAX))
    assert any("two_arm_equality" in x for x in s1_plan_problems(_plan(arms=2, null_kind="symmetric_fixed"), VAX))


def test_stated_bar_must_be_text_stated():
    row = {"level": "vaccine", "text": "After Pfizer, Headache precedes Fatigue in at least two thirds of the reports."}
    assert stated_bar(row["text"]) == 0.667
    assert any("text_stated" in x for x in s1_plan_problems(_plan(), row))
    assert s1_plan_problems(_plan(null_kind="text_stated", p0=0.667), row) == []
    assert any("requires a bar" in x for x in s1_plan_problems(_plan(null_kind="text_stated", p0=0.667), VAX))


def test_procedure_validity():
    assert procedure_problems(_plan(test_rule="exact_if_small_else_asymptotic"), VAX)
    assert procedure_problems(_plan(arms=2, null_kind="two_arm_equality", p0=None), VAX)   # family must be two_proportions
    assert procedure_problems(_plan(arms=2, null_kind="two_arm_equality", p0=None,
                                    test_family="two_proportions", test_rule="exact_if_small_else_asymptotic"), VAX) == []
    assert procedure_problems(_plan(quantity="extreme_of_set", extreme="earliest", denominator="all_present_unique_first",
                                    events=["A", "B", "C"]), VAX)   # argmax needs named_vs_runner_up
