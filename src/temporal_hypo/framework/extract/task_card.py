"""The dataset card shown to the toolbox S1 frame -- computed from the eval DB, never typed.

What a statistician is told about a dataset before formulating anything (11 §13.5):
the representation, the cohorts and their sizes, the stage-population geometry
(without it a model cannot know the 0.5 symmetry fails for single-event position
claims), the vocabulary size. Nothing here names a template group or a mode.
"""

from __future__ import annotations

import sqlite3


def stage_population(conn: sqlite3.Connection, max_level: int = 5) -> list[tuple[int, float, int]]:
    """(level_index, mean terms at that level over reports that have it, n reports)."""
    rows = conn.execute(
        "SELECT level_index, AVG(c), COUNT(*) FROM ("
        "  SELECT vaers_id, level_index, COUNT(*) AS c FROM level_terms "
        "  GROUP BY vaers_id, level_index) "
        "WHERE level_index <= ? GROUP BY level_index ORDER BY level_index", (max_level,)
    ).fetchall()
    return [(int(l), float(m), int(n)) for l, m, n in rows]


def dataset_card(conn: sqlite3.Connection) -> str:
    cohorts = conn.execute(
        "SELECT vaccine, COUNT(*) FROM reports GROUP BY vaccine ORDER BY vaccine").fetchall()
    n_reports = sum(c for _, c in cohorts)
    n_terms = conn.execute("SELECT COUNT(DISTINCT term) FROM level_terms").fetchone()[0]
    levels = conn.execute("SELECT AVG(num_stages) FROM reports").fetchone()[0]
    stages = stage_population(conn)
    stage_txt = "; ".join(f"stage {l}: {m:.2f} events (n={n})" for l, m, n in stages)
    cohort_txt = ", ".join(f"{v}: {c}" for v, c in cohorts)
    return "\n".join([
        f"DATASET: {n_reports} VAERS adverse-event reports, each annotated as a LEVELED ORDER -- "
        f"an ordered sequence of stages (mean {levels:.1f} per report); every stage holds one "
        f"or more MedDRA event terms that occurred together; a term's position is its FIRST "
        f"mention. Terms at the same stage CO-EXIST (no order between them).",
        f"COHORTS (one vaccine per report): {cohort_txt}. A report is identified by its VAERS id.",
        f"VOCABULARY: {n_terms} distinct event terms; claims name terms verbatim.",
        f"STAGE POPULATION (mean events per stage): {stage_txt}. Earlier stages hold more "
        f"events, so a randomly chosen event is more likely to be early than late -- the "
        f"chance rate for 'is X early?' is NOT 0.5 and must be computed from the data; "
        f"pair-order claims are unaffected (swapping the pair is a symmetry).",
    ])
