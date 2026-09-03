# Template Faithfulness Audit — what each of the 184 hypothesis strings asks, diffed against the statistic that labels it

Branch `model-pipeline-design`, 2026-09-01. Companion to `11_model_pipeline.md` §10.1; deliverable for issue 24 (`09_next_steps.md` row 24).

Every gold label in `data/release/v1` is computed by one fixed statistic per template
group (`cores.MODE_BY_GROUP` -> `claim_schema.MODE_SPEC` / `pilot.RULE_BY_MODE`; the
arithmetic is `core/answers.py` over the helpers in `generation/corpus.py`). The
hypothesis TEXT comes from 184 strings in `data/templates/{pairwise,sequence,first_last}.yaml`:
20 groups x 4 registers x 2 formats = 160, plus 24 negated forms (C-V1, C-V2, C-V3).
Issue 13 (decisions.md 2026-08-14, "C-V3 register audit") found three registers asking a
MAJORITY question while the statistic was an ARGMAX; issue 24 (open_questions.md
"Framework") found P-V2/P-V4's original/media/clinical registers saying "more often"
(count language) while the statistic is a Fisher RATE comparison. This document is the
standing review both issues asked for, done once for every string: for each, the
denominator and the contrast the WORDING implies, what the CODE computes, and a verdict.

**Rubric** (fixed before reading the strings; applied uniformly):

- "typically", "usually", "in the majority of cases", "most people" = a proportion > 0.5
  over the conditioned denominator (FAITHFUL for the binomial modes when the denominator
  wording matches).
- "more often than" comparing two arms is AMBIGUOUS between counts and rates unless
  "rate" / "proportion" / "share" appears.
- A wording that leaves the denominator implicit (e.g. "After Moderna, does A typically
  occur before B?" does not say co-exist reports are excluded) is a NOTE, not a mismatch,
  unless it implies a DIFFERENT denominator.
- MISMATCH is reserved for a wording whose natural reading is a different proposition
  from the one computed.
- Strings that omit event slots the input cannot recover are UNDERDETERMINED-INPUT, a
  separate defect class from all of the above (`claim_schema.UNDERDETERMINED`).

Each string gets exactly one class. Every count below was measured on
`data/release/v1/pilot_instances_answers.jsonl` (18,492 instances / 147,936 records) and,
where an alternative reading needs numbers the release does not carry (whole-cohort
counts, antecedent counts, tie-inclusive first/last counts), on `data/medtempo.db`
through `CorpusIndex` -- the same index that produced the labels. Nothing is estimated.
Three classifications are judgment calls and are marked "weak" in the tables: C-V2 media
("more often" across two groups of people), P-M2 research ("proportion" of an unstated
base), and the first/last claims that drop "of the three". Each measurement's definition
is given inline in section 2 so it can be re-run from the release and the DB; no script
was added to the repository (this file is the audit's only artefact) and no code or data
was changed.

---

## 1. Findings at a glance

### 1.1 By class

| class | strings | of which negated forms | meaning |
|---|--:|--:|---|
| FAITHFUL | 70 | 9 | denominator and contrast both pinned by the wording (or forced by the claim shape) and equal to the statistic |
| NOTE | 65 | 8 | contrast matches; something is left implicit or lexically loose that has a plausible alternative reading -- measured or argued below; no label changes under the natural reading |
| AMBIGUOUS | 38 | 2 | two readings of the wording that yield DIFFERENT labels on measured instances (count vs rate; denominator; majority vs argmax; lexical) |
| MISMATCH | 1 | 1 | the wording's natural reading is a different proposition from the one computed |
| UNDERDETERMINED-INPUT | 10 | 4 | the string omits event slots and no input field recovers them, so the input does not determine the claim (a different defect class; the harness already emits `underdetermined` for these) |
| **total** | **184** | **24** | 20 groups x 4 registers x 2 formats = 160, plus 24 negated forms (C-V1, C-V2, C-V3) |

Of the 184: 32 are CHOICE *question* strings, which assert nothing (check (c),
section 3); 15 CHOICE *claim* strings omit the other candidate(s) but the
input's `options` field supplies them (NOTE); 10 BOOL strings omit event slots
with no input field to recover them (UNDERDETERMINED-INPUT).

### 1.2 By group

| group | mode | strings | FAITHFUL | NOTE | AMBIGUOUS | MISMATCH | UNDERDET. | release instances | measured exposure (instances, see section 2) |
|---|---|--:|--:|--:|--:|--:|--:|--:|---|
| P-R1 | `rep_dir_bool` | 8 | 8 | 0 | 0 | 0 | 0 | 600 | -- |
| P-R2 | `rep_dir_choice` | 8 | 5 | 3 | 0 | 0 | 0 | 600 | -- |
| P-V1 | `dir_bool` | 8 | 0 | 8 | 0 | 0 | 0 | 501 | co-exist inclusion (NOTE sensitivity): 110 signs / 176 labels |
| P-V2 | `antecedent_bool` | 8 | 0 | 0 | 8 | 0 | 0 | 2,253 | count 273; antecedent rate 158; both-present rate 169; clinical 2nd parse 1059 |
| P-V3 | `dir_choice` | 8 | 2 | 6 | 0 | 0 | 0 | 501 | co-exist inclusion (NOTE sensitivity): 110 signs / 176 labels |
| P-V4 | `pairpair_bool` | 8 | 0 | 0 | 8 | 0 | 0 | 8,571 | count 2194; both-present rate 495 |
| P-M2 | `multi_dir_precedes` | 8 | 0 | 0 | 8 | 0 | 0 | 87 | count 8; whole-cohort rate 8; both-present 4 |
| C-R1 | `rep_sym_bool` | 8 | 6 | 0 | 2 | 0 | 0 | 300 | co-presence reading of 'together': 119 |
| C-V1 | `sym_bool_cooccurs` | 16 | 7 | 9 | 0 | 0 | 0 | 756 | 0 (lexical notes only) |
| C-V2 | `assoc_bool` | 16 | 6 | 5 | 4 | 1 | 0 | 1,047 | media count reading 467; clinical negated question 145 |
| C-V3 | `cooc_modal_bool` | 16 | 8 | 0 | 0 | 0 | 8 | 522 | 522 x 4 underdetermined records |
| S-R1 | `rep_seq_bool` | 8 | 8 | 0 | 0 | 0 | 0 | 600 | -- |
| S-V1 | `seq_bool` | 8 | 0 | 8 | 0 | 0 | 0 | 6 | ties:orderable 11:5, 14:8, 2:0, 11:3 (no label change) |
| S-V3 | `modal_choice` | 8 | 0 | 8 | 0 | 0 | 0 | 6 | ties:orderable 11:5, 14:8, 2:0, 11:3 (no label change) |
| F-R1 | `rep_first_choice` | 8 | 6 | 2 | 0 | 0 | 0 | 600 | -- |
| F-R2 | `rep_last_choice` | 8 | 6 | 2 | 0 | 0 | 0 | 600 | -- |
| F-R3 | `rep_first_bool` | 8 | 8 | 0 | 0 | 0 | 0 | 600 | -- |
| F-V1 | `first_choice` | 8 | 0 | 5 | 3 | 0 | 0 | 102 | majority test 12 sup->ins; tie-inclusive 0 |
| F-V2 | `last_choice` | 8 | 0 | 5 | 3 | 0 | 0 | 138 | majority test 22 sup->ins; tie-inclusive 1 |
| F-V3 | `first_bool` | 8 | 0 | 4 | 2 | 0 | 2 | 102 | majority test 12 sup->ins; tie-inclusive 0; 102 x 2 underdetermined records |
| **all** | | **184** | **70** | **65** | **38** | **1** | **10** | **18,492** | |

Groups carrying at least one AMBIGUOUS or MISMATCH string: **P-V2, P-V4, P-M2, C-R1, C-V2, F-V1, F-V2, F-V3**. Of the
38 AMBIGUOUS strings, 24 are strong (P-V2, P-V4, the six count-worded
P-M2 strings, C-R1 clinical) and 14 are weak (P-M2 research, C-V2 media, the
eight first/last strings that read as majority as readily as argmax).

### 1.3 What the audit found

1. **Issue 24 is confirmed and its numbers reproduce exactly.** On P-V2 the count order
   (k1 > k2) and the rate order (k1/n1 > k2/n2) disagree on **273 of 2,253** instances
   (53 supported / 53 refuted / 167 insufficient); on P-V4 on **2,194 of 8,571** (687 /
   687 / 820). Method as in issue 24: sign(k1 - k2) vs sign(k1/n1 - k2/n2), ties counted
   as disagreements, rows with an empty arm skipped (251 and 953 `not_locatable` rows,
   whose label no reading can move). C-V2 467 and P-M2 8 also reproduce.
2. **"Rate" alone does not repair P-V2/P-V4.** The research registers say "rate" but never
   say *per what*. Read with the only population they name ("Among {v} reports"), both
   arms share one denominator and the rate order IS the count order -- the same 273 /
   2,194 instances. Read as the natural conditional ("the rate at which B follows A" =
   per report containing A), P-V2 differs from the code on **158** instances (14 / 14 /
   130). Read over reports with both events present (co-exist included), P-V2 differs on
   169 and P-V4 on **495** (35 / 35 / 425). So the fix issue 24 floated ("reword the
   three registers to rate language") is necessary but not sufficient: the ordered-pair
   denominator has to be named in the text or stated once as a release convention.
   Every one of the eight P-V2 strings and eight P-V4 strings is therefore AMBIGUOUS,
   not only the six count-worded ones.
3. **One MISMATCH, new.** C-V2 clinical `question_negated` -- "is {A} unassociated with
   {B} once their individual frequencies are accounted for?" -- asks for INDEPENDENCE, a
   two-sided point null. The code's negated claim is "not positively associated", and it
   is labelled supported by significant NEGATIVE association. On the **145** negated
   instances labelled supported, the literal answer to the question as worded is No (they
   are associated, negatively). The paired `claim_negated` ("not associated ... beyond
   what their individual frequencies imply") is one-sided and fine. 145 records.
4. **One syntactic ambiguity, new.** P-V2 clinical -- "does {B} more often follow {A} than
   {C}?" -- parses either as "than it follows C" (the code's arm 2 = P(C before B)) or as
   "than C follows A" (arm 2 = P(A before C)). The second parse differs from the code on
   **1,059 of 2,000** sign-defined instances (406 / 395 / 258): a different claim, not a
   different denominator. The original and media strings ("than it follows {C}", "than
   after {C}") are unambiguous on this point.
5. **One lexical ambiguity with label consequences.** C-R1 clinical -- "Did this patient
   have {A} and {B} together?" -- reads as co-present in the patient as readily as
   concurrent. Every posed pair is co-present, so that reading answers yes on all 300
   instances; gold refutes **119**. The other three C-R1 registers ("co-occur",
   "concurrent", "at the same time") are exact.
6. **The issue-13 class (majority vs argmax) survives, weakly, in eight first/last
   strings**: the F-V1 and F-V2 research/media/clinical claims ("{A} is most frequently
   the earliest", "{A} comes first most often") and F-V3 media ("is {A} most often the
   first among ..."). In every supported instance the named candidate does hold more than
   half of the tie-free denominator, so a point-majority reader agrees with the argmax;
   but under the same exact binomial test against 0.5, **12 of 34** (F-V1), **22 of 46**
   (F-V2) and **12 of 34** (F-V3) supported instances become insufficient, because
   named-vs-runner-up is a more powerful comparison than named-vs-everything-else.
   The strings that keep "among {A}, {B}, {C}" / "of the three" next to the superlative
   (all the originals, F-V3 clinical, all the questions) are argmax-anchored.
7. **No other string names a different cell or direction than the code** (check (a)).
   Arm order, the named cell (co_exist for C-V3; slot A for first/last; the slot ordering
   for sequence), and the first-named cohort for P-M2 all match `_realize_*` and
   `evidence_ids`.
8. **Negation** (check (b)): 23 of the 24 negated strings negate exactly the proposition of
   their plain form (the "< 0.5" vs "<= 0.5" difference between C-V1 research's
   `question_negated` and `claim_negated` lives at the exact tie, which the test never
   labels decisively). The 24th is the C-V2 clinical MISMATCH above.
9. **The largest sensitivity in the audit sits in the NOTE class**, exactly where the
   rubric puts implicit denominators: P-V1 and P-V3 never say that same-stage (co-exist)
   reports leave the denominator. A reader who counts them as "not before" flips the sign
   of the majority on **110 of 501** instances in each group (70 supported / 40
   insufficient) and, under the same binomial test and floor, the label on **176 of 501**
   (120 supported -> insufficient, 22 supported -> refuted, 34 insufficient -> refuted).
   The two groups share cores, so the numbers coincide. This is not a mismatch -- the
   family's stated rule excludes co-exist pairs -- but it is the strongest argument in
   this document for stating the conventions once, where the model can read them.
10. **UNDERDETERMINED-INPUT** (check (d)): C-V3 research and clinical (8 strings) and F-V3
    research (2 strings) omit the events. 522 x 4 + 102 x 2 = **2,292** records, exactly
    the count the oracle run reports as `underdetermined` (`11_model_pipeline.md` §10.3).
    The 15 CHOICE claims that omit candidates are not in this class: `options` is an
    `INPUT_FIELDS` member and recovers the set.
11. **Tie handling in first/last and sequence is implicit but immaterial.** Crediting a tie
    for first/last to every tied candidate changes the unique argmax on **0** F-V1, **1**
    F-V2 and **0** F-V3 instances. In the sequence groups tie-pattern reports outnumber
    orderable reports in every shipped instance (ties : orderable = 11:5, 14:8, 2:0, 11:3
    over the four distinct cores; S-V1 and S-V3 share them),
    but a tie pattern is not an "ordering" under the family's stated definition, so the
    argmax over orderings is unaffected.

---

## 2. Measured exposures

For every AMBIGUOUS or MISMATCH finding, and for the NOTE-class implicit denominators
where an alternative reading is well-formed, the table gives the number of release
instances on which a reader taking the alternative reading would order (or label) the
claim differently from the code. "Instances differing" is a sign comparison unless the
row says "same test", in which case the alternative denominator was run through the same
exact test, alpha and family floor as the gold label. Rows with an empty arm (n = 0 or
n2 = 0; gold `not_locatable`) are skipped in every row: P-V2 251, P-V4 953, P-M2 10,
C-V2 120, P-V1 56, P-V3 56, F-V1 12, F-V2 16, F-V3 12. Records = instances x the number
of strings of that register/format that render on those instances (each instance renders
8 records; negated variants render only on negated instances).

| # | group | strings (class) | alternative reading measured | instances differing from the code | by gold verdict (sup / ref / ins) | records (instances x strings) |
|--:|---|---|---|--:|---|--:|
| 1 | P-V2 | original, media, clinical q+c (AMBIGUOUS) | count order k1 > k2 vs rate order k1/n1 > k2/n2 | **273** of 2,253 | 53 sup / 53 ref / 167 ins | 1,638 |
| 2 | P-V2 | research q+c (AMBIGUOUS) | antecedent-conditioned rate k1/N_A vs k2/N_C (N_x = cohort reports containing x) | **158** of 2,253 | 14 sup / 14 ref / 130 ins | 316 |
| 3 | P-V2 | all 8 (denominator) | both-present rate k1/(n1+co-exist) vs k2/(n2+co-exist) | **169** of 2,253 | 20 sup / 20 ref / 129 ins | 1,352 |
| 4 | P-V2 | clinical q+c (AMBIGUOUS) | second parse 'B follows A more often than C follows A': arm 2 = P(A before C) | **1,059** of 2,253 | 406 sup / 395 ref / 258 ins | 2,118 |
| 5 | P-V4 | original, media, clinical q+c (AMBIGUOUS) | count order vs rate order | **2,194** of 8,571 | 687 sup / 687 ref / 820 ins | 13,164 |
| 6 | P-V4 | research q+c (AMBIGUOUS) | whole-cohort rate ('Among {v} reports, the A-before-B rate'): same denominator both arms = count order | **2,194** of 8,571 | 687 sup / 687 ref / 820 ins | 4,388 |
| 7 | P-V4 | all 8 (denominator) | both-present rate | **495** of 8,571 | 35 sup / 35 ref / 425 ins | 3,960 |
| 8 | P-M2 | original, media, clinical q+c (AMBIGUOUS) | count order vs rate order | **8** of 87 | 2 sup / 2 ref / 4 ins | 48 |
| 9 | P-M2 | research q+c (AMBIGUOUS, weak) | proportion of the whole cohort k/N | **8** of 87 | 2 sup / 2 ref / 4 ins | 16 |
| 10 | P-M2 | all 8 (denominator) | both-present rate | **4** of 87 | 0 sup / 0 ref / 4 ins | 32 |
| 11 | C-V2 | media q+c (+negated) (AMBIGUOUS, weak) | count order |A and B| vs |B without A| | **467** of 1,047 | 183 sup / 183 ref / 101 ins | 934 |
| 12 | C-V2 | clinical question_negated (MISMATCH) | 'unassociated' = independence: negated instances gold-labelled supported on significant NEGATIVE association | **145** of 1,047 | 145 sup / 0 ref / 0 ins | 145 |
| 13 | C-R1 | clinical q+c (AMBIGUOUS) | 'have A and B together' read as co-presence (always yes) | **119** of 300 | 0 sup / 119 ref / 0 ins | 238 |
| 14 | P-V1 | all 8 (NOTE sensitivity) | co-exist reports counted as not-before: sign of the majority | **110** of 501 | 70 sup / 0 ref / 40 ins | 880 |
| 15 | P-V1 | all 8 (NOTE sensitivity) | same, three-decision label under the same binomial test and floor | **176** of 501 | 142 sup / 0 ref / 34 ins | 1,408 |
| 16 | P-V3 | all 8 (6 NOTE, 2 FAITHFUL) sensitivity | co-exist reports counted as not-before: sign | **110** of 501 | 70 sup / 0 ref / 40 ins | 880 |
| 17 | P-V3 | all 8 sensitivity | same, three-decision label | **176** of 501 | 142 sup / 0 ref / 34 ins | 1,408 |
| 18 | F-V1 | research, media, clinical claims (AMBIGUOUS, weak) | majority reading: named share vs 0.5 under the same binomial test | **12** of 102 | 12 sup / 0 ref / 0 ins | 36 |
| 19 | F-V2 | research, media, clinical claims (AMBIGUOUS, weak) | majority reading, same test | **22** of 138 | 22 sup / 0 ref / 0 ins | 66 |
| 20 | F-V3 | media q+c (AMBIGUOUS, weak) | majority reading, same test | **12** of 102 | 12 sup / 0 ref / 0 ins | 24 |
| 21 | F-V1 | all 8 (NOTE sensitivity) | tie credited to every tied candidate: unique argmax changes | **0** of 102 | 0 sup / 0 ref / 0 ins | 0 |
| 22 | F-V2 | all 8 (NOTE sensitivity) | tie credited to every tied candidate | **1** of 138 | 1 sup / 0 ref / 0 ins | 8 |
| 23 | F-V3 | all 8 (NOTE sensitivity) | tie credited to every tied candidate | **0** of 102 | 0 sup / 0 ref / 0 ins | 0 |

Reading the table: rows 1 and 5 are issue 24's 273 / 2,194. Rows 2, 6 and 9 are the part
issue 24 missed -- the "rate"/"proportion" registers are exposed too, through their
unstated denominator. Rows 3, 7 and 10 show that no P-V2/P-V4/P-M2 register states the
denominator, so the both-present reading is available to all eight strings of each
group. Row 4 is the P-V2 clinical second parse (its base is 2,000, not 2,002: two further
instances have A and C never ordered, so the second-parse sign is undefined). Row 11 is
the weak C-V2 media count reading; row 12 is the MISMATCH; row 13 the C-R1 lexical
ambiguity. Rows 14-17 are the NOTE-class co-exist sensitivity for P-V1/P-V3 (not a defect
under the rubric; reported because it is the largest number here). Rows 18-20 are the
surviving issue-13 class; rows 21-23 show that the implicit tie rule in first/last costs
at most one label.

---

## 3. The four cross-cutting checks

**(a) Named cell / direction.** For each mode the string's named cell and asserted
direction were read against `cores._realize_*` and `evidence.evidence_ids`: P-V2 arm 1 is
(A, B) with k1 = A before B ("B follows A"), arm 2 is (C, B); P-V4 arms (A, B) and (C,
D); P-M2 cohort 1 is the first-named vaccine; C-V3's named cell is co_exist; first/last
name slot A; the sequence modes name the slot ordering. All 184 strings agree with the
code on this, with two exceptions already counted: the P-V2 clinical second parse
(finding 4) changes arm 2, and the C-V2 clinical `question_negated` (finding 3) changes
the proposition from one-sided to two-sided. The issue-13 class (majority wording on an
argmax statistic) is gone from C-V3 -- all four registers now ask the argmax, and the
media register's "together more often than in either order" is literally
co_exist > max(before, after) -- but it persists weakly in eight first/last strings
(finding 6).

**(b) Negated forms.** Twelve register pairs (C-V1, C-V2, C-V3 x 4 registers), each with
a `question_negated` and a `claim_negated`. `oriented_significance` implements negation as
a tail swap (the negated claim tail is "less"), so the faithful negation of "share > 0.5"
is "share < 0.5" and of "co_exist is the argmax" is "co_exist is not". Twenty-three
strings do exactly that ("do NOT typically", "NOT concurrent in the majority", "no more
prevalent", "do NOT show up together more often than in either order" = not(co > before
and co > after) = co <= max). C-V1 research's question says "a minority of cases" (< 0.5)
where its claim says "NOT ... in the majority" (<= 0.5) -- same labels, since the exact
tie is never decisive (NOTE). C-V2 clinical's question says "unassociated" (= independent)
where its claim says "not associated beyond what their frequencies imply" (one-sided):
different propositions, and the labels diverge on 145 instances (MISMATCH). Negated
instances are never labelled insufficient (negation is derived only for decisive cores),
so the exposure is exactly the negated-supported count.

**(c) CHOICE question forms.** The 32 CHOICE question strings ("Which came first,
A or B?", "what is the most common ordering", "which cohort shows a higher proportion")
assert nothing. The instance's supported/refuted polarity is carried by slot order -- the
asserted option is slot A of the paired claim (`claim_schema.asserted_option_for`) -- and
the question is scored on `gold_answer` against a per-record seeded shuffle of `options`
(`evaluate.shuffle_options`; the release's `options` list already differs from the slot
order on e.g. F-V1-0000). This is a harness convention, not something the string
communicates; the appendix marks every such string "(c)" and still classifies its
denominator/contrast wording. Separately, 15 CHOICE *claims* name only the asserted
option ("In this case, {A} came first.", "{A} tends to come first.", "{A} is most
frequently the earliest."); they are determined by the input only because `options` is
an input field, and are marked NOTE for that reason.

**(d) Lossy templates.** C-V3 research and clinical (8 strings incl. negated) and F-V3
research (2 strings) contain no event slots (C-V3) or only {A} (F-V3), and as BOOL
groups have no `options` field to recover them. Their denominator and contrast wording is
otherwise faithful ("concurrent presentation is the most common relation" among reports
with both; "the single most frequent earliest event"). They are UNDERDETERMINED-INPUT --
the input does not determine the claim -- and produce the 2,292 `underdetermined` records
the harness already expects. Whether to keep them as the harness's underdetermined probe
or to insert the slots is a design decision (section 4.3), not a labelling error.

---

## 4. Recommendations

### 4.1 Reword: the 24 strong AMBIGUOUS strings and the MISMATCH, plus (optionally) the four C-V2 media strings

Text-only regeneration; instance ids, cores and labels are unchanged (the label never
depended on the text). Each proposal keeps the register's voice per
`03_templates.md` (original = canonical; research = precise scope, formal; media =
public-facing, brand-named; clinical = practitioner-conversational). "Rate"/"more likely"
settles count-vs-rate; the denominator is named where the register can bear it and
otherwise left to the convention statement in 4.2.

| group | register | format | current | proposed |
|---|---|---|---|---|
| P-V2 | original | question | After {v}, does {B} follow {A} more often than it follows {C}? | After {v}, does {B} follow {A} at a higher rate than it follows {C}? |
| P-V2 | original | claim | After {v}, {B} follows {A} more often than it follows {C}. | After {v}, {B} follows {A} at a higher rate than it follows {C}. |
| P-V2 | research | question | Among {v} reports, is the rate at which {B} follows {A} higher than the rate at which it follows {C}? | Among {v} reports in which each pair occurs at different stages, is the rate at which {B} follows {A} higher than the rate at which it follows {C}? |
| P-V2 | research | claim | Among {v} reports, the rate at which {B} follows {A} is higher than the rate at which it follows {C}. | Among {v} reports in which each pair occurs at different stages, the rate at which {B} follows {A} is higher than the rate at which it follows {C}. |
| P-V2 | media | question | After {v}, does {B} come after {A} more often than after {C}? | After {v}, is {B} more likely to come after {A} than after {C}? |
| P-V2 | media | claim | After {v}, {B} comes after {A} more often than after {C}. | After {v}, {B} is more likely to come after {A} than after {C}. |
| P-V2 | clinical | question | In {v} recipients, does {B} more often follow {A} than {C}? | In {v} recipients, is {B} more likely to follow {A} than to follow {C}? |
| P-V2 | clinical | claim | In {v} recipients, {B} more often follows {A} than {C}. | In {v} recipients, {B} is more likely to follow {A} than to follow {C}. |
| P-V4 | original | question | After {v}, does {A} precede {B} more often than {C} precedes {D}? | After {v}, does {A} precede {B} at a higher rate than {C} precedes {D}? |
| P-V4 | original | claim | After {v}, {A} precedes {B} more often than {C} precedes {D}. | After {v}, {A} precedes {B} at a higher rate than {C} precedes {D}. |
| P-V4 | research | question | Among {v} reports, is the {A}-before-{B} rate higher than the {C}-before-{D} rate? | Among {v} reports in which each pair occurs at different stages, is the {A}-before-{B} rate higher than the {C}-before-{D} rate? |
| P-V4 | research | claim | Among {v} reports, the {A}-before-{B} rate is higher than the {C}-before-{D} rate. | Among {v} reports in which each pair occurs at different stages, the {A}-before-{B} rate is higher than the {C}-before-{D} rate. |
| P-V4 | media | question | After {v}, does {A} come before {B} more often than {C} comes before {D}? | After {v}, is {A} more likely to come before {B} than {C} is to come before {D}? |
| P-V4 | media | claim | After {v}, {A} comes before {B} more often than {C} comes before {D}. | After {v}, {A} is more likely to come before {B} than {C} is to come before {D}. |
| P-V4 | clinical | question | In {v} recipients, is the {A}-then-{B} order more frequent than the {C}-then-{D} order? | In {v} recipients, is the {A}-then-{B} order proportionally more frequent than the {C}-then-{D} order? |
| P-V4 | clinical | claim | In {v} recipients, the {A}-then-{B} order is more frequent than the {C}-then-{D} order. | In {v} recipients, the {A}-then-{B} order is proportionally more frequent than the {C}-then-{D} order. |
| P-M2 | original | question | After which vaccine, {v1} or {v2}, does {A} more often precede {B}? | After which vaccine, {v1} or {v2}, does {A} precede {B} at a higher rate? |
| P-M2 | original | claim | {A} precedes {B} more often after {v1} than after {v2}. | {A} precedes {B} at a higher rate after {v1} than after {v2}. |
| P-M2 | media | question | Is {A}-before-{B} more common after {v1} or {v2}? | Is {A}-before-{B} proportionally more common after {v1} or {v2}? |
| P-M2 | media | claim | {A}-before-{B} is more common after {v1} than {v2}. | {A}-before-{B} is proportionally more common after {v1} than {v2}. |
| P-M2 | clinical | question | In which group is {A} more often the precursor to {B}, {v1} or {v2} recipients? | In which group is {A} more likely to be the precursor to {B}, {v1} or {v2} recipients? |
| P-M2 | clinical | claim | {v1} recipients more often have {A} as a precursor to {B}. | {v1} recipients are more likely to have {A} as a precursor to {B}. |
| C-R1 | clinical | question | Did this patient have {A} and {B} together? | Did {A} and {B} present concurrently in this patient? |
| C-R1 | clinical | claim | This patient had {A} and {B} together. | In this patient, {A} and {B} presented concurrently. |
| C-V2 | clinical | question_negated | In {v} recipients, is {A} unassociated with {B} once their individual frequencies are accounted for? | In {v} recipients, is {A} NOT associated with {B} beyond what their individual frequencies imply? |
| C-V2 | media | question / claim (+negated) | ... report {B} more often than everyone else does | After {v}, do a larger share of people who report {A} also report {B} than of everyone else? / After {v}, a larger share of people who report {A} also report {B} than of everyone else. / negated: ... report {B} at no higher a rate than everyone else |

P-M2's exposure is 8 instances (4 decisive); "accept and document" is defensible there,
and the rewording is offered only so the whole two-arm family speaks the same way. The
C-V2 media rewording is likewise optional (the per-capita reading is the ordinary one);
it is listed because it costs two words.

### 4.2 Accept and document (NOTE class, weak AMBIGUOUS, and the implicit denominators everywhere)

No register of any cohort group states its conditioning rule in full, and the rubric is
right that a natural-language hypothesis should not have to. But the P-V1/P-V3 numbers
(176 of 501 labels move under the most natural alternative reading) say the rule must be
stated *somewhere the reader of the text can see it*. Recommendation: a four-line
convention statement shipped with the release (README / `dataset_statistics.md`) and
included verbatim in every harness prompt and in the paper's task definition:

> 1. "A precedes / occurs before / follows B" claims are over reports in which A and B are
>    recorded at *different* stages; reports recording them at the same stage are neither
>    for nor against the order and are excluded.
> 2. "A and B co-occur / are concurrent / together" means recorded at the *same* stage of
>    the same report; the denominator is reports containing both.
> 3. "The most common ordering of A, B, C" is over reports recording all three at
>    pairwise-distinct stages; "most commonly the first / last" is over reports containing
>    all candidates with a unique earliest / latest.
> 4. "Most common / dominant / most frequently" is an argmax against the runner-up, not a
>    majority; "typically / usually / in the majority" is a majority.

With that statement in place the 65 NOTE strings need no text change. Two optional
tightenings, each two words: C-V1 media "show up together" -> "show up at the same time"
(matches C-R1 media); the eight weak first/last strings -> append "of the three" /
restore "among {A}, {B}, {C}" (e.g. "In {v} reports with all three, {A} is most frequently
the earliest of the three."), which also removes the candidate-set dependence on
`options` for those claims.

### 4.3 UNDERDETERMINED-INPUT (10 strings, 2,292 records)

Two one-slot insertions fix them ("Among {v} reports with both {A} and {B}, is concurrent
presentation the most common relation?"; "In {v} reports with all three of {A}, {B}, {C},
is {A} the single most frequent earliest event?"). But these records are currently the
harness's only *naturally occurring* underdetermined probe (§10.3 counts exactly 2,292
"expected by template"). Decision for the user: keep them as the probe (and say so in
the paper), or fix the strings and build the probe deliberately. Either is sound; leaving
them unfixed *without* saying they are the probe is the only wrong option.

### 4.4 Cost and side effects

All changes above are text-only: `instances.build_records` re-renders from the same
cores, so ids, `fact_id`s, evidence ids and labels are byte-identical, and the
`validate_gold.py` invariants are unaffected. The register-invariance metric on P-V2/P-V4
(issue 24's confound) becomes interpretable only after 4.1; until then a model that reads
the text as written can legitimately disagree with the gold on 273 / 2,194 instances and
be scored wrong for it. The rules parser (`extract/rules.py`) is template-keyed and is
not affected either way.

---

## Appendix A -- the 184 strings

One row per template string, grouped by template group; the "code computes" line in each
group header is the same for every row of that group (it is a property of the mode).
Columns: register, format, negated, the verbatim string, the denominator the wording
implies, the quantity/contrast the wording implies, the verdict, and a one-clause reason.
"(c)" marks a neutral CHOICE question (section 3). Exposure numbers in the reasons are the
instance counts of section 2.

### P-R1 -- `rep_dir_bool` (BOOL, report level; 8 strings; 600 instances)

**Code computes:** single report, no test: relation(A,B) at first-mention stages; `before` -> supported, else refuted (co-exist pairs are never posed since 2026-08-14).  
**Classes:** 8 FAITHFUL.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 1 | original | question |  | Did {A} occur before {B} in report {r}? | this report | A at an earlier stage than B (single observation) | **FAITHFUL** | before/precede/happen before/come before = the per-report before relation; exact |
| 2 | original | claim |  | In report {r}, {A} occurred before {B}. | this report | A at an earlier stage than B (single observation) | **FAITHFUL** | before/precede/happen before/come before = the per-report before relation; exact |
| 3 | research | question |  | In this report, does {A} precede {B}? | this report | A at an earlier stage than B (single observation) | **FAITHFUL** | before/precede/happen before/come before = the per-report before relation; exact |
| 4 | research | claim |  | This report records {A} preceding {B}. | this report | A at an earlier stage than B (single observation) | **FAITHFUL** | before/precede/happen before/come before = the per-report before relation; exact |
| 5 | media | question |  | In this case, did {A} happen before {B}? | this report | A at an earlier stage than B (single observation) | **FAITHFUL** | before/precede/happen before/come before = the per-report before relation; exact |
| 6 | media | claim |  | In this case, {A} happened before {B}. | this report | A at an earlier stage than B (single observation) | **FAITHFUL** | before/precede/happen before/come before = the per-report before relation; exact |
| 7 | clinical | question |  | Did {A} come before {B} in this patient? | this report | A at an earlier stage than B (single observation) | **FAITHFUL** | before/precede/happen before/come before = the per-report before relation; exact |
| 8 | clinical | claim |  | In this patient, {A} came before {B}. | this report | A at an earlier stage than B (single observation) | **FAITHFUL** | before/precede/happen before/come before = the per-report before relation; exact |

### P-R2 -- `rep_dir_choice` (CHOICE, report level; 8 strings; 600 instances)

**Code computes:** single report, no test: names the earlier of A, B; co-exist pairs never posed.  
**Classes:** 5 FAITHFUL, 3 NOTE.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 9 | original | question |  | Which came first in report {r}, {A} or {B}? | this report | which of A, B is earlier (single observation) | **FAITHFUL** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list |
| 10 | original | claim |  | In report {r}, {A} came first, before {B}. | this report | A earlier than B | **FAITHFUL** | names both events; exact |
| 11 | research | question |  | Of {A} and {B}, which is the earlier event in this report? | this report | which of A, B is earlier (single observation) | **FAITHFUL** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list |
| 12 | research | claim |  | In this report, {A} is the earlier event. | this report | A earlier than the other option | **NOTE** | omits B; the two-option set is supplied by the input `options` field, so the claim is determined by the input, not by the string |
| 13 | media | question |  | In this case, which came first, {A} or {B}? | this report | which of A, B is earlier (single observation) | **FAITHFUL** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list |
| 14 | media | claim |  | In this case, {A} came first. | this report | A earlier than the other option | **NOTE** | omits B; the two-option set is supplied by the input `options` field, so the claim is determined by the input, not by the string |
| 15 | clinical | question |  | Between {A} and {B}, which came first in this patient? | this report | which of A, B is earlier (single observation) | **FAITHFUL** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list |
| 16 | clinical | claim |  | In this patient, {A} came first. | this report | A earlier than the other option | **NOTE** | omits B; the two-option set is supplied by the input `options` field, so the claim is determined by the input, not by the string |

### P-V1 -- `dir_bool` (BOOL, vaccine level; 8 strings; 501 instances)

**Code computes:** n = cohort reports with A and B at DISTINCT stages (co-exist excluded); k = A before B; exact binomial k/n vs 0.5, both one-sided tails; floor n >= 10.  
**Classes:** 8 NOTE.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 17 | original | question |  | Does {A} typically occur before {B} after {v}? | {v} reports where both occur (co-exist reports not said to be excluded) | proportion A-before-B > 0.5 ('typically') | **NOTE** | '>0.5' matches the binomial; the ORDERED-pair denominator is implicit -- a reader who counts co-exist reports as 'not before' flips the sign on 110/501 instances (70 sup / 0 ref / 40 ins) and the same-test label on 176/501 (120 sup->ins, 22 sup->ref, 34 ins->ref) |
| 18 | original | claim |  | After {v}, {A} typically occurs before {B}. | {v} reports where both occur (co-exist reports not said to be excluded) | proportion A-before-B > 0.5 ('typically') | **NOTE** | '>0.5' matches the binomial; the ORDERED-pair denominator is implicit -- a reader who counts co-exist reports as 'not before' flips the sign on 110/501 instances (70 sup / 0 ref / 40 ins) and the same-test label on 176/501 (120 sup->ins, 22 sup->ref, 34 ins->ref) |
| 19 | research | question |  | Among {v} reports, does {A} precede {B} in the majority of cases? | 'Among {v} reports ... cases' -- cases where both occur, implicit | proportion > 0.5 ('in the majority of cases') | **NOTE** | '>0.5' matches the binomial; the ORDERED-pair denominator is implicit -- a reader who counts co-exist reports as 'not before' flips the sign on 110/501 instances (70 sup / 0 ref / 40 ins) and the same-test label on 176/501 (120 sup->ins, 22 sup->ref, 34 ins->ref) |
| 20 | research | claim |  | Among {v} reports, {A} precedes {B} in the majority of cases. | 'Among {v} reports ... cases' -- cases where both occur, implicit | proportion > 0.5 ('in the majority of cases') | **NOTE** | '>0.5' matches the binomial; the ORDERED-pair denominator is implicit -- a reader who counts co-exist reports as 'not before' flips the sign on 110/501 instances (70 sup / 0 ref / 40 ins) and the same-test label on 176/501 (120 sup->ins, 22 sup->ref, 34 ins->ref) |
| 21 | media | question |  | After {v}, do most people get {A} before {B}? | 'most people' after {v} -- people with both events, implicit | proportion > 0.5 ('most people') | **NOTE** | '>0.5' matches the binomial; the ORDERED-pair denominator is implicit -- a reader who counts co-exist reports as 'not before' flips the sign on 110/501 instances (70 sup / 0 ref / 40 ins) and the same-test label on 176/501 (120 sup->ins, 22 sup->ref, 34 ins->ref) |
| 22 | media | claim |  | After {v}, most people get {A} before {B}. | 'most people' after {v} -- people with both events, implicit | proportion > 0.5 ('most people') | **NOTE** | '>0.5' matches the binomial; the ORDERED-pair denominator is implicit -- a reader who counts co-exist reports as 'not before' flips the sign on 110/501 instances (70 sup / 0 ref / 40 ins) and the same-test label on 176/501 (120 sup->ins, 22 sup->ref, 34 ins->ref) |
| 23 | clinical | question |  | In {v} recipients, does {A} usually come before {B}? | {v} recipients with both, implicit | proportion > 0.5 ('usually') | **NOTE** | '>0.5' matches the binomial; the ORDERED-pair denominator is implicit -- a reader who counts co-exist reports as 'not before' flips the sign on 110/501 instances (70 sup / 0 ref / 40 ins) and the same-test label on 176/501 (120 sup->ins, 22 sup->ref, 34 ins->ref) |
| 24 | clinical | claim |  | In {v} recipients, {A} usually comes before {B}. | {v} recipients with both, implicit | proportion > 0.5 ('usually') | **NOTE** | '>0.5' matches the binomial; the ORDERED-pair denominator is implicit -- a reader who counts co-exist reports as 'not before' flips the sign on 110/501 instances (70 sup / 0 ref / 40 ins) and the same-test label on 176/501 (120 sup->ins, 22 sup->ref, 34 ins->ref) |

### P-V2 -- `antecedent_bool` (BOOL, vaccine level; 8 strings; 2,253 instances)

**Code computes:** arm 1: n1 = reports with A and B at distinct stages, k1 = A before B; arm 2: n2 = reports with C and B at distinct stages, k2 = C before B; one cohort; Fisher exact k1/n1 vs k2/n2, both tails; floor 10 on each arm.  
**Classes:** 8 AMBIGUOUS.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 25 | original | question |  | After {v}, does {B} follow {A} more often than it follows {C}? | unstated: reports in which B follows A vs reports in which B follows C; no base given | 'more often' -- a count (k1 > k2) or a rate | **AMBIGUOUS** | count vs rate: sign(k1-k2) != sign(k1/n1-k2/n2) on 273/2253 instances (53 sup / 53 ref / 167 ins); the arm denominator is also unstated -- the antecedent-conditioned rate (k1/N_A vs k2/N_C) differs on 158 (14 sup / 14 ref / 130 ins), the both-present rate on 169 (20 sup / 20 ref / 129 ins) |
| 26 | original | claim |  | After {v}, {B} follows {A} more often than it follows {C}. | unstated: reports in which B follows A vs reports in which B follows C; no base given | 'more often' -- a count (k1 > k2) or a rate | **AMBIGUOUS** | count vs rate: sign(k1-k2) != sign(k1/n1-k2/n2) on 273/2253 instances (53 sup / 53 ref / 167 ins); the arm denominator is also unstated -- the antecedent-conditioned rate (k1/N_A vs k2/N_C) differs on 158 (14 sup / 14 ref / 130 ins), the both-present rate on 169 (20 sup / 20 ref / 129 ins) |
| 27 | research | question |  | Among {v} reports, is the rate at which {B} follows {A} higher than the rate at which it follows {C}? | 'the rate at which B follows A' -- most naturally per occurrence of A (reports with A); code uses reports with A and B at distinct stages; 'Among {v} reports' suggests the whole cohort | rate comparison | **AMBIGUOUS** | 'rate' settles count-vs-rate but not the denominator: the antecedent-conditioned rate flips 158/2253 (14 sup / 14 ref / 130 ins); a whole-cohort rate has the same denominator on both arms and so orders exactly as the count (273) |
| 28 | research | claim |  | Among {v} reports, the rate at which {B} follows {A} is higher than the rate at which it follows {C}. | 'the rate at which B follows A' -- most naturally per occurrence of A (reports with A); code uses reports with A and B at distinct stages; 'Among {v} reports' suggests the whole cohort | rate comparison | **AMBIGUOUS** | 'rate' settles count-vs-rate but not the denominator: the antecedent-conditioned rate flips 158/2253 (14 sup / 14 ref / 130 ins); a whole-cohort rate has the same denominator on both arms and so orders exactly as the count (273) |
| 29 | media | question |  | After {v}, does {B} come after {A} more often than after {C}? | unstated: reports in which B follows A vs reports in which B follows C; no base given | 'more often' -- a count (k1 > k2) or a rate | **AMBIGUOUS** | count vs rate: sign(k1-k2) != sign(k1/n1-k2/n2) on 273/2253 instances (53 sup / 53 ref / 167 ins); the arm denominator is also unstated -- the antecedent-conditioned rate (k1/N_A vs k2/N_C) differs on 158 (14 sup / 14 ref / 130 ins), the both-present rate on 169 (20 sup / 20 ref / 129 ins) |
| 30 | media | claim |  | After {v}, {B} comes after {A} more often than after {C}. | unstated: reports in which B follows A vs reports in which B follows C; no base given | 'more often' -- a count (k1 > k2) or a rate | **AMBIGUOUS** | count vs rate: sign(k1-k2) != sign(k1/n1-k2/n2) on 273/2253 instances (53 sup / 53 ref / 167 ins); the arm denominator is also unstated -- the antecedent-conditioned rate (k1/N_A vs k2/N_C) differs on 158 (14 sup / 14 ref / 130 ins), the both-present rate on 169 (20 sup / 20 ref / 129 ins) |
| 31 | clinical | question |  | In {v} recipients, does {B} more often follow {A} than {C}? | unstated (as original) | 'more often' -- count or rate; AND 'than {C}' may attach as 'than C [follows A]' | **AMBIGUOUS** | count vs rate (273/2253) AND a syntactic ambiguity: parsed as 'B follows A more often than C follows A' the second arm becomes P(A before C) -- that reading differs from the code on 1059/2000 sign-defined instances (406 sup / 395 ref / 258 ins) |
| 32 | clinical | claim |  | In {v} recipients, {B} more often follows {A} than {C}. | unstated (as original) | 'more often' -- count or rate; AND 'than {C}' may attach as 'than C [follows A]' | **AMBIGUOUS** | count vs rate (273/2253) AND a syntactic ambiguity: parsed as 'B follows A more often than C follows A' the second arm becomes P(A before C) -- that reading differs from the code on 1059/2000 sign-defined instances (406 sup / 395 ref / 258 ins) |

### P-V3 -- `dir_choice` (CHOICE, vaccine level; 8 strings; 501 instances)

**Code computes:** same statistic as dir_bool; the CHOICE answer is the event with the higher ordered share.  
**Classes:** 2 FAITHFUL, 6 NOTE.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 33 | original | question |  | After {v}, which usually comes first, {A} or {B}? | {v} reports with both, co-exist implicit | which event has the > 0.5 ordered share ('usually') | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; co-exist exclusion implicit -- the both-present reading flips 110/501 signs and 176 same-test labels (twin of P-V1: identical cores) |
| 34 | original | claim |  | After {v}, {A} usually comes before {B}. | {v} reports with both, co-exist implicit | A before B in > 0.5 ('usually') | **NOTE** | co-exist exclusion implicit -- the both-present reading flips 110/501 signs and 176 same-test labels (twin of P-V1: identical cores) |
| 35 | research | question |  | Among {v} reports with both, which more often precedes the other, {A} or {B}? | {v} reports with both -- explicit | count(A before B) vs count(B before A) | **FAITHFUL** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; explicit both-present base; co-exist reports precede neither, so the comparison equals the ordered-pair majority exactly |
| 36 | research | claim |  | Among {v} reports with both, {A} more often precedes {B}. | {v} reports with both -- explicit | count(A before B) > count(B before A) | **FAITHFUL** | explicit both-present base; co-exist reports add to neither count, so this IS k/n > 0.5 over the ordered pairs |
| 37 | media | question |  | After {v}, which side effect tends to come first, {A} or {B}? | {v} reports with both, implicit | which event 'tends to come first' (> 0.5) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; co-exist exclusion implicit -- the both-present reading flips 110/501 signs and 176 same-test labels (twin of P-V1: identical cores) |
| 38 | media | claim |  | After {v}, {A} tends to come first. | {v} reports with both, implicit | A first in > 0.5 ('tends to') | **NOTE** | omits B (supplied by `options`); co-exist exclusion implicit -- the both-present reading flips 110/501 signs and 176 same-test labels (twin of P-V1: identical cores) |
| 39 | clinical | question |  | In {v} patients, what usually shows up first, {A} or {B}? | {v} patients with both, implicit | which 'usually shows up first' (> 0.5) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; co-exist exclusion implicit -- the both-present reading flips 110/501 signs and 176 same-test labels (twin of P-V1: identical cores) |
| 40 | clinical | claim |  | In {v} patients, {A} usually shows up first. | {v} patients with both, implicit | A first in > 0.5 ('usually') | **NOTE** | omits B (supplied by `options`); co-exist exclusion implicit -- the both-present reading flips 110/501 signs and 176 same-test labels (twin of P-V1: identical cores) |

### P-V4 -- `pairpair_bool` (BOOL, vaccine level; 8 strings; 8,571 instances)

**Code computes:** arm 1 = ordered (A,B) pairs, arm 2 = ordered (C,D) pairs, one cohort; Fisher exact k1/n1 vs k2/n2, both tails; floor 10 on each arm.  
**Classes:** 8 AMBIGUOUS.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 41 | original | question |  | After {v}, does {A} precede {B} more often than {C} precedes {D}? | unstated: reports with A before B vs reports with C before D | 'more often' -- count (k1 > k2) or rate | **AMBIGUOUS** | count vs rate: sign(k1-k2) != sign(k1/n1-k2/n2) on 2194/8571 instances (687 sup / 687 ref / 820 ins); arm denominators unstated (both-present reading differs on 495: 35 sup / 35 ref / 425 ins) |
| 42 | original | claim |  | After {v}, {A} precedes {B} more often than {C} precedes {D}. | unstated: reports with A before B vs reports with C before D | 'more often' -- count (k1 > k2) or rate | **AMBIGUOUS** | count vs rate: sign(k1-k2) != sign(k1/n1-k2/n2) on 2194/8571 instances (687 sup / 687 ref / 820 ins); arm denominators unstated (both-present reading differs on 495: 35 sup / 35 ref / 425 ins) |
| 43 | research | question |  | Among {v} reports, is the {A}-before-{B} rate higher than the {C}-before-{D} rate? | 'Among {v} reports, the A-before-B rate' -- read literally, a rate over the cohort; code: over reports with A and B at distinct stages | rate comparison | **AMBIGUOUS** | 'rate' settles count-vs-rate but the denominator is unstated: the whole-cohort rate has one denominator for both arms and orders exactly as the count (2194/8571); the both-present rate differs on 495 (35 sup / 35 ref / 425 ins) |
| 44 | research | claim |  | Among {v} reports, the {A}-before-{B} rate is higher than the {C}-before-{D} rate. | 'Among {v} reports, the A-before-B rate' -- read literally, a rate over the cohort; code: over reports with A and B at distinct stages | rate comparison | **AMBIGUOUS** | 'rate' settles count-vs-rate but the denominator is unstated: the whole-cohort rate has one denominator for both arms and orders exactly as the count (2194/8571); the both-present rate differs on 495 (35 sup / 35 ref / 425 ins) |
| 45 | media | question |  | After {v}, does {A} come before {B} more often than {C} comes before {D}? | unstated: reports with A before B vs reports with C before D | 'more often' -- count (k1 > k2) or rate | **AMBIGUOUS** | count vs rate: sign(k1-k2) != sign(k1/n1-k2/n2) on 2194/8571 instances (687 sup / 687 ref / 820 ins); arm denominators unstated (both-present reading differs on 495: 35 sup / 35 ref / 425 ins) |
| 46 | media | claim |  | After {v}, {A} comes before {B} more often than {C} comes before {D}. | unstated: reports with A before B vs reports with C before D | 'more often' -- count (k1 > k2) or rate | **AMBIGUOUS** | count vs rate: sign(k1-k2) != sign(k1/n1-k2/n2) on 2194/8571 instances (687 sup / 687 ref / 820 ins); arm denominators unstated (both-present reading differs on 495: 35 sup / 35 ref / 425 ins) |
| 47 | clinical | question |  | In {v} recipients, is the {A}-then-{B} order more frequent than the {C}-then-{D} order? | unstated | 'more frequent' -- count language | **AMBIGUOUS** | count vs rate: sign(k1-k2) != sign(k1/n1-k2/n2) on 2194/8571 instances (687 sup / 687 ref / 820 ins); arm denominators unstated (both-present reading differs on 495: 35 sup / 35 ref / 425 ins) |
| 48 | clinical | claim |  | In {v} recipients, the {A}-then-{B} order is more frequent than the {C}-then-{D} order. | unstated | 'more frequent' -- count language | **AMBIGUOUS** | count vs rate: sign(k1-k2) != sign(k1/n1-k2/n2) on 2194/8571 instances (687 sup / 687 ref / 820 ins); arm denominators unstated (both-present reading differs on 495: 35 sup / 35 ref / 425 ins) |

### P-M2 -- `multi_dir_precedes` (CHOICE, multi level; 8 strings; 87 instances)

**Code computes:** arm 1 = ordered (A,B) pairs in the v1 cohort, arm 2 = the same in the v2 cohort; Fisher exact p1 vs p2, both tails; floor 10 each.  
**Classes:** 8 AMBIGUOUS.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 49 | original | question |  | After which vaccine, {v1} or {v2}, does {A} more often precede {B}? | v1 vs v2 cohorts; per-cohort base unstated | 'more often precede' -- count or rate | **AMBIGUOUS** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; 'more often'/'more common' across two cohorts of unequal size (Pfizer 1,019 / Moderna 983 / Janssen 1,164): count order differs from the code's rate order on 8/87 (2 sup / 2 ref / 4 ins) |
| 50 | original | claim |  | {A} precedes {B} more often after {v1} than after {v2}. | v1 vs v2 cohorts; base unstated | 'more often' -- count or rate | **AMBIGUOUS** | 'more often'/'more common' across two cohorts of unequal size (Pfizer 1,019 / Moderna 983 / Janssen 1,164): count order differs from the code's rate order on 8/87 (2 sup / 2 ref / 4 ins) |
| 51 | research | question |  | Between {v1} and {v2}, which cohort shows a higher {A}-preceding-{B} proportion? | v1 vs v2 cohorts; proportion of what is unstated | proportion comparison | **AMBIGUOUS** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; 'proportion' settles count-vs-rate, but 'which cohort shows a higher ... proportion' reads as a proportion OF THE COHORT: that reading differs on 8/87 (2 sup / 2 ref / 4 ins); the both-present reading on 4 (all insufficient); weak |
| 52 | research | claim |  | {v1} shows a higher {A}-precedes-{B} proportion than {v2}. | v1 vs v2 cohorts; proportion of what is unstated | proportion comparison | **AMBIGUOUS** | 'proportion' settles count-vs-rate, but 'which cohort shows a higher ... proportion' reads as a proportion OF THE COHORT: that reading differs on 8/87 (2 sup / 2 ref / 4 ins); the both-present reading on 4 (all insufficient); weak |
| 53 | media | question |  | Is {A}-before-{B} more common after {v1} or {v2}? | v1 vs v2 cohorts; base unstated | 'more common after v1 or v2' -- count or rate | **AMBIGUOUS** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; 'more often'/'more common' across two cohorts of unequal size (Pfizer 1,019 / Moderna 983 / Janssen 1,164): count order differs from the code's rate order on 8/87 (2 sup / 2 ref / 4 ins) |
| 54 | media | claim |  | {A}-before-{B} is more common after {v1} than {v2}. | v1 vs v2 cohorts; base unstated | 'more common' -- count or rate | **AMBIGUOUS** | 'more often'/'more common' across two cohorts of unequal size (Pfizer 1,019 / Moderna 983 / Janssen 1,164): count order differs from the code's rate order on 8/87 (2 sup / 2 ref / 4 ins) |
| 55 | clinical | question |  | In which group is {A} more often the precursor to {B}, {v1} or {v2} recipients? | v1 vs v2 recipients; base unstated | 'more often the precursor' -- count or rate | **AMBIGUOUS** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; 'more often'/'more common' across two cohorts of unequal size (Pfizer 1,019 / Moderna 983 / Janssen 1,164): count order differs from the code's rate order on 8/87 (2 sup / 2 ref / 4 ins) |
| 56 | clinical | claim |  | {v1} recipients more often have {A} as a precursor to {B}. | v1 vs v2 recipients; base unstated | 'more often' -- count or rate | **AMBIGUOUS** | 'more often'/'more common' across two cohorts of unequal size (Pfizer 1,019 / Moderna 983 / Janssen 1,164): count order differs from the code's rate order on 8/87 (2 sup / 2 ref / 4 ins) |

### C-R1 -- `rep_sym_bool` (BOOL, report level; 8 strings; 300 instances)

**Code computes:** single report, no test: same stage -> supported, before/after -> refuted.  
**Classes:** 6 FAITHFUL, 2 AMBIGUOUS.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 57 | original | question |  | Do {A} and {B} co-occur in report {r}? | this report | A and B at the same stage (single observation) | **FAITHFUL** | 'co-occur' is the benchmark's own term for same-stage; exact |
| 58 | original | claim |  | In report {r}, {A} and {B} co-occur. | this report | A and B at the same stage (single observation) | **FAITHFUL** | 'co-occur' is the benchmark's own term for same-stage; exact |
| 59 | research | question |  | In this report, are {A} and {B} concurrent? | this report | same stage | **FAITHFUL** | 'concurrent' = same stage; exact |
| 60 | research | claim |  | In this report, {A} and {B} are concurrent. | this report | same stage | **FAITHFUL** | 'concurrent' = same stage; exact |
| 61 | media | question |  | In this case, did {A} and {B} happen at the same time? | this report | same stage | **FAITHFUL** | 'at the same time' = same stage; exact |
| 62 | media | claim |  | In this case, {A} and {B} happened at the same time. | this report | same stage | **FAITHFUL** | 'at the same time' = same stage; exact |
| 63 | clinical | question |  | Did this patient have {A} and {B} together? | this patient | 'have A and B together' -- co-present in the patient, or concurrent | **AMBIGUOUS** | lexical: co-presence is always true of a posed pair, so that reading answers yes on all 300 instances while gold refutes 119; 'concurrent' would pin it |
| 64 | clinical | claim |  | This patient had {A} and {B} together. | this patient | 'have A and B together' -- co-present in the patient, or concurrent | **AMBIGUOUS** | lexical: co-presence is always true of a posed pair, so that reading answers yes on all 300 instances while gold refutes 119; 'concurrent' would pin it |

### C-V1 -- `sym_bool_cooccurs` (BOOL, vaccine level; 16 strings; 756 instances)

**Code computes:** n = cohort reports with both present; k = same stage; exact binomial k/n vs 0.5, both tails; floor 10.  
**Classes:** 7 FAITHFUL, 9 NOTE.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 65 | original | question |  | Do {A} and {B} typically co-occur after {v}? | {v} reports with both (forced: a report lacking one cannot 'co-occur') | co-exist share > 0.5; negated: < 0.5 | **FAITHFUL** | exact; the negated forms negate the same proposition (the exact tie at 0.5 is never labelled decisively) |
| 66 | original | claim |  | After {v}, {A} and {B} typically co-occur. | {v} reports with both (forced: a report lacking one cannot 'co-occur') | co-exist share > 0.5; negated: < 0.5 | **FAITHFUL** | exact; the negated forms negate the same proposition (the exact tie at 0.5 is never labelled decisively) |
| 67 | original | question | yes | Is it the case that {A} and {B} do NOT typically co-occur after {v}? | {v} reports with both (forced: a report lacking one cannot 'co-occur') | co-exist share > 0.5; negated: < 0.5 | **FAITHFUL** | exact; the negated forms negate the same proposition (the exact tie at 0.5 is never labelled decisively) |
| 68 | original | claim | yes | After {v}, {A} and {B} do not typically co-occur. | {v} reports with both (forced: a report lacking one cannot 'co-occur') | co-exist share > 0.5; negated: < 0.5 | **FAITHFUL** | exact; the negated forms negate the same proposition (the exact tie at 0.5 is never labelled decisively) |
| 69 | research | question |  | In {v} reports, are {A} and {B} concurrent in the majority of cases? | {v} reports ... cases with both (forced) | share > 0.5 ('majority of cases') | **FAITHFUL** | exact |
| 70 | research | claim |  | In {v} reports, {A} and {B} are concurrent in the majority of cases. | {v} reports ... cases with both (forced) | share > 0.5 ('majority of cases') | **FAITHFUL** | exact |
| 71 | research | question | yes | In {v} reports, are {A} and {B} concurrent in a minority of cases? | {v} reports ... cases with both (forced) | share < 0.5 ('a minority of cases') | **NOTE** | 'in a minority of cases' (< 0.5) vs the claim_negated's 'NOT ... in the majority' (<= 0.5): they differ only at the exact tie, which the test never labels decisively; same labels |
| 72 | research | claim | yes | In {v} reports, {A} and {B} are NOT concurrent in the majority of cases. | {v} reports ... cases with both (forced) | share <= 0.5 | **FAITHFUL** | exact one-sided negation |
| 73 | media | question |  | After {v}, do {A} and {B} usually show up together? | {v} reports with both, implicit; 'show up together' not anchored to a stage | share > 0.5 (negated: < 0.5) | **NOTE** | lexical: 'together' can mean the same report rather than the same stage; the co-presence reading has no well-formed denominator here, so no label changes; contrast matches |
| 74 | media | claim |  | After {v}, {A} and {B} usually show up together. | {v} reports with both, implicit; 'show up together' not anchored to a stage | share > 0.5 (negated: < 0.5) | **NOTE** | lexical: 'together' can mean the same report rather than the same stage; the co-presence reading has no well-formed denominator here, so no label changes; contrast matches |
| 75 | media | question | yes | After {v}, is it true that {A} and {B} usually do NOT show up together? | {v} reports with both, implicit; 'show up together' not anchored to a stage | share > 0.5 (negated: < 0.5) | **NOTE** | lexical: 'together' can mean the same report rather than the same stage; the co-presence reading has no well-formed denominator here, so no label changes; contrast matches |
| 76 | media | claim | yes | After {v}, {A} and {B} usually do not show up together. | {v} reports with both, implicit; 'show up together' not anchored to a stage | share > 0.5 (negated: < 0.5) | **NOTE** | lexical: 'together' can mean the same report rather than the same stage; the co-presence reading has no well-formed denominator here, so no label changes; contrast matches |
| 77 | clinical | question |  | In {v} recipients, do {A} and {B} typically present together? | {v} recipients with both, implicit | 'typically present together' > 0.5 (negated: not) | **NOTE** | 'present together' is concurrent in clinical usage, but 'together' is not anchored to a stage; contrast matches |
| 78 | clinical | claim |  | In {v} recipients, {A} and {B} typically present together. | {v} recipients with both, implicit | 'typically present together' > 0.5 (negated: not) | **NOTE** | 'present together' is concurrent in clinical usage, but 'together' is not anchored to a stage; contrast matches |
| 79 | clinical | question | yes | In {v} recipients, is it the case that {A} and {B} do NOT typically present together? | {v} recipients with both, implicit | 'typically present together' > 0.5 (negated: not) | **NOTE** | 'present together' is concurrent in clinical usage, but 'together' is not anchored to a stage; contrast matches |
| 80 | clinical | claim | yes | In {v} recipients, {A} and {B} do not typically present together. | {v} recipients with both, implicit | 'typically present together' > 0.5 (negated: not) | **NOTE** | 'present together' is concurrent in clinical usage, but 'together' is not anchored to a stage; contrast matches |

### C-V2 -- `assoc_bool` (BOOL, vaccine level; 16 strings; 1,047 instances)

**Code computes:** arm 1 = reports containing A (k1 = also B); arm 2 = reports NOT containing A (k2 = B); whole cohort; Fisher exact P(B|A) vs P(B|not A), both tails.  
**Classes:** 6 FAITHFUL, 5 NOTE, 4 AMBIGUOUS, 1 MISMATCH.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 81 | original | question |  | After {v}, do {A} and {B} occur together more often than their separate rates would predict? | the whole {v} cohort (presence x presence) | P(A and B) > P(A)P(B), which has the same sign as P(B\|A) > P(B\|not A); negated: not more | **NOTE** | contrast equivalent to the Fisher 2x2 and 'rates' resolves count-vs-rate; lexical drift: 'occur together' means the same REPORT here but the same STAGE in C-V1 / C-R1 |
| 82 | original | claim |  | After {v}, {A} and {B} occur together more often than their separate rates would predict. | the whole {v} cohort (presence x presence) | P(A and B) > P(A)P(B), which has the same sign as P(B\|A) > P(B\|not A); negated: not more | **NOTE** | contrast equivalent to the Fisher 2x2 and 'rates' resolves count-vs-rate; lexical drift: 'occur together' means the same REPORT here but the same STAGE in C-V1 / C-R1 |
| 83 | original | question | yes | After {v}, is it the case that {A} and {B} do NOT occur together more often than their separate rates would predict? | the whole {v} cohort (presence x presence) | P(A and B) > P(A)P(B), which has the same sign as P(B\|A) > P(B\|not A); negated: not more | **NOTE** | contrast equivalent to the Fisher 2x2 and 'rates' resolves count-vs-rate; lexical drift: 'occur together' means the same REPORT here but the same STAGE in C-V1 / C-R1 |
| 84 | original | claim | yes | After {v}, {A} and {B} do not occur together more often than their separate rates would predict. | the whole {v} cohort (presence x presence) | P(A and B) > P(A)P(B), which has the same sign as P(B\|A) > P(B\|not A); negated: not more | **NOTE** | contrast equivalent to the Fisher 2x2 and 'rates' resolves count-vs-rate; lexical drift: 'occur together' means the same REPORT here but the same STAGE in C-V1 / C-R1 |
| 85 | research | question |  | Among {v} reports, is {B} more prevalent in reports containing {A} than in reports without it? | reports containing A vs reports without A -- explicit | P(B\|A) > P(B\|not A) ('more prevalent'); negated: 'no more prevalent' = <= | **FAITHFUL** | both arms named; prevalence is a rate; exact |
| 86 | research | claim |  | Among {v} reports, {B} is more prevalent in reports containing {A} than in reports without it. | reports containing A vs reports without A -- explicit | P(B\|A) > P(B\|not A) ('more prevalent'); negated: 'no more prevalent' = <= | **FAITHFUL** | both arms named; prevalence is a rate; exact |
| 87 | research | question | yes | Among {v} reports, is {B} no more prevalent in reports containing {A} than in reports without it? | reports containing A vs reports without A -- explicit | P(B\|A) > P(B\|not A) ('more prevalent'); negated: 'no more prevalent' = <= | **FAITHFUL** | both arms named; prevalence is a rate; exact |
| 88 | research | claim | yes | Among {v} reports, {B} is not more prevalent in reports containing {A} than in reports without it. | reports containing A vs reports without A -- explicit | P(B\|A) > P(B\|not A) ('more prevalent'); negated: 'no more prevalent' = <= | **FAITHFUL** | both arms named; prevalence is a rate; exact |
| 89 | media | question |  | After {v}, do people who report {A} also report {B} more often than everyone else does? | people who report A vs 'everyone else' -- explicit arms | 'more often' -- per-capita rate (ordinary reading) or count | **AMBIGUOUS** | weak: 'X do Y more often than Z do' is per-capita in ordinary usage, but the rubric's count reading (\|A and B\| vs \|B without A\|) differs from the code on 467/1047 (183 sup / 183 ref / 101 ins) |
| 90 | media | claim |  | After {v}, people who report {A} also report {B} more often than everyone else does. | people who report A vs 'everyone else' -- explicit arms | 'more often' -- per-capita rate (ordinary reading) or count | **AMBIGUOUS** | weak: 'X do Y more often than Z do' is per-capita in ordinary usage, but the rubric's count reading (\|A and B\| vs \|B without A\|) differs from the code on 467/1047 (183 sup / 183 ref / 101 ins) |
| 91 | media | question | yes | After {v}, do people who report {A} report {B} no more often than everyone else does? | people who report A vs 'everyone else' -- explicit arms | 'more often' -- per-capita rate (ordinary reading) or count | **AMBIGUOUS** | weak: 'X do Y more often than Z do' is per-capita in ordinary usage, but the rubric's count reading (\|A and B\| vs \|B without A\|) differs from the code on 467/1047 (183 sup / 183 ref / 101 ins) |
| 92 | media | claim | yes | After {v}, people who report {A} do not report {B} more often than everyone else does. | people who report A vs 'everyone else' -- explicit arms | 'more often' -- per-capita rate (ordinary reading) or count | **AMBIGUOUS** | weak: 'X do Y more often than Z do' is per-capita in ordinary usage, but the rubric's count reading (\|A and B\| vs \|B without A\|) differs from the code on 467/1047 (183 sup / 183 ref / 101 ins) |
| 93 | clinical | question |  | In {v} recipients, is {A} associated with {B} beyond what their individual frequencies imply? | the whole {v} cohort | 'associated beyond what their frequencies imply' = positive excess over independence | **FAITHFUL** | exact |
| 94 | clinical | claim |  | In {v} recipients, {A} is associated with {B} beyond what their individual frequencies imply. | the whole {v} cohort | 'associated beyond what their frequencies imply' = positive excess over independence | **FAITHFUL** | exact |
| 95 | clinical | question | yes | In {v} recipients, is {A} unassociated with {B} once their individual frequencies are accounted for? | the whole {v} cohort | 'unassociated once frequencies are accounted for' = INDEPENDENCE (two-sided point null) | **MISMATCH** | the code's negated claim is 'not positively associated' and is SUPPORTED by significant NEGATIVE association; on the 145 negated instances labelled supported the literal answer to 'is A unassociated with B?' is No (they are associated, negatively); a point null can never be supported under the benchmark's own three-decision rule |
| 96 | clinical | claim | yes | In {v} recipients, {A} is not associated with {B} beyond what their individual frequencies imply. | the whole {v} cohort | 'not associated ... beyond what their individual frequencies imply' = not a positive excess | **NOTE** | the qualifier makes it one-sided (matches), but 'not associated' invites the independence misreading that the question form commits |

### C-V3 -- `cooc_modal_bool` (BOOL, vaccine level; 16 strings; 522 instances)

**Code computes:** cells {before, after, co_exist} over reports with both present (n = their sum); named cell co_exist vs max(before, after); exact binomial on the 2-cell table vs 0.5; floor 10 on n.  
**Classes:** 8 FAITHFUL, 8 UNDERDETERMINED-INPUT.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 97 | original | question |  | After {v}, is co-occurrence the dominant relation for {A} and {B}? | {v} reports with both (every such report is one of the three cells) | co_exist is the argmax of {before, after, co_exist}; negated: it is not | **FAITHFUL** | 'dominant relation' = argmax over the three relation cells, named cell co_exist; the negation negates exactly that; exact |
| 98 | original | claim |  | After {v}, co-occurrence is the dominant relation for {A} and {B}. | {v} reports with both (every such report is one of the three cells) | co_exist is the argmax of {before, after, co_exist}; negated: it is not | **FAITHFUL** | 'dominant relation' = argmax over the three relation cells, named cell co_exist; the negation negates exactly that; exact |
| 99 | original | question | yes | After {v}, is co-occurrence NOT the dominant relation for {A} and {B}? | {v} reports with both (every such report is one of the three cells) | co_exist is the argmax of {before, after, co_exist}; negated: it is not | **FAITHFUL** | 'dominant relation' = argmax over the three relation cells, named cell co_exist; the negation negates exactly that; exact |
| 100 | original | claim | yes | After {v}, co-occurrence is not the dominant relation for {A} and {B}. | {v} reports with both (every such report is one of the three cells) | co_exist is the argmax of {before, after, co_exist}; negated: it is not | **FAITHFUL** | 'dominant relation' = argmax over the three relation cells, named cell co_exist; the negation negates exactly that; exact |
| 101 | research | question |  | Among {v} reports with both events, is concurrent presentation the most common relation? | {v} reports / recipients with both -- explicit | concurrent presentation is the most common relation (argmax); negated: it is not | **UNDERDETERMINED-INPUT** | omits {A} and {B}: the input does not determine the claim (harness token `underdetermined`; 522 instances x 1 record per string); wording otherwise faithful ('most common relation' among reports with both = argmax) |
| 102 | research | claim |  | Among {v} reports with both events, concurrent presentation is the most common relation. | {v} reports / recipients with both -- explicit | concurrent presentation is the most common relation (argmax); negated: it is not | **UNDERDETERMINED-INPUT** | omits {A} and {B}: the input does not determine the claim (harness token `underdetermined`; 522 instances x 1 record per string); wording otherwise faithful ('most common relation' among reports with both = argmax) |
| 103 | research | question | yes | Among {v} reports with both events, is concurrent presentation NOT the most common relation? | {v} reports / recipients with both -- explicit | concurrent presentation is the most common relation (argmax); negated: it is not | **UNDERDETERMINED-INPUT** | omits {A} and {B}: the input does not determine the claim (harness token `underdetermined`; 522 instances x 1 record per string); wording otherwise faithful ('most common relation' among reports with both = argmax) |
| 104 | research | claim | yes | Among {v} reports with both events, concurrent presentation is not the most common relation. | {v} reports / recipients with both -- explicit | concurrent presentation is the most common relation (argmax); negated: it is not | **UNDERDETERMINED-INPUT** | omits {A} and {B}: the input does not determine the claim (harness token `underdetermined`; 522 instances x 1 record per string); wording otherwise faithful ('most common relation' among reports with both = argmax) |
| 105 | media | question |  | After {v}, do {A} and {B} show up together more often than in either order? | {v} reports with both, implicit (irrelevant to an argmax over the cells) | co_exist > before AND co_exist > after (= co_exist > max); negated: co_exist <= max | **FAITHFUL** | 'together more often than in either order' is the argmax with named cell co_exist, and 'in either order' anchors 'together' to the same stage; exact |
| 106 | media | claim |  | After {v}, {A} and {B} show up together more often than in either order. | {v} reports with both, implicit (irrelevant to an argmax over the cells) | co_exist > before AND co_exist > after (= co_exist > max); negated: co_exist <= max | **FAITHFUL** | 'together more often than in either order' is the argmax with named cell co_exist, and 'in either order' anchors 'together' to the same stage; exact |
| 107 | media | question | yes | After {v}, is it the case that {A} and {B} do NOT show up together more often than in either order? | {v} reports with both, implicit (irrelevant to an argmax over the cells) | co_exist > before AND co_exist > after (= co_exist > max); negated: co_exist <= max | **FAITHFUL** | 'together more often than in either order' is the argmax with named cell co_exist, and 'in either order' anchors 'together' to the same stage; exact |
| 108 | media | claim | yes | After {v}, {A} and {B} do not show up together more often than in either order. | {v} reports with both, implicit (irrelevant to an argmax over the cells) | co_exist > before AND co_exist > after (= co_exist > max); negated: co_exist <= max | **FAITHFUL** | 'together more often than in either order' is the argmax with named cell co_exist, and 'in either order' anchors 'together' to the same stage; exact |
| 109 | clinical | question |  | In {v} recipients with both, is concurrence the most common presentation? | {v} reports / recipients with both -- explicit | concurrent presentation is the most common relation (argmax); negated: it is not | **UNDERDETERMINED-INPUT** | omits {A} and {B}: the input does not determine the claim (harness token `underdetermined`; 522 instances x 1 record per string); wording otherwise faithful ('most common relation' among reports with both = argmax) |
| 110 | clinical | claim |  | In {v} recipients with both, concurrence is the most common presentation. | {v} reports / recipients with both -- explicit | concurrent presentation is the most common relation (argmax); negated: it is not | **UNDERDETERMINED-INPUT** | omits {A} and {B}: the input does not determine the claim (harness token `underdetermined`; 522 instances x 1 record per string); wording otherwise faithful ('most common relation' among reports with both = argmax) |
| 111 | clinical | question | yes | In {v} recipients with both, is concurrence NOT the most common presentation? | {v} reports / recipients with both -- explicit | concurrent presentation is the most common relation (argmax); negated: it is not | **UNDERDETERMINED-INPUT** | omits {A} and {B}: the input does not determine the claim (harness token `underdetermined`; 522 instances x 1 record per string); wording otherwise faithful ('most common relation' among reports with both = argmax) |
| 112 | clinical | claim | yes | In {v} recipients with both, concurrence is not the most common presentation. | {v} reports / recipients with both -- explicit | concurrent presentation is the most common relation (argmax); negated: it is not | **UNDERDETERMINED-INPUT** | omits {A} and {B}: the input does not determine the claim (harness token `underdetermined`; 522 instances x 1 record per string); wording otherwise faithful ('most common relation' among reports with both = argmax) |

### S-R1 -- `rep_seq_bool` (BOOL, report level; 8 strings; 600 instances)

**Code computes:** single report, no test: strict stage(A) < stage(B) < stage(C); intervening events allowed; only fully ordered triples are posed.  
**Classes:** 8 FAITHFUL.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 113 | original | question |  | Do {A}, {B}, {C} occur in the order {A} → {B} → {C} in report {r}? | this report | A, then B, then C at strictly increasing stages (single observation) | **FAITHFUL** | strict per-report order; only fully ordered triples are posed; exact |
| 114 | original | claim |  | In report {r}, {A}, {B}, {C} occur in the order {A} → {B} → {C}. | this report | A, then B, then C at strictly increasing stages (single observation) | **FAITHFUL** | strict per-report order; only fully ordered triples are posed; exact |
| 115 | research | question |  | In this report, is the observed ordering of {A}, {B}, {C} exactly {A} → {B} → {C}? | this report | 'exactly A -> B -> C' = this permutation, no ties | **FAITHFUL** | 'exactly' = this permutation and no ties; intervening events are allowed because the ordering is of A, B, C relative to each other; exact |
| 116 | research | claim |  | In this report, the observed ordering is {A} → {B} → {C}. | this report | 'exactly A -> B -> C' = this permutation, no ties | **FAITHFUL** | 'exactly' = this permutation and no ties; intervening events are allowed because the ordering is of A, B, C relative to each other; exact |
| 117 | media | question |  | In this case, did things go {A}, then {B}, then {C}? | this report | A, then B, then C at strictly increasing stages (single observation) | **FAITHFUL** | strict per-report order; only fully ordered triples are posed; exact |
| 118 | media | claim |  | In this case, the progression was {A}, then {B}, then {C}. | this report | A, then B, then C at strictly increasing stages (single observation) | **FAITHFUL** | strict per-report order; only fully ordered triples are posed; exact |
| 119 | clinical | question |  | Did this patient progress {A}, then {B}, then {C}? | this report | A, then B, then C at strictly increasing stages (single observation) | **FAITHFUL** | strict per-report order; only fully ordered triples are posed; exact |
| 120 | clinical | claim |  | This patient progressed {A} → {B} → {C}. | this report | A, then B, then C at strictly increasing stages (single observation) | **FAITHFUL** | strict per-report order; only fully ordered triples are posed; exact |

### S-V1 -- `seq_bool` (BOOL, vaccine level; 8 strings; 6 instances)

**Code computes:** cells = the strict orderings observed over reports with all three at pairwise-distinct stages (tie patterns excluded from n and from the cells); named ordering vs runner-up; exact binomial vs 0.5; floor 5.  
**Classes:** 8 NOTE.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 121 | original | question |  | After {v}, is {A} → {B} → {C} the most common ordering of {A}, {B}, {C}? | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | A -> B -> C is the most common (research: single most frequent = unique) strict ordering (argmax) | **NOTE** | argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 122 | original | claim |  | After {v}, {A} → {B} → {C} is the most common ordering of {A}, {B}, {C}. | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | A -> B -> C is the most common (research: single most frequent = unique) strict ordering (argmax) | **NOTE** | argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 123 | research | question |  | In {v} reports with all three events, is {A} → {B} → {C} the single most frequent ordering? | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | A -> B -> C is the most common (research: single most frequent = unique) strict ordering (argmax) | **NOTE** | argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 124 | research | claim |  | In {v} reports with all three, {A} → {B} → {C} is the single most frequent ordering. | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | A -> B -> C is the most common (research: single most frequent = unique) strict ordering (argmax) | **NOTE** | argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 125 | media | question |  | After {v}, is {A}, then {B}, then {C} the most common order? | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | A -> B -> C is the most common (research: single most frequent = unique) strict ordering (argmax) | **NOTE** | argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 126 | media | claim |  | After {v}, {A}, then {B}, then {C} is the most common order. | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | A -> B -> C is the most common (research: single most frequent = unique) strict ordering (argmax) | **NOTE** | argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 127 | clinical | question |  | In {v} recipients with all three, is {A} → {B} → {C} the most frequent progression? | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | A -> B -> C is the most common (research: single most frequent = unique) strict ordering (argmax) | **NOTE** | argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 128 | clinical | claim |  | In {v} recipients with all three, {A} → {B} → {C} is the most frequent progression. | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | A -> B -> C is the most common (research: single most frequent = unique) strict ordering (argmax) | **NOTE** | argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |

### S-V3 -- `modal_choice` (CHOICE, vaccine level; 8 strings; 6 instances)

**Code computes:** same statistic as seq_bool; the CHOICE answer is the modal ordering.  
**Classes:** 8 NOTE.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 129 | original | question |  | After {v}, what is the most common ordering of {A}, {B}, {C}? | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | which ordering is modal (argmax) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 130 | original | claim |  | After {v}, the most common ordering of {A}, {B}, {C} is {A} → {B} → {C}. | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | the named ordering is the modal / most common ordering (argmax) | **NOTE** | argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 131 | research | question |  | Among {v} reports with all three events, what is the modal ordering of {A}, {B}, {C}? | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | which ordering is modal (argmax) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 132 | research | claim |  | Among {v} reports with all three, the modal ordering is {A} → {B} → {C}. | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | the named ordering is the modal / most common ordering (argmax) | **NOTE** | argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 133 | media | question |  | After {v}, what's the most common order people experience {A}, {B}, and {C}? | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | which ordering is modal (argmax) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 134 | media | claim |  | After {v}, the most common order is {A} → {B} → {C}. | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | the named ordering is the modal / most common ordering (argmax) | **NOTE** | argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 135 | clinical | question |  | What's the most common progression of {A}, {B}, {C} in {v} patients? | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | which ordering is modal (argmax) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |
| 136 | clinical | claim |  | The most common progression in {v} patients is {A} → {B} → {C}. | {v} reports with all three -- research/clinical say so explicitly, but the code also requires pairwise-DISTINCT stages (tie patterns excluded), which no register states | the named ordering is the modal / most common ordering (argmax) | **NOTE** | argmax over strict orderings matches modal-vs-runner-up; tie-pattern reports are neither a cell nor in n and outnumber orderable reports in every shipped instance (ties:orderable = 11:5, 14:8, 2:0, 11:3); a tie pattern is not an 'ordering' under the family's stated definition (sequence.yaml notes), so no label changes |

### F-R1 -- `rep_first_choice` (CHOICE, report level; 8 strings; 600 instances)

**Code computes:** single report, no test: the unique earliest of the three (only tie-free triples are posed).  
**Classes:** 6 FAITHFUL, 2 NOTE.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 137 | original | question |  | In report {r}, which of {A}, {B}, {C} occurs first? | this report | which of A, B, C is earliest (single observation) | **FAITHFUL** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; only tie-free triples are posed |
| 138 | original | claim |  | In report {r}, {A} occurs first among {A}, {B}, {C}. | this report | A is earliest among A, B, C | **FAITHFUL** | names the candidate set; exact |
| 139 | research | question |  | Of {A}, {B}, {C}, which is the earliest event in this report? | this report | which of A, B, C is earliest (single observation) | **FAITHFUL** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; only tie-free triples are posed |
| 140 | research | claim |  | In this report, {A} is the earliest of {A}, {B}, {C}. | this report | A is the earliest of A, B, C | **FAITHFUL** | names the candidate set; exact |
| 141 | media | question |  | In this case, which came first, {A}, {B}, or {C}? | this report | which of A, B, C is earliest (single observation) | **FAITHFUL** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; only tie-free triples are posed |
| 142 | media | claim |  | In this case, {A} came first. | this report | A is earliest among the options | **NOTE** | omits B and C; the candidate set is supplied by the input `options` field |
| 143 | clinical | question |  | Of {A}, {B}, {C}, which appeared first in this patient? | this report | which of A, B, C is earliest (single observation) | **FAITHFUL** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; only tie-free triples are posed |
| 144 | clinical | claim |  | In this patient, {A} appeared first. | this report | A is earliest among the options | **NOTE** | omits B and C; the candidate set is supplied by the input `options` field |

### F-R2 -- `rep_last_choice` (CHOICE, report level; 8 strings; 600 instances)

**Code computes:** single report, no test: the unique latest of the three (only tie-free triples are posed).  
**Classes:** 6 FAITHFUL, 2 NOTE.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 145 | original | question |  | In report {r}, which of {A}, {B}, {C} occurs last? | this report | which of A, B, C is latest (single observation) | **FAITHFUL** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; only tie-free triples are posed |
| 146 | original | claim |  | In report {r}, {A} occurs last among {A}, {B}, {C}. | this report | A is latest among A, B, C | **FAITHFUL** | names the candidate set; exact |
| 147 | research | question |  | Of {A}, {B}, {C}, which is the latest event in this report? | this report | which of A, B, C is latest (single observation) | **FAITHFUL** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; only tie-free triples are posed |
| 148 | research | claim |  | In this report, {A} is the latest of {A}, {B}, {C}. | this report | A is the latest of A, B, C | **FAITHFUL** | names the candidate set; exact |
| 149 | media | question |  | In this case, which came last, {A}, {B}, or {C}? | this report | which of A, B, C is latest (single observation) | **FAITHFUL** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; only tie-free triples are posed |
| 150 | media | claim |  | In this case, {A} came last. | this report | A is latest among the options | **NOTE** | omits B and C; the candidate set is supplied by the input `options` field |
| 151 | clinical | question |  | Of {A}, {B}, {C}, which appeared last in this patient? | this report | which of A, B, C is latest (single observation) | **FAITHFUL** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; only tie-free triples are posed |
| 152 | clinical | claim |  | In this patient, {A} appeared last. | this report | A is latest among the options | **NOTE** | omits B and C; the candidate set is supplied by the input `options` field |

### F-R3 -- `rep_first_bool` (BOOL, report level; 8 strings; 600 instances)

**Code computes:** single report, no test: is slot A the unique earliest of the three.  
**Classes:** 8 FAITHFUL.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 153 | original | question |  | In report {r}, is {A} the first of {A}, {B}, {C} to occur? | this report | A is the unique earliest of A, B, C (single observation) | **FAITHFUL** | names the candidate set; only tie-free triples are posed; exact |
| 154 | original | claim |  | In report {r}, {A} is the first of {A}, {B}, {C} to occur. | this report | A is the unique earliest of A, B, C (single observation) | **FAITHFUL** | names the candidate set; only tie-free triples are posed; exact |
| 155 | research | question |  | In this report, is {A} the earliest of {A}, {B}, {C}? | this report | A is the unique earliest of A, B, C (single observation) | **FAITHFUL** | names the candidate set; only tie-free triples are posed; exact |
| 156 | research | claim |  | In this report, {A} is the earliest of {A}, {B}, {C}. | this report | A is the unique earliest of A, B, C (single observation) | **FAITHFUL** | names the candidate set; only tie-free triples are posed; exact |
| 157 | media | question |  | In this case, did {A} come first among {A}, {B}, {C}? | this report | A is the unique earliest of A, B, C (single observation) | **FAITHFUL** | names the candidate set; only tie-free triples are posed; exact |
| 158 | media | claim |  | In this case, {A} came first among {A}, {B}, {C}. | this report | A is the unique earliest of A, B, C (single observation) | **FAITHFUL** | names the candidate set; only tie-free triples are posed; exact |
| 159 | clinical | question |  | Did {A} appear first among {A}, {B}, {C} in this patient? | this report | A is the unique earliest of A, B, C (single observation) | **FAITHFUL** | names the candidate set; only tie-free triples are posed; exact |
| 160 | clinical | claim |  | In this patient, {A} appeared first among {A}, {B}, {C}. | this report | A is the unique earliest of A, B, C (single observation) | **FAITHFUL** | names the candidate set; only tie-free triples are posed; exact |

### F-V1 -- `first_choice` (CHOICE, vaccine level; 8 strings; 102 instances)

**Code computes:** cells = the unique-earliest candidate over reports with all three present and no tie for first (ties excluded); named vs runner-up; exact binomial vs 0.5; floor 10.  
**Classes:** 5 NOTE, 3 AMBIGUOUS.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 161 | original | question |  | After {v}, which of {A}, {B}, {C} is most commonly the first event? | {v} reports with all three and a unique first event (ties implicit) | which candidate is most commonly the first event (argmax) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; ties for first leave the denominator -- not stated; crediting a tie to every tied candidate changes 0/102 labels |
| 162 | original | claim |  | After {v}, {A} is most commonly the first event among {A}, {B}, {C}. | {v} reports with all three and a unique first event (ties implicit) | A is most commonly the first event among A, B, C (argmax, anchored by 'among') | **NOTE** | ties for first leave the denominator -- not stated; crediting a tie to every tied candidate changes 0/102 labels |
| 163 | research | question |  | In {v} reports with all three, which event is most frequently the earliest among {A}, {B}, {C}? | '{v} reports with all three' -- stated, but tie reports are dropped | which event is most frequently the earliest among A, B, C (argmax) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; ties for first leave the denominator -- not stated; crediting a tie to every tied candidate changes 0/102 labels |
| 164 | research | claim |  | In {v} reports with all three, {A} is most frequently the earliest. | '{v} reports with all three' -- stated, but tie reports are dropped | A is most frequently the earliest -- argmax or majority | **AMBIGUOUS** | weak: majority vs argmax ('most frequently the earliest' / 'first most often' without 'of the three' reads as > 0.5 as readily as argmax): the named share exceeds 0.5 in every supported instance (0 sign changes), but under the same binomial test vs 0.5 12/34 supported become insufficient; omits B and C (supplied by `options`) |
| 165 | media | question |  | After {v}, which comes first most often, {A}, {B}, or {C}? | {v} reports with all three (ties implicit) | which comes first most often (argmax) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; ties for first leave the denominator -- not stated; crediting a tie to every tied candidate changes 0/102 labels |
| 166 | media | claim |  | After {v}, {A} comes first most often. | {v} reports with all three (ties implicit) | A comes first most often -- argmax or majority | **AMBIGUOUS** | weak: majority vs argmax ('most frequently the earliest' / 'first most often' without 'of the three' reads as > 0.5 as readily as argmax): the named share exceeds 0.5 in every supported instance (0 sign changes), but under the same binomial test vs 0.5 12/34 supported become insufficient; omits B and C (supplied by `options`) |
| 167 | clinical | question |  | In {v} patients, which of {A}, {B}, {C} is most frequently the earliest? | {v} patients with all three (ties implicit) | which of A, B, C is most frequently the earliest (argmax) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; ties for first leave the denominator -- not stated; crediting a tie to every tied candidate changes 0/102 labels |
| 168 | clinical | claim |  | In {v} patients, {A} is most frequently the earliest. | {v} patients with all three (ties implicit) | A is most frequently the earliest -- argmax or majority | **AMBIGUOUS** | weak: majority vs argmax ('most frequently the earliest' / 'first most often' without 'of the three' reads as > 0.5 as readily as argmax): the named share exceeds 0.5 in every supported instance (0 sign changes), but under the same binomial test vs 0.5 12/34 supported become insufficient; omits B and C (supplied by `options`) |

### F-V2 -- `last_choice` (CHOICE, vaccine level; 8 strings; 138 instances)

**Code computes:** as first_choice with latest / no tie for last.  
**Classes:** 5 NOTE, 3 AMBIGUOUS.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 169 | original | question |  | After {v}, which of {A}, {B}, {C} is most commonly the last event? | {v} reports with all three and a unique last event (ties implicit) | which candidate is most commonly the last event (argmax) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; ties for last leave the denominator -- not stated; crediting a tie to every tied candidate changes 1/138 labels |
| 170 | original | claim |  | After {v}, {A} is most commonly the last event among {A}, {B}, {C}. | {v} reports with all three and a unique last event (ties implicit) | A is most commonly the last event among A, B, C (argmax, anchored by 'among') | **NOTE** | ties for last leave the denominator -- not stated; crediting a tie to every tied candidate changes 1/138 labels |
| 171 | research | question |  | In {v} reports with all three, which event is most frequently the latest among {A}, {B}, {C}? | '{v} reports with all three' -- stated, but tie reports are dropped | which event is most frequently the latest among A, B, C (argmax) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; ties for last leave the denominator -- not stated; crediting a tie to every tied candidate changes 1/138 labels |
| 172 | research | claim |  | In {v} reports with all three, {A} is most frequently the latest. | '{v} reports with all three' -- stated, but tie reports are dropped | A is most frequently the latest -- argmax or majority | **AMBIGUOUS** | weak: majority vs argmax ('most frequently the latest' / 'last most often' without 'of the three' reads as > 0.5 as readily as argmax): the named share exceeds 0.5 in every supported instance (0 sign changes), but under the same binomial test vs 0.5 22/46 supported become insufficient; omits B and C (supplied by `options`) |
| 173 | media | question |  | After {v}, which comes last most often, {A}, {B}, or {C}? | {v} reports with all three (ties implicit) | which comes last most often (argmax) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; ties for last leave the denominator -- not stated; crediting a tie to every tied candidate changes 1/138 labels |
| 174 | media | claim |  | After {v}, {A} comes last most often. | {v} reports with all three (ties implicit) | A comes last most often -- argmax or majority | **AMBIGUOUS** | weak: majority vs argmax ('most frequently the latest' / 'last most often' without 'of the three' reads as > 0.5 as readily as argmax): the named share exceeds 0.5 in every supported instance (0 sign changes), but under the same binomial test vs 0.5 22/46 supported become insufficient; omits B and C (supplied by `options`) |
| 175 | clinical | question |  | In {v} patients, which of {A}, {B}, {C} is most frequently the latest? | {v} patients with all three (ties implicit) | which of A, B, C is most frequently the latest (argmax) | **NOTE** | (c) neutral CHOICE question: asserts nothing; the asserted option is slot A of the paired claim and the question is scored on `gold_answer` over a seeded-shuffled `options` list; ties for last leave the denominator -- not stated; crediting a tie to every tied candidate changes 1/138 labels |
| 176 | clinical | claim |  | In {v} patients, {A} is most frequently the latest. | {v} patients with all three (ties implicit) | A is most frequently the latest -- argmax or majority | **AMBIGUOUS** | weak: majority vs argmax ('most frequently the latest' / 'last most often' without 'of the three' reads as > 0.5 as readily as argmax): the named share exceeds 0.5 in every supported instance (0 sign changes), but under the same binomial test vs 0.5 22/46 supported become insufficient; omits B and C (supplied by `options`) |

### F-V3 -- `first_bool` (BOOL, vaccine level; 8 strings; 102 instances)

**Code computes:** same statistic as first_choice with the named candidate fixed to slot A.  
**Classes:** 4 NOTE, 2 AMBIGUOUS, 2 UNDERDETERMINED-INPUT.

| # | register | format | neg | string | implied denominator | implied contrast | verdict | reason |
|--:|---|---|:-:|---|---|---|---|---|
| 177 | original | question |  | After {v}, is {A} the most common first event among {A}, {B}, {C}? | {v} reports with all three and a unique first (ties implicit) | A is the most common first event among A, B, C (argmax, anchored by 'among') | **NOTE** | ties for first leave the denominator -- not stated; the tie-inclusive reading changes 0/102 labels |
| 178 | original | claim |  | After {v}, {A} is the most common first event among {A}, {B}, {C}. | {v} reports with all three and a unique first (ties implicit) | A is the most common first event among A, B, C (argmax, anchored by 'among') | **NOTE** | ties for first leave the denominator -- not stated; the tie-inclusive reading changes 0/102 labels |
| 179 | research | question |  | In {v} reports with all three, is {A} the single most frequent earliest event? | '{v} reports with all three' -- stated | A is the single most frequent earliest event (unique argmax) | **UNDERDETERMINED-INPUT** | omits {B} and {C} (BOOL: no `options` field to recover them): the input does not determine the claim (102 instances x 1 record per string); wording otherwise faithful |
| 180 | research | claim |  | In {v} reports with all three, {A} is the single most frequent earliest event. | '{v} reports with all three' -- stated | A is the single most frequent earliest event (unique argmax) | **UNDERDETERMINED-INPUT** | omits {B} and {C} (BOOL: no `options` field to recover them): the input does not determine the claim (102 instances x 1 record per string); wording otherwise faithful |
| 181 | media | question |  | After {v}, is {A} most often the first among {A}, {B}, {C}? | {v} reports with all three (ties implicit) | 'A is most often the first among A, B, C' -- the candidate set attaches to 'the first', so 'most often' reads as a majority as readily as an argmax | **AMBIGUOUS** | weak: majority vs argmax (the issue-13 class): named share > 0.5 in every supported instance (0 sign changes), but under the same binomial test vs 0.5 12/34 supported become insufficient |
| 182 | media | claim |  | After {v}, {A} is most often the first among {A}, {B}, {C}. | {v} reports with all three (ties implicit) | 'A is most often the first among A, B, C' -- the candidate set attaches to 'the first', so 'most often' reads as a majority as readily as an argmax | **AMBIGUOUS** | weak: majority vs argmax (the issue-13 class): named share > 0.5 in every supported instance (0 sign changes), but under the same binomial test vs 0.5 12/34 supported become insufficient |
| 183 | clinical | question |  | In {v} patients, is {A} the most frequent earliest of {A}, {B}, {C}? | {v} patients with all three (ties implicit) | A is the most frequent earliest of A, B, C (argmax, anchored by 'of') | **NOTE** | ties for first leave the denominator -- not stated; the tie-inclusive reading changes 0/102 labels |
| 184 | clinical | claim |  | In {v} patients, {A} is the most frequent earliest of {A}, {B}, {C}. | {v} patients with all three (ties implicit) | A is the most frequent earliest of A, B, C (argmax, anchored by 'of') | **NOTE** | ties for first leave the denominator -- not stated; the tie-inclusive reading changes 0/102 labels |

