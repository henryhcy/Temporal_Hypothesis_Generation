# Three Sample Instances (fully annotated)

One-off snapshot of the finished generator; regenerate with
`python scripts/make_sample_instances.py`. Chosen to span every mechanism in
the benchmark: a BOOL single-cohort claim, an argmax CHOICE claim, and the only
surviving two-cohort group.

Two things here are NOT in the released record, shown only for comparison: the
**positional/rank statistics** (retired as verdict drivers on 2026-08-11 --
descriptive only), and the **mirror partner**, so the supported/refuted pairing
is visible.

Report ids are gold-side: they are the answer to the localization step, so they
live in `*_answers.jsonl` and never in `*_questions.jsonl`.

## 1. P-V1 — dir_bool (BOOL, vaccine)

*Why this example: widest evidence spread: has co-exist reports EXCLUDED from n*

### The hypothesis, all four registers

- **question** (original): Does Headache typically occur before Vomiting after Pfizer?
- **original**: After Pfizer, Headache typically occurs before Vomiting.
- **research**: Among Pfizer reports, Headache precedes Vomiting in the majority of cases.
- **media**: After Pfizer, most people get Headache before Vomiting.
- **clinical**: In Pfizer recipients, Headache usually comes before Vomiting.

### Gold label

| field | value |
|---|---|
| `gold_verdict` | supported |
| `test_verdict` | supported |
| `negated` | False |
| `gold_proportion` | 0.76 |
| `gold_n` | 25 |
| `gold_k` | 19 |
| `ci` | [0.5657, 0.885] |
| `ci_width` | 0.3193 |
| `confidence_tag` | low |
| `effect_size` | 0.5469 |

### Test

| field | value |
|---|---|
| `sig_test` | binom_exact |
| `p_value` | 0.007317 |
| `p_claim` | 0.007317 |
| `p_opposite` | 0.997961 |
| `significant` | True |
| `alpha` | 0.05 |
| `min_n_floor` | 10 |
| `family` | pairwise |

### Covered case ids (the evidence)

- **denominator** — 25 reports: 1002916, 1005548, 1080700, 1098926, 1118672, 1118837, 1137403, 1153432, 1171386, 1280111 … (+15 more)
- **numerator** — 19 reports: 1098926, 1118672, 1118837, 1137403, 1171386, 1280111, 1320879, 1373556, 1385457, 1420761 … (+9 more)
- **excluded** — 9 reports: 1137469, 1141282, 1149335, 1225836, 1340375, 1812643, 2201122, 2566456, 2689093

### Positional / rank statistics — DESCRIPTIVE ONLY, not the label

```json
{
  "wilcoxon_signed_rank": {
    "what": "level(Headache) - level(Vomiting) per report, symmetric about 0?",
    "n_present_reports": 34,
    "n_nonzero_pairs": 25,
    "statistic_W_plus": 67.0,
    "p": 0.008409461015849934,
    "method": "normal",
    "note": "keeps ALL both-present reports, including co-exist (d=0), unlike the precedes denominator which drops them"
  }
}
```

### Mirror pair

- shared `derived_from_core_id`: `P-V1|Pfizer|Headache+Vomiting`
- **supported**: After Pfizer, Headache typically occurs before Vomiting.
- **refuted**: After Pfizer, Vomiting typically occurs before Headache.
- refuted tails: p_claim = 0.997961, p_opposite = 0.007317
- same core, opposite orientation; both share derived_from_core_id and MUST stay on the same side of any train/test split

## 2. F-V2 — last_choice (CHOICE, vaccine)

*Why this example: argmax CHOICE: per-candidate counts, ties excluded, answer key*

### The hypothesis, all four registers

- **question** (original): After Janssen, which of Dizziness, Chills, Headache is most commonly the last event?
- **original**: After Janssen, Dizziness is most commonly the last event among Dizziness, Chills, Headache.
- **research**: In Janssen reports with all three, Dizziness is most frequently the latest.
- **media**: After Janssen, Dizziness comes last most often.
- **clinical**: In Janssen patients, Dizziness is most frequently the latest.

### Gold label

| field | value |
|---|---|
| `gold_verdict` | supported |
| `test_verdict` | supported |
| `negated` | False |
| `gold_proportion` | 0.68 |
| `gold_n` | 25 |
| `gold_k` | 17 |
| `ci` | [0.4841, 0.8279] |
| `ci_width` | 0.3438 |
| `confidence_tag` | low |
| `effect_size` | 0.7081 |
| `options` | ['Chills', 'Dizziness', 'Headache'] |
| `gold_answer` | Dizziness |

### Test

| field | value |
|---|---|
| `sig_test` | modal_runner |
| `p_value` | 0.00845 |
| `p_claim` | 0.00845 |
| `p_opposite` | 0.997828 |
| `significant` | True |
| `alpha` | 0.05 |
| `min_n_floor` | 10 |
| `family` | first_last |

### Covered case ids (the evidence)

- **denominator** — 25 reports: 1074476, 1082139, 1089648, 1093041, 1094194, 1103729, 1156013, 1158036, 1195134, 1196015 … (+15 more)
- **numerator** — 17 reports: 1074476, 1082139, 1089648, 1093041, 1094194, 1156013, 1196452, 1201116, 1203097, 1204897 … (+7 more)
- **excluded** — 18 reports: 1080401, 1102224, 1117861, 1165945, 1190551, 1197193, 1208584, 1208986, 1214024, 1214392 … (+8 more)
- **ties** — 18 reports: 1080401, 1102224, 1117861, 1165945, 1190551, 1197193, 1208584, 1208986, 1214024, 1214392 … (+8 more)

### Per-cell counts behind the test

```json
{
  "fracs": {
    "Chills": 0.2,
    "Dizziness": 0.68,
    "Headache": 0.12
  },
  "winner": "Dizziness",
  "unique": true,
  "tie_rate": 0.4186046511627907,
  "counts": {
    "Chills": 5,
    "Dizziness": 17,
    "Headache": 3
  }
}
```

### Positional / rank statistics — DESCRIPTIVE ONLY, not the label

```json
{
  "wilcoxon_signed_rank": {
    "what": "level(Dizziness) - level(Chills) per report, symmetric about 0?",
    "n_present_reports": 71,
    "n_nonzero_pairs": 48,
    "statistic_W_plus": 703.5,
    "p": 0.22380194666728878,
    "method": "normal",
    "note": "keeps ALL both-present reports, including co-exist (d=0), unlike the precedes denominator which drops them"
  },
  "friedman": {
    "what": "do the three events differ in position?",
    "n_reports": 43,
    "Q": 6.275862068965439,
    "df": 2,
    "p": 0.04337244122080687
  },
  "kendalls_w": {
    "what": "how consistent is the ordering across reports?",
    "W": 0.07297514033680834,
    "p": 0.043372441220805184
  }
}
```

### Mirror pair

- shared `derived_from_core_id`: `F-V2|Janssen|Chills+Dizziness+Headache`
- **supported**: After Janssen, Dizziness is most commonly the last event among Dizziness, Chills, Headache.
- **refuted**: After Janssen, Headache is most commonly the last event among Headache, Chills, Dizziness.
- refuted tails: p_claim = 0.999799, p_opposite = 0.001288
- same core, opposite orientation; both share derived_from_core_id and MUST stay on the same side of any train/test split

## 3. P-M2 — multi_dir_precedes (CHOICE, multi)

*Why this example: two-cohort: per-cohort denominators, the only surviving multi group*

### The hypothesis, all four registers

- **question** (original): After which vaccine, Janssen or Pfizer, does Chills more often precede Pain in extremity?
- **original**: Chills precedes Pain in extremity more often after Janssen than after Pfizer.
- **research**: Janssen shows a higher Chills-precedes-Pain in extremity proportion than Pfizer.
- **media**: Chills-before-Pain in extremity is more common after Janssen than Pfizer.
- **clinical**: Janssen recipients more often have Chills as a precursor to Pain in extremity.

### Gold label

| field | value |
|---|---|
| `gold_verdict` | supported |
| `test_verdict` | supported |
| `negated` | False |
| `gold_proportion` | 0.6304 |
| `gold_n` | 46 |
| `gold_k` | 29 |
| `gold_n2` | 24 |
| `gold_k2` | 8 |
| `ci` | [0.0507, 0.4947] |
| `ci_width` | 0.444 |
| `confidence_tag` | low |
| `effect_size` | 0.6038 |
| `options` | ['Pfizer', 'Janssen'] |
| `gold_answer` | Janssen |

### Test

| field | value |
|---|---|
| `sig_test` | fisher_exact |
| `p_value` | 0.017064 |
| `p_claim` | 0.017064 |
| `p_opposite` | 0.995776 |
| `significant` | True |
| `alpha` | 0.05 |
| `min_n_floor` | 10 |
| `family` | pairwise |

### Covered case ids (the evidence)

- **cohort_1**
    - **denominator** — 46 reports: 1081109, 1081513, 1082139, 1086098, 1092914, 1094194, 1096690, 1110379, 1114774, 1149344 … (+36 more)
    - **numerator** — 29 reports: 1081109, 1092914, 1096690, 1110379, 1149344, 1158036, 1163644, 1167388, 1184010, 1195134 … (+19 more)
    - **excluded** — 14 reports: 1081210, 1145410, 1190629, 1203097, 1214392, 1215391, 1236375, 1238873, 1241093, 1288007 … (+4 more)
- **cohort_2**
    - **denominator** — 24 reports: 927944, 951488, 951763, 1004313, 1077427, 1090979, 1118672, 1137786, 1156244, 1156567 … (+14 more)
    - **numerator** — 8 reports: 951763, 1077427, 1156244, 1257243, 1403315, 1478861, 1483481, 1775004
    - **excluded** — 10 reports: 935855, 961289, 1201142, 1320879, 1348027, 1360448, 1793346, 1873699, 2693165, 2808653

### Positional / rank statistics — DESCRIPTIVE ONLY, not the label

```json
{
  "mann_whitney_u": {
    "what": "is the Chills-Pain in extremity rank distance shifted between cohorts?",
    "n1": 60,
    "n2": 34,
    "U": 770.5,
    "p": 0.04512388474971869,
    "method": "normal",
    "caveat": "anti-conservative on tie-heavy ordinal data; NOT a label"
  }
}
```

### Mirror pair

- shared `derived_from_core_id`: `P-M2|Pfizer+Janssen|Chills+Pain in extremity`
- **supported**: Chills precedes Pain in extremity more often after Janssen than after Pfizer.
- **refuted**: Chills precedes Pain in extremity more often after Pfizer than after Janssen.
- refuted tails: p_claim = 0.995776, p_opposite = 0.017064
- same core, opposite orientation; both share derived_from_core_id and MUST stay on the same side of any train/test split
