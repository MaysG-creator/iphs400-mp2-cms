"""Shared test fixtures.

`client` gives you the app. `client_as(role)` gives you a client that is logged
in as a seeded user of that role, so access-control tests stay one line:

    def test_editor_cannot_manage_users(client_as):
        assert client_as("editor").get("/admin/users").status_code in (302, 403)

Every test gets its own empty database with the demo admin and editor seeded.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import settings
from app.main import create_app
from app.users import DEMO_ADMIN, DEMO_EDITOR, seed_demo_users

# The same users scripts/seed_demo.py creates. Passwords come from the
# environment there; in tests they are fixed and meaningless.
DEMO_USERS = {
    "admin": {"email": DEMO_ADMIN["email"], "password": "test-admin-pw"},
    "editor": {"email": DEMO_EDITOR["email"], "password": "test-editor-pw"},
}

CSRF_FIELD = re.compile(r'name="csrf_token" value="([^"]+)"')
TAG = re.compile(r"<[^>]+>")
NEW = "/admin/updates/new"


def csrf_token(client: TestClient, path: str = "/login") -> str:
    """GET a page and return the CSRF token from its form."""
    match = CSRF_FIELD.search(client.get(path).text)
    assert match, f"no CSRF token on {path}"
    return match.group(1)


def login(client: TestClient, email: str, password: str):
    return client.post("/login", data={"email": email, "password": password,
                                       "csrf_token": csrf_token(client)},
                       follow_redirects=False)


def visible(html: str) -> str:
    """The page's text as a reader sees it, whitespace collapsed."""
    return " ".join(TAG.sub(" ", html).split())


def save_new(client: TestClient, title: str, body: str = "", **extra):
    data = {"title": title, "body": body, "csrf_token": csrf_token(client, NEW), **extra}
    return client.post("/admin/updates", data=data, follow_redirects=False)


def create(client: TestClient, title: str, body: str = "") -> str:
    """Save a new update and return its edit URL."""
    response = save_new(client, title, body)
    assert response.status_code == 303, response.text
    return response.headers["location"]


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", path)
    seed_demo_users(DEMO_USERS["admin"]["password"],
                    DEMO_USERS["editor"]["password"])
    return path


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def client_as():
    """Return a factory: client_as("editor") -> a logged-in TestClient."""

    def _login(role: str) -> TestClient:
        user = DEMO_USERS[role]
        c = TestClient(create_app())
        response = login(c, user["email"], user["password"])
        assert response.status_code in (200, 302, 303), (
            f"Login as {role} failed with {response.status_code}")
        return c

    return _login
