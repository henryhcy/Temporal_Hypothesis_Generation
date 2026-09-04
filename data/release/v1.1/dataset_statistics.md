# Dataset Statistics

Generated from commit `fbbeb00`.

| | |
|---|--:|
| records (instance x register x format) | 147,936 |
| instances | 18,492 |
| groups | 20 |
| distinct cores | 11,828 |
| distinct facts (split/count key) | 8,964 |
| supported / refuted / insufficient | 6,857 / 6,771 / 4,864 |
| insufficient sub-types | {'not_locatable': 1630, 'sparse': 1505, 'underpowered': 1729} |
| negated instances | 775 |
| mirror pairs (same core, both ways) | 6,664 |
| positional block coverage | 66% |

## Per group

| group | level | mode | inst | sup | ref | insuf | sub-types | negated | reoriented | facts | median n |
|---|---|---|--:|--:|--:|--:|---|--:|--:|--:|--:|
| C-R1 | report | rep_sym_bool | 300 | 193 | 107 | 0 | — | 0 | 0 | 300 | — |
| C-V1 | vaccine | sym_bool_cooccurs | 756 | 252 | 252 | 252 | not_l:84, spars:84, under:84 | 252 | 0 | 504 | 21.0 |
| C-V2 | vaccine | assoc_bool | 1047 | 349 | 349 | 349 | not_l:120, under:229 | 349 | 0 | 698 | 195.0 |
| C-V3 | vaccine | cooc_modal_bool | 522 | 174 | 174 | 174 | not_l:58, spars:58, under:58 | 174 | 0 | 348 | 23.0 |
| F-R1 | report | rep_first_choice | 600 | 300 | 300 | 0 | — | 0 | 300 | 300 | — |
| F-R2 | report | rep_last_choice | 600 | 300 | 300 | 0 | — | 0 | 300 | 300 | — |
| F-R3 | report | rep_first_bool | 600 | 300 | 300 | 0 | — | 0 | 300 | 300 | — |
| F-V1 | vaccine | first_choice | 102 | 34 | 34 | 34 | not_l:12, spars:11, under:11 | 0 | 34 | 68 | 14.0 |
| F-V2 | vaccine | last_choice | 138 | 46 | 46 | 46 | not_l:16, spars:15, under:15 | 0 | 46 | 92 | 14.0 |
| F-V3 | vaccine | first_bool | 102 | 34 | 34 | 34 | not_l:12, spars:11, under:11 | 0 | 34 | 68 | 14.0 |
| P-M2 | multi | multi_dir_precedes | 87 | 29 | 29 | 29 | not_l:10, spars:10, under:9 | 0 | 29 | 58 | 21.5 |
| P-R1 | report | rep_dir_bool | 600 | 300 | 300 | 0 | — | 0 | 300 | 300 | — |
| P-R2 | report | rep_dir_choice | 600 | 300 | 300 | 0 | — | 0 | 300 | 300 | — |
| P-V1 | vaccine | dir_bool | 501 | 167 | 167 | 167 | not_l:56, spars:56, under:55 | 0 | 167 | 334 | 17.0 |
| P-V2 | vaccine | antecedent_bool | 2253 | 751 | 751 | 751 | not_l:251, spars:250, under:250 | 0 | 751 | 1153 | 27.0 |
| P-V3 | vaccine | dir_choice | 501 | 167 | 167 | 167 | not_l:56, spars:56, under:55 | 0 | 167 | 334 | 17.0 |
| P-V4 | vaccine | pairpair_bool | 8571 | 2857 | 2857 | 2857 | not_l:953, spars:952, under:952 | 0 | 2857 | 4163 | 25.0 |
| S-R1 | report | rep_seq_bool | 600 | 300 | 300 | 0 | — | 0 | 300 | 300 | — |
| S-V1 | vaccine | seq_bool | 6 | 2 | 2 | 2 | not_l:1, spars:1 | 0 | 2 | 4 | 5.0 |
| S-V3 | vaccine | modal_choice | 6 | 2 | 2 | 2 | not_l:1, spars:1 | 0 | 2 | 4 | 5.0 |

## Distributions

- **gold_n_all**: {'q25': 16.0, 'q50': 26.0, 'q75': 42.0, 'min': 1, 'max': 465}
- **ci_width**: {'q25': 0.3205, 'q50': 0.4106, 'q75': 0.4899, 'min': 0.0421, 'max': 0.811}
- **abs_effect_size_decisive**: {'q25': 0.5932, 'q50': 0.7746, 'q75': 0.9882, 'min': 0.1135, 'max': 2.5903}
- **p_claim_supported**: {'q25': 0.0008, 'q50': 0.0072, 'q75': 0.0233, 'min': 0.0, 'max': 0.05}

## Files

- questions: `pilot_instances_questions.jsonl` (53,021,719 bytes, sha256 `3545ea9db53bc9a5…`)
- answers: `pilot_instances_answers.jsonl` (51,927,469 bytes, sha256 `613149e14da44acd…`)
