# Open Questions

Items still under discussion. Do not assume answers in code; surface gaps
when implementing.

When an item is resolved, move it to `decisions.md` with the date and
**delete it from this file**. On 2026-08-12 this file was cleaned: 11 items
already marked RESOLVED were removed (they had grown to roughly half the file,
so the list no longer answered "what is open?"). Reasoning that lived only here
was preserved in `decisions.md` under "Reasoning preserved from retired open
questions". Several other entries were trimmed to their still-open remainder
rather than deleted whole — each says so.

Every item here appears in the `09_next_steps.md` issue register with its number.

---

## Decisions blocking work

### Is a ONE-group multi tier worth the shape? (issue 1 — blocking the roster)
Settled by measurement: **P-M2 is the only two-cohort group left.** C-M2 and F-M3
were dropped for failing their permutation nulls, F-M3 has no viable substitute,
and the six non-directional multi groups sit at S = 0 pending removal.

So the tier is one group, S = 30, ~90 instances at 3·S. Options:

(a) **Ship P-M2 alone.** Keeps the "does the vaccine matter" claim family,
    arguably the most clinically interesting question in the benchmark, and the
    screening story is a genuine methods strength: seven two-cohort shapes tested
    against a label-permutation null, one survived.
(b) **Swap P-M2 for M-F** (precedes-wide, same claim family): more supply (46 vs
    30 decisive) and plainer wording, marginally weaker against its null (0.034
    vs 0.023). Needs four-register wording written.
(c) **Retire the two-cohort tier for v1.** Loses the claim family entirely; the
    benchmark becomes single-cohort plus report-level.

(a) and (b) both leave ~90 of ~20,700 instances, so the tier is a rounding error
on size but not on scientific scope. Note (a) and (b) are the SAME claim family
(precedes) and should not both ship.

**Supporting evidence — no single-event candidate survives floor 10.** The 08
doc's replacement recommendation was computed at floor 20 and does not survive.
Re-run at floor 10 with 2000 rounds
(`data/pilot/multi_inventory_floor10_2000rounds.json`):

| candidate | shape | p_perm @ floor 20 | p_perm @ floor 10 (2000 rds) | |
|---|---|--:|--:|---|
| P-M2 precedes-strict | pair | 0.005 | **0.025** | clears |
| M-F precedes-wide | pair | 0.025 | **0.033** | clears |
| M-C last-overall | single | 0.055 | **0.073** | fails |
| M-H early-half | single | **0.035** | **0.120** | fails |
| C-M2 co-occurs | pair | 0.129 | **0.151** | fails |
| M-B first-overall | single | 0.373 | **0.453** | noise |

M-H, the 08 doc's recommended "new shape", degrades to 0.120; M-C to 0.073.
Neither can carry a single-event slot.

### Does the sequence family survive at cohort level? (issue 9)
The sequence family's entire cohort-level supply is:

| group | mode | S |
|---|---|--:|
| S-V1 | seq_bool (modal-vs-runner-up) | **4** |
| S-V3 | modal_choice (modal-vs-runner-up since 08-11) | **4** |
| S-R1 | report-level | n/a — deterministic, unaffected |

Eight decisive cores across two groups, and they are largely the SAME four
triples asked two ways, so this is not a family. (S-M1/S-M2/S-M3 are gone or
going; S-V4 was removed 08-11.) Options: (a) accept sequence as a
report-level-only family; (b) apply §6 lever 4 (vaccine-agnostic scope, pooling
all 3,166 reports, ~46% of triples become significant) at the cost of changing
the claim scope to "across all vaccines"; (c) apply §6 lever 5 (coarsen events to
MedDRA SOC/HLGT categories), the real structural fix, which needs a term→category
map.

This subsumes the old "per-group vs benchmark-level balance" question. Equal
thirds stays **per group** — template wording is mechanical and fixed per group,
so group identity is trivially readable from the question text, and a group
shipped at 40/338 would let a model learn "text shaped like this → refuted" and
score ~89% with no temporal reasoning. Benchmark-level balance only closes that
shortcut if group identity is hidden, which it cannot be. What remains open is
purely that S-V1/S-V3 are starved at any balance rule.

---

## Test tracks

### The positional/rank track has no valid test at the n we have (issue 16)
Status is easy to misread: positional results are not *missing*, they were
**measured and retired** on 2026-08-11 (§6 lever 2). The reason was specific —
the Mann-Whitney **normal approximation** is anti-conservative on tie-heavy
ordinal data, calling ~11% of cores decisive under shuffled cohort labels against
a nominal 5%. Running the track as it stands would manufacture false gold labels.

What was retired is the **approximation**, not the idea. The codebase now says
exact tests only, and the rank track is the one place that rule was never
applied. Current state of `core/positions.py`:

| test | used for | exact path? |
|---|---|---|
| Wilcoxon signed-rank | single-cohort precedes pairs | **yes**, n <= 15 |
| Mann-Whitney U | two-cohort (multi tier) | **no** — normal only |
| Friedman | sequence / first-last triples | **no** — chi-square only |
| Kendall's W | consistency | **no** — chi-square only |

The three families with no exact path are exactly the three that are starved.

Why this is worth doing rather than dropping: **the rank track conditions far
less.** The categorical sequence test needs all three events at distinct levels
(median n ~ 6); a rank test runs over every co-present report (median n ~ 21).
That was lever 2's original promise, and it failed only on the approximation.
So a valid exact rank test is a candidate fix for BOTH the thin-family problem
and the missing second track.

Open questions before building it:
- **Is an exact rank test admissible under the "model runs the test" rule?**
  With heavy ties the exact conditional distribution is the permutation
  distribution over the observed multiset. That is deterministic and enumerable
  (a DP over the tied multiset, not sampling), so it is reproducible — but
  `decisions.md` excludes permutation from gold labels on the grounds that the
  model must be able to run whatever produced the label. Decide whether an
  enumerated tie-conditional distribution counts as exact (it should) or as
  permutation (it should not).
- **Does it clear its own permutation null?** Non-negotiable, >= 2000 rounds. The
  whole point is that the approximate version did not.
- **If it clears, is it a second reported statistic or a verdict driver for the
  starved groups?** These are different commitments; the second is what would
  actually rescue the sequence tier.

## Claim/label defects

### C-V3 asks an argmax question but ships a majority statistic (issue 13)
C-V3's text is *"After {v}, is co-occurrence the dominant relation for {A} and
{B}?"* — an **argmax** over {before, after, co-occur}. The statistic it ships is
`sym_bool_cooccurs`: co-occurrence rate **> 0.5**, a majority claim. Those are
different questions; a pair can be 40% co-occur / 35% before / 25% after —
co-occurrence is dominant, yet the majority test refutes.

Measured: the two readings disagree on **195 of 959 computable cores (20%)**, and
**5 of those carry a shipped decisive verdict**. Example — Janssen, Fatigue /
Headache: before 45, after 75, co-occur 76. Co-occurrence *is* the most common
relation, and the instance ships `refuted`.

Same null-alignment defect that got S-V1/F-V3 reworded on 07-13 and F-V2/F-R2 on
08-12. `validate_gold.py` cannot catch it: the label is internally consistent
with its statistic, and what is misaligned is the TEXT. A model that correctly
answers the question as worded is marked wrong.

Options:
(a) **Reword to the statistic** — "do {A} and {B} co-occur in most reports where
    both appear?" But then C-V3 is a pure paraphrase of C-V1 (same BOOL, same
    statistic), and the register axis already supplies paraphrase, so C-V3 stops
    earning a slot.
(b) **Change the statistic to the argmax** — modal-vs-runner-up over the 3-cell
    relation distribution. This is the house pattern already locked for
    S-V1/S-V3/F-V1/F-V3, and it makes C-V3 genuinely distinct instead of a
    duplicate. Needs a permutation-null screen at >= 2000 rounds.
(c) **Remove C-V3.**
Recommended: (b), falling back to (c). Do not ship as-is.

### Twin groups duplicate the same core; the split key does not know (issue 14)
Four group pairs compute the **identical statistic on the identical cores**:

| pair | contrast | identical cores |
|---|---|--:|
| P-V1 / P-V3 | BOOL vs CHOICE | 575 / 575 (100%) |
| C-V1 / C-V3 | **none — both BOOL** | 959 / 959 (100%) |
| S-V1 / S-V3 | BOOL vs CHOICE | 278 / 278 (100%) |
| F-V1 / F-V3 | CHOICE vs BOOL | 195 / 195 (100%) |

Three pairs are a deliberate answer-format contrast and should stay. Two
consequences are not deliberate:

1. **Split leakage.** `instances.core_id` is `f"{group_id}|{vaccines}|{events}"`,
   so P-V1's and P-V3's versions of one fact get **different**
   `derived_from_core_id`. The standing caveat ("mirror pairs share a
   `derived_from_core_id`, keep them together") covers the two ORIENTATIONS of
   one core, not the cross-group twins. A split keyed on that id puts the same
   fact on both sides. Fix: add a group-independent `fact_id` (vaccines + events
   + mode-family) and split on that.
2. **Effective size.** S = 1365 counts each twinned fact twice: **727 distinct
   decisive facts**, 638 duplicates (47%). Both numbers are real — the benchmark
   does ask 1365 questions — but only 727 are independent evidence, which is the
   number that belongs in a power or coverage claim.

---

## Dataset

### Confidence-tag cutoffs are PROVISIONAL (issue 4)
`generation/confidence.py` buckets the 95% Wilson CI width into `high` (<= 0.15),
`moderate` (<= 0.30) and `low` (> 0.30). **Those two numbers were never
calibrated** — they are placeholders, and `04_corpus_survey.md` A4 is the task
that fixes them (the CI-width distribution over viable cores, plus the fraction
that would be tagged low).

Why it matters now: at the floor-10 gate the widths are wide by construction. A
core at k=19/n=25 has width 0.319 and therefore tags `low`, so a floor-sized core
is essentially always `low` and the tag carries almost no information as shipped.
Either recalibrate the cuts against the measured distribution or drop the tag and
release the raw width. Do not report the tag as a finding until A4 runs.

Related, and already locked: the interval is Wilson (not Wald) so it stays inside
[0,1] at k=0 and k=n, its centre is shrunk toward 0.5 and therefore differs from
the point estimate, and two-cohort groups use Wilson-Newcombe on the *difference*.
Effect size is Cohen's h on the arcsine transform, measured against the null the
test actually uses (`decisions.md` 2026-08-11).

### Sourcing `not_locatable` for the non-sequence families (issue 5)
*(Trimmed 2026-08-12: step B resolved `sparse` (0 → 2,722) and partly resolved
`not_locatable` (0 → 116). Only the remainder is open.)*

All 118 `not_locatable` cores are in the SEQUENCE groups (triples present but
always at the same level, so nothing is orderable). The pairwise, co-occurs and
first/last families have **zero** — their enumeration pre-filters pairs/triples
to co-occurrence >= 10, which guarantees a non-empty denominator. So the
insufficient third cannot span all three sub-types within those groups, and 118
is well under what an equal-thirds insufficient class would want anyway.

Open: source it from the pilot enumeration path, which already forms ALL
combinations of the top-K terms and therefore includes pairs that never co-occur?
Or add an explicit generator that picks known non-co-occurring event pairs per
cohort? The 2026-07-28 decision requires this third to be generated deliberately
either way; the question is which mechanism.

### Report-level first/last tie handling for CHOICE (issue 7)
*(Narrowed 2026-08-12: the COHORT-level rule was settled on 08-11 — tie reports
leave the denominator entirely. This is now a report-level question only.)*

Should a report-level CHOICE instance whose candidates tie be marked
`insufficient` (single-valued gold), or accept any tied option as supported
(set-valued gold)? **Current working assumption**: `insufficient`. Set-valued
gold is more defensible at report level than at cohort level precisely because
there is no aggregation to distort — which is why it was rejected for cohorts but
is genuinely open here.

### Report-level groups do not reach equal thirds (issue 6)
Deferred by user decision. Seven of the 23 groups are report-level. The question
underneath: what does `insufficient` mean for a single-report claim? The CHOICE
variants treat a co-exist pair as unanswerable while the BOOL variants map
co_exist to `refuted`.

### Synonym table contents (issue 8)
The manual synonym table for `{A}`/`{B}`/`{C}` slot-filling has not been built,
so `synonym_used` echoes the raw MedDRA term and the released text has no lexical
variation. Open: how many synonyms per term type, source vocabulary (UMLS, MeSH,
manual), and validation process.

### Disconnected components in MedTempo (issue 11)
Rate never measured (`04_corpus_survey.md` A6). If common, the leveled-order
representation needs to handle multiple components per report. If rare (under
5%), mark such reports `insufficient` for cross-component hypotheses and proceed.

### Coverage of multi-vaccine pairs
With only three vaccine pairs, the two-cohort tier is thin. Currently uses the
general n >= 10 floor per cohort. *(The original entry asked about tightening it
for "differ" verdicts; those groups are retired, so what remains is whether 10 is
right for the directional tier — which is now largely moot given the tier is one
group. Fold into issue 1.)*

### R1/R3/R5 group definitions (issue 2)
*(Trimmed 2026-08-12: selection, IDs and answer types were all confirmed
2026-07-28 — R1, R3, R5 adopted, R4 dropped, IDs P-V2=R3, C-V2=R5, P-V4=R1, all
BOOL.)*

Open before coding: the exact **four-register wording** for each. R1 needs a
4-event (A,B,C,D) enumeration shape and R5 a 2x2 presence x presence corpus
helper with marginals. Their supply estimates (P-V2 372, P-V4 415, C-V2 144)
predate every floor and test change and **must be re-measured** — the floor-10
and exact-test changes roughly doubled supply elsewhere, so these may be
understated rather than overstated.

---

## Framework

### Architecture detail (issue 3)
The intended loop: hypothesis → decide which test applies → query the annotation
store for the conditioned reports → aggregate → exact test → three-decision
verdict. Retrieval is a mechanical query over structured data, so the capability
under test is steps 1, 2 and 5. Not yet specified in detail.

### CRAFT integration
Whether the framework uses CRAFT as the relation extractor, or implements its own
hypothesis-conditioned extractor. *(Much reduced in scope by the 2026-08-11 input
change: the framework reads annotations, so extraction is no longer part of this
task. What remains is whether an end-to-end CRAFT → verification pipeline is
worth demonstrating as a separate result.)*

### MedTempo release bookkeeping
Not a design question — resolved 2026-08-11 (the annotations are releasable). The
remaining action: the benchmark release must cite the MedTempo paper and
coordinate with the public archive before the annotation artifact is distributed.

---

## Evaluation

### Metrics breakdown
Verdict agreement is the headline. The six failure modes should be reported
separately: query parsing, conditioning, aggregation, null choice, test/tail, and
the min-n gate. Add **pair-consistency** over mirror pairs — a model answering
`supported` to both directions of one core is the cheapest failure to catch. Not
specified in detail.

### Baselines
The deterministic upper bound is a true **100%**, which makes it a real reference
rather than an estimate. Then: full-cohort annotations in context (~30K tokens,
cacheable), tool-using with code execution, and a single-pass variant. Not
formalized.

### Models to evaluate
Continuity with CRAFT suggests GPT-4.1, Claude Sonnet 4.5, Llama-3.3-70B,
MedGemma-27B. To be confirmed once budget and timeline are firm.
