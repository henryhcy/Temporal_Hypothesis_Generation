# Pilot Distribution Report (Part A)

## A1. Viable-core counts per group

- Viable target per group: **50**
- Under-target groups (0): none
- Starved groups (0 viable): none

| group | viable | enumerated |
|---|---:|---:|
| P-R1 | 300 | 300 |
| P-R2 | 300 | 300 |
| P-V1 | 425 | 900 |
| P-V2 | 3015 | 5040 |
| P-V3 | 425 | 900 |
| P-V4 | 9067 | 16380 |
| P-M2 | 270 | 534 |
| C-R1 | 300 | 300 |
| C-V1 | 519 | 900 |
| C-V2 | 900 | 900 |
| C-V3 | 519 | 900 |
| S-R1 | 300 | 300 |
| S-V1 | 235 | 1680 |
| S-V3 | 235 | 1680 |
| F-R1 | 300 | 300 |
| F-R2 | 300 | 300 |
| F-R3 | 300 | 300 |
| F-V1 | 178 | 1680 |
| F-V2 | 218 | 1680 |
| F-V3 | 178 | 1680 |

## A2. Cohort-size (n) distribution per family

- **pairwise**: n=15140  min=10.0 p25=18.0 median=28.0 p75=47.0 max=465.0
  - histogram: {'<= 10': 306, '10-25': 6498, '25-50': 5124, '50-100': 2187, '100-250': 740, '> 250': 285}
- **sequence**: n=470  min=5.0 p25=5.0 median=7.0 p75=9.0 max=28.0
  - histogram: {'<= 10': 390, '10-25': 78, '25-50': 2, '50-100': 0, '100-250': 0, '> 250': 0}
- **first_last**: n=574  min=10.0 p25=11.0 median=14.0 p75=18.0 max=55.0
  - histogram: {'<= 10': 98, '10-25': 427, '25-50': 48, '50-100': 1, '100-250': 0, '> 250': 0}

## A3. Natural verdict distribution (no balancing)

| family | supported | refuted | insufficient |
|---|---:|---:|---:|
| pairwise | 0.3208 | 0.2598 | 0.4194 |
| sequence | 0.1721 | 0.0 | 0.8279 |
| first_last | 0.2372 | 0.0 | 0.7628 |

Per-group natural verdicts:

| group | supported | refuted | insufficient |
|---|---:|---:|---:|
| P-R1 | 1.0 | 0.0 | 0.0 |
| P-R2 | 1.0 | 0.0 | 0.0 |
| P-V1 | 0.3244 | 0.1256 | 0.55 |
| P-V2 | 0.3706 | 0.2248 | 0.4046 |
| P-V3 | 0.3244 | 0.1256 | 0.55 |
| P-V4 | 0.2867 | 0.2632 | 0.4501 |
| P-M2 | 0.206 | 0.2959 | 0.4981 |
| C-R1 | 0.6433 | 0.3567 | 0.0 |
| C-V1 | 0.1089 | 0.4533 | 0.4378 |
| C-V2 | 0.5 | 0.5 | 0.0 |
| C-V3 | 0.1967 | 0.3467 | 0.4567 |
| S-R1 | 1.0 | 0.0 | 0.0 |
| S-V1 | 0.0982 | 0.0 | 0.9018 |
| S-V3 | 0.0982 | 0.0 | 0.9018 |
| F-R1 | 1.0 | 0.0 | 0.0 |
| F-R2 | 1.0 | 0.0 | 0.0 |
| F-R3 | 1.0 | 0.0 | 0.0 |
| F-V1 | 0.094 | 0.0 | 0.906 |
| F-V2 | 0.1149 | 0.0 | 0.8851 |
| F-V3 | 0.094 | 0.0 | 0.906 |

## A4. Wilson CI-width distribution (single-proportion cores)

- summary: {'count': 15914, 'min': 0.0197, 'p25': 0.2551, 'median': 0.3193, 'p75': 0.4002, 'max': 0.6517}
- histogram: {'<= 0.15': 882, '0.15-0.3': 6007, '0.3-0.45': 7165, '0.45-0.6': 1650, '> 0.6': 210}
- fraction low-confidence (width > 0.30): **0.5671**
- provisional low-confidence cut = CI width > 0.30; A4 calibrates it

## A5. Multi-vaccine overlap and insufficiency

| pair | both clear | one thin | frac insufficient | enough? |
|---|---:|---:|---:|:--:|
| Pfizer+Moderna | 82 | 89 | 0.5205 | yes |
| Pfizer+Janssen | 102 | 108 | 0.5143 | yes |
| Moderna+Janssen | 86 | 67 | 0.4379 | yes |

- Janssen pairs lacking enough computable cores (fallback trigger): none

## A6. Representation diagnostics

- first/last tie-rate summary: {'count': 574, 'min': 0.0, 'p25': 0.36, 'median': 0.4545, 'p75': 0.56, 'max': 0.7347}
- first-level co-occurrence rate (reports whose earliest level has >1 term): **0.6226**
- duplicate-term-across-levels count: 7
- cycle check: N/A; disconnected-component rate: N/A
- _Annotations are stored as leveled orders (a single acyclic chain of co-exist clusters); raw pairwise relations are not retained, so cycles and disconnected components are not recoverable. The duplicate-term-across-levels count is the computable integrity check._
