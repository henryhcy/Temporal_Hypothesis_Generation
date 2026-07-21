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

from temporal_hypo.core.answers import compute_answer, core_significance
from temporal_hypo.core.min_n import min_n_gate
from temporal_hypo.generation.cores import (
    enumerate_group_full,
    feasible_polarities,
    realize,
)
from temporal_hypo.core import positions
from temporal_hypo.core import significance as _sig
from temporal_hypo.generation import corpus
from temporal_hypo.generation.corpus import CorpusIndex
from temporal_hypo.generation.templates import REGISTERS, load_groups, render

_REPO = Path(__file__).resolve().parent.parent

_TEST_LABEL = {
    "binom_exact": "binomial exact",
    "modal_runner": "modal-vs-runner-up binomial",
    "fisher_exact": "Fisher exact (2x2)",
    "multinomial_gof_exact": "multinomial GOF (exact)",
    "multinomial_gof_asymptotic": "multinomial GOF (chi-square)",
    "homogeneity_exact": "Fisher-Freeman-Halton (exact)",
    "homogeneity_asymptotic": "homogeneity (chi-square)",
}

# How each p-value is computed (shown per example and in the methods appendix).
_HOW = {
    "binom_exact": "exact binomial vs the 1/2 chance null (pairwise precedes, co-occurs), "
                   "ONE-SIDED in the observed direction (greater if the rate is above 0.5, "
                   "less if below) so it corroborates the observed verdict, not the reverse",
    "modal_runner": "modal-vs-runner-up -- one-sided exact binomial of the modal cell's "
                    "count vs the runner-up's (null 0.5): is the named most-common ordering/"
                    "event significantly ahead of its nearest competitor? (verifies the mode, "
                    "which GOF-vs-uniform cannot)",
    "fisher_exact": "Fisher exact on the 2x2 -- ONE-SIDED toward the higher-rate cohort for "
                    "the directional multi_dir_* claims, TWO-SIDED for the multi_differ_* "
                    "\"do they differ\" claims",
    "multinomial_gof_exact": "exact multinomial goodness-of-fit -- sum the multinomial "
                             "probabilities of every table (same n) whose chi-square "
                             "statistic vs uniform is >= the observed",
    "multinomial_gof_asymptotic": "chi-square goodness-of-fit vs uniform (large-n "
                                  "approximation, used only when every expected cell >= 5)",
    "homogeneity_exact": "Fisher-Freeman-Halton -- sum the probabilities of every 2xk table "
                         "with the observed margins that are <= the observed table's",
    "homogeneity_asymptotic": "chi-square test of homogeneity (used only when every "
                              "expected cell >= 5)",
    "wilcoxon": "Wilcoxon signed-rank -- rank |d| where d=level(A)-level(B) (co-exist d=0 "
                "dropped), sum the signed ranks; exact sign-flip null for small n, else "
                "normal approximation with tie/continuity correction",
    "mannwhitney": "Mann-Whitney U -- pool and rank the two cohorts' values, U from the "
                   "rank-sum; normal approximation with tie correction",
    "friedman": "Friedman -- rank the three events within each report (ties averaged), "
                "chi-square (df=2) on the rank sums",
    "kendall": "Kendall's W -- normalised concordance (0..1) of the within-report rankings; "
               "p from chi-square on n(k-1)W",
}


def _group_viable(index, group):
    """Viable cores for a group. Report-level cores are single deterministic
    observations (n is None) and are not floor-gated -- every report is usable."""
    cores = enumerate_group_full(index, group)
    if group.level == "report":
        return cores
    return [c for c in cores if min_n_gate(c.n, c.family, n2=c.n2).testable]


def _categorical_definite(group, core, sig) -> bool:
    """A core whose gold label is a definite verdict a categorical test can
    corroborate. Excludes PROP (gold is a within-5pp tolerance claim, not a
    significance claim) and report-level cores (single deterministic
    observation -> no sampling distribution, sig.test is None)."""
    return (sig.test is not None and group.answer_type != "PROP"
            and core.natural_verdict in ("supported", "refuted"))


def _pick_core(group, graded):
    """Pick the example core to showcase for a template.

    Prefer a SUCCESSFUL example -- a definite gold verdict that the categorical
    test corroborates (significant at alpha) and that can render a supported
    claim -- so the report shows a worked example whose p-value backs the gold
    label. Only when NO such core exists do we fall back to a both-verdict,
    max-n core (the failed example, shown as-is, exactly as before).

    Ranked (desc): corroborated > can-show-supported > both-polarity > larger n.
    ``graded`` is a list of ``(core, Significance)`` pairs.
    """
    if not graded:
        return None

    def key(item):
        c, s = item
        corroborated = _categorical_definite(group, c, s) and bool(s.significant)
        fp = feasible_polarities(c)
        return (corroborated, "supported" in fp,
                {"supported", "refuted"} <= fp, c.n or 0)

    return max(graded, key=key)[0]


# --- fail-case reporting (definite gold verdict the categorical test can't back) --

def _fail_reason(core, sig) -> str:
    """Why a definite-gold core is not significant: the significance min-n GATE,
    a small n, a weak effect, or a small between-cohort gap."""
    n = core.n or 0
    # A small p that is STILL 'not significant' means the significance verdict's
    # min-n floor (>=MIN_N) overrode it. Common for sequence: the family viability
    # floor is 5 but significance requires n>=10, so an exact test on a near-
    # unanimous but tiny sample (e.g. 7/8, p=0.000) is gated out.
    if sig.p_value is not None and sig.p_value < _sig.ALPHA:
        return (f"p={sig.p_value:.3f} < 0.05 but n={n} below the significance "
                f"min-n gate ({_sig.MIN_N}): verdict forced to insufficient")
    p = core.proportion or 0.0
    if sig.test == "binom_exact":
        null = sig.details.get("null", 0.5)
        delta = abs(p - null)
        if n < 20 and delta < 0.2:
            return f"small n and weak effect (rate {p:.2f} vs null {null:.2f}, n={n})"
        if n < 20:
            return f"n too small (n={n}) to reject at a=0.05"
        return f"effect too weak (rate {p:.2f} vs null {null:.2f}, n={n})"
    if sig.test == "fisher_exact":
        d = abs(p - (core.proportion2 or 0.0))
        lo = min(core.n or 0, core.n2 or 0)
        if lo < 20 and d < 0.2:
            return f"small cohorts and small gap (gap={d:.2f}, n={core.n}/{core.n2})"
        if lo < 20:
            return f"cohorts too small (n={core.n}/{core.n2})"
        return f"difference too small (gap={d:.2f}, n={core.n}/{core.n2})"
    # multinomial GOF / homogeneity distribution tests
    return f"distribution too close to uniform / n small (n={core.n})"


def _ladder(items, k=10):
    """A representative ladder of <=k items from a sorted list (endpoints kept)."""
    n = len(items)
    if n <= k:
        return items
    return [items[round(i * (n - 1) / (k - 1))] for i in range(k)]


def _fail_case(core, sig) -> dict:
    return {
        "events": list(core.events), "vaccines": list(core.vaccines),
        "k": core.k, "n": core.n, "k2": core.k2, "n2": core.n2,
        "p": sig.p_value, "test": sig.test, "reason": _fail_reason(core, sig),
    }


def _fc_cohort(fc) -> str:
    v = fc["vaccines"]
    return f"{v[0]} vs {v[1]}" if len(v) == 2 else (v[0] if v else "?")


def _fc_counts(fc) -> str:
    s = f"{fc['k']}/{fc['n']}"
    if fc["n2"] is not None:
        s += f" ; {fc['k2']}/{fc['n2']}"
    return s


def _pv(p) -> str:
    return "n/a" if p is None else f"{p:.3f}"


def _side_label(alt) -> str:
    """How the tail is taken for the categorical test (empty for omnibus GOF)."""
    if alt in ("greater", "less"):
        return f" (one-sided, {alt})"
    if alt == "two-sided":
        return " (two-sided)"
    return ""


def _focal_ranks(index, ev, cohort):
    """The focal (first) event's within-triple rank per report in a cohort."""
    return [positions._avg_ranks(list(pos))[0]
            for pos in corpus.triple_positions(index, list(ev), cohort)]


def _position_test(index, group, core) -> dict | None:
    """The 05 position-based (rank) test for the group, computed on real data."""
    if core.report_id is not None:                 # report-level: not eligible
        return None
    gid, ev, vax = group.id, core.events, core.vaccines
    if gid in ("C-V1", "C-V2", "C-V3"):            # co-occurs has no position analog
        return None
    if group.level == "vaccine":
        cohort = index.cohort(vax[0])
        if len(ev) == 2:                           # precedes pair -> Wilcoxon
            r = positions.wilcoxon_signed_rank(
                corpus.pair_distances(index, ev[0], ev[1], cohort))
            return {"name": "Wilcoxon signed-rank",
                    "detail": f"level({ev[0]})-level({ev[1]}); n={r['n']} ({r['method']})",
                    "p_value": r["p"], "how": _HOW["wilcoxon"],
                    "null": f"H0: the {ev[0]}-vs-{ev[1]} rank-distances are symmetric "
                            "about 0 (neither event tends to come earlier)"}
        blocks = corpus.triple_positions(index, list(ev), cohort)
        if gid == "S-V4":                          # consistency -> Kendall's W
            r = positions.kendalls_w(blocks)
            return {"name": "Kendall's W",
                    "detail": f"W={r['W']:.3f}; n={len(blocks)} reports",
                    "p_value": r["p"], "how": _HOW["kendall"],
                    "null": "H0: no agreement in the event rankings across reports "
                            "(W = 0, orderings unrelated report-to-report)"}
        r = positions.friedman(blocks)             # triple ordering -> Friedman
        return {"name": "Friedman",
                "detail": f"Q={r['Q']:.2f} df={r['df']}; n={len(blocks)} reports",
                "p_value": r["p"], "how": _HOW["friedman"],
                "null": f"H0: {ev[0]}, {ev[1]}, {ev[2]} share one within-report rank "
                        "distribution (no systematic ordering)"}
    # multi-vaccine: compare the two cohorts
    c1, c2 = index.cohort(vax[0]), index.cohort(vax[1])
    if len(ev) == 2:                               # pair -> Mann-Whitney on d
        d1 = corpus.pair_distances(index, ev[0], ev[1], c1)
        d2 = corpus.pair_distances(index, ev[0], ev[1], c2)
        if gid in ("C-M1", "C-M2"):
            d1, d2, lbl = [abs(x) for x in d1], [abs(x) for x in d2], \
                f"|level({ev[0]})-level({ev[1]})|"
        else:
            lbl = f"level({ev[0]})-level({ev[1]})"
        r = positions.mann_whitney_u(d1, d2)
        return {"name": "Mann-Whitney U",
                "detail": f"{lbl} between {vax[0]}/{vax[1]}; n={r['n1']}/{r['n2']}",
                "p_value": r["p"], "how": _HOW["mannwhitney"],
                "null": f"H0: {vax[0]} and {vax[1]} draw {lbl} from the same "
                        "distribution (no cohort difference in rank-distance)"}
    r = positions.mann_whitney_u(_focal_ranks(index, ev, c1),  # multi triple, per event
                                 _focal_ranks(index, ev, c2))
    return {"name": "Mann-Whitney U (per event)",
            "detail": f"{ev[0]}'s within-triple rank between {vax[0]}/{vax[1]}; "
                      f"n={r['n1']}/{r['n2']}",
            "p_value": r["p"], "how": _HOW["mannwhitney"],
            "null": f"H0: {ev[0]}'s within-triple rank has the same distribution "
                    f"for {vax[0]} and {vax[1]}"}


def _null_hypothesis(mode, events, vaccines) -> str:
    """The categorical-test null H0 for a group's mode -- what the p-value tests
    against. Uses the core's real event/vaccine names for readability."""
    ev = list(events)
    a = ev[0] if ev else "A"
    b = ev[1] if len(ev) > 1 else "B"
    seq = " -> ".join(ev) if len(ev) >= 2 else a
    v1 = vaccines[0] if len(vaccines) > 0 else "v1"
    v2 = vaccines[1] if len(vaccines) > 1 else "v2"
    if mode in ("dir_bool", "dir_choice"):
        return f"H0: P({a} precedes {b}) = 0.5 (no directional preference among ordered reports)"
    if mode == "sym_bool_cooccurs":
        return f"H0: P({a} and {b} co-occur) = 0.5 (among reports containing both)"
    if mode == "seq_bool":
        return (f"H0: the {seq} ordering and the runner-up ordering are equally "
                "frequent (P = 0.5; no unique mode)")
    if mode == "modal_choice":
        return "H0: the 6 orderings are equally likely -- uniform (no modal ordering)"
    if mode == "consistency_bool":
        return "H0: the 6 orderings are equally likely -- uniform (no consistent ordering)"
    if mode == "first_bool":
        return (f"H0: {a} and the runner-up event are equally often the first "
                "(P = 0.5; no unique most-common first event)")
    if mode in ("first_choice", "last_choice"):
        which = "last" if mode == "last_choice" else "first"
        return f"H0: the 3 candidates are equally likely to be {which} -- uniform"
    if mode in ("multi_differ_precedes", "multi_dir_precedes"):
        return f"H0: P({a} precedes {b}) is equal for {v1} and {v2} (p1 = p2)"
    if mode in ("multi_differ_cooccurs", "multi_dir_cooccurs"):
        return f"H0: the {a}/{b} co-occurrence rate is equal for {v1} and {v2} (p1 = p2)"
    if mode in ("multi_differ_sequence", "multi_dir_sequence"):
        return f"H0: P(ordering = {seq}) is equal for {v1} and {v2} (p1 = p2)"
    if mode == "multi_dir_first":
        return f"H0: the first-event rate is equal for {v1} and {v2} (p1 = p2)"
    if mode in ("multi_same_first", "multi_differ_first"):
        return f"H0: {v1} and {v2} have the same first-event distribution (homogeneity)"
    if mode == "multi_same_modal_order":
        return f"H0: {v1} and {v2} have the same ordering distribution (homogeneity)"
    if mode.startswith("rep_"):
        return "H0: none -- single deterministic observation, no sampling distribution"
    return "H0: (unspecified)"


def _example_for(index, group, core) -> dict:
    ans = compute_answer(index, group.id, core.events,
                         vaccines=core.vaccines, report_id=core.report_id)
    fp = feasible_polarities(core)
    polarities = [p for p in ("supported", "refuted") if p in fp] or ["insufficient"]

    rendered = {}
    for pol in polarities:
        facts = realize(core, pol)
        # render every register's filled question + claim so the worked example
        # is self-contained (no need to cross-reference the template catalogue).
        rendered[pol] = {
            "gold_verdict": facts.gold_verdict,
            "registers": {
                reg: {
                    "question": render(group, reg, "question", facts.slot_values),
                    "claim": render(group, reg, "claim", facts.slot_values),
                }
                for reg in REGISTERS
            },
        }

    null_h = _null_hypothesis(ans.mode, core.events, core.vaccines)
    sg = core_significance(core)
    alt = sg.details.get("alternative") if sg.details else None
    test = None
    if ans.sig_test is not None:
        test = {
            "name": _TEST_LABEL.get(ans.sig_test, ans.sig_test),
            "p_value": ans.p_value,
            "significant": ans.significant,
            "how": _HOW.get(ans.sig_test, ""),
            "null": null_h,
            "alternative": alt,
        }
    pos = _position_test(index, group, core)

    # p-value vs gold-label MISMATCH flags (both types)
    #   type1: a definite gold verdict but the categorical test is not significant.
    #          Excludes PROP -- its gold is "value within 5pp", not a significance
    #          claim, so a non-significant PROP is not a mismatch.
    #   type2: structural (p computed on a different quantity than the gold names).
    #          RESOLVED: the sequence groups now compute on the modal ordering they
    #          actually name, so the test and the claim always match.
    categorical_definite = bool(test is not None and group.answer_type != "PROP"
                                and ans.verdict in ("supported", "refuted"))
    type1 = categorical_definite and not ans.significant
    type2 = False
    # Presented-example status: whether the showcased core's p-value corroborates
    # its gold label. "n/a" for PROP (tolerance claim) and report-level (no test).
    if categorical_definite:
        status = "successful" if ans.significant else "failed"
    else:
        status = "n/a"
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
        "gold_verdict": ans.verdict,
        "null": null_h,
        "test": test, "position_test": pos,
        "mismatch": {"type1": type1, "type2": type2},
        "status": status,
        "examples": rendered,
    }


def run(db_path: Path, out_dir: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    index = CorpusIndex.load(conn)
    groups = load_groups()
    entries = []
    overall = {"definite": 0, "fail": 0}
    by_family: dict[str, dict[str, int]] = {}
    for group in groups.values():
        viable = _group_viable(index, group)
        # grade every viable core once: its significance drives both the pick
        # (prefer a successful example) and the population fail-rate.
        graded = [(c, core_significance(c)) for c in viable]
        core = _pick_core(group, graded)
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
        # population gold-label-vs-significance over this group's cores that carry
        # a definite gold verdict AND an applicable categorical test.
        definite = [(c, s) for c, s in graded if _categorical_definite(group, c, s)]
        fail = sum(1 for _, s in definite if not s.significant)
        e["definite_cores"] = len(definite)
        e["fail_cores"] = fail
        e["fail_rate"] = (fail / len(definite)) if definite else None
        # concrete fail cases: definite-gold cores the test does NOT corroborate,
        # laddered by p (closest-to-significant -> no-effect) so >=10 show the range.
        fails = sorted((cs for cs in definite if not cs[1].significant),
                       key=lambda cs: (cs[1].p_value if cs[1].p_value is not None else 1.0))
        e["fail_examples"] = [_fail_case(c, s) for c, s in _ladder(fails, 10)]
        if fails:
            ns = sorted(c.n for c, _ in fails if c.n is not None)
            ps = sorted(s.p_value for _, s in fails if s.p_value is not None)
            e["fail_summary"] = {"count": len(fails),
                                 "median_n": ns[len(ns) // 2] if ns else None,
                                 "median_p": round(ps[len(ps) // 2], 4) if ps else None}
        else:
            e["fail_summary"] = {"count": 0, "median_n": None, "median_p": None}
        overall["definite"] += len(definite)
        overall["fail"] += fail
        # keyed by primitive so co-occurs shows separately from precedes
        fam = by_family.setdefault(group.primitive, {"definite": 0, "fail": 0})
        fam["definite"] += len(definite)
        fam["fail"] += fail
        entries.append(e)
    conn.close()

    stats = {"overall": overall, "by_family": by_family}
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "examples.jsonl", "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    md = _render_md(entries, stats) + _failcases_md(entries)
    (out_dir / "examples.md").write_text(md, encoding="utf-8")
    tex = _render_tex(entries, stats) + _failcases_tex(entries)
    (out_dir / "examples.tex").write_text(tex, encoding="utf-8")
    # committed, directly-readable review copy under docs/reference/
    ref = _REPO / "docs" / "reference" / "Worked_Examples.md"
    ref.write_text(md, encoding="utf-8")
    return {"entries": entries, "out_dir": str(out_dir), "ref": str(ref),
            "stats": stats}


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


_METHOD_NAME = {
    "binom_exact": "Binomial exact",
    "modal_runner": "Modal-vs-runner-up binomial", "fisher_exact": "Fisher exact",
    "multinomial_gof_exact": "Multinomial GOF (exact)",
    "multinomial_gof_asymptotic": "Multinomial GOF (chi-square)",
    "homogeneity_exact": "Fisher-Freeman-Halton",
    "homogeneity_asymptotic": "Homogeneity (chi-square)",
    "wilcoxon": "Wilcoxon signed-rank", "mannwhitney": "Mann-Whitney U",
    "friedman": "Friedman", "kendall": "Kendall's W",
}
_METHOD_ORDER = list(_METHOD_NAME)


def _mismatch_tags(e) -> list:
    m = e.get("mismatch", {})
    tags = []
    if m.get("type1"):
        tags.append("type1 (gold set but the test is not significant)")
    if m.get("type2"):
        tags.append("type2 (p computed on the canonical ordering; gold = the modal)")
    return tags


_FAMILY_ORDER = [("precedes", "pairwise-precedes"), ("co_occurs", "co-occurs"),
                 ("sequence", "sequence"), ("first_last", "first/last")]


def _pct(num, den) -> str:
    return "n/a" if not den else f"{num}/{den} ({num / den:.1%})"


def _presented_failrate(entries):
    """(failed, categorical) presented-example counts: how many showcased
    examples still fail (no successful core existed) out of those with a test."""
    cat = [e for e in entries if not e.get("note") and e.get("status") in
           ("successful", "failed")]
    failed = [e for e in cat if e["status"] == "failed"]
    return failed, cat


def _render_md(entries, stats) -> str:
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

    # gold-label vs significance-test fail rate
    ov = stats["overall"]
    failed_pres, cat_pres = _presented_failrate(entries)
    out += ["## Gold-label vs significance-test fail rate", "",
            "For every viable core with a definite gold verdict "
            "(supported/refuted) and an applicable categorical test (PROP and "
            "report-level excluded), we check whether the test is significant at "
            "alpha=0.05. A **fail** is a definite gold label the test does NOT "
            "corroborate. This is the population rate over ALL such cores.", "",
            f"- **Overall population**: {_pct(ov['fail'], ov['definite'])} of "
            "definite-verdict categorical cores are not significant.", ""]
    out += ["| family | definite cores | failed | fail rate |", "|---|--:|--:|--:|"]
    for key, label in _FAMILY_ORDER:
        f = stats["by_family"].get(key)
        if f:
            out.append(f"| {label} | {f['definite']} | {f['fail']} "
                       f"| {_pct(f['fail'], f['definite'])} |")
    out += ["",
            "For the worked examples below we search each template's cores for a "
            "**successful** example (definite gold + significant test) to "
            "showcase; only when none exists do we present a failed one.", "",
            f"- **Presented examples**: {_pct(len(failed_pres), len(cat_pres))} "
            "of testable templates still show a failed example "
            "(no successful core exists)"
            + (f": {', '.join(e['group_id'] for e in failed_pres)}."
               if failed_pres else "."), "",
            "| template | definite cores | failed | fail rate | presented |",
            "|---|--:|--:|--:|:--:|"]
    for e in entries:
        if e.get("note"):
            continue
        dc = e.get("definite_cores", 0)
        out.append(f"| {e['group_id']} | {dc} | {e.get('fail_cores', 0)} "
                   f"| {_pct(e.get('fail_cores', 0), dc)} | {e.get('status', 'n/a')} |")
    out.append("")

    # mismatch summary (rendered in red in the LaTeX findings)
    flagged = [e for e in entries if not e.get("note")
               and (e["mismatch"]["type1"] or e["mismatch"]["type2"])]
    out += ["## P-value vs gold-label mismatches", "",
            "Templates whose worked example has a p-value that does not match the "
            "gold label (flagged **red** in the LaTeX findings). "
            "**type1** = a definite gold verdict but the categorical test is not "
            "significant. **type2** = structural: the p is computed on a different "
            "quantity than the gold names.", ""]
    if flagged:
        out.append("| template | type1 | type2 |")
        out.append("|---|:--:|:--:|")
        for e in flagged:
            out.append(f"| {e['group_id']} "
                       f"| {'yes' if e['mismatch']['type1'] else ''} "
                       f"| {'yes' if e['mismatch']['type2'] else ''} |")
    else:
        out.append("_none_")
    out.append("")

    for e in entries:
        if e.get("note"):
            out += [f"## {e['group_id']}  --  {e['note']}", ""]
            continue
        out.append(f"## {e['group_id']}  ({e['family']}, {e['level']}, {e['answer_type']})")
        _status = e.get("status", "n/a")
        _sym = {"successful": "✓ SUCCESSFUL", "failed": "✗ FAILED",
                "n/a": "— (no significance test: PROP / report-level)"}[_status]
        out.append(f"- **Presented example**: {_sym} "
                   f"(gold-vs-significance over this template's cores: "
                   f"{_pct(e.get('fail_cores', 0), e.get('definite_cores', 0))} fail)")
        out.append(f"- **Qualified cores**: {e['viable_cores']} viable | "
                   f"{e['supported_capable']} supported-capable (true cases) | "
                   f"{e['refuted_capable']} refuted-capable")
        out.append(f"- **Core**: events {e['events']}, cohort {_cohort_str(e)}")
        out.append(f"- **Conditioned counts**: {_counts_str(e)}")
        tags = _mismatch_tags(e)
        if tags:
            out.append(f"- **⚠ P-VALUE vs GOLD MISMATCH** (red in the LaTeX "
                       f"findings): {'; '.join(tags)}")
        if e["test"]:
            t = e["test"]
            pv = "n/a" if t["p_value"] is None else f"{t['p_value']:.4g}"
            out.append(f"- **Categorical test**: {t['name']}{_side_label(t.get('alternative'))}, "
                       f"p = {pv} "
                       f"({'significant' if t['significant'] else 'not significant'})")
            out.append(f"    - *{t['null']}*")
            out.append(f"    - *how p is computed*: {t['how']}")
        else:
            out.append("- **Categorical test**: none (report-level: single "
                       "observation, no sampling distribution)")
            out.append(f"    - *{e['null']}*")
        if e["position_test"]:
            pt = e["position_test"]
            pv = "n/a" if pt["p_value"] is None else f"{pt['p_value']:.4g}"
            out.append(f"- **Position-based test**: {pt['name']} "
                       f"({pt['detail']}), p = {pv}")
            out.append(f"    - *{pt['null']}*")
            out.append(f"    - *how p is computed*: {pt['how']}")
        if e["ci"]:
            out.append(f"- **95% CI**: {e['ci']}"
                       + (f", effect size {e['effect_size']}" if e["effect_size"] is not None else ""))
        if e["gold_answer"] is not None:
            out.append(f"- **Options**: {e['options']}  ->  correct: **{e['gold_answer']}**")
        for pol, r in e["examples"].items():
            out.append(f"- **{r['gold_verdict'].upper()}** example "
                       f"(filled, all registers):")
            for reg in REGISTERS:
                rv = r["registers"][reg]
                out.append(f"    - **{reg.capitalize()}**")
                out.append(f"        - Q: {rv['question']}")
                out.append(f"        - Claim: {rv['claim']}")
        out.append("")

    out += ["## Statistical methods (how each p-value is computed)", ""]
    for key in _METHOD_ORDER:
        out.append(f"- **{_METHOD_NAME[key]}**: {_HOW[key]}")
    out.append("")
    return "\n".join(out) + "\n"


def _esc(s) -> str:
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("_", r"\_"), ("#", r"\#"), ("{", r"\{"), ("}", r"\}"),
                 ("→", r"$\rightarrow$ ")]:  # arrow escaped last (adds a backslash)
        s = str(s).replace(a, b)
    return s


def _render_tex(entries, stats) -> str:
    flagged = [e for e in entries if not e.get("note")
               and (e["mismatch"]["type1"] or e["mismatch"]["type2"])]
    out = [r"\section{Worked Examples per Template (computed from MedTempo)}",
           r"Each template group is shown with one real viable core: the "
           r"conditioned counts, the categorical and position-based significance "
           r"tests computed on the data, and the gold verdict. Where a "
           r"\emph{successful} core exists (a definite gold verdict the "
           r"categorical test corroborates), it is the one shown; otherwise the "
           r"failed example is shown as-is.", ""]

    # findings: gold-label vs significance-test fail rate
    ov = stats["overall"]
    failed_pres, cat_pres = _presented_failrate(entries)
    out.append(r"\subsection*{Gold-label vs significance-test fail rate}")
    out.append(r"Over every viable core with a definite gold verdict and an "
               r"applicable categorical test (PROP and report-level excluded), "
               r"the \textbf{fail rate} is the share whose test is not "
               r"significant at $\alpha=0.05$ --- a gold label the test does not "
               r"corroborate. Population: \textbf{" + _esc(_pct(ov["fail"], ov["definite"]))
               + r"} of definite-verdict categorical cores. Presented examples: "
               + _esc(_pct(len(failed_pres), len(cat_pres)))
               + r" of testable templates still show a failed example"
               + (r" (\textcolor{red}{" + _esc(", ".join(e["group_id"] for e in failed_pres))
                  + r"})" if failed_pres else r"") + r".")
    out.append(r"\begin{itemize}")
    for key, label in _FAMILY_ORDER:
        f = stats["by_family"].get(key)
        if f:
            out.append(r"\item \textbf{" + _esc(label) + r":} "
                       + _esc(_pct(f["fail"], f["definite"])) + r" fail")
    out.append(r"\end{itemize}")
    out.append("")

    # findings: p-value vs gold-label mismatches (RED)
    out.append(r"\subsection*{p-value vs gold-label mismatches}")
    out.append(r"Templates whose worked example has a p-value that does not "
               r"corroborate the gold label. \textbf{type1}: a definite gold "
               r"verdict but the categorical test is not significant. "
               r"\textbf{type2}: structural --- the p is computed on a different "
               r"quantity than the gold names (e.g.\ \texttt{seq\_bool} tests the "
               r"canonical ordering while the gold names the modal).")
    if flagged:
        out.append(r"\begin{itemize}")
        for e in flagged:
            short = [k for k in ("type1", "type2") if e["mismatch"][k]]
            out.append(r"\item \textcolor{red}{\textbf{" + _esc(e["group_id"])
                       + "}: " + _esc(", ".join(short)) + "}")
        out.append(r"\end{itemize}")
    else:
        out.append(r"None.")
    out.append("")

    for e in entries:
        out.append(r"\subsection*{" + _esc(e["group_id"]) + "}")
        if e.get("note"):
            out.append(_esc(e["note"]))
            continue
        flag = e["mismatch"]["type1"] or e["mismatch"]["type2"]
        _status = e.get("status", "n/a")
        _label = {"successful": r"\textbf{Presented example:} successful "
                                r"(p-value corroborates the gold label)",
                  "failed": r"\textcolor{red}{\textbf{Presented example:} failed "
                            r"(no successful core exists; gold set but the test "
                            r"is not significant)}",
                  "n/a": r"\textbf{Presented example:} n/a "
                         r"(PROP tolerance / report-level; no significance test)"}[_status]
        out.append(_label + r" \\")
        if flag:
            short = [k for k in ("type1", "type2") if e["mismatch"][k]]
            out.append(r"\textcolor{red}{\textbf{p-value vs gold mismatch: "
                       + _esc(", ".join(short)) + r"}} \\")
        out.append(r"\textbf{Qualified cores:} " + f"{e['viable_cores']} viable, "
                   f"{e['supported_capable']} supported-capable, "
                   f"{e['refuted_capable']} refuted-capable" + r". \\")
        out.append(r"\textbf{Core:} events " + _esc(", ".join(e["events"]))
                   + r"; cohort " + _esc(_cohort_str(e)) + r". \\")
        out.append(r"\textbf{Counts:} " + _esc(_counts_str(e)) + r". \\")
        if e["test"]:
            t = e["test"]
            pv = "n/a" if t["p_value"] is None else f"{t['p_value']:.4g}"
            sig = "significant" if t["significant"] else "not significant"
            line = (r"\textbf{Categorical test:} " + _esc(t["name"])
                    + _esc(_side_label(t.get("alternative")))
                    + f", $p = {pv}$ ({sig})")
            out.append((r"\textcolor{red}{" + line + "}" if flag else line) + r". \\")
            out.append(r"\emph{" + _esc(t["null"]) + r"} \\")
            out.append(r"\emph{how:} " + _esc(t["how"]) + r". \\")
        else:
            out.append(r"\textbf{Categorical test:} none (report-level). "
                       + r"\emph{" + _esc(e["null"]) + r"} \\")
        if e["position_test"]:
            pt = e["position_test"]
            pv = "n/a" if pt["p_value"] is None else f"{pt['p_value']:.4g}"
            out.append(r"\textbf{Position-based test:} " + _esc(pt["name"]) + " ("
                       + _esc(pt["detail"]) + f"), $p = {pv}$" + r". \\")
            out.append(r"\emph{" + _esc(pt["null"]) + r"} \\")
            out.append(r"\emph{how:} " + _esc(pt["how"]) + r". \\")
        for pol, r in e["examples"].items():
            out.append(r"\textbf{" + _esc(r["gold_verdict"].capitalize())
                       + r" example} (filled, all registers): \\")
            out.append(r"\begin{tabularx}{\linewidth}{@{}l L L@{}}")
            out.append(r"\toprule")
            out.append(r"\textbf{Register} & \textbf{Question} & \textbf{Claim} \\")
            out.append(r"\midrule")
            for reg in REGISTERS:
                rv = r["registers"][reg]
                out.append(_esc(reg.capitalize()) + " & " + _esc(rv["question"])
                           + " & " + _esc(rv["claim"]) + r" \\")
            out.append(r"\bottomrule")
            out.append(r"\end{tabularx}")
            out.append(r"\vspace{3pt}")
        out.append("")

    out.append(r"\subsection*{Statistical methods (how each p-value is computed)}")
    out.append(r"\begin{itemize}")
    for key in _METHOD_ORDER:
        out.append(r"\item \textbf{" + _esc(_METHOD_NAME[key]) + ":} "
                   + _esc(_HOW[key]))
    out.append(r"\end{itemize}")
    return "\n".join(out) + "\n"


_FAILCASE_INTRO_MD = (
    "For each testable group, up to 10 failing cores -- a **definite** gold verdict "
    "(supported/refuted) that the categorical test does **not** corroborate at "
    "alpha=0.05 -- laddered from closest-to-significant (lowest p) to no-effect "
    "(highest p) so the range of failure modes is visible. *Processed* = the "
    "group's definite categorical cores; *failed* = those the test can't "
    "corroborate. Report-level and PROP groups carry no categorical test, so they "
    "process 0 cores and have no fail cases.")


def _failcases_md(entries) -> str:
    out = ["", "## Fail-case examples per template (why the gold label is not "
           "significant)", "", _FAILCASE_INTRO_MD, ""]
    for e in entries:
        if e.get("note"):
            continue
        dc = e.get("definite_cores", 0)
        if not e.get("fail_examples"):
            out.append(f"### {e['group_id']} — 0 processed "
                       f"(no categorical test: {e['answer_type']}/{e['level']})")
            out.append("")
            continue
        fs = e["fail_summary"]
        out.append(f"### {e['group_id']} — {dc} processed, {e['fail_cores']} failed "
                   f"({_pct(e['fail_cores'], dc)}); median n {fs['median_n']}, "
                   f"median p {fs['median_p']}")
        out.append(f"*Tested against — {e['null']}*")
        out.append("")
        out.append("| # | events | cohort | counts (k/n) | p | why it failed |")
        out.append("|--:|---|---|---|--:|---|")
        for i, fc in enumerate(e["fail_examples"], 1):
            out.append(f"| {i} | {', '.join(fc['events'])} | {_fc_cohort(fc)} "
                       f"| {_fc_counts(fc)} | {_pv(fc['p'])} | {fc['reason']} |")
        out.append("")
    return "\n".join(out) + "\n"


def _failcases_tex(entries) -> str:
    out = [r"\subsection*{Fail-case examples per template (why the gold label is "
           r"not significant)}",
           r"For each testable group, up to 10 failing cores --- a definite gold "
           r"verdict the categorical test does not corroborate at $\alpha=0.05$ --- "
           r"laddered from closest-to-significant to no-effect. \emph{Processed} = "
           r"the group's definite categorical cores; \emph{failed} = those the test "
           r"cannot corroborate.", ""]
    for e in entries:
        if e.get("note") or not e.get("fail_examples"):
            continue
        fs = e["fail_summary"]
        out.append(r"\paragraph{" + _esc(e["group_id"]) + "} "
                   + f"{e['definite_cores']} processed, {e['fail_cores']} failed "
                   + f"({_esc(_pct(e['fail_cores'], e['definite_cores']))}); "
                   + f"median n {fs['median_n']}, median p {fs['median_p']}. "
                   + r"\emph{Tested against --- " + _esc(e["null"]) + r"} \\")
        out.append(r"\begin{longtable}{@{}r p{3.9cm} p{2.5cm} l l p{4.4cm}@{}}")
        out.append(r"\toprule")
        out.append(r"\# & Events & Cohort & Counts & $p$ & Why it failed \\")
        out.append(r"\midrule \endhead")
        for i, fc in enumerate(e["fail_examples"], 1):
            out.append(f"{i} & " + _esc(", ".join(fc["events"])) + " & "
                       + _esc(_fc_cohort(fc)) + " & " + _esc(_fc_counts(fc)) + " & "
                       + _esc(_pv(fc["p"])) + " & " + _esc(fc["reason"]) + r" \\")
        out.append(r"\bottomrule")
        out.append(r"\end{longtable}")
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
