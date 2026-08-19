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

### Adopt any of the six screened candidate families? (issue 19)
`10_family_expansion.md` (branch `template-family-expansion`, 2026-08-14) screened
six families the shipped grid cannot express, 30 groups in
`data/templates/candidates/`. Five clear their permutation nulls; the recommended
order is R1/R3 comparative, then N2 immediate-succession, then N1 position with a
structural null, then R5 presence-association, then N3 and N4 narrowly for
capability rather than mass. Stratified cohorts, N4b at 3/4, and recurrence are
rejected on measurement.

**Blocked behind issue 14.** Every candidate family has a BOOL and a CHOICE variant
computing the same statistic on the same cores -- the twin duplication that already
affects four shipped pairs. Adopting six families before the group-independent
`fact_id` exists multiplies the split leak rather than causing it.

Open beyond that: this is a scope decision as much as a supply one. N5 burden and
R5 association are not claims about temporal ORDER, so adopting them widens what the
benchmark is about, and that is an advisor question.

### A single-event position claim cannot use a 0.5 null (issue 20)
Measured 2026-08-14. Stage populations are uneven -- mean 2.45 terms at rank 0, 2.21
at rank 1, ~1.74 from rank 3 on -- so a term drawn at random from a report's slots is
more likely to be early, and the corpus structural early rate is **0.5327**, not 0.5.
Testing against 0.5 manufactures support: the permutation null mean sat at 15.2% of
cores against a nominal alpha of 5%. Against the per-core structural rate it lands at
5.3%, i.e. alpha, and the family gets stronger.

Open: `core/answers.py::_null_ref` returns a hardcoded 0.5 for every mode and would
have to widen to `_null_ref(mode, core)` to express a per-core null. That interface
was deliberately flattened to 0.5 on 08-11 to fix a claim/test mismatch, so widening
it needs care and a re-run of `validate_gold.py` family D.

Pair-ORDER claims are unaffected: swapping A and B is a symmetry of the shuffle, so
`precedes` really is 0.5 exactly. The bias is specific to one-event position claims.

### Cross-cohort comparison of a single-event position is invalid as posed (issue 21)
Measured 2026-08-14, and the trap generalises, so it is worth keeping even though the
shapes it kills are all rejected anyway.

Comparing one event's position between two cohorts with a Fisher 2x2 is confounded by
**report geometry**: the two cohorts contain different timelines, so they carry
different structural rates. The per-core structural gap between age bands is median
3.5pp, Q3 6.0pp, max 12.8pp, with **37 of 124 comparable cores above 5pp** -- the same
magnitude as the effects being called significant. A label-shuffle null cannot absorb
it, because every shuffled round gives both cohorts the same geometry mix while the
real data has a systematic difference. The null is therefore too permissive by
construction, which is why X6 (age-band position) shows p_dec 0.003 and still must be
rejected.

Affects X6, X7 and M-H, and also **T-V3 and K-V5**, the two candidate groups that
compare two events without requiring co-occurrence. Fix: test each arm against its
own structural rate and compare the deviations. Until then those two groups are on
hold. Does NOT affect pair-order contrasts (P-M2, X1, X3, X5).

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
