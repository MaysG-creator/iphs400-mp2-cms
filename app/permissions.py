"""Who may change which update (spec #1, Permissions).

The admin may do anything. An editor may edit any draft and delete only their
own drafts; published updates are the admin's alone. The `may_*` functions
answer for templates; the `check_*` functions raise Refused for routes, and
the refused screen shows the reason.
"""
from __future__ import annotations

import sqlite3

from app.auth import Refused

PUBLISHED_IS_ADMIN_ONLY = ("This update is published, so only the admin can change or "
                           "delete it. Editors can edit drafts only.")
OWN_DRAFTS_ONLY = "Editors can delete only their own drafts. Ask the author or the admin."


def is_admin(user: sqlite3.Row) -> bool:
    return user["role"] == "admin"


def may_edit(user: sqlite3.Row, update: sqlite3.Row) -> bool:
    return is_admin(user) or update["status"] == "draft"


def may_delete(user: sqlite3.Row, update: sqlite3.Row) -> bool:
    return is_admin(user) or (update["status"] == "draft"
                              and update["author_id"] == user["id"])


def check_edit(user: sqlite3.Row, update: sqlite3.Row) -> None:
    if not may_edit(user, update):
        raise Refused(PUBLISHED_IS_ADMIN_ONLY)


def check_delete(user: sqlite3.Row, update: sqlite3.Row) -> None:
    check_edit(user, update)
    if not may_delete(user, update):
        raise Refused(OWN_DRAFTS_ONLY)
