"""Sessions, CSRF tokens, and the signed-in user.

The session lives in a signed cookie (Starlette's SessionMiddleware). It holds
only the user id and the CSRF token, never a password.
"""
from __future__ import annotations

import hmac
import secrets
import sqlite3

from fastapi import Depends, HTTPException, Request

from app import users


class LoginRequired(Exception):
    """Raised for an anonymous visitor; main.py turns it into a redirect."""


class Refused(HTTPException):
    """A signed-in user tried something their role does not allow. main.py
    shows the "not allowed" screen with this reason, as a 403."""

    def __init__(self, reason: str):
        super().__init__(status_code=403, detail=reason)


def csrf_token(request: Request) -> str:
    """Return this session's CSRF token, creating one if needed."""
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


async def check_csrf(request: Request) -> None:
    """Dependency for every state-changing route: reject a missing or wrong token."""
    form = await request.form()
    sent = form.get("csrf_token")
    expected = request.session.get("csrf_token")
    if not (isinstance(sent, str) and expected
            and hmac.compare_digest(sent, expected)):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")


def signed_in_user(request: Request) -> sqlite3.Row | None:
    """The signed-in, still-active user, or None."""
    user_id = request.session.get("user_id")
    return users.get_active_user(user_id) if user_id else None


def current_user(request: Request) -> sqlite3.Row:
    """Dependency for every admin screen: the signed-in, still-active user."""
    user = signed_in_user(request)
    if user is None:
        request.session.pop("user_id", None)
        raise LoginRequired
    return user


def admin_user(user: sqlite3.Row = Depends(current_user)) -> sqlite3.Row:
    """Dependency for admin-only actions: an editor is refused with 403."""
    if user["role"] != "admin":
        raise Refused("Only the admin can do this.")
    return user


def start_session(request: Request, user: sqlite3.Row) -> None:
    """Begin a fresh session for the user, with a new CSRF token."""
    request.session.clear()
    request.session["user_id"] = user["id"]
    csrf_token(request)


def end_session(request: Request) -> None:
    request.session.clear()


CSRF = Depends(check_csrf)
SIGNED_IN = Depends(current_user)
ADMIN = Depends(admin_user)
