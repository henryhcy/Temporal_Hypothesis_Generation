CREATE TABLE IF NOT EXISTS reports (
    report_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    vaers_id    INTEGER UNIQUE NOT NULL,
    vaccine     TEXT NOT NULL,   -- 'Pfizer' | 'Moderna' | 'Janssen'
    narrative   TEXT NOT NULL,
    num_groups  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS level_terms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id   INTEGER NOT NULL REFERENCES reports(report_id),
    level_index INTEGER NOT NULL,   -- 0-based position in leveled order
    term        TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lt_report ON level_terms(report_id);
CREATE INDEX IF NOT EXISTS idx_lt_term   ON level_terms(term);
