# Project: Temporal Hypothesis Generation

A benchmark for temporal hypothesis verification over clinical narratives,
built on the MedTempo corpus.

## What this project is

We construct a dataset of natural-language hypotheses about temporal
patterns of vaccine adverse events, with gold labels computed deterministically
from expert-annotated timelines (MedTempo). The framework receives the
**annotated leveled-order sequences** plus a hypothesis (never narrative text),
and must translate the hypothesis into the correct statistical procedure over
those timelines and return a verdict. See `decisions.md` 2026-08-11
("the framework reads ANNOTATIONS, not narratives"), which reversed the seed
design; the reasoning and token measurements are recorded there.

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

Current phase is a PILOT. Verdict balance is now **equal thirds per group**
(supported / refuted / insufficient), which supersedes the provisional 45/45/10;
the roster is **23 groups**, not 30. The pilot's remaining job is the
distribution report (`04_corpus_survey.md`, Part A) used to recalibrate the
sampling numbers — including **A4**, which is what will fix the still-provisional
confidence-tag cutoffs. Do not scale to the full benchmark until that report has
been reviewed. Part C (gold-label validation) is mechanised in
`scripts/validate_gold.py` and passing.

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
- **Framework input is annotated leveled orders + hypothesis.** Never narrative
  text. Superseded the seed rule on 2026-08-11; MedTempo is published with an
  upcoming conference paper and will be archived publicly, so the annotations
  are effectively part of the release.
- **Gold labels use leveled-order representation.** See `02_dataset_design.md`
  for the format and the computation rules.
- **The gold label is the three-decision verdict**, oriented to each instance's
  own asserted claim: `refuted` requires significance in the OPPOSITE direction,
  never "failed to prove". Every released statistic (p-value, CI, effect size)
  must describe the instance's own claim, not the canonical orientation.
- **Exact tests only.** Chi-square is removed from the codebase. Min-n floors
  live in `core/min_n.py` (10, sequence 5) and are the only gate.
- **Releases split input from gold.** `*_questions.jsonl` carries only
  `INPUT_FIELDS`; `*_answers.jsonl` carries the gold. `writers.split_release`
  raises if a gold field leaks.
- **Run `scripts/validate_gold.py` before trusting generated data.** Six
  invariant families; it is what caught the first-mention bug.

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
- Use `pytest`. Run tests before committing. The `.venv` has lost its editable
  install, so tests need `PYTHONPATH=src` until `pip install -e .` is re-run.
- Plan docs in `docs/plan/` are append-friendly Markdown; do not silently rewrite
  decisions, append to `decisions.md` instead.

## How to work with this repo

- **Start every session with `git pull`.** Work happens on more than one machine;
  the committed docs are the only source of truth for current settings, next steps
  and open problems. Do not rely on prior-conversation memory for them.
- New decisions land in `docs/plan/decisions.md` with a date.
- Resolved items in `open_questions.md` move to `decisions.md`; delete from open.
- The group seeds in `03_templates.md` are the canonical template list, but the
  SHIPPING roster is 23 groups — see `09_next_steps.md` for what was removed and
  why. Any changes go through `decisions.md` first.
- When implementing a new component, first verify the relevant plan doc
  describes it. If the plan is silent, surface the gap rather than improvising.
