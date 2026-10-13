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


ROLES = ("admin", "editor")
MIN_PASSWORD_LENGTH = 8
USE_HAND_OVER = "There is only ever one admin. Use hand-over to pass the admin role on."


class InvalidUser(ValueError):
    """The user form cannot be saved; the message is shown to the admin."""


def create_user(email: str, name: str, password: str, role: str) -> int:
    with db.connect() as conn:
        cursor = conn.execute(
            "INSERT INTO users (email, name, password_hash, role) VALUES (?, ?, ?, ?)",
            (email.strip(), name, _hasher.hash(password), role),
        )
        return cursor.lastrowid


def add_user(email: str, name: str, password: str, role: str) -> int:
    """Check the admin's new-user form, then create the user. A new user is
    never an admin: the only way to become one is hand-over."""
    email, name = email.strip(), name.strip()
    if "@" not in email:
        raise InvalidUser("Enter an email address.")
    if not name:
        raise InvalidUser("Enter a name.")
    if role not in ROLES:
        raise InvalidUser("Choose a role.")
    if role == "admin":
        raise InvalidUser(USE_HAND_OVER)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidUser(f"The starting password needs at least "
                          f"{MIN_PASSWORD_LENGTH} characters.")
    try:
        return create_user(email, name, password, role)
    except sqlite3.IntegrityError:
        raise InvalidUser("A user with that email already exists.") from None


def list_users() -> list[sqlite3.Row]:
    with db.connect() as conn:
        return conn.execute(
            "SELECT id, email, name, role, active FROM users "
            "ORDER BY role = 'admin' DESC, active DESC, name COLLATE NOCASE"
        ).fetchall()


def get_user(user_id: int) -> sqlite3.Row | None:
    with db.connect() as conn:
        return conn.execute(
            "SELECT id, email, name, role, active FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def set_role(user_id: int, role: str) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def set_active(user_id: int, active: bool) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE users SET active = ? WHERE id = ?", (int(active), user_id))


def hand_over(from_id: int, to_id: int) -> None:
    """Demote the current admin and promote the target in one transaction, so
    there is never a moment with two admins or none."""
    with db.connect() as conn:
        conn.execute("UPDATE users SET role = 'editor' WHERE id = ?", (from_id,))
        conn.execute("UPDATE users SET role = 'admin' WHERE id = ? AND active = 1", (to_id,))
        if conn.execute("SELECT changes()").fetchone()[0] != 1:
            raise InvalidUser("Hand-over needs an active user to receive the admin role.")


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
