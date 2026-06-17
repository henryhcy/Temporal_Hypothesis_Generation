"""Verdict balancing, frequency banding, and per-group selection (Part B).

Implements the provisional pilot sampling numbers (decisions.md):
- target-with-availability-cap: target T per group; take all if under-target.
- verdict balance 45/45/10 supported/refuted/insufficient, insufficient CAPPED.
- refuted instances are produced by realizing a flippable core in its refuted
  orientation (decisions.md "flip a supported core").
- quantile frequency bands (by gold_n) with light stratified draw.

All randomness is seeded for reproducibility.
"""

from __future__ import annotations

import random
from collections import defaultdict, deque
from dataclasses import dataclass, field

from temporal_hypo.generation.cores import ViableCore, feasible_polarities

# Provisional targets (decisions.md "Pilot phase").
T_DEFAULT = 100
SUPPORTED_FRAC = 0.45
REFUTED_FRAC = 0.45
INSUFFICIENT_FRAC = 0.10


@dataclass
class GroupSelection:
    group_id: str
    chosen: list[tuple[ViableCore, str, str]]  # (core, polarity, band)
    targets: dict[str, int]
    counts: dict[str, int]
    under_target: dict[str, bool]
    pool_sizes: dict[str, int]


def _band_cutoffs(values: list[int]) -> tuple[float, float]:
    """Tertile cutoffs on gold_n (33rd, 67th percentile)."""
    if not values:
        return (0.0, 0.0)
    s = sorted(values)

    def pct(q: float) -> float:
        if len(s) == 1:
            return float(s[0])
        pos = q * (len(s) - 1)
        lo, hi = int(pos), min(int(pos) + 1, len(s) - 1)
        frac = pos - lo
        return s[lo] * (1 - frac) + s[hi] * frac

    return (pct(1 / 3), pct(2 / 3))


def assign_bands(cores: list[ViableCore]) -> dict[int, str]:
    """Map id(core) -> frequency band ('low'/'medium'/'high'/'na')."""
    ns = [c.n for c in cores if c.n is not None]
    lo_cut, hi_cut = _band_cutoffs(ns)
    band: dict[int, str] = {}
    for c in cores:
        if c.n is None:
            band[id(c)] = "na"
        elif c.n <= lo_cut:
            band[id(c)] = "low"
        elif c.n <= hi_cut:
            band[id(c)] = "medium"
        else:
            band[id(c)] = "high"
    return band


def _stratified_draw(
    pool: list[ViableCore], count: int, band: dict[int, str], rng: random.Random
) -> list[ViableCore]:
    """Draw up to `count` cores, round-robin across bands for spread."""
    if count <= 0 or not pool:
        return []
    buckets: dict[str, list[ViableCore]] = defaultdict(list)
    for c in pool:
        buckets[band[id(c)]].append(c)
    queues = []
    for b in sorted(buckets):
        items = buckets[b]
        rng.shuffle(items)
        queues.append(deque(items))
    result: list[ViableCore] = []
    while len(result) < count and any(queues):
        for q in queues:
            if len(result) >= count:
                break
            if q:
                result.append(q.popleft())
    return result


def balance_group(
    cores: list[ViableCore],
    group_id: str,
    *,
    t: int = T_DEFAULT,
    seed: int = 0,
) -> GroupSelection:
    """Select (core, polarity) pairs to approximate the 45/45/10 balance."""
    rng = random.Random(seed)
    band = assign_bands(cores)

    feas = {id(c): feasible_polarities(c) for c in cores}
    supported_pool = [c for c in cores if "supported" in feas[id(c)]]
    refuted_pool = [c for c in cores if "refuted" in feas[id(c)]]
    insufficient_pool = [c for c in cores if feas[id(c)] == {"insufficient"}]

    n_sup = round(t * SUPPORTED_FRAC)
    n_ref = round(t * REFUTED_FRAC)
    n_insuf = t - n_sup - n_ref  # ~10; the CAP on insufficient

    chosen: list[tuple[ViableCore, str, str]] = []

    sup_sel = _stratified_draw(supported_pool, n_sup, band, rng)
    used = {id(c) for c in sup_sel}
    for c in sup_sel:
        chosen.append((c, "supported", band[id(c)]))

    # refuted: prefer cores not already used as supported, then flip used ones
    ref_fresh = [c for c in refuted_pool if id(c) not in used]
    ref_sel = _stratified_draw(ref_fresh, n_ref, band, rng)
    if len(ref_sel) < n_ref:
        remaining = n_ref - len(ref_sel)
        flippable_used = [c for c in sup_sel if "refuted" in feas[id(c)]]
        ref_sel += _stratified_draw(flippable_used, remaining, band, rng)
    for c in ref_sel:
        chosen.append((c, "refuted", band[id(c)]))

    insuf_sel = _stratified_draw(insufficient_pool, n_insuf, band, rng)
    for c in insuf_sel:
        chosen.append((c, "insufficient", band[id(c)]))

    counts = {
        "supported": len(sup_sel),
        "refuted": len(ref_sel),
        "insufficient": len(insuf_sel),
    }
    targets = {"supported": n_sup, "refuted": n_ref, "insufficient": n_insuf}
    under = {k: counts[k] < targets[k] for k in targets}
    pool_sizes = {
        "supported": len(supported_pool),
        "refuted": len(refuted_pool),
        "insufficient": len(insufficient_pool),
    }
    return GroupSelection(
        group_id=group_id, chosen=chosen, targets=targets, counts=counts,
        under_target=under, pool_sizes=pool_sizes,
    )
