# Next Steps — as of 2026-08-11

Consolidated state and sequencing. Companion to `decisions.md` (locked),
`open_questions.md` (open), and `08_multi_tier_inventory.md` (multi-tier
evidence, now partly stale — see its banner).

## Where the code now stands

| | |
|---|---|
| Roster as coded | **25 groups** (30 − PROP ×3 − S-M2 − S-V4) |
| Roster after the pending 07-28 migration | **23** (−6 multi, +R1/R3/R5) |
| Verdict labeler | `core/verdict.py`, three-decision, implemented |
| Min-n gate | **10 everywhere, sequence 5** (`core/min_n.py`, 08-11) |
| Tests | **exact only** — chi-square removed from the codebase (08-11) |
| Gold label shipped | **the three-decision verdict** (step C, 08-11) |
| Insufficient sub-types | all three populated: 5,646 / 2,722 / 116 (step B, 08-11) |
| Decisive cores (S) across all 25 groups | **1526** |
| Groups at S = 0 | **6** — exactly the six pending removal |

Live groups and their equal-thirds budgets (~1.5·S): C-V1/C-V3 567 each,
P-V1/P-V3 327 each, F-V3 111, C-M2 64, P-M2 45, F-M3 28, S-V1 6.

**Every group we intend to keep can now ship a verdict.** The remaining S = 0
groups are exactly the six the roster migration deletes, so supply is no longer
the blocker — the open items below are validity and composition questions.

## Decisions blocking further code

Both items that previously gated everything are LOCKED: the min-n floor (10,
sequence 5) and the non-directional CHOICE test swap (S-V3/F-V1/F-V2 to
modal-vs-runner-up, S-V4 removed). What remains:

1. **C-M2.** Fails its own permutation null at **both** floors — p_perm 0.129 at
   floor 20, **0.151** at floor 10 with 2000 rounds — so this is not a supply
   problem and no floor rescues it. Its supported/refuted labels would be largely
   noise. Drop, or keep with the caveat documented?
2. **Sequence family.** The floor of 5 keeps S-V1 and S-V3 at **4** decisive
   cores each, but they are largely the same four triples asked two ways. Report-level-only, vaccine-agnostic pooling, or
   MedDRA coarsening? Note this is coupled to the floor: a universal 10 would
   have forced report-level-only by fiat.
3. **§6 lever 2 (position test as verdict driver).** The rank tests are
   anti-conservative on tie-heavy data (~11% decisive under shuffled labels vs a
   nominal 5%). Retiring is FREE: `core/positions.py` is imported only by
   `make_examples.py` and `replacement_inventory.py`, never by `core/answers.py`,
   so no gold label reads those p-values.
4. **How to source `not_locatable` outside the sequence family.** `sparse` is
   solved (step B). All 116 `not_locatable` cores are sequence triples that are
   present but never orderable; the pairwise, co-occurs and first/last families
   have none, because their enumeration pre-filters to co-occurrence ≥ 10.
5. **Is a one-family multi tier worth the shape?** Of the multi candidates only
   P-M2 (p_perm 0.025) and M-F (0.033) clear their null, and they are the same
   claim family, so only one ships. Both single-event candidates now fail
   (M-H 0.120, M-C 0.073). C-M2 fails. F-M3 is untested.

## Implementation order

**A. Roster migration.** Remove P-M1, C-M1, S-M1, S-M3, F-M1, F-M2 (locked
07-28). Add R3 = P-V2, R5 = C-V2, R1 = P-V4 — each needs four-register wording;
R5 needs a corpus helper (2×2 presence × presence with marginals) and R1 a
4-event (A,B,C,D) enumeration shape. Fold in decisions 1–2.

Note: the Overleaf draft has already published the new groups' IDs
(P-V2 = R3, C-V2 = R5, P-V4 = R1) and their answer types (all BOOL), while
`open_questions.md` still lists both as open. Reconcile before or during A.

**B. Corpus helpers report n at every size** — **DONE 2026-08-11**
(decisions.md). The helpers measure and `core/min_n` is the only floor;
`ViableCore.computable` now means "clears the family floor". `sparse` 0 → 2,722,
`not_locatable` 0 → 116, the unnameable `unknown` bucket 2,838 → 0, and S held at
1,526. Remaining gap for D: `not_locatable` has zero supply outside the sequence
family.

**C. Flip the gold label** — **DONE 2026-08-11** (decisions.md). The shipped
`gold_verdict` is the three-decision verdict, and `feasible_polarities` gates on
decisiveness so supported/refuted can only be drawn from decisive cores. 57.5% of
cores changed label; nothing flipped supported ↔ refuted. Landed before A rather
than after, because the test swap in the now-locked decision had already fixed
the groups that would have been mislabeled.

**D. Equal-thirds sampler.** Replace the 45/45/10 balance the pilot still
targets: ~1.5·S budget per group, supported and refuted drawn from *different*
event combinations (never the A→B / B→A mirror), insufficient spanning all three
sub-types with the not-locatable third generated deliberately. Carries two
constraints found on 08-11: `not_locatable` has no supply outside the sequence
family (open question 4), and C-V1/C-V3 are not orientable so they arrive 40
supported / 338 refuted with no way to rebalance within the group.

**E. Regenerate the go/no-go table** on the final roster
(`scripts/run_verdict_labels.py`) and review before scaling past the pilot.

**F. Gate any new group on a permutation null**, at **≥ 2000 rounds**. 200 is
triage only: M-C crossed the alpha line between 200 and 2000 rounds (0.035 →
0.073). `scripts/run_multi_inventory.py` is the pattern; it needs an F-M3 entry,
since F-M3 has never been permutation-validated and its nearest analog (M-B
first-overall) is pure noise at 0.453.

**G. Overleaf draft.** Both generated `.tex` files predate the 08-04 and 08-11
decisions. The *published* draft overstates supply by 334 cases — it credits
F-V1 130, F-V2 176, S-V3 14, S-V4 14 as decisive, which the three-decision rule
does not — for a headline of 2,627 decisive / ~3,940 items.

**The generator is NOT the problem** (verified 08-11 by regenerating): it counts
`s.significant`, which became falsy for non-directional modes when the
three-decision labeler landed, so a fresh run already reports 0 for all four and
a headline of 2,293. The stale numbers exist only in the Jul-28 file on Overleaf.
Of that 2,293, the 931 new-group ceilings (P-V2 372, P-V4 415, C-V2 144) are not
yet implemented, so the defensible implemented figure is **1,362**.

Two real blockers before regenerating: the "What changed in the redesign" section
was deleted by hand on Overleaf and the generator resurrects it (confirmed), and
`ROSTER` still lists S-V3/S-V4/F-V1/F-V2 with `multinomial GOF` in the Test
column, which decision 1 changes. The draft also has no methods text on the
permutation null, the min-n floor, or the rank-test invalidation — the strongest
methodological material the project has.

## Standing caveats

- Group-level validity ≠ per-core validity: a group that clears its permutation
  null still contains false positives at the alpha rate. Inherent to
  significance-as-verdict.
- `p_perm` is a **design-time** diagnostic. decisions.md still excludes
  permutation from gold-label computation, because the model must be able to run
  whatever test produces the label.
- Exactness costs enumeration, not accuracy: the k-category tests grow as
  `C(n+k-1, k-1)`, so a large-k table can exceed `EXACT_MAX_TABLES` and raise
  rather than approximate. Nothing in the current corpus does.
- The `.venv` lost its editable install; tests need `PYTHONPATH=src` until
  `pip install -e .` is re-run.
