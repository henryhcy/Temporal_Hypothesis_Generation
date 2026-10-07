-- MedTempo evaluation database (SQLite). This is the COMPLETE schema.
--
-- * Every report identifier in this database is the public VAERS report id
--   (`vaers_id`, 6-7 digits). There is no other report key.
-- * There is NO report text in this database: only the annotated timeline of
--   MedDRA terms per report, plus the vaccine.
-- * `level_terms` is the raw leveled order: `term` appears at position
--   `level_index` (0 = earliest) in the report's timeline. Several terms can
--   share a level (they co-exist), and a term can be listed at more than one
--   level of the same report.
-- * The POSITION of a term in a report is its FIRST mention. The view
--   `first_mention` already applies that rule (`level` = MIN(level_index)), so it
--   holds exactly one row per (vaers_id, term). Use it for every before / after /
--   co-exist question: A precedes B in a report when a.level < b.level, they
--   co-exist when a.level = b.level.
-- * `report_terms` is a browsing aid: one row per (report, level) with the terms
--   at that level joined by ' | ' in alphabetical order.

CREATE TABLE reports (
    vaers_id    INTEGER PRIMARY KEY,     -- VAERS report id
    vaccine     TEXT    NOT NULL,        -- 'Pfizer' | 'Moderna' | 'Janssen'
    num_stages  INTEGER NOT NULL         -- number of levels in the report's timeline
);

CREATE TABLE level_terms (
    vaers_id    INTEGER NOT NULL REFERENCES reports(vaers_id),
    level_index INTEGER NOT NULL,        -- 0-based position in the leveled order
    term        TEXT    NOT NULL         -- MedDRA preferred term, verbatim
);

CREATE INDEX idx_lt_vid  ON level_terms(vaers_id);
CREATE INDEX idx_lt_term ON level_terms(term, vaers_id);
CREATE INDEX idx_r_vax   ON reports(vaccine);

-- First-mention position of every term in every report: one row per (vaers_id, term).
CREATE VIEW first_mention AS
SELECT lt.vaers_id,
       r.vaccine,
       lt.term,
       MIN(lt.level_index) AS level
FROM level_terms lt
JOIN reports r USING (vaers_id)
GROUP BY lt.vaers_id, r.vaccine, lt.term;

-- First-mention RANK of every term: `rank` is the term's position among the
-- report's OCCUPIED first-mention levels (0 = earliest stage, dense), and
-- `n_ranks` is how many such stages the report has. Use it for questions about
-- CONSECUTIVE stages (|a.rank - b.rank| = 1) and about the EARLIER HALF of a
-- timeline (rank < (n_ranks - 1) / 2.0; a term on the exact middle rank is in
-- neither half). Ranks, not level indices: levels can have gaps.
CREATE VIEW first_mention_rank AS
SELECT f.vaers_id,
       f.vaccine,
       f.term,
       f.level,
       (SELECT COUNT(DISTINCT g.level) FROM first_mention g
         WHERE g.vaers_id = f.vaers_id AND g.level < f.level) AS rank,
       (SELECT COUNT(DISTINCT g.level) FROM first_mention g
         WHERE g.vaers_id = f.vaers_id) AS n_ranks
FROM first_mention f;

-- The raw leveled order, one row per (report, level); terms sorted alphabetically.
CREATE VIEW report_terms AS
SELECT lt.vaers_id,
       r.vaccine,
       lt.level_index,
       group_concat(lt.term, ' | ' ORDER BY lt.term) AS terms
FROM level_terms lt
JOIN reports r USING (vaers_id)
GROUP BY lt.vaers_id, r.vaccine, lt.level_index;
