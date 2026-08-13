# Next Steps — as of 2026-08-12

Consolidated state and sequencing. Companion to `decisions.md` (locked),
`open_questions.md` (open), and `08_multi_tier_inventory.md` (multi-tier evidence,
partly stale — see its banner).

**Read this file and `open_questions.md` at the start of every session** — after
`git pull`. Work happens on more than one machine, so committed docs are the only
record of current settings, pending work and known defects.

## Open issues register — everything live, one table

| # | issue | kind | status | detail lives in |
|--:|---|---|---|---|
| 1 | Multi tier is P-M2 alone — ship it, swap to M-F, or retire the tier for v1? | **decision** | **blocking the roster** | `open_questions.md` "Is a ONE-group multi tier worth the shape?" |
| 2 | Roster migration A: remove the 6 non-directional groups, add R1/R3/R5 | build | not started; old supply estimates (372/415/144) predate every floor and test change and must be re-measured | §3 below |
| 3 | Eval harness does not exist — architecture, metrics, baselines | build | not started; input format now settled so it is specifiable | §2 below |
| 4 | Confidence-tag cutoffs (0.15 / 0.30) were never calibrated | **known defect** | provisional; a floor-sized core always tags `low`, so the tag is near-uninformative as shipped | `open_questions.md`, and A4 in `04_corpus_survey.md` |
| 5 | `not_locatable` exists only in the sequence family (all 116) | dataset gap | mechanism undecided | §4 below |
| 6 | Report-level groups (7 of 25) do not reach equal thirds | dataset gap | deferred by user decision | §4 below |
| 7 | Report-level first/last ties — set-valued vs single-valued gold | decision | open, small | `open_questions.md` |
| 8 | Synonym table never built; `synonym_used` echoes the raw MedDRA term | dataset gap | open — released text has no lexical variation | §4 below |
| 9 | Sequence cohort tier has S = 8 across two groups (S-V1, S-V3) | decision | open — take in full and flag, or drop the tier | `open_questions.md` "Does the sequence family survive at cohort level?" |
| 10 | Overleaf draft is badly stale (S, roster, tests, nulls, gold rule, input format) | write-up | hold until #1 and #2 settle | §5 below |
| 11 | Disconnected components in MedTempo — rate never measured | survey | open | `open_questions.md` |
| 12 | `.venv` lost its editable install | environment | workaround: `PYTHONPATH=src` | standing caveats |
| 13 | C-V3's text asks an argmax, its statistic tests a majority | **claim/label defect** | **open** — 20% of cores disagree, 5 shipped decisive | `open_questions.md` "C-V3 asks an argmax" |
| 14 | Twin groups duplicate cores; `core_id` includes `group_id`, so a split separates them | **leakage risk** | open — needs a group-independent `fact_id` | `open_questions.md` "Twin groups duplicate" |

Items 1–12 contain no correctness bug in generated data: `validate_gold.py` clears
all 20,749 instances on six invariant families as of 2026-08-11. Items 4, 5, 6 and 8
are completeness/calibration gaps, not wrong labels.

**Item 13 is different, and `validate_gold.py` structurally cannot catch it.** Its
label is internally consistent with its statistic; what is misaligned is the TEXT
against the statistic. Every invariant check in the validator compares gold fields to
each other, so no invariant family covers "does the question the instance ASKS match
the quantity it SCORES". That class of defect has now appeared three times (S-V1/F-V3
on 07-13, F-V2/F-R2 on 08-12, C-V3 today) and is found only by reading a rendered
instance beside its statistic. Worth a standing review step, not another invariant.

## Where the code now stands

| | |
|---|---|
| Roster as coded | **23 groups** = 7 report-level + 16 cohort-level |
| Cohort groups that ship a verdict | **10** (the other 6 are non-directional, pending removal) |
| Roster after the pending 07-28 migration | **20** (−6 non-directional, +R1/R3/R5) |
| Min-n gate | 10, sequence 5 (`core/min_n.py`) |
| Tests | exact only; chi-square removed from the codebase |
| Gold label | the **three-decision verdict**, oriented to each instance's own claim |
| Framework input | the **annotated leveled orders**, never narratives |
| Decisive cores (S) | **1365** — every remaining group clears its null |
| Insufficient sub-types | all populated: underpowered ~5.6k / sparse ~2.7k / not_locatable 116 |
| Sampler | equal thirds **per group**, every decisive core posed **both ways** |
| Release format | `*_questions.jsonl` (input only) + `*_answers.jsonl` (gold), split enforced |
| Gold-label validation | **20,749 instances, six invariant families, all passing** |
| Reported statistics | one-sided exact p-value, 95% Wilson CI (Wilson-Newcombe on the difference for two-cohort), Cohen's h against the test's own null — all oriented to the instance's asserted claim |
| Confidence tag | **provisional and uncalibrated** — see issue 4 |

### Closed since the 08-11 entry (2026-08-12)

- Two claim/label mismatches found while building sample instances and fixed:
  F-V2/F-R2 named the wrong event in every instance, and two-cohort `gold_n2`/`gold_k2`
  described the wrong cohort. Both now covered by regression tests and by
  `validate_gold.py`. See `decisions.md`.
- The one-off sample artifacts and their generator scripts were removed at the
  user's request (`850d52f`); `openpyxl` was reverted out of the `render` extra.
  Nothing in the pipeline depends on them.

## The pipeline is DONE for the testable templates

Steps B, C and D are complete, plus the release format and the validation guard:

- **B** — corpus helpers report `n` at every size; the shared gate is the only floor.
- **C** — the shipped label is the three-decision verdict, and each instance's
  statistics describe **its own** asserted claim.
- **D** — equal thirds per group; one claim per core per class; re-orientation
  minimised; the insufficient third spread across sub-types.
- **Release** — report ids not narratives, with the input/gold boundary enforced by
  `writers.split_release`.
- **Part C** — mechanised in `scripts/validate_gold.py`. Worth putting in CI: it is
  what caught the first-mention bug.

## What is next, in priority order

### 1. Validity ledger - CLOSED 2026-08-11

All three items done. The roster now ships nothing that fails its own null:

- **Lever 2** - retired. `core/positions.py` is descriptive-only and
  `core/answers.py` does not import it.
- **F-M3** - retired (0.183-0.188), and all three substitute shapes fail too
  (M-J 0.096, M-G 0.509, M-I 0.698). The first/last family structurally cannot have a
  two-cohort group.
- **C-M2** - dropped (0.129 / 0.151 / 0.195 / 0.202 over four measurements).

**The live decision now: the multi tier is P-M2 alone.** Ship it, swap it for M-F, or
retire the two-cohort tier for v1? See `open_questions.md`.

### 2. The eval harness — the actual path to modeling

Nothing exists yet; `src/` is entirely corpus, generation and statistics. The input
format is now settled, so this is finally specifiable. Three open questions gate it:

- **Architecture.** The intended loop: hypothesis → decide which test applies →
  query the annotation store for the conditioned reports → aggregate → exact test →
  three-decision verdict. Retrieval is a mechanical query over structured data, so
  the capability under test is steps 1, 2 and 5.
- **Metrics.** Verdict agreement is the headline, but the six failure modes are
  separately diagnosable and should be reported separately: query parsing,
  conditioning, aggregation, null choice, test/tail, min-n gate. Add
  **pair-consistency** over mirror pairs — a model answering `supported` to both
  directions of one core is the cheapest thing to catch.
- **Baselines.** The deterministic upper bound is now a true **100%**, which makes it
  a real reference rather than an estimate. Then: full-cohort annotations in context
  (~30K tokens, cacheable), tool-using with code execution, and a single-pass variant.

### 3. Roster migration A — the biggest remaining supply lever

Remove P-M1, C-M1, S-M1, S-M3, F-M1, F-M2 (all at S = 0, so nothing shippable is
lost). Add R3 = P-V2, R5 = C-V2, R1 = P-V4: each needs four-register wording, R5 a
2×2 presence × presence corpus helper, R1 a 4-event enumeration shape. The Overleaf
draft already published their IDs and BOOL answer types.

Their old supply estimates (P-V2 372, P-V4 415, C-V2 144) predate every floor and
test change made today, so **re-measure before relying on ~931**.

### 4. Dataset completeness

- **`not_locatable` outside the sequence family.** All 116 are sequence triples that
  are present but never orderable; pairwise/co-occurs/first-last have none, because
  their enumeration pre-filters to co-occurrence ≥ 10. The 07-28 decision requires
  this third to be generated deliberately.
- **Report-level groups** (7 of 25). Deferred by decision. They do not reach equal
  thirds, and the question underneath is what `insufficient` means for a
  single-report claim — the CHOICE variants treat a co-exist pair as unanswerable
  while the BOOL variants map co_exist to `refuted`.
- **First/last tie handling for CHOICE at report level.** The natural next small
  decision: set-valued gold is defensible at report level precisely because there is
  no aggregation to distort, unlike cohort level where it was rejected on 08-11.
- **Synonym table.** Never built; `synonym_used` echoes the raw MedDRA term, so the
  released text has no lexical variation.

### 5. Overleaf draft (step G)

Badly stale — today changed S, the roster, the tests, the nulls, the gold-label rule
and the input format. Do not regenerate until the roster settles (item 3), and note
the generator resurrects the "What changed in the redesign" section that was deleted
by hand on Overleaf.

## Standing caveats

- Group-level validity ≠ per-core validity: a group that clears its permutation null
  still contains false positives at the alpha rate. Inherent to
  significance-as-verdict.
- `p_perm` is a design-time diagnostic, excluded from gold-label computation.
- Mirror pairs are correlated by construction: both members share a
  `derived_from_core_id`, and any train/test split MUST keep a pair together.
- **Changing a test can silently invalidate the reasoning behind a gate** — that is
  how the first/last tie problem survived until Part C. Re-check the gate whenever a
  test changes.
- The `.venv` lost its editable install; tests need `PYTHONPATH=src` until
  `pip install -e .` is re-run.
