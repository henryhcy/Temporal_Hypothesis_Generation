# Next Steps — as of 2026-09-21 (v1.1 frozen; experiment queue open)

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
| 3 | Eval harness — architecture, metrics, baselines | build | **2026-09-22: two new baselines run** — `counts-llm` 0.959 verdict but only 66% p-value agreement (52% Fisher), and `e2e-llm-sql` 0.860 (denominator F1 0.950→0.673, coexist leak 0.198, not_locatable FPR 0.273): two independent measured arguments for the decomposition, in different stages (§10.3a, §10.3b). NOTE §10.3c: neither run tested null/test SELECTION — e2e gold-forces the procedure, smoke-1c hands it over in the mode catalogue. **designed + M1/M2 BUILT 2026-09-01** (`11_model_pipeline.md`; branch `model-pipeline-design`): B0 oracle = exactly 100% over all 147,936 records, 2,292 underdetermined as expected; local 7B smoke runs scored (§10.3: extraction 0.740→0.928 with hints, text-to-SQL 0.545, full local 0.292); **2026-09-03: API adapters built, claude-opus-5 runs scored** — S2-only 0.975, mixed local-S1+API-S2 0.903 (S2 was a capability gap, not benchmark impossibility); M3–M5 not started; **experiment queue frozen 2026-09-04, see §1a below**, pending dataset stabilization (issues 22–25) | `11_model_pipeline.md` §10.3 |
| ~~4~~ | ~~Confidence tag~~ | — | **CLOSED 2026-08-14 by removal**: tag + width fields leave the release; the Wilson CI stays | `decisions.md` batch 2 |
| ~~5~~ | ~~not_locatable sourcing~~ | — | **CLOSED 2026-08-14: implemented** — `enumerate_false_cores` injects seeded zero-joint combinations at balance time, ceil(S/3)+3 per non-report group | `decisions.md` batch 2 |
| ~~6~~ | ~~Report-level equal thirds~~ | — | **CLOSED 2026-08-14**: dissolved — report level is two-class by design, implemented with issue 7 | `decisions.md` batch 2 |
| ~~7~~ | ~~Report-level ties~~ | — | **CLOSED 2026-08-14: implemented** — `_report_combo` picks the earliest fully-ordered pair/triple; C-R1 keeps ties (its supported case) | `decisions.md` batch 2 |
| ~~8~~ | ~~Synonym table~~ | — | **CLOSED 2026-08-14: v1 ships without it** (documented limitation) | `decisions.md` batch |
| 9 | Sequence cohort tier has S = 8 across two groups (S-V1, S-V3) | decision | **DECIDED 2026-08-14: (b) take in full, flagged thin**; levers 4/5 recorded as post-v1 | `decisions.md` batch 2 |
| 10 | Overleaf update | write-up | **re-synced 2026-09-30** (Overleaf commit `b99e25b`, `overleaf-hypogen` clone): v1.1 numbers, stage/toolbox/external baseline tables, Related Work + positioning table (`tab:related`), `related_work.bib` stubs (author lists marked TODO). AAAI twin is regenerated from the ARR body (`dataset_construction.tex` is the master). Still stale: `Findings_and_Templates.tex` (regenerable via `make_findings_tex.py`) | §5 below |
| ~~11~~ | ~~Disconnected components~~ | — | **CLOSED 2026-08-14 by inspection**: the leveled-order format is a single chain by construction; `num_groups` = stage count (mislabeled); upstream per issue 15 | `decisions.md` batch |
| 12 | `.venv` runs Python 3.9 / **SQLite 3.39.5**, but the eval DB views need **SQLite >= 3.44** (ORDER BY inside `group_concat`) — 108 framework tests error out on it | **environment blocker** | **FIXED 2026-09-05 on this machine**: `python3.13 -m venv .venv313 && .venv313/bin/pip install -e ".[dev]"` → 527 passed / 5 skipped, and the editable install works so `PYTHONPATH=src` is no longer needed. Do the same on any machine running the harness | standing caveats |
| ~~13~~ | ~~C-V3 argmax vs majority~~ | — | **CLOSED 2026-08-14: implemented AND CLEARED** — 258 decisive of 959 vs null mean 62.6, p_perm 0.0005 (`data/pilot/cv3_screen.json`); natural balance 101/157 vs the old 40/338; registers reworded to argmax | `decisions.md` batch 2 |
| ~~14~~ | ~~Twin-core leakage~~ | — | **CLOSED 2026-08-14: `fact_id` field ships on every record** (statistic-family + cohort + sorted events); the deferred split (issue 17) keys on it; papers quote distinct-fact counts | `decisions.md` batch 2 |
| ~~15~~ | ~~Corpus provenance / "expert-annotated"~~ | — | **CLOSED 2026-08-12** — MedTempo is taken as the gold-label dataset; corpus quality is out of scope | `decisions.md` "MedTempo is the gold-label dataset" |
| 16 | Positional/rank track has no exact test at our n | **decision + build** | verdict-driver question still open; descriptive positional attributes **SHIPPED** in answer records 2026-08-14 (`generation/positional.py`) | `open_questions.md` "Test tracks" |
| 17 | No train/dev/test split is produced at all | build | DEFERRED by user 2026-08-14 until after dataset creation; issues 14/16 still change how it must be keyed; provisional internal split specified in `11_model_pipeline.md` §8 (2026-09-01: `data/splits/fact_split_v1.json`, keyed on `fact_id`, not part of the release, not built) | §4 below; `11_model_pipeline.md` §8 |
| 18 | Expected false-label count never quantified | **write-up gap** | deferred by user 2026-08-14 until after dataset creation; pure arithmetic over released records | `decisions.md` batch 2 |
| 19 | Six candidate template families screened; 5 clear their nulls | **decision** | open — adopt R1/R3 + N2 + N1 + R5 (+N3/N4 narrowly)? Blocked behind issue 14 | `10_family_expansion.md` (branch `template-family-expansion`) |
| 20 | Single-event position claims cannot use a 0.5 null | **known defect (new families only)** | measured — stage populations are uneven, structural rate 0.5327; the fix needs `_null_ref(mode, core)` | `10_family_expansion.md` §4.3, §4.5 |
| 21 | Cross-cohort comparison of a single-event position is invalid | **method finding** | measured — the label-shuffle null cannot absorb per-core report geometry (37 of 124 cores carry a >5pp structural gap); affects T-V3, K-V5, X6, X7, M-H | `10_family_expansion.md` §4.5 |
| 22 | Top-K enumeration ceiling (`K_PAIR`/`K_TRIPLE`) is an undocumented pilot knob; release ships 17–97% of available decisive supply | **decision** | **DECIDED 2026-09-04: keep v1 caps, document as design choice** (top-25/top-16 most frequent terms per cohort); full enumeration revisited only at post-pilot scale-up | `decisions.md` 2026-09-04 |
| 23 | `MAX_REPORT_CORES` takes the 300 lowest report ids = a chronological prefix; Janssen is 8.8% of report-level instances vs 36.8% of corpus | **defect** | **FIXED 2026-09-04 in v1.1** — seeded shuffle (`REPORT_SAMPLE_SEED`); Janssen 8.8% → 35.1% at the report tier | `decisions.md` "v1.1 REGENERATED" |
| 24 | P-V2/P-V4 wording says "more often" (count language) in the original/media/clinical registers while the statistic is a Fisher RATE comparison; count-order and rate-order disagree on **P-V2 273 / P-V4 2,194 instances** (C-V2 467 / P-M2 8 are rate-worded, so unaffected). Same defect class as issue 13 | **decision** | open 2026-09-01 — reword or accept as documented ambiguity. **Audit DONE 2026-09-01** (`11a_template_faithfulness_audit.md`, all 184 strings: 70 FAITHFUL / 65 NOTE / 38 AMBIGUOUS / 1 MISMATCH / 10 underdetermined-input; counts reproduced exactly; NEW: C-V2 clinical `question_negated` "unassociated" mismatch, 145 instances; P-V2 clinical "than {C}" second parse, 1,059; rewordings proposed in its §4) — the reword-vs-accept decision remains — **DEFERRED by user 2026-09-04 ("think more, come back later")**; confounds register-invariance on P-V2/P-V4. NOTE: a later reword is TEXT-ONLY (ids/labels survive), so it does not block the v1.1 regeneration for issues 23/25 | `11a_template_faithfulness_audit.md`; `open_questions.md` "Framework" |
| 25 | `test_verdict` equals the CANONICAL verdict at report tier (`oriented_significance` returns `core_significance` there), so it disagrees with `gold_verdict` on exactly **1,800 refuted report-level rows** (300 each in P-R1, P-R2, S-R1, F-R1, F-R2, F-R3). No gold label is wrong; the provenance field is | **defect** | **FIXED 2026-09-04 in v1.1** — report branch now oriented; `test_verdict == gold_verdict` on all 18,492 v1.1 rows (v1 keeps its 1,800; harness still never reads the field) | `decisions.md` "v1.1 REGENERATED" |
| 26 | P3 paraphrase probe: may an eval-only paraphrase set be LLM-authored (never released as benchmark text; `CLAUDE.md` "Mechanical generation only" governs benchmark text), hand-written, or skipped? | **decision** | open 2026-09-01 — user decision; P3 is the only protocol that evidences out-of-template generalization; nothing in M1/M2 depends on it | `open_questions.md` "Framework"; `11_model_pipeline.md` §4 |
| 27 | Null/test SELECTION is untested and currently untestable: 20 modes collapse to 3 cohort signatures, and the S1 mode catalogue prints test + null + p0 + conditioning + H0 per mode | **decision + build** | open 2026-09-22 — prerequisite is `NullSpec` expressing a DATA-DERIVED null (issue 20); a computed p0 cannot be printed in a catalogue row, which is what would make inference real | `11_model_pipeline.md` §10.3c |
| 28 | No run has held the middle condition (mode given / conditioning withheld, or the reverse) — smoke-1c is given everything, e2e-sql nothing | measurement gap | open 2026-09-22; **the toolbox frame (issue 29) is this condition** — separates "which claim type is this" from "what does that type require" | `11_model_pipeline.md` §10.3c |
| 29 | **S1 toolbox frame** (the eval protocol): task card + test DEFINITIONS + situation-phrased conditioning primitives, NO mode catalogue / per-mode H0; model composes the procedure; `derive_mode(procedure)` reverse lookup for S2/S3; scored on procedure fields + slots | **build** | **BUILT 2026-09-30** (branch `s1-toolbox`, `--s1-frame toolbox`; 11 §11a). v1.1 smoke slice: 7B 0.918 lookup -> 0.64-0.68 compose (110-125/400 plans match no mode); **claude-opus-5 1.000 lookup -> 1.000 compose** -- the gap is model-tier; frontier S1 is solved on seen templates without the mapping, so S1 difficulty must come from P2 / null diversity (rows 32, T2) | `decisions.md` "state every stipulation, withhold only the mapping" |
| 30 | S1 structural lever: (tier, answer_type, n_events) pins the mode for 25/38 smoke-1c mode errors (P-R2 18, P-V4 7, P-M2 7); constrained decoding by signature + self-contradiction retry (`underdetermined` on a determined input) | system lever | open 2026-09-29 — legitimate scaffolding (uses the input, not the key) but keep it OUT of the capability ledger | `decisions.md` same entry, "S1 error structure" |
| 31 | **S1 conditional plan + method adjudication by guards** -- plan = claim shape / denominator / null recipe / tail / test selection RULE / gate; S3 resolves the rule; equivalence-class table 11 §13.4; exact-only restated as "valid at the instance's n" | **build + decision** | **BUILT 2026-09-30** with issue 29: plan schema, `derive_mode`, rule resolution in S3 (asymptotic branch = one-sided two-proportion z, guard min expected cell >= 5), plan scoring + `rule_valid` | `decisions.md` 2026-09-29 "conditional plan"; `11` §13 |
| 32 | **Null diversity expansion -> v1.2** | build | **DONE 2026-10-08**: six review items implemented; **v1.2 final = the working release** (70,104 records / 8,763 instances / 29 groups; cap 600; report groups 200/200; ids pseudonymised; validated 56,138; B0 1.000 on all records). Next: the v1.2-final smoke rows (S1 7B/32B zero-shot on v2.1, S2 coder-32B, e2e, counts, registers), then `eval_core` | `decisions.md` IMPLEMENTED 2026-10-08 |
| 33 | **External validation on P-Bench**: hide the stated H0, score the formulated null against it; Fisher-family subset through our executor | experiment | open 2026-09-29 -- hypotheses authored by others; no new gold needed | `11` §12.1, §13 |
| 35 | Report-tier denominator under the toolbox frame | decision | **CLOSED 2026-10-08**: the report tier is a separate single-report READING task; denominator/null/test are not part of it (harness fills single_report); headline statistics on cohort+multi only | `decisions.md` 2026-10-08 review item 6 |
| 39 | **Architecture vs information confound**: cells B (sentence→SQL + conventions), D (plan→SQL + conventions, no per-mode rule) and E (plan-checked replan) | experiment | **measured at 7B/32B 2026-10-08** (decisions.md A-E grid): at 32B conventions +0.14, explicit plan +0.14, per-mode rule +0.10, one verification round +0.05 and leak 0.41→0.15; Opus column on hold (advisor q3). Next: per-stage verify-and-repair rounds (adopted) | `decisions.md` 2026-10-08 |
| 40 | **Slice drift**: v1 vs v1.1 smoke slices share 104/200 instances; all Opus S2 rows are v1 | bookkeeping | **default changed 2026-10-08** (`--release` = v1.2); every row from here is on `smoke_200_v1.2_s0`; the Opus rows are re-run on the v1.2 slice when the API opens | `decisions.md` IMPLEMENTED 10-08 |
| 41 | **Per-stage verify-and-repair rounds** (S1 conventions-consistency, S2 executor-error + plan-consistency re-ask, S3 rule validity), bounded; rounds=0 capability row, rounds=k system row | build | **BUILT + MEASURED 2026-10-08** (`--verify-rounds`): S1 r1 +0.04 (32B) / +0.14 (7B), r2 nothing; S2 r2 +0.03 at 32B; e2e-D 32B 0.665 -> 0.750. Settings: S1 1 round, S2 2 rounds | `decisions.md` 2026-10-08 |
| 36 | **S2 stipulation-attribution profile + faithfulness score** (`scripts/s2_attribution.py`): name the violated rule for every wrong denominator; report P(stages right \| verdict right) beside accuracy | analysis | **adopted 2026-10-06**; first table in the draft; run on eval_core and on the Opus e2e-sql run next | `decisions.md` 10-06 |
| 37 | **Abstention metrics**: false-decisiveness, over-abstention, insufficient-subtype accuracy | analysis | adopted 2026-10-06; implement in `evaluate.py` | `decisions.md` 10-06 |
| 38 | **Pretraining knowledge of VAERS**: closed-book verdicts across model vintages, counterfactual control, report-id recall | experiment | open 2026-10-06 — design pending; decides whether frontier S1/S2 numbers owe anything to priors | `decisions.md` 10-06 |
| 34 | **External systems as baselines** (EHRAgent, EHRSQL-protocol S2, StatQA-style S3, VERITAS A/B/C) on MedTempo, local 32B | experiment | **measured 2026-09-29, then STOPPED** (11 §10.3d): all near chance, all fail at the denominator. Not yet commensurate: 32B vs our Opus rows, and no toolbox card given. Re-run only after v1.2, with the task card as each system's data description and matched model tiers; VERITAS C never ran; use the authors' 3600 s cap | `11` §10.3d; draft "External systems" |

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

## Session summary 2026-09-29/30 — S1 reframed, toolbox built and measured (branch `s1-toolbox`)

**Where the discussion went.** Starting question: how to do better on S1. The
error taxonomy of the best catalogue run (7B, 54 errors / 400) showed one group
(P-R2) carrying a third of them and 25/38 mode errors sitting on records whose
GIVEN fields already pinned the mode — a lever for the *system*, but then the
harder point: the catalogue prompt hands the model the answer (test, null, H0,
conditioning per mode), so S1 "accuracy" was mode classification + lookup, not
formulation. That led to the reframing now in `decisions.md` (2026-09-29):

1. **State every stipulation, withhold only the mapping.** Conventions
   (co-exist exclusion, tie drop, presence split, first mention, floors, alpha)
   are dataset stipulations, not entailed by sentences — the audit's 176/501
   P-V1 label flips under the alternative reading prove it — so they are stated
   (phrased by situation), and only the 20-row mode mapping is withheld. e2e-sql
   (§10.3b) is re-read accordingly: it measured convention-guessing.
2. **S1 output is a conditional plan**: quantity / denominator primitive / arms
   / null RECIPE (symmetric-fixed, text-stated, data-derived, two-arm equality)
   / tail / test FAMILY + selection RULE resolved by S3 on the retrieved counts
   / gate. "Exact tests only" becomes "every gold-producing test must be valid at
   the instance's n" (guards, 11 §13.4). `answer_type` stays an input field.
3. **Null diversity is the dataset expansion** (issue 32 → v1.2): N1 position
   with the data-derived structural null (the one null that cannot be looked
   up), N3/N4 text bars, N2 succession — doc 10's candidates, screens done.
4. The related-work read (11 §12): P-Bench/Fisher-R1, LATCH, StatFormBench,
   StatABench, DiscoveryBench/BLADE. None combines model-formulated nulls +
   deterministic execution + per-stage gold; none poses event-ORDER claims; none
   scores the denominator. The system loop itself is not the novelty — the
   grounded instrument is. P-Bench with H0 hidden is the external validation.

**Built (11 §11a; 604 tests).** `--s1-frame toolbox`: computed dataset card
(`extract/task_card.py`), catalogue-free prompt (a test proves no mode/group/H0
leaks), `PLAN_JSON_SCHEMA`, `derive_mode` reverse lookup (unique after adding
`extreme`), `normalize_plan_shape` / `normalize_plan` filling only IMPLIED
fields, rule resolution in S3 (Fisher vs one-sided two-proportion z, guard
min expected cell >= 5), plan scoring + `rule_valid`, few-shot as the P1/P2
dial, `.env` key loading, `rescore` reading the release from the run config.

**Measured (v1.1 smoke slice, 400 records, blind-group, procedure-blind).**

| S1 condition | 7B | claude-opus-5 |
|---|--:|--:|
| catalogue + hints (lookup; upper bound) | 0.918 | 1.000 |
| toolbox, 3 few-shot plans | 0.64–0.68 (wording-sensitive) | 1.000 (claim EM 1.000; plan EM 0.985) |
| **toolbox, zero-shot (the headline condition)** | **0.490** (claim EM 0.487; plan EM 0.122; 179 plans match no mode) — few-shot was propping the 7B up too (0.64–0.68 → 0.49); zero-shot it composes almost nothing (rule_valid 0.258) | **0.958** (claim EM 0.910; plan EM 0.812; rule_valid 0.943) — all 36 mode errors are two shapes: C-V2 association composed as plain co-occurrence (22; arms 1 / both_present — the family e2e-sql found unrecoverable from the sentence) and P-V2 antecedent composed as the four-event pair-vs-pair (14). Both are exactly the shapes the 3 few-shot plans had covered (assoc_bool, antecedent_bool), which is why removing them cost 4 points |

Readings: the compose gap is model-tier (7B loses 25–30 points, Opus ~0);
three worked examples were worth ~4 verdict / ~9 claim-EM points to Opus, i.e.
few-shot DOES leak the mapping, so zero-shot is the headline and few-shot a
reported dial; P2 group-holdout is downgraded (with zero-shot no group has an
example); v1.2 null diversity is the critical path for any remaining S1
difficulty at the frontier. Harness lessons: two toolbox versions lost 232/170
records to a reverse lookup stricter than the semantics and a schema null
escape — fixed by implied-field normalization, never by consulting the answer.

**Operational.** Branches cleaned to `main` = `model-pipeline-design` (frozen
paper line) + `s1-toolbox` (next-step work); candidate templates + screening
harness committed to the main line; the lab Anthropic key lives in the
gitignored `.env` (loaded by `run_eval.py`); VERITAS baselines on the other
machine kept for the record (rule: S2/S3 and upper-bound rows stay valid;
catalogue-S1 capability claims are superseded).

**Next, in order.** (1) 7B zero-shot recorded (0.490); (2) **v1.2 build** (issue
32; doc 10 §7.2 order: N1 structural null → N3/N4 bars → N2) + B0 re-cert;
(3) zero-shot toolbox on v1.2 (7B + Opus); (4) P-Bench external validation
(issue 33); (5) full `eval_core` under zero-shot toolbox for the paper table.

## §1a Experiment queue (frozen 2026-09-04, run AFTER the dataset is stabilized)

Priority order agreed at the 09-03/09-04 review; every strong number so far is on
the SCAFFOLDED task (mode catalogue, DDL, conditioning prose, floors all given,
in-distribution text) — these runs are what turn it into a paper:

> **Reordered 2026-09-30** (see the session summary above): zero-shot toolbox is
> the S1 headline; v1.2 null diversity is the critical path; P2 folds are
> downgraded. Items below keep their original numbering.

1. **Single-pass (B3) + in-context (B1) baselines with a frontier model** — the
   motivating claim. If frontier fails without the decomposition, the framework
   is the story; if it passes, the benchmark is too easy and we need to know.
2. **P1 (register-holdout) and P2 (group-holdout) protocols** with the prompted
   extractor (constrain the k-shot pool) — the only generalization evidence.
3. **Frontier failure analysis** — categorize smoke-4/5 residuals (genuine
   hardness vs issue-24 ambiguity) for the error-analysis section.
4. Fill the model×stage grid: opus-S1-only and opus-both (~$20).
5. Full `eval_core` runs for the paper table (~$40 at smoke-4 rates).
6. M3 fine-tune only if the above leaves it a role.

## §1b Server run plan (2026-09-29) — what to run on the multi-GPU box, and how

Branches: `model-pipeline-design` = the frozen line every number in 11 §10.3
comes from (also `main`, fast-forwarded 2026-09-29). `s1-toolbox` = next-step
work (issues 29, 31, 32, 33). Run paper numbers from `model-pipeline-design`;
run toolbox experiments from `s1-toolbox` once it has code.

### Environment (once per machine)
```
git clone <repo> && cd Temporal_Hypothesis_Generation && git checkout model-pipeline-design
python3.13 -m venv .venv313 && .venv313/bin/pip install -e ".[dev]"   # SQLite >= 3.44 required (issue 12)
.venv313/bin/pytest -q -m "not slow"                                   # expect ~530 passed
python scripts/build_eval_db.py                                        # -> data/medtempo_eval.db (narrative-free)
# local models (Ollama; one server per GPU for parallel runs):
ollama pull qwen2.5:7b-instruct && ollama pull qwen2.5-coder:7b
CUDA_VISIBLE_DEVICES=0 OLLAMA_HOST=127.0.0.1:11434 ollama serve &
CUDA_VISIBLE_DEVICES=1 OLLAMA_HOST=127.0.0.1:11435 ollama serve &      # ... pass --ollama-url per run
# API models: export ANTHROPIC_API_KEY / OPENAI_API_KEY, or pass --ask-api-key (hidden prompt)
```
Release = `data/release/v1.1`; subsets `results/subsets/eval_core_v1.1_pg90_s0.json`
(1,649 instances) and `smoke_200_v1.1_s0.json` (200). Every run writes
`config.json` (model digests, shas), `predictions.jsonl`, `metrics.json`,
`report.md`; re-score with `scripts/rescore.py --run <dir> --min-group-size 6`
(smokes) or default 30 (eval_core). Responses are cached under `results/cache/`
keyed on (model, prompt) -- reruns and mixed-provider runs replay for free.
Measured rates: 7B ≈ 3.3 s/record on one GPU (400 records ≈ 22 min); Opus-5 SQL
≈ $9 / 400 records; Opus-5 S1 ≈ $6 / 400 records.

Common tail for every run below (blind-group, model fills the procedure):
`--condition blind-group --procedure blind --registers original --formats question,claim`
(drop `--registers original` for all four registers = 4x the records).

### Runnable NOW (no new code)
| id | command (add the common tail) | needs | time / cost | reports |
|---|---|---|---|---|
| R1 upper bound, paper scale | `run_eval.py --pipeline llm-s1+compiler --model qwen2.5:7b-instruct --tier-hint --routing-hint --subset eval_core --out results/ec_s1_7b` | 1 GPU | ~3 h (original) / ~12 h (all registers; split by `--registers` across GPUs) | the `procedure-given`-style ceiling row at 1,649 instances (catalogue S1; see decisions 09-29 -- NOT a capability number) |
| R2 S2 ceiling, paper scale | `run_eval.py --pipeline rules+llm-sql --sql-provider anthropic --model claude-opus-5 --subset eval_core --out results/ec_rules_opus-sql` | API | ~$75, ~2 h | smoke-4 at scale |
| R3 deployment mix, paper scale | `... --pipeline llm-s1+llm-sql --provider ollama --sql-provider anthropic --model qwen2.5:7b-instruct --sql-model claude-opus-5 --tier-hint --routing-hint --subset eval_core` | 1 GPU + API | S1 replays from R1's cache; ~$75 | smoke-5 at scale |
| R4 grid cells | opus S1-only: `--pipeline llm-s1+compiler --provider anthropic --model claude-opus-5 --subset results/subsets/smoke_200_v1.1_s0.json`; opus both: `--pipeline llm-s1+llm-sql --provider anthropic --model claude-opus-5 ...` | API | ~$6 + ~$15 | completes the model x stage grid (11 §10.3) |
| R5 null-hints ablation | R1/R4 commands `+ --hide-null-hints` | GPU / API | as above | issue 27 -- NOTE 11 §10.3c: still leaks conditioning per mode; the toolbox frame (issue 29) is the real condition |
| R6 P1 register holdout | R1 with `--registers research` (and media, clinical) and the k-shot pool restricted to the other registers (`--k-shot-registers`, small flag if absent) | 1 GPU each | ~3 h per register | paraphrase robustness (11 §4 P1) |

### After the toolbox frame lands (branch `s1-toolbox`)
| id | what | needs | notes |
|---|---|---|---|
| T1 | DONE 2026-09-30: 7B 0.680 (`v11_smoke200_toolbox_v4_7b`), Opus **1.000** (`v11_smoke200_toolbox_opus_v4`, ~$15.6 -- the toolbox prompt + 3 few-shot plans is ~5.9K tokens/call); lookup rows 0.918 / 1.000 | -- | model-tier gap; next is T2 (P2 under the toolbox, Opus, ~$16) |
| T2 | P2 group holdout under toolbox (k-shot pool excludes the held-out group; 20 folds) | GPU | the only fair S1 head-to-head vs classification (which is at 0 on held-out groups) |
| T3 | P-Bench external: hide H0, score the formulated null; Fisher-family subset through our executor | API | issue 33; needs a P-Bench loader (small) |
| T4 | single-pass frontier baseline (B3): hypothesis + cohort dump -> verdict | API | queue item 1; needs the cohort-dump exporter (11 §5 `docs.py`) |
| T5 | v1.2 (issue 32) regeneration + B0 re-certification (`--pipeline oracle --subset all`, ~9 min CPU) before any T-run on it | CPU | existing groups' instances unchanged; new groups only |

What stays valid across the reframing: every S2/S3 number (R2, R3's SQL side)
and every ceiling row; what gets superseded: S1 capability claims made from the
catalogue prompt (they become upper-bound rows). Kill in-flight runs only if they
are catalogue-S1 *capability* measurements (P2 with the catalogue, local 7B
single-pass, classifier fine-tunes).

## Where the code now stands

| | |
|---|---|
| Roster as coded | **20 groups** = 7 report-level + 12 single-cohort + P-M2 (migration A COMPLETE 2026-08-14; P-V2/P-V4/C-V2 all cleared their 2000-round screens at p_perm 0.0005 — roster FINAL) |
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
| Gold-label validation | six invariant families incl. per-arm DB recomputation for the new modes; **exhaustive run on v1.1 clean 2026-09-21** (`validate_gold --sample 0`, 43,618 realized instances, all six families) — dataset FROZEN, §1a queue unblocked |
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
