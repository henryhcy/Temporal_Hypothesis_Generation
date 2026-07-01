"""Worked examples per template (06_pilot_examples.md, Step 4).

For each of the 30 template groups, pick a real viable core from MedTempo and
show, on real data: the supported and refuted example text (all rendered from
the same existing core), the conditioned counts (k, n), the significance test
that applies with its p-value, the 95% CI, and the gold verdict.

Refuted examples assert a FALSE relation about the SAME real, co-occurring
events (never absent events), per the central requirement of 06.

Outputs (data/pilot/):
- examples.md    -- human-readable worked examples with test computation
- examples.jsonl -- machine-readable, one record per (group, polarity)
- examples.tex   -- a LaTeX section to fold into the template v6 catalogue

    python scripts/make_examples.py [--db data/medtempo.db] [--out data/pilot]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from temporal_hypo.core.answers import compute_answer
from temporal_hypo.core.min_n import min_n_gate
from temporal_hypo.generation.cores import (
    enumerate_group_full,
    feasible_polarities,
    realize,
)
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.templates import load_groups, render

_REPO = Path(__file__).resolve().parent.parent

_TEST_LABEL = {
    "binom_exact": "binomial exact",
    "fisher_exact": "Fisher exact (2x2)",
    "multinomial_gof_exact": "multinomial GOF (exact)",
    "multinomial_gof_asymptotic": "multinomial GOF (chi-square)",
    "homogeneity_exact": "Fisher-Freeman-Halton (exact)",
    "homogeneity_asymptotic": "homogeneity (chi-square)",
}


def _group_viable(index, group):
    """Viable cores for a group. Report-level cores are single deterministic
    observations (n is None) and are not floor-gated -- every report is usable."""
    cores = enumerate_group_full(index, group)
    if group.level == "report":
        return cores
    return [c for c in cores if min_n_gate(c.n, c.family, n2=c.n2).testable]


def _pick_core(viable):
    """A representative viable core: prefer one that yields BOTH verdicts, max n."""
    if not viable:
        return None
    return max(viable, key=lambda c:
               ({"supported", "refuted"} <= feasible_polarities(c), c.n or 0))


def _example_for(index, group, core) -> dict:
    ans = compute_answer(index, group.id, core.events,
                         vaccines=core.vaccines, report_id=core.report_id)
    fp = feasible_polarities(core)
    polarities = [p for p in ("supported", "refuted") if p in fp] or ["insufficient"]

    rendered = {}
    for pol in polarities:
        facts = realize(core, pol)
        rendered[pol] = {
            "gold_verdict": facts.gold_verdict,
            "question": render(group, "original", "question", facts.slot_values),
            "claim": render(group, "original", "claim", facts.slot_values),
        }

    test = None
    if ans.sig_test is not None:
        test = {
            "name": _TEST_LABEL.get(ans.sig_test, ans.sig_test),
            "p_value": ans.p_value,
            "significant": ans.significant,
        }
    return {
        "group_id": group.id, "family": group.family, "level": group.level,
        "answer_type": group.answer_type,
        "events": list(core.events),
        "vaccines": list(core.vaccines),
        "report_id": core.report_id,
        "k": core.k, "n": core.n, "k2": core.k2, "n2": core.n2,
        "proportion": round(ans.proportion, 4) if ans.proportion is not None else None,
        "ci": [round(ans.ci[0], 4), round(ans.ci[1], 4)] if ans.ci else None,
        "effect_size": round(ans.effect_size, 4) if ans.effect_size is not None else None,
        "options": ans.options, "gold_answer": ans.gold_answer,
        "test": test,
        "examples": rendered,
    }


def run(db_path: Path, out_dir: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    index = CorpusIndex.load(conn)
    groups = load_groups()
    entries = []
    for group in groups.values():
        viable = _group_viable(index, group)
        core = _pick_core(viable)
        if core is None:
            entries.append({"group_id": group.id, "note": "no viable core"})
            continue
        e = _example_for(index, group, core)
        # per-template richness: how many cores can yield a TRUE (supported)
        # example vs a refuted one -- so we see which templates are rich vs poor.
        e["viable_cores"] = len(viable)
        e["supported_capable"] = sum(1 for c in viable
                                     if "supported" in feasible_polarities(c))
        e["refuted_capable"] = sum(1 for c in viable
                                   if "refuted" in feasible_polarities(c))
        entries.append(e)
    conn.close()

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "examples.jsonl", "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    md = _render_md(entries)
    (out_dir / "examples.md").write_text(md, encoding="utf-8")
    (out_dir / "examples.tex").write_text(_render_tex(entries), encoding="utf-8")
    # committed, directly-readable review copy under docs/reference/
    ref = _REPO / "docs" / "reference" / "Worked_Examples.md"
    ref.write_text(md, encoding="utf-8")
    return {"entries": entries, "out_dir": str(out_dir), "ref": str(ref)}


def _cohort_str(e) -> str:
    if e["report_id"] is not None:
        return f"report VAERS-{e['report_id']}"
    if len(e["vaccines"]) == 2:
        return f"{e['vaccines'][0]} vs {e['vaccines'][1]}"
    return e["vaccines"][0] if e["vaccines"] else "?"


def _counts_str(e) -> str:
    if e["n"] is None:
        return "(single report; deterministic)"
    s = f"k={e['k']} / n={e['n']}"
    if e["n2"] is not None:
        s += f"  |  cohort2 k={e['k2']} / n={e['n2']}"
    if e["proportion"] is not None:
        s += f"  (rate {e['proportion']})"
    return s


def _render_md(entries) -> str:
    out = ["# Worked Examples per Template (real MedTempo data)", "",
           "One live example per template group. Each shows the conditioned",
           "counts, the significance test computed on the real data, and the",
           "gold verdict. Refuted examples assert a false relation about the",
           "SAME real, co-occurring events.", "",
           "## True-case distribution (which templates are rich vs poor)", "",
           "`supported-capable` = number of viable cores that can yield a TRUE "
           "(supported) example.", "",
           "| template | viable cores | supported-capable | refuted-capable |",
           "|---|--:|--:|--:|"]
    for e in entries:
        if e.get("note"):
            out.append(f"| {e['group_id']} | 0 | 0 | 0 |")
        else:
            out.append(f"| {e['group_id']} | {e['viable_cores']} "
                       f"| {e['supported_capable']} | {e['refuted_capable']} |")
    out.append("")
    for e in entries:
        if e.get("note"):
            out += [f"## {e['group_id']}  --  {e['note']}", ""]
            continue
        out.append(f"## {e['group_id']}  ({e['family']}, {e['level']}, {e['answer_type']})")
        out.append(f"- **Qualified cores**: {e['viable_cores']} viable | "
                   f"{e['supported_capable']} supported-capable (true cases) | "
                   f"{e['refuted_capable']} refuted-capable")
        out.append(f"- **Core**: events {e['events']}, cohort {_cohort_str(e)}")
        out.append(f"- **Conditioned counts**: {_counts_str(e)}")
        if e["test"]:
            t = e["test"]
            pv = "n/a" if t["p_value"] is None else f"{t['p_value']:.4g}"
            out.append(f"- **Test**: {t['name']}, p = {pv} "
                       f"({'significant' if t['significant'] else 'not significant'})")
        else:
            out.append("- **Test**: none (report-level: single observation, no "
                       "sampling distribution)")
        if e["ci"]:
            out.append(f"- **95% CI**: {e['ci']}"
                       + (f", effect size {e['effect_size']}" if e["effect_size"] is not None else ""))
        if e["gold_answer"] is not None:
            out.append(f"- **Options**: {e['options']}  ->  correct: **{e['gold_answer']}**")
        for pol, r in e["examples"].items():
            out.append(f"- **{r['gold_verdict'].upper()}** example:")
            out.append(f"    - Q: {r['question']}")
            out.append(f"    - Claim: {r['claim']}")
        out.append("")
    return "\n".join(out) + "\n"


def _esc(s) -> str:
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("_", r"\_"), ("#", r"\#"), ("{", r"\{"), ("}", r"\}")]:
        s = str(s).replace(a, b)
    return s


def _render_tex(entries) -> str:
    out = [r"\section{Worked Examples per Template (computed from MedTempo)}",
           r"Each template group is shown with one real viable core: the "
           r"conditioned counts, the significance test computed on the data, and "
           r"the gold verdict. Refuted examples assert a false relation about the "
           r"same real, co-occurring events.", ""]
    for e in entries:
        out.append(r"\subsection*{" + _esc(e["group_id"]) + "}")
        if e.get("note"):
            out.append(_esc(e["note"]))
            continue
        out.append(r"\textbf{Qualified cores:} " + f"{e['viable_cores']} viable, "
                   f"{e['supported_capable']} supported-capable (true cases), "
                   f"{e['refuted_capable']} refuted-capable" + r". \\")
        out.append(r"\textbf{Core:} events " + _esc(", ".join(e["events"]))
                   + r"; cohort " + _esc(_cohort_str(e)) + r". \\")
        out.append(r"\textbf{Counts:} " + _esc(_counts_str(e)) + r". \\")
        if e["test"]:
            t = e["test"]
            pv = "n/a" if t["p_value"] is None else f"{t['p_value']:.4g}"
            out.append(r"\textbf{Test:} " + _esc(t["name"]) + f", $p = {pv}$ ("
                       + ("significant" if t["significant"] else "not significant")
                       + r"). \\")
        else:
            out.append(r"\textbf{Test:} none (report-level). \\")
        for pol, r in e["examples"].items():
            out.append(r"\textbf{" + _esc(r["gold_verdict"]) + r":} "
                       + _esc(r["claim"]) + r" \\")
        out.append("")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate worked examples per template.")
    ap.add_argument("--db", type=Path, default=_REPO / "data" / "medtempo.db")
    ap.add_argument("--out", type=Path, default=_REPO / "data" / "pilot")
    args = ap.parse_args()
    res = run(args.db, args.out)
    entries = res["entries"]
    ok = sum(1 for e in entries if not e.get("note"))
    print(f"Wrote worked examples for {ok}/{len(entries)} templates to {res['out_dir']}")
    print("  examples.md, examples.jsonl, examples.tex")
    missing = [e["group_id"] for e in entries if e.get("note")]
    if missing:
        print(f"  NO viable core (should be none): {missing}")


if __name__ == "__main__":
    main()
