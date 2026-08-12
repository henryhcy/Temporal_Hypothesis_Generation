"""ONE-OFF: render ONE sample instance as a single flat row in an .xlsx.

Reads `docs/reference/Sample_Instances.json` (produced by
`scripts/make_sample_instances.py`) and writes
`docs/reference/Sample_Instances.xlsx` with **one sheet and one data row** -- the
whole instance flattened, so the released schema reads left-to-right in the shape a
spreadsheet user expects.

Takes the FIRST example (P-V1) unless `--index` says otherwise. Report-id lists are
comma-joined into single cells; at ~25 ids that is a few hundred characters, well
inside Excel's 32,767-character cell limit.

Header colours mark what each block is:
  dark grey  identity          blue   the hypothesis as the framework sees it
  green      the label         brown  the statistics behind the label
  purple     which reports were used
  light grey DESCRIPTIVE ONLY -- not the label
  gold       the paired (mirror) instance

Needs `openpyxl` (declared under the `render` extra, not a runtime dependency):

    pip install -e ".[render]"
    python scripts/sample_instances_to_excel.py [--index 0]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

_REPO = Path(__file__).resolve().parent.parent

_HDR = Font(bold=True, color="FFFFFF", size=10)
_FILLS = {
    "id": "44546A",
    "text": "2F5597",
    "gold": "375623",
    "test": "833C00",
    "evidence": "7030A0",
    "descr": "808080",
    "mirror": "BF8F00",
}
_NULL_BY_TEST = {
    "binom_exact": "P = 0.5",
    "modal_runner": "named cell = runner-up (P = 0.5 on the 2-cell table)",
    "fisher_exact": "p1 = p2",
}


def _join(ids):
    return ", ".join(str(i) for i in ids)


def flatten(s):
    """(column, value, colour-group) triples, in reading order."""
    gold, test = s["gold"], s["test"]
    ev = s["covered_case_ids"]
    pos = s.get("positional_statistics_DESCRIPTIVE_ONLY") or {}
    mp = s["mirror_pair"]
    ci = gold.get("ci") or [None, None]

    rows = [
        ("group_id", s["group_id"], "id"),
        ("mode", s["mode"], "id"),
        ("answer_type", s["answer_type"], "id"),
        ("level", s["level"], "id"),

        ("question_original", s["question_original"], "text"),
        ("claim_original", s["claim_all_registers"]["original"], "text"),
        ("claim_research", s["claim_all_registers"]["research"], "text"),
        ("claim_media", s["claim_all_registers"]["media"], "text"),
        ("claim_clinical", s["claim_all_registers"]["clinical"], "text"),

        ("gold_verdict", gold.get("gold_verdict"), "gold"),
        ("test_verdict", gold.get("test_verdict"), "gold"),
        ("insufficient_subtype", gold.get("insufficient_subtype"), "gold"),
        ("negated", gold.get("negated"), "gold"),
        ("gold_answer", gold.get("gold_answer"), "gold"),
        ("options", _join(gold.get("options") or []) or None, "gold"),
        ("gold_proportion", gold.get("gold_proportion"), "gold"),
        ("gold_n", gold.get("gold_n"), "gold"),
        ("gold_k", gold.get("gold_k"), "gold"),
        ("gold_n2", gold.get("gold_n2"), "gold"),
        ("gold_k2", gold.get("gold_k2"), "gold"),
        ("ci_low", ci[0], "gold"),
        ("ci_high", ci[1], "gold"),
        ("ci_width", gold.get("ci_width"), "gold"),
        ("confidence_tag", gold.get("confidence_tag"), "gold"),
        ("effect_size", gold.get("effect_size"), "gold"),

        ("sig_test", test.get("sig_test"), "test"),
        ("null", _NULL_BY_TEST.get(test.get("sig_test")), "test"),
        ("p_value", test.get("p_value"), "test"),
        ("p_claim", test.get("p_claim"), "test"),
        ("p_opposite", test.get("p_opposite"), "test"),
        ("significant", test.get("significant"), "test"),
        ("alpha", test.get("alpha"), "test"),
        ("min_n_floor", test.get("min_n_floor"), "test"),
        ("family", test.get("family"), "test"),
    ]

    # evidence: flat for a single cohort, cohort-prefixed for two
    blocks = {"": ev} if "denominator" in ev else ev
    for prefix, block in blocks.items():
        pre = f"{prefix}_" if prefix else ""
        for setname in ("denominator", "numerator", "excluded", "ties"):
            if setname in block:
                rows.append((f"{pre}{setname}_count",
                             block[setname]["count"], "evidence"))
                rows.append((f"{pre}{setname}_report_ids",
                             _join(block[setname]["report_ids"]), "evidence"))

    for test_name, payload in pos.items():
        for k, v in payload.items():
            if k in ("what", "note", "caveat"):
                continue
            rows.append((f"{test_name}__{k} (DESCRIPTIVE ONLY)", v, "descr"))

    rows += [
        ("derived_from_core_id", mp["derived_from_core_id"], "mirror"),
        ("mirror_refuted_text", mp["refuted_text"], "mirror"),
        ("mirror_refuted_verdict", mp["refuted_verdict"], "mirror"),
        ("mirror_refuted_p_claim", mp["refuted_p_claim"], "mirror"),
        ("mirror_refuted_p_opposite", mp["refuted_p_opposite"], "mirror"),
    ]
    return [r for r in rows if r[1] is not None]


def main() -> None:
    ap = argparse.ArgumentParser(description="One sample instance -> one xlsx row")
    ap.add_argument("--src", type=Path,
                    default=_REPO / "docs" / "reference" / "Sample_Instances.json")
    ap.add_argument("--out", type=Path,
                    default=_REPO / "docs" / "reference" / "Sample_Instances.xlsx")
    ap.add_argument("--index", type=int, default=0,
                    help="which sample to render (default 0 = the first, P-V1)")
    args = ap.parse_args()

    samples = json.loads(args.src.read_text(encoding="utf-8"))
    s = samples[args.index]
    cells = flatten(s)

    wb = Workbook()
    ws = wb.active
    ws.title = s["group_id"]
    ws.append([c[0] for c in cells])
    ws.append([c[1] for c in cells])

    for i, (name, value, group) in enumerate(cells, start=1):
        h = ws.cell(row=1, column=i)
        h.font = _HDR
        h.fill = PatternFill("solid", fgColor=_FILLS[group])
        h.alignment = Alignment(wrap_text=True, vertical="bottom")
        ws.cell(row=2, column=i).alignment = Alignment(vertical="top", wrap_text=True)
        width = max(len(name) + 2, min(len(str(value)) + 2, 60))
        ws.column_dimensions[get_column_letter(i)].width = min(width, 60)
    ws.row_dimensions[1].height = 46
    ws.freeze_panes = "A2"
    wb.save(args.out)

    print(f"wrote {args.out}")
    print(f"  sheet '{ws.title}': 1 header row + 1 data row, {len(cells)} columns")
    for name, value, _ in cells:
        v = str(value)
        print(f"    {name:<46} {v[:56] + ('…' if len(v) > 56 else '')}")


if __name__ == "__main__":
    main()
