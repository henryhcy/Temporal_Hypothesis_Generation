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
