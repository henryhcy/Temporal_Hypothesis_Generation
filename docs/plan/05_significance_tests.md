# 05. Significance Tests: Reference and Implementation

> **STATUS (2026-08-12): the min-n section is current (updated 08-11); the test
> descriptions and the per-group table were NOT, and contradicted it.** Two
> corrections applied below: chi-square is gone everywhere (it survived only in
> this doc's prose), and the position-test track is descriptive-only. The
> per-group table lists seven groups that no longer exist and is marked as
> historical rather than deleted, since it records what each retired group was
> tested with.

This is the single reference for the significance-test design. It covers the
two test representations, the per-group test assignments for both, the
minimum-n constraint on every test, how the tests are run at inference, and
the shared gating helper. The companion docx
(`docs/reference/Temporal_Hypothesis_Templates.docx`) carries the same content
with worked formulas.

## Data type and why these tests

Outcomes are categorical (nominal labels: which ordering, before/after) or
ordinal (event positions: level indices), never continuous measurements. We
have order but no measured spacing, because MedTempo has no timestamps. So:

- We can count, which gives proportions, so categorical tests apply.
- We can rank positions, so rank-based tests apply.
- We cannot form a meaningful mean or independent variance, so mean-based
  tests (t-test, F-test, ANOVA) do NOT apply. For categorical data the
  variance is fixed by the proportion, not estimated separately.

Test selection is governed by the number of categories and the number of
cohorts, not by variance.

## Two test representations

> **AMENDED 2026-08-11: this is no longer a choice of two label-producing
> tracks.** The categorical track produces every gold label. The position track
> is **descriptive only** — `core/positions.py` must not be imported by
> `core/answers.py`. Its normal approximation is anti-conservative on tie-heavy
> ordinal data: under shuffled cohort labels the rank tests call ~11% of cores
> decisive against a nominal 5%, so the §6 lever-2 proposal to make them the
> verdict driver was retired. The description below is kept because the
> complementarity argument is still the right intuition for *diagnostics*.

Every cohort-level group can carry two tests drawn from the same leveled-order
data.

1. **Categorical** (on the outcome label). Counts of labels follow a binomial
   (2 categories) or multinomial (k categories) distribution. Answers "in what
   fraction".
2. **Position-based** (on the event level indices). From positions we derive a
   per-report quantity (rank-distance d = level(A) - level(B); co-exist gives
   d = 0) tested with non-parametric rank methods. Answers "by how much, on
   average".

The two are complementary and can disagree at the margin (frequent-but-small
vs rare-but-large), which is diagnostic. Co-occurs has no natural
position-based analog (co-occurrence is the single point d = 0) and keeps the
categorical test only.

## The categorical tests

**EXACT TESTS ONLY (2026-08-11).** ~~Exact tests are primary; chi-square tests
are large-sample approximations used only when every expected cell count is
>= 5.~~ There is no asymptotic branch and no expected-cell chooser anywhere in
the codebase: one test per claim shape, at every n. Past
`significance.EXACT_MAX_TABLES` the k-category enumeration raises
`ExactTestTooLarge` rather than quietly reverting — an infeasible table is a
design signal (coarsen the categories, or gate the core out), not something to
approximate. `chi2_sf` survives solely as a distribution function for the
descriptive rank tests.

- **Binomial exact** (one cohort, two categories). Tests whether a proportion
  departs from a chance baseline p0. Used for pairwise/co-occurs vaccine-level
  groups, sequence one-ordering groups, and first/last one-candidate groups.
  Run **one-sided in the observed direction** (`greater` above the null,
  `less` below) because these claims are directional; see the 2026-07-13
  one-sided decision in `decisions.md`.
- **Fisher's exact** (two cohorts, two categories, 2x2). Tests whether two
  cohort proportions differ. Used for multi-vaccine BOOL/CHOICE on a single
  outcome. **One-sided** for the directional `multi_dir_*` modes; **two-sided**
  for the `multi_differ_*` "do they differ" modes.
- **Exact multinomial goodness-of-fit** (one cohort, k categories) ~~with
  chi-square goodness-of-fit as the large-n approximation~~. Tests whether a
  distribution departs from uniform. **NOTE (2026-07-14 / 2026-08-11): GOF no
  longer labels any argmax claim.** Showing a distribution is not flat does not
  show the NAMED cell is the mode, so every "most common X" group moved to
  modal-vs-runner-up (a one-sided exact binomial of the named cell against its
  strongest competitor). Used for "most common ordering" and
  "which is first" within one cohort.
- **Fisher-Freeman-Halton exact** (two cohorts, k categories, 2xk), with
  chi-square homogeneity as the large-n approximation. Tests whether two
  cohorts share a distribution. Used for "is the ordering / first event the
  same across two vaccines".

Chance baselines: p0 = 1/2 for pairwise/co-occurs, 1/6 for a sequence
(six orderings), 1/3 for first/last (three candidates); uniform 1/k for the
distribution tests.

## The position-based tests

All are non-parametric and produce p-values without any mean or normality
assumption.

- **Wilcoxon signed-rank** (one cohort, paired events). Tests whether the
  median rank-distance is non-zero, i.e., whether A is systematically earlier
  than B by a margin. Used for precedes vaccine-level and F-V3.
- **Mann-Whitney U** (two cohorts, independent). Tests whether one cohort's
  positions are systematically earlier. Used for multi-vaccine position
  comparisons.
- **Friedman** (one cohort, three events ranked within report). Tests whether
  the three events differ in typical position; lowest mean rank is typically
  first. Used for S-V3, F-V1, F-V2 in the position view.
- **Kendall's W** (coefficient of concordance, 0 to 1). Measures how
  consistently reports agree on an ordering; W near 1 = consistent. Used for
  S-V4.
- **Kruskal-Wallis** (three or more cohorts). The three-group extension of
  Mann-Whitney. Reserved for future three-vaccine groups; not used in the
  current two-vaccine design.

## Per-group assignments

Report-level groups (P-R1, P-R2, C-R1, S-R1, F-R1, F-R2, F-R3) are NOT
eligible: a single report is one observation with no sampling distribution.
The other 23 groups:

| Group | Categorical test | Position-based test |
|---|---|---|
> **HISTORICAL TABLE (as of 2026-07).** Kept as the record of what each group
> was tested with; **do not read it as the current assignment.** Retired since:
> P-V2 / C-V2 / S-V2 (PROP, 07-14), S-M2 (08-04), S-V4 (08-11), C-M2 and F-M3
> (08-11, failed their nulls). The argmax groups (S-V1, S-V3, F-V1, F-V2, F-V3)
> moved to modal-vs-runner-up. The right-hand column is descriptive-only. The
> live mapping is `cores.MODE_BY_GROUP` plus the dispatch in `core/answers.py`.

| P-V1, P-V2, P-V3 | Binomial exact vs 1/2 | Wilcoxon signed-rank |
| P-M1, P-M2 | Fisher's exact | Mann-Whitney U |
| C-V1, C-V2, C-V3 | Binomial exact vs 1/2 | none (no rank analog) |
| C-M1, C-M2 | Fisher's exact | Mann-Whitney on \|d\| (optional, weak) |
| S-V1, S-V2 | Binomial exact vs 1/6 | Wilcoxon signed-rank (concordance) |
| S-V3 | Exact multinomial GOF | Friedman |
| S-V4 | Exact multinomial GOF | Kendall's W |
| S-M1, S-M2 | Fisher's exact | Mann-Whitney U per event |
| S-M3 | Fisher-Freeman-Halton | Mann-Whitney U per event |
| F-V1, F-V2 | Exact multinomial GOF | Friedman |
| F-V3 | Binomial exact vs 1/3 | Wilcoxon signed-rank |
| F-M1, F-M2 | Fisher-Freeman-Halton | Kruskal-Wallis / Mann-Whitney per event |
| F-M3 | Fisher's exact | Mann-Whitney U |

~~Verdict polarity: most groups map significant to "the asserted effect is
real". S-M3 and F-M1 ask "is it the SAME" … The gold-label code needs a
per-group polarity flag.~~

**SUPERSEDED 2026-07-28. No polarity flag exists or should be added.** The
three-decision test made it unnecessary: the label follows from WHICH TAIL is
significant, so direction is a property of the claim, not a per-group constant.
The groups that needed an inverted flag (S-M3, F-M1, F-M2) are exactly the
"same"/"differ" shapes that cannot map onto three decisions at all — needing the
flag was the symptom, and they are pending removal.

## Minimum-n constraint (applies to every test)

Every test requires a minimum conditioned sample. Below it the p-value is
coarse and the verdict is fragile to small extraction errors, so the instance
is labeled `insufficient` rather than tested.

Rule: a family floor, and NOTHING ELSE. The expected-count guard is gone
(2026-08-11) -- every k-category test is exact, and an exact test needs no
minimum expected cell.

| Group type | Table | Min n | Binding constraint |
|---|---|---|---|
| Pairwise / co-occurs, 1 cohort | 1x2 | 10 | family floor |
| Pairwise / co-occurs, 2 cohorts | 2x2 | 10 per cohort | family floor |
| Sequence one-ordering, 1 cohort | 1x2 | 5 | family floor |
| First/last one-candidate, 1 cohort | 1x2 | 10 | family floor |
| First/last distribution, 1 cohort | 1x3 | 10 | family floor |
| Sequence distribution, 1 cohort | 1x6 | 5 | family floor |
| First/last distribution, 2 cohorts | 2x3 | 10 per cohort | family floor |
| Sequence distribution, 2 cohorts | 2x6 | 5 per cohort | family floor |

The floor is **10 for every family except sequence, which is 5** (decisions.md
2026-08-11). Sequence gets the lower floor because its denominator -- reports
where the triple is present AND orderable -- is a far deeper conditioning than
pair co-presence, and at 10 the family's cohort-level supply is exactly zero. The
10 matches the enumeration viability floor (`corpus._MIN_N`), so the gate no
longer discards cores the enumerator was willing to emit.

The position-based tests inherit the same family floors and additionally require
enough non-zero pairs for the signed-rank tests. NOTE: those tests use a normal
approximation that a permutation check found anti-conservative on tie-heavy
ordinal data, and they produce no benchmark label -- see `open_questions.md`.

## How the tests are run

The same closed-form tests run twice: once offline to compute the gold label,
and once by the model at inference. The model is given a code-execution tool
and runs the identical test through a statistics library (e.g., scipy). Because
both sides use the same closed-form test and the same min-n helper, they match
by construction; any discrepancy reflects the model extracting different counts
from the narratives, which is the capability under test.

No permutation or Monte-Carlo test is used anywhere. Permutation is not a
closed-form step the model can execute, and the gold label must use whatever
test the model runs. Sparse cases that permutation might have rescued are
gated to `insufficient` by the min-n helper instead.

## Shared min-n helper

The minimum-n logic is a single standalone helper that BOTH dataset creation
and model evaluation call directly. This guarantees the threshold is defined
in one place and applied identically on both sides.

- Interface: takes the conditioned counts (and optionally the intended test
  type) and returns a decision (testable / insufficient) plus a reason.
- Gate-only: it answers "is there enough data to run a test", not "which
  test". This keeps it neutral for the test-chosen-by-model evaluation mode,
  where selecting the test is the model's job.
- Optional test-type argument enables the expected-count >= 5 cell-adequacy
  check for the k-category tests.

Build the gold-label generator to CALL this helper, not inline the threshold
logic, so the single-source-of-truth property holds from the start.

## Reporting

Every eligible instance reports both a p-value and a 95% confidence interval
from the same conditioned data. The p-value states whether the effect departs
from chance; the CI states how precisely the rate is estimated.

- CI methods: Wilson (single proportion), Wilson-Newcombe (difference),
  bootstrap (sequence, multi-vaccine, rank statistics), Sison-Glaz
  (multinomial).
- Effect size: Cohen's h or odds ratio (proportions), Cramer's V (k-category
  tables), rank-biserial (rank tests).
- Alpha = 0.05 throughout.
- No multiple-testing correction at the benchmark level, so instances stay
  independent; documented as a known property.

## Evaluation modes (deferred to the evaluation phase)

Two modes are planned; see `open_questions.md` for details.

- **Test-chosen-by-model** (agentic, headline): the model selects, builds,
  runs, and interprets the test. Graded on the VERDICT, allowing a valid
  alternative test to count as correct.
- **Test-given-in-prompt** (isolation): the test and null are specified, so
  the evaluation isolates execution from selection.
