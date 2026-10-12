# eval_core v1.2 under the final prompt configuration (2026-10-10/11)

| row (32B; eval_core: 2,350 instances, 4,700 records) | all | cohort tiers | report tier | den-F1 | co-exist leak | faithfulness | false-decisive | over-abstain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 our planner 32B + 1 round (gold S2/S3) | 0.954 | 0.931 | 0.999 | 0.944 | 0.00 | -- | 0.02 | 0.04 |
| C  S2 coder-32B + 2 rounds (gold plan) | 0.880 | 0.816 | 1.000 | 0.797 | 0.18 | 0.81 | 0.02 | 0.26 |
| A  e2e sentence->SQL, schema only | 0.466 | 0.494 | 0.412 | 0.455 | 0.64 | 0.21 | 0.22 | 0.49 |
| B  e2e + conventions | 0.590 | 0.525 | 0.713 | 0.570 | 0.40 | 0.32 | 0.24 | 0.42 |
| D  our pipeline, no verifier | 0.555 | 0.476 | 0.704 | 0.542 | 0.16 | 0.29 | 0.14 | 0.57 |
| D+2 our pipeline + 2 verify rounds | 0.646 | 0.615 | 0.704 | 0.663 | 0.08 | 0.74 | 0.13 | 0.36 |
| E  our pipeline + consistency re-ask | 0.642 | 0.609 | 0.704 | 0.656 | 0.13 | 0.71 | 0.12 | 0.36 |
| counts-given judgment (gold counts) | 0.739 | 0.602 | 1.000 | 1.000 | 0.00 | 1.00 | 0.18 | 0.48 |


**Addendum 2026-10-12 (core set, `core_v12_*`): the verified e2e control and D'.**

| row (32B; 4,700 records; 3,080 cohort) | all | cohort | report | den-F1 | leak | faithfulness | false-decisive | over-abstain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B+2  e2e + conventions + 2 plan-free repair rounds | 0.669 | 0.645 | 0.713 | 0.699 | 0.50 | 0.64 | 0.22 | 0.26 |
| D'   our plan, named primitive resolved for S2 | 0.831 | 0.743 | 0.999 | 0.705 | 0.18 | 0.75 | 0.04 | 0.31 |
| **D'+2** | **0.856** | **0.781** | 0.999 | 0.752 | 0.17 | **0.78** | 0.03 | 0.26 |
| (D+2, prose plan, for reference) | 0.646 | 0.615 | 0.704 | 0.663 | 0.08 | 0.74 | 0.13 | 0.36 |
| (C+2, gold plan) | 0.880 | 0.816 | 1.000 | 0.797 | 0.18 | 0.81 | 0.02 | 0.26 |

The slice ordering holds at scale: verified e2e 0.669 vs the prose pipeline
0.646 (level on the verdict; evidence 0.64 vs 0.74, leak 0.50 vs 0.08,
false-decisiveness 0.22 vs 0.13); the plan-as-contract pipeline 0.856 (cohort
0.781) is +0.19 over the verified e2e and 0.024 below the gold-plan row, with
the report tier solved (0.999) because the resolved `single_report` primitive
is the compiler's whole-report query. Headline rows for the paper: D'+2 vs
B+2 vs EHRAgent-A, with C+2 and the planner as the stage ceilings.
