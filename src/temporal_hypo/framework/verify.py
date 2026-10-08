"""Per-stage verifiers for the bounded verify-and-repair rounds (decisions.md
2026-10-08, issue 41).

A verifier may read three things and nothing else: the OUTPUT CONTRACT (the
plan schema; the SQL row contract), the STATED CONVENTIONS (the same
stipulations the toolbox prompt gives the model) and the DATA (what a
statement returned). It never reads the gold claim, the gold sets or the mode
table, so a repair prompt built from its findings restates something the model
was already told -- it cannot hand over the answer. Problems are phrased as
the convention they violate, never as a mode name.

Stage 1 checks a composed plan against the conventions (``s1_plan_problems``);
stage 3's procedure validity is a property of that same plan and is checked in
the same pass (``procedure_problems``). Stage 2's checks live next to the
retriever: an executor error, and ``sql.llm_sql.plan_consistency``.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

# quantity -> the denominator primitive(s) the conventions name for it (1 arm)
_QUANTITY_DENOMINATOR = {
    "order_of_pair": {"ordered_pair"},
    "immediate_order_of_pair": {"consecutive_pair"},
    "adjacency_of_pair": {"ordered_pair"},
    "position_of_event": {"present_offmid"},
    "co_occurrence_of_pair": {"both_present", "presence_split"},
    "dominant_relation_of_pair": {"both_present"},
    "ordering_of_triple": {"orderable_triple"},
    "extreme_of_set": {"all_present_unique_first", "all_present_unique_last"},
}
_DERIVED_OK = {"position_of_event", "adjacency_of_pair"}
_ARGMAX = {"dominant_relation_of_pair", "ordering_of_triple", "extreme_of_set"}
_BARS = (
    (re.compile(r"two[\s-]thirds|two out of (every )?three|2/3", re.I), 0.667),
    (re.compile(r"three[\s-]quarters|three out of (every )?four|3/4", re.I), 0.75),
    (re.compile(r"at least half|half or more|in half or more|at least 50\s?%", re.I), 0.5),
)
VALID_RULES = {"two_proportions": {"exact_always", "exact_if_small_else_asymptotic"},
               "proportion_vs_p0": {"exact_always"},
               "named_vs_runner_up": {"exact_always"},
               "none": {"exact_always", "exact_if_small_else_asymptotic"}}


def stated_bar(text: str) -> float | None:
    """The quantitative bar the wording states, if any (the text is an INPUT field)."""
    for pat, p0 in _BARS:
        if pat.search(text or ""):
            return p0
    return None


def s1_plan_problems(plan: Mapping[str, Any], row: Mapping[str, Any]) -> list[str]:
    """Violations of the stated conventions by a composed plan (empty = consistent)."""
    problems: list[str] = []
    tier = row.get("level")
    q = plan.get("quantity")
    den = plan.get("denominator")
    arms = plan.get("arms")
    nk = plan.get("null_kind")
    events = [e for e in (plan.get("events") or []) if e]

    if tier == "report":
        # review item 6 (2026-10-08): the report tier is a reading task; the harness
        # fills denominator / arms / null itself, so there is nothing to verify here.
        return problems

    # quantity <-> denominator, as the conventions phrase each situation
    want = _QUANTITY_DENOMINATOR.get(q)
    if want and den not in want:
        problems.append(
            f"quantity {q} is computed over the denominator the conventions name for that "
            f"situation ({' or '.join(sorted(want))}), not {den}")
    if q == "extreme_of_set":
        x = plan.get("extreme")
        if x == "earliest" and den == "all_present_unique_last" or x == "latest" and den == "all_present_unique_first":
            problems.append("the extreme (earliest/latest) and the denominator (unique first/last) disagree")
    if q == "position_of_event" and len(events) != 1:
        problems.append("a position claim is about ONE event; events must list exactly that term")
    if q != "position_of_event" and len(events) < 2:
        problems.append("this quantity relates two or more named events; events lists fewer")

    # the null, as the conventions derive it
    if arms == 2 and nk != "two_arm_equality":
        problems.append("a comparison between two groups (arms = 2) tests the EQUALITY of the two "
                        "rates: null_kind two_arm_equality (no p0)")
    if arms in (None, 1):
        if nk == "data_derived" and q not in _DERIVED_OK:
            problems.append("a data-derived null exists only for ONE event's position in the timeline "
                            "and for the adjacency rate of a pair; this quantity has a symmetry "
                            "(null_kind symmetric_fixed, p0 = 0.5) or a bar stated in the text")
        if q in _DERIVED_OK and nk not in ("data_derived",):
            problems.append("for one event's position (or a pair's adjacency rate) the chance rate is "
                            "NOT 0.5: it is computed from the reports' stage structure -- "
                            "null_kind data_derived, p0 null")
        bar = stated_bar(row.get("text") or "")
        if bar is not None and q not in _ARGMAX:
            if nk != "text_stated" or plan.get("p0") is None or abs(float(plan.get("p0")) - bar) > 0.02:
                problems.append(f"the wording states a bar ({bar}): null_kind text_stated with p0 = {bar}")
        elif bar is None and nk == "text_stated":
            problems.append("null_kind text_stated requires a bar stated in the wording; none is stated")
    return problems


def procedure_problems(plan: Mapping[str, Any], row: Mapping[str, Any]) -> list[str]:
    """Stage-3 validity of the plan's test choice (the toolbox's own rules)."""
    problems: list[str] = []
    if row.get("level") == "report":
        return problems
    q = plan.get("quantity")
    arms = plan.get("arms")
    fam = plan.get("test_family")
    rule = plan.get("test_rule")
    nk = plan.get("null_kind")
    if arms == 2 and fam != "two_proportions":
        problems.append("two arms are compared with the two_proportions family (a 2x2 table)")
    elif arms in (None, 1):
        if q in _ARGMAX and fam != "named_vs_runner_up":
            problems.append("a 'most common' claim tests the NAMED cell against its strongest "
                            "competitor: family named_vs_runner_up")
        if q not in _ARGMAX and fam != "proportion_vs_p0":
            problems.append("one proportion against a null p0 is the proportion_vs_p0 family")
    if fam in VALID_RULES and rule not in VALID_RULES[fam]:
        problems.append(f"test_rule {rule} is not valid for {fam}: use {' or '.join(sorted(VALID_RULES[fam]))}")
    if nk in ("symmetric_fixed", "text_stated"):
        p0 = plan.get("p0")
        if p0 is None or not (0.0 < float(p0) < 1.0):
            problems.append("a fixed null needs p0 strictly between 0 and 1")
    return problems


def all_plan_problems(plan: Mapping[str, Any], row: Mapping[str, Any]) -> list[str]:
    return s1_plan_problems(plan, row) + procedure_problems(plan, row)
