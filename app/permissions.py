"""Who may change which update or page (spec #1, Permissions).

The admin may do anything. An editor may edit any draft and delete only their
own drafts; published content is the admin's alone, and so are slugs and nav
order. Users are the admin's alone too, and there is always exactly one admin:
the admin never demotes or deactivates themselves, and the role only moves by
hand-over to another active user. The `may_*` functions answer for templates; the `check_*` functions
raise Refused for routes, and the refused screen shows the reason.
"""
from __future__ import annotations

import sqlite3

from app.auth import Refused
from app.users import USE_HAND_OVER

PUBLISHED_IS_ADMIN_ONLY = ("This is published, so only the admin can change or "
                           "delete it. Editors can edit drafts only.")
OWN_DRAFTS_ONLY = "Editors can delete only their own drafts. Ask the author or the admin."
SLUG_IS_ADMIN_ONLY = "Only the admin can change a slug."
NAV_ORDER_IS_ADMIN_ONLY = "Only the admin can set a page's nav order."
NOT_YOURSELF = ("You cannot demote or deactivate yourself. Use hand-over on another "
                "user to pass the admin role on.")
HAND_OVER_NEEDS_ACTIVE_USER = ("Hand-over needs an active user. Reactivate them first, "
                               "or choose someone else.")


def is_admin(user: sqlite3.Row) -> bool:
    return user["role"] == "admin"


def may_edit(user: sqlite3.Row, item: sqlite3.Row) -> bool:
    return is_admin(user) or item["status"] == "draft"


def may_delete(user: sqlite3.Row, item: sqlite3.Row) -> bool:
    return is_admin(user) or (item["status"] == "draft"
                              and item["author_id"] == user["id"])


def check_edit(user: sqlite3.Row, item: sqlite3.Row) -> None:
    if not may_edit(user, item):
        raise Refused(PUBLISHED_IS_ADMIN_ONLY)


def check_delete(user: sqlite3.Row, item: sqlite3.Row) -> None:
    check_edit(user, item)
    if not may_delete(user, item):
        raise Refused(OWN_DRAFTS_ONLY)


def check_admin_fields(user: sqlite3.Row, item: sqlite3.Row | None, *,
                       slug: str | None, nav_order: str | None) -> None:
    """Refuse an editor whose form changes the slug or nav order. Sending the
    current value back unchanged is fine; `item` is None for new content."""
    if is_admin(user):
        return
    slug, nav_order = (slug or "").strip(), (nav_order or "").strip()
    if slug and (item is None or slug != item["slug"]):
        raise Refused(SLUG_IS_ADMIN_ONLY)
    if nav_order and (item is None or not _same_number(nav_order, item["nav_order"])):
        raise Refused(NAV_ORDER_IS_ADMIN_ONLY)


def _same_number(text: str, number: int) -> bool:
    try:
        return int(text) == number
    except ValueError:
        return False


def check_not_yourself(user: sqlite3.Row, target: sqlite3.Row) -> None:
    """The admin may change any user but themselves; hand-over is the way out."""
    if target["id"] == user["id"]:
        raise Refused(NOT_YOURSELF)


def check_role_change(user: sqlite3.Row, target: sqlite3.Row, role: str) -> None:
    check_not_yourself(user, target)
    if role == "admin":
        raise Refused(USE_HAND_OVER)


def check_hand_over(user: sqlite3.Row, target: sqlite3.Row) -> None:
    check_not_yourself(user, target)
    if not target["active"]:
        raise Refused(HAND_OVER_NEEDS_ACTIVE_USER)
