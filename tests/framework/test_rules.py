"""Tests for the rule-based reverse-template parser (``framework/extract/rules.py``).

Fast tests render every one of the 184 template strings with slot values drawn
from the synthetic CORPUS and round-trip them through the parser in both input
conditions; the release-wide check (``slow`` + ``needs_release``) parses every
question row and compares it with ``from_gold``.
"""

from __future__ import annotations

import collections
import gzip
import itertools
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pytest

from temporal_hypo.core.answers import _ARROW
from temporal_hypo.framework.claim_schema import MODE_SPEC, ROLES, build_claim, from_gold
from temporal_hypo.core.pseudonym import report_ref
from temporal_hypo.framework.extract.rules import (
    ARROW, RulesExtractor, compile_patterns, iter_bindings, vocabulary_from_db,
)
from temporal_hypo.generation.cores import MODE_BY_GROUP
from temporal_hypo.generation.templates import (
    FORMATS, NEGATED_FORMATS, REGISTERS, load_groups, render,
)
from tests.framework.conftest import (
    CORPUS, RELEASE_DIR, RELEASE_STEM, REPO_ROOT, needs_release,
)

# slot values: A, B, C, D from the CORPUS terms; the CORPUS as vocabulary
EVENTS = ("Headache", "Fatigue", "Pyrexia", "Rash")
VOCAB = {t for _, _, levels in CORPUS for level in levels for t in level}
REPORT_ID = 1001
N_TEMPLATES = 280   # 184 v1.1 strings + 96 v1.2 (nine groups x 8, plus 24 negated forms)

# The templates that never name the events they are about (documented in the
# plan and the harness brief): C-V3 research + clinical in all four forms, and
# F-V3 research question + claim.  (group, register, format, negated) -> roles.
UNDERDETERMINED_TEMPLATES: dict[tuple[str, str, str, bool], tuple[str, ...]] = {
    **{("C-V3", r, f, n): ("A", "B")
       for r in ("research", "clinical") for f in FORMATS for n in (False, True)},
    **{("F-V3", "research", f, False): ("B", "C") for f in FORMATS},
}
RELEASE_UNDERDETERMINED = {(g, r, f) for (g, r, f, _n) in UNDERDETERMINED_TEMPLATES}


@dataclass(frozen=True)
class Case:
    group_id: str
    register: str
    fmt: str
    negated: bool
    row: dict
    mode: str
    expected_terms: tuple[str | None, ...]
    names_all_events: bool      # every event role appears in the template text


def _options(mode: str, events: tuple[str, ...], vaccines: list[str]) -> list[str] | None:
    """Options shaped like ``core.answers.answer_key`` -- in a NON-text order where
    that is possible, as a refuted CHOICE row would carry them."""
    spec = MODE_SPEC[mode]
    if spec.answer_type != "CHOICE":
        return None
    if mode == "multi_dir_precedes":
        return list(vaccines)
    if mode == "modal_choice":
        return [ARROW.join(p) for p in itertools.permutations(events)]
    if spec.n_events == 2:
        return [events[1], events[0]]
    return [events[1], events[0], events[2]]        # B, A, C: B/C keep their order


def cases(groups) -> Iterator[Case]:
    """One Case per template string (184), rendered with the fixture slots."""
    for g in groups.values():
        mode = MODE_BY_GROUP[g.id]
        n = MODE_SPEC[mode].n_events
        events = EVENTS[:n]
        if g.level == "report":
            vaccines: list[str] = []
            cohort = {"level": "report", "vaccines": [], "report_id": REPORT_ID}
        elif g.level == "multi":
            vaccines = ["Pfizer", "Moderna"]
            cohort = {"level": "multi", "vaccines": vaccines, "report_id": None}
        else:
            vaccines = ["Pfizer"]
            cohort = {"level": "vaccine", "vaccines": vaccines, "report_id": None}
        values = {ROLES[i]: e for i, e in enumerate(events)}
        values["r"] = report_ref(REPORT_ID)
        if len(vaccines) == 1:
            values["v"] = vaccines[0]
        elif len(vaccines) == 2:
            values["v1"], values["v2"] = vaccines
        options = _options(mode, events, vaccines)
        for register in REGISTERS:
            for fmt in FORMATS:
                for negated in (False, True):
                    if negated and NEGATED_FORMATS[fmt] not in g.variants[register]:
                        continue
                    template = g.variants[register][NEGATED_FORMATS[fmt] if negated else fmt]
                    text = render(g, register, fmt, values, negated=negated)
                    row = {
                        "hypothesis_id": f"{g.id}-0000-{register}-{fmt}",
                        "group_id": g.id, "level": g.level, "answer_type": g.answer_type,
                        "register": register, "format": fmt, "text": text,
                        "options": options, "cohort": cohort,
                    }
                    missing = UNDERDETERMINED_TEMPLATES.get((g.id, register, fmt, negated), ())
                    expected = tuple(None if ROLES[i] in missing else e for i, e in enumerate(events))
                    names_all = all(f"{{{ROLES[i]}}}" in template for i in range(n))
                    yield Case(g.id, register, fmt, negated, row, mode, expected, names_all)


def _blind(row: dict) -> dict:
    """A row as the blind-group condition sees it -- and with a decoy group id
    so a parser that peeked would be caught."""
    out = dict(row)
    out["group_id"] = "P-R1" if row["group_id"] != "P-R1" else "F-V3"
    out["hypothesis_id"] = "opaque"
    return out


def _key(claim):
    return (claim.mode, claim.terms, claim.negated)


@pytest.fixture(scope="module")
def extractor(groups):
    return RulesExtractor(groups, VOCAB)


@pytest.fixture(scope="module")
def all_cases(groups):
    return list(cases(groups))


# ---------------------------------------------------------------------------
# compile
# ---------------------------------------------------------------------------

def test_compile_patterns_shape(groups):
    pats = compile_patterns(groups)
    assert len(pats) == N_TEMPLATES
    assert len({p.template for p in pats}) == N_TEMPLATES - 2          # two shared strings
    # 59 distinct strings repeat a slot (one of them is the F-R1/F-R3 shared string);
    # v1.2 added 34 (Y-V1 and H-V5 name {A} twice in every form, Y-V2 in most,
    # H-V1 in the three non-original registers since the 2026-10-08 rewording)
    assert len({p.template for p in pats if "(?P=" in p.regex.pattern}) == 59
    assert sum("(?P=" in p.regex.pattern for p in pats) == 60
    assert sum(p.negated for p in pats) == 6 * len(REGISTERS) * len(FORMATS)   # C-V1/2/3 + T-V1/Y-V1/Y-V3
    for p in pats:
        assert p.regex.pattern.startswith("^") and p.regex.pattern.endswith("$")
        assert p.literal_len > 0
        assert set(p.slots) <= {"A", "B", "C", "D", "v", "v1", "v2", "r"}
    shared = collections.Counter(p.template for p in pats)
    assert {t for t, c in shared.items() if c > 1} == {
        "In this case, {A} came first.",
        "In this report, {A} is the earliest of {A}, {B}, {C}.",
    }


def test_arrow_matches_answer_key():
    assert ARROW == _ARROW


def test_vocabulary_from_db(raw_conn):
    assert vocabulary_from_db(raw_conn) == VOCAB


def test_fixture_covers_every_template(all_cases):
    assert len(all_cases) == N_TEMPLATES


# ---------------------------------------------------------------------------
# (1) given-group round trip, (2) blind-group round trip
# ---------------------------------------------------------------------------

def test_given_group_round_trip(extractor, all_cases):
    failures = []
    for c in all_cases:
        claim = extractor.extract(c.row)
        if claim is None or _key(claim) != (c.mode, c.expected_terms, c.negated):
            failures.append((c.group_id, c.register, c.fmt, c.negated, c.row["text"],
                             None if claim is None else _key(claim)))
            continue
        assert claim.source == "rules"
        assert claim.raw["group_id"] == c.group_id
        # the whole WHAT layer equals what gold would build from the same parts
        gold = build_claim(c.mode, c.expected_terms, c.row["cohort"], negated=c.negated,
                           options=c.row["options"], source="gold")
        assert claim.what_key() == gold.what_key()
        assert claim.procedure == gold.procedure
    assert not failures, failures


def test_blind_group_round_trip(extractor, all_cases):
    failures = []
    for c in all_cases:
        claim = extractor.extract(_blind(c.row), blind_group=True)
        if claim is None or _key(claim) != (c.mode, c.expected_terms, c.negated):
            failures.append((c.group_id, c.register, c.fmt, c.negated, c.row["text"],
                             None if claim is None else _key(claim)))
    assert not failures, failures


def test_blind_group_never_reads_group_id(extractor, all_cases):
    for c in all_cases:
        row = {k: v for k, v in c.row.items() if k not in ("group_id", "hypothesis_id")}
        claim = extractor.extract(row, blind_group=True)
        assert claim is not None and _key(claim) == (c.mode, c.expected_terms, c.negated)


def test_shared_strings_resolved_by_answer_type_and_options(extractor):
    report = {"level": "report", "vaccines": [], "report_id": 7}
    base = {"level": "report", "register": "media", "format": "claim",
            "text": "In this case, Chills came first.", "cohort": report}
    two = extractor.extract({**base, "answer_type": "CHOICE",
                             "options": ["Nausea", "Chills"]}, blind_group=True)
    three = extractor.extract({**base, "answer_type": "CHOICE",
                               "options": ["Nausea", "Chills", "Headache"]}, blind_group=True)
    assert two.mode == "rep_dir_choice" and two.terms == ("Chills", "Nausea")
    assert three.mode == "rep_first_choice" and three.terms == ("Chills", "Nausea", "Headache")

    text = "In this report, Chills is the earliest of Chills, Nausea, Headache."
    base = {"level": "report", "register": "research", "format": "claim", "text": text,
            "cohort": report}
    choice = extractor.extract({**base, "answer_type": "CHOICE",
                                "options": ["Nausea", "Chills", "Headache"]}, blind_group=True)
    boolean = extractor.extract({**base, "answer_type": "BOOL", "options": None},
                                blind_group=True)
    assert choice.mode == "rep_first_choice" and boolean.mode == "rep_first_bool"
    assert choice.terms == boolean.terms == ("Chills", "Nausea", "Headache")


# ---------------------------------------------------------------------------
# (3) option-permutation invariance
# ---------------------------------------------------------------------------

def test_option_permutation_invariance(extractor, all_cases):
    for c in all_cases:
        if c.row["options"] is None:
            continue
        base = extractor.extract(c.row)
        for perm in itertools.permutations(c.row["options"]):
            row = {**c.row, "options": list(perm)}
            for blind in (False, True):
                claim = extractor.extract(_blind(row) if blind else row, blind_group=blind)
                assert claim is not None, (c.group_id, c.register, c.fmt, perm)
                # the claim's identity never depends on how the options are listed
                assert (claim.mode, claim.negated, claim.asserted_option, claim.cohorts,
                        claim.terms[0], frozenset(claim.terms), claim.procedure) == \
                       (base.mode, base.negated, base.asserted_option, base.cohorts,
                        base.terms[0], frozenset(base.terms), base.procedure)
                if c.names_all_events:
                    assert claim.what_key() == base.what_key()
                else:
                    # unnamed candidates follow the options order (== the gold order)
                    assert list(claim.terms[1:]) == [o for o in perm if o != claim.terms[0]]


# ---------------------------------------------------------------------------
# (4) the underdetermined set
# ---------------------------------------------------------------------------

def test_underdetermined_set_is_exactly_documented(extractor, all_cases):
    found = {}
    for c in all_cases:
        claim = extractor.extract(c.row)
        if claim.is_underdetermined:
            found[(c.group_id, c.register, c.fmt, c.negated)] = claim.underdetermined
            assert claim.mode == c.mode and claim.negated == c.negated
            assert all((e.term is None) == (e.role in claim.underdetermined) for e in claim.events)
    assert found == UNDERDETERMINED_TEMPLATES
    assert len(found) == 10


# ---------------------------------------------------------------------------
# validation, negation, awkward vocabulary
# ---------------------------------------------------------------------------

def test_negation_detected_without_vocabulary(groups):
    ex = RulesExtractor(groups)          # no vocabulary: ordering alone must do it
    for c in cases(groups):
        if c.group_id not in ("C-V1", "C-V2", "C-V3"):
            continue
        for blind in (False, True):
            claim = ex.extract(_blind(c.row) if blind else c.row, blind_group=blind)
            assert claim is not None
            assert _key(claim) == (c.mode, c.expected_terms, c.negated), (c, blind)


def test_terms_containing_template_literals(groups):
    vocab = VOCAB | {"Hallucination, visual", "Hallucinations, mixed",
                     "Drug reaction with eosinophilia and systemic symptoms",
                     "Ureteroscopy abnormal", "Increased tendency to bruise", "Pharyngitis"}
    ex = RulesExtractor(groups, vocab)
    report = {"level": "report", "vaccines": [], "report_id": 123456}
    vax = {"level": "vaccine", "vaccines": ["Moderna"], "report_id": None}
    rows = [
        ({"group_id": "F-R1", "level": "report", "answer_type": "CHOICE", "register": "research",
          "format": "question", "cohort": report,
          "options": ["Headache", "Hallucination, visual", "Hallucinations, mixed"],
          "text": "Of Hallucination, visual, Headache, Hallucinations, mixed, which is the "
                  "earliest event in this report?"},
         ("rep_first_choice", ("Hallucination, visual", "Headache", "Hallucinations, mixed"))),
        ({"group_id": "C-R1", "level": "report", "answer_type": "BOOL", "register": "original",
          "format": "question", "cohort": report, "options": None,
          "text": "Do Drug reaction with eosinophilia and systemic symptoms and Headache "
                  "co-occur in report MT-0123456?"},
         ("rep_sym_bool", ("Drug reaction with eosinophilia and systemic symptoms", "Headache"))),
        ({"group_id": "P-V4", "level": "vaccine", "answer_type": "BOOL", "register": "research",
          "format": "question", "cohort": vax, "options": None,
          "text": "Among Moderna reports, is the Increased tendency to bruise-before-"
                  "Ureteroscopy abnormal rate higher than the Hallucinations, mixed-before-"
                  "Pharyngitis rate?"},
         ("pairpair_bool", ("Increased tendency to bruise", "Ureteroscopy abnormal",
                            "Hallucinations, mixed", "Pharyngitis"))),
    ]
    for row, (mode, terms) in rows:
        for blind in (False, True):
            claim = ex.extract(row, blind_group=blind)
            assert claim is not None and (claim.mode, claim.terms) == (mode, terms)


def test_iter_bindings_enumerates_every_split(groups):
    pat = next(p for p in compile_patterns(groups)
               if p.group_id == "F-R1" and p.register == "research" and p.fmt == "question")
    text = "Of Hallucination, visual, Headache, Hallucinations, mixed, which is the earliest event in this report?"
    splits = [tuple(b[r] for r in "ABC") for b in iter_bindings(pat, text)]
    assert len(splits) == 6          # C(4, 2) ways to place two ", " separators in five pieces
    assert ("Hallucination, visual", "Headache", "Hallucinations, mixed") in splits
    assert pat.regex.match(text).groupdict()["A"] == "Hallucination"      # the regex's own split


def test_rejects_out_of_vocabulary_and_inconsistent_scope(extractor):
    vax = {"level": "vaccine", "vaccines": ["Pfizer"], "report_id": None}
    row = {"group_id": "P-V1", "level": "vaccine", "answer_type": "BOOL", "register": "original",
           "format": "claim", "options": None, "cohort": vax,
           "text": "After Pfizer, Headache typically occurs before Fatigue."}
    assert extractor.extract(row).terms == ("Headache", "Fatigue")
    assert extractor.extract({**row, "text": "After Pfizer, Headache typically occurs before Vertigo."}) is None
    assert extractor.extract({**row, "text": "After Moderna, Headache typically occurs before Fatigue."}) is None
    assert extractor.extract({**row, "text": "After Pfizer, Headache typically occurs before Fatigue"}) is None
    assert extractor.extract({**row, "text": "Nothing to see here."}) is None
    assert extractor.extract({**row, "text": ""}) is None
    rep = {"level": "report", "vaccines": [], "report_id": 1001}
    row = {"group_id": "P-R1", "level": "report", "answer_type": "BOOL", "register": "original",
           "format": "question", "options": None, "cohort": rep,
           "text": "Did Headache occur before Fatigue in report MT-0001001?"}
    assert extractor.extract(row).report_id == 1001
    assert extractor.extract({**row, "text": row["text"].replace("1001", "1002")}) is None
    assert extractor.extract({**row, "text": row["text"].replace("MT-0001001", "1001")}) is None
    # a CHOICE row whose named event is not among its options is not a parse
    row = {"group_id": "P-R2", "level": "report", "answer_type": "CHOICE", "register": "media",
           "format": "claim", "options": ["Nausea", "Rash"], "cohort": rep,
           "text": "In this case, Headache came first."}
    assert extractor.extract(row) is None


# ---------------------------------------------------------------------------
# (5) the whole release, both conditions, against from_gold
# ---------------------------------------------------------------------------

def _iter_jsonl(path_stem: Path) -> Iterator[dict]:
    gz = path_stem.with_suffix(path_stem.suffix + ".gz")
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)
    else:
        with open(path_stem, encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)


def _gold_key(claim):
    return (claim.mode, claim.terms, claim.negated, claim.asserted_option)


@pytest.mark.slow
@needs_release
def test_release_round_trip_both_conditions():
    db = REPO_ROOT / "data" / "medtempo.db"
    if not db.exists():
        pytest.skip("data/medtempo.db not present")
    conn = sqlite3.connect(f"file:{db.resolve().as_posix()}?mode=ro", uri=True)
    try:
        vocab = vocabulary_from_db(conn)
    finally:
        conn.close()
    assert len(vocab) == 1660
    ex = RulesExtractor(load_groups(), vocab)

    answers = {a["instance_id"]: a
               for a in _iter_jsonl(RELEASE_DIR / f"{RELEASE_STEM}_answers.jsonl")}
    assert len(answers) == 8_763       # v1.2 (cap 600 / group)
    gold_cache: dict[str, tuple] = {}

    tallies = {cond: collections.Counter() for cond in ("given", "blind")}
    confusion = {cond: collections.defaultdict(collections.Counter) for cond in tallies}
    und_templates = {cond: set() for cond in tallies}
    n_rows = 0
    for q in _iter_jsonl(RELEASE_DIR / f"{RELEASE_STEM}_questions.jsonl"):
        n_rows += 1
        iid = q["hypothesis_id"].rsplit("-", 2)[0]
        if iid not in gold_cache:
            gold_cache[iid] = _gold_key(from_gold(answers[iid]))
        gold = gold_cache[iid]
        for cond, blind in (("given", False), ("blind", True)):
            claim = ex.extract(q, blind_group=blind)
            if claim is None:
                tallies[cond]["wrong"] += 1
                confusion[cond][q["group_id"]][("no_parse", q["register"], q["format"])] += 1
            elif claim.is_underdetermined:
                if (claim.mode, claim.negated) == (gold[0], gold[2]):
                    tallies[cond]["underdetermined"] += 1
                    und_templates[cond].add((q["group_id"], q["register"], q["format"]))
                else:
                    tallies[cond]["wrong"] += 1
                    confusion[cond][q["group_id"]][("underdetermined_wrong_mode",
                                                    claim.mode, claim.negated)] += 1
            elif _gold_key(claim) == gold:
                tallies[cond]["exact"] += 1
            else:
                tallies[cond]["wrong"] += 1
                confusion[cond][q["group_id"]][("parsed_as", claim.mode, q["register"],
                                                q["format"])] += 1

    assert n_rows == 70_104
    for cond in ("given", "blind"):
        t = tallies[cond]
        if t["wrong"] or t["exact"] != 67_812 or t["underdetermined"] != 2_292:
            print(f"\n[{cond}] tallies: {dict(t)}")
            for gid, ctr in sorted(confusion[cond].items()):
                print(f"  {gid}: {dict(ctr.most_common(10))}")
        assert t["wrong"] == 0, (cond, dict(t))
        assert t["exact"] == 67_812, (cond, dict(t))
        assert t["underdetermined"] == 2_292, (cond, dict(t))
        assert und_templates[cond] == RELEASE_UNDERDETERMINED
