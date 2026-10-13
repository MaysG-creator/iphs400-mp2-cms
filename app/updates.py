"""Updates: team news items, stored as posts.

New updates are always drafts. The slug is made from the title on first save,
kept unique, and never changed by an edit.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import datetime, timezone

from app import db


class InvalidUpdate(ValueError):
    """The form cannot be saved; the message is shown to the user."""


_SELECT = (
    "SELECT posts.id, title, slug, body, status, posts.created_at, updated_at, "
    "posts.author_id, users.name AS author FROM posts JOIN users ON users.id = posts.author_id"
)


def slugify(title: str) -> str:
    # Strip accents (é -> e); any other non-ASCII character separates words.
    plain = "".join(c for c in unicodedata.normalize("NFKD", title)
                    if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-") or "update"


def _unique_slug(conn: sqlite3.Connection, title: str) -> str:
    base = slugify(title)
    taken = {row["slug"] for row in conn.execute(
        "SELECT slug FROM posts WHERE slug = ? OR slug LIKE ?", (base, f"{base}-%"))}
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    return slug


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise InvalidUpdate("The title cannot be empty.")
    return title


def create_update(title: str, body: str, author_id: int) -> int:
    title = _clean_title(title)
    now = _now()
    with db.connect() as conn:
        cursor = conn.execute(
            "INSERT INTO posts (title, slug, body, status, author_id, created_at, updated_at) "
            "VALUES (?, ?, ?, 'draft', ?, ?, ?)",
            (title, _unique_slug(conn, title), body, author_id, now, now),
        )
        return cursor.lastrowid


def edit_update(update_id: int, title: str, body: str) -> None:
    title = _clean_title(title)
    with db.connect() as conn:
        conn.execute(
            "UPDATE posts SET title = ?, body = ?, updated_at = ? WHERE id = ?",
            (title, body, _now(), update_id),
        )


def publish(update_id: int) -> None:
    """Mark published. Going live counts as an update, so fans see a fresh date."""
    with db.connect() as conn:
        conn.execute("UPDATE posts SET status = 'published', updated_at = ? WHERE id = ?",
                     (_now(), update_id))


def unpublish(update_id: int) -> None:
    """Back to draft. The next `cms publish` removes it from the site."""
    with db.connect() as conn:
        conn.execute("UPDATE posts SET status = 'draft' WHERE id = ?", (update_id,))


def delete_update(update_id: int) -> None:
    """Gone for good. If it was published, the next `cms publish` removes it."""
    with db.connect() as conn:
        conn.execute("DELETE FROM posts WHERE id = ?", (update_id,))


def get_update(update_id: int) -> sqlite3.Row | None:
    with db.connect() as conn:
        return conn.execute(f"{_SELECT} WHERE posts.id = ?", (update_id,)).fetchone()


def list_published() -> list[sqlite3.Row]:
    """What `cms publish` exports: published updates, newest written first.

    Ordered by created_at, not updated_at, so a correction never jumps above a
    newer update (CONTEXT.md, Decisions)."""
    with db.connect() as conn:
        return conn.execute(f"{_SELECT} WHERE status = 'published' "
                            "ORDER BY posts.created_at DESC, posts.id DESC").fetchall()


def list_updates() -> list[sqlite3.Row]:
    with db.connect() as conn:
        return conn.execute(f"{_SELECT} ORDER BY updated_at DESC, posts.id DESC").fetchall()
