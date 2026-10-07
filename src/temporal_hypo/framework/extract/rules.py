"""Rule-based reverse-template parser: hypothesis text -> ``StructuredClaim``.

WHAT. Every released hypothesis was rendered mechanically from one of the 184
template strings in ``data/templates/*.yaml`` (``generation.templates``). This
module inverts that rendering: each template becomes one anchored regex whose
literals are escaped and whose ``{slot}`` placeholders become named capture
groups -- the first occurrence of a slot is ``(?P<X>.+?)``, every repeat is the
backreference ``(?P=X)`` (25 templates name a slot twice, e.g. S-V1
"is {A} -> {B} -> {C} the most common ordering of {A}, {B}, {C}"; a second named
group of the same name would not compile). A match binds the slots; the
bindings are validated (event terms against the DB vocabulary, vaccines against
``VACCINES``, ``{r}`` against ``VAERS-(\\d+)`` and the row's cohort), lossy slots
are filled from the row's structured ``cohort`` / ``options``, and the result is
assembled with ``claim_schema.build_claim`` so the HOW layer is the reference one.

WHY. The parser is the *template-table upper bound* (baseline B0): a Stage-1
method that is exact by construction, so that any error downstream of it is a
retrieval / test / verdict error and not an extraction error. It also gives the
harness a free, model-independent Stage-1 answer for every release row, which is
what the LLM extractors are scored against alongside ``from_gold``.

Design points that matter:

- **Validation is what makes negation detection free.** The negated C-V1/C-V2/
  C-V3 forms differ from the plain ones by a literal ("do not", "NOT", "no more",
  "a minority", "unassociated"). A plain pattern that matches a negated sentence
  can only do so by swallowing the negation into an event slot ("Nausea do not"),
  which is not a vocabulary term. Negated patterns are also tried first, so the
  outcome does not depend on a vocabulary being supplied.
- **Non-greedy is not enough on its own.** A handful of MedDRA terms contain
  ", " or " and " (``Hallucinations, mixed``; ``Drug reaction with eosinophilia
  and systemic symptoms``), and the templates separate slots with exactly those
  strings. When the regex's own binding fails validation, ``iter_bindings``
  enumerates every other way to split the sentence into the template's
  segments, pruned by the same validation, and the first valid split wins.
- **Lossy templates.** Non-original report-tier registers omit ``{r}`` (filled
  from ``cohort.report_id``); the P-M2 clinical claim omits ``{v2}`` (the other
  cohort vaccine); several CHOICE claims name only the asserted event ("In this
  case, {A} came first.") and the remaining candidates are filled from
  ``options`` (the options other than A, in options order -- which is the order
  the release's gold events use). The C-V3 research/clinical wordings and the
  F-V3 research wording never name the events at all: those parse to a claim
  whose missing roles are ``EventSlot(term=None)`` with ``underdetermined`` set
  (2,292 release rows), which the harness answers ``underdetermined``.
- **Two template strings are shared by two groups** ('In this case, {A} came
  first.' P-R2/F-R1; 'In this report, {A} is the earliest of {A}, {B}, {C}.'
  F-R1/F-R3). ``answer_type`` and ``level`` are visible in both input
  conditions and narrow the candidate groups; the remaining P-R2/F-R1 case is
  settled by the option count (a 2-event CHOICE fills one candidate from two
  options, a 3-event one fills two from three -- the wrong group cannot fill
  exactly).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Callable, Iterator, Mapping

from temporal_hypo.framework.claim_schema import (
    MODE_SPEC, ROLES, StructuredClaim, build_claim,
)
from temporal_hypo.framework.extract import visible_fields
from temporal_hypo.generation.cores import MODE_BY_GROUP
from temporal_hypo.generation.templates import (
    FORMATS, NEGATED_FORMATS, REGISTERS, Group, load_groups,
)
from temporal_hypo.generation.vaccines import VACCINES

__all__ = [
    "ARROW", "EVENT_SLOTS", "REPORT_SLOT", "VACCINE_SLOTS", "VAERS_RE",
    "RulesExtractor", "TemplatePattern", "compile_patterns", "iter_bindings",
    "vocabulary_from_db",
]

EVENT_SLOTS: tuple[str, ...] = ROLES                  # A, B, C, D
VACCINE_SLOTS: tuple[str, ...] = ("v", "v1", "v2")
REPORT_SLOT = "r"
# The report reference as `cores.report_ref` renders it.
VAERS_RE = re.compile(r"VAERS-(\d+)")
# The ordering separator `core.answers.answer_key` uses for modal_choice options
# (== answers._ARROW; the S-V3 templates spell it the same way).
ARROW = " → "

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")
# Which cohort vaccine a vaccine slot must name (index into cohort["vaccines"]).
_VACCINE_SLOT_INDEX = {"v": 0, "v1": 0, "v2": 1}
# CHOICE modes whose options ARE the event terms (so unnamed roles fill from them).
_EVENT_OPTION_MODES = frozenset({
    "dir_choice", "rep_dir_choice", "first_choice", "last_choice",
    "rep_first_choice", "rep_last_choice",
    "imm_choice",   # v1.2
})

SlotCheck = Callable[[str, str], bool]


# ---------------------------------------------------------------------------
# patterns
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TemplatePattern:
    """One compiled template: where it came from, its regex, and its shape."""

    group_id: str
    register: str
    fmt: str                       # "question" | "claim"
    negated: bool
    regex: re.Pattern
    slots: tuple[str, ...]         # slot names in order of first appearance
    literal_len: int               # total length of the literal text (specificity)
    template: str                  # the raw template string
    # ("lit", text) | ("slot", name) -- the template split for `iter_bindings`
    segments: tuple[tuple[str, str], ...]

    @property
    def event_slots(self) -> tuple[str, ...]:
        return tuple(s for s in self.slots if s in EVENT_SLOTS)


def _segments(template: str) -> tuple[tuple[str, str], ...]:
    segs: list[tuple[str, str]] = []
    pos = 0
    for m in _PLACEHOLDER_RE.finditer(template):
        if m.start() > pos:
            segs.append(("lit", template[pos:m.start()]))
        segs.append(("slot", m.group(1)))
        pos = m.end()
    if pos < len(template):
        segs.append(("lit", template[pos:]))
    return tuple(segs)


def _regex(segments: tuple[tuple[str, str], ...]) -> re.Pattern:
    seen: set[str] = set()
    parts = ["^"]
    for kind, val in segments:
        if kind == "lit":
            parts.append(re.escape(val))
        elif val in seen:
            parts.append(f"(?P={val})")
        else:
            seen.add(val)
            parts.append(f"(?P<{val}>.+?)")
    parts.append("$")
    return re.compile("".join(parts))


def compile_patterns(groups: Mapping[str, Group]) -> list[TemplatePattern]:
    """One ``TemplatePattern`` per (group, register, format, negated) template.

    Negated forms are included wherever the YAML authors them
    (``question_negated`` / ``claim_negated``). Group order follows ``groups``.
    """
    out: list[TemplatePattern] = []
    for group in groups.values():
        for register in REGISTERS:
            variant = group.variants.get(register) or {}
            for fmt in FORMATS:
                for negated in (False, True):
                    key = NEGATED_FORMATS[fmt] if negated else fmt
                    template = variant.get(key)
                    if template is None:
                        continue
                    segs = _segments(template)
                    slots: list[str] = []
                    for kind, val in segs:
                        if kind == "slot" and val not in slots:
                            slots.append(val)
                    out.append(TemplatePattern(
                        group_id=group.id, register=register, fmt=fmt,
                        negated=negated, regex=_regex(segs), slots=tuple(slots),
                        literal_len=sum(len(v) for k, v in segs if k == "lit"),
                        template=template, segments=segs,
                    ))
    return out


def iter_bindings(pattern: TemplatePattern, text: str,
                  slot_ok: SlotCheck | None = None) -> Iterator[dict[str, str]]:
    """Every way to split ``text`` into ``pattern``'s segments, pruned by ``slot_ok``.

    Exhaustive where the regex is not: the regex commits to one (leftmost,
    shortest) split, which is wrong when a slot value itself contains the
    literal that follows it. Slot values are non-empty; a repeated slot must
    repeat its first value verbatim. ``slot_ok(name, value)`` rejects a value
    before recursion, which keeps the search linear in practice.
    """
    segs = pattern.segments
    n = len(text)

    def rec(i: int, pos: int, bound: dict[str, str]) -> Iterator[dict[str, str]]:
        if i == len(segs):
            if pos == n:
                yield dict(bound)
            return
        kind, val = segs[i]
        if kind == "lit":
            if text.startswith(val, pos):
                yield from rec(i + 1, pos + len(val), bound)
            return
        if val in bound:                       # repeat: must match the first value
            if text.startswith(bound[val], pos):
                yield from rec(i + 1, pos + len(bound[val]), bound)
            return
        nxt = segs[i + 1][1] if i + 1 < len(segs) and segs[i + 1][0] == "lit" else None
        end = pos + 1
        while end <= n:
            if nxt is not None:                # jump to the next place the literal can start
                end = text.find(nxt, end)
                if end < 0:
                    return
            value = text[pos:end]
            if slot_ok is None or slot_ok(val, value):
                bound[val] = value
                yield from rec(i + 1, end, bound)
                del bound[val]
            end += 1

    yield from rec(0, 0, {})


def vocabulary_from_db(conn: sqlite3.Connection) -> set[str]:
    """The event vocabulary: every distinct annotated term (1,660 in medtempo.db)."""
    return {row[0] for row in conn.execute("SELECT DISTINCT term FROM level_terms")}


# ---------------------------------------------------------------------------
# the extractor
# ---------------------------------------------------------------------------

def _pattern_order(p: TemplatePattern) -> tuple:
    """Negated forms first (a plain pattern can swallow a negation into a slot;
    the reverse cannot happen), then the most specific literal first."""
    return (not p.negated, -p.literal_len)


class RulesExtractor:
    """Reverse-template parser implementing the ``Extractor`` protocol.

    ``vocabulary`` is the set of admissible event terms (``vocabulary_from_db``);
    with ``None`` every non-empty span is accepted as an event, which is exact on
    the release except that it relies on pattern ORDER rather than validation to
    reject a plain pattern on a negated sentence.
    """

    name = "rules"

    def __init__(self, groups: Mapping[str, Group] | None = None,
                 vocabulary: set[str] | None = None) -> None:
        self.groups: dict[str, Group] = dict(groups) if groups is not None else load_groups()
        self.vocabulary = set(vocabulary) if vocabulary is not None else None
        self.patterns: list[TemplatePattern] = compile_patterns(self.groups)
        self._by_group: dict[tuple[str, str, str], list[TemplatePattern]] = {}
        self._by_rf: dict[tuple[str, str], list[TemplatePattern]] = {}
        for p in self.patterns:
            self._by_group.setdefault((p.group_id, p.register, p.fmt), []).append(p)
            self._by_rf.setdefault((p.register, p.fmt), []).append(p)
        for lst in list(self._by_group.values()) + list(self._by_rf.values()):
            lst.sort(key=_pattern_order)

    # -- protocol -----------------------------------------------------------

    def extract(self, question_row: Mapping, *, blind_group: bool = False
                ) -> StructuredClaim | None:
        """Parse one question row; ``None`` when no template matches.

        Reads only the fields the condition allows (``visible_fields``). In the
        given-group condition only that group's patterns for the row's
        register/format are tried; blind, every pattern for the register/format
        whose group has the row's ``level`` and ``answer_type``.
        """
        row = visible_fields(question_row, blind_group=blind_group)
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            return None
        text = text.strip()
        cohort = row.get("cohort") or {}
        slot_ok = self._slot_check(cohort)
        for pattern in self.candidates(row, blind_group=blind_group):
            binding = self.bind(pattern, text, slot_ok)
            if binding is None:
                continue
            claim = self._assemble(pattern, binding, row)
            if claim is not None:
                return claim
        return None

    # -- pieces (public so tests and diagnostics can call them) --------------

    def candidates(self, row: Mapping, *, blind_group: bool) -> list[TemplatePattern]:
        """The patterns to try for a (projected) row, most specific first."""
        register, fmt = row.get("register"), row.get("format")
        if not blind_group and "group_id" in row:
            gid = row["group_id"]
            if gid not in self.groups:
                return []
            if register in REGISTERS and fmt in FORMATS:
                return list(self._by_group.get((gid, register, fmt), ()))
            return sorted((p for p in self.patterns if p.group_id == gid), key=_pattern_order)
        if register in REGISTERS and fmt in FORMATS:
            pool = self._by_rf.get((register, fmt), [])
        else:
            pool = sorted(self.patterns, key=_pattern_order)
        level, answer_type = row.get("level"), row.get("answer_type")
        out = []
        for p in pool:
            g = self.groups[p.group_id]
            if level is not None and g.level != level:
                continue
            if answer_type is not None and g.answer_type != answer_type:
                continue
            out.append(p)
        return out

    def bind(self, pattern: TemplatePattern, text: str,
             slot_ok: SlotCheck | None = None) -> dict[str, str] | None:
        """The first VALID slot binding of ``pattern`` on ``text``, or None.

        The regex decides whether any binding exists and supplies the usual one;
        if that binding fails ``slot_ok`` the alternative splits are enumerated.
        """
        m = pattern.regex.match(text)
        if m is None:
            return None
        binding = m.groupdict()
        if slot_ok is None or all(slot_ok(k, v) for k, v in binding.items()):
            return binding
        return next(iter_bindings(pattern, text, slot_ok), None)

    def _slot_check(self, cohort: Mapping) -> SlotCheck:
        vocabulary = self.vocabulary
        cohort_vaccines = [str(v) for v in (cohort.get("vaccines") or ())]
        report_id = cohort.get("report_id")

        def slot_ok(name: str, value: str) -> bool:
            if name in EVENT_SLOTS:
                return vocabulary is None or value in vocabulary
            if name in VACCINE_SLOTS:
                if value not in VACCINES:
                    return False
                if not cohort_vaccines:          # no cohort given: vocabulary only
                    return True
                i = _VACCINE_SLOT_INDEX[name]
                return i < len(cohort_vaccines) and cohort_vaccines[i] == value
            if name == REPORT_SLOT:
                m = VAERS_RE.fullmatch(value)
                if m is None:
                    return False
                return report_id is None or int(m.group(1)) == int(report_id)
            return False                          # a slot the roster does not use ({p})

        return slot_ok

    def _assemble(self, pattern: TemplatePattern, binding: Mapping[str, str],
                  row: Mapping) -> StructuredClaim | None:
        """Bindings + the row's cohort/options -> claim; None if inconsistent."""
        mode = MODE_BY_GROUP[pattern.group_id]
        spec = MODE_SPEC[mode]
        cohort = row.get("cohort") or {}
        options = row.get("options")
        terms: list[str | None] = [binding.get(role) for role in ROLES[: spec.n_events]]

        if spec.answer_type == "CHOICE" and options:
            opts = [str(o) for o in options]
            if mode in _EVENT_OPTION_MODES:
                named = [t for t in terms if t is not None]
                if any(t not in opts for t in named):
                    return None
                # unnamed candidates: the options other than the named ones, in
                # options order (the release's gold events use the same order)
                fill = [o for o in opts if o not in named]
                missing = [i for i, t in enumerate(terms) if t is None]
                if len(fill) != len(missing):
                    return None
                for i, o in zip(missing, fill):
                    terms[i] = o
            elif mode == "modal_choice":
                if None in terms or ARROW.join(terms) not in opts:   # type: ignore[arg-type]
                    return None
            elif mode == "multi_dir_precedes":
                if set(opts) != set(str(v) for v in (cohort.get("vaccines") or ())):
                    return None

        raw = {
            "group_id": pattern.group_id, "register": pattern.register,
            "format": pattern.fmt, "negated": pattern.negated,
            "template": pattern.template, "binding": dict(binding),
        }
        return build_claim(mode, terms, cohort, negated=pattern.negated,
                           options=options, source=self.name, raw=raw)
