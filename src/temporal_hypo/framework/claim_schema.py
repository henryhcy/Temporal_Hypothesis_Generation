"""``StructuredClaim`` -- the Stage-1 output contract shared by every extractor.

Two layers. The WHAT layer is the identity of the claim and must come from the
text: which statistic (``mode``), which events in which asserted order, which
cohort, whether the wording is negated, and -- for CHOICE -- which option the
text asserts. The HOW layer (``Procedure``) is the statistical procedure the
claim requires: the test, the null, the tail, the min-n floor, the number of
arms and the conditioning rule. The HOW layer is a pure function of
``(mode, negated)`` via ``derive_procedure``; extractors may fill it (so the
"null choice" and "test/tail" failure modes are measurable) or leave it to be
derived.

``MODE_SPEC`` is the single table behind everything: it restates the dispatch in
``core.answers`` (``_BINOM_NULL`` / ``_MODAL_RUNNER`` / ``_FISHER`` plus the
``cooc_modal_bool`` special case) and the per-family conditioning rules from
``generation.corpus`` as data. A test asserts it against those sources so it
cannot drift.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping, Sequence

from temporal_hypo.core.min_n import family_floor
from temporal_hypo.core.significance import ALPHA
from temporal_hypo.generation.cores import MODE_BY_GROUP

# ---------------------------------------------------------------------------
# vocabularies
# ---------------------------------------------------------------------------

TIERS = ("report", "vaccine", "multi")
FAMILIES = ("pairwise", "sequence", "first_last")   # == YAML top-level family; C-* are pairwise
PRIMITIVES = ("precedes", "co_occurs", "sequence", "first_last")
ANSWER_TYPES = ("BOOL", "CHOICE")
ROLES = ("A", "B", "C", "D")
TESTS = ("binom_exact", "modal_runner", "fisher_exact")
NULL_KINDS = ("binomial", "two_arm_equality", "none")
STATISTICS = ("conditioned_proportion", "named_vs_runner_up",
              "rate_arm1_vs_arm2", "single_observation")
TAILS = ("greater", "less")
CONDITIONINGS = (
    "ordered_pair",              # both present at DISTINCT levels; co-exist excluded
    "both_present",              # both present; co-exist is the numerator (or a cell)
    "orderable_triple",          # all three present at pairwise-distinct levels
    "all_present_unique_first",  # all candidates present, unique earliest; ties dropped
    "all_present_unique_last",   # all candidates present, unique latest; ties dropped
    "presence_split",            # whole cohort split on presence of A
    "single_report",             # the one report; first-mention levels of the events
)
VERDICTS = ("supported", "refuted", "insufficient")
# The harness's fourth response token: the INPUT does not determine the claim
# (C-V3 research/clinical and F-V3 research never name the events). Distinct
# from `insufficient`, which is a property of the DATA.
UNDERDETERMINED = "underdetermined"
RESPONSES = VERDICTS + (UNDERDETERMINED,)

MODES = tuple(sorted(set(MODE_BY_GROUP.values())))
GROUP_BY_MODE = {m: g for g, m in MODE_BY_GROUP.items()}


@dataclass(frozen=True)
class ModeSpec:
    """Static facts about one mode (statistic key)."""

    mode: str
    tier: str
    family: str
    primitive: str
    answer_type: str
    n_events: int
    arms: int
    conditioning: str
    test: str | None              # None at report tier
    null_kind: str
    statistic: str
    named_cell_kind: str | None   # None | "event" | "ordering" | "relation"

    @property
    def is_report(self) -> bool:
        return self.tier == "report"


def _spec(mode, tier, family, primitive, answer_type, n_events, arms,
          conditioning, test, null_kind, statistic, named_cell_kind=None):
    return ModeSpec(mode, tier, family, primitive, answer_type, n_events, arms,
                    conditioning, test, null_kind, statistic, named_cell_kind)


MODE_SPEC: dict[str, ModeSpec] = {s.mode: s for s in (
    # --- report tier: single deterministic observation, no test -------------
    _spec("rep_dir_bool", "report", "pairwise", "precedes", "BOOL", 2, 1,
          "single_report", None, "none", "single_observation"),
    _spec("rep_dir_choice", "report", "pairwise", "precedes", "CHOICE", 2, 1,
          "single_report", None, "none", "single_observation"),
    _spec("rep_sym_bool", "report", "pairwise", "co_occurs", "BOOL", 2, 1,
          "single_report", None, "none", "single_observation"),
    _spec("rep_seq_bool", "report", "sequence", "sequence", "BOOL", 3, 1,
          "single_report", None, "none", "single_observation"),
    _spec("rep_first_choice", "report", "first_last", "first_last", "CHOICE", 3, 1,
          "single_report", None, "none", "single_observation"),
    _spec("rep_last_choice", "report", "first_last", "first_last", "CHOICE", 3, 1,
          "single_report", None, "none", "single_observation"),
    _spec("rep_first_bool", "report", "first_last", "first_last", "BOOL", 3, 1,
          "single_report", None, "none", "single_observation"),
    # --- single cohort, exact binomial vs 0.5 --------------------------------
    _spec("dir_bool", "vaccine", "pairwise", "precedes", "BOOL", 2, 1,
          "ordered_pair", "binom_exact", "binomial", "conditioned_proportion"),
    _spec("dir_choice", "vaccine", "pairwise", "precedes", "CHOICE", 2, 1,
          "ordered_pair", "binom_exact", "binomial", "conditioned_proportion"),
    _spec("sym_bool_cooccurs", "vaccine", "pairwise", "co_occurs", "BOOL", 2, 1,
          "both_present", "binom_exact", "binomial", "conditioned_proportion"),
    # --- single cohort, modal-vs-runner-up (2-cell binomial vs 0.5) ----------
    _spec("cooc_modal_bool", "vaccine", "pairwise", "co_occurs", "BOOL", 2, 1,
          "both_present", "modal_runner", "binomial", "named_vs_runner_up",
          "relation"),
    _spec("seq_bool", "vaccine", "sequence", "sequence", "BOOL", 3, 1,
          "orderable_triple", "modal_runner", "binomial", "named_vs_runner_up",
          "ordering"),
    _spec("modal_choice", "vaccine", "sequence", "sequence", "CHOICE", 3, 1,
          "orderable_triple", "modal_runner", "binomial", "named_vs_runner_up",
          "ordering"),
    _spec("first_choice", "vaccine", "first_last", "first_last", "CHOICE", 3, 1,
          "all_present_unique_first", "modal_runner", "binomial",
          "named_vs_runner_up", "event"),
    _spec("first_bool", "vaccine", "first_last", "first_last", "BOOL", 3, 1,
          "all_present_unique_first", "modal_runner", "binomial",
          "named_vs_runner_up", "event"),
    _spec("last_choice", "vaccine", "first_last", "first_last", "CHOICE", 3, 1,
          "all_present_unique_last", "modal_runner", "binomial",
          "named_vs_runner_up", "event"),
    # --- two arms / two cohorts, Fisher exact 2x2 -----------------------------
    _spec("antecedent_bool", "vaccine", "pairwise", "precedes", "BOOL", 3, 2,
          "ordered_pair", "fisher_exact", "two_arm_equality", "rate_arm1_vs_arm2"),
    _spec("pairpair_bool", "vaccine", "pairwise", "precedes", "BOOL", 4, 2,
          "ordered_pair", "fisher_exact", "two_arm_equality", "rate_arm1_vs_arm2"),
    _spec("assoc_bool", "vaccine", "pairwise", "co_occurs", "BOOL", 2, 2,
          "presence_split", "fisher_exact", "two_arm_equality", "rate_arm1_vs_arm2"),
    _spec("multi_dir_precedes", "multi", "pairwise", "precedes", "CHOICE", 2, 2,
          "ordered_pair", "fisher_exact", "two_arm_equality", "rate_arm1_vs_arm2"),
)}

assert set(MODE_SPEC) == set(MODES), sorted(set(MODE_SPEC) ^ set(MODES))

# Modes whose wording carries a negated form (the symmetric co-occurs claims).
NEGATABLE_MODES = frozenset({"sym_bool_cooccurs", "assoc_bool", "cooc_modal_bool"})


# ---------------------------------------------------------------------------
# the claim
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EventSlot:
    role: str                 # "A" | "B" | "C" | "D" -- the slot as the TEXT names it
    term: str | None          # verbatim MedDRA term; None => not recoverable from the input


@dataclass(frozen=True)
class CohortSpec:
    vaccine: str | None       # Pfizer | Moderna | Janssen | None (report tier)
    report_id: int | None     # VAERS id (== reports.vaers_id), report tier only


@dataclass(frozen=True)
class NullSpec:
    kind: str                 # binomial | two_arm_equality | none
    p0: float | None          # 0.5 for binomial; None otherwise
    statistic: str            # conditioned_proportion | named_vs_runner_up | rate_arm1_vs_arm2 | single_observation


@dataclass(frozen=True)
class Procedure:
    """The HOW layer: what test the claim requires and how it is run."""

    test: str | None          # binom_exact | modal_runner | fisher_exact | None (report tier)
    null: NullSpec
    claim_tail: str           # "greater" for the plain claim, "less" when negated
    alpha: float
    min_n_floor: int | None   # family floor; None at report tier
    arms: int                 # 1 | 2
    conditioning: str         # one of CONDITIONINGS


def derive_procedure(mode: str, *, negated: bool = False) -> Procedure:
    """The procedure a mode requires -- the reference HOW layer.

    ``claim_tail`` is "greater" for every plain claim (the asserted direction is
    carried by the event/arm ORDER), and "less" when the wording is negated, which
    is exactly the tail swap ``core.answers.oriented_significance`` applies.
    """
    s = MODE_SPEC[mode]
    p0 = 0.5 if s.null_kind == "binomial" else None
    return Procedure(
        test=s.test,
        null=NullSpec(s.null_kind, p0, s.statistic),
        claim_tail="less" if negated else "greater",
        alpha=ALPHA,
        min_n_floor=None if s.is_report else family_floor(s.family),
        arms=s.arms,
        conditioning=s.conditioning,
    )


@dataclass(frozen=True)
class StructuredClaim:
    # WHAT
    tier: str
    family: str
    primitive: str
    mode: str
    events: tuple[EventSlot, ...]        # ORDERED as the text asserts
    cohorts: tuple[CohortSpec, ...]      # 1 (vaccine or report) | 2 (P-M2, v1 then v2)
    negated: bool
    answer_type: str
    options: tuple[str, ...] | None
    asserted_option: str | None          # CHOICE: the option the text asserts (None if unstated)
    # HOW
    procedure: Procedure
    # bookkeeping (never scored)
    source: str = "unknown"              # "rules" | "llm:<model>" | "gold" | ...
    underdetermined: tuple[str, ...] = ()  # roles whose term the input does not determine
    confidence: float | None = None
    raw: dict | None = field(default=None, compare=False)   # extractor's raw output
    plan: dict | None = field(default=None, compare=False)  # toolbox frame: the composed plan (serialized; scored separately)

    # -- derived views -------------------------------------------------------

    @property
    def terms(self) -> tuple[str | None, ...]:
        return tuple(e.term for e in self.events)

    @property
    def spec(self) -> ModeSpec:
        return MODE_SPEC[self.mode]

    @property
    def is_underdetermined(self) -> bool:
        return bool(self.underdetermined) or any(t is None for t in self.terms)

    @property
    def vaccines(self) -> tuple[str, ...]:
        return tuple(c.vaccine for c in self.cohorts if c.vaccine is not None)

    @property
    def report_id(self) -> int | None:
        for c in self.cohorts:
            if c.report_id is not None:
                return c.report_id
        return None

    def named_cell(self):
        """The cell the claim asserts is the mode (argmax modes only).

        Keys must match the ``counts`` dict the oracle sees: a ``tuple[str, ...]``
        ordering for the sequence modes, the named event's term for first/last,
        the string ``"co_exist"`` for C-V3, and None for every other mode.
        """
        kind = self.spec.named_cell_kind
        if kind is None:
            return None
        if kind == "relation":
            return "co_exist"
        if kind == "ordering":
            return tuple(self.terms) if None not in self.terms else None
        return self.terms[0]

    # -- (de)serialisation ---------------------------------------------------

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "StructuredClaim":
        proc = d["procedure"]
        return cls(
            tier=d["tier"], family=d["family"], primitive=d["primitive"],
            mode=d["mode"],
            events=tuple(EventSlot(e["role"], e["term"]) for e in d["events"]),
            cohorts=tuple(CohortSpec(c["vaccine"], c["report_id"]) for c in d["cohorts"]),
            negated=bool(d["negated"]), answer_type=d["answer_type"],
            options=tuple(d["options"]) if d.get("options") is not None else None,
            asserted_option=d.get("asserted_option"),
            procedure=Procedure(
                test=proc["test"],
                null=NullSpec(proc["null"]["kind"], proc["null"]["p0"],
                              proc["null"]["statistic"]),
                claim_tail=proc["claim_tail"], alpha=proc["alpha"],
                min_n_floor=proc["min_n_floor"], arms=proc["arms"],
                conditioning=proc["conditioning"]),
            source=d.get("source", "unknown"),
            underdetermined=tuple(d.get("underdetermined", ())),
            confidence=d.get("confidence"),
            plan=d.get("plan"),
        )

    @classmethod
    def from_json(cls, s: str) -> "StructuredClaim":
        return cls.from_dict(json.loads(s))

    def with_procedure(self, procedure: Procedure) -> "StructuredClaim":
        return replace(self, procedure=procedure)

    def what_key(self) -> tuple:
        """The WHAT layer as a hashable key (for exact-match scoring)."""
        return (self.mode, self.terms, tuple((c.vaccine, c.report_id) for c in self.cohorts),
                self.negated, self.asserted_option)


# ---------------------------------------------------------------------------
# construction helpers
# ---------------------------------------------------------------------------

def _cohorts_from_row_cohort(cohort: Mapping[str, Any]) -> tuple[CohortSpec, ...]:
    """The question/answer row's structured ``cohort`` block -> CohortSpec tuple."""
    if cohort.get("report_id") is not None:
        return (CohortSpec(None, int(cohort["report_id"])),)
    return tuple(CohortSpec(v, None) for v in cohort.get("vaccines") or ())


def asserted_option_for(mode: str, terms: Sequence[str | None],
                        vaccines: Sequence[str]) -> str | None:
    """The option a CHOICE claim's text asserts, given its oriented slots.

    dir_choice / rep_dir_choice / first/last choice: the first-named event;
    modal_choice: the asserted ordering joined by the templates' arrow;
    multi_dir_precedes: the first-named vaccine. None for BOOL modes.
    """
    s = MODE_SPEC[mode]
    if s.answer_type != "CHOICE":
        return None
    if mode == "multi_dir_precedes":
        return vaccines[0] if vaccines else None
    if mode == "modal_choice":
        return None if None in terms else " → ".join(terms)  # answers._ARROW
    return terms[0] if terms else None


def build_claim(mode: str, terms: Sequence[str | None], cohort: Mapping[str, Any],
                *, negated: bool = False, options: Sequence[str] | None = None,
                source: str = "unknown", procedure: Procedure | None = None,
                underdetermined: Sequence[str] = (), confidence: float | None = None,
                raw: dict | None = None) -> StructuredClaim:
    """Assemble a claim from its WHAT-layer parts; the HOW layer is derived unless given."""
    s = MODE_SPEC[mode]
    terms = tuple(terms)
    if len(terms) != s.n_events:
        raise ValueError(f"{mode} takes {s.n_events} events, got {len(terms)}: {terms}")
    cohorts = _cohorts_from_row_cohort(cohort)
    events = tuple(EventSlot(ROLES[i], t) for i, t in enumerate(terms))
    und = tuple(underdetermined) or tuple(e.role for e in events if e.term is None)
    vaccines = tuple(c.vaccine for c in cohorts if c.vaccine)
    return StructuredClaim(
        tier=s.tier, family=s.family, primitive=s.primitive, mode=mode,
        events=events, cohorts=cohorts, negated=bool(negated),
        answer_type=s.answer_type,
        options=tuple(options) if options is not None else None,
        asserted_option=asserted_option_for(mode, terms, vaccines),
        procedure=procedure or derive_procedure(mode, negated=negated),
        source=source, underdetermined=und, confidence=confidence, raw=raw,
    )


def from_gold(answer_row: Mapping[str, Any]) -> StructuredClaim:
    """The gold claim of a release answer row -- the reference every extractor is scored against.

    ``factual_core.events`` is the ORIENTED event tuple (as the text names it), and
    ``cohort`` is the structured scope shared with the question side.
    """
    fc = answer_row["factual_core"]
    return build_claim(
        answer_row["mode"], fc["events"], answer_row["cohort"],
        negated=bool(answer_row.get("negated", False)),
        options=answer_row.get("options"), source="gold",
    )


# ---------------------------------------------------------------------------
# validation (records inconsistencies; never auto-corrects)
# ---------------------------------------------------------------------------

def validate(claim: StructuredClaim) -> list[str]:
    """Inconsistencies between the claim's layers and the mode's spec.

    These are recorded as the "null choice / test-tail / gate" signal, not fixed
    silently -- a model that names the wrong test must be scored as such.
    """
    problems: list[str] = []
    if claim.mode not in MODE_SPEC:
        return [f"unknown mode {claim.mode!r}"]
    s = claim.spec
    ref = derive_procedure(claim.mode, negated=claim.negated)
    p = claim.procedure
    if claim.tier != s.tier:
        problems.append(f"tier {claim.tier!r} != {s.tier!r}")
    if claim.family != s.family:
        problems.append(f"family {claim.family!r} != {s.family!r}")
    if claim.primitive != s.primitive:
        problems.append(f"primitive {claim.primitive!r} != {s.primitive!r}")
    if claim.answer_type != s.answer_type:
        problems.append(f"answer_type {claim.answer_type!r} != {s.answer_type!r}")
    if len(claim.events) != s.n_events:
        problems.append(f"{len(claim.events)} events, mode takes {s.n_events}")
    want_cohorts = 2 if claim.mode == "multi_dir_precedes" else 1
    if len(claim.cohorts) != want_cohorts:
        problems.append(f"{len(claim.cohorts)} cohorts, mode takes {want_cohorts}")
    if claim.negated and claim.mode not in NEGATABLE_MODES:
        problems.append(f"negated wording does not exist for {claim.mode}")
    if p.test != ref.test:
        problems.append(f"test {p.test!r} != {ref.test!r}")
    if p.null != ref.null:
        problems.append(f"null {p.null} != {ref.null}")
    if p.claim_tail != ref.claim_tail:
        problems.append(f"claim_tail {p.claim_tail!r} != {ref.claim_tail!r}")
    if p.min_n_floor != ref.min_n_floor:
        problems.append(f"min_n_floor {p.min_n_floor!r} != {ref.min_n_floor!r}")
    if p.arms != ref.arms:
        problems.append(f"arms {p.arms} != {ref.arms}")
    if p.conditioning != ref.conditioning:
        problems.append(f"conditioning {p.conditioning!r} != {ref.conditioning!r}")
    if abs(p.alpha - ref.alpha) > 1e-12:
        problems.append(f"alpha {p.alpha} != {ref.alpha}")
    if claim.answer_type == "CHOICE" and claim.options and claim.asserted_option is not None \
            and claim.asserted_option not in claim.options:
        problems.append(f"asserted_option {claim.asserted_option!r} not in options")
    return problems


# ---------------------------------------------------------------------------
# JSON schema for structured-output extraction (the flat LLM-facing shape)
# ---------------------------------------------------------------------------

# The LLM emits the WHAT layer plus (optionally) the HOW layer in this flat
# form; `claim_from_flat` folds it into a StructuredClaim using the question
# row's structured `cohort` / `options` (cohort identification is given, not
# under test -- see 11_model_pipeline.md §2).
FLAT_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "mode": {"type": "string", "enum": list(MODES)},
        "events": {"type": "array", "items": {"type": "string"},
                   "minItems": 2, "maxItems": 4,
                   "description": "The event terms IN THE ORDER THE CLAIM ASSERTS (A, B[, C[, D]]). Use the exact spelling from the text."},
        "negated": {"type": "boolean",
                    "description": "true only if the wording asserts the NEGATION of the claim (e.g. 'do NOT typically co-occur')."},
        "asserted_option": {"type": ["string", "null"],
                            "description": "For CHOICE claims: the option the text asserts; null if the text is a neutral question."},
        "test": {"type": ["string", "null"], "enum": list(TESTS) + [None]},
        "null_kind": {"type": ["string", "null"], "enum": list(NULL_KINDS) + [None]},
        "p0": {"type": ["number", "null"]},
        "claim_tail": {"type": ["string", "null"], "enum": list(TAILS) + [None]},
        "arms": {"type": ["integer", "null"], "enum": [1, 2, None]},
        "conditioning": {"type": ["string", "null"], "enum": list(CONDITIONINGS) + [None]},
        "min_n_floor": {"type": ["integer", "null"]},
    },
    "required": ["mode", "events", "negated"],
    "additionalProperties": False,
}


def claim_from_flat(flat: Mapping[str, Any], question_row: Mapping[str, Any], *,
                    source: str, procedure_given: bool = False) -> StructuredClaim:
    """Fold a flat extractor output into a StructuredClaim.

    Missing HOW fields are filled from ``derive_procedure`` and the claim records
    which ones the extractor actually supplied (``raw``); with
    ``procedure_given=True`` the whole HOW layer is overridden by the reference
    (the "test-given-in-prompt" evaluation mode).
    """
    mode = flat["mode"]
    if mode not in MODE_SPEC:
        raise ValueError(f"unknown mode {mode!r}")
    s = MODE_SPEC[mode]
    terms = list(flat.get("events") or [])
    # pad / trim to the mode's arity so a wrong-arity answer is still a claim
    # (and is then scored as wrong on the slots it invented or dropped)
    terms = (terms + [None] * s.n_events)[: s.n_events]
    negated = bool(flat.get("negated", False))
    ref = derive_procedure(mode, negated=negated)
    if procedure_given:
        proc = ref
    else:
        null_kind = flat.get("null_kind") or ref.null.kind
        p0 = flat.get("p0", ref.null.p0 if flat.get("null_kind") is None else flat.get("p0"))
        proc = Procedure(
            test=flat.get("test", ref.test) if "test" in flat else ref.test,
            null=NullSpec(null_kind, p0, ref.null.statistic),
            claim_tail=flat.get("claim_tail") or ref.claim_tail,
            alpha=ALPHA,
            min_n_floor=flat.get("min_n_floor", ref.min_n_floor) if "min_n_floor" in flat else ref.min_n_floor,
            arms=flat.get("arms") or ref.arms,
            conditioning=flat.get("conditioning") or ref.conditioning,
        )
    claim = build_claim(mode, terms, question_row["cohort"], negated=negated,
                        options=question_row.get("options"), source=source,
                        procedure=proc, raw=dict(flat))
    if flat.get("asserted_option") is not None and s.answer_type == "CHOICE":
        claim = replace(claim, asserted_option=flat["asserted_option"])
    return claim


# ---------------------------------------------------------------------------
# the PLAN -- S1's output under the toolbox frame (11 §13.3, issues 29/31)
# ---------------------------------------------------------------------------
#
# Under the toolbox frame the model never sees a mode name. It COMPOSES the
# procedure from primitives: what quantity the claim compares, over which
# denominator, against which null (as a recipe), with which test family and
# selection rule. ``derive_mode`` is the reverse lookup that turns a composed
# plan back into the mode the rest of the pipeline (S2 compiler, S3 oracle)
# is keyed on -- the inverse of ``derive_procedure``. The tier is taken from
# the input row's ``level`` (a GIVEN field), never inferred.

# The quantity is WHAT is measured; ``arms`` says whether it is compared across
# two groups (v2, 2026-09-30: "rate_across_two_arms" conflated the two and was
# the largest source of no-shape plans in the first toolbox smoke).
QUANTITIES = (
    "order_of_pair",              # is A before B (one direction of an ordered pair)
    "co_occurrence_of_pair",      # do A and B occur together (same level / same report)
    "dominant_relation_of_pair",  # is co-existence the most common relation of A,B
    "ordering_of_triple",         # is A->B->C the most common strict ordering
    "extreme_of_set",             # is the named candidate most often the earliest/latest
)
_LEGACY_QUANTITY = "rate_across_two_arms"
EXTREMES = ("earliest", "latest")
PLAN_NULL_KINDS = ("symmetric_fixed", "text_stated", "data_derived",
                   "two_arm_equality", "none")
TEST_FAMILIES = ("proportion_vs_p0", "named_vs_runner_up", "two_proportions", "none")
TEST_RULES = ("exact_always", "exact_if_small_else_asymptotic")

# (quantity, extreme) per mode -- the two plan fields the structural spec lacks.
PLAN_BY_MODE: dict[str, tuple[str, str | None]] = {
    "rep_dir_bool": ("order_of_pair", None), "rep_dir_choice": ("order_of_pair", None),
    "dir_bool": ("order_of_pair", None), "dir_choice": ("order_of_pair", None),
    "rep_sym_bool": ("co_occurrence_of_pair", None),
    "sym_bool_cooccurs": ("co_occurrence_of_pair", None),
    "cooc_modal_bool": ("dominant_relation_of_pair", None),
    "rep_seq_bool": ("ordering_of_triple", None), "seq_bool": ("ordering_of_triple", None),
    "modal_choice": ("ordering_of_triple", None),
    "rep_first_choice": ("extreme_of_set", "earliest"),
    "rep_first_bool": ("extreme_of_set", "earliest"),
    "first_choice": ("extreme_of_set", "earliest"), "first_bool": ("extreme_of_set", "earliest"),
    "rep_last_choice": ("extreme_of_set", "latest"), "last_choice": ("extreme_of_set", "latest"),
    "antecedent_bool": ("order_of_pair", None),      # arms 2
    "pairpair_bool": ("order_of_pair", None),        # arms 2
    "assoc_bool": ("co_occurrence_of_pair", None),   # arms 2, presence_split
    "multi_dir_precedes": ("order_of_pair", None),   # arms 2, tier multi
}
assert set(PLAN_BY_MODE) == set(MODES), sorted(set(PLAN_BY_MODE) ^ set(MODES))

_TEST_TO_FAMILY = {"binom_exact": "proportion_vs_p0", "modal_runner": "named_vs_runner_up",
                   "fisher_exact": "two_proportions", None: "none"}
_FAMILY_TO_TEST = {v: k for k, v in _TEST_TO_FAMILY.items()}


def plan_signature(tier: str, answer_type: str, n_events: int, arms: int,
                   conditioning: str, quantity: str, extreme: str | None) -> tuple:
    return (tier, answer_type, int(n_events), int(arms), conditioning, quantity, extreme)


def _build_mode_by_signature() -> dict[tuple, str]:
    table: dict[tuple, str] = {}
    for m, s in MODE_SPEC.items():
        q, x = PLAN_BY_MODE[m]
        key = plan_signature(s.tier, s.answer_type, s.n_events, s.arms, s.conditioning, q, x)
        assert key not in table, f"plan signature clash: {table[key]} / {m}"
        table[key] = m
    return table


MODE_BY_SIGNATURE: dict[tuple, str] = _build_mode_by_signature()


def normalize_plan_shape(tier: str, answer_type: str, n_events: int, arms: int | None,
                         conditioning: str | None, quantity: str | None,
                         extreme: str | None) -> tuple:
    """Fill plan fields that other plan fields (or the given tier) already IMPLY.

    Nothing here consults the answer: a presence split is two arms by definition,
    the first/last denominators name their extreme, a single report has one arm,
    and the legacy quantity "rate_across_two_arms" is "the pair's quantity,
    compared across two arms". Everything not implied stays as emitted.
    """
    arms = int(arms) if arms is not None else 1
    if quantity == _LEGACY_QUANTITY:
        arms = 2
        quantity = "co_occurrence_of_pair" if conditioning == "presence_split" else "order_of_pair"
    if conditioning == "presence_split":
        arms = 2
    if tier == "report":
        arms = 1
    if quantity == "extreme_of_set" and extreme is None:
        extreme = {"all_present_unique_first": "earliest",
                   "all_present_unique_last": "latest"}.get(conditioning or "")
    if quantity != "extreme_of_set":
        extreme = None
    return plan_signature(tier, answer_type, n_events, arms, conditioning, quantity, extreme)


def derive_mode(tier: str, answer_type: str, n_events: int, arms: int | None,
                conditioning: str | None, quantity: str | None,
                extreme: str | None = None) -> str | None:
    """The mode a composed plan corresponds to, or None if no mode has that shape."""
    return MODE_BY_SIGNATURE.get(
        normalize_plan_shape(tier, answer_type, n_events, arms, conditioning, quantity, extreme))


def derive_plan(mode: str, *, negated: bool = False) -> dict:
    """The reference plan for a mode (few-shot targets; inverse of ``derive_mode``)."""
    s = MODE_SPEC[mode]
    proc = derive_procedure(mode, negated=negated)
    q, x = PLAN_BY_MODE[mode]
    if s.is_report:
        null_kind = "none"
    elif s.null_kind == "two_arm_equality":
        null_kind = "two_arm_equality"
    else:
        null_kind = "symmetric_fixed"
    fam = _TEST_TO_FAMILY[proc.test]
    return {
        "quantity": q,
        "extreme": x,
        "arms": s.arms,
        "denominator": s.conditioning,
        "null_kind": null_kind,
        "p0": proc.null.p0,
        "null_reference": None,
        "tail": proc.claim_tail,
        "test_family": fam,
        "test_rule": ("exact_if_small_else_asymptotic" if fam == "two_proportions"
                      else "exact_always"),
        "min_n_floor": proc.min_n_floor,
    }


PLAN_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "events": FLAT_JSON_SCHEMA["properties"]["events"],
        "negated": FLAT_JSON_SCHEMA["properties"]["negated"],
        "asserted_option": FLAT_JSON_SCHEMA["properties"]["asserted_option"],
        "quantity": {"type": "string", "enum": list(QUANTITIES),
                     "description": "WHAT is measured (the arms field says whether it is compared across two groups)."},
        "extreme": {"type": ["string", "null"], "enum": list(EXTREMES) + [None],
                    "description": "REQUIRED when quantity is extreme_of_set: earliest or latest. null for every other quantity."},
        "arms": {"type": "integer", "enum": [1, 2],
                 "description": "1 = one population (or one report); 2 = the quantity is COMPARED between two groups: two vaccine cohorts, reports with vs without an event, or two event pairs."},
        "denominator": {"type": "string", "enum": list(CONDITIONINGS),
                        "description": "Which reports the statistic is computed over (a primitive from the conventions)."},
        "null_kind": {"type": "string", "enum": list(PLAN_NULL_KINDS)},
        "p0": {"type": ["number", "null"],
               "description": "The null proportion when it is a fixed number (symmetric or stated in the text); null when computed from the data or not a proportion."},
        "null_reference": {"type": ["string", "null"],
                           "description": "For a data-derived null: the population the reference rate is computed over."},
        "tail": {"type": "string", "enum": list(TAILS)},
        "test_family": {"type": "string", "enum": list(TEST_FAMILIES)},
        "test_rule": {"type": "string", "enum": list(TEST_RULES),
                      "description": "How the concrete test is chosen once n is known."},
        "min_n_floor": {"type": ["integer", "null"]},
    },
    "required": ["events", "negated", "quantity", "arms", "denominator", "null_kind",
                 "tail", "test_family", "test_rule"],
    "additionalProperties": False,
}


def plan_from_claim(claim: StructuredClaim) -> dict:
    """The plan JSON the toolbox frame asks for, rendered from a claim (few-shot targets)."""
    plan = {
        "events": [t for t in claim.terms],
        "negated": bool(claim.negated),
        "asserted_option": claim.asserted_option if claim.answer_type == "CHOICE" else None,
    }
    plan.update(derive_plan(claim.mode, negated=claim.negated))
    return plan


def claim_from_plan(plan: Mapping[str, Any], question_row: Mapping[str, Any], *,
                    source: str) -> StructuredClaim:
    """Fold a composed plan into a StructuredClaim via ``derive_mode``.

    The tier comes from the row's ``level`` (given). Raises ``ValueError`` when
    the plan's shape matches no mode -- the caller records it as no-claim; the
    plan itself is kept in ``raw`` so its fields can be scored independently.
    """
    tier = question_row.get("level")
    answer_type = question_row.get("answer_type")
    terms = [t for t in (plan.get("events") or [])]
    mode = derive_mode(tier, answer_type, len(terms), plan.get("arms"),
                       plan.get("denominator"), plan.get("quantity"), plan.get("extreme"))
    if mode is None:
        raise ValueError(
            f"no mode for plan shape tier={tier} answer_type={answer_type} n_events={len(terms)} "
            f"arms={plan.get('arms')} denominator={plan.get('denominator')} "
            f"quantity={plan.get('quantity')} extreme={plan.get('extreme')}")
    s = MODE_SPEC[mode]
    negated = bool(plan.get("negated", False))
    ref = derive_procedure(mode, negated=negated)
    fam = plan.get("test_family")
    test = _FAMILY_TO_TEST.get(fam, ref.test)
    nk = plan.get("null_kind")
    if nk in ("symmetric_fixed", "text_stated", "data_derived"):
        null = NullSpec("binomial", plan.get("p0"), ref.null.statistic)
    elif nk == "two_arm_equality":
        null = NullSpec("two_arm_equality", None, ref.null.statistic)
    elif nk == "none":
        null = NullSpec("none", None, ref.null.statistic)
    else:
        null = ref.null
    proc = Procedure(
        test=test, null=null,
        claim_tail=plan.get("tail") or ref.claim_tail, alpha=ALPHA,
        min_n_floor=plan.get("min_n_floor", ref.min_n_floor),
        arms=int(plan.get("arms") or ref.arms),
        conditioning=plan.get("denominator") or ref.conditioning,
    )
    claim = build_claim(mode, terms, question_row["cohort"], negated=negated,
                        options=question_row.get("options"), source=source,
                        procedure=proc, raw=dict(plan))
    claim = replace(claim, plan=dict(plan))
    if plan.get("asserted_option") is not None and s.answer_type == "CHOICE":
        claim = replace(claim, asserted_option=plan["asserted_option"])
    return claim
