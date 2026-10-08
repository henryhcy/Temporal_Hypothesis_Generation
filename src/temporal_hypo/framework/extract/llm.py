"""Stage 1 by prompting: hypothesis text -> ``StructuredClaim`` through a chat model.

WHAT: ``LLMExtractor`` builds one chat prompt -- the task, the 20-mode catalogue
(``pilot.RULE_BY_MODE`` + ``MODE_SPEC`` + the H0 wording per mode), the floors
and alpha, k few-shot pairs, and the visible fields of the question row -- asks
the ``Provider`` for the flat JSON shape ``claim_schema.FLAT_JSON_SCHEMA``, and
folds the reply with ``claim_from_flat``. WHY: this is the "prompted local LLM"
S1 method of plan 11 §3; the two toggles the evaluation needs are
``blind_group`` (hide ``group_id``, so the mode must be inferred from the text)
and ``procedure_given`` (the HOW layer is derived by the harness instead of
asked for, isolating WHAT-layer errors from null/test/tail errors).

Design points that matter for scoring:

- The floors (10 pairwise/first_last, 5 sequence) and alpha (0.05 per side) are
  always stated, in both modes (plan 11 §2: withholding them makes the
  ``sparse``/``underpowered`` classes unwinnable for the wrong reason).
- Events must be copied VERBATIM and in the order the claim ASSERTS; the
  harness compares slot-for-slot against ``from_gold``.
- Vocabulary "snapping" is exact-match only: an unknown spelling is left as-is
  (and recorded), never fuzzy-corrected -- a misspelled event is a Stage-1 error
  the metrics must see.
- One JSON-repair retry; every other failure returns ``None`` with the reason on
  ``last_error`` so the pipeline can log it and move on.

``H0_BY_MODE`` copies the wording of ``scripts/make_examples.py::_null_hypothesis``
for the modes it covers (with ``{A}``/``{B}``/``{C}``/``{v1}``/``{v2}``
placeholders) and adds the four two-arm / modal-relation modes that script never
handled, phrased against the oracle's actual nulls (Fisher p1 = p2; modal vs
runner-up). The script is a CLI and is not imported.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Mapping, Sequence

from temporal_hypo.framework.claim_schema import (
    FLAT_JSON_SCHEMA,
    GROUP_BY_MODE,
    MODE_SPEC,
    MODES,
    PLAN_JSON_SCHEMA,
    QUANTITIES,
    StructuredClaim,
    claim_from_flat,
    claim_from_plan,
    derive_procedure,
    plan_from_claim,
)
from temporal_hypo.framework.extract import visible_fields
from temporal_hypo.framework.extract.llm_client import Completion, Provider, parse_json_object
from temporal_hypo.generation.cores import MODE_BY_GROUP
from temporal_hypo.generation.pilot import RULE_BY_MODE

# ---------------------------------------------------------------------------
# the catalogue text
# ---------------------------------------------------------------------------

# H0 per mode. Placeholders: {A} {B} {C} {D} events, {v1} {v2} vaccines.
H0_BY_MODE: dict[str, str] = {
    # -- copied from scripts/make_examples.py::_null_hypothesis ----------------
    "dir_bool": "H0: P({A} precedes {B}) = 0.5 (no directional preference among ordered reports)",
    "dir_choice": "H0: P({A} precedes {B}) = 0.5 (no directional preference among ordered reports)",
    "sym_bool_cooccurs": "H0: P({A} and {B} co-occur) = 0.5 (among reports containing both)",
    "seq_bool": "H0: the {A} -> {B} -> {C} ordering and the runner-up ordering are equally "
                "frequent (P = 0.5; no unique mode)",
    "modal_choice": "H0: the named ordering and the runner-up ordering are equally "
                    "frequent (P = 0.5; no unique modal ordering)",
    "first_bool": "H0: {A} and the runner-up event are equally often the first "
                  "(P = 0.5; no unique most-common first event)",
    "first_choice": "H0: the named candidate and the runner-up are equally often "
                    "the first (P = 0.5; no unique most-common first event)",
    "last_choice": "H0: the named candidate and the runner-up are equally often "
                   "the last (P = 0.5; no unique most-common last event)",
    "multi_dir_precedes": "H0: P({A} precedes {B}) is equal for {v1} and {v2} (p1 = p2)",
    "rep_dir_bool": "H0: none -- single deterministic observation, no sampling distribution",
    "rep_dir_choice": "H0: none -- single deterministic observation, no sampling distribution",
    "rep_sym_bool": "H0: none -- single deterministic observation, no sampling distribution",
    "rep_seq_bool": "H0: none -- single deterministic observation, no sampling distribution",
    "rep_first_choice": "H0: none -- single deterministic observation, no sampling distribution",
    "rep_last_choice": "H0: none -- single deterministic observation, no sampling distribution",
    "rep_first_bool": "H0: none -- single deterministic observation, no sampling distribution",
    # -- not covered by the script; phrased against core.answers' actual nulls --
    "cooc_modal_bool": "H0: co-existence and the runner-up relation (before or after) are "
                       "equally frequent among reports containing both {A} and {B} "
                       "(P = 0.5; no unique modal relation)",
    "antecedent_bool": "H0: P({B} follows {A}) = P({B} follows {C}) over the two ordered-pair "
                       "arms of the same cohort (p1 = p2)",
    "pairpair_bool": "H0: P({A} precedes {B}) = P({C} precedes {D}) over the two ordered-pair "
                     "arms of the same cohort (p1 = p2)",
    "assoc_bool": "H0: P({B} present | {A} present) = P({B} present | {A} absent) "
                  "(p1 = p2; no association)",
    # -- v1.2 families (decisions.md 2026-10-07) ---------------------------------
    "early_bool": "H0: P({A} in the earlier half) = the STRUCTURAL early-rate of the reports "
                  "that contain {A} (computed from their stage populations; not 0.5)",
    "rep_early_bool": "H0: none -- single deterministic observation, no sampling distribution",
    "imm_bool": "H0: P({A} directly before {B} | the two are at consecutive stages) = 0.5",
    "imm_choice": "H0: P({A} directly before {B} | the two are at consecutive stages) = 0.5",
    "rep_imm_bool": "H0: none -- single deterministic observation, no sampling distribution",
    "adj_rate_bool": "H0: P({A} and {B} at consecutive stages | distinct stages) = the mean "
                     "chance 2/L over those reports (L = the report's stage count; not 0.5)",
    "precedes_bar": "H0: P({A} precedes {B}) = 2/3 among ordered reports (the stated bar)",
    "cooc_bar": "H0: P({A} and {B} co-occur) = 2/3 among reports containing both (the stated bar)",
    "first_bar": "H0: P({A} is the unique earliest of {A},{B},{C}) = 1/2 (the stated bar)",
}
assert set(H0_BY_MODE) == set(MODES), sorted(set(H0_BY_MODE) ^ set(MODES))

# What the event roles mean per mode (the order the model must emit them in).
ROLES_BY_MODE: dict[str, str] = {
    "rep_dir_bool": "A,B: A occurred before B",
    "rep_dir_choice": "A,B: A came first (A = the asserted/first-named event)",
    "rep_sym_bool": "A,B: A and B co-occur (same level)",
    "rep_seq_bool": "A,B,C: strict order A -> B -> C",
    "rep_first_choice": "A,B,C: A is the earliest (A = asserted/first-named)",
    "rep_last_choice": "A,B,C: A is the latest (A = asserted/first-named)",
    "rep_first_bool": "A,B,C: A is the first of the three",
    "dir_bool": "A,B: A typically before B",
    "dir_choice": "A,B: A usually before B (A = asserted/first-named)",
    "sym_bool_cooccurs": "A,B: A and B typically co-occur",
    "cooc_modal_bool": "A,B: co-existence is the dominant relation of A and B",
    "seq_bool": "A,B,C: A -> B -> C is the most common ordering",
    "modal_choice": "A,B,C: the asserted/first-named ordering A -> B -> C",
    "first_choice": "A,B,C: A most commonly first (A = asserted/first-named)",
    "first_bool": "A,B,C: A is the most common first event",
    "last_choice": "A,B,C: A most commonly last (A = asserted/first-named)",
    "antecedent_bool": "A,B,C: B follows A more often than B follows C (arm1 = pair A,B; arm2 = pair C,B)",
    "pairpair_bool": "A,B,C,D: A precedes B more often than C precedes D (arm1 = A,B; arm2 = C,D)",
    "assoc_bool": "A,B: B occurs more often with A than without A (arm1 = has A; arm2 = lacks A)",
    "multi_dir_precedes": "A,B: A precedes B more often after cohort v1 than v2 (v1 = asserted/first-named vaccine)",
    # v1.2
    "early_bool": "A: A falls in the earlier half of the timeline more often than chance",
    "rep_early_bool": "A: A occurred in the first half of this report's timeline",
    "imm_bool": "A,B: when at consecutive stages, A is usually the earlier",
    "imm_choice": "A,B: when at consecutive stages, A is the earlier more often (A = asserted/first-named)",
    "rep_imm_bool": "A,B: A occupied the stage directly before B",
    "adj_rate_bool": "A,B: A and B fall at consecutive stages more often than chance",
    "precedes_bar": "A,B: A precedes B in at least two thirds of ordered reports",
    "cooc_bar": "A,B: A and B co-occur in at least two thirds of reports containing both",
    "first_bar": "A,B,C: A is the earliest in at least half of the reports containing all three",
}
assert set(ROLES_BY_MODE) == set(MODES)

from temporal_hypo.core.min_n import PAIRWISE_FLOOR, SEQUENCE_FLOOR
# Single source of truth (core/min_n.py) -- the prompt's floor constants can
# never drift from the gate's (fixed 2026-09-02; they were duplicated literals).
ALPHA_TEXT = "0.05 per side (one-sided exact tests in the claim's direction)"


def h0_for(mode: str, events: Sequence[str | None] = (), vaccines: Sequence[str] = ()) -> str:
    """The H0 wording for ``mode`` with real names filled in where known."""
    letters = ["A", "B", "C", "D"]
    vals = {L: L for L in letters}
    for i, t in enumerate(events[:4]):
        if t:
            vals[letters[i]] = str(t)
    vals["v1"] = vaccines[0] if len(vaccines) > 0 else "v1"
    vals["v2"] = vaccines[1] if len(vaccines) > 1 else "v2"
    return H0_BY_MODE[mode].format_map(vals)


def _mode_order() -> list[str]:
    """Modes in template-group order (P-R1 ... F-V3), which reads best in a table."""
    return [MODE_BY_GROUP[g] for g in MODE_BY_GROUP if MODE_BY_GROUP[g] in MODE_SPEC]


def mode_catalogue(*, show_groups: bool = True, include_procedure: bool = True,
                   include_null_hints: bool = True) -> str:
    """The 20-mode table shown to the model (compact, one line per mode).

    ``include_null_hints=False`` is the null/test-inference ablation (issue 27).
    Four columns give the answer away, not the two you would expect: ``test``
    names it and ``null`` prints ``p0``, but ``rule`` also says "Fisher 2x2" and
    "supported if frac>0.5", and ``H0`` states the null in words. All four drop
    together, leaving mode, tier/family/answer_type, events and conditioning --
    so the model must infer the procedure from the claim's structure.
    """
    head = ["mode"]
    if show_groups:
        head.append("group")
    head += ["tier/family/answer_type", "events (roles)", "conditioning of the denominator"]
    if include_procedure:
        head += ["arms", "test", "null", "floor"]
    if include_null_hints:
        head += ["rule", "H0"]
    lines = [" | ".join(head)]
    for mode in _mode_order():
        s = MODE_SPEC[mode]
        proc = derive_procedure(mode)
        row = [mode]
        if show_groups:
            row.append(GROUP_BY_MODE[mode])
        row += [f"{s.tier}/{s.family}/{s.answer_type}", ROLES_BY_MODE[mode], s.conditioning]
        if include_procedure:
            row += [str(s.arms), str(s.test), f"{s.null_kind}"
                    + (f" p0={proc.null.p0}" if proc.null.p0 is not None else ""),
                    str(proc.min_n_floor)]
        if include_null_hints:
            row += [RULE_BY_MODE[mode], H0_BY_MODE[mode]]
        lines.append(" | ".join(row))
    return "\n".join(lines)


CONDITIONING_GLOSS = (
    "ordered_pair: both events present at DISTINCT first-mention levels (co-existing "
    "pairs are EXCLUDED); both_present: both present, co-existence counts;\n"
    "orderable_triple: all three present at pairwise-distinct levels; "
    "all_present_unique_first/last: all candidates present with a unique earliest/latest "
    "(ties are dropped);\n"
    "presence_split: the whole vaccine cohort split on whether the report contains A; "
    "single_report: the one report named by VAERS id, first-mention levels;\n"
    "consecutive_pair: both present at CONSECUTIVE first-mention ranks (|rank(A) - rank(B)| = 1; "
    "co-existing and gapped pairs are excluded); present_offmid: reports containing A with at "
    "least two stages where A is not on the exact middle rank."
)


def _what_schema() -> dict:
    """``FLAT_JSON_SCHEMA`` restricted to the WHAT layer (procedure-given mode)."""
    keep = ("mode", "events", "negated", "asserted_option")
    return {
        "type": "object",
        "properties": {k: FLAT_JSON_SCHEMA["properties"][k] for k in keep},
        "required": list(FLAT_JSON_SCHEMA["required"]),
        "additionalProperties": False,
    }


WHAT_JSON_SCHEMA: dict = _what_schema()


TIER_HINT = (
    "- TIER: the input's `level` fixes which modes are admissible. level=report -> one of the "
    "nine rep_* modes (the claim is about ONE report, a single deterministic observation, no "
    "test); level=vaccine -> a single-cohort mode (dir_*, sym_bool_cooccurs, assoc_bool, "
    "cooc_modal_bool, seq_bool, modal_choice, first_*, last_choice, antecedent_bool, "
    "pairpair_bool, early_bool, imm_*, adj_rate_bool, precedes_bar, cooc_bar, first_bar); "
    "level=multi -> multi_dir_precedes. Never choose a cohort mode for a "
    "report-level input or a rep_* mode for a cohort-level input."
)

ROUTING_HINT = (
    "- CANDIDATE COUNT: count the distinct event terms the text names. Exactly 1 -> a "
    "position mode (early_bool, rep_early_bool). Exactly 2 -> a "
    "pairwise mode (dir_*, rep_dir_*, sym_bool_cooccurs, cooc_modal_bool, assoc_bool, "
    "multi_dir_precedes, imm_*, rep_imm_bool, adj_rate_bool, precedes_bar, cooc_bar), NEVER a "
    "first/last or sequence mode. Exactly 3 -> a sequence, "
    "first/last, antecedent or first-bar mode (seq_bool, modal_choice, first_*, last_choice, "
    "antecedent_bool, first_bar, rep_seq_bool, rep_first_*, rep_last_choice). Exactly 4 -> "
    "pairpair_bool. 'Which came first, A or B?' with only two candidates is a DIRECTION "
    "claim (dir_choice / rep_dir_choice), not a first/last claim."
)


def system_prompt(*, procedure_given: bool, blind_group: bool, tier_hint: bool = False,
                  routing_hint: bool = False, null_hints: bool = True) -> str:
    """The system message: task, output contract, catalogue, statistical constants.

    ``tier_hint`` adds an explicit rule tying the admissible modes to the input's
    ``level`` (an ablation: the tier is GIVEN structurally, so stating the rule
    does not leak anything the model was not already handed).
    """
    schema = WHAT_JSON_SCHEMA if procedure_given else FLAT_JSON_SCHEMA
    parts = [
        "You translate a natural-language hypothesis about vaccine adverse-event timelines "
        "(VAERS reports annotated as leveled orders of MedDRA event terms) into ONE structured "
        "claim in JSON. The claim names the statistic (mode), the events in the order the claim "
        "asserts, whether the wording is negated, and -- for CHOICE items -- the option the text "
        "asserts. The harness then retrieves the conditioned reports and runs the exact test.",
        "",
        "INPUT: a JSON object with fields level (report|vaccine|multi), answer_type (BOOL|CHOICE), "
        "register, format (question|claim), text, options (CHOICE only), cohort "
        "{level, vaccines[], report_id}"
        + ("" if blind_group else ", and group_id (the template group; each group maps to exactly "
           "one mode -- use it)")
        + ". The cohort is given: do not re-derive vaccines or the report id.",
        "",
        "OUTPUT: exactly one JSON object matching this schema (no prose, no code fences):",
        json.dumps(schema, ensure_ascii=False),
        "",
        "FIELD RULES:",
        "- mode: one of the 20 modes below. level + answer_type + the wording pin it down.",
        *([TIER_HINT] if tier_hint else []),
        *([ROUTING_HINT] if routing_hint else []),
        "- events: copy each event term VERBATIM from the text (exact spelling and case) and list "
        "them IN THE ORDER THE CLAIM ASSERTS, following the role column (A first, then B, ...). "
        "For a CHOICE question that asserts nothing, list them in the order the text names them.",
        "- negated: true ONLY when the wording asserts the negation ('do not typically co-occur', "
        "'is not the dominant relation', 'no more often than'). Plain claims and neutral questions "
        "are false. Only the co-occurrence modes have negated wording.",
        "- asserted_option: for CHOICE items, the option string the text asserts (an event, an "
        "ordering written with ' → ' as in options, or a vaccine); null when the text is a "
        "neutral question. Always null for BOOL.",
    ]
    if procedure_given:
        parts.append("The statistical procedure (test, null, tail, floor, arms, conditioning) is "
                     "derived by the harness from the mode -- do NOT output procedure fields.")
    elif null_hints:
        parts += [
            "- test / null_kind / p0 / claim_tail / arms / conditioning / min_n_floor: the "
            "procedure the claim requires (see the catalogue): binom_exact with null_kind "
            "binomial p0=0.5 for the single-cohort proportion modes; modal_runner (binomial "
            "p0=0.5 over the named cell vs the runner-up) for the argmax modes; fisher_exact with "
            "null_kind two_arm_equality (p0 null) for the two-arm modes; null test, null_kind "
            "'none', p0 null, min_n_floor null at the report tier. claim_tail is 'greater' for "
            "every plain claim and 'less' when negated.",
        ]
    else:
        # The ablation: name the fields, state NOTHING about which value each takes.
        parts += [
            "- test / null_kind / p0 / claim_tail / arms / min_n_floor: the statistical procedure "
            "this claim requires. Work it out from what the claim asserts -- what quantity is "
            "being compared, against what baseline, and how many groups the comparison spans. "
            "`test` is the exact test to run, `null_kind` and `p0` state the hypothesis it is run "
            "against, `arms` is how many groups the statistic compares, and `claim_tail` is the "
            "direction the claim asserts.",
            "- conditioning: which reports the statistic is computed over (see the glossary).",
        ]
    parts += [
        "",
        "STATISTICAL CONSTANTS (always apply): alpha = " + ALPHA_TEXT + "; minimum-n floors: "
        f"{PAIRWISE_FLOOR} for pairwise (precedes / co-occurs) and first_last, {SEQUENCE_FLOOR} for "
        "sequence; below the floor the verdict is insufficient. A term's position in a report is "
        "its FIRST mention.",
        "",
        "CONDITIONING GLOSSARY:",
        CONDITIONING_GLOSS,
        "",
        "MODE CATALOGUE:",
        # include_procedure is ON in procedure-blind mode -- that is the point of the
        # catalogue there, and it is exactly what the ablation removes.
        mode_catalogue(show_groups=not blind_group,
                       include_procedure=(not procedure_given) and null_hints,
                       include_null_hints=null_hints),
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# the TOOLBOX frame (11 §13, issues 29/31): task card + primitives, NO catalogue
# ---------------------------------------------------------------------------

CONVENTIONS_TEXT = (
    "CONVENTIONS OF THIS DATASET (stipulations, stated once; phrased by situation, apply them):\n"
    "- A term's position in a report is its FIRST mention; terms at the same stage co-exist.\n"
    "- When a claim orders two events (A before B), a report where they co-exist cannot "
    "witness the order: the denominator is reports with both present at DISTINCT stages "
    "(primitive ordered_pair). When a claim is about co-occurrence itself, co-existing "
    "reports are the numerator over reports with both present (both_present).\n"
    "- When a claim orders three events, the denominator is reports with all three at "
    "pairwise-distinct stages (orderable_triple).\n"
    "- When a claim asks which of several candidates is earliest (or latest), a report "
    "where two candidates tie for that extreme has no answer and is dropped: the denominator "
    "is reports with all candidates present and a unique extreme "
    "(all_present_unique_first / all_present_unique_last).\n"
    "- When a claim compares an event's rate between reports that do and do not contain "
    "another event, the WHOLE cohort is split on presence of that event (presence_split); "
    "nothing is conditioned on co-occurrence.\n"
    "- When a claim compares two vaccine cohorts, each cohort is its own arm with the "
    "same denominator rule applied inside it.\n"
    "- A report's STAGES are its occupied first-mention levels, ranked 0, 1, 2, ... from the "
    "earliest; two events are at consecutive stages when their ranks differ by exactly one. "
    "Order words alone (precedes, before, after, follows, comes first, is followed by) are "
    "DISTANCE-BLIND: A at stage 0 and B at stage 5 is A before B, and the denominator stays "
    "ordered_pair whether the claim is about one pair, a pair compared with another pair, or "
    "a pair compared across cohorts. ONLY wording that says the two are adjacent -- "
    "'immediately before', 'directly preceding', 'right before, with nothing in between', "
    "'back to back', 'in consecutive stages' -- conditions on consecutive ranks: then a "
    "report where the two co-exist or have a stage between them cannot witness the claim, "
    "and the denominator is reports with both at consecutive ranks (consecutive_pair). When "
    "a claim is about how OFTEN two events land at consecutive stages at all, the "
    "denominator is reports with both at distinct stages (ordered_pair), the numerator is "
    "the adjacent ones, and chance is the report's own 2/L (L = its stage count), so the "
    "null is computed from the data.\n"
    "- When a claim is about ONE event falling in the earlier half of a timeline, a report "
    "with a single stage has no halves and an event on the exact middle stage is in "
    "neither half: both leave the denominator (present_offmid). Earlier stages hold more "
    "events, so the chance of 'early' is the structural early-rate of the reports in the "
    "denominator, computed from the data, never 0.5.\n"
    "- When the wording states a bar ('in at least two thirds', 'in at least half'), the "
    "null proportion is that bar, read off the text; refuted means significantly BELOW it.\n"
    "- A claim about ONE named report is a single deterministic observation over that "
    "report's first-mention levels (single_report): no test, no floor.\n"
    "- Population claims: alpha = " + "ALPHA_TEXT_PLACEHOLDER" + "; minimum-n floors: "
    "FLOORS_PLACEHOLDER; below the floor the verdict is insufficient. Verdicts are "
    "supported / refuted / insufficient; refuted requires significance in the OPPOSITE "
    "direction, never merely a failure to reach significance."
)

NULL_SOURCES_TEXT = (
    "HOW TO FORMULATE THE NULL (decide what 'chance' means for the quantity the claim compares):\n"
    "- symmetric_fixed: the claim orders two named events, or names one of k candidates -- "
    "swapping the roles is a symmetry, so the null proportion is p0 = 0.5: SET p0 = 0.5. For a "
    "named candidate against its strongest competitor ('most common first/last', 'most common "
    "ordering') the test family is named_vs_runner_up (0.5 on those two cells) -- NOT a plain "
    "proportion and NOT data-derived.\n"
    "- text_stated: the wording carries a quantitative bar ('in at least two-thirds of "
    "reports') -- p0 is that bar.\n"
    "- data_derived: the claim is about ONE event's position relative to the report's "
    "timeline and no symmetry applies -- the null proportion is the structural rate of the "
    "reference population, computed from the data (see STAGE POPULATION); state the "
    "reference population in null_reference and leave p0 null.\n"
    "- two_arm_equality: the claim compares a rate between two groups -- the null is that "
    "the two rates are equal (a comparison, not a number).\n"
    "- none: a single named report is observed, not tested."
)

TOOLBOX_TEXT = (
    "TEST TOOLBOX (families; the concrete test is chosen by the rule once n is known):\n"
    "- proportion_vs_p0: k successes of n against a fixed p0 -- exact binomial "
    "(P(X>=k) or P(X<=k) in the claim's direction); valid at any n.\n"
    "- named_vs_runner_up: the named cell against its largest competitor -- exact binomial "
    "at 0.5 on those two cells; valid at any n.\n"
    "- two_proportions: a 2x2 table -- Fisher's exact test (one-sided, conditions on the "
    "margins), valid at any n; a chi-square test is an asymptotic alternative valid only "
    "when every expected cell is >= 5.\n"
    "- none: report-tier observation.\n"
    "test_rule: exact_always, or exact_if_small_else_asymptotic (exact when any expected "
    "cell < 5, asymptotic otherwise)."
)

PROCEDURE_TEXT = (
    "PROCEDURE (work through these in order):\n"
    "1. Identify the claim shape: what quantity is asserted (quantity), how many named "
    "events, how many groups (arms), whether it is about one named report or a population "
    "(the input's level says which).\n"
    "2. Decide what chance means for that quantity (null_kind, p0 / null_reference).\n"
    "3. Name the reports the statistic is computed over (denominator) using the primitives "
    "in the conventions.\n"
    "4. State the direction the claim asserts (tail: greater for a plain claim, less when the "
    "wording is negated).\n"
    "5. Choose the test family and the selection rule.\n"
    "6. State the gate (min_n_floor: the floor for this kind of claim; null for one report)."
)


def conventions_block(dataset_card: str | None = None) -> str:
    """The situation-phrased stipulations (plus the computed dataset card when given),
    as one text block -- the same words the toolbox S1 frame states. Used by the S2
    prompt variants that state the conventions without the per-mode rule (the
    cell-B / cell-D baselines of the 2026-10-07 audit)."""
    conv = (CONVENTIONS_TEXT
            .replace("ALPHA_TEXT_PLACEHOLDER", ALPHA_TEXT)
            .replace("FLOORS_PLACEHOLDER",
                     f"{PAIRWISE_FLOOR} per arm for claims about pairs, first/last and "
                     f"co-occurrence, {SEQUENCE_FLOOR} for three-event orderings"))
    return "\n\n".join(x for x in (dataset_card, conv) if x)


def toolbox_system_prompt(*, dataset_card: str, blind_group: bool = True) -> str:
    """The toolbox frame: task card + conventions + null sources + test toolbox + procedure.

    Contains NO mode names, NO template-group ids, NO per-mode H0 and NO
    mapping sentence -- the model composes the procedure from primitives
    (decisions 2026-09-29 "state every stipulation, withhold only the mapping").
    """
    conv = (CONVENTIONS_TEXT
            .replace("ALPHA_TEXT_PLACEHOLDER", ALPHA_TEXT)
            .replace("FLOORS_PLACEHOLDER",
                     f"{PAIRWISE_FLOOR} per arm for claims about pairs, first/last and "
                     f"co-occurrence, {SEQUENCE_FLOOR} for three-event orderings"))
    parts = [
        "You are the statistician for a dataset of annotated adverse-event timelines. Given a "
        "natural-language hypothesis, you formulate the exact statistical procedure that "
        "verifies it: what is compared, over which reports, against which null hypothesis, "
        "with which test. The harness then retrieves the reports and runs your plan.",
        "",
        "INPUT: a JSON object with fields level (report|vaccine|multi), answer_type "
        "(BOOL|CHOICE), register, format (question|claim), text, options (CHOICE only), "
        "cohort {level, vaccines[], report_id}"
        + ("" if blind_group else ", and group_id")
        + ". The cohort is given: do not re-derive vaccines or the report id.",
        "",
        dataset_card,
        "",
        conv,
        "",
        NULL_SOURCES_TEXT,
        "",
        TOOLBOX_TEXT,
        "",
        PROCEDURE_TEXT,
        "",
        "OUTPUT: exactly one JSON object matching this schema (no prose, no code fences):",
        json.dumps(PLAN_JSON_SCHEMA, ensure_ascii=False),
        "",
        "FIELD RULES:",
        "- events: copy each event term VERBATIM from the text (exact spelling and case) and "
        "list them IN THE ORDER THE CLAIM ASSERTS (the event whose position/precedence is "
        "asserted first; for a two-arm comparison, arm 1's events before arm 2's). For a "
        "CHOICE question that asserts nothing, list them in the order the text names them.",
        "- negated: true ONLY when the wording asserts the negation ('do not typically "
        "co-occur', 'no more often than'). Plain claims and neutral questions are false.",
        "- asserted_option: for CHOICE items, the option string the text asserts; null when "
        "the text is a neutral question. Always null for BOOL.",
        "- quantity is WHAT is measured; arms is 2 whenever that quantity is COMPARED between "
        "two groups (two vaccine cohorts; reports with vs without an event -- denominator "
        "presence_split; or one event pair against another). A three-event claim of the form "
        "'B follows A more often than it follows C' compares two pairs: arms = 2.",
        "- extreme: REQUIRED for extreme_of_set -- earliest ('first', 'earliest') or latest "
        "('last', 'latest'); null for every other quantity.",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# flat <-> claim (few-shot rendering is the inverse of claim_from_flat)
# ---------------------------------------------------------------------------

def flat_from_claim(claim: StructuredClaim, *, include_procedure: bool = True) -> dict:
    """The flat JSON the model is asked for, rendered from a claim (few-shot targets).

    Inverse of ``claim_from_flat``: ``claim_from_flat(flat_from_claim(c), row)`` has
    the same WHAT key and procedure as ``c``.
    """
    flat: dict[str, Any] = {
        "mode": claim.mode,
        "events": [t for t in claim.terms],
        "negated": bool(claim.negated),
        "asserted_option": claim.asserted_option if claim.answer_type == "CHOICE" else None,
    }
    if include_procedure:
        p = claim.procedure
        flat.update({
            "test": p.test,
            "null_kind": p.null.kind,
            "p0": p.null.p0,
            "claim_tail": p.claim_tail,
            "arms": p.arms,
            "conditioning": p.conditioning,
            "min_n_floor": p.min_n_floor,
        })
    return flat


def snap_terms(terms: Sequence[Any], vocabulary: set[str] | None
               ) -> tuple[list[str | None], list[str]]:
    """Whitespace-strip the terms; report which are NOT in the vocabulary.

    Exact, case-sensitive membership only -- no fuzzy correction (a wrong
    spelling must stay wrong so Stage 1 is scored honestly).
    """
    out: list[str | None] = []
    oov: list[str] = []
    for t in terms:
        if t is None:
            out.append(None)
            continue
        s = str(t).strip()
        out.append(s)
        if vocabulary is not None and s not in vocabulary:
            oov.append(s)
    return out, oov


# ---------------------------------------------------------------------------
# few-shot examples
# ---------------------------------------------------------------------------

def _slot_values(fc: Mapping[str, Any]) -> dict[str, str]:
    letters = ("A", "B", "C", "D")
    vals = {letters[i]: t for i, t in enumerate(fc.get("events") or ())}
    vax = list(fc.get("vaccines") or ())
    if len(vax) == 1:
        vals["v"] = vax[0]
    elif len(vax) >= 2:
        vals["v1"], vals["v2"] = vax[0], vax[1]
    if fc.get("report_id") is not None:
        vals["r"] = f"VAERS-{fc['report_id']}"
    return vals


def question_row_from_answer(answer_row: Mapping[str, Any], groups: Mapping[str, Any] | None = None,
                             *, register: str = "original", fmt: str = "claim") -> dict:
    """Synthesize the INPUT_FIELDS row of an answer row by rendering its template.

    The original register's claim format names every slot for all 20 shipping
    groups, so the rendered text determines the gold claim -- which is what a
    few-shot pair must show.
    """
    from temporal_hypo.generation.templates import load_groups, render

    groups = groups or load_groups()
    mode = answer_row["mode"]
    gid = GROUP_BY_MODE[mode]
    group = groups[gid]
    fc = answer_row["factual_core"]
    negated = bool(answer_row.get("negated", False))
    text = render(group, register, fmt, _slot_values(fc), negated=negated)
    cohort = answer_row["cohort"]
    return {
        "hypothesis_id": f"{gid}-fewshot-{register}-{fmt}",
        "group_id": gid,
        "level": cohort.get("level", MODE_SPEC[mode].tier),
        "answer_type": MODE_SPEC[mode].answer_type,
        "register": register,
        "format": fmt,
        "text": text,
        "options": answer_row.get("options"),
        "cohort": cohort,
    }


FewshotItem = Any   # (question_row, answer_row) | {"question", "answer"} | merged row | answer row


def fewshot_pairs(examples: Sequence[FewshotItem], *, k: int,
                  groups: Mapping[str, Any] | None = None) -> list[tuple[dict, dict]]:
    """Normalise the caller's few-shot material into (question_row, answer_row) pairs.

    Accepted item shapes: a 2-tuple/list ``(question_row, answer_row)`` (what
    ``scripts/run_eval.py`` builds from ``subsets.fewshot_pool``);
    ``{"question": row, "answer": row}``; a merged row carrying both ``text`` and
    ``factual_core``; or a bare answer row, whose user turn is rendered from its
    template via ``question_row_from_answer``. Items that fit none of these, or
    cannot be rendered, are skipped.
    """
    pairs: list[tuple[dict, dict]] = []
    for ex in examples:
        if len(pairs) >= k:
            break
        try:
            if isinstance(ex, (tuple, list)):
                if len(ex) != 2 or not all(isinstance(x, Mapping) for x in ex):
                    continue
                q, a = dict(ex[0]), dict(ex[1])
            elif not isinstance(ex, Mapping):
                continue
            elif "question" in ex and "answer" in ex:
                q, a = dict(ex["question"]), dict(ex["answer"])
            elif "text" in ex and "factual_core" in ex:
                q, a = dict(ex), dict(ex)
            elif "factual_core" in ex:
                a = dict(ex)
                q = question_row_from_answer(a, groups)
            else:
                continue
        except (KeyError, ValueError):
            continue
        pairs.append((q, a))
    return pairs


# ---------------------------------------------------------------------------
# the extractor
# ---------------------------------------------------------------------------

_REPAIR_INSTRUCTION = (
    "Your previous reply could not be used ({error}). Reply again with ONLY one JSON object "
    "that matches the schema exactly: the category field must be one of {modes}; 'events' must be a list "
    "of the verbatim event terms in the asserted order; 'negated' must be a boolean. "
    "No prose, no code fences."
)


class LLMExtractor:
    """Prompted extraction through a ``Provider`` (see the module docstring)."""

    def __init__(self, client: Provider, model: str, *, procedure_given: bool = False,
                 fewshot: Sequence[Mapping[str, Any]] = (), k_shot: int = 3,
                 vocabulary: set[str] | None = None, temperature: float = 0.0,
                 max_tokens: int = 400, groups: Mapping[str, Any] | None = None,
                 tier_hint: bool = False, routing_hint: bool = False,
                 null_hints: bool = True, frame: str = "catalogue",
                 dataset_card: str | None = None) -> None:
        if frame not in ("catalogue", "toolbox"):
            raise ValueError(f"frame must be 'catalogue' or 'toolbox', got {frame!r}")
        if frame == "toolbox" and not dataset_card:
            raise ValueError("the toolbox frame needs a dataset_card (task_card.dataset_card)")
        self.frame = frame
        self.dataset_card = dataset_card
        self.client = client
        self.model = model
        self.name = (f"llm:{model}" + ("+tier-hint" if tier_hint else "")
                     + ("+routing-hint" if routing_hint else "")
                     + ("" if null_hints else "+no-null-hints")
                     + ("+toolbox" if frame == "toolbox" else ""))
        self.tier_hint = bool(tier_hint)
        self.routing_hint = bool(routing_hint)
        self.null_hints = bool(null_hints)
        self.procedure_given = bool(procedure_given)
        self.fewshot = list(fewshot)
        self.k_shot = int(k_shot)
        self.vocabulary = vocabulary
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self._groups = groups
        self._pairs: list[tuple[dict, dict]] | None = None
        self._system: dict[bool, str] = {}
        # per-call diagnostics (the pipeline logs them)
        self.last_error: str | None = None
        self.last_flat: dict | None = None
        self.last_completions: list[Completion] = []
        self.last_notes: list[str] = []

    # -- prompt --------------------------------------------------------------

    @property
    def schema(self) -> dict:
        if self.frame == "toolbox":
            return PLAN_JSON_SCHEMA
        return WHAT_JSON_SCHEMA if self.procedure_given else FLAT_JSON_SCHEMA

    def _system_message(self, blind_group: bool) -> str:
        if self.frame == "toolbox":
            if blind_group not in self._system:
                self._system[blind_group] = toolbox_system_prompt(
                    dataset_card=self.dataset_card or "", blind_group=blind_group)
            return self._system[blind_group]
        if blind_group not in self._system:
            self._system[blind_group] = system_prompt(tier_hint=self.tier_hint,
                                                      routing_hint=self.routing_hint,
                                                      procedure_given=self.procedure_given, null_hints=self.null_hints,
                                                      blind_group=blind_group)
        return self._system[blind_group]

    def _fewshot(self) -> list[tuple[dict, dict]]:
        if self._pairs is None:
            self._pairs = fewshot_pairs(self.fewshot, k=self.k_shot, groups=self._groups) \
                if self.k_shot > 0 else []
        return self._pairs

    @staticmethod
    def _user_turn(question_row: Mapping[str, Any], *, blind_group: bool) -> str:
        return json.dumps(visible_fields(question_row, blind_group=blind_group),
                          ensure_ascii=False)

    def _assistant_turn(self, question_row: Mapping[str, Any], answer_row: Mapping[str, Any]) -> str:
        from temporal_hypo.framework.claim_schema import from_gold

        gold = from_gold(answer_row)
        if self.frame == "toolbox":
            flat = plan_from_claim(gold)
        else:
            flat = flat_from_claim(gold, include_procedure=not self.procedure_given)
        # a neutral question asserts no option; keep the target coherent with the rule
        if question_row.get("format") == "question" and flat.get("asserted_option") is not None:
            flat["asserted_option"] = None
        return json.dumps(flat, ensure_ascii=False)

    def build_messages(self, question_row: Mapping[str, Any], *, blind_group: bool = False
                       ) -> list[dict]:
        """System + k few-shot (user, assistant) pairs + the row as the final user turn."""
        msgs = [{"role": "system", "content": self._system_message(blind_group)}]
        for q, a in self._fewshot():
            msgs.append({"role": "user", "content": self._user_turn(q, blind_group=blind_group)})
            msgs.append({"role": "assistant", "content": self._assistant_turn(q, a)})
        msgs.append({"role": "user", "content": self._user_turn(question_row, blind_group=blind_group)})
        return msgs

    # -- calls ---------------------------------------------------------------

    def _complete(self, messages: list[dict]) -> Completion:
        c = self.client.complete(messages, schema=self.schema, model=self.model,
                                 temperature=self.temperature, max_tokens=self.max_tokens)
        self.last_completions.append(c)
        return c

    def _check_flat(self, flat: Mapping[str, Any]) -> str | None:
        """A schema-level problem worth a repair retry, or None."""
        if self.frame == "toolbox":
            if flat.get("quantity") not in QUANTITIES:
                return f"unknown quantity {flat.get('quantity')!r}"
            if (flat.get("quantity") == "extreme_of_set"
                    and flat.get("extreme") not in ("earliest", "latest")
                    and flat.get("denominator") not in ("all_present_unique_first",
                                                        "all_present_unique_last")):
                return ("quantity is extreme_of_set but extreme is not set: reply with the same "
                        "plan and extreme = 'earliest' (the claim is about the first/earliest "
                        "event) or 'latest' (the last/latest event)")
        else:
            mode = flat.get("mode")
            if mode not in MODE_SPEC:
                return f"unknown mode {mode!r}"
        ev = flat.get("events")
        if not isinstance(ev, list) or not ev or not all(isinstance(t, str) for t in ev):
            return "events must be a non-empty list of strings"
        return None

    def _ask(self, messages: list[dict]) -> dict:
        """Call, parse, and retry once with a repair instruction on a bad reply."""
        first = self._complete(messages)
        try:
            flat = parse_json_object(first.text)
            self.last_flat = dict(flat)          # kept even if the checks below reject it
            problem = self._check_flat(flat)
            if problem:
                raise ValueError(problem)
            return flat
        except ValueError as exc:
            err = str(exc)
        self.last_notes.append(f"repair retry: {err}")
        repair = messages + [
            {"role": "assistant", "content": first.text},
            {"role": "user", "content": (err + ". " if self.frame == "toolbox" else "")
             + _REPAIR_INSTRUCTION.format(
                error=err, modes=", ".join(QUANTITIES if self.frame == "toolbox" else MODES))},
        ]
        second = self._complete(repair)
        flat = parse_json_object(second.text)          # raises -> caller records None
        self.last_flat = dict(flat)
        problem = self._check_flat(flat)
        if problem:
            raise ValueError(problem)
        return flat

    def extract(self, question_row: Mapping[str, Any], *, blind_group: bool = False
                ) -> StructuredClaim | None:
        """The claim for one question row, or None (reason on ``last_error``)."""
        self.last_error = None
        self.last_flat = None
        self.last_completions = []
        self.last_notes = []
        try:
            messages = self.build_messages(question_row, blind_group=blind_group)
            flat = self._ask(messages)
            self.last_flat = dict(flat)
            terms, oov = snap_terms(flat.get("events") or [], self.vocabulary)
            if oov:
                self.last_notes.append("out-of-vocabulary terms: " + ", ".join(repr(t) for t in oov))
            flat = dict(flat, events=terms)
            self.last_flat = dict(flat)
            if self.frame == "toolbox":
                claim = claim_from_plan(flat, question_row, source=self.name)
            else:
                claim = claim_from_flat(flat, question_row, source=self.name,
                                        procedure_given=self.procedure_given)
            if self.last_notes:
                claim = replace(claim, raw=dict(claim.raw or {}, notes=list(self.last_notes)))
            return claim
        except Exception as exc:  # noqa: BLE001 - any failure is "no parse", logged
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    # -- accounting ----------------------------------------------------------

    @property
    def last_usage(self) -> dict | None:
        """Token totals over the calls of the last ``extract`` (None if unknown)."""
        if not self.last_completions:
            return None
        p = [c.prompt_tokens for c in self.last_completions]
        k = [c.completion_tokens for c in self.last_completions]
        if any(x is None for x in p) or any(x is None for x in k):
            return None
        return {"prompt": sum(p), "completion": sum(k)}

    @property
    def last_tokens(self) -> dict | None:
        """Alias of ``last_usage`` in the prediction row's ``tokens`` shape."""
        return self.last_usage

    @property
    def last_ms(self) -> float:
        return sum(c.ms for c in self.last_completions)

    @property
    def last_cached(self) -> bool:
        return bool(self.last_completions) and all(c.cached for c in self.last_completions)
