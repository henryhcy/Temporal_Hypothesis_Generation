"""Shared fixtures for the framework (eval harness) tests.

One synthetic corpus, small enough to count by hand, rich enough to exercise
every conditioning rule: ordered pairs, co-exist pairs, orderable and tied
triples, first/last ties, a term mentioned at two levels (first-mention rule),
reports with a term absent, and three vaccine cohorts. Built with
``tests/generation/conftest.py::make_db`` so the raw schema matches the real
``medtempo.db`` exactly (including the ``narrative`` column the eval DB must drop).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.generation.conftest import make_db

H, F, P, R, N, C = ("Headache", "Fatigue", "Pyrexia", "Rash", "Nausea", "Chills")

# (vaers_id, vaccine, levels)  -- levels are the leveled order, earliest first
CORPUS: list[tuple[int, str, list[list[str]]]] = [
    # Pfizer: H before F in 6, F before H in 2, co-exist in 3, H only in 2, F only in 1
    (1001, "Pfizer", [[H], [F], [P]]),
    (1002, "Pfizer", [[H], [F, P]]),
    (1003, "Pfizer", [[H, R], [F]]),
    (1004, "Pfizer", [[H], [C], [F]]),
    (1005, "Pfizer", [[H], [F]]),
    (1006, "Pfizer", [[H], [N], [F], [P]]),
    (1007, "Pfizer", [[F], [H]]),
    (1008, "Pfizer", [[F], [P], [H]]),
    (1009, "Pfizer", [[H, F], [P]]),
    (1010, "Pfizer", [[H, F]]),
    (1011, "Pfizer", [[P], [H, F]]),
    (1012, "Pfizer", [[H], [P]]),
    (1013, "Pfizer", [[H]]),
    (1014, "Pfizer", [[F], [R]]),
    # first-mention trap: Headache at levels 0 and 2 -> position is 0
    (1015, "Pfizer", [[H], [F], [H, P]]),
    # Moderna: a tie-heavy cohort for first/last and sequence
    (2001, "Moderna", [[H], [F], [P]]),
    (2002, "Moderna", [[H], [P], [F]]),
    (2003, "Moderna", [[H, F], [P]]),          # tie for first (H,F) -> dropped for first, ok for last
    (2004, "Moderna", [[F], [H], [P]]),
    (2005, "Moderna", [[H], [F, P]]),          # tie for last
    (2006, "Moderna", [[P], [H], [F]]),
    (2007, "Moderna", [[H], [F]]),             # P absent -> not in triple denominators
    (2008, "Moderna", [[H], [F], [P]]),
    (2009, "Moderna", [[H], [F], [P]]),
    (2010, "Moderna", [[F], [P], [H]]),
    (2011, "Moderna", [[H, F, P]]),            # all tied
    (2012, "Moderna", [[H], [F], [P]]),
    # Janssen: small cohort, nothing co-occurs for (Rash, Nausea)
    (3001, "Janssen", [[H], [R]]),
    (3002, "Janssen", [[N], [H]]),
    (3003, "Janssen", [[H], [F]]),
    (3004, "Janssen", [[C]]),
]


@pytest.fixture(scope="session")
def raw_conn() -> sqlite3.Connection:
    """The raw MedTempo-shaped DB (has `narrative`; report_id surrogate PK)."""
    return make_db(CORPUS)


@pytest.fixture(scope="session")
def eval_db_path(tmp_path_factory) -> Path:
    """The narrative-free eval DB built from the synthetic corpus."""
    from temporal_hypo.framework.sql.build_eval_db import build_eval_db

    src = make_db(CORPUS)
    dst = tmp_path_factory.mktemp("evaldb") / "medtempo_eval.db"
    build_eval_db(src, dst)
    return dst


@pytest.fixture(scope="session")
def corpus_index(raw_conn):
    from temporal_hypo.generation.corpus import CorpusIndex

    return CorpusIndex.load(raw_conn)


@pytest.fixture(scope="session")
def groups():
    from temporal_hypo.generation.templates import load_groups

    return load_groups()


REPO_ROOT = Path(__file__).resolve().parents[2]
# v1.2 is the first release in PSEUDONYM id space (core/pseudonym.py); the
# texts of v1/v1.1 carry VAERS ids and no longer parse under REPORT_RE.
RELEASE_DIR = REPO_ROOT / "data" / "release" / "v1.2"
RELEASE_STEM = "pilot_instances"


def release_pseudonymizer():
    """The RELEASE's id space: the suite runs the pseudonymiser in identity mode,
    so a test that joins the real release to the real raw DB must map under the
    private key file (skipped when absent)."""
    from temporal_hypo.core.pseudonym import KEY_PATH, Pseudonymizer
    if not KEY_PATH.exists():
        pytest.skip("data/private/pseudonym.key not present")
    return Pseudonymizer.from_hex(KEY_PATH.read_text())


def release_index(conn):
    """A CorpusIndex in the release's id space (see ``release_pseudonymizer``)."""
    from temporal_hypo.generation.corpus import CorpusIndex
    return CorpusIndex.load(conn, pseudonymizer=release_pseudonymizer())


def release_available() -> bool:
    return (RELEASE_DIR / f"{RELEASE_STEM}_answers.jsonl").exists() or \
        (RELEASE_DIR / f"{RELEASE_STEM}_answers.jsonl.gz").exists()


needs_release = pytest.mark.skipif(not release_available(),
                                   reason="data/release/v1.2 not present")
