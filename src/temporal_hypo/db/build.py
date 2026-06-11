"""Build the MedTempo SQLite database from the two source CSVs."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pandas as pd

VAX_MAP: dict[str, str] = {
    "PFIZER\\BIONTECH": "Pfizer",
    "MODERNA": "Moderna",
    "JANSSEN": "Janssen",
}

_SCHEMA = Path(__file__).with_name("schema.sql")


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
    conn.commit()


def _parse_levels(gold_json: str) -> list[list[str]] | None:
    """Parse a leveled-order JSON string into list[list[str]].

    Returns None if the string is not a JSON array or cannot be parsed.
    Trailing commas (a common human-editing artefact) are stripped before parsing.
    """
    text = gold_json.strip() if isinstance(gold_json, str) else ""
    if not text.startswith("["):
        return None
    # Remove trailing commas before } or ] — handles manual annotation errors
    text = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, list):
        return None
    levels = []
    for group in raw:
        if isinstance(group, dict):
            terms = [k for k in group if isinstance(k, str) and k]
            if terms:
                levels.append(terms)
    return levels if levels else None


def build(
    annot_csv: Path,
    vaers_csv: Path,
    db_path: Path,
) -> dict[str, int]:
    """Build medtempo.db from the two source CSVs.

    Returns a dict with counts: inserted, skipped_no_match, skipped_filter,
    skipped_no_json, and per-vaccine inserted counts.
    """
    annot = pd.read_csv(annot_csv)
    vaers = pd.read_csv(vaers_csv)

    # Normalise vaers_id to int in both frames
    annot["vaers_id"] = annot["vaers_id"].astype(int)
    vaers["vaers_id"] = vaers["vaers_id"].astype(float).astype(int)

    merged = annot.merge(vaers[["vaers_id", "vax_manu"]], on="vaers_id", how="inner")

    counts: dict[str, int] = {
        "total_joined": len(merged),
        "skipped_filter": 0,
        "skipped_no_json": 0,
        "inserted": 0,
        "skipped_no_match": len(annot) - len(merged),
    }
    vaccine_counts: dict[str, int] = {v: 0 for v in VAX_MAP.values()}

    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    _create_tables(conn)

    rows_reports: list[tuple] = []
    rows_level_terms: list[tuple] = []

    for _, row in merged.iterrows():
        final_result = int(row["final_result"])
        if final_result not in (0, 1):
            counts["skipped_filter"] += 1
            continue

        gold_json = row["llm_result_final"] if final_result == 1 else row["final_corrected_version"]
        levels = _parse_levels(str(gold_json) if pd.notna(gold_json) else "")
        if levels is None:
            counts["skipped_no_json"] += 1
            continue

        vax_raw = str(row["vax_manu"]).strip()
        vaccine = VAX_MAP.get(vax_raw)
        if vaccine is None:
            counts["skipped_filter"] += 1
            continue

        vaers_id = int(row["vaers_id"])
        narrative = str(row["symptom_text"]) if pd.notna(row["symptom_text"]) else ""
        num_groups = len(levels)

        rows_reports.append((vaers_id, vaccine, narrative, num_groups))
        for level_index, terms in enumerate(levels):
            for term in terms:
                rows_level_terms.append((vaers_id, level_index, term))

        counts["inserted"] += 1
        vaccine_counts[vaccine] += 1

    conn.executemany(
        "INSERT INTO reports (vaers_id, vaccine, narrative, num_groups) VALUES (?,?,?,?)",
        rows_reports,
    )
    conn.commit()

    conn.executemany(
        """INSERT INTO level_terms (report_id, level_index, term)
           VALUES ((SELECT report_id FROM reports WHERE vaers_id=?), ?, ?)""",
        rows_level_terms,
    )
    conn.commit()
    conn.close()

    counts.update({f"vaccine_{k}": v for k, v in vaccine_counts.items()})
    return counts
