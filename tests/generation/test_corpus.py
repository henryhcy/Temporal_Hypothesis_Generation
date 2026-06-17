"""CorpusIndex mirrors core.aggregation exactly (no-divergence guard)."""

from __future__ import annotations

import random

from temporal_hypo.core import aggregation as agg
from temporal_hypo.generation import corpus
from temporal_hypo.generation.corpus import CorpusIndex

from .conftest import make_db


def _random_corpus(n=200, seed=0):
    rng = random.Random(seed)
    terms = ["A", "B", "C", "D", "E"]
    vaxes = ["Pfizer", "Moderna", "Janssen"]
    reports = []
    for i in range(n):
        present = [t for t in terms if rng.random() < 0.7]
        rng.shuffle(present)
        # random leveling: assign each present term a level, allow co-exist
        levels_map: dict[int, list[str]] = {}
        for t in present:
            lvl = rng.randrange(max(1, len(present)))
            levels_map.setdefault(lvl, []).append(t)
        levels = [levels_map[k] for k in sorted(levels_map)]
        reports.append((i + 1, rng.choice(vaxes), levels))
    return reports


def test_corpus_matches_aggregation_on_random_corpus():
    reports = _random_corpus()
    conn = make_db(reports)
    index = CorpusIndex.load(conn)

    for vax in (None, "Pfizer", "Moderna", "Janssen"):
        cohort_db = agg.get_cohort(conn, vax)
        cohort_idx = index.cohort(vax)
        assert sorted(cohort_db) == sorted(cohort_idx)

        pairs = [("A", "B"), ("B", "A"), ("C", "D"), ("A", "E")]
        for a, b in pairs:
            assert agg.precedes_fraction(conn, a, b, cohort_db) == \
                corpus.precedes_fraction(index, a, b, cohort_idx)
            assert agg.co_occurs_fraction(conn, a, b, cohort_db) == \
                corpus.co_occurs_fraction(index, a, b, cohort_idx)

        triples = [("A", "B", "C"), ("C", "B", "A"), ("A", "D", "E")]
        for a, b, c in triples:
            assert agg.sequence_fraction(conn, a, b, c, cohort_db) == \
                corpus.sequence_fraction(index, a, b, c, cohort_idx)

            db_first = agg.first_among_fractions(conn, [a, b, c], cohort_db)
            idx_first = corpus.first_among_fractions(index, [a, b, c], cohort_idx)
            _compare_among(db_first, idx_first, [a, b, c])

            db_last = agg.last_among_fractions(conn, [a, b, c], cohort_db)
            idx_last = corpus.last_among_fractions(index, [a, b, c], cohort_idx)
            _compare_among(db_last, idx_last, [a, b, c])

            db_ord = agg.ordering_distribution(conn, [a, b, c], cohort_db)
            idx_ord = corpus.ordering_distribution(index, [a, b, c], cohort_idx)
            if db_ord is None:
                assert idx_ord is None
            else:
                assert db_ord["n"] == idx_ord["n"]
                assert db_ord["tie"] == idx_ord["tie"]
                assert db_ord["modal_count"] == idx_ord["modal_count"]
                assert abs(db_ord["modal_share"] - idx_ord["modal_share"]) < 1e-12
    conn.close()


def _compare_among(db, idx, terms):
    if db is None:
        assert idx is None
        return
    assert int(db["n"]) == int(idx["n"])
    assert abs(db["tie_rate"] - idx["tie_rate"]) < 1e-12
    for t in terms:
        assert abs(db[t] - idx[t]) < 1e-12
