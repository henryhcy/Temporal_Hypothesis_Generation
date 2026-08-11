"""Verdict balancing, frequency banding, and per-group selection (Part B).

EQUAL THIRDS per group (decisions.md 2026-07-28, per-group confirmed 08-11),
replacing the provisional 45/45/10:

- Each group targets ``S // 2`` supported, the same number refuted, and the same
  number insufficient -- so the budget is ~1.5*S and the group is internally
  balanced. Per-group rather than benchmark-wide because template wording is fixed
  per group, which makes a skewed group a directly exploitable shortcut.
- **One claim per decisive core.** A core is never used as both supported and
  refuted; that would ship the A->B / B->A mirror of a single case with opposite
  labels.
- **Minimum re-orientation.** Each class is drawn from the cores whose data already
  falls on that side before borrowing from the other side. For C-V1/C-V3 that
  minimises negation (149 of 378 rather than ~197); elsewhere it minimises slot
  flips.
- **The insufficient third spreads across its sub-types** (underpowered / sparse /
  not_locatable) as evenly as supply allows: allocation is round-robin one at a
  time, so a sub-type that runs out simply stops receiving and the remainder spills
  to the others.
- quantile frequency bands (by gold_n) with light stratified draw.

All randomness is seeded for reproducibility.
"""

from __future__ import annotations

import random
from collections import defaultdict, deque
from dataclasses import dataclass, field

from temporal_hypo.generation.cores import (
    ViableCore,
    cohort_decision,
    feasible_polarities,
)

# Retired 2026-08-11: the provisional 45/45/10 balance and the T=100 per-group
# target. The budget is now derived from the group's own decisive supply (~1.5*S),
# because S is a property of the corpus and ranges from 4 to 378 across groups.
T_DEFAULT = 100          # retained only as an optional hard cap
CLASSES = ("supported", "refuted", "insufficient")


@dataclass
class GroupSelection:
    group_id: str
    chosen: list[tuple[ViableCore, str, str]]  # (core, polarity, band)
    targets: dict[str, int]
    counts: dict[str, int]
    under_target: dict[str, bool]
    pool_sizes: dict[str, int]
    # insufficient composition: how the third split across its sub-types
    subtype_counts: dict[str, int] = field(default_factory=dict)
    subtype_pools: dict[str, int] = field(default_factory=dict)
    # how many chosen instances will need re-orientation (negation / slot flip)
    reoriented: int = 0
    S: int = 0


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


def _water_fill(capacities: dict[str, int], total: int) -> dict[str, int]:
    """Spread ``total`` as evenly as possible over pools with the given capacities.

    One unit at a time in a fixed rotation: every pool gets an equal share until it
    is exhausted, and whatever it cannot take spills to the others. That is exactly
    "spread evenly across sub-types; if a type runs short, use it all and make up
    the difference from the rest".
    """
    alloc = {k: 0 for k in capacities}
    remaining = total
    while remaining > 0:
        active = [k for k in sorted(capacities) if alloc[k] < capacities[k]]
        if not active:
            break
        for k in active:
            if remaining == 0:
                break
            alloc[k] += 1
            remaining -= 1
    return alloc


def balance_group(
    cores: list[ViableCore],
    group_id: str,
    group=None,
    *,
    t: int | None = None,
    seed: int = 0,
) -> GroupSelection:
    """Select (core, polarity) pairs for an EQUAL-THIRDS group (decisions.md).

    ``group`` is the template Group; passing it lets ``feasible_polarities`` see
    whether the group has negated wording, which is what allows a non-slot-
    orientable group (C-V1/C-V3) to supply both classes. ``t`` optionally caps the
    per-class target; by default the target is the group's own ``S // 2``.
    """
    rng = random.Random(seed)
    band = assign_bands(cores)

    feas = {id(c): feasible_polarities(c, group) for c in cores}
    decisive = [c for c in cores if feas[id(c)] != {"insufficient"}]
    insufficient_pool = [c for c in cores if feas[id(c)] == {"insufficient"}]

    # Which class does each decisive core fall on WITHOUT re-orientation? Drawing
    # from these first is what keeps negation and slot flips to a minimum.
    natural: dict[int, str] = {}
    for c in decisive:
        d = cohort_decision(c) if c.report_id is None else None
        nat = d.verdict if d is not None else c.natural_verdict
        natural[id(c)] = nat if nat in ("supported", "refuted") else "supported"

    S = len(decisive)
    per_class = S // 2
    if t is not None:
        per_class = min(per_class, t // len(CLASSES))
    targets = {k: per_class for k in CLASSES}

    chosen: list[tuple[ViableCore, str, str]] = []
    used: set[int] = set()
    reoriented = 0

    def take(want: str, count: int) -> int:
        """Fill `count` instances of class `want`, natural-first. Returns the count."""
        nonlocal reoriented
        got = 0
        for stage in ("natural", "reorient"):
            if got >= count:
                break
            pool = [c for c in decisive
                    if id(c) not in used
                    and want in feas[id(c)]
                    and ((natural[id(c)] == want) if stage == "natural"
                         else (natural[id(c)] != want))]
            picked = _stratified_draw(pool, count - got, band, rng)
            for c in picked:
                used.add(id(c))
                chosen.append((c, want, band[id(c)]))
                if stage == "reorient":
                    reoriented += 1
            got += len(picked)
        return got

    n_sup = take("supported", per_class)
    n_ref = take("refuted", per_class)

    # the insufficient third, spread over its sub-types
    by_sub: dict[str, list[ViableCore]] = defaultdict(list)
    for c in insufficient_pool:
        d = cohort_decision(c) if c.report_id is None else None
        by_sub[(d.subtype if d and d.subtype else "unknown")].append(c)
    sub_alloc = _water_fill({k: len(v) for k, v in by_sub.items()}, per_class)
    n_insuf = 0
    sub_counts: dict[str, int] = {}
    for sub, want in sorted(sub_alloc.items()):
        picked = _stratified_draw(by_sub[sub], want, band, rng)
        sub_counts[sub] = len(picked)
        n_insuf += len(picked)
        for c in picked:
            chosen.append((c, "insufficient", band[id(c)]))

    counts = {"supported": n_sup, "refuted": n_ref, "insufficient": n_insuf}
    return GroupSelection(
        group_id=group_id, chosen=chosen, targets=targets, counts=counts,
        under_target={k: counts[k] < targets[k] for k in CLASSES},
        pool_sizes={"supported": sum(1 for c in decisive if "supported" in feas[id(c)]),
                    "refuted": sum(1 for c in decisive if "refuted" in feas[id(c)]),
                    "insufficient": len(insufficient_pool)},
        subtype_counts=sub_counts,
        subtype_pools={k: len(v) for k, v in by_sub.items()},
        reoriented=reoriented,
        S=S,
    )
