# 01. Project Overview

> **STATUS (2026-08-12): framing is current; the input medium and the
> contribution numbers were superseded.** Corrected in place below with dates.

## What we are building

A benchmark and framework for **temporal hypothesis verification over
expert-annotated clinical timelines**. Given a natural-language hypothesis about
the temporal pattern of vaccine adverse events, and the annotated leveled orders
for the relevant cohort, return a verdict (supported / refuted / insufficient)
grounded in a statistical test over those timelines.

*(Superseded 2026-08-11: this originally read "over clinical narratives … and
the relevant report narratives". The framework never sees narrative text. The
task is translating a hypothesis into the right statistical procedure, not
extracting timelines from prose — that is CRAFT's problem.)*

## Why it is novel

Existing work splits the problem in unhelpful ways:

- **Temporal knowledge graph QA** (TempoQR, CRONQUESTIONS, the TKGQA survey)
  assumes a clean structured KG with timestamps. Our setting has neither
  structure nor timestamps, only ordinal relations (before, after, co-exist)
  buried in free-text narratives.

- **Scientific claim verification** (SciFact, ClaimDB, BioVerge) verifies
  textual claims against text or tables, without statistical aggregation
  over a population.

- **Pharmacovigilance signal detection** (PRR, ROR on VAERS/FAERS) does
  statistical analysis but is not driven by natural-language hypotheses.

Our position: **agentic temporal claim verification with statistical
grounding, evaluated on a benchmark of typed temporal hypotheses over
expert-annotated clinical narratives.**

## Contribution claims

1. A benchmark of temporal hypotheses (questions and claims) across **23
   semantic groups × 4 registers** (Original, Research, Media, Clinical), with
   deterministic gold labels computed from expert-annotated leveled orderings.
   *(Was "30 groups × 3 registers"; the roster shrank as groups that could not
   produce a well-posed test were retired, and the Original seed counts as a
   register.)*

2. A framework that reads the annotated leveled orders plus the hypothesis,
   locates the relevant cohort, runs the appropriate exact test, and returns a
   three-decision verdict. *(Was "reads only the narrative text … including
   proportions where applicable"; superseded 2026-08-11 and 2026-07-28.)*

3. An empirical study of where current LLMs fail on the benchmark, with error
   decomposition into the six separately-diagnosable failure modes: query
   parsing, conditioning, aggregation, null choice, test/tail selection, and the
   min-n gate — plus **pair-consistency** over mirror pairs, since a model
   answering `supported` to both directions of one core is the cheapest failure
   to detect. *(Was "evidence localization, relation extraction, statistical
   aggregation"; relation extraction left the task with the 08-11 input change.)*

## Substrate

- **MedTempo**: 3,166 expert-annotated VAERS adverse event reports.
- **Three vaccines**: Pfizer, Moderna, Janssen. *(These docs formerly wrote
  "Johnson"; that string appears nowhere in code or output.)*
- **Three relation types per pair**: before, after, co-exist.
- **No timestamps**; ordinal relations only — which is why every test is
  categorical or rank-based, and no mean-based test applies.

## Out of scope for v1

- Significance testing groups (the SIG family).
- Three-vaccine comparative groups.
- Cross-corpus extension (i2b2, MACCROBAT, THYME).
- Lay and forum-register surface forms.

These are deferred to follow-on work and may inform a v2 of the benchmark.

## Connection to CRAFT

CRAFT (separate work, currently under review) extracts full temporal
timelines from clinical narratives. This project takes a narrower task:
verify a specific temporal hypothesis. The two are complementary:

- CRAFT: full-timeline extraction.
- This project: hypothesis-conditioned verification.

The framework here may use CRAFT internally as one option for extracting
relations, but the contribution is the verification framework itself, not
the extractor.
