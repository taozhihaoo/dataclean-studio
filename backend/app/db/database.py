"""SQLite access: schema, connections, and the tiny persistence layer.

SQLite keeps only metadata (files, jobs, processing runs). Raw file bytes
and dataset contents stay on the filesystem, never in the database.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id                TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    stored_path       TEXT NOT NULL,
    size_bytes        INTEGER NOT NULL,
    content_kind      TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    file_id      TEXT REFERENCES files(id) ON DELETE SET NULL,
    filename     TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT 'upload',
    status       TEXT NOT NULL DEFAULT 'ready',
    row_count    INTEGER,
    column_count INTEGER,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processing_runs (
    id         TEXT PRIMARY KEY,
    job_id     TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL,
    status     TEXT NOT NULL,
    summary    TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_job ON processing_runs(job_id);
"""


def get_connection() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    """Transaction-scoped connection; commits on success, rolls back on error."""
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()
