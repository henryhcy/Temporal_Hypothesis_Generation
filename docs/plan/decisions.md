# Decisions Log

Single source of truth for what has been settled. Append entries with the
date when a decision is locked. Do not silently rewrite past entries; if a
decision changes, append a new entry that supersedes it.

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
