"""Tests for ``framework.io``: the two-file release loader and its integrity rules."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from temporal_hypo.framework import io as rio
from temporal_hypo.framework.io import Release, load_release, release_sha256s
from temporal_hypo.generation.instances import INPUT_FIELDS
from temporal_hypo.generation.templates import FORMATS, REGISTERS
from tests.framework.conftest import RELEASE_DIR, RELEASE_STEM, needs_release

STEM = "fake"


# ---------------------------------------------------------------------------
# a tiny release: 3 instances x 8 question rows, 3 gold rows, a manifest
# ---------------------------------------------------------------------------

def _gold(instance_id: str, group: str, verdict: str, mode: str, events: list[str],
          cohort: dict, *, core: str, fact: str, test_verdict: str | None = None) -> dict:
    return {
        "group_id": group, "level": cohort["level"], "answer_type": "BOOL",
        "gold_verdict": verdict, "negated": False,
        "gold_n": 12, "gold_k": 10, "gold_n2": None, "gold_k2": None,
        "family": "pairwise", "mode": mode, "p_claim": 0.01, "p_opposite": 0.99,
        "sig_test": "binom_exact", "evidence_ids": {"denominator": [1, 2], "numerator": [1],
                                                    "excluded": []},
        "test_verdict": verdict if test_verdict is None else test_verdict,
        "insufficient_subtype": None, "options": None, "gold_answer": None,
        "cohort": cohort, "derived_from_core_id": core, "fact_id": fact,
        "factual_core": {"primitive": "precedes", "events": events,
                         "vaccines": cohort["vaccines"], "report_id": cohort["report_id"]},
        "instance_id": instance_id,
        "hypothesis_ids": [f"{instance_id}-{r}-{f}" for r in REGISTERS for f in FORMATS],
    }


def _questions(gold: dict) -> list[dict]:
    out = []
    for hid in gold["hypothesis_ids"]:
        _, register, fmt = hid.rsplit("-", 2)
        out.append({
            "hypothesis_id": hid, "group_id": gold["group_id"], "level": gold["level"],
            "answer_type": gold["answer_type"], "register": register, "format": fmt,
            "text": f"{gold['factual_core']['events'][0]} before "
                    f"{gold['factual_core']['events'][1]} ({register}/{fmt})",
            "options": None, "cohort": gold["cohort"],
        })
    return out


def fake_rows() -> tuple[list[dict], list[dict]]:
    vax = {"level": "vaccine", "vaccines": ["Pfizer"], "report_id": None}
    rep = {"level": "report", "vaccines": [], "report_id": 956032}
    golds = [
        _gold("P-V1-0000", "P-V1", "supported", "dir_bool", ["Headache", "Fatigue"], vax,
              core="P-V1|Pfizer|Headache+Fatigue", fact="precedes|Pfizer|Fatigue+Headache"),
        _gold("P-V1-0001", "P-V1", "refuted", "dir_bool", ["Fatigue", "Headache"], vax,
              core="P-V1|Pfizer|Headache+Fatigue", fact="precedes|Pfizer|Fatigue+Headache"),
        # issue 25: report-tier refuted row whose test_verdict is wrong
        _gold("P-R1-0000", "P-R1", "refuted", "rep_dir_bool", ["Back pain", "Chest discomfort"],
              rep, core="P-R1|R956032|Chest discomfort+Back pain",
              fact="rep_precedes|R956032|Back pain+Chest discomfort", test_verdict="supported"),
    ]
    questions = [q for g in golds for q in _questions(g)]
    return questions, golds


def _jsonl(rows: list[dict]) -> bytes:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8")


def write_fake_release(dirpath: Path, *, plain: bool = True, gz: bool = False,
                       questions: list[dict] | None = None,
                       answers: list[dict] | None = None,
                       manifest: bool = True) -> Path:
    """Write the fake release in the requested layout; the manifest hashes the given rows."""
    q_rows, a_rows = fake_rows()
    questions = q_rows if questions is None else questions
    answers = a_rows if answers is None else answers
    dirpath.mkdir(parents=True, exist_ok=True)
    files = {}
    for kind, rows in (("questions", questions), ("answers", answers)):
        data = _jsonl(rows)
        path = dirpath / f"{STEM}_{kind}.jsonl"
        if plain:
            path.write_bytes(data)
        if gz:
            with gzip.open(path.with_name(path.name + ".gz"), "wb") as f:
                f.write(data)
        files[kind] = {"path": path.name, "bytes": len(data),
                       "sha256": hashlib.sha256(data).hexdigest()}
    if manifest:
        (dirpath / rio.MANIFEST_NAME).write_text(
            json.dumps({"files": files, "totals": {"records": len(questions),
                                                   "instances": len(answers)}}),
            encoding="utf-8")
    return dirpath


@pytest.fixture
def fake_dir(tmp_path: Path) -> Path:
    return write_fake_release(tmp_path / "rel")


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def test_load_plain_release(fake_dir: Path):
    rel = load_release(fake_dir, STEM)
    assert isinstance(rel, Release)
    assert len(rel.questions) == 24 and len(rel.answers) == 3
    assert rel.instance_ids == ["P-V1-0000", "P-V1-0001", "P-R1-0000"]
    assert rel.release_dir == fake_dir and rel.stem == STEM
    # file order preserved
    assert rel.questions[0]["hypothesis_id"] == "P-V1-0000-original-question"
    # join helpers
    assert rel.instance_id_of("P-V1-0001-clinical-claim") == "P-V1-0001"
    assert rel.answer_for("P-V1-0001-clinical-claim")["gold_verdict"] == "refuted"
    with pytest.raises(KeyError):
        rel.answer_for("P-V9-0000-original-claim")
    # manifest is carried through, plus the informational issue-25 count
    assert rel.manifest["totals"] == {"records": 24, "instances": 3}
    assert rel.manifest[rio.ISSUE25_KEY] == 1
    assert "fake" in repr(rel) and "24" in repr(rel)


def test_test_verdict_is_never_exposed(fake_dir: Path):
    rel = load_release(fake_dir, STEM)
    assert all("test_verdict" not in row for row in rel.answers.values())
    # the gold label the harness uses is untouched
    assert rel.answers["P-R1-0000"]["gold_verdict"] == "refuted"


def test_load_gz_only_verifies_uncompressed_sha(tmp_path: Path):
    d = write_fake_release(tmp_path / "rel", plain=False, gz=True)
    assert not (d / f"{STEM}_questions.jsonl").exists()
    rel = load_release(d, STEM, verify_sha=True)
    assert len(rel.questions) == 24 and len(rel.answers) == 3


def test_gz_preferred_when_both_present(tmp_path: Path):
    d = write_fake_release(tmp_path / "rel", plain=True, gz=True)
    # break the .jsonl only: with verify_sha=False the .gz is read and must be fine
    (d / f"{STEM}_questions.jsonl").write_bytes(b"{not json\n")
    rel = load_release(d, STEM, verify_sha=False)
    assert len(rel.questions) == 24
    # with verify_sha=True the corrupt sibling .jsonl is caught against the manifest
    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_release(d, STEM, verify_sha=True)


def test_sha_verification_fails_on_tampering(fake_dir: Path):
    path = fake_dir / f"{STEM}_answers.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["gold_verdict"] = "refuted"          # same byte count, different content
    path.write_bytes(_jsonl(rows))
    with pytest.raises(ValueError, match="sha256 mismatch.*answers"):
        load_release(fake_dir, STEM, verify_sha=True)
    rel = load_release(fake_dir, STEM, verify_sha=False)
    assert rel.answers["P-V1-0000"]["gold_verdict"] == "refuted"


def test_sha_verification_fails_on_tampered_gz(tmp_path: Path):
    d = write_fake_release(tmp_path / "rel", plain=False, gz=True)
    path = d / f"{STEM}_questions.jsonl.gz"
    with gzip.open(path, "rb") as f:
        data = f.read()
    with gzip.open(path, "wb") as f:
        f.write(data + b'{"hypothesis_id": "P-V1-0000-original-question", "group_id": "P-V1"}\n')
    with pytest.raises(ValueError, match="sha256 mismatch|byte-count mismatch"):
        load_release(d, STEM, verify_sha=True)


def test_manifest_required_only_when_verifying(tmp_path: Path):
    d = write_fake_release(tmp_path / "rel", manifest=False)
    with pytest.raises(FileNotFoundError, match="dataset_statistics.json"):
        load_release(d, STEM, verify_sha=True)
    rel = load_release(d, STEM, verify_sha=False)
    assert rel.manifest == {rio.ISSUE25_KEY: 1}


def test_missing_files_raise(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_release(tmp_path, STEM, verify_sha=False)


def test_input_fields_assertion_extra_key(tmp_path: Path):
    q, a = fake_rows()
    q[5] = dict(q[5], gold_verdict="supported")   # a gold leak
    d = write_fake_release(tmp_path / "rel", questions=q)
    with pytest.raises(ValueError, match=r"P-V1-0000-media-claim.*extra=\['gold_verdict'\]"):
        load_release(d, STEM)


def test_input_fields_assertion_missing_key(tmp_path: Path):
    q, a = fake_rows()
    q[0] = {k: v for k, v in q[0].items() if k != "cohort"}
    d = write_fake_release(tmp_path / "rel", questions=q)
    with pytest.raises(ValueError, match=r"missing=\['cohort'\]"):
        load_release(d, STEM)
    assert set(INPUT_FIELDS) == set(q[1])   # the fixture rows really are INPUT_FIELDS


def test_join_failure_names_first_offender(tmp_path: Path):
    q, a = fake_rows()
    orphan = dict(q[0], hypothesis_id="P-V1-0007-original-question")
    q.insert(3, orphan)
    d = write_fake_release(tmp_path / "rel", questions=q)
    with pytest.raises(ValueError, match="P-V1-0007-original-question.*no answer row"):
        load_release(d, STEM)


def test_join_failure_when_answer_does_not_list_question(tmp_path: Path):
    q, a = fake_rows()
    a[1] = dict(a[1], hypothesis_ids=a[1]["hypothesis_ids"][:-1])
    d = write_fake_release(tmp_path / "rel", answers=a)
    with pytest.raises(ValueError, match="P-V1-0001-clinical-claim.*not listed"):
        load_release(d, STEM)


def test_answer_row_consistency_checks(tmp_path: Path):
    q, a = fake_rows()
    dup = write_fake_release(tmp_path / "dup", answers=a + [dict(a[0])])
    with pytest.raises(ValueError, match="duplicate instance_id"):
        load_release(dup, STEM)
    bad = [dict(a[0], hypothesis_ids=a[0]["hypothesis_ids"] + ["P-V1-0001-original-claim"])] + a[1:]
    d = write_fake_release(tmp_path / "bad", answers=bad)
    with pytest.raises(ValueError, match="joins to 'P-V1-0001' instead"):
        load_release(d, STEM)


def test_instance_id_derived_when_absent(tmp_path: Path):
    q, a = fake_rows()
    a = [{k: v for k, v in row.items() if k != "instance_id"} for row in a]
    d = write_fake_release(tmp_path / "rel", answers=a)
    rel = load_release(d, STEM)
    assert set(rel.answers) == {"P-V1-0000", "P-V1-0001", "P-R1-0000"}


def test_invalid_json_line_is_reported_with_position(tmp_path: Path):
    d = write_fake_release(tmp_path / "rel")
    path = d / f"{STEM}_questions.jsonl"
    path.write_bytes(path.read_bytes() + b"{oops\n")
    with pytest.raises(ValueError, match=r"fake_questions.jsonl:25: invalid JSON"):
        load_release(d, STEM, verify_sha=False)


# ---------------------------------------------------------------------------
# iteration and hashes
# ---------------------------------------------------------------------------

def test_iter_records_filters(fake_dir: Path):
    rel = load_release(fake_dir, STEM)
    assert len(list(rel.iter_records())) == 24
    assert [q["hypothesis_id"] for q in rel.iter_records(registers="original", formats="claim")] == [
        "P-V1-0000-original-claim", "P-V1-0001-original-claim", "P-R1-0000-original-claim"]
    assert len(list(rel.iter_records(registers={"original", "media"}))) == 12
    assert len(list(rel.iter_records(formats=["question"]))) == 12
    assert {q["group_id"] for q in rel.iter_records(groups="P-R1")} == {"P-R1"}
    assert len(list(rel.iter_records(groups=["P-R1"]))) == 8
    got = list(rel.iter_records(instance_ids=["P-V1-0001"]))
    assert len(got) == 8 and all(rel.instance_id_of(q["hypothesis_id"]) == "P-V1-0001" for q in got)
    assert len(list(rel.iter_records(limit=5))) == 5
    assert len(list(rel.iter_records(limit=0))) == 0
    combo = list(rel.iter_records(groups="P-V1", registers="clinical", formats="question", limit=1))
    assert [q["hypothesis_id"] for q in combo] == ["P-V1-0000-clinical-question"]
    assert list(rel.iter_records(registers="lay")) == []


def test_release_sha256s_match_manifest(tmp_path: Path):
    for layout in ({"plain": True, "gz": False}, {"plain": False, "gz": True}, {"plain": True, "gz": True}):
        d = write_fake_release(tmp_path / f"rel_{layout['plain']}_{layout['gz']}", **layout)
        manifest = json.loads((d / rio.MANIFEST_NAME).read_text(encoding="utf-8"))
        shas = release_sha256s(d, STEM)
        assert set(shas) == {"questions", "answers"}
        assert shas == {k: manifest["files"][k]["sha256"] for k in shas}


# ---------------------------------------------------------------------------
# the real release
# ---------------------------------------------------------------------------

@pytest.mark.slow
@needs_release
def test_real_release_loads_and_verifies():
    rel = load_release(RELEASE_DIR, RELEASE_STEM, verify_sha=True)
    assert len(rel.questions) == 147_936
    assert len(rel.answers) == 18_492
    assert rel.manifest[rio.ISSUE25_KEY] == 1800
    assert all("test_verdict" not in row for row in rel.answers.values())
    assert all(len(row["hypothesis_ids"]) == 8 for row in rel.answers.values())
    assert set(rel.questions[0]) == set(INPUT_FIELDS)
    shas = release_sha256s(RELEASE_DIR, RELEASE_STEM)
    assert shas == {k: rel.manifest["files"][k]["sha256"] for k in ("questions", "answers")}
    # every gold row answers question rows that exist, and vice versa
    listed = {h for row in rel.answers.values() for h in row["hypothesis_ids"]}
    assert listed == {q["hypothesis_id"] for q in rel.questions}
    assert len(list(rel.iter_records(registers="original", formats="question"))) == 18_492
