# Dataset Statistics

Generated from commit `fd52a3a`.

| | |
|---|--:|
| records (instance x register x format) | 158,624 |
| instances | 19,828 |
| groups | 29 |
| distinct cores | 12,897 |
| distinct facts (split/count key) | 9,890 |
| supported / refuted / insufficient | 7,349 / 7,349 / 5,130 |
| insufficient sub-types | {'not_locatable': 1725, 'sparse': 1583, 'underpowered': 1822} |
| negated instances | 844 |
| mirror pairs (same core, both ways) | 6,931 |
| positional block coverage | 61% |

## Per group

| group | level | mode | inst | sup | ref | insuf | sub-types | negated | reoriented | facts | median n |
|---|---|---|--:|--:|--:|--:|---|--:|--:|--:|--:|
| C-R1 | report | rep_sym_bool | 214 | 107 | 107 | 0 | — | 0 | 0 | 214 | — |
| C-V1 | vaccine | sym_bool_cooccurs | 756 | 252 | 252 | 252 | not_l:84, spars:84, under:84 | 252 | 0 | 504 | 21.0 |
| C-V2 | vaccine | assoc_bool | 1047 | 349 | 349 | 349 | not_l:120, under:229 | 349 | 0 | 698 | 195.0 |
| C-V3 | vaccine | cooc_modal_bool | 522 | 174 | 174 | 174 | not_l:58, spars:58, under:58 | 174 | 0 | 348 | 23.0 |
| F-R1 | report | rep_first_choice | 600 | 300 | 300 | 0 | — | 0 | 300 | 300 | — |
| F-R2 | report | rep_last_choice | 600 | 300 | 300 | 0 | — | 0 | 300 | 300 | — |
| F-R3 | report | rep_first_bool | 600 | 300 | 300 | 0 | — | 0 | 300 | 300 | — |
| F-V1 | vaccine | first_choice | 102 | 34 | 34 | 34 | not_l:12, spars:11, under:11 | 0 | 34 | 68 | 14.0 |
| F-V2 | vaccine | last_choice | 138 | 46 | 46 | 46 | not_l:16, spars:15, under:15 | 0 | 46 | 92 | 14.0 |
| F-V3 | vaccine | first_bool | 102 | 34 | 34 | 34 | not_l:12, spars:11, under:11 | 0 | 34 | 68 | 14.0 |
| H-V1 | vaccine | precedes_bar | 105 | 35 | 35 | 35 | not_l:12, spars:12, under:11 | 0 | 0 | 101 | 16.0 |
| H-V3 | vaccine | cooc_bar | 12 | 4 | 4 | 4 | not_l:2, spars:1, under:1 | 0 | 0 | 12 | 26.5 |
| H-V5 | vaccine | first_bar | 66 | 22 | 22 | 22 | not_l:8, spars:7, under:7 | 0 | 0 | 61 | 13.5 |
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
| T-R1 | report | rep_early_bool | 262 | 131 | 131 | 0 | — | 0 | 0 | 262 | — |
| T-V1 | vaccine | early_bool | 102 | 34 | 34 | 34 | not_l:15, under:19 | 34 | 0 | 68 | 145.0 |
| Y-R1 | report | rep_imm_bool | 362 | 181 | 181 | 0 | — | 0 | 62 | 300 | — |
| Y-V1 | vaccine | imm_bool | 204 | 68 | 68 | 68 | not_l:23, spars:23, under:22 | 0 | 68 | 136 | 17.0 |
| Y-V2 | vaccine | imm_choice | 204 | 68 | 68 | 68 | not_l:23, spars:23, under:22 | 0 | 68 | 136 | 17.0 |
| Y-V3 | vaccine | adj_rate_bool | 105 | 35 | 35 | 35 | not_l:12, spars:12, under:11 | 35 | 0 | 70 | 26.0 |

## Distributions

- **gold_n_all**: {'q25': 16.0, 'q50': 26.0, 'q75': 42.0, 'min': 1, 'max': 465}
- **ci_width**: {'q25': 0.3193, 'q50': 0.4061, 'q75': 0.4874, 'min': 0.0421, 'max': 0.811}
- **abs_effect_size_decisive**: {'q25': 0.5817, 'q50': 0.7617, 'q75': 0.982, 'min': 0.1135, 'max': 2.5903}
- **p_claim_supported**: {'q25': 0.0009, 'q50': 0.0075, 'q75': 0.0235, 'min': 0.0, 'max': 0.05}

## Files

- questions: `pilot_instances_questions.jsonl` (56,748,108 bytes, sha256 `d52b67b0df32d3ba…`)
- answers: `pilot_instances_answers.jsonl` (54,226,017 bytes, sha256 `4f7a6581f76c6d11…`)
