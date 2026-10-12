"""T01: log in and out (issue #2)."""
from __future__ import annotations

import logging
import runpy
import sqlite3

import pytest

from app import settings
from app.users import create_user, set_active
from conftest import DEMO_USERS, csrf_token, login

LOGIN_ERROR = "Email or password is incorrect"


def stored_hashes() -> dict[str, str]:
    with sqlite3.connect(settings.DATABASE_PATH) as conn:
        return dict(conn.execute("SELECT email, password_hash FROM users"))


@pytest.mark.parametrize("role", ["admin", "editor"])
def test_seeded_user_can_log_in_and_out(client, role):
    user = DEMO_USERS[role]

    response = login(client, user["email"], user["password"])
    assert response.status_code == 303
    assert response.headers["location"].endswith("admin")
    page = client.get("/admin")
    assert page.status_code == 200
    assert user["email"] in page.text

    response = client.post("/logout", data={"csrf_token": csrf_token(client, "/admin")},
                           follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("login")
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_wrong_password_is_refused_with_message(client):
    response = login(client, DEMO_USERS["admin"]["email"], "not-the-password")
    assert response.status_code == 401
    assert LOGIN_ERROR in response.text
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_unknown_email_gets_the_same_message(client):
    response = login(client, "nobody@example.test", "whatever")
    assert response.status_code == 401
    assert LOGIN_ERROR in response.text


def test_anonymous_visitor_to_admin_is_sent_to_login(client):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("login")
    assert 'name="password"' in client.get("/admin").text


def test_seeded_passwords_are_argon2_hashes():
    hashes = stored_hashes()
    for user in DEMO_USERS.values():
        stored = hashes[user["email"]]
        assert stored.startswith("$argon2")
        assert user["password"] not in stored


def test_login_never_logs_the_password(client, caplog):
    caplog.set_level(logging.DEBUG)
    user = DEMO_USERS["editor"]
    login(client, user["email"], user["password"])
    login(client, user["email"], "wrong-pw-xyz")
    assert user["password"] not in caplog.text
    assert "wrong-pw-xyz" not in caplog.text


@pytest.mark.parametrize("token", [None, "forged-token"])
def test_login_without_valid_csrf_token_is_rejected(client, token):
    user = DEMO_USERS["admin"]
    client.get("/login")
    data = {"email": user["email"], "password": user["password"]}
    if token:
        data["csrf_token"] = token
    response = client.post("/login", data=data, follow_redirects=False)
    assert response.status_code == 403
    assert client.get("/admin", follow_redirects=False).status_code == 303


@pytest.mark.parametrize("token", [None, "forged-token"])
def test_logout_without_valid_csrf_token_is_rejected(client_as, token):
    client = client_as("admin")
    data = {"csrf_token": token} if token else {}
    response = client.post("/logout", data=data, follow_redirects=False)
    assert response.status_code == 403
    assert client.get("/admin").status_code == 200


def test_deactivated_user_cannot_log_in(client):
    user_id = create_user("gone@example.test", "Graduated Editor", "pw-gone", "editor")
    set_active(user_id, False)
    response = login(client, "gone@example.test", "pw-gone")
    assert response.status_code == 401
    assert LOGIN_ERROR in response.text


def test_deactivated_user_loses_an_open_session(client):
    user_id = create_user("leaving@example.test", "Leaving Editor", "pw-leave", "editor")
    login(client, "leaving@example.test", "pw-leave")
    assert client.get("/admin").status_code == 200
    set_active(user_id, False)
    assert client.get("/admin", follow_redirects=False).status_code == 303


def read_env_example() -> dict[str, str]:
    values = {}
    for line in (settings.ROOT / ".env.example").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"')
    return values


def test_seed_script_runs_clean_from_env_example(client, monkeypatch, tmp_path, capsys):
    env = read_env_example()
    monkeypatch.setattr(settings, "DATABASE_PATH", tmp_path / "fresh.db")
    for key in ("CMS_ADMIN_PASSWORD", "CMS_EDITOR_PASSWORD"):
        monkeypatch.setenv(key, env[key])

    seed = runpy.run_path(str(settings.ROOT / "scripts" / "seed_demo.py"))
    assert seed["main"]() == 0
    assert seed["main"]() == 0  # running it twice is harmless

    assert env["CMS_ADMIN_PASSWORD"] not in capsys.readouterr().out
    with sqlite3.connect(settings.DATABASE_PATH) as conn:
        roles = dict(conn.execute("SELECT email, role FROM users"))
    assert roles == {DEMO_USERS[role]["email"]: role for role in ("admin", "editor")}
    for role in ("admin", "editor"):
        password = env[f"CMS_{role.upper()}_PASSWORD"]
        assert login(client, DEMO_USERS[role]["email"], password).status_code == 303


def test_env_example_is_readable_by_env_file():
    """`uv run --env-file` stops at an unquoted value containing spaces."""
    for line in (settings.ROOT / ".env.example").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            value = line.partition("=")[2].strip()
            assert " " not in value or value[0] == value[-1] == '"', line


def test_login_and_admin_screens_set_a_mobile_viewport(client_as, client):
    """390 px fit is checked by hand with a screenshot; this guards the basics."""
    viewport = 'name="viewport" content="width=device-width, initial-scale=1"'
    assert viewport in client.get("/login").text
    assert viewport in client_as("editor").get("/admin").text
