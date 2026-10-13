"""T02: admin writes update drafts (issue #3)."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from conftest import DEMO_USERS, NEW, create, csrf_token, login, save_new, visible

def slug_on(html: str) -> str:
    return re.search(r"Slug: (\S+)", visible(html)).group(1)


def save_edit(client: TestClient, url: str, title: str, body: str = "", **extra):
    data = {"title": title, "body": body, "csrf_token": csrf_token(client, url), **extra}
    return client.post(url, data=data, follow_redirects=False)


def test_admin_creates_a_draft_with_author_and_timestamps(client_as):
    admin = client_as("admin")
    url = create(admin, "Lords beat Denison", "A **good** night.")

    page = admin.get(url)
    assert page.status_code == 200
    assert 'value="Lords beat Denison"' in page.text
    text = visible(page.text)
    assert "Status: Draft" in text
    assert "Author: Sample Admin" in text
    assert re.search(r"Created \d{4}-\d\d-\d\d \d\d:\d\d", text)
    assert re.search(r"Updated \d{4}-\d\d-\d\d \d\d:\d\d", text)

    listing = admin.get("/admin/updates").text
    assert "Lords beat Denison" in listing and "Draft" in listing


def test_new_updates_are_drafts_even_if_the_form_says_published(client_as):
    admin = client_as("admin")
    url = create(admin, "Sneaky", "")
    save_edit(admin, url, "Sneaky", "", status="published")
    assert "Status: Draft" in visible(admin.get(url).text)


def test_slug_comes_from_title_and_stays_unique(client_as):
    admin = client_as("admin")
    first = admin.get(create(admin, "Lords Beat Denison 2–1!")).text
    second = admin.get(create(admin, "Lords Beat Denison 2–1!")).text
    slugs = [slug_on(page) for page in (first, second)]
    assert slugs[0] == "lords-beat-denison-2-1"
    assert slugs[1] != slugs[0] and slugs[1].startswith("lords-beat-denison-2-1")


def test_slug_does_not_change_when_the_title_is_edited(client_as):
    admin = client_as("admin")
    url = create(admin, "Original title")
    save_edit(admin, url, "A new title")
    page = admin.get(url).text
    assert 'value="A new title"' in page
    assert slug_on(page) == "original-title"


def test_an_edit_persists_across_a_server_restart(client_as):
    admin = client_as("admin")
    url = create(admin, "Before", "old body")
    assert save_edit(admin, url, "After", "new body").status_code == 303

    restarted = TestClient(create_app())
    login(restarted, DEMO_USERS["admin"]["email"], DEMO_USERS["admin"]["password"])
    page = restarted.get(url).text
    assert 'value="After"' in page and "new body" in page


def test_editor_shows_a_markdown_preview(client_as):
    admin = client_as("admin")
    url = create(admin, "Preview me", "Some **bold** words")
    assert "<strong>bold</strong>" in admin.get(url).text


def test_preview_button_renders_without_saving(client_as):
    admin = client_as("admin")
    response = save_new(admin, "Not yet", "# Heading", action="preview")
    assert response.status_code == 200
    assert "<h1>Heading</h1>" in response.text
    assert "Not yet" not in admin.get("/admin/updates").text


@pytest.mark.parametrize("body", [
    "<script>alert(1)</script>",
    '<img src="x" onerror="alert(1)">',
    "[click](javascript:alert(1))",
])
def test_preview_is_sanitized(client_as, body):
    admin = client_as("admin")
    for page in (save_new(admin, "XSS", body, action="preview").text,
                 admin.get(create(admin, "XSS", body)).text):
        preview = page.split('class="preview"', 1)[1]
        assert "<script" not in preview
        assert "onerror" not in preview
        assert 'href="javascript:' not in preview


def test_good_save_shows_a_success_message(client_as):
    admin = client_as("admin")
    assert "Draft saved." in visible(admin.get(create(admin, "Saved")).text)
    assert "Draft saved." not in admin.get("/admin/updates").text  # shown once


@pytest.mark.parametrize("title", ["", "   "])
def test_empty_title_shows_an_error_and_saves_nothing(client_as, title):
    admin = client_as("admin")
    response = save_new(admin, title, "body kept")
    assert response.status_code == 400
    assert "The title cannot be empty." in visible(response.text)
    assert "body kept" in response.text
    assert "body kept" not in admin.get("/admin/updates").text


def test_empty_title_on_edit_shows_an_error_and_keeps_the_old_one(client_as):
    admin = client_as("admin")
    url = create(admin, "Keep me")
    response = save_edit(admin, url, "")
    assert response.status_code == 400
    assert "The title cannot be empty." in visible(response.text)
    assert 'value="Keep me"' in admin.get(url).text


def test_unknown_update_is_not_found(client_as):
    assert client_as("admin").get("/admin/updates/999").status_code == 404


@pytest.mark.parametrize("path", ["/admin", "/admin/updates", NEW])
def test_admin_navigation_is_on_every_admin_screen(client_as, path):
    page = client_as("admin").get(path).text
    nav = page.split("<nav", 1)[1].split("</nav>", 1)[0]
    assert 'href="/admin"' in nav
    assert 'href="/admin/updates"' in nav
    assert f'href="{NEW}"' in nav
    assert 'action="/logout"' in nav


def test_navigation_is_on_the_edit_screen(client_as):
    admin = client_as("admin")
    assert 'href="/admin/updates"' in admin.get(create(admin, "Nav check")).text


@pytest.mark.parametrize("token", [None, "forged-token"])
def test_saving_without_a_valid_csrf_token_is_rejected(client_as, token):
    admin = client_as("admin")
    url = create(admin, "Guarded")
    admin.get(NEW)
    for path in ("/admin/updates", url):
        data = {"title": "Forged", "body": ""}
        if token:
            data["csrf_token"] = token
        assert admin.post(path, data=data, follow_redirects=False).status_code == 403
    assert "Forged" not in admin.get("/admin/updates").text


def test_every_form_on_the_editor_carries_a_csrf_token(client_as):
    admin = client_as("admin")
    for path in (NEW, create(admin, "Forms")):
        page = admin.get(path).text
        forms = re.findall(r"<form.*?</form>", page, re.S)
        assert forms
        for form in forms:
            assert 'name="csrf_token"' in form


@pytest.mark.parametrize("method,path", [
    ("get", "/admin/updates"), ("get", NEW), ("get", "/admin/updates/1"),
    ("post", "/admin/updates"), ("post", "/admin/updates/1"),
])
def test_anonymous_visitor_is_sent_to_login(client, method, path):
    response = getattr(client, method)(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/login")


def test_editor_screen_sets_a_mobile_viewport(client_as):
    """390 px fit is checked by hand with a screenshot; this guards the basics."""
    page = client_as("admin").get(NEW).text
    assert 'name="viewport" content="width=device-width, initial-scale=1"' in page
