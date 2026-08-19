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
    """Part C: hand-checkable entries with the evidence and the arithmetic.

    Each entry lists the reports that SUPPORT the claim, the ones that are in the
    denominator but do NOT, and the ones EXCLUDED with the reason -- so the counts
    can be recomputed by eye and the conditioning rule verified, which is the one
    thing this guard exists to catch.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    out = ["# Part C: Validation Sample (gold-label correctness guard)", "",
           "For each entry: the claim as the instance asserts it, the reports behind "
           "it split into supports / against / excluded, and the test that produced "
           "the verdict. **Recompute the counts by eye before trusting Part A.**", "",
           "`levels` are the leveled-order positions of the claim's events in that "
           "report -- lower index = earlier. Equal indices mean co-exist.", "",
           "What to check, in order of what has actually gone wrong before:", "",
           "1. **The exclusion rule.** Every report under `excluded` must genuinely "
           "fail the conditioning for the stated reason, and none of them may appear "
           "under supports/against. A precedes claim must NOT count co-exist pairs.",
           "2. **The counts.** `len(supports) + len(against) = n`, and "
           "`len(supports) = k`. Flagged automatically as `counts match`.",
           "3. **The direction.** Each report under `supports` must actually satisfy "
           "the claim as worded (including negation, if `negated` is true).",
           "4. **The verdict.** `supported` needs p_claim < alpha; `refuted` needs "
           "p_opposite < alpha; otherwise `insufficient` with a sub-type.", ""]

    def _rows(label, rows):
        if not rows:
            return []
        block = [f"  - {label}:"]
        for vid, lv in rows:
            block.append(f"      - {vid}  levels={lv}")
        return block

    for i, s_ in enumerate(samples, 1):
        neg = "  [NEGATED wording]" if s_.get("negated") else ""
        out.append(f"## {i}. {s_['group_id']} ({s_['mode']}, {s_['answer_type']}) "
                   f"-- realized as {s_['polarity']}{neg}")
        out.append(f"- claim: \"{s_['claim']}\"")
        out.append(f"- events: {s_['events']}   cohort: {s_['vaccines'] or 'report-level'}")
        out.append(f"- conditioning rule: {s_['rule']}")
        if s_.get("exclusion_reason"):
            out.append(f"- excluded when: {s_['exclusion_reason']}")
        out.append(f"- **n = {s_['n']}, k = {s_['k']}, proportion = {s_['proportion']}**")
        cc = s_.get("counts_check")
        if cc:
            ok = "OK" if (cc["matches_gold_n"] and cc["matches_gold_k"]) else "MISMATCH"
            out.append(f"- counts match: **{ok}** "
                       f"(denominator ids {cc['denominator_ids']} vs n {s_['n']}; "
                       f"numerator ids {cc['numerator_ids']} vs k {s_['k']}; "
                       f"{cc['excluded_ids']} excluded)")
        if s_.get("min_n_floor") is not None:
            out.append(f"- min-n floor for this family: {s_['min_n_floor']}")
        out.append(f"- test: {s_['test']}   p_claim = {s_['p_claim']}   "
                   f"p_opposite = {s_['p_opposite']}   alpha = {s_['alpha']}")
        sub = f" ({s_['subtype']})" if s_.get("subtype") else ""
        out.append(f"- **gold verdict: {s_['verdict']}{sub}**")
        if s_.get("ci"):
            out.append(f"- 95% CI: {s_['ci']}")
        if s_.get("cohort2"):
            c2 = s_["cohort2"]
            out.append(f"- cohort 2: proportion={c2['proportion2']} n={c2['n2']} "
                       f"k={c2['k2']}")
        out += _rows("supports the claim (numerator)", s_.get("supports"))
        out += _rows("in denominator but does NOT support", s_.get("against"))
        out += _rows("EXCLUDED from the denominator", s_.get("excluded"))
        for key in ("cohort_1", "cohort_2"):
            if s_.get(key):
                b = s_[key]
                out.append(f"  - {key}: n={b['denominator']} k={b['numerator']} "
                           f"excluded={b['excluded']}")
                out += _rows(f"{key} sample", b["sample"])
        out.append("")
    path.write_text("\n".join(out), encoding="utf-8")


def split_release(records: list[dict], out_dir: Path, *, stem: str = "benchmark") -> dict:
    """Write the release as TWO files, enforcing the input/gold boundary.

    ``<stem>_questions.jsonl`` carries only ``instances.INPUT_FIELDS`` -- what a
    framework may see. ``<stem>_answers.jsonl`` carries everything, keyed by
    ``hypothesis_id``.

    This exists because the gold side now includes ``evidence_ids``, the report ids
    the statistic was computed over. Those ids ARE the answer to the localization
    step (finding ~19 relevant reports in a ~1,000-report cohort), so handing them
    to the framework would remove the hardest part of the task. A single flat file
    made that boundary a convention; this makes it mechanical.
    """
    from temporal_hypo.generation.instances import INPUT_FIELDS

    questions = [{k: r[k] for k in INPUT_FIELDS if k in r} for r in records]
    q_path = out_dir / f"{stem}_questions.jsonl"
    a_path = out_dir / f"{stem}_answers.jsonl"
    write_jsonl(questions, q_path)
    write_jsonl(records, a_path)

    leaked = sorted({k for q in questions for k in q} - set(INPUT_FIELDS))
    if leaked:
        raise ValueError(f"non-input fields leaked into the questions file: {leaked}")
    return {"questions": str(q_path), "answers": str(a_path),
            "n_questions": len(questions), "input_fields": list(INPUT_FIELDS)}
