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

### Min-n floor
RESOLVED (see `decisions.md` 2026-08-11): floors are **10 / 5 / 10** (pairwise,
sequence, first/last), aligning pairwise and first/last with the enumeration
viability floor. S goes 587 -> 1362 and F-M3 revives (0 -> 19).

### Per-group vs benchmark-level verdict balance (2026-08-11)
Equal thirds is locked **per group** (decisions.md 2026-07-28). The C-V1/C-V3 skew
that put this in doubt is RESOLVED by negation (decisions.md 2026-08-11): both
groups now reach 189/189 from all 378 decisive cores, ~52% negated.

Argument for keeping it per-group rather than benchmark-level: template wording is
mechanical and fixed per group, so the group is trivially identifiable from the
question text. A group shipped at 40/338 would let a model learn "text shaped like
this -> answer refuted" and score ~89% on it with no temporal reasoning.
Benchmark-level balance only closes that shortcut if group identity is hidden,
which it cannot be.

Still open, but narrower: **S-V1 and S-V3 have S = 4 each**, so 1.5*S = 6 items and
they are starved whatever the balance rule. Take them in full and flag, or drop
the sequence cohort tier (see the sequence-family question)?

### Sourcing `not_locatable` for the non-sequence families (2026-08-11)
Step B RESOLVED `sparse` (0 -> 2,722) and partly resolved `not_locatable`
(0 -> 116). See `decisions.md` 2026-08-11.

What remains: all 116 `not_locatable` cores are in the SEQUENCE groups (triples
present but always at the same level, so nothing is orderable). The pairwise,
co-occurs and first/last families have **zero** -- their enumeration pre-filters
pairs/triples to co-occurrence >= 10, which guarantees a non-empty denominator. So
the insufficient third cannot span all three sub-types within those groups, and
116 is well under the ~254 an equal-thirds insufficient class would want anyway.

Open: source it from the pilot enumeration path, which already forms ALL
combinations of the top-K terms and therefore includes pairs that never co-occur?
Or add an explicit generator that picks known non-co-occurring event pairs per
cohort? The 2026-07-28 decision requires this third to be generated deliberately
either way; the question is which mechanism.

### Non-directional CHOICE groups
RESOLVED (see `decisions.md` 2026-08-11): S-V3, F-V1 and F-V2 now use the
modal-vs-runner-up test (S +4 / +74 / +86); **S-V4 removed** outright as
unrescuable. Groups at S = 0 are now exactly the six pending roster removal.

### Does the sequence family survive at cohort level? (2026-08-04)
S-M2 is REMOVED (see `decisions.md`, power-dead: best directional p = 0.058 over
all 90 cores). With S-M1 and S-M3 also going in the roster migration, the
sequence family has no multi tier at all, and its entire cohort-level supply is:

| group | mode | S |
|---|---|--:|
| S-V1 | seq_bool (modal-vs-runner-up) | **4** |
| S-V3 | modal_choice (modal-vs-runner-up since 08-11) | **4** |
| S-R1 | report-level | n/a — deterministic, unaffected |

(S-V4 was removed on 2026-08-11.) Eight decisive cores across two groups, and
they are largely the SAME four triples asked two ways, so this is not a family. Options: (a) accept sequence as a
report-level-only family; (b) apply the §6 lever 4 (vaccine-agnostic scope,
pooling all 3,166 reports, ~46% of triples become significant) at the cost of
changing the claim scope to "across all vaccines"; (c) apply §6 lever 5 (coarsen
events to MedDRA SOC/HLGT categories), the real structural fix, which needs a
term→category map. Not a detail — decide before the roster migration.

### C-M2 does not beat its own permutation null (2026-08-04, re-confirmed 08-11)
See `08_multi_tier_inventory.md`. C-M2's decisive cores sit inside the
shuffled-label distribution at **both** floors, so this is not a supply problem
and the floor decision does not rescue it:

| floor | real decisive | null mean | p_perm |
|---|--:|--:|--:|
| 20 | 23 | 16.7 | 0.129 |
| **10** | 42 | 34.3 | **0.151** (2000 rounds) |

Lowering the floor nearly doubled its decisive count and left it *further* inside
the null — exactly what you expect if the signal is not there. Plausible reason:
whether two symptoms land at the *same* timeline stage reflects
annotation/narrative style, not the vaccine. Open: drop C-M2, or keep it as a
deliberately hard/negative group with the caveat documented? Recommendation is
drop — a group whose supported/refuted labels are mostly noise cannot carry a
gold label, and the multi tier now has P-M2 (30) and F-M3 (19) without it.

### At floor 10 there is NO viable single-event candidate (2026-08-11)
The 08 doc's replacement recommendation was computed at floor 20 and does not
survive the new floor. Re-run at floor 10 with **2000 rounds**
(`data/pilot/multi_inventory_floor10_2000rounds.json`) -- 200 rounds proved too
coarse here, see the caveat below:

| candidate | shape | p_perm @ floor 20 | p_perm @ floor 10 (2000 rds) | |
|---|---|--:|--:|---|
| P-M2 precedes-strict | pair | 0.005 | **0.025** | clears |
| M-F precedes-wide | pair | 0.025 | **0.033** | clears |
| M-C last-overall | single | 0.055 | **0.073** | fails |
| M-H early-half | single | **0.035** | **0.120** | fails |
| C-M2 co-occurs | pair | 0.129 | **0.151** | fails |
| M-B first-overall | single | 0.373 | **0.453** | noise |

**The single-event shape is dead at floor 10.** M-H, the 08 doc's recommended
"new shape", degrades to 0.120; M-C, its borderline sibling, to 0.073. Neither
can carry the tier's single-event slot. Consequence: the only validated multi
candidates are P-M2 and M-F, which are **the same claim family** (precedes) and
should not both ship -- so the validated multi tier collapses to ONE claim family
plus whatever F-M3 does when it is finally tested. Reopen: is a one-family multi
tier worth the shape at all, versus retiring the tier for v1?

**Methodological caveat: 200 rounds is not enough resolution for a ship/no-ship
call.** At p ~= 0.04 the 200-round SE is ~0.014, and M-C actually crossed the
alpha line between run sizes (0.035 at 200 rounds -> 0.073 at 2000). Any
permutation gate on a new group (next-steps F) should use >= 2000 rounds; the
200-round default is for triage only.

### F-M3 has never been permutation-validated, and its nearest analog is noise
The floor decision revived F-M3 (0 -> 19 decisive), but revived is not validated:
every `p_perm` in `08_multi_tier_inventory.md` is for a *candidate*, and F-M3 was
never among them. Its claim shape ("{A} is first more often after {v1}") is the
multi-event relative of **M-B first-overall, the single worst candidate in the
sweep** (p_perm 0.458 at floor 20, 0.458 at floor 10 — pure noise). That is not
proof F-M3 fails (different core universe: 387 triple-conditioned cores vs M-B's
193 single-event ones), but it is reason enough not to ship it unchecked.
Per next-steps F, run F-M3 through a permutation null before it takes a slot;
`run_multi_inventory.py`'s candidate list needs an F-M3 entry to do it.

### Retire §6 lever 2 (position test as verdict driver)?
The permutation null shows the Mann-Whitney normal approximation is
**anti-conservative on tie-heavy ordinal data**: shuffled labels produce ~11%
decisive cores against a nominal 5%. The lever's headline (S-M1/S-M2/S-M3 going
0 → 6 significant) is 6.7% — *below* the noise rate. Rank-based candidates
M-E′ (p_perm 0.33) and M-A (0.38) collapse the same way. Open: retire the lever,
or re-run it with an EXACT Mann-Whitney before trusting any of its counts. Note
`core/positions.py` uses this same normal approximation throughout, so anything
reading its p-values as verdicts is affected.

### Is a two-group multi tier enough of a tier? (updated 2026-08-11)
RESOLVED in part: F-M3's S = 0 was a floor casualty and the floor decision
revived it (19 decisive at floor 10), as predicted. The multi tier is now P-M2
(30), C-M2 (43), F-M3 (19) by supply. But **two of those three are in doubt on
validity, not supply**: C-M2 fails its permutation null at both floors, and F-M3
has never been run against one. If C-M2 drops and F-M3 fails, the tier is P-M2
alone. Open: whether to backfill with M-F or M-C (see the ranking item above),
and whether a one- or two-group multi tier justifies the shape at all.

## Framework

### MedTempo annotation release
RESOLVED (2026-08-11): **not a blocker.** MedTempo is published with an upcoming
conference paper, and will be archived for public visibility afterwards. So the
2026-08-11 decision to give the framework the annotated leveled-order sequences at
inference time stands, and the input design does not revert to narratives.

Remaining bookkeeping, not a design question: the benchmark release must cite the
MedTempo paper and wait for (or coordinate with) the public archive before the
annotation artifact is distributed.

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
