# 04. Pilot and Distribution Report

> **STATUS (2026-08-12): mostly DELIVERED; two parts are still live.**
> Still open: **A4** (CI-width distribution — the only thing that will fix the
> uncalibrated confidence-tag cutoffs, issue 4) and **A6** (disconnected-
> component rate, issue 11). Everything else has been superseded or done:
> the roster is 23 groups not 30, the balance is equal thirds per group not
> 45/45/10, T = 100 was replaced by a ~3·S availability-capped budget, and
> Part C is mechanised in `scripts/validate_gold.py` rather than hand-checked.
> Read "30 groups", "T = 100" and "45/45/10" below as historical.

The sampling numbers in `decisions.md` (T, verdict balance, band cutoffs) are
provisional. This document specifies a PILOT run whose job is twofold:

1. Produce a small benchmark dataset across all 30 groups using the
   provisional numbers, so we can inspect real generated instances end to end.
2. Report the corpus distributions we need in order to recalibrate the
   provisional numbers into final ones.

Run the pilot first. Do not scale to the full benchmark until the pilot's
distribution report has been reviewed and the numbers recalibrated.

## Scope of the pilot

- Cover all 30 groups (not a subset). Starvation and viability problems are
  group-specific, so every group must be visible in the pilot.
- Small scale per group: generate up to the provisional target (T = 100
  instances per group), or all available if the group is under-target.
- All four registers and both formats, as in the full design.

## Part A: distribution report

The pilot must emit a distribution report (Markdown plus a machine-readable
JSON) covering the following. These are the numbers that calibrate the
provisional decisions.

### A1. Viable-core counts per group  (calibrates T)
- For each of the 30 groups, the number of viable factual cores at the
  current threshold.
- The count of groups falling below ~50 viable cores (the binding
  requirement for T = 100).
- A flag list of under-target groups.

### A2. Cohort-size (n) distribution across viable cores  (calibrates bands)
- Per family (pairwise, sequence, first/last): the distribution of n across
  viable cores (min, 25th, median, 75th, max, plus a histogram).
- Enough detail to decide quantile vs fixed-count banding and how many bands
  the range supports.

### A3. Natural verdict distribution  (calibrates verdict balance)
- If gold labels were computed on all viable cores with NO balancing, what
  fraction come out supported / refuted / insufficient?
- Reported per group and per family.
- This shows how far the provisional 45/45/10 target distorts the natural
  distribution, and whether that distortion is acceptable.

### A4. Confidence-interval width distribution  (calibrates the low-band floor)
- For viable cores (or a sample), the distribution of 95% CI widths on the
  gold proportion.
- The fraction of cores that would be tagged low-confidence (CI width above
  the threshold in `decisions.md`).
- Informs whether the n >= 10 floor is too permissive.

### A5. Multi-vaccine overlap and insufficiency  (calibrates option 1)
- For each of the three vaccine pairs, the count of event pairs/triples that
  clear the per-cohort threshold in BOTH cohorts.
- Within multi-vaccine cores, the fraction that come out `insufficient`
  because one cohort is below threshold.
- Specifically flag whether Janssen-containing pairs (written "Johnson" in
  these seed docs) have enough computable
  (non-insufficient) cores to fill a reduced budget; if not, that triggers
  the contingent fallback in `decisions.md`.

### A6. Representation diagnostics
- Disconnected-component rate (fraction of reports with >1 component). This
  resolves the open question in `open_questions.md`.
- Cycle-check result (any report whose directional relations contain a
  cycle). Cycles indicate a conversion error.
- Tie rate for first/last (fraction of reports where two or more candidates
  share the earliest/latest level).

## Part B: pilot dataset

Using the provisional numbers, generate a small dataset across all 30 groups:

- Apply target-with-availability-cap (T = 100, ~50-core requirement).
- Apply the 45/45/10 verdict balance, with insufficient capped.
- Apply quantile frequency banding and one-synonym-per-instance sampling.
- Output in the per-instance JSONL schema from `02_dataset_design.md`,
  extended with the statistical fields from `decisions.md`: point estimate,
  p-value (with the test name and null stated), 95% CI, effect size, and a
  high/moderate/low confidence tag.

The pilot dataset is for inspection, not release. We read a sample of
generated instances to confirm the templates, slot-filling, and gold labels
look correct.

## Part C: validation sample (correctness guard)

**DELIVERED and MECHANISED (2026-08-11) as `scripts/validate_gold.py`** — six
invariant families over every generated instance, rather than a 20-30 core hand
check. It earned its keep immediately: it is what caught the first-mention bug,
and the F-V2/F-R2 wrong-event bug and the `gold_n2`/`gold_k2` cohort swap were
both found the same way. Run it before trusting generated data; it belongs in CI.

**Known limit worth stating.** Every invariant compares gold fields TO EACH
OTHER, so no invariant can catch a mismatch between the question an instance
ASKS and the quantity it SCORES. That defect class has now appeared three times
(S-V1/F-V3 07-13, F-V2/F-R2 08-12, C-V3 08-12) and is found only by reading a
rendered instance beside its statistic. It needs a review step, not another
invariant.

~~Original spec: select 20-30 cores spanning families and answer types, compute
gold labels by code AND record the inputs so a human can hand-check.~~

## Output locations (suggested)

- `data/pilot/distribution_report.md` and `distribution_report.json`
- `data/pilot/pilot_instances.jsonl`
- `data/pilot/validation_sample.md` (the 20-30 hand-checkable cores)

## After the pilot

Bring the distribution report back to the research discussion. We recalibrate
the provisional numbers in `decisions.md`:

- Set the final T at the knee of the per-group viable-core distribution.
- Set the band cutoffs from the n-distribution.
- Confirm or adjust the verdict balance against the natural distribution.
- Decide the low-band floor from the CI-width distribution.
- Confirm multi-vaccine coverage or trigger the Janssen-pair fallback.

Only then scale to the full benchmark.

## What the pilot does NOT do

- It does not produce the released benchmark; it produces a pilot for
  inspection plus a distribution report.
- It does not finalize any sampling number; all remain provisional until
  recalibrated from the report.
