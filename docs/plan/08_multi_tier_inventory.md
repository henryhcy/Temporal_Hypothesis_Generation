# Multi-Tier (Two-Cohort) Candidate Inventory — 2026-08-04

The multi tier is down to three groups (P-M2, C-M2, F-M3) after the 2026-07-28
removals and the S-M2 removal. This is a measured inventory of candidate
replacements, run over the full corpus (`data/medtempo.db`, 3,166 reports).

The diagnosis that drives every candidate: **the multi tier dies from
conditioning, not from corpus size.** Requiring 2–3 specific events to be
co-present in BOTH cohorts collapses n to ~6–20. Every candidate below keeps a
temporal claim and a directional alternative (so the three-decision rule
applies) while conditioning on fewer events — the only lever that raises n.

## Method, and why the obvious baseline is wrong

The natural sanity check is "cores × 0.05 decisive cores expected by chance".
**It is wrong here in both directions**, so every number below is validated
against a **permutation null** instead: shuffle the vaccine labels (preserving
cohort sizes and the fixed core universe), recount, 200 rounds. That destroys
any real cohort difference while preserving core dependence, the discreteness of
the tests, and the term-frequency structure.

`p_perm` = the fraction of shuffled rounds whose decisive count matched or beat
the real one. It asks: **does this group carry more signal than shuffled labels
would produce?** A group that fails it is a group whose supported/refuted labels
are mostly noise.

## Results (min-n floor 20, alpha 0.05 per side)

| candidate | shape | cores | decisive | null mean | p_perm | |
|---|---|--:|--:|--:|--:|---|
| **[base] P-M2** precedes-strict | pair | 99 | 18 | 7.5 | **0.005** | strongest |
| **M-F** precedes-wide | pair | 232 | 26 | 15.6 | **0.025** | **best new** |
| **M-H** early-half | *single event* | 163 | 18 | 10.9 | **0.035** | **new shape** |
| M-C last-overall | single event | 163 | 17 | 10.5 | 0.055 | borderline |
| **[base] C-M2** co-occurs | pair | 232 | 23 | 16.7 | **0.129** | **fails** |
| M-B first-overall | single event | 163 | 13 | 10.9 | 0.373 | noise |
| M-E′ normalised gap | pair, rank | 232 | 31 | 27.3 | 0.333 | noise |
| M-A earliness | single, rank | 160 | 20 | 17.2 | 0.381 | noise |
| M-D "B follows A" | pair | 4353 | 110 | — | — | below chance |

Definitions of the new shapes:

- **M-F precedes-wide** — "In {v1}, {A} comes before {B} more often than in
  {v2}", denominator = reports where **both are present** (co-occurrence counts
  as "does not precede"). P-M2 drops the tied reports; keeping them more than
  doubles the core count (99 → 232) and the decisive count (18 → 26). Same
  claim family, wider denominator, plainer language.
- **M-H early-half** — "In {v1}, {A} appears in the first half of the timeline
  more often than in {v2}", denominator = reports containing **A** with ≥ 2
  levels. **Conditions on ONE event**, so it enumerates over terms (65) rather
  than pairs, which is what sidesteps the co-presence dilution.
- **M-C last-overall** — "{A} is the report's last event more often after {v1}".
- **M-B first-overall** — the same for first. Noise; "first" is dominated by a
  few very common onset terms whose rates barely move across cohorts.
- **M-D "B follows A"** (conditioned on A present only) produced *fewer*
  decisive cores than chance: with B usually absent, the Fisher test on a rare
  numerator is heavily conservative. Rejected.

## Three findings that matter beyond the candidate list

### 1. Every rank-based candidate is noise
M-E′ and M-A look excellent against the analytic baseline (3.1x and 2.5x) and
collapse under permutation (p_perm 0.33 and 0.38). Cause: the Mann-Whitney
normal approximation over **tie-heavy small-integer ordinal data** is
anti-conservative — shuffled labels yield ~11% decisive cores, more than double
the nominal 5%.

**This invalidates §6 lever 2 of `07_significance_findings.md`** ("make the
position test the verdict driver for sequence + multi", citing S-M1/S-M2/S-M3
going 0 → 6 significant). Six out of 90 cores is **6.7%, below the ~11% that
shuffled labels produce**. The lever manufactures false positives rather than
recovering signal. It also independently confirms the S-M2 removal: the
position-test "rescue" was never real.

### 2. C-M2 does not beat its own permutation null
C-M2 (co-occurrence rate across cohorts) is a **kept** group in the 2026-07-28
roster, but its 23 decisive cores sit inside the shuffled distribution
(mean 16.7, p95 25, p_perm 0.129). Whether two symptoms are recorded at the
*same* timeline stage appears to be a property of the annotation/narrative
style rather than of the vaccine. Its supported/refuted labels would be largely
noise. Needs a decision — see `open_questions.md`.

### 3. The permutation null belongs in the pipeline
Two of the three checks above only appear under permutation; the analytic
baseline endorsed the two worst candidates and did not flag C-M2. Any future
group proposal should clear a permutation null before it gets a slot. Note this
is a **design-time validation diagnostic**, not a labeling method — decisions.md
excludes permutation from gold-label computation because the model must be able
to run whatever test produces the label, and that constraint is untouched.

## Recommendation

A multi tier of **P-M2 (or M-F), M-H, and F-M3** — one pair-precedence group,
one single-event timing group, one first-event group — replacing C-M2. M-F and
P-M2 are the same claim family and should not both ship; M-F is the better of
the two on supply (26 vs 18 decisive) and on wording, P-M2 the better on
signal-to-null (0.005 vs 0.025).

Caveats to carry: these are group-level validity checks, so a passing group
still contains per-core false positives at the alpha rate — that is inherent to
significance-as-verdict. And M-H's "first half" boundary (currently
`level/max_level < 0.5`, which puts the middle stage of a 3-level report in the
second half) needs a definitional call before it ships.

Reproduce: `scripts/run_multi_inventory.py`.
