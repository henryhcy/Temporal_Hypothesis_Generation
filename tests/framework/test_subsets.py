"""Tests for ``framework.subsets``: eval_core balance and pull-in rules, invariance subset, few-shot pool."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from temporal_hypo.framework.io import Release, load_release
from temporal_hypo.framework.subsets import (
    describe_subset,
    eval_core,
    fact_components,
    fewshot_pool,
    invariance_subset,
    mirror_components,
    read_subset,
    read_subset_meta,
    write_subset,
)
from tests.framework.conftest import RELEASE_DIR, RELEASE_STEM, needs_release


# ---------------------------------------------------------------------------
# a synthetic Release with the structures that matter
# ---------------------------------------------------------------------------

class _Builder:
    """Answer rows only -- the subset functions never look at question rows."""

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self._seq: Counter = Counter()

    def _add(self, group: str, verdict: str, *, core: str, fact: str, mode: str) -> str:
        iid = f"{group}-{self._seq[group]:04d}"
        self._seq[group] += 1
        level = "report" if group.split("-")[1].startswith("R") else "vaccine"
        self.rows[iid] = {
            "instance_id": iid, "group_id": group, "level": level, "gold_verdict": verdict,
            "mode": mode, "derived_from_core_id": core, "fact_id": fact,
            "hypothesis_ids": [f"{iid}-original-question", f"{iid}-original-claim"],
        }
        return iid

    def pair(self, group: str, *, core: str, fact: str, mode: str) -> tuple[str, str]:
        """A mirror pair: supported + refuted on one core."""
        return (self._add(group, "supported", core=core, fact=fact, mode=mode),
                self._add(group, "refuted", core=core, fact=fact, mode=mode))

    def single(self, group: str, verdict: str, *, tag: str, mode: str) -> str:
        return self._add(group, verdict, core=f"{group}|{tag}", fact=f"{mode}|{tag}", mode=mode)

    def release(self) -> Release:
        return Release(questions=[], answers=dict(self.rows), manifest={},
                       release_dir=Path("."), stem="synthetic")


def build_release() -> Release:
    b = _Builder()
    # A-V1 / A-V3: answer-format twins. 20 facts; each has a mirror pair in BOTH groups.
    for i in range(20):
        fact = f"precedes|Pfizer|E{i}+F{i}"
        b.pair("A-V1", core=f"A-V1|Pfizer|E{i}+F{i}", fact=fact, mode="dir_bool")
        b.pair("A-V3", core=f"A-V3|Pfizer|E{i}+F{i}", fact=fact, mode="dir_choice")
    # A-V3 has 10 extra pairs of its own (facts with no twin)
    for i in range(20, 30):
        b.pair("A-V3", core=f"A-V3|Pfizer|E{i}+F{i}", fact=f"precedes|Pfizer|E{i}+F{i}",
               mode="dir_choice")
    # insufficient instances are unpaired singletons
    for g, mode in (("A-V1", "dir_bool"), ("A-V3", "dir_choice")):
        for i in range(20):
            b.single(g, "insufficient", tag=f"ins{i}", mode=mode)
    # B-V4: pairpair-style facts, 3 cores (3 mirror pairs) per fact, 5 facts; 10 insufficient
    for i in range(5):
        fact = f"pairpair|Moderna|Q{i}+R{i}+S{i}+T{i}"
        for j in range(3):
            b.pair("B-V4", core=f"B-V4|Moderna|pairing{j}|{i}", fact=fact, mode="pairpair_bool")
    for i in range(10):
        b.single("B-V4", "insufficient", tag=f"ins{i}", mode="pairpair_bool")
    # C-R1: report tier, two classes, all singletons (like the real C-R1)
    for i in range(40):
        b.single("C-R1", "supported", tag=f"s{i}", mode="rep_sym_bool")
    for i in range(25):
        b.single("C-R1", "refuted", tag=f"r{i}", mode="rep_sym_bool")
    # D-V2: a class shorter than its quota (3 pairs, 50 insufficient)
    for i in range(3):
        b.pair("D-V2", core=f"D-V2|Janssen|G{i}+H{i}", fact=f"antecedent|Janssen|G{i}+H{i}",
               mode="antecedent_bool")
    for i in range(50):
        b.single("D-V2", "insufficient", tag=f"ins{i}", mode="antecedent_bool")
    # S-V1: tiny group, everything must be taken
    b.pair("S-V1", core="S-V1|Pfizer|X+Y+Z", fact="seq_modal|Pfizer|X+Y+Z", mode="seq_bool")
    b.single("S-V1", "insufficient", tag="ins0", mode="seq_bool")
    return b.release()


@pytest.fixture(scope="module")
def rel() -> Release:
    return build_release()


def _by_group_verdict(rel: Release, ids: list[str]) -> dict[str, Counter]:
    out: dict[str, Counter] = defaultdict(Counter)
    for i in ids:
        r = rel.answers[i]
        out[r["group_id"]][r["gold_verdict"]] += 1
    return out


def _assert_no_straddle(rel: Release, ids: list[str], key: str) -> None:
    chosen = set(ids)
    members: dict[str, set[str]] = defaultdict(set)
    for iid, row in rel.answers.items():
        members[row[key]].add(iid)
    for iid in ids:
        assert members[rel.answers[iid][key]] <= chosen, (key, iid)


# ---------------------------------------------------------------------------
# eval_core
# ---------------------------------------------------------------------------

def test_eval_core_balanced_thirds_and_cap(rel: Release):
    ids = eval_core(rel, per_group=30, seed=0)
    counts = _by_group_verdict(rel, ids)
    # A-V1 has 20 pairs + 20 singletons and its twins live in A-V3: exactly 10/10/10
    assert counts["A-V1"] == Counter(supported=10, refuted=10, insufficient=10)
    # A-V3 receives A-V1's 10 twin pairs by pull-in, which fill its own supported/refuted quota
    assert counts["A-V3"] == Counter(supported=10, refuted=10, insufficient=10)
    # report tier: halves
    assert counts["C-R1"] == Counter(supported=15, refuted=15)
    # a short class is not topped up from the others
    assert counts["D-V2"] == Counter(supported=3, refuted=3, insufficient=10)
    # a tiny group is taken whole
    assert counts["S-V1"] == Counter(supported=1, refuted=1, insufficient=1)
    assert ids == sorted(ids)


def test_eval_core_cap_exceeded_only_by_pulls(rel: Release):
    ids = eval_core(rel, per_group=6, seed=0)
    counts = _by_group_verdict(rel, ids)
    # B-V4: quota 2/2/2, but one supported draw pulls its whole 6-instance fact
    assert counts["B-V4"] == Counter(supported=3, refuted=3, insufficient=2)
    chosen_b = [i for i in ids if i.startswith("B-V4") and rel.answers[i]["gold_verdict"] != "insufficient"]
    facts = {rel.answers[i]["fact_id"] for i in chosen_b}
    assert len(facts) == 1 and len(chosen_b) == 6
    # every other group without oversize components sits exactly at the cap
    assert sum(counts["A-V1"].values()) == 6
    assert sum(counts["C-R1"].values()) == 6
    assert sum(counts["D-V2"].values()) == 6


def test_eval_core_never_splits_mirrors_or_twins(rel: Release):
    for seed in (0, 1, 7):
        for cap in (6, 30, 90):
            ids = eval_core(rel, per_group=cap, seed=seed)
            _assert_no_straddle(rel, ids, "derived_from_core_id")
            _assert_no_straddle(rel, ids, "fact_id")
            assert len(ids) == len(set(ids))


def test_eval_core_twins_cross_groups(rel: Release):
    ids = eval_core(rel, per_group=30, seed=3)
    chosen = set(ids)
    for iid in ids:
        if iid.startswith("A-V1") and rel.answers[iid]["gold_verdict"] != "insufficient":
            fact = rel.answers[iid]["fact_id"]
            twins = [j for j, r in rel.answers.items() if r["fact_id"] == fact and j.startswith("A-V3")]
            assert len(twins) == 2 and set(twins) <= chosen


def test_eval_core_deterministic_and_seed_sensitive(rel: Release):
    a = eval_core(rel, per_group=30, seed=0)
    b = eval_core(rel, per_group=30, seed=0)
    c = eval_core(rel, per_group=30, seed=1)
    assert a == b
    assert a != c
    assert len(a) == len(c)   # same shape, different draw


def test_eval_core_quotas_met_where_available(rel: Release):
    per_group = 30
    ids = eval_core(rel, per_group=per_group, seed=0)
    counts = _by_group_verdict(rel, ids)
    avail = _by_group_verdict(rel, list(rel.answers))
    for g, classes in avail.items():
        quota = per_group // len(classes)
        for v, n in classes.items():
            assert counts[g][v] >= min(quota, n), (g, v)


def test_eval_core_edge_caps(rel: Release):
    assert eval_core(rel, per_group=0) == []
    everything = eval_core(rel, per_group=10_000)
    assert everything == sorted(rel.answers)
    with pytest.raises(ValueError):
        eval_core(rel, per_group=-1)


def test_components(rel: Release):
    fc = fact_components(rel)
    mc = mirror_components(rel)
    assert fc["A-V1-0000"] == ("A-V1-0000", "A-V1-0001", "A-V3-0000", "A-V3-0001")
    assert mc["A-V1-0000"] == ("A-V1-0000", "A-V1-0001")
    assert len(fc["B-V4-0000"]) == 6
    assert fc["C-R1-0000"] == ("C-R1-0000",)


# ---------------------------------------------------------------------------
# invariance subset
# ---------------------------------------------------------------------------

def test_invariance_subset_size_strata_and_mirrors(rel: Release):
    ids = invariance_subset(rel, n=40, seed=0)
    assert len(ids) == 40 and ids == sorted(ids)
    _assert_no_straddle(rel, ids, "derived_from_core_id")
    per_group = Counter(rel.answers[i]["group_id"] for i in ids)
    # 6 groups; round-robin: every group contributes, none dominates
    assert set(per_group) == {"A-V1", "A-V3", "B-V4", "C-R1", "D-V2", "S-V1"}
    assert per_group["S-V1"] <= 3
    assert max(per_group.values()) <= 12
    assert invariance_subset(rel, n=40, seed=0) == ids
    assert invariance_subset(rel, n=40, seed=5) != ids


def test_invariance_subset_within_pool(rel: Release):
    core = eval_core(rel, per_group=30, seed=0)
    ids = invariance_subset(rel, n=20, seed=0, within=core)
    assert len(ids) == 20 and set(ids) <= set(core)
    _assert_no_straddle(rel, ids, "derived_from_core_id")


def test_invariance_subset_exhausts_small_pool(rel: Release):
    ids = invariance_subset(rel, n=10_000)
    assert ids == sorted(rel.answers)
    assert invariance_subset(rel, n=0) == []


# ---------------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------------

def test_write_read_subset_roundtrip(rel: Release, tmp_path: Path):
    ids = eval_core(rel, per_group=30)
    meta = {"cap": 30, "seed": 0, **describe_subset(rel, ids)}
    path = write_subset(ids, tmp_path / "sub" / "eval_core.json", meta)
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload) == {"ids", "meta"}
    assert payload["ids"] == ids
    assert payload["meta"]["cap"] == 30
    assert payload["meta"]["per_group"]["C-R1"] == 30
    assert read_subset(path) == ids
    assert read_subset_meta(path)["n_instances"] == len(ids)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"instances": ids}), encoding="utf-8")
    with pytest.raises(ValueError):
        read_subset(bad)


def test_describe_subset(rel: Release):
    d = describe_subset(rel, ["A-V1-0000", "A-V1-0001", "C-R1-0000"])
    assert d["n_instances"] == 3 and d["n_facts"] == 2 and d["n_cores"] == 2
    assert d["per_group"] == {"A-V1": 2, "C-R1": 1}
    assert d["per_group_verdict"]["A-V1"] == {"refuted": 1, "supported": 1}


# ---------------------------------------------------------------------------
# few-shot pool
# ---------------------------------------------------------------------------

def test_fewshot_pool_disjoint_by_fact_and_core(rel: Release):
    core = eval_core(rel, per_group=30, seed=0)
    pool = fewshot_pool(rel, core, k_per_mode=2, seed=0)
    excluded = set(core)
    banned_facts = {rel.answers[i]["fact_id"] for i in core}
    banned_cores = {rel.answers[i]["derived_from_core_id"] for i in core}
    for row in pool:
        assert row["instance_id"] not in excluded
        assert row["fact_id"] not in banned_facts
        assert row["derived_from_core_id"] not in banned_cores
    per_mode = Counter(r["mode"] for r in pool)
    assert all(n <= 2 for n in per_mode.values())
    # modes with eligible rows left are represented; S-V1 (seq_bool) was taken whole
    assert "seq_bool" not in per_mode
    assert per_mode["dir_bool"] == 2 and per_mode["rep_sym_bool"] == 2
    # ordered by mode, then draw
    assert [r["mode"] for r in pool] == sorted(r["mode"] for r in pool)
    assert [r["instance_id"] for r in fewshot_pool(rel, core, k_per_mode=2, seed=0)] == \
        [r["instance_id"] for r in pool]
    assert [r["instance_id"] for r in fewshot_pool(rel, core, k_per_mode=2, seed=1)] != \
        [r["instance_id"] for r in pool]


def test_fewshot_pool_k_and_unknown_ids(rel: Release):
    pool = fewshot_pool(rel, ["not-an-id"], k_per_mode=1)
    modes = [r["mode"] for r in pool]
    assert modes == sorted(set(r["mode"] for r in rel.answers.values()))
    assert fewshot_pool(rel, [], k_per_mode=0) == []
    with pytest.raises(ValueError):
        fewshot_pool(rel, [], k_per_mode=-1)


# ---------------------------------------------------------------------------
# the real release
# ---------------------------------------------------------------------------

@pytest.mark.slow
@needs_release
def test_eval_core_on_real_release():
    release = load_release(RELEASE_DIR, RELEASE_STEM, verify_sha=False)
    per_group = 90
    ids = eval_core(release, per_group=per_group, seed=0)
    assert ids == eval_core(release, per_group=per_group, seed=0)
    _assert_no_straddle(release, ids, "derived_from_core_id")
    _assert_no_straddle(release, ids, "fact_id")
    d = describe_subset(release, ids)
    print(f"\neval_core(per_group={per_group}, seed=0): {d['n_instances']} instances, "
          f"{d['n_facts']} facts, {d['n_cores']} cores")
    for g, n in d["per_group"].items():
        print(f"  {g:6s} {n:4d}  {d['per_group_verdict'][g]}")
    avail = _by_group_verdict(release, list(release.answers))
    counts = _by_group_verdict(release, ids)
    for g, classes in avail.items():
        quota = per_group // len(classes)
        for v, n in classes.items():
            assert counts[g][v] >= min(quota, n), (g, v)
    # groups whose facts never leave the group and have <= 2 instances per fact sit at the cap
    fact_groups: dict[str, set[str]] = defaultdict(set)
    fact_size: Counter = Counter()
    for row in release.answers.values():
        fact_groups[row["fact_id"]].add(row["group_id"])
        fact_size[row["fact_id"]] += 1
    for g, n in d["per_group"].items():
        simple = all(len(fact_groups[r["fact_id"]]) == 1 and fact_size[r["fact_id"]] <= 2
                     for r in release.answers.values() if r["group_id"] == g)
        if simple:
            assert n <= per_group, (g, n)
    assert 1_500 <= d["n_instances"] <= 2_200
    # a few-shot pool drawn outside eval_core is disjoint by fact; modes whose
    # instances were ALL drawn (S-V1/S-V3 have 6, P-M2 87 <= cap) have no examples
    pool = fewshot_pool(release, ids, k_per_mode=2, seed=0)
    banned = {release.answers[i]["fact_id"] for i in ids}
    assert all(r["fact_id"] not in banned for r in pool)
    eligible_modes = {r["mode"] for r in release.answers.values() if r["fact_id"] not in banned}
    assert eligible_modes == {r["mode"] for r in pool}
    assert len(pool) == 2 * len(eligible_modes)
    all_modes = {r["mode"] for r in release.answers.values()}
    assert all_modes - eligible_modes == {"seq_bool", "modal_choice", "multi_dir_precedes"}
    print(f"  fewshot_pool: {len(pool)} rows over {len(eligible_modes)} modes; "
          f"no examples for {sorted(all_modes - eligible_modes)}")
    inv = invariance_subset(release, n=200, seed=0, within=ids)
    assert len(inv) == 200 and set(inv) <= set(ids)
    _assert_no_straddle(release, inv, "derived_from_core_id")
