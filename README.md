# Temporal Hypothesis Generation

A benchmark for evaluating LLMs on hypothesis verification and question answering over temporal adverse event data from VAERS (Vaccine Adverse Event Reporting System).

## Project Overview

Hypothesis/claim verification and question answering are fundamentally similar tasks. This project builds a large-scale benchmark dataset by:

1. **Template-based generation** — Define fill-in-the-blank templates for hypotheses (claims) and questions. Each template has placeholders (e.g., symptom names, temporal relationships) that get populated from the source data, producing tens of thousands of instances automatically.

2. **Automatic gold labeling** — Because instances are derived from structured, human-annotated data via templates, gold labels (true/false for claims, yes/no or specific answers for questions) are deterministic and require no additional human annotation.

3. **Model evaluation & interpretation** — Once the benchmark is constructed, run LLM predictions on the hypotheses/questions and analyze model behavior and reasoning.

## Data

### Source: `data/o4mini_annotation_final.csv`

Gold-standard human annotations of VAERS free-text adverse event reports. Each row represents one report with:

| Column | Description |
|---|---|
| `vaers_id` | Unique VAERS report identifier |
| `symptom_text` | Free-text adverse event narrative |
| `symptom_list` | MedDRA-coded symptoms extracted from the text |
| `final_result` | Gold-standard temporal grouping (JSON): symptoms grouped by when they occurred |
| `final_corrected_version` | Corrected grouping if the LLM output needed fixing |
| `num_groups` | Number of distinct temporal stages in the report |
| `agreement` | Whether LLM and human annotators agreed |
| `llm_result_final` | The LLM (o4-mini) output used for annotation |

The core annotation task: symptoms that occurred at the same time after vaccination are placed in the same group. A report with `num_groups=3` means symptoms occurred across three distinct time windows.

## Roadmap

- [ ] **Phase 1 — Database**: Convert `o4mini_annotation_final.csv` into a relational database (SQLite or PostgreSQL) for efficient querying during template population.
- [ ] **Phase 2 — Templates**: Design hypothesis and question templates with named placeholders.
- [ ] **Phase 3 — Dataset generation**: Populate templates from the database; derive gold labels automatically.
- [ ] **Phase 4 — Model evaluation**: Run LLM predictions; implement evaluation metrics and interpretation tools.

## Repository Structure

```
data/
  o4mini_annotation_final.csv   # Gold-standard annotation dataset
```
