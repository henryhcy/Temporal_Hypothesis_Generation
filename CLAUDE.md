# Project: Temporal Hypothesis Generation

A benchmark for temporal hypothesis verification over annotated clinical
timelines, built on the MedTempo corpus (VAERS reports).

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

**Docs 01–06 are SEED documents.** They were written in June and describe the
project as originally conceived. A 2026-08-12 audit corrected the statements that
had drifted — each is struck in place with its date and replacement, so the
history stays readable — but treat them as annotated history, not as spec. When a
seed doc and `decisions.md` / `CLAUDE.md` / the code disagree, the seed doc is
wrong.

- `docs/plan/01_overview.md`      — project framing and contribution; input medium and contribution numbers corrected
- `docs/plan/02_dataset_design.md` — leveled-order schema (current) + gold-label rules (**rules 3–8 superseded, read the strikeouts**) + release format (**reversed 08-11**)
- `docs/plan/03_templates.md`     — YAML structure (current); roster counts, PROP, verdict mechanics and negation all corrected
- `docs/plan/04_corpus_survey.md` — pilot spec; **delivered except A4 (confidence-tag calibration) and A6 (disconnected components)**
- `docs/plan/05_significance_tests.md` — min-n section is CURRENT; the per-group test table is **historical** (lists seven retired groups)
- `docs/plan/06_pilot_examples.md` — pilot task spec; delivered. Its "cores must actually exist" rule is still exactly right
- `docs/plan/07_significance_findings.md` — measured power findings and the §6 levers (lever 2 is RETIRED); carries update banners
- `docs/plan/08_multi_tier_inventory.md` — two-cohort screening evidence; read its banner, parts are superseded
- `docs/plan/09_next_steps.md`     — **current state, the live issue register, and priority order**
- `docs/plan/11_model_pipeline.md` — **the eval harness / model pipeline design (2026-09-01)**: stage contract, `StructuredClaim`, narrative-free eval DB, metrics, leakage protocols, milestones, results (§10.3); M1+M2 BUILT on branch `model-pipeline-design`; `11a_template_faithfulness_audit.md` audits all 184 template strings (issue 24)
- **`s1-toolbox` branch (2026-09-30):** S1 is evaluated under the TOOLBOX frame (`--s1-frame toolbox`,
  11 §11a/§13): conventions stated, mode mapping withheld, the model composes a conditional plan;
  the catalogue frame is the upper bound. Headline condition is zero-shot. API keys: gitignored `.env`.
- `docs/plan/decisions.md`        — locked decisions, **chronological and append-only**: read newest-first, and never quote one entry as current without checking for a later one on the same topic
- `docs/plan/open_questions.md`   — items still under discussion (do not assume). Cleaned 08-12; every entry is genuinely open and carries its issue number

If a question is in `open_questions.md`, do not guess an answer in code. Ask.
`09_next_steps.md` is the fastest way back into context: it opens with a table of
every live issue and which doc holds the detail.

Current phase is a PILOT. Verdict balance is now **equal thirds per group**
(supported / refuted / insufficient), which supersedes the provisional 45/45/10;
the roster is **23 groups**, not 30. The pilot's remaining job is the
distribution report (`04_corpus_survey.md`, Part A) used to recalibrate the
sampling numbers — including **A4**, which is what will fix the still-provisional
confidence-tag cutoffs. Do not scale to the full benchmark until that report has
been reviewed. Part C (gold-label validation) is mechanised in
`scripts/validate_gold.py` and passing.

The generation pipeline is DONE for the testable templates (steps B, C, D, the
release format, and mechanised Part C validation). ~~What is NOT built: the eval
harness — `src/` is entirely corpus, generation and statistics.~~ **2026-09-01:**
the eval harness is designed in `11_model_pipeline.md` and M1+M2 are BUILT on
branch `model-pipeline-design`: `src/temporal_hypo/framework/` holds rules/LLM
extraction, the SQL compiler + LLM text-to-SQL, the oracle hookup and the scorer;
the deterministic B0 baseline reproduces the gold on ALL 147,936 records
(`scripts/run_eval.py --pipeline oracle`), and local 7B smoke results live in
`11_model_pipeline.md` §10.3. The fine-tuned extractor and the in-context and
agent baselines (M3–M5) are NOT built. See
`09_next_steps.md` for the priority order ~~and the one decision currently blocking
the roster (the multi tier is P-M2 alone)~~ (**2026-09-01:** that decision was made
on 2026-08-14 — P-M2 ships alone; the 20-group roster is FINAL and the v1 dataset is
generated). **2026-09-04: the working release is `data/release/v1.1`** — issues
23 (report-tier vaccine skew) and 25 (`test_verdict`) fixed by regeneration;
v1 stays committed and immutable; B0 re-verified at exactly 100% on v1.1.

A core must actually exist in the data (the events genuinely co-occur and the
denominator clears the min-n gate) before it can yield a hypothesis. Never build
a claim from events that never co-occur — that is what `insufficient` /
`not_locatable` is for, and it is a separate class from `refuted`.

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
- **Four register variants per group.** The canonical Original plus Research,
  Media and Clinical. Chart-style has been dropped. Any new group needs all four
  written before it can ship.
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
- **Exact tests only**, one-sided in the claim's direction, alpha 0.05 per side.
  Chi-square is removed from the codebase. Min-n floors live in `core/min_n.py`
  (10, sequence 5) and are the only gate — helpers measure, the gate decides, so
  never re-implement a floor inside a helper.
- **Each decisive core is posed BOTH ways** (a supported instance and a refuted
  mirror). Mirror pairs share a `derived_from_core_id` and **must stay on the same
  side of any train/test split**.
- **Negation is the orientation operator for symmetric claims**, and it is not
  configurable — it applies wherever the template YAML provides it, which today is
  ~~only C-V1 and C-V3~~ **C-V1, C-V2 and C-V3 (corrected 2026-09-01: C-V2 shipped
  negated wording on 2026-08-14 and 349 negated C-V2 instances are in the release)**.
  Samplers must PREFER PLAIN WORDING and negate only to fill a
  remaining deficit.
- **Conditioning rules differ per family and are the subtlety worth protecting:**
  precedes EXCLUDES co-exist from its denominator, co-occurs treats co-exist as the
  numerator, sequence requires all three events at DISTINCT levels, first/last
  requires every candidate present and drops tie reports from n entirely, and a
  term's position in a report is its FIRST mention.
- **The permutation null (`p_perm`) is a design-time validation diagnostic only.**
  It never enters a gold label — the model must be able to run whatever test
  produced the label. Any new group must clear it at >= 2000 rounds before it gets
  a roster slot; 200 rounds is triage.
- **Rank/position tests are descriptive only.** `core/positions.py` must not be
  imported by `core/answers.py`; the normal approximation is anti-conservative on
  tie-heavy ordinal data (§6 lever 2, retired).
- **Releases split input from gold.** `*_questions.jsonl` carries only
  `INPUT_FIELDS`; `*_answers.jsonl` carries the gold. `writers.split_release`
  raises if a gold field leaks.
- **Run `scripts/validate_gold.py` before trusting generated data.** Six
  invariant families; it is what caught the first-mention bug.
- **The eval harness reads `data/medtempo_eval.db`, never `data/medtempo.db`**
  (2026-09-01). The eval DB is keyed on `vaers_id`, has no `narrative` column and no
  surrogate id; it is the mechanical guard behind "never narrative text". Build it
  with `scripts/build_eval_db.py`; the DDL in `framework/sql/views.sql` is what
  models see.
- **Never call `core/answers.py::compute_answer` for an asserted claim** (2026-09-01).
  It reports the WINNER's tail, not the asserted cell's; the harness scores a claim
  with `core_significance(core, named=claim.named_cell())` and applies the negation
  tail swap exactly as `oriented_significance` does.
- **Never read `test_verdict`** (issue 25, 2026-09-01). It equals the canonical, not
  the oriented, verdict on 1,800 report-level refuted rows. `gold_verdict` is the
  label; the harness and every metric use it alone.

## Out of scope for v1

Do not implement these unless explicitly asked:

- Significance-test (SIG) hypothesis groups
- Three-vaccine multi-cohort groups (only 2-vaccine pair comparisons in v1)
- Lay or forum-register paraphrases
- LLM-based hypothesis generation
- Connections to other temporal corpora (i2b2, MACCROBAT, THYME); MedTempo only
- Equivalence / non-inferiority margins to revive the "differ"/"same" two-cohort
  groups — REJECTED 2026-08-11, see `decisions.md`
- Chi-square, and any use of `p_perm` or a rank test as a verdict driver

## Standing caveats

- **Changing a test can silently invalidate the reasoning behind a gate.** That is
  how the first/last tie problem survived until Part C. Re-check the gate whenever
  a test changes.
- **Group-level validity is not per-core validity.** A group that clears its
  permutation null still contains false positives at the alpha rate. Inherent to
  significance-as-verdict; state it rather than hiding it.
- Exact tests are discrete, so achievable p-values come in jumps and the true
  false-positive rate never equals nominal alpha (~1.6% at n=6, ~3.3% at n=11).

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
