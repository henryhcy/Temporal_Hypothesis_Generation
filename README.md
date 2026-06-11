# Temporal Hypothesis Generation

A benchmark and framework for **temporal hypothesis verification over
clinical narratives**, built on the MedTempo corpus.

Given a natural-language hypothesis about the temporal pattern of vaccine
adverse events, and the relevant report narratives, the framework returns
a verdict (supported / refuted / insufficient) grounded in the temporal
structure of the reports.

## Status

Under active development. Currently in dataset design and template
generation phase.

## Documentation

Project plans, design decisions, and open questions live in `docs/plan/`.
For a project introduction and contribution framing, start with
[`docs/plan/01_overview.md`](docs/plan/01_overview.md).

For a quick orientation:

- **What this project is** — see [`docs/plan/01_overview.md`](docs/plan/01_overview.md)
- **What's been decided** — see [`docs/plan/decisions.md`](docs/plan/decisions.md)
- **What's still open** — see [`docs/plan/open_questions.md`](docs/plan/open_questions.md)

## Repository layout

```
.
├── CLAUDE.md                     Instructions for Claude Code working in this repo
├── README.md                     This file
├── data/
│   └── templates/                Template YAML files (source of truth)
│       ├── pairwise.yaml         precedes + co-occurs (13 groups)
│       ├── sequence.yaml         sequence (8 groups)
│       └── first_last.yaml       first / last (9 groups)
├── docs/
│   ├── plan/                     Project plans, design docs, decisions
│   │   ├── 01_overview.md
│   │   ├── 02_dataset_design.md
│   │   ├── 03_templates.md
│   │   ├── decisions.md
│   │   └── open_questions.md
│   └── reference/                Generated artifacts (e.g., .docx renders)
│       └── Temporal_Hypothesis_Templates.docx
├── scripts/
│   └── render_templates_docx.py  Regenerates the .docx from YAML
├── src/                          Implementation (gold-label generator, framework)
└── tests/                        Test suite
```

## Setup

Requires Python 3.10+. Works on Windows and Linux/macOS.

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip setuptools
pip install -e ".[dev]"
```

**Linux / macOS (bash):**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools
pip install -e ".[dev]"
```

**Build the database** (run once after cloning, and again if source CSVs change):
```bash
python scripts/build_db.py
```

**Regenerate the .docx template reference** (requires `.[render]` extras):
```bash
pip install -e ".[render]"
python scripts/render_templates_docx.py
```

**Run tests:**
```bash
pytest
```

## Working with this repo

If you are using Claude Code on this repo, the conventions and pointers
to plan documents are in `CLAUDE.md`. Claude Code reads it automatically
at the start of each session.

## Citation

To be added on publication.
