# Dataset Statistics

Generated from commit `e7f572c`.

| | |
|---|--:|
| records (instance x register x format) | 70,104 |
| instances | 8,763 |
| groups | 29 |
| distinct cores | 5,703 |
| distinct facts (split/count key) | 4,761 |
| supported / refuted / insufficient | 3,476 / 3,468 / 1,819 |
| insufficient sub-types | {'not_locatable': 618, 'sparse': 498, 'underpowered': 703} |
| negated instances | 643 |
| mirror pairs (same core, both ways) | 3,007 |
| positional block coverage | 39% |

## Per group

| group | level | mode | inst | sup | ref | insuf | sub-types | negated | reoriented | facts | median n |
|---|---|---|--:|--:|--:|--:|---|--:|--:|--:|--:|
| C-R1 | report | rep_sym_bool | 400 | 200 | 200 | 0 | — | 0 | 0 | 400 | — |
| C-V1 | vaccine | sym_bool_cooccurs | 600 | 200 | 200 | 200 | not_l:67, spars:67, under:66 | 200 | 0 | 400 | 19.0 |
| C-V2 | vaccine | assoc_bool | 600 | 200 | 200 | 200 | not_l:100, under:100 | 200 | 0 | 400 | 229.0 |
| C-V3 | vaccine | cooc_modal_bool | 522 | 139 | 139 | 244 | not_l:58, spars:58, under:128 | 174 | 0 | 348 | 23.0 |
| F-R1 | report | rep_first_choice | 400 | 200 | 200 | 0 | — | 0 | 200 | 200 | — |
| F-R2 | report | rep_last_choice | 400 | 200 | 200 | 0 | — | 0 | 200 | 200 | — |
| F-R3 | report | rep_first_bool | 400 | 200 | 200 | 0 | — | 0 | 200 | 200 | — |
| F-V1 | vaccine | first_choice | 102 | 34 | 33 | 35 | not_l:12, spars:11, under:12 | 0 | 34 | 68 | 14.0 |
| F-V2 | vaccine | last_choice | 138 | 46 | 44 | 48 | not_l:16, spars:15, under:17 | 0 | 46 | 92 | 14.0 |
| F-V3 | vaccine | first_bool | 102 | 34 | 33 | 35 | not_l:12, spars:11, under:12 | 0 | 34 | 68 | 14.0 |
| H-V1 | vaccine | precedes_bar | 105 | 35 | 35 | 35 | not_l:12, spars:12, under:11 | 0 | 0 | 101 | 16.0 |
| H-V3 | vaccine | cooc_bar | 12 | 4 | 4 | 4 | not_l:2, spars:1, under:1 | 0 | 0 | 12 | 26.5 |
| H-V5 | vaccine | first_bar | 66 | 22 | 22 | 22 | not_l:8, spars:7, under:7 | 0 | 0 | 61 | 13.5 |
| P-M2 | multi | multi_dir_precedes | 87 | 29 | 29 | 29 | not_l:10, spars:10, under:9 | 0 | 29 | 58 | 21.5 |
| P-R1 | report | rep_dir_bool | 400 | 200 | 200 | 0 | — | 0 | 200 | 200 | — |
| P-R2 | report | rep_dir_choice | 400 | 200 | 200 | 0 | — | 0 | 200 | 200 | — |
| P-V1 | vaccine | dir_bool | 501 | 167 | 167 | 167 | not_l:56, spars:56, under:55 | 0 | 167 | 334 | 17.0 |
| P-V2 | vaccine | antecedent_bool | 600 | 200 | 200 | 200 | not_l:67, spars:67, under:66 | 0 | 200 | 375 | 22.0 |
| P-V3 | vaccine | dir_choice | 501 | 167 | 167 | 167 | not_l:56, spars:56, under:55 | 0 | 167 | 334 | 17.0 |
| P-V4 | vaccine | pairpair_bool | 600 | 200 | 200 | 200 | not_l:67, spars:67, under:66 | 0 | 200 | 393 | 24.0 |
| S-R1 | report | rep_seq_bool | 400 | 200 | 200 | 0 | — | 0 | 200 | 200 | — |
| S-V1 | vaccine | seq_bool | 6 | 2 | 0 | 4 | not_l:1, spars:1, under:2 | 0 | 2 | 4 | 5.0 |
| S-V3 | vaccine | modal_choice | 6 | 2 | 0 | 4 | not_l:1, spars:1, under:2 | 0 | 2 | 4 | 5.0 |
| T-R1 | report | rep_early_bool | 400 | 200 | 200 | 0 | — | 0 | 0 | 400 | — |
| T-V1 | vaccine | early_bool | 102 | 34 | 34 | 34 | not_l:15, under:19 | 34 | 0 | 68 | 145.0 |
| Y-R1 | report | rep_imm_bool | 400 | 200 | 200 | 0 | — | 0 | 200 | 200 | — |
| Y-V1 | vaccine | imm_bool | 204 | 68 | 68 | 68 | not_l:23, spars:23, under:22 | 0 | 68 | 136 | 17.0 |
| Y-V2 | vaccine | imm_choice | 204 | 68 | 68 | 68 | not_l:23, spars:23, under:22 | 0 | 68 | 136 | 17.0 |
| Y-V3 | vaccine | adj_rate_bool | 105 | 25 | 25 | 55 | not_l:12, spars:12, under:31 | 35 | 0 | 70 | 26.0 |

## Distributions

- **gold_n_all**: {'q25': 14.0, 'q50': 21.0, 'q75': 41.0, 'min': 1, 'max': 465}
- **ci_width**: {'q25': 0.2581, 'q50': 0.3446, 'q75': 0.4401, 'min': 0.047, 'max': 0.811}
- **abs_effect_size_decisive**: {'q25': 0.4606, 'q50': 0.6629, 'q75': 0.8672, 'min': 0.1161, 'max': 2.4981}
- **p_claim_supported**: {'q25': 0.0011, 'q50': 0.0082, 'q75': 0.0249, 'min': 0.0, 'max': 0.0499}

## Files

- questions: `pilot_instances_questions.jsonl` (24,566,808 bytes, sha256 `3c99ef4cdb0e7452…`)
- answers: `pilot_instances_answers.jsonl` (21,546,861 bytes, sha256 `419cdf57ed53fc51…`)
