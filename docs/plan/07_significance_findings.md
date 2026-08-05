# Significance & Sampling — Working Session Findings (July 2026)

A self-contained record of the diagnostic findings, design decisions, and the
open questions from the significance/sampling working session. Companion to
`decisions.md` (locked decisions) and `open_questions.md` (still open). The
numbers are computed by `scripts/make_examples.py` over the full corpus
(`data/medtempo.db`, 3,166 reports) and are reproduced in
`docs/reference/Worked_Examples.md`.

---

## 1. The core finding: supported ≠ significant

Across every viable core that carries a **definite gold verdict**
(supported/refuted) and an **applicable categorical test** (PROP and
report-level excluded), most are **not statistically significant** at α = 0.05.

- **Overall fail rate: 2354 / 2998 = 78.5%.** ("processed" = the 2,998 definite
  categorical cores; "fail" = the 2,354 the test does not corroborate.)
- By family:
  - pairwise-precedes  350/534   (65.5%)
  - co-occurs          876/1186  (73.9%)
  - sequence           876/919   (95.3%)
  - first/last         252/359   (70.2%)

The fail rate counts a core as fail whether its gold is **supported OR refuted**;
the supported-only slice is 80.5% (1016/1262) and refuted-only 77.1%
(1338/1736). It is instance-level, so mirror templates (P-V1/P-V3, C-V1/C-V3)
that compute the identical statistic are counted in each group.

### Significant-core inventory (the ceiling)

The number of significant cores is fixed by the corpus and is the hard ceiling
on how many "supported" items a group can ever yield. Under **significance-as-
verdict** (§3) this column literally caps each group's supported class.

| group | significant cores | | group | significant cores |
|---|--:|---|---|--:|
| P-V1 | 77  | | S-V1 | 20 |
| P-V3 | 77  | | S-V3 | 12 |
| P-M1 | 15  | | S-V4 | 11 |
| P-M2 | 15  | | S-M1 | **0** |
| C-V1 | 141 | | S-M2 | **0** |
| C-V3 | 141 | | S-M3 | **0** |
| C-M1 | 14  | | F-V1 | 25 |
| C-M2 | 14  | | F-V2 | 37 |
| F-M1 | 2   | | F-V3 | 41 |
| F-M2 | 2   | | F-M3 | **0** |

Four groups (**S-M1, S-M2, S-M3, F-M3**) have **zero** significant cores — a
constant-answer, degenerate template as-is.

---

## 2. Why — the report → core dilution funnel

The corpus is fully used; scarcity is in the **viable cores**, not the reports.

```
3,166 reports  →  Pfizer 1,019 · Moderna 983 · Janssen 1,164   (median 6 terms/report)

PAIRS (2 events, 1 vaccine):
   ~15k–18k distinct pairs exist per cohort
   →  only 89–179 recur in ≥20 reports        (median usable n ≈ 30)   testable

TRIPLES (3 events, 1 vaccine):
   ~68k–111k distinct triples exist per cohort
   →  only 553–1,432 co-occur in ≥5 reports
   →  after the STRICT-ORDER shrink: median orderable n = 6, max 9–28   tiny

MULTI-VACCINE TRIPLES (must clear the floor in BOTH cohorts):
   →  328–488 triples qualify
   →  median of min(n1,n2) = 7–8 reports per cohort                     hopeless for Fisher
```

**Effective sample size per question**: pairwise ≈ 30, sequence ≈ 6,
multi-vaccine ≈ 7–8 per cohort. That gradient IS the significance gradient
(46% → 8% → 0% significant). Slicing 3,166 reports into "this exact triple, this
exact vaccine pair, strictly ordered" leaves ~6–8 reports behind each question.
Significance needs more than that; the corpus doesn't have it for those types.
**Raising T (the per-group instance budget) cannot fix this** — T caps how many
enumerated cores we KEEP, not how many reports stand behind a question.

---

## 3. Design direction: significance-as-verdict

The intended framework pipeline: the model runs the significance test first;
**significant in the asserted direction → `supported`, significant in the
opposite direction → `refuted`, not significant → `insufficient`.** Under this
pipeline the significance verdict and the supported/refuted verdict **coincide**
— they are no longer two separate axes reported together. (Recorded in
`decisions.md`, 2026-07-01.)

Consequences:
- Gold `supported` is now defined as "statistically significant" — a stricter,
  more defensible standard than "proportion > 0.5 in a tiny cohort."
- The per-group null must be the **negation of the claim** (§4).
- The **supported class is capped by the significant-core inventory** (§1), so
  the four zero-significant groups can produce no supported items.

**Still open:** whether not-significant maps to `insufficient` (recommended:
two-sided test + direction gives supported/refuted/insufficient cleanly) or
`refuted`.

---

## 4. Reword decision — align the null with the claim boundary

"Significant ⟹ supported" is only coherent when the test's null p₀ sits at the
boundary the claim asserts.

- **Aligned:** pairwise "A typically precedes B" (claim boundary 0.5, null p₀ =
  0.5). Chance = 1/k = 0.5 only when k = 2.
- **Misaligned:** the BOOL **sequence / first-of-3** claims are worded
  "typically / majority" (boundary 0.5) but their null is the **chance** rate
  (1/6 for a 3-event ordering, 1/3 for first-of-3). A 30% modal ordering is
  significant vs 1/6 yet is not a majority → test and claim disagree.

**Decision:** reword those BOOL claims to match the chance null ("A→B→C is the
**most common** ordering / occurs **more often than chance**"; "X is the **most
common first** event") rather than move the null to 0.5 (which almost nothing in
this corpus clears). Pairwise and the CHOICE (uniform-null GOF) groups are
unchanged. (Recorded in `decisions.md`, 2026-07-01.) Exact per-register strings
are not yet written.

### Null hypotheses, by mode (now shown in the report per template)

| family | H0 (what the p-value tests against) |
|---|---|
| pairwise precedes | P(A precedes B) = 0.5 |
| co-occurs | P(A and B co-occur) = 0.5 |
| sequence (bool/prop) | P(ordering = A→B→C) = 1/6 |
| modal / consistency | the 6 orderings are uniform |
| first-bool | P(A is first) = 1/3 |
| first / last choice | the 3 candidates are uniform |
| multi differ / dir | rates equal across cohorts (p₁ = p₂, Fisher) |
| multi same-first / same-order | same distribution across cohorts (homogeneity) |
| report-level | none (single deterministic observation) |

H0 is the **no-effect / chance baseline**, NOT the reverse of the claim. The
claim is the *alternative* (H1); the reverse direction ("B precedes A") is a
different alternative, not the null. For "differ" claims H0 ("no difference")
does coincide with the negation, because the claim is about the existence of an
effect.

---

## 5. The min-n gate inconsistency

`significance_verdict` forces `insufficient` whenever **n < 10**, regardless of
p. But the **sequence family viability floor is 5**. So sequence cores with
5 ≤ n < 10 pass viability yet **can never be significant** — even a unanimous
7/8 (p = 0.000) is gated out.

- **114 fails (all sequence) are pure n-gate** — p < 0.05 but blocked by n < 10.
  That is 13% of the 876 sequence fails.
- Exact tests are valid at small n by construction, so the blanket n ≥ 10 gate
  is arguably too conservative. **Lowering the sequence significance gate to the
  family floor (5) would flip those 114 fail → significant** for free.
- The other 95% of fails are genuinely underpowered (p ≥ 0.05); no gate change
  touches those.

This is a `decisions.md`-level reconciliation (family floor vs significance
MIN_N) — not yet applied.

> **Update (2026-08-04): this recovery is MOOT, and the reconciliation is a net
> loss.** The 2026-07-14 redesign already replaced the sequence test with
> modal-vs-runner-up on a 2-cell table floored at 5, so the 114 cores were
> recovered by that change, not by a gate move. Applying the shared family
> floors (20 / 5 / 30) in place of the blanket 10 measures **0 cores gained and
> 1,075 lost** — pairwise −721 (floor 10→20) and first/last −354 (floor 10→30);
> sequence loses none. Numbers and a floor sweep: `data/pilot/verdict_labels.md`
> (`scripts/run_verdict_labels.py`). The floor is now the binding constraint on
> supply; the choice is open in `open_questions.md`.

---

## 6. Levers to improve the undersized (starved) groups

Ranked by impact × cost; the ceiling (§1) is the hard limit.

**Already in hand (no new design):**
1. **Reword** (§4) — lifts S-V/F-V by dropping the bar from majority (0.5) to
   beats-chance (1/6, 1/3). E.g. S-V1 supportable cores ~20 → ~95.
2. **Make the position (rank) test the verdict driver for sequence + multi.**
   The categorical test runs on the strictly-ordered denominator (~6–8); the
   Friedman/Mann-Whitney rank tests run on ALL co-present reports (~21), keeping
   the co-occurrence info the categorical test discards. Measured effect on the
   dead groups:

   | group | categorical-sig | position-sig | co-present n/cohort |
   |---|--:|--:|--:|
   | S-M1 | 0 | 6 | 21 |
   | S-M2 | 0 | 6 | 21 |
   | S-M3 | 0 | 6 | 21 |
   | F-M3 | 0 | 2 | 43 |

   Takes them from degenerate (constant answer) to live. Already implemented in
   `core/positions.py`.
3. **Lower the sequence significance n-gate 10 → 5** (§5) — recovers 114 cores.

**Needs a design call:**
4. **Vaccine-agnostic scope variant** for single-vaccine sequence/first → pools
   all 3,166 reports, doubles n (~6 → 12), ~46% of triples become significant.
   Changes the claim scope ("across all vaccines").
5. **Coarsen event granularity to symptom categories (MedDRA SOC/HLGT)** for the
   multi groups → pools many rare specific triples into one well-powered
   category triple. Highest ceiling for the multi tier; needs a term→category
   map. This is the real structural fix if "6 significant cores" is not enough.

**Fallback:** curate-for-power (top-n highest-n cores) or drop/merge the
still-degenerate groups (S-M*, F-M3).

---

## 7. Conceptual clarifications (for reference)

- **Point estimate vs significance.** A rate of 0.63 at n = 46 is on the
  "supported" side of 0.5 (so gold = supported) but its 95% CI still includes
  0.50 (p = 0.10) — the sample is too small to rule out a coin flip. "Above 0.5"
  ≠ "significantly above 0.5." This is the whole reason for the 78.5% fail rate.
- **Reversing a failing core does NOT rescue it** *(as of the two-sided regime;
  see the 2026-07-13 update below).* Our tests are two-sided /
  relabel-invariant, so the p-value is a property of the DATA, not the claim
  direction: 29/46 and 17/46 both give p = 0.104; Fisher is identical under
  cohort/event swap. Reversing flips supported↔refuted but leaves p unchanged.

  > **Update (2026-07-13): directional tests are now one-sided.** The directional
  > binomial and `multi_dir_*` Fisher tests run one-sided in the observed
  > direction, so the p-value IS direction-aware: 29/46 gives p ~ 0.052 for
  > "greater" and ~0.96 for "less". This does not "rescue by reversing" (the
  > reverse direction now correctly fails) but it does halve the tail for
  > effects already on the supported side, lifting successful pairs +23.5%
  > (1,976 -> 2,441). The `multi_differ_*` and omnibus tests stay two-sided.
  > See `decisions.md`, "One-sided directional tests for the significance
  > verdict".
  (The 67 that appear to flip are all S-V1 + F-V3 chance-null artifacts —
  "significantly BELOW chance" = a significant *refuted*, not a rescued
  supported.) Reversal is a **generation** tool for refuted items from
  already-significant cores, not a rescue tool.
- **Null hypothesis** = the chance / no-effect baseline you try to reject, not
  the reverse of the claim (§4).

---

## 8. Report / code changes made this session

All in `scripts/make_examples.py` (+ `scripts/make_findings_tex.py`), regenerated
into `docs/reference/Worked_Examples.md` and `Findings_and_Templates.tex`:

- **Successful-example picker** — each template showcases a *successful* core
  (definite gold the test corroborates) when one exists, falling back to a
  failed example only when none does. Flagged templates dropped 11 → 4.
- **All-register worked examples** — every example renders the filled question +
  claim in all four registers (Original/Research/Media/Clinical), so it is
  self-contained (no need to cross-reference the catalogue).
- **Gold-vs-significance fail-rate section** — overall, per-family, per-template,
  with each presented example marked successful / failed / n-a.
- **Fail-case examples per template** — ≥10 failing cores per testable group,
  laddered by p from closest-to-significant to no-effect, each with k/n, p, and
  a "why it failed" reason (weak effect / small gap / small cohorts / n-gate).
- **n-gate attribution** — fail reasons distinguish the significance min-n gate
  (p<0.05 but n<10) from genuine weak effects.
- **Null hypothesis per template** — H0 shown under the categorical test, the
  position test, and each fail-case header.
- **Position-based tests + p-value method details** — Wilcoxon / Mann-Whitney /
  Friedman / Kendall's W (`core/positions.py`), each with a "how p is computed"
  line, computed alongside the categorical test.
- **Modal-ordering fix** — seq_bool / prop_sequence compute on the modal ordering
  they name (k, p-value, claim all agree).

---

## 9. Open decisions & next step

> **Update (2026-08-04):** the labeler is built (`core/verdict.py`), and the
> go/no-go artifact below now exists as `data/pilot/verdict_labels.md`. Headline:
> **587 decisive cores across all 27 groups**, and **12 groups at S = 0** — six
> of them the multi groups the 2026-07-28 roster decision already retires, plus
> S-V3/S-V4/F-V1/F-V2 (non-directional) and S-M2/F-M3 (genuinely underpowered).
> Live groups and their ~1.5·S budgets: C-V1/C-V3 266 each, P-V1/P-V3 130 each,
> C-M2 34, P-M2 27, F-V3 21, S-V1 6.

**Open:**
- not-significant → `insufficient` (recommended) or `refuted`.
  *(RESOLVED 2026-07-28: `insufficient`. Implemented 2026-08-04.)*
- Exact reworded claim strings per register for the sequence/first BOOL groups.
- Lower the sequence significance n-gate 10 → 5? (recovers 114 cores).
- Fate of the zero-supported groups (S-M1/2/3, F-M3): position-test driver +
  categories, or drop/merge.

---

## 10. S-M2 is not gate-starved, it is power-dead (2026-08-04)

S-M2 (`multi_dir_sequence`: "A→B→C is more common after {v1} than after {v2}")
returns S = 0 at **every** floor from 5 to 40. Measured over all 90 computable
cores:

| | value |
|---|---|
| cores, computable / enumerated | 90 / 387 |
| n per cohort (min/median/max) | v1 5 / **6** / 13 · v2 5 / **9.5** / 28 |
| **best directional p across all 90 cores** | **0.0580** |
| cores with p < 0.10 | 3 |
| cores with p < 0.20 | 6 |
| cores where perfect separation could not reach 0.05 | 0 / 90 |

The last row matters: this is **not** a combinatorial impossibility (a
hypothetical 6/6-vs-0/8 split would give p ≈ 0.0002). The corpus simply never
produces separation that clean at n ≈ 6. Nor is it the min-n gate — the sequence
floor is 5 and these cores sit at n = 5–13. Nor is it alpha: the single best core
misses at 0.058, and moving alpha to catch one core is not a design.

The cause is the §2 funnel at its narrowest: conditioning on *this exact triple*
× *strict order* × *this vaccine* leaves ~6 reports per cohort, and a two-cohort
Fisher test on 6-vs-9 cannot resolve anything short of near-perfect separation.

**Position-test alternative (the §6 lever 2):** Mann-Whitney on the focal event's
within-triple rank runs on all co-present reports (median n = **21**, not 6) and
yields **6 / 90 decisive** — live, but still starved, and it changes the claim
from an ordering-frequency claim to a rank claim ("A tends to occur earlier
after {v1} than after {v2}").

**Contrast with F-M3**, the other kept-but-S=0 multi group: F-M3 has 19 decisive
cores at floor 10 and 5 at floor 20 — it dies at the first/last floor of 30, so
it is a *floor* casualty and the floor decision can revive it. S-M2 cannot be
revived by any floor.

**Consequence if S-M2 goes:** the sequence family loses its entire multi tier
(S-M1/S-M2/S-M3 all gone) and the whole cohort-level sequence supply reduces to
S-V1's 4 decisive cores, with S-V3/S-V4 non-directional. The sequence tier as a
whole is the finding here, not just S-M2.

---

**Recommended next step:** lock the not-significant mapping, then **prototype the
full significance-as-verdict labeling** (folding in the reworded chance-nulls,
the position-test verdict driver for sequence/multi, and the n-gate lowered to
5) and emit the resulting **per-group supported / refuted / insufficient
distribution**. That table is the go/no-go artifact — it turns the design into
"here is exactly what each template would ship" — before scaling past the pilot.
