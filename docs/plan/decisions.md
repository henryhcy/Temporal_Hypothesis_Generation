# Decisions Log

Single source of truth for what has been settled. Append entries with the
date when a decision is locked. Do not silently rewrite past entries; if a
decision changes, append a new entry that supersedes it.

---

## Initial seed (project setup)

### Scope and framing
- **Project scope**: temporal hypothesis verification over clinical narratives, built on MedTempo.
- **Positioning**: agentic temporal claim verification, not deep research.
- **Out of scope for v1**: SIG groups, three-vaccine groups, cross-corpus extension, lay/forum registers, LLM-based hypothesis generation.

### Dataset
- **MedTempo treatment**: private scaffolding only; never released as part of the benchmark.
- **Framework input**: narrative text plus hypothesis only. No relations or event lists provided at inference.
- **Storage representation**: leveled order per report (list of co-exist clusters in temporal sequence).
- **Three vaccines**: Pfizer, Moderna, Johnson.
- **Relation vocabulary**: before, after, co-exist (only).
- **Co-exist semantics**: collapses true simultaneity and order-unknown into one bucket.
- **First-mention rule**: when a term appears multiple times in a narrative, only the first mention is recorded.
- **Transitive closure**: computed on-the-fly per query, not stored. Stored relations are direct annotations only.

### Gold-label computation rules
1. **precedes denominator (cohort level)**: only reports where both events appear AND the pair is ordered. Co-exist pairs excluded.
2. **co-occurs denominator**: reports where both events appear (co-exist kept, as it is the event of interest).
3. **sequence denominator**: reports containing all three events.
4. **first_among denominator**: reports containing all named candidates. Tie-reports excluded from per-candidate counts; tie rate reported separately.
5. **Minimum n threshold**: n = 10. Below this, verdict is `insufficient`.
6. **Majority threshold for BOOL "typically"**: > 0.5 strictly. Exact 0.5 maps to `insufficient`.
7. **PROP tolerance**: a claimed value supported if within 5 percentage points of true proportion.
8. **Multi-vaccine "differ" verdict**: effect-size rule, |p1 - p2| > 10 percentage points.

### Templates and registers
- **30 template groups total** (after redundancy correction and the F-M1/F-M2 review). Group IDs in `03_templates.md`.
- **Three active registers**: Research, Media, Clinical. Plus the canonical "Original" as a baseline.
- **Chart-style register dropped**.
- **Mechanical generation only**. No LLM-based rewrites.
- **Negation modifier**: applied to a subset of BOOL instances; flips the assertion polarity and the gold verdict.

### Multi-vaccine scope
- **Two-vaccine pairs only** for v1. Three-vaccine groups deferred.
- **Three pairs available**: Pfizer-Moderna, Pfizer-Johnson, Moderna-Johnson.

### Sequence semantics
- **Strict ordering for sequence_holds**: A → B → C requires level_of(A) < level_of(B) < level_of(C) with strict inequalities. Co-occurrence within the sequence does not satisfy strict ordering.
