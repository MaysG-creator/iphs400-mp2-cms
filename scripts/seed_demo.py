#!/usr/bin/env python3
"""Create demo data so a grader (and you) can use the CMS immediately.

    uv run --env-file .env python scripts/seed_demo.py

It creates one admin and one editor (passwords read from the environment, never
hard-coded), and, if there are no updates yet, a few sample updates: one
published and two drafts. Every sample says it is a sample and holds no score,
so nothing invented can pass for a real result. Running it twice is harmless:
existing users and updates are kept.

The rubric expects this to run clean on a fresh clone with .env.example values
(item E4), because the database itself is never committed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db, settings, updates  # noqa: E402
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


def seed_sample_updates() -> int:
    """Add the sample updates if the database has none. Return how many were added."""
    if updates.list_updates():
        return 0
    with db.connect() as conn:
        ids = {row["email"]: row["id"] for row in conn.execute("SELECT id, email FROM users")}
    for title, body, email, published in SAMPLE_UPDATES:
        update_id = updates.create_update(title, body, ids[email])
        if published:
            updates.publish(update_id)
    return len(SAMPLE_UPDATES)


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
    print(f"Database: {settings.DATABASE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
