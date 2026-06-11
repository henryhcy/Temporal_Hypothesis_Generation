# 01. Project Overview

## What we are building

A benchmark and framework for **temporal hypothesis verification over clinical
narratives**. Given a natural-language hypothesis about the temporal pattern of
vaccine adverse events, and the relevant report narratives, return a verdict
(supported / refuted / insufficient) grounded in the temporal structure of
the reports.

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

1. A benchmark of temporal hypotheses (questions and claims) across 30
   semantic groups × 3 registers, with deterministic gold labels computed
   from expert-annotated leveled orderings.

2. A framework that reads only the narrative text plus the hypothesis,
   locates the temporal evidence, and returns a verdict — including
   proportions where applicable.

3. An empirical study of where current LLMs and current temporal reasoning
   systems fail on the benchmark, with error decomposition into evidence
   localization, relation extraction, and statistical aggregation.

## Substrate

- **MedTempo**: 3,166 expert-annotated VAERS adverse event reports.
- **Three vaccines**: Pfizer, Moderna, Johnson.
- **Three relation types per pair**: before, after, co-exist.
- **No timestamps**; ordinal relations only.

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
