# Worked Examples per Template (real MedTempo data)

One live example per template group. Each shows the conditioned
counts, the significance test computed on the real data, and the
gold verdict. Refuted examples assert a false relation about the
SAME real, co-occurring events.

## True-case distribution (which templates are rich vs poor)

`supported-capable` = number of viable cores that can yield a TRUE (supported) example.

| template | viable cores | supported-capable | refuted-capable |
|---|--:|--:|--:|
| P-R1 | 3166 | 1196 | 3166 |
| P-R2 | 3166 | 1196 | 1196 |
| P-V1 | 173 | 168 | 168 |
| P-V3 | 173 | 168 | 168 |
| P-M1 | 99 | 39 | 60 |
| P-M2 | 99 | 99 | 99 |
| C-R1 | 3166 | 1970 | 1196 |
| C-V1 | 374 | 90 | 271 |
| C-V3 | 374 | 90 | 271 |
| C-M1 | 232 | 89 | 143 |
| C-M2 | 232 | 232 | 232 |
| S-R1 | 3166 | 489 | 3166 |
| S-V1 | 275 | 192 | 192 |
| S-V3 | 275 | 192 | 192 |
| S-V4 | 275 | 62 | 174 |
| S-M1 | 90 | 44 | 46 |
| S-M2 | 90 | 75 | 75 |
| S-M3 | 90 | 25 | 65 |
| F-R1 | 3166 | 1196 | 3166 |
| F-R2 | 3166 | 1299 | 3166 |
| F-R3 | 3166 | 1196 | 1196 |
| F-V1 | 82 | 67 | 82 |
| F-V2 | 82 | 73 | 82 |
| F-V3 | 82 | 67 | 82 |
| F-M1 | 46 | 23 | 23 |
| F-M2 | 46 | 23 | 23 |
| F-M3 | 46 | 45 | 45 |

## Gold-label vs significance-test fail rate

For every viable core with a definite gold verdict (supported/refuted) and an applicable categorical test (PROP and report-level excluded), we check whether the test is significant at alpha=0.05. A **fail** is a definite gold label the test does NOT corroborate. This is the population rate over ALL such cores.

- **Overall population**: 2234/2939 (76.0%) of definite-verdict categorical cores are not significant.

| family | definite cores | failed | fail rate |
|---|--:|--:|--:|
| pairwise-precedes | 534 | 327 | 327/534 (61.2%) |
| co-occurs | 1186 | 795 | 795/1186 (67.0%) |
| sequence | 875 | 848 | 848/875 (96.9%) |
| first/last | 344 | 264 | 264/344 (76.7%) |

For the worked examples below we search each template's cores for a **successful** example (definite gold + significant test) to showcase; only when none exists do we present a failed one.

- **Presented examples**: 4/20 (20.0%) of testable templates still show a failed example (no successful core exists): S-M1, S-M2, S-M3, F-M3.

| template | definite cores | failed | fail rate | presented |
|---|--:|--:|--:|:--:|
| P-R1 | 0 | 0 | n/a | n/a |
| P-R2 | 0 | 0 | n/a | n/a |
| P-V1 | 168 | 81 | 81/168 (48.2%) | successful |
| P-V3 | 168 | 81 | 81/168 (48.2%) | successful |
| P-M1 | 99 | 84 | 84/99 (84.8%) | successful |
| P-M2 | 99 | 81 | 81/99 (81.8%) | successful |
| C-R1 | 0 | 0 | n/a | n/a |
| C-V1 | 361 | 184 | 184/361 (51.0%) | successful |
| C-V3 | 361 | 184 | 184/361 (51.0%) | successful |
| C-M1 | 232 | 218 | 218/232 (94.0%) | successful |
| C-M2 | 232 | 209 | 209/232 (90.1%) | successful |
| S-R1 | 0 | 0 | n/a | n/a |
| S-V1 | 192 | 188 | 188/192 (97.9%) | successful |
| S-V3 | 192 | 180 | 180/192 (93.8%) | successful |
| S-V4 | 236 | 225 | 225/236 (95.3%) | successful |
| S-M1 | 90 | 90 | 90/90 (100.0%) | failed |
| S-M2 | 75 | 75 | 75/75 (100.0%) | failed |
| S-M3 | 90 | 90 | 90/90 (100.0%) | failed |
| F-R1 | 0 | 0 | n/a | n/a |
| F-R2 | 0 | 0 | n/a | n/a |
| F-R3 | 0 | 0 | n/a | n/a |
| F-V1 | 67 | 42 | 42/67 (62.7%) | successful |
| F-V2 | 73 | 36 | 36/73 (49.3%) | successful |
| F-V3 | 67 | 53 | 53/67 (79.1%) | successful |
| F-M1 | 46 | 44 | 44/46 (95.7%) | successful |
| F-M2 | 46 | 44 | 44/46 (95.7%) | successful |
| F-M3 | 45 | 45 | 45/45 (100.0%) | failed |

## P-value vs gold-label mismatches

Templates whose worked example has a p-value that does not match the gold label (flagged **red** in the LaTeX findings). **type1** = a definite gold verdict but the categorical test is not significant. **type2** = structural: the p is computed on a different quantity than the gold names.

| template | type1 | type2 |
|---|:--:|:--:|
| S-M1 | yes |  |
| S-M2 | yes |  |
| S-M3 | yes |  |
| F-M3 | yes |  |

## P-R1  (pairwise, report, BOOL)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 3166 viable | 1196 supported-capable (true cases) | 3166 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Categorical test**: none (report-level: single observation, no sampling distribution)
    - *H0: none -- single deterministic observation, no sampling distribution*
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: Did Dizziness occur before Injection site pain in report VAERS-916915?
        - Claim: In report VAERS-916915, Dizziness occurred before Injection site pain.
    - **Research**
        - Q: In this report, does Dizziness precede Injection site pain?
        - Claim: This report records Dizziness preceding Injection site pain.
    - **Media**
        - Q: In this case, did Dizziness happen before Injection site pain?
        - Claim: In this case, Dizziness happened before Injection site pain.
    - **Clinical**
        - Q: Did Dizziness come before Injection site pain in this patient?
        - Claim: In this patient, Dizziness came before Injection site pain.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: Did Injection site pain occur before Dizziness in report VAERS-916915?
        - Claim: In report VAERS-916915, Injection site pain occurred before Dizziness.
    - **Research**
        - Q: In this report, does Injection site pain precede Dizziness?
        - Claim: This report records Injection site pain preceding Dizziness.
    - **Media**
        - Q: In this case, did Injection site pain happen before Dizziness?
        - Claim: In this case, Injection site pain happened before Dizziness.
    - **Clinical**
        - Q: Did Injection site pain come before Dizziness in this patient?
        - Claim: In this patient, Injection site pain came before Dizziness.

## P-R2  (pairwise, report, CHOICE)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 3166 viable | 1196 supported-capable (true cases) | 1196 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Categorical test**: none (report-level: single observation, no sampling distribution)
    - *H0: none -- single deterministic observation, no sampling distribution*
- **Options**: ['Dizziness', 'Injection site pain']  ->  correct: **Dizziness**
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: Which came first in report VAERS-916915, Dizziness or Injection site pain?
        - Claim: In report VAERS-916915, Dizziness came first, before Injection site pain.
    - **Research**
        - Q: Of Dizziness and Injection site pain, which is the earlier event in this report?
        - Claim: In this report, Dizziness is the earlier event.
    - **Media**
        - Q: In this case, which came first, Dizziness or Injection site pain?
        - Claim: In this case, Dizziness came first.
    - **Clinical**
        - Q: Between Dizziness and Injection site pain, which came first in this patient?
        - Claim: In this patient, Dizziness came first.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: Which came first in report VAERS-916915, Injection site pain or Dizziness?
        - Claim: In report VAERS-916915, Injection site pain came first, before Dizziness.
    - **Research**
        - Q: Of Injection site pain and Dizziness, which is the earlier event in this report?
        - Claim: In this report, Injection site pain is the earlier event.
    - **Media**
        - Q: In this case, which came first, Injection site pain or Dizziness?
        - Claim: In this case, Injection site pain came first.
    - **Clinical**
        - Q: Between Injection site pain and Dizziness, which came first in this patient?
        - Claim: In this patient, Injection site pain came first.

## P-V1  (pairwise, vaccine, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 81/168 (48.2%) fail)
- **Qualified cores**: 173 viable | 168 supported-capable (true cases) | 168 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Janssen
- **Conditioned counts**: k=44 / n=119  (rate 0.3697)
- **Categorical test**: binomial exact (one-sided, less), p = 0.002863 (significant)
    - *H0: P(Fatigue precedes Headache) = 0.5 (no directional preference among ordered reports)*
    - *how p is computed*: exact binomial vs the 1/2 chance null (pairwise precedes, co-occurs), ONE-SIDED in the observed direction (greater if the rate is above 0.5, less if below) so it corroborates the observed verdict, not the reverse
- **Position-based test**: Wilcoxon signed-rank (level(Fatigue)-level(Headache); n=119 (normal)), p = 0.002862
    - *H0: the Fatigue-vs-Headache rank-distances are symmetric about 0 (neither event tends to come earlier)*
    - *how p is computed*: Wilcoxon signed-rank -- rank |d| where d=level(A)-level(B) (co-exist d=0 dropped), sum the signed ranks; exact sign-flip null for small n, else normal approximation with tie/continuity correction
- **95% CI**: [0.2884, 0.4593], effect size -0.2635
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: Does Headache typically occur before Fatigue after Janssen?
        - Claim: After Janssen, Headache typically occurs before Fatigue.
    - **Research**
        - Q: Among Janssen reports, does Headache precede Fatigue in the majority of cases?
        - Claim: Among Janssen reports, Headache precedes Fatigue in the majority of cases.
    - **Media**
        - Q: After Janssen, do most people get Headache before Fatigue?
        - Claim: After Janssen, most people get Headache before Fatigue.
    - **Clinical**
        - Q: In Janssen recipients, does Headache usually come before Fatigue?
        - Claim: In Janssen recipients, Headache usually comes before Fatigue.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: Does Fatigue typically occur before Headache after Janssen?
        - Claim: After Janssen, Fatigue typically occurs before Headache.
    - **Research**
        - Q: Among Janssen reports, does Fatigue precede Headache in the majority of cases?
        - Claim: Among Janssen reports, Fatigue precedes Headache in the majority of cases.
    - **Media**
        - Q: After Janssen, do most people get Fatigue before Headache?
        - Claim: After Janssen, most people get Fatigue before Headache.
    - **Clinical**
        - Q: In Janssen recipients, does Fatigue usually come before Headache?
        - Claim: In Janssen recipients, Fatigue usually comes before Headache.

## P-V3  (pairwise, vaccine, CHOICE)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 81/168 (48.2%) fail)
- **Qualified cores**: 173 viable | 168 supported-capable (true cases) | 168 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Janssen
- **Conditioned counts**: k=44 / n=119  (rate 0.3697)
- **Categorical test**: binomial exact (one-sided, less), p = 0.002863 (significant)
    - *H0: P(Fatigue precedes Headache) = 0.5 (no directional preference among ordered reports)*
    - *how p is computed*: exact binomial vs the 1/2 chance null (pairwise precedes, co-occurs), ONE-SIDED in the observed direction (greater if the rate is above 0.5, less if below) so it corroborates the observed verdict, not the reverse
- **Position-based test**: Wilcoxon signed-rank (level(Fatigue)-level(Headache); n=119 (normal)), p = 0.002862
    - *H0: the Fatigue-vs-Headache rank-distances are symmetric about 0 (neither event tends to come earlier)*
    - *how p is computed*: Wilcoxon signed-rank -- rank |d| where d=level(A)-level(B) (co-exist d=0 dropped), sum the signed ranks; exact sign-flip null for small n, else normal approximation with tie/continuity correction
- **95% CI**: [0.2884, 0.4593], effect size -0.2635
- **Options**: ['Fatigue', 'Headache']  ->  correct: **Headache**
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, which usually comes first, Headache or Fatigue?
        - Claim: After Janssen, Headache usually comes before Fatigue.
    - **Research**
        - Q: Among Janssen reports with both, which more often precedes the other, Headache or Fatigue?
        - Claim: Among Janssen reports with both, Headache more often precedes Fatigue.
    - **Media**
        - Q: After Janssen, which side effect tends to come first, Headache or Fatigue?
        - Claim: After Janssen, Headache tends to come first.
    - **Clinical**
        - Q: In Janssen patients, what usually shows up first, Headache or Fatigue?
        - Claim: In Janssen patients, Headache usually shows up first.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, which usually comes first, Fatigue or Headache?
        - Claim: After Janssen, Fatigue usually comes before Headache.
    - **Research**
        - Q: Among Janssen reports with both, which more often precedes the other, Fatigue or Headache?
        - Claim: Among Janssen reports with both, Fatigue more often precedes Headache.
    - **Media**
        - Q: After Janssen, which side effect tends to come first, Fatigue or Headache?
        - Claim: After Janssen, Fatigue tends to come first.
    - **Clinical**
        - Q: In Janssen patients, what usually shows up first, Fatigue or Headache?
        - Claim: In Janssen patients, Fatigue usually shows up first.

## P-M1  (pairwise, multi, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 84/99 (84.8%) fail)
- **Qualified cores**: 99 viable | 39 supported-capable (true cases) | 60 refuted-capable
- **Core**: events ['Headache', 'Nausea'], cohort Pfizer vs Moderna
- **Conditioned counts**: k=39 / n=48  |  cohort2 k=20 / n=34  (rate 0.8125)
- **Categorical test**: Fisher exact (2x2) (two-sided), p = 0.04459 (significant)
    - *H0: P(Headache precedes Nausea) is equal for Pfizer and Moderna (p1 = p2)*
    - *how p is computed*: Fisher exact on the 2x2 -- ONE-SIDED toward the higher-rate cohort for the directional multi_dir_* claims, TWO-SIDED for the multi_differ_* "do they differ" claims
- **Position-based test**: Mann-Whitney U (level(Headache)-level(Nausea) between Pfizer/Moderna; n=89/85), p = 0.002855
    - *H0: Pfizer and Moderna draw level(Headache)-level(Nausea) from the same distribution (no cohort difference in rank-distance)*
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [0.0259, 0.411], effect size 0.4977
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: Does the Headache-before-Nausea rate differ between Pfizer and Moderna?
        - Claim: The Headache-before-Nausea rate differs between Pfizer and Moderna.
    - **Research**
        - Q: Among reports with both events, is the Headache-precedes-Nausea proportion different between Pfizer and Moderna?
        - Claim: The Headache-precedes-Nausea proportion differs between Pfizer and Moderna cohorts.
    - **Media**
        - Q: Is there a real difference between Pfizer and Moderna in how often Headache comes before Nausea?
        - Claim: Pfizer and Moderna differ in how often Headache comes before Nausea.
    - **Clinical**
        - Q: Do my Pfizer and Moderna patients differ in how often Headache comes before Nausea?
        - Claim: Pfizer and Moderna recipients differ in the rate of Headache before Nausea.

## P-M2  (pairwise, multi, CHOICE)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 81/99 (81.8%) fail)
- **Qualified cores**: 99 viable | 99 supported-capable (true cases) | 99 refuted-capable
- **Core**: events ['Headache', 'Nausea'], cohort Pfizer vs Moderna
- **Conditioned counts**: k=39 / n=48  |  cohort2 k=20 / n=34  (rate 0.8125)
- **Categorical test**: Fisher exact (2x2) (one-sided, greater), p = 0.02436 (significant)
    - *H0: P(Headache precedes Nausea) is equal for Pfizer and Moderna (p1 = p2)*
    - *how p is computed*: Fisher exact on the 2x2 -- ONE-SIDED toward the higher-rate cohort for the directional multi_dir_* claims, TWO-SIDED for the multi_differ_* "do they differ" claims
- **Position-based test**: Mann-Whitney U (level(Headache)-level(Nausea) between Pfizer/Moderna; n=89/85), p = 0.002855
    - *H0: Pfizer and Moderna draw level(Headache)-level(Nausea) from the same distribution (no cohort difference in rank-distance)*
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [0.0259, 0.411], effect size 0.4977
- **Options**: ['Pfizer', 'Moderna']  ->  correct: **Pfizer**
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: After which vaccine, Pfizer or Moderna, does Headache more often precede Nausea?
        - Claim: Headache precedes Nausea more often after Pfizer than after Moderna.
    - **Research**
        - Q: Between Pfizer and Moderna, which cohort shows a higher Headache-preceding-Nausea proportion?
        - Claim: Pfizer shows a higher Headache-precedes-Nausea proportion than Moderna.
    - **Media**
        - Q: Is Headache-before-Nausea more common after Pfizer or Moderna?
        - Claim: Headache-before-Nausea is more common after Pfizer than Moderna.
    - **Clinical**
        - Q: In which group is Headache more often the precursor to Nausea, Pfizer or Moderna recipients?
        - Claim: Pfizer recipients more often have Headache as a precursor to Nausea.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: After which vaccine, Moderna or Pfizer, does Headache more often precede Nausea?
        - Claim: Headache precedes Nausea more often after Moderna than after Pfizer.
    - **Research**
        - Q: Between Moderna and Pfizer, which cohort shows a higher Headache-preceding-Nausea proportion?
        - Claim: Moderna shows a higher Headache-precedes-Nausea proportion than Pfizer.
    - **Media**
        - Q: Is Headache-before-Nausea more common after Moderna or Pfizer?
        - Claim: Headache-before-Nausea is more common after Moderna than Pfizer.
    - **Clinical**
        - Q: In which group is Headache more often the precursor to Nausea, Moderna or Pfizer recipients?
        - Claim: Moderna recipients more often have Headache as a precursor to Nausea.

## C-R1  (pairwise, report, BOOL)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 3166 viable | 1970 supported-capable (true cases) | 1196 refuted-capable
- **Core**: events ['Arthralgia', 'Chills'], cohort report VAERS-917671
- **Conditioned counts**: (single report; deterministic)
- **Categorical test**: none (report-level: single observation, no sampling distribution)
    - *H0: none -- single deterministic observation, no sampling distribution*
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: Do Arthralgia and Chills co-occur in report VAERS-917671?
        - Claim: In report VAERS-917671, Arthralgia and Chills co-occur.
    - **Research**
        - Q: In this report, are Arthralgia and Chills concurrent?
        - Claim: In this report, Arthralgia and Chills are concurrent.
    - **Media**
        - Q: In this case, did Arthralgia and Chills happen at the same time?
        - Claim: In this case, Arthralgia and Chills happened at the same time.
    - **Clinical**
        - Q: Did this patient have Arthralgia and Chills together?
        - Claim: This patient had Arthralgia and Chills together.

## C-V1  (pairwise, vaccine, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 184/361 (51.0%) fail)
- **Qualified cores**: 374 viable | 90 supported-capable (true cases) | 271 refuted-capable
- **Core**: events ['Chills', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=150 / n=204  (rate 0.7353)
- **Categorical test**: binomial exact (one-sided, greater), p = 6.043e-12 (significant)
    - *H0: P(Chills and Pyrexia co-occur) = 0.5 (among reports containing both)*
    - *how p is computed*: exact binomial vs the 1/2 chance null (pairwise precedes, co-occurs), ONE-SIDED in the observed direction (greater if the rate is above 0.5, less if below) so it corroborates the observed verdict, not the reverse
- **95% CI**: [0.6708, 0.7911], effect size 0.49
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: Do Chills and Pyrexia typically co-occur after Janssen?
        - Claim: After Janssen, Chills and Pyrexia typically co-occur.
    - **Research**
        - Q: In Janssen reports, are Chills and Pyrexia concurrent in the majority of cases?
        - Claim: In Janssen reports, Chills and Pyrexia are concurrent in the majority of cases.
    - **Media**
        - Q: After Janssen, do Chills and Pyrexia usually show up together?
        - Claim: After Janssen, Chills and Pyrexia usually show up together.
    - **Clinical**
        - Q: In Janssen recipients, do Chills and Pyrexia typically present together?
        - Claim: In Janssen recipients, Chills and Pyrexia typically present together.

## C-V3  (pairwise, vaccine, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 184/361 (51.0%) fail)
- **Qualified cores**: 374 viable | 90 supported-capable (true cases) | 271 refuted-capable
- **Core**: events ['Chills', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=150 / n=204  (rate 0.7353)
- **Categorical test**: binomial exact (one-sided, greater), p = 6.043e-12 (significant)
    - *H0: P(Chills and Pyrexia co-occur) = 0.5 (among reports containing both)*
    - *how p is computed*: exact binomial vs the 1/2 chance null (pairwise precedes, co-occurs), ONE-SIDED in the observed direction (greater if the rate is above 0.5, less if below) so it corroborates the observed verdict, not the reverse
- **95% CI**: [0.6708, 0.7911], effect size 0.49
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, is co-occurrence the dominant relation for Chills and Pyrexia?
        - Claim: After Janssen, co-occurrence is the dominant relation for Chills and Pyrexia.
    - **Research**
        - Q: Among Janssen reports with both events, is concurrent presentation more common than ordered?
        - Claim: Among Janssen reports with both events, concurrent presentation is more common than ordered.
    - **Media**
        - Q: After Janssen, are Chills and Pyrexia more often together than in order?
        - Claim: After Janssen, Chills and Pyrexia are more often together than in order.
    - **Clinical**
        - Q: In Janssen recipients with both, is concurrence more common than sequential onset?
        - Claim: In Janssen recipients with both, concurrence is more common than sequential onset.

## C-M1  (pairwise, multi, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 218/232 (94.0%) fail)
- **Qualified cores**: 232 viable | 89 supported-capable (true cases) | 143 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Moderna vs Janssen
- **Conditioned counts**: k=70 / n=137  |  cohort2 k=77 / n=196  (rate 0.5109)
- **Categorical test**: Fisher exact (2x2) (two-sided), p = 0.03398 (significant)
    - *H0: the Fatigue/Headache co-occurrence rate is equal for Moderna and Janssen (p1 = p2)*
    - *how p is computed*: Fisher exact on the 2x2 -- ONE-SIDED toward the higher-rate cohort for the directional multi_dir_* claims, TWO-SIDED for the multi_differ_* "do they differ" claims
- **Position-based test**: Mann-Whitney U (|level(Fatigue)-level(Headache)| between Moderna/Janssen; n=137/196), p = 0.0297
    - *H0: Moderna and Janssen draw |level(Fatigue)-level(Headache)| from the same distribution (no cohort difference in rank-distance)*
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [0.0098, 0.2234], effect size 0.2379
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: Does the Fatigue-Headache co-occurrence rate differ between Moderna and Janssen?
        - Claim: The Fatigue-Headache co-occurrence rate differs between Moderna and Janssen.
    - **Research**
        - Q: Among reports with both events, is the co-occurrence proportion different between Moderna and Janssen?
        - Claim: The co-occurrence proportion differs between Moderna and Janssen.
    - **Media**
        - Q: Is there a real difference between Moderna and Janssen in how often Fatigue and Headache happen together?
        - Claim: Moderna and Janssen differ in how often Fatigue and Headache happen together.
    - **Clinical**
        - Q: Do my Moderna and Janssen patients differ in how often Fatigue and Headache co-occur?
        - Claim: Moderna and Janssen recipients differ in Fatigue-Headache co-occurrence rates.

## C-M2  (pairwise, multi, CHOICE)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 209/232 (90.1%) fail)
- **Qualified cores**: 232 viable | 232 supported-capable (true cases) | 232 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Moderna vs Janssen
- **Conditioned counts**: k=70 / n=137  |  cohort2 k=77 / n=196  (rate 0.5109)
- **Categorical test**: Fisher exact (2x2) (one-sided, greater), p = 0.02154 (significant)
    - *H0: the Fatigue/Headache co-occurrence rate is equal for Moderna and Janssen (p1 = p2)*
    - *how p is computed*: Fisher exact on the 2x2 -- ONE-SIDED toward the higher-rate cohort for the directional multi_dir_* claims, TWO-SIDED for the multi_differ_* "do they differ" claims
- **Position-based test**: Mann-Whitney U (|level(Fatigue)-level(Headache)| between Moderna/Janssen; n=137/196), p = 0.0297
    - *H0: Moderna and Janssen draw |level(Fatigue)-level(Headache)| from the same distribution (no cohort difference in rank-distance)*
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [0.0098, 0.2234], effect size 0.2379
- **Options**: ['Moderna', 'Janssen']  ->  correct: **Moderna**
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: After which vaccine, Moderna or Janssen, do Fatigue and Headache more often co-occur?
        - Claim: Fatigue and Headache co-occur more often after Moderna than after Janssen.
    - **Research**
        - Q: Between Moderna and Janssen, which cohort shows higher Fatigue-Headache co-occurrence?
        - Claim: Moderna shows higher Fatigue-Headache co-occurrence than Janssen.
    - **Media**
        - Q: Is Fatigue and Headache together more common after Moderna or Janssen?
        - Claim: Fatigue and Headache together is more common after Moderna than Janssen.
    - **Clinical**
        - Q: In which group are Fatigue and Headache more often concurrent, Moderna or Janssen?
        - Claim: In Moderna recipients, Fatigue and Headache are more often concurrent.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: After which vaccine, Janssen or Moderna, do Fatigue and Headache more often co-occur?
        - Claim: Fatigue and Headache co-occur more often after Janssen than after Moderna.
    - **Research**
        - Q: Between Janssen and Moderna, which cohort shows higher Fatigue-Headache co-occurrence?
        - Claim: Janssen shows higher Fatigue-Headache co-occurrence than Moderna.
    - **Media**
        - Q: Is Fatigue and Headache together more common after Janssen or Moderna?
        - Claim: Fatigue and Headache together is more common after Janssen than Moderna.
    - **Clinical**
        - Q: In which group are Fatigue and Headache more often concurrent, Janssen or Moderna?
        - Claim: In Janssen recipients, Fatigue and Headache are more often concurrent.

## S-R1  (sequence, report, BOOL)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 3166 viable | 489 supported-capable (true cases) | 3166 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain', 'Asthenia'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Categorical test**: none (report-level: single observation, no sampling distribution)
    - *H0: none -- single deterministic observation, no sampling distribution*
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: Do Dizziness, Injection site pain, Asthenia occur in the order Dizziness → Injection site pain → Asthenia in report VAERS-916915?
        - Claim: In report VAERS-916915, Dizziness, Injection site pain, Asthenia occur in the order Dizziness → Injection site pain → Asthenia.
    - **Research**
        - Q: In this report, is the observed ordering of Dizziness, Injection site pain, Asthenia exactly Dizziness → Injection site pain → Asthenia?
        - Claim: In this report, the observed ordering is Dizziness → Injection site pain → Asthenia.
    - **Media**
        - Q: In this case, did things go Dizziness, then Injection site pain, then Asthenia?
        - Claim: In this case, the progression was Dizziness, then Injection site pain, then Asthenia.
    - **Clinical**
        - Q: Did this patient progress Dizziness, then Injection site pain, then Asthenia?
        - Claim: This patient progressed Dizziness → Injection site pain → Asthenia.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: Do Asthenia, Injection site pain, Dizziness occur in the order Asthenia → Injection site pain → Dizziness in report VAERS-916915?
        - Claim: In report VAERS-916915, Asthenia, Injection site pain, Dizziness occur in the order Asthenia → Injection site pain → Dizziness.
    - **Research**
        - Q: In this report, is the observed ordering of Asthenia, Injection site pain, Dizziness exactly Asthenia → Injection site pain → Dizziness?
        - Claim: In this report, the observed ordering is Asthenia → Injection site pain → Dizziness.
    - **Media**
        - Q: In this case, did things go Asthenia, then Injection site pain, then Dizziness?
        - Claim: In this case, the progression was Asthenia, then Injection site pain, then Dizziness.
    - **Clinical**
        - Q: Did this patient progress Asthenia, then Injection site pain, then Dizziness?
        - Claim: This patient progressed Asthenia → Injection site pain → Dizziness.

## S-V1  (sequence, vaccine, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 188/192 (97.9%) fail)
- **Qualified cores**: 275 viable | 192 supported-capable (true cases) | 192 refuted-capable
- **Core**: events ['Fatigue', 'Nausea', 'Vomiting'], cohort Janssen
- **Conditioned counts**: k=7 / n=8  (rate 0.875)
- **Categorical test**: modal-vs-runner-up binomial (one-sided, greater), p = 0.03516 (significant)
    - *H0: the Fatigue -> Nausea -> Vomiting ordering and the runner-up ordering are equally frequent (P = 0.5; no unique mode)*
    - *how p is computed*: modal-vs-runner-up -- one-sided exact binomial of the modal cell's count vs the runner-up's (null 0.5): is the named most-common ordering/event significantly ahead of its nearest competitor? (verifies the mode, which GOF-vs-uniform cannot)
- **Position-based test**: Friedman (Q=8.78 df=2; n=22 reports), p = 0.0124
    - *H0: Fatigue, Nausea, Vomiting share one within-report rank distribution (no systematic ordering)*
    - *how p is computed*: Friedman -- rank the three events within each report (ties averaged), chi-square (df=2) on the rank sums
- **95% CI**: [0.5291, 0.9776], effect size 1.5778
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, is Nausea → Vomiting → Fatigue the most common ordering of Nausea, Vomiting, Fatigue?
        - Claim: After Janssen, Nausea → Vomiting → Fatigue is the most common ordering of Nausea, Vomiting, Fatigue.
    - **Research**
        - Q: In Janssen reports with all three events, is Nausea → Vomiting → Fatigue the single most frequent ordering?
        - Claim: In Janssen reports with all three, Nausea → Vomiting → Fatigue is the single most frequent ordering.
    - **Media**
        - Q: After Janssen, is Nausea, then Vomiting, then Fatigue the most common order?
        - Claim: After Janssen, Nausea, then Vomiting, then Fatigue is the most common order.
    - **Clinical**
        - Q: In Janssen recipients with all three, is Nausea → Vomiting → Fatigue the most frequent progression?
        - Claim: In Janssen recipients with all three, Nausea → Vomiting → Fatigue is the most frequent progression.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, is Fatigue → Nausea → Vomiting the most common ordering of Fatigue, Nausea, Vomiting?
        - Claim: After Janssen, Fatigue → Nausea → Vomiting is the most common ordering of Fatigue, Nausea, Vomiting.
    - **Research**
        - Q: In Janssen reports with all three events, is Fatigue → Nausea → Vomiting the single most frequent ordering?
        - Claim: In Janssen reports with all three, Fatigue → Nausea → Vomiting is the single most frequent ordering.
    - **Media**
        - Q: After Janssen, is Fatigue, then Nausea, then Vomiting the most common order?
        - Claim: After Janssen, Fatigue, then Nausea, then Vomiting is the most common order.
    - **Clinical**
        - Q: In Janssen recipients with all three, is Fatigue → Nausea → Vomiting the most frequent progression?
        - Claim: In Janssen recipients with all three, Fatigue → Nausea → Vomiting is the most frequent progression.

## S-V3  (sequence, vaccine, CHOICE)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 180/192 (93.8%) fail)
- **Qualified cores**: 275 viable | 192 supported-capable (true cases) | 192 refuted-capable
- **Core**: events ['Fatigue', 'Headache', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=8 / n=25  (rate 0.32)
- **Categorical test**: multinomial GOF (exact), p = 0.03251 (significant)
    - *H0: the 6 orderings are equally likely -- uniform (no modal ordering)*
    - *how p is computed*: exact multinomial goodness-of-fit -- sum the multinomial probabilities of every table (same n) whose chi-square statistic vs uniform is >= the observed
- **Position-based test**: Friedman (Q=0.35 df=2; n=90 reports), p = 0.8412
    - *H0: Fatigue, Headache, Pyrexia share one within-report rank distribution (no systematic ordering)*
    - *how p is computed*: Friedman -- rank the three events within each report (ties averaged), chi-square (df=2) on the rank sums
- **95% CI**: [0.1721, 0.5159], effect size 0.3615
- **Options**: ['Fatigue → Headache → Pyrexia', 'Fatigue → Pyrexia → Headache', 'Headache → Fatigue → Pyrexia', 'Headache → Pyrexia → Fatigue', 'Pyrexia → Fatigue → Headache', 'Pyrexia → Headache → Fatigue']  ->  correct: **Headache → Pyrexia → Fatigue**
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, what is the most common ordering of Headache, Pyrexia, Fatigue?
        - Claim: After Janssen, the most common ordering of Headache, Pyrexia, Fatigue is Headache → Pyrexia → Fatigue.
    - **Research**
        - Q: Among Janssen reports with all three events, what is the modal ordering of Headache, Pyrexia, Fatigue?
        - Claim: Among Janssen reports with all three, the modal ordering is Headache → Pyrexia → Fatigue.
    - **Media**
        - Q: After Janssen, what's the most common order people experience Headache, Pyrexia, and Fatigue?
        - Claim: After Janssen, the most common order is Headache → Pyrexia → Fatigue.
    - **Clinical**
        - Q: What's the most common progression of Headache, Pyrexia, Fatigue in Janssen patients?
        - Claim: The most common progression in Janssen patients is Headache → Pyrexia → Fatigue.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, what is the most common ordering of Fatigue, Pyrexia, Headache?
        - Claim: After Janssen, the most common ordering of Fatigue, Pyrexia, Headache is Fatigue → Pyrexia → Headache.
    - **Research**
        - Q: Among Janssen reports with all three events, what is the modal ordering of Fatigue, Pyrexia, Headache?
        - Claim: Among Janssen reports with all three, the modal ordering is Fatigue → Pyrexia → Headache.
    - **Media**
        - Q: After Janssen, what's the most common order people experience Fatigue, Pyrexia, and Headache?
        - Claim: After Janssen, the most common order is Fatigue → Pyrexia → Headache.
    - **Clinical**
        - Q: What's the most common progression of Fatigue, Pyrexia, Headache in Janssen patients?
        - Claim: The most common progression in Janssen patients is Fatigue → Pyrexia → Headache.

## S-V4  (sequence, vaccine, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 225/236 (95.3%) fail)
- **Qualified cores**: 275 viable | 62 supported-capable (true cases) | 174 refuted-capable
- **Core**: events ['Headache', 'Hyperhidrosis', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=7 / n=13  (rate 0.5385)
- **Categorical test**: multinomial GOF (exact), p = 0.01523 (significant)
    - *H0: the 6 orderings are equally likely -- uniform (no consistent ordering)*
    - *how p is computed*: exact multinomial goodness-of-fit -- sum the multinomial probabilities of every table (same n) whose chi-square statistic vs uniform is >= the observed
- **Position-based test**: Kendall's W (W=0.184; n=33 reports), p = 0.002276
    - *H0: no agreement in the event rankings across reports (W = 0, orderings unrelated report-to-report)*
    - *how p is computed*: Kendall's W -- normalised concordance (0..1) of the within-report rankings; p from chi-square on n(k-1)W
- **95% CI**: [0.2914, 0.7679], effect size 0.8067
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, is the ordering of Headache, Hyperhidrosis, Pyrexia consistent across reports?
        - Claim: After Janssen, the ordering of Headache, Hyperhidrosis, Pyrexia is consistent across reports.
    - **Research**
        - Q: In Janssen reports with all three, does a single ordering dominate across cases?
        - Claim: In Janssen reports with all three, a single ordering of Headache, Hyperhidrosis, Pyrexia dominates.
    - **Media**
        - Q: After Janssen, do people usually experience Headache, Hyperhidrosis, Pyrexia in the same order?
        - Claim: After Janssen, people usually experience Headache, Hyperhidrosis, Pyrexia in the same order.
    - **Clinical**
        - Q: In Janssen patients, is the progression of Headache, Hyperhidrosis, Pyrexia consistent across cases?
        - Claim: In Janssen patients, the progression of Headache, Hyperhidrosis, Pyrexia is consistent.

## S-M1  (sequence, multi, BOOL)
- **Presented example**: ✗ FAILED (gold-vs-significance over this template's cores: 90/90 (100.0%) fail)
- **Qualified cores**: 90 viable | 44 supported-capable (true cases) | 46 refuted-capable
- **Core**: events ['Fatigue', 'Headache', 'Pain'], cohort Moderna vs Janssen
- **Conditioned counts**: k=1 / n=13  |  cohort2 k=7 / n=18  (rate 0.0769)
- **⚠ P-VALUE vs GOLD MISMATCH** (red in the LaTeX findings): type1 (gold set but the test is not significant)
- **Categorical test**: Fisher exact (2x2) (two-sided), p = 0.09535 (not significant)
    - *H0: P(ordering = Fatigue -> Headache -> Pain) is equal for Moderna and Janssen (p1 = p2)*
    - *how p is computed*: Fisher exact on the 2x2 -- ONE-SIDED toward the higher-rate cohort for the directional multi_dir_* claims, TWO-SIDED for the multi_differ_* "do they differ" claims
- **Position-based test**: Mann-Whitney U (per event) (Fatigue's within-triple rank between Moderna/Janssen; n=48/81), p = 0.7497
    - *H0: Fatigue's within-triple rank has the same distribution for Moderna and Janssen*
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [-0.5456, 0.0045], effect size -0.7846
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: Does the Fatigue → Headache → Pain rate differ between Moderna and Janssen?
        - Claim: The Fatigue → Headache → Pain rate differs between Moderna and Janssen.
    - **Research**
        - Q: Among reports with all three events, is the Fatigue → Headache → Pain proportion different between Moderna and Janssen?
        - Claim: The Fatigue → Headache → Pain proportion differs between Moderna and Janssen.
    - **Media**
        - Q: Is there a real difference between Moderna and Janssen in how often things go Fatigue → Headache → Pain?
        - Claim: Moderna and Janssen differ in how often things go Fatigue → Headache → Pain.
    - **Clinical**
        - Q: Do Moderna and Janssen patients differ in how often they follow Fatigue → Headache → Pain?
        - Claim: Moderna and Janssen recipients differ in the Fatigue → Headache → Pain rate.

## S-M2  (sequence, multi, CHOICE)
- **Presented example**: ✗ FAILED (gold-vs-significance over this template's cores: 75/75 (100.0%) fail)
- **Qualified cores**: 90 viable | 75 supported-capable (true cases) | 75 refuted-capable
- **Core**: events ['Fatigue', 'Headache', 'Pain'], cohort Moderna vs Janssen
- **Conditioned counts**: k=1 / n=13  |  cohort2 k=7 / n=18  (rate 0.0769)
- **⚠ P-VALUE vs GOLD MISMATCH** (red in the LaTeX findings): type1 (gold set but the test is not significant)
- **Categorical test**: Fisher exact (2x2) (one-sided, less), p = 0.05799 (not significant)
    - *H0: P(ordering = Fatigue -> Headache -> Pain) is equal for Moderna and Janssen (p1 = p2)*
    - *how p is computed*: Fisher exact on the 2x2 -- ONE-SIDED toward the higher-rate cohort for the directional multi_dir_* claims, TWO-SIDED for the multi_differ_* "do they differ" claims
- **Position-based test**: Mann-Whitney U (per event) (Fatigue's within-triple rank between Moderna/Janssen; n=48/81), p = 0.7497
    - *H0: Fatigue's within-triple rank has the same distribution for Moderna and Janssen*
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [-0.5456, 0.0045], effect size -0.7846
- **Options**: ['Moderna', 'Janssen']  ->  correct: **Janssen**
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: Is the sequence Fatigue → Headache → Pain more common after Janssen or Moderna?
        - Claim: The sequence Fatigue → Headache → Pain is more common after Janssen than Moderna.
    - **Research**
        - Q: Between Janssen and Moderna, which cohort shows a higher proportion of Fatigue → Headache → Pain?
        - Claim: Janssen shows a higher proportion of Fatigue → Headache → Pain than Moderna.
    - **Media**
        - Q: Is Fatigue → Headache → Pain more common after Janssen or Moderna?
        - Claim: Fatigue → Headache → Pain is more common after Janssen than Moderna.
    - **Clinical**
        - Q: In which group is Fatigue → Headache → Pain more common, Janssen or Moderna recipients?
        - Claim: Fatigue → Headache → Pain is more common in Janssen recipients.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: Is the sequence Fatigue → Headache → Pain more common after Moderna or Janssen?
        - Claim: The sequence Fatigue → Headache → Pain is more common after Moderna than Janssen.
    - **Research**
        - Q: Between Moderna and Janssen, which cohort shows a higher proportion of Fatigue → Headache → Pain?
        - Claim: Moderna shows a higher proportion of Fatigue → Headache → Pain than Janssen.
    - **Media**
        - Q: Is Fatigue → Headache → Pain more common after Moderna or Janssen?
        - Claim: Fatigue → Headache → Pain is more common after Moderna than Janssen.
    - **Clinical**
        - Q: In which group is Fatigue → Headache → Pain more common, Moderna or Janssen recipients?
        - Claim: Fatigue → Headache → Pain is more common in Moderna recipients.

## S-M3  (sequence, multi, BOOL)
- **Presented example**: ✗ FAILED (gold-vs-significance over this template's cores: 90/90 (100.0%) fail)
- **Qualified cores**: 90 viable | 25 supported-capable (true cases) | 65 refuted-capable
- **Core**: events ['Fatigue', 'Pain', 'Pyrexia'], cohort Moderna vs Janssen
- **Conditioned counts**: k=5 / n=12  |  cohort2 k=6 / n=15  (rate 0.4167)
- **⚠ P-VALUE vs GOLD MISMATCH** (red in the LaTeX findings): type1 (gold set but the test is not significant)
- **Categorical test**: Fisher-Freeman-Halton (exact), p = 0.2482 (not significant)
    - *H0: Moderna and Janssen have the same ordering distribution (homogeneity)*
    - *how p is computed*: Fisher-Freeman-Halton -- sum the probabilities of every 2xk table with the observed margins that are <= the observed table's
- **Position-based test**: Mann-Whitney U (per event) (Fatigue's within-triple rank between Moderna/Janssen; n=39/65), p = 0.6701
    - *H0: Fatigue's within-triple rank has the same distribution for Moderna and Janssen*
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: Is the typical ordering of Fatigue, Pain, Pyrexia the same after Moderna and Janssen?
        - Claim: The typical ordering of Fatigue, Pain, Pyrexia is the same after Moderna and Janssen.
    - **Research**
        - Q: Is the modal ordering of Fatigue, Pain, Pyrexia the same between Moderna and Janssen cohorts?
        - Claim: The modal ordering of Fatigue, Pain, Pyrexia is the same in Moderna and Janssen cohorts.
    - **Media**
        - Q: Do Moderna and Janssen produce the same typical order of Fatigue, Pain, Pyrexia?
        - Claim: Moderna and Janssen produce the same typical order of Fatigue, Pain, Pyrexia.
    - **Clinical**
        - Q: Is the typical progression of Fatigue, Pain, Pyrexia the same in Moderna and Janssen recipients?
        - Claim: The typical progression of Fatigue, Pain, Pyrexia is the same in Moderna and Janssen recipients.

## F-R1  (first_last, report, CHOICE)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 3166 viable | 1196 supported-capable (true cases) | 3166 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain', 'Asthenia'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Categorical test**: none (report-level: single observation, no sampling distribution)
    - *H0: none -- single deterministic observation, no sampling distribution*
- **Options**: ['Dizziness', 'Injection site pain', 'Asthenia']  ->  correct: **Dizziness**
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: In report VAERS-916915, which of Dizziness, Injection site pain, Asthenia occurs first?
        - Claim: In report VAERS-916915, Dizziness occurs first among Dizziness, Injection site pain, Asthenia.
    - **Research**
        - Q: Of Dizziness, Injection site pain, Asthenia, which is the earliest event in this report?
        - Claim: In this report, Dizziness is the earliest of Dizziness, Injection site pain, Asthenia.
    - **Media**
        - Q: In this case, which came first, Dizziness, Injection site pain, or Asthenia?
        - Claim: In this case, Dizziness came first.
    - **Clinical**
        - Q: Of Dizziness, Injection site pain, Asthenia, which appeared first in this patient?
        - Claim: In this patient, Dizziness appeared first.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: In report VAERS-916915, which of Injection site pain, Dizziness, Asthenia occurs first?
        - Claim: In report VAERS-916915, Injection site pain occurs first among Injection site pain, Dizziness, Asthenia.
    - **Research**
        - Q: Of Injection site pain, Dizziness, Asthenia, which is the earliest event in this report?
        - Claim: In this report, Injection site pain is the earliest of Injection site pain, Dizziness, Asthenia.
    - **Media**
        - Q: In this case, which came first, Injection site pain, Dizziness, or Asthenia?
        - Claim: In this case, Injection site pain came first.
    - **Clinical**
        - Q: Of Injection site pain, Dizziness, Asthenia, which appeared first in this patient?
        - Claim: In this patient, Injection site pain appeared first.

## F-R2  (first_last, report, CHOICE)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 3166 viable | 1299 supported-capable (true cases) | 3166 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain', 'Asthenia'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Categorical test**: none (report-level: single observation, no sampling distribution)
    - *H0: none -- single deterministic observation, no sampling distribution*
- **Options**: ['Dizziness', 'Injection site pain', 'Asthenia']  ->  correct: **Asthenia**
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: In report VAERS-916915, which of Asthenia, Dizziness, Injection site pain occurs last?
        - Claim: In report VAERS-916915, Injection site pain occurs last among Asthenia, Dizziness, Injection site pain.
    - **Research**
        - Q: Of Asthenia, Dizziness, Injection site pain, which is the latest event in this report?
        - Claim: In this report, Injection site pain is the latest of Asthenia, Dizziness, Injection site pain.
    - **Media**
        - Q: In this case, which came last, Asthenia, Dizziness, or Injection site pain?
        - Claim: In this case, Injection site pain came last.
    - **Clinical**
        - Q: Of Asthenia, Dizziness, Injection site pain, which appeared last in this patient?
        - Claim: In this patient, Injection site pain appeared last.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: In report VAERS-916915, which of Dizziness, Injection site pain, Asthenia occurs last?
        - Claim: In report VAERS-916915, Asthenia occurs last among Dizziness, Injection site pain, Asthenia.
    - **Research**
        - Q: Of Dizziness, Injection site pain, Asthenia, which is the latest event in this report?
        - Claim: In this report, Asthenia is the latest of Dizziness, Injection site pain, Asthenia.
    - **Media**
        - Q: In this case, which came last, Dizziness, Injection site pain, or Asthenia?
        - Claim: In this case, Asthenia came last.
    - **Clinical**
        - Q: Of Dizziness, Injection site pain, Asthenia, which appeared last in this patient?
        - Claim: In this patient, Asthenia appeared last.

## F-R3  (first_last, report, BOOL)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 3166 viable | 1196 supported-capable (true cases) | 1196 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain', 'Asthenia'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Categorical test**: none (report-level: single observation, no sampling distribution)
    - *H0: none -- single deterministic observation, no sampling distribution*
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: In report VAERS-916915, is Dizziness the first of Dizziness, Injection site pain, Asthenia to occur?
        - Claim: In report VAERS-916915, Dizziness is the first of Dizziness, Injection site pain, Asthenia to occur.
    - **Research**
        - Q: In this report, is Dizziness the earliest of Dizziness, Injection site pain, Asthenia?
        - Claim: In this report, Dizziness is the earliest of Dizziness, Injection site pain, Asthenia.
    - **Media**
        - Q: In this case, did Dizziness come first among Dizziness, Injection site pain, Asthenia?
        - Claim: In this case, Dizziness came first among Dizziness, Injection site pain, Asthenia.
    - **Clinical**
        - Q: Did Dizziness appear first among Dizziness, Injection site pain, Asthenia in this patient?
        - Claim: In this patient, Dizziness appeared first among Dizziness, Injection site pain, Asthenia.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: In report VAERS-916915, is Injection site pain the first of Injection site pain, Dizziness, Asthenia to occur?
        - Claim: In report VAERS-916915, Injection site pain is the first of Injection site pain, Dizziness, Asthenia to occur.
    - **Research**
        - Q: In this report, is Injection site pain the earliest of Injection site pain, Dizziness, Asthenia?
        - Claim: In this report, Injection site pain is the earliest of Injection site pain, Dizziness, Asthenia.
    - **Media**
        - Q: In this case, did Injection site pain come first among Injection site pain, Dizziness, Asthenia?
        - Claim: In this case, Injection site pain came first among Injection site pain, Dizziness, Asthenia.
    - **Clinical**
        - Q: Did Injection site pain appear first among Injection site pain, Dizziness, Asthenia in this patient?
        - Claim: In this patient, Injection site pain appeared first among Injection site pain, Dizziness, Asthenia.

## F-V1  (first_last, vaccine, CHOICE)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 42/67 (62.7%) fail)
- **Qualified cores**: 82 viable | 67 supported-capable (true cases) | 82 refuted-capable
- **Core**: events ['Chills', 'Headache', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=22 / n=116  (rate 0.1897)
- **Categorical test**: multinomial GOF (chi-square), p = 0.0002104 (significant)
    - *H0: the 3 candidates are equally likely to be first -- uniform*
    - *how p is computed*: chi-square goodness-of-fit vs uniform (large-n approximation, used only when every expected cell >= 5)
- **Position-based test**: Friedman (Q=13.05 df=2; n=116 reports), p = 0.001469
    - *H0: Chills, Headache, Pyrexia share one within-report rank distribution (no systematic ordering)*
    - *how p is computed*: Friedman -- rank the three events within each report (ties averaged), chi-square (df=2) on the rank sums
- **95% CI**: [0.1287, 0.2705], effect size -0.3298
- **Options**: ['Chills', 'Headache', 'Pyrexia']  ->  correct: **Headache**
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, which of Headache, Chills, Pyrexia typically occurs first?
        - Claim: After Janssen, Headache typically occurs first among Headache, Chills, Pyrexia.
    - **Research**
        - Q: In Janssen reports with all three, which event is the typical earliest among Headache, Chills, Pyrexia?
        - Claim: In Janssen reports with all three, Headache is typically the earliest.
    - **Media**
        - Q: After Janssen, which usually comes first, Headache, Chills, or Pyrexia?
        - Claim: After Janssen, Headache usually comes first.
    - **Clinical**
        - Q: In Janssen patients, which of Headache, Chills, Pyrexia typically appears first?
        - Claim: In Janssen patients, Headache typically appears first.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, which of Pyrexia, Chills, Headache typically occurs first?
        - Claim: After Janssen, Pyrexia typically occurs first among Pyrexia, Chills, Headache.
    - **Research**
        - Q: In Janssen reports with all three, which event is the typical earliest among Pyrexia, Chills, Headache?
        - Claim: In Janssen reports with all three, Pyrexia is typically the earliest.
    - **Media**
        - Q: After Janssen, which usually comes first, Pyrexia, Chills, or Headache?
        - Claim: After Janssen, Pyrexia usually comes first.
    - **Clinical**
        - Q: In Janssen patients, which of Pyrexia, Chills, Headache typically appears first?
        - Claim: In Janssen patients, Pyrexia typically appears first.

## F-V2  (first_last, vaccine, CHOICE)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 36/73 (49.3%) fail)
- **Qualified cores**: 82 viable | 73 supported-capable (true cases) | 82 refuted-capable
- **Core**: events ['Chills', 'Headache', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=28 / n=116  (rate 0.2414)
- **Categorical test**: multinomial GOF (chi-square), p = 0.0001234 (significant)
    - *H0: the 3 candidates are equally likely to be last -- uniform*
    - *how p is computed*: chi-square goodness-of-fit vs uniform (large-n approximation, used only when every expected cell >= 5)
- **Position-based test**: Friedman (Q=13.05 df=2; n=116 reports), p = 0.001469
    - *H0: Chills, Headache, Pyrexia share one within-report rank distribution (no systematic ordering)*
    - *how p is computed*: Friedman -- rank the three events within each report (ties averaged), chi-square (df=2) on the rank sums
- **95% CI**: [0.1726, 0.3267], effect size -0.2038
- **Options**: ['Chills', 'Headache', 'Pyrexia']  ->  correct: **Headache**
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, which of Headache, Chills, Pyrexia typically occurs last?
        - Claim: After Janssen, Pyrexia typically occurs last among Headache, Chills, Pyrexia.
    - **Research**
        - Q: In Janssen reports with all three, which is the typical latest among Headache, Chills, Pyrexia?
        - Claim: In Janssen reports with all three, Pyrexia is typically the latest.
    - **Media**
        - Q: After Janssen, which usually comes last, Headache, Chills, or Pyrexia?
        - Claim: After Janssen, Pyrexia usually comes last.
    - **Clinical**
        - Q: In Janssen patients, which of Headache, Chills, Pyrexia typically appears last?
        - Claim: In Janssen patients, Pyrexia typically appears last.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, which of Chills, Headache, Pyrexia typically occurs last?
        - Claim: After Janssen, Pyrexia typically occurs last among Chills, Headache, Pyrexia.
    - **Research**
        - Q: In Janssen reports with all three, which is the typical latest among Chills, Headache, Pyrexia?
        - Claim: In Janssen reports with all three, Pyrexia is typically the latest.
    - **Media**
        - Q: After Janssen, which usually comes last, Chills, Headache, or Pyrexia?
        - Claim: After Janssen, Pyrexia usually comes last.
    - **Clinical**
        - Q: In Janssen patients, which of Chills, Headache, Pyrexia typically appears last?
        - Claim: In Janssen patients, Pyrexia typically appears last.

## F-V3  (first_last, vaccine, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 53/67 (79.1%) fail)
- **Qualified cores**: 82 viable | 67 supported-capable (true cases) | 82 refuted-capable
- **Core**: events ['Chills', 'Headache', 'Nausea'], cohort Janssen
- **Conditioned counts**: k=17 / n=64  (rate 0.2656)
- **Categorical test**: modal-vs-runner-up binomial (one-sided, greater), p = 0.03196 (significant)
    - *H0: Chills and the runner-up event are equally often the first (P = 0.5; no unique most-common first event)*
    - *how p is computed*: modal-vs-runner-up -- one-sided exact binomial of the modal cell's count vs the runner-up's (null 0.5): is the named most-common ordering/event significantly ahead of its nearest competitor? (verifies the mode, which GOF-vs-uniform cannot)
- **Position-based test**: Friedman (Q=7.40 df=2; n=64 reports), p = 0.02477
    - *H0: Chills, Headache, Nausea share one within-report rank distribution (no systematic ordering)*
    - *how p is computed*: Friedman -- rank the three events within each report (ties averaged), chi-square (df=2) on the rank sums
- **95% CI**: [0.173, 0.3848], effect size -0.148
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, is Chills the most common first event among Chills, Headache, Nausea?
        - Claim: After Janssen, Chills is the most common first event among Chills, Headache, Nausea.
    - **Research**
        - Q: In Janssen reports with all three, is Chills the single most frequent earliest event?
        - Claim: In Janssen reports with all three, Chills is the single most frequent earliest event.
    - **Media**
        - Q: After Janssen, is Chills most often the first among Chills, Headache, Nausea?
        - Claim: After Janssen, Chills is most often the first among Chills, Headache, Nausea.
    - **Clinical**
        - Q: In Janssen patients, is Chills the most frequent earliest of Chills, Headache, Nausea?
        - Claim: In Janssen patients, Chills is the most frequent earliest of Chills, Headache, Nausea.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: After Janssen, is Headache the most common first event among Headache, Chills, Nausea?
        - Claim: After Janssen, Headache is the most common first event among Headache, Chills, Nausea.
    - **Research**
        - Q: In Janssen reports with all three, is Headache the single most frequent earliest event?
        - Claim: In Janssen reports with all three, Headache is the single most frequent earliest event.
    - **Media**
        - Q: After Janssen, is Headache most often the first among Headache, Chills, Nausea?
        - Claim: After Janssen, Headache is most often the first among Headache, Chills, Nausea.
    - **Clinical**
        - Q: In Janssen patients, is Headache the most frequent earliest of Headache, Chills, Nausea?
        - Claim: In Janssen patients, Headache is the most frequent earliest of Headache, Chills, Nausea.

## F-M1  (first_last, multi, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 44/46 (95.7%) fail)
- **Qualified cores**: 46 viable | 23 supported-capable (true cases) | 23 refuted-capable
- **Core**: events ['Chills', 'Pain', 'Pyrexia'], cohort Pfizer vs Moderna
- **Conditioned counts**: k=7 / n=57  |  cohort2 k=None / n=52  (rate 0.1228)
- **Categorical test**: Fisher-Freeman-Halton (exact), p = 0.013 (significant)
    - *H0: Pfizer and Moderna have the same first-event distribution (homogeneity)*
    - *how p is computed*: Fisher-Freeman-Halton -- sum the probabilities of every 2xk table with the observed margins that are <= the observed table's
- **Position-based test**: Mann-Whitney U (per event) (Chills's within-triple rank between Pfizer/Moderna; n=57/52), p = 0.02167
    - *H0: Chills's within-triple rank has the same distribution for Pfizer and Moderna*
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: Is the typical first event among Chills, Pain, Pyrexia the same after Pfizer and Moderna?
        - Claim: The typical first event among Chills, Pain, Pyrexia is the same after Pfizer and Moderna.
    - **Research**
        - Q: Is the modal earliest event among Chills, Pain, Pyrexia the same between Pfizer and Moderna cohorts?
        - Claim: The modal earliest event is the same in Pfizer and Moderna cohorts.
    - **Media**
        - Q: Do Pfizer and Moderna have the same typical first event among Chills, Pain, Pyrexia?
        - Claim: Pfizer and Moderna have the same typical first event among Chills, Pain, Pyrexia.
    - **Clinical**
        - Q: Is the usual first event among Chills, Pain, Pyrexia the same in Pfizer and Moderna patients?
        - Claim: The usual first event is the same in Pfizer and Moderna patients.

## F-M2  (first_last, multi, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 44/46 (95.7%) fail)
- **Qualified cores**: 46 viable | 23 supported-capable (true cases) | 23 refuted-capable
- **Core**: events ['Chills', 'Pain', 'Pyrexia'], cohort Pfizer vs Moderna
- **Conditioned counts**: k=7 / n=57  |  cohort2 k=None / n=52  (rate 0.1228)
- **Categorical test**: Fisher-Freeman-Halton (exact), p = 0.013 (significant)
    - *H0: Pfizer and Moderna have the same first-event distribution (homogeneity)*
    - *how p is computed*: Fisher-Freeman-Halton -- sum the probabilities of every 2xk table with the observed margins that are <= the observed table's
- **Position-based test**: Mann-Whitney U (per event) (Chills's within-triple rank between Pfizer/Moderna; n=57/52), p = 0.02167
    - *H0: Chills's within-triple rank has the same distribution for Pfizer and Moderna*
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: Do Pfizer and Moderna differ in which of Chills, Pain, Pyrexia appears first?
        - Claim: Pfizer and Moderna differ in which of Chills, Pain, Pyrexia appears first.
    - **Research**
        - Q: Is the modal first event among Chills, Pain, Pyrexia different between Pfizer and Moderna?
        - Claim: The modal first event differs between Pfizer and Moderna.
    - **Media**
        - Q: Do Pfizer and Moderna differ in which of Chills, Pain, Pyrexia usually comes first?
        - Claim: Pfizer and Moderna differ in which usually comes first.
    - **Clinical**
        - Q: Does the usual first event among Chills, Pain, Pyrexia differ between Pfizer and Moderna patients?
        - Claim: The usual first event differs between Pfizer and Moderna patients.

## F-M3  (first_last, multi, CHOICE)
- **Presented example**: ✗ FAILED (gold-vs-significance over this template's cores: 45/45 (100.0%) fail)
- **Qualified cores**: 46 viable | 45 supported-capable (true cases) | 45 refuted-capable
- **Core**: events ['Chills', 'Headache', 'Pyrexia'], cohort Pfizer vs Moderna
- **Conditioned counts**: k=10 / n=67  |  cohort2 k=7 / n=60  (rate 0.1493)
- **⚠ P-VALUE vs GOLD MISMATCH** (red in the LaTeX findings): type1 (gold set but the test is not significant)
- **Categorical test**: Fisher exact (2x2) (one-sided, greater), p = 0.3924 (not significant)
    - *H0: the first-event rate is equal for Pfizer and Moderna (p1 = p2)*
    - *how p is computed*: Fisher exact on the 2x2 -- ONE-SIDED toward the higher-rate cohort for the directional multi_dir_* claims, TWO-SIDED for the multi_differ_* "do they differ" claims
- **Position-based test**: Mann-Whitney U (per event) (Chills's within-triple rank between Pfizer/Moderna; n=67/60), p = 0.7023
    - *H0: Chills's within-triple rank has the same distribution for Pfizer and Moderna*
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [-0.0916, 0.1523], effect size 0.0961
- **Options**: ['Pfizer', 'Moderna']  ->  correct: **Pfizer**
- **SUPPORTED** example (filled, all registers):
    - **Original**
        - Q: Is Headache the first event more often after Pfizer or Moderna?
        - Claim: Headache is the first event more often after Pfizer than Moderna.
    - **Research**
        - Q: Between Pfizer and Moderna, which cohort more often has Headache as the earliest of Headache, Chills, Pyrexia?
        - Claim: Pfizer more often has Headache as the earliest of Headache, Chills, Pyrexia.
    - **Media**
        - Q: Is Headache the first event more often after Pfizer or Moderna?
        - Claim: Headache is the first event more often after Pfizer than Moderna.
    - **Clinical**
        - Q: In which group is Headache more often the first of Headache, Chills, Pyrexia, Pfizer or Moderna?
        - Claim: In Pfizer recipients, Headache is more often the first.
- **REFUTED** example (filled, all registers):
    - **Original**
        - Q: Is Headache the first event more often after Moderna or Pfizer?
        - Claim: Headache is the first event more often after Moderna than Pfizer.
    - **Research**
        - Q: Between Moderna and Pfizer, which cohort more often has Headache as the earliest of Headache, Chills, Pyrexia?
        - Claim: Moderna more often has Headache as the earliest of Headache, Chills, Pyrexia.
    - **Media**
        - Q: Is Headache the first event more often after Moderna or Pfizer?
        - Claim: Headache is the first event more often after Moderna than Pfizer.
    - **Clinical**
        - Q: In which group is Headache more often the first of Headache, Chills, Pyrexia, Moderna or Pfizer?
        - Claim: In Moderna recipients, Headache is more often the first.

## Statistical methods (how each p-value is computed)

- **Binomial exact**: exact binomial vs the 1/2 chance null (pairwise precedes, co-occurs), ONE-SIDED in the observed direction (greater if the rate is above 0.5, less if below) so it corroborates the observed verdict, not the reverse
- **Modal-vs-runner-up binomial**: modal-vs-runner-up -- one-sided exact binomial of the modal cell's count vs the runner-up's (null 0.5): is the named most-common ordering/event significantly ahead of its nearest competitor? (verifies the mode, which GOF-vs-uniform cannot)
- **Fisher exact**: Fisher exact on the 2x2 -- ONE-SIDED toward the higher-rate cohort for the directional multi_dir_* claims, TWO-SIDED for the multi_differ_* "do they differ" claims
- **Multinomial GOF (exact)**: exact multinomial goodness-of-fit -- sum the multinomial probabilities of every table (same n) whose chi-square statistic vs uniform is >= the observed
- **Multinomial GOF (chi-square)**: chi-square goodness-of-fit vs uniform (large-n approximation, used only when every expected cell >= 5)
- **Fisher-Freeman-Halton**: Fisher-Freeman-Halton -- sum the probabilities of every 2xk table with the observed margins that are <= the observed table's
- **Homogeneity (chi-square)**: chi-square test of homogeneity (used only when every expected cell >= 5)
- **Wilcoxon signed-rank**: Wilcoxon signed-rank -- rank |d| where d=level(A)-level(B) (co-exist d=0 dropped), sum the signed ranks; exact sign-flip null for small n, else normal approximation with tie/continuity correction
- **Mann-Whitney U**: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **Friedman**: Friedman -- rank the three events within each report (ties averaged), chi-square (df=2) on the rank sums
- **Kendall's W**: Kendall's W -- normalised concordance (0..1) of the within-report rankings; p from chi-square on n(k-1)W


## Fail-case examples per template (why the gold label is not significant)

For each testable group, up to 10 failing cores -- a **definite** gold verdict (supported/refuted) that the categorical test does **not** corroborate at alpha=0.05 -- laddered from closest-to-significant (lowest p) to no-effect (highest p) so the range of failure modes is visible. *Processed* = the group's definite categorical cores; *failed* = those the test can't corroborate. Report-level and PROP groups carry no categorical test, so they process 0 cores and have no fail cases.

### P-R1 — 0 processed (no categorical test: BOOL/report)

### P-R2 — 0 processed (no categorical test: CHOICE/report)

### P-V1 — 168 processed, 81 failed (81/168 (48.2%)); median n 29, median p 0.2307
*Tested against — H0: P(Fatigue precedes Headache) = 0.5 (no directional preference among ordered reports)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Chills, Pain in extremity | Janssen | 29/46 | 0.052 | effect too weak (rate 0.63 vs null 0.50, n=46) |
| 2 | Chills, Pain in extremity | Pfizer | 8/24 | 0.076 | effect too weak (rate 0.33 vs null 0.50, n=24) |
| 3 | Dizziness, Nausea | Pfizer | 21/34 | 0.115 | effect too weak (rate 0.62 vs null 0.50, n=34) |
| 4 | Dizziness, Fatigue | Janssen | 31/54 | 0.170 | effect too weak (rate 0.57 vs null 0.50, n=54) |
| 5 | Dizziness, Fatigue | Moderna | 11/27 | 0.221 | effect too weak (rate 0.41 vs null 0.50, n=27) |
| 6 | Nausea, Pain | Janssen | 26/58 | 0.256 | effect too weak (rate 0.45 vs null 0.50, n=58) |
| 7 | Dizziness, Nausea | Moderna | 12/21 | 0.332 | effect too weak (rate 0.57 vs null 0.50, n=21) |
| 8 | Pain, Pyrexia | Pfizer | 16/35 | 0.368 | effect too weak (rate 0.46 vs null 0.50, n=35) |
| 9 | Headache, Pain in extremity | Janssen | 39/80 | 0.456 | effect too weak (rate 0.49 vs null 0.50, n=80) |
| 10 | Fatigue, Pyrexia | Moderna | 26/53 | 0.500 | effect too weak (rate 0.49 vs null 0.50, n=53) |

### P-V3 — 168 processed, 81 failed (81/168 (48.2%)); median n 29, median p 0.2307
*Tested against — H0: P(Fatigue precedes Headache) = 0.5 (no directional preference among ordered reports)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Chills, Pain in extremity | Janssen | 29/46 | 0.052 | effect too weak (rate 0.63 vs null 0.50, n=46) |
| 2 | Chills, Pain in extremity | Pfizer | 8/24 | 0.076 | effect too weak (rate 0.33 vs null 0.50, n=24) |
| 3 | Dizziness, Nausea | Pfizer | 21/34 | 0.115 | effect too weak (rate 0.62 vs null 0.50, n=34) |
| 4 | Dizziness, Fatigue | Janssen | 31/54 | 0.170 | effect too weak (rate 0.57 vs null 0.50, n=54) |
| 5 | Dizziness, Fatigue | Moderna | 11/27 | 0.221 | effect too weak (rate 0.41 vs null 0.50, n=27) |
| 6 | Nausea, Pain | Janssen | 26/58 | 0.256 | effect too weak (rate 0.45 vs null 0.50, n=58) |
| 7 | Dizziness, Nausea | Moderna | 12/21 | 0.332 | effect too weak (rate 0.57 vs null 0.50, n=21) |
| 8 | Pain, Pyrexia | Pfizer | 16/35 | 0.368 | effect too weak (rate 0.46 vs null 0.50, n=35) |
| 9 | Headache, Pain in extremity | Janssen | 39/80 | 0.456 | effect too weak (rate 0.49 vs null 0.50, n=80) |
| 10 | Fatigue, Pyrexia | Moderna | 26/53 | 0.500 | effect too weak (rate 0.49 vs null 0.50, n=53) |

### P-M1 — 99 processed, 84 failed (84/99 (84.8%)); median n 33, median p 0.5385
*Tested against — H0: P(Headache precedes Nausea) is equal for Pfizer and Moderna (p1 = p2)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Nausea, Vomiting | Pfizer vs Janssen | 13/21 ; 26/30 | 0.051 | difference too small (gap=0.25, n=21/30) |
| 2 | Fatigue, Pain in extremity | Moderna vs Janssen | 16/44 ; 21/41 | 0.194 | difference too small (gap=0.15, n=44/41) |
| 3 | Nausea, Pyrexia | Pfizer vs Janssen | 14/37 ; 29/58 | 0.293 | difference too small (gap=0.12, n=37/58) |
| 4 | Fatigue, Pain | Moderna vs Janssen | 15/44 ; 27/63 | 0.423 | difference too small (gap=0.09, n=44/63) |
| 5 | Asthenia, Chills | Moderna vs Janssen | 6/20 ; 5/24 | 0.509 | difference too small (gap=0.09, n=20/24) |
| 6 | Chills, Dizziness | Pfizer vs Janssen | 11/20 ; 30/48 | 0.596 | difference too small (gap=0.07, n=20/48) |
| 7 | Arthralgia, Pain | Moderna vs Janssen | 11/20 ; 19/31 | 0.773 | difference too small (gap=0.06, n=20/31) |
| 8 | Pain, Pyrexia | Moderna vs Janssen | 19/40 ; 31/70 | 0.843 | difference too small (gap=0.03, n=40/70) |
| 9 | Dizziness, Pyrexia | Moderna vs Janssen | 9/20 ; 20/46 | 1.000 | difference too small (gap=0.02, n=20/46) |
| 10 | Feeling abnormal, Headache | Moderna vs Janssen | 7/26 ; 7/23 | 1.000 | difference too small (gap=0.04, n=26/23) |

### P-M2 — 99 processed, 81 failed (81/99 (81.8%)); median n 33, median p 0.3213
*Tested against — H0: P(Headache precedes Nausea) is equal for Pfizer and Moderna (p1 = p2)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Chills, Pain | Moderna vs Janssen | 17/31 ; 50/68 | 0.055 | difference too small (gap=0.19, n=31/68) |
| 2 | Chills, Nausea | Pfizer vs Janssen | 21/26 ; 42/63 | 0.141 | difference too small (gap=0.14, n=26/63) |
| 3 | Fatigue, Pain | Pfizer vs Moderna | 20/44 ; 15/44 | 0.192 | difference too small (gap=0.11, n=44/44) |
| 4 | Headache, Pyrexia | Pfizer vs Moderna | 32/61 ; 25/56 | 0.255 | difference too small (gap=0.08, n=61/56) |
| 5 | Arthralgia, Pain in extremity | Pfizer vs Janssen | 5/33 ; 7/30 | 0.307 | difference too small (gap=0.08, n=33/30) |
| 6 | Headache, Nausea | Moderna vs Janssen | 20/34 ; 52/82 | 0.397 | difference too small (gap=0.05, n=34/82) |
| 7 | Arthralgia, Pain | Moderna vs Janssen | 11/20 ; 19/31 | 0.437 | difference too small (gap=0.06, n=20/31) |
| 8 | Fatigue, Pain | Pfizer vs Janssen | 20/44 ; 27/63 | 0.472 | difference too small (gap=0.03, n=44/63) |
| 9 | Pain in extremity, Pyrexia | Pfizer vs Moderna | 24/33 ; 24/34 | 0.531 | difference too small (gap=0.02, n=33/34) |
| 10 | Asthenia, Headache | Moderna vs Janssen | 7/25 ; 10/35 | 0.598 | difference too small (gap=0.01, n=25/35) |

### C-R1 — 0 processed (no categorical test: BOOL/report)

### C-V1 — 361 processed, 184 failed (184/361 (51.0%)); median n 30, median p 0.2595
*Tested against — H0: P(Chills and Pyrexia co-occur) = 0.5 (among reports containing both)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Dizziness, Fatigue | Pfizer | 21/55 | 0.052 | effect too weak (rate 0.38 vs null 0.50, n=55) |
| 2 | Arthralgia, Neck pain | Janssen | 7/22 | 0.067 | effect too weak (rate 0.32 vs null 0.50, n=22) |
| 3 | Cough, Fatigue | Janssen | 12/32 | 0.108 | effect too weak (rate 0.38 vs null 0.50, n=32) |
| 4 | Feeling abnormal, Pain | Janssen | 11/28 | 0.172 | effect too weak (rate 0.39 vs null 0.50, n=28) |
| 5 | Hyperhidrosis, Pain | Moderna | 15/25 | 0.212 | effect too weak (rate 0.60 vs null 0.50, n=25) |
| 6 | Headache, Pain | Pfizer | 56/105 | 0.279 | effect too weak (rate 0.53 vs null 0.50, n=105) |
| 7 | Chills, Vomiting | Moderna | 12/27 | 0.351 | effect too weak (rate 0.44 vs null 0.50, n=27) |
| 8 | Cough, Dyspnoea | Pfizer | 14/26 | 0.423 | effect too weak (rate 0.54 vs null 0.50, n=26) |
| 9 | Chills, Fatigue | Pfizer | 37/76 | 0.454 | effect too weak (rate 0.49 vs null 0.50, n=76) |
| 10 | Chills, Nausea | Pfizer | 27/53 | 0.500 | effect too weak (rate 0.51 vs null 0.50, n=53) |

### C-V3 — 361 processed, 184 failed (184/361 (51.0%)); median n 30, median p 0.2595
*Tested against — H0: P(Chills and Pyrexia co-occur) = 0.5 (among reports containing both)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Dizziness, Fatigue | Pfizer | 21/55 | 0.052 | effect too weak (rate 0.38 vs null 0.50, n=55) |
| 2 | Arthralgia, Neck pain | Janssen | 7/22 | 0.067 | effect too weak (rate 0.32 vs null 0.50, n=22) |
| 3 | Cough, Fatigue | Janssen | 12/32 | 0.108 | effect too weak (rate 0.38 vs null 0.50, n=32) |
| 4 | Feeling abnormal, Pain | Janssen | 11/28 | 0.172 | effect too weak (rate 0.39 vs null 0.50, n=28) |
| 5 | Hyperhidrosis, Pain | Moderna | 15/25 | 0.212 | effect too weak (rate 0.60 vs null 0.50, n=25) |
| 6 | Headache, Pain | Pfizer | 56/105 | 0.279 | effect too weak (rate 0.53 vs null 0.50, n=105) |
| 7 | Chills, Vomiting | Moderna | 12/27 | 0.351 | effect too weak (rate 0.44 vs null 0.50, n=27) |
| 8 | Cough, Dyspnoea | Pfizer | 14/26 | 0.423 | effect too weak (rate 0.54 vs null 0.50, n=26) |
| 9 | Chills, Fatigue | Pfizer | 37/76 | 0.454 | effect too weak (rate 0.49 vs null 0.50, n=76) |
| 10 | Chills, Nausea | Pfizer | 27/53 | 0.500 | effect too weak (rate 0.51 vs null 0.50, n=53) |

### C-M1 — 232 processed, 218 failed (218/232 (94.0%)); median n 32, median p 0.577
*Tested against — H0: the Fatigue/Headache co-occurrence rate is equal for Moderna and Janssen (p1 = p2)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Arthralgia, Pain in extremity | Pfizer vs Janssen | 10/43 ; 23/53 | 0.052 | difference too small (gap=0.20, n=43/53) |
| 2 | Chills, Nausea | Moderna vs Janssen | 37/72 ; 43/106 | 0.169 | difference too small (gap=0.11, n=72/106) |
| 3 | Asthenia, Pain | Pfizer vs Janssen | 6/20 ; 16/34 | 0.262 | difference too small (gap=0.17, n=20/34) |
| 4 | Dizziness, Nausea | Pfizer vs Janssen | 32/66 ; 57/102 | 0.429 | difference too small (gap=0.07, n=66/102) |
| 5 | Fatigue, Nausea | Pfizer vs Janssen | 27/62 ; 40/106 | 0.515 | difference too small (gap=0.06, n=62/106) |
| 6 | Arthralgia, Chills | Moderna vs Janssen | 18/32 ; 28/44 | 0.635 | difference too small (gap=0.07, n=32/44) |
| 7 | Chest pain, Headache | Pfizer vs Janssen | 9/27 ; 8/30 | 0.773 | difference too small (gap=0.07, n=27/30) |
| 8 | Pain in extremity, Pyrexia | Pfizer vs Janssen | 12/45 ; 23/76 | 0.836 | difference too small (gap=0.04, n=45/76) |
| 9 | Feeling abnormal, Pain in extremity | Moderna vs Janssen | 5/22 ; 6/22 | 1.000 | difference too small (gap=0.05, n=22/22) |
| 10 | Myalgia, Pain in extremity | Moderna vs Janssen | 7/22 ; 8/27 | 1.000 | difference too small (gap=0.02, n=22/27) |

### C-M2 — 232 processed, 209 failed (209/232 (90.1%)); median n 32, median p 0.3376
*Tested against — H0: the Fatigue/Headache co-occurrence rate is equal for Moderna and Janssen (p1 = p2)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Chills, Tremor | Moderna vs Janssen | 18/25 ; 14/30 | 0.052 | difference too small (gap=0.25, n=25/30) |
| 2 | Myalgia, Pyrexia | Pfizer vs Janssen | 19/38 ; 36/56 | 0.122 | difference too small (gap=0.14, n=38/56) |
| 3 | Fatigue, Injection site pain | Pfizer vs Janssen | 5/24 ; 15/43 | 0.178 | difference too small (gap=0.14, n=24/43) |
| 4 | Chills, Pyrexia | Pfizer vs Moderna | 94/125 ; 96/136 | 0.243 | difference too small (gap=0.05, n=125/136) |
| 5 | Injection site pain, Pyrexia | Pfizer vs Janssen | 5/20 ; 9/54 | 0.308 | difference too small (gap=0.08, n=20/54) |
| 6 | Fatigue, Myalgia | Pfizer vs Moderna | 17/33 ; 26/45 | 0.375 | difference too small (gap=0.06, n=33/45) |
| 7 | Dyspnoea, Pain | Moderna vs Janssen | 9/23 ; 13/39 | 0.424 | difference too small (gap=0.06, n=23/39) |
| 8 | Dyspnoea, Fatigue | Moderna vs Janssen | 16/30 ; 22/44 | 0.482 | difference too small (gap=0.03, n=30/44) |
| 9 | Chills, Dizziness | Pfizer vs Janssen | 9/29 ; 23/71 | 0.546 | difference too small (gap=0.01, n=29/71) |
| 10 | Dizziness, Pain in extremity | Pfizer vs Janssen | 3/23 ; 5/40 | 0.619 | difference too small (gap=0.01, n=23/40) |

### S-R1 — 0 processed (no categorical test: BOOL/report)

### S-V1 — 192 processed, 188 failed (188/192 (97.9%)); median n 7, median p 0.377
*Tested against — H0: the Fatigue -> Nausea -> Vomiting ordering and the runner-up ordering are equally frequent (P = 0.5; no unique mode)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Headache, Nausea, Pain in extremity | Pfizer | 6/7 | 0.063 | distribution too close to uniform / n small (n=7) |
| 2 | Chills, Dizziness, Hyperhidrosis | Janssen | 4/5 | 0.188 | distribution too close to uniform / n small (n=5) |
| 3 | Fatigue, Headache, Injection site pain | Janssen | 7/14 | 0.274 | distribution too close to uniform / n small (n=14) |
| 4 | Dizziness, Nausea, Pyrexia | Janssen | 3/6 | 0.312 | distribution too close to uniform / n small (n=6) |
| 5 | Injection site pain, Pain in extremity, Pyrexia | Janssen | 4/6 | 0.344 | distribution too close to uniform / n small (n=6) |
| 6 | Arthralgia, Fatigue, Pain | Moderna | 2/5 | 0.500 | distribution too close to uniform / n small (n=5) |
| 7 | Feeling abnormal, Headache, Pain | Janssen | 2/6 | 0.500 | distribution too close to uniform / n small (n=6) |
| 8 | Arthralgia, Fatigue, Pyrexia | Pfizer | 3/6 | 0.500 | distribution too close to uniform / n small (n=6) |
| 9 | Chills, Dizziness, Pain | Janssen | 3/5 | 0.500 | distribution too close to uniform / n small (n=5) |
| 10 | Nausea, Pain, Pyrexia | Janssen | 3/9 | 0.500 | distribution too close to uniform / n small (n=9) |

### S-V3 — 192 processed, 180 failed (180/192 (93.8%)); median n 6, median p 0.213
*Tested against — H0: the 6 orderings are equally likely -- uniform (no modal ordering)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Fatigue, Nausea, Vomiting | Janssen | 7/8 | 0.000 | p=0.000 < 0.05 but n=8 below the significance min-n gate (10): verdict forced to insufficient |
| 2 | Immediate post-injection reaction, Pain, Pyrexia | Janssen | 4/5 | 0.020 | p=0.020 < 0.05 but n=5 below the significance min-n gate (10): verdict forced to insufficient |
| 3 | Dizziness, Fatigue, Pain | Janssen | 4/7 | 0.061 | distribution too close to uniform / n small (n=7) |
| 4 | Chills, Fatigue, Nausea | Janssen | 5/13 | 0.178 | distribution too close to uniform / n small (n=13) |
| 5 | Dyspnoea, Nausea, Pain | Janssen | 3/5 | 0.213 | distribution too close to uniform / n small (n=5) |
| 6 | Fatigue, Headache, Pain | Janssen | 7/18 | 0.219 | distribution too close to uniform / n small (n=18) |
| 7 | Headache, Hypoaesthesia, Pain in extremity | Janssen | 3/6 | 0.406 | distribution too close to uniform / n small (n=6) |
| 8 | Arthralgia, Fatigue, Pain in extremity | Janssen | 3/8 | 0.706 | distribution too close to uniform / n small (n=8) |
| 9 | Arthralgia, Headache, Pyrexia | Janssen | 2/5 | 0.907 | distribution too close to uniform / n small (n=5) |
| 10 | Dizziness, Fatigue, Pyrexia | Janssen | 2/7 | 1.000 | distribution too close to uniform / n small (n=7) |

### S-V4 — 236 processed, 225 failed (225/236 (95.3%)); median n 6, median p 0.4444
*Tested against — H0: the 6 orderings are equally likely -- uniform (no consistent ordering)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Fatigue, Nausea, Vomiting | Janssen | 7/8 | 0.000 | p=0.000 < 0.05 but n=8 below the significance min-n gate (10): verdict forced to insufficient |
| 2 | Dyspnoea, Fatigue, Headache | Moderna | 3/5 | 0.059 | distribution too close to uniform / n small (n=5) |
| 3 | Arthralgia, Headache, Pyrexia | Pfizer | 4/7 | 0.136 | distribution too close to uniform / n small (n=7) |
| 4 | Dizziness, Headache, Pyrexia | Moderna | 3/5 | 0.213 | distribution too close to uniform / n small (n=5) |
| 5 | Dizziness, Fatigue, Feeling abnormal | Pfizer | 4/9 | 0.368 | distribution too close to uniform / n small (n=9) |
| 6 | Chills, Fatigue, Hyperhidrosis | Janssen | 2/5 | 0.444 | distribution too close to uniform / n small (n=5) |
| 7 | Injection site pain, Nausea, Pain | Janssen | 3/9 | 0.482 | distribution too close to uniform / n small (n=9) |
| 8 | Fatigue, Feeling abnormal, Pyrexia | Janssen | 2/6 | 0.753 | distribution too close to uniform / n small (n=6) |
| 9 | Asthenia, Pain, Pyrexia | Janssen | 2/5 | 0.907 | distribution too close to uniform / n small (n=5) |
| 10 | Chills, Injection site pain, Myalgia | Janssen | 1/5 | 1.000 | distribution too close to uniform / n small (n=5) |

### S-M1 — 90 processed, 90 failed (90/90 (100.0%)); median n 6, median p 1.0
*Tested against — H0: P(ordering = Fatigue -> Headache -> Pain) is equal for Moderna and Janssen (p1 = p2)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Chills, Myalgia, Pyrexia | Pfizer vs Janssen | 0/7 ; 3/6 | 0.070 | cohorts too small (n=7/6) |
| 2 | Chills, Myalgia, Pyrexia | Pfizer vs Moderna | 0/7 ; 1/5 | 0.417 | cohorts too small (n=7/5) |
| 3 | Chills, Fatigue, Pyrexia | Pfizer vs Moderna | 0/6 ; 2/11 | 0.515 | small cohorts and small gap (gap=0.18, n=6/11) |
| 4 | Fatigue, Headache, Pyrexia | Moderna vs Janssen | 1/10 ; 6/25 | 0.644 | small cohorts and small gap (gap=0.14, n=10/25) |
| 5 | Chills, Pain, Pyrexia | Moderna vs Janssen | 0/6 ; 1/8 | 1.000 | small cohorts and small gap (gap=0.12, n=6/8) |
| 6 | Fatigue, Headache, Nausea | Pfizer vs Moderna | 2/8 ; 1/6 | 1.000 | small cohorts and small gap (gap=0.08, n=8/6) |
| 7 | Headache, Pain in extremity, Pyrexia | Pfizer vs Moderna | 0/7 ; 0/6 | 1.000 | small cohorts and small gap (gap=0.00, n=7/6) |
| 8 | Headache, Pain in extremity, Pyrexia | Pfizer vs Janssen | 0/7 ; 1/17 | 1.000 | small cohorts and small gap (gap=0.06, n=7/17) |
| 9 | Dizziness, Fatigue, Headache | Moderna vs Janssen | 0/5 ; 1/16 | 1.000 | small cohorts and small gap (gap=0.06, n=5/16) |
| 10 | Pain, Pain in extremity, Pyrexia | Moderna vs Janssen | 0/7 ; 0/13 | 1.000 | small cohorts and small gap (gap=0.00, n=7/13) |

### S-M2 — 75 processed, 75 failed (75/75 (100.0%)); median n 6, median p 0.5385
*Tested against — H0: P(ordering = Fatigue -> Headache -> Pain) is equal for Moderna and Janssen (p1 = p2)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Fatigue, Headache, Pain | Moderna vs Janssen | 1/13 ; 7/18 | 0.058 | cohorts too small (n=13/18) |
| 2 | Chills, Headache, Pyrexia | Pfizer vs Moderna | 0/7 ; 2/8 | 0.267 | cohorts too small (n=7/8) |
| 3 | Chills, Headache, Pyrexia | Pfizer vs Janssen | 0/7 ; 4/22 | 0.308 | small cohorts and small gap (gap=0.18, n=7/22) |
| 4 | Chills, Fatigue, Pyrexia | Moderna vs Janssen | 2/11 ; 1/14 | 0.407 | small cohorts and small gap (gap=0.11, n=11/14) |
| 5 | Fatigue, Nausea, Pyrexia | Moderna vs Janssen | 1/5 ; 4/12 | 0.528 | small cohorts and small gap (gap=0.13, n=5/12) |
| 6 | Fatigue, Pain, Pyrexia | Moderna vs Janssen | 0/12 ; 1/15 | 0.556 | small cohorts and small gap (gap=0.07, n=12/15) |
| 7 | Chills, Fatigue, Injection site pain | Moderna vs Janssen | 1/6 ; 1/11 | 0.596 | small cohorts and small gap (gap=0.08, n=6/11) |
| 8 | Chills, Injection site pain, Pain | Moderna vs Janssen | 0/6 ; 1/10 | 0.625 | small cohorts and small gap (gap=0.10, n=6/10) |
| 9 | Fatigue, Pain, Pain in extremity | Moderna vs Janssen | 1/7 ; 2/11 | 0.674 | small cohorts and small gap (gap=0.04, n=7/11) |
| 10 | Dizziness, Fatigue, Headache | Moderna vs Janssen | 0/5 ; 1/16 | 0.762 | small cohorts and small gap (gap=0.06, n=5/16) |

### S-M3 — 90 processed, 90 failed (90/90 (100.0%)); median n 6, median p 0.5823
*Tested against — H0: Moderna and Janssen have the same ordering distribution (homogeneity)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Dizziness, Headache, Pyrexia | Moderna vs Janssen | 3/5 ; 4/12 | 0.043 | p=0.043 < 0.05 but n=5 below the significance min-n gate (10): verdict forced to insufficient |
| 2 | Headache, Nausea, Pyrexia | Pfizer vs Janssen | 4/9 ; 4/16 | 0.189 | distribution too close to uniform / n small (n=9) |
| 3 | Chills, Fatigue, Pyrexia | Moderna vs Janssen | 5/11 ; 6/14 | 0.292 | distribution too close to uniform / n small (n=11) |
| 4 | Chills, Myalgia, Pyrexia | Moderna vs Janssen | 2/5 ; 3/6 | 0.403 | distribution too close to uniform / n small (n=5) |
| 5 | Fatigue, Headache, Pain | Pfizer vs Janssen | 3/7 ; 7/18 | 0.529 | distribution too close to uniform / n small (n=7) |
| 6 | Chills, Fatigue, Headache | Moderna vs Janssen | 4/11 ; 8/28 | 0.647 | distribution too close to uniform / n small (n=11) |
| 7 | Chills, Headache, Myalgia | Pfizer vs Janssen | 2/5 ; 3/9 | 0.768 | distribution too close to uniform / n small (n=5) |
| 8 | Chills, Fatigue, Pain in extremity | Moderna vs Janssen | 4/6 ; 3/9 | 0.916 | distribution too close to uniform / n small (n=6) |
| 9 | Fatigue, Nausea, Pain | Pfizer vs Moderna | 3/6 ; 3/5 | 1.000 | distribution too close to uniform / n small (n=6) |
| 10 | Feeling abnormal, Headache, Nausea | Moderna vs Janssen | 2/5 ; 2/5 | 1.000 | distribution too close to uniform / n small (n=5) |

### F-R1 — 0 processed (no categorical test: CHOICE/report)

### F-R2 — 0 processed (no categorical test: CHOICE/report)

### F-R3 — 0 processed (no categorical test: BOOL/report)

### F-V1 — 67 processed, 42 failed (42/67 (62.7%)); median n 42, median p 0.2466
*Tested against — H0: the 3 candidates are equally likely to be first -- uniform*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Chills, Nausea, Pyrexia | Pfizer | 5/31 | 0.053 | distribution too close to uniform / n small (n=31) |
| 2 | Fatigue, Headache, Myalgia | Janssen | 9/32 | 0.074 | distribution too close to uniform / n small (n=32) |
| 3 | Chills, Fatigue, Pyrexia | Moderna | 9/55 | 0.113 | distribution too close to uniform / n small (n=55) |
| 4 | Chills, Headache, Pain in extremity | Janssen | 12/43 | 0.197 | distribution too close to uniform / n small (n=43) |
| 5 | Fatigue, Pain, Pyrexia | Moderna | 9/39 | 0.230 | distribution too close to uniform / n small (n=39) |
| 6 | Headache, Myalgia, Pyrexia | Janssen | 7/38 | 0.269 | distribution too close to uniform / n small (n=38) |
| 7 | Fatigue, Headache, Pain | Pfizer | 8/42 | 0.513 | distribution too close to uniform / n small (n=42) |
| 8 | Headache, Nausea, Pain | Janssen | 8/63 | 0.692 | distribution too close to uniform / n small (n=63) |
| 9 | Chills, Fatigue, Headache | Pfizer | 7/44 | 0.846 | distribution too close to uniform / n small (n=44) |
| 10 | Chills, Fatigue, Headache | Moderna | 8/56 | 0.956 | distribution too close to uniform / n small (n=56) |

### F-V2 — 73 processed, 36 failed (36/73 (49.3%)); median n 43, median p 0.2686
*Tested against — H0: the 3 candidates are equally likely to be last -- uniform*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Dizziness, Fatigue, Nausea | Janssen | 12/38 | 0.066 | distribution too close to uniform / n small (n=38) |
| 2 | Headache, Pain, Pyrexia | Moderna | 10/48 | 0.080 | distribution too close to uniform / n small (n=48) |
| 3 | Fatigue, Headache, Pain | Janssen | 23/81 | 0.102 | distribution too close to uniform / n small (n=81) |
| 4 | Headache, Nausea, Pyrexia | Pfizer | 8/32 | 0.161 | distribution too close to uniform / n small (n=32) |
| 5 | Fatigue, Headache, Pyrexia | Pfizer | 9/47 | 0.223 | distribution too close to uniform / n small (n=47) |
| 6 | Fatigue, Headache, Pain in extremity | Janssen | 14/46 | 0.273 | distribution too close to uniform / n small (n=46) |
| 7 | Fatigue, Pain, Pyrexia | Janssen | 11/65 | 0.482 | distribution too close to uniform / n small (n=65) |
| 8 | Fatigue, Nausea, Pyrexia | Janssen | 10/43 | 0.607 | distribution too close to uniform / n small (n=43) |
| 9 | Chills, Fatigue, Headache | Pfizer | 6/44 | 0.710 | distribution too close to uniform / n small (n=44) |
| 10 | Headache, Nausea, Pyrexia | Janssen | 12/71 | 0.913 | distribution too close to uniform / n small (n=71) |

### F-V3 — 67 processed, 53 failed (53/67 (79.1%)); median n 42, median p 0.3036
*Tested against — H0: Chills and the runner-up event are equally often the first (P = 0.5; no unique most-common first event)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Fatigue, Headache, Pain in extremity | Moderna | 11/33 | 0.059 | distribution too close to uniform / n small (n=33) |
| 2 | Fatigue, Headache, Myalgia | Janssen | 9/32 | 0.133 | distribution too close to uniform / n small (n=32) |
| 3 | Chills, Nausea, Pain | Janssen | 12/46 | 0.180 | distribution too close to uniform / n small (n=46) |
| 4 | Chills, Headache, Pain | Pfizer | 11/55 | 0.240 | distribution too close to uniform / n small (n=55) |
| 5 | Headache, Myalgia, Pyrexia | Janssen | 7/38 | 0.274 | distribution too close to uniform / n small (n=38) |
| 6 | Chills, Myalgia, Pyrexia | Janssen | 5/37 | 0.363 | distribution too close to uniform / n small (n=37) |
| 7 | Headache, Nausea, Pain | Janssen | 8/63 | 0.395 | distribution too close to uniform / n small (n=63) |
| 8 | Dizziness, Headache, Pyrexia | Janssen | 11/46 | 0.412 | distribution too close to uniform / n small (n=46) |
| 9 | Chills, Fatigue, Headache | Moderna | 8/56 | 0.500 | distribution too close to uniform / n small (n=56) |
| 10 | Chills, Headache, Pyrexia | Janssen | 22/116 | 0.500 | distribution too close to uniform / n small (n=116) |

### F-M1 — 46 processed, 44 failed (44/46 (95.7%)); median n 42, median p 0.5575
*Tested against — H0: Pfizer and Moderna have the same first-event distribution (homogeneity)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Chills, Pain, Pyrexia | Pfizer vs Janssen | 7/57 ; None/88 | 0.052 | distribution too close to uniform / n small (n=57) |
| 2 | Chills, Pain in extremity, Pyrexia | Moderna vs Janssen | 11/30 ; None/40 | 0.238 | distribution too close to uniform / n small (n=30) |
| 3 | Headache, Nausea, Pyrexia | Pfizer vs Janssen | 8/32 ; None/71 | 0.343 | distribution too close to uniform / n small (n=32) |
| 4 | Headache, Nausea, Pyrexia | Pfizer vs Moderna | 8/32 ; None/35 | 0.410 | distribution too close to uniform / n small (n=32) |
| 5 | Chills, Headache, Pain | Pfizer vs Janssen | 11/55 ; None/88 | 0.479 | distribution too close to uniform / n small (n=55) |
| 6 | Chills, Headache, Pain | Moderna vs Janssen | 8/43 ; None/88 | 0.563 | distribution too close to uniform / n small (n=43) |
| 7 | Fatigue, Pain, Pyrexia | Pfizer vs Moderna | 4/31 ; None/39 | 0.700 | distribution too close to uniform / n small (n=31) |
| 8 | Fatigue, Headache, Pain in extremity | Moderna vs Janssen | 11/33 ; None/46 | 0.818 | distribution too close to uniform / n small (n=33) |
| 9 | Chills, Fatigue, Headache | Moderna vs Janssen | 8/56 ; None/88 | 0.968 | distribution too close to uniform / n small (n=56) |
| 10 | Fatigue, Headache, Nausea | Pfizer vs Janssen | 8/35 ; None/68 | 1.000 | distribution too close to uniform / n small (n=35) |

### F-M2 — 46 processed, 44 failed (44/46 (95.7%)); median n 42, median p 0.5575
*Tested against — H0: Pfizer and Moderna have the same first-event distribution (homogeneity)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Chills, Pain, Pyrexia | Pfizer vs Janssen | 7/57 ; None/88 | 0.052 | distribution too close to uniform / n small (n=57) |
| 2 | Chills, Pain in extremity, Pyrexia | Moderna vs Janssen | 11/30 ; None/40 | 0.238 | distribution too close to uniform / n small (n=30) |
| 3 | Headache, Nausea, Pyrexia | Pfizer vs Janssen | 8/32 ; None/71 | 0.343 | distribution too close to uniform / n small (n=32) |
| 4 | Headache, Nausea, Pyrexia | Pfizer vs Moderna | 8/32 ; None/35 | 0.410 | distribution too close to uniform / n small (n=32) |
| 5 | Chills, Headache, Pain | Pfizer vs Janssen | 11/55 ; None/88 | 0.479 | distribution too close to uniform / n small (n=55) |
| 6 | Chills, Headache, Pain | Moderna vs Janssen | 8/43 ; None/88 | 0.563 | distribution too close to uniform / n small (n=43) |
| 7 | Fatigue, Pain, Pyrexia | Pfizer vs Moderna | 4/31 ; None/39 | 0.700 | distribution too close to uniform / n small (n=31) |
| 8 | Fatigue, Headache, Pain in extremity | Moderna vs Janssen | 11/33 ; None/46 | 0.818 | distribution too close to uniform / n small (n=33) |
| 9 | Chills, Fatigue, Headache | Moderna vs Janssen | 8/56 ; None/88 | 0.968 | distribution too close to uniform / n small (n=56) |
| 10 | Fatigue, Headache, Nausea | Pfizer vs Janssen | 8/35 ; None/68 | 1.000 | distribution too close to uniform / n small (n=35) |

### F-M3 — 45 processed, 45 failed (45/45 (100.0%)); median n 42, median p 0.3321
*Tested against — H0: the first-event rate is equal for Pfizer and Moderna (p1 = p2)*

| # | events | cohort | counts (k/n) | p | why it failed |
|--:|---|---|---|--:|---|
| 1 | Chills, Fatigue, Pain | Moderna vs Janssen | 6/43 ; 17/62 | 0.079 | difference too small (gap=0.13, n=43/62) |
| 2 | Chills, Nausea, Pyrexia | Moderna vs Janssen | 4/39 ; 13/64 | 0.144 | difference too small (gap=0.10, n=39/64) |
| 3 | Chills, Pain in extremity, Pyrexia | Moderna vs Janssen | 11/30 ; 10/40 | 0.214 | difference too small (gap=0.12, n=30/40) |
| 4 | Fatigue, Headache, Pyrexia | Pfizer vs Janssen | 7/47 ; 19/90 | 0.261 | difference too small (gap=0.06, n=47/90) |
| 5 | Chills, Fatigue, Pyrexia | Pfizer vs Moderna | 8/49 ; 6/55 | 0.301 | difference too small (gap=0.05, n=49/55) |
| 6 | Chills, Nausea, Pyrexia | Pfizer vs Moderna | 5/31 ; 4/39 | 0.353 | difference too small (gap=0.06, n=31/39) |
| 7 | Chills, Fatigue, Headache | Pfizer vs Moderna | 7/44 ; 7/56 | 0.419 | difference too small (gap=0.03, n=44/56) |
| 8 | Chills, Fatigue, Pyrexia | Pfizer vs Janssen | 8/49 ; 15/81 | 0.473 | difference too small (gap=0.02, n=49/81) |
| 9 | Chills, Headache, Pain | Pfizer vs Janssen | 11/55 ; 19/88 | 0.497 | difference too small (gap=0.02, n=55/88) |
| 10 | Fatigue, Pain, Pyrexia | Pfizer vs Janssen | 4/31 ; 8/65 | 0.586 | difference too small (gap=0.01, n=31/65) |

