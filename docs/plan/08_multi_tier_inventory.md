# Multi-Tier (Two-Cohort) Candidate Inventory — 2026-08-04

> **SUPERSEDED — read the refreshed table below (2026-08-11).** The original
> figures in this doc were measured at min-n floor 20, before the first-mention and
> tie fixes, and at 200 rounds. All of that changed on 2026-08-11, so the
> "Results" table and the "Recommendation" have been replaced with a re-run at
> floor 10, 2000 rounds, on the corrected corpus. The three "findings that matter"
> sections below are UNAFFECTED — they are about rank tests and about method, not
> about the floor.
>
> **Headline change: F-M3 was measured for the first time and FAILS
> (p_perm 0.188).** With C-M2 also failing, the validated multi tier collapses to a
> single claim family.

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

## Results (min-n floor 10, alpha 0.05 per side, 2000 rounds, corrected corpus)

Re-run 2026-08-11 via `scripts/run_multi_inventory.py` (defaults are now floor 10 /
1000 rounds). `decisive/cores` is the real count over the core universe.

| candidate | shape | decisive/cores | null mean | null p95 | p_perm | |
|---|---|--:|--:|--:|--:|---|
| **[base] P-M2** precedes-strict | pair | 30/322 | 18.3 | 27 | **0.023** | **clears** |
| **M-F** precedes-wide | pair | 46/572 | 32.2 | 44 | **0.034** | **clears** |
| M-C last-overall | single event | 18/193 | 11.6 | 18 | 0.073 | fails |
| M-H early-half | single event | 18/193 | 12.5 | 20 | 0.109 | fails |
| **[base] F-M3** first-of-triple | **triple** | 8/75 | 5.2 | 10 | **0.188** | **fails** |
| **[base] C-M2** co-occurs | pair | 41/572 | 34.6 | 47 | **0.202** | **fails** |
| M-B first-overall | single event | 13/193 | 12.3 | 19 | 0.462 | noise |
| M-E′ normalised gap | pair, rank | — | — | — | 0.333 | noise (floor-20 figure) |
| M-A earliness | single, rank | — | — | — | 0.381 | noise (floor-20 figure) |
| M-D "B follows A" | pair | — | — | — | — | below chance |

Round-count stability, same code and data — the verdicts do not move, so 1000 rounds
is sufficient and **200 is triage only** (it read M-C as 0.035, a passing value):

| candidate | 200 | 1000 | 2000 | 3000 |
|---|--:|--:|--:|--:|
| P-M2 | 0.045 | 0.024 | 0.025 | 0.025 |
| M-F | 0.035 | 0.036 | 0.033 | 0.032 |
| M-C | **0.035** | 0.080 | 0.073 | 0.076 |
| M-H | 0.095 | 0.119 | 0.120 | 0.107 |
| C-M2 | 0.144 | 0.195 | 0.151 | 0.203 |
| M-B | 0.458 | 0.472 | 0.453 | 0.465 |

### F-M3, measured at last

F-M3 shipped in the roster having never been screened. It now has: **8 decisive
cores against a noise mean of 5.2 and a noise p95 of 10 — p_perm 0.188.** Shuffled
labels reach 8-or-more in 19% of rounds, so its supported/refuted labels cannot be
distinguished from randomising which vaccine each patient received.

This is what the M-B analogy predicted. Note the two are NOT the same shape and the
inventory treats them differently on purpose: M-B asks "is A *at* level 0" (ties
count), F-M3 asks "is A *uniquely* first among A, B, C" (ties leave the denominator,
per the 08-11 decision). F-M3 is the stricter, better-posed claim, and it still fails.

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

## Substitutes for F-M3: none exist (2026-08-11)

After F-M3 failed, three untested first/last two-cohort shapes were screened
(floor 10, 1000 rounds). All fail:

| candidate | claim | decisive/cores | null mean | p_perm |
|---|---|--:|--:|--:|
| M-J last-of-triple WIDE | A is last among A,B,C; ties count as not-last | 30/387 | 21.2 | **0.096** |
| F-M3 first-of-triple | A is first among A,B,C; ties excluded | 8/75 | 5.2 | **0.183** |
| M-G first-of-triple WIDE | A is first among A,B,C; ties count as not-first | 20/387 | **20.0** | **0.509** |
| M-I last-of-triple | A is last among A,B,C; ties excluded | 5/105 | 6.6 | **0.698** |

### Why the family has no viable two-cohort shape

It is structural, not a matter of finding the right wording:

1. **With TWO events, "first" IS "precedes."** "A is first between A and B" is
   literally "A precedes B", so it is P-M2, not a distinct group. A first/last multi
   group therefore *requires* three events.
2. **With THREE events, the conditioning starves it.** Requiring all three co-present
   in BOTH cohorts leaves 75 cores when ties are excluded, or 387 when they are not.
3. **And the widening trick that rescued precedes does not transfer.** M-F beat P-M2
   on supply by counting co-exist as "does not precede". The same move here produces
   **M-G at real 20 vs null mean 20.0** -- exactly what noise makes. Cause: the
   first/last tie rate is ~55%, so the widened denominator is majority tie reports,
   which dilute the numerator equally in both cohorts and add variance without signal.
4. **M-I lands BELOW chance** (5 real vs 6.6 expected), the same conservative-Fisher
   signature that retired M-D: a rare numerator on a small table makes the exact test
   heavily conservative.

M-J is the least-bad at 0.096, roughly twice alpha. More rounds cannot rescue it --
p_perm is a ratio, not a precision artefact -- and there is no obvious better-posed
variant left, since narrow and wide denominators are the only two choices and both
have been tried in both directions.

**Conclusion: the first/last family has no two-cohort tier.** F-M3 is retired with no
replacement.

## Recommendation (rewritten 2026-08-11)

**Only P-M2 and M-F clear, and they are the same claim family** (does A precede B
more often in one cohort), so at most one of them ships. C-M2 fails (0.195-0.202),
F-M3 fails (0.183-0.188) and is now RETIRED with no viable substitute, and no
single-event or triple-based candidate clears.

So the validated multi tier is **one group**: P-M2, or M-F as a wider-denominator
rewording of it. M-F has more supply (46 vs 30 decisive) and plainer wording; P-M2 is
marginally stronger against its null (0.023 vs 0.034).

That forces the question in `open_questions.md`: **is a one-group multi tier worth
the shape at all for v1?** The alternative is to retire the two-cohort tier and keep
the benchmark single-cohort plus report-level, which loses the "does vaccine matter"
claim family entirely but ships nothing that fails its own null.

Caveats to carry: these are group-level checks, so a passing group still contains
per-core false positives at the alpha rate — inherent to significance-as-verdict.
And M-H's "first half" boundary (`level/max_level < 0.5`, which puts the middle stage
of a 3-level report in the second half) would need a definitional call if it were
ever revived, though at 0.109 it is not a candidate.

Reproduce: `scripts/run_multi_inventory.py` (floor 10, 1000 rounds by default).
