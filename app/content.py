"""Updates and pages: the two kinds of content (see CONTEXT.md).

Both have the same fields and rules: a title, a slug, a Markdown body, a status
(draft or published), an author, and created and updated timestamps. Pages add
a nav order. New content is always a draft.

A slug is made from the title on first save and changes only when the admin
asks. Slugs are unique across updates and pages together, because both are
files in the same exported site; "index" is reserved for the home page.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import datetime, timezone

from app import db


class InvalidContent(ValueError):
    """The form cannot be saved; the message is shown to the user."""


TABLES = ("posts", "pages")
RESERVED_SLUGS = {"index"}


def slugify(text: str) -> str:
    # Strip accents (é -> e); any other non-ASCII character separates words.
    plain = "".join(c for c in unicodedata.normalize("NFKD", text)
                    if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def _unique_slug(conn: sqlite3.Connection, text: str, fallback: str,
                 keep: str | None = None) -> str:
    """A free slug for `text`. `keep` is the item's own current slug, not a clash."""
    base = slugify(text) or fallback
    taken = set(RESERVED_SLUGS)
    for table in TABLES:
        taken |= {row["slug"] for row in conn.execute(
            f"SELECT slug FROM {table} WHERE slug = ? OR slug LIKE ?", (base, f"{base}-%"))}
    taken.discard(keep)
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    return slug


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise InvalidContent("The title cannot be empty.")
    return title


def parse_nav_order(value: str) -> int:
    try:
        return int(value.strip())
    except ValueError:
        raise InvalidContent("Nav order must be a whole number, like 10.") from None


class Store:
    """One kind of content, kept in its own table."""

    def __init__(self, table: str, noun: str, plural: str, *, published_order: str,
                 has_nav_order: bool = False):
        self.table, self.noun, self.plural = table, noun, plural
        self.has_nav_order = has_nav_order
        self._published_order = published_order
        nav = f"{table}.nav_order, " if has_nav_order else ""
        self._select = (
            f"SELECT {table}.id, title, slug, body, status, {table}.created_at, updated_at, "
            f"{nav}{table}.author_id, users.name AS author "
            f"FROM {table} JOIN users ON users.id = {table}.author_id"
        )

    def create(self, title: str, body: str, author_id: int,
               nav_order: int | None = None) -> int:
        title = _clean_title(title)
        now = _now()
        with db.connect() as conn:
            columns = ["title", "slug", "body", "status", "author_id", "created_at", "updated_at"]
            values = [title, _unique_slug(conn, title, self.noun), body, "draft",
                      author_id, now, now]
            if self.has_nav_order:
                if nav_order is None:  # a new page goes to the end of the menu
                    nav_order = conn.execute(
                        f"SELECT COALESCE(MAX(nav_order), 0) + 1 FROM {self.table}").fetchone()[0]
                columns.append("nav_order")
                values.append(nav_order)
            cursor = conn.execute(
                f"INSERT INTO {self.table} ({', '.join(columns)}) "
                f"VALUES ({', '.join('?' * len(values))})", values)
            return cursor.lastrowid

    def edit(self, item_id: int, title: str, body: str, *, slug: str | None = None,
             nav_order: int | None = None) -> None:
        """Save an edit. A new slug is made URL-safe and unique; None or blank
        keeps the current one."""
        title = _clean_title(title)
        changes = {"title": title, "body": body, "updated_at": _now()}
        with db.connect() as conn:
            if slug is not None:
                current = conn.execute(f"SELECT slug FROM {self.table} WHERE id = ?",
                                       (item_id,)).fetchone()
                if slug.strip() and not slugify(slug):
                    raise InvalidContent("A slug needs at least one letter or number.")
                if current and slugify(slug) not in ("", current["slug"]):
                    changes["slug"] = _unique_slug(conn, slug, self.noun, keep=current["slug"])
            if nav_order is not None and self.has_nav_order:
                changes["nav_order"] = nav_order
            conn.execute(
                f"UPDATE {self.table} SET {', '.join(f'{k} = ?' for k in changes)} WHERE id = ?",
                (*changes.values(), item_id))

    def publish(self, item_id: int) -> None:
        """Mark published. Going live counts as an update, so fans see a fresh date."""
        with db.connect() as conn:
            conn.execute(f"UPDATE {self.table} SET status = 'published', updated_at = ? "
                         "WHERE id = ?", (_now(), item_id))

    def unpublish(self, item_id: int) -> None:
        """Back to draft. The next `cms publish` removes it from the site."""
        with db.connect() as conn:
            conn.execute(f"UPDATE {self.table} SET status = 'draft' WHERE id = ?", (item_id,))

    def delete(self, item_id: int) -> None:
        """Gone for good. If it was published, the next `cms publish` removes it."""
        with db.connect() as conn:
            conn.execute(f"DELETE FROM {self.table} WHERE id = ?", (item_id,))

    def get(self, item_id: int) -> sqlite3.Row | None:
        with db.connect() as conn:
            return conn.execute(f"{self._select} WHERE {self.table}.id = ?",
                                (item_id,)).fetchone()

    def list_all(self, status: str | None = None) -> list[sqlite3.Row]:
        """Every item, or only those with `status`, most recently updated first."""
        where, args = ("WHERE status = ?", (status,)) if status else ("", ())
        with db.connect() as conn:
            return conn.execute(f"{self._select} {where} "
                                f"ORDER BY updated_at DESC, {self.table}.id DESC",
                                args).fetchall()

    def count(self, status: str | None = None) -> int:
        where, args = ("WHERE status = ?", (status,)) if status else ("", ())
        with db.connect() as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {self.table} {where}",
                                args).fetchone()[0]

    def list_published(self) -> list[sqlite3.Row]:
        """What `cms publish` exports, in the order the public site shows it."""
        with db.connect() as conn:
            return conn.execute(f"{self._select} WHERE status = 'published' "
                                f"ORDER BY {self._published_order}").fetchall()


# The home page orders updates by when they were first written, not updated_at,
# so a correction never jumps above a newer update (CONTEXT.md, Decisions).
UPDATES = Store("posts", "update", "updates",
                published_order="posts.created_at DESC, posts.id DESC")
PAGES = Store("pages", "page", "pages", has_nav_order=True,
              published_order="pages.nav_order, pages.title, pages.id")

STORES = {store.noun: store for store in (UPDATES, PAGES)}
STATUSES = ("draft", "published")


def list_content(status: str | None = None, noun: str | None = None) -> list[dict]:
    """Updates and pages together, most recently updated first, for the content
    list. `status` and `noun` ("update" or "page") filter and combine; None means any.
    Each row's `kind` is its Store, as on the editor screens."""
    items = [{**row, "kind": store} for store in STORES.values() if noun in (None, store.noun)
             for row in store.list_all(status)]
    return sorted(items, key=lambda item: item["updated_at"], reverse=True)


def dashboard_counts() -> dict[str, int]:
    """Drafts of either kind, published updates, and published pages. A draft
    counts once, as a draft, whatever its kind."""
    return {"drafts": sum(store.count("draft") for store in STORES.values()),
            "published_updates": UPDATES.count("published"),
            "published_pages": PAGES.count("published")}
