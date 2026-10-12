"""Users: argon2 password hashing, lookup, and the demo seed.

A plain password only ever passes through these functions on its way to
argon2. It is never stored, returned, or logged.
"""
from __future__ import annotations

import sqlite3

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app import db

_hasher = PasswordHasher()
# Verified against when the email is unknown, so a miss costs the same time
# as a wrong password and does not reveal which emails exist.
_DUMMY_HASH = _hasher.hash("no-such-user")

DEMO_ADMIN = {"email": "admin@example.test", "name": "Sample Admin"}
DEMO_EDITOR = {"email": "editor@example.test", "name": "Sample Editor"}


def create_user(email: str, name: str, password: str, role: str) -> int:
    with db.connect() as conn:
        cursor = conn.execute(
            "INSERT INTO users (email, name, password_hash, role) VALUES (?, ?, ?, ?)",
            (email.strip(), name, _hasher.hash(password), role),
        )
        return cursor.lastrowid


def set_active(user_id: int, active: bool) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE users SET active = ? WHERE id = ?", (int(active), user_id))


def get_active_user(user_id: int) -> sqlite3.Row | None:
    with db.connect() as conn:
        return conn.execute(
            "SELECT id, email, name, role FROM users WHERE id = ? AND active = 1",
            (user_id,),
        ).fetchone()


def authenticate(email: str, password: str) -> sqlite3.Row | None:
    """Return the active user with this email and password, else None."""
    with db.connect() as conn:
        user = conn.execute(
            "SELECT id, email, name, role, active, password_hash FROM users "
            "WHERE email = ?",
            (email.strip(),),
        ).fetchone()
    try:
        _hasher.verify(user["password_hash"] if user else _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return None
    if not user or not user["active"]:
        return None
    return user


def seed_demo_users(admin_password: str, editor_password: str) -> list[str]:
    """Create the demo admin and editor if missing. Return the emails created."""
    created = []
    with db.connect() as conn:
        existing = {row["email"].lower() for row in conn.execute("SELECT email FROM users")}
    for person, password, role in ((DEMO_ADMIN, admin_password, "admin"),
                                   (DEMO_EDITOR, editor_password, "editor")):
        if person["email"] not in existing:
            create_user(person["email"], person["name"], password, role)
            created.append(person["email"])
    return created
