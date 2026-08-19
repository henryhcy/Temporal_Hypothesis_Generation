# Template-Family Expansion — limitations of the current benchmark, and what can replace them

Branch `template-family-expansion`, 2026-08-14. Companion to
`08_multi_tier_inventory.md`, which screened *replacements inside* the two-cohort
tier; this doc steps back and asks what the benchmark cannot express **at all**.

Reproduce: `scripts/run_family_inventory.py --rounds 2000 --floor 10`
Candidate templates: `data/templates/candidates/*.yaml` (6 families, 30 groups,
120 register variants). Nothing here is in the shipping roster.

---

## 1. The box the benchmark currently lives in

23 shipped groups, and every one is a cell in this grid:

| | precedes | co-occurs | sequence (A<B<C) | first/last-of-set |
|---|---|---|---|---|
| **report** | P-R1, P-R2 | C-R1 | S-R1 | F-R1, F-R2, F-R3 |
| **one vaccine cohort** | P-V1, P-V3 | C-V1, C-V3 | S-V1, S-V3 | F-V1, F-V2, F-V3 |
| **two vaccine cohorts** | P-M1, P-M2 | C-M1 | S-M1, S-M3 | F-M1, F-M2 |

Four primitives, three scopes, two answer types (BOOL / CHOICE), four registers.
That is the whole expressive range. The nine limitations below are what the grid
cannot say — each one is a claim a clinical researcher would plausibly make and
the benchmark cannot currently pose.

---

## 2. Limitations, in order of how much they cost

### L1. Every cohort-level claim conditions on TWO OR MORE named events co-occurring
This is the structural one, and it is upstream of most of the starved-tier
problems. `precedes` needs A and B at distinct stages; `co_occurs` needs both
present; `sequence` needs three at distinct stages; `first/last` needs every
candidate present. So the benchmark cannot ask **"is this an early symptom or a
late one?"** — the simplest temporal question about a single event.

The cost is measured, over the 176-term / 1,139-pair universe at pooled scope:

| denominator | median | Q1 | Q3 | max |
|---|--:|--:|--:|--:|
| one event (reports containing A) | **45** | 28 | 103 | 1,063 |
| one pair (reports ordering A and B) | **12** | 9 | 21 | 237 |

3.8× at the median. The sharper way to read the second row: **the median pair core
sits 2 above the min-n floor of 10, and the lower quartile sits below it.** Half
the benchmark's evidence base is within a couple of reports of being discarded,
which is why floors, ties and power dominate every design discussion in
`07_significance_findings.md`. Single-event conditioning is the only lever that
moves that number without changing the corpus.

### L2. `precedes` is distance-blind, by explicit design
`corpus.sequence_fraction` documents it: *"Gaps are fine: a<b<d<e<c still counts
as a<b<c."* So A at stage 0 with B at stage 1 and A at stage 0 with B at stage 5
are recorded as the same relation. **"The rash followed the fever immediately"**
is not expressible, though the annotation carries everything needed to decide it.
`corpus.pair_distances` computes gaps already — and is consumed only by the
retired rank diagnostics.

### L3. The whole benchmark has only TWO nulls, and both are predictable from the answer type
Every cohort claim tests against 0.5 or against modal-vs-runner-up. A solver can
therefore choose the null from `answer_type` **without reading the claim**: BOOL →
0.5, CHOICE → runner-up cell. Nothing requires reading a quantitative bar out of
the hypothesis text, and nothing requires *deriving* a null from the data's own
geometry. For a benchmark whose stated capability is "translate a natural-language
hypothesis into the correct statistical procedure", that is the single biggest
shortcut available.

### L4. There are only two contrast shapes, and one of them is nearly dead
Either a proportion is compared to chance (V tier) or the same proportion is
compared across two vaccine cohorts (M tier). The M tier is down to **one group**.
The obvious third shape — two *different* proportions inside one cohort ("does A
precede B more often than C precedes D") — is menu items R1/R2/R3 from 07-13, was
**adopted in the 07-28 roster decision as P-V4 and P-V2**, and has never been
coded or measured. It gets a two-sample contrast without splitting the corpus, so
each arm keeps its full denominator.

### L5. A cohort can only be a vaccine brand
`age_yrs` and `sex` are present for all 3,166 reports in
`data/VAERS_Sampled_Data_v4.csv` and were dropped at DB build; the schema is
`reports(vaers_id, vaccine, narrative, num_groups)`. So "does this pattern differ
by age?" — a first-instinct research question — was never even available to
consider. (Measured below. It fails, and the failure is informative.)

### L6. The timeline's own shape is never a claim target
Reports carry 2–14 distinct stages (934 have exactly 2, 985 have 3, one has 14).
Nothing in the benchmark asks whether an event belongs to short courses or long
ones, though it is a temporal property of the event and needs no second event.

### L7. "Do A and B co-occur at all" is missing
`co_occurs` means *recorded at the same stage*, conditioned on both already being
present. The plainer question — do these two events show up in the same report
more than their separate rates predict — is menu item R5, adopted as C-V2, still
owed by the migration.

### L8. Every statistic is a proportion
With the rank track retired (§6 lever 2, anti-conservative normal approximation),
nothing in the benchmark tests a distribution, a count or a spread. That is a
defensible v1 scope, but it means "how much earlier" is unaskable — only "earlier
or not".

### L9. Answer-format twins are already duplicating cores, and new families would multiply it
Four shipped pairs compute the identical statistic on identical cores (issue 14:
P-V1/P-V3, C-V1/C-V3, S-V1/S-V3, F-V1/F-V3 — 100% overlap each). Any new family
with a BOOL and a CHOICE variant adds more, and `core_id` embeds `group_id`, so a
split keyed on `derived_from_core_id` puts the same fact on both sides.
**Consequence for this proposal: the candidate families below must not be adopted
before issue 14's group-independent `fact_id` exists.**

---

## 3. Method

Six candidate families, each measured against a permutation null, with **shipped
groups included as controls**. The controls are the reason the rest of the table
can be trusted: a null model that mis-scored P-V1 or P-M2 would invalidate every
candidate beside it.

**Three null models, because the families need different ones.** Getting this
wrong is not a subtlety — it silently produces a null identical to the real data:

| null | what it permutes | what it preserves | for |
|---|---|---|---|
| **level shuffle** | which term sits at which occupied stage, inside each report | report size, the multiset of stage sizes, term frequencies, every co-occurrence | order and position families |
| **label shuffle** | the cohort label on each report | cohort sizes, all timelines | cohort-contrast families |
| **edge swap** | which report contains which term (degree-preserving double swap) | report size AND term prevalence exactly | presence families |

The edge swap is not optional pedantry. Burden and association depend only on
presence, which the level shuffle never touches, so under a level-shuffle null
burden returned **3,881 decisive cores against a null mean of 3,881.0** — the null
and the real corpus were identical by construction. Under the edge swap the same
family reports 691 of 1,770 against a null mean of 132.1.

**`p_perm` is reported twice**, and the pair matters:

- `p_dec` — rounds whose **decisive** count (supported + refuted) matched or beat real
- `p_sup` — rounds whose **supported** count matched or beat real

For a symmetric 0.5 null the two agree. For a **threshold** null they diverge
violently, and the divergence is itself the finding: data sitting at the 0.5
chance rate is significantly *below* a 2/3 bar as soon as n is moderate, so
`refuted` becomes free and only `p_sup` measures signal. Reading `p_dec` on a
threshold family would endorse a group whose refuted labels are pure sample size.

**Scopes.** Single-cohort families are measured twice: `ALL` pools every report
(this is §6 lever 4, the vaccine-agnostic scope) and `VACCINE` sums the three
per-cohort scopes, which is what the shipped V groups actually ask. The gap
between the two rows is the price the benchmark pays for naming a vaccine in the
claim.

**Universe.** Terms need ≥ 20 reports in scope; pairs need co-occurrence ≥ 10.
Cores are keyed on presence, which is invariant under the level shuffle, so real
and null count the same cores. The two-proportion families are capped at the top
40 pairs / top 60 terms by denominator — the full universe is O(pairs²), so those
decisive counts are **a floor on supply, not a census**, and the cap is stated
rather than silently applied.

---

## 4. Results

2,000 rounds, floor 10, alpha 0.05 per side. `p` values of 0.000 mean **no
shuffled round matched the real count** (the floor at 2,000 rounds is
1/2001 = 0.0005). Presence families ran 500 rounds — the edge swap costs ~4× a
level shuffle — and that is marked.

### 4.1 Controls — the null models are validated before anything else is read

| control | real | null mean | p_dec | expected | |
|---|--:|--:|--:|---|---|
| P-M2 vaccine precedes (shipped) | 30/322 | 18.7 | **0.023** | 0.023 in `08_multi_tier_inventory.md` | **exact match** |
| C-M2 vaccine co-occurs (dropped 08-11) | 42/579 | 35.7 | 0.221 | fails, 0.195–0.202 | reproduces |
| M-H vaccine position (rejected 08-11) | see 4.4 | | | fails, 0.120 | reproduces |
| P-V1 precedes vs 0.5 (shipped) | 316/766 | 47.4 | 0.000 | strong | as expected |

P-M2 landing on 0.023 to three decimals, from an independently written harness and
a differently-built universe, is the single best evidence that the numbers below
mean what they say.

### 4.2 Single-cohort families — pooled scope and per-vaccine scope

`sup` / `ref` are supported and refuted core counts. Read **p_sup** for threshold
families; read either for the rest.

| family | scope | sup | ref | decisive/cores | null mean | p_dec | p_sup |
|---|---|--:|--:|--:|--:|--:|--:|
| **N2 immediate succession** | ALL | 66 | 69 | **135/391** | 23.6 | **0.000** | **0.000** |
| | VACCINE | 40 | 38 | 78/252 | 15.9 | 0.000 | 0.000 |
| **N3 adjacency vs chance 2/L** | ALL | 53 | 22 | **75/766** | 29.2 | **0.000** | **0.000** |
| | VACCINE | 40 | 11 | 51/574 | 21.3 | 0.000 | 0.000 |
| **N1 position vs 0.5** *(biased — see 4.3)* | ALL | 37 | 31 | 68/176 | **26.7** | 0.000 | 0.001 |
| | VACCINE | 70 | 7 | 77/202 | 28.0 | 0.000 | 0.000 |
| N4 dominance ≥ 2/3 | ALL | **38** | 356 | 394/766 | 310.0 | 0.000 | 0.000 |
| | VACCINE | 23 | 258 | 281/574 | 221.0 | 0.000 | 0.000 |
| N4b dominance ≥ 3/4 | ALL | **18** | 447 | 465/766 | 503.7 | **0.997** | 0.000 |
| | VACCINE | 8 | 326 | 334/574 | 373.3 | **0.998** | 0.000 |
| **R1 pair-vs-pair** | ALL | 200 | 111 | **311/502** | 39.4 | **0.000** | **0.000** |
| | VACCINE | 341 | 344 | **685/1541** | 101.0 | 0.000 | 0.000 |
| **R3 conditional antecedent** | ALL | 94 | 57 | **151/278** | 19.8 | **0.000** | **0.000** |
| | VACCINE | 169 | 156 | 325/799 | 45.0 | 0.000 | 0.000 |
| R2 event-vs-event first rate | ALL | 367 | 449 | 816/1770 | 228.0 | 0.000 | 0.000 |
| | VACCINE | 774 | 882 | 1656/5310 | 407.5 | 0.000 | 0.000 |

Presence families, 500 rounds, edge-swap null:

| family | sup | ref | decisive/cores | null mean | p_dec |
|---|--:|--:|--:|--:|--:|
| **R5 presence association** | 1254 | 452 | **1706/8462** | 685.2 | **0.002** |
| **N5 timeline burden** | 409 | 282 | **691/1770** | 132.1 | **0.002** |

Three things worth reading off this table:

**The threshold family is valid but structurally lopsided.** At ≥ 2/3 it produces
38 supported against 356 refuted; at ≥ 3/4, 18 against 447. And `p_dec` at ≥ 3/4 is
**0.997** — shuffled timelines produce MORE decisive cores than the real corpus,
because refutation there is driven by sample size rather than by signal. `p_sup` is
0.000 in both cases, so real support exists; the family is usable only if the
sampler is built to hunt for it. Equal thirds would cap ≥ 2/3 at ~114 items.

**Naming a vaccine is not always the expensive choice.** R1 and R3 both get MORE
decisive cores at per-vaccine scope than pooled (685 vs 311, 325 vs 151) because
three cohorts supply three independent core universes. Pooling helps the
denominator, splitting helps the core count, and which wins is family-specific — not
a general argument for lever 4.

**N3 and N1(VACCINE) are strongly one-sided** (53/22 and 70/7). For N3 that is
expected and fine: real timelines cluster related events together, so adjacency
genuinely exceeds chance more often than it falls short. It still means the refuted
third has to be sought deliberately.

### 4.3 The position family's null is NOT 0.5 — measured, and it changes the answer

The first draft of the position family tested against 0.5 on a symmetry argument:
each of a report's L stage-ranks is equally likely, so early and late balance out.
**That argument is wrong, because stages are not equally populated.** Measured mean
stage sizes: 2.45 terms at rank 0, 2.21 at rank 1, 1.84 at rank 2, ~1.74 from rank
3 on. Earlier stages hold more events, so a term drawn at random from a report's
slots is more likely to be early, and the corpus-wide structural early rate is
**0.5327**.

The consequence is not extra noise, it is manufactured support:

| null used | decisive/cores | supported | refuted | permutation null mean | null as % of cores |
|---|--:|--:|--:|--:|--:|
| 0.5 (naive) | 68/176 | 37 | 31 | 26.7 | **15.2%** |
| per-core structural rate | 59/176 | 22 | 37 | **9.3** | **5.3%** |

A permutation null mean of 15.2% of cores against a nominal alpha of 5% is the
tell — a correctly specified null puts it at alpha. Full corrected numbers in 4.5.

**Pair-order claims are not affected.** For `precedes`, swapping A and B is a
symmetry of the same shuffle, so its 0.5 null is exact — which is why P-V1's control
row behaves and why this bias had never surfaced before. The bias is specific to
claims about ONE event's position, i.e. exactly the new family.

### 4.4 Stratified cohorts (age, sex) — REJECTED, and the failure is informative

| shape | real | null mean | p_dec | p_sup |
|---|--:|--:|--:|--:|
| X1 age-band precedes (<50 vs ≥50) | 14/211 | 11.2 | 0.239 | 0.473 |
| X2 age-band co-occurs | 25/373 | 20.0 | 0.160 | 0.974 |
| X3 sex precedes (F vs M) | 10/118 | 7.3 | 0.218 | 0.857 |
| X4 sex co-occurs | 7/219 | 13.7 | 0.979 | 0.997 |
| X5 age-quartile precedes (≤35 vs ≥63) | 5/59 | 3.8 | 0.341 | 0.313 |
| X6 age-band position | 17/124 | 7.4 | **0.003** | 0.877 |
| X7 sex position | 5/101 | 6.0 | 0.732 | 0.358 |

Not one shape survives. X4 lands **below** chance (7 real against 13.7 expected),
the conservative-Fisher signature that retired M-D and M-I. X6 is the one that looks
like it clears, at p_dec 0.003 — and §4.5 shows why it does not: its null model
cannot absorb the report-geometry difference between age bands, which is the same
size as the effects being called significant.

**This refutes the stated diagnosis of the two-cohort tier's weakness.** The
recorded explanation has been cohort SIZE — ~1,000-report vaccine cohorts leaving
n ≈ 10–30 a side. But age at the median splits 1,501 / 1,536, each band *larger*
than any vaccine cohort, and needs one comparison per pair where vaccine needs
three (removing the core dependence that inflates the vaccine null). It yields 211
cores against vaccine's 322-over-three-comparisons — roughly double per comparison —
and still finds nothing.

So the two-cohort tier is not thin because the cohorts are small. It is thin
because **symptom order barely varies across patient strata at all**. Two
consequences:

- **P-M2's pass is a stronger result than it looked.** It is not the lucky survivor
  of a power problem; it is a real cohort effect in a corpus where the other
  obvious stratifications produce nothing.
- **"Split on something else" is closed off as a rescue route for issue 1.** That
  option can be struck from the open question rather than left hanging.

### 4.5 Supplementary run — corrected position null and the remaining strata

Same seed, same universe, 2,000 rounds (`data/pilot/family_inventory_2000b.log`).

**The corrected position null, at both scopes:**

| scope | null used | sup | ref | decisive/cores | null mean | null as % of cores | p |
|---|---|--:|--:|--:|--:|--:|--:|
| ALL | 0.5 (naive) | 37 | 31 | 68/176 | 26.7 | **15.2%** | 0.001 |
| ALL | **structural** | 22 | 37 | **59/176** | **9.3** | **5.3%** | **0.000** |
| VACCINE | 0.5 (naive) | 70 | 7 | 77/202 | 28.0 | **13.9%** | 0.000 |
| VACCINE | **structural** | 47 | 11 | **58/202** | **10.3** | **5.1%** | **0.000** |

At both scopes the corrected null puts the permutation null mean at **5.1–5.3% of
cores**, i.e. exactly the nominal alpha, which is what a correctly specified null
looks like. The naive version sat at 14–15%, nearly three times alpha. The family
survives the correction with 58–59 decisive cores and now beats its null by 5.6–6.3×
instead of 2.5×, so the correction *strengthens* the evidence while removing the
inflation.

The supported/refuted split differs between scopes (22/37 pooled, 47/11 per-vaccine)
because the two scopes do not contain the same cores: the per-vaccine universe
requires 20 reports *within* a cohort, which selects the most common terms, and
common terms are disproportionately onset events. Not a contradiction, but a reason
to fix the scope before quoting a balance figure.

**The remaining stratified shapes — and one that looked like it passed:**

| shape | sup | ref | decisive/cores | null mean | p_dec | p_sup |
|---|--:|--:|--:|--:|--:|--:|
| X5 age-quartile precedes (≤35 vs ≥63) | 3 | 2 | 5/59 | 3.8 | 0.341 | 0.313 |
| X6 age-band position | 2 | 15 | 17/124 | 7.4 | **0.003** | 0.877 |
| X7 sex position | 4 | 1 | 5/101 | 6.0 | 0.732 | 0.358 |
| [ctl] M-H vaccine position (rejected 08-11) | 12 | 10 | 22/289 | 16.4 | 0.137 | 0.156 |

The control reproduces its documented failure (0.137 here against 0.120 on 08-11).

**X6 appears to clear at p_dec 0.003 and must still be rejected.** Because a
two-cohort contrast is orientable, `p_dec` is the right statistic for it — so this
is not a threshold-family misreading. The problem is the null model, and it is worth
recording precisely because the trap generalises:

The statistic compares each band's early-rate with a Fisher 2×2, but the two bands
have different **report geometry**, and position is geometry-sensitive (§4.3). The
per-core structural early-rate gap between bands is median **3.5pp**, Q3 6.0pp, max
12.8pp, and **37 of the 124 cores have a geometry gap alone above 5pp** — the same
magnitude as the effects a Fisher test calls significant at these n. The label
shuffle cannot absorb any of it: shuffling assigns each report to a random band, so
every null round has ~zero geometry gap while the real data has a systematic one.
The null is therefore too permissive by construction, and the 15 refuted cores are
consistent with the aggregate structural rates (0.5269 for <50 against 0.5356 for
≥50) rather than with any temporal effect.

The fix is the same one T-V3 and K-V5 need: test each arm against its OWN structural
rate and compare the deviations, not the raw rates. Until that exists, **any
cross-cohort comparison of a single-event position is invalid**, which covers X6, X7
and M-H alike. It does not affect the pair-order contrasts (X1, X3, X5, P-M2),
because precedes is exactly symmetric under the shuffle.

### 4.6 Two aspects checked and NOT pursued

- **Recurrence** (a term recorded at more than one stage). `CorpusIndex` collapses
  these by the first-mention rule, so it looked like discarded information. It is
  not: **7 of 22,674 report-term pairs, 0.03%.** No supply, no family. Worth
  recording because it also confirms the first-mention rule throws nothing away.
- **Stage width** ("is A usually recorded alone at its stage?"). Supply exists (176
  terms at n ≥ 20) but the median solo-stage rate is **0.22**, so a 0.5 null would
  refute nearly everywhere, and the honest null is geometry-dependent like N1's.
  Identified, **not screened** — low priority, and listed here so the gap is not
  mistaken for coverage.

---

## 5. Can a model actually finish these? — solvability and implementation cost

The constraint on this whole exercise is that a hypothesis has to be **answerable
by the eventual framework**: mechanically computable from the annotated leveled
orders, with an exact test the model itself can run. That rules a family out
faster than a weak `p_perm` does. Complexity is also capped deliberately — nothing
here goes past three named events, and nothing crosses three cohorts.

| family | events | new corpus helper | new test | touches a LOCKED interface? |
|---|--:|---|---|---|
| position | 1–2 | `early_half_fraction` (rank-based) | none — binomial vs 0.5 | no |
| proximity / direction | 2 | `adjacent_direction_fraction` | none — binomial vs 0.5 | no |
| proximity / rate | 2 | `adjacency_rate` + per-report 2/L accumulation | binomial vs a **per-core** null | **yes** — see below |
| threshold | 2–3 | none, reuses `precedes_fraction` etc. | binomial vs 2/3, 3/4, 1/3 | **yes** — see below |
| comparative | 2–4 | none, reuses the pair counters | none — Fisher 2×2, already shipped | no (reuses `gold_n2`/`gold_k2`) |
| association | 2–3 | `presence_table`, `burden_fraction` | none — Fisher 2×2 | no |
| stratified | 1–2 | none | none | **yes** — DB schema and model input |

**The locked interface at issue is `core/answers.py::_null_ref`.** It takes a
`mode` argument and returns a hardcoded `0.5`, with a docstring recording the
2026-08-11 decision that fixed exactly this: the argmax modes used to be scored
against retired GOF references, so their p-value and effect size answered
different questions. Two candidate families need that constant to vary again:

- **threshold** needs a per-MODE constant (2/3, 3/4, 1/3). Cheap and safe — the
  signature already takes `mode`, and the value is fixed by the template text, so
  the claim and the test stay aligned by construction.
- **adjacency-rate** needs a per-CORE value (the mean of 2/L over that core's
  reports), which the current signature cannot express. This is the one candidate
  that would require widening a locked interface to `_null_ref(mode, core)`.

Neither is a reason to reject a family, but both are reasons to re-run
`validate_gold.py` invariant family D (direction) and the effect-size check
afterwards: a varying null is precisely the condition under which p-value and
effect size drift apart, and that drift has already happened twice in this
project.

**Stratified is the expensive one** even though the statistics are trivial: the
cohort covariates would have to enter the DB schema *and* the model's input, since
a claim about patients under 50 is unanswerable from timelines that do not carry
an age. It failed its null, so this cost is moot — but it is the reason not to
adopt it "just in case".

---

## 6. Which families suit an auto-research setting

"Auto-research style" means an agent poses a hypothesis and has to work out how to
test it. A family earns a slot only if it survives all five of these — the first
two are hard gates, the last three are trade-offs:

1. **Signal** — clears its permutation null on `p_sup`.
2. **Solvable** — exact, deterministic, runnable by the model from annotations alone.
3. **Balance** — both verdicts reachable in useful numbers, so the label is not
   predictable from the wording.
4. **Supply** — decisive cores worth the engineering.
5. **New capability** — probes something the shipped grid cannot.

| family | signal | solvable | balance | supply | new capability | verdict |
|---|---|---|---|--:|---|---|
| **R1/R3 comparative** | 0.000 | yes, Fisher already shipped | **341/344, 169/156** | **685 + 325** | two denominators in one claim | **ADOPT FIRST** |
| **N2 immediate succession** | 0.000 | yes, binomial vs exact 0.5 | **66/69** | 135 / 78 | distance-aware relation; stricter denominator | **ADOPT** |
| **N1 position** (structural null) | 0.000 | yes, but null must be derived | 22/37 corrected | 176 / 202 | single-event conditioning — fixes L1 | **ADOPT** with the corrected null |
| **N4 threshold ≥ 2/3** | p_sup 0.000 | yes, null read from text | **38/356 — poor** | 38 supported | the null is IN THE CLAIM — the only such family | **ADOPT NARROWLY** |
| **N3 adjacency vs chance** | 0.000 | yes, null derived per core | 53/22 | 75 / 51 | null derived from data geometry | **ADOPT for capability** |
| **R5 presence association** | 0.002 | yes, Fisher on marginals | 1254/452 | **1706** | association vs independence | **ADOPT** (already owed as C-V2) |
| N5 timeline burden | 0.002 | yes | 409/282 | 691 | timeline shape as a target | optional — widens scope beyond order |
| R2 / T-V3 event-vs-event | 0.000 | yes | 774/882 | 1656 | compares events that never co-occur | **HOLD** — geometry confound, quantified in §4.5 (37 of 124 comparable cores carry a >5pp structural gap) |
| N4b threshold ≥ 3/4 | p_dec **0.997** | yes | 18/447 | 18 | none beyond ≥ 2/3 | **REJECT** |
| Stratified age/sex | all fail | yes | — | ~0 | patient-strata cohorts | **REJECT** (§4.4) |
| Recurrence | — | — | — | **7 pairs** | — | **REJECT** — no supply |

Two families deserve emphasis for the auto-research framing specifically, because
they attack the shortcut in L3 rather than just adding supply:

- **N4 threshold** is the only family in the benchmark where the null lives in the
  hypothesis TEXT. Everywhere else a solver can read the null off `answer_type`.
  Its supply is poor and its balance is bad, but 38 supported cores of a shape no
  other group has is worth more diagnostically than 400 more cores of precedes.
- **N3 adjacency** is the only family where the null must be DERIVED from the
  conditioned reports (the mean of 2/L). A solver that assumes 0.5 gets a
  systematically wrong answer, and that error is currently unmeasurable.

Both are cheap to include and neither should carry much of the dataset's mass.

---

## 7. Recommendation

### 7.1 One prerequisite, before any of this ships

**Issue 14's group-independent `fact_id` has to land first.** Every family here has
a BOOL and a CHOICE variant computing the same statistic on the same cores, which is
exactly the twin duplication already affecting four shipped pairs. `core_id` embeds
`group_id`, so a split keyed on `derived_from_core_id` would put the same fact on
both sides — and adopting six families before fixing it multiplies the leak rather
than causing it. This is a sequencing constraint, not an objection.

### 7.2 Adopt in this order

1. **R1 + R3 (comparative)** — highest supply (685 + 325 decisive at per-vaccine
   scope), balanced verdicts, no new test code, and **already owed**: they are
   P-V4 and P-V2 in the 07-28 roster decision, which issue 2 has been waiting on
   with unmeasured supply estimates. This measurement replaces those estimates.
2. **N2 immediate succession** — the cleanest new primitive. Exact 0.5 null,
   balanced 66/69, and it closes L2, the one limitation that is a documented design
   choice rather than an oversight.
3. **N1 position, with the structural null** — the only lever that raises the
   denominator without touching the corpus (L1). Requires widening `_null_ref` to
   take the core.
4. **R5 presence association** — owed as C-V2, largest supply of all, no new test.
   Note it is not a temporal claim.
5. **N4 at ≥ 2/3 only, and N3** — small, deliberately. These two exist to remove the
   null-choice shortcut (L3), not to carry mass. Drop ≥ 3/4.

Hold R2/T-V3 pending the geometry confound. Treat N5 burden as a scope decision for
the advisor, not a supply decision. Strike stratified cohorts.

### 7.3 What this changes about issue 1 (the one-group multi tier)

Issue 1 has been framed as three options: ship P-M2 alone, swap it for M-F, or
retire the two-cohort tier. **There is now a fourth**, and it is better than the
other three:

> Keep P-M2 as the two-cohort tier, and put the benchmark's two-sample capability in
> the **within-cohort comparative family** instead.

The reasoning is measured, not aesthetic. What the M tier is *for* is testing
whether a model can compare two proportions. It does that badly — one surviving
group, 30 decisive cores — because splitting a 3,166-report corpus into cohorts
starves both arms. R1/R3 test the same capability with both arms at full
denominator, and deliver 685 + 325 decisive cores. And §4.4 shows the starvation is
not fixable by choosing a better split, because patient strata carry no order signal
at all.

So P-M2 stops being a tier that has to justify its own existence and becomes what it
actually is: one interesting claim about vaccine brands, sitting beside a
well-powered two-sample family that does the pedagogical work.

### 7.4 What this does NOT resolve

- **Issue 9 (sequence cohort tier, S = 8)** is untouched. Nothing screened here
  conditions on three events at distinct stages, so the sequence family gains no
  supply. Issue 16 (exact rank tests) is still its only live lever.
- **Issue 13 (C-V3 argmax vs majority)** is unaffected and still the only defect
  putting wrong labels in generated data.
- **Issue 16** remains upstream of issue 9. Note the position family arrives at the
  same conclusion from a different direction: single-event conditioning is where the
  denominator is, and the rank track's appeal was the same thing.
- Every count here is subject to the standing caveat that group-level validity is
  not per-core validity. A family clearing its null still contains alpha-rate false
  positives, and the two-proportion families additionally contain the geometry
  artefacts described in §4.3.
