# Part C: Validation Sample (gold-label correctness guard)

For each entry: the claim as the instance asserts it, the reports behind it split into supports / against / excluded, and the test that produced the verdict. **Recompute the counts by eye before trusting Part A.**

`levels` are the leveled-order positions of the claim's events in that report -- lower index = earlier. Equal indices mean co-exist.

What to check, in order of what has actually gone wrong before:

1. **The exclusion rule.** Every report under `excluded` must genuinely fail the conditioning for the stated reason, and none of them may appear under supports/against. A precedes claim must NOT count co-exist pairs.
2. **The counts.** `len(supports) + len(against) = n`, and `len(supports) = k`. Flagged automatically as `counts match`.
3. **The direction.** Each report under `supports` must actually satisfy the claim as worded (including negation, if `negated` is true).
4. **The verdict.** `supported` needs p_claim < alpha; `refuted` needs p_opposite < alpha; otherwise `insufficient` with a sub-type.

## 1. P-V1 (dir_bool, BOOL) -- realized as supported
- claim: "After Pfizer, Headache typically occurs before Fatigue."
- events: ['Headache', 'Fatigue']   cohort: ['Pfizer']
- conditioning rule: precedes denom = reports with both, ordered; supported if frac>0.5
- excluded when: co-exist (same level) -- not ordered, so excluded from a PRECEDES denominator
- **n = 50, k = 35, proportion = 0.7**
- counts match: **OK** (denominator ids 50 vs n 50; numerator ids 35 vs k 35; 67 excluded)
- min-n floor for this family: 10
- test: binom_exact   p_claim = 0.0033   p_opposite = 0.998699   alpha = 0.05
- **gold verdict: supported**
- 95% CI: [0.5625, 0.809]
  - supports the claim (numerator):
      - 5341252  levels={'Headache': 1, 'Fatigue': 2}
      - 8882718  levels={'Headache': 0, 'Fatigue': 1}
      - 3443605  levels={'Headache': 0, 'Fatigue': 1}
      - 8803251  levels={'Headache': 0, 'Fatigue': 1}
      - 9454869  levels={'Headache': 0, 'Fatigue': 1}
      - 7956230  levels={'Headache': 1, 'Fatigue': 2}
  - in denominator but does NOT support:
      - 30669  levels={'Headache': 3, 'Fatigue': 1}
      - 989864  levels={'Headache': 2, 'Fatigue': 1}
      - 2094006  levels={'Headache': 1, 'Fatigue': 0}
      - 9284759  levels={'Headache': 1, 'Fatigue': 0}
      - 4161604  levels={'Headache': 6, 'Fatigue': 2}
      - 7586307  levels={'Headache': 1, 'Fatigue': 0}
  - EXCLUDED from the denominator:
      - 8958400  levels={'Headache': 2, 'Fatigue': 2}
      - 4460409  levels={'Headache': 2, 'Fatigue': 2}
      - 8128597  levels={'Headache': 1, 'Fatigue': 1}
      - 3756722  levels={'Headache': 1, 'Fatigue': 1}
      - 7034748  levels={'Headache': 2, 'Fatigue': 2}
      - 6933763  levels={'Headache': 1, 'Fatigue': 1}

## 2. P-V2 (antecedent_bool, BOOL) -- realized as insufficient
- claim: "After Pfizer, Headache follows Fatigue more often than it follows Pyrexia."
- events: ['Fatigue', 'Headache', 'Pyrexia']   cohort: ['Pfizer']
- conditioning rule: B-follows-A rate vs B-follows-C rate (two ordered-pair arms, one cohort); Fisher 2x2
- **n = 50, k = 15, proportion = 0.3**
- min-n floor for this family: 10
- test: fisher_exact   p_claim = 0.976668   p_opposite = 0.05572   alpha = 0.05
- **gold verdict: insufficient (underpowered)**
- 95% CI: [0.191, 0.4375]
- cohort 2: proportion=0.4667 n=60 k=28
  - cohort_1: n=50 k=15 excluded=67
  - cohort_1 sample:
      - 5341252  levels={'Fatigue': 2, 'Headache': 1, 'Pyrexia': None}
      - 8882718  levels={'Fatigue': 1, 'Headache': 0, 'Pyrexia': 1}
      - 3443605  levels={'Fatigue': 1, 'Headache': 0, 'Pyrexia': 0}
      - 30669  levels={'Fatigue': 1, 'Headache': 3, 'Pyrexia': None}
  - cohort_2: n=60 k=28 excluded=59
  - cohort_2 sample:
      - 1290146  levels={'Fatigue': None, 'Headache': 0, 'Pyrexia': 3}
      - 7180193  levels={'Fatigue': None, 'Headache': 1, 'Pyrexia': 0}
      - 8882718  levels={'Fatigue': 1, 'Headache': 0, 'Pyrexia': 1}
      - 8803251  levels={'Fatigue': 1, 'Headache': 0, 'Pyrexia': 1}

## 3. P-V3 (dir_choice, CHOICE) -- realized as supported
- claim: "After Pfizer, Headache usually comes before Fatigue."
- events: ['Headache', 'Fatigue']   cohort: ['Pfizer']
- conditioning rule: precedes frac on ordered-pair denom; names higher-frac event
- excluded when: co-exist (same level) -- not ordered, so excluded from a PRECEDES denominator
- **n = 50, k = 35, proportion = 0.7**
- counts match: **OK** (denominator ids 50 vs n 50; numerator ids 35 vs k 35; 67 excluded)
- min-n floor for this family: 10
- test: binom_exact   p_claim = 0.0033   p_opposite = 0.998699   alpha = 0.05
- **gold verdict: supported**
- 95% CI: [0.5625, 0.809]
  - supports the claim (numerator):
      - 5341252  levels={'Headache': 1, 'Fatigue': 2}
      - 8882718  levels={'Headache': 0, 'Fatigue': 1}
      - 3443605  levels={'Headache': 0, 'Fatigue': 1}
      - 8803251  levels={'Headache': 0, 'Fatigue': 1}
      - 9454869  levels={'Headache': 0, 'Fatigue': 1}
      - 7956230  levels={'Headache': 1, 'Fatigue': 2}
  - in denominator but does NOT support:
      - 30669  levels={'Headache': 3, 'Fatigue': 1}
      - 989864  levels={'Headache': 2, 'Fatigue': 1}
      - 2094006  levels={'Headache': 1, 'Fatigue': 0}
      - 9284759  levels={'Headache': 1, 'Fatigue': 0}
      - 4161604  levels={'Headache': 6, 'Fatigue': 2}
      - 7586307  levels={'Headache': 1, 'Fatigue': 0}
  - EXCLUDED from the denominator:
      - 8958400  levels={'Headache': 2, 'Fatigue': 2}
      - 4460409  levels={'Headache': 2, 'Fatigue': 2}
      - 8128597  levels={'Headache': 1, 'Fatigue': 1}
      - 3756722  levels={'Headache': 1, 'Fatigue': 1}
      - 7034748  levels={'Headache': 2, 'Fatigue': 2}
      - 6933763  levels={'Headache': 1, 'Fatigue': 1}

## 4. P-V4 (pairpair_bool, BOOL) -- realized as insufficient
- claim: "After Pfizer, Headache precedes Fatigue more often than Pyrexia precedes Pain."
- events: ['Headache', 'Fatigue', 'Pyrexia', 'Pain']   cohort: ['Pfizer']
- conditioning rule: A-before-B rate vs C-before-D rate (two ordered-pair arms, one cohort); Fisher 2x2
- **n = 50, k = 35, proportion = 0.7**
- min-n floor for this family: 10
- test: fisher_exact   p_claim = 0.105425   p_opposite = 0.956149   alpha = 0.05
- **gold verdict: insufficient (underpowered)**
- 95% CI: [0.5625, 0.809]
- cohort 2: proportion=0.5429 n=35 k=19
  - cohort_1: n=50 k=35 excluded=67
  - cohort_1 sample:
      - 5341252  levels={'Headache': 1, 'Fatigue': 2, 'Pyrexia': None, 'Pain': None}
      - 8882718  levels={'Headache': 0, 'Fatigue': 1, 'Pyrexia': 1, 'Pain': None}
      - 3443605  levels={'Headache': 0, 'Fatigue': 1, 'Pyrexia': 0, 'Pain': 0}
      - 30669  levels={'Headache': 3, 'Fatigue': 1, 'Pyrexia': None, 'Pain': None}
  - cohort_2: n=35 k=19 excluded=58
  - cohort_2 sample:
      - 1290146  levels={'Headache': 0, 'Fatigue': None, 'Pyrexia': 3, 'Pain': 2}
      - 9987037  levels={'Headache': None, 'Fatigue': 2, 'Pyrexia': 3, 'Pain': 1}
      - 5454409  levels={'Headache': None, 'Fatigue': None, 'Pyrexia': 1, 'Pain': 0}
      - 827872  levels={'Headache': 1, 'Fatigue': None, 'Pyrexia': 1, 'Pain': 2}

## 5. C-V1 (sym_bool_cooccurs, BOOL) -- realized as insufficient
- claim: "After Pfizer, Headache and Fatigue typically co-occur."
- events: ['Headache', 'Fatigue']   cohort: ['Pfizer']
- conditioning rule: co-occurs frac (both-present denom); supported if >0.5
- excluded when: n/a -- every both-present report counts for CO-OCCURS
- **n = 117, k = 67, proportion = 0.5726**
- counts match: **OK** (denominator ids 117 vs n 117; numerator ids 67 vs k 67; 0 excluded)
- min-n floor for this family: 10
- test: binom_exact   p_claim = 0.069377   p_opposite = 0.952164   alpha = 0.05
- **gold verdict: insufficient (underpowered)**
- 95% CI: [0.4821, 0.6586]
  - supports the claim (numerator):
      - 8958400  levels={'Headache': 2, 'Fatigue': 2}
      - 4460409  levels={'Headache': 2, 'Fatigue': 2}
      - 8128597  levels={'Headache': 1, 'Fatigue': 1}
      - 3756722  levels={'Headache': 1, 'Fatigue': 1}
      - 7034748  levels={'Headache': 2, 'Fatigue': 2}
      - 6933763  levels={'Headache': 1, 'Fatigue': 1}
  - in denominator but does NOT support:
      - 5341252  levels={'Headache': 1, 'Fatigue': 2}
      - 8882718  levels={'Headache': 0, 'Fatigue': 1}
      - 3443605  levels={'Headache': 0, 'Fatigue': 1}
      - 30669  levels={'Headache': 3, 'Fatigue': 1}
      - 989864  levels={'Headache': 2, 'Fatigue': 1}
      - 8803251  levels={'Headache': 0, 'Fatigue': 1}

## 6. C-V2 (assoc_bool, BOOL) -- realized as supported
- claim: "After Pfizer, Headache and Fatigue occur together more often than their separate rates would predict."
- events: ['Headache', 'Fatigue']   cohort: ['Pfizer']
- conditioning rule: P(B|A) vs P(B|not A), presence x presence; Fisher 2x2
- **n = 301, k = 117, proportion = 0.3887**
- min-n floor for this family: 10
- test: fisher_exact   p_claim = 0.0   p_opposite = 1.0   alpha = 0.05
- **gold verdict: supported**
- 95% CI: [0.128, 0.2521]
- cohort 2: proportion=0.1992 n=718 k=143
  - cohort_1: n=301 k=117 excluded=0
  - cohort_1 sample:
      - 8958400  levels={'Headache': 2, 'Fatigue': 2}
      - 5341252  levels={'Headache': 1, 'Fatigue': 2}
      - 211234  levels={'Headache': 0, 'Fatigue': None}
      - 1290146  levels={'Headache': 0, 'Fatigue': None}
  - cohort_2: n=718 k=143 excluded=0
  - cohort_2 sample:
      - 2596992  levels={'Headache': None, 'Fatigue': None}
      - 6964051  levels={'Headache': None, 'Fatigue': None}
      - 707515  levels={'Headache': None, 'Fatigue': None}
      - 6489279  levels={'Headache': None, 'Fatigue': None}

## 7. C-V3 (cooc_modal_bool, BOOL) -- realized as supported
- claim: "After Pfizer, co-occurrence is the dominant relation for Headache and Fatigue."
- events: ['Headache', 'Fatigue']   cohort: ['Pfizer']
- conditioning rule: co_exist vs max(before, after), modal-vs-runner-up (both-present denom); named cell = co_exist
- excluded when: n/a -- every both-present report counts for CO-OCCURS
- **n = 117, k = 67, proportion = 0.5726**
- counts match: **OK** (denominator ids 117 vs n 117; numerator ids 67 vs k 67; 0 excluded)
- min-n floor for this family: 10
- test: modal_runner   p_claim = 0.000996   p_opposite = 0.999507   alpha = 0.05
- **gold verdict: supported**
- 95% CI: [0.4821, 0.6586]
  - supports the claim (numerator):
      - 8958400  levels={'Headache': 2, 'Fatigue': 2}
      - 4460409  levels={'Headache': 2, 'Fatigue': 2}
      - 8128597  levels={'Headache': 1, 'Fatigue': 1}
      - 3756722  levels={'Headache': 1, 'Fatigue': 1}
      - 7034748  levels={'Headache': 2, 'Fatigue': 2}
      - 6933763  levels={'Headache': 1, 'Fatigue': 1}
  - in denominator but does NOT support:
      - 5341252  levels={'Headache': 1, 'Fatigue': 2}
      - 8882718  levels={'Headache': 0, 'Fatigue': 1}
      - 3443605  levels={'Headache': 0, 'Fatigue': 1}
      - 30669  levels={'Headache': 3, 'Fatigue': 1}
      - 989864  levels={'Headache': 2, 'Fatigue': 1}
      - 8803251  levels={'Headache': 0, 'Fatigue': 1}

## 8. S-V3 (modal_choice, CHOICE) -- realized as insufficient
- claim: "After Pfizer, the most common ordering of Headache, Pyrexia, Fatigue is Headache → Pyrexia → Fatigue."
- events: ['Headache', 'Pyrexia', 'Fatigue']   cohort: ['Pfizer']
- conditioning rule: argmax strict ordering over orderable denom; modal-vs-runner-up test
- excluded when: two or more of the three share a level -- triple not orderable
- **n = 6, k = 3, proportion = 0.5**
- counts match: **OK** (denominator ids 6 vs n 6; numerator ids 3 vs k 3; 41 excluded)
- min-n floor for this family: 5
- test: modal_runner   p_claim = 0.5   p_opposite = 0.8125   alpha = 0.05
- **gold verdict: insufficient (underpowered)**
- 95% CI: [0.1876, 0.8124]
  - supports the claim (numerator):
      - 2045476  levels={'Headache': 0, 'Pyrexia': 1, 'Fatigue': 2}
      - 8645528  levels={'Headache': 0, 'Pyrexia': 2, 'Fatigue': 3}
      - 29289  levels={'Headache': 0, 'Pyrexia': 1, 'Fatigue': 4}
  - in denominator but does NOT support:
      - 4161604  levels={'Headache': 6, 'Pyrexia': 5, 'Fatigue': 2}
      - 8480848  levels={'Headache': 3, 'Pyrexia': 6, 'Fatigue': 2}
      - 4709905  levels={'Headache': 2, 'Pyrexia': 1, 'Fatigue': 0}
  - EXCLUDED from the denominator:
      - 4460409  levels={'Headache': 2, 'Pyrexia': 2, 'Fatigue': 2}
      - 8128597  levels={'Headache': 1, 'Pyrexia': 1, 'Fatigue': 1}
      - 8882718  levels={'Headache': 0, 'Pyrexia': 1, 'Fatigue': 1}
      - 3443605  levels={'Headache': 0, 'Pyrexia': 0, 'Fatigue': 1}
      - 989864  levels={'Headache': 2, 'Pyrexia': 2, 'Fatigue': 1}
      - 6933763  levels={'Headache': 1, 'Pyrexia': 1, 'Fatigue': 1}

## 9. F-V1 (first_choice, CHOICE) -- realized as insufficient
- claim: "After Pfizer, Headache is most commonly the first event among Headache, Fatigue, Pyrexia."
- events: ['Headache', 'Fatigue', 'Pyrexia']   cohort: ['Pfizer']
- conditioning rule: first_among argmax (all-candidates denom); modal-vs-runner-up test
- excluded when: tie for first -- no single earliest event
- **n = 20, k = 8, proportion = 0.4**
- counts match: **OK** (denominator ids 20 vs n 20; numerator ids 8 vs k 8; 27 excluded)
- min-n floor for this family: 10
- test: modal_runner   p_claim = 0.5   p_opposite = 0.696381   alpha = 0.05
- **gold verdict: insufficient (underpowered)**
- 95% CI: [0.2188, 0.6134]
  - supports the claim (numerator):
      - 8882718  levels={'Headache': 0, 'Fatigue': 1, 'Pyrexia': 1}
      - 8803251  levels={'Headache': 0, 'Fatigue': 1, 'Pyrexia': 1}
      - 6981502  levels={'Headache': 1, 'Fatigue': 2, 'Pyrexia': 2}
      - 2489821  levels={'Headache': 0, 'Fatigue': 1, 'Pyrexia': 1}
      - 2045476  levels={'Headache': 0, 'Fatigue': 2, 'Pyrexia': 1}
      - 8645528  levels={'Headache': 0, 'Fatigue': 3, 'Pyrexia': 2}
  - in denominator but does NOT support:
      - 989864  levels={'Headache': 2, 'Fatigue': 1, 'Pyrexia': 2}
      - 4161604  levels={'Headache': 6, 'Fatigue': 2, 'Pyrexia': 5}
      - 7586307  levels={'Headache': 1, 'Fatigue': 0, 'Pyrexia': 1}
      - 3221671  levels={'Headache': 1, 'Fatigue': 0, 'Pyrexia': 1}
      - 8480848  levels={'Headache': 3, 'Fatigue': 2, 'Pyrexia': 6}
      - 334132  levels={'Headache': 1, 'Fatigue': 1, 'Pyrexia': 0}
  - EXCLUDED from the denominator:
      - 4460409  levels={'Headache': 2, 'Fatigue': 2, 'Pyrexia': 2}
      - 8128597  levels={'Headache': 1, 'Fatigue': 1, 'Pyrexia': 1}
      - 3443605  levels={'Headache': 0, 'Fatigue': 1, 'Pyrexia': 0}
      - 6933763  levels={'Headache': 1, 'Fatigue': 1, 'Pyrexia': 1}
      - 7956230  levels={'Headache': 1, 'Fatigue': 2, 'Pyrexia': 1}
      - 2107541  levels={'Headache': 0, 'Fatigue': 0, 'Pyrexia': 1}

## 10. F-V2 (last_choice, CHOICE) -- realized as insufficient
- claim: "After Pfizer, Fatigue is most commonly the last event among Fatigue, Headache, Pyrexia."
- events: ['Fatigue', 'Headache', 'Pyrexia']   cohort: ['Pfizer']
- conditioning rule: last_among argmax (all-candidates denom); modal-vs-runner-up test
- excluded when: tie for last -- no single latest event
- **n = 18, k = 9, proportion = 0.5**
- counts match: **OK** (denominator ids 18 vs n 18; numerator ids 9 vs k 9; 29 excluded)
- min-n floor for this family: 10
- test: modal_runner   p_claim = 0.303619   p_opposite = 0.849121   alpha = 0.05
- **gold verdict: insufficient (underpowered)**
- 95% CI: [0.2903, 0.7097]
  - supports the claim (numerator):
      - 3443605  levels={'Fatigue': 1, 'Headache': 0, 'Pyrexia': 0}
      - 7956230  levels={'Fatigue': 2, 'Headache': 1, 'Pyrexia': 1}
      - 1944276  levels={'Fatigue': 2, 'Headache': 0, 'Pyrexia': 0}
      - 632545  levels={'Fatigue': 1, 'Headache': 0, 'Pyrexia': 0}
      - 2045476  levels={'Fatigue': 2, 'Headache': 0, 'Pyrexia': 1}
      - 8645528  levels={'Fatigue': 3, 'Headache': 0, 'Pyrexia': 2}
  - in denominator but does NOT support:
      - 4161604  levels={'Fatigue': 2, 'Headache': 6, 'Pyrexia': 5}
      - 2107541  levels={'Fatigue': 0, 'Headache': 0, 'Pyrexia': 1}
      - 8480848  levels={'Fatigue': 2, 'Headache': 3, 'Pyrexia': 6}
      - 5552387  levels={'Fatigue': 0, 'Headache': 0, 'Pyrexia': 1}
      - 4685111  levels={'Fatigue': 1, 'Headache': 1, 'Pyrexia': 2}
      - 4709905  levels={'Fatigue': 0, 'Headache': 2, 'Pyrexia': 1}
  - EXCLUDED from the denominator:
      - 4460409  levels={'Fatigue': 2, 'Headache': 2, 'Pyrexia': 2}
      - 8128597  levels={'Fatigue': 1, 'Headache': 1, 'Pyrexia': 1}
      - 8882718  levels={'Fatigue': 1, 'Headache': 0, 'Pyrexia': 1}
      - 989864  levels={'Fatigue': 1, 'Headache': 2, 'Pyrexia': 2}
      - 6933763  levels={'Fatigue': 1, 'Headache': 1, 'Pyrexia': 1}
      - 8803251  levels={'Fatigue': 1, 'Headache': 0, 'Pyrexia': 1}

## 11. F-V3 (first_bool, BOOL) -- realized as insufficient
- claim: "After Pfizer, Headache is the most common first event among Headache, Fatigue, Pyrexia."
- events: ['Headache', 'Fatigue', 'Pyrexia']   cohort: ['Pfizer']
- conditioning rule: most-common first event (all-candidates denom); unique winner; modal-vs-runner-up test
- excluded when: tie for first -- no single earliest event
- **n = 20, k = 8, proportion = 0.4**
- counts match: **OK** (denominator ids 20 vs n 20; numerator ids 8 vs k 8; 27 excluded)
- min-n floor for this family: 10
- test: modal_runner   p_claim = 0.5   p_opposite = 0.696381   alpha = 0.05
- **gold verdict: insufficient (underpowered)**
- 95% CI: [0.2188, 0.6134]
  - supports the claim (numerator):
      - 8882718  levels={'Headache': 0, 'Fatigue': 1, 'Pyrexia': 1}
      - 8803251  levels={'Headache': 0, 'Fatigue': 1, 'Pyrexia': 1}
      - 6981502  levels={'Headache': 1, 'Fatigue': 2, 'Pyrexia': 2}
      - 2489821  levels={'Headache': 0, 'Fatigue': 1, 'Pyrexia': 1}
      - 2045476  levels={'Headache': 0, 'Fatigue': 2, 'Pyrexia': 1}
      - 8645528  levels={'Headache': 0, 'Fatigue': 3, 'Pyrexia': 2}
  - in denominator but does NOT support:
      - 989864  levels={'Headache': 2, 'Fatigue': 1, 'Pyrexia': 2}
      - 4161604  levels={'Headache': 6, 'Fatigue': 2, 'Pyrexia': 5}
      - 7586307  levels={'Headache': 1, 'Fatigue': 0, 'Pyrexia': 1}
      - 3221671  levels={'Headache': 1, 'Fatigue': 0, 'Pyrexia': 1}
      - 8480848  levels={'Headache': 3, 'Fatigue': 2, 'Pyrexia': 6}
      - 334132  levels={'Headache': 1, 'Fatigue': 1, 'Pyrexia': 0}
  - EXCLUDED from the denominator:
      - 4460409  levels={'Headache': 2, 'Fatigue': 2, 'Pyrexia': 2}
      - 8128597  levels={'Headache': 1, 'Fatigue': 1, 'Pyrexia': 1}
      - 3443605  levels={'Headache': 0, 'Fatigue': 1, 'Pyrexia': 0}
      - 6933763  levels={'Headache': 1, 'Fatigue': 1, 'Pyrexia': 1}
      - 7956230  levels={'Headache': 1, 'Fatigue': 2, 'Pyrexia': 1}
      - 2107541  levels={'Headache': 0, 'Fatigue': 0, 'Pyrexia': 1}

## 12. P-M2 (multi_dir_precedes, CHOICE) -- realized as insufficient
- claim: "Headache precedes Fatigue more often after Pfizer than after Moderna."
- events: ['Headache', 'Fatigue']   cohort: ['Pfizer', 'Moderna']
- conditioning rule: two precedes fracs; names higher cohort
- **n = 50, k = 35, proportion = 0.7**
- min-n floor for this family: 10
- test: fisher_exact   p_claim = 0.32294   p_opposite = 0.804484   alpha = 0.05
- **gold verdict: insufficient (underpowered)**
- 95% CI: [0.5625, 0.809]
- cohort 2: proportion=0.6418 n=67 k=43
  - cohort_1: n=50 k=35 excluded=67
  - cohort_1 sample:
      - 5341252  levels={'Headache': 1, 'Fatigue': 2}
      - 8882718  levels={'Headache': 0, 'Fatigue': 1}
      - 3443605  levels={'Headache': 0, 'Fatigue': 1}
      - 30669  levels={'Headache': 3, 'Fatigue': 1}
  - cohort_2: n=67 k=43 excluded=70
  - cohort_2 sample:
      - 3874603  levels={'Headache': 1, 'Fatigue': 2}
      - 4298201  levels={'Headache': 0, 'Fatigue': 1}
      - 150098  levels={'Headache': 1, 'Fatigue': 0}
      - 1282819  levels={'Headache': 0, 'Fatigue': 1}

## 13. P-R1 (rep_dir_bool, BOOL) -- realized as supported
- claim: "In report MT-9619450, Injection site paraesthesia occurred before Injection site pruritus."
- events: ['Injection site paraesthesia', 'Injection site pruritus']   cohort: report-level
- conditioning rule: per-report relation; before => supported
- **n = None, k = None, proportion = None**
- test: None   p_claim = None   p_opposite = None   alpha = 0.05
- **gold verdict: supported (deterministic)**
  - supports the claim (numerator):
      - 9619450  levels={'Injection site paraesthesia': 0, 'Injection site pruritus': 1}

## 14. C-R1 (rep_sym_bool, BOOL) -- realized as refuted
- claim: "In report MT-9619450, Injection site paraesthesia and Injection site pruritus co-occur."
- events: ['Injection site paraesthesia', 'Injection site pruritus']   cohort: report-level
- conditioning rule: per-report relation; co_exist => supported
- **n = None, k = None, proportion = None**
- test: None   p_claim = None   p_opposite = None   alpha = 0.05
- **gold verdict: refuted (deterministic)**
  - supports the claim (numerator):
      - 9619450  levels={'Injection site paraesthesia': 0, 'Injection site pruritus': 1}

## 15. S-R1 (rep_seq_bool, BOOL) -- realized as supported
- claim: "In report MT-9619450, Injection site paraesthesia, Injection site pruritus, Injection site erythema occur in the order Injection site paraesthesia → Injection site pruritus → Injection site erythema."
- events: ['Injection site paraesthesia', 'Injection site pruritus', 'Injection site erythema']   cohort: report-level
- conditioning rule: per-report strict order A<B<C
- **n = None, k = None, proportion = None**
- test: None   p_claim = None   p_opposite = None   alpha = 0.05
- **gold verdict: supported (deterministic)**
  - supports the claim (numerator):
      - 9619450  levels={'Injection site paraesthesia': 0, 'Injection site pruritus': 1, 'Injection site erythema': 2}

## 16. F-R1 (rep_first_choice, CHOICE) -- realized as supported
- claim: "In report MT-9619450, Injection site paraesthesia occurs first among Injection site paraesthesia, Injection site pruritus, Injection site erythema."
- events: ['Injection site paraesthesia', 'Injection site pruritus', 'Injection site erythema']   cohort: report-level
- conditioning rule: per-report first_among single winner
- **n = None, k = None, proportion = None**
- test: None   p_claim = None   p_opposite = None   alpha = 0.05
- **gold verdict: supported (deterministic)**
  - supports the claim (numerator):
      - 9619450  levels={'Injection site paraesthesia': 0, 'Injection site pruritus': 1, 'Injection site erythema': 2}
