"""T05: pages with nav order (issue #6)."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.publish import render_site
from conftest import DEMO_USERS, csrf_token, login, visible
from test_t02_updates import save_edit, slug_on
from test_t03_publish import LINK, create, export, post_status_form, publish_new

NEW_PAGE = "/admin/pages/new"


def create_page(client: TestClient, title: str, body: str = "", **extra) -> str:
    """Save a new page and return its edit URL."""
    data = {"title": title, "body": body, "csrf_token": csrf_token(client, NEW_PAGE), **extra}
    response = client.post("/admin/pages", data=data, follow_redirects=False)
    assert response.status_code == 303, response.text
    return response.headers["location"]


def publish_page(client: TestClient, title: str, body: str = "", **extra) -> str:
    url = create_page(client, title, body, **extra)
    assert post_status_form(client, url, "publish").status_code == 303
    return url


def restarted_admin() -> TestClient:
    client = TestClient(create_app())
    login(client, DEMO_USERS["admin"]["email"], DEMO_USERS["admin"]["password"])
    return client


def nav_titles(html: str) -> list[str]:
    nav = re.search(r'<nav class="site-nav".*?</nav>', html, re.S)
    assert nav, "no site navigation"
    return [visible(a) for a in re.findall(r"<a [^>]*>.*?</a>", nav.group(0), re.S)]


# --- drafts, publishing, and permissions ----------------------------------

def test_editor_creates_a_page_as_a_draft_with_all_the_update_fields(client_as):
    editor = client_as("editor")
    page = editor.get(create_page(editor, "Roster (sample)", "A **list**.")).text
    text = visible(page)
    assert 'value="Roster (sample)"' in page
    assert "Status: Draft" in text and "Author: Sample Editor" in text
    assert slug_on(page) == "roster-sample"
    assert re.search(r"Created \d{4}-\d\d-\d\d \d\d:\d\d", text)
    assert re.search(r"Updated \d{4}-\d\d-\d\d \d\d:\d\d", text)
    assert re.search(r"Nav order: \d+", text)
    assert "<strong>list</strong>" in page
    assert "Roster (sample)" in editor.get("/admin/pages").text


def test_editor_edits_a_page_draft(client_as):
    admin, editor = client_as("admin"), client_as("editor")
    url = create_page(admin, "Schedule (sample)")
    assert save_edit(editor, url, "Schedule fixed (sample)").status_code == 303
    assert 'value="Schedule fixed (sample)"' in admin.get(url).text


def test_page_markdown_is_sanitized_in_the_preview(client_as):
    editor = client_as("editor")
    page = editor.get(create_page(editor, "XSS page", "<script>alert(1)</script>")).text
    assert "<script>alert" not in page


@pytest.mark.parametrize("verb", ["publish", "unpublish"])
def test_editor_cannot_publish_or_unpublish_a_page(client_as, verb):
    admin, editor = client_as("admin"), client_as("editor")
    url = create_page(admin, "History (sample)")
    if verb == "unpublish":
        post_status_form(admin, url, "publish")
    before = re.search(r"Status: \w+", visible(admin.get(url).text)).group(0)
    response = post_status_form(editor, url, verb)
    assert response.status_code == 403 and "Not allowed" in visible(response.text)
    assert before in visible(admin.get(url).text)


def test_editor_cannot_edit_or_delete_a_published_page(client_as):
    admin, editor = client_as("admin"), client_as("editor")
    url = publish_page(admin, "About (sample)")
    refused = editor.post(url, data={"title": "Changed", "body": "",
                                     "csrf_token": csrf_token(editor, NEW_PAGE)},
                          follow_redirects=False)
    assert refused.status_code == 403 and "Not allowed" in visible(refused.text)
    assert editor.get(f"{url}/delete").status_code == 403
    assert 'value="About (sample)"' in admin.get(url).text


def test_editor_cannot_delete_someone_elses_page_draft(client_as):
    admin, editor = client_as("admin"), client_as("editor")
    url = create_page(admin, "Admin page (sample)")
    assert editor.get(f"{url}/delete").status_code == 403
    assert editor.get(url).status_code == 200


def delete(client: TestClient, url: str):
    return client.post(f"{url}/delete", data={"csrf_token": csrf_token(client, f"{url}/delete")},
                       follow_redirects=False)


def test_editor_deletes_their_own_page_draft(client_as):
    editor = client_as("editor")
    url = create_page(editor, "Abandoned page (sample)")
    assert delete(editor, url).status_code == 303
    assert editor.get(url).status_code == 404


def test_admin_deletes_a_published_page_after_a_confirm_step(client_as, tmp_path):
    admin = client_as("admin")
    url = publish_page(admin, "Results (sample)", "Pull these words")
    confirm = visible(admin.get(f"{url}/delete").text)
    assert "Delete \u201cResults (sample)\u201d?" in confirm and "This page is published" in confirm
    assert delete(admin, url).status_code == 303
    assert "Results (sample)" not in "\n".join(export(tmp_path).values())


# --- persistence ---------------------------------------------------------------

def test_page_create_edit_publish_unpublish_delete_persist_across_a_restart(client_as):
    admin = client_as("admin")
    url = create_page(admin, "Persisted (sample)")
    assert 'value="Persisted (sample)"' in restarted_admin().get(url).text

    save_edit(admin, url, "Persisted edit (sample)", nav_order="7")
    page = restarted_admin().get(url).text
    assert 'value="Persisted edit (sample)"' in page and 'name="nav_order" value="7"' in page

    post_status_form(admin, url, "publish")
    assert "Status: Published" in visible(restarted_admin().get(url).text)
    post_status_form(admin, url, "unpublish")
    assert "Status: Draft" in visible(restarted_admin().get(url).text)

    delete(admin, url)
    assert restarted_admin().get(url).status_code == 404


# --- nav order -----------------------------------------------------------------

def test_admin_sets_a_pages_nav_order(client_as):
    admin = client_as("admin")
    url = create_page(admin, "Ordered (sample)", nav_order="3")
    assert 'name="nav_order" value="3"' in admin.get(url).text
    assert save_edit(admin, url, "Ordered (sample)", nav_order="9").status_code == 303
    assert 'name="nav_order" value="9"' in admin.get(url).text


def test_nav_order_must_be_a_whole_number(client_as):
    admin = client_as("admin")
    url = create_page(admin, "Ordered (sample)", nav_order="3")
    response = save_edit(admin, url, "Ordered (sample)", nav_order="first")
    assert response.status_code == 400 and "whole number" in visible(response.text)
    assert 'name="nav_order" value="3"' in admin.get(url).text


def test_editor_cannot_set_nav_order(client_as):
    admin, editor = client_as("admin"), client_as("editor")
    url = create_page(admin, "Ordered (sample)", nav_order="3")
    assert 'name="nav_order"' not in editor.get(url).text
    response = save_edit(editor, url, "Ordered (sample)", nav_order="1")
    assert response.status_code == 403 and "Not allowed" in visible(response.text)
    assert 'name="nav_order" value="3"' in admin.get(url).text

    data = {"title": "Sneaky (sample)", "body": "", "nav_order": "1",
            "csrf_token": csrf_token(editor, NEW_PAGE)}
    assert editor.post("/admin/pages", data=data, follow_redirects=False).status_code == 403
    assert "Sneaky (sample)" not in admin.get("/admin/pages").text


@pytest.mark.parametrize("same", ["3", "03", " 3 "])
def test_editor_may_resubmit_the_unchanged_nav_order(client_as, same):
    admin, editor = client_as("admin"), client_as("editor")
    url = create_page(admin, "Ordered (sample)", nav_order="3")
    assert save_edit(editor, url, "Ordered again (sample)", nav_order=same).status_code == 303


# --- slugs ---------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["update", "page"])
def test_admin_changes_a_slug_and_it_is_made_url_safe(client_as, kind):
    admin = client_as("admin")
    url = (create if kind == "update" else create_page)(admin, "Old name (sample)")
    assert save_edit(admin, url, "Old name (sample)", slug="New Name! 2026").status_code == 303
    assert slug_on(admin.get(url).text) == "new-name-2026"


@pytest.mark.parametrize("kind", ["update", "page"])
def test_admin_slug_change_is_kept_unique(client_as, kind):
    admin = client_as("admin")
    create(admin, "Taken")
    create_page(admin, "Also taken")
    url = (create if kind == "update" else create_page)(admin, "Mine")
    save_edit(admin, url, "Mine", slug="taken")
    first = slug_on(admin.get(url).text)
    save_edit(admin, url, "Mine", slug="also-taken")
    second = slug_on(admin.get(url).text)
    assert first not in ("taken", "mine") and first.startswith("taken")
    assert second != "also-taken" and second.startswith("also-taken")


@pytest.mark.parametrize("kind", ["update", "page"])
def test_editor_slug_change_is_refused_and_the_slug_is_unchanged(client_as, kind):
    admin, editor = client_as("admin"), client_as("editor")
    url = (create if kind == "update" else create_page)(editor, "Editor draft (sample)")
    assert 'name="slug"' not in editor.get(url).text
    response = save_edit(editor, url, "Editor draft (sample)", slug="hijacked")
    assert response.status_code == 403 and "Not allowed" in visible(response.text)
    assert slug_on(admin.get(url).text) == "editor-draft-sample"


@pytest.mark.parametrize("kind", ["update", "page"])
def test_admin_slug_with_no_letters_or_numbers_is_rejected_with_a_message(client_as, kind):
    admin = client_as("admin")
    url = (create if kind == "update" else create_page)(admin, "Kept (sample)")
    response = save_edit(admin, url, "Kept (sample)", slug="!!!")
    assert response.status_code == 400 and "at least one letter or number" in visible(response.text)
    assert slug_on(admin.get(url).text) == "kept-sample"


def test_a_page_and_an_update_with_the_same_title_get_different_slugs(client_as):
    admin = client_as("admin")
    update_slug = slug_on(admin.get(create(admin, "Schedule")).text)
    page_slug = slug_on(admin.get(create_page(admin, "Schedule")).text)
    another_update = slug_on(admin.get(create(admin, "Schedule")).text)
    assert len({update_slug, page_slug, another_update}) == 3


def test_a_page_cannot_take_the_home_pages_address(client_as):
    admin = client_as("admin")
    assert slug_on(admin.get(create_page(admin, "Index")).text) != "index"


# --- CSRF ----------------------------------------------------------------------

def test_page_forms_carry_csrf_tokens(client_as):
    admin = client_as("admin")
    assert 'name="csrf_token"' in admin.get(NEW_PAGE).text
    url = create_page(admin, "Forms (sample)")
    html = admin.get(url).text
    for action in (url, f"{url}/publish"):
        form = re.search(rf'<form[^>]*action="{re.escape(action)}".*?</form>', html, re.S)
        assert form and 'name="csrf_token"' in form.group(0)
    assert 'name="csrf_token"' in admin.get(f"{url}/delete").text


@pytest.mark.parametrize("suffix", ["", "/publish", "/delete"])
def test_page_post_without_a_csrf_token_is_rejected(client_as, suffix):
    admin = client_as("admin")
    url = create_page(admin, "Guarded page (sample)")
    response = admin.post(f"{url}{suffix}", data={"title": "Changed"}, follow_redirects=False)
    assert response.status_code == 403
    page = admin.get(url).text
    assert "Status: Draft" in visible(page) and 'value="Guarded page (sample)"' in page


# --- the export ----------------------------------------------------------------

def test_published_pages_appear_in_every_exported_pages_nav_in_nav_order(client_as, tmp_path):
    admin = client_as("admin")
    publish_page(admin, "About (sample)", nav_order="40")
    publish_page(admin, "Schedule (sample)", nav_order="10")
    publish_page(admin, "History (sample)", nav_order="30")
    publish_page(admin, "Results (sample)", nav_order="20")
    create_page(admin, "Draft page (sample)", "Secret page words", nav_order="15")
    publish_new(admin, "An update (sample)")

    files = export(tmp_path)
    html_files = [path for path in files if path.endswith(".html")]
    assert len(html_files) == 6  # home, four pages, one update
    expected = ["Schedule (sample)", "Results (sample)", "History (sample)", "About (sample)"]
    for path in html_files:
        titles = nav_titles(files[path])
        assert [t for t in titles if t != "Home"] == expected, path
    text = "\n".join(files.values())
    assert "Draft page (sample)" not in text and "Secret page words" not in text


def test_reordering_and_unpublishing_change_the_nav_on_the_next_export(client_as, tmp_path):
    admin = client_as("admin")
    first = publish_page(admin, "First (sample)", nav_order="1")
    second = publish_page(admin, "Second (sample)", nav_order="2")
    save_edit(admin, first, "First (sample)", nav_order="3")
    assert nav_titles(export(tmp_path)["index.html"])[-2:] == ["Second (sample)", "First (sample)"]

    post_status_form(admin, second, "unpublish")
    titles = nav_titles(export(tmp_path)["index.html"])
    assert "Second (sample)" not in titles and "First (sample)" in titles


def test_an_exported_page_shows_its_body_and_last_updated_date(client_as, tmp_path):
    publish_page(client_as("admin"), "Roster (sample)", "Sample **roster**.")
    page = export(tmp_path)["roster-sample.html"]
    assert "<strong>roster</strong>" in page
    assert re.search(r"Roster \(sample\) Last updated [A-Z][a-z]+ \d{1,2}, \d{4}", visible(page))


def test_nav_uses_relative_paths_and_every_link_resolves(client_as, tmp_path):
    admin = client_as("admin")
    publish_page(admin, "Schedule (sample)", "See [Kenyon](https://kenyon.edu).")
    publish_page(admin, "About (sample)")
    publish_new(admin, "An update (sample)")
    out = render_site(tmp_path / "site")

    pages = list(out.rglob("*.html"))
    assert len(pages) == 4
    for page in pages:
        for target in LINK.findall(page.read_text()):
            assert not target.startswith("/"), f"{page.name}: root-absolute {target}"
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            assert (page.parent / target).resolve().is_file(), f"{page.name}: broken {target}"


def test_slug_change_moves_the_exported_page(client_as, tmp_path):
    admin = client_as("admin")
    url = publish_page(admin, "Contact (sample)")
    save_edit(admin, url, "Contact (sample)", slug="about-contact")
    files = export(tmp_path)
    assert "about-contact.html" in files and "contact-sample.html" not in files


@pytest.mark.parametrize("body", [
    "<script>alert(1)</script>",
    '<img src="x" onerror="alert(1)">',
    "[click](javascript:alert(1))",
])
def test_exported_page_bodies_are_sanitized(client_as, tmp_path, body):
    publish_page(client_as("admin"), "XSS page (sample)", body)
    page = export(tmp_path)["xss-page-sample.html"]
    assert "<script" not in page and "onerror" not in page and 'href="javascript:' not in page
