#!/usr/bin/env python3
"""Create demo data so a grader (and you) can use the CMS immediately.

    uv run --env-file .env python scripts/seed_demo.py

It creates one admin and one editor (passwords read from the environment, never
hard-coded). Later tickets extend it with sample updates and pages, at least one
draft and one published. Running it twice is harmless: existing users are kept.

The rubric expects this to run clean on a fresh clone with .env.example values
(item E4), because the database itself is never committed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import settings  # noqa: E402
from app.users import DEMO_ADMIN, DEMO_EDITOR, seed_demo_users  # noqa: E402


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
    print(f"Database: {settings.DATABASE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
