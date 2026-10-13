"""T03: publish an update to the live site (issue #4)."""
from __future__ import annotations

import re
import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.publish import render_site
from conftest import DEMO_USERS, create, csrf_token, login, visible
from test_t02_updates import save_edit


def post_status_form(client: TestClient, url: str, verb: str):
    """POST the publish or unpublish form on an update's edit screen."""
    return client.post(f"{url}/{verb}", data={"csrf_token": csrf_token(client, url)},
                       follow_redirects=False)


def test_admin_publishes_a_draft_and_it_persists_across_a_restart(client_as):
    admin = client_as("admin")
    url = create(admin, "Lords win (sample)")
    response = post_status_form(admin, url, "publish")
    assert response.status_code == 303 and response.headers["location"] == url

    restarted = TestClient(create_app())
    login(restarted, DEMO_USERS["admin"]["email"], DEMO_USERS["admin"]["password"])
    assert "Status: Published" in visible(restarted.get(url).text)


def test_admin_unpublishes_and_it_persists_across_a_restart(client_as):
    admin = client_as("admin")
    url = create(admin, "Pulled (sample)")
    post_status_form(admin, url, "publish")
    assert post_status_form(admin, url, "unpublish").status_code == 303

    restarted = TestClient(create_app())
    login(restarted, DEMO_USERS["admin"]["email"], DEMO_USERS["admin"]["password"])
    assert "Status: Draft" in visible(restarted.get(url).text)


@pytest.mark.parametrize("verb,start,after", [
    ("publish", "Draft", "Draft"), ("unpublish", "Published", "Published"),
])
def test_editor_cannot_publish_or_unpublish(client_as, verb, start, after):
    admin, editor = client_as("admin"), client_as("editor")
    url = create(admin, "Admin only (sample)")
    if start == "Published":
        post_status_form(admin, url, "publish")
    assert post_status_form(editor, url, verb).status_code == 403
    assert f"Status: {after}" in visible(admin.get(url).text)


def form_posting_to(html: str, action: str) -> str:
    match = re.search(rf'<form[^>]*action="{re.escape(action)}".*?</form>', html, re.S)
    assert match, f"no form posting to {action}"
    return match.group(0)


def test_publish_and_unpublish_are_post_forms_with_csrf_tokens(client_as):
    admin = client_as("admin")
    url = create(admin, "Form check")
    form = form_posting_to(admin.get(url).text, f"{url}/publish")
    assert 'method="post"' in form and 'name="csrf_token"' in form

    post_status_form(admin, url, "publish")
    form = form_posting_to(admin.get(url).text, f"{url}/unpublish")
    assert 'method="post"' in form and 'name="csrf_token"' in form


def test_admin_unpublishes_a_published_update(client_as):
    admin = client_as("admin")
    url = create(admin, "Pull me")
    post_status_form(admin, url, "publish")
    assert post_status_form(admin, url, "unpublish").status_code == 303
    assert "Status: Draft" in visible(admin.get(url).text)


@pytest.mark.parametrize("verb", ["publish", "unpublish"])
@pytest.mark.parametrize("token", [None, "forged-token"])
def test_status_change_without_a_valid_csrf_token_is_rejected(client_as, verb, token):
    admin = client_as("admin")
    url = create(admin, "Guarded")
    if verb == "unpublish":
        post_status_form(admin, url, "publish")
    before = visible(admin.get(url).text)
    data = {"csrf_token": token} if token else {}
    assert admin.post(f"{url}/{verb}", data=data, follow_redirects=False).status_code == 403
    assert re.search(r"Status: \w+", visible(admin.get(url).text)).group(0) == \
        re.search(r"Status: \w+", before).group(0)


@pytest.mark.parametrize("verb", ["publish", "unpublish"])
def test_anonymous_status_change_is_sent_to_login(client, verb):
    response = client.post(f"/admin/updates/1/{verb}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/login")


def export(tmp_path) -> dict[str, str]:
    """Run `cms publish` into a temp folder; return {relative path: text} of every file."""
    out = render_site(tmp_path / "site")
    return {p.relative_to(out).as_posix(): p.read_text()
            for p in out.rglob("*") if p.is_file()}


def exported_text(files: dict[str, str]) -> str:
    return "\n".join(files.values())


def publish_new(client: TestClient, title: str, body: str = "") -> str:
    url = create(client, title, body)
    assert post_status_form(client, url, "publish").status_code == 303
    return url


def test_export_holds_only_published_updates(client_as, tmp_path):
    admin = client_as("admin")
    publish_new(admin, "Published sample", "Published body words")
    create(admin, "Draft sample", "Secret draft words")
    post_status_form(admin, publish_new(admin, "Pulled sample", "Pulled body words"), "unpublish")

    text = exported_text(export(tmp_path))
    assert "Published sample" in text and "Published body words" in text
    for gone in ("Draft sample", "Secret draft words", "Pulled sample", "Pulled body words"):
        assert gone not in text


def test_republishing_after_an_unpublish_removes_the_update(client_as, tmp_path):
    admin = client_as("admin")
    url = publish_new(admin, "Wrong score (sample)", "Body to pull")
    first = export(tmp_path)
    assert "Wrong score (sample)" in exported_text(first)
    assert any(path != "index.html" and path.endswith(".html") for path in first)

    post_status_form(admin, url, "unpublish")
    second = export(tmp_path)
    assert "Wrong score (sample)" not in exported_text(second)
    assert "Body to pull" not in exported_text(second)


def test_home_lists_published_updates_newest_first_with_last_updated_dates(client_as, tmp_path):
    admin = client_as("admin")
    for title in ("First sample", "Second sample", "Third sample"):
        publish_new(admin, title)

    home = visible(export(tmp_path)["index.html"])
    positions = [home.index(t) for t in ("Third sample", "Second sample", "First sample")]
    assert positions == sorted(positions)
    date = r"Last updated [A-Z][a-z]+ \d{1,2}, \d{4}"
    for title in ("First sample", "Second sample", "Third sample"):
        assert re.search(rf"{title} {date}", home)


def test_each_update_page_shows_its_last_updated_date(client_as, tmp_path):
    publish_new(client_as("admin"), "Dated sample", "Body")
    files = export(tmp_path)
    page = next(text for path, text in files.items() if path.startswith("updates/"))
    assert re.search(r"Dated sample Last updated [A-Z][a-z]+ \d{1,2}, \d{4}", visible(page))


LINK = re.compile(r'(?:href|src)="([^"]*)"')


def test_export_uses_relative_paths_and_every_internal_link_resolves(client_as, tmp_path):
    admin = client_as("admin")
    publish_new(admin, "Linked sample", "See [the site](https://kenyon.edu).")
    publish_new(admin, "Another sample")
    out = render_site(tmp_path / "site")

    pages = list(out.rglob("*.html"))
    assert len(pages) == 3
    for page in pages:
        for target in LINK.findall(page.read_text()):
            assert not target.startswith("/"), f"{page.name}: root-absolute {target}"
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            assert (page.parent / target).resolve().is_file(), f"{page.name}: broken {target}"


@pytest.mark.parametrize("body", [
    "<script>alert(1)</script>",
    '<img src="x" onerror="alert(1)">',
    "[click](javascript:alert(1))",
])
def test_exported_bodies_are_sanitized(client_as, tmp_path, body):
    publish_new(client_as("admin"), "XSS sample", body)
    text = exported_text(export(tmp_path))
    assert "<script" not in text
    assert "onerror" not in text
    assert 'href="javascript:' not in text


def test_public_site_sets_a_mobile_viewport_and_a_css_only_banner(client_as, tmp_path):
    """Look and 390 px fit are checked by hand with screenshots; this guards the basics."""
    publish_new(client_as("admin"), "Look sample")
    files = export(tmp_path)
    for path, text in files.items():
        if path.endswith(".html"):
            assert 'name="viewport" content="width=device-width, initial-scale=1"' in text
            assert 'class="banner"' in text and "<img" not in text
    assert ".banner" in files["style.css"]


def test_editing_an_older_update_does_not_move_it_above_a_newer_one(client_as, tmp_path):
    """Order is by when an update was first written, so a correction stays put."""
    admin = client_as("admin")
    older = publish_new(admin, "Older sample")
    publish_new(admin, "Newer sample")
    time.sleep(1.1)  # timestamps are kept to the second; make the edit strictly later
    assert save_edit(admin, older, "Older sample corrected").status_code == 303

    home = visible(export(tmp_path)["index.html"])
    assert home.index("Newer sample") < home.index("Older sample corrected")


def last_updated(html: str) -> str:
    return re.search(r'Updated <time datetime="([^"]+)"', html).group(1)


def test_publishing_sets_the_last_updated_time(client_as):
    """A fan judging freshness sees when the update went live, not when it was drafted."""
    admin = client_as("admin")
    url = create(admin, "Drafted earlier (sample)")
    drafted = last_updated(admin.get(url).text)
    time.sleep(1.1)
    post_status_form(admin, url, "publish")
    assert last_updated(admin.get(url).text) > drafted
