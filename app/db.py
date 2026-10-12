"""SQLite access. Every call opens a short-lived connection to the current
settings.DATABASE_PATH, so tests can point it at a temporary file."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator

from app import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'editor')),
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Yield a connection with the schema in place; commit on success."""
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()
