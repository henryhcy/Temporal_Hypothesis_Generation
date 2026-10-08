"""The report-id pseudonymiser (decisions.md 2026-10-08, review item 4)."""
import os
import sqlite3

import pytest

from temporal_hypo.core.pseudonym import DOMAIN, REPORT_RE, Pseudonymizer, report_ref

KEY_A = "a" * 64
KEY_B = "b" * 64


def test_is_a_permutation_with_an_inverse():
    pz = Pseudonymizer.from_hex(KEY_A)
    ids = list(range(916_000, 917_000)) + [0, 1, DOMAIN - 1, 2_817_150]
    out = [pz(i) for i in ids]
    assert len(set(out)) == len(ids)
    assert all(0 <= y < DOMAIN for y in out)
    assert [pz.inverse(y) for y in out] == ids
    assert sum(1 for i, y in zip(ids, out) if i == y) < 3        # not the identity


def test_stable_under_the_same_key_and_different_across_keys():
    a1, a2, b = (Pseudonymizer.from_hex(k) for k in (KEY_A, KEY_A, KEY_B))
    assert [a1(i) for i in range(1000, 1100)] == [a2(i) for i in range(1000, 1100)]
    assert [a1(i) for i in range(1000, 1100)] != [b(i) for i in range(1000, 1100)]


def test_identity_mode_and_rendering():
    pz = Pseudonymizer.from_hex("identity")
    assert pz.is_identity and pz(1001) == 1001
    assert report_ref(1001) == "MT-0001001"
    m = REPORT_RE.fullmatch(report_ref(482913))
    assert m and int(m.group(1)) == 482913
    with pytest.raises(ValueError):
        pz(DOMAIN)


def test_default_reads_the_env_then_the_key_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDTEMPO_PSEUDONYM_KEY", KEY_A)
    assert not Pseudonymizer.default(tmp_path / "none").is_identity
    monkeypatch.delenv("MEDTEMPO_PSEUDONYM_KEY")
    with pytest.raises(FileNotFoundError):
        Pseudonymizer.default(tmp_path / "none")
    p = Pseudonymizer.generate(tmp_path / "k")
    assert Pseudonymizer.default(p)(1001) == Pseudonymizer.from_hex(p.read_text())(1001)
    with pytest.raises(FileExistsError):
        Pseudonymizer.generate(p)


def test_corpus_index_and_eval_db_share_the_id_space(tmp_path):
    from temporal_hypo.framework.sql.build_eval_db import build_eval_db
    from temporal_hypo.generation.corpus import CorpusIndex
    from tests.generation.conftest import make_db

    corpus = [(1001, "Pfizer", [["Headache"], ["Fatigue"]]), (1002, "Moderna", [["Nausea", "Headache"]])]
    pz = Pseudonymizer.from_hex(KEY_A)
    index = CorpusIndex.load(make_db(corpus), pseudonymizer=pz)
    assert set(index.report_terms) == {pz(1001), pz(1002)} and 1001 not in index.report_terms
    assert index.vaers_of[pz(1001)] == 1001
    counts = build_eval_db(make_db(corpus), tmp_path / "e.db", pseudonymizer=pz)
    assert counts["reports"] == 2 and counts["identity"] is False
    con = sqlite3.connect(tmp_path / "e.db")
    assert {r for (r,) in con.execute("SELECT report_id FROM reports")} == {pz(1001), pz(1002)}
    assert con.execute("SELECT level FROM first_mention WHERE report_id = ? AND term = 'Fatigue'",
                       (pz(1001),)).fetchone()[0] == 1
