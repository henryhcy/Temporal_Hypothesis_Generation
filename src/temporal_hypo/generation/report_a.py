"""Part A distribution report: corpus diagnostics A1-A6.

Computed over the full pre-balancing viable-core population so the numbers
reflect the corpus, not the sampled pilot dataset. See 04_corpus_survey.md.
"""

from __future__ import annotations

import sqlite3

from temporal_hypo.generation.confidence import ci_width, percentile, wilson_ci
from temporal_hypo.generation.cores import ViableCore
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.templates import Group

VIABLE_TARGET = 50  # binding requirement for T=100 (decisions.md)


def _summary(values: list[float]) -> dict:
    if not values:
        return {"count": 0}
    s = sorted(values)
    return {
        "count": len(s),
        "min": round(s[0], 4),
        "p25": round(percentile(s, 0.25), 4),
        "median": round(percentile(s, 0.50), 4),
        "p75": round(percentile(s, 0.75), 4),
        "max": round(s[-1], 4),
    }


def _histogram(values: list[float], edges: list[float]) -> dict:
    bins = {f"<= {edges[0]}": 0}
    for i in range(1, len(edges)):
        bins[f"{edges[i-1]}-{edges[i]}"] = 0
    bins[f"> {edges[-1]}"] = 0
    keys = list(bins)
    for v in values:
        placed = False
        if v <= edges[0]:
            bins[keys[0]] += 1
            placed = True
        else:
            for i in range(1, len(edges)):
                if v <= edges[i]:
                    bins[keys[i]] += 1
                    placed = True
                    break
        if not placed:
            bins[keys[-1]] += 1
    return bins


def build_report(
    index: CorpusIndex,
    conn: sqlite3.Connection,
    groups: dict[str, Group],
    cores_by_group: dict[str, list[ViableCore]],
) -> dict:
    report: dict = {}

    # --- A1: viable-core counts per group --------------------------------
    a1 = {}
    under = []
    starved = []
    for gid, cores in cores_by_group.items():
        viable = sum(1 for c in cores if c.computable)
        a1[gid] = {"viable_cores": viable, "total_enumerated": len(cores)}
        if viable < VIABLE_TARGET:
            under.append(gid)
        if viable == 0:
            starved.append(gid)
    report["A1_viable_core_counts"] = {
        "per_group": a1,
        "viable_target": VIABLE_TARGET,
        "under_target_groups": under,
        "starved_groups": starved,
    }

    # --- A2: cohort-size (n) distribution per family ---------------------
    by_family_n: dict[str, list[float]] = {}
    for gid, cores in cores_by_group.items():
        fam = groups[gid].family
        for c in cores:
            if c.computable and c.n is not None:
                by_family_n.setdefault(fam, []).append(float(c.n))
    report["A2_cohort_size_distribution"] = {
        fam: {
            "summary": _summary(ns),
            "histogram": _histogram(ns, [10, 25, 50, 100, 250]),
        }
        for fam, ns in by_family_n.items()
    }

    # --- A3: natural verdict distribution --------------------------------
    def _verdict_split(cores: list[ViableCore]) -> dict:
        tally = {"supported": 0, "refuted": 0, "insufficient": 0}
        for c in cores:
            tally[c.natural_verdict] = tally.get(c.natural_verdict, 0) + 1
        total = sum(tally.values()) or 1
        return {**tally, "fractions": {k: round(v / total, 4) for k, v in tally.items()}}

    a3_group = {gid: _verdict_split(cores) for gid, cores in cores_by_group.items()}
    a3_family: dict[str, list[ViableCore]] = {}
    for gid, cores in cores_by_group.items():
        a3_family.setdefault(groups[gid].family, []).extend(cores)
    report["A3_natural_verdict_distribution"] = {
        "per_group": a3_group,
        "per_family": {fam: _verdict_split(cs) for fam, cs in a3_family.items()},
    }

    # --- A4: Wilson CI-width distribution (single-proportion cores) ------
    widths = []
    for gid, cores in cores_by_group.items():
        if groups[gid].level != "vaccine":
            continue
        for c in cores:
            if c.computable and c.k is not None and c.n:
                widths.append(ci_width(wilson_ci(c.k, c.n)))
    low_conf = sum(1 for w in widths if w > 0.30)
    report["A4_ci_width_distribution"] = {
        "summary": _summary(widths),
        "histogram": _histogram(widths, [0.15, 0.30, 0.45, 0.60]),
        "fraction_low_confidence_gt_0.30": round(low_conf / len(widths), 4)
        if widths else None,
        "note": "provisional low-confidence cut = CI width > 0.30; A4 calibrates it",
    }

    # --- A5: multi-vaccine overlap and insufficiency ---------------------
    pair_stats: dict[str, dict] = {}
    for gid, cores in cores_by_group.items():
        if groups[gid].level != "multi":
            continue
        for c in cores:
            pair = "+".join(c.vaccines)
            d = pair_stats.setdefault(pair, {"both_clear": 0, "one_thin": 0})
            if c.computable:
                d["both_clear"] += 1
            else:
                d["one_thin"] += 1
    for pair, d in pair_stats.items():
        total = d["both_clear"] + d["one_thin"]
        d["total"] = total
        d["fraction_insufficient"] = round(d["one_thin"] / total, 4) if total else None
        d["enough_for_reduced_budget"] = d["both_clear"] >= VIABLE_TARGET
    report["A5_multi_vaccine_overlap"] = {
        "per_pair": pair_stats,
        "janssen_pairs_flagged": [
            p for p in pair_stats if "Janssen" in p
            and not pair_stats[p]["enough_for_reduced_budget"]
        ],
    }

    # --- A6: representation diagnostics ----------------------------------
    tie_rates = []
    for gid, cores in cores_by_group.items():
        if groups[gid].primitive != "first_last" or groups[gid].level != "vaccine":
            continue
        for c in cores:
            if c.computable and "tie_rate" in c.extra:
                tie_rates.append(c.extra["tie_rate"])

    # structural: fraction of multi-event reports whose earliest level has >1 term
    first_level_tie = conn.execute(
        """
        WITH firsts AS (
            SELECT report_id, MIN(level_index) AS lvl
            FROM level_terms GROUP BY report_id
        )
        SELECT
          SUM(CASE WHEN cnt > 1 THEN 1 ELSE 0 END) AS tied,
          COUNT(*) AS total
        FROM (
            SELECT lt.report_id, COUNT(*) AS cnt
            FROM level_terms lt
            JOIN firsts f ON f.report_id = lt.report_id AND lt.level_index = f.lvl
            GROUP BY lt.report_id
        )
        """
    ).fetchone()
    tied, total_reports = (first_level_tie[0] or 0), (first_level_tie[1] or 0)

    # duplicate-term-across-levels integrity (a term at >1 distinct level in a report)
    dup = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT report_id, term
            FROM level_terms
            GROUP BY report_id, term
            HAVING COUNT(DISTINCT level_index) > 1
        )
        """
    ).fetchone()[0]

    report["A6_representation_diagnostics"] = {
        "first_last_tie_rate": {
            "summary": _summary(tie_rates),
            "note": "per-core fraction of reports with >=2 candidates tied at the "
                    "earliest/latest level (first/last vaccine groups)",
        },
        "first_level_co_occurrence_rate": round(tied / total_reports, 4)
        if total_reports else None,
        "duplicate_term_across_levels_count": dup,
        "cycle_check": "N/A",
        "disconnected_component_rate": "N/A",
        "na_rationale": (
            "Annotations are stored as leveled orders (a single acyclic chain "
            "of co-exist clusters); raw pairwise relations are not retained, so "
            "cycles and disconnected components are not recoverable. The "
            "duplicate-term-across-levels count is the computable integrity check."
        ),
    }

    return report
