"""Output writers: pilot JSONL, distribution report (md + json), Part C sample."""

from __future__ import annotations

import json
from pathlib import Path


def write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_report(report: dict, md_path: Path, json_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    md_path.write_text(_render_report_md(report), encoding="utf-8")


def _render_report_md(r: dict) -> str:
    out: list[str] = ["# Pilot Distribution Report (Part A)", ""]

    a1 = r["A1_viable_core_counts"]
    out += ["## A1. Viable-core counts per group", ""]
    out += [f"- Viable target per group: **{a1['viable_target']}**"]
    out += [f"- Under-target groups ({len(a1['under_target_groups'])}): "
            f"{', '.join(a1['under_target_groups']) or 'none'}"]
    out += [f"- Starved groups (0 viable): "
            f"{', '.join(a1['starved_groups']) or 'none'}", ""]
    out += ["| group | viable | enumerated |", "|---|---:|---:|"]
    for gid, d in a1["per_group"].items():
        out.append(f"| {gid} | {d['viable_cores']} | {d['total_enumerated']} |")
    out.append("")

    out += ["## A2. Cohort-size (n) distribution per family", ""]
    for fam, d in r["A2_cohort_size_distribution"].items():
        s = d["summary"]
        out.append(f"- **{fam}**: n={s.get('count',0)}  "
                   f"min={s.get('min')} p25={s.get('p25')} median={s.get('median')} "
                   f"p75={s.get('p75')} max={s.get('max')}")
        out.append(f"  - histogram: {d['histogram']}")
    out.append("")

    out += ["## A3. Natural verdict distribution (no balancing)", ""]
    out += ["| family | supported | refuted | insufficient |", "|---|---:|---:|---:|"]
    for fam, d in r["A3_natural_verdict_distribution"]["per_family"].items():
        fr = d["fractions"]
        out.append(f"| {fam} | {fr['supported']} | {fr['refuted']} | "
                   f"{fr['insufficient']} |")
    out += ["", "Per-group natural verdicts:", "",
            "| group | supported | refuted | insufficient |", "|---|---:|---:|---:|"]
    for gid, d in r["A3_natural_verdict_distribution"]["per_group"].items():
        fr = d["fractions"]
        out.append(f"| {gid} | {fr['supported']} | {fr['refuted']} | "
                   f"{fr['insufficient']} |")
    out.append("")

    a4 = r["A4_ci_width_distribution"]
    out += ["## A4. Wilson CI-width distribution (single-proportion cores)", ""]
    out += [f"- summary: {a4['summary']}"]
    out += [f"- histogram: {a4['histogram']}"]
    out += [f"- fraction low-confidence (width > 0.30): "
            f"**{a4['fraction_low_confidence_gt_0.30']}**"]
    out += [f"- {a4['note']}", ""]

    a5 = r["A5_multi_vaccine_overlap"]
    out += ["## A5. Multi-vaccine overlap and insufficiency", ""]
    out += ["| pair | both clear | one thin | frac insufficient | enough? |",
            "|---|---:|---:|---:|:--:|"]
    for pair, d in a5["per_pair"].items():
        out.append(f"| {pair} | {d['both_clear']} | {d['one_thin']} | "
                   f"{d['fraction_insufficient']} | "
                   f"{'yes' if d['enough_for_reduced_budget'] else 'NO'} |")
    out += ["", f"- Janssen pairs lacking enough computable cores "
            f"(fallback trigger): {', '.join(a5['janssen_pairs_flagged']) or 'none'}",
            ""]

    a6 = r["A6_representation_diagnostics"]
    out += ["## A6. Representation diagnostics", ""]
    out += [f"- first/last tie-rate summary: {a6['first_last_tie_rate']['summary']}"]
    out += [f"- first-level co-occurrence rate (reports whose earliest level has "
            f">1 term): **{a6['first_level_co_occurrence_rate']}**"]
    out += [f"- duplicate-term-across-levels count: "
            f"{a6['duplicate_term_across_levels_count']}"]
    out += [f"- cycle check: {a6['cycle_check']}; disconnected-component rate: "
            f"{a6['disconnected_component_rate']}"]
    out += [f"- _{a6['na_rationale']}_", ""]

    return "\n".join(out)


def write_validation_sample(samples: list[dict], path: Path) -> None:
    """Part C: 20-30 hand-checkable cores with full reconstruction detail."""
    path.parent.mkdir(parents=True, exist_ok=True)
    out = ["# Part C: Validation Sample (gold-label correctness guard)", "",
           "Each entry records the cohort, the per-report leveled orders entering "
           "the denominator, the numerator/denominator under the locked rule, and "
           "the computed gold. Recompute by hand to confirm before trusting Part A.",
           ""]
    for i, s in enumerate(samples, 1):
        out.append(f"## {i}. {s['group_id']} ({s['mode']}) -- {s['answer_type']}")
        out.append(f"- claim: \"{s['claim']}\"")
        out.append(f"- events: {s['events']}  vaccines: {s['vaccines']}")
        out.append(f"- locked rule: {s['rule']}")
        out.append(f"- denominator (n): {s['n']}   numerator (k): {s['k']}")
        out.append(f"- gold proportion: {s['proportion']}   gold verdict: "
                   f"**{s['verdict']}**")
        if s.get("cohort2"):
            c2 = s["cohort2"]
            out.append(f"- cohort 2: proportion={c2['proportion2']} "
                       f"n={c2['n2']} k={c2['k2']}")
        if s.get("ci"):
            out.append(f"- 95% CI: {s['ci']}  (width {s['ci_width']}, "
                       f"tag {s['confidence_tag']})")
        if s.get("sample_reports"):
            out.append(f"- sample reports entering the denominator "
                       f"(vaers_id -> relevant levels):")
            for vid, lv in s["sample_reports"]:
                out.append(f"    - {vid}: {lv}")
        out.append("")
    path.write_text("\n".join(out), encoding="utf-8")
