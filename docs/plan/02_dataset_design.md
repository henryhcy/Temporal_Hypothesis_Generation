# 02. Dataset Design

> **STATUS (2026-08-12): the leveled-order schema below is current; several
> LOCKED COMPUTATION RULES and the entire release section were superseded.**
> Each superseded item is struck in place with its date and the rule that
> replaced it, so nothing is silently rewritten. The live sources of truth are
> `decisions.md`, `CLAUDE.md` ("Conditioning rules differ per family"), and
> `core/min_n.py` for the floors. Reading this doc without the strikeouts would
> produce the wrong denominators, the wrong verdict rule and the wrong release.

## Source data

MedTempo, a corpus of 3,166 expert-annotated VAERS adverse event reports.
Each report contains:

- A narrative (free text)
- A vaccine label (Pfizer, Moderna, or Janssen — the DB and all generated text
  use `Janssen`; earlier drafts of these docs wrote "Johnson", which appears
  nowhere in code or output)
- A set of clinical events (one per term type per report, using first mention)
- Pairwise temporal relations among events: before, after, or co-exist

## Storage representation: leveled order

Per report, store a **leveled order**: a list of co-exist clusters in temporal
sequence.

```python
levels = [["headache"], ["fever", "rash"], ["fatigue"]]
# headache occurs first; fever and rash co-occur next; fatigue occurs last
```

This is the partial order written compactly. It is interconvertible with
the pairwise relations (build levels from relations by topological sort;
recover pairwise relations from levels by comparing indices).

### Why leveled order over flat ordered list

A flat ordered list cannot represent co-exist. The leveled list can.

### Why leveled order over relations table

Simpler query code, no graph traversal at query time. Pairwise relations
are still derivable when needed.

## Per-report functions

These three functions cover all four hypothesis families:

```python
def level_of(levels, term):
    """Return the level index of term in the report, or None if absent."""

def precedes(levels, A, B):
    """Return 'before' | 'after' | 'co_exist' | 'missing'."""

def first_among(levels, terms):
    """Return list of terms tied for earliest; or 'missing' if any absent."""
```

`sequence_holds(levels, [A, B, C])` is composed from these: return True iff
all terms present and level_of(A) < level_of(B) < level_of(C) strictly.

## Cohort-level aggregation: fractions

Compute a proportion over a cohort, then label it with the three-decision test
(rule 6). ~~For PROP and the "majority"-style BOOL/CHOICE groups~~ — PROP was
retired 2026-07-14.

### Locked computation rules

Rules 1 and 2 are unchanged and are the subtlety most worth protecting. Rules
3–8 have all moved.

1. **Denominator for `precedes(A, B)` at cohort level**: only reports where
   both A and B appear AND the pair is ordered (not co-exist). Co-exist
   pairs are excluded from the denominator. *Rationale: measures "when there
   is an order, how often is it A → B."* — **CURRENT.**

2. **Denominator for `co_occurs(A, B)` at cohort level**: only reports where
   both A and B appear. Co-exist reports are the event of interest, so they
   are kept. — **CURRENT.**

3. ~~**Denominator for `sequence(A, B, C)`**: only reports containing all three
   events.~~ **SUPERSEDED 2026-07-01.** The denominator is the ORDERABLE one:
   reports where all three events appear *at distinct levels*. A report where
   two of the three co-occur cannot exhibit a strict ordering, so it leaves the
   denominator entirely rather than counting as a failure.

4. ~~**Denominator for `first_among`**: only reports containing all named
   candidates. Tie-reports are excluded from per-candidate counts; tie rate is
   reported separately.~~ **SUPERSEDED 2026-08-11.** Tie reports leave the
   DENOMINATOR, not just the numerator. Keeping them in n while barring them
   from every numerator meant the candidate shares could not sum to 1 and every
   candidate was biased toward `refuted`. `tie_rate` is still reported, computed
   over reports where all candidates were present.

5. ~~**Minimum n threshold**: below n=10 return `insufficient`. Locked
   threshold: 10.~~ **AMENDED 2026-08-11.** The floor is **10 for every family
   except sequence, which is 5** — sequence conditions far more deeply, and at
   10 its cohort-level supply is exactly zero. The floors live in
   `core/min_n.py` and are the ONLY gate: helpers measure at every size, the
   gate decides. Never re-implement a floor inside a helper.

6. ~~**Majority threshold for BOOL "typically" groups**: fraction > 0.5
   strictly; ties map to `insufficient`.~~ **SUPERSEDED 2026-07-28.** A point
   estimate above 0.5 is not a verdict. The label is the **three-decision
   test**: significant in the claim's direction → `supported`; significant in
   the OPPOSITE direction → `refuted`; neither → `insufficient`. `refuted`
   therefore requires positive counter-evidence and never means "failed to
   prove". Exact tests only, one-sided, alpha 0.05 per side.

7. ~~**PROP tolerance**: |p_claimed − p_actual| ≤ 5 percentage points.~~
   **RETIRED 2026-07-14** along with the PROP groups. A ±5pp match against the
   true value is point-estimate fact-checking with no principled null.

8. ~~**Multi-vaccine "differ" verdict**: |p1 − p2| > 10 percentage points.~~
   **RETIRED 2026-07-28.** "Differ" claims cannot map onto the three decisions:
   not-significant can never be a clean `refuted` without accepting H0. The
   multi tier is directional-only. Equivalence margins (TOST) as a rescue were
   explicitly REJECTED 2026-08-11 — they reintroduce the same unmotivated
   number that retired PROP.

9. **Argmax claims use modal-vs-runner-up** (added 2026-07-14, extended to the
   CHOICE groups 2026-08-11). "Most common X" is verified by a one-sided exact
   binomial of the NAMED cell against its strongest competitor, not by a
   goodness-of-fit against uniform — GOF shows only that the distribution is not
   flat, never that the named cell is the mode.

10. **A term's position in a report is its FIRST mention** (2026-08-11). Found
    during Part C validation; it had been silently inconsistent.

### Cycle check (one-time, at corpus construction)

For each report, verify the directional relations form a DAG. Flag any
cycles, fix or drop them, and record the rate. Cycles would corrupt the
leveled-order construction.

### Disconnected components

If a report has events that are mutually unrelated (no relation connects
them across two clusters), the leveled order is undefined. For v1, treat
such reports as `insufficient` for any cross-component hypothesis. Measure
the rate during corpus construction.

## What we release vs what stays internal

> **THIS SECTION WAS REVERSED ON 2026-08-11.** The original text below is kept
> struck through because the reversal is the single biggest design change in the
> project, and reading the old version as current would define the wrong task.

~~Released: the hypothesis instances plus the raw VAERS narrative texts.
Internal: the MedTempo annotations, never exposed to evaluated systems. The
framework receives only the narrative text and must extract what it needs.~~

**Current.** The framework receives the **annotated leveled orders**, never
narrative text. MedTempo is published alongside an upcoming conference paper and
will be archived publicly, so withholding the annotations protected nothing. The
task is therefore *"translate a hypothesis into the right statistical procedure
over structured timelines"*, not *"extract timelines from text"* — extraction is
CRAFT's problem, and leaving it in made this benchmark a re-run of CRAFT with a
noisier signal. See `decisions.md` 2026-08-11 for the token measurements.

Two consequences that are easy to miss:

- **The release ships report ids, not narratives.**
- **`evidence_ids` — the report ids the statistic was computed over — are GOLD,
  never input.** They are the answer to the localization step (finding ~19
  relevant reports inside a ~1,000-report cohort), so handing them over would
  delete the hardest part of the task.

## Per-instance schema (release format)

The release is **two files**, not one, and the boundary is enforced mechanically
by `writers.split_release`, which raises if a gold field reaches the questions
file. A single flat file made the boundary a convention; this makes it a check.

- `<stem>_questions.jsonl` — only `instances.INPUT_FIELDS`: `hypothesis_id`,
  `group_id`, `level`, `answer_type`, `register`, `format`, `text`, `options`,
  `cohort`.
- `<stem>_answers.jsonl` — everything, keyed by `hypothesis_id`.

`instances.INPUT_FIELDS` is the authoritative list; the fields below are the
gold side and drift as the design does, so read `generation/instances.py` rather
than trusting this list to be complete:

| field | what it carries |
|---|---|
| `gold_verdict` / `test_verdict` | the three-decision label for the claim THIS instance asserts |
| `insufficient_subtype` | `underpowered` / `sparse` / `not_locatable` |
| `p_claim`, `p_opposite` | both one-sided tails; the claim tail alone cannot separate refuted from insufficient |
| `gold_n`, `gold_k`, `gold_n2`, `gold_k2` | the counts, so the label can be RECOMPUTED from the corpus |
| `min_n_floor`, `alpha`, `family`, `mode` | the gate and null that produced it |
| `evidence_ids` | the reports the statistic ran over — gold only |
| `negated` | whether the text asserts the claim's negation |
| `derived_from_core_id` | the core; mirror pairs share it and must not be split apart |
| `ci`, `ci_width`, `effect_size`, `confidence_tag` | all oriented to the instance's own claim; the tag is still uncalibrated (issue 4) |
| `factual_core` | evaluation diagnostics, not input |

## What still needs work

See `open_questions.md` for items that are still under discussion (e.g.,
sequence with internal co-occurrence, exact synonym table contents).

### v1.2 additions to the locked rules (2026-10-07, decisions.md BUILT v1.2)

11. **Stages are first-mention RANKS.** A report's stages are its occupied
    first-mention levels, ranked 0, 1, 2, ... from the earliest (dense; levels
    can have gaps). Two events are at *consecutive* stages when their ranks
    differ by exactly one.
12. **Denominator for `immediate(A, B)`**: reports with A and B at consecutive
    ranks; co-existing and gapped pairs leave the denominator. Null 0.5
    (slot-orientable, like precedes).
13. **Denominator for `position(A)`** ("A in the earlier half"): reports
    containing A with at least two stages whose A is not on the exact middle
    rank. The null is NOT 0.5: it is the mean over the denominator of each
    report's early-slot share (the structural early-rate; doc 10 §4.3),
    computed from the data. Orientation by negation.
14. **`adjacency(A, B)`** ("consecutive more often than chance"): the
    ordered-pair denominator, numerator = adjacent, null = the mean of 2/L
    over the denominator (L = the report's stage count). Orientation by negation.
15. **Text-stated bars** ("in at least two thirds", "in at least half"): the
    existing statistic against the bar read off the text; supported =
    significantly above, refuted = significantly below; each orientation is
    its own instance (no mirror pairs).

16. **Report ids are pseudonyms** (2026-10-08, review item 4). The VAERS id
    never appears in a text, a record or the eval DB: `core/pseudonym.py`
    maps it through a keyed permutation (`MT-0482913`); the key is private
    (`data/private/`). The annotations are untouched; only the lookup key is
    removed, so a model cannot retrieve a public report by id.
17. **Composition cap** (2026-10-08, review item 4): at most 200 instances per
    class per group (`--cap 600`), drawn seeded over cores with mirror pairs
    kept together; the report-tier enumerator caps per natural class so the
    non-orientable report groups (C-R1, T-R1, Y-R1) are balanced.
