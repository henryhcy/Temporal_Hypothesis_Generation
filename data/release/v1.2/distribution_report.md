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
| C-R1 | 600 | 600 |
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
| T-R1 | 600 | 600 |
| T-V1 | 75 | 75 |
| Y-R1 | 600 | 600 |
| Y-V1 | 223 | 900 |
| Y-V2 | 223 | 900 |
| Y-V3 | 425 | 900 |
| H-V1 | 850 | 1800 |
| H-V3 | 519 | 900 |
| H-V5 | 534 | 5040 |

## A2. Cohort-size (n) distribution per family

- **pairwise**: n=15140  min=10.0 p25=18.0 median=28.0 p75=47.0 max=465.0
  - histogram: {'<= 10': 306, '10-25': 6498, '25-50': 5124, '50-100': 2187, '100-250': 740, '> 250': 285}
- **sequence**: n=470  min=5.0 p25=5.0 median=7.0 p75=9.0 max=28.0
  - histogram: {'<= 10': 390, '10-25': 78, '25-50': 2, '50-100': 0, '100-250': 0, '> 250': 0}
- **first_last**: n=574  min=10.0 p25=11.0 median=14.0 p75=18.0 max=55.0
  - histogram: {'<= 10': 98, '10-25': 427, '25-50': 48, '50-100': 1, '100-250': 0, '> 250': 0}
- **position**: n=75  min=44.0 p25=64.5 median=87.0 p75=167.5 max=424.0
  - histogram: {'<= 10': 0, '10-25': 0, '25-50': 4, '50-100': 41, '100-250': 22, '> 250': 8}
- **proximity**: n=871  min=10.0 p25=12.0 median=16.0 p75=25.0 max=120.0
  - histogram: {'<= 10': 90, '10-25': 574, '25-50': 167, '50-100': 37, '100-250': 3, '> 250': 0}
- **threshold**: n=1903  min=10.0 p25=12.0 median=17.0 p75=26.0 max=213.0
  - histogram: {'<= 10': 189, '10-25': 1214, '25-50': 370, '50-100': 97, '100-250': 33, '> 250': 0}

## A3. Natural verdict distribution (no balancing)

| family | supported | refuted | insufficient |
|---|---:|---:|---:|
| pairwise | 0.3212 | 0.2639 | 0.4148 |
| sequence | 0.1721 | 0.0 | 0.8279 |
| first_last | 0.2372 | 0.0 | 0.7628 |
| position | 0.5215 | 0.4785 | 0.0 |
| proximity | 0.2491 | 0.1918 | 0.5591 |
| threshold | 0.0415 | 0.201 | 0.7575 |

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
| C-R1 | 0.5 | 0.5 | 0.0 |
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
| T-R1 | 0.5 | 0.5 | 0.0 |
| T-V1 | 0.6933 | 0.3067 | 0.0 |
| Y-R1 | 0.5 | 0.5 | 0.0 |
| Y-V1 | 0.1578 | 0.0811 | 0.7611 |
| Y-V2 | 0.1578 | 0.0811 | 0.7611 |
| Y-V3 | 0.2644 | 0.2078 | 0.5278 |
| H-V1 | 0.1128 | 0.3594 | 0.5278 |
| H-V3 | 0.02 | 0.5567 | 0.4233 |
| H-V5 | 0.0198 | 0.081 | 0.8992 |

## A4. Wilson CI-width distribution (single-proportion cores)

- summary: {'count': 18763, 'min': 0.0197, 'p25': 0.2588, 'median': 0.3331, 'p75': 0.4108, 'max': 0.6517}
- histogram: {'<= 0.15': 913, '0.15-0.3': 6623, '0.3-0.45': 8710, '0.45-0.6': 2307, '> 0.6': 210}
- fraction low-confidence (width > 0.30): **0.5984**
- provisional low-confidence cut = CI width > 0.30; A4 calibrates it

## A5. Multi-vaccine overlap and insufficiency

| pair | both clear | one thin | frac insufficient | enough? |
|---|---:|---:|---:|:--:|
| Pfizer+Moderna | 82 | 89 | 0.5205 | yes |
| Pfizer+Janssen | 102 | 108 | 0.5143 | yes |
| Moderna+Janssen | 86 | 67 | 0.4379 | yes |

- Janssen pairs lacking enough computable cores (fallback trigger): none

## A6. Representation diagnostics

- first/last tie-rate summary: {'count': 1108, 'min': 0.0, 'p25': 0.3672, 'median': 0.4615, 'p75': 0.5714, 'max': 0.7347}
- first-level co-occurrence rate (reports whose earliest level has >1 term): **0.6226**
- duplicate-term-across-levels count: 7
- cycle check: N/A; disconnected-component rate: N/A
- _Annotations are stored as leveled orders (a single acyclic chain of co-exist clusters); raw pairwise relations are not retained, so cycles and disconnected components are not recoverable. The duplicate-term-across-levels count is the computable integrity check._
