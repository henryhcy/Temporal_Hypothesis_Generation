# Project Context for Claude Code

## What this project is

A benchmark for LLM hypothesis verification and question answering, built on top of gold-standard temporal annotations of VAERS adverse event reports.

**Key insight**: hypothesis/claim verification and QA are the same task — a claim "Symptom A and B occurred at the same time" is equivalent to "Did Symptom A and B occur at the same time?" with a yes/no answer. The benchmark covers both framings.

## The data

`data/o4mini_annotation_final.csv` — human-annotated VAERS reports. Each row is one adverse event report where symptoms have been grouped by when they occurred after vaccination (temporal grouping). Annotated by two humans + resolved into a `final_result` column. ~3,500 rows (the rest of the large file are raw LLM outputs used during annotation).

Key columns:
- `vaers_id` — report ID
- `symptom_text` — free-text narrative
- `symptom_list` — list of coded symptoms
- `final_result` — gold temporal grouping (JSON list of groups, each group = symptoms that co-occurred)
- `num_groups` — number of distinct temporal stages
- `agreement` — did LLM and humans agree?

## Build plan (phases)

1. **Relational DB**: Parse `final_result` JSON and load into SQLite (or Postgres). Tables needed: `reports`, `symptoms`, `groups`, `group_memberships`. This enables efficient template population without re-parsing CSV.

2. **Templates**: Define hypothesis/question templates with named placeholders, e.g.:
   - Hypothesis: "Following vaccination, {symptom_a} and {symptom_b} occurred at the same time." → label: TRUE if they share a group, FALSE otherwise.
   - Question: "How many distinct symptom onset periods were reported?" → label: `num_groups` value.

3. **Dataset generation**: Query DB to instantiate templates at scale. Gold labels are derived directly from the DB (no extra annotation needed). Target: tens of thousands of instances.

4. **Model evaluation**: Feed instances to LLMs; collect predictions; compute metrics (accuracy, F1, calibration); interpret model reasoning.

## What has been done

- Repo initialized with the gold-standard CSV at `data/o4mini_annotation_final.csv`.
- README written.
- Nothing else yet.

## Notes

- The broader `/home/henryhcy/vaers/temporal/` directory (not in this repo) contains prior experiments: model results for Claude, GPT-4o, LLaMA, MedGemma across many prompting strategies. Useful reference if designing evaluation prompts.
- `medtempo_eval.py` in that directory has existing evaluation utilities worth reusing.
- The user works in Python; prior work used Jupyter notebooks and pandas.
