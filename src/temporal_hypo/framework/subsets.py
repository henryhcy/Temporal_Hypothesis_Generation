"""Evaluation subsets of a release: ``eval_core``, the invariance subset, few-shot pools.

What: seeded, deterministic selections of INSTANCE ids (not question rows) from
a loaded ``Release``, plus the tiny JSON format they are persisted in
(``{"ids": [...], "meta": {...}}``).

Why the selection rules are what they are:

- ``eval_core`` caps each group (default 90) and balances the cap across the
  gold verdicts -- thirds for the cohort tiers, halves at the report tier which
  has no ``insufficient`` class -- so a group's score is not dominated by its
  natural verdict skew. Balance wins over volume: a class with fewer instances
  than its quota is not topped up from the other classes.
- Mirror pairs (same ``derived_from_core_id``: the supported claim and its
  refuted mirror) and twins (same ``fact_id``: the identical statistic posed
  under another group, e.g. P-V1/P-V3) are NEVER split. Drawing one instance
  draws its whole fact component, even past the cap, because pair- and
  twin-consistency metrics need both members and a split would leak the fact
  across any later train/test boundary (CLAUDE.md; decisions.md 2026-08-14).
  Since a mirror pair shares its core it also shares its ``fact_id``, so the
  component closure is taken over BOTH keys with a union-find rather than
  assuming that.
- ``invariance_subset`` is the small set on which all 8 register x format
  texts are run; it is stratified across groups by round-robin so every group
  contributes, and keeps mirrors together.
- ``fewshot_pool`` supplies in-context examples that cannot leak the evaluation
  set: rows outside the excluded instances AND not sharing a ``fact_id`` (or
  core) with any of them.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping

from temporal_hypo.framework.io import Release

VERDICT_ORDER = ("supported", "refuted", "insufficient")


# ---------------------------------------------------------------------------
# components: what must travel together
# ---------------------------------------------------------------------------

class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self._parent.setdefault(x, x)

    def find(self, x: str) -> str:
        p = self._parent
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # deterministic root choice so components are reproducible
            if ra < rb:
                self._parent[rb] = ra
            else:
                self._parent[ra] = rb


def _components(answers: Mapping[str, dict], keys: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    """instance_id -> the sorted member tuple of its component under the given keys.

    Two instances are joined when they share the value of ANY listed key
    (``derived_from_core_id`` for mirrors, ``fact_id`` for twins).
    """
    uf = _UnionFind()
    first_by_key: dict[tuple[str, str], str] = {}
    for iid in sorted(answers):
        uf.add(iid)
        row = answers[iid]
        for key in keys:
            val = row.get(key)
            if val is None:
                continue
            k = (key, str(val))
            other = first_by_key.setdefault(k, iid)
            if other != iid:
                uf.union(iid, other)
    members: dict[str, list[str]] = defaultdict(list)
    for iid in sorted(answers):
        members[uf.find(iid)].append(iid)
    out: dict[str, tuple[str, ...]] = {}
    for group in members.values():
        t = tuple(group)
        for iid in t:
            out[iid] = t
    return out


def fact_components(release: Release) -> dict[str, tuple[str, ...]]:
    """Mirror + twin closure: instance_id -> every instance sharing its core or fact."""
    return _components(release.answers, ("derived_from_core_id", "fact_id"))


def mirror_components(release: Release) -> dict[str, tuple[str, ...]]:
    """Mirror closure only: instance_id -> the instances sharing its ``derived_from_core_id``."""
    return _components(release.answers, ("derived_from_core_id",))


# ---------------------------------------------------------------------------
# eval_core
# ---------------------------------------------------------------------------

def _split_quota(total: int, n_classes: int) -> list[int]:
    """Split a cap into per-class quotas as evenly as possible (remainder to the first classes)."""
    if n_classes <= 0:
        return []
    base, rem = divmod(total, n_classes)
    return [base + (1 if i < rem else 0) for i in range(n_classes)]


def _class_order(present: Iterable[str]) -> list[str]:
    present = set(present)
    return [v for v in VERDICT_ORDER if v in present] + sorted(present - set(VERDICT_ORDER))


def eval_core(release: Release, *, per_group: int = 90, seed: int = 0) -> list[str]:
    """Seeded, verdict-balanced per-group sample; returns sorted ``instance_id``s.

    For each group (in sorted order) the cap is split evenly over the verdict
    classes present (30/30/30 at ``per_group=90`` for the cohort tiers, 45/45 at
    the report tier). Instances are drawn from a seeded shuffle of each class
    until that class's quota is met; every draw pulls in the instance's whole
    mirror/twin component (``fact_components``), across groups if need be, and
    pulled-in instances count toward their own group/class quotas. A group can
    therefore exceed ``per_group`` only through pulls, and falls short only when
    a class has fewer instances than its quota.
    """
    if per_group < 0:
        raise ValueError(f"per_group must be >= 0, got {per_group}")
    answers = release.answers
    comp = fact_components(release)

    buckets: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for iid in sorted(answers):
        row = answers[iid]
        buckets[row["group_id"]][row["gold_verdict"]].append(iid)

    rng = random.Random(seed)
    selected: set[str] = set()
    for group in sorted(buckets):
        classes = _class_order(buckets[group])
        quotas = _split_quota(per_group, len(classes))
        for verdict, quota in zip(classes, quotas):
            candidates = list(buckets[group][verdict])
            rng.shuffle(candidates)
            have = sum(1 for i in candidates if i in selected)
            for iid in candidates:
                if have >= quota:
                    break
                if iid in selected:
                    continue
                members = comp[iid]
                selected.update(members)
                have += sum(1 for m in members
                            if answers[m]["group_id"] == group
                            and answers[m]["gold_verdict"] == verdict)
    return sorted(selected)


# ---------------------------------------------------------------------------
# invariance subset
# ---------------------------------------------------------------------------

def invariance_subset(release: Release, *, n: int = 200, seed: int = 0,
                      within: Iterable[str] | None = None) -> list[str]:
    """``n`` instances stratified across groups by round-robin, mirrors together.

    Each round visits the groups in sorted order and takes one mirror component
    (a pair, or a singleton) from that group's seeded shuffle; a component that
    would overshoot ``n`` is skipped in favour of the next one. Groups that run
    dry simply drop out of later rounds. ``within`` restricts the pool (e.g. to
    ``eval_core``) so the same predictions serve both analyses; only pool
    members of a component are taken. Returns sorted ``instance_id``s -- exactly
    ``n`` whenever a fitting component exists, otherwise as many as fit.
    """
    if n < 0:
        raise ValueError(f"n must be >= 0, got {n}")
    answers = release.answers
    pool = set(answers) if within is None else {i for i in within if i in answers}
    comp = mirror_components(release)

    queues: dict[str, list[str]] = defaultdict(list)
    for iid in sorted(pool):
        queues[answers[iid]["group_id"]].append(iid)
    rng = random.Random(seed)
    for group in sorted(queues):
        rng.shuffle(queues[group])
        queues[group].reverse()          # pop() from the end == shuffled order

    selected: set[str] = set()
    progress = True
    while len(selected) < n and progress:
        progress = False
        for group in sorted(queues):
            q = queues[group]
            while q:
                iid = q.pop()
                if iid in selected:
                    continue
                members = [m for m in comp[iid] if m in pool]
                if len(selected) + len(members) > n:
                    continue
                selected.update(members)
                progress = True
                break
    return sorted(selected)


# ---------------------------------------------------------------------------
# persistence and description
# ---------------------------------------------------------------------------

def write_subset(ids: Iterable[str], path: Path, meta: Mapping | None = None) -> Path:
    """Write ``{"ids": [...], "meta": {...}}`` as JSON; creates parent directories."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ids": list(ids), "meta": dict(meta or {})}
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def read_subset(path: Path) -> list[str]:
    """The ``ids`` list of a file written by ``write_subset``."""
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict) or not isinstance(payload.get("ids"), list) \
            or not all(isinstance(i, str) for i in payload["ids"]):
        raise ValueError(f"{path}: expected {{'ids': [str, ...], 'meta': {{...}}}}")
    return list(payload["ids"])


def read_subset_meta(path: Path) -> dict:
    """The ``meta`` block of a subset file (``{}`` when absent)."""
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    return dict(payload.get("meta") or {})


def describe_subset(release: Release, ids: Iterable[str]) -> dict:
    """Counts worth recording beside a subset: per group, per group x verdict, facts, cores."""
    ids = list(ids)
    per_group: dict[str, int] = defaultdict(int)
    per_group_verdict: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    facts: set[str] = set()
    cores: set[str] = set()
    for iid in ids:
        row = release.answers[iid]
        per_group[row["group_id"]] += 1
        per_group_verdict[row["group_id"]][row["gold_verdict"]] += 1
        facts.add(row["fact_id"])
        cores.add(row["derived_from_core_id"])
    return {
        "n_instances": len(ids),
        "n_facts": len(facts),
        "n_cores": len(cores),
        "per_group": {g: per_group[g] for g in sorted(per_group)},
        "per_group_verdict": {g: dict(sorted(per_group_verdict[g].items()))
                              for g in sorted(per_group_verdict)},
    }


# ---------------------------------------------------------------------------
# few-shot pool
# ---------------------------------------------------------------------------

def fewshot_pool(release: Release, exclude_instance_ids: Iterable[str], *,
                 k_per_mode: int = 2, seed: int = 0,
                 exclude_groups: Iterable[str] = ()) -> list[dict]:
    """Gold rows usable as in-context examples without leaking the excluded set.

    Eligible rows are outside ``exclude_instance_ids`` and share neither a
    ``fact_id`` nor a ``derived_from_core_id`` with any excluded instance. Up to
    ``k_per_mode`` rows are drawn per mode from a seeded shuffle (fewer where a
    mode is short); the result is ordered by mode, then draw order.
    """
    if k_per_mode < 0:
        raise ValueError(f"k_per_mode must be >= 0, got {k_per_mode}")
    answers = release.answers
    excluded = {i for i in exclude_instance_ids if i in answers}
    # P2 (group holdout): no example may come from a held-out group -- under the
    # toolbox frame a worked example IS a mapping row, so this is the leakage dial.
    banned_groups = set(exclude_groups)
    banned_facts = {answers[i]["fact_id"] for i in excluded}
    banned_cores = {answers[i]["derived_from_core_id"] for i in excluded}

    by_mode: dict[str, list[str]] = defaultdict(list)
    for iid in sorted(answers):
        row = answers[iid]
        if iid in excluded or row["fact_id"] in banned_facts \
                or row["derived_from_core_id"] in banned_cores \
                or row.get("group_id") in banned_groups:
            continue
        by_mode[row["mode"]].append(iid)

    rng = random.Random(seed)
    out: list[dict] = []
    for mode in sorted(by_mode):
        candidates = by_mode[mode]
        rng.shuffle(candidates)
        out.extend(answers[i] for i in candidates[:k_per_mode])
    return out
