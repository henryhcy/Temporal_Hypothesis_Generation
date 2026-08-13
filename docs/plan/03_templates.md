# 03. Templates

> **STATUS (2026-08-12): the YAML structure is current; the roster counts,
> the PROP answer type, the verdict mechanics and the negation rule were all
> superseded.** Corrected in place with dates.

## Where templates live

The canonical templates are stored as YAML under `data/templates/`:

```
data/templates/
├── pairwise.yaml      ← 10 groups: precedes + co_occurs
├── sequence.yaml      ←  5 groups: sequence
└── first_last.yaml    ←  8 groups: first / last
```

YAML is the **single source of truth**. The `.docx` under `docs/reference/`
is a generated artifact for advisor meetings, produced by
`scripts/render_templates_docx.py`.

### Why three files

Each family has its own gold-label computation logic and its own slot
schema:

- **pairwise**: two events `{A}`, `{B}`. Proportion over both-present cohort.
- **sequence**: three events `{A}`, `{B}`, `{C}`. Strict ordering required.
- **first / last**: candidate set `{A}`, `{B}`, `{C}`. Argmax with tie handling.

Splitting per family keeps each YAML file's schema clean and the
generator code per-family-focused.

## Common structure

Each file has this top-level shape:

```yaml
family: <name>
description: "..."
notes: "..."
common:
  registers: [original, research, media, clinical]
groups:
  - id: <group-id>
    primitive: <relation>
    level: <report | vaccine | multi>
    answer_type: <BOOL | CHOICE>
    slots: [A, B, ..., v]
    variants:
      original:
        question: "..."
        claim: "..."
        # OPTIONAL, and only where negation is the orientation operator:
        question_negated: "..."
        claim_negated: "..."
      research: { ... }
      media:    { ... }
      clinical: { ... }
```

*(PROP and the `{p}` slot were retired 2026-07-14. The `*_negated` variants were
added 2026-08-11 — negation now lives IN the YAML, superseding the "applied at
generation time" rule below.)*

### Per-family schemas

**`pairwise.yaml`** — primitive is `precedes` or `co_occurs`. Slots are
`[A, B]` plus level-specific cohort slots (`r` for report, `v` for vaccine,
`v1`/`v2` for multi). ~~PROP groups also carry the value slot `p`.~~ (retired
2026-07-14)

**`sequence.yaml`** — slots always include `A, B, C`. Strict ordering
locked at the file level (see the `notes` field in the YAML). Cohort slots
per level as above.

**`first_last.yaml`** — slots include `A, B, C` plus cohort slots.
~~Tie-handling rule (CHOICE on ties → `insufficient`) locked at the file
level.~~ **SUPERSEDED 2026-08-11**: tie reports leave the DENOMINATOR entirely
(see `02_dataset_design.md` rule 4). Report-level tie handling is still open.

## Structure summary

| Family    | Report | Vaccine | Multi | Total | File              |
|-----------|:------:|:-------:|:-----:|:-----:|-------------------|
| pairwise  | 3      | 4       | 3     | 10    | `pairwise.yaml`   |
| sequence  | 1      | 2       | 2     |  5    | `sequence.yaml`   |
| first/last| 3      | 3       | 2     |  8    | `first_last.yaml` |
| **Total** | **7**  | **9**   | **7** | **23** |                  |

(pairwise covers both `precedes` and `co_occurs`, which is why its count is
higher than the others.)

**Read this table as a snapshot, not a spec** — it is regenerable with
`grep -c '^- id: ' data/templates/*.yaml`, and it has been wrong before. The
seed roster was 30; groups were retired in three waves (PROP 07-14, the
non-directional multi groups 07-28, S-M2 08-04, S-V4/C-M2/F-M3 08-11).
**6 of the 23 are non-directional and still pending removal** (P-M1, C-M1, S-M1,
S-M3, F-M1, F-M2) — they enumerate cores but cannot ship a verdict, so the
roster after migration A is 23 − 6 + 3 = 20. See `09_next_steps.md`.

## Slots

| Slot   | Type     | Meaning                                                |
|--------|----------|--------------------------------------------------------|
| `{A}`, `{B}`, `{C}` | event   | Event term type from MedTempo + synonym table |
| `{v}`            | vaccine | Single vaccine (Pfizer, Moderna, or Janssen)     |
| `{v1}`, `{v2}`   | vaccine | Two vaccines for multi-vaccine groups            |
| `{r}`            | context | Report identifier or contextual reference        |
| ~~`{p}`~~        | value   | ~~Asserted proportion~~ retired with PROP, 07-14 |

The synonym table for `{A}`/`{B}`/`{C}` is built manually from MedTempo
term types plus medically-equivalent alternatives. See `open_questions.md`
for the open issues on synonym scope.

## Registers

Each group is projected into three registers plus the canonical Original
seed. All four are generated mechanically; no LLM rewrites.

| Register   | Description                                                              |
|------------|--------------------------------------------------------------------------|
| Original   | Canonical seed phrasing; baseline for comparison.                        |
| Research   | Precise scope, explicit cohort, formal vocabulary. Papers, reports.      |
| Media      | Public-facing, brand-named, comparison framing. Journalism, regulatory.  |
| Clinical   | Practitioner-conversational. References to patients, recipients.         |

The chart-style register has been explicitly dropped.

Negation modifier. **SUPERSEDED 2026-08-11**: ~~not stored in the YAML; applied
at generation time~~ — negation IS stored in the YAML, as `question_negated` /
`claim_negated` variants, and it exists only where a template provides them
(today C-V1 and C-V3 alone). It is the **orientation operator for symmetric
claims**: a co-occurrence claim has no A/B swap to flip, so negating the
assertion is the only way to pose its refuted mirror. Gold flips with it, and
`negated` is reported per instance. Samplers must PREFER PLAIN WORDING and
negate only to fill a remaining deficit.

## Verdict mechanics

**SUPERSEDED 2026-07-28 — the whole section below described the retired
point-estimate rule.** ~~BOOL supported if the assertion matches the data;
CHOICE if it names the correct option; PROP within 5pp; refuted by flipping the
assertion.~~

Current: the label is the **three-decision test**, applied to the claim THIS
instance asserts.

- **supported** — significant in the claim's direction (one-sided exact test,
  alpha 0.05).
- **refuted** — significant in the OPPOSITE direction. Positive
  counter-evidence, never "we failed to prove it".
- **insufficient** — neither direction significant. Sub-typed as
  `underpowered` (enough data, no effect), `sparse` (below the family floor),
  or `not_locatable` (the events never co-occur, so n = 0).

Refuted instances are built by re-posing an EXISTING decisive core with its
claim reversed — swapping A and B, naming a non-modal cell, or negating a
symmetric claim. The events must still genuinely co-occur; only the asserted
relation is false. Every decisive core is posed both ways, which is what makes
`derived_from_core_id` a split-critical field.

## Generation pipeline

The generator reads the three YAML files and, per group:

1. Enumerates viable factual cores from MedTempo (cohorts with sufficient
   n, candidate event sets that appear in enough reports).
2. Computes the gold artifact per core (proportion, verdict, n).
3. Slot-fills the four register variants with the event synonyms and
   cohort phrasing.
4. Optionally applies the negation modifier to a subset of BOOL instances.
5. Balances supported / refuted / insufficient to **equal thirds per group**
   (superseding the provisional 45/45/10 and the pooled balance), capped by
   availability at ~3·S where S is the group's decisive-core count.

Benchmark size is an OUTPUT of that budget, not a target to hit: the current run
is ~20,700 instances. *(The seed target of "10,000 to 15,000" predates equal
thirds, the register/format expansion and both-ways posing, so it no longer
constrains anything — do not size the roster to it.)*

## Regenerating the .docx

```bash
python scripts/render_templates_docx.py
```

This reads the three YAML files and writes
`docs/reference/Temporal_Hypothesis_Templates.docx`. Commit YAML changes;
the .docx can be regenerated on demand.
