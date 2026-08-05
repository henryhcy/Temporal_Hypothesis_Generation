# Next Steps — as of 2026-08-05

Consolidated state and sequencing after the three-decision labeler landed.
Companion to `decisions.md` (locked), `open_questions.md` (open), and
`08_multi_tier_inventory.md` (the multi-tier evidence).

## Where the code now stands

| | |
|---|---|
| Roster as coded | **26 groups** (30 − PROP ×3 − S-M2) |
| Roster after the pending 07-28 migration | **23** (−6 multi, +R1/R3/R5) |
| Verdict labeler | `core/verdict.py`, three-decision, implemented |
| Min-n gate | shared family floors (20 / 5 / 30) via `core/min_n.py` |
| Gold label shipped | still the legacy point-estimate `verdict`; `test_verdict` rides alongside |
| Decisive cores (S) across all 26 groups | **587** |
| Groups at S = 0 | **11** — six pending removal, plus S-V3/S-V4/F-V1/F-V2 (non-directional) and F-M3 (floor) |

Live groups and their equal-thirds budgets (~1.5·S): C-V1/C-V3 266 each,
P-V1/P-V3 130 each, C-M2 34, P-M2 27, F-V3 21, S-V1 6.

## Decisions blocking further code

These five gate the roster migration; **1 gates everything**, since the floor
sets every group's supply and decides whether F-M3 lives.

1. **Min-n floor.** Family floors cost 1,075 decisive cores vs the retired
   blanket 10 (pairwise −55%, first/last −85%). Exact tests are valid at small
   n, so this is a quality call, not a validity one. Floor sweep in
   `open_questions.md`.
2. **Non-directional CHOICE groups** (S-V3, F-V1, F-V2). Adopt the
   modal-vs-runner-up test already locked for their BOOL twins (rescue: +4, +14,
   +21 decisive) or retire them. **S-V4 is not rescuable** — "the ordering is
   consistent" has no opposite direction, the same defect that retires the
   "same" multi groups.
3. **C-M2.** Fails its permutation null (p_perm 0.129); its supported/refuted
   labels would be largely noise. Drop, or keep with the caveat documented?
4. **Sequence family.** With S-M1/S-M2/S-M3 gone, cohort-level supply is S-V1's
   4 cores. Report-level-only, vaccine-agnostic pooling, or MedDRA coarsening?
5. **§6 lever 2 (position test as verdict driver).** The rank tests are
   anti-conservative on tie-heavy data (~11% decisive under shuffled labels vs a
   nominal 5%). Retire the lever, or re-run it with an exact Mann-Whitney?

## Implementation order

**A. Roster migration.** Remove P-M1, C-M1, S-M1, S-M3, F-M1, F-M2 (locked
07-28). Add R3 = P-V2, R5 = C-V2, R1 = P-V4 — each needs four-register wording;
R5 needs a corpus helper (2×2 presence × presence with marginals) and R1 a
4-event (A,B,C,D) enumeration shape. Fold in decisions 2–4.

**B. Corpus helpers must report n below the viability floor.** They currently
return None and drop n, so `sparse` and `not_locatable` are indistinguishable
downstream — 3,616 cores sit in an unlabeled bucket. This is a **prerequisite
for D**: the deliberate not-locatable third cannot be generated without it.

**C. Flip the gold label** from the legacy point-estimate `verdict` to
`test_verdict`. Deliberately deferred until A lands, because flipping now would
mislabel the six non-directional groups that A deletes.

**D. Equal-thirds sampler.** Replace the 45/45/10 balance: ~1.5·S budget per
group, supported and refuted drawn from *different* event combinations (never
the A→B / B→A mirror), insufficient spanning all three sub-types with the
not-locatable third generated deliberately.

**E. Regenerate the go/no-go table** on the final roster
(`scripts/run_verdict_labels.py`) and review before scaling past the pilot.

**F. Gate any new group on a permutation null.** The analytic
"cores × alpha" baseline endorsed the two worst candidates in the multi-tier
sweep and failed to flag C-M2. `scripts/run_multi_inventory.py` is the pattern.

## Standing caveats

- Group-level validity ≠ per-core validity: a group that clears its permutation
  null still contains false positives at the alpha rate. Inherent to
  significance-as-verdict.
- `p_perm` is a **design-time** diagnostic. decisions.md still excludes
  permutation from gold-label computation, because the model must be able to run
  whatever test produces the label.
- The `.venv` lost its editable install; tests need `PYTHONPATH=src` until
  `pip install -e .` is re-run.
