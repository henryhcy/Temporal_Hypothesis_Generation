"""Whole-dataset statistics for a generated release (2026-08-14).

Reads a release directory containing ``<stem>_questions.jsonl`` and
``<stem>_answers.jsonl`` (as written by ``writers.split_release``) and emits
``dataset_statistics.md`` + ``.json`` beside them. Every number the Overleaf
dataset-construction section quotes comes from THIS script's JSON, so the
draft can never drift from the artifact it describes.

    python scripts/dataset_stats.py [--dir data/release/v1] [--stem pilot_instances]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics as st
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent


def _quantiles(xs, q=(0.25, 0.5, 0.75)):
    if not xs:
        return None
    xs = sorted(xs)
    out = {}
    for p in q:
        i = p * (len(xs) - 1)
        lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
        out[f"q{int(p * 100)}"] = round(xs[lo] + (xs[hi] - xs[lo]) * (i - lo), 4)
    out["min"], out["max"] = round(xs[0], 4), round(xs[-1], 4)
    return out


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_stats(rel_dir: Path, stem: str) -> dict:
    a_path = rel_dir / f"{stem}_answers.jsonl"
    q_path = rel_dir / f"{stem}_questions.jsonl"
    instances = [json.loads(l) for l in
                 a_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    # answers are one row per instance (writers.split_release, 2026-08-14);
    # each row lists its 8 question records
    n_records = sum(len(r["hypothesis_ids"]) for r in instances)

    groups = sorted({r["group_id"] for r in instances})
    per_group: dict[str, dict] = {}
    for gid in groups:
        gi = [r for r in instances if r["group_id"] == gid]
        verd = Counter(r["gold_verdict"] for r in gi)
        subs = Counter(r["insufficient_subtype"] for r in gi
                       if r["gold_verdict"] == "insufficient")
        ns = [r["gold_n"] for r in gi if r["gold_n"]]
        decisive_facts = {r["fact_id"] for r in gi
                          if r["gold_verdict"] in ("supported", "refuted")}
        per_group[gid] = {
            "level": gi[0]["level"],
            "family": gi[0]["family"],
            "mode": gi[0]["mode"],
            "answer_type": gi[0]["answer_type"],
            "instances": len(gi),
            "records": sum(len(r["hypothesis_ids"]) for r in gi),
            "supported": verd.get("supported", 0),
            "refuted": verd.get("refuted", 0),
            "insufficient": verd.get("insufficient", 0),
            "insufficient_subtypes": dict(subs),
            "negated": sum(1 for r in gi if r.get("negated")),
            "reoriented": sum(1 for r in gi if r.get("flip_kind")),
            "distinct_cores": len({r["derived_from_core_id"] for r in gi}),
            "distinct_facts": len({r["fact_id"] for r in gi}),
            "decisive_distinct_facts": len(decisive_facts),
            "gold_n": _quantiles(ns),
            "positional_coverage": (
                round(sum(1 for r in gi if r.get("positional")) / len(gi), 3)
                if gi else None),
        }

    decis = [r for r in instances if r["gold_verdict"] in ("supported", "refuted")]
    widths = [r["ci"][1] - r["ci"][0] for r in instances if r.get("ci")]
    effects = [abs(r["effect_size"]) for r in decis
               if r.get("effect_size") is not None]
    p_claims = [r["p_claim"] for r in decis
                if r["gold_verdict"] == "supported" and r.get("p_claim") is not None]

    mirror = Counter(r["derived_from_core_id"] for r in instances
                     if r["gold_verdict"] in ("supported", "refuted"))
    mirror_pairs = sum(1 for c in mirror.values() if c == 2)

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True,
                                cwd=_REPO).stdout.strip()
    except OSError:
        commit = None

    families = sorted({g["family"] for g in per_group.values()})
    per_family = {}
    for fam in families:
        fg = [g for g in per_group.values() if g["family"] == fam]
        per_family[fam] = {
            "groups": sum(1 for _ in fg),
            "instances": sum(g["instances"] for g in fg),
            "supported": sum(g["supported"] for g in fg),
            "refuted": sum(g["refuted"] for g in fg),
            "insufficient": sum(g["insufficient"] for g in fg),
        }

    return {
        "generated_from_commit": commit,
        "files": {
            "questions": {"path": q_path.name,
                          "bytes": q_path.stat().st_size,
                          "sha256": _sha256(q_path)},
            "answers": {"path": a_path.name,
                        "bytes": a_path.stat().st_size,
                        "sha256": _sha256(a_path)},
        },
        "totals": {
            "records": n_records,
            "instances": len(instances),
            "groups": len(groups),
            "registers": 4, "formats": 2,
            "distinct_cores": len({r["derived_from_core_id"]
                                   for r in instances}),
            "distinct_facts": len({r["fact_id"] for r in instances}),
            "supported": sum(1 for r in instances
                             if r["gold_verdict"] == "supported"),
            "refuted": sum(1 for r in instances
                           if r["gold_verdict"] == "refuted"),
            "insufficient": sum(1 for r in instances
                                if r["gold_verdict"] == "insufficient"),
            "insufficient_subtypes": dict(Counter(
                r["insufficient_subtype"] for r in instances
                if r["gold_verdict"] == "insufficient")),
            "negated": sum(1 for r in instances if r.get("negated")),
            "mirror_pairs": mirror_pairs,
            "positional_coverage": round(
                sum(1 for r in instances if r.get("positional"))
                / len(instances), 3),
        },
        "distributions": {
            "gold_n_all": _quantiles([r["gold_n"] for r in instances
                                      if r["gold_n"]]),
            "ci_width": _quantiles(widths),
            "abs_effect_size_decisive": _quantiles(effects),
            "p_claim_supported": _quantiles(p_claims),
        },
        "per_family": per_family,
        "per_group": per_group,
    }


def render_md(stats: dict) -> str:
    t = stats["totals"]
    lines = [
        "# Dataset Statistics",
        "",
        f"Generated from commit `{stats['generated_from_commit']}`.",
        "",
        f"| | |",
        f"|---|--:|",
        f"| records (instance x register x format) | {t['records']:,} |",
        f"| instances | {t['instances']:,} |",
        f"| groups | {t['groups']} |",
        f"| distinct cores | {t['distinct_cores']:,} |",
        f"| distinct facts (split/count key) | {t['distinct_facts']:,} |",
        f"| supported / refuted / insufficient | {t['supported']:,} / "
        f"{t['refuted']:,} / {t['insufficient']:,} |",
        f"| insufficient sub-types | {t['insufficient_subtypes']} |",
        f"| negated instances | {t['negated']:,} |",
        f"| mirror pairs (same core, both ways) | {t['mirror_pairs']:,} |",
        f"| positional block coverage | {t['positional_coverage']:.0%} |",
        "",
        "## Per group",
        "",
        "| group | level | mode | inst | sup | ref | insuf | sub-types | "
        "negated | reoriented | facts | median n |",
        "|---|---|---|--:|--:|--:|--:|---|--:|--:|--:|--:|",
    ]
    for gid, g in stats["per_group"].items():
        med = g["gold_n"]["q50"] if g["gold_n"] else "—"
        subs = ", ".join(f"{k[:5]}:{v}" for k, v in
                         sorted(g["insufficient_subtypes"].items())) or "—"
        lines.append(
            f"| {gid} | {g['level']} | {g['mode']} | {g['instances']} | "
            f"{g['supported']} | {g['refuted']} | {g['insufficient']} | {subs} | "
            f"{g['negated']} | {g['reoriented']} | {g['distinct_facts']} | {med} |")
    lines += ["", "## Distributions", ""]
    for name, d in stats["distributions"].items():
        lines.append(f"- **{name}**: {d}")
    lines += ["", "## Files", ""]
    for k, f in stats["files"].items():
        lines.append(f"- {k}: `{f['path']}` ({f['bytes']:,} bytes, "
                     f"sha256 `{f['sha256'][:16]}…`)")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=_REPO / "data" / "release" / "v1")
    ap.add_argument("--stem", type=str, default="pilot_instances")
    args = ap.parse_args()
    stats = build_stats(args.dir, args.stem)
    (args.dir / "dataset_statistics.json").write_text(
        json.dumps(stats, indent=2), encoding="utf-8")
    (args.dir / "dataset_statistics.md").write_text(
        render_md(stats), encoding="utf-8")
    t = stats["totals"]
    print(f"{t['records']:,} records / {t['instances']:,} instances / "
          f"{t['groups']} groups")
    print(f"verdicts {t['supported']}/{t['refuted']}/{t['insufficient']}, "
          f"facts {t['distinct_facts']:,}")
    print(f"written to {args.dir / 'dataset_statistics.md'}")


if __name__ == "__main__":
    main()
