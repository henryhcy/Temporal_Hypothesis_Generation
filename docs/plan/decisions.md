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
