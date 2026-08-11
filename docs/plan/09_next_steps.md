# Next Steps — as of 2026-08-11 (end of day)

Consolidated state and sequencing. Companion to `decisions.md` (locked),
`open_questions.md` (open), and `08_multi_tier_inventory.md` (multi-tier evidence,
partly stale — see its banner).

## Where the code now stands

| | |
|---|---|
| Roster as coded | **25 groups** = 7 report-level + 18 cohort-level |
| Cohort groups that ship a verdict | **12** (the other 6 are non-directional, pending removal) |
| Roster after the pending 07-28 migration | **22** (−6 non-directional, +R1/R3/R5) |
| Min-n gate | 10, sequence 5 (`core/min_n.py`) |
| Tests | exact only; chi-square removed from the codebase |
| Gold label | the **three-decision verdict**, oriented to each instance's own claim |
| Framework input | the **annotated leveled orders**, never narratives |
| Decisive cores (S) | **1415** |
| Insufficient sub-types | all populated: underpowered ~5.6k / sparse ~2.7k / not_locatable 116 |
| Sampler | equal thirds **per group**, every decisive core posed **both ways** |
| Release format | `*_questions.jsonl` (input only) + `*_answers.jsonl` (gold), split enforced |
| Gold-label validation | **22,176 instances, six invariant families, all passing** |

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

### 1. Three cheap validity calls, before anything ships

All measured, all in `open_questions.md`, none needs new analysis:

- **Drop C-M2.** Fails its own permutation null at both floors (p_perm 0.129 at 20,
  **0.151** at 10 with 2000 rounds), and currently ships coin-flip labels.
- **Permutation-test F-M3.** Never validated, and its nearest analog (M-B
  first-overall) is pure noise at 0.453. Needs an entry in
  `run_multi_inventory.py`, then a ≥2000-round run.
- **Retire §6 lever 2.** Free: `core/positions.py` is imported only by two scripts,
  never by `core/answers.py`, so no gold label reads those rank p-values.

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
