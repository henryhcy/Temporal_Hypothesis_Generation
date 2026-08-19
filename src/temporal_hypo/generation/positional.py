"""Descriptive positional (rank) statistics for released answer records.

Decisions.md 2026-08-14 batch 1, item 5: positional statistics ship on the
ANSWER side wherever they are computable, marked descriptive-only. They never
drive a verdict -- §6 lever 2 stays retired, because the Mann-Whitney normal
approximation is anti-conservative on tie-heavy small-integer ordinal data
(~11% decisive under shuffled labels against a nominal 5%). A consumer wanting
a second opinion on "how much earlier" gets these numbers; a consumer wanting
a LABEL must use the exact-test fields, which is why every block carries
``role: descriptive_only`` and its approximation ``method`` explicitly.

Orientation follows the instance's asserted claim (``facts.events_assigned``,
``facts.vaccines_assigned``), matching ``answers.oriented_significance``: for a
pair claim, ``median_gap < 0`` means the FIRST named event sits earlier. The
rank track conditions LESS than the categorical track on purpose (co-exist is
kept as d = 0; non-orderable triples are kept as tied ranks), so its n can
exceed ``gold_n`` -- that difference is the track's original selling point and
is worth surfacing, not hiding.
"""

from __future__ import annotations

import statistics as st

from temporal_hypo.core import positions
from temporal_hypo.generation import corpus


_PAIR_MODES = {"dir_bool", "dir_choice", "sym_bool_cooccurs", "cooc_modal_bool"}
_TRIPLE_MODES = {"seq_bool", "modal_choice",
                 "first_choice", "last_choice", "first_bool"}


def _rounded(d: dict, keys=("stat", "p", "U", "Q", "W")) -> dict:
    return {k: (round(v, 6) if isinstance(v, float) else v)
            for k, v in d.items()}


def positional_stats(index, facts) -> dict | None:
    """The descriptive rank-statistics block for one realized instance.

    Returns None where no positional statistic is defined (report level: a
    single observation has no distribution) or where the conditioned data is
    empty (the deliberately false not_locatable combinations).
    """
    core = facts.core
    if index is None or core.report_id is not None:
        return None
    m = core.mode
    ev = list(facts.events_assigned)

    if m in _PAIR_MODES:
        d = corpus.pair_distances(index, ev[0], ev[1], core.cohort_ids)
        if not d:
            return None
        r = positions.wilcoxon_signed_rank(d)
        return {
            "role": "descriptive_only",
            "test": "wilcoxon_signed_rank",
            "method": r["method"],           # 'exact' only at n<=15
            "n_present": len(d),             # co-exist KEPT (d=0), unlike gold_n
            "n_nonzero": r["n"],
            "stat": round(float(r["stat"]), 4),
            "p": round(float(r["p"]), 6),
            "median_gap": st.median(d),
            "mean_gap": round(st.mean(d), 4),
        }

    if m in _TRIPLE_MODES:
        blocks = corpus.triple_positions(index, ev, core.cohort_ids)
        if len(blocks) < 2:
            return None
        fr = positions.friedman(blocks)
        kw = positions.kendalls_w(blocks)
        return {
            "role": "descriptive_only",
            "test": "friedman",
            "method": fr["method"],          # chi-square approximation
            "n_present": len(blocks),        # non-orderable triples KEPT as ties
            "Q": round(float(fr["Q"]), 4),
            "df": fr["df"],
            "p": round(float(fr["p"]), 6),
            "kendalls_w": round(float(kw["W"]), 4),
        }

    if m in ("antecedent_bool", "pairpair_bool"):
        # Two within-cohort arms: per-arm signed-rank on the level gaps, plus
        # Mann-Whitney between the two arms' gap distributions -- "is the A->B
        # gap pattern different from the C->(B|D) one", descriptive only.
        arm2 = (ev[2], ev[1]) if m == "antecedent_bool" else (ev[2], ev[3])
        d1 = corpus.pair_distances(index, ev[0], ev[1], core.cohort_ids)
        d2 = corpus.pair_distances(index, arm2[0], arm2[1], core.cohort_ids)
        if not d1 or not d2:
            return None
        mw = positions.mann_whitney_u(d1, d2)
        return {
            "role": "descriptive_only",
            "test": "mann_whitney_u_arms",
            "method": mw["method"],          # normal approx: anti-conservative
            "n1_present": len(d1),
            "n2_present": len(d2),
            "U": round(float(mw["U"]), 4),
            "p": round(float(mw["p"]), 6),
            "median_gap_1": st.median(d1),
            "median_gap_2": st.median(d2),
        }

    if m == "multi_dir_precedes":
        v1, v2 = facts.vaccines_assigned
        d1 = corpus.pair_distances(index, ev[0], ev[1], index.cohort(v1))
        d2 = corpus.pair_distances(index, ev[0], ev[1], index.cohort(v2))
        if not d1 or not d2:
            return None
        r = positions.mann_whitney_u(d1, d2)
        return {
            "role": "descriptive_only",
            "test": "mann_whitney_u",
            "method": r["method"],           # normal approx: anti-conservative
            "n1_present": len(d1),
            "n2_present": len(d2),
            "U": round(float(r["U"]), 4),
            "p": round(float(r["p"]), 6),
            "median_gap_1": st.median(d1),
            "median_gap_2": st.median(d2),
        }

    return None
