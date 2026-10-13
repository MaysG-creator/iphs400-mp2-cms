"""T07: user management and hand-over (issue #8)."""
from __future__ import annotations

import re
import sqlite3

import pytest

from app import settings
from app.main import create_app
from conftest import DEMO_USERS, create, csrf_token, login, visible
from fastapi.testclient import TestClient

USERS = "/admin/users"
NEW_USER = "/admin/users/new"


def add_user(client, email: str = "new@example.test", name: str = "New Editor (sample)",
             role: str = "editor", password: str = "starting-pw-1", **extra):
    data = {"email": email, "name": name, "role": role, "password": password,
            "csrf_token": csrf_token(client, NEW_USER), **extra}
    return client.post(USERS, data=data, follow_redirects=False)


def user_id(email: str) -> int:
    with sqlite3.connect(settings.DATABASE_PATH) as conn:
        return conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]


def admin_id() -> int:
    return user_id(DEMO_USERS["admin"]["email"])


def editor_id() -> int:
    return user_id(DEMO_USERS["editor"]["email"])


def active_admins() -> list[str]:
    with sqlite3.connect(settings.DATABASE_PATH) as conn:
        return [row[0] for row in conn.execute(
            "SELECT email FROM users WHERE role = 'admin' AND active = 1")]


def act(client, uid: int, action: str, **data):
    """POST one of the user actions (role, deactivate, reactivate, hand-over)."""
    token = csrf_token(client, USERS)
    return client.post(f"{USERS}/{uid}/{action}", data={"csrf_token": token, **data},
                       follow_redirects=False)


def fresh_login(email: str, password: str):
    return login(TestClient(create_app()), email, password)


def row_for(html: str, email: str) -> str:
    for row in re.findall(r"<tr>.*?</tr>", html, re.S):
        if email in row:
            return visible(row)
    raise AssertionError(f"no row for {email}")


# --- create ------------------------------------------------------------------

def test_admin_creates_a_user_who_can_then_log_in(client_as):
    admin = client_as("admin")
    response = add_user(admin)
    assert response.status_code == 303
    assert "New Editor (sample)" in visible(admin.get(response.headers["location"]).text)
    assert fresh_login("new@example.test", "starting-pw-1").status_code == 303


def test_new_users_password_is_stored_as_an_argon2_hash(client_as):
    add_user(client_as("admin"))
    with sqlite3.connect(settings.DATABASE_PATH) as conn:
        stored = conn.execute("SELECT password_hash FROM users WHERE email = ?",
                              ("new@example.test",)).fetchone()[0]
    assert stored.startswith("$argon2")
    assert "starting-pw-1" not in stored


def test_user_list_shows_each_users_name_email_role_and_status(client_as):
    admin = client_as("admin")
    add_user(admin)
    html = admin.get(USERS).text
    row = row_for(html, "new@example.test")
    assert "New Editor (sample)" in row and "Editor" in row and "Active" in row
    assert "Admin" in row_for(html, DEMO_USERS["admin"]["email"])


@pytest.mark.parametrize("field,value,message", [
    ("email", "", "Enter an email address."),
    ("email", "not-an-email", "Enter an email address."),
    ("name", "  ", "Enter a name."),
    ("password", "short", "The starting password needs at least 8 characters."),
    ("role", "owner", "Choose a role."),
])
def test_create_form_explains_what_is_wrong(client_as, field, value, message):
    admin = client_as("admin")
    response = add_user(admin, **{field: value})
    assert response.status_code == 400
    assert message in visible(response.text)


def test_create_refuses_a_duplicate_email(client_as):
    admin = client_as("admin")
    response = add_user(admin, email=DEMO_USERS["editor"]["email"].upper())
    assert response.status_code == 400
    assert "A user with that email already exists." in visible(response.text)


def test_create_refuses_a_second_admin(client_as):
    admin = client_as("admin")
    response = add_user(admin, role="admin")
    assert response.status_code == 400
    assert "hand-over" in visible(response.text).lower()
    assert active_admins() == [DEMO_USERS["admin"]["email"]]


def test_create_form_never_echoes_the_password(client_as):
    response = add_user(client_as("admin"), name="", password="secret-pw-echo")
    assert response.status_code == 400
    assert "secret-pw-echo" not in response.text


# --- change role ---------------------------------------------------------------

def test_admin_changes_a_users_role_to_editor(client_as):
    admin = client_as("admin")
    add_user(admin)
    response = act(admin, user_id("new@example.test"), "role", role="editor")
    assert response.status_code == 303
    assert "Editor" in row_for(admin.get(USERS).text, "new@example.test")


def test_changing_a_role_to_admin_is_refused_and_points_to_hand_over(client_as):
    admin = client_as("admin")
    response = act(admin, editor_id(), "role", role="admin")
    assert response.status_code == 403
    text = visible(response.text)
    assert "hand-over" in text.lower()
    assert "Editors write" not in text  # the admin is not told what editors may do
    assert active_admins() == [DEMO_USERS["admin"]["email"]]


def test_changing_a_role_to_an_unknown_value_is_refused(client_as):
    admin = client_as("admin")
    response = act(admin, editor_id(), "role", role="owner")
    assert response.status_code == 400
    assert active_admins() == [DEMO_USERS["admin"]["email"]]


def test_admin_cannot_demote_themselves(client_as):
    admin = client_as("admin")
    response = act(admin, admin_id(), "role", role="editor")
    assert response.status_code == 403
    assert active_admins() == [DEMO_USERS["admin"]["email"]]


# --- deactivate --------------------------------------------------------------

def test_deactivated_user_cannot_log_in_and_keeps_authorship(client_as):
    admin, editor = client_as("admin"), client_as("editor")
    url = create(editor, "Written before graduating (sample)")
    response = act(admin, editor_id(), "deactivate")
    assert response.status_code == 303
    assert "Inactive" in row_for(admin.get(USERS).text, DEMO_USERS["editor"]["email"])
    assert fresh_login(DEMO_USERS["editor"]["email"],
                       DEMO_USERS["editor"]["password"]).status_code == 401
    assert "Author: Sample Editor" in visible(admin.get(url).text)


def test_deactivated_user_is_signed_out_of_an_open_session(client_as):
    admin, editor = client_as("admin"), client_as("editor")
    act(admin, editor_id(), "deactivate")
    response = editor.get("/admin", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].endswith("/login")


def test_reactivated_user_can_log_in_again(client_as):
    admin = client_as("admin")
    act(admin, editor_id(), "deactivate")
    assert act(admin, editor_id(), "reactivate").status_code == 303
    assert fresh_login(DEMO_USERS["editor"]["email"],
                       DEMO_USERS["editor"]["password"]).status_code == 303


def test_admin_cannot_deactivate_themselves(client_as):
    admin = client_as("admin")
    response = act(admin, admin_id(), "deactivate")
    assert response.status_code == 403
    assert admin.get("/admin").status_code == 200
    assert active_admins() == [DEMO_USERS["admin"]["email"]]


def test_unknown_user_is_404(client_as):
    assert act(client_as("admin"), 9999, "deactivate").status_code == 404


# --- hand-over -----------------------------------------------------------------

def hand_over(client, uid: int):
    """Open the confirm screen, then POST its form, as a person would."""
    confirm = client.get(f"{USERS}/{uid}/hand-over")
    assert confirm.status_code == 200, confirm.text
    token = csrf_token(client, f"{USERS}/{uid}/hand-over")
    return client.post(f"{USERS}/{uid}/hand-over", data={"csrf_token": token},
                       follow_redirects=False)


def test_hand_over_swaps_the_admin_in_one_step(client_as):
    admin = client_as("admin")
    response = hand_over(admin, editor_id())
    assert response.status_code == 303
    assert active_admins() == [DEMO_USERS["editor"]["email"]]
    # The old admin is now an editor and is refused from user management.
    assert admin.get(USERS, follow_redirects=False).status_code == 403
    new_admin = client_as("editor")
    assert new_admin.get(USERS).status_code == 200
    assert "Editor" in row_for(new_admin.get(USERS).text, DEMO_USERS["admin"]["email"])


def test_hand_over_confirm_screen_names_both_people(client_as):
    text = visible(client_as("admin").get(f"{USERS}/{editor_id()}/hand-over").text)
    assert "Sample Editor" in text and "you become an editor" in text.lower()


def test_hand_over_to_yourself_is_refused(client_as):
    admin = client_as("admin")
    assert act(admin, admin_id(), "hand-over").status_code == 403
    assert active_admins() == [DEMO_USERS["admin"]["email"]]


def test_hand_over_to_a_deactivated_user_is_refused(client_as):
    admin = client_as("admin")
    act(admin, editor_id(), "deactivate")
    assert act(admin, editor_id(), "hand-over").status_code == 403
    assert active_admins() == [DEMO_USERS["admin"]["email"]]


def test_the_database_never_holds_two_active_admins(client_as):
    from app import users
    with pytest.raises(sqlite3.IntegrityError):
        users.create_user("second@example.test", "Second Admin", "pw-second", "admin")
    assert active_admins() == [DEMO_USERS["admin"]["email"]]


# --- who can reach it ------------------------------------------------------------

def user_routes() -> list[tuple[str, str]]:
    uid = 2  # the demo editor; the route is refused before the id matters
    return [("get", USERS), ("get", NEW_USER), ("post", USERS),
            ("post", f"{USERS}/{uid}/role"), ("post", f"{USERS}/{uid}/deactivate"),
            ("post", f"{USERS}/{uid}/reactivate"), ("get", f"{USERS}/{uid}/hand-over"),
            ("post", f"{USERS}/{uid}/hand-over")]


@pytest.mark.parametrize("method,path", user_routes())
def test_editor_is_refused_on_every_user_route(client_as, method, path):
    editor = client_as("editor")
    data = {"csrf_token": csrf_token(editor, "/admin"), "role": "admin",
            "email": "sneaky@example.test", "name": "Sneaky", "password": "sneaky-pw-1"}
    kwargs = {"data": data} if method == "post" else {}
    response = getattr(editor, method)(path, follow_redirects=False, **kwargs)
    assert response.status_code == 403
    assert active_admins() == [DEMO_USERS["admin"]["email"]]


@pytest.mark.parametrize("method,path", user_routes())
def test_anonymous_visitor_is_sent_to_login(client, method, path):
    response = getattr(client, method)(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/login")


@pytest.mark.parametrize("method,path", [r for r in user_routes() if r[0] == "post"])
def test_user_forms_reject_a_post_without_a_csrf_token(client_as, method, path):
    admin = client_as("admin")
    response = admin.post(path, data={"role": "editor", "email": "x@example.test",
                                      "name": "X", "password": "long-enough"},
                          follow_redirects=False)
    assert response.status_code == 403
    assert active_admins() == [DEMO_USERS["admin"]["email"]]


@pytest.mark.parametrize("path", [USERS, NEW_USER])
def test_user_forms_carry_a_csrf_token(client_as, path):
    assert 'name="csrf_token"' in client_as("admin").get(path).text


def test_users_link_is_in_the_admin_nav_for_the_admin_only(client_as):
    def nav(role):
        page = client_as(role).get("/admin").text
        return page.split("<nav", 1)[1].split("</nav>", 1)[0]
    assert f'href="{USERS}"' in nav("admin")
    assert f'href="{USERS}"' not in nav("editor")


# --- small screens -----------------------------------------------------------

@pytest.mark.parametrize("path", [USERS, NEW_USER])
def test_user_screens_set_a_mobile_viewport(client_as, path):
    """390 px fit is checked by hand with a screenshot; this guards the basics."""
    page = client_as("admin").get(path).text
    assert 'name="viewport" content="width=device-width, initial-scale=1"' in page
