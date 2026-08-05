# Open Questions

Items still under discussion. Do not assume answers in code; surface gaps
when implementing.

When an item is resolved, move it to `decisions.md` with the date and
delete it from this file.

---

## Dataset

### First/last tie handling for CHOICE
Currently tie-reports are excluded from per-candidate counts. Question:
should CHOICE instances on ties be marked `insufficient` (single-valued
gold), or accept any tied option as supported (set-valued gold)?
**Current working assumption**: `insufficient` for clean single-valued gold.
Not yet locked.

### Synonym table contents
The manual synonym table for `{A}`/`{B}`/`{C}` slot-filling has not yet
been built. Open: how many synonyms per term type, source vocabulary
(UMLS, MeSH, manual), and validation process.

### Coverage of multi-vaccine pairs
With only three vaccine pairs, the multi-vaccine tier may be statistically
thin for some symptom pairs. Open: minimum cohort size in each pair before
generating multi-vaccine instances. Currently uses the general n ≥ 10
threshold, but may need tightening for "differ" verdicts.

### Verdict balance targets
RESOLVED (see `decisions.md` 2026-07-28): equal thirds (~1/3 supported,
1/3 refuted, 1/3 insufficient), capped per group by S (~1.5*S budget), with the
insufficient third spanning all sub-types (underpowered / sparse / not-locatable).
Supersedes the provisional 45/45/10.

### Disconnected components in MedTempo
Need to measure the rate. If common, the leveled-order representation
needs to handle multiple components per report. If rare (under 5%), can
mark such reports as `insufficient` for cross-component hypotheses and
proceed. Pending corpus survey.

### New group definitions for R1/R3/R5 (selection now locked)
Selection RESOLVED (see `decisions.md` 2026-07-28): adopt **R1, R3, R5** (drop
R4); remove the 6 misaligned multi groups; roster -> 24. Still open before
coding: confirm the three new groups' **IDs** (proposed P-V2=R3, C-V2=R5,
P-V4=R1), **answer types** (BOOL vs CHOICE), and the exact **four-register
wording**. R1's 4-event (A,B,C,D) slot is a new enumeration shape. R5 needs a new
corpus helper (2x2 presence x presence with marginals).

### Min-n floor: what does the family floor cost, and is it worth it? (2026-08-04)
The three-decision labeler now gates on the shared family floors (20
pairwise/co-occurs, 5 sequence, 30 first/last) instead of the retired blanket
n >= 10. Measured cost over the full corpus (`data/pilot/verdict_labels.md`,
regenerate with `scripts/run_verdict_labels.py`) -- S = decisive cores, which
caps each group's supported AND refuted classes:

| family | S@10 | S@15 | S@20 | S@25 | S@30 |
|---|--:|--:|--:|--:|--:|
| pairwise / co-occurs | 1265 | 833 | **569** | 401 | 296 |
| first / last | 93 | 57 | 39 | 24 | **14** |
| sequence | 0 | 0 | 0 | 0 | 0 |  (**4** at the locked floor of 5)

(S@5 = S@10 for pairwise and first/last: the enumeration viability floor is
already 10, so nothing exists below it there.)

The locked floors cost pairwise 55% of its decisive supply and first/last 85%.
Note the floor is a QUALITY choice, not a validity one -- the tests are exact,
so they are valid at small n; the floor decides how thin the evidence behind a
shipped question may be. Open: keep 20/30, or lower to 15 (pairwise 833,
first/last 57), or align the floor with the enumeration viability floor of 10?
The sequence floor of 5 is load-bearing and should stay: it is the only thing
keeping S-V1 non-zero (S = 4 at 5, 0 at 10).

### Non-directional groups: adopt modal-vs-runner-up for the CHOICE groups?
Deferred on 2026-07-14, now forced by the three-decision labeler: S-V3, S-V4,
F-V1, F-V2 are tested GOF-vs-uniform, which has no direction, so they can carry
no supported/refuted verdict and all sit at S = 0. Measured rescue if the
modal-vs-runner-up test (already locked for their BOOL twins S-V1/F-V3) replaced
GOF: S-V3 +4, F-V1 +14, F-V2 +21 decisive cores. S-V4 (`consistency_bool`) is
NOT rescued -- "the ordering is consistent" has no opposite direction to be
significant in, the same defect that retires the "same" multi groups. Open:
adopt for S-V3/F-V1/F-V2 (small but non-zero), and retire or reshape S-V4.

### Does the sequence family survive at cohort level? (2026-08-04)
S-M2 is REMOVED (see `decisions.md`, power-dead: best directional p = 0.058 over
all 90 cores). With S-M1 and S-M3 also going in the roster migration, the
sequence family has no multi tier at all, and its entire cohort-level supply is:

| group | mode | S |
|---|---|--:|
| S-V1 | seq_bool (modal-vs-runner-up) | **4** |
| S-V3 | modal_choice | 0 — non-directional |
| S-V4 | consistency_bool | 0 — non-directional, and unrescuable |
| S-R1 | report-level | n/a — deterministic, unaffected |

Four decisive cores cannot carry a family. Options: (a) accept sequence as a
report-level-only family; (b) apply the §6 lever 4 (vaccine-agnostic scope,
pooling all 3,166 reports, ~46% of triples become significant) at the cost of
changing the claim scope to "across all vaccines"; (c) apply §6 lever 5 (coarsen
events to MedDRA SOC/HLGT categories), the real structural fix, which needs a
term→category map. Not a detail — decide before the roster migration.

### C-M2 does not beat its own permutation null (2026-08-04)
See `08_multi_tier_inventory.md`. C-M2's 23 decisive cores sit inside the
shuffled-label distribution (mean 16.7, p95 25, **p_perm 0.129**), so its
supported/refuted labels would be largely noise. Plausible reason: whether two
symptoms land at the *same* timeline stage reflects annotation/narrative style,
not the vaccine. Open: drop C-M2, or keep it as a deliberately hard/negative
group with the caveat documented? Candidate replacements that DO clear the null:
M-F precedes-wide (26 decisive, p_perm 0.025) and M-H early-half (18, 0.035) —
the latter conditions on a single event, a new slot shape for the tier.

### Retire §6 lever 2 (position test as verdict driver)?
The permutation null shows the Mann-Whitney normal approximation is
**anti-conservative on tie-heavy ordinal data**: shuffled labels produce ~11%
decisive cores against a nominal 5%. The lever's headline (S-M1/S-M2/S-M3 going
0 → 6 significant) is 6.7% — *below* the noise rate. Rank-based candidates
M-E′ (p_perm 0.33) and M-A (0.38) collapse the same way. Open: retire the lever,
or re-run it with an EXACT Mann-Whitney before trusting any of its counts. Note
`core/positions.py` uses this same normal approximation throughout, so anything
reading its p-values as verdicts is affected.

### F-M3 is S = 0 too, but for the opposite reason — do not treat it like S-M2
F-M3 has 19 decisive cores at floor 10 and 5 at floor 20; it only reaches 0 at
the first/last floor of 30. It is a FLOOR casualty, so the min-n decision above
revives it or kills it. Of the four directional multi groups the 2026-07-28
decision keeps, only P-M2 (S = 18) and C-M2 (S = 23) are live at the locked
floors. Open: whether a two-group multi tier is enough of a tier.

## Framework

### Architecture detail
The framework reads narrative + hypothesis and returns a verdict. The
internal pipeline (decomposition, evidence localization, relation
inference, aggregation, verdict synthesis) is sketched but not specified
in detail. Pending design pass.

### CRAFT integration
Whether the framework uses CRAFT as the relation extractor for open-book
mode, or implements its own hypothesis-conditioned extractor. Not locked.

## Evaluation

### Metrics breakdown
Headline metric is verdict agreement. Secondary metrics (proportion error,
stage-wise diagnostics, register-wise breakdowns) are agreed in principle
but not specified in detail.

### Baselines
Vanilla RAG, tool-using LLM with code execution, single-pass framework
variant, deterministic upper bound. Mentioned in earlier discussion;
not formalized in plan docs yet.

### Models to evaluate
Continuity with CRAFT suggests: GPT-4.1, Claude Sonnet 4.5, Llama-3.3-70B,
MedGemma-27B. To be confirmed once experimental budget and timeline are
firm.
