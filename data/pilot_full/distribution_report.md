# Pilot Distribution Report (Part A)

## A1. Viable-core counts per group

- Viable target per group: **50**
- Under-target groups (0): none
- Starved groups (0 viable): none

| group | viable | enumerated |
|---|---:|---:|
| P-R1 | 3166 | 3166 |
| P-R2 | 3166 | 3166 |
| P-V1 | 575 | 959 |
| P-V2 | 575 | 959 |
| P-V3 | 575 | 959 |
| P-M1 | 322 | 579 |
| P-M2 | 322 | 579 |
| C-R1 | 3166 | 3166 |
| C-V1 | 959 | 959 |
| C-V2 | 959 | 959 |
| C-V3 | 959 | 959 |
| C-M1 | 579 | 579 |
| C-M2 | 579 | 579 |
| S-R1 | 3166 | 3166 |
| S-V1 | 756 | 756 |
| S-V2 | 756 | 756 |
| S-V3 | 756 | 756 |
| S-V4 | 756 | 756 |
| S-M1 | 387 | 387 |
| S-M2 | 387 | 387 |
| S-M3 | 359 | 387 |
| F-R1 | 3166 | 3166 |
| F-R2 | 3166 | 3166 |
| F-R3 | 3166 | 3166 |
| F-V1 | 756 | 756 |
| F-V2 | 756 | 756 |
| F-V3 | 756 | 756 |
| F-M1 | 387 | 387 |
| F-M2 | 387 | 387 |
| F-M3 | 387 | 387 |

## A2. Cohort-size (n) distribution per family

- **pairwise**: n=6404  min=10.0 p25=12.0 median=16.0 p75=25.0 max=213.0
  - histogram: {'<= 10': 742, '10-25': 4082, '25-50': 1136, '50-100': 326, '100-250': 118, '> 250': 0}
- **sequence**: n=4157  min=10.0 p25=11.0 median=14.0 p75=19.0 max=116.0
  - histogram: {'<= 10': 607, '10-25': 2950, '25-50': 460, '50-100': 136, '100-250': 4, '> 250': 0}
- **first_last**: n=3429  min=10.0 p25=11.0 median=14.0 p75=19.0 max=116.0
  - histogram: {'<= 10': 492, '10-25': 2442, '25-50': 381, '50-100': 111, '100-250': 3, '> 250': 0}

## A3. Natural verdict distribution (no balancing)

| family | supported | refuted | insufficient |
|---|---:|---:|---:|
| pairwise | 0.4426 | 0.3422 | 0.2152 |
| sequence | 0.2639 | 0.6736 | 0.0624 |
| first_last | 0.4347 | 0.0972 | 0.4681 |

Per-group natural verdicts:

| group | supported | refuted | insufficient |
|---|---:|---:|---:|
| P-R1 | 0.3778 | 0.6222 | 0.0 |
| P-R2 | 0.3778 | 0.0 | 0.6222 |
| P-V1 | 0.2711 | 0.2982 | 0.4307 |
| P-V2 | 0.5996 | 0.0 | 0.4004 |
| P-V3 | 0.2711 | 0.2982 | 0.4307 |
| P-M1 | 0.3109 | 0.2453 | 0.4439 |
| P-M2 | 0.2677 | 0.2798 | 0.4525 |
| C-R1 | 0.6222 | 0.3778 | 0.0 |
| C-V1 | 0.2138 | 0.7466 | 0.0396 |
| C-V2 | 1.0 | 0.0 | 0.0 |
| C-V3 | 0.2138 | 0.7466 | 0.0396 |
| C-M1 | 0.4991 | 0.5009 | 0.0 |
| C-M2 | 0.5613 | 0.4283 | 0.0104 |
| S-R1 | 0.1545 | 0.8455 | 0.0 |
| S-V1 | 0.0 | 1.0 | 0.0 |
| S-V2 | 1.0 | 0.0 | 0.0 |
| S-V3 | 0.6058 | 0.0 | 0.3942 |
| S-V4 | 0.0 | 0.9987 | 0.0013 |
| S-M1 | 0.0879 | 0.9121 | 0.0 |
| S-M2 | 0.2558 | 0.4031 | 0.3411 |
| S-M3 | 0.2687 | 0.6589 | 0.0724 |
| F-R1 | 0.3778 | 0.0 | 0.6222 |
| F-R2 | 0.4103 | 0.0 | 0.5897 |
| F-R3 | 0.3778 | 0.0 | 0.6222 |
| F-V1 | 0.836 | 0.0 | 0.164 |
| F-V2 | 0.8585 | 0.0 | 0.1415 |
| F-V3 | 0.0529 | 0.9471 | 0.0 |
| F-M1 | 0.5969 | 0.4031 | 0.0 |
| F-M2 | 0.4031 | 0.5969 | 0.0 |
| F-M3 | 0.5685 | 0.3979 | 0.0336 |

## A4. Wilson CI-width distribution (single-proportion cores)

- summary: {'count': 9894, 'min': 0.0542, 'p25': 0.2775, 'median': 0.3699, 'p75': 0.4434, 'max': 0.5268}
- histogram: {'<= 0.15': 264, '0.15-0.3': 2693, '0.3-0.45': 4863, '0.45-0.6': 2074, '> 0.6': 0}
- fraction low-confidence (width > 0.30): **0.7011**
- provisional low-confidence cut = CI width > 0.30; A4 calibrates it

## A5. Multi-vaccine overlap and insufficiency

| pair | both clear | one thin | frac insufficient | enough? |
|---|---:|---:|---:|:--:|
| Pfizer+Moderna | 1160 | 160 | 0.1212 | yes |
| Pfizer+Janssen | 1452 | 188 | 0.1146 | yes |
| Moderna+Janssen | 1484 | 194 | 0.1156 | yes |

- Janssen pairs lacking enough computable cores (fallback trigger): none

## A6. Representation diagnostics

- first/last tie-rate summary: {'count': 2268, 'min': 0.0, 'p25': 0.3846, 'median': 0.5, 'p75': 0.6283, 'max': 1.0}
- first-level co-occurrence rate (reports whose earliest level has >1 term): **0.6226**
- duplicate-term-across-levels count: 7
- cycle check: N/A; disconnected-component rate: N/A
- _Annotations are stored as leveled orders (a single acyclic chain of co-exist clusters); raw pairwise relations are not retained, so cycles and disconnected components are not recoverable. The duplicate-term-across-levels count is the computable integrity check._
