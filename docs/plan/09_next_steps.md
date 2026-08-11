# Next Steps — as of 2026-08-11

Consolidated state and sequencing. Companion to `decisions.md` (locked),
`open_questions.md` (open), and `08_multi_tier_inventory.md` (multi-tier
evidence, now partly stale — see its banner).

## Where the code now stands

| | |
|---|---|
| Roster as coded | **26 groups** (30 − PROP ×3 − S-M2) |
| Roster after the pending 07-28 migration | **23** (−6 multi, +R1/R3/R5) |
| Verdict labeler | `core/verdict.py`, three-decision, implemented |
| Min-n gate | **10 everywhere, sequence 5** (`core/min_n.py`, 08-11) |
| Tests | **exact only** — chi-square removed from the codebase (08-11) |
| Gold label shipped | still the legacy point-estimate `verdict`; `test_verdict` rides alongside |
| Decisive cores (S) across all 26 groups | **1362** |
| Groups at S = 0 | **10** — six pending removal, plus S-V3/S-V4/F-V1/F-V2 (non-directional) |

Live groups and their equal-thirds budgets (~1.5·S): C-V1/C-V3 567 each,
P-V1/P-V3 327 each, F-V3 111, C-M2 64, P-M2 45, F-M3 28, S-V1 6.

**After the roster migration, the four non-directional groups are the only
remaining S = 0 groups.** That makes decision 1 below the last supply blocker.

## Decisions blocking further code

The min-n floor — previously the item that gated everything — is now LOCKED at
10 (sequence 5). What remains:

1. **Non-directional CHOICE groups** (S-V3, F-V1, F-V2). Adopt the
   modal-vs-runner-up test already locked for their BOOL twins? At floor 10 the
   rescue is no longer marginal: **F-V2 +86, F-V1 +74, S-V3 +4** decisive cores
   (it was +21/+14/+4 at the old floors). **S-V4 is not rescuable** — "the
   ordering is consistent" has no opposite direction, the same defect that
   retires the "same" multi groups.
2. **C-M2.** Fails its own permutation null at **both** floors — p_perm 0.129 at
   floor 20, **0.151** at floor 10 with 2000 rounds — so this is not a supply
   problem and no floor rescues it. Its supported/refuted labels would be largely
   noise. Drop, or keep with the caveat documented?
3. **Sequence family.** The floor of 5 keeps S-V1's **4** decisive cores alive,
   but 4 cores is not a family. Report-level-only, vaccine-agnostic pooling, or
   MedDRA coarsening? Note this is coupled to the floor: a universal 10 would
   have forced report-level-only by fiat.
4. **§6 lever 2 (position test as verdict driver).** The rank tests are
   anti-conservative on tie-heavy data (~11% decisive under shuffled labels vs a
   nominal 5%). Retiring is FREE: `core/positions.py` is imported only by
   `make_examples.py` and `replacement_inventory.py`, never by `core/answers.py`,
   so no gold label reads those p-values.
5. **How to source the `sparse` insufficient sub-type.** New, and created by the
   floor decision: `sparse` was the band between the viability floor and the test
   floor, and those are now equal, so its measured count is **0** while the
   07-28 decision requires insufficient to span all three sub-types.
6. **Is a one-family multi tier worth the shape?** Of the multi candidates only
   P-M2 (p_perm 0.025) and M-F (0.033) clear their null, and they are the same
   claim family, so only one ships. Both single-event candidates now fail
   (M-H 0.120, M-C 0.073). C-M2 fails. F-M3 is untested.

## Implementation order

**A. Roster migration.** Remove P-M1, C-M1, S-M1, S-M3, F-M1, F-M2 (locked
07-28). Add R3 = P-V2, R5 = C-V2, R1 = P-V4 — each needs four-register wording;
R5 needs a corpus helper (2×2 presence × presence with marginals) and R1 a
4-event (A,B,C,D) enumeration shape. Fold in decisions 1–3.

Note: the Overleaf draft has already published the new groups' IDs
(P-V2 = R3, C-V2 = R5, P-V4 = R1) and their answer types (all BOOL), while
`open_questions.md` still lists both as open. Reconcile before or during A.

**B. Corpus helpers must report n below the viability floor.** They currently
return None and drop n, so `sparse` and `not_locatable` are indistinguishable
downstream — 3,319 cores sit in the unlabeled bucket. This is now a prerequisite
for **two** insufficient sub-types, not one. It is also **not sufficient on its
own** for `sparse`: enumeration itself stops at n ≥ 10, so no sub-viability core
ever reaches the labeler (see open question 5).

**C. Flip the gold label** from the legacy point-estimate `verdict` to
`test_verdict`. Deliberately deferred until A lands, because flipping now would
mislabel the non-directional groups that A deletes or reshapes.

**D. Equal-thirds sampler.** Replace the 45/45/10 balance: ~1.5·S budget per
group, supported and refuted drawn from *different* event combinations (never
the A→B / B→A mirror), insufficient spanning all three sub-types with the
not-locatable third generated deliberately.

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
