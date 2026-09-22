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
| smoke-3 (`results/smoke200_llm-s1_llm-sql`, 448 s — S1 cached from smoke-1) | `llm-s1+llm-sql` (the full local pipeline) | blind-group | blind | same slice | 400 | **0.292** | 0.300 | 0.250 [0.217, 0.286] | 0.675 (mode 0.718) | 0.228 (EM 0.149; report_hit 0.380) | 0.082 (any 0.116) | 0.227 | 0.010 (n=198) | 0.018 (166 pairs); twins 0.667 | 16, all unexpected → scored wrong |
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
