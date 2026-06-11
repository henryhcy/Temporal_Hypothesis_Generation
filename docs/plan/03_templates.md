# 03. Templates

## Structure

- **4 primitive families**: precedes, co-occurs, sequence, first / last
- **3 cohort levels**: report, vaccine, multi-vaccine (2-vaccine pairs in v1)
- **2 hypothesis formats**: question, claim
- **3 answer types**: BOOL (yes/no), CHOICE (pick one), PROP (fraction)
- **30 template groups** total, each projected into 3 registers plus the
  canonical seed

## Group inventory

| Family       | Report | Vaccine | Multi | Total |
|--------------|:------:|:-------:|:-----:|:-----:|
| precedes     | 2      | 3       | 2     | 7     |
| co-occurs    | 1      | 3       | 2     | 6     |
| sequence     | 1      | 4       | 2     | 8     |
| first / last | 3      | 3       | 3     | 9     |
| **Total**    | **7**  | **13**  | **9** | **30** |

## Registers

Each group is projected into three registers plus the original canonical
seed. All four are generated mechanically; no LLM rewrites.

| Register   | Description                                                              |
|------------|--------------------------------------------------------------------------|
| Original   | The canonical seed phrasing; kept as a baseline.                         |
| Research   | Precise scope, explicit cohort, formal vocabulary. Papers, reports.      |
| Media      | Public-facing, brand-named, comparison framing. Journalism, regulatory.  |
| Clinical   | Practitioner-conversational. References to patients, recipients.         |

The chart-style register has been explicitly **dropped**.

Negation modifier: a separate transformation applied to a subset of BOOL
instances to flip polarity. Gold answer flips correspondingly.

## Slot conventions

| Slot     | Meaning                                                          |
|----------|------------------------------------------------------------------|
| `{A}`, `{B}`, `{C}` | Event term types from MedTempo (plus synonyms). |
| `{v}`    | A single vaccine (Pfizer, Moderna, or Johnson).                  |
| `{v1}`, `{v2}` | Two vaccines for multi-vaccine groups.                     |
| `{r}`    | A report identifier or contextual reference ("this report").     |
| `{p}`    | An asserted proportion value (in PROP claim instances).          |

The synonym table for `{A}`/`{B}`/`{C}` is built manually from MedTempo
term types plus medically-equivalent alternatives.

## The 30 groups

For the full per-group seed list including all three register projections of
both question and claim forms, see the deliverable document
`Temporal_Hypothesis_Templates.docx` (kept under `docs/reference/`). The
group IDs and answer types are:

### precedes
- P-R1 (Report, BOOL): Does {A} occur before {B} in this report?
- P-R2 (Report, CHOICE): Which came first, {A} or {B}?
- P-V1 (Vaccine, BOOL): Does {A} typically precede {B} after {v}?
- P-V2 (Vaccine, PROP): In what fraction of {v} reports does {A} precede {B}?
- P-V3 (Vaccine, CHOICE): After {v}, which usually comes first, {A} or {B}?
- P-M1 (Multi, BOOL): Does the rate differ between {v1} and {v2}?
- P-M2 (Multi, CHOICE): After which of {v1}, {v2} does {A} more often precede {B}?

### co-occurs
- C-R1 (Report, BOOL): Do {A} and {B} co-occur in this report?
- C-V1 (Vaccine, BOOL): Do {A} and {B} typically co-occur after {v}?
- C-V2 (Vaccine, PROP): What fraction of {v} reports show {A} and {B} together?
- C-V3 (Vaccine, BOOL): Is co-occurrence the dominant relation for {A} and {B} after {v}?
- C-M1 (Multi, BOOL): Does the co-occurrence rate differ between {v1} and {v2}?
- C-M2 (Multi, CHOICE): After which of {v1}, {v2} do {A} and {B} more often co-occur?

### sequence
- S-R1 (Report, BOOL): Do {A}, {B}, {C} occur in the order {A} → {B} → {C}?
- S-V1 (Vaccine, BOOL): After {v}, do {A}, {B}, {C} typically occur as {A} → {B} → {C}?
- S-V2 (Vaccine, PROP): What fraction of {v} reports show this sequence?
- S-V3 (Vaccine, CHOICE): After {v}, what is the most common ordering?
- S-V4 (Vaccine, BOOL): After {v}, is the ordering consistent across reports?
- S-M1 (Multi, BOOL): Does the sequence rate differ between {v1} and {v2}?
- S-M2 (Multi, CHOICE): Is the sequence more common after {v1} or {v2}?
- S-M3 (Multi, BOOL): Is the typical ordering the same after {v1} and {v2}?

### first / last
- F-R1 (Report, CHOICE): Which of {A}, {B}, {C} occurs first in this report?
- F-R2 (Report, CHOICE): Which of {A}, {B}, {C} occurs last in this report?
- F-R3 (Report, BOOL): Is {A} the first of {A}, {B}, {C}?
- F-V1 (Vaccine, CHOICE): After {v}, which typically occurs first?
- F-V2 (Vaccine, CHOICE): After {v}, which typically occurs last?
- F-V3 (Vaccine, BOOL): After {v}, is {A} usually the first?
- F-M1 (Multi, BOOL): Is the typical first event the same after {v1} and {v2}?
- F-M2 (Multi, BOOL): Do {v1} and {v2} differ in which appears first?
- F-M3 (Multi, CHOICE): Is {A} the first event more often after {v1} or {v2}?

## Verdict mechanics

- **BOOL claim**: supported if the assertion matches; refuted if it doesn't.
- **CHOICE claim**: supported if it names the correct option.
- **PROP claim**: supported if the asserted value is within 5 percentage
  points of the true proportion (see Decision 7 in `decisions.md`).
- **Insufficient**: cohort below threshold, ordering indeterminable, or
  candidate events missing.

Refuted instances are generated by flipping the assertion (BOOL), naming
the wrong option (CHOICE), or asserting an off value (PROP).

## Generation pipeline

1. For each group, enumerate viable factual cores from MedTempo (cohorts
   with sufficient n, candidate event sets that appear).
2. Compute the gold artifact per core (proportion, verdict, n).
3. Balance supported / refuted / insufficient across the instance pool.
4. Instantiate templates per group per register, slot-fill from the synonym
   table.
5. Optional: apply negation modifier to a subset of BOOL instances.

Target final benchmark size: 10,000 to 15,000 instances.
