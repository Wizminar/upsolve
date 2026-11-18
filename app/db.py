"""SQLite persistence: schema and connection helpers."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    problem_id   TEXT PRIMARY KEY,          -- "<contestId><index>", e.g. 1520A
    contest_id   INTEGER NOT NULL,
    idx          TEXT NOT NULL,
    name         TEXT NOT NULL,
    rating       INTEGER,                   -- NULL for unrated problems
    tags         TEXT NOT NULL DEFAULT '[]',-- JSON list, '*special' removed
    solved_count INTEGER NOT NULL DEFAULT 0,
    dedup_key    TEXT NOT NULL              -- same statement reused in Div1/Div2 shares a key
);
CREATE INDEX IF NOT EXISTS ix_problems_rating ON problems(rating);
CREATE INDEX IF NOT EXISTS ix_problems_dedup ON problems(dedup_key);

CREATE TABLE IF NOT EXISTS problem_tags (
    problem_id TEXT NOT NULL REFERENCES problems(problem_id),
    tag        TEXT NOT NULL,
    PRIMARY KEY (problem_id, tag)
);
CREATE INDEX IF NOT EXISTS ix_problem_tags_tag ON problem_tags(tag);

CREATE TABLE IF NOT EXISTS users (
    handle            TEXT PRIMARY KEY COLLATE NOCASE,
    rating            INTEGER,
    max_rating        INTEGER,
    rank              TEXT,
    max_rank          TEXT,
    avatar            TEXT,
    country           TEXT,
    registered_at     INTEGER,
    last_synced_at    INTEGER,
    last_submission_id INTEGER NOT NULL DEFAULT 0,
    in_dataset        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS submissions (
    id               INTEGER PRIMARY KEY,   -- Codeforces submission id (dedup key)
    handle           TEXT NOT NULL COLLATE NOCASE,
    problem_id       TEXT NOT NULL,
    created_at       INTEGER NOT NULL,
    verdict          TEXT,
    language         TEXT,
    participant_type TEXT
);
CREATE INDEX IF NOT EXISTS ix_sub_handle_time ON submissions(handle, created_at);

CREATE TABLE IF NOT EXISTS attempts (
    handle        TEXT NOT NULL COLLATE NOCASE,
    problem_id    TEXT NOT NULL,
    first_at      INTEGER NOT NULL,         -- first eligible submission
    solved        INTEGER NOT NULL,         -- accepted within the 24 h window
    ever_solved   INTEGER NOT NULL,         -- accepted at any time
    solved_at     INTEGER,
    n_submissions INTEGER NOT NULL,
    in_contest    INTEGER NOT NULL,         -- first eligible submission made as a contestant
    PRIMARY KEY (handle, problem_id)
);
CREATE INDEX IF NOT EXISTS ix_attempts_handle_time ON attempts(handle, first_at);

CREATE TABLE IF NOT EXISTS rating_changes (
    handle       TEXT NOT NULL COLLATE NOCASE,
    contest_id   INTEGER NOT NULL,
    contest_name TEXT,
    rank         INTEGER,
    old_rating   INTEGER,
    new_rating   INTEGER,
    at           INTEGER,
    PRIMARY KEY (handle, contest_id)
);

CREATE TABLE IF NOT EXISTS topic_ratings (
    handle     TEXT NOT NULL COLLATE NOCASE,
    tag        TEXT NOT NULL,
    rating     REAL NOT NULL,
    attempts   INTEGER NOT NULL,
    solved     INTEGER NOT NULL,
    updated_at INTEGER,
    PRIMARY KEY (handle, tag)
);

CREATE TABLE IF NOT EXISTS topic_rating_history (
    handle TEXT NOT NULL COLLATE NOCASE,
    tag    TEXT NOT NULL,             -- '__overall__' for the overall practice rating
    at     INTEGER NOT NULL,
    rating REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_trh ON topic_rating_history(handle, tag, at);

CREATE TABLE IF NOT EXISTS training (
    handle        TEXT PRIMARY KEY COLLATE NOCASE,
    topics        TEXT NOT NULL DEFAULT '[]',
    weekly_target INTEGER NOT NULL DEFAULT 5,
    updated_at    INTEGER
);

CREATE TABLE IF NOT EXISTS recommendation_log (
    handle      TEXT NOT NULL COLLATE NOCASE,
    problem_id  TEXT NOT NULL,
    shown_at    INTEGER NOT NULL,
    probability REAL NOT NULL,
    source      TEXT NOT NULL,         -- 'model' or 'elo'
    PRIMARY KEY (handle, problem_id)
);

CREATE TABLE IF NOT EXISTS sync_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    handle          TEXT NOT NULL COLLATE NOCASE,
    status          TEXT NOT NULL,     -- queued | running | done | failed
    stage           TEXT,
    started_at      INTEGER,
    finished_at     INTEGER,
    new_submissions INTEGER NOT NULL DEFAULT 0,
    message         TEXT
);

CREATE TABLE IF NOT EXISTS plugin_store (
    plugin_id  TEXT NOT NULL,
    scope      TEXT NOT NULL,          -- a handle, or '_global'
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,          -- JSON
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (plugin_id, scope, key)
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def session(path: Path | None = None):
    conn = connect(path)
    try:
        init(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value)),
    )
