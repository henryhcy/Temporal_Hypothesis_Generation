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
| P-V2 | 173 | 173 | 173 |
| P-V3 | 173 | 168 | 168 |
| P-M1 | 99 | 39 | 60 |
| P-M2 | 99 | 99 | 99 |
| C-R1 | 3166 | 1970 | 1196 |
| C-V1 | 374 | 90 | 271 |
| C-V2 | 374 | 374 | 374 |
| C-V3 | 374 | 90 | 271 |
| C-M1 | 232 | 89 | 143 |
| C-M2 | 232 | 232 | 232 |
| S-R1 | 3166 | 489 | 3166 |
| S-V1 | 275 | 62 | 236 |
| S-V2 | 275 | 275 | 275 |
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
| F-V3 | 82 | 2 | 82 |
| F-M1 | 46 | 23 | 23 |
| F-M2 | 46 | 23 | 23 |
| F-M3 | 46 | 45 | 45 |

## Gold-label vs significance-test fail rate

For every viable core with a definite gold verdict (supported/refuted) and an applicable categorical test (PROP and report-level excluded), we check whether the test is significant at alpha=0.05. A **fail** is a definite gold label the test does NOT corroborate. This is the population rate over ALL such cores.

- **Overall population**: 2354/2998 (78.5%) of definite-verdict categorical cores are not significant.

| family | definite cores | failed | fail rate |
|---|--:|--:|--:|
| pairwise-precedes | 534 | 350 | 350/534 (65.5%) |
| co-occurs | 1186 | 876 | 876/1186 (73.9%) |
| sequence | 919 | 876 | 876/919 (95.3%) |
| first/last | 359 | 252 | 252/359 (70.2%) |

For the worked examples below we search each template's cores for a **successful** example (definite gold + significant test) to showcase; only when none exists do we present a failed one.

- **Presented examples**: 4/20 (20.0%) of testable templates still show a failed example (no successful core exists): S-M1, S-M2, S-M3, F-M3.

| template | definite cores | failed | fail rate | presented |
|---|--:|--:|--:|:--:|
| P-R1 | 0 | 0 | n/a | n/a |
| P-R2 | 0 | 0 | n/a | n/a |
| P-V1 | 168 | 91 | 91/168 (54.2%) | successful |
| P-V2 | 0 | 0 | n/a | n/a |
| P-V3 | 168 | 91 | 91/168 (54.2%) | successful |
| P-M1 | 99 | 84 | 84/99 (84.8%) | successful |
| P-M2 | 99 | 84 | 84/99 (84.8%) | successful |
| C-R1 | 0 | 0 | n/a | n/a |
| C-V1 | 361 | 220 | 220/361 (60.9%) | successful |
| C-V2 | 0 | 0 | n/a | n/a |
| C-V3 | 361 | 220 | 220/361 (60.9%) | successful |
| C-M1 | 232 | 218 | 218/232 (94.0%) | successful |
| C-M2 | 232 | 218 | 218/232 (94.0%) | successful |
| S-R1 | 0 | 0 | n/a | n/a |
| S-V1 | 236 | 216 | 216/236 (91.5%) | successful |
| S-V2 | 0 | 0 | n/a | n/a |
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
| F-V3 | 82 | 41 | 41/82 (50.0%) | successful |
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
- **SUPPORTED** example:
    - Q: Did Dizziness occur before Injection site pain in report VAERS-916915?
    - Claim: In report VAERS-916915, Dizziness occurred before Injection site pain.
- **REFUTED** example:
    - Q: Did Injection site pain occur before Dizziness in report VAERS-916915?
    - Claim: In report VAERS-916915, Injection site pain occurred before Dizziness.

## P-R2  (pairwise, report, CHOICE)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 3166 viable | 1196 supported-capable (true cases) | 1196 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Categorical test**: none (report-level: single observation, no sampling distribution)
- **Options**: ['Dizziness', 'Injection site pain']  ->  correct: **Dizziness**
- **SUPPORTED** example:
    - Q: Which came first in report VAERS-916915, Dizziness or Injection site pain?
    - Claim: In report VAERS-916915, Dizziness came first, before Injection site pain.
- **REFUTED** example:
    - Q: Which came first in report VAERS-916915, Injection site pain or Dizziness?
    - Claim: In report VAERS-916915, Injection site pain came first, before Dizziness.

## P-V1  (pairwise, vaccine, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 91/168 (54.2%) fail)
- **Qualified cores**: 173 viable | 168 supported-capable (true cases) | 168 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Janssen
- **Conditioned counts**: k=44 / n=119  (rate 0.3697)
- **Categorical test**: binomial exact, p = 0.005727 (significant)
    - *how p is computed*: two-sided exact binomial -- sum the Binomial(n, p0) probabilities of outcomes no more likely than the observed k (null p0 = 1/2 pairwise/co-occurs, 1/6 sequence, 1/3 first-among-3)
- **Position-based test**: Wilcoxon signed-rank (level(Fatigue)-level(Headache); n=119 (normal)), p = 0.002862
    - *how p is computed*: Wilcoxon signed-rank -- rank |d| where d=level(A)-level(B) (co-exist d=0 dropped), sum the signed ranks; exact sign-flip null for small n, else normal approximation with tie/continuity correction
- **95% CI**: [0.2884, 0.4593], effect size -0.2635
- **SUPPORTED** example:
    - Q: Does Headache typically occur before Fatigue after Janssen?
    - Claim: After Janssen, Headache typically occurs before Fatigue.
- **REFUTED** example:
    - Q: Does Fatigue typically occur before Headache after Janssen?
    - Claim: After Janssen, Fatigue typically occurs before Headache.

## P-V2  (pairwise, vaccine, PROP)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 173 viable | 173 supported-capable (true cases) | 173 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Janssen
- **Conditioned counts**: k=44 / n=119  (rate 0.3697)
- **Categorical test**: binomial exact, p = 0.005727 (significant)
    - *how p is computed*: two-sided exact binomial -- sum the Binomial(n, p0) probabilities of outcomes no more likely than the observed k (null p0 = 1/2 pairwise/co-occurs, 1/6 sequence, 1/3 first-among-3)
- **Position-based test**: Wilcoxon signed-rank (level(Fatigue)-level(Headache); n=119 (normal)), p = 0.002862
    - *how p is computed*: Wilcoxon signed-rank -- rank |d| where d=level(A)-level(B) (co-exist d=0 dropped), sum the signed ranks; exact sign-flip null for small n, else normal approximation with tie/continuity correction
- **95% CI**: [0.2884, 0.4593], effect size -0.2635
- **SUPPORTED** example:
    - Q: In what fraction of Janssen reports does Fatigue precede Headache?
    - Claim: In about 37% of Janssen reports, Fatigue precedes Headache.
- **REFUTED** example:
    - Q: In what fraction of Janssen reports does Fatigue precede Headache?
    - Claim: In about 57% of Janssen reports, Fatigue precedes Headache.

## P-V3  (pairwise, vaccine, CHOICE)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 91/168 (54.2%) fail)
- **Qualified cores**: 173 viable | 168 supported-capable (true cases) | 168 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Janssen
- **Conditioned counts**: k=44 / n=119  (rate 0.3697)
- **Categorical test**: binomial exact, p = 0.005727 (significant)
    - *how p is computed*: two-sided exact binomial -- sum the Binomial(n, p0) probabilities of outcomes no more likely than the observed k (null p0 = 1/2 pairwise/co-occurs, 1/6 sequence, 1/3 first-among-3)
- **Position-based test**: Wilcoxon signed-rank (level(Fatigue)-level(Headache); n=119 (normal)), p = 0.002862
    - *how p is computed*: Wilcoxon signed-rank -- rank |d| where d=level(A)-level(B) (co-exist d=0 dropped), sum the signed ranks; exact sign-flip null for small n, else normal approximation with tie/continuity correction
- **95% CI**: [0.2884, 0.4593], effect size -0.2635
- **Options**: ['Fatigue', 'Headache']  ->  correct: **Headache**
- **SUPPORTED** example:
    - Q: After Janssen, which usually comes first, Headache or Fatigue?
    - Claim: After Janssen, Headache usually comes before Fatigue.
- **REFUTED** example:
    - Q: After Janssen, which usually comes first, Fatigue or Headache?
    - Claim: After Janssen, Fatigue usually comes before Headache.

## P-M1  (pairwise, multi, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 84/99 (84.8%) fail)
- **Qualified cores**: 99 viable | 39 supported-capable (true cases) | 60 refuted-capable
- **Core**: events ['Headache', 'Nausea'], cohort Pfizer vs Moderna
- **Conditioned counts**: k=39 / n=48  |  cohort2 k=20 / n=34  (rate 0.8125)
- **Categorical test**: Fisher exact (2x2), p = 0.04459 (significant)
    - *how p is computed*: Fisher exact -- sum the hypergeometric probabilities of the 2x2 tables with the observed margins that are <= the observed table's probability
- **Position-based test**: Mann-Whitney U (level(Headache)-level(Nausea) between Pfizer/Moderna; n=89/85), p = 0.002855
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [0.0259, 0.411], effect size 0.4977
- **SUPPORTED** example:
    - Q: Does the Headache-before-Nausea rate differ between Pfizer and Moderna?
    - Claim: The Headache-before-Nausea rate differs between Pfizer and Moderna.

## P-M2  (pairwise, multi, CHOICE)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 84/99 (84.8%) fail)
- **Qualified cores**: 99 viable | 99 supported-capable (true cases) | 99 refuted-capable
- **Core**: events ['Headache', 'Nausea'], cohort Pfizer vs Moderna
- **Conditioned counts**: k=39 / n=48  |  cohort2 k=20 / n=34  (rate 0.8125)
- **Categorical test**: Fisher exact (2x2), p = 0.04459 (significant)
    - *how p is computed*: Fisher exact -- sum the hypergeometric probabilities of the 2x2 tables with the observed margins that are <= the observed table's probability
- **Position-based test**: Mann-Whitney U (level(Headache)-level(Nausea) between Pfizer/Moderna; n=89/85), p = 0.002855
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [0.0259, 0.411], effect size 0.4977
- **Options**: ['Pfizer', 'Moderna']  ->  correct: **Pfizer**
- **SUPPORTED** example:
    - Q: After which vaccine, Pfizer or Moderna, does Headache more often precede Nausea?
    - Claim: Headache precedes Nausea more often after Pfizer than after Moderna.
- **REFUTED** example:
    - Q: After which vaccine, Moderna or Pfizer, does Headache more often precede Nausea?
    - Claim: Headache precedes Nausea more often after Moderna than after Pfizer.

## C-R1  (pairwise, report, BOOL)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 3166 viable | 1970 supported-capable (true cases) | 1196 refuted-capable
- **Core**: events ['Arthralgia', 'Chills'], cohort report VAERS-917671
- **Conditioned counts**: (single report; deterministic)
- **Categorical test**: none (report-level: single observation, no sampling distribution)
- **SUPPORTED** example:
    - Q: Do Arthralgia and Chills co-occur in report VAERS-917671?
    - Claim: In report VAERS-917671, Arthralgia and Chills co-occur.

## C-V1  (pairwise, vaccine, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 220/361 (60.9%) fail)
- **Qualified cores**: 374 viable | 90 supported-capable (true cases) | 271 refuted-capable
- **Core**: events ['Chills', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=150 / n=204  (rate 0.7353)
- **Categorical test**: binomial exact, p = 1.209e-11 (significant)
    - *how p is computed*: two-sided exact binomial -- sum the Binomial(n, p0) probabilities of outcomes no more likely than the observed k (null p0 = 1/2 pairwise/co-occurs, 1/6 sequence, 1/3 first-among-3)
- **95% CI**: [0.6708, 0.7911], effect size 0.49
- **SUPPORTED** example:
    - Q: Do Chills and Pyrexia typically co-occur after Janssen?
    - Claim: After Janssen, Chills and Pyrexia typically co-occur.

## C-V2  (pairwise, vaccine, PROP)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 374 viable | 374 supported-capable (true cases) | 374 refuted-capable
- **Core**: events ['Headache', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=111 / n=213  (rate 0.5211)
- **Categorical test**: binomial exact, p = 0.5837 (not significant)
    - *how p is computed*: two-sided exact binomial -- sum the Binomial(n, p0) probabilities of outcomes no more likely than the observed k (null p0 = 1/2 pairwise/co-occurs, 1/6 sequence, 1/3 first-among-3)
- **95% CI**: [0.4543, 0.5872], effect size 0.0423
- **SUPPORTED** example:
    - Q: What fraction of Janssen reports show Headache and Pyrexia together?
    - Claim: In about 52% of Janssen reports, Headache and Pyrexia occur together.
- **REFUTED** example:
    - Q: What fraction of Janssen reports show Headache and Pyrexia together?
    - Claim: In about 72% of Janssen reports, Headache and Pyrexia occur together.

## C-V3  (pairwise, vaccine, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 220/361 (60.9%) fail)
- **Qualified cores**: 374 viable | 90 supported-capable (true cases) | 271 refuted-capable
- **Core**: events ['Chills', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=150 / n=204  (rate 0.7353)
- **Categorical test**: binomial exact, p = 1.209e-11 (significant)
    - *how p is computed*: two-sided exact binomial -- sum the Binomial(n, p0) probabilities of outcomes no more likely than the observed k (null p0 = 1/2 pairwise/co-occurs, 1/6 sequence, 1/3 first-among-3)
- **95% CI**: [0.6708, 0.7911], effect size 0.49
- **SUPPORTED** example:
    - Q: After Janssen, is co-occurrence the dominant relation for Chills and Pyrexia?
    - Claim: After Janssen, co-occurrence is the dominant relation for Chills and Pyrexia.

## C-M1  (pairwise, multi, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 218/232 (94.0%) fail)
- **Qualified cores**: 232 viable | 89 supported-capable (true cases) | 143 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Moderna vs Janssen
- **Conditioned counts**: k=70 / n=137  |  cohort2 k=77 / n=196  (rate 0.5109)
- **Categorical test**: Fisher exact (2x2), p = 0.03398 (significant)
    - *how p is computed*: Fisher exact -- sum the hypergeometric probabilities of the 2x2 tables with the observed margins that are <= the observed table's probability
- **Position-based test**: Mann-Whitney U (|level(Fatigue)-level(Headache)| between Moderna/Janssen; n=137/196), p = 0.0297
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [0.0098, 0.2234], effect size 0.2379
- **SUPPORTED** example:
    - Q: Does the Fatigue-Headache co-occurrence rate differ between Moderna and Janssen?
    - Claim: The Fatigue-Headache co-occurrence rate differs between Moderna and Janssen.

## C-M2  (pairwise, multi, CHOICE)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 218/232 (94.0%) fail)
- **Qualified cores**: 232 viable | 232 supported-capable (true cases) | 232 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Moderna vs Janssen
- **Conditioned counts**: k=70 / n=137  |  cohort2 k=77 / n=196  (rate 0.5109)
- **Categorical test**: Fisher exact (2x2), p = 0.03398 (significant)
    - *how p is computed*: Fisher exact -- sum the hypergeometric probabilities of the 2x2 tables with the observed margins that are <= the observed table's probability
- **Position-based test**: Mann-Whitney U (|level(Fatigue)-level(Headache)| between Moderna/Janssen; n=137/196), p = 0.0297
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [0.0098, 0.2234], effect size 0.2379
- **Options**: ['Moderna', 'Janssen']  ->  correct: **Moderna**
- **SUPPORTED** example:
    - Q: After which vaccine, Moderna or Janssen, do Fatigue and Headache more often co-occur?
    - Claim: Fatigue and Headache co-occur more often after Moderna than after Janssen.
- **REFUTED** example:
    - Q: After which vaccine, Janssen or Moderna, do Fatigue and Headache more often co-occur?
    - Claim: Fatigue and Headache co-occur more often after Janssen than after Moderna.

## S-R1  (sequence, report, BOOL)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 3166 viable | 489 supported-capable (true cases) | 3166 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain', 'Asthenia'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Categorical test**: none (report-level: single observation, no sampling distribution)
- **SUPPORTED** example:
    - Q: Do Dizziness, Injection site pain, Asthenia occur in the order Dizziness → Injection site pain → Asthenia in report VAERS-916915?
    - Claim: In report VAERS-916915, Dizziness, Injection site pain, Asthenia occur in the order Dizziness → Injection site pain → Asthenia.
- **REFUTED** example:
    - Q: Do Asthenia, Injection site pain, Dizziness occur in the order Asthenia → Injection site pain → Dizziness in report VAERS-916915?
    - Claim: In report VAERS-916915, Asthenia, Injection site pain, Dizziness occur in the order Asthenia → Injection site pain → Dizziness.

## S-V1  (sequence, vaccine, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 216/236 (91.5%) fail)
- **Qualified cores**: 275 viable | 62 supported-capable (true cases) | 236 refuted-capable
- **Core**: events ['Headache', 'Hyperhidrosis', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=7 / n=13  (rate 0.5385)
- **Categorical test**: binomial exact, p = 0.002398 (significant)
    - *how p is computed*: two-sided exact binomial -- sum the Binomial(n, p0) probabilities of outcomes no more likely than the observed k (null p0 = 1/2 pairwise/co-occurs, 1/6 sequence, 1/3 first-among-3)
- **Position-based test**: Friedman (Q=12.17 df=2; n=33 reports), p = 0.002276
    - *how p is computed*: Friedman -- rank the three events within each report (ties averaged), chi-square (df=2) on the rank sums
- **95% CI**: [0.2914, 0.7679], effect size 0.8067
- **SUPPORTED** example:
    - Q: After Janssen, do Headache, Pyrexia, Hyperhidrosis typically occur as Headache → Pyrexia → Hyperhidrosis?
    - Claim: After Janssen, Headache, Pyrexia, Hyperhidrosis typically occur as Headache → Pyrexia → Hyperhidrosis.
- **REFUTED** example:
    - Q: After Janssen, do Pyrexia, Headache, Hyperhidrosis typically occur as Pyrexia → Headache → Hyperhidrosis?
    - Claim: After Janssen, Pyrexia, Headache, Hyperhidrosis typically occur as Pyrexia → Headache → Hyperhidrosis.

## S-V2  (sequence, vaccine, PROP)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 275 viable | 275 supported-capable (true cases) | 275 refuted-capable
- **Core**: events ['Chills', 'Fatigue', 'Headache'], cohort Janssen
- **Conditioned counts**: k=8 / n=28  (rate 0.2857)
- **Categorical test**: binomial exact, p = 0.1216 (not significant)
    - *how p is computed*: two-sided exact binomial -- sum the Binomial(n, p0) probabilities of outcomes no more likely than the observed k (null p0 = 1/2 pairwise/co-occurs, 1/6 sequence, 1/3 first-among-3)
- **Position-based test**: Friedman (Q=7.71 df=2; n=88 reports), p = 0.02115
    - *how p is computed*: Friedman -- rank the three events within each report (ties averaged), chi-square (df=2) on the rank sums
- **95% CI**: [0.1525, 0.4706], effect size 0.2868
- **SUPPORTED** example:
    - Q: What fraction of Janssen reports show the sequence Headache → Chills → Fatigue?
    - Claim: In about 29% of Janssen reports, the sequence is Headache → Chills → Fatigue.
- **REFUTED** example:
    - Q: What fraction of Janssen reports show the sequence Headache → Chills → Fatigue?
    - Claim: In about 49% of Janssen reports, the sequence is Headache → Chills → Fatigue.

## S-V3  (sequence, vaccine, CHOICE)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 180/192 (93.8%) fail)
- **Qualified cores**: 275 viable | 192 supported-capable (true cases) | 192 refuted-capable
- **Core**: events ['Fatigue', 'Headache', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=8 / n=25  (rate 0.32)
- **Categorical test**: multinomial GOF (exact), p = 0.03251 (significant)
    - *how p is computed*: exact multinomial goodness-of-fit -- sum the multinomial probabilities of every table (same n) whose chi-square statistic vs uniform is >= the observed
- **Position-based test**: Friedman (Q=0.35 df=2; n=90 reports), p = 0.8412
    - *how p is computed*: Friedman -- rank the three events within each report (ties averaged), chi-square (df=2) on the rank sums
- **95% CI**: [0.1721, 0.5159], effect size 0.3615
- **Options**: ['Fatigue → Headache → Pyrexia', 'Fatigue → Pyrexia → Headache', 'Headache → Fatigue → Pyrexia', 'Headache → Pyrexia → Fatigue', 'Pyrexia → Fatigue → Headache', 'Pyrexia → Headache → Fatigue']  ->  correct: **Headache → Pyrexia → Fatigue**
- **SUPPORTED** example:
    - Q: After Janssen, what is the most common ordering of Headache, Pyrexia, Fatigue?
    - Claim: After Janssen, the most common ordering of Headache, Pyrexia, Fatigue is Headache → Pyrexia → Fatigue.
- **REFUTED** example:
    - Q: After Janssen, what is the most common ordering of Fatigue, Pyrexia, Headache?
    - Claim: After Janssen, the most common ordering of Fatigue, Pyrexia, Headache is Fatigue → Pyrexia → Headache.

## S-V4  (sequence, vaccine, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 225/236 (95.3%) fail)
- **Qualified cores**: 275 viable | 62 supported-capable (true cases) | 174 refuted-capable
- **Core**: events ['Headache', 'Hyperhidrosis', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=7 / n=13  (rate 0.5385)
- **Categorical test**: multinomial GOF (exact), p = 0.01523 (significant)
    - *how p is computed*: exact multinomial goodness-of-fit -- sum the multinomial probabilities of every table (same n) whose chi-square statistic vs uniform is >= the observed
- **Position-based test**: Kendall's W (W=0.184; n=33 reports), p = 0.002276
    - *how p is computed*: Kendall's W -- normalised concordance (0..1) of the within-report rankings; p from chi-square on n(k-1)W
- **95% CI**: [0.2914, 0.7679], effect size 0.8067
- **SUPPORTED** example:
    - Q: After Janssen, is the ordering of Headache, Hyperhidrosis, Pyrexia consistent across reports?
    - Claim: After Janssen, the ordering of Headache, Hyperhidrosis, Pyrexia is consistent across reports.

## S-M1  (sequence, multi, BOOL)
- **Presented example**: ✗ FAILED (gold-vs-significance over this template's cores: 90/90 (100.0%) fail)
- **Qualified cores**: 90 viable | 44 supported-capable (true cases) | 46 refuted-capable
- **Core**: events ['Fatigue', 'Headache', 'Pain'], cohort Moderna vs Janssen
- **Conditioned counts**: k=1 / n=13  |  cohort2 k=7 / n=18  (rate 0.0769)
- **⚠ P-VALUE vs GOLD MISMATCH** (red in the LaTeX findings): type1 (gold set but the test is not significant)
- **Categorical test**: Fisher exact (2x2), p = 0.09535 (not significant)
    - *how p is computed*: Fisher exact -- sum the hypergeometric probabilities of the 2x2 tables with the observed margins that are <= the observed table's probability
- **Position-based test**: Mann-Whitney U (per event) (Fatigue's within-triple rank between Moderna/Janssen; n=48/81), p = 0.7497
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [-0.5456, 0.0045], effect size -0.7846
- **SUPPORTED** example:
    - Q: Does the Fatigue → Headache → Pain rate differ between Moderna and Janssen?
    - Claim: The Fatigue → Headache → Pain rate differs between Moderna and Janssen.

## S-M2  (sequence, multi, CHOICE)
- **Presented example**: ✗ FAILED (gold-vs-significance over this template's cores: 75/75 (100.0%) fail)
- **Qualified cores**: 90 viable | 75 supported-capable (true cases) | 75 refuted-capable
- **Core**: events ['Fatigue', 'Headache', 'Pain'], cohort Moderna vs Janssen
- **Conditioned counts**: k=1 / n=13  |  cohort2 k=7 / n=18  (rate 0.0769)
- **⚠ P-VALUE vs GOLD MISMATCH** (red in the LaTeX findings): type1 (gold set but the test is not significant)
- **Categorical test**: Fisher exact (2x2), p = 0.09535 (not significant)
    - *how p is computed*: Fisher exact -- sum the hypergeometric probabilities of the 2x2 tables with the observed margins that are <= the observed table's probability
- **Position-based test**: Mann-Whitney U (per event) (Fatigue's within-triple rank between Moderna/Janssen; n=48/81), p = 0.7497
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [-0.5456, 0.0045], effect size -0.7846
- **Options**: ['Moderna', 'Janssen']  ->  correct: **Janssen**
- **SUPPORTED** example:
    - Q: Is the sequence Fatigue → Headache → Pain more common after Janssen or Moderna?
    - Claim: The sequence Fatigue → Headache → Pain is more common after Janssen than Moderna.
- **REFUTED** example:
    - Q: Is the sequence Fatigue → Headache → Pain more common after Moderna or Janssen?
    - Claim: The sequence Fatigue → Headache → Pain is more common after Moderna than Janssen.

## S-M3  (sequence, multi, BOOL)
- **Presented example**: ✗ FAILED (gold-vs-significance over this template's cores: 90/90 (100.0%) fail)
- **Qualified cores**: 90 viable | 25 supported-capable (true cases) | 65 refuted-capable
- **Core**: events ['Fatigue', 'Pain', 'Pyrexia'], cohort Moderna vs Janssen
- **Conditioned counts**: k=5 / n=12  |  cohort2 k=6 / n=15  (rate 0.4167)
- **⚠ P-VALUE vs GOLD MISMATCH** (red in the LaTeX findings): type1 (gold set but the test is not significant)
- **Categorical test**: Fisher-Freeman-Halton (exact), p = 0.2482 (not significant)
    - *how p is computed*: Fisher-Freeman-Halton -- sum the probabilities of every 2xk table with the observed margins that are <= the observed table's
- **Position-based test**: Mann-Whitney U (per event) (Fatigue's within-triple rank between Moderna/Janssen; n=39/65), p = 0.6701
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **SUPPORTED** example:
    - Q: Is the typical ordering of Fatigue, Pain, Pyrexia the same after Moderna and Janssen?
    - Claim: The typical ordering of Fatigue, Pain, Pyrexia is the same after Moderna and Janssen.

## F-R1  (first_last, report, CHOICE)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 3166 viable | 1196 supported-capable (true cases) | 3166 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain', 'Asthenia'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Categorical test**: none (report-level: single observation, no sampling distribution)
- **Options**: ['Dizziness', 'Injection site pain', 'Asthenia']  ->  correct: **Dizziness**
- **SUPPORTED** example:
    - Q: In report VAERS-916915, which of Dizziness, Injection site pain, Asthenia occurs first?
    - Claim: In report VAERS-916915, Dizziness occurs first among Dizziness, Injection site pain, Asthenia.
- **REFUTED** example:
    - Q: In report VAERS-916915, which of Injection site pain, Dizziness, Asthenia occurs first?
    - Claim: In report VAERS-916915, Injection site pain occurs first among Injection site pain, Dizziness, Asthenia.

## F-R2  (first_last, report, CHOICE)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 3166 viable | 1299 supported-capable (true cases) | 3166 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain', 'Asthenia'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Categorical test**: none (report-level: single observation, no sampling distribution)
- **Options**: ['Dizziness', 'Injection site pain', 'Asthenia']  ->  correct: **Asthenia**
- **SUPPORTED** example:
    - Q: In report VAERS-916915, which of Asthenia, Dizziness, Injection site pain occurs last?
    - Claim: In report VAERS-916915, Injection site pain occurs last among Asthenia, Dizziness, Injection site pain.
- **REFUTED** example:
    - Q: In report VAERS-916915, which of Dizziness, Injection site pain, Asthenia occurs last?
    - Claim: In report VAERS-916915, Asthenia occurs last among Dizziness, Injection site pain, Asthenia.

## F-R3  (first_last, report, BOOL)
- **Presented example**: — (no significance test: PROP / report-level) (gold-vs-significance over this template's cores: n/a fail)
- **Qualified cores**: 3166 viable | 1196 supported-capable (true cases) | 1196 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain', 'Asthenia'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Categorical test**: none (report-level: single observation, no sampling distribution)
- **SUPPORTED** example:
    - Q: In report VAERS-916915, is Dizziness the first of Dizziness, Injection site pain, Asthenia to occur?
    - Claim: In report VAERS-916915, Dizziness is the first of Dizziness, Injection site pain, Asthenia to occur.
- **REFUTED** example:
    - Q: In report VAERS-916915, is Injection site pain the first of Injection site pain, Dizziness, Asthenia to occur?
    - Claim: In report VAERS-916915, Injection site pain is the first of Injection site pain, Dizziness, Asthenia to occur.

## F-V1  (first_last, vaccine, CHOICE)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 42/67 (62.7%) fail)
- **Qualified cores**: 82 viable | 67 supported-capable (true cases) | 82 refuted-capable
- **Core**: events ['Chills', 'Headache', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=22 / n=116  (rate 0.1897)
- **Categorical test**: multinomial GOF (chi-square), p = 0.0002104 (significant)
    - *how p is computed*: chi-square goodness-of-fit vs uniform (large-n approximation, used only when every expected cell >= 5)
- **Position-based test**: Friedman (Q=13.05 df=2; n=116 reports), p = 0.001469
    - *how p is computed*: Friedman -- rank the three events within each report (ties averaged), chi-square (df=2) on the rank sums
- **95% CI**: [0.1287, 0.2705], effect size -0.3298
- **Options**: ['Chills', 'Headache', 'Pyrexia']  ->  correct: **Headache**
- **SUPPORTED** example:
    - Q: After Janssen, which of Headache, Chills, Pyrexia typically occurs first?
    - Claim: After Janssen, Headache typically occurs first among Headache, Chills, Pyrexia.
- **REFUTED** example:
    - Q: After Janssen, which of Pyrexia, Chills, Headache typically occurs first?
    - Claim: After Janssen, Pyrexia typically occurs first among Pyrexia, Chills, Headache.

## F-V2  (first_last, vaccine, CHOICE)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 36/73 (49.3%) fail)
- **Qualified cores**: 82 viable | 73 supported-capable (true cases) | 82 refuted-capable
- **Core**: events ['Chills', 'Headache', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=28 / n=116  (rate 0.2414)
- **Categorical test**: multinomial GOF (chi-square), p = 0.0001234 (significant)
    - *how p is computed*: chi-square goodness-of-fit vs uniform (large-n approximation, used only when every expected cell >= 5)
- **Position-based test**: Friedman (Q=13.05 df=2; n=116 reports), p = 0.001469
    - *how p is computed*: Friedman -- rank the three events within each report (ties averaged), chi-square (df=2) on the rank sums
- **95% CI**: [0.1726, 0.3267], effect size -0.2038
- **Options**: ['Chills', 'Headache', 'Pyrexia']  ->  correct: **Headache**
- **SUPPORTED** example:
    - Q: After Janssen, which of Headache, Chills, Pyrexia typically occurs last?
    - Claim: After Janssen, Pyrexia typically occurs last among Headache, Chills, Pyrexia.
- **REFUTED** example:
    - Q: After Janssen, which of Chills, Headache, Pyrexia typically occurs last?
    - Claim: After Janssen, Pyrexia typically occurs last among Chills, Headache, Pyrexia.

## F-V3  (first_last, vaccine, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 41/82 (50.0%) fail)
- **Qualified cores**: 82 viable | 2 supported-capable (true cases) | 82 refuted-capable
- **Core**: events ['Headache', 'Injection site pain', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=20 / n=39  (rate 0.5128)
- **Categorical test**: binomial exact, p = 0.02573 (significant)
    - *how p is computed*: two-sided exact binomial -- sum the Binomial(n, p0) probabilities of outcomes no more likely than the observed k (null p0 = 1/2 pairwise/co-occurs, 1/6 sequence, 1/3 first-among-3)
- **Position-based test**: Friedman (Q=10.36 df=2; n=39 reports), p = 0.005622
    - *how p is computed*: Friedman -- rank the three events within each report (ties averaged), chi-square (df=2) on the rank sums
- **95% CI**: [0.362, 0.6613], effect size 0.3655
- **SUPPORTED** example:
    - Q: After Janssen, is Injection site pain usually the first of Injection site pain, Headache, Pyrexia?
    - Claim: After Janssen, Injection site pain is usually the first of Injection site pain, Headache, Pyrexia.
- **REFUTED** example:
    - Q: After Janssen, is Pyrexia usually the first of Pyrexia, Headache, Injection site pain?
    - Claim: After Janssen, Pyrexia is usually the first of Pyrexia, Headache, Injection site pain.

## F-M1  (first_last, multi, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 44/46 (95.7%) fail)
- **Qualified cores**: 46 viable | 23 supported-capable (true cases) | 23 refuted-capable
- **Core**: events ['Chills', 'Pain', 'Pyrexia'], cohort Pfizer vs Moderna
- **Conditioned counts**: k=7 / n=57  |  cohort2 k=None / n=52  (rate 0.1228)
- **Categorical test**: Fisher-Freeman-Halton (exact), p = 0.013 (significant)
    - *how p is computed*: Fisher-Freeman-Halton -- sum the probabilities of every 2xk table with the observed margins that are <= the observed table's
- **Position-based test**: Mann-Whitney U (per event) (Chills's within-triple rank between Pfizer/Moderna; n=57/52), p = 0.02167
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **REFUTED** example:
    - Q: Is the typical first event among Chills, Pain, Pyrexia the same after Pfizer and Moderna?
    - Claim: The typical first event among Chills, Pain, Pyrexia is the same after Pfizer and Moderna.

## F-M2  (first_last, multi, BOOL)
- **Presented example**: ✓ SUCCESSFUL (gold-vs-significance over this template's cores: 44/46 (95.7%) fail)
- **Qualified cores**: 46 viable | 23 supported-capable (true cases) | 23 refuted-capable
- **Core**: events ['Chills', 'Pain', 'Pyrexia'], cohort Pfizer vs Moderna
- **Conditioned counts**: k=7 / n=57  |  cohort2 k=None / n=52  (rate 0.1228)
- **Categorical test**: Fisher-Freeman-Halton (exact), p = 0.013 (significant)
    - *how p is computed*: Fisher-Freeman-Halton -- sum the probabilities of every 2xk table with the observed margins that are <= the observed table's
- **Position-based test**: Mann-Whitney U (per event) (Chills's within-triple rank between Pfizer/Moderna; n=57/52), p = 0.02167
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **SUPPORTED** example:
    - Q: Do Pfizer and Moderna differ in which of Chills, Pain, Pyrexia appears first?
    - Claim: Pfizer and Moderna differ in which of Chills, Pain, Pyrexia appears first.

## F-M3  (first_last, multi, CHOICE)
- **Presented example**: ✗ FAILED (gold-vs-significance over this template's cores: 45/45 (100.0%) fail)
- **Qualified cores**: 46 viable | 45 supported-capable (true cases) | 45 refuted-capable
- **Core**: events ['Chills', 'Headache', 'Pyrexia'], cohort Pfizer vs Moderna
- **Conditioned counts**: k=10 / n=67  |  cohort2 k=7 / n=60  (rate 0.1493)
- **⚠ P-VALUE vs GOLD MISMATCH** (red in the LaTeX findings): type1 (gold set but the test is not significant)
- **Categorical test**: Fisher exact (2x2), p = 0.6141 (not significant)
    - *how p is computed*: Fisher exact -- sum the hypergeometric probabilities of the 2x2 tables with the observed margins that are <= the observed table's probability
- **Position-based test**: Mann-Whitney U (per event) (Chills's within-triple rank between Pfizer/Moderna; n=67/60), p = 0.7023
    - *how p is computed*: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **95% CI**: [-0.0916, 0.1523], effect size 0.0961
- **Options**: ['Pfizer', 'Moderna']  ->  correct: **Pfizer**
- **SUPPORTED** example:
    - Q: Is Headache the first event more often after Pfizer or Moderna?
    - Claim: Headache is the first event more often after Pfizer than Moderna.
- **REFUTED** example:
    - Q: Is Headache the first event more often after Moderna or Pfizer?
    - Claim: Headache is the first event more often after Moderna than Pfizer.

## Statistical methods (how each p-value is computed)

- **Binomial exact**: two-sided exact binomial -- sum the Binomial(n, p0) probabilities of outcomes no more likely than the observed k (null p0 = 1/2 pairwise/co-occurs, 1/6 sequence, 1/3 first-among-3)
- **Fisher exact**: Fisher exact -- sum the hypergeometric probabilities of the 2x2 tables with the observed margins that are <= the observed table's probability
- **Multinomial GOF (exact)**: exact multinomial goodness-of-fit -- sum the multinomial probabilities of every table (same n) whose chi-square statistic vs uniform is >= the observed
- **Multinomial GOF (chi-square)**: chi-square goodness-of-fit vs uniform (large-n approximation, used only when every expected cell >= 5)
- **Fisher-Freeman-Halton**: Fisher-Freeman-Halton -- sum the probabilities of every 2xk table with the observed margins that are <= the observed table's
- **Homogeneity (chi-square)**: chi-square test of homogeneity (used only when every expected cell >= 5)
- **Wilcoxon signed-rank**: Wilcoxon signed-rank -- rank |d| where d=level(A)-level(B) (co-exist d=0 dropped), sum the signed ranks; exact sign-flip null for small n, else normal approximation with tie/continuity correction
- **Mann-Whitney U**: Mann-Whitney U -- pool and rank the two cohorts' values, U from the rank-sum; normal approximation with tie correction
- **Friedman**: Friedman -- rank the three events within each report (ties averaged), chi-square (df=2) on the rank sums
- **Kendall's W**: Kendall's W -- normalised concordance (0..1) of the within-report rankings; p from chi-square on n(k-1)W

