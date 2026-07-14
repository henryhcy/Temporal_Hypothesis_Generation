# Open Questions

Items still under discussion. Do not assume answers in code; surface gaps
when implementing.

When an item is resolved, move it to `decisions.md` with the date and
delete it from this file.

---

## Dataset

### First/last tie handling for CHOICE
Currently tie-reports are excluded from per-candidate counts. Question:
should CHOICE instances on ties be marked `insufficient` (single-valued
gold), or accept any tied option as supported (set-valued gold)?
**Current working assumption**: `insufficient` for clean single-valued gold.
Not yet locked.

### Synonym table contents
The manual synonym table for `{A}`/`{B}`/`{C}` slot-filling has not yet
been built. Open: how many synonyms per term type, source vocabulary
(UMLS, MeSH, manual), and validation process.

### Coverage of multi-vaccine pairs
With only three vaccine pairs, the multi-vaccine tier may be statistically
thin for some symptom pairs. Open: minimum cohort size in each pair before
generating multi-vaccine instances. Currently uses the general n ≥ 10
threshold, but may need tightening for "differ" verdicts.

### Verdict balance targets
Currently aiming for roughly balanced supported/refuted, with a 10-20%
insufficient slice. Exact targets per group not locked.

### Disconnected components in MedTempo
Need to measure the rate. If common, the leveled-order representation
needs to handle multiple components per report. If rare (under 5%), can
mark such reports as `insufficient` for cross-component hypotheses and
proceed. Pending corpus survey.

### Template replacement selection (PROP retirement + redundant backfill)
Remove PROP (P-V2, C-V2, S-V2); S-V1/F-V3 reworded to "most common" (become
twins of S-V3/F-V1) -- see `decisions.md` 2026-07-13. The corpus inventory is
now DONE (2026-07-14): narrowed to **R1, R3, R4, R5** (R2/R6/R7/R8 removed --
too thin / degenerate / a restated S-V4; see `decisions.md`). Still open before
locking: which of P-V2 -> R3, C-V2 -> R5, plus R4/R1 to instantiate; the exact
four-register YAML strings and gold-verdict rule per chosen group; and whether R6
folds into the S-V4 fix.

## Framework

### Architecture detail
The framework reads narrative + hypothesis and returns a verdict. The
internal pipeline (decomposition, evidence localization, relation
inference, aggregation, verdict synthesis) is sketched but not specified
in detail. Pending design pass.

### CRAFT integration
Whether the framework uses CRAFT as the relation extractor for open-book
mode, or implements its own hypothesis-conditioned extractor. Not locked.

## Evaluation

### Metrics breakdown
Headline metric is verdict agreement. Secondary metrics (proportion error,
stage-wise diagnostics, register-wise breakdowns) are agreed in principle
but not specified in detail.

### Baselines
Vanilla RAG, tool-using LLM with code execution, single-pass framework
variant, deterministic upper bound. Mentioned in earlier discussion;
not formalized in plan docs yet.

### Models to evaluate
Continuity with CRAFT suggests: GPT-4.1, Claude Sonnet 4.5, Llama-3.3-70B,
MedGemma-27B. To be confirmed once experimental budget and timeline are
firm.
