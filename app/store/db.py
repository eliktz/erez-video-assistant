"""SQLite connection and schema. One file, no server, inspectable with `sqlite3 data/erez.db`."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id            TEXT PRIMARY KEY,
    platform      TEXT NOT NULL,
    native_id     TEXT NOT NULL,
    url           TEXT NOT NULL,
    creator       TEXT,
    caption       TEXT,
    posted_at     TEXT,
    views         INTEGER,
    likes         INTEGER,
    comments      INTEGER,
    source        TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id       TEXT NOT NULL REFERENCES videos(id),
    rubric_version TEXT NOT NULL,
    payload_json   TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    UNIQUE(video_id, rubric_version)
);

CREATE TABLE IF NOT EXISTS digests (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    for_date   TEXT NOT NULL UNIQUE,
    body_he    TEXT,
    html_path  TEXT,
    sent_at    TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_usage (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    provider   TEXT NOT NULL,
    operation  TEXT NOT NULL,
    units      REAL NOT NULL,
    cost_usd   REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_videos_posted ON videos(posted_at);
CREATE INDEX IF NOT EXISTS idx_usage_created ON provider_usage(created_at);
"""


def connect(path: str) -> sqlite3.Connection:
    """Open the database, creating the file and schema if needed."""
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
