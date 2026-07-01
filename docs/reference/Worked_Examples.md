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

## P-R1  (pairwise, report, BOOL)
- **Qualified cores**: 3166 viable | 1196 supported-capable (true cases) | 3166 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Test**: none (report-level: single observation, no sampling distribution)
- **SUPPORTED** example:
    - Q: Did Dizziness occur before Injection site pain in report VAERS-916915?
    - Claim: In report VAERS-916915, Dizziness occurred before Injection site pain.
- **REFUTED** example:
    - Q: Did Injection site pain occur before Dizziness in report VAERS-916915?
    - Claim: In report VAERS-916915, Injection site pain occurred before Dizziness.

## P-R2  (pairwise, report, CHOICE)
- **Qualified cores**: 3166 viable | 1196 supported-capable (true cases) | 1196 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Test**: none (report-level: single observation, no sampling distribution)
- **Options**: ['Dizziness', 'Injection site pain']  ->  correct: **Dizziness**
- **SUPPORTED** example:
    - Q: Which came first in report VAERS-916915, Dizziness or Injection site pain?
    - Claim: In report VAERS-916915, Dizziness came first, before Injection site pain.
- **REFUTED** example:
    - Q: Which came first in report VAERS-916915, Injection site pain or Dizziness?
    - Claim: In report VAERS-916915, Injection site pain came first, before Dizziness.

## P-V1  (pairwise, vaccine, BOOL)
- **Qualified cores**: 173 viable | 168 supported-capable (true cases) | 168 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Janssen
- **Conditioned counts**: k=44 / n=119  (rate 0.3697)
- **Test**: binomial exact, p = 0.005727 (significant)
- **95% CI**: [0.2884, 0.4593], effect size -0.2635
- **SUPPORTED** example:
    - Q: Does Headache typically occur before Fatigue after Janssen?
    - Claim: After Janssen, Headache typically occurs before Fatigue.
- **REFUTED** example:
    - Q: Does Fatigue typically occur before Headache after Janssen?
    - Claim: After Janssen, Fatigue typically occurs before Headache.

## P-V2  (pairwise, vaccine, PROP)
- **Qualified cores**: 173 viable | 173 supported-capable (true cases) | 173 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Janssen
- **Conditioned counts**: k=44 / n=119  (rate 0.3697)
- **Test**: binomial exact, p = 0.005727 (significant)
- **95% CI**: [0.2884, 0.4593], effect size -0.2635
- **SUPPORTED** example:
    - Q: In what fraction of Janssen reports does Fatigue precede Headache?
    - Claim: In about 37% of Janssen reports, Fatigue precedes Headache.
- **REFUTED** example:
    - Q: In what fraction of Janssen reports does Fatigue precede Headache?
    - Claim: In about 57% of Janssen reports, Fatigue precedes Headache.

## P-V3  (pairwise, vaccine, CHOICE)
- **Qualified cores**: 173 viable | 168 supported-capable (true cases) | 168 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Janssen
- **Conditioned counts**: k=44 / n=119  (rate 0.3697)
- **Test**: binomial exact, p = 0.005727 (significant)
- **95% CI**: [0.2884, 0.4593], effect size -0.2635
- **Options**: ['Fatigue', 'Headache']  ->  correct: **Headache**
- **SUPPORTED** example:
    - Q: After Janssen, which usually comes first, Headache or Fatigue?
    - Claim: After Janssen, Headache usually comes before Fatigue.
- **REFUTED** example:
    - Q: After Janssen, which usually comes first, Fatigue or Headache?
    - Claim: After Janssen, Fatigue usually comes before Headache.

## P-M1  (pairwise, multi, BOOL)
- **Qualified cores**: 99 viable | 39 supported-capable (true cases) | 60 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Moderna vs Janssen
- **Conditioned counts**: k=24 / n=67  |  cohort2 k=44 / n=119  (rate 0.3582)
- **Test**: Fisher exact (2x2), p = 1 (not significant)
- **95% CI**: [-0.1489, 0.1331], effect size -0.024
- **REFUTED** example:
    - Q: Does the Fatigue-before-Headache rate differ between Moderna and Janssen?
    - Claim: The Fatigue-before-Headache rate differs between Moderna and Janssen.

## P-M2  (pairwise, multi, CHOICE)
- **Qualified cores**: 99 viable | 99 supported-capable (true cases) | 99 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Moderna vs Janssen
- **Conditioned counts**: k=24 / n=67  |  cohort2 k=44 / n=119  (rate 0.3582)
- **Test**: Fisher exact (2x2), p = 1 (not significant)
- **95% CI**: [-0.1489, 0.1331], effect size -0.024
- **Options**: ['Moderna', 'Janssen']  ->  correct: **Janssen**
- **SUPPORTED** example:
    - Q: After which vaccine, Janssen or Moderna, does Fatigue more often precede Headache?
    - Claim: Fatigue precedes Headache more often after Janssen than after Moderna.
- **REFUTED** example:
    - Q: After which vaccine, Moderna or Janssen, does Fatigue more often precede Headache?
    - Claim: Fatigue precedes Headache more often after Moderna than after Janssen.

## C-R1  (pairwise, report, BOOL)
- **Qualified cores**: 3166 viable | 1970 supported-capable (true cases) | 1196 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Test**: none (report-level: single observation, no sampling distribution)
- **REFUTED** example:
    - Q: Do Dizziness and Injection site pain co-occur in report VAERS-916915?
    - Claim: In report VAERS-916915, Dizziness and Injection site pain co-occur.

## C-V1  (pairwise, vaccine, BOOL)
- **Qualified cores**: 374 viable | 90 supported-capable (true cases) | 271 refuted-capable
- **Core**: events ['Headache', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=111 / n=213  (rate 0.5211)
- **Test**: binomial exact, p = 0.5837 (not significant)
- **95% CI**: [0.4543, 0.5872], effect size 0.0423
- **SUPPORTED** example:
    - Q: Do Headache and Pyrexia typically co-occur after Janssen?
    - Claim: After Janssen, Headache and Pyrexia typically co-occur.

## C-V2  (pairwise, vaccine, PROP)
- **Qualified cores**: 374 viable | 374 supported-capable (true cases) | 374 refuted-capable
- **Core**: events ['Headache', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=111 / n=213  (rate 0.5211)
- **Test**: binomial exact, p = 0.5837 (not significant)
- **95% CI**: [0.4543, 0.5872], effect size 0.0423
- **SUPPORTED** example:
    - Q: What fraction of Janssen reports show Headache and Pyrexia together?
    - Claim: In about 52% of Janssen reports, Headache and Pyrexia occur together.
- **REFUTED** example:
    - Q: What fraction of Janssen reports show Headache and Pyrexia together?
    - Claim: In about 72% of Janssen reports, Headache and Pyrexia occur together.

## C-V3  (pairwise, vaccine, BOOL)
- **Qualified cores**: 374 viable | 90 supported-capable (true cases) | 271 refuted-capable
- **Core**: events ['Headache', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=111 / n=213  (rate 0.5211)
- **Test**: binomial exact, p = 0.5837 (not significant)
- **95% CI**: [0.4543, 0.5872], effect size 0.0423
- **SUPPORTED** example:
    - Q: After Janssen, is co-occurrence the dominant relation for Headache and Pyrexia?
    - Claim: After Janssen, co-occurrence is the dominant relation for Headache and Pyrexia.

## C-M1  (pairwise, multi, BOOL)
- **Qualified cores**: 232 viable | 89 supported-capable (true cases) | 143 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Moderna vs Janssen
- **Conditioned counts**: k=70 / n=137  |  cohort2 k=77 / n=196  (rate 0.5109)
- **Test**: Fisher exact (2x2), p = 0.03398 (significant)
- **95% CI**: [0.0098, 0.2234], effect size 0.2379
- **SUPPORTED** example:
    - Q: Does the Fatigue-Headache co-occurrence rate differ between Moderna and Janssen?
    - Claim: The Fatigue-Headache co-occurrence rate differs between Moderna and Janssen.

## C-M2  (pairwise, multi, CHOICE)
- **Qualified cores**: 232 viable | 232 supported-capable (true cases) | 232 refuted-capable
- **Core**: events ['Fatigue', 'Headache'], cohort Moderna vs Janssen
- **Conditioned counts**: k=70 / n=137  |  cohort2 k=77 / n=196  (rate 0.5109)
- **Test**: Fisher exact (2x2), p = 0.03398 (significant)
- **95% CI**: [0.0098, 0.2234], effect size 0.2379
- **Options**: ['Moderna', 'Janssen']  ->  correct: **Moderna**
- **SUPPORTED** example:
    - Q: After which vaccine, Moderna or Janssen, do Fatigue and Headache more often co-occur?
    - Claim: Fatigue and Headache co-occur more often after Moderna than after Janssen.
- **REFUTED** example:
    - Q: After which vaccine, Janssen or Moderna, do Fatigue and Headache more often co-occur?
    - Claim: Fatigue and Headache co-occur more often after Janssen than after Moderna.

## S-R1  (sequence, report, BOOL)
- **Qualified cores**: 3166 viable | 489 supported-capable (true cases) | 3166 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain', 'Asthenia'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Test**: none (report-level: single observation, no sampling distribution)
- **SUPPORTED** example:
    - Q: Do Dizziness, Injection site pain, Asthenia occur in the order Dizziness → Injection site pain → Asthenia in report VAERS-916915?
    - Claim: In report VAERS-916915, Dizziness, Injection site pain, Asthenia occur in the order Dizziness → Injection site pain → Asthenia.
- **REFUTED** example:
    - Q: Do Asthenia, Injection site pain, Dizziness occur in the order Asthenia → Injection site pain → Dizziness in report VAERS-916915?
    - Claim: In report VAERS-916915, Asthenia, Injection site pain, Dizziness occur in the order Asthenia → Injection site pain → Dizziness.

## S-V1  (sequence, vaccine, BOOL)
- **Qualified cores**: 275 viable | 62 supported-capable (true cases) | 236 refuted-capable
- **Core**: events ['Headache', 'Hyperhidrosis', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=0 / n=13  (rate 0.0)
- **Test**: binomial exact, p = 0.1446 (not significant)
- **95% CI**: [0.0, 0.2281], effect size -0.8411
- **SUPPORTED** example:
    - Q: After Janssen, do Headache, Pyrexia, Hyperhidrosis typically occur as Headache → Pyrexia → Hyperhidrosis?
    - Claim: After Janssen, Headache, Pyrexia, Hyperhidrosis typically occur as Headache → Pyrexia → Hyperhidrosis.
- **REFUTED** example:
    - Q: After Janssen, do Pyrexia, Headache, Hyperhidrosis typically occur as Pyrexia → Headache → Hyperhidrosis?
    - Claim: After Janssen, Pyrexia, Headache, Hyperhidrosis typically occur as Pyrexia → Headache → Hyperhidrosis.

## S-V2  (sequence, vaccine, PROP)
- **Qualified cores**: 275 viable | 275 supported-capable (true cases) | 275 refuted-capable
- **Core**: events ['Chills', 'Fatigue', 'Headache'], cohort Janssen
- **Conditioned counts**: k=1 / n=28  (rate 0.0357)
- **Test**: binomial exact, p = 0.0733 (not significant)
- **95% CI**: [0.0063, 0.1771], effect size -0.4608
- **SUPPORTED** example:
    - Q: What fraction of Janssen reports show the sequence Chills → Fatigue → Headache?
    - Claim: In about 4% of Janssen reports, the sequence is Chills → Fatigue → Headache.
- **REFUTED** example:
    - Q: What fraction of Janssen reports show the sequence Chills → Fatigue → Headache?
    - Claim: In about 24% of Janssen reports, the sequence is Chills → Fatigue → Headache.

## S-V3  (sequence, vaccine, CHOICE)
- **Qualified cores**: 275 viable | 192 supported-capable (true cases) | 192 refuted-capable
- **Core**: events ['Fatigue', 'Headache', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=8 / n=25  (rate 0.32)
- **Test**: multinomial GOF (exact), p = 0.03251 (significant)
- **95% CI**: [0.1721, 0.5159], effect size 0.3615
- **Options**: ['Fatigue → Headache → Pyrexia', 'Fatigue → Pyrexia → Headache', 'Headache → Fatigue → Pyrexia', 'Headache → Pyrexia → Fatigue', 'Pyrexia → Fatigue → Headache', 'Pyrexia → Headache → Fatigue']  ->  correct: **Headache → Pyrexia → Fatigue**
- **SUPPORTED** example:
    - Q: After Janssen, what is the most common ordering of Headache, Pyrexia, Fatigue?
    - Claim: After Janssen, the most common ordering of Headache, Pyrexia, Fatigue is Headache → Pyrexia → Fatigue.
- **REFUTED** example:
    - Q: After Janssen, what is the most common ordering of Fatigue, Pyrexia, Headache?
    - Claim: After Janssen, the most common ordering of Fatigue, Pyrexia, Headache is Fatigue → Pyrexia → Headache.

## S-V4  (sequence, vaccine, BOOL)
- **Qualified cores**: 275 viable | 62 supported-capable (true cases) | 174 refuted-capable
- **Core**: events ['Chills', 'Fatigue', 'Headache'], cohort Janssen
- **Conditioned counts**: k=8 / n=28  (rate 0.2857)
- **Test**: multinomial GOF (exact), p = 0.1181 (not significant)
- **95% CI**: [0.1525, 0.4706], effect size 0.2868
- **REFUTED** example:
    - Q: After Janssen, is the ordering of Chills, Fatigue, Headache consistent across reports?
    - Claim: After Janssen, the ordering of Chills, Fatigue, Headache is consistent across reports.

## S-M1  (sequence, multi, BOOL)
- **Qualified cores**: 90 viable | 44 supported-capable (true cases) | 46 refuted-capable
- **Core**: events ['Fatigue', 'Headache', 'Pain'], cohort Moderna vs Janssen
- **Conditioned counts**: k=1 / n=13  |  cohort2 k=7 / n=18  (rate 0.0769)
- **Test**: Fisher exact (2x2), p = 0.09535 (not significant)
- **95% CI**: [-0.5456, 0.0045], effect size -0.7846
- **SUPPORTED** example:
    - Q: Does the Fatigue → Headache → Pain rate differ between Moderna and Janssen?
    - Claim: The Fatigue → Headache → Pain rate differs between Moderna and Janssen.

## S-M2  (sequence, multi, CHOICE)
- **Qualified cores**: 90 viable | 75 supported-capable (true cases) | 75 refuted-capable
- **Core**: events ['Fatigue', 'Headache', 'Pain'], cohort Moderna vs Janssen
- **Conditioned counts**: k=1 / n=13  |  cohort2 k=7 / n=18  (rate 0.0769)
- **Test**: Fisher exact (2x2), p = 0.09535 (not significant)
- **95% CI**: [-0.5456, 0.0045], effect size -0.7846
- **Options**: ['Moderna', 'Janssen']  ->  correct: **Janssen**
- **SUPPORTED** example:
    - Q: Is the sequence Fatigue → Headache → Pain more common after Janssen or Moderna?
    - Claim: The sequence Fatigue → Headache → Pain is more common after Janssen than Moderna.
- **REFUTED** example:
    - Q: Is the sequence Fatigue → Headache → Pain more common after Moderna or Janssen?
    - Claim: The sequence Fatigue → Headache → Pain is more common after Moderna than Janssen.

## S-M3  (sequence, multi, BOOL)
- **Qualified cores**: 90 viable | 25 supported-capable (true cases) | 65 refuted-capable
- **Core**: events ['Fatigue', 'Headache', 'Pain'], cohort Moderna vs Janssen
- **Conditioned counts**: k=5 / n=13  |  cohort2 k=7 / n=18  (rate 0.3846)
- **Test**: Fisher-Freeman-Halton (exact), p = 0.332 (not significant)
- **REFUTED** example:
    - Q: Is the typical ordering of Fatigue, Headache, Pain the same after Moderna and Janssen?
    - Claim: The typical ordering of Fatigue, Headache, Pain is the same after Moderna and Janssen.

## F-R1  (first_last, report, CHOICE)
- **Qualified cores**: 3166 viable | 1196 supported-capable (true cases) | 3166 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain', 'Asthenia'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Test**: none (report-level: single observation, no sampling distribution)
- **Options**: ['Dizziness', 'Injection site pain', 'Asthenia']  ->  correct: **Dizziness**
- **SUPPORTED** example:
    - Q: In report VAERS-916915, which of Dizziness, Injection site pain, Asthenia occurs first?
    - Claim: In report VAERS-916915, Dizziness occurs first among Dizziness, Injection site pain, Asthenia.
- **REFUTED** example:
    - Q: In report VAERS-916915, which of Injection site pain, Dizziness, Asthenia occurs first?
    - Claim: In report VAERS-916915, Injection site pain occurs first among Injection site pain, Dizziness, Asthenia.

## F-R2  (first_last, report, CHOICE)
- **Qualified cores**: 3166 viable | 1299 supported-capable (true cases) | 3166 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain', 'Asthenia'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Test**: none (report-level: single observation, no sampling distribution)
- **Options**: ['Dizziness', 'Injection site pain', 'Asthenia']  ->  correct: **Asthenia**
- **SUPPORTED** example:
    - Q: In report VAERS-916915, which of Asthenia, Dizziness, Injection site pain occurs last?
    - Claim: In report VAERS-916915, Injection site pain occurs last among Asthenia, Dizziness, Injection site pain.
- **REFUTED** example:
    - Q: In report VAERS-916915, which of Dizziness, Injection site pain, Asthenia occurs last?
    - Claim: In report VAERS-916915, Asthenia occurs last among Dizziness, Injection site pain, Asthenia.

## F-R3  (first_last, report, BOOL)
- **Qualified cores**: 3166 viable | 1196 supported-capable (true cases) | 1196 refuted-capable
- **Core**: events ['Dizziness', 'Injection site pain', 'Asthenia'], cohort report VAERS-916915
- **Conditioned counts**: (single report; deterministic)
- **Test**: none (report-level: single observation, no sampling distribution)
- **SUPPORTED** example:
    - Q: In report VAERS-916915, is Dizziness the first of Dizziness, Injection site pain, Asthenia to occur?
    - Claim: In report VAERS-916915, Dizziness is the first of Dizziness, Injection site pain, Asthenia to occur.
- **REFUTED** example:
    - Q: In report VAERS-916915, is Injection site pain the first of Injection site pain, Dizziness, Asthenia to occur?
    - Claim: In report VAERS-916915, Injection site pain is the first of Injection site pain, Dizziness, Asthenia to occur.

## F-V1  (first_last, vaccine, CHOICE)
- **Qualified cores**: 82 viable | 67 supported-capable (true cases) | 82 refuted-capable
- **Core**: events ['Chills', 'Headache', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=22 / n=116  (rate 0.1897)
- **Test**: multinomial GOF (chi-square), p = 0.0002104 (significant)
- **95% CI**: [0.1287, 0.2705], effect size -0.3298
- **Options**: ['Chills', 'Headache', 'Pyrexia']  ->  correct: **Headache**
- **SUPPORTED** example:
    - Q: After Janssen, which of Headache, Chills, Pyrexia typically occurs first?
    - Claim: After Janssen, Headache typically occurs first among Headache, Chills, Pyrexia.
- **REFUTED** example:
    - Q: After Janssen, which of Pyrexia, Chills, Headache typically occurs first?
    - Claim: After Janssen, Pyrexia typically occurs first among Pyrexia, Chills, Headache.

## F-V2  (first_last, vaccine, CHOICE)
- **Qualified cores**: 82 viable | 73 supported-capable (true cases) | 82 refuted-capable
- **Core**: events ['Chills', 'Headache', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=28 / n=116  (rate 0.2414)
- **Test**: multinomial GOF (chi-square), p = 0.0001234 (significant)
- **95% CI**: [0.1726, 0.3267], effect size -0.2038
- **Options**: ['Chills', 'Headache', 'Pyrexia']  ->  correct: **Headache**
- **SUPPORTED** example:
    - Q: After Janssen, which of Headache, Chills, Pyrexia typically occurs last?
    - Claim: After Janssen, Pyrexia typically occurs last among Headache, Chills, Pyrexia.
- **REFUTED** example:
    - Q: After Janssen, which of Chills, Headache, Pyrexia typically occurs last?
    - Claim: After Janssen, Pyrexia typically occurs last among Chills, Headache, Pyrexia.

## F-V3  (first_last, vaccine, BOOL)
- **Qualified cores**: 82 viable | 2 supported-capable (true cases) | 82 refuted-capable
- **Core**: events ['Headache', 'Injection site pain', 'Pyrexia'], cohort Janssen
- **Conditioned counts**: k=20 / n=39  (rate 0.5128)
- **Test**: binomial exact, p = 0.02573 (significant)
- **95% CI**: [0.362, 0.6613], effect size 0.3655
- **SUPPORTED** example:
    - Q: After Janssen, is Injection site pain usually the first of Injection site pain, Headache, Pyrexia?
    - Claim: After Janssen, Injection site pain is usually the first of Injection site pain, Headache, Pyrexia.
- **REFUTED** example:
    - Q: After Janssen, is Pyrexia usually the first of Pyrexia, Headache, Injection site pain?
    - Claim: After Janssen, Pyrexia is usually the first of Pyrexia, Headache, Injection site pain.

## F-M1  (first_last, multi, BOOL)
- **Qualified cores**: 46 viable | 23 supported-capable (true cases) | 23 refuted-capable
- **Core**: events ['Chills', 'Headache', 'Pyrexia'], cohort Pfizer vs Moderna
- **Conditioned counts**: k=10 / n=67  |  cohort2 k=None / n=60  (rate 0.1493)
- **Test**: Fisher-Freeman-Halton (exact), p = 0.5621 (not significant)
- **SUPPORTED** example:
    - Q: Is the typical first event among Chills, Headache, Pyrexia the same after Pfizer and Moderna?
    - Claim: The typical first event among Chills, Headache, Pyrexia is the same after Pfizer and Moderna.

## F-M2  (first_last, multi, BOOL)
- **Qualified cores**: 46 viable | 23 supported-capable (true cases) | 23 refuted-capable
- **Core**: events ['Chills', 'Headache', 'Pyrexia'], cohort Pfizer vs Moderna
- **Conditioned counts**: k=10 / n=67  |  cohort2 k=None / n=60  (rate 0.1493)
- **Test**: Fisher-Freeman-Halton (exact), p = 0.5621 (not significant)
- **REFUTED** example:
    - Q: Do Pfizer and Moderna differ in which of Chills, Headache, Pyrexia appears first?
    - Claim: Pfizer and Moderna differ in which of Chills, Headache, Pyrexia appears first.

## F-M3  (first_last, multi, CHOICE)
- **Qualified cores**: 46 viable | 45 supported-capable (true cases) | 45 refuted-capable
- **Core**: events ['Chills', 'Headache', 'Pyrexia'], cohort Pfizer vs Moderna
- **Conditioned counts**: k=10 / n=67  |  cohort2 k=7 / n=60  (rate 0.1493)
- **Test**: Fisher exact (2x2), p = 0.6141 (not significant)
- **95% CI**: [-0.0916, 0.1523], effect size 0.0961
- **Options**: ['Pfizer', 'Moderna']  ->  correct: **Pfizer**
- **SUPPORTED** example:
    - Q: Is Headache the first event more often after Pfizer or Moderna?
    - Claim: Headache is the first event more often after Pfizer than Moderna.
- **REFUTED** example:
    - Q: Is Headache the first event more often after Moderna or Pfizer?
    - Claim: Headache is the first event more often after Moderna than Pfizer.

