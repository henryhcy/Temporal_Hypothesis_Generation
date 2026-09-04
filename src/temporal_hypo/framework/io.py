"""Release loading: the two-file layout, its manifest, and the input/gold join.

What: ``load_release`` reads ``<stem>_questions.jsonl[.gz]`` (``INPUT_FIELDS``
only) and ``<stem>_answers.jsonl[.gz]`` (one gold row per instance) from a
release directory into a ``Release`` -- the question rows in file order plus the
gold rows indexed by ``instance_id``.

Why a dedicated loader: the release's integrity rules are mechanical and every
script in the harness needs the same ones, so they live here once:

- the questions file may carry ONLY ``instances.INPUT_FIELDS`` -- a gold field
  here would hand the framework the answer (``writers.split_release``);
- every question row must join to exactly one gold row through
  ``instance_id = hypothesis_id.rsplit("-", 2)[0]`` (the ``split_release`` rule),
  and the gold row must list that ``hypothesis_id`` back;
- the manifest ``dataset_statistics.json["files"]`` records the sha256 of the
  UNCOMPRESSED files; a run's provenance is those hashes, so loading verifies
  the bytes it actually parsed against them (streaming, one pass);
- ``test_verdict`` is wrong on 1,800 report-tier refuted rows in v1 (issue 25;
  FIXED in v1.1, where the count is 0). The
  harness's gold label is ``gold_verdict``; the loader counts the disagreement
  into ``Release.manifest["issue25_test_verdict_mismatch"]`` (informational) and
  then DROPS the field, so no downstream code can read it by accident.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from temporal_hypo.generation.instances import INPUT_FIELDS

MANIFEST_NAME = "dataset_statistics.json"
FILE_KINDS = ("questions", "answers")
ISSUE25_KEY = "issue25_test_verdict_mismatch"
_FORBIDDEN_GOLD_FIELD = "test_verdict"


# ---------------------------------------------------------------------------
# the loaded release
# ---------------------------------------------------------------------------

def instance_id_of(hypothesis_id: str) -> str:
    """``split_release``'s join rule: strip the ``-<register>-<format>`` suffix."""
    return hypothesis_id.rsplit("-", 2)[0]


@dataclass(repr=False)
class Release:
    """A loaded release: question rows (input side) and gold rows by instance.

    ``questions`` keeps file order. ``answers`` maps ``instance_id`` to the gold
    row; each gold row answers the 8 register x format question rows listed in
    its ``hypothesis_ids``. ``manifest`` is ``dataset_statistics.json`` plus the
    informational ``issue25_test_verdict_mismatch`` count.
    """

    questions: list[dict]
    answers: dict[str, dict]
    manifest: dict
    release_dir: Path
    stem: str

    def __repr__(self) -> str:  # the default would print 150k rows in a traceback
        return (f"Release(stem={self.stem!r}, release_dir={str(self.release_dir)!r}, "
                f"questions={len(self.questions)}, instances={len(self.answers)})")

    # -- joins ---------------------------------------------------------------

    @staticmethod
    def instance_id_of(hypothesis_id: str) -> str:
        return instance_id_of(hypothesis_id)

    def answer_for(self, hypothesis_id: str) -> dict:
        """The gold row of a question row (by ``hypothesis_id``)."""
        iid = instance_id_of(hypothesis_id)
        try:
            return self.answers[iid]
        except KeyError:
            raise KeyError(f"no answer row for {hypothesis_id!r} (instance {iid!r})") from None

    @property
    def instance_ids(self) -> list[str]:
        """Instance ids in answers-file order."""
        return list(self.answers)

    # -- iteration -----------------------------------------------------------

    def iter_records(self, *, registers: Iterable[str] | str | None = None,
                     formats: Iterable[str] | str | None = None,
                     groups: Iterable[str] | str | None = None,
                     instance_ids: Iterable[str] | str | None = None,
                     limit: int | None = None) -> Iterator[dict]:
        """Question rows in file order, filtered; ``limit`` caps the yield count.

        Yields the stored dicts (not copies) -- copy before mutating, e.g. for a
        seeded option shuffle. A lone string is accepted where a set is expected.
        """
        regs, fmts, grps, iids = (_as_set(x) for x in (registers, formats, groups, instance_ids))
        n = 0
        for q in self.questions:
            if limit is not None and n >= limit:
                return
            if regs is not None and q.get("register") not in regs:
                continue
            if fmts is not None and q.get("format") not in fmts:
                continue
            if grps is not None and q.get("group_id") not in grps:
                continue
            if iids is not None and instance_id_of(q["hypothesis_id"]) not in iids:
                continue
            n += 1
            yield q


def _as_set(x: Iterable[str] | str | None) -> set[str] | None:
    if x is None:
        return None
    if isinstance(x, str):
        return {x}
    return set(x)


# ---------------------------------------------------------------------------
# files and hashes
# ---------------------------------------------------------------------------

def _paths(release_dir: Path, stem: str, kind: str) -> tuple[Path, Path]:
    """(gz path, plain path) for one file kind; either may be absent."""
    plain = Path(release_dir) / f"{stem}_{kind}.jsonl"
    return plain.with_name(plain.name + ".gz"), plain


def _pick(release_dir: Path, stem: str, kind: str) -> Path:
    """The file to read: the ``.gz`` when present, else the ``.jsonl``."""
    gz, plain = _paths(release_dir, stem, kind)
    if gz.exists():
        return gz
    if plain.exists():
        return plain
    raise FileNotFoundError(f"release file missing: neither {gz} nor {plain} exists")


def _opener(path: Path):
    return gzip.open if path.suffix == ".gz" else open


def _sha256_of(path: Path) -> tuple[str, int]:
    """sha256 and byte count of a file's UNCOMPRESSED content (streams a ``.gz``)."""
    h = hashlib.sha256()
    n = 0
    with _opener(path)(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def release_sha256s(release_dir: Path, stem: str = "pilot_instances") -> dict:
    """``{"questions": sha256, "answers": sha256}`` of the uncompressed files.

    Hashes the ``.jsonl`` when it exists, else the decompressed ``.gz``; the
    value is the one the manifest's ``files.<kind>.sha256`` records either way.
    Use it for run provenance (``config.json``).
    """
    out: dict[str, str] = {}
    for kind in FILE_KINDS:
        gz, plain = _paths(release_dir, stem, kind)
        path = plain if plain.exists() else _pick(release_dir, stem, kind)
        out[kind], _ = _sha256_of(path)
    return out


def _read_manifest(release_dir: Path, *, required: bool) -> dict:
    path = Path(release_dir) / MANIFEST_NAME
    if not path.exists():
        if required:
            raise FileNotFoundError(
                f"{path} not found; pass verify_sha=False to load without the manifest")
        return {}
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)
    if not isinstance(manifest, dict):
        raise ValueError(f"{path}: manifest must be a JSON object")
    return manifest


def _check_digest(path: Path, kind: str, got_sha: str, got_bytes: int,
                  expect: Mapping[str, Any] | None) -> None:
    if not expect:
        raise ValueError(f"manifest has no files.{kind} entry to verify {path.name} against")
    want_sha = expect.get("sha256")
    if want_sha and got_sha != want_sha:
        raise ValueError(f"sha256 mismatch for {path.name} ({kind}): manifest {want_sha} "
                         f"!= actual {got_sha} (uncompressed content)")
    want_bytes = expect.get("bytes")
    if want_bytes is not None and got_bytes != want_bytes:
        raise ValueError(f"byte-count mismatch for {path.name} ({kind}): manifest "
                         f"{want_bytes} != actual {got_bytes}")


def _read_jsonl(path: Path, kind: str, expect: Mapping[str, Any] | None,
                *, verify: bool) -> list[dict]:
    """Parse one JSONL file (plain or gzip), hashing the uncompressed bytes as they stream."""
    h = hashlib.sha256()
    nbytes = 0
    rows: list[dict] = []
    with _opener(path)(path, "rb") as f:
        for lineno, raw in enumerate(f, 1):
            h.update(raw)
            nbytes += len(raw)
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise ValueError(f"{path.name}:{lineno}: invalid JSON line ({e})") from None
            if not isinstance(row, dict):
                raise ValueError(f"{path.name}:{lineno}: expected a JSON object, got {type(row).__name__}")
            rows.append(row)
    if verify:
        _check_digest(path, kind, h.hexdigest(), nbytes, expect)
    return rows


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def load_release(release_dir: Path, stem: str = "pilot_instances", *,
                 verify_sha: bool = True) -> Release:
    """Load a two-file release and enforce its integrity rules.

    Reads the ``.gz`` of each file when present, else the ``.jsonl``. With
    ``verify_sha=True`` the manifest (``dataset_statistics.json``) is required
    and the sha256 (and byte count) of the UNCOMPRESSED content is checked
    against ``files.<kind>``: the streamed bytes that were parsed, and -- when a
    ``.gz`` was read but a sibling ``.jsonl`` also exists -- that ``.jsonl`` too,
    so a corrupted release directory cannot pass on one of its two copies.

    Raises ``ValueError`` on: a question row whose keys are not exactly
    ``INPUT_FIELDS``; a duplicate ``instance_id``; a gold row whose
    ``hypothesis_ids`` do not belong to it; a question row with no gold row or
    not listed by its gold row (the first offender is named).
    """
    release_dir = Path(release_dir)
    manifest_src = _read_manifest(release_dir, required=verify_sha)
    files = manifest_src.get("files", {}) if verify_sha else {}

    loaded: dict[str, list[dict]] = {}
    for kind in FILE_KINDS:
        path = _pick(release_dir, stem, kind)
        loaded[kind] = _read_jsonl(path, kind, files.get(kind), verify=verify_sha)
        if verify_sha and path.suffix == ".gz":
            gz, plain = _paths(release_dir, stem, kind)
            if plain.exists():
                sha, nbytes = _sha256_of(plain)
                _check_digest(plain, kind, sha, nbytes, files.get(kind))

    questions = loaded["questions"]
    answers = _index_answers(loaded["answers"])
    _check_question_rows(questions, answers)

    manifest = dict(manifest_src)
    manifest[ISSUE25_KEY] = _strip_test_verdict(answers)
    return Release(questions=questions, answers=answers, manifest=manifest,
                   release_dir=release_dir, stem=stem)


def _index_answers(rows: list[dict]) -> dict[str, dict]:
    """Gold rows by ``instance_id`` (derived from ``hypothesis_ids`` if absent)."""
    out: dict[str, dict] = {}
    for i, row in enumerate(rows):
        hids = row.get("hypothesis_ids") or ()
        iid = row.get("instance_id")
        if iid is None:
            if not hids:
                raise ValueError(f"answers row {i} has neither instance_id nor hypothesis_ids")
            iid = instance_id_of(hids[0])
        for hid in hids:
            if instance_id_of(hid) != iid:
                raise ValueError(f"answers row {iid!r} lists {hid!r}, which joins to "
                                 f"{instance_id_of(hid)!r} instead")
        if iid in out:
            raise ValueError(f"duplicate instance_id in answers: {iid!r}")
        out[iid] = row
    return out


def _check_question_rows(questions: list[dict], answers: Mapping[str, dict]) -> None:
    want = frozenset(INPUT_FIELDS)
    for i, q in enumerate(questions):
        keys = frozenset(q)
        if keys != want:
            hid = q.get("hypothesis_id", f"<row {i}>")
            extra = sorted(keys - want)
            missing = sorted(want - keys)
            raise ValueError(f"question row {hid!r} keys != INPUT_FIELDS: "
                             f"extra={extra} missing={missing}")
        hid = q["hypothesis_id"]
        iid = instance_id_of(hid)
        gold = answers.get(iid)
        if gold is None:
            raise ValueError(f"question {hid!r} (instance {iid!r}) has no answer row")
        listed = gold.get("hypothesis_ids")
        if listed is not None and hid not in listed:
            raise ValueError(f"question {hid!r} is not listed in answer row {iid!r}'s hypothesis_ids")


def _strip_test_verdict(answers: Mapping[str, dict]) -> int:
    """Count rows where issue-25's ``test_verdict`` disagrees with ``gold_verdict``, then drop it."""
    mismatch = 0
    for row in answers.values():
        if _FORBIDDEN_GOLD_FIELD in row:
            if row.pop(_FORBIDDEN_GOLD_FIELD) != row.get("gold_verdict"):
                mismatch += 1
    return mismatch
