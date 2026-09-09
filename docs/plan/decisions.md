# Decisions Log

Single source of truth for what has been settled. Append entries with the
date when a decision is locked. Do not silently rewrite past entries; if a
decision changes, append a new entry that supersedes it.

> **READ THIS FILE NEWEST-FIRST WHEN IN DOUBT.** It is chronological and
> append-only, so early entries record what was true in June/July and have often
> been superseded — the seed section immediately below still says "clinical
> narratives", "30 template groups" and "Johnson", all three of which are now
> wrong. That is by design: the history is the point. But it means **no single
> entry here can be quoted as current** without checking for a later one on the
> same topic. For current state, read `09_next_steps.md`; for current
> conventions, `CLAUDE.md`.

---

## Initial seed (project setup)

### Scope and framing
- **Project scope**: temporal hypothesis verification over clinical narratives, built on MedTempo.
- **Positioning**: agentic temporal claim verification, not deep research.
- **Out of scope for v1**: SIG groups, three-vaccine groups, cross-corpus extension, lay/forum registers, LLM-based hypothesis generation.

### Dataset
- **MedTempo treatment**: private scaffolding only; never released as part of the benchmark.
- **Framework input**: narrative text plus hypothesis only. No relations or event lists provided at inference.
- **Storage representation**: leveled order per report (list of co-exist clusters in temporal sequence).
- **Three vaccines**: Pfizer, Moderna, Johnson.
- **Relation vocabulary**: before, after, co-exist (only).
- **Co-exist semantics**: collapses true simultaneity and order-unknown into one bucket.
- **First-mention rule**: when a term appears multiple times in a narrative, only the first mention is recorded.
- **Transitive closure**: computed on-the-fly per query, not stored. Stored relations are direct annotations only.

### Gold-label computation rules
1. **precedes denominator (cohort level)**: only reports where both events appear AND the pair is ordered. Co-exist pairs excluded.
2. **co-occurs denominator**: reports where both events appear (co-exist kept, as it is the event of interest).
3. **sequence denominator**: reports containing all three events.
4. **first_among denominator**: reports containing all named candidates. Tie-reports excluded from per-candidate counts; tie rate reported separately.
5. **Minimum n threshold**: n = 10. Below this, verdict is `insufficient`.
6. **Majority threshold for BOOL "typically"**: > 0.5 strictly. Exact 0.5 maps to `insufficient`.
7. **PROP tolerance**: a claimed value supported if within 5 percentage points of true proportion.
8. **Multi-vaccine "differ" verdict**: effect-size rule, |p1 - p2| > 10 percentage points.

### Templates and registers
- **30 template groups total** (after redundancy correction and the F-M1/F-M2 review). Group IDs in `03_templates.md`.
- **Three active registers**: Research, Media, Clinical. Plus the canonical "Original" as a baseline.
- **Chart-style register dropped**.
- **Mechanical generation only**. No LLM-based rewrites.
- **Negation modifier**: applied to a subset of BOOL instances; flips the assertion polarity and the gold verdict.

### Multi-vaccine scope
- **Two-vaccine pairs only** for v1. Three-vaccine groups deferred.
- **Three pairs available**: Pfizer-Moderna, Pfizer-Johnson, Moderna-Johnson.

### Sequence semantics
- **Strict ordering for sequence_holds**: A → B → C requires level_of(A) < level_of(B) < level_of(C) with strict inequalities. Co-occurrence within the sequence does not satisfy strict ordering.

---

## Sampling and significance (in progress)

### Next step locked: corpus survey before generation
- The sampling plan is NOT finalized. Before generating any benchmark
  instances, run the corpus survey specified in `04_corpus_survey.md`.
- The survey counts viable cores per group, event/pair/triple frequencies,
  disconnected-component rate, multi-vaccine overlap, and runs a cycle check.
- Sampling decisions (pair/triple selection, per-group budgets, verdict
  balance, synonym sampling, multi-vaccine coverage) are resolved against the
  survey output, then recorded here. See `open_questions.md` for the
  pending items.

### Significance reframed as confidence quantification
- The statistical contribution reports BOTH a significance test (p-value) and
  a confidence interval for every eligible gold value. The p-value answers
  "is the effect real (vs a chance baseline)"; the CI answers "how precise is
  the estimate." They are two summaries of the same computation and are
  reported together.
- Each cohort-level instance carries: point estimate, p-value (with its test
  and null stated), 95% confidence interval, an effect size, and a
  high/moderate/low confidence tag.

- Test families (exact tests preferred over normal approximations):
  - One proportion vs chance baseline: binomial exact test. Null p = 0.5 for
    pairwise/co-occurs, 1/6 for sequence (6 orderings), 1/3 for first-among-3.
  - Two proportions (multi-vaccine pair): Fisher's exact test on the 2x2
    table; chi-square of independence as a large-n equivalent when all
    expected cell counts >= 5.
  - Multinomial / distribution (modal ordering, first-event distribution,
    "same across cohorts"): chi-square goodness-of-fit (vs uniform) or
    chi-square test of homogeneity. Guard: expected counts >= 5 per cell;
    merge rare categories or use a permutation/Monte-Carlo chi-square when
    cells are too sparse.

- Significance verdict: "significant" if p < 0.05 AND the minimum-n threshold
  is met; otherwise `insufficient`. Alpha = 0.05 fixed throughout.

- Interval methods: Wilson for single proportions, Wilson-Newcombe for
  differences, bootstrap for sequence and multi-vaccine groups, Sison-Glaz
  (or equivalent) for multinomial groups.
- Effect size: Cohen's h or odds ratio for proportion differences (exact
  choice still open).

- Note on interpretation: for single-cohort groups, most real symptom pairs
  will test as significant (clinical events have genuine temporal structure),
  so the significance verdict is a weaker discriminator than the direction or
  proportion for those groups. The multi-vaccine "do they differ" tests are
  the more diagnostic significance verdicts, since a true difference vs noise
  is genuinely uncertain. Weight/treat multi-vaccine SIG as the harder track.

- t-test is NOT used: outcomes are categorical (yes/no per report), so
  binomial / Fisher / chi-square and their CIs are the correct tools. A
  rank-based test (Wilcoxon rank-sum on rank-distance) may be added as a
  secondary cross-method check for multi-vaccine groups only.
- No multiple-testing correction at the benchmark level (keeps instances
  independent); documented as a known limitation.
- Confidence level: 95% throughout (alpha = 0.05 convention).
- Report-level groups are deterministic per report (single observation) and
  do not carry an interval or p-value, though they may be annotated with their
  cohort's confidence context.

---

## Pilot phase: provisional sampling numbers

These numbers are PROVISIONAL, set to run a pilot. They are not final. The
pilot reports the actual corpus distributions (see `04_corpus_survey.md`),
and we recalibrate these numbers from those distributions on the second pass.

### Unifying sampling principle: target-with-availability-cap
For every sampling axis (group, frequency band, vaccine pair): set a target;
cells at or above target are sampled down to it; cells below take everything
available and are flagged as under-target. The benchmark documents which
cells are under-target. This principle is stable; only the target numbers are
provisional.

### Per-group budget (provisional)
- Target T = 100 instances per group.
- Because refuted instances are generated by flipping supported cores, the
  binding requirement is roughly 50 viable cores per group (≈ 50 supported +
  ≈ 40 refuted-by-flip + ≈ 10 insufficient = 100). The starvation check is
  therefore against ~50 viable cores, not 100.
- Groups below the requirement take all available cores and are flagged.

### Verdict balance (provisional)
- Target 45 / 45 / 10 supported / refuted / insufficient per group.
- Refuted instances are generated by flipping a supported core (wrong
  direction for BOOL, plausible wrong option for CHOICE, off-by-enough value
  for PROP).
- Insufficient is CAPPED at the ~10% slice per group. Genuinely-insufficient
  cores (thin cohort, ties, indeterminable ordering) fill this slice but do
  not exceed it, so that "always answer insufficient" is not a winning
  shortcut.

### Frequency-band selection (provisional)
- Stratified sampling across frequency bands with a viability floor.
- Bands defined by quantile (default three: high / medium / low by cohort
  size), robust to whatever distribution the pilot reveals.
- Low-band floor (whether to keep n≥10 cores or raise the floor) decided from
  the pilot's CI-width distribution.

### Synonym sampling (locked, not provisional)
- One synonym sampled per instance per event slot, logged as an attribute.
- Do NOT generate one instance per synonym combination (avoids near-duplicate
  inflation). This is locked, not pilot-dependent.

### Multi-vaccine coverage (provisional, refined option 1)
- Accept unequal representation across the three vaccine pairs
  (Pfizer-Moderna, Pfizer-Johnson, Moderna-Johnson). Johnson-containing pairs
  will likely be smaller; accepted and flagged.
- For a core where one cohort is below threshold, the multi-vaccine verdict is
  `insufficient` (correct: not enough data to judge a difference). These count
  toward the capped insufficient slice, not on top of it.
- Contingent fallback (decide from pilot): if a Johnson pair has too few
  computable (non-insufficient) cores to fill even a reduced budget, drop that
  pair from the affected multi-vaccine groups in the pilot and note it as a
  limitation.

---

## Significance tests: final design (see 05_significance_tests.md)

### Two test representations per group
- CATEGORICAL test on the outcome label (binomial / multinomial counts).
- POSITION-BASED test on the event level indices (rank methods).
- Complementary, can disagree at the margin (diagnostic). Co-occurs has no
  position analog and is categorical-only.

### Categorical tests (exact primary, chi-square as large-n approximation)
- Binomial exact (1 cohort, 2 categories), null p0 = 1/2, 1/6, or 1/3.
- Fisher's exact (2 cohorts, 2 categories, 2x2).
- Exact multinomial goodness-of-fit (1 cohort, k categories); chi-square GOF
  is the large-n approximation.
- Fisher-Freeman-Halton exact (2 cohorts, k categories, 2xk); chi-square
  homogeneity is the large-n approximation.

### Position-based tests (non-parametric, no mean/variance)
- Wilcoxon signed-rank (1 cohort, paired events).
- Mann-Whitney U (2 cohorts).
- Friedman (1 cohort, 3 events ranked within report).
- Kendall's W (concordance, consistency questions).
- Kruskal-Wallis (3+ cohorts; reserved for future three-vaccine groups).

### Minimum-n constraint on every test
- Family floor: 20 per cohort for pairwise/co-occurs, 30 per cohort for
  sequence and first/last.
- Raised by the expected-count >= 5 guard for k-category distribution tests
  (1xk needs n >= 5k; 2xk needs each cohort large enough that every cell
  expects 5). The 2x6 sequence homogeneity group (S-M3) often fails and may be
  deferred.
- Below threshold the verdict is `insufficient`. Numbers are provisional;
  recalibrated from the pilot.

### Model runs the test
- The same closed-form tests run twice: offline for the gold label, and by the
  model at inference using a code-execution tool. Both use the same test and
  the same min-n helper, so they match by construction; discrepancy reflects
  the model's count extraction, which is the capability under test.

### No permutation; min-n gating instead
- Permutation/Monte-Carlo is excluded everywhere: it is not a closed-form step
  the model can run, and the gold label must use whatever the model runs.
  Sparse cases are gated to `insufficient` by the shared min-n helper.

### Shared min-n helper
- Standalone helper called by BOTH dataset creation and model evaluation.
  Gate-only (testable yes/no + reason, does not pick the test). Optional
  test-type argument enables the cell-adequacy check. Build the gold-label
  generator to call it, not inline the thresholds.

### Verdict polarity
- Most groups: significant = asserted effect is real.
- S-M3 and F-M1 ask "is it the SAME": significant = differs = "no" (inverted).
- F-M2 asks "do they differ": natural polarity. Per-group polarity flag needed.

### Evaluation modes (deferred to eval phase; see open_questions.md)
- Test-chosen-by-model (agentic, headline): grade on the verdict, allow valid
  alternative tests.
- Test-given-in-prompt (isolation): grade execution given the specified test.

---

## Sequence family: strict order over an orderable denominator (2026-07-01)

Context: strict 3-event orderings are rare in MedTempo (a specific triple is
fully orderable in only 15–32% of its reports; modal ordering share <=0.5), so
the sequence groups starved. Strict ordering is KEPT (co-occurrence must not
count as an order); the fix is to the denominator and floor, not the semantics.

### Strict ordering already captures gapped subsequences
- `sequence_holds` compares only the three events' levels, so `a<b<d<e<c`
  already yields `a<b<c` (intervening events ignored). No weak/co-occurrence
  reading is needed or wanted. A weak-order experiment was tried and REVERTED.

### Orderable denominator (amends the earlier rule 3)
- Sequence gold (`sequence_fraction`, `ordering_distribution`) now conditions on
  the ORDERABLE denominator: only reports where the three events occur at
  DISTINCT levels count; co-occurrence reports are excluded (not counted as
  evidence for or against the order). This makes "majority ordering" achievable
  and is consistent with pairwise-precedes, which already excludes co-exist from
  its denominator (rule 1). Supersedes the earlier "denominator = reports
  containing all three events" for sequence.

### Sequence viability floor lowered to n>=5 (provisional)
- `SEQ_MIN_N = 5` on the orderable denominator (min_n `sequence` floor = 5;
  first/last stays 30). Small n is acceptable because we control benchmark size
  and only need >=5–10 supported ("true") examples per template. Verified
  supported-capable cores per sequence template: S-V1 62, S-V2 275, S-V3 192,
  S-V4 62, S-M1 44, S-M2 75, S-M3 25, S-R1 489. Number is provisional/tunable.

### Deferred: wording/scope review
- Do NOT reword templates yet. The per-template true-case distribution is
  emitted by `scripts/make_examples.py` (examples.md). Review it before any
  wording change. Note: S-V4 (consistency) is viable under the orderable
  denominator (62 true cases) — likely no reword needed; S-M3 (25) is the
  poorest sequence template.
- Known nuance to revisit: `seq_bool` computes on the canonical ordering while
  the supported instance names the modal ordering (example shows k on the
  canonical) -- a display/semantics coherence item for the wording review.
  RESOLVED (2026-07-01): `seq_bool`/`prop_sequence` now compute on the MODAL
  ordering they name (k, p-value, and claim all reference the modal); the
  canonical-vs-modal mismatch no longer occurs. See the entry below.

---

## Significance-as-verdict + reword BOOL sequence/first claims (2026-07-01)

### Pipeline direction: the significance test IS the verdict (emerging)
- The intended framework pipeline is: the model runs the significance test
  first; a significant result in the asserted direction => `supported`, a
  significant result in the opposite direction => `refuted`, not significant =>
  `insufficient`. Under this pipeline the significance verdict and the
  supported/refuted verdict COINCIDE -- they are no longer two separate axes
  "reported together" (this refines the earlier "significance reframed as
  confidence quantification" entry, which kept them separate).
- This is the adopted direction; two sub-items are still open (below).

### Why some templates need rewording (the null must equal the claim boundary)
- "Significant => supported" is only coherent when the test's null p0 sits at
  the boundary the claim asserts. This holds for pairwise (claim "majority",
  null p0 = 0.5 -- same boundary) but BREAKS for the BOOL sequence/first-of-3
  claims: they are worded "typically / in the majority" (boundary 0.5) while
  their null is the CHANCE rate (1/6 for a 3-event ordering, 1/3 for
  first-of-3). A 30% modal ordering is significant vs 1/6 yet is not a majority,
  so test and claim disagree. Root cause: chance = 1/k, which equals 0.5 only
  when k = 2 (pairwise).

### Decision: reword to the chance null (not move the null to 0.5)
- Chosen: reword the BOOL sequence/first claims so the wording matches the
  existing chance null, rather than keep "majority" and move the null to 0.5
  (which almost nothing in this corpus clears -- see the funnel below).
  - `seq_bool` (S-V1, S-R1) and the seq_bool part of multi: "typically occur as
    A -> B -> C" / "in the majority" => "A -> B -> C is the most common (modal)
    ordering" (occurs more often than any other ordering / more often than
    chance).
  - `first_bool` (F-V3, F-R3, multi first): "X is usually the first" => "X is
    the most common first event" (first more often than chance).
- UNCHANGED: pairwise precedes/co-occurs (null already 0.5 = the majority
  boundary, so "typically/majority" is correct); the CHOICE modal_choice /
  first_choice groups (already tested vs uniform by GOF).

### Supporting evidence: the report -> core dilution funnel
- The corpus is fully used (all 3,166 reports; ~1,000 per vaccine, median 6
  terms/report). Scarcity is in the VIABLE CORES, not the reports. Funnel:
  pairwise pairs recur in a median ~30 reports (testable); triples co-occur in
  >=5 reports for only a few hundred combos, and after the STRICT-ORDER shrink
  the median orderable n is ~6 (max 9-28); multi-vaccine triples clear the
  floor in both cohorts with a median min(n1,n2) of ~7-8. So a sequence question
  is answered by ~6 strictly-ordered reports and a multi-vaccine question by
  ~7-8 per cohort -- below the power any test needs. This is why raising T
  cannot add significant cores (T caps how many enumerated cores we KEEP, not
  how many reports stand behind a question), and why S-M1/S-M2/S-M3/F-M3 have
  ZERO significant cores in the full enumeration.

### Still open
- Exact new claim strings per register (the YAML wording) for the reworded
  groups -- not yet written.
- The not-significant mapping: `refuted` vs `insufficient` (the clean option is
  one-sided test + direction => supported / refuted / insufficient; see the
  one-sided entry below, which now supplies the direction).
- Handling of the zero-supported groups (S-M1, S-M2, S-M3, F-M3): raising min-n
  will not help (already power-starved); candidates are drop or reword/rescope.
- Whether to raise the per-cohort min-n floor and/or add significance-stratified
  selection to lift the supported share where the inventory allows.

---

## One-sided directional tests for the significance verdict (2026-07-13)

Supersedes the "two-sided throughout" wording in the earlier significance
entries for the DIRECTIONAL tests only (the differ and omnibus tests are
unchanged). Context: under significance-as-verdict, `supported == significant`,
so the two-sided fail rate (78.5%, see `07_significance_findings.md`) is the
hard cap on the supported class. Two-sided tests are relabel-invariant -- the
p-value is a property of the data, not the claim direction -- so a supported-side
effect at 29/46 (two-sided p ~ 0.104) fails even though the data clearly favor
the claim.

### Decision: run the directional tests one-sided in the observed direction
- Single-proportion binomial modes (`dir_bool`, `dir_choice`, `prop_precedes`,
  `sym_bool_cooccurs`, `prop_cooccurs`, `seq_bool`, `prop_sequence`,
  `first_bool`) and the directional multi-vaccine Fisher modes
  (`multi_dir_precedes`, `multi_dir_cooccurs`, `multi_dir_sequence`,
  `multi_dir_first`) now test ONE-SIDED. The alternative is chosen from the
  observed proportion: above the null -> `greater` (tests the supported
  direction), below -> `less` (tests the refuted direction). So the test
  corroborates whichever gold verdict the core carries and does NOT reward the
  reverse claim.
- The reverse hypothesis now "means differently": on the same 29/46 data,
  "greater" gives p ~ 0.052 while "less" gives p ~ 0.96. This is the intended
  break from the two-sided relabel-invariance noted in `07_findings` §7.

### Unchanged (still two-sided / omnibus)
- `multi_differ_*` stay TWO-SIDED: "do they differ" is a symmetric question.
- The GOF (`modal_choice`, `consistency_bool`, `first_choice`, `last_choice`)
  and homogeneity (`multi_same_first`, `multi_differ_first`,
  `multi_same_modal_order`) tests are omnibus and have no one-sided form.

### Measured effect (full corpus, `data/medtempo.db`)
- Successful pairs (definite-gold categorical cores the test corroborates):
  1,976 -> 2,441 (**+465, +23.5%**); fail rate 81.4% -> 77.1%.
- Concentrated in the well-powered directional groups (P-V/C-V +53/+86 each,
  F-V3 +20, C-M2 +12). The power-starved sequence-multi groups (S-M1/S-M2) stay
  at 0 -- one-sided cannot add power that the n~6-8 cohorts do not have.
- Implementation: `alternative` arg on `binom_exact_p` / `fisher_exact_2x2`
  (`core/significance.py`, default still two-sided); direction chosen in
  `core_significance` (`core/answers.py`).

---

## Template redesign for testability: null alignment, PROP removal (2026-07-13)

Design session (not yet implemented in code except the one-sided tests above).
Guiding principle established this session: **every cohort-level claim must rest
on a principled null** -- either a chance baseline (0.5, 1/6, 1/3, uniform) or
another group in the data. A claim whose only reference is the true value itself
is fact-checking, not hypothesis testing, and does not belong in the benchmark.
Report-level groups stay exact/deterministic (no test) and are unaffected.

### LOCKED: S-V1 and F-V3 -> "most common", with a distributional test
- Wording: `seq_bool` (S-V1) -> "A -> B -> C is the **most common** ordering";
  `first_bool` (F-V3) -> "X is the **most common first** event". Keeps the vague,
  test-requiring phrasing; drops "typically/usually/majority" which implied a
  0.5 bar that the corpus cannot clear for 3-event orderings / first-of-3.
- Test MUST change with the wording: "most common" is an argmax (distributional)
  claim, NOT "beats chance 1/6". A binomial-vs-1/6 test does not verify it (a
  25% ordering beats 1/6 yet may not be the mode). Use **modal-vs-runner-up**:
  one-sided binomial of the claimed cell's count vs the runner-up's count, null
  0.5 ("does the named ordering significantly out-count its nearest
  competitor?"). Plain GOF-vs-uniform is rejected -- it only shows non-uniform,
  not that the *named* ordering is the mode.
- Consequence: S-V1 becomes a BOOL twin of S-V3 (modal_choice); F-V3 a twin of
  F-V1 (first_choice). Accepted; the redundant slots get backfilled from the
  replacement menu below.

### LOCKED: remove the PROP groups (P-V2, C-V2, S-V2)
- PROP claims ("in about {p}% of reports ...") are graded by a +/-5pp tolerance
  match against the computed cohort rate = point-estimate fact-check, no null.
  There is no non-arbitrary way to reword an absolute percentage into a test:
  the reference is either the truth (fact-check) or an injected threshold
  (arbitrary, or data-derived => leaky). So PROP is REMOVED, not reworded.
- Latent bug to fix regardless: `prop_precedes`, `prop_cooccurs`,
  `prop_sequence` are still in `_BINOM_NULL` (`core/answers.py`), so
  `core_significance` attaches a chance-null p-value that does not correspond to
  the PROP claim. Remove them from `_BINOM_NULL` when PROP is retired.
  (`make_examples.py::_categorical_definite` already excludes PROP.)

### LOCKED: S-V4 rule/test mismatch to fix
- `consistency_bool` gold uses `modal_share > 0.5` but the test is GOF-vs-uniform
  (departure from uniform). These can disagree independent of wording. Align the
  gold rule to the test (or vice versa) so the verdict and the p-value agree.

### PENDING: replacement groups for the retired PROP + redundant slots
A valid replacement needs a principled reference. Menu (see also
`open_questions.md`); recommended shortlist **R1 + R5 + R3**, primitive-preserving
mapping P-V2->R1, C-V2->R5, S-V2->R7 (or R1 on orderings):
- R1 pair-vs-pair precedence: "In {v}, A precedes B more often than C precedes
  D." (two-proportion; McNemar if reports overlap.)
- R2 event-vs-event first-rate: "In {v}, A is first more often than B is."
- R3 conditional antecedent: "In {v}, B follows A more often than B follows C."
- R4 temporal-gap magnitude: "In {v}, A and B are farther apart than C and D."
  (Mann-Whitney on level distances; position-based.)
- R5 association vs independence: "In {v}, A and B co-occur more than if
  independent." (2x2 chi-square/Fisher on presence x presence; best co-occurs
  replacement.)
- R6 concentration vs uniform (overlaps S-V4; could BE the fixed S-V4).
- R7 multiple-of-chance threshold: "A -> B -> C occurs at least twice the chance
  rate (>1/3)." (binomial vs k*p0; keeps a number, anchored to chance not data.)
- R8 strongest-pair superlative (CHOICE): "Among (A,B),(A,C),(A,D), A->B is the
  strongest ordering." (argmax + modal-vs-runner-up.)

Open: which subset to adopt; whether R6 folds into the S-V4 fix; exact
four-register YAML strings and the gold-verdict rule per chosen group; inventory
check for each replacement against the corpus before locking.

---

## Replacement menu narrowed by the R1-R8 corpus inventory (2026-07-14)

Ran all eight R1-R8 candidates over the full corpus
(`scripts/replacement_inventory.py`; table in `Findings_and_Templates.tex`
Section 5, "Replacement Template Inventory"). Viable = top-K enumerated cores
clearing the family floor; Sig = one-sided-significant cores (the supported
ceiling under significance-as-verdict).

### KEPT (in discussion): R1, R3, R4, R5
- **R3** conditional antecedent -- 372 sig cores (37.1%), median n 29. Powered;
  maps P-V2 -> R3.
- **R4** temporal-gap magnitude (Mann-Whitney on level distances) -- 1,635 sig
  (38.7%), median n 34. Richest; position-based.
- **R5** association vs independence (2x2 presence x presence) -- 144 sig
  (25.3%), each core over the whole ~1,000-report cohort so significance is
  robust; best co-occurs replacement, maps C-V2 -> R5.
- **R1** pair-vs-pair precedence -- 415 sig (18.4%), median n 28. Solid.

### REMOVED (do NOT re-propose these ideas): R2, R6, R7, R8
Recorded so they are not regenerated if more replacements are needed later.
- **R2** event-vs-event first-rate -- too thin: only 53 viable cores (a decisive
  winner-vs-runner-up first-of-3 split is rare in the corpus).
- **R6** concentration vs uniform -- not a new group: it is a GOF-non-uniform
  test = a restated S-V4 (29 sig). Fold into the S-V4 fix instead of adding.
- **R7** multiple-of-chance (>= 2x, i.e. > 1/3) -- too hard: 4.8% significant at
  the n~7 orderable sizes; the 2x-chance bar is unreachable in this corpus.
- **R8** strongest-pair superlative -- degenerate: ZERO significant cores (the
  top precedes-pair and its runner-up are statistically indistinguishable).

Still open: exact four-register YAML + gold-verdict rule for the kept
R1/R3/R4/R5; which of P-V2 -> R3, C-V2 -> R5, plus R4/R1, to actually
instantiate.

---

## Implemented: PROP retired + S-V1/F-V3 modal-vs-runner-up (2026-07-14)

Goal for this change: no template does rate/fraction checking any more (audited;
none remains in `src/`).

### PROP groups removed (P-V2, C-V2, S-V2)
- Deleted from the YAML, `MODE_BY_GROUP`, the `_build_vaccine_core` / feasibility
  / realize branches, `_BINOM_NULL`, and `prop_verdict` (+ its tests). An
  absolute-% claim graded by a +/-5pp tolerance is point-estimate fact-checking
  with no principled null, so it is retired, not reworded. Roster: 30 -> 27
  groups. The freed slots are to be backfilled from the R1/R3/R4/R5 menu.

### S-V1 (seq_bool) and F-V3 (first_bool) -> "most common" + modal-vs-runner-up
- Wording: "typically / usually / in the majority" -> "is the most common
  ordering" (S-V1) / "the most common first event" (F-V3). Verdict is now an
  argmax (like S-V3 modal_choice / F-V1 first_choice): supported iff a UNIQUE
  modal ordering / first event exists; a tie is `insufficient`; naming a
  non-modal refutes. No >0.5 rate threshold any more.
- Test: **modal-vs-runner-up** -- one-sided exact binomial of the top cell's
  count vs (top + runner-up), null 0.5, min-n 5. Verifies the NAMED item is the
  mode (which the old binomial-vs-1/6 and plain GOF-vs-uniform cannot). This is
  strictly harder than beats-chance, so their fail rate rises.

### New fail rate (post-redesign, 27 groups): 76.0% (2234/2939)
Progression two-sided -> one-sided -> post-redesign:
- overall 78.5% -> 74.7% -> **76.0%**
- pairwise-precedes 65.5% -> 61.2% -> 61.2% (unchanged by redesign)
- co-occurs 73.9% -> 67.0% -> 67.0% (unchanged)
- sequence 95.3% -> 95.2% -> **96.9%** (S-V1 stricter)
- first/last 70.2% -> 67.4% -> **76.7%** (F-V3 stricter)
Per-template counts are in `Findings_and_Templates.tex` / `Worked_Examples.md`.

### Still deferred / open
- **S-V4** (consistency_bool) rule/test mismatch NOT yet fixed (still
  modal_share>0.5 gold vs GOF-vs-uniform test).
- **S-V3 / F-V1 / F-V2** (modal_choice / first_choice / last_choice, CHOICE)
  still use GOF-vs-uniform; the same "GOF does not verify the named mode"
  critique applies -- candidates to also move to modal-vs-runner-up for
  consistency with their S-V1 / F-V3 twins.
- not-significant -> `insufficient` vs `refuted` mapping (deliberately deferred).

---

## Multi tier -> directional-only; adopt R1/R3/R5 (2026-07-28)

### Remove the "differ" and "same" multi groups (6)
Rationale: NHST can only REJECT the no-effect null, never ACCEPT it, so the
existence/equivalence claim shapes do not map onto supported/refuted/insufficient.
- "differ" (H1 = differ): significant -> supported, but not-significant can only
  be `insufficient`, NEVER a clean `refuted` (failing to reject != proving equal).
- "same" (the claim IS H0): can never be `supported` -- no evidence accrues FOR a
  null. This is why S-M3 / F-M1 were already degenerate (0 significant cores).
- Equivalence testing (TOST) could rescue "same" but needs an arbitrary margin
  delta -- the same unmotivated-number defect that retired PROP.
REMOVED: **P-M1, C-M1, S-M1** (rate/fraction differ), **S-M3, F-M1** (same),
**F-M2** (differ-first). The multi tier is now DIRECTIONAL-ONLY, which is the
fully hypothesis-aligned form: "higher after v1 than v2" makes both directions
one-sided alternatives -> supported / refuted / insufficient all well-defined.
KEPT (directional): P-M2, C-M2, S-M2, F-M3. No directional multi versions of the
new R-groups are added (removal only).

### Adopt R1, R3, R5 (single-cohort, principled null); drop R4
Fills the retired PROP slots + the S-V1/S-V3, F-V3/F-V1 redundancy. R4 (gap
magnitude) NOT adopted this round despite good inventory (kept simple). IDs and
answer types CONFIRMED (2026-07-28) -- all three are **BOOL**:

- **R3 conditional antecedent** = **P-V2** (freed), precedes family, vaccine
  level, BOOL, events A,B,C. Claim: "In {v}, {A} precedes {B} more often than
  {C} precedes {B}" (B's antecedent: A vs C). Gold: two independent proportions
  p1=P(A<B), p2=P(C<B) via `precedes_fraction`; verdict directional (supported
  p1>p2, refuted p1<p2, insufficient no sig gap); test = Fisher 2x2 one-sided
  (reuses `_FISHER` dir path). 372 sig cores in inventory.
- **R5 association vs independence** = **C-V2** (freed), co_occurs family,
  vaccine level, BOOL, events A,B. Claim: "In {v}, {A} and {B} occur together
  more than if independent." Gold: 2x2 presence x presence over the FULL cohort;
  null = independence; test = chi-square/Fisher; supported = significant POSITIVE
  association, refuted = significant negative, insufficient = n.s. Needs a new
  corpus helper (co-presence + marginals). 144 sig cores.
- **R1 pair-vs-pair precedence** = **P-V4** (new), precedes family, vaccine
  level, BOOL, events A,B,C,D (NEW 4-event slot). Claim: "In {v}, {A} precedes
  {B} more often than {C} precedes {D}." Gold: two independent proportions
  p1=P(A<B), p2=P(C<D); directional verdict; Fisher 2x2 one-sided. 415 sig. The
  two pairs need only each be viable in the cohort, not co-occur together.

### Resulting roster: 24 groups
27 (post-PROP) - 6 (multi removals) + 3 (R1/R3/R5) = 24. Every group is a
well-posed hypothesis test: chance-baseline single-cohort, or directional
two-cohort.

### Still open before coding
- IDs (P-V2=R3, C-V2=R5, P-V4=R1) and answer types (all BOOL) CONFIRMED
  2026-07-28. Remaining: exact four-register wording per group (to draft during
  implementation), and R5's new corpus helper + R1's 4-event enumeration shape.

---

## Verdict framework, alpha, and benchmark balance locked (2026-07-28)

### Verdict = a three-decision directional test
The gold verdict for a cohort-level claim is a three-decision (directional) test,
not the textbook two-outcome NHST. The null is nondirectional (no effect:
p = 0.5, or p1 = p2); the CLAIM asserts a direction, and the decision is:
- p (claim's direction) < alpha            -> **supported**
- else, p (opposite direction) < alpha     -> **refuted**
- else (neither direction significant)     -> **insufficient**
So supported/refuted both require significance (in opposite directions); a single
claim-direction p-value cannot separate refuted from insufficient -- the opposite
tail must be checked. `refuted` NEVER means "non-significant, therefore false"
(that would be accepting H0); it means positive counter-evidence.

Backing (for the write-up; verify exact cites): three-decision / directional
testing -- Kaiser (1960, Psychological Review), Jones & Tukey (2000,
Psychological Methods). Verification-label precedent -- FEVER
(Supported/Refuted/NotEnoughInfo), NLI (entailment/contradiction/neutral).
This supersedes the long-open "not-significant -> insufficient vs refuted"
question: it is **insufficient** (refuted requires a significant opposite effect).

### Alpha = 0.05 per side (one-sided directional), chosen for yield
Directional tests run one-sided in the observed direction at alpha = 0.05.
Rationale: it is a standard directional test AND maximizes usable cases (0.05 per
side == a two-sided test at 0.10). Known property to document: choosing the
direction after seeing the data makes the probability of declaring SOME direction
under a true null ~0.10 (2*alpha), not 0.05; the wrong-SIGN error stays <= alpha/2.
Tightening to 0.025 per side would pin the false-decision rate at 0.05 but shrink
the decisive-case supply -- rejected in favor of more cases. Alpha = 0.05 per side
fixed.

### Benchmark verdict balance = equal thirds (supersedes 45/45/10)
Target ~1/3 supported, 1/3 refuted, 1/3 insufficient per group. Rationale: the
three-decision test has three equally-legitimate outcomes with no cost asymmetry,
so equal mass caps every trivial policy ("always supported" = the yes-man,
"always insufficient" = the cop-out) at 33% = chance. Weighting any class inflates
that class's shortcut baseline (50/25/25 hands the yes-man 50%). Supersedes the
provisional 45/45/10.

- **Supply:** supported and refuted are both sourced from the S *decisive*
  (significant) cases -- one claim per case, orientation chosen (with the effect
  -> supported; against -> refuted). So supported + refuted <= S. Balanced thirds
  => per-group budget ~= **1.5 * S** (S/2 each of supported/refuted, S/2
  insufficient). Insufficient supply is effectively unlimited (downsample).
- Draw supported and refuted from **different event combinations**, never the
  exact A->B / B->A mirror of one case (that is a near-duplicate the model could
  exploit).
- **Availability cap** (existing principle): groups with tiny S (sequence:
  S-V1=4, S-M2=0) cannot fill the target -- take what is available and flag as
  starved; pairwise/co-occurs have S in the hundreds.

### Insufficient must span ALL of its sub-types (required)
The insufficient third is NOT one failure mode. It must include, and be labeled
by, all three:
1. **underpowered** -- events co-occur enough (n >= floor) but no significant
   effect either way;
2. **sparse** -- events co-occur but n < the min-n floor;
3. **not-locatable** -- one or both events absent, or the events never co-occur,
   so the conditioned n = 0.
Note: enumeration currently builds cores only from co-occurring events, so
(3) is NOT generated automatically -- not-locatable cases must be added
DELIBERATELY (they test whether the framework returns insufficient instead of
hallucinating a relationship). Caveat: under the unconditional association group
C-V2, a strong dissociation (both events common, never together) is a significant
NEGATIVE association -> **refuted**, not insufficient; the conditional groups give
insufficient there.

### Metrics
Grade with per-class precision/recall and macro-F1 (not bare accuracy), so the
result is robust to small deviations from exact thirds and the yes-man failure
(refuted-recall -> 0) is always visible.

---

## Implemented: three-decision labeler + shared min-n gate (2026-08-04)

Implements the 2026-07-28 verdict framework in code. New module
`core/verdict.py`; `core/answers.py` rewired; `scripts/run_verdict_labels.py`
emits the per-group label distribution (`data/pilot/verdict_labels.{md,json}`).

### Both tails are now computed, always
`core_significance` used to run one one-sided test in the OBSERVED direction.
That cannot express the three-decision rule: one p-value cannot tell `refuted`
(significant counter-evidence) from `insufficient` (nothing significant either
way). Every directional mode now returns `p_claim` (the claim's direction) and
`p_opposite`, and `verdict.three_decision` maps the pair to the label. The two
tails are provably mutually exclusive at any alpha < 0.5, so the check order is
cosmetic. The claim direction defaults to the core's canonical orientation;
`named=` labels an argmax claim naming any other cell, which is how a refuted
instance is built from a real core.

### Insufficient sub-types are labeled at the source
`three_decision` returns the sub-type the 07-28 decision requires:
`underpowered` (clears the floor, nothing significant), `sparse` (below the
family floor), `not_locatable` (n = 0). KNOWN GAP: the corpus fraction helpers
return None below the enumeration viability floor, DROPPING n, so a sparse core
and a not-locatable one are indistinguishable downstream -- 3,616 cores land in
an unlabeled bucket. Generating the deliberate `not_locatable` third needs those
helpers to report n even below the floor. Sub-type is left None rather than
guessed.

### Non-directional shapes are flagged, not forced
The omnibus GOF / homogeneity modes and the "differ"/"same" multi shapes have no
directional alternative, so no three-decision verdict exists for them. They are
labeled `insufficient` + `non_directional` rather than pushed into a verdict.
This is the same defect the 07-28 roster decision retires the multi groups for;
it now also lands on S-V3, S-V4, F-V1, F-V2 (all GOF-vs-uniform), which is the
deferred 2026-07-14 "move the CHOICE groups to modal-vs-runner-up" call, now
forced. See `open_questions.md`.

### Gate = the shared family floor (was a blanket n >= 10)
`significance.MIN_N = 10` no longer gates any label; `core.min_n.min_n_gate`
(20 pairwise/co-occurs, 5 sequence, 30 first/last) does, on the CORE's
conditioned denominator, per the 05 "one helper, applied in one place" rule. The
private `_MODAL_RUNNER_MIN_N = 5` floor on (top + runner-up) is gone with it.
`significance_verdict` survives as a raw two-outcome helper, documented as not
the label.

**This is a net LOSS of decisive cores, not the free gain sec.5 of
07_significance_findings anticipated** -- measured over the full corpus:
1,199 cores were decisive before and are not now (1,075 to the tightened floor,
124 to non-directional shapes); **0 gained**. The sec.5 "114 sequence cores
blocked by the n-gate" recovery is MOOT: the 2026-07-14 modal-vs-runner-up
redesign already replaced that test with a 2-cell one floored at 5.
The floor choice, not alpha or the test, is now the binding constraint on
supply. NOT LOCKED -- see `open_questions.md`.

---

## LOCKED + implemented: S-M2 removed as power-dead (2026-08-04)

**S-M2** (`multi_dir_sequence`, "A -> B -> C is more common after {v1} than
{v2}") is REMOVED. Evidence (`07_significance_findings.md` sec.10, measured over
all 90 computable cores):

- **the best directional p across every core is 0.0580** -- not one clears
  alpha; 3 cores reach p < 0.10, 6 reach p < 0.20;
- S = 0 at **every** floor from 5 to 40, so this is not the min-n question;
- 0/90 cores are combinatorially incapable (perfect separation would give
  p ~ 0.0002) -- the corpus simply never separates that cleanly at n ~ 6;
- cause: conditioning on *this triple* x *strict order* x *this vaccine* leaves
  a median of 6 orderable reports per cohort, and Fisher on 6-vs-9 resolves
  nothing.

Rejected alternative: reworking it as the position test (Mann-Whitney on the
focal event's within-triple rank over all co-present reports, median n = 21)
yields 6/90 decisive -- live but still starved, and it silently changes the
claim from an ordering-frequency claim to a rank claim. Not worth a group slot.

Distinguish this from **F-M3**, the other kept-but-S=0 multi group: F-M3 has 19
decisive cores at floor 10 and 5 at floor 20, dying only at the first/last floor
of 30. F-M3 is a FLOOR casualty and the open floor decision can revive it; S-M2
cannot be revived by any floor. Do not remove them for the same reason.

Removed from `data/templates/sequence.yaml`, `MODE_BY_GROUP`, the
`_MULTI_TRIPLE_MODES` / `_build_multi_core` / `feasible_polarities` / `realize`
branches, `_FISHER` (`core/answers.py`), and the pilot group list. The
`multi_dir_sequence` mode no longer exists. Roster: 27 -> **26** as coded
(the 2026-07-28 removals of P-M1/C-M1/S-M1/S-M3/F-M1/F-M2 and the R1/R3/R5
additions are still pending, which will take it to 23).

**Consequence to face during the roster migration:** with S-M1/S-M2/S-M3 gone the
sequence family has NO multi tier, and its entire cohort-level supply is S-V1's
4 decisive cores (S-V3/S-V4 being non-directional). Whether the sequence family
survives as more than a report-level group is now an open question, not a
detail -- see `open_questions.md`.

---

## LOCKED + implemented: min-n floor = 10, aligned with viability (2026-08-11)

The family floors are now **10 pairwise/co-occurs, 5 sequence, 10 first/last**
(`core/min_n.py`), replacing the 2026-08-04 provisional 20 / 5 / 30. The pairwise
and first/last floors are set to the **enumeration viability floor**
(`corpus._MIN_N = 10`), so the test gate no longer discards cores the enumerator
was willing to emit. Sequence stays at 5: its ORDERABLE denominator is thinner
than the others, and the 5 is load-bearing -- it is the only thing keeping S-V1
non-zero (S = 4 at 5, 0 at 10).

The principle: **one universal standard (10), with a survival exception for a
family that cannot generate anything at it.** A benchmark should hold every
shipped question to the same evidence bar, so the default is a single number for
all families; sequence gets 5 only because its supply is exactly zero at 10 and
the alternative is deleting the family's entire cohort-level tier. Any future
family is held to 10 unless it demonstrates the same zero-supply problem.

Rationale: the floor is a **quality** choice, not a validity one. The tests are
exact, so they are valid at small n; the floor only decides how thin the evidence
behind a shipped question may be. At 20 / 30 the floor was the binding constraint
on the whole benchmark's supply, costing pairwise 55% and first/last 85% of their
decisive cores, and it was doing so to buy a robustness the exact tests already
provide.

### Measured effect (full corpus, regenerate with `scripts/run_verdict_labels.py`)

| | floor 20/5/30 | **floor 10/5/10** |
|---|--:|--:|
| Decisive cores S (all groups) | 587 | **1362** |
| P-V1 / P-V3 | 130 | **218** each |
| C-V1 / C-V3 | 266 | **378** each |
| F-V3 | 21 | **74** |
| P-M2 | 18 | **30** |
| C-M2 | 23 | **43** |
| F-M3 | **0** | **19** |
| S-V1 | 4 | 4 (floor unchanged) |

**F-M3 is revived**, as the 2026-08-04 S-M2 entry anticipated: it was a floor
casualty, not power-dead. The multi tier is now P-M2 (30), C-M2 (43), F-M3 (19),
all live. Groups still at S = 0: P-M1, C-M1, S-M1, S-M3, F-M1, F-M2 (all six
pending removal) plus S-V3, S-V4, F-V1, F-V2 -- so **after the roster migration
the only remaining S = 0 groups are the four non-directional ones**, which makes
the non-directional decision the sole surviving supply blocker.

### Consequence: the `sparse` insufficient sub-type is now unreachable

`sparse` was defined as the band between the viability floor and the test floor.
Setting them equal collapses that band to nothing -- measured `sparse` count is
now exactly **0** (it was the band 10-19 / 10-29). Cores below 10 are not
enumerated at all, and the corpus helpers drop their n, so they land in the
`unknown` bucket (3,319 cores) rather than in `sparse`.

The 2026-07-28 decision REQUIRES the insufficient class to span all three
sub-types, so this must be fixed, not accepted. Next-steps item B (helpers report
n below the viability floor) is now a prerequisite for **two** sub-types --
`sparse` as well as `not_locatable` -- and B alone is not sufficient: enumeration
itself stops at 10, so sourcing `sparse` also needs a sub-viability enumeration
path for the insufficient class. See `open_questions.md`.

### Re-validation of the multi tier at the new floor (done)

`08_multi_tier_inventory.md`'s permutation nulls were all computed at floor 20,
so every `p_perm` in it is stale. Re-run at floor 10 with 2000 rounds
(`data/pilot/multi_inventory_floor10_2000rounds.json`): P-M2 **0.025** and M-F
**0.033** still clear; C-M2 still fails (**0.151**); and **both single-event
candidates now fail** -- M-H 0.035 -> **0.120**, M-C 0.055 -> **0.073**. The 08
doc's recommendation of a "P-M2 (or M-F) + M-H + F-M3" tier therefore does not
survive this decision, and is flagged stale in place.

Two open consequences (see `open_questions.md`): the validated multi tier
collapses to a single claim family (P-M2 and M-F are the same claim, so only one
ships), and 200 rounds is now known to be too coarse for a ship/no-ship call --
M-C crossed the alpha line between 200 and 2000 rounds, so the next-steps F
permutation gate needs >= 2000 rounds.

---

## LOCKED + implemented: exact tests only, chi-square abandoned (2026-08-11)

**Every benchmark label comes from an exact test, at every n.** The asymptotic
chi-square path is removed from the codebase, not merely deprioritised:
`significance.chi2_gof` and `significance.chi2_contingency` are deleted, and
`multinomial_gof` / `contingency_test` now call the exact multinomial GOF and
Fisher-Freeman-Halton unconditionally.

Rationale: current practice favours exact inference well past the n this corpus
reaches, so the approximation was buying nothing but ambiguity. It also removes a
class of question the benchmark should not have to answer -- "which test produced
this gold label?" -- since the answer is now always the same test for a given
claim shape.

Consequences:

- **The expected-cell guard is gone.** `min_n.MIN_EXPECTED` and
  `min_n.uses_exact` (plus the `_min_expected_*` helpers) are deleted: they
  existed only to choose between chi-square and exact. The min-n gate is now a
  pure family floor and nothing else. `05_significance_tests.md`'s "binding
  constraint" column is updated -- no row says ">= 5 per cell" any more.
- **`chi2_sf` survives, but only as a distribution function** for the rank
  diagnostics in `core.positions`, which produce no label and are themselves
  under review (their normal approximation is anti-conservative on tie-heavy
  data). Nothing on the label path consults a chi-square distribution.
- **Feasibility is now a real constraint, and it fails loudly.** The k-category
  exact tests enumerate every table with the observed margins -- `C(n+k-1, k-1)`
  for GOF -- so cost grows fast in k. Past `EXACT_MAX_TABLES` (5,000,000) the
  test raises `ExactTestTooLarge` instead of falling back. An infeasible table is
  a design signal (coarsen the categories, or gate the core out), not something
  to approximate away.

### Measured effect (full corpus)

Feasible everywhere: no core in any group trips the cap, and the full labeling
run takes ~17 s. **Four cores changed**, all omnibus first/last distribution
tests where the chi-square tail claimed significance and the exact test does not:

| group | chi-square regime | **exact only** |
|---|--:|--:|
| F-V1 first_choice (omnibus significant) | 130 | **129** |
| F-V2 last_choice (omnibus significant) | 176 | **173** |
| S-V3 / S-V4 | 14 / 14 | 14 / 14 (already exact -- tiny n) |
| every directional group | unchanged | unchanged (already exact) |

S is unchanged at **1362**: the four affected cores sit in non-directional groups
that contribute 0 decisive cores either way. So the correction is invisible in
supply but not in correctness -- and it is in the expected direction, chi-square
being anti-conservative in the tail. The modal-vs-runner-up rescue counts are
also unchanged (S-V3 4, F-V1 74, F-V2 86); that test is an exact binomial
already.

Note for the Overleaf draft: its F-V1 = 130 and F-V2 = 176 are now 129 and 173.

---

## LOCKED + implemented: the gold label IS the three-decision verdict (2026-08-11)

Step C of `09_next_steps.md`. The released `gold_verdict` for every cohort-level
instance now comes from `core.verdict.three_decision`, not from the point-estimate
majority rule. The rule was implemented and measured since 2026-07-28 but was
authoritative for nothing: `generation.cores.realize` stamped
`aggregation.bool_verdict` (proportion > 0.5 -> supported) and
`feasible_polarities` admitted supported/refuted whenever the proportion sat off
0.5 by 1e-12.

### Why this had to land before any modeling

Under the retired rule, "Chills typically precedes Dizziness" at 11/20 in Pfizer
shipped as a **supported** gold label. A framework answering `insufficient` --
the correct answer to a coin flip -- was scored **wrong**. The benchmark was
rewarding overconfidence and penalising statistical caution, the exact opposite
of what it claims to measure. Any eval run before this flip measured the wrong
thing.

### Measured effect (11,867 cohort-level cores)

| legacy \ three-decision | supported | refuted | insufficient |
|---|--:|--:|--:|
| supported (4,852) | 584 | 0 | **4,268** |
| refuted (3,498) | 0 | 942 | **2,556** |
| insufficient (3,517) | 0 | 0 | 3,517 |

**57.5% of cores change label.** Critically, nothing flips supported <-> refuted:
both cells are 0. Three-decision is strictly more conservative than the point
estimate, never contradictory about direction, so this is a precision change and
not a reinterpretation of the corpus.

### Two mechanisms, not one

1. **The label.** `realize` overrides the realized verdict for cohort-level cores:
   orienting a DECISIVE core with its effect gives `supported`, against it
   `refuted`; a non-decisive core gives `insufficient` in either orientation.
2. **Feasibility.** `feasible_polarities` now gates on decisiveness, so the
   sampler can only draw supported/refuted from decisive cores. This is what makes
   "S caps both classes" true in code rather than only in the plan.

### New distinction: ORIENTABLE vs data-fixed modes

Surfaced by this work. `_ORIENTABLE` = the modes whose claim can be posed either
way from one core -- by flipping the event order (`dir_*`), naming a non-modal
cell (the argmax modes), or swapping cohorts (`multi_dir_*`). A decisive
orientable core supplies BOTH classes.

`sym_bool_cooccurs` (C-V1, C-V3) is **not** orientable: "A and B typically
co-occur" is symmetric, so there is nothing to flip. Its class is fixed by which
tail fired, and a decisive core supplies exactly ONE of supported/refuted. This
matters for the sampler: C-V1/C-V3 contribute 40 supported and 338 refuted, and
no orientation trick rebalances them.

### Side effects

- The `multi_differ_*` / `multi_same_*` groups now emit `insufficient` for every
  instance (0/0/10 in the pilot). Correct and honest: they are non-directional, so
  three_decision refuses to force a verdict. They are the six groups the 07-28
  roster decision retires.
- Fixed a PRE-EXISTING break in `run_pilot.py`, unrelated to this change and
  present on HEAD: `pilot.VALIDATION_GROUPS` still named the PROP groups retired
  on 2026-07-14, so the pilot died with `KeyError: 'P-V2'`. It now skips ids that
  no longer exist. The pilot generates end-to-end again.
- Test fixtures across `tests/generation/` used 14/20 as their "clearly
  supported" case -- one-sided p = 0.058, i.e. precisely the class this flip
  reclassifies. Moved to 16/20 (p = 0.0059). A new test in `test_answers.py` pins
  the emit path to the labeler so `generation.cores` and `core.answers` cannot
  drift.

### Still open

The pilot still targets the provisional 45/45/10 balance; equal thirds is step D.
And with C-V1/C-V3 supplying 40/338, per-group equal thirds may not be reachable
for every group -- see `open_questions.md`.

---

## LOCKED + implemented: helpers measure, the gate decides (2026-08-11)

Step B of `09_next_steps.md`. The cohort fraction helpers in
`generation/corpus.py` and their DB-backed mirrors in `core/aggregation.py` no
longer apply a private floor. Each reports its conditioned denominator `n`
whatever its size, including 0, and the floor is applied in exactly one place --
the shared gate in `core/min_n.py`.

Before this there were **two floors in two places**: `corpus._MIN_N = 10` /
`SEQ_MIN_N = 5` inside the helpers, plus the family floors in the gate. The
helpers returned `None` below their own floor, which threw n away, and that made
`sparse` (0 < n < floor) indistinguishable from `not_locatable` (n = 0)
downstream -- 2,838 cores sat in an unnamed bucket. It also violated the
05_significance_tests rule that the threshold is defined and applied in one place.

### Contract change

- The tuple helpers return `tuple[float | None, int]`, never `None`. The fraction
  is None **exactly when n = 0**, since a proportion over an empty denominator
  does not exist.
- The dict helpers (`first_among_fractions`, `last_among_fractions`,
  `ordering_distribution`) always return a dict; at n = 0 the per-term fractions
  and `modal_share` are None and `modal` is None.
- **`ViableCore.computable` is redefined**: it now means "clears the shared family
  floor" (`_is_testable`, which calls `min_n_gate`), not "the helper returned
  something". Non-computable cores now CARRY their n and, for two-cohort modes,
  both n and n2 -- that is the entire point.

### Measured effect (11,867 cohort-level cores)

| insufficient sub-type | before | after |
|---|--:|--:|
| underpowered | 5,646 | 5,646 |
| **sparse** | **0** | **2,722** |
| **not_locatable** | **0** | **116** |
| unknown (n dropped, unnameable) | 2,838 | **0** |

**The invariant held: S = 1526, 584 supported / 942 refuted, unchanged.** Correct
by construction -- a sub-floor core cannot be decisive, because the gate rejects it
before either tail is consulted -- and worth pinning, since it is what makes this a
labeling improvement rather than a change to the corpus's evidence.

### Where each sub-type actually comes from

`sparse` is dominated by the **pairwise precedes** and **sequence** shapes:
P-V1/P-V3 384 each, S-V1/S-V3 451 each, P-M1/P-M2 257 each. Cause: enumeration
filters on **co-occurrence** count, while the test denominator is the strictly
**ordered** (or orderable) subset, which is smaller. The gap between those two
quantities is the sparse band. Example: Abdominal pain upper / Fatigue in Pfizer
co-occurs often enough to enumerate but is strictly ordered in only 9 reports.

`not_locatable` comes entirely from the **sequence** groups (S-V1/S-V3 30 each,
S-M1/S-M3 28 each): triples that are present but always at the SAME level, so the
orderable denominator is 0. There is genuinely no ordering to locate. Semantically
exactly what the sub-type is for.

### Still open for step D

`not_locatable` has **zero supply in the pairwise, co-occurs and first/last
families** -- the co-occurrence pre-filter guarantees a non-empty denominator
there. So the insufficient third cannot span all three sub-types *within* those
groups from enumeration alone, and 116 cores total is well under the ~254 an
equal-thirds insufficient class would want. The deliberate `not_locatable`
generation the 2026-07-28 decision calls for is still required for those families;
the pilot's enumeration path (all combinations of the top-K terms, unfiltered by
co-occurrence) is the natural source. See `open_questions.md`.

---

## CLARIFIED: "directional" and "orientable" are different properties (2026-08-11)

Not a change of behaviour -- a conceptual distinction that the code implemented
correctly but the prose conflated. It has to be right before the sampler (step D)
encodes it.

### The criterion for whether `refuted` exists at all

**Is the negation of the claim a REGION of parameter space, or a POINT?** A region
can be confirmed by evidence; a point null can only fail to be rejected.

| claim | its negation | `refuted` available? |
|---|---|---|
| C-V1: co-existence rate **> 0.5** | rate **< 0.5** -- a region | **yes** |
| P-V1: P(A before B) **> 0.5** | **< 0.5** -- a region | **yes** |
| argmax: count(named) **>** runner-up | **<** runner-up -- a region | **yes** |
| "the two cohorts **differ**" | p1 **=** p2 -- a **point** | no |
| GOF: "**not** uniform" | **exactly** uniform -- a **point** | no |

This is what the 2026-07-13 "reword to the chance null" decision bought: every
claim's boundary now sits at a chance baseline with two testable sides.

### The two properties

- **DIRECTIONAL** -- a reversed hypothesis exists and can be significant. This
  licenses `refuted`. `refuted` NEVER means "not significant, therefore false".
- **SLOT-ORIENTABLE** -- the claim can be re-worded from a single core to assert
  either side, by reassigning slots. This makes a group's supply BALANCED.

They are independent. **C-V1/C-V3 are directional but not slot-orientable.**

Worked example, C-V1 *Abdominal pain upper / Headache* in Pfizer, co-existence
0/10: `p_claim` (rate > 0.5) = 1.000, `p_opposite` (rate < 0.5) = **0.00098**, so
the verdict is `refuted` on significant counter-evidence. "A and B do not
typically co-occur" is a substantive claim about the world -- they are usually
recorded at *different* timeline stages -- and the data confirms it. That is
categorically unlike "differ", whose negation is the point null p1 = p2.

But swapping A and B changes nothing, since co-occurrence is symmetric. So which
class a core supplies is fixed by the data, and C-V1/C-V3 arrive **40 supported /
338 refuted**. That is a WORDING limitation, not a statistical one.

### Consequence: negation is the orientation operator for symmetric claims

For P-V1 we flip the event order, which swaps `p_claim` and `p_opposite`. For a
symmetric claim there is no event flip -- but negating the sentence does the same
job: "A and B do **not** typically co-occur" makes the asserted direction the
lower tail, so the old `p_opposite` becomes the new `p_claim`. Negation does not
manufacture a verdict; it re-words the instance so the assertion matches the
direction the evidence already supports.

| core | plain wording | negated wording |
|---|---|---|
| rate significantly > 0.5 (40 cores) | supported | refuted |
| rate significantly < 0.5 (338 cores) | refuted | supported |

Choosing per core turns 378 decisive cores into a balanced **189 / 189**, instead
of capping the group at 120 and discarding 298 cores.

Caveat to track: a negated claim also tests negation handling, so a group mixing
both measures slightly more than pure temporal reasoning. The negated fraction is
reported per instance rather than left implicit.

### Code

`generation.cores._ORIENTABLE` is renamed **`_SLOT_ORIENTABLE`**, because the old
name reads as "has no reverse" for the modes it excludes -- which is exactly the
confusion this entry exists to prevent.

---

## LOCKED: negation is OPTIONAL and minimised (2026-08-11)

Refinement of the negation entry above. Negation is a supply mechanism for the two
symmetric groups, not a structural part of the design.

- **Only C-V1 and C-V3 need it** -- 2 of 25 groups. Every other cohort group is
  slot-orientable, so its equal-thirds budget is already 1.5*S and negation adds
  nothing.
- **It never displaces the original wording.** Minimum negated for C-V1 is 149 of
  378 decisive cores (**39%**), so **61% keep the plain claim**.
- **It is NOT configurable.** An `allow_negation` opt-out was added and then
  removed the same day: switching negation off costs C-V1/C-V3 894 items (120 each
  instead of 567) and buys nothing, since only 2 of 25 groups are affected and 61%
  of their instances keep the plain claim anyway. Negation applies wherever the
  template YAML provides it.
- **Samplers must PREFER PLAIN WORDING**: take the class the data already falls
  on, and negate only to fill the remaining deficit. A naive alternating
  assignment produces 197 negated instead of 149 -- ~48 needless negations. This
  is a requirement on step D.

### Why S is unchanged at 1526

S counts decisive **cores** -- whether the test settles the claim, which is a
property of the data and the test, not of the wording. Negation changes which
CLASS a core can be posed as, never whether it is decisive, so S is invariant
under negation by construction.

What negation changes is the **usable** fraction of that supply under equal
thirds:

| | items |
|---|--:|
| without negation | 1,394 |
| with negation | **2,288** (+894, +64%) |

All of the gain is C-V1/C-V3: without negation the group is capped by its scarcer
class (3 x min(40, 338) = 120 items, using 80 of 378 decisive cores and discarding
298); with negation all 378 are usable either way (1.5 x 378 = 567).

### Roster arithmetic (for the record)

25 groups = **7 report-level** (deterministic, no test) + **18 cohort-level**
carrying a test. Of the 18, **12 have S > 0** and ship today; the **6 at S = 0**
are the non-directional multi groups pending removal. So 19 of 25 groups can
produce instances.


---

## Template count: what changed since the Overleaf draft (2026-08-11)

Recorded because the draft's "17 hypothesis-test groups" and the code's counts
look inconsistent and are not. **min-n changed neither number.**

The published draft lists exactly 17 testable groups: P-V1, P-V2*, P-V3, P-V4*,
P-M2, C-V1, C-V2*, C-V3, C-M2, S-V1, S-V3, S-V4, S-M2, F-V1, F-V2, F-V3, F-M3
(plus 7 report-level = 24). Three of those (*) are DESIGNED BUT NOT BUILT --
R3/R5/R1, still pending in the roster migration.

| step | testable |
|---|--:|
| Overleaf draft (Jul 28) | **17** |
| − S-M2, power-dead (08-04) | 16 |
| − S-V4, non-directional and unrescuable (08-11) | **15** |
| − P-V2 / P-V4 / C-V2, designed but not implemented | **12** |

So 12 groups ship a verdict today, and the gap from 15 is entirely the three
unbuilt groups -- not the floor. Separately, `load_groups()` reports **18**
testable, because the code still contains the six non-directional multi groups
(P-M1, C-M1, S-M1, S-M3, F-M1, F-M2) that the draft already retired on paper;
roster migration A deletes them. All six sit at S = 0, so they cost nothing but
count.

What min-n DID change is S, not the roster: 587 (floors 20/5/30) -> 1362
(floors 10/5/10) -> 1526 (after the argmax test swap).

### Ceiling on S

S is capped by the cores that clear the gate, so the hard ceiling with the current
roster is **9,029** against an actual **1,526** -- a 17% decisive rate, headroom
7,503. The rate is the interesting part, and it is very uneven:

| group | clears gate | S | decisive rate |
|---|--:|--:|--:|
| C-V1 / C-V3 | 959 | 378 | **39%** |
| P-V1 / P-V3 | 575 | 218 | **38%** |
| F-V2 | 756 | 86 | 11% |
| F-V1 / F-V3 | 756 | 74 | 10% |
| P-M2 | 322 | 30 | 9% |
| C-M2 | 579 | 43 | 7% |
| F-M3 | 387 | 19 | 5% |
| S-V1 / S-V3 | 275 | 4 | **1%** |

Reading it: single-cohort pairwise questions rest on ~30 reports each and settle
~4 times in 10. Two-cohort and sequence questions slice the corpus to ~6-8 reports
and settle ~1 in 20, or 1 in 100 for sequence. That gradient is a property of the
corpus, not of the tests, and it is what makes the verdicts non-trivial.

The ceiling is not reachable by tuning -- closing it would need either more
corpus or coarser events (the MedDRA option in `open_questions.md`). The three
unbuilt groups are the only near-term additions; the draft's estimates for them
(P-V2 372, P-V4 415, C-V2 144) predate the floor change and need re-measuring.

---

## LOCKED: effect size measured on the tested quantity (2026-08-11)

The five argmax modes (`seq_bool`, `modal_choice`, `first_bool`, `first_choice`,
`last_choice`) test named-vs-runner-up on a 2-cell table against 0.5, but their
effect size was still measured against the retired GOF-vs-uniform references
(1/6 over orderings, 1/3 over candidates). So the p-value answered "does the named
cell beat its rival?" while `effect_size` answered "how far above chance-uniform is
this share?" -- the same claim/test mismatch the morning's test swap fixed for the
p-value, left behind in a released field.

Now: `_null_ref` returns **0.5 for every mode**, and the effect size for the argmax
modes is computed on **named / (named + runner-up)**. The reported `proportion` and
the CI stay on the share of the whole denominator, which is the better descriptive
number -- only the effect size moves onto the tested quantity.

Worked case, F-V1 (Chills, Headache, Pyrexia) in Janssen -- Headache 22, Chills 21,
Pyrexia 2:

| | before | after |
|---|--:|--:|
| effect_size | **-0.670** | **+0.023** |
| p_claim | 0.500 | 0.500 |

A large negative effect reported beside p = 0.50 was incoherent. F-V2 on the same
triple (Headache 28 vs Pyrexia 16) now reads effect +0.276 with p = 0.048 -- both
statistics agreeing there is a real effect.

---

## LOCKED: verdict balance is enforced PER GROUP (2026-08-11)

Confirms the 2026-07-28 equal-thirds decision at the per-group level rather than
benchmark-wide. Two independent reasons:

1. **We cannot control per-group viable-case counts.** S ranges from 4 (S-V1,
   S-V3) to 378 (C-V1, C-V3) and is a property of the corpus. Benchmark-level
   balance would let the big groups set the overall mix while individual groups
   drifted arbitrarily far from thirds.
2. **Group identity is inferable from the text.** Template wording is mechanical
   and fixed per group, so "After {v}, do {A} and {B} typically co-occur?" is a
   C-V1 fingerprint. A group shipped at 40/338 would let a model learn "text
   shaped like this -> answer refuted" and score ~89% on it with no temporal
   reasoning. Benchmark-level balance only closes that shortcut if group identity
   is hidden, which it cannot be.

Cost, accepted: groups with tiny S are taken in full and flagged as starved
(S-V1/S-V3 at 6 items each). Negation removes the cost for C-V1/C-V3.

---

## REJECTED: equivalence margins to revive the "differ"/"same" multi groups (2026-08-11)

**The idea is conceptually right and empirically not worth it.** Recorded so it is
not re-proposed.

The reasoning is sound and follows directly from the region-vs-point criterion:
`p1 = p2` is a POINT null, so it can never be confirmed -- but
`|p1 - p2| < delta` is a REGION, so with an equivalence margin BOTH framings
become testable and `refuted` becomes reachable. That would revive up to six
groups currently at S = 0.

Measured (TOST convention, 90% Newcombe CI on the difference; `equivalent` when the
CI sits inside the margin, `different` when it lies wholly outside):

| delta | equivalent | different | decisive |
|--:|--:|--:|--:|
| 0.05 | 0 | 81 | 81 |
| **0.10** | **1** | **52** | **53** |
| 0.15 | 36 | 21 | 57 |
| 0.20 | 119 | 10 | 129 |
| 0.30 | 521 | 1 | 522 |

Why it fails at a defensible margin:

- **0.10 is the project's own margin** -- the initial-seed rule 8 already sets
  |p1 - p2| > 10pp as the "differ" threshold. At delta = 0.10, exactly **1 core out
  of 1,378** can be declared equivalent. The "same" claims the reframing was meant
  to rescue essentially do not exist.
- **It is worse than the directional framing already in place.** At delta = 0.10,
  P-M1 yields 15 "different" cores from the same 322 cores that P-M2 already turns
  into 30 decisive. Requiring the CI to clear a 10pp margin is strictly stricter
  than requiring significance against 0.
- **The large yields need an indefensible margin.** delta = 0.20-0.30 means calling
  a 20-30 percentage-point gap in adverse-event timing "practically the same",
  which is not a claim this benchmark should assert.
- **Equivalence is structurally underpowered here.** Fitting a difference CI inside
  +/-10pp needs roughly n ~ 100-200 per cohort; the multi tier conditions down to
  n ~ 6-20. This is a corpus-size limit, not a test choice.

Conclusion: keep the multi tier directional. The six non-directional groups stay
slated for removal, now with a measured reason rather than only a conceptual one.

---

## FIXED: released statistics describe the instance's own claim (2026-08-11)

**Diagnosis: an instruction conflict, not a calculation error.** Every number was
computed correctly -- for a different claim than the one in the record.

`core_significance(core)` describes the core's CANONICAL claim. `realize` produces
an ORIENTED instance (reversed event order, a different named cell, swapped
cohorts, or a negated predicate). `instances.py` emitted both in one record: the
text, `gold_verdict` and `gold_proportion` oriented, the `p_claim` / `p_opposite` /
`p_value` / `effect_size` canonical. A comment in `instances.py` explicitly
INSTRUCTED that mixture as a deferral ("the per-instance ORIENTED label lands with
the equal-thirds sampler rewrite"), so two definitions of "the claim" coexisted by
design.

Measured before the fix: **576 of 2,864 cohort records (20%)** carried a `p_claim`
that contradicted their own asserted proportion. Worst reading:

> "Does Chills typically occur before Pyrexia after Moderna?" -- asserted
> proportion **0.675**, `gold_verdict` **supported**, `p_claim` **0.9917** (not
> significant), `p_opposite` **0.019** (significant).

### The fix

The conflicting instruction is removed. `answers.oriented_significance(facts)`
computes the tails for the ASSERTED claim, and `instances.py` uses it. Three cases,
the first two exact rather than approximate:

- **Reversed direction / swapped cohorts** -> the tails SWAP. Under the 0.5 null the
  assertion's count goes k -> n-k and P(X >= n-k) = P(X <= k) by the binomial's
  symmetry about 0.5; Fisher's one-sided tails mirror the same way.
- **Negated predicate** -> also a swap, which is precisely why negation works as an
  orientation operator.
- **A different named cell** (argmax modes) -> NOT a swap; the 2-cell table changes,
  so the tails are recomputed via `named=`.

`core_test_verdict` is retained as PROVENANCE (the canonical verdict, deliberately
allowed to differ) and a new `test_verdict` field carries the asserted claim's
verdict, which must equal `gold_verdict`.

### A second bug the verification exposed

Checking the fix surfaced 24 records labelled `insufficient` whose own statistics
said `refuted`. Cause: `_realize_insufficient` asserted `core.events` verbatim, so
for an argmax mode it named whichever candidate sorts FIRST ALPHABETICALLY rather
than the modal one -- a different claim, and one the data can decisively refute
(naming a 2/116 candidate against a 22/116 mode). It now orients the slots the way
the supported branch does. Also note: decisiveness is NOT orientation-invariant for
argmax modes, since a core whose mode barely beats its runner-up can still
decisively refute a far weaker candidate.

### Verification (full pilot, 5,488 cohort records)

| check | before | after |
|---|--:|--:|
| `p_claim` contradicts its own asserted proportion | 576 | **0** |
| `test_verdict` != `gold_verdict` | 24 | **0** |
| `supported` with p_claim >= 0.05 | — | **0** |
| `refuted` with p_opposite >= 0.05 | — | **0** |
| `insufficient` with a significant tail | — | **0** |

Note one of the first checks I wrote was itself wrong: it flagged refuted records
for having a large `p_claim`, but `refuted` requires the OPPOSITE tail to be
significant, so a large claim tail is correct there. The corrected checks test each
verdict against the tail its own definition uses. All five are now regression tests.

---

## IMPLEMENTED: equal-thirds sampler, per group (2026-08-11) -- step D, cohort level

`generation/sampling.balance_group` replaces the provisional 45/45/10 and the
T = 100 per-group target. Per group: **S // 2 supported, the same refuted, the same
insufficient**, so the budget is ~1.5*S and the group is internally balanced. The
budget comes from the group's own decisive supply because S is a corpus property
ranging 4..378.

Three rules it now enforces that the old sampler did not:

1. **One claim per decisive core.** The retired sampler, when short on refuted,
   re-used cores it had already emitted as supported -- shipping the A->B / B->A
   mirror of one case with both labels, which the 2026-07-28 decision forbids.
2. **Minimum re-orientation.** Each class is drawn from the cores whose data
   already falls on that side before borrowing from the other. For C-V1/C-V3 this
   is the negation minimisation (plain wording wherever the data allows); elsewhere
   it minimises slot flips. Reported per group as `reoriented`.
3. **The insufficient third spreads across sub-types**, allocated round-robin one
   unit at a time (`_water_fill`), so a short sub-type takes all it has and the
   remainder spills to the others -- "spread evenly; if a type runs short, use it
   all and make up the difference from the rest".

### Measured (pilot enumeration; S is smaller here than whole-population because
the pilot draws from top-K terms)

| group | S | target | sup/ref/insuf | reoriented | insufficient sub-types |
|---|--:|--:|---|--:|---|
| P-V1 / P-V3 | 165 | 82 | 82/82/82 | 43 | 27 not_loc / 28 sparse / 27 underpow |
| C-V1 / C-V3 | 252 | 126 | 126/126/126 | 102 | 23 not_loc / 52 sparse / 51 underpow |
| P-M2 | 29 | 14 | 14/14/14 | 8 | 5 / 5 / 4 |
| C-M2 | 28 | 14 | 14/14/14 | 5 | 5 / 5 / 4 |
| F-V1 / F-V3 | 56 | 28 | 28/28/28 | 28 | 10 / 9 / 9 |
| F-V2 | 58 | 29 | 29/29/29 | 29 | 10 / 10 / 9 |
| F-M3 | 17 | 8 | 8/8/8 | 4 | 3 / 3 / 2 |
| S-V1 / S-V3 | 2 | 1 | 1/1/1 | 1 | starved, as expected |
| the six non-directional | 0 | 0 | 0/0/0 | 0 | correctly ship nothing |

C-V1/C-V3 show the spread rule working: `not_locatable` has only 23 cores, so it is
taken in full and the shortfall spills evenly to `sparse` (52) and `underpowered`
(51) rather than capping the third at 3 x 23.

### NOT done: the 7 report-level groups

Equal thirds does not hold for them and they need their own decision, because
"insufficient" means something different for a single-report claim:

| group | sup/ref/insuf | problem |
|---|---|---|
| P-R1 | 119/150/0 | no insufficient supply; classes skewed |
| C-R1 | 150/119/0 | same |
| S-R1 | 42/150/0 | same, badly skewed |
| F-R1 / F-R2 | 119/150/0, 112/150/0 | same |
| P-R2 / F-R3 | 59/59/59 | balanced, but the sub-type is `unknown` |

Two open questions, both design calls rather than implementation:

1. **What is `insufficient` for a report-level claim?** The CHOICE variants produce
   some (a `co_exist` pair cannot answer "which came first"), which is why P-R2 and
   F-R3 balance. The BOOL variants map `co_exist` to `refuted` instead, so they
   produce none. Since the seed decision defines co-exist as collapsing true
   simultaneity WITH order-unknown, "A occurred before B" on a co-exist pair is
   arguably `insufficient` rather than `refuted` -- the annotation cannot tell us
   which. That choice is worth making explicitly.
2. **The report-level insufficient sub-type is unlabeled** (`unknown`). It needs its
   own name(s) -- the natural analogues are "order unknown" (events co-exist) and
   "not present" (an event is absent from the report), and they test different
   framework behaviours, exactly as `sparse` and `not_locatable` do at cohort level.

---

## SUPERSEDES 2026-07-28: each decisive core is posed BOTH ways (2026-08-11)

The 2026-07-28 decision said supported and refuted are drawn from *different* event
combinations -- "one claim per case, never the A->B / B->A mirror of a single case".
That is now reversed: **every decisive core contributes both a supported and a
refuted instance**, so supported = refuted = S and the per-group budget is ~3*S
instead of ~1.5*S. Rationale: clinical corpora are scarce, and the corpus caps S at
1,526 with no parameter that lifts it.

| | one claim per core | **both ways** |
|---|--:|--:|
| cohort instances (whole population) | 2,286 | **4,578** |
| released records (x8 register/format) | 18,288 | **36,624** |

Every group has enough insufficient supply to match S, so the third stays exactly
equal (checked per group: smallest headroom is F-M3 at 368 available for 19 needed).

### The cost, and why it is worth paying

The two instances from one core are a **MIRROR PAIR**: identical evidence, identical
computation, opposite labels. They are NOT independent items, so any metric treating
them as such overstates confidence, and a pair split across train/test is direct
leakage.

Accepted because a mirror pair is a **direction-sensitivity probe**, which is the
capability this benchmark exists to measure. A model answering `supported` to both
"A typically precedes B" and "B typically precedes A" is caught immediately, where
two unrelated items would let it hide. This is the contrast-set argument: paired
minimal edits are more informative per item than independent ones.

Two safeguards, both already in place:

1. **Pairs are identifiable.** `instances.core_id` keys off the CORE's canonical
   events, not the realized orientation, so both members share
   `derived_from_core_id`. Any train/test split MUST keep a pair together. Pinned by
   a test.
2. **`mirror_pairs` is reported per group**, so the correlated fraction is explicit
   rather than implicit. Evaluation should report a pair-consistency metric
   alongside accuracy -- of the mirror pairs, how often does the model flip its
   verdict with the claim.

`balance_group(..., per_core=1)` restores the old one-claim-per-core behaviour if
the mirror pairs ever prove undesirable.

### Side effect on negation

Posing every core both ways means exactly one instance of each pair is re-oriented,
so for C-V1/C-V3 the negated share is pinned at **50%** (252 of 504 decisive
instances each) rather than the one-way minimum of 39%. The minimisation rule still
holds within each class; it is the both-ways requirement that forces the rest. This
is arguably the ideal negation probe -- a claim and its negation over identical
evidence -- but it does mean half of those two groups' decisive instances are
negated, which the benchmark documentation must state.

### Measured (pilot enumeration)

Cohort level: **3,246 instances**, 1,082 supported / 1,082 refuted / 1,082
insufficient, 1,082 mirror pairs. Every live group is exactly S/S/S; the six
non-directional groups still ship nothing. Report-level groups are unchanged and
still deferred.

---

## LOCKED: the release ships REPORT IDS, not narratives (2026-08-11)

Answers the cohort-evidence question. The framework reads the corpus itself, so an
instance references its evidence by report id instead of duplicating ~240K tokens of
narrative per cohort-level question.

**Scope of "the model uses MedTempo": the VAERS NARRATIVES, never the annotations.**
The leveled-order timelines are what the gold label is computed FROM, so a framework
given them would just recompute the label. The seed decision ("MedTempo is private
scaffolding; the framework never sees its annotations at inference") is unchanged
and is now the load-bearing boundary for this design.

### New gold-side fields

`generation/evidence.py` recovers, per instance and **in the orientation the
instance asserts**:

| field | meaning |
|---|---|
| `denominator` | reports satisfying the claim's conditioning -- this is `n` |
| `numerator` | the subset supporting the asserted direction -- this is `k` |
| `excluded` | reports where the events are all PRESENT but cannot speak to the claim: a co-exist pair for precedes, a tie for first/last, a non-orderable triple for sequence |

Two-cohort modes return `cohort_1` / `cohort_2` blocks. `excluded` is the new
one and the most diagnostic: it is the report-level witness separating "present but
unusable" from "absent entirely", i.e. the evidence behind `not_locatable`.

Also added so a label can be recomputed from the corpus without re-deriving the
conditioning: `gold_k`, `gold_n2`, `gold_k2`, `family`, `mode`, `min_n_floor`,
`alpha`. Verified self-consistent: `len(denominator) == gold_n` and
`len(numerator) == gold_k`, pinned by tests.

Note `ViableCore.cohort_ids` is misleadingly named -- it holds the WHOLE ~1,000-report
cohort, not the conditioned denominator. The conditioned ids only exist via
`evidence.evidence_ids`.

### The input/gold boundary is now MECHANICAL

The denominator ids are the answer to the localization step -- finding ~19 relevant
reports inside a ~1,000-report cohort, a **55x** search, which is the benchmark's
central difficulty. Shipping them in a record the framework reads would remove it.

So `writers.split_release` emits two files and `instances.INPUT_FIELDS` defines the
boundary:

- `*_questions.jsonl` -- `hypothesis_id, group_id, level, answer_type, register,
  format, text, options, cohort`. Nothing else.
- `*_answers.jsonl` -- everything, keyed by `hypothesis_id`.

The splitter raises if any non-input field reaches the questions file, and a test
asserts the gold fields are absent from `INPUT_FIELDS`. Previously the whole record
was one flat object, so the boundary was a convention.

Measured on the pilot: 16.2 MB questions vs 68.0 MB answers.

### Still open

What the framework is GIVEN to search is now the live question: the full cohort
(faithful but ~240K tokens/question), an exhaustive term-search tool (unbiased, and
matches the "agentic" framing), or the pre-filtered evidence set (cheap, but hands
over localization). Note that semantic top-k retrieval is not a neutral option here:
for a cohort-level claim the evidence is a DISTRIBUTION, not a passage, so
relevance-ranked retrieval biases the proportion rather than merely losing recall.

---

## SUPERSEDES the seed decision: the framework reads ANNOTATIONS, not narratives (2026-08-11)

The seed decision said MedTempo is private scaffolding, "never released as part of
the benchmark; the framework never sees its annotations at inference time", and that
framework input is "narrative + hypothesis only. No relations, no event lists".
**That is reversed: the framework is given the annotated leveled-order sequences and
never sees narrative text.**

### This resolves a contradiction that was already in the docs

`01_overview` / CLAUDE.md position the project as "CRAFT extracts; this framework
**verifies hypotheses against extracted information**". Verifying against extracted
information means the extracted timelines ARE the input. The "narrative only, no
relations" rule said the opposite. The two statements never agreed; this picks the
positioning, which is also the only reading under which the CRAFT -> verification
chain makes sense as two papers.

### Why it is the better design, measured

| | annotations | narratives |
|---|--:|--:|
| whole corpus | **96K tokens** | 727K |
| one cohort | **29-36K** | 213-274K |
| median report | **26 tokens** | 230 |

- **The localization problem dissolves.** A full cohort fits in context at ~30K
  tokens, so there is no need to retrieve, and therefore no retrieval bias. That
  matters because for a cohort-level claim the evidence is a DISTRIBUTION, not a
  passage -- relevance-ranked retrieval would have biased the proportion rather than
  merely losing recall.
- **It is cacheable.** The cohort annotation block is byte-identical across every
  question about that cohort, so it is a fixed prefix. Full-context evaluation costs
  one cached prefix plus a short hypothesis per item, instead of 780M narrative
  tokens per model.
- **It isolates the capability under test** from extraction noise, which is CRAFT's
  problem, not this benchmark's.

### What remains hard -- the benchmark is not trivialised

Gold timelines remove extraction, not reasoning. A framework must still:

1. parse the hypothesis into a formal query (which events, cohort, relation,
   asserted direction);
2. apply the right **conditioning**, which is where the subtlety lives -- precedes
   EXCLUDES co-exist from its denominator while co-occurs treats co-exist as the
   numerator event; sequence requires all three events at DISTINCT levels; first/last
   requires every candidate present and excludes tie reports;
3. aggregate exhaustively rather than sampling;
4. pick the right null -- 0.5 for pairwise/co-occurs, named-vs-runner-up for the
   argmax modes;
5. run it one-sided in the claim's direction and apply the three-decision rule,
   where `refuted` needs the OPPOSITE tail significant;
6. respect the min-n floor (10, sequence 5).

Every one of those is a distinct, diagnosable failure. The `excluded` id set added
earlier measures failure 2 directly: a framework that counts co-exist reports inside
a precedes denominator gets the wrong proportion, and the ids say so.

### Two consequences to accept explicitly

1. **The paper's claim changes.** This is no longer "locate temporal evidence in
   clinical text". It is "translate a natural-language temporal hypothesis into the
   correct statistical procedure over structured timelines, and execute it". Sharper
   and cleanly separable from CRAFT -- but it must be stated that way, and the
   deterministic upper bound becomes a true 100% rather than an estimate.
2. **MedTempo annotations are now effectively part of the release.** That is the one
   thing the seed decision protected. Whether that is acceptable -- licensing, and
   whether CRAFT's annotations are published -- is an OPEN question, not something
   this entry settles. If they cannot be released, the whole design reverts to
   narratives.

### Target framework shape (the intended agentic loop)

hypothesis -> decide which test applies -> query the annotation store for the
conditioned reports -> aggregate -> run the exact test -> three-decision verdict.
Retrieval is a mechanical query over structured data, so the interesting work is
steps 1, 2 and 5.

---

## Part C validation: run, and it found two real bugs (2026-08-11)

Part C existed as a 20-entry hand-check that had never been acted on. Doing it
properly found three defects -- one in the validation artifact itself, two in the
gold-label path.

### 0. The hand-check artifact was misleading

`validation_sample.md` listed "sample reports entering the denominator" by testing
only that both events were PRESENT. For a precedes claim that wrongly included
co-exist pairs -- reports the locked rule EXCLUDES. A human following it would either
reject correct code or validate against the wrong evidence, so the guard could not
do the one job the spec gives it ("guards against ... a wrong co-exist exclusion").

Rewritten to use `evidence.evidence_ids`, and each entry now lists **supports /
against / excluded** with the levels, plus the test, both tails, the min-n floor and
an automatic `counts match` line. The evidence is now self-evidently checkable: for
a precedes claim, supports have A's level < B's, against have it >, and excluded are
exactly the equal-level pairs.

### 1. BUG: the first-mention rule was not implemented in the index

`CorpusIndex.load` assigned `terms[term] = level_index` unconditionally, so when a
term appeared at more than one level the LAST row won -- and the query had no
`ORDER BY`, so **which** row won depended on SQLite's plan. That violated the seed
decision ("when a term appears multiple times, only the first mention is recorded")
and made gold labels non-reproducible across machines.

Found by cross-checking against `core.aggregation`, the DB-backed mirror, which
reads the levels list and is first-mention by construction. It disagreed on 5 of
1,685 instances. Example: report 1709458 has Nausea at levels 1 AND 2 and
Hypoaesthesia at level 1 -- first-mention makes them **co-exist**, the index called it
**after**.

Scope: 7 of 22,674 (report, term) pairs sit at multiple levels, across 6 of 3,166
reports. Small, but it moved labels: **S 1526 -> 1529**.

### 2. BUG: sub-floor cores had no numerator, and named the wrong cell

Insufficient realizations of below-floor cores carried `gold_k = None`, so their
labels were not recomputable, and the first/last branch stored no `extra` -- so the
claim named the alphabetically-first candidate while `k` described the top one. The
two disagreed on 66 instances. Both gate-fail branches now carry `k` and `extra`, and
`_realize_insufficient` treats an empty denominator as `k = 0` rather than unknown.

### 3. Mislabelled tie semantics in the new evidence module

`evidence.py` put first/last tie reports in `excluded`. Locked rule 4 keeps them IN
the denominator (they dilute the proportion) while they support no candidate. Now
reported as a separate `ties` set, with `excluded` reserved for reports the
conditioning removes from the denominator entirely -- which is what happens to a
non-orderable triple in the sequence modes. The two are genuinely different and
conflating them would have misstated n for every first/last group.

### The mechanised guard

`scripts/validate_gold.py` replaces trust-by-sample with **22,242 instances checked,
all passing**, over six invariant families:

| | check |
|---|---|
| A | the denominator/numerator id sets reproduce `n` and `k` |
| B | numerator subset of denominator; denominator and excluded disjoint |
| C | conditioning per locked rule, verified against the leveled orders |
| D | every numerator report actually satisfies the claim as asserted |
| E | `supported` needs p_claim < alpha, `refuted` needs p_opposite < alpha, and the min-n gate agrees with the sub-type |
| F | independent recomputation through the DB-backed `core.aggregation` mirror |

F is the one that earned its keep: two implementations of the same locked rule
disagreeing is exactly the failure a single-path check cannot see. Worth keeping in
CI.

**Part A distributions are now trustworthy** in the sense CLAUDE.md requires. The
human hand-check of `validation_sample.md` remains worth doing on top -- the
mechanised checks verify internal consistency and cross-implementation agreement,
but only a person can confirm the leveled orders match what the narratives say.

---

## SUPERSEDES seed rule 4: first/last ties LEAVE the denominator (2026-08-11)

Seed rule 4 put tie reports in the first/last denominator ("reports containing all
named candidates; tie-reports excluded from per-candidate counts"). **Ties now leave
n**, exactly as a co-exist pair does for precedes and a non-orderable triple does for
sequence. All four families treat an unresolvable report the same way.

### Why the old rule was the odd one out

Precedes drops co-exist because the relation cannot be resolved. Sequence drops
non-orderable triples for the same reason. First/last was the only family that kept
its unresolvable case inside n -- and the tie share is large: **median n was 14 with a
median of 8 ties, ~55% of the denominator**.

A tie contributes to NEITHER cell of the modal-vs-runner-up test, so the gate was
passing on a number more than half composed of reports the test never sees. Example:
n = 47 while the test ran on 9 vs 8 = 17 observations.

This was a loose end created by the same-day test swap: the 2026-08-04 decision chose
to gate on "the CORE's conditioned denominator" and retired a private floor on
(top + runner-up), but that was decided when first/last was tested GOF-vs-uniform.
The test changed to modal-vs-runner-up on 08-11 and the gate rationale was never
revisited.

### The p-values do not move -- only the gate

Verified: every affected core's `p_claim` is byte-identical before and after, because
ties were never in the 2-cell table. S falls purely because cores that cleared the
floor on a tie-inflated n no longer clear it, so they are gated to
`insufficient / sparse` BEFORE the test is consulted.

Worked case (F-V1, Arthralgia/Fatigue/Pain in extremity, Pfizer): counts are Pain in
extremity 5, Arthralgia 0, Fatigue 0, with n = 11 and 6 ties. Top-vs-runner is 5 vs 0,
p = 0.0312, unchanged. But n - ties = 5, below the floor of 10, so the core is gated
out. Asking "is Pain in extremity most commonly first?" on 5 resolving reports out of
11 -- with no unique first event in 6 of them -- is exactly the thinness the floor
exists to refuse.

### Cost

| | before | after |
|---|--:|--:|
| F-V1 / F-V3 | 74 each | **36 each** |
| F-V2 | 86 | **59** |
| F-M3 | 19 | **8** |
| **total S** | 1529 | **1415** |

Accepted: uniform treatment of unresolvable evidence is one sentence to defend,
where the old position needed a special case for one family. `tie_rate` is still
reported and is now computed over reports where all candidates were PRESENT
(`n_present`), so it cannot exceed 1 now that ties are outside n.

### Rejected alternative: credit every tied candidate

Considered giving each tied candidate a count. Integer shared credit makes counts sum
to more than n and lets "A is most commonly first" be satisfied by reports where A
merely tied -- in the worked case it would push Pain in extremity from 5 toward 11 on
the strength of non-wins. Fractional credit (0.5 each) breaks the exact binomial,
which requires integer counts, and every test in the project is exact on integers.

Note this is separate from the still-open REPORT-level tie question (F-R1/F-R2: one
report where two events tie for first, set-valued gold vs `insufficient`). Shared
credit is defensible there, because there is no aggregation to distort.

---

## Multi-tier screen re-run; F-M3 FAILS; lever 2 retired (2026-08-11)

Refresh pass over the permutation screen, on the corrected corpus (post first-mention
and tie fixes) at the new defaults (floor 10, 2000 rounds). Every previously recorded
`p_perm` predated those fixes, so all figures below supersede the earlier ones.

| candidate | shape | decisive/cores | null mean | null p95 | p_perm | |
|---|---|--:|--:|--:|--:|---|
| P-M2 precedes-strict | pair | 30/322 | 18.3 | 27 | **0.023** | clears |
| M-F precedes-wide | pair | 46/572 | 32.2 | 44 | **0.034** | clears |
| M-C last-overall | single | 18/193 | 11.6 | 18 | 0.073 | fails |
| M-H early-half | single | 18/193 | 12.5 | 20 | 0.109 | fails |
| **F-M3 first-of-triple** | **triple** | **8/75** | **5.2** | **10** | **0.188** | **FAILS** |
| C-M2 co-occurs | pair | 41/572 | 34.6 | 47 | **0.202** | fails |
| M-B first-overall | single | 13/193 | 12.3 | 19 | 0.462 | noise |

### F-M3 was in the shipping roster and had never been screened. It fails.

8 decisive cores against a noise mean of 5.2 and a noise p95 of 10. Shuffled labels
reach 8-or-more in **19%** of rounds, so its supported/refuted labels cannot be
distinguished from randomising which vaccine each patient received.

Implemented as a new `triple` shape in `run_multi_inventory.py`: reports containing
all three candidates, ties excluded from the denominator per the 08-11 tie decision,
and the focal event fixed from the real data so real and null count identical cores.
Triples are counted per report (~35 increments each) rather than over all C(65,3)
combinations. The real count of 8 matches F-M3's actual S, confirming the shape.

Note M-B and F-M3 are NOT the same claim and the script treats them differently on
purpose: M-B asks "is A AT level 0" (ties count), F-M3 asks "is A UNIQUELY first
among A, B, C" (ties excluded). F-M3 is the better-posed claim and still fails.

### Consequence: the validated multi tier is ONE group

Only P-M2 and M-F clear, and they are the same claim family, so at most one ships.
C-M2 and F-M3 both fail. No single-event candidate clears. The choice is now: ship
P-M2 (or M-F) alone as the multi tier, retire the two-cohort tier for v1, or ship the
failing groups as documented negatives. See `open_questions.md`.

### Round count: settled empirically

Verdicts are identical at 1000, 2000 and 3000 rounds; only precision changes
(SE ≈ √(p(1−p)/R), so ±0.011 / ±0.008 / ±0.006). 1000 rounds takes ~157 s, so there
is no cost argument for less. **200 rounds is triage only and must never decide**: it
read M-C as 0.035 — a passing value — where 1000+ gives ~0.076. Defaults are now
floor 10 / 1000 rounds, and `--floor` had been left at the retired 20.

### §6 lever 2: RETIRED

Agreed and recorded. The Mann-Whitney normal approximation is anti-conservative on
tie-heavy ordinal data (~11% decisive under shuffled labels vs a nominal 5%), so the
lever manufactured false positives rather than recovering signal. Retiring cost
nothing: `core/positions.py` is imported only by `make_examples.py` and
`replacement_inventory.py`, never by `core/answers.py`. The module now carries a
header stating it is descriptive-only and must not produce labels.

---

## LOCKED + implemented: F-M3 retired, no substitute exists (2026-08-11)

**F-M3 (`multi_dir_first`) is removed.** It failed its permutation null on first
measurement -- 8 decisive cores against a noise mean of 5.2, p_perm 0.183-0.188, so
shuffled labels reach 8-or-more in ~19% of rounds. Its supported/refuted labels were
not distinguishable from randomising which vaccine each patient received.

Roster: 25 -> **24** as coded. S: 1415 -> **1407**.

### Substitutes were screened. There are none.

Three untested first/last two-cohort shapes, floor 10, 1000 rounds:

| candidate | decisive/cores | null mean | p_perm |
|---|--:|--:|--:|
| M-J last-of-triple, ties count as not-last | 30/387 | 21.2 | 0.096 |
| M-G first-of-triple, ties count as not-first | 20/387 | **20.0** | 0.509 |
| M-I last-of-triple, ties excluded | 5/105 | 6.6 | 0.698 |

### Why this family cannot have a two-cohort group -- structural, not wording

1. **With TWO events, "first" IS "precedes."** "A is first between A and B" is
   literally P-M2, so a distinct first/last multi group REQUIRES three events.
2. **Three-event co-presence in BOTH cohorts leaves 75 cores** (ties excluded) or 387
   (ties kept). Either way it is the thinnest conditioning in the benchmark.
3. **The widening trick that rescued precedes does not transfer.** M-F beat P-M2 on
   supply by counting co-exist as "does not precede"; the same move here gives M-G at
   real 20 vs null mean **20.0** -- indistinguishable from noise. Cause: the
   first/last tie rate is ~55%, so a widened denominator is majority ties, which
   dilute the numerator equally in both cohorts and add variance without signal.
4. **M-I comes in BELOW chance** (5 vs 6.6 expected), the conservative-Fisher
   signature that retired M-D: a rare numerator on a small table makes the exact test
   heavily conservative.

M-J at 0.096 is the least-bad and still ~2x alpha. More rounds cannot help -- p_perm
is a ratio, not a precision artefact -- and narrow/wide denominators in both
directions exhaust the design space.

### Consequence for the multi tier

With F-M3 gone and C-M2 failing (0.195-0.202, four independent measurements), the only
two-cohort candidates that clear their null are **P-M2 (0.023) and M-F (0.034), which
are the same claim family**. So the validated multi tier is at most ONE group. Whether
to ship it alone or retire the two-cohort tier for v1 is the remaining open question.

Removed from `data/templates/first_last.yaml`, `MODE_BY_GROUP`,
`_MULTI_TRIPLE_MODES`, `_SLOT_ORIENTABLE`, the `_build_multi_core` /
`_realize_multi_dir` focal branches, `_FISHER`, `evidence.evidence_ids`, the pilot
mode blurbs and validation list, `final_templates` ROSTER, and `make_examples`. The
`multi_dir_first` mode no longer exists. Validation re-run: 21,310 instances, all six
checks passing.

---

## LOCKED + implemented: C-M2 dropped (2026-08-11)

**C-M2 (`multi_dir_cooccurs`) is removed.** It failed its permutation null on four
independent measurements and got worse as the corpus got cleaner:

| measurement | real decisive | null mean | p_perm |
|---|--:|--:|--:|
| floor 20, 200 rounds | 23 | 16.7 | 0.129 |
| floor 10, 2000 rounds (pre-fix) | 42 | 34.3 | 0.151 |
| floor 10, 1000 rounds (corrected) | 41 | 34.5 | 0.195 |
| floor 10, 2000 rounds (corrected) | 41 | 34.6 | **0.202** |

Roster: 24 -> **23** as coded. S: 1407 -> **1365**.

It also responded to the floor change the wrong way round: halving the floor nearly
doubled its decisive count (23 -> 42) and pushed it FURTHER into the null. More data
making a group worse is the signature of no signal.

### Why the labels were individually valid and collectively meaningless

Every one of its 42 decisive cores had a correct exact p-value. Examples that would
have shipped:

| claim | higher cohort | lower cohort | p |
|---|---|---|--:|
| Fatigue & Injection site pain, Moderna > Pfizer | 19/34 = 0.559 | 5/24 = 0.208 | 0.008 |
| Arthralgia & Nausea, Moderna > Pfizer | 13/22 = 0.591 | 4/17 = 0.235 | 0.028 |
| Asthenia & Cough, Pfizer > Moderna | 10/12 = 0.833 | 6/15 = 0.400 | 0.028 |

Defensible in isolation. But scrambling the vaccine labels produces ~35 such findings
on average and reaches 41+ about one round in five, so there is no way to tell which
of the 42 are real.

### The likely cause, which is worth reporting

Whether two symptoms land at the SAME timeline level is largely a property of how the
report was written and annotated, not of the vaccine. "Patient experienced fatigue and
injection site pain" in one clause co-occurs; split across two sentences it is
ordered. That is narrative style, and style does not vary by vaccine.

Contrast **P-M2** (precedes), which PASSES at 0.023 on the same corpus with the same
test. Order is a clinical fact about onset; simultaneity in the annotation is partly a
transcription artefact. That is a substantive finding about what MedTempo-style
leveled orders can support, and it belongs in the paper.

### Consequence: the multi tier is P-M2 alone

Remaining multi groups: P-M2 (S = 30, p_perm 0.023) plus the six non-directional ones
already slated for removal (all S = 0). Whether a one-group two-cohort tier is worth
the shape for v1 is the open question in `open_questions.md`.

Removed from `data/templates/pairwise.yaml`, `MODE_BY_GROUP`, `_SLOT_ORIENTABLE`,
`_FISHER`, the `_build_multi_core` mode tuple, `evidence.evidence_ids`, the pilot mode
blurbs and validation list, `final_templates` ROSTER, `make_examples`, and the
`aggregation.direction_verdict` docstring. The `multi_dir_cooccurs` mode no longer
exists. Validation re-run: 20,749 instances, all six checks passing.

---

## FIXED while building the sample instances: two claim/label mismatches (2026-08-11)

Building three fully-annotated sample instances (a one-off script, since removed
along with its output) surfaced two defects that the existing checks did not cover. Both are the same shape
of error: a field describing something other than what the instance asserts.

### 1. F-V2 and F-R2 named the WRONG EVENT in every instance

The argmax realizers (`_realize_extreme_choice`, `_realize_modal_choice`) put the
NAMED event in slot **{A}**. F-V1, F-V3, F-R1 and F-R3 assert `{A}` and were correct.
**F-V2 and F-R2 asserted `{C}`** -- an arbitrary non-winner. Measured: **59 of 59**
F-V2 decisive instances named an event other than their own `gold_answer`:

> "After Pfizer, **Headache** is most commonly the last event among Nausea, Chills,
> Headache." -- with `gold_answer` = **Nausea**, which had 17/25 against Headache's 3.

Fixed by rewording F-V2 and F-R2 to assert `{A}` across all four registers, matching
their siblings and the realize path. A test now asserts that every argmax template's
first event placeholder is `{A}`.

Note the earlier oriented-statistics fix could not catch this: the *statistics* were
right, and the *answer key* was right. Only the rendered TEXT was wrong, and nothing
compared the text against the answer key.

### 2. Two-cohort `gold_n2` / `gold_k2` described the wrong cohort

Added during the evidence-ids work and taken from the CORE rather than the realized
instance, so whenever a `multi_dir_*` realization swapped cohorts they reported the
first cohort's numbers under the second cohort's name. The sample made it obvious:
`gold_n2` read 46 while cohort_2's denominator held 24 reports. `gold_k` was also
absent for every multi instance, because `_realize_multi_dir` never passed `k`.

`InstanceFacts` now carries oriented `gold_n2` / `gold_k2`, `_realize_multi_dir`
passes the higher/lower counts it already computed, and the insufficient path passes
the second cohort through (no re-orientation happens there). The multi gate-fail
branch now also carries `k`/`k2`, which it never did.

`validate_gold.py` gained the matching invariant: for two-cohort instances,
`len(cohort_1.denominator) == gold_n`, `len(cohort_1.numerator) == gold_k`, and the
same for cohort_2 against `gold_n2` / `gold_k2`. 20,749 instances, all passing.

### The lesson worth keeping

This is the third time today a field has described a different claim than the one in
the record: the p-value tails, `_realize_insufficient`'s named cell, and now the
template slot plus the second cohort. **Any per-instance field must be derived from
the realized instance, never from the core** -- and the check that catches it has to
compare the rendered TEXT against the gold, not just the numbers against each other.

---

## Reasoning preserved from retired open questions (2026-08-12)

Bookkeeping entry. `open_questions.md` had accumulated 11 items already marked
RESOLVED, which made the "open" list unreadable — you could not tell what was
live without reading every entry. They are removed from that file per the stated
convention. Two pieces of reasoning existed ONLY there and are recorded here so
the deletion loses nothing.

### Why the first/last family structurally cannot have a two-cohort group
Behind the F-M3 retirement, and it generalises beyond that one group. With TWO
events, "which is first" IS "which precedes" — a first/last multi group is only
distinct from the precedes tier once it uses THREE events. But three-event
co-presence in both cohorts leaves 75-387 cores carrying a ~55% tie rate, and the
tie is the trap: excluding tied reports starves n, while including them dilutes
the numerator EQUALLY in both cohorts. That symmetry is why the widening trick
that rescued precedes (M-F, `p_perm` 0.033) produces pure noise here — M-G scored
20 decisive against a null mean of 20.0. The family has no two-cohort form that
is both distinct from precedes and adequately powered.

### Why C-M2 failed its null where P-M2 passed, on the same corpus
Same-level co-occurrence appears to reflect **narrative and annotation style**
rather than the vaccine: whether two events land at the same level depends on how
a reporter wrote the sequence and how the annotator resolved simultaneity. That
varies by report, not by cohort, so shuffling the vaccine labels barely changes
the statistic. Order (P-M2) survives the same shuffle because it encodes
something about the events themselves. Worth remembering before proposing any
future group built on simultaneity.

### Method note, promoted to CLAUDE.md
A permutation gate needs **>= 2000 rounds** for a ship/no-ship call. At p ~ 0.04
the 200-round SE is ~0.014, and M-C actually crossed the alpha line between run
sizes (0.035 at 200 rounds -> 0.073 at 2000). 200 rounds is triage only.

---

## MedTempo is the gold-label dataset, taken as given (2026-08-12)

**Decision: treat MedTempo as the gold-label corpus. Not a project risk, not a
blocker, and no further action.** Raised on 08-12 that the shipped annotations
are 89.5% raw o4-mini output accepted by a human reviewer, 10.5% human-corrected,
with inter-annotator agreement measured on 27 of 3,166 reports (0.852).
User decision: "expert annotation" is an exaggerated way of putting it, but it is
not wrong -- the human verification pass is real -- and it does not affect
anything badly. The corpus is external, published with its own paper, and this
project consumes it rather than producing it.

Consequences for how we write and work:
- Keep the numbers above on record so nobody re-derives them as a surprise.
- Prefer "expert-verified" over "expert-annotated" where it costs nothing, and
  cite the MedTempo paper for methodology rather than restating it here.
- Corpus quality is OUT of scope. Do not open further work on annotation
  provenance, agreement sampling, or annotation-noise estimation.
- The one substantive read-through stands and is already recorded: C-M2 failed
  its permutation null on same-level co-occurrence, which plausibly tracks
  annotation style. That is a reason to be wary of groups built on simultaneity --
  a design note, not a corpus problem.

Issue 15 is closed. Supersedes the open question "The corpus is LLM-drafted and
expert-VERIFIED" in `open_questions.md`, which is deleted.

---

## Dataset-creation decision batch (2026-08-14)

User decisions unblocking the v1 dataset build:

1. **Issue 13 — C-V3 becomes modal-vs-runner-up.** The statistic moves from
   "co-occurrence rate > 0.5" to the argmax its text already asks: the modal cell
   vs the runner-up over the 3-cell relation distribution {before, after,
   co_occur}. NOT shipped until it clears a >=2000-round label-permutation screen
   (the standing rule for any changed statistic); if the screen fails, C-V3 is
   DROPPED instead. Side effect either way: C-V1 and C-V3 stop being statistical
   twins, so issue 14's twin count falls from four pairs to three.
2. **Issue 1 — the multi tier ships P-M2 ALONE.** The M-F swap, retiring the
   tier, and the comparative-family substitution are all declined for v1. The
   screening story (seven two-cohort shapes tested, one survivor) is a methods
   strength for the paper.
3. **Issue 2 — the removal half is CONFIRMED.** P-M1, C-M1, S-M1, S-M3, F-M1,
   F-M2 (all S = 0) leave the roster. The three additions (R1/R3/R5 =
   P-V4/P-V2/C-V2) are pending the user's confirmation of the listed template
   wording; each must clear its own >=2000-round permutation screen at full
   enumeration before shipping.
4. **Issue 8 — v1 ships WITHOUT the synonym table.** `synonym_used` keeps
   echoing the raw MedDRA term. Documented limitation, not a blocking gap.
5. **Positional statistics ship as DESCRIPTIVE gold-side attributes** wherever
   computable (signed-rank on level gaps for pair modes, Mann-Whitney for the
   two-cohort group, Friedman/Kendall for triples), each marked
   descriptive-only. They never drive a verdict -- §6 lever 2 stays retired, and
   the issue-16 verdict-driver question stays open without blocking the dataset.
6. **Issue 17 — the train/dev/test split is DEFERRED until after dataset
   creation.** Issue 14 (fact_id) remains open as a field-design question.

### Issue 11 CLOSED by inspection (same date)

"Disconnected components in MedTempo" is moot at this layer: the released
leveled-order format is a single totally-ordered chain of stages by construction
(`db/build.py::_parse_levels` parses a JSON list of stages; `num_groups` in both
the DB and the source CSV is just the STAGE COUNT, mislabeled -- its distribution
exactly matches levels-per-report). Any independence between event chains inside
one narrative was resolved at ANNOTATION time, upstream of this benchmark, and
upstream corpus quality is out of scope by the issue-15 decision (2026-08-12).
No representation change and no insufficient-marking mechanism is needed.

---

## Dataset-creation decision batch 2 (2026-08-14)

The remaining calls, all made by the user; nothing blocks the v1 build now.

1. **Issue 9 — (b): S-V1 and S-V3 ship IN FULL, flagged.** S = 4 each (largely
   the same four triples posed as BOOL vs CHOICE), 12 items per group at equal
   thirds. Levers 4 (vaccine-agnostic pooling) and 5 (MedDRA coarsening) are
   recorded as post-v1 options, not v1 work.
2. **Issue 2 — all three additions CONFIRMED**: P-V2 (R3 conditional
   antecedent), P-V4 (R1 pair-vs-pair, four events accepted), C-V2 (R5
   association vs independence). Four-register + negated wording authored at
   implementation; C-V2 requires negation (symmetric claim); each addition must
   clear its own >=2000-round permutation screen at full enumeration before it
   ships.
3. **Issue 14 — fact_id ships as a FIELD now, the split stays deferred.**
   fact_id = "{statistic}|{vaccines}|{events}" (no group id) is emitted on
   every record at creation, so twins share it; the later train/dev/test split
   keys on it. S-style counts quoted for power/coverage must use DISTINCT
   fact_ids (727 today), not instance counts.
4. **Issue 5 — not_locatable comes from deliberately FALSE combinations.**
   User: "It should never be generated from core because core is for successful
   pairs. I need the combination to be false and it could be randomly combined
   as long as there is no actual reports as so." Implementation: a seeded
   generator samples pairs/triples of REAL cohort terms whose joint report count
   in that cohort is ZERO; those become insufficient/not_locatable instances.
   Enumerated cores are never a source. (The sequence family's 118 natural
   zero-orderable triples remain valid not_locatable supply.)
5. **Issues 6+7 — (iii): order-asking report-level questions are NOT POSED on
   tied reports.** Enumeration picks the earliest fully-ordered pair/triple in
   the report instead (every report has >= 2 stages, so one exists). Report
   level therefore becomes strictly TWO-CLASS deterministic -- supported/refuted,
   balanced 50/50 -- and insufficient does not exist at report level, matching
   the user's framing. C-R1 keeps using co-exist pairs (they are its supported
   case). Context: the earliest two events are tied in 62% of reports, so this
   also removes a large degenerate-question pool.
6. **Issue 4 — CLOSED by REMOVAL.** confidence_tag (never-calibrated 0.15/0.30
   cutoffs) and ci_width leave the released records. The Wilson CI itself
   STAYS: it is the locked 07-13 reported statistic and nothing about it was in
   question. Grep-verified that nothing downstream consumed tag or width (only
   the emitting pipeline and their own tests), so removal is free and A4's
   calibration job disappears.
7. **Issue 18 — deferred until after dataset creation**, per user. It is pure
   read-only arithmetic over the finished records (sum of exact per-core test
   sizes at each n) and lands in the statistics report + limitations.

### C-V3 register audit (same date, while implementing issue 13)

Only the ORIGINAL register actually asked the argmax ("is co-occurrence the
dominant relation"); research/media/clinical asked the MAJORITY question
("concurrent more common than ordered" = rate > 0.5, i.e. the very statistic
being retired). With the statistic moving to modal-vs-runner-up, all four
registers are reworded to argmax phrasing so the four paraphrases finally ask
the same question.

---

## v1 DATASET GENERATED; all three additions CLEAR their screens (2026-08-14)

The 2000-round full-enumeration screens (`scripts/screen_new_groups.py`,
`data/pilot/new_groups_screen.json`) all come back at the 0.0005 floor -- no
shuffled round approached any real count:

| group | decisive/cores | null mean | null p95 | p_perm | null model |
|---|--:|--:|--:|--:|---|
| P-V2 | 2,302 / 10,060 | 341.3 | 452 | **0.0005** | level shuffle |
| P-V4 | 16,884 / 49,862 | 1,848.9 | 2,435 | **0.0005** | level shuffle |
| C-V2 | 2,098 / 26,764 | 924.4 | 976 | **0.0005** | edge swap |

So the 20-group roster is FINAL and the generated artifact ships unchanged:
`data/release/v1` -- 147,936 records / 18,492 instances, verdicts
6,845/6,783/4,864, 8,964 distinct facts, 6,664 mirror pairs, positional
coverage 65.7%, committed gzipped with sha256 provenance (f0ea221).

Release-format refinement, same date: answers are ONE ROW PER INSTANCE
(instance_id + hypothesis_ids), because per-record answers duplicated the
evidence-id lists eightfold (389 MB measured -> 52 MB). The input/gold
boundary and the questions file are unchanged.

Presentation caveats recorded with the artifact, decisions pending user
review: P-V4 supplies 46% of all instances (cap or keep); C-R1 ships
181/119 (class fixed by data; balancing would need authored negation);
S-V1/S-V3 ship at S = 2 per the issue-9 (b) decision.

The Overleaf dataset-construction section is drafted
(`docs/draft/dataset_construction.md`) and PRESENTED; Overleaf is untouched
pending the user's approval, per their instruction.

---

## LOCKED: model pipeline / eval-harness architecture (2026-09-01)

Branch `model-pipeline-design`. The design is `11_model_pipeline.md`; this entry
records what is locked, the doc carries the reasoning and the measured numbers.
Issue 3 moves from "not started" to "designed; M1 (deterministic chain) + M2
(local-LLM extraction + local-LLM text-to-SQL) being built this session". Three
new issues are filed in `09_next_steps.md`: 24 (P-V2/P-V4 count-vs-rate wording,
decision), 25 (`test_verdict` provenance defect on 1,800 rows, defect), 26 (P3
paraphrase authorship, decision). Scope was set by the user at plan review:
"implement for local only; stop at text-to-SQL; do eval on the local setup" —
M3–M5 (fine-tuned extractor + split, in-context and agent baselines, write-up
hooks) are designed, not built.

> **Cross-reference for top-down readers:** the entry at `decisions.md:1514-1518`
> ("the VAERS NARRATIVES, never the annotations", 2026-08-11) is SUPERSEDED by the
> entry at `:1574` of the SAME date ("the framework reads ANNOTATIONS, not
> narratives"). Anyone reading this file forwards meets the reversed statement
> first. The narrative-free eval DB below is the mechanical form of the later
> decision.

### Decision: a three-stage contract with `StructuredClaim` as the S1 output

`question row (INPUT_FIELDS only) -S1-> StructuredClaim -S2-> per-arm ArmRows -S3->
Prediction -S4-> metrics`. Every extractor (rules, prompted LLM, fine-tuned) emits
the same `StructuredClaim` (`framework/claim_schema.py`): a WHAT layer (tier,
family, primitive, mode — the 20 `cores.MODE_BY_GROUP` strings — events in the
asserted order, cohorts, negated, answer_type, options, asserted_option) and a
HOW layer (`Procedure`: test, null, claim_tail, alpha, min_n_floor, arms,
conditioning). The HOW layer is a pure function of `(mode, negated)`
(`derive_procedure`), asserted by test against `answers._BINOM_NULL /
_MODAL_RUNNER / _FISHER` plus the `cooc_modal_bool` special case; extractors may
fill it so that null-choice and test/tail errors are measurable rather than
derived away. `from_gold(answer_row)` is the reference claim and the free training
label. Every retrieval method returns, per arm, rows `(vaers_id, in_denominator,
in_numerator, excluded, cell)` (`framework/sql/aggregate.py::ARM_COLUMNS`); `cell`
is NULL for excluded rows and `counts` is built from denominator rows only,
because `answers._named_counts` takes `max` over every non-named key and a tie
bucket leaking in as a cell would corrupt every argmax p-value.

### Decision: the eval DB is narrative-free and keyed on `vaers_id`

The harness reads `data/medtempo_eval.db` (built by `scripts/build_eval_db.py` from
`medtempo.db`), never the raw DB. Schema: `reports(vaers_id PK, vaccine,
num_stages)`, `level_terms(vaers_id, level_index, term)`, views `first_mention`
(`MIN(level_index)` per report and term — the first-mention rule as a view; 7
(report, term) pairs sit at two levels in the real DB) and `report_terms`. No
`narrative` column, no surrogate `report_id`. This is the mechanical guard behind
"the framework never sees narrative text", and it makes every id in the harness
the release's `vaers_id`. The executor opens it `mode=ro`, allows only
SELECT/READ on the four relations (+ FUNCTION) through `set_authorizer`, one
statement starting SELECT/WITH, 5 s progress-handler timeout, 10,000-row cap,
and logs every call to `sql_log.jsonl`.

### Decision: the min-n floors and alpha are GIVEN to the model in both modes

Floors (10; sequence 5) and alpha (0.05 per side) go in every prompt,
`procedure-blind` and `procedure-given` alike. `05_significance_tests.md`
designed the gate to be shared by both sides; withholding it would make the 3,234
`sparse` + `underpowered` instances (17.5%) unwinnable for a reason unrelated to
the capability. What the model must supply is the test, the null, the tail, the
arms and the conditioning — not the constants.

### Decision: S3 is `core_significance(core, named=claim.named_cell())`, never `compute_answer`

`compute_answer` reports the WINNER's tail (verified on F-V1: it would call an
asserted runner-up "supported"). The harness builds a `ViableCore` from the claim
and the retrieved counts (`run_test.to_viable_core`, with `extra` complete for all
20 modes so `answer_key` never returns None on the 1,200 report-tier first/last
CHOICE instances; `computable = min_n_gate(n, family, n2=n2).testable`; no rows
=> `n=0` => `not_locatable`, never `n=None`), calls `core_significance(named=)`,
and applies the negation tail swap exactly as `oriented_significance` does.
Report tier: `report_rule` on the ORIENTED events + `verdict.deterministic`,
tested against all 3,900 gold rows. An unknown family from a model is recorded as
a procedure error and the gold family is used for the gate (`family_floor` must
not raise inside the harness).

### Decision: `procedure-honouring` is the default S3 variant

The harness runs the model's STATED test / null / tail on the model's counts
(`binom_exact_p`, `fisher_exact_2x2`, `three_decision`), so a wrong procedure
yields a wrong verdict and the null-choice and test/tail failure modes are causal,
not cosmetic. `gold-procedure` (override HOW; isolates WHAT + retrieval),
`model-computed` (model returns p's and verdict) and `agent` (tools `run_sql`,
`exact_test`, `min_n_gate`, `submit_evidence(arm, ids)` required before `submit`)
are the other variants; only the first two are built in M1/M2. Alternative-test
adjudication: verdict scored as-is; the named test is bucketed `gold | synonym
(binomial/sign -> binom_exact; fisher/hypergeometric -> fisher_exact) |
other-exact | approximate`; `approximate` is never "valid" (exact tests only).

### Decision: retrieval is scored on `evidence_ids` sets with the 0/0 convention

Per arm: set precision / recall / F1 / exact match of the predicted denominator
(and numerator) ids against the gold `evidence_ids`; P = R = F1 = 1.0 iff both
sets are empty, 0.0 if gold is empty and the prediction is not — that row is the
`not_locatable` fabrication probe, also reported as a false-positive-rate column.
`coexist_leak` = |pred_den ∩ gold.excluded| / |gold.excluded|; `cohort_leak`
likewise for out-of-cohort ids. The report tier is scored as `report_hit` and
kept OUT of the retrieval macro (its 3,900 instances have no denominator).

### Decision: the headline is group-macro of class-macro-F1 with a bootstrap CI, fact-weighted companion

Class-macro-F1 over {supported, refuted, insufficient} per group (the `### Metrics`
decision at `decisions.md:656-659`), averaged over groups with at least a stated
minimum number of instances (S-V1 / S-V3 have 6 each and are excluded and LISTED),
bootstrap CI over instances; a fact-weighted number (each `fact_id` weight 1)
alongside; micro accuracy, per-tier / family / register / format / negated /
sub-type breakdowns; the report tier's macro is over {supported, refuted} only.
The unit is the instance (8 texts aggregated); distinct `fact_id` is quoted in
every headline count. Default eval set = `original` register x both formats on
`eval-core` (per-group cap 90 at 30/30/30, mirror pairs and twins kept together);
all 8 texts only on a seeded 200-instance invariance subset.

### Decision: a fourth response token, `underdetermined`

2,292 records (C-V3 research + clinical 2,088; F-V3 research 204) never name the
events, so no reading of the input determines the claim. The harness answers
`underdetermined` for them, scores that token separately, and excludes those rows
from every other metric by default. It is distinct from `insufficient`, which is a
property of the DATA (`CLAUDE.md`), and it is the reason B0 is 100% on 145,644
records rather than on 147,936.

### Decision: CHOICE options are shuffled with a seeded permutation before any parser reads the row

The release lists the asserted option first on F-R1 / P-R2 and last on F-R2, so
`options[0]` and `options[2]` are perfect baselines there. The harness applies a
seeded shuffle (seed recorded in `config.json`) before S1 sees the row, reports the
`options[i]` baselines, requires parses to be invariant to option permutation, and
treats `None` (80 tie instances) as a valid answer class.

### Decision: leakage protocols P1 / P2 hold out fact AND X, never X alone

Every instance's 8 texts share one gold row, so a register holdout that keeps the
fact on the train side measures nothing. P0 `fact_split` (sanity floor), P1
`fact ∧ register` (the reported generalization number, 4 folds), P2 `fact ∧ group`
(procedure inference for a novel shape; 964 facts span two groups via twins, so
the held-out group's facts leave the train side too), P3 `novel_paraphrase`
(authorship = issue 26). Table in `11_model_pipeline.md` §4.

### Decision: the provisional split lives at `data/splits/fact_split_v1.json`, keyed on `fact_id`

Pipeline-internal, not part of the release; stratified by group of first
appearance, 70/10/20, groups with fewer than 10 facts entirely to test, no
`fact_id` / `derived_from_core_id` / `instance_id` straddles; the release sha256s
recorded inside. Placed OUTSIDE `data/release/v1/` so the published artifact
directory stays immutable (a small deviation from the option wording "under
data/release/v1/splits/"; the intent — provisional, internal, not release — is
unchanged). Issue 17 stays open as the RELEASE question; regeneration for issues
22/23 changes instance ids but `fact_id` survives it. Not built this session (only
the fine-tune stage needs it).

### Decision: local GPU first, API adapters behind the same interface

No API keys; RTX 5060 Ti 16 GB (Blackwell, sm_120 — torch >= 2.7 / CUDA 12.8
wheels when fine-tuning arrives; no bitsandbytes on Windows). Runtime: Ollama
(`/api/chat` with JSON-schema `format`, temperature 0), model
`qwen2.5:7b-instruct` (Q4_K_M, ~4.7 GB) for both extraction and SQL,
`qwen2.5-coder:7b` optional second SQL model. The client is stdlib `urllib` —
zero new required dependencies; `anthropic` / `openai` adapters later behind
`llm_client.Provider.complete(messages, schema, model)`. Responses cached on disk
under `results/cache/` keyed sha256(model + messages + schema), so re-runs are
free and deterministic.

### Decision: the harness never reads `test_verdict` (issue 25)

`test_verdict` equals the CANONICAL verdict at report tier
(`oriented_significance` returns `core_significance` there), so it disagrees with
`gold_verdict` on exactly 1,800 refuted report-level rows (300 each in P-R1,
P-R2, S-R1, F-R1, F-R2, F-R3). No gold label is wrong; the provenance field is.
`gold_verdict` is the label everywhere in the harness (`io.load_release` asserts
`gold_verdict == test_verdict` only where `report_id is None`); the fix — the
report branch of `oriented_significance` plus the `instances.py` comment — needs
regeneration or a field patch and is filed as issue 25.

---

## Scorer definitions fixed on the B0 run; `underdetermined` policy (2026-09-01)

Found while running the deterministic B0 baseline (`results/oracle_v1`, all
147,936 records) and the first local-LLM smoke run; all three are scorer
definitions in `framework/evaluate.py`, none changes a gold label.

### Decision: twin consistency keys on the ASSERTED claim
Twins are instances sharing `fact_id` AND the same asserted claim -- identical
oriented events, the same `negated` flag and the same cohort order. A key on
`(fact_id, events)` alone paired every negation-oriented mirror (C-V1 252,
C-V2 349, C-V3 174 pairs) and every P-M2 vaccine-swap mirror (29) with its own
opposite and reported the GOLD as 29% inconsistent (804 of 2,571 groups). With
the corrected key B0 reads 1.000 over 1,767 twin groups.

### Decision: the not_locatable false-positive rate is PER ARM
A `not_locatable` instance has an EMPTY gold denominator in at least one arm; the
fabrication false positive is a non-empty predicted denominator for such an arm.
The first definition ("any predicted arm non-empty") charged the legitimately
non-empty other arm of P-V2/P-V4/P-M2 one-arm-empty instances and read 0.208 on
B0 (12,784 records); the per-arm definition reads 0.000, as an exact retriever
must.

### Decision: only TEMPLATE-underdetermined rows are set aside from scoring
The 2,292 rows whose templates never name the events (C-V3 research/clinical,
F-V3 research) are the only rows excluded from the verdict metrics; they are
scored on the `underdetermined` token alone. A model that answers
`underdetermined` -- or emits a claim with missing events -- on any OTHER row is
scored as a wrong verdict and counted under `underdetermined.unexpected`, so the
token cannot be used to opt out of hard items. (The first local 7B run produced
16 such rows; excluding them would have lifted its accuracy from 0.740 to 0.771.)

### Definition: first/last modes compare roles B.. as an unordered candidate set
"Which of A, B, C is first" is the same claim under any order of B and C. The
release lists B/C in options order and the harness shuffles options before any
parser reads the row, so extraction metrics (`events_ordered_em`, `claim_em`,
per-role accuracy) compare the candidates as a set for `first_choice`,
`first_bool`, `last_choice`, `rep_first_choice`, `rep_last_choice`,
`rep_first_bool` (`evaluate.canonical_terms`). Role A and every other mode keep
strict order -- there the order IS the claim.

Regression tests: `tests/framework/test_pipeline.py` (B0 slice: twins 1.0, FPR
0.0, claim_em 1.0 under shuffled options) and `tests/framework/test_evaluate.py`.

## DECIDED: the text-to-SQL stage will use API models (2026-09-02)

The S2 text-to-SQL stage will be run with **frontier API models (OpenAI GPT or
Anthropic Claude)**, not a local 7B, when the harness is next extended. Decided
after the local smoke runs showed S2 is the discriminating stage and the local
`qwen2.5-coder:7b` is far below it (denominator F1 0.250, 128/486 `sql_error`,
conditioning wrong on 41.5% of records — `11_model_pipeline.md` §10.3).

- The harness needs no structural change: the `Provider` protocol in
  `framework/extract/llm_client.py` was designed for exactly this — add an
  `openai`/`anthropic` adapter with the same `complete(messages, schema)`
  interface and the same disk cache.
- The local results in §10.3 stand as the local-model baseline row, not as the
  headline S2 number.
- S1 extraction remains local-first (a 7B with the tier hint already reads
  0.918); this decision covers S2 only.
- Supersedes the local-only scoping of 2026-09-01 for S2 alone; no API keys are
  in the environment yet, so nothing runs until they exist.
- **Built the same day:** `AnthropicClient` / `OpenAIClient` in
  `framework/extract/llm_client.py` (stdlib urllib, same cache, forced-tool /
  json_schema structured output, backoff on 429/5xx), `client_for` factory,
  `run_eval.py --provider/--sql-provider` (keys from env), and model provenance
  (Ollama digest + version) recorded in every run's `config.json`.


## DECIDED: enumeration caps are a documented design choice (issue 22, 2026-09-04)

`K_PAIR = 25` / `K_TRIPLE = 16` (`generation/cores.py`) stay at their v1 values:
hypotheses are posed over each cohort's 25 most frequent event terms (16 for
triples). This is now a DOCUMENTED sampling policy, not a hidden knob: it bounds
the enumeration combinatorially and biases the benchmark toward well-powered,
clinically common events. The release therefore ships 17-97% of the decisive
supply per group (measured 2026-08-31); full enumeration is revisited only with
the post-pilot scale-up (Part A distribution report), never as a silent change.
Decided at the 2026-09-04 dataset-stabilization review.


## v1.1 REGENERATED: issues 23 and 25 fixed (2026-09-04)

`data/release/v1.1` supersedes v1 as the working release; v1 stays committed and
immutable. Same generator settings (seed 0, target 300), same totals — 18,492
instances / 147,936 records / 8,964 facts — with two confined fixes:

- **Issue 23 (report-tier vaccine skew): FIXED.** `_enum_report` samples reports
  in a seeded-shuffle order (`REPORT_SAMPLE_SEED = 20260904`) instead of the 300
  chronologically lowest VAERS ids. Measured on v1.1: Janssen 35.1% / Moderna
  31.2% / Pfizer 33.8% of report-tier reports vs corpus 36.8/31.0/32.2 (v1 had
  Janssen at 8.8%). 382 distinct reports; C-R1's natural split moved to 193/107.
- **Issue 25 (`test_verdict` canonical at report tier): FIXED.**
  `oriented_significance` now mirrors the deterministic verdict when the
  instance asserts the flipped claim (`flip_kind` direction/option/order);
  C-R1's plain-posed refuted rows are untouched, exactly matching the measured
  v1 crosstab. Measured on v1.1: `test_verdict == gold_verdict` on ALL 18,492
  rows (v1: 1,800 mismatches).

Verification at regeneration: the artifact checks above, and **B0 oracle = exactly
100% over all 147,936 v1.1 records** (verdict/class-macro/group-macro 1.0,
retrieval EM 1.0, p-agreement 1.0, 2,292 underdetermined all expected, 466 s;
`results/oracle_v1.1`). **Exhaustive `validate_gold --sample 0` landed clean:
43,618 realized instances, ALL CHECKS PASSED across the six invariant families
(A evidence arithmetic, B set algebra, C conditioning, D direction, E verdict,
F independent recompute). The dataset is FROZEN; the §1a experiment queue in
`09_next_steps.md` is unblocked.** Cohort-tier
instances are unchanged from v1 (only report-tier ids moved: the v1.1 smoke
slice shares 177/200 ids with v1's). Subset files are now release-versioned
(`eval_core_v1.1_pg90_s0.json`, `smoke_200_v1.1_s0.json`); `run_eval.py` derives
the subset filename from the release directory. Issue 24 (wording) is
independent of this regeneration: a later reword is text-only and id-stable.

---

## Evidence for the issue-22 cap decision, and two environment findings (2026-09-05)

### What `K_PAIR = 25` actually selects (recorded for the 2026-09-04 decision)
Issue 22 was decided as "keep the caps and document them as a sampling policy".
This is the measurement that documents them, because the policy is sharper than
"the top 25 most frequent terms" makes it sound.

Per cohort, the viable pair set (co-occurring >= 10) against what top-25 reaches:

| cohort | viable pairs | reachable from top-25 | top-25 pairs that are NOT viable |
|---|--:|--:|--:|
| Pfizer | 247 | 158 (64%) | 142 / 300 |
| Moderna | 293 | 169 (58%) | 131 / 300 |
| Janssen | 419 | 192 (46%) | 108 / 300 |

Two things follow, and both belong in any write-up of the sampling policy:

1. **Roughly half of every cohort's top-25 pairs never co-occur enough to be
   testable.** The cap does not spend its budget on 300 usable candidates; it
   spends about 160 usable and 140 dead ones.
2. **36-54% of the genuinely viable pairs involve a term ranked below #25**, so
   they are unreachable at any budget under this policy.

The mechanism is that FREQUENCY IS A POOR PROXY FOR TESTABILITY -- two common
terms need not co-occur, and two mid-frequency terms often do. So the cap is not
a neutral subsample of the fact space: it is a frequency prior on which questions
get asked. That is defensible as a stated policy (common events are the
clinically interesting ones), but it is not "we took a smaller sample".

Janssen is the worst-covered cohort at 46%, and it is also the cohort with the
most viable pairs -- the policy is least representative exactly where the corpus
is richest.

Related diagnostic, same measurement: for the sequence groups the default
enumeration visits 1,680 triples and finds 2 decisive, while exhaustive
enumeration visits 756 and finds 4. Enumerating twice the candidates for half the
yield is the clearest single illustration of the point.

### The eval harness needs SQLite >= 3.44 (issue 12, upgraded)
The eval DB views use ORDER BY inside `group_concat`, which SQLite added in
3.44.0. The committed `.venv` runs Python 3.9.6 linking SQLite 3.39.5, so all 108
framework tests ERROR there while the 173 generation tests pass -- a split that
looks like a code failure and is not. Fix on this machine:

    python3.13 -m venv .venv313
    .venv313/bin/pip install -e ".[dev]"

gives Python 3.13.14 / SQLite 3.53.1, 527 passed + 5 skipped, and a working
editable install (so `PYTHONPATH=src` is no longer required). `.gitignore` now
covers `.venv*/`.

### `sync_overleaf.py --push` can silently skip the push
It checks for changes AFTER `git add`, so when a commit already exists but has
not been pushed -- exactly the state the documented review-then-push workflow
produces -- it reports "no changes to sync" and exits 0 without pushing. Hit on
2026-08-20; worked around by pushing from the clone. Fix is to check
`@{u}..HEAD` before returning.
