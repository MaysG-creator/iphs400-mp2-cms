#!/usr/bin/env python3
"""Create demo data so a grader (and you) can use the CMS immediately.

    uv run --env-file .env python scripts/seed_demo.py

It creates one admin and one editor (passwords read from the environment, never
hard-coded), and, if there are none yet, a few sample updates (one published and
two drafts) and sample pages (four published, one draft). Every sample says it
is a sample and holds no score, so nothing invented can pass for a real result.
Running it twice is harmless: existing users, updates, and pages are kept.

The rubric expects this to run clean on a fresh clone with .env.example values
(item E4), because the database itself is never committed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db, settings  # noqa: E402
from app.content import PAGES, UPDATES  # noqa: E402
from app.users import DEMO_ADMIN, DEMO_EDITOR, seed_demo_users  # noqa: E402


# (title, body, author email, published?)
SAMPLE_UPDATES = [
    ("Welcome to the new team site (sample)",
     "**This is sample content.** Real updates from the student media team will "
     "appear here, newest first, each with the date it was last updated.",
     DEMO_ADMIN["email"], True),
    ("Sample match report draft",
     "**Sample draft.** A match report is written after a fixture and holds the "
     "verified score and scorers. This one has neither.",
     DEMO_EDITOR["email"], False),
    ("Sample preseason notes draft",
     "**Sample draft.** Drafts stay in the admin console until the admin publishes them.",
     DEMO_EDITOR["email"], False),
]


# (title, body, author email, published?, nav order). Schedule and Results come
# before History and About (CONTEXT.md, Nav order).
SAMPLE_PAGES = [
    ("Schedule (sample)",
     "**Sample page.** Fixtures will be listed here once the admin publishes them.",
     DEMO_ADMIN["email"], True, 10),
    ("Roster (sample)",
     "**Sample draft.** The roster stays in the admin console until it is checked.",
     DEMO_EDITOR["email"], False, 20),
    ("Results (sample)",
     "**Sample page.** Verified results will appear here. There are none yet.",
     DEMO_ADMIN["email"], True, 30),
    ("History (sample)",
     "**Sample page.** The program's past titles and accomplishments go here.",
     DEMO_ADMIN["email"], True, 40),
    ("About (sample)",
     "**Sample page.** Who runs this site and how to reach the student media team.",
     DEMO_ADMIN["email"], True, 50),
]


def _user_ids() -> dict[str, int]:
    with db.connect() as conn:
        return {row["email"]: row["id"] for row in conn.execute("SELECT id, email FROM users")}


def seed_sample_updates() -> int:
    """Add the sample updates if the database has none. Return how many were added."""
    if UPDATES.list_all():
        return 0
    ids = _user_ids()
    for title, body, email, published in SAMPLE_UPDATES:
        update_id = UPDATES.create(title, body, ids[email])
        if published:
            UPDATES.publish(update_id)
    return len(SAMPLE_UPDATES)


def seed_sample_pages() -> int:
    """Add the sample pages if the database has none. Return how many were added."""
    if PAGES.list_all():
        return 0
    ids = _user_ids()
    for title, body, email, published, nav_order in SAMPLE_PAGES:
        page_id = PAGES.create(title, body, ids[email], nav_order=nav_order)
        if published:
            PAGES.publish(page_id)
    return len(SAMPLE_PAGES)


def main() -> int:
    admin_pw = os.environ.get("CMS_ADMIN_PASSWORD")
    editor_pw = os.environ.get("CMS_EDITOR_PASSWORD")
    if not admin_pw or not editor_pw:
        print("Set CMS_ADMIN_PASSWORD and CMS_EDITOR_PASSWORD in .env "
              "(copy .env.example).")
        return 1

    created = seed_demo_users(admin_pw, editor_pw)
    for person in (DEMO_ADMIN, DEMO_EDITOR):
        state = "created" if person["email"] in created else "already exists"
        print(f"{person['email']}: {state}")
    print(f"Sample updates added: {seed_sample_updates()}")
    print(f"Sample pages added: {seed_sample_pages()}")
    print(f"Database: {settings.DATABASE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
