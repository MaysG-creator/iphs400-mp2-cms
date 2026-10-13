"""T06: dashboard and content list (issue #7)."""
from __future__ import annotations

import re
import time

import pytest

from conftest import create, visible
from test_t02_updates import save_edit
from test_t03_publish import post_status_form
from test_t05_pages import create_page, publish_page

CONTENT = "/admin/content"


def publish_update(client, title: str) -> str:
    url = create(client, title)
    assert post_status_form(client, url, "publish").status_code == 303
    return url


@pytest.fixture
def mixed(client_as):
    """Two update drafts, one published update, one page draft, one published page."""
    admin, editor = client_as("admin"), client_as("editor")
    create(editor, "Draft update one (sample)")
    create(admin, "Draft update two (sample)")
    publish_update(admin, "Live update (sample)")
    create_page(editor, "Draft page (sample)")
    publish_page(admin, "Live page (sample)")
    return admin, editor


def row_titles(html: str) -> list[str]:
    body = re.search(r"<tbody>.*?</tbody>", html, re.S)
    if not body:
        return []
    return [visible(re.search(r"<a [^>]*>(.*?)</a>", row, re.S).group(1))
            for row in re.findall(r"<tr>.*?</tr>", body.group(0), re.S)]


def row_for(html: str, title: str) -> str:
    for row in re.findall(r"<tr>.*?</tr>", html, re.S):
        if title in row:
            return visible(row)
    raise AssertionError(f"no row for {title}")


# --- dashboard -------------------------------------------------------------

def test_dashboard_counts_match_the_data(mixed):
    admin, _ = mixed
    text = visible(admin.get("/admin").text)
    assert "Drafts 3" in text
    assert "Published updates 1" in text
    assert "Published pages 1" in text


def test_dashboard_counts_follow_a_status_change(mixed):
    admin, _ = mixed
    url = publish_update(admin, "Another live one (sample)")
    assert "Published updates 2" in visible(admin.get("/admin").text)
    post_status_form(admin, url, "unpublish")
    text = visible(admin.get("/admin").text)
    assert "Published updates 1" in text and "Drafts 4" in text


def test_a_draft_page_counts_as_a_draft_not_a_page(client_as):
    admin = client_as("admin")
    url = create_page(admin, "Roster (sample)")
    text = visible(admin.get("/admin").text)
    assert "Drafts 1" in text and "Published pages 0" in text
    post_status_form(admin, url, "publish")
    text = visible(admin.get("/admin").text)
    assert "Drafts 0" in text and "Published pages 1" in text


def test_empty_dashboard_shows_zero_counts(client_as):
    text = visible(client_as("admin").get("/admin").text)
    assert "Drafts 0" in text and "Published updates 0" in text and "Published pages 0" in text


def test_dashboard_counts_link_to_the_matching_list(client_as):
    page = client_as("admin").get("/admin").text
    assert f'href="{CONTENT}?status=draft"' in page
    assert f'href="{CONTENT}?status=published&amp;type=update"' in page
    assert f'href="{CONTENT}?status=published&amp;type=page"' in page


# --- content list ----------------------------------------------------------

def test_content_list_shows_updates_and_pages_together(mixed):
    admin, _ = mixed
    html = admin.get(CONTENT).text
    assert sorted(row_titles(html)) == sorted([
        "Draft update one (sample)", "Draft update two (sample)", "Live update (sample)",
        "Draft page (sample)", "Live page (sample)"])
    row = row_for(html, "Draft page (sample)")
    assert "Page" in row and "Draft" in row and "Sample Editor" in row
    assert re.search(r"\d{4}-\d\d-\d\d", row)
    row = row_for(html, "Live update (sample)")
    assert "Update" in row and "Published" in row and "Sample Admin" in row


def test_content_list_links_each_row_to_its_editor(mixed):
    admin, _ = mixed
    html = admin.get(CONTENT).text
    assert re.search(r'href="/admin/updates/\d+"[^>]*>Live update', html)
    assert re.search(r'href="/admin/pages/\d+"[^>]*>Live page', html)


def test_content_list_shows_the_most_recently_updated_first(client_as):
    admin = client_as("admin")
    url = create(admin, "Older update (sample)")
    create_page(admin, "Newer page (sample)")
    time.sleep(1.1)  # timestamps are kept to the second; make the edit strictly later
    save_edit(admin, url, "Older update, corrected (sample)")
    assert row_titles(admin.get(CONTENT).text) == [
        "Older update, corrected (sample)", "Newer page (sample)"]


@pytest.mark.parametrize("query,expected", [
    ("status=draft", {"Draft update one (sample)", "Draft update two (sample)",
                      "Draft page (sample)"}),
    ("status=published", {"Live update (sample)", "Live page (sample)"}),
    ("type=update", {"Draft update one (sample)", "Draft update two (sample)",
                     "Live update (sample)"}),
    ("type=page", {"Draft page (sample)", "Live page (sample)"}),
    ("status=draft&type=page", {"Draft page (sample)"}),
    ("status=published&type=update", {"Live update (sample)"}),
])
def test_content_list_filters_by_status_and_type_and_they_combine(mixed, query, expected):
    admin, _ = mixed
    assert set(row_titles(admin.get(f"{CONTENT}?{query}").text)) == expected


def test_filter_form_keeps_the_chosen_filters(mixed):
    admin, _ = mixed
    html = admin.get(f"{CONTENT}?status=draft&type=page").text
    assert re.search(r'<option value="draft" selected>', html)
    assert re.search(r'<option value="page" selected>', html)


def test_unknown_filter_value_shows_everything(mixed):
    admin, _ = mixed
    assert len(row_titles(admin.get(f"{CONTENT}?status=bogus&type=").text)) == 5


def test_filter_with_no_matches_shows_a_clear_empty_message(client_as):
    admin = client_as("admin")
    create(admin, "Only a draft (sample)")
    html = admin.get(f"{CONTENT}?status=published&type=update").text
    assert row_titles(html) == []
    assert "No published updates match these filters." in visible(html)


def test_empty_content_list_says_so(client_as):
    assert "Nothing has been written yet." in visible(client_as("admin").get(CONTENT).text)


# --- who can see it ----------------------------------------------------------

@pytest.mark.parametrize("role", ["admin", "editor"])
@pytest.mark.parametrize("path", ["/admin", CONTENT, f"{CONTENT}?status=draft&type=page"])
def test_admin_and_editor_see_the_dashboard_and_list(mixed, client_as, role, path):
    assert client_as(role).get(path).status_code == 200


def test_editor_sees_the_same_counts_and_list(mixed):
    _, editor = mixed
    assert "Drafts 3" in visible(editor.get("/admin").text)
    assert len(row_titles(editor.get(CONTENT).text)) == 5


@pytest.mark.parametrize("path", ["/admin", CONTENT, f"{CONTENT}?status=draft"])
def test_anonymous_visitor_is_sent_to_login(client, path):
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/login")


def test_content_list_is_in_the_admin_navigation(client_as):
    page = client_as("editor").get("/admin").text
    nav = page.split("<nav", 1)[1].split("</nav>", 1)[0]
    assert f'href="{CONTENT}"' in nav


# --- small screens -----------------------------------------------------------

@pytest.mark.parametrize("path", ["/admin", CONTENT])
def test_dashboard_and_list_set_a_mobile_viewport(mixed, path):
    """390 px fit is checked by hand with a screenshot; this guards the basics."""
    admin, _ = mixed
    page = admin.get(path).text
    assert 'name="viewport" content="width=device-width, initial-scale=1"' in page
