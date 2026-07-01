# Project: Temporal Hypothesis Generation

A benchmark for temporal hypothesis verification over clinical narratives,
built on the MedTempo corpus.

## What this project is

We construct a dataset of natural-language hypotheses about temporal
patterns of vaccine adverse events, with gold labels computed deterministically
from expert-annotated timelines (MedTempo). The framework receives only raw
narratives plus a hypothesis, and must locate the temporal evidence and
return a verdict.

This is positioned as agentic temporal claim verification, not deep research.
It is the natural follow-on to the CRAFT paper (timeline extraction):
CRAFT extracts; this framework verifies hypotheses against extracted information.

## Where the plan lives

Before implementing anything, read the plan docs:

- `docs/plan/01_overview.md`      — project framing and contribution
- `docs/plan/02_dataset_design.md` — MedTempo schema, leveled order, gold-label rules
- `docs/plan/03_templates.md`     — the 30 template groups and three registers
- `docs/plan/04_corpus_survey.md` — pilot + distribution report spec; run BEFORE the full benchmark
- `docs/plan/05_significance_tests.md` — significance-test reference: both tracks, per-group assignments, min-n
- `docs/plan/06_pilot_examples.md` — pilot task: per-template diagnostics and worked supported/refuted examples
- `docs/plan/decisions.md`        — locked decisions (single source of truth)
- `docs/plan/open_questions.md`   — items still under discussion (do not assume)

If a question is in `open_questions.md`, do not guess an answer in code. Ask.

Current phase is a PILOT. The sampling numbers in `decisions.md` (T = 100,
45/45/10 verdict balance, quantile bands) are provisional inputs to the pilot,
not final values. The pilot has two jobs: (1) generate a small dataset across
all 30 groups using the provisional numbers, and (2) emit a distribution
report (`04_corpus_survey.md`, Part A) that we use to recalibrate those
numbers. Do not scale to the full benchmark until the distribution report has
been reviewed. Validate the gold-label computation against a hand-checkable
sample (Part C) before trusting the distributions.

The concrete starting task for this phase is `06_pilot_examples.md`:
per-template diagnostics plus worked supported and refuted examples. A core
must actually exist in the data (events genuinely co-occur and clear the
min-n gate) before it can yield a hypothesis. Refuted hypotheses assert a
false relation about a real, existing core; never build them from events that
never co-occur.

## Where the templates live

The canonical template definitions are in `data/templates/`:

- `data/templates/pairwise.yaml`    — precedes and co-occurs groups
- `data/templates/sequence.yaml`    — sequence groups
- `data/templates/first_last.yaml`  — first / last groups

These YAML files are the **single source of truth** for the templates.
The .docx under `docs/reference/` is a generated artifact for advisor
meetings, produced by `scripts/render_templates_docx.py`.

## Conventions

- **Mechanical generation only.** Slot-filling and templated paraphrase only.
  No LLM-based rewrites for the benchmark.
- **Three active registers.** Research, Media, Clinical. Chart-style has been
  dropped. The "Original" canonical seed is kept as a baseline.
- **MedTempo is private scaffolding.** Used to compute gold labels during dataset
  construction. Never released as part of the benchmark; the framework never
  sees its annotations at inference time.
- **Framework input is narrative + hypothesis only.** No relations, no event
  lists, no metadata beyond what the hypothesis text contains.
- **Gold labels use leveled-order representation.** See `02_dataset_design.md`
  for the format and the computation rules.

## Out of scope for v1

Do not implement these unless explicitly asked:

- Significance-test (SIG) hypothesis groups
- Three-vaccine multi-cohort groups (only 2-vaccine pair comparisons in v1)
- Lay or forum-register paraphrases
- LLM-based hypothesis generation
- Connections to other temporal corpora (i2b2, MACCROBAT, THYME); MedTempo only

## Coding conventions

- Python primary language. Type hints on public functions.
- Tests live next to the code they test (`tests/` mirroring `src/`).
- Use `pytest`. Run tests before committing.
- Plan docs in `docs/plan/` are append-friendly Markdown; do not silently rewrite
  decisions, append to `decisions.md` instead.

## How to work with this repo

- New decisions land in `docs/plan/decisions.md` with a date.
- Resolved items in `open_questions.md` move to `decisions.md`; delete from open.
- The 30 group seeds in `03_templates.md` are the canonical template list.
  Any changes go through `decisions.md` first.
- When implementing a new component, first verify the relevant plan doc
  describes it. If the plan is silent, surface the gap rather than improvising.
