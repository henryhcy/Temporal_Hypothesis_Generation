# 02. Dataset Design

## Source data

MedTempo, a corpus of 3,166 expert-annotated VAERS adverse event reports.
Each report contains:

- A narrative (free text)
- A vaccine label (Pfizer, Moderna, or Johnson)
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

For PROP and the "majority"-style BOOL/CHOICE groups, compute proportions
over a cohort.

### Locked computation rules

1. **Denominator for `precedes(A, B)` at cohort level**: only reports where
   both A and B appear AND the pair is ordered (not co-exist). Co-exist
   pairs are excluded from the denominator. *Rationale: measures "when there
   is an order, how often is it A → B."*

2. **Denominator for `co_occurs(A, B)` at cohort level**: only reports where
   both A and B appear. Co-exist reports are the event of interest, so they
   are kept.

3. **Denominator for `sequence(A, B, C)` at cohort level**: only reports
   containing all three events.

4. **Denominator for `first_among` at cohort level**: only reports containing
   all named candidates. Tie-reports (multiple events at the earliest level)
   are excluded from per-candidate counts; tie rate is reported separately.

5. **Minimum n threshold**: if the denominator is below n=10, return
   `insufficient` rather than a fraction. Locked threshold: 10.

6. **Majority threshold for BOOL "typically" / "usually" groups**: fraction
   > 0.5 strictly. Ties (= 0.5) map to `insufficient`.

7. **PROP tolerance**: a claim asserting value p is supported if
   |p_claimed - p_actual| ≤ 5 percentage points.

8. **Multi-vaccine "differ" verdict**: locked as an effect-size rule for v1.
   Two cohorts "differ" if |p1 - p2| > 10 percentage points. (A test-based
   alternative is possible but deferred.)

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

### Released as benchmark

- The hypothesis instances (text only) with cohort report IDs.
- The corresponding narrative texts (raw VAERS reports as provided by MedTempo).
- The gold verdicts and gold proportions.

### Internal (not released)

- The MedTempo annotations (events, relations, leveled orders). These compute
  the gold labels but are not exposed to evaluated systems.

The framework receives only the narrative text and the hypothesis. It must
extract whatever it needs to answer.

## Per-instance schema (release format)

JSONL, one record per line:

```json
{
  "hypothesis_id": "string",
  "group_id": "P-V1",
  "level": "vaccine",
  "answer_type": "BOOL",
  "register": "research",
  "format": "question",
  "text": "Among Pfizer reports, does headache precede fever in the majority of cases?",
  "cohort_report_ids": ["R001", "R042", ...],
  "gold_verdict": "supported",
  "gold_proportion": 0.68,
  "gold_n": 47,
  "factual_core": {
    "primitive": "precedes",
    "events": ["headache", "fever"],
    "vaccines": ["Pfizer"]
  }
}
```

The `factual_core` field is metadata used for evaluation diagnostics, not
input to the framework.

## What still needs work

See `open_questions.md` for items that are still under discussion (e.g.,
sequence with internal co-occurrence, exact synonym table contents).
