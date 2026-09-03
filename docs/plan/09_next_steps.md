# Next Steps — as of 2026-08-14 (dataset build day)

> **Doc audit completed 2026-08-12.** Every plan doc was scanned against the code
> and against `decisions.md`. Seed docs 01–06 had drifted badly — 02 alone
> carried four superseded gold-label rules and a release section that was exactly
> backwards — and are now corrected in place with dated strikeouts.
> `open_questions.md` was cleaned (11 already-resolved items removed, others
> trimmed to their open remainder) so the file answers "what is open?" again.
> `decisions.md` gained a read-newest-first banner: it is append-only, so its
> seed section still says "narratives", "30 groups" and "Johnson". Details in the
> audit entry at the bottom of this file.

Consolidated state and sequencing. Companion to `decisions.md` (locked),
`open_questions.md` (open), and `08_multi_tier_inventory.md` (multi-tier evidence,
partly stale — see its banner).

**Read this file and `open_questions.md` at the start of every session** — after
`git pull`. Work happens on more than one machine, so committed docs are the only
record of current settings, pending work and known defects.

## Open issues register — everything live, one table

| # | issue | kind | status | detail lives in |
|--:|---|---|---|---|
| ~~1~~ | ~~Multi tier~~ | — | **DECIDED 2026-08-14: ship P-M2 alone** | `decisions.md` "Dataset-creation decision batch" |
| ~~2~~ | ~~Roster migration A~~ | — | **CLOSED 2026-08-14: COMPLETE** — six groups removed; P-V2/P-V4/C-V2 shipped, all three cleared their 2000-round screens at p_perm 0.0005 | `decisions.md` "v1 DATASET GENERATED" |
| 3 | Eval harness — architecture, metrics, baselines | build | **designed + M1/M2 BUILT 2026-09-01** (`11_model_pipeline.md`; branch `model-pipeline-design`): B0 oracle = exactly 100% over all 147,936 records, 2,292 underdetermined as expected; local 7B smoke runs scored (§10.3: extraction 0.740, text-to-SQL 0.545, full local 0.292 — S2 is the weak stage); M3–M5 (fine-tuned extractor + split, in-context/agent baselines, write-up hooks) not started | `11_model_pipeline.md` §10.3 |
| ~~4~~ | ~~Confidence tag~~ | — | **CLOSED 2026-08-14 by removal**: tag + width fields leave the release; the Wilson CI stays | `decisions.md` batch 2 |
| ~~5~~ | ~~not_locatable sourcing~~ | — | **CLOSED 2026-08-14: implemented** — `enumerate_false_cores` injects seeded zero-joint combinations at balance time, ceil(S/3)+3 per non-report group | `decisions.md` batch 2 |
| ~~6~~ | ~~Report-level equal thirds~~ | — | **CLOSED 2026-08-14**: dissolved — report level is two-class by design, implemented with issue 7 | `decisions.md` batch 2 |
| ~~7~~ | ~~Report-level ties~~ | — | **CLOSED 2026-08-14: implemented** — `_report_combo` picks the earliest fully-ordered pair/triple; C-R1 keeps ties (its supported case) | `decisions.md` batch 2 |
| ~~8~~ | ~~Synonym table~~ | — | **CLOSED 2026-08-14: v1 ships without it** (documented limitation) | `decisions.md` batch |
| 9 | Sequence cohort tier has S = 8 across two groups (S-V1, S-V3) | decision | **DECIDED 2026-08-14: (b) take in full, flagged thin**; levers 4/5 recorded as post-v1 | `decisions.md` batch 2 |
| 10 | Overleaf update | write-up | dataset-construction section DRAFTED and presented (`docs/draft/dataset_construction.md`); awaiting user approval before any sync; rest of the draft still stale | §5 below |
| ~~11~~ | ~~Disconnected components~~ | — | **CLOSED 2026-08-14 by inspection**: the leveled-order format is a single chain by construction; `num_groups` = stage count (mislabeled); upstream per issue 15 | `decisions.md` batch |
| 12 | `.venv` lost its editable install | environment | workaround: `PYTHONPATH=src` | standing caveats |
| ~~13~~ | ~~C-V3 argmax vs majority~~ | — | **CLOSED 2026-08-14: implemented AND CLEARED** — 258 decisive of 959 vs null mean 62.6, p_perm 0.0005 (`data/pilot/cv3_screen.json`); natural balance 101/157 vs the old 40/338; registers reworded to argmax | `decisions.md` batch 2 |
| ~~14~~ | ~~Twin-core leakage~~ | — | **CLOSED 2026-08-14: `fact_id` field ships on every record** (statistic-family + cohort + sorted events); the deferred split (issue 17) keys on it; papers quote distinct-fact counts | `decisions.md` batch 2 |
| ~~15~~ | ~~Corpus provenance / "expert-annotated"~~ | — | **CLOSED 2026-08-12** — MedTempo is taken as the gold-label dataset; corpus quality is out of scope | `decisions.md` "MedTempo is the gold-label dataset" |
| 16 | Positional/rank track has no exact test at our n | **decision + build** | verdict-driver question still open; descriptive positional attributes **SHIPPED** in answer records 2026-08-14 (`generation/positional.py`) | `open_questions.md` "Test tracks" |
| 17 | No train/dev/test split is produced at all | build | DEFERRED by user 2026-08-14 until after dataset creation; issues 14/16 still change how it must be keyed; provisional internal split specified in `11_model_pipeline.md` §8 (2026-09-01: `data/splits/fact_split_v1.json`, keyed on `fact_id`, not part of the release, not built) | §4 below; `11_model_pipeline.md` §8 |
| 18 | Expected false-label count never quantified | **write-up gap** | deferred by user 2026-08-14 until after dataset creation; pure arithmetic over released records | `decisions.md` batch 2 |
| 19 | Six candidate template families screened; 5 clear their nulls | **decision** | open — adopt R1/R3 + N2 + N1 + R5 (+N3/N4 narrowly)? Blocked behind issue 14 | `10_family_expansion.md` (branch `template-family-expansion`) |
| 20 | Single-event position claims cannot use a 0.5 null | **known defect (new families only)** | measured — stage populations are uneven, structural rate 0.5327; the fix needs `_null_ref(mode, core)` | `10_family_expansion.md` §4.3, §4.5 |
| 21 | Cross-cohort comparison of a single-event position is invalid | **method finding** | measured — the label-shuffle null cannot absorb per-core report geometry (37 of 124 cores carry a >5pp structural gap); affects T-V3, K-V5, X6, X7, M-H | `10_family_expansion.md` §4.5 |
| 22 | Top-K enumeration ceiling (`K_PAIR`/`K_TRIPLE`) is an undocumented pilot knob; release ships 17–97% of available decisive supply | **decision** | open — regenerate with `--full`? needs a per-group cap decided jointly, since the surplus sits in the dominant groups | `open_questions.md` "Enumeration breadth" |
| 23 | `MAX_REPORT_CORES` takes the 300 lowest report ids = a chronological prefix; Janssen is 8.8% of report-level instances vs 36.8% of corpus | **defect** | open — fix confined to `_enum_report` (stratify or shuffle); needs regeneration | `open_questions.md` "Enumeration breadth" |
| 24 | P-V2/P-V4 wording says "more often" (count language) in the original/media/clinical registers while the statistic is a Fisher RATE comparison; count-order and rate-order disagree on **P-V2 273 / P-V4 2,194 instances** (C-V2 467 / P-M2 8 are rate-worded, so unaffected). Same defect class as issue 13 | **decision** | open 2026-09-01 — reword or accept as documented ambiguity. **Audit DONE 2026-09-01** (`11a_template_faithfulness_audit.md`, all 184 strings: 70 FAITHFUL / 65 NOTE / 38 AMBIGUOUS / 1 MISMATCH / 10 underdetermined-input; counts reproduced exactly; NEW: C-V2 clinical `question_negated` "unassociated" mismatch, 145 instances; P-V2 clinical "than {C}" second parse, 1,059; rewordings proposed in its §4) — the reword-vs-accept decision remains; confounds register-invariance on P-V2/P-V4 | `11a_template_faithfulness_audit.md`; `open_questions.md` "Framework" |
| 25 | `test_verdict` equals the CANONICAL verdict at report tier (`oriented_significance` returns `core_significance` there), so it disagrees with `gold_verdict` on exactly **1,800 refuted report-level rows** (300 each in P-R1, P-R2, S-R1, F-R1, F-R2, F-R3). No gold label is wrong; the provenance field is | **defect** | open 2026-09-01 — fix confined to `answers.py::oriented_significance` report branch + `instances.py` comment; needs regeneration or a field patch; the harness never reads `test_verdict` | `decisions.md` "model pipeline / eval-harness architecture" (2026-09-01) |
| 26 | P3 paraphrase probe: may an eval-only paraphrase set be LLM-authored (never released as benchmark text; `CLAUDE.md` "Mechanical generation only" governs benchmark text), hand-written, or skipped? | **decision** | open 2026-09-01 — user decision; P3 is the only protocol that evidences out-of-template generalization; nothing in M1/M2 depends on it | `open_questions.md` "Framework"; `11_model_pipeline.md` §4 |

Items 1–12 contain no correctness bug in generated data: `validate_gold.py` clears
all 20,749 instances on six invariant families as of 2026-08-11. Items 4, 5, 6 and 8
are completeness/calibration gaps, not wrong labels.

**Item 13 is different, and `validate_gold.py` structurally cannot catch it.** Its
label is internally consistent with its statistic; what is misaligned is the TEXT
against the statistic. Every invariant check in the validator compares gold fields to
each other, so no invariant family covers "does the question the instance ASKS match
the quantity it SCORES". That class of defect has now appeared three times (S-V1/F-V3
on 07-13, F-V2/F-R2 on 08-12, C-V3 today) and is found only by reading a rendered
instance beside its statistic. Worth a standing review step, not another invariant.

## Where the code now stands

| | |
|---|---|
| Roster as coded | **20 groups** = 7 report-level + 12 single-cohort + P-M2 (migration A COMPLETE 2026-08-14; P-V2/P-V4/C-V2 pending their screens) |
| Cohort groups that ship a verdict | **all 13** — the non-directional groups are gone; every cohort mode has a directional alternative |
| Report-level classes | **two** (supported/refuted, 50/50): order questions are not posed on tied reports; `insufficient` does not exist at report level |
| Min-n gate | 10, sequence 5 (`core/min_n.py`) |
| Tests | exact only; chi-square removed from the codebase |
| Gold label | the **three-decision verdict**, oriented to each instance's own claim |
| Framework input | the **annotated leveled orders**, never narratives |
| Decisive cores (S) | **stale — re-measure at generation.** The 1365 predates today: C-V3's argmax alone is 258 (was 378 shared with C-V1); the additions measured 2,302 / 16,884 / 2,098 decisive at full enumeration |
| Insufficient sub-types | all populated: underpowered 3,246 / sparse 4,941 / not_locatable 118 (re-measured 08-12) |
| Sampler | equal thirds **per group**, every decisive core posed **both ways**; ceil(S/3)+3 seeded FALSE combinations injected per non-report group for the not_locatable third |
| Release format | `*_questions.jsonl` (input only) + `*_answers.jsonl` (gold), split enforced; answers now carry `fact_id` and the descriptive `positional` block |
| Gold-label validation | six invariant families incl. per-arm DB recomputation for the new modes; last exhaustive run 17,341 instances (pre-additions), sampled clean at 20 groups |
| Reported statistics | one-sided exact p-value, 95% Wilson CI (Wilson-Newcombe on the difference for every two-arm/two-cohort mode), Cohen's h against the test's own null — all oriented to the instance's asserted claim |
| Confidence fields | Wilson CI only — the tag and width fields were REMOVED 2026-08-14 (issue 4 closed by removal) |

### Closed since the 08-11 entry (2026-08-12)

- Two claim/label mismatches found while building sample instances and fixed:
  F-V2/F-R2 named the wrong event in every instance, and two-cohort `gold_n2`/`gold_k2`
  described the wrong cohort. Both now covered by regression tests and by
  `validate_gold.py`. See `decisions.md`.
- The one-off sample artifacts and their generator scripts were removed at the
  user's request (`850d52f`); `openpyxl` was reverted out of the `render` extra.
  Nothing in the pipeline depends on them.

## The pipeline is DONE for the testable templates

Steps B, C and D are complete, plus the release format and the validation guard:

- **B** — corpus helpers report `n` at every size; the shared gate is the only floor.
- **C** — the shipped label is the three-decision verdict, and each instance's
  statistics describe **its own** asserted claim.
- **D** — equal thirds per group; one claim per core per class; re-orientation
  minimised; the insufficient third spread across sub-types.
- **Release** — report ids not narratives, with the input/gold boundary enforced by
  `writers.split_release`.
- **Part C** — mechanised in `scripts/validate_gold.py`. Worth putting in CI: it is
  what caught the first-mention bug.

## Sequencing — read this before picking anything up (2026-08-13)

The register is a list, not an order. Seventeen issues are open; these are the
dependencies that actually constrain what can be done when. The detail sections
below (§1–§5) are older and do NOT reflect issues 13–18 — use this ordering.

### The one dependency that is easy to get wrong

**Issue 16 (exact rank tests) comes BEFORE issues 1 and 9.**

Issues 1 (multi tier is P-M2 alone) and 9 (sequence cohort tier has S = 8) both
look like "accept the thin tier or retire it" decisions. They are not, yet. The
rank track conditions far less than the categorical one — co-present n ≈ 21
against orderable n ≈ 6 — so a valid exact rank test could change the supply
underneath both decisions. §6 lever 2 promised exactly this and failed only
because the Mann-Whitney *normal approximation* is anti-conservative on tie-heavy
data, not because the idea was wrong.

Deciding 1 and 9 first risks retiring two tiers that were rescuable, and those
retirements are hard to walk back once the roster, the wording and the draft have
moved on. Test 16 first; then 1 and 9 are informed decisions rather than guesses.

Note 16 may also come back negative — the exact test may still fail its
permutation null, or the "model runs the test" rule may exclude an enumerated
tie-conditional distribution. That is a fine outcome: it converts 1 and 9 from
open questions into settled ones with a measurement behind them.

### Order

**Blocking dataset lock**

1. **13 — C-V3 argmax vs majority.** Independent of everything; fix whenever. It
   is the only item currently putting wrong labels in generated data (5 shipped
   decisive cores). Move it to the argmax statistic, or remove the group.
2. **16 — exact rank tests.** Upstream of 1 and 9, per above.
3. **1 — multi tier**, **9 — sequence tier.** Decide only after 16 reports.
4. **2 — roster migration A.** Needs 1 and 9 settled. Re-measure R1/R3/R5 supply
   first: the 372/415/144 estimates predate every floor and test change, and
   those changes roughly doubled supply elsewhere, so they may be *understated*.
5. **14 — group-independent `fact_id`**, then **17 — the train/dev/test split.**
   Strictly in that order: a split keyed on `derived_from_core_id` puts the same
   fact on both sides, because `core_id` embeds `group_id`.

**Parallel — none of this blocks lock**

- 4 (confidence-tag calibration, needs 04's A4), 5 (`not_locatable` outside
  sequence), 6 (report-level thirds), 7 (report-level ties), 8 (synonym table),
  11 (disconnected components, 04's A6).

**Blocking modeling**

- 3 (eval harness). Specifiable now — the input format is settled. Can be
  specified in parallel with the above, but not finalised until the roster is.

**Write-up, after the roster settles**

- 10 (Overleaf draft), 18 (expected false-label count), MedTempo citation and
  archive coordination.

**Housekeeping**

- 12 (`.venv` editable install; `PYTHONPATH=src` works meanwhile).

## What is next, in priority order

> **Older section (pre-2026-08-13).** §1–§5 below were written before issues
> 13–18 existed. They still hold as detail on the items they cover; the ordering
> above supersedes their numbering.

### 1. Validity ledger - CLOSED 2026-08-11

All three items done. The roster now ships nothing that fails its own null:

- **Lever 2** - retired. `core/positions.py` is descriptive-only and
  `core/answers.py` does not import it.
- **F-M3** - retired (0.183-0.188), and all three substitute shapes fail too
  (M-J 0.096, M-G 0.509, M-I 0.698). The first/last family structurally cannot have a
  two-cohort group.
- **C-M2** - dropped (0.129 / 0.151 / 0.195 / 0.202 over four measurements).

**The live decision now: the multi tier is P-M2 alone.** Ship it, swap it for M-F, or
retire the two-cohort tier for v1? See `open_questions.md`.

### 2. The eval harness — the actual path to modeling

~~Nothing exists yet; `src/` is entirely corpus, generation and statistics.~~
**Designed 2026-09-01 in `11_model_pipeline.md`** (branch `model-pipeline-design`):
the three-stage contract (S1 extraction → `StructuredClaim`; S2 text-to-SQL retrieval
over the narrative-free `medtempo_eval.db`; S3 exact test through the existing oracle
`core_significance(named=)`) plus S4 evaluation with per-stage attribution, pair/twin
consistency and the `underdetermined` token. The architecture / metrics / baselines
questions that used to sit here are answered there (§2, §5–§7) and locked in
`decisions.md` (2026-09-01). M1 (deterministic chain) + M2 (local-LLM extraction and
local-LLM SQL) are BUILT on that branch (2026-09-01; B0 = 100%, smoke runs in
`11_model_pipeline.md` §10.3); M3–M5 are designed only.

M1 verification line (the harness is correct iff this holds exactly):
`scripts/run_eval.py --pipeline oracle --subset all` → verdict 1.0 on the 145,644
answerable records, 2,292 `underdetermined`, retrieval EM 1.0 on every arm,
`(n,k[,n2,k2])` EM 1.0, p-agreement 1.0, pair-contradiction 0.0; `options[0]` = 1.0
on F-R1/P-R2, `options[2]` = 1.0 on F-R2, per-group majority 0.370. Any deviation is
a harness bug. Results are recorded in `11_model_pipeline.md` §10.

### 3. Roster migration A — the biggest remaining supply lever

Remove P-M1, C-M1, S-M1, S-M3, F-M1, F-M2 (all at S = 0, so nothing shippable is
lost). Add R3 = P-V2, R5 = C-V2, R1 = P-V4: each needs four-register wording, R5 a
2×2 presence × presence corpus helper, R1 a 4-event enumeration shape. The Overleaf
draft already published their IDs and BOOL answer types.

Their old supply estimates (P-V2 372, P-V4 415, C-V2 144) predate every floor and
test change made today, so **re-measure before relying on ~931**.

### 4. Dataset completeness

- **`not_locatable` outside the sequence family.** All 116 are sequence triples that
  are present but never orderable; pairwise/co-occurs/first-last have none, because
  their enumeration pre-filters to co-occurrence ≥ 10. The 07-28 decision requires
  this third to be generated deliberately.
- **Report-level groups** (7 of 25). Deferred by decision. They do not reach equal
  thirds, and the question underneath is what `insufficient` means for a
  single-report claim — the CHOICE variants treat a co-exist pair as unanswerable
  while the BOOL variants map co_exist to `refuted`.
- **First/last tie handling for CHOICE at report level.** The natural next small
  decision: set-valued gold is defensible at report level precisely because there is
  no aggregation to distort, unlike cohort level where it was rejected on 08-11.
- **Synonym table.** Never built; `synonym_used` echoes the raw MedDRA term, so the
  released text has no lexical variation.
- **No train/dev/test split is produced (issue 17).** `writers.split_release`
  splits INPUT from GOLD, which is a different axis entirely. Three docs say "any
  train/test split must keep mirror pairs together", but nothing produces a
  split, so that instruction has no implementation to constrain. Do not build one
  until issue 14 lands — it must be keyed on a group-independent `fact_id`, not
  on `derived_from_core_id`, or twinned groups leak across the boundary.

### 5. Overleaf draft (step G)

Badly stale — today changed S, the roster, the tests, the nulls, the gold-label rule
and the input format. Do not regenerate until the roster settles (item 3), and note
the generator resurrects the "What changed in the redesign" section that was deleted
by hand on Overleaf.

## Standing caveats

- Group-level validity ≠ per-core validity: a group that clears its permutation null
  still contains false positives at the alpha rate. Inherent to
  significance-as-verdict.
- `p_perm` is a design-time diagnostic, excluded from gold-label computation.
- Mirror pairs are correlated by construction: both members share a
  `derived_from_core_id`, and any train/test split MUST keep a pair together.
- **Changing a test can silently invalidate the reasoning behind a gate** — that is
  how the first/last tie problem survived until Part C. Re-check the gate whenever a
  test changes.
- The `.venv` lost its editable install; tests need `PYTHONPATH=src` until
  `pip install -e .` is re-run.

---

## Doc audit — 2026-08-12

Scanned every plan doc against the code and `decisions.md` before adding
templates or touching dataset construction, on the principle that a stale spec is
worse than no spec: it gets followed.

### What was wrong

| doc | state found | action |
|---|---|---|
| `CLAUDE.md` | current | doc index annotated with each seed doc's status |
| `01_overview` | "over clinical **narratives**", "30 groups × 3 registers", "Johnson", proportions as output | corrected in place, dated |
| `02_dataset_design` | **most dangerous** — rules 3,4,6,7,8 superseded; release section exactly backwards; schema single-file | rules struck with replacements; release rewritten; schema now two-file |
| `03_templates` | roster 13/8/9=30 (actual 10/5/8=23), PROP + `{p}`, "negation is not stored in the YAML", verdict mechanics = the retired point-estimate rule, 10-15k size target | all corrected; roster table marked a snapshot with the regeneration command |
| `04_corpus_survey` | 30 groups, T=100, 45/45/10, "Johnson", Part C as a hand-check | banner marking A4/A6 as the only live parts; Part C marked mechanised, with its known limit |
| `05_significance_tests` | **self-contradictory** — prescribed chi-square in one section, exact-only in another; per-group table listed 7 retired groups; position tests as a live label track | chi-square struck; position track marked descriptive-only; table marked historical |
| `06_pilot_examples` | 30 groups, T=100, 45/45/10 | banner; its "cores must exist" rule flagged as still correct |
| `07`, `08` | already carried supersession banners | none needed |
| `open_questions` | **11 of ~24 entries already RESOLVED** — roughly half the file | resolved entries removed, 3 trimmed to their open remainder, issue numbers added |
| `decisions.md` | append-only history being read as current | read-newest-first banner; reasoning rescued from the deleted open questions appended |

### What this cost us, and the rule worth keeping

Two of these had already caused real work. The retired point-estimate verdict
rule survived in `02` and `03` for two weeks after the three-decision test
replaced it, and `05` prescribed chi-square in its own prose while its own min-n
section said exact-only. Nobody implemented from them in that window — but the
docs are what a new session reads first, and `CLAUDE.md` explicitly points
implementers at `02` for gold-label rules.

**Rule: a decision is not landed until the doc it contradicts is struck.**
Appending to `decisions.md` records the decision; it does not retract the old one
from wherever it was already written down. The seed docs are the natural place
for that debt to accumulate because nothing in the test suite touches them.

### Not in scope of the audit

The audit corrected statements about the project. It did not re-derive numbers:
per-group S, instance counts and permutation p-values were taken from the
committed docs and from one fresh `run_verdict_labels.py` run, which reconciled
(S = 1365, the six S = 0 groups exactly as recorded). One drift noted and left:
`not_locatable` reads 116 in some places and 118 in the current run.
