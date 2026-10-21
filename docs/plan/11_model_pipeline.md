# Model Pipeline — the eval harness from hypothesis text to verdict, and how it is scored

Branch `model-pipeline-design`, 2026-09-01. Answers issue 3 of `09_next_steps.md`
(the eval harness, "not started" since the register opened). Companion to
`decisions.md` "LOCKED: model pipeline / eval-harness architecture (2026-09-01)",
which records the decisions; this doc carries the reasoning, the contracts and the
numbers. Every count below was re-measured against `data/release/v1` on the date
above: 147,936 records / 18,492 instances / 8,964 distinct facts / 6,664 mirror
pairs; verdicts 6,845 supported / 6,783 refuted / 4,864 insufficient
(1,630 `not_locatable`, 1,505 `sparse`, 1,729 `underpowered`).

Scope of this session (user decision 2026-09-01, revised at plan review: "implement
for local only; stop at text-to-SQL; do eval on the local setup"): this design
**plus** M1 (deterministic chain) and M2 (local-LLM extraction and local-LLM
text-to-SQL, evaluated end-to-end with a local model). M3–M5 are designed here and
not built. Code lives in `src/temporal_hypo/framework/`, tests in `tests/framework/`.

---

## 1. What is actually under test — honest framing

The benchmark's surface variation is **register × format and nothing else**. The 20
groups carry 184 template strings (182 distinct; `templates.load_groups()`): 4
registers × {question, claim} per group, plus a negated pair for the three symmetric
co-occurs groups (C-V1, C-V2, C-V3 — 24 negated strings). Event slots are filled with
verbatim MedDRA terms — **0 out-of-vocabulary terms across 147,936 rows** against the
1,660 terms in `level_terms` — the vaccine slot draws from a 3-word set, and the
report slot is `VAERS-{id}`. So on in-distribution text, stage 1 is a lookup: a regex
per template recovers the gold claim exactly on **145,644 records**; the remaining
**2,292** (C-V3 research + clinical 2,088; F-V3 research 204) never name the events
at all and no method can recover them (§2.1, `underdetermined`).

What the harness therefore measures, in order of how much of the score each can move:

| capability | where it is scored | evidence it rests on |
|---|---|---|
| (a) **conditioning / retrieval** — the per-family denominator rule (precedes excludes co-exist; sequence needs three distinct levels; first/last drops ties; first-mention positions) | S2 set-F1 vs `evidence_ids`, `coexist_leak` | the gold id sets ship in the answers file |
| (b) **the three-decision rule + min-n gate** — `supported` needs p_claim < α, `refuted` needs p_opposite < α, floors 10 / 5 | S3 `(n,k)` EM, p-agreement, verdict, sub-type recall | oracle reproduces every label from `(mode, family, n, k, n2, k2, counts, named)` |
| (c) **`not_locatable` fabrication resistance** — zero-joint combinations must yield an empty denominator, not invented reports | retrieval FPR on the 1,630 `not_locatable` instances | seeded false combinations (issue 5) |
| (d) **negation handling** — C-V1 252 / C-V2 349 / C-V3 174 negated instances swap the tails | `negated_acc`, verdict on negated rows | `oriented_significance` |
| (e) **NL → procedure generalization** — reading an unseen wording and choosing the right test, null and conditioning | **only** under the held-out protocols P1 / P3 (§4) | not evidenced by P0 |

Say it plainly in the paper: **P0 (all 182 forms seen) cannot evidence (e)**. A
model that has seen every template string is being tested on retrieval and
statistics, not on language. The generalization claim rests on P1 (a whole register
of held-out facts unseen) and P3 (paraphrases that never appear as benchmark text,
authorship pending — issue 26). The deterministic B0 baseline at 100% is the
demonstration that the harness is correct, *not* that the text entails the label
(issue 24 is the live caveat on that: P-V2/P-V4 wording is count language over a
rate statistic on 273 / 2,194 instances).

---

## 2. Pipeline contract

```
question row (INPUT_FIELDS only) ──S1──► StructuredClaim ──S2──► per-arm ArmRows ──S3──► Prediction ──S4──► metrics
                                  extract               compile / LLM-SQL         aggregate + test        evaluate
```

Each stage is a pure function of the previous stage's output plus the eval DB. Any
stage can be replaced by its gold value (**gold-forcing**, §7.3), which is how the
per-stage failure rates are made marginal rather than conditional.

### 2.1 Input and the two conditions

The input is a question row carrying **only** `instances.INPUT_FIELDS`:
`hypothesis_id, group_id, level, answer_type, register, format, text, options,
cohort{level, vaccines[], report_id}`. Gold comes from the answers file via
`Release.answer_for(hypothesis_id)` (`instance_id = hypothesis_id.rsplit("-", 2)[0]`)
and is never on the model's side of the boundary.

Two conditions (`extract/__init__.py::visible_fields`):

| condition | visible fields | what it removes |
|---|---|---|
| `given-group` | `group_id, level, answer_type, register, format, text, options, cohort` | nothing — the mode is a lookup from `group_id` |
| `blind-group` | `level, answer_type, register, format, text, options, cohort` | `group_id`; `hypothesis_id` is treated as opaque (it embeds the group prefix) |

What stays visible in `blind-group` still carries structure, and the doc should be
exact about how much (measured on all 147,936 rows): `level` pins the **tier** for
100% of records; for every **CHOICE** row the `options` shape pins the family too
(2 event options → pairwise, 3 → first/last, 6 orderings → sequence, 2 vaccines →
the multi tier). For **BOOL** rows — 126,864 of 147,936, 85.8% — the non-text
fields do *not* separate pairwise / sequence / first_last, so the family and the
mode have to come from the text. `blind-group` withholds the label, not the tier;
its 20 × 20 mode-confusion matrix is the S1 result that matters.

Cohort identification is **given**, not under test: `cohort` is structured in the
input, and the claim's `CohortSpec` is filled from it (`claim_from_flat`,
`build_claim`). The text names the vaccine too, so an extractor that disagrees with
`cohort` is scored on `cohort_em`, but the SQL always binds the given cohort.

### 2.2 Floors and alpha are always given

The min-n floors (10; sequence 5) and alpha (0.05 per side) are in every prompt, in
`procedure-blind` and `procedure-given` alike. `05_significance_tests.md` ("Shared
min-n helper") designed the gate to be **shared by both sides**; withholding it
would make the **3,234 `sparse` + `underpowered` instances (17.5%)** unwinnable for
a reason that has nothing to do with the capability. What the model must supply is
the test, the null, the tail, the number of arms and the conditioning rule.

### 2.3 `StructuredClaim` — the S1 output (`framework/claim_schema.py`)

Two layers. The WHAT layer is the identity of the claim and must come from the
text; the HOW layer (`Procedure`) is the statistical procedure the claim requires
and is a pure function of `(mode, negated)` through `derive_procedure`. Extractors
may fill the HOW layer (so null-choice and test/tail errors are measurable) or
leave it to be derived. The dataclasses, copied from the module:

```python
TIERS = ("report", "vaccine", "multi")
FAMILIES = ("pairwise", "sequence", "first_last")   # == YAML top-level family; C-* are pairwise
PRIMITIVES = ("precedes", "co_occurs", "sequence", "first_last")
ANSWER_TYPES = ("BOOL", "CHOICE")
ROLES = ("A", "B", "C", "D")
TESTS = ("binom_exact", "modal_runner", "fisher_exact")
NULL_KINDS = ("binomial", "two_arm_equality", "none")
STATISTICS = ("conditioned_proportion", "named_vs_runner_up",
              "rate_arm1_vs_arm2", "single_observation")
TAILS = ("greater", "less")
CONDITIONINGS = (
    "ordered_pair",              # both present at DISTINCT levels; co-exist excluded
    "both_present",              # both present; co-exist is the numerator (or a cell)
    "orderable_triple",          # all three present at pairwise-distinct levels
    "all_present_unique_first",  # all candidates present, unique earliest; ties dropped
    "all_present_unique_last",   # all candidates present, unique latest; ties dropped
    "presence_split",            # whole cohort split on presence of A
    "single_report",             # the one report; first-mention levels of the events
)
VERDICTS = ("supported", "refuted", "insufficient")
UNDERDETERMINED = "underdetermined"       # the harness's fourth response token
RESPONSES = VERDICTS + (UNDERDETERMINED,)
MODES = tuple(sorted(set(MODE_BY_GROUP.values())))   # the 20 statistic keys

@dataclass(frozen=True)
class EventSlot:
    role: str                 # "A" | "B" | "C" | "D" -- the slot as the TEXT names it
    term: str | None          # verbatim MedDRA term; None => not recoverable from the input

@dataclass(frozen=True)
class CohortSpec:
    vaccine: str | None       # Pfizer | Moderna | Janssen | None (report tier)
    report_id: int | None     # VAERS id (== reports.vaers_id), report tier only

@dataclass(frozen=True)
class NullSpec:
    kind: str                 # binomial | two_arm_equality | none
    p0: float | None          # 0.5 for binomial; None otherwise
    statistic: str            # conditioned_proportion | named_vs_runner_up | rate_arm1_vs_arm2 | single_observation

@dataclass(frozen=True)
class Procedure:
    """The HOW layer: what test the claim requires and how it is run."""
    test: str | None          # binom_exact | modal_runner | fisher_exact | None (report tier)
    null: NullSpec
    claim_tail: str           # "greater" for the plain claim, "less" when negated
    alpha: float
    min_n_floor: int | None   # family floor; None at report tier
    arms: int                 # 1 | 2
    conditioning: str         # one of CONDITIONINGS

@dataclass(frozen=True)
class StructuredClaim:
    # WHAT
    tier: str
    family: str
    primitive: str
    mode: str
    events: tuple[EventSlot, ...]        # ORDERED as the text asserts
    cohorts: tuple[CohortSpec, ...]      # 1 (vaccine or report) | 2 (P-M2, v1 then v2)
    negated: bool
    answer_type: str
    options: tuple[str, ...] | None
    asserted_option: str | None          # CHOICE: the option the text asserts (None if unstated)
    # HOW
    procedure: Procedure
    # bookkeeping (never scored)
    source: str = "unknown"              # "rules" | "llm:<model>" | "gold" | ...
    underdetermined: tuple[str, ...] = ()  # roles whose term the input does not determine
    confidence: float | None = None
    raw: dict | None = field(default=None, compare=False)   # extractor's raw output
```

Derived views: `terms`, `spec` (the `ModeSpec` row), `is_underdetermined`,
`vaccines`, `report_id`, `named_cell()` (the key the oracle's `counts` dict uses: a
term tuple for the sequence modes, the named event's term for first/last,
`"co_exist"` for C-V3, None otherwise), `what_key()` for exact-match scoring,
`to_dict / to_json / from_dict / from_json`, `with_procedure`.

- **`MODE_SPEC`** is the single table behind everything — one `ModeSpec(mode, tier,
  family, primitive, answer_type, n_events, arms, conditioning, test, null_kind,
  statistic, named_cell_kind)` row per mode. `derive_procedure(mode, negated)` reads
  it; a test asserts it against `answers._BINOM_NULL / _MODAL_RUNNER / _FISHER` and
  the `cooc_modal_bool` special case so it cannot drift. `family` is the YAML
  top-level family — `pairwise | sequence | first_last`, never `co_occurs`; the C-*
  groups ship `family = pairwise` and `primitive = co_occurs`.
- **`claim_tail`** is `"greater"` for every plain claim (the asserted direction is
  carried by the event/arm ORDER) and `"less"` when negated — exactly the tail swap
  `core.answers.oriented_significance` applies. Negated wording exists only for
  `sym_bool_cooccurs`, `assoc_bool`, `cooc_modal_bool` (`NEGATABLE_MODES`).
- **`from_gold(answer_row)`** builds the reference claim from `mode`,
  `factual_core.events` (ORIENTED as the text names them), `cohort`, `negated`,
  `options` — the free training label and the thing every extractor is scored
  against. **`validate(claim)`** lists inconsistencies between the layers and the
  spec; it records, never corrects.
- **`FLAT_JSON_SCHEMA`** is the LLM-facing shape (`mode`, `events`, `negated`
  required; `asserted_option`, `test`, `null_kind`, `p0`, `claim_tail`, `arms`,
  `conditioning`, `min_n_floor` optional); `claim_from_flat(flat, question_row,
  source=, procedure_given=)` folds it into a claim, pads or trims a wrong-arity
  event list so the row is still scored, and with `procedure_given=True`
  overrides the HOW layer with the reference (the `procedure-given` mode).
- The gold NL null string per mode is reused from
  `scripts/make_examples.py::_null_hypothesis` (see §3.2 for the four modes it
  does not cover).

### 2.4 The arm row contract and the compile table (`framework/sql/aggregate.py`)

Every retrieval method — the reference compiler and a model's SQL alike — returns,
**per arm**, rows of exactly this shape (`ARM_COLUMNS`):

```
(vaers_id, in_denominator, in_numerator, excluded, cell)
```

`vaers_id` is the release's report id, never the DB surrogate. `cell` is the
report's cell in the argmax table (a winner term, an ordering label `A|B|C` in the
asserted spelling joined by `ORDERING_SEP`, or `before/after/co_exist`) and is
**NULL for every row with `in_denominator = 0`**; `aggregate()` builds `counts`
from denominator rows only. The reason is mechanical: `answers._named_counts` takes
`max` over every non-named key of `counts`, so a tie bucket leaking in as a cell
corrupts every argmax p-value. Test: `sum(counts.values()) == n` for every argmax
mode. Report-tier retrieval has a different shape — `(term, level)` rows for the one
report, folded by `report_levels` into `{term: first-mention level}`.

The compile table restates `generation/evidence.py::evidence_ids` as data. Levels
`lA, lB, ...` are first-mention levels of the claim's events in one cohort report;
"present" means the term occurs in the report at all.

| mode(s) | group(s) | arms | denominator (n) | numerator (k) | excluded | `cell` (denominator rows only) |
|---|---|---|---|---|---|---|
| `dir_bool`, `dir_choice` | P-V1, P-V3 | 1 | A and B present, lA ≠ lB | lA < lB | lA = lB (co-exist) | — |
| `sym_bool_cooccurs` | C-V1 | 1 | A and B present | lA = lB | none | — |
| `cooc_modal_bool` | C-V3 | 1 | A and B present | lA = lB (named cell `co_exist`) | none | `before` / `after` / `co_exist` |
| `seq_bool`, `modal_choice` | S-V1, S-V3 | 1 | A, B, C present at pairwise-distinct levels | lA < lB < lC | two or more share a level | ordering of the TERMS sorted by level, `X|Y|Z` |
| `first_choice`, `first_bool` | F-V1, F-V3 | 1 | A, B, C present, unique earliest | earliest = A | tie for earliest | the winner term |
| `last_choice` | F-V2 | 1 | A, B, C present, unique latest | latest = A | tie for latest | the winner term |
| `antecedent_bool` | P-V2 | 2 | arm 1: (A, B) ordered pair; arm 2: (C, B) ordered pair | lA < lB; lC < lB | co-exist, per arm | — |
| `pairpair_bool` | P-V4 | 2 | arm 1: (A, B); arm 2: (C, D) ordered pairs | lA < lB; lC < lD | co-exist, per arm | — |
| `assoc_bool` | C-V2 | 2 | arm 1: cohort reports containing A; arm 2: cohort reports NOT containing A | B present | none | — |
| `multi_dir_precedes` | P-M2 | 2 | (A, B) ordered pair in v1; the same in v2 | lA < lB, per arm | co-exist, per arm | — |
| `rep_dir_bool`, `rep_dir_choice`, `rep_sym_bool`, `rep_seq_bool`, `rep_first_choice`, `rep_last_choice`, `rep_first_bool` | P-R1, P-R2, C-R1, S-R1, F-R1, F-R2, F-R3 | report | the one report: `(term, level)` for the named events, first mention | — | — | — |

Two-arm modes list arm 1 then arm 2 in the claim's asserted order; the canonical
claim for all four is "arm 1's rate exceeds arm 2's". Sequence, first/last and
`cooc_modal_bool` are the argmax modes; their `counts` must cover the whole
denominator.

---

## 3. Stage 1 — extraction methods (interchangeable, same output)

All extractors implement `extract/__init__.py::Extractor`:
`name: str; extract(question_row, *, blind_group=False) -> StructuredClaim | None`.
`None` means "no parse"; a claim with `underdetermined` roles means "parsed, but the
input does not name these events".

### 3.1 Rules parser (`extract/rules.py`) — M1, the B0 component

A regex per template string from `templates.load_groups()`: literals escaped, the
first occurrence of `{X}` → `(?P<X>.+?)`, every repeat → **`(?P=X)`** (25 distinct
strings — 26 template slots — repeat an event slot, e.g. S-V1 *"is {A} → {B} → {C}
the most common ordering of {A}, {B}, {C}"*), anchored `^…$`, longest-literal
patterns tried first. Vocabulary validation makes the parse unambiguous and makes
negation detection free: every event slot must be one of the 1,660 DB terms
(`vocabulary_from_db`), `{v}` ∈ `VACCINES`, `{r}` matches `VAERS-(\d+)`. Lossy
templates are filled from the structured fields that are visible in both
conditions: `{r}` from `cohort.report_id` (missing in the non-original registers),
`{v2}` from `cohort.vaccines[1]` (missing in the P-M2 clinical claim), `{B}`/`{C}`
from `options` (missing in some CHOICE claims). The **two identical strings across
groups** — `'In this case, {A} came first.'` (P-R2 media claim / F-R1 media claim)
and `'In this report, {A} is the earliest of {A}, {B}, {C}.'` (F-R1 / F-R3 research
claim) — are disambiguated by `answer_type` and `len(options)`. Parses are invariant
to option permutation (§7.2). In `given-group` only that group's patterns are tried;
in `blind-group` all 184, narrowed by `register` / `format` (visible in both).

Unrecoverable: C-V3 research + clinical (2,088 rows) and F-V3 research (204 rows)
never name A / B — **2,292 rows → `EventSlot(term=None)`, `underdetermined`**.

### 3.2 Prompted local LLM (`extract/llm.py`, `extract/llm_client.py`) — M2

Prompt = task statement + the 20-mode catalogue (`pilot.RULE_BY_MODE` rule prose,
the `MODE_SPEC` fields, and the H0 wording per mode) + the floors and alpha +
`FLAT_JSON_SCHEMA` + k few-shot examples rendered from `from_gold` rows drawn
**outside the eval set** (`subsets.fewshot_pool`) + the visible fields of the row.
One JSON-repair retry; vocabulary snapping by **exact match only** (no fuzzy
snapping — a misspelled term is a wrong term). Two procedure modes:
**`procedure-blind`** (the model fills the HOW layer; scored) and
**`procedure-given`** (`claim_from_flat(..., procedure_given=True)`; isolates WHAT).

H0 strings: `scripts/make_examples.py::_null_hypothesis` covers 16 of the 20 modes
and returns `"H0: (unspecified)"` for the four 2026-08-14 additions and C-V3's
argmax form, so the prompt builder must carry these four itself (same style):

| mode | H0 wording to use |
|---|---|
| `cooc_modal_bool` | H0: co-exist and the runner-up relation (before or after) are equally frequent (P = 0.5; co-exist is not the unique modal relation) |
| `antecedent_bool` | H0: P(B follows A \| A,B ordered) = P(B follows C \| C,B ordered) (p1 = p2) |
| `pairpair_bool` | H0: P(A before B \| A,B ordered) = P(C before D \| C,D ordered) (p1 = p2) |
| `assoc_bool` | H0: P(B \| A present) = P(B \| A absent) (p1 = p2; no association) |

Provider adapter: `Provider.complete(messages, *, schema, model, temperature=0,
max_tokens) -> Completion(text, prompt_tokens, completion_tokens, ms, cached)`.
Local backend first — `OllamaClient` over stdlib `urllib` to
`http://localhost:11434/api/chat` with `format` = the JSON schema and temperature 0;
`anthropic` / `openai` adapters **built 2026-09-02** behind the same protocol (`llm_client.client_for`; CLI `--provider` / `--sql-provider`, keys from `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`; structured output via forced tool call / `response_format=json_schema`). Disk cache under
`results/cache/` keyed sha256(model + messages + schema), so a re-run is free and
deterministic. **Runtime decision:** Ollama (`winget install Ollama.Ollama`),
`qwen2.5:7b-instruct` (Q4_K_M, ~4.7 GB — fits the 16 GB GPU with headroom) for both
extraction and SQL; `qwen2.5-coder:7b` as the optional second SQL model. Throughput
estimate ~3–5 s per call → a 200-instance smoke (≈400 calls) ≈ 25 min per pipeline;
full `eval-core` (≈2,800 calls) ≈ 3 h per pipeline, run in the background.

### 3.3 Fine-tuned extractor (`extract/finetune.py`) — M3, designed only

Pairs `text (+ options + cohort) → compact WHAT-layer JSON` from `from_gold`; the
HOW layer is always derived (the fine-tune measures reading, not statistics).
Models sized for 16 GB: `google/flan-t5-base` (250M, seq2seq) primary;
`Qwen2.5-0.5B / 1.5B-Instruct` + LoRA (fp16 — **no bitsandbytes on Windows**)
secondary. **The RTX 5060 Ti is Blackwell (sm_120): torch ≥ 2.7 / CUDA 12.8 wheels.**
CPU fallback so the row is never empty: a char-n-gram nearest-template classifier —
which will hit ~100% on P0, itself the finding of §1. Needs the split (§8).

---

## 4. Leakage protocols — what each measures

Every instance's 8 texts share one gold row, so a register holdout that keeps the
fact on the train side measures nothing: the model has seen the same fact under
three other wordings. **Register holdout must be fact ∧ register.**

| protocol | train | test | measures |
|---|---|---|---|
| P0 `fact_split` | train facts, all registers | test facts, all registers | sanity floor only; all 182 forms seen |
| P1 `fact ∧ register` | registers {r1, r2, r3} of train facts | register r4 of **test** facts (× 4 folds) | paraphrase robustness — **the reported generalization number** |
| P2 `fact ∧ group` | 19 groups, minus every `fact_id` that appears in the held-out group | the held-out group (964 facts span two groups via twins; for P-V3 this removes all 334) | procedure inference for a novel shape; score the HOW layer + slots, not the mode string |
| P3 `novel_paraphrase` | full train | ~200 hand-authored (or eval-only LLM-authored — **user decision, issue 26**) rewrites, never benchmark text | true out-of-template generalization |

P0–P2 need the provisional split (§8) and therefore land with M3. P3 needs the
authorship decision first.

---

## 5. Stage 2 — text-to-SQL retrieval

### 5.1 The eval DB (`framework/sql/views.sql`, `build_eval_db.py`, `scripts/build_eval_db.py`)

`data/medtempo_eval.db` is built from `data/medtempo.db` (3,166 reports — Janssen
1,164 / Pfizer 1,019 / Moderna 983; 22,681 `level_terms` rows; 1,660 terms) and is
the **only** database the harness opens. It is keyed on `vaers_id`, drops the
surrogate `reports.report_id` and the `narrative` column, and puts the first-mention
rule in a view so a model cannot get it wrong by forgetting it. The DDL file is what
models see verbatim; the sketch:

```sql
-- framework/sql/views.sql is authoritative; this is its shape.
CREATE TABLE reports (
  vaers_id    INTEGER PRIMARY KEY,      -- the release's report id; no surrogate key
  vaccine     TEXT    NOT NULL,         -- 'Pfizer' | 'Moderna' | 'Janssen'
  num_stages  INTEGER NOT NULL          -- raw `num_groups`, relabelled (issue 11)
);                                      -- NO narrative column
CREATE TABLE level_terms (
  vaers_id    INTEGER NOT NULL REFERENCES reports(vaers_id),
  level_index INTEGER NOT NULL,         -- 0 = earliest stage of the leveled order
  term        TEXT    NOT NULL          -- verbatim MedDRA term
);
CREATE INDEX idx_lt_vid  ON level_terms(vaers_id);
CREATE INDEX idx_lt_term ON level_terms(term, vaers_id);
CREATE INDEX idx_r_vax   ON reports(vaccine);
-- a term's position is its FIRST mention (7 (report, term) pairs sit at two levels)
CREATE VIEW first_mention AS
  SELECT lt.vaers_id, r.vaccine, lt.term, MIN(lt.level_index) AS level
  FROM level_terms lt JOIN reports r USING (vaers_id)
  GROUP BY lt.vaers_id, lt.term;
-- one row per (report, stage): the stage's terms sorted and joined
CREATE VIEW report_terms AS
  SELECT lt.vaers_id, r.vaccine, lt.level_index,
         group_concat(lt.term, ' | ' ORDER BY lt.term) AS terms
  FROM level_terms lt JOIN reports r USING (vaers_id)
  GROUP BY lt.vaers_id, lt.level_index;
```

(`group_concat(... ORDER BY ...)` needs SQLite ≥ 3.44; the venv ships 3.49.1.)
Tests: `PRAGMA table_info(reports)` has no `narrative`; the eval DB reproduces
`CorpusIndex.report_terms` for every report; `SELECT narrative FROM reports` through
the executor is refused.

### 5.2 Reference compiler (`framework/sql/compiler.py`) — the retrieval upper bound

`compile_sql(claim) -> list[ArmQuery(label, sql, params, cell_kind)]` over
`first_mention` with bound parameters (`:a`, `:b`, `:vax`, …); labels `"arm"`
(1-arm), `"cohort_1" / "cohort_2"` (2-arm), `"report"`. One join shape per
conditioning; the verified `ordered_pair` shape (13/13 modes checked set-for-set
against `evidence_ids` on the raw schema):

```sql
SELECT a.vaers_id,
       (a.level <> b.level) AS in_denominator,
       (a.level <  b.level) AS in_numerator,
       (a.level =  b.level) AS excluded,
       CASE WHEN a.level < b.level THEN 'before'
            WHEN a.level > b.level THEN 'after' END AS cell   -- NULL when excluded
FROM first_mention a JOIN first_mention b USING (vaers_id)
WHERE a.vaccine = :vax AND a.term = :a AND b.term = :b;
```

`both_present` is the same join with `in_denominator = 1` (and, for C-V3, `cell`
`co_exist` on equal levels); `orderable_triple` is the 3-way join with
`in_denominator = (lA<>lB AND lB<>lC AND lA<>lC)`; `all_present_unique_first/last`
counts winners at `MIN`/`MAX` and excludes `n_winners > 1`; `presence_split` is a
`LEFT JOIN` from `reports` on A and B split on `a.term IS [NOT] NULL`;
`single_report` is `SELECT term, level FROM first_mention WHERE vaers_id = :r AND
term IN (...)`. Release-wide test: the compiler's id sets equal `evidence_ids` for
all 18,492 instances.

### 5.3 LLM text-to-SQL (`framework/sql/llm_sql.py`) — M2

Input = the DDL + the claim JSON + the row contract (`ARM_COLUMNS`, or `(term,
level)` at report tier) + the conditioning prose for the claim's mode
(`pilot.RULE_BY_MODE`, `pilot._EXCLUSION_REASON`) + the reminder that position is
first mention and ids are `vaers_id`. Output: one statement per arm as JSON
`{"arms": [{"label", "sql"}]}`, executed through the read-only executor and folded
by `execute_queries` → `Retrieval(arms, levels, queries, ok)`. Failure classes:
`sql_error | contract_violation (columns mismatch) | empty_result | timeout |
denied | not_select | multi_statement | row_cap`; a failed arm yields an empty
`ArmCounts` and `ok = False`, and the instance goes on to S3 as `n = 0`.

### 5.4 Read-only executor (`framework/sql/executor.py`)

`ReadOnlyExecutor(db_path, timeout_s=5.0, row_cap=10_000, log_path)`: URI
`mode=ro`; `set_authorizer` allowing `SQLITE_SELECT`, `SQLITE_READ` on
`{reports, level_terms, first_mention, report_terms}` and `SQLITE_FUNCTION`,
denying everything else (writes, `ATTACH`, `PRAGMA`, `sqlite_master`); a single
statement that starts with `SELECT` / `WITH` after stripping comments; a
progress-handler timeout; rows fetched to cap + 1 and marked `truncated`; one JSON
line per call in `sql_log.jsonl`.

### 5.5 Scoring retrieval

Per arm, the predicted denominator (and numerator) id sets against
`evidence_ids`: set precision / recall / F1 / exact match, with the **0/0
convention P = R = F1 = 1.0 iff both sets are empty, 0.0 if gold is empty and the
prediction is not**. That second case is the fabrication probe: on the 1,630
`not_locatable` instances the gold denominator is empty, and any non-empty
prediction is a false positive, reported as a separate **`not_locatable` FPR**
column. `coexist_leak` = |pred_den ∩ gold.excluded| / |gold.excluded| (the precedes
family's signature failure); `cohort_leak` = share of predicted ids outside the
cohort. The report tier is scored as `report_hit` (the retrieved first-mention
levels of the named events equal gold) and is **kept out of the retrieval macro** —
its 3,900 instances have no denominator.

### 5.6 Document export (`framework/docs.py`) — M4, designed only

`export_documents(eval_conn)` writes one JSON per report from the eval DB. It exists
only as the ~30K-token cohort payload for the in-context baseline B1 (§7.5). A
predicate-over-documents retriever is recorded as a post-v1 option, not built.

---

## 6. Stage 3 — aggregation and test (`framework/run_test.py`)

`to_viable_core(claim, retrieval) -> ViableCore` rebuilds the object the oracle
expects from the claim and the retrieved counts. Its `extra` must be complete for
**all 20 modes**: `seq_bool / modal_choice` → `counts` + `modal`; `first_* /
last_*` → `counts` + `winner`; `cooc_modal_bool` → `counts` with the named cell
`co_exist`; `rep_dir_* / rep_sym_bool` → `rel`; `rep_seq_bool` → holds + indices;
**`rep_first_* / rep_last_choice` → `winner` + `unique` + indices** — otherwise
`answer_key` returns None on the 1,200 report-tier first/last CHOICE instances.
`computable = min_n_gate(n, family, n2=n2).testable`; **never `n = None`** — no
rows ⇒ `n = 0` ⇒ `not_locatable`. Then:

- **`core_significance(core, named=claim.named_cell())`** — never
  `compute_answer`, which reports the WINNER's tail (verified on F-V1: it would call
  an asserted runner-up "supported"). Negation = tail swap exactly as
  `oriented_significance` does. `answer_key(core)` gives `(options, gold_answer)`
  for CHOICE.
- **Report tier**: `report_rule(claim, levels)` on the **oriented** events —
  `rep_dir_*` supported iff lA < lB (co-exist → refuted for BOOL, None answer for
  CHOICE); `rep_sym_bool` iff lA = lB; `rep_seq_bool` iff lA < lB < lC;
  `rep_first_*` iff A is the UNIQUE earliest; `rep_last_choice` iff A is the UNIQUE
  latest — then `verdict.deterministic`. Tested against all 3,900 `gold_verdict`
  rows.
- An unknown family from a model is recorded as a procedure error and the **gold
  family** is used for the gate — `family_floor` must not raise inside the harness.

`run_test(claim, retrieval, *, procedure_mode) -> Prediction(response, verdict,
subtype, p_claim, p_opposite, test, n, k, n2, k2, answer, gate_reason,
procedure_errors, notes)`; `claim.is_underdetermined` short-circuits to
`response = "underdetermined"`. Variants:

| variant | what runs | isolates | built |
|---|---|---|---|
| **`procedure-honouring`** (default) | the claim's **stated** `test / null.p0 / claim_tail` on the retrieved counts via `binom_exact_p` / `fisher_exact_2x2` + `three_decision` with the claim's `min_n_floor`-implied family; incompatible test/arms → error recorded, fall back to the reference | makes null-choice and test/tail failures **causal** — a wrong procedure yields a wrong verdict | M1 |
| `gold-procedure` | `core_significance(named=)` + negation swap (the reference) | WHAT layer + retrieval | M1 |
| `model-computed` | the model returns p's and the verdict; the harness only checks | the model's own arithmetic | M4 |
| `agent` | tools `run_sql`, `exact_test`, `min_n_gate`, **`submit_evidence(arm, ids)` required before `submit`** | end-to-end tool use, with retrieval still scoreable | M4 |

Test: with the reference procedure, `honouring == gold` on every mode.
**Alternative-test adjudication**: the verdict is scored as-is; the named test is
bucketed `gold | synonym (binomial / sign → binom_exact; fisher / hypergeometric →
fisher_exact) | other-exact | approximate`. `approximate` (chi-square, normal
approximation) is never "valid" — exact tests only (`CLAUDE.md` Conventions).

---

## 7. Evaluation (`framework/evaluate.py`)

### 7.1 Units and the eval set

Three units, all quoted in every headline count: the **record** (one text), the
**instance** (its 8 texts aggregated), the distinct **`fact_id`** (8,964). The
**default eval set is the `original` register × both formats** (≈2,800 calls on
`eval-core`); all 8 texts are run only on a seeded 200-instance **invariance
subset**. **`eval-core`** (`subsets.eval_core`): per-group cap 90 at 30/30/30 per
verdict where available, **mirror pairs (`derived_from_core_id`) and twins
(`fact_id`) kept together**, deterministic under `seed=0`, written to
`results/subsets/eval_core_v1.json` with the release sha256s. Few-shot examples come
from outside it (`subsets.fewshot_pool`).

### 7.2 Metric definitions

| stage | metric | definition |
|---|---|---|
| S1 | `mode_acc` | predicted `mode` == gold mode (given-group: trivially 1.0; blind-group: the number that matters, with the 20 × 20 confusion) |
| S1 | `events_em` / `events_set_em` / per-role acc | ordered tuple EM; set EM (catches orientation errors separately); accuracy per role A–D |
| S1 | `cohort_em`, `negated_acc` | `CohortSpec` tuple EM; negation flag accuracy (C-V1/2/3 carry the signal) |
| S1 | procedure per-field | accuracy of `test`, `null.kind`, `null.p0`, `claim_tail`, `min_n_floor`, `arms`, `conditioning` vs `derive_procedure` — only meaningful in `procedure-blind` |
| S1 | `claim_em` | `what_key()` equal **and** procedure equal |
| S2 | set P / R / F1 / EM per arm | denominator and numerator id sets vs `evidence_ids`; 0/0 convention (§5.5) |
| S2 | `not_locatable` FPR | share of gold-`not_locatable` instances with a non-empty predicted denominator |
| S2 | `coexist_leak`, `cohort_leak` | §5.5 |
| S2 | `report_hit` | report tier only; kept out of the retrieval macro |
| S3 | `nk_em` | `(n, k[, n2, k2])` exact match |
| S3 | `p_agree` | \|Δp\| ≤ 1e-4 on both tails, **only on the 11,457 instances whose gold `p_claim` is not None** (3,135 `sparse` / `not_locatable` rows and the 3,900 report rows have none) |
| S3 | `p_noneness` | binary agreement on whether p is None |
| S3 | test bucket | `gold / synonym / other-exact / approximate` (§6) |
| verdict | micro accuracy | over {supported, refuted, insufficient} |
| verdict | class-macro-F1 | per `decisions.md:656-659`: per-class P/R/F1, macro over the three classes, so the yes-man failure (refuted-recall → 0) is always visible |
| verdict | **group-macro of class-macro-F1** (headline) | mean over groups with ≥ `min_group_size` instances (default 30; S-V1 / S-V3 have 6 and are **excluded and listed**), **bootstrap CI** over instances (default 200 resamples) |
| verdict | fact-weighted companion | each `fact_id` weight 1 (P-V4 alone is 46% of instances) |
| verdict | breakdowns | per tier (report tier macro over {supported, refuted} only), family, register, format, negated; **sub-type recall** for sparse / underpowered / not_locatable |
| verdict | `answer_acc` (CHOICE) | with the **seeded option shuffle applied before any parser reads the row**; `None` a valid class (80 tie instances); `options[0]` / `options[2]` trivial baselines reported — they score 100% on F-R1 / P-R2 and on F-R2 in release order |
| response | `underdetermined` | the 2,292 unanswerable rows: P/R of the token, scored separately; **excluded from every other metric by default**. Distinct from `insufficient`, which is a property of the DATA |

### 7.3 Attribution — ordered checks with printed denominators

For every wrong row the first failing stage is charged, in this order:
**S1-parse → S1-procedure (sub-buckets null / test-tail / gate) → S2-conditioning
(+ `coexist_leak`) → S2-aggregation → S3-test → S3-gate → S3-verdict**, with
**`lucky`** when the verdict is right despite an earlier failure. Two things keep
this honest: **each stage's denominator is printed** (a stage that never runs
because S1 failed has a smaller denominator, and the report says so), and the
**unconditional rates under gold-forcing** are reported alongside — gold S1 fed into
S2, gold S2 fed into S3 — so the six failure modes the docs have always named (query
parsing, conditioning, aggregation, null choice, test/tail, min-n gate) are
**marginal**, as the docs read them, not conditional on upstream success.

### 7.4 Consistency

- **Pair consistency** over `derived_from_core_id` (6,664 pairs, both members
  present in the run): the detector promised in `dataset_construction.tex:146-148`
  — a model answering `supported` (or `refuted`) to both directions of one core is
  a `pair_contradiction`.
- **Twin consistency** over `fact_id`: the same fact in two groups (964 facts) gets
  the same verdict where gold does.
- **Register / format invariance** per instance on the invariance subset, with the
  caveat that P-V2 / P-V4 invariance is confounded by issue 24.

### 7.5 Baselines and models

> **The no-reasoning FLOOR is random, not majority (2026-09-21).** On accuracy
> the trivial strategies are within a few points of each other (0.26–0.37). On
> the headline metric they span **0.10 to 0.40**, and the ordering inverts:
> majority-per-group scores 0.235 because it predicts one class per group and
> so gets F1 = 0 on the other two, while a tier-aware coin flip scores **0.397**
> because it spreads predictions across every class. Report random-tier-aware
> as the floor; keep majority alongside as the illustration of what the metric
> punishes. Against 0.235 the smoke-4 result (0.971) reads as 74 points of
> headroom; against the honest floor it is 57. A reviewer will compute random.
> Tier-aware is the legitimate form: `level` is an input field, so knowing that
> report-tier rows are never `insufficient` costs no reasoning.

| id | pipeline | what it proves / measures |
|---|---|---|
| **B0 `template-table`** | rules → compiler → oracle | **must be exactly 100% on the 145,644 answerable records** — proves harness correctness, *not* that the text entails the label; issue 22 does not threaten it, issue 24 is the real caveat |
| B-triv | per-group majority (**37.0%** aggregate), always-`insufficient`, `options[i]` | chance and shortcut floors |
| `llm-s1+compiler` | LLM extraction → reference SQL → oracle | S1 in isolation, end to end |
| `rules+llm-sql` | rules → LLM SQL → oracle | S2 in isolation |
| `llm-s1+llm-sql` | LLM extraction → LLM SQL → oracle | the full local pipeline, stopping at text-to-SQL |
| B1 in-context (M4) | ~30K-token cohort block in the prompt, **requests sorted by cohort** so the prefix cache hits | can a model verify without SQL |
| B2 agent (M4) | tools `run_sql` / `exact_test` / `min_n_gate` / `submit_evidence` | tool-using verification |
| B3 single-pass (M4) | text → verdict, no tools | should sit near 33–37%; higher = shortcut |

Models: local first — 7–8B-class open models at 4-bit on the 16 GB GPU
(`qwen2.5:7b-instruct` primary, `qwen2.5-coder:7b`, Llama-3.x-8B, MedGemma-4B);
27B / 70B and API models (GPT-4.1, Claude, Llama-3.3-70B, MedGemma-27B) later behind
the same `Provider` interface. Per-cohort tables carry a caveat line for issue 23
(Janssen is 8.8% of report-tier instances vs 36.8% of the corpus).

### 7.6 Run artifact

`results/<run_id>/{config.json, predictions.jsonl, sql_log.jsonl, metrics.json,
report.md, failures.md}`. `config.json` records the pipeline, condition, procedure
mode, model, subset, seed, and the sha256s of the release files
(`dataset_statistics.json["files"]`) and of the eval DB. `failures.md` shows the
worst 25 instances in the `validation_sample.md` supports / against / excluded
format. One prediction row per record:

```
{"hypothesis_id", "instance_id", "group_id", "register", "format", "condition", "pipeline", "model",
 "claim": StructuredClaim.to_dict() | None, "claim_problems": [str],
 "retrieval": {"ok", "arms": [{"label", "n", "k", "denominator_ids", "numerator_ids", "excluded_ids", "counts"}],
               "levels": {term: level} | None,
               "queries": [{"label", "sql", "params", "n_rows", "ms", "error", "error_class"}]} | None,
 "prediction": {"response", "verdict", "subtype", "p_claim", "p_opposite", "test", "n", "k", "n2", "k2",
                "answer", "gate_reason", "procedure_errors"} | None,
 "latency_ms", "tokens": {"prompt", "completion"} | None, "error": str | None}
```

---

## 8. Provisional split (`framework/split.py`, `scripts/make_split.py`) — M3, designed only

`make_split(answers, seed=0, fractions=(.7, .1, .2), min_facts_for_train=10) ->
{fact_id: split}`: stratified by the group of a fact's first appearance; groups with
fewer than 10 facts (S-V1 / S-V3) go entirely to test; pins: **no `fact_id`,
`derived_from_core_id` or `instance_id` straddles a boundary** (a split keyed on
`derived_from_core_id` alone would put the same fact on both sides, because
`core_id` embeds `group_id` — the issue-14 lesson). **Location:
`data/splits/fact_split_v1.json`**, with the release sha256s recorded inside —
outside `data/release/v1/` so the published artifact directory stays immutable (a
small deviation from the option wording "under data/release/v1/splits/"; the intent
— provisional, pipeline-internal, not release — is unchanged). Issue 17 stays open
as the *release* question; regeneration for issues 22/23 changes instance ids but
`fact_id` survives it. Not built this session: only the fine-tune stage needs it.

---

## 9. Code layout and reuse points

```
src/temporal_hypo/framework/
  claim_schema.py          StructuredClaim, Procedure, NullSpec, MODE_SPEC, derive_procedure,
                           validate, FLAT_JSON_SCHEMA, from_gold, claim_from_flat      [M1, contract]
  io.py                    Release, load_release, release_sha256s                          [M1]
  subsets.py               eval_core, invariance_subset, fewshot_pool, read/write_subset   [M2]
  extract/__init__.py      Extractor protocol, visible_fields, GIVEN/BLIND_GROUP_FIELDS    [M1, contract]
  extract/rules.py         RulesExtractor, compile_patterns, vocabulary_from_db            [M1]
  extract/llm_client.py    Provider, Completion, OllamaClient, CacheDir, parse_json_object [M2]
  extract/llm.py           LLMExtractor (prompt builder, k-shot, repair retry, snapping)   [M2]
  extract/finetune.py      fine-tuned WHAT-layer extractor                                 [M3, designed]
  sql/views.sql            the eval DDL models see verbatim                                [M1]
  sql/build_eval_db.py     build_eval_db, EVAL_DDL, open_eval_db                           [M1]
  sql/executor.py          ReadOnlyExecutor, ExecResult                                    [M1]
  sql/aggregate.py         ARM_COLUMNS, ArmRow, ArmCounts, aggregate, report_levels        [M1, contract]
  sql/compiler.py          compile_sql -> list[ArmQuery]                                   [M1]
  sql/retrieve.py          execute_queries -> Retrieval, QueryLog                          [M1]
  sql/llm_sql.py           LLMSQLRetriever                                                 [M2]
  docs.py                  export_documents (B1 payload)                                   [M4, designed]
  run_test.py              to_viable_core, report_rule, run_test -> Prediction             [M1]
  pipeline.py              the four pipelines, prediction rows                              [M1]
  baselines.py             oracle, majority, always-insufficient, options[i]               [M1]
  evaluate.py              evaluate -> metrics, write_report (metrics.json/report.md/failures.md) [M1]
  split.py                 make_split                                                      [M3, designed]
scripts/
  build_eval_db.py         --db data/medtempo.db --out data/medtempo_eval.db               [M1]
  run_eval.py              --pipeline oracle|llm-s1+compiler|rules+llm-sql|llm-s1+llm-sql
                           --condition given-group|blind-group --procedure blind|given
                           --subset all|eval_core --registers --formats --limit --model
                           --out results/<run_id>                                          [M1/M2]
  make_split.py, finetune_extractor.py                                                     [M3, designed]
tests/framework/           conftest.py (synthetic CORPUS via tests/generation/conftest.py::make_db,
                           `needs_release` gate), test_<module>.py per module
```

Scripts follow `scripts/build_db.py` (argparse, `_REPO_ROOT`, `main()`, package
imports, `PYTHONPATH=src`). The core harness stays on stdlib + pandas + pyyaml —
**no new required dependency**; `pyproject.toml` declares the optional extras `llm
= ["anthropic", "openai"]` and `finetune = ["transformers", "torch", "datasets",
"accelerate", "peft"]` for later, not installed now.

Reuse points (the harness calls these, it does not re-implement them):
`core/answers.py::core_significance, answer_key` (and `oriented_significance` as the
negation reference); `core/verdict.py::three_decision, deterministic`;
`core/min_n.py::min_n_gate, family_floor`; `core/significance.py::binom_exact_p,
fisher_exact_2x2`; `generation/evidence.py::evidence_ids` (tests only);
`generation/templates.py::load_groups, template_string`;
`generation/cores.py::MODE_BY_GROUP, ViableCore, _build_report_core`;
`generation/instances.py::INPUT_FIELDS, fact_id`; `generation/pilot.py::RULE_BY_MODE,
_EXCLUSION_REASON`; `scripts/make_examples.py::_null_hypothesis` (strings copied, the
script is not imported); `scripts/validate_gold.py::check_instance` (the Part C logic
the release-wide tests mirror).

---

## 10. Milestones and verification

Order is cheapest-and-most-de-risking first; each step has its own check so a
failure is localised. Test command throughout (from the repo root):
`PYTHONPATH=src ./.venv/Scripts/python -m pytest tests/framework -q` (release-wide
and DB-wide tests are `@pytest.mark.slow` and gated by `needs_release`).

### 10.1 M1 — deterministic chain (no model; proves the harness) — BUILT 2026-09-01, B0 = 100%

| step | files | check |
|---|---|---|
| 1 | `claim_schema.py` | `derive_procedure` == `answers._BINOM_NULL / _MODAL_RUNNER / _FISHER` + `cooc_modal_bool`; `from_gold` round-trips 50 release rows |
| 2 | `io.py` | loads 147,936 / 18,492 rows; sha256s match `dataset_statistics.json`; every `hypothesis_id` joins; `gold_verdict == test_verdict` asserted **only where `report_id is None`** (issue 25) |
| 3 | `extract/rules.py` | **first test written**: all 184 strings rendered with fixture slots round-trip; on the release 145,644 parsed, 2,292 underdetermined, `claim_em` = 1.0 vs `from_gold` |
| 4 | `sql/views.sql`, `sql/build_eval_db.py`, `scripts/build_eval_db.py` | `PYTHONPATH=src ./.venv/Scripts/python scripts/build_eval_db.py --db data/medtempo.db --out data/medtempo_eval.db` → 3,166 reports / 22,681 level_terms / 1,660 terms; `PRAGMA table_info(reports)` has no `narrative`; `first_mention` reproduces `CorpusIndex.report_terms` |
| 5 | `sql/executor.py` | denies write / `ATTACH` / `PRAGMA` / a second statement / `SELECT narrative`; times out; caps rows |
| 6 | `sql/compiler.py`, `sql/retrieve.py` (+ `aggregate.py`) | id sets == `evidence_ids` on the conftest corpus for every mode; release-wide (slow) all 18,492 instances; `sum(counts) == n` on every argmax mode |
| 7 | `run_test.py` | reproduces P-V1 / P-M2 / F-V1 / S-V1 / C-V3 / F-R1 release rows; `report_rule` == 3,900 gold rows; the `named=` trap (F-V1); unknown family → procedure error, not a crash; `honouring == gold` under the reference procedure |
| 8 | `evaluate.py` | hand-built prediction sets exercise the 0/0 convention, p-agreement on non-null only, class-macro-F1, group-macro + CI + min-size exclusion, fact weighting, attribution denominators, gold-forcing, pair / twin / register consistency, `underdetermined`, the option shuffle, the three report writers |
| 9 | `pipeline.py`, `baselines.py`, `scripts/run_eval.py` | `PYTHONPATH=src ./.venv/Scripts/python scripts/run_eval.py --pipeline oracle --subset all --out results/oracle_all` → **verdict 1.0 on 145,644 records, 2,292 underdetermined, retrieval EM 1.0 on all arms, `nk_em` 1.0, `p_agree` 1.0, pair-contradiction 0.0; `options[0]` = 1.0 on F-R1 / P-R2, `options[2]` = 1.0 on F-R2; majority 0.370** |

Also an M1 deliverable: the **register / statistic faithfulness audit** (issue 24)
— for each of the 184 strings, the implied denominator and contrast, diffed against
`RULE_BY_MODE`. It is the standing review step `09_next_steps.md` asked for after
issue 13, mechanised as far as it can be. **DONE 2026-09-01 →
`11a_template_faithfulness_audit.md`** (all 184 strings): 70 FAITHFUL / 65 NOTE /
38 AMBIGUOUS (24 strong) / **1 MISMATCH** / 10 underdetermined-input. Issue 24's
counts reproduced exactly (P-V2 273, P-V4 2,194; C-V2 467, P-M2 8); new findings:
C-V2 clinical `question_negated` says "unassociated" (an independence/two-sided
reading) while gold supports 145 negated instances on significant NEGATIVE
association — the one outright mismatch; P-V2 clinical "than {C}" has a second
syntactic parse (arm 2 = P(A before C)) that differs on 1,059/2,000; and "rate"
wording alone does not fix P-V2/P-V4 because the research registers never name
the denominator. Proposed register-voiced rewordings for all 25 strings are in
the audit §4; adopting them is issue 24's still-open decision.

### 10.2 M2 — local LLM stages — BUILT 2026-09-01, smoke runs in §10.3

| step | files | check |
|---|---|---|
| 10 | runtime: `winget install Ollama.Ollama`; `ollama pull qwen2.5:7b-instruct` (+ optional `qwen2.5-coder:7b`) | `curl localhost:11434/api/tags` lists the model; one structured-output call returns schema-valid JSON |
| 11 | `extract/llm_client.py` | unit test with a stub `Provider` (no network); cache hit on re-run |
| 12 | `extract/llm.py` | 20-instance dry run parses to `StructuredClaim`; blind-group mode confusion produced |
| 13 | `sql/llm_sql.py` | 20-instance dry run; rows flow through `aggregate()`; `coexist_leak` computed; every failure class logged |
| 14 | `subsets.py` | `eval_core` counts per group; no pair or twin straddles; `results/subsets/eval_core_v1.json` written |
| 15 | eval runs (background) | smoke: `scripts/run_eval.py --pipeline <P> --condition blind-group --procedure blind --subset eval_core --registers original --formats question,claim --limit 200 --model qwen2.5:7b-instruct --out results/<run_id>` for each of the three pipelines; then full `eval-core` for `llm-s1+llm-sql` if time allows. Each run writes `metrics.json` + `report.md` + `failures.md` |

Whole-session checks: `PYTHONPATH=src ./.venv/Scripts/python -m pytest -q` green
including `tests/framework/`; the B0 numbers of step 9 **exactly** as stated — any
deviation is a harness bug fixed before M2 starts; the smoke runs complete for all
three pipelines and `failures.md` renders in the `validation_sample.md` format;
`pyproject.toml` gains no required dependency; every number quoted in this doc
re-measured after writing (done 2026-09-01: all match).

### 10.3 Results — to be filled after the M1/M2 runs

The orchestrator fills this table from each run's `metrics.json`; until then the
rows are placeholders. Verdict columns are over the answerable records of the run;
`underdetermined` is reported separately.

| run | pipeline | condition | procedure | subset / filters | records | verdict acc | class-macro-F1 | group-macro-F1 [95% CI] | S1 `claim_em` | S2 set-F1 (den) | `coexist_leak` | `not_loc` FPR | `p_agree` | pair-contradiction | `underdetermined` |
|---|---|---|---|---|--:|--:|--:|---|--:|--:|--:|--:|--:|--:|--:|
| B0 (`results/oracle_v1`, 556 s) | `oracle` = rules → compiler → gold procedure | given-group | gold | all | 147,936 (145,644 scored) | **1.000** | **1.000** | **1.000** [1.000, 1.000] (S-V1, S-V3 excluded: 6 instances each) | 1.000 | 1.000 (set EM 1.000 on den/num/excl; n,k EM 1.000; report_hit 1.000) | 0.000 | 0.000 | 1.000 (n=89,874; None-agreement 1.000) | 0.000 (6,664 cores / 52,548 pairs); twins 1.000 (1,767 groups); register/format invariance 1.000 | **2,292** = expected by template, 0 unexpected |
| B-triv (`results/trivial_v1`) | `majority_per_group` | — | — | all | 147,936 | 0.370 | 0.180 | 0.234 [0.229, 0.239] | — | — | — | — | — | 1.000 (by construction: both mirrors get the group majority) | — |
| B-triv | `always_insufficient` | — | — | all | 147,936 | 0.263 | 0.139 | 0.102 [0.097, 0.106] | — | — | — | — | — | 0.000 | — |
| B-triv (computed 2026-09-21 on v1.1 answers, 20 seeds) | `random_uniform` — uniform over the 3 verdicts | — | — | all | 18,492 inst. | 0.333 | 0.331 | **0.360** | — | — | — | — | — | ~0.33 (independent draws) | — |
| B-triv (same) | `random_tier_aware` — uniform over {sup, ref} at the report tier (where `level` is visible and `insufficient` does not exist), 3-way elsewhere | — | — | all | 18,492 inst. | 0.368 | 0.364 | **0.397** | — | — | — | — | — | ~0.33 | — |
| B-triv | `options[0]` / `options[2]` (CHOICE answer, **gold order**) | — | — | all (21,072 CHOICE records) | 147,936 | 0.370 | 0.180 | 0.234 | — | — | — | — | — | — | answer_acc **0.600** / **0.312** (F-R1 & P-R2 = 1.000 at index 0; F-R2 = 1.000 at index 2 — the position leak); **as presented after the seeded shuffle: 0.396 / 0.212** |
| smoke-1 (`results/smoke200_llm-s1_compiler`, 1,322 s) | `llm-s1+compiler` (S1 = qwen2.5:7b-instruct, 3-shot; S2 = compiler) | blind-group | blind | `smoke_200_s0` (200 instances ⊂ eval_core, stratified), original, question+claim | 400 | **0.740** | 0.732 | 0.770 [0.748, 0.783] (20 groups, min 6) | 0.675 (mode 0.718) | 0.984 (EM 0.983; report_hit 0.380) | 0.000 (any 0.006) | 0.000 | 0.960 (n=198) | 0.000 (166 pairs); twins 0.750 | 16, all unexpected → scored wrong |
| smoke-1b (`results/smoke200_llm-s1_compiler_tierhint`, 1,330 s) | `llm-s1+compiler` **+ `--tier-hint`** (one prompt line: `level` fixes the admissible modes) | blind-group | blind | same slice | 400 | **0.918** | 0.933 | 0.933 [0.894, 0.952] | 0.830 (mode 0.882) | 0.965 (EM 0.963; report_hit 0.848) | 0.000 | 0.000 | 0.924 (n=198) | 0.000 (166 pairs); twins 0.875 | 21, all unexpected → scored wrong |
| smoke-1c (`results/smoke200_llm-s1_compiler_tierhint_routing`, 1,326 s) | `llm-s1+compiler` **+ `--tier-hint --routing-hint`** (adds the candidate-count → mode-family rule, 2026-09-02) | blind-group | blind | same slice | 400 | **0.928** | 0.926 | 0.935 [0.905, 0.956] | 0.878 (mode 0.905) | 0.947 (EM 0.944; report_hit 0.886) | 0.000 | 0.000 | 0.924 (n=198) | 0.006 (166 pairs); twins 0.917 | 12, all unexpected → scored wrong |
| smoke-2 (`results/smoke200_rules_llm-sql`, 872 s) | `rules+llm-sql` (S1 = rules; S2 = qwen2.5-coder:7b) | blind-group | blind | same slice | 400 | **0.545** | 0.540 | 0.475 [0.446, 0.513] | 1.000 (mode 1.000) | 0.250 (EM 0.169; report_hit 1.000) | 0.071 (any 0.105) | 0.182 | 0.010 (n=198) | 0.012 (166 pairs); twins 0.833 | 0 |
| smoke-4 (`results/smoke200_rules_api-sql`, ~36 min, ~$8.80: 1.02M in / 0.15M out) | `rules+llm-sql` (S1 = rules; **S2 = claude-opus-5** via `--sql-provider anthropic`, 2026-09-03) | blind-group | blind | same slice | 400 | **0.975** | 0.962 | 0.971 [0.936, 0.992] | 1.000 (mode 1.000) | 0.950 (EM 0.950; report_hit 0.987) | 0.000 | 0.000 | 0.960 (n=198) | 0.000 (166 pairs); twins 1.000 | 0 |
| smoke-5 (`results/smoke200_local-s1_api-sql`, ~4 min — S1 and most SQL replayed from cache) | `llm-s1+llm-sql` **mixed: S1 = qwen2.5:7b-instruct + both hints, S2 = claude-opus-5** (2026-09-03) | blind-group | blind | same slice | 400 | **0.903** | 0.894 | 0.906 [0.867, 0.930] | 0.878 (mode 0.905) | 0.897 (EM 0.895; report_hit 0.880) | 0.000 | 0.000 | 0.874 (n=198) | 0.006 (166 pairs); twins 0.917 | 12, all unexpected → scored wrong |
| ref-v1.1 (`results/v11_smoke200_catalogue_7b`) | `llm-s1+compiler`, catalogue + both hints (the LOOKUP; procedure-given-style upper bound), **v1.1 slice** | blind-group | blind | v1.1 smoke_200 | 400 | **0.918** | 0.929 | 0.928 | 0.865 (mode 0.897) | 0.963 (compiler) | 0.000 | 0.000 | — | twins 0.875 | 18 unexpected |
| ref-v1.1-nonull (`results/v11_smoke200_catalogue_nonull_7b`) | same, `--hide-null-hints` (issue 27; catalogue keeps mode→conditioning) | blind-group | blind | v1.1 smoke_200 | 400 | 0.890 | 0.875 | 0.904 | 0.823 (mode 0.882) | — | — | — | test field 0.545 / null.kind 0.552 — un-runnable stated tests fall back to the reference in S3, so the verdict barely moves | twins 0.667 | 8 |
| **T1-v3 toolbox** (`results/v11_smoke200_toolbox_v3_7b`, 2026-09-30) | `llm-s1+compiler --s1-frame toolbox`: NO catalogue; the model COMPOSES the plan (§11a) | blind-group | blind | v1.1 smoke_200 | 400 | **0.642** | 0.770 | 0.687 [0.640, 0.712] | 0.627 (mode 0.642; **125 plans match no mode**) | — | 0.000 | 0.000 | plan fields (n=275 folded): quantity 0.978, denominator 0.935, arms 0.916, extreme 1.000, tail 0.993, test_family 0.789, rule_valid 0.789, p0 0.796, null_kind 0.625; plan_em 0.556 | twins 0.625 | 0 |
| **T1-Opus toolbox** (`results/v11_smoke200_toolbox_opus_v4`, 2026-09-30; ~$15.6: 2.36M in / 0.15M out) | `--s1-frame toolbox --provider anthropic --model claude-opus-5`: NO catalogue; composes the plan | blind-group | blind | v1.1 smoke_200 | 400 | **1.000** | 1.000 | 1.000 | **1.000** (mode 1.000; 0 no-shape) | — | 0.000 | 0.000 | plan_em **0.985** -- 394/400 plans match the reference field-for-field; the other 6 (P-R2) compose the two-candidate 'which came first' as `extreme_of_set`, semantically the same claim, folded by the two-candidate identity; rule_valid 1.000 | twins 1.000 | 0 |
| T1-Opus catalogue (`results/v11_smoke200_catalogue_opus`) | the LOOKUP with the catalogue + hints, Opus | blind-group | blind | v1.1 smoke_200 | 400 | **1.000** | 1.000 | 1.000 | 1.000 | — | 0.000 | 0.000 | — | twins 1.000 | 0 |
| T1-v4 toolbox 7B (`results/v11_smoke200_toolbox_v4_7b`; v3 + argmax wording + two-candidate normalization) | same as T1-v3 | blind-group | blind | v1.1 smoke_200 | 400 | **0.680** | — | — | 0.667 (mode 0.68; 110 no-claim) | — | — | — | plan_em 0.497; rule_valid 0.631; null_kind 0.566; test_family 0.631 | — | — |
| **T1-Opus toolbox ZERO-SHOT** (`results/v11_smoke200_toolbox_opus_zeroshot`, 2026-09-30, ~$6) | `--s1-frame toolbox --k-shot 0`, claude-opus-5 — **the headline S1 condition** | blind-group | blind | v1.1 smoke_200 | 400 | **0.958** | — | — | 0.910 (mode 0.910; 0 no-shape) | — | — | — | plan_em 0.812; rule_valid 0.943; the 36 mode errors are two shapes: C-V2 association → plain co-occurrence (22), P-V2 antecedent → pair-vs-pair (14) — exactly the shapes the 3 few-shot plans had covered | — | 0 |
| T1-7B toolbox ZERO-SHOT (`results/v11_smoke200_toolbox_7b_zeroshot`) | same, qwen2.5:7b-instruct | blind-group | blind | v1.1 smoke_200 | 400 | **0.490** | — | 0.558 [0.515, 0.591] | 0.487 (mode 0.502; **179 no-shape**) | — | — | — | plan_em 0.122; rule_valid 0.258 — without worked examples the 7B composes almost nothing | — | 0 |
| T1-v1 / T1-v2 toolbox (superseded harness versions) | same slice; v1 = strict reverse lookup, v2 = arms-carries-comparison | blind-group | blind | v1.1 smoke_200 | 400 | 0.390 / 0.525 | — | — | no-shape 232 / 170 — 3 of 4 failure classes were the HARNESS (§11a) | — | — | — | — | — | — |
| smoke-3 (`results/smoke200_llm-s1_llm-sql`, 448 s — S1 cached from smoke-1) | `llm-s1+llm-sql` (the full local pipeline) | blind-group | blind | same slice | 400 | **0.292** | 0.300 | 0.250 [0.217, 0.286] | 0.675 (mode 0.718) | 0.228 (EM 0.149; report_hit 0.380) | 0.082 (any 0.116) | 0.227 | 0.010 (n=198) | 0.018 (166 pairs); twins 0.667 | 16, all unexpected → scored wrong |
| e2e-sql (`results/smoke200_e2e_sql`, 2,122 s, $9.19) | `e2e-llm-sql` — the SENTENCE straight to SQL (S1 gold-forced by rules; claim JSON, conditioning rule and arm plan ALL withheld) | blind-group | blind | same slice | 400 | **0.860** | 0.830 | — (no group >= 30 after the cohort split) | 1.000 (gold-forced) | **0.673** (EM 0.508) | **0.198** | **0.273** | — | — | 0 |
| full | `llm-s1+llm-sql` | blind-group | blind | eval_core (1,649 instances), original, question+claim | ≈3,300 | — | — | — | — | — | — | — | — | — | **deferred** (~2.5 h GPU; the smoke already localises the failure to S2). Run with: `PYTHONPATH=src python scripts/run_eval.py --pipeline llm-s1+llm-sql --model qwen2.5:7b-instruct --sql-model qwen2.5-coder:7b --subset eval_core --condition blind-group --procedure blind --registers original --formats question,claim --out results/full_local` (S1 replays from `results/cache/`) |

Model for every LLM row: `qwen2.5:7b-instruct` via Ollama unless noted; smoke rows
are scored with `min_group_size=6` so all 20 groups enter the group-macro (the B0
row uses the default 30). Attribution tables (with per-stage denominators and
gold-forced rates) and the S1 mode confusion live in each run's `report.md`.

**What the smoke runs say (2026-09-01).** The stages fail independently and the
attribution separates them cleanly:

- **S1 (7B extraction) fails almost entirely by TIER confusion.** Blind-group
  mode accuracy is 0.718, but the errors are report-tier claims mapped onto their
  cohort statistic (`rep_dir_choice → dir_choice` 11/11, `rep_last_choice →
  last_choice` 24/24, `rep_seq_bool → seq_bool` 24/24, `rep_sym_bool →
  sym_bool_cooccurs` 14/14): vaccine-tier verdict accuracy is 0.986 against 0.414
  at the report tier, even though the input's `level` field states the tier. The
  `--tier-hint` ablation (smoke-1b) settles it: adding the ONE prompt line that
  `level` fixes the admissible modes lifts the same model to **0.918** (claim_em
  0.675 → 0.830; report-tier accuracy 0.414 → 0.848) — most of the S1 gap is
  instruction salience, not capability. The residual confusions are semantic
  neighbours (`rep_dir_choice → rep_first_choice` 14/24 — "which came first" read
  as a first-among question; `pairpair_bool → dir_bool` 8/22 — the four-event
  contrast collapsed to one pair).
- **Prompt rules trade errors, they don't remove them** (smoke-1c, 2026-09-02).
  Adding the candidate-count → mode-family rule (`--routing-hint`, on top of the
  tier hint) is a net +0.010 verdict (0.918 → 0.928; mode 0.882 → 0.905; report
  tier 0.848 → 0.886) but redistributes rather than solves: P-R2 stays broken
  (6/24 correct — 9 still `rep_first_choice`, and 6 NEWLY dropped the report tier
  to `dir_choice`), and the hint introduced a fresh regression, 7/20 P-M2 rows
  read as `rep_dir_choice` (multi tier 1.000 → 0.750). The residual S1 gap looks
  like few-shot/fine-tune territory, not more prompt rules.
- **Compose vs look up, first measurement (T1-v3, 2026-09-30).** With the catalogue
  withheld and every convention stated, the same 7B drops from **0.918 (lookup)
  to 0.642 (compose)** on identical inputs. The gap is NOT in the fields: when a
  plan matches a mode, the model gets the quantity right 97.8%, the denominator
  93.5%, the arms 91.6%, the tail 99.3%; the gap is **125/400 plans whose shape
  matches no mode** — compositions that are wrong as a whole: "is A first of the
  three" and "A → B → C in this report" composed as a PAIR order (43); "B follows
  A more often than it follows C" as ONE arm (22); "which of A, B, C occurs
  first" over a cohort given a SINGLE-REPORT denominator (20); the four-event
  contrast as a triple (10); association as plain co-occurrence (12). Those are
  exactly the situation-recognition failures the frame exists to surface, and
  the weakest composed fields are the null kind (0.625 — the argmax family is
  called data-derived or a plain proportion) and the test family (0.789). Two
  harness lessons recorded in §11a: the first two toolbox versions lost 232 and
  170 records to a reverse lookup stricter than the semantics and to a schema
  null-escape on `extreme` — fixed by normalization of IMPLIED fields and by
  removing the escape, never by consulting the answer. Next: the same frame on
  claude-opus-5 decides whether the compose gap is model-tier or task.
- **The compose gap is MODEL-TIER (T1-Opus, 2026-09-30).** On the same frame and
  slice, claude-opus-5 composes the procedure at **1.000** on verdicts and claim
  EM (plan EM 0.985: six P-R2 plans are the semantically equivalent two-candidate
  `extreme_of_set`) — against 1.000 with the catalogue. Before the last
  normalization it was 0.985, and all six misses were P-R2's two-candidate
  "which came first, A or B?" composed as `extreme_of_set`, which over two
  candidates IS a pair order (the earliest of {A, B} is the one that precedes) —
  folded by that identity, not by the answer. Consequences: (1) at the frontier,
  S1 on in-distribution templates is solved WITHOUT the mapping — the toolbox
  frame is honest and it costs Opus nothing; (2) the 7B's 0.64 is a capability
  gap in situation recognition, not task ambiguity; (3) any remaining S1
  difficulty at the frontier has to come from off-template generalization (P2
  group holdout — a held-out shape has no worked example) and from null
  diversity (v1.2) — the catalogue was never what made S1 easy for a strong
  model. Cost note: the toolbox prompt + 3 few-shot plans is ~5.9K tokens per
  call (2.36M input for 400 records, ~$15.6), 2.5x the earlier $6 estimate.
  The 7B under the same v4 prompt moved 0.642 -> 0.680 on verdicts while its
  composed test_family / rule_valid FELL (0.789 -> 0.631): the sharper argmax
  wording redistributed its errors rather than removing them -- the same
  prompt-saturation pattern as the catalogue hints. Report the 7B compose
  number as 0.64-0.68 (wording-sensitive), the frontier as 1.000 (not).
- **Zero-shot is the headline (2026-09-30).** A worked example is a mapping row, so
  `--k-shot 0` is the honest condition: Opus 1.000 → **0.958** (the 3 examples
  covered exactly the two shapes it now misses, C-V2 association and P-V2
  antecedent); 7B 0.64-0.68 → **0.490** (179/400 no-shape; rule_valid 0.258).
  Few-shot stays as a reported dial; P2 group holdout is downgraded (no group
  has an example); the remaining disclosed channel is the conventions text.
- **S2 was a model-capability gap, not benchmark impossibility** (smoke-4,
  2026-09-03). The same text-to-SQL stage that scored 0.545 with the local 7B
  scores **0.975** with `claude-opus-5` on identical inputs (gold claims,
  identical prompts and executor): denominator F1 0.250 → **0.950**, invalid SQL
  128/486 → **22/486**, conditioning wrong 41.5% → **2.5%**, `not_locatable`
  fabrication 0.182 → **0.000**, coexist leak 0.105 → **0.000**, pair
  contradiction 0.012 → 0.000, twins 0.833 → 1.000. The residual errors sit in
  the same conditioning-heavy groups (F-V3/P-M2/C-V2/P-V2 at 0.90-0.91) — the
  benchmark still discriminates at the top, but the headroom above frontier is
  ~2.5 points, not 45. Cost ~$8.80 / 36 min for the 400-record smoke.
- **The deployment config — local S1, frontier S2 — lands at 0.903** (smoke-5,
  2026-09-03), almost exactly the independence product of its stages (smoke-1c
  0.928 × smoke-4 0.975 = 0.904): at the frontier, stage errors neither compound
  super-multiplicatively (the 7B story) nor cancel much. 37/400 verdicts were
  "lucky" (right despite an upstream error, mostly S1 procedure fields that the
  honoured test tolerated). The local-vs-API split costs one S1 point of
  headroom and keeps extraction free and on-device.
- **S2 (7B text-to-SQL) is the weak stage, two ways.** 128/486 statements fail
  outright (`sql_error`, dominated by an unqualified `vaers_id` in self-joins;
  4 `row_cap` cross-joins), and among statements that RUN, conditioning is wrong
  on 41.5% of records (`coexist_leak` any-rate 0.105; not_locatable fabrication
  FPR 0.18 vs 0.00 for the compiler path) — while the report-tier query
  (`single_report`) is 100% correct. With gold claims in (smoke-2), verdict
  accuracy is 0.545; the compiler path with the same model's claims (smoke-1)
  scores 0.740.
- **Errors compound multiplicatively.** smoke-3 stacks S1 (gold-forced error
  0.335) on S2 (gold-forced error 0.714 given correct S1) and lands at 0.292 —
  slightly above the 37.0% majority baseline on class-macro-F1 (0.300 vs 0.180)
  but far below either single-stage pipeline.
- **Consistency diagnostics behave as designed:** pair-contradiction stays ≤0.018
  everywhere (the model is not answering `supported` to both mirrors); negated
  wording is a real failure axis for the SQL paths (0/26 correct); `insufficient`
  is heavily over-predicted whenever retrieval degrades (precision 0.17–0.38),
  which is exactly the "empty result → claim insufficiency" signature the
  three-decision design punishes.

### 10.3a Counts-only baseline (2026-09-22) — the model CANNOT compute the exact tests

`counts-llm`, claude-opus-5, 242 cohort-tier records of the v1.1 smoke slice
(the report tier has no counts and falls through to `run_test`). The model is
given the counts, the test, its definition, the null, the tail, the floor and
alpha; it returns the verdict. No text, no schema, no retrieval. ~1,440 prompt /
90 completion tokens per record, ~$6.9 per run.

| run | what changed | verdict acc | p-value agreement (tol 1e-3) |
|---|---|--:|--:|
| v1 | first attempt | 0.884 | 108/196 = 55% |
| v2 | **prompt bug fixed** (below) | 0.950 | 120/198 = 61% |
| v3 | + a one-line definition per test | **0.959** | **128/194 = 66%** |

**The headline is the gap between those two columns.** Verdict accuracy is 0.959
while the model's own p-values match the exact computation only **66%** of the
time. Both are true because the two disagree mostly where it does not matter:
most cores sit far from alpha, so a wrong p still lands on the right side of it.
The failures concentrate exactly where they hurt — at the boundary and on the
largest tables:

| test | p agreement | note |
|---|--:|---|
| modal_runner | 52/68 = 76% | |
| binom_exact | 34/46 = 74% | |
| **fisher_exact** | **42/80 = 52%** | the 2x2 hypergeometric sum; all 6 verdict errors are here |

Of the 10 remaining verdict errors, **6 are Fisher arithmetic** — P-M2 gold
p = 0.0433 against the model's 0.0555 (a near-boundary miss that flips the
verdict), and C-V2 gold 0.0331 against 0.175 on an 82-vs-937 table (not close).
The other 4 are S-V1/S-V3 at n = 5, k = 0, where the model declined to report a
p at all. Every error is decisive-gold → `insufficient`: the model under-calls
significance and **never once fabricated it** (all 54 gold-`insufficient` rows
correct, in every run).

So this baseline answers its question in the framework's favour: a frontier
model handed the numbers and told exactly which test to run still cannot do the
arithmetic reliably, and it fails hardest on Fisher, which is the test the
two-arm groups (P-V2, P-V4, C-V2, P-M2 — 58% of the release) all use. The
deterministic stage 3 is not bookkeeping; it is doing the work precisely in the
boundary cases that are statistically interesting.

**Two prompt bugs found and fixed — both worth recording, because each looked
like a model failure and neither was.**

1. **Double-flipped tail on negated claims (v1 → v2).** `derive_procedure`
   already returns `claim_tail="less"` when negated, so the payload's tail is
   ALREADY oriented. The prompt additionally said "if `negated` is true the
   claim tail is the other one", asking for a second flip. The model obeyed and
   returned exactly the complementary tail (`p_model = 1 - p_gold`: gold 0.000977
   against 1.0, gold 0.0262 against 0.9738). Negated-row accuracy was **0.385**;
   after the fix, **0.923**. Presented as a finding this would have read as
   "frontier models cannot handle negation", which is false.
2. **A test named but never defined (v2 → v3).** `modal_runner` was passed as a
   test name with the cells in the payload, but with no statement of what it
   does. The model defaulted to a binomial on k-of-n (12 of 18 → p = 0.1189)
   instead of the named cell against its largest competitor (12 of 16 →
   p = 0.0384). Naming a project-specific test is not the same as specifying it;
   the definition is scaffolding the framework would supply in deployment, so
   withholding it measured the wrong thing.

The general lesson for every baseline in this section: **when a baseline
underperforms, check the prompt against the harness's own semantics before
reporting a capability gap.** Two of the three iterations here were harness
bugs, and both had plausible capability stories attached.

### 10.3b End-to-end text-to-SQL (2026-09-22) — the conditioning rules are NOT recoverable from the text

`e2e-llm-sql`, claude-opus-5, the full 400-record v1.1 smoke slice, 2,122 s,
$9.19, zero row-level errors. Identical model, executor, scorer and slice to
smoke-4; the prompt drops exactly three blocks — the claim JSON (so no mode), the
CONDITIONING RULE prose, and the ARM PLAN. Stage 1 is gold-forced by the rules
parser (`claim_em` 1.000), so **every** difference is retrieval.

| diagnostic | smoke-4 (rule given) | e2e (rule withheld) |
|---|--:|--:|
| verdict accuracy | 0.975 | **0.860** |
| denominator set F1 | 0.950 | **0.673** (EM 0.508) |
| `coexist_leak` | 0.000 | **0.198** |
| `not_locatable` FPR | 0.000 | **0.273** |

Both leaks are SEMANTIC, not formatting — co-existing reports pulled into a
*precedes* denominator, and evidence invented for claims whose gold denominator
is empty. That is what identifies the loss as conditioning rather than a misread
output contract, and it is the check that had to pass before any capability
claim (cf. the two prompt bugs in §10.3a).

**The loss is concentrated, and where it falls is the result.** Report tier
0.981 and the *precedes* family 1.000 are untouched — the model derives that rule
unaided, writing `la = lb` into `excluded` with nothing having told it to. What
collapses: **C-V2 (association) 0.50**, **F-V2 0.36 / F-V1 0.45 (first/last)**,
S-V3 0.58, C-V1 0.70. Per family: pairwise 0.907 (n=226), sequence 0.833 (n=48),
first_last 0.786 (n=126).

The pattern tracks how far each rule is ENTAILED by the wording. "A precedes B"
does imply that co-occurring reports cannot settle the question. But nothing in
"A and B occur together more often than if independent" says to split the whole
cohort on presence rather than condition on co-occurrence, and nothing in "which
event comes last" says tied reports leave the denominator entirely. Those are
stipulations about what the statistic means for this corpus, not facts about the
sentence — they are what the structured claim carries, and a system without it
cannot reconstruct them.

> **Re-reading (2026-09-29).** Those stipulations were withheld, so this run
> measured convention-guessing, not temporal reasoning: the accurate statement
> is "conditioning is unrecoverable when the conventions are hidden". The
> protocol from here on states every convention (situation-phrased) and
> withholds only the mode mapping -- `decisions.md` "state every stipulation,
> withhold only the mapping"; the middle condition is issue 28/29.

### 10.3c What smoke-1c and e2e-sql did NOT test: null and test selection

Asked 2026-09-22, and the answer differs per run. Recorded because "procedure-
blind" is easy to misread as "the model inferred the procedure".

**e2e-sql: the procedure was GOLD and never in play.** Stage 1 is the rules
parser, which calls `derive_procedure(mode)` for the reference test, null, tail,
floor and arms. The model only ever wrote SQL — it never saw a test name, never
chose a null, and its output carries no procedure fields. The 0.860 is purely
retrieval, which is the intended scope, but it says NOTHING about null inference.

**smoke-1c: the procedure was requested, but the answer was in the prompt.** In
`procedure-blind` the model IS asked to emit `test / null_kind / p0 / claim_tail
/ arms / conditioning / min_n_floor`. Two things hand it the answer:

1. the instruction states the mapping outright — "binom_exact with null_kind
   binomial p0=0.5 for the single-cohort proportion modes; modal_runner for the
   argmax modes; fisher_exact with null_kind two_arm_equality for the two-arm
   modes";
2. `mode_catalogue()` is a 20-row lookup table whose columns are
   `mode | tier/family/answer_type | events | conditioning | arms | test | null |
   floor | rule | H0` — the null with its p0, the conditioning AND the H0, per mode.

So once the model picks the mode, every procedure field is read off a row.
**Procedure-blind means the model must EMIT the procedure, not INFER it.**
smoke-1c's real task is mode classification, which is exactly what its confusion
matrix reports and why one `--tier-hint` line moved it 0.740 -> 0.918.

**Consequence for the null-inference direction.** Removing the catalogue today
would not create a real task either: with only 3 cohort signatures (binom_exact
p0=0.5; modal_runner p0=0.5; fisher_exact two_arm_equality) the mapping compresses
into the three sentences above. Null selection becomes a genuine inference
problem only once nulls are DIVERSE and some are DATA-DERIVED — and a p0 that must
be computed from the cohort cannot be printed in a catalogue row at all. That is
the structural reason the `NullSpec` change (issue 20) is a prerequisite rather
than tidying.

**Measurement gap.** smoke-1c and e2e-sql sit at opposite extremes — one is given
everything in a table, the other nothing. Nobody has run the middle condition
(mode given but conditioning withheld, or the reverse), which is where "knows
which claim type this is" separates from "knows what that claim type requires".

### 10.3d External published systems on MedTempo (2026-09-24 → 09-29; local models only, GPU box)

Four published systems run on the v1.1 smoke slice / its cohort-tier subset with
`qwen2.5-coder:32b` via Ollama (no API). Code lives OUTSIDE this repo in sibling
dirs on the GPU box (`~/ehragent_baseline`, `~/ehrsql_baseline`,
`~/statqa_baseline`, `~/veritas_baseline` A/B, `~/veritas_adapted` C); summaries
in `~/ehragent_baseline/RESULTS_32B.md`, `~/PART2_perphase_results.md`. Verdict
accuracy on cohort+multi tiers; chance ≈ 0.33.

| system | stage | model | n | acc | where it fails |
|---|---|---|---|---:|---|
| EHRAgent, variant A (e2e code agent over the eval DB) | S1–S3 | 7B / **32B** | 400 | 0.103 / **0.417** (overall incl. report 0.150 / 0.527) | 7B: 72% no answer; 32B: retrieval — variant B (retrieval→oracle S3) 0.446 |
| EHRSQL protocol (one SQL per hypothesis, counts→gold test) | S2 | 32B | 242 | 0.384 | counts exactly gold on **2.9%**; 27% abstain; verdict lands because cores sit far from α |
| StatQA-style test selection (gold counts + hypothesis → test) | S3 | 32B | 242 | 0.364 (selection acc) | two-proportion z-test where Fisher is required (56/86); χ² on every modal-runner task (0/98; the taxonomy has no modal-runner equivalent) — corrected 2026-10-07 |
| VERITAS A (own test contract) | S1–S3 | 32B, 16k ctx | 39 | 0.333 primary / 0.179 strict | no one-sample plan type → planning loops; 14/39 hit the 40-min cap; gold-test match 0.00 |
| VERITAS B (+ our exact-test pool advertised) | S1–S3 | 32B | 39 | 0.308 / 0.179 | adopts our tests 33%; denominator = whole cohort (n=1,164 vs gold 6) |
| VERITAS C (contract extended with one-sample/modal types + validator) | S1–S3 | — | — | **not run** (built; one smoke, timed out while sharing a GPU) | — |

Readings: (1) every system fails at the DENOMINATOR, corroborating §10.3b from
outside our harness; (2) supplying the test pool changes which test is picked,
not accuracy (VERITAS B, StatQA) — supports the conditional-plan + guards design
over "hand the agent the tests"; (3) the EHRAgent 7B→32B gain is retrieval.
Caveats for the paper: all at 32B local while our frontier rows are Opus (the
compose gap is model-tier, decisions 09-30), and each system got the schema plus
a short data note, NOT the situation-phrased conventions of the toolbox card —
so these are a conventions-withheld condition in the §10.3b sense. Operational
notes: the Ollama OpenAI-compat endpoint defaults `num_ctx` to 2048 and
truncates from the START (EHRAgent 7B/32B-A runs were affected; `-8k` Modelfile
variants built, re-runs started and stopped at 8/400); my 40-min VERITAS cap was
tighter than the authors' 3600 s (`experiments/run_experiments.py`) and cost 64%
of A's GPU-hours to runs with no verdict. All runs STOPPED 2026-09-29; results
kept as-is. Draft: `docs/draft/dataset_construction.tex` "External systems".

### 10.3e Local coder models under the toolbox frame (2026-09-30, GPU box; branch `s1-toolbox`)

Same slice, flags and scorer as the T1 rows (v1.1 `smoke_200`, 400 records,
blind-group, procedure-blind, `--k-shot 0` unless stated); Ollama native API,
`num_ctx` 8192; run dirs `results/v11_smoke200_*` on the GPU box (gitignored).
Chance ≈ 0.33 on verdicts. Per-tier = report / vaccine / multi (158 / 222 / 20).

| run | pipeline / S1 frame | model | acc | claim EM | no-shape | plan EM | rule_valid | per tier | den-F1 |
|---|---|---|---:|---:|---:|---:|---:|---|---:|
| toolbox zs (cross-machine replicate) | llm-s1+compiler / toolbox | qwen2.5:7b-instruct | **0.482** | 0.468 | 187 | 0.061 | 0.254 | 0.40 / 0.55 / 0.45 | — |
| toolbox zs | same | qwen2.5-coder:7b | 0.400 | 0.410 | 226 | 0.149 | 0.621 | 0.65 / 0.26 / 0.05 | — |
| toolbox zs | same | qwen2.5-coder:32b | **0.410** | 0.390 | 218 | 0.302 | 0.797 | **0.00** / 0.65 / 1.00 | — |
| toolbox 3-shot | same, `--k-shot 3` | qwen2.5-coder:32b | 0.580 | 0.575 | 163 | 0.578 | 0.726 | **0.00** / 0.955 / 1.00 | — |
| catalogue + hints (lookup) | llm-s1+compiler / catalogue | qwen2.5-coder:32b | 0.993 | 0.935 | 0 | — | — | 1.00 / 0.99 / 1.00 | — |
| e2e toolbox zs | llm-s1+llm-sql / toolbox | qwen2.5-coder:7b | 0.320 | 0.410 | 226 | — | — | 0.65 / 0.11 / 0.05 | 0.172 |
| e2e toolbox zs | same | qwen2.5-coder:32b | 0.302 | 0.390 | 218 | — | — | 0.00 / 0.46 / 0.90 | 0.435 |
| S2 isolation | rules+llm-sql | qwen2.5-coder:7b | 0.540 | 1.0 | — | — | — | 1.00 / 0.24 / 0.20 | 0.229 (all-sets EM 0.05) |
| S2 isolation | rules+llm-sql | qwen2.5-coder:32b | **0.875** | 1.0 | — | — | — | 1.00 / 0.78 / 0.90 | **0.695** (all-sets EM 0.40; co-exist leak any 0.37, mean 0.37; not-loc FPR 0.00) |
| S3 counts-llm | counts-llm | qwen2.5-coder:7b | 0.655 on 400 (report tier 158/158 by fall-through); **cohort-only 0.430** | — | — | — | — | — | p agree **0.000** (n=198) |
| S3 counts-llm | counts-llm | qwen2.5-coder:32b | 0.725 on 400; **cohort-only 0.545** | — | — | — | — | — | p agree **0.020** (n=198) |
| **toolbox zs** | llm-s1+compiler / toolbox | **qwen2.5:32b-instruct** | **0.887** | 0.870 | 25 (all vaccine; 0 report-tier) | 0.611 | 0.789 | **1.00** / 0.80 / 1.00 | — |
| toolbox 3-shot | same, `--k-shot 3` | qwen2.5:32b-instruct | 0.915 | 0.912 | 32 (all report, cohort denominators) | 0.845 | 0.932 | 0.80 / 0.99 / 1.00 | — |
| **e2e toolbox zs, mixed** | llm-s1+llm-sql / toolbox | **S1 qwen2.5:32b-instruct + SQL qwen2.5-coder:32b** | **0.762** | 0.870 | 25 | — | — | 1.00 / 0.58 / 0.90 | 0.554 |
| catalogue + hints (lookup) | llm-s1+compiler / catalogue | qwen2.5:32b-instruct | 0.990 | 0.980 | 0 | — | — | 0.99 / 0.99 / 1.00 | — |
| S2 isolation | rules+llm-sql | qwen2.5:32b-instruct | 0.830 | 1.0 | — | — | — | 1.00 / 0.76 / 0.30 | 0.705 (all-sets EM 0.41; co-exist leak any 0.23; not-loc FPR 0.00) |
| register: research / media / clinical | toolbox zs | **qwen2.5:32b-instruct** | **0.772 / 0.855 / 0.840** | claim EM 0.728 / 0.818 / 0.795 | no-shape 55 / 52 / 26 | | | (original 0.887; report tier 0.93 / 0.87 / 0.94, cohort 0.67 / 0.85 / 0.77) | |
| register: research / media / clinical | toolbox zs | qwen2.5-coder:7b | 0.500 / 0.287 / 0.455 | | | | | (original 0.400) | |
| register: research / media / clinical | toolbox zs | qwen2.5-coder:32b | 0.357 / 0.335 / 0.395 | | | | | (original 0.410; all carry the report-tier 0) | |

**Readings.**
1. **The 32B compose failure is ONE shape.** All 158 report-tier plans (39.5% of
   the slice) carry a cohort denominator (`ordered_pair` 48, `all_present_unique_first`
   48, `orderable_triple` 24, `all_present_unique_last` 24, `both_present` 14) with
   `arms=1` and the right quantity/extreme; `derive_mode` finds no report mode and
   the record scores wrong. Identical under 3-shot (158/158). The prompt defines
   `single_report` (`extract/llm.py:190`). On the cohort tiers the 32B composes at
   0.678 zero-shot and 0.959 with three plans (lookup 0.987). **Issue 35**: decide
   whether `tier=report ⇒ denominator=single_report` is an IMPLIED fold (tier is an
   input field; "a single report has one arm" is already folded) or a genuine
   situation-recognition failure to report as such. Not folded here — the
   normalization set is the branch owner's call. If folded, 32B zero-shot ≈ 0.8.
2. **The few-shot leak grows as capability falls**: three worked plans are worth
   +0.17 to the 32B (0.41 → 0.58; cohort tier 0.68 → 0.96) against +0.04 to Opus.
3. **Instruct beats coder at S1 at 7B** (0.482 vs 0.400 zero-shot); the instruct-7B
   number replicates the other machine's 0.490 within 0.008 (187 vs 179 no-shape).
   `qwen2.5:32b-instruct` S1 runs are queued (zs, 3-shot, and e2e with coder-32B SQL).
4. **S2 at 32B: right verdict, wrong denominator.** 0.875 verdict with set F1 0.695
   and a co-exist leak on 37% of *precedes* records — the EHRSQL pattern (§10.3d):
   cores far from α forgive the denominator. Opus: 0.975 / 0.950 / 0.00. S2 is
   model-tier like S1, but its residual at 32B is conditioning, not syntax.
5. **Local models cannot compute the exact test at all**: p-value agreement 0.000
   (7B) and 0.020 (32B) with verdicts 0.655 / 0.725 — the verdict comes from the
   direction of the counts, not from the test. Opus: 0.66 agreement. Strongest
   support yet for "the model plans, the harness computes".
6. **End-to-end local** 0.320 (7B) / 0.302 (32B; report tier zeroed). The
   multiplicative picture holds on the cohort tiers (32B: 0.65 S1 × 0.78 S2 ≈ 0.51
   vs 0.46 measured).
7. **Registers**: the 7B swings by ±0.11 across registers; the 32B stays within 0.08.
8. **Which 32B matters (added 06:00).** `qwen2.5:32b-instruct` composes at **0.887**
   zero-shot (claim EM 0.870; report tier 1.000, cohort 0.814; 25 no-shape, none on
   the report tier) and 0.915 with three plans — 0.07 below Opus. So the coder-32B
   report-tier failure (reading 1) is model-specific, not a property of the frame;
   issue 35 stays open only as a scoring-policy question. The few-shot leak ranks
   inversely with composition strength: +0.03 (instruct-32B), +0.04 (Opus), +0.17
   (coder-32B). **Local headline configuration = instruct for S1, coder for SQL**:
   end-to-end 0.762 ≈ 0.887 × 0.875 (stages independent again; denominator F1 0.55).
   Curiously the instruct-32B's 32 three-shot no-shapes are ALL report-tier cohort
   denominators — the worked plans (all cohort-shaped) pull it toward the coder's error.
9. **SQL stays with the coder; registers cost the instruct-32B 0.03–0.12 (added 17:20).**
   instruct-32B on `rules+llm-sql`: 0.830 vs coder-32B 0.875 — the coder leaks more
   co-exist reports (37% vs 23%) but wins the two-cohort tier (0.90 vs 0.30), so the
   mixed configuration (instruct S1 + coder SQL) stands. Register sensitivity at the
   headline model: research 0.772 (claim EM 0.728, no-shape 55), media 0.855,
   clinical 0.840 against original 0.887; the loss is on the cohort tiers, where the
   register rewrites the statistical situation, not the event names. The 7B's ±0.11
   swings are noise around a low mean. Draft: `tab:registers`.

### 10.3f Attribution, faithfulness and abstention on both smoke slices (2026-10-08)

**S2 attribution + faithfulness** (`scripts/s2_attribution.py`; cohort records;
the failed-SQL cause counted since the 10-07 audit fix):

| run | records | wrong/failed denominators | verdict still right | faithfulness | dominant named causes |
|---|---:|---:|---:|---:|---|
| v1.1 S2 coder-7B | 242 | 224 | 12 | 0.10 | SQL failed 154, n=k 30 |
| v1.1 S2 coder-32B | 242 | 142 | 74 | 0.52 | SQL failed 54, event absent 46, n=k 18, co-exist leak 14, wrong cohort 10 |
| v1.1 S2 instruct-32B | 242 | 126 | 48 | 0.67 | event absent 42, n=k 36, SQL failed 34 |
| v1.1 e2e instruct+coder 32B | 242 | 156 | 48 | 0.56 | SQL failed 52, n=k 38, no plan 25 |
| v1.2 S2 coder-7B | 266 | 194 | 24 | 0.51 | SQL failed 94, n=k 24, event absent 16, co-exist 12, non-consecutive 10 |
| **v1.2 S2 coder-32B** | 266 | 100 | 26 | **0.81** | SQL failed 40, event absent 30, n=k 20 |
| v1.2 e2e instruct+coder 32B | 266 | 119 | 24 | 0.81 | SQL failed 39, n=k 35, no plan 19, event absent 14 |

The v1.2 slice carries the nine new groups, whose denominators the 32B gets
right (S2 at 1.0 on eight of them), which is why its faithfulness is higher
there; the two 32B failure modes that remain are the same two: a failed
statement and the eligible set defined as the supporting set (n = k).

**Abstention metrics** (`scripts/abstention_metrics.py`; cohort records; gold
from the compiler run on the same slice):

| run (v1.1 slice / v1.2 slice) | false-decisiveness | over-abstention | subtype acc | no-answer |
|---|---|---|---|---|
| S1 toolbox zs, instruct-7B | 0.000 / 0.022 | 0.061 / 0.129 | 0.943 / 0.977 | 0.384 / 0.335 |
| S1 toolbox zs, instruct-32B | 0.000 / 0.058 | 0.059 / 0.051 | 0.922 / 0.938 | 0.087 / 0.071 |
| S1 catalogue, instruct-32B | 0.000 / 0.000 | 0.000 / 0.000 | 1.000 / 1.000 | 0.008 / 0.004 |
| S2 coder-7B | 0.074 / 0.162 | 0.840 / 0.604 | 0.480 / 0.548 | 0 / 0 |
| S2 coder-32B | 0.037 / 0.000 | 0.255 / 0.323 | 0.692 / 0.784 | 0 / 0 |
| S2 instruct-32B (v1.1 only) | 0.000 | 0.319 | 0.778 | 0 |
| e2e instruct+coder 32B | 0.040 / 0.029 | 0.341 / 0.303 | 0.688 / 0.761 | 0.103 / 0.071 |
| counts-llm coder-7B | **0.148 / 0.216** | 0.670 / 0.646 | **0.000 / 0.000** | 0 |
| counts-llm coder-32B | **0.111 / 0.081** | 0.511 / 0.521 | **0.000 / 0.000** | 0 |

Readings: (1) with S1 as the only model stage, false-decisiveness is ~0 and
the subtype is right ~94% -- the deterministic S3 does the abstaining; (2) a
model-written S2 over-abstains (25-84%: failed or under-inclusive SQL becomes
insufficient) and mislabels the subtype a quarter of the time; (3) a model
computing the test itself INVENTS a result on 8-22% of gold-insufficient claims
and never names the right subtype -- the abstention counterpart of the p-value
finding. (4) The 7B's no-answer rate (34-38%) is the no-shape plans.

### 10.4 M3–M5 — designed, not built

M3 split + fine-tune (P0 / P1 / P2 table); M4 in-context B1, agent B2, single-pass
B3, `model-computed` variant; M5 write-up hooks (tables for the Overleaf draft,
issue 10). ~~API provider adapters land with whichever of these first needs them.~~ **2026-09-02: built** (`--provider`/`--sql-provider`; run configs now record provider + Ollama model digests).

---

## 11. Open questions

| # | question | kind | where |
|--:|---|---|---|
| 24 | P-V2 / P-V4 count-vs-rate wording (273 / 2,194 instances): reword, or accept and document? The faithfulness audit is DONE (`11a_template_faithfulness_audit.md`: 1 MISMATCH, 24 strong AMBIGUOUS, rewordings proposed) — the reword-vs-accept decision remains | decision | `open_questions.md` "Framework" |
| 26 | P3 paraphrase probe: hand-written, LLM-authored eval-only, or skipped? | decision (user) | `open_questions.md` "Framework" |
| 3 | Models to evaluate beyond the local 7B class: GPT-4.1 / Claude / Llama-3.3-70B / MedGemma-27B when budget exists; API budget itself | decision | `open_questions.md` "Evaluation" |
| 17 | The provisional split location (`data/splits/`, §8) and whether the release ever ships a split | decision | `09_next_steps.md` row 17 |
| 25 | `test_verdict` provenance defect (1,800 rows): regenerate or field-patch? Register only — the harness never reads the field | defect | `09_next_steps.md` row 25 |


## 11a S1 toolbox frame — BUILT 2026-09-30 (branch `s1-toolbox`; issues 29/31)

The evaluation protocol for S1 from decisions 2026-09-29 ("state every
stipulation, withhold only the mapping"), as implemented. `--s1-frame toolbox`
selects it; `catalogue` (the 20-row table) remains the procedure-given upper
bound.

**Prompt.** A **computed dataset card** (`extract/task_card.py`, from the eval
DB: report count, cohort sizes, vocabulary size, mean events per stage — the
geometry a model needs to see that 0.5 is not the chance rate for a single
event's position), the conventions phrased by *situation*, the four null
sources, the test toolbox with definitions, the six-step procedure (§13). No
mode names, no group ids, no per-mode H0, no mapping sentence — a test asserts
the prompt contains none of them. ~2.2K tokens against the catalogue's ~2.9K.

**Output — the conditional plan** (`PLAN_JSON_SCHEMA`, schema-constrained):
`events`, `negated`, `asserted_option`, **`quantity`** (what is measured:
order_of_pair / co_occurrence_of_pair / dominant_relation_of_pair /
ordering_of_triple / extreme_of_set), **`extreme`** (earliest | latest | none —
a required string, never null: v2 lost 86/400 plans to a null escape),
**`arms`** (1, or 2 when the quantity is COMPARED between two groups), the
**denominator primitive**, the **null recipe** (kind ∈ symmetric_fixed /
text_stated / data_derived / two_arm_equality / none, `p0`, `null_reference`),
`tail`, **`test_family`** + **`test_rule`** (exact_always |
exact_if_small_else_asymptotic), `min_n_floor`.

**Folding.** `derive_mode` is the inverse of `derive_procedure`: the plan's
`(tier, answer_type, n_events, arms, denominator, quantity, extreme)` maps to
exactly one of the 20 modes (a test proves the round trip), with the tier taken
from the input's `level`. `normalize_plan_shape` fills only what other fields
already IMPLY — a presence split is two arms, the first/last denominators name
their extreme, a single report has one arm, the legacy "rate_across_two_arms"
means "the pair's quantity, compared across arms" — and nothing that would need
the answer. A plan matching no mode is recorded as no-claim (the verdict is
wrong by construction) but its fields are still scored.

**Execution.** S2/S3 are unchanged. In `procedure-honouring`, S3 resolves the
plan's `test_rule` on the retrieved 2x2 (guard: every expected cell >= 5) and
runs either Fisher's exact or the one-sided two-proportion z
(`core.significance.two_proportion_z_p`, the asymptotic branch); the branch
taken is recorded in the prediction's notes. Fisher stays the gold test.

**Scoring** (`extraction.plan`): every plan field against `derive_plan(gold)`,
`plan_em`, and `rule_valid` (test family right AND the rule valid for that
family, `VALID_RULES`). Mode accuracy stays as a diagnostic.

**Few-shot as the leakage dial.** `--k-shot-exclude-groups` (P2: no example
from a held-out group) and `--k-shot-registers` (P1: examples rendered only in
the training registers). Under the toolbox frame a worked example IS a mapping
row, so these are the measured hint settings.

**Design lessons from the first two toolbox smokes (7B, v1.1 slice).** Three
of the four largest failure classes in v1 (0.39) and v2 (0.525) were the
reverse lookup being stricter than the semantics, not the model: a quantity
that conflated "what" with "compared across arms", `arms=1` on a presence
split, and the null escape on `extreme`. Each was fixed by normalization or by
removing the escape, never by consulting the answer. What remains after v3 is
the model's own composition: "A -> B -> C in this report" and "is A first of
the three" composed as a pair order; "B follows A more often than it follows C"
composed as one arm; the four-event contrast as a triple. Results: §10.3, rows
T1-v1..v3.

## 12 Related work (2026-09-29; four closest papers read in full, rest from abstracts)

Positioning against the benchmarks and systems that overlap with this benchmark's task. (NOTE 2026-09-30: VERITAS is an EXTERNAL system run as a baseline in §10.3 -- not our name; an earlier version of this section mislabelled our row.)
The four closest were read end to end against one rubric (input/output, who
formulates the null, who computes, temporal content, stage-level gold,
portability); the others from abstracts. Update this section before submission.

### 12.1 Statistical-analysis and hypothesis-testing benchmarks

- **P-Bench / Fisher-R1** — Miao, Mu, Chen, Zou. *Fisher-R1: Training LLM Agents
  for Reliable Hypothesis Testing.* arXiv:2608.07437 (Aug 2026).
  425 tasks (economics, biology, medicine): research question + **explicit H0/H1**
  + CSV in an R session + role-tagged glossary → p-value + reject/fail-to-reject.
  The agent chooses the method (a "reference-method family" labels Easy/Hard but
  is never scored); the model writes R that a sandbox runs; scoring is final-stage
  only (decision, and |z(p̂)−z(p*)|<0.5 for "strict"). Row eligibility is applied
  before the CSV is generated, so the denominator is not part of the task (except
  adversarial NA/outlier rows in Hard). Best: GPT-5.4 Easy 92.9 raw / 64.7 strict,
  Hard 58.3 / 30.5; Fisher-R1-7B (RL on 8,642 synthetic tasks) 87.0 / 65.7 Easy.
  Authors' stated gap: multi-test pipelines, multiple-comparison correction,
  explicit assumption justification.
- **StatABench** — Zhu, Ding, Lai, Wang, Jing, Chen. arXiv:2606.22977 (Jun 2026).
  404 closed questions over 18 topics + 30 open modelling tasks; practical items
  require calling one of 35 fixed SAToolKit functions (ks_test, logrank, cox,
  DiD, PSM, ...) with the right parameters — deterministic execution, single gold
  tool. Whether H0 is stated in the question is not stated; the model selects a
  TEST, it does not formulate a null. Final-answer scoring; tool choice analysed
  only post hoc (50% of failures). No clinical/EHR, no event-order content.
  Best: GPT-5.1 68.6.
- **StatFormBench** — Wang, Zhao, Cong, Deng, Deng. *Benchmarking Language Models
  for Statistical Problem Formulation.* arXiv:2609.01982, EMNLP 2026 main.
  1,013 (background, request, data) triples → problem CATEGORY (20 coarse / 85
  fine, e.g. "Proportion Test", "Independence Test") + variable set with roles.
  The only benchmark whose target is formulation, but the output is a family
  label, not a null statement, and nothing is computed. Few-shot / category
  definitions add only +1.9–3.8. Best fine accuracy 72.0 (Gemini 3.1 Pro).
- **StatQA** — Zhu et al. 2024, https://statqa.github.io/ — 11,623 items on
  method applicability and variable selection for pre-formulated questions over
  tables. **StatEval** (Lu et al., arXiv:2510.09517), **StatLLM** (Song et al.,
  arXiv:2502.17657; SAS code), **QRData** (Liu et al. 2024): statistical reasoning
  or code generation with the analysis target given or strongly implied.

### 12.2 LLM-assisted hypothesis testing systems (clinical)

- **LATCH** — Gim et al. *An LLM-assisted framework for accelerated and verifiable
  clinical hypothesis testing from electronic health records.* medRxiv
  10.64898/2026.02.10.26346008 (Feb 2026); PMC12919150; code
  github.com/latch-project/LATCH. The closest ARCHITECTURE: an LLM semantic layer
  (planner JSON, variable mapping, cohort SQL) over a deterministic statistics
  engine (fixed R pipelines); the LLM never touches patient rows. Portable to
  "any standardized structured health dataset" via a schema summary table. But
  the user supplies **both the hypothesis and the method**; validation is
  concordance with 20 published NHANES/AI-READI studies (cohort n, direction,
  CI overlap), not an independent per-stage gold; data are cross-sectional
  survey/registry tables, so no event-order claims.

### 12.3 Data-driven discovery agents

- **DiscoveryBench** — Majumder et al., ICLR 2025, arXiv:2407.01725. 264 tasks
  from published workflows; open-ended hypothesis search + verification, no
  prescribed statistics; peak 25%.
- **BLADE** — Gu et al., arXiv:2408.09667. 12 datasets; scores the analysis
  DECISIONS of agents against expert analyses.
- **ProjectionBench** — arXiv:2605.30284: progressive disclosure from a research
  question down to the classical null test.
Discovery, not verification: open-ended, rubric- or expert-judged, no computable
truth value per claim.

### 12.4 Temporal reasoning over clinical records

- **CRAFT** — arXiv:2608.12779: iterative LLM extraction of stage-by-stage symptom
  timelines from narratives (this project's predecessor; MedTempo is its corpus).
- **TIMER** — npj Digital Medicine 2025, arXiv:2503.04176: time-aware instruction
  tuning over multi-visit EHRs.
- **CliniCIRCA** — arXiv:2609.19585: date-resolved longitudinal patient journeys.
These extract or reason over timelines; none poses statistical hypotheses over
them or verifies a claim against a computed test.

### 12.5 The gap, stated against the table

| | null formulated by the model | deterministic execution | event-ORDER claims | clinical timelines | gold at every stage (incl. denominator) | dataset-in interface |
|---|---|---|---|---|---|---|
| P-Bench / Fisher-R1 | no (H0 given; test chosen, unscored) | no (model R in sandbox) | no | partly | no | no |
| LATCH | no (hypothesis + method given) | **yes** | no | yes (survey/registry) | partial (vs published n / CI) | **yes** (schema summary) |
| StatFormBench | family label only | nothing executed | no | textbook | formulation only | no |
| StatABench | test selection, no null | yes (tool calls) | no | no | final answer only | no |
| DiscoveryBench / BLADE | open-ended | agent code | no | no | rubric / expert | no |
| **This work** | **yes** (null recipe: kind, p0 or its computation, reference population; toolbox frame, issue 29) | **yes** (`procedure-honouring`) | **yes** (precedes / co-occur / sequence / first-last) | **yes** (annotated VAERS timelines) | **yes** (claim, evidence set, counts, p, verdict) | task card (planned; LATCH's schema-summary pattern) |

No prior work combines model-formulated nulls, deterministic execution, and
per-stage gold; none poses event-order hypotheses within records; none scores
the eligibility (denominator) rule as a stage — which e2e-sql (§10.3b) showed is
where systems fail. Caveats to keep honest: null DIVERSITY is thin today (three
cohort signatures; issue 20 is the fix); the portability claim needs at least one
external dataset actually run (LATCH's interface is the precedent, not ours);
arithmetic fragility is corroborated by P-Bench's strict metric (frontier 64.7%
on Easy) and our counts-llm (66% p agreement).


## 13 S1 expert knowledge: formulating the null and the test plan (2026-09-29)

The content the toolbox task card must carry -- what a statistician knows that a
catalogue row hides. Written to be lifted into the S1 prompt (issue 29) and into
the paper's method section. Nothing here is keyed to a mode label.

### 13.1 Four sources of null, and which one a claim needs

| source | when | the null | example |
|---|---|---|---|
| **symmetric-fixed** | the claim orders TWO named events, or names one of k candidates | p0 = 0.5 by swap symmetry (exact); argmax: named cell vs its largest competitor at 0.5 | "A precedes B" -> P(A before B) = 0.5 over reports with both at distinct stages |
| **text-stated** | the wording carries a quantitative bar | p0 = the bar | "in at least two-thirds of reports" -> p0 = 0.667 (families N3/N4) |
| **data-derived** | the claim is about ONE event's position relative to the report's timeline | p0 = the structural rate of the reference population, computed from the data | "is A typically early?" -> p0 = fraction of slots in the early half over the reports the claim conditions on (0.5327 corpus-wide; per-core) |
| **two-arm equality** | the claim compares a rate between two groups | p1 = p2 -- a comparison, not a number (Fisher conditions on the margins) | "B follows A more often than it follows C"; "after v1 more than after v2" |

**Why the data-derived null exists (doc 10 §4.3).** The symmetry argument for
0.5 -- "each stage rank is equally likely" -- fails because stages are not
equally populated (mean 2.45 events at stage 0, 2.21 at 1, 1.84 at 2, ~1.74
after). A random slot is more likely to be early, so the corpus-wide structural
early rate is 0.5327 and varies per cohort and core. Testing against 0.5
manufactures support: permutation-null mean 15.2% of cores decisive against
alpha = 5% (37 supported / 31 refuted); against the structural rate 5.3%
(22 / 37). Pair-order claims are unaffected -- swapping A and B is a symmetry of
the same shuffle -- which is why the bias never surfaced in the shipped roster.
Boundary: comparing ONE event's position ACROSS cohorts is invalid (issue 21).

### 13.2 The statistician's procedure (to be phrased in the task card)

1. **Identify the claim shape**: what quantity is asserted; how many named
   events; how many arms; one named report or a population.
2. **Decide what "chance" means for that quantity**: a swap symmetry -> 0.5; a
   stated bar -> that bar; no symmetry (a single position against the timeline's
   geometry) -> a rate that must be COMPUTED from the data; two arms -> equality.
3. **Name the reference population of the null** -- which reports the rate is
   computed over. This is a denominator choice of its own and is scored.
4. **Write the null as a recipe**: kind, statistic, reference population, p0 or
   the computation that yields it; the tail from the claim's direction.
5. **Choose the test FAMILY and a selection RULE** conditional on the data facts
   that arrive only after retrieval (n, expected cells) -- never a single fixed
   test.
6. **State the gate**: the min-n floor and that below it the verdict is
   `insufficient`.

Division of labour: S1 states the recipe and the rule; S2 retrieves the
denominator (and the reference population for a data-derived p0); S3 computes
p0 where needed, resolves the rule on the actual counts, runs the branch.

### 13.3 The conditional plan -- S1's output

The procedure is planned before retrieval but test validity depends on n, which
exists only after it. Pre-registration solves this: the plan is a decision rule
over data facts, resolved by S3. Example for an association claim:

```
events: [Fatigue, Headache]        compare: rate of B across two arms
denominator: presence_split(A) over the whole cohort
null: {kind: two_arm_equality}     tail: greater
test_rule: fisher_exact if min expected cell < 5 else chi_square
gate: floor 10 per arm -> insufficient below
```

The min-n gate already works this way (stated up front, resolved after
retrieval); `procedure-honouring` now runs the model's stated RULE. Scored in
three layers: the family (right comparison), the rule (selects a valid test at
every n it could meet -- §13.4), the resolution (S3's branch matches the counts).
A stricter method score than P-Bench, which never grades the method.

### 13.4 Method adjudication as guards (replaces "exact tests only" as a slogan)

Principle: **every gold-producing test must be valid at the instance's n.** The
2026-08-11 exact-only lock is the small-n branch of this rule, not a separate
constraint. Equivalence classes, to be completed when the toolbox is widened:

| claim family | valid members | guard |
|---|---|---|
| single proportion vs p0 | `binom_exact` | always |
| | normal approximation | n*p0*(1-p0) large enough -- never at our floors |
| two proportions | `fisher_exact` | always |
| | `chi_square` | every expected cell >= 5 (asymptotic) |
| named cell vs competitor (argmax) | `modal_runner` (exact binomial on the two cells) | always |
| k-category distribution | exact multinomial / Fisher-Freeman-Halton | always |
| magnitude / rank ("how much earlier") | exact conditional permutation distribution (enumerated, ties conditioned) | only as exact enumeration; the normal-approximation rank tests stay descriptive (issue 16) |

On this corpus every guard resolves to the exact branch; on a large external
dataset (P-Bench, NHANES) the asymptotic branches fire -- the same plan is
scored the same way, which is what makes the S1 output portable.

### 13.5 What the dataset card must carry for the inference to be possible

Representation (leveled orders; a term's position is its first mention; cohort
= vaccine, report = VAERS id); the **stage-population summary** (mean slots per
stage -- without it a model cannot know the symmetry fails; alternatively the
agent variant queries it); cohort sizes and typical counts per claim shape (so
the regime of the test rule is anticipated); the vocabulary; the conventions,
situation-phrased (decisions "state every stipulation"); the toolbox with
definitions (§13.4). This is LATCH's schema-summary pattern applied to a
timeline corpus.


### 10.3g The v1.2-FINAL smoke rows (2026-10-08; both GPUs; `results/v12f_smoke200_*`, `results/chains/v12f_*.sh`)

Every row below is on the final v1.2 release (cap 600, pseudonymised ids,
conventions v2.1) and the new slice `smoke_200_v1.2_s0` (200 instances over all
29 groups; 400 records). The pre-final v1.2 rows of §10.3f are superseded. The
full table with stage metrics is `docs/plan/results_v12f_smoke200.md`
(generated from `metrics.json`, `scripts/abstention_metrics.py` and
`scripts/s2_attribution.py`); the headline statistic is the COHORT column
(vaccine + multi tiers; review item 6).

| row | all | cohort | den-F1 | faithfulness | over-abstention |
|---|---:|---:|---:|---:|---:|
| S1 catalogue lookup 32B (answer-injected) | 0.998 | 0.996 | 1.000 | -- | 0.00 |
| S1 toolbox zero-shot 32B, rounds 0 / +1 verify | 0.897 / **0.915** | 0.845 / **0.872** | 0.879 / 0.890 | -- | 0.09 / 0.10 |
| S1 toolbox zero-shot 7B, rounds 0 / +1 | 0.605 / 0.650 | 0.554 / 0.624 | 0.633 / 0.694 | -- | 0.14 / 0.11 |
| S1 32B registers research / media / clinical (1 round; original 0.915) | 0.840 / 0.887 / 0.882 | | | | |
| S2 coder-32B, rounds 0 / +2 | 0.810 / **0.880** | 0.705 / **0.814** | 0.654 / 0.804 | 0.75 / 0.85 | 0.40 / 0.24 |
| S2 coder-7B, rounds 0 / +2 | 0.615 / 0.660 | 0.403 / 0.473 | 0.322 / 0.350 | 0.35 / 0.46 | 0.69 / 0.59 |
| A e2e schema only, 32B / 7B | 0.297 / 0.417 | 0.360 / 0.283 | 0.198 / 0.104 | 0.10 / 0.32 | 0.73 / 0.91 |
| B e2e + conventions, 32B / 7B | 0.527 / 0.400 | 0.523 / 0.314 | 0.477 / 0.150 | 0.36 / 0.27 | 0.48 / 0.87 |
| D plan + conventions, 32B rounds 0 / +2 | 0.537 / **0.645** | 0.446 / **0.612** | 0.526 / 0.688 | 0.48 / 0.72 | 0.49 / 0.27 |
| E plan + consistency re-ask, 32B | 0.632 | 0.593 | 0.685 | 0.64 | 0.24 |
| D / E at 7B (C2 0.417) | 0.362-0.398 | 0.198-0.252 | 0.18 | 0.26-0.33 | 0.64-0.67 |
| counts-given judgment 32B / 7B | 0.705 / 0.650 | 0.543 / 0.457 | (given) | 1.00 | 0.55 / 0.62; subtype acc 0.00 |

**Findings.**
1. **The verifier pays at every stage and every size**: S1 +0.018 at 32B
   (+0.045 at 7B); S2 +0.070 at 32B (den-F1 0.654 -> 0.804, faithfulness
   0.75 -> 0.85), +0.045 at 7B; the composed system D +0.108 (cohort +0.166,
   faithfulness 0.48 -> 0.72, co-exist leak 0.29 -> 0.15).
2. **On v1.2 the decomposition does NOT beat e2e+conventions by itself**: D at
   rounds 0 is 0.537 vs B 0.527 overall and BELOW it on the cohort tiers
   (0.446 vs 0.523). Per family, D r0 loses on pairwise (0.45 vs 0.64: C-V1
   0.12, P-V2 0.00, P-V4 0.14; the plan-frame coder-32B returns n = k
   denominators (63) and invalid SQL (48) on the comparative shapes) and on
   threshold (0.33). With two rounds D recovers pairwise to 0.62, threshold
   0.71, P-V4 0.86, P-V3 0.83. The v1.1 ordering (B 0.52 < D 0.67) therefore
   needs the verifier on v1.2: architecture + verification, not architecture
   alone, is what beats information alone. E (single re-ask) sits between
   (0.632; faithfulness 0.64).
3. **Information alone is worth more on v1.2 than on v1.1**: A -> B +0.23 at
   32B (v1.1: +0.14); at 7B B is below A (0.400 vs 0.417) -- the 7B cannot use
   the conventions.
4. **Registers** at 32B: research -0.075, media -0.028, clinical -0.033 against
   original (0.915); at 7B the swings are noise around 0.6.
5. **Counts-given judgment** is still the floor that verdict accuracy hides:
   0.705 overall but 0.543 on the cohort tiers, false-decisiveness 0.17, subtype
   accuracy 0.00, p-agreement 0.03.
6. **C-V2 (assoc_bool) is 0/18 under the toolbox at 32B** -- and this is NOT
   new: on v1.1 the same 32B composed every C-V2 record as ONE-ARM
   co-occurrence (`sym_bool_cooccurs`, 22/22; v1.2-final 18/18); v1.1's 0.27
   was six verdicts that happened to agree. The gold is the two-arm Fisher
   test (rate of B among reports with A vs without A); the wording "occur
   together more often than their separate rates would predict" is faithful
   to it. Under the catalogue the mode is given (1.00); zero-shot, the 32B
   never composes the two-arm shape -- the same error the draft already
   records for Opus on v1.1 ("association composed as plain co-occurrence").
   The earlier note in this section that blamed the wording was wrong
   (corrected 2026-10-08 22:00). **Issue 42** is therefore a conventions gap:
   the toolbox text states a stipulation for every other situation but not
   for "more often than their separate rates would predict" (= two arms,
   presence split, equality null). Whether to add that sentence is the
   user's call (it is wording-level information, like the majority sentence).
   **Decided and measured (conventions v2.2, 22:46):** the bullet now bridges
   the association wordings; the S1 zero-shot 32B row re-run with ONLY that
   sentence changed goes **0.897 -> 0.950** (cohort 0.845 -> 0.922; claim EM
   0.897 -> 0.945; mode accuracy 0.912 -> 0.960; no-shape plans 17 -> 8).
   23 of 29 groups are unchanged record for record; C-V2 0.00 -> 0.67 (12/18
   now composed as the two-arm shape), H-V3 0.00 -> 1.00 (the sentence's
   "only same-stage wording is co-occurrence" also fixed the co-occurrence
   bar), P-V2 0.25 -> 0.42; one record each lost on P-V3 and Y-V3. Every
   S1-dependent row (verify-1, registers, cells D / E) is re-run on v2.2 for
   the final table.
8. **The `vaers_id -> report_id` rename cost SQL validity -- issue 43.** The
   SQL-writing rows regressed on the OLD 20 groups only (A 0.380 -> 0.275,
   C 0.875 -> 0.758, D r0 0.665 -> 0.523; B unchanged 0.522 -> 0.520; S1
   unchanged 0.887 -> 0.893), and the new groups are EASIER (C 0.961). The
   executor logs show why: failed statements rose from 52 -> 86 (C), 17 -> 48
   (D), 117 -> 170 (A), and the new dominant error is a DANGLING ALIAS copied
   from the view definitions in the DDL -- `SELECT lt.report_id ... FROM
   first_mention fm_a JOIN first_mention fm_b` (`lt.report_id` 117 in A, 33 in
   D; `f.report_id` 38 in C). With `vaers_id` the same copying happened at a
   quarter of the rate (A: 24). This is a prompt artefact of the rename, not
   the data and not the method; the verify rounds already repair most of it
   (C+2: 36 failures left, D+2: 11). Controlled test queued: the same rows
   with the schema shown as table/column LISTINGS (view semantics in comments,
   no SELECT bodies to copy aliases from; `--ddl-style listing`).
   **Step 1 result (listing DDL, same rows, 22:10):** the copied-alias error is
   gone everywhere, and the S2 row (gold plan) recovers: C failed statements
   86 -> 42 (v1.1: 52), denominator F1 0.654 -> 0.761 (v1.1: 0.695), verdict
   0.810 -> 0.830, old groups 0.758 -> 0.779 -- SQL validity is no longer the
   gap there; the remaining 0.10 to v1.1 on the old groups comes with a BETTER
   denominator F1, i.e. it is the re-drawn instances, not the SQL. In the
   sentence->SQL and plan->SQL frames the error only MOVED: A 170 -> 197 and D
   48 -> 92 failed statements, now `ambiguous column name: report_id` (157 / 57)
   -- without the view bodies the coder writes an unqualified `report_id` in a
   self-join of first_mention (v1.1's A had the same error on `vaers_id`, 60).
   A 0.297 -> 0.378, D 0.537 -> 0.520 (cohort 0.446 -> 0.380). **Step 2
   (queued, `_ddl_listing_hint`)**: the row contract now says to select the id
   as `<alias>.report_id AS report_id` in a self-join (uniform across cells);
   A / B / D re-run with listing + hint.
   **Step 2 result (listing + hint, 00:33):** failed statements A 170 -> 34,
   B 89 -> 16, D 48 -> 23 (v1.1 D: 17); A 0.297 -> **0.502** (old groups 0.275 ->
   0.490, ABOVE v1.1's 0.380), B 0.527 -> 0.588, D r0 0.537 -> 0.573 (old groups
   0.523 -> 0.607; v1.1 0.665). The errors that remain are semantic (co-exist
   leak A 0.60, B 0.47), which is what the benchmark is about. B and D in this
   step also carry conventions v2.2 (their prompts include the conventions
   block), so their gains are hint + v2.2 together; A has no conventions and
   is the clean hint effect. On the OLD groups the plan frame beats the
   sentence frame again at rounds 0 (D 0.607 vs B 0.540, as on v1.1); on the
   NEW families D r0 is below B -- plan -> SQL does not translate the new
   denominators (consecutive_pair, present_offmid, bars) without the verifier.
   **Final prompt configuration (2026-10-10): conventions v2.2 + listing DDL +
   self-join hint**; `--ddl-style listing` is the run_eval default. Every
   SQL-writing row is re-run under it for the final table
   (`results/v12f_smoke200_*_final`).
7. Pre-final -> final drift on the same groups: S1 32B 0.863 -> 0.897 (v2.1
   text + the rewording), S2 32B 0.840 -> 0.810 (rounds 0) and 0.880 -> 0.880
   (rounds 2); the slice changed (cap, pseudonyms), so these are not paired.


### 10.3h THE v1.2 TABLE: every row under the final prompt configuration (2026-10-10)

Conventions v2.2, listing DDL, self-join hint (decisions.md 2026-10-10); slice
`smoke_200_v1.2_s0`; `results/v12f_smoke200_*_final` (S1 rows: `*_conv22*`;
counts rows unchanged). Cohort = vaccine + multi tiers (258 records).

| row | all | cohort | den-F1 | faithfulness | over-abstention |
|---|---:|---:|---:|---:|---:|
| S1 catalogue lookup 32B (answer-injected) | 0.998 | 0.996 | 1.000 | -- | -- |
| S1 toolbox zero-shot 32B / +1 round | 0.950 / 0.955 | 0.922 / 0.930 | 0.946 / 0.954 | -- / -- | -- / 0.04 |
| S1 toolbox zero-shot 7B / +1 round | 0.595 / 0.657 | 0.558 / 0.655 | 0.638 / 0.721 | -- / -- | -- / 0.10 |
| C  S2 coder-32B, rounds 0 / +2 | 0.900 / 0.905 | 0.845 / 0.853 | 0.767 / 0.803 | 0.73 / 0.79 | 0.22 / 0.20 |
| C  S2 coder-7B, rounds 0 / +2 | 0.570 / 0.620 | 0.349 / 0.426 | 0.196 / 0.359 | 0.29 / 0.55 | 0.87 / 0.70 |
| A  e2e schema only, 32B / 7B | 0.502 / 0.440 | 0.562 / 0.275 | 0.441 / 0.101 | 0.21 / 0.23 | 0.44 / 1.00 |
| B  e2e + conventions, 32B / 7B | 0.588 / 0.380 | 0.543 / 0.279 | 0.517 / 0.124 | 0.28 / 0.18 | 0.38 / 0.94 |
| D  plan + conventions 32B, rounds 0 / +2 | 0.573 / 0.645 | 0.453 / 0.566 | 0.525 / 0.611 | 0.35 / 0.71 | 0.57 / 0.42 |
| E  plan + consistency re-ask, 32B / 7B | 0.652 / 0.263 | 0.578 / 0.171 | 0.615 / 0.234 | 0.71 / 0.48 | 0.40 / 0.72 |
| D  7B rounds 0 / +2 (C2 7B 0.365) | 0.287 / 0.295 | 0.209 / 0.221 | 0.238 / 0.230 | 0.39 / 0.37 | 0.71 / 0.69 |
| counts-given judgment 32B / 7B | 0.705 / 0.650 | 0.543 / 0.457 | 1.000 / 1.000 | -- / -- | -- / -- |

**Reading.** (1) Each stage alone is 0.90-0.96 at 32B (planner 0.955 with one
round, SQL stage 0.905 with two). (2) The composed system WITH the verifier is
the best end-to-end system: D+2 0.645 / E 0.652 against B 0.588 (cohort 0.566 /
0.578 vs 0.543) -- a modest verdict margin, and a large evidence margin:
faithfulness 0.71 vs 0.28, co-exist leak 0.07 vs 0.47. Without the verifier
the composed system is level with B (0.573 vs 0.588): the loss is in handing
the plan to the SQL stage, and the repair rounds recover about half of it.
(3) The 7B tier is a capability floor: the composed pipeline (0.29) is BELOW
plain sentence->SQL (0.44); stating the conventions to the 7B costs accuracy
(B 0.38 < A 0.44). (4) Counts-given judgment (0.705) is handed the gold counts
and is not a competitor; its cohort-tier 0.543 with subtype accuracy 0 is the
floor of "the model does the statistics itself". (5) Over-abstention: our
rows 0.40-0.42, B 0.38, A 0.44, S2-alone 0.20; the planner alone 0.04.


### 10.3i eval_core v1.2 -- the full experiment under the final configuration (2026-10-10/11)

`--subset eval_core` (2,350 instances, original register, question + claim =
4,700 records; cohort tiers 3,080 records), conventions v2.2 + listing DDL +
hint; `results/core_v12_*`; table also in `docs/plan/results_core_v12.md`.
Wall time: S1 7.7 h, S2+2 7.7 h, A 7.3 h, B 7.0 h, D+2 19.2 h, E 1.4 h (cached
S1), D r0 0.6 h (cached), counts 0.3 h -- two GPUs, ~30 h.

| row (32B; eval_core: 2,350 instances, 4,700 records) | all | cohort tiers | report tier | den-F1 | co-exist leak | faithfulness | false-decisive | over-abstain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 our planner 32B + 1 round (gold S2/S3) | 0.954 | 0.931 | 0.999 | 0.944 | 0.00 | -- | 0.02 | 0.04 |
| C  S2 coder-32B + 2 rounds (gold plan) | 0.880 | 0.816 | 1.000 | 0.797 | 0.18 | 0.81 | 0.02 | 0.26 |
| A  e2e sentence->SQL, schema only | 0.466 | 0.494 | 0.412 | 0.455 | 0.64 | 0.21 | 0.22 | 0.49 |
| B  e2e + conventions | 0.590 | 0.525 | 0.713 | 0.570 | 0.40 | 0.32 | 0.24 | 0.42 |
| D  our pipeline, no verifier | 0.555 | 0.476 | 0.704 | 0.542 | 0.16 | 0.29 | 0.14 | 0.57 |
| D+2 our pipeline + 2 verify rounds | 0.646 | 0.615 | 0.704 | 0.663 | 0.08 | 0.74 | 0.13 | 0.36 |
| E  our pipeline + consistency re-ask | 0.642 | 0.609 | 0.704 | 0.656 | 0.13 | 0.71 | 0.12 | 0.36 |
| counts-given judgment (gold counts) | 0.739 | 0.602 | 1.000 | 1.000 | 0.00 | 1.00 | 0.18 | 0.48 |


**Reading (matches the 200-slice within noise).** Our planner 0.954, our SQL
stage 0.880; the composed pipeline with the verifier 0.646 (cohort 0.615)
against the best end-to-end system 0.590 (cohort 0.525): +0.06 on the verdict
overall and +0.09 on the cohort tiers, and faithfulness 0.74 vs 0.32 with
co-exist leak 0.08 vs 0.40. Without the verifier the pipeline is below B on the
verdict (0.555) but already ahead on evidence (leak 0.16, den-F1 0.54 vs 0.57).
E equals D+2 (0.642). The report tier is where B gains (0.713 vs our 0.704,
both far below the planner's 0.999: the plan->SQL hand-off loses report-tier
claims that S1 alone reads perfectly). Counts-given 0.739 overall / 0.602 cohort
with false-decisiveness 0.18.


### 10.3j The verified end-to-end control, the plan-as-contract pipeline (D'), and EHRAgent on v1.2 (2026-10-11/12)

Slice `smoke_200_v1.2_s0` (400 records; 258 cohort-tier), final prompt
configuration. The question (user, 10-11): if e2e + verifier matches our
pipeline + verifier, what is the architecture worth?

| row (32B) | all | cohort | den-F1 | co-exist leak | faithfulness | false-decisive | over-abstain |
|---|---:|---:|---:|---:|---:|---:|---:|
| B  e2e + conventions | 0.588 | 0.543 | 0.517 | 0.47 | 0.28 | 0.24 | 0.42 |
| **B+2  + 2 repair rounds, PLAN-FREE checks** (executor errors, n = k, empty-vs-nonempty arms) | 0.660 | 0.655 | 0.643 | 0.56 | 0.53 | 0.15 | 0.22 |
| A+2  schema only + 2 rounds | 0.530 | 0.605 | 0.498 | 0.79 | 0.28 | 0.19 | 0.29 |
| D  our plan -> S2 told the plan in PROSE + conventions | 0.573 | 0.453 | 0.525 | 0.15 | 0.35 | 0.06 | 0.58 |
| D+2 | 0.645 | 0.566 | 0.611 | 0.07 | 0.71 | 0.04 | 0.42 |
| **D'  our plan -> the harness resolves the plan's named primitive to its definition for S2** (= the C2 frame at 32B) | 0.855 | 0.775 | 0.717 | 0.15 | 0.75 | 0.01 | 0.27 |
| **D'+2** | **0.865** | **0.791** | **0.763** | 0.16 | **0.78** | **0.00** | 0.26 |
| C  gold plan, same frame (+2) | 0.905 | 0.853 | 0.803 | 0.16 | 0.79 | 0.00 | 0.20 |
| EHRAgent 32B, variant A (minimal; agent picks and RUNS the test; verdict parsed) | 0.743 | 0.624 | n/a | n/a | n/a | **0.64** | 0.07 |
| EHRAgent 32B, variant B + conventions (agent's counts -> our exact test) | 0.405 (report tier n/a) | 0.628 | n/a | n/a | n/a | 0.23 | 0.22 (no answer 10%) |
| EHRAgent 32B, variant B minimal | 0.297 | 0.461 | n/a | n/a | n/a | 0.51 | 0.28 |

**Findings.**
1. **The user's worry was right about the prose pipeline.** Given the plan-free
   checks, the end-to-end model with the conventions reaches 0.660 / cohort
   0.655 -- level with (on the cohort tiers above) our prose-plan pipeline
   with its verifier (0.645 / 0.566). On the verdict, verification alone
   explains that gap. The evidence does not follow: B+2's faithfulness is
   0.53 with a co-exist leak of 0.56 (the repaired queries execute and still
   include same-stage reports), against 0.71 / 0.07 for D+2.
2. **The architecture gain is real once the plan is used as a CONTRACT.** When
   the harness resolves the model's plan -- its named denominator primitive --
   into that primitive's definition for S2, instead of handing S2 the plan as
   prose plus the whole conventions text, the composed pipeline goes to 0.855
   (cohort 0.775) and 0.865 with the verifier: +0.20 over the verified
   end-to-end control, faithfulness 0.78 vs 0.53, false-decisiveness 0.00 vs
   0.15, within 0.04 of the gold-plan row. Nothing on the baseline side
   changed; D' uses only the model's own plan. This is the pipeline as it
   should be built: the plan is a structured object and the stage contract
   carries it. (Implementation note: today the S2 frame keys the definition by
   the plan's derived mode, `RULE_BY_MODE`; the paper describes and the code
   should key it by the plan's primitive -- same text, honest naming.)
3. **EHRAgent at 32B on v1.2** (4 h per run; the earlier 16-20 h estimate was
   wrong): variant A 0.743 overall / 0.624 cohort -- competitive with every row
   except D' on the verdict, but it decides 64% of the claims the data cannot
   decide (false-decisiveness 0.64; only 37 of 258 cohort answers are
   'insufficient'), its evidence cannot be audited (the agent returns a verdict,
   not report sets), and the report tier (0.96) is where most of its overall
   number comes from. Variant B + conventions (counts -> our test) 0.628 cohort
   with 10% no answer; minimal 0.461. Stating the conventions is worth +0.17
   to the agent, as it was to the single-query model.
4. **Paper claim, revised:** "a plan that is a contract" -- stated conventions,
   a structured plan resolved by the harness for the retrieval stage, and
   bounded verification -- beats the strongest verified end-to-end system by
   0.20 and the agentic baseline by 0.12 on the verdict, and by 0.25-0.50 on
   whether the evidence is right. Core-set runs of B+2 and D' / D'+2 are
   running (`core_v12_*`).

**Addendum 2026-10-12 (core set, `core_v12_*`): the verified e2e control and D'.**

| row (32B; 4,700 records; 3,080 cohort) | all | cohort | report | den-F1 | leak | faithfulness | false-decisive | over-abstain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B+2  e2e + conventions + 2 plan-free repair rounds | 0.669 | 0.645 | 0.713 | 0.699 | 0.50 | 0.64 | 0.22 | 0.26 |
| D'   our plan, named primitive resolved for S2 | 0.831 | 0.743 | 0.999 | 0.705 | 0.18 | 0.75 | 0.04 | 0.31 |
| **D'+2** | **0.856** | **0.781** | 0.999 | 0.752 | 0.17 | **0.78** | 0.03 | 0.26 |
| (D+2, prose plan, for reference) | 0.646 | 0.615 | 0.704 | 0.663 | 0.08 | 0.74 | 0.13 | 0.36 |
| (C+2, gold plan) | 0.880 | 0.816 | 1.000 | 0.797 | 0.18 | 0.81 | 0.02 | 0.26 |

The slice ordering holds at scale: verified e2e 0.669 vs the prose pipeline
0.646 (level on the verdict; evidence 0.64 vs 0.74, leak 0.50 vs 0.08,
false-decisiveness 0.22 vs 0.13); the plan-as-contract pipeline 0.856 (cohort
0.781) is +0.19 over the verified e2e and 0.024 below the gold-plan row, with
the report tier solved (0.999) because the resolved `single_report` primitive
is the compiler's whole-report query. Headline rows for the paper: D'+2 vs
B+2 vs EHRAgent-A, with C+2 and the planner as the stage ceilings.


### 10.3k VERITAS (ECCV 2026) on the v1.2 dev slice, final adaptation (2026-10-13)

`~/veritas_baseline`, condition D = exact-test pool pre-bound + conventions v2.2;
Coder-32B, 8k context (16k offloaded 5% to CPU and halved speed), minimal
verbosity, 3,072 output tokens, 10-minute phases, no retries; 129 cohort-tier
claims (claim form), group-interleaved, two shards on the two GPUs, 07:04
finish (~11 h). **Completed 50/129 (39%)**; verdict accuracy with failures as
misses **0.349** (ECO label 0.302; binary 0.667); gold supported 45 -> 3 right,
refuted 48 -> 13, insufficient 36 -> 29; false-decisiveness 7/36 = 0.19; test
used matches the gold exact test 0.147 (none 95, Fisher 26, runner-up 5,
binomial 2, t-test 1). Reading: with the same information and tools as the
other systems, VERITAS mostly cannot get a claim through its three phases in
30 minutes at 32B, and when it does it abstains -- the opposite failure to
EHRAgent-A. Near the 0.33-0.37 floors, as on v1.1 (0.333 / 0.308 on 39 claims).
Test-slice run (120 claims) in progress behind EHRAgent on the test slice.


### 10.3l EHRAgent 32B on the TEST slice (test_200_v1.2; 2026-10-13)

Same adaptation as 10.3j. Variant B + conventions (counts -> our test): cohort
0.58 (139/240; report tier n/a; 44% no parseable counts). Variant A (runs its
own test): 0.743 overall, cohort 0.63 (151/240), report 0.91, 3% no answer.
Dev slice was 0.628 / 0.624 cohort -- the agentic baseline's numbers transfer.


### 10.3m VERITAS on the TEST slice (test_200_v1.2, 120 cohort claims; 2026-10-13 23:01)

Same condition as 10.3k. Completed 47/120 (39%); verdict accuracy with failures
as misses **0.317** (binary 0.642); supported 48 -> 8 right, refuted 46 -> 9,
insufficient 26 -> 21; test matches gold 0.142. Dev slice 0.349: consistent.
The held-out run of our rows was HELD (user, 23:00) pending the new split
design (dev = the 200-instance slice; test ~1,200 fact-disjoint; train = rest).

### 10.3n Case studies for the dev slice: repair rounds, and paraphrase for the full pipeline (2026-10-14 00:50)

Both run on the 200-instance dev slice, final configuration, 32B-Instruct S1 +
32B-Coder S2. Decided 2026-10-13 (user): these are case studies, not main-table
rows; the main table is the original register, claim form only.

**(a) How many repair rounds?** D' with 0 / 1 / 2 / 3 verify-and-repair rounds
(400 records, both forms; claim-only in brackets). `verify_rounds` governs both
stages, so round 0 has no S1 check either.

| rounds | verdict | den-F1 | faithfulness | lucky (right verdict, wrong denominator) | over-abstention | S2 repair fired | tokens / record |
|---|---|---|---|---|---|---|---|
| 0 | 0.855 [0.865] | 0.717 | 0.75 | 32 | 0.265 | 0 / 400 | 4.9k |
| 1 | 0.843 [0.850] | 0.764 | 0.86 | 18 | 0.306 | 91 / 400 | 6.8k |
| 2 | 0.865 [0.870] | 0.763 | 0.78 | 37 | 0.257 | 93 / 400 (77 again) | 8.7k |
| 3 | 0.850 [0.855] | 0.768 | 0.83 | 25 | 0.290 | 91 / 400 (75, 71) | 10.7k |

Runs: `v12f_smoke200_cellC2_catalogueS2_instruct32b_coder32b_final` (0),
`v12f_smoke200_dprime_verify1_final` (1), `..._verify2_final` (2),
`v12f_smoke200_dprime_verify3_final` (3); faithfulness and abstention from
`scripts/s2_attribution.py` / `scripts/abstention_metrics.py` against
`v12f_smoke200_gold_sets`. Per-record transitions: each extra round changes
6-19 of 400 verdicts; the net verdict change never exceeds 0.012 (5 records),
inside the slice's noise. What the rounds buy is retrieval: den-F1 0.717 ->
0.764 at one round and flat after, faithfulness 0.75 -> 0.78-0.86. The
records that flip from right to wrong flip almost entirely INTO abstention (r0
-> r1: 12 right->wrong, 13 became insufficient; r2 -> r3: 6 and 6): a repair
that cannot produce a clean statement ends in `insufficient`, which trades a
lucky verdict for an honest one. The S2 check fires on 23% of records and 71
of the 91 are still flagged after three rounds -- the persistent cases are
genuine n = k situations and absent events, which no rewrite can fix. Two
rounds remain the operating point (best verdict, +3.9k tokens per record over
round 0); the third round adds cost without retrieval gain. Rows 0/2 and 1/3
were produced on different days, so part of the 1/3 vs 0/2 contrast is
run-to-run variance of a temperature-0 32B model, not a parity effect.

**(b) Paraphrase, full pipeline.** D' on the research / media / clinical
registers (claim form, 200 instances each):

| register | D' (0 rounds) | D' + 2 |
|---|---|---|
| original | 0.865 | 0.870 |
| research | 0.790 | 0.815 |
| media | 0.755 | 0.770 |
| clinical | 0.825 | 0.840 |

Runs `v12f_smoke200_dprime_registers_final` (0.790 over 600) and
`..._verify2_final` (0.808). The drop (-0.03 to -0.11 at two rounds) matches the
planner-alone drop on the same registers (-0.02 to -0.12, 10.3h): the
paraphrase cost is paid at planning and passes through the contract unchanged,
S2 adds no register sensitivity of its own. B / B+2 on the same registers
(`night2_gpu1.sh`, done 02:24): B 0.587 / 0.600 / 0.557 (research / media /
clinical; 0.640 original), B+2 0.679 / 0.690 / 0.599 (0.715 original). The
end-to-end control loses 0.04-0.12 under paraphrase, the same band as D'; the
D' - B+2 gap stays 0.08-0.24 on every register.

### 10.3o Claude Opus 5.5 on the dev slice (200 claims, original register; 2026-10-14 01:35)

Same prompts and flags as the local main-table rows (`results/chains/
frontier_dev.sh`); API via the native structured-output route (Opus 5.5
rejects forced tool calls; `llm_client.py` falls back per model, same schema,
same JSON). Prompt caching on (billing only). Cost from the real token counts
at the 2026-10-14 list price ($4 in / $20 out / cache read $0.20):

| row | Opus 5.5 | 32B local (claim-only) | den-F1 (Opus) | cost |
|---|---|---|---|---|
| planner alone (S1, gold S2/S3) | 0.990 (claim EM 0.975) | 0.965 | -- | $0 (cached from D') |
| D' | **0.990** | 0.865 | 1.000 | $2.51 |
| D' + 2 | 0.990 (claim EM 0.955) | 0.870 | 1.000 | +$0.31 |
| B (end-to-end + conventions) | **1.000** | ~0.64 | 1.000 | $2.14 |
| B + 2 | 0.990 | 0.715 | 0.986 | +$0.16 |
| counts-given (S3) | 1.000 | 0.705 | -- | $0.81 |

Total $5.92 for six rows; about 20 min per 200-record row, 4-6 s per call.
Per tier (D'): vaccine 124/124, report 70/71, multi 4/5. The SQL is genuinely
right -- e.g. the precedes arm excludes `a.level = b.level` from the
denominator and flags it `excluded` -- so the conventions, stated once, are
sufficient for a frontier model with no contract at all. Verified by reading
statements against gold n/k; no error rows, no API failures.

What it means (the user's question of 2026-10-14): the dev slice is SOLVED by
Opus 5.5 end-to-end. The contract's measurable value is for open 32B models
(0.87 vs 0.66-0.72 end-to-end, at zero API cost) and for faithfulness; the
benchmark's difficulty at the frontier must come from the test set, the
paraphrase registers, or the no-conventions condition. Cell A (no
conventions) at Opus (`frontier_dev_A.sh`, done 01:55, +$2.31, total $8.24):
**A 0.945** (den-F1 0.903, den-EM 0.787; vaccine tier 0.911, report 1.000),
A+2 0.935 (den-F1 0.882). So a frontier model infers most of the stipulations
from the schema and the claim wording alone and still misses 11 of 124 cohort
verdicts and a fifth of the denominators; stating the conventions closes that
to 1.000. The conventions ARE information, worth +0.055 verdict / +0.21
denominator exactness at the frontier (vs +0.14 / +0.3 at 32B). Repair hurts
slightly at Opus in cell A (-0.01): without a contract the plan-free checks
flag correct n = k statements.

**gpt-5.6-sol (OpenAI; 2026-10-14 19:01).** Chosen as the peer of Opus 5.5:
"GPT-5.6 flagship model for complex professional work", the same $4 / $20
price point (cached input $0.40). Same eight rows, same order
(`results/chains/frontier_dev_gpt.sh`); reasoning effort left at the provider
default (it reasons adaptively: 12k hidden tokens on D', 42k on each
end-to-end row, 105k on counts-given). Total $8.75.

| row | gpt-5.6-sol | Opus 5.5 | 32B local | den-F1 (GPT) | cost |
|---|---|---|---|---|---|
| planner alone | 0.995 (claim EM 0.980) | 0.990 (0.975) | 0.965 | -- | $0 (cached) |
| D' | 0.995 | 0.990 | 0.865 | 1.000 | $2.00 |
| D' + 2 | 0.990 | 0.990 | 0.870 | 0.992 | +$0.30 |
| A: schema only | 0.925 | 0.945 | 0.505 | 0.913 (EM 0.829) | $1.76 |
| A + 2 | 0.910 | 0.935 | 0.545 | 0.891 | +$0.08 |
| B: + conventions | 0.995 | 1.000 | 0.640 | 1.000 | $1.88 |
| B + 2 | 0.990 | 0.990 | 0.715 | 0.985 | +$0.23 |
| counts-given | 1.000 | 1.000 | 0.705 | -- | $2.51 |

Per tier (D'): vaccine 124/124, report 71/71, multi 4/5; cell A: vaccine
0.887, report 0.986. The two frontier models agree to within one record on
every row: the conventions, stated once, are sufficient for both; without
them both lose 0.05-0.07 verdict and 17-21% of denominators. Repair at the
frontier is neutral to slightly negative in every cell (-0.005 to -0.015),
for the same reason as at Opus (plan-free checks flag correct n = k
statements). The slice is saturated for frontier models at this price point;
the open-weight sweep (10.3p) and the test set are where the spread is.

### 10.3p Open-weight sweep on the dev slice: qwen3.8-27B and gemma4-31B (2026-10-14 21:38)

Same prompts and flags as the 32B rows, ONE model in both stages, thinking
OFF (`--think off`; both think by default -- gemma4 despite its library page),
claim form, original register, 200 instances. Served by Ollama v0.40.4 from a
user install with NVIDIA's CUDA forward-compat library (driver 535 on the
box; `results/chains/ollama_servers.sh`); models fully resident on one A5000
at 8k context. Chains: `results/chains/openweight_dev.sh`. 95% bootstrap
intervals over instances in brackets.

| row | qwen3.8-27B | gemma4-31B | Qwen2.5-32B pair | Opus 5.5 / GPT-5.6 |
|---|---|---|---|---|
| planner alone | 0.945 [0.910, 0.975] | 0.985 [0.965, 1.000] | 0.965 | 0.990 / 0.995 |
| D' | 0.845 (den-F1 0.774) | 0.890 (0.898) | 0.865 (0.72) | 0.990 / 0.995 |
| D' + 2 | **0.905** [0.865, 0.945] (0.898) | **0.970** [0.945, 0.990] (0.965) | 0.870 (0.76) | 0.990 / 0.990 |
| B | 0.840 (0.731) | 0.875 (0.779) | 0.640 | 1.000 / 0.995 |
| B + 2 | 0.895 [0.850, 0.935] (0.818) | 0.925 [0.890, 0.960] (0.886) | 0.715 | 0.990 / 0.990 |
| counts-given | 0.700 | 0.810 | 0.705 | 1.000 / 1.000 |

Faithfulness P(den exact | verdict right), cohort tier (129): qwen3.8 D'
0.867 -> D'+2 **0.964**, B 0.701 -> B+2 0.806; gemma4 D' 0.972 -> D'+2
0.960, B 0.837 -> B+2 0.886. False-decisiveness at +2: D' 0.086 / 0.028 vs
B 0.111 / 0.083; over-abstention D' 0.065 / 0.043 vs B 0.108 / 0.108.
Per tier (D'+2): vaccine 0.855 / 0.968, report 1.000 / 0.986, multi 0.8 / 0.8.
Live latency (sequential, one A5000): D' 8.8 s / 13.2 s per record (4.7k /
4.8k prompt tokens), B 4.6 / 4.7 s; D'+2 adds ~4-5 s; counts ~1 s.

Reading. (1) The newest open generation closes most of the verdict gap to
the frontier with the contract: gemma4-31B D'+2 at 0.970 is within 0.02 of
Opus, at zero API cost and 13 s per record on a workstation GPU. (2) The
contract's VERDICT advantage over verified end-to-end shrinks as models
improve: +0.155 at the Qwen2.5-32B pair, +0.045 at gemma4 (borderline on 200),
+0.010 at qwen3.8 (not resolved). (3) The FAITHFULNESS advantage does not
shrink: denominator F1 0.90 vs 0.82 (qwen3.8) and 0.97 vs 0.89 (gemma4) at
two rounds; faithfulness 0.96 vs 0.81 and 0.96 vs 0.89; false-decisiveness
halves or better. This is the paper's claim from here: the contract is what
makes an open model's verdict auditable, and it is worth 0.15 verdict at the
32B generation and ~0.05 at the newest, while the denominator gap persists.
(4) qwen3.8 D' at 0 rounds (0.845) is below its planner (0.945): a 27B model
in the SQL slot loses 0.10 that two repair rounds recover (0.905); the Coder
in the 32B pair is what makes D' r0 land. gpt-oss:20b (reasoning model,
`--think low`) queued on GPU0 (first attempt aborted: the pull had not
completed).

**gpt-oss-20b (OpenAI open-weight reasoning model, `--think low`; 22:28).**
planner 0.740 (claim EM 0.74), D' 0.675, D'+2 0.715 [0.645, 0.780], B 0.800,
B+2 **0.850** [0.800, 0.895], counts 0.740. The one model where the verified
end-to-end row beats the contract pipeline -- and the reason is visible in
the abstention block: at D'+2, 37% of cohort records have NO answer (plan
composition failed, so S2 never ran), against 0% for B+2. When it does
answer, the contract is the more faithful system as everywhere else:
faithfulness 0.92 vs 0.80, false-decisiveness 0.043 vs 0.083,
over-abstention 0.069 vs 0.194. Per tier (D'+2 / B+2): vaccine 0.556 / 0.798,
report 0.986 / 0.930. Latency 6.0 s (D') / 3.5 s (B) per record, 12.9 GB.
Reading: the contract needs a planner that can compose the plan; a 20B
reasoning model at low effort misreads the plan shape on a quarter of the
claims (the 7B failure mode), and the pipeline then abstains rather than
guess, which is the designed behaviour but costs verdict accuracy against a
baseline that always answers. This goes in the paper as the boundary
condition of the method, not hidden.

**2026-10-14 22:45 (user): gpt-oss-20b is DROPPED from the paper** (results
kept in `results/dev_gptoss_20b_*`; not in the sweep table or the draft).

### 10.3q TEST SET: local models complete; frontier in progress (2026-10-15 23:55)

Test set = `test_cohort_v1.2_s0` (1,500 cohort/multi instances, 17 groups, claim
form, original register, fact-disjoint from dev; decisions.md 2026-10-14).
Report-tier case study = `test_report_v1.2_s0` (180). Prompts frozen. 95%
bootstrap intervals over instances are about +/-0.02 on 1,500. Gold sets for
attribution: `results/test_gold_sets` (rules+compiler, 1.000).

| row | Qwen2.5-32B pair | gemma4-31B | qwen3.8-27B | Opus 5.5 | GPT-5.6 |
|---|---|---|---|---|---|
| planner alone, 1 round | 0.953 | 0.995 | 0.917 | 0.993 | 0.993 |
| SQL stage alone (gold plan), 2 rounds | 0.836 | -- | -- | -- | -- |
| D' (0 rounds) | 0.761 | 0.844 | 0.735 | **0.999** | **0.999** |
| D' + 1 | 0.775 | 0.971 | pending | 0.993 | 0.991 |
| D' + 2 | **0.810** | **0.981** | **0.872** | 0.993 | 0.983 |
| D' + 3 | 0.814 | pending | pending | 0.992 | 0.983 |
| A: schema only | 0.529 | -- | -- | 0.878 | 0.876 |
| B: + conventions | 0.575 | 0.859 | 0.748 | running | running |
| counts-given (S3) | 0.611 | 0.777 | 0.619 | pending | pending |
| report case study: D' + 2 / B (+2) / A | 1.000 / 0.750 / 0.433 | 1.000 / 1.000 / -- | 1.000 / -- / -- | pending | pending |

(A + verifier and B + verifier were run for the pair and gemma4 before the
user removed them: pair 0.539 / 0.638, gemma4 B+2 0.900; not in the paper.)

Faithfulness P(den exact | verdict right), 1,500 cohort: pair D' 0.768 ->
D'+2 0.859, B 0.405; gemma4 D' 0.903 -> 0.945, B 0.859; qwen3.8 D' 0.865 ->
**0.972**, B 0.693; Opus D' 1.000 (one wrong denominator in 1,500), A 0.856;
GPT D' 1.000, A 0.908. Abstention at D'+2: false-decisiveness pair 0.033 /
gemma4 0.010 / qwen3.8 0.047 vs B 0.234 / 0.036 / 0.141; over-abstention
0.223 / 0.023 / 0.068 vs B 0.388 / 0.182 / 0.224. No-answer rate: pair 0.031,
qwen3.8 0.025, others 0.

Per family (D'+2 vs B): the pair's loss is first/last (0.435 vs 0.332), P-V2
(0.417) and H-V5 (0.410) -- argmax and tie rules in SQL; gemma4 holds 0.95-1.0
on every family (`scripts/group_table.py`).

Live latency on one A5000 (sequential): D' 12.3 s (pair, with model swaps) /
14.1 s (gemma4) / 10.1 s (qwen3.8) per record; B 6 s. Frontier cost so far
(real usage, list price): Opus $50.0 after D' (21.4), planner, 1/2/3 rounds
(2.0-2.3 each), A (21.8); GPT $39.9 after the same rows. B, counts and the two
report rows remain; GPT's counts row spends hidden reasoning tokens (dev: 105k
per 200) and may push it past the $90 cap, in which case the two report rows
run separately.

Reading, dev -> test: every dev conclusion transfers. (1) Frontier models with
the conventions solve the test set (0.999) and lose 0.12 without them. (2)
gemma4-31B with the contract and two rounds reaches 0.981 on 1,500 instances
at zero API cost, 14 s per record. (3) The contract beats the end-to-end
control on every open model: +0.235 (pair), +0.122 (gemma4), +0.124
(qwen3.8) in verdict, and 0.86-0.97 vs 0.41-0.86 in faithfulness. (4) Repair
at the frontier is slightly negative (0.999 -> 0.983-0.993): flagged correct
n = k statements become abstentions. (5) Report tier: every system reads a
single report at 1.000 except the 2024 Coder end to end (0.750 with
conventions, 0.433 without).

**Update 2026-10-16 08:07 -- frontier chains complete; local repair rounds complete.**
Opus 5.5 (total **$79.84**): B 1.000, counts 0.999, report D'+2 0.983 (3 of 180
abstained), report B 1.000. GPT-5.6 (total **$88.91**, under the $90 cap): B
0.984, counts 0.999, report D'+2 1.000, report B 1.000. Faithfulness of B at
the frontier 1.000 / 1.000; false-decisiveness 0.000 / 0.000. Repair rounds,
D' 0/1/2/3: gemma4 0.844 / 0.971 / 0.981 / 0.985; qwen3.8 0.735 / 0.869 /
0.872 / 0.875; pair 0.761 / 0.775 / 0.810 / 0.814; Opus 0.999 / 0.993 /
0.993 / 0.992; GPT 0.999 / 0.991 / 0.983 / 0.983. So for the open models the
first round does most of the work (gemma4 +0.13, qwen3.8 +0.13) and rounds 2-3
add 0.01; at the frontier every round costs 0.005-0.015 (correct statements
flagged into abstention). EHRAgent A at 1,248/1,500 (08:07); VERITAS D at
36/204 (~3.3 min per claim, ~9 h to go).

**Update 2026-10-17 09:30 -- every test cell is in except EHRAgent B.**
VERITAS D on the 204-claim test subsample (12 per group; 09:16): verdict
accuracy **0.402** with incomplete runs scored as misses (95 of 204 runs
completed all three phases within the 10-min phase caps; ~12 h on one GPU);
binary supported-vs-not 0.696; exact test matched 0.216; it answers
insufficient on 166 of 204. Dev 0.349, old test slice 0.317: consistent.
S2 alone (gold plan, model SQL, 2 rounds): gemma4 **0.989** (den-F1 0.98),
qwen3.8 **0.944** (den-F1 0.946); so the full pipeline's gap to its own S2
ceiling is 0.008 (gemma4) and 0.072 (qwen3.8) -- the plan is the remaining
loss, and for qwen3.8 the planner-alone row (0.917) says the same. Report-tier
B without repair: pair 0.750, gemma4 1.000, qwen3.8 1.000. Frontier S2-alone
not run: bounded below by the D' denominator F1 (1.000 / 1.000 with the
model's own plan), written as ">= 0.999" in the paper. EHRAgent B + conventions
at 1,184/1,500 (09:28; ~1.5 h to go).

**Update 2026-10-17 12:34 -- EHRAgent variant B + conventions on the test set
(repo record only; user 2026-10-16).** Counts -> our exact test, conventions in
its prompt: **0.649** on the 1,500 (A, own test: 0.605); cohort tier 0.63,
multi 0.94; 65 of 1,500 (4.3%) unparseable. On dev the two variants agreed
(0.624 vs 0.628); on test B+conv is +0.044 over A, i.e. giving EHRAgent our
exact test and the stipulations buys it four points, still 0.16 below the 2024
pair under the contract (0.810) and 0.07 above the end-to-end control with
the same Coder (0.575). Both GPUs idle from 12:34; every planned run is done.

### 10.3r Agentic baselines with the open models; the 204-claim subsample (2026-10-20)

**EHRAgent's paper (EMNLP 2024) used only GPT-4 (gpt-4-0613) and
GPT-3.5-turbo (0613); open models were a stated future direction.** So the
Coder-32B is our adaptation, and a reviewer can ask for the best open model
inside the agent. EHRAgent with gemma4-31B (thinking off via
`reasoning_effort=none` on the OpenAI-compatible endpoint; 8k tag) ran at
~5 min per claim (3 of 5 first outputs unparseable; the agent's twelve-round
repair loop absorbs the time) -- 5 days for 1,500 -- and was STOPPED at 5/1,500
(user, 17:00). EHRAgent with qwen3.8-27B started on the full set at 17:04 on
GPU0; the pace decides full set vs the 204-claim subsample.

**Why 204.** VERITAS: 12 per cohort group x 17 groups, verdict-balanced
round-robin (4/4/4) -- the smallest balanced per-group count that sums to
about 200, the budget VERITAS can cover in ~30 h at its measured 9 min per
claim (mean 534 s, median 560 s on the 204; many runs hit the 10-min phase
cap). A full 1,500 would need 192 GPU-h (the remaining 1,296 claims) -- not
feasible before the 25th. The queued VERITAS runs with gemma4 / qwen3.8
(~30 h each) are CANCELLED (canceller armed on the GPU1 chain).

**Paired check on the identical 204 claims** (bootstrap over claims, 2,000):
VERITAS 0.402 [0.33, 0.47]; EHRAgent A 0.559 [0.49, 0.62] (full 0.605);
B 0.593 [0.53, 0.66] (0.575); pair D'+2 0.804 [0.75, 0.86] (0.810); qwen3.8
D'+2 0.887 (0.872); gemma4 D'+2 0.980 (0.981); Opus D' 1.000 (0.999). Every
full-set number lies inside its own 204 interval. In the paper: main table
keeps VERITAS with a dagger; a main-results paragraph explains the subsample;
Appendix "The agentic subsample" carries the paired table (user, 2026-10-20).

**2026-10-20 18:30 -- verifier budget made uniform in the modular table.** `--verify-rounds N`
gives BOTH stages up to N rounds (S1: conventions-consistency re-ask; S2: executor /
n=k / plan-primitive checks). In D'+2 the S1 check fired on 960 of 1,500 records
(gemma4) and S2 on 382. Planner-alone rows re-scored at 2 rounds (all S1 calls were
disk-cache hits from D'+2; zero API cost): pair 0.953, qwen3.8 0.917, gemma4 0.992
(0.995 at 1 round), Opus 0.993, GPT 0.993. The modular table now states the budget on
every verified row. The model-judged verdict from counts is named as an ablation that
REPLACES S3 (user): S3 is the pipeline's exact-test stage.

**Update 2026-10-20 21:20.** Cell A (schema only, no conventions) on the test set:
gemma4 **0.635** (B with conventions 0.859), qwen3.8 **0.587** (B 0.748); report
tier A: gemma4 0.744, qwen3.8 0.989; report-tier planner alone 1.000 for both.
S1+S2+LLM-verdict (the exact test replaced by the model judging from its own
counts, 2 rounds): gemma4 **0.770** vs 0.981 with the exact test; qwen3.8 and the
pair running. VERITAS with the open models cancelled (user). EHRAgent interim:
qwen3.8 0.848 vs ours 0.867 on the same 698 claims; GPT-5.6 0.794 vs ours 0.999 on
933 ($35.41 so far).
**21:35.** S1+S2+LLM-verdict for qwen3.8: **0.568** (0.872 with the exact test).
EHRAgent GPT-5.6 at 989/1,500, qwen3.8 at 735/1,500.
**2026-10-21 02:36.** All remaining runs done. EHRAgent GPT-5.6 on the full test
set **0.792** (macro P/R/F1 0.808/0.792/0.794; $56.30, 4,501 calls); EHRAgent
qwen3.8 **0.839** (0.863/0.839/0.843); on the 204-claim subsample 0.784 and
0.868. Abstention (insufficient_analysis.py): EHRAgent overclaim 0.578 (Coder) /
0.079 (qwen3.8) / 0.145 (GPT-5.6), underclaim 0.033 / 0.191 / 0.197. S3-LLM
ablation: pair 0.512, qwen3.8 0.568, gemma4 0.770. Draft cells filled (main
table, abstention table, subsample table, RQ3 and error-analysis prose).
