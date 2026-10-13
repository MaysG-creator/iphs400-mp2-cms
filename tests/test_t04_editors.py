"""T04: editors are draft-only (issue #5)."""
from __future__ import annotations

import pytest

from app.main import create_app
from conftest import NEW, create, csrf_token, visible
from test_t02_updates import save_edit
from test_t03_publish import export, exported_text, post_status_form, publish_new


def test_editor_creates_an_update_and_it_is_saved_as_a_draft(client_as):
    editor = client_as("editor")
    text = visible(editor.get(create(editor, "Editor writes (sample)")).text)
    assert "Status: Draft" in text and "Author: Sample Editor" in text


def test_editor_edits_a_draft_written_by_someone_else(client_as):
    admin, editor = client_as("admin"), client_as("editor")
    url = create(admin, "Admin draft (sample)")
    assert save_edit(editor, url, "Fixed by editor (sample)").status_code == 303
    assert 'value="Fixed by editor (sample)"' in admin.get(url).text


def test_editor_cannot_edit_published_content(client_as):
    admin, editor = client_as("admin"), client_as("editor")
    url = create(admin, "Live (sample)")
    post_status_form(admin, url, "publish")
    response = editor.post(url, data={"title": "Changed", "body": "",
                                      "csrf_token": csrf_token(editor, NEW)},
                           follow_redirects=False)
    assert response.status_code == 403
    assert 'value="Live (sample)"' in admin.get(url).text


def test_refused_screen_explains_what_is_not_allowed(client_as):
    admin, editor = client_as("admin"), client_as("editor")
    url = create(admin, "Admin only (sample)")
    response = post_status_form(editor, url, "publish")
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("text/html")
    text = visible(response.text)
    assert "Not allowed" in text
    assert "Only the admin can do this." in text
    assert 'href="/admin/updates"' in response.text  # a way back, via the admin nav
    assert 'name="viewport" content="width=device-width, initial-scale=1"' in response.text


def delete(client, url: str):
    """Open the confirm screen, then POST its form, as a person would."""
    confirm = client.get(f"{url}/delete")
    assert confirm.status_code == 200, confirm.text
    return client.post(f"{url}/delete", data={"csrf_token": csrf_token(client, f"{url}/delete")},
                       follow_redirects=False)


def test_editor_deletes_their_own_draft(client_as):
    editor = client_as("editor")
    url = create(editor, "Abandoned (sample)")
    response = delete(editor, url)
    assert response.status_code == 303
    assert "Deleted the draft" in visible(editor.get(response.headers["location"]).text)
    assert editor.get(url).status_code == 404
    assert "Abandoned (sample)" not in editor.get("/admin/updates").text


def post_delete_unconfirmed(client, url: str):
    """POST the delete without the confirm screen (which may itself be refused)."""
    return client.post(f"{url}/delete", data={"csrf_token": csrf_token(client, NEW)},
                       follow_redirects=False)


def test_editor_cannot_delete_another_editors_draft(client_as):
    admin, editor = client_as("admin"), client_as("editor")
    url = create(admin, "Someone else's draft (sample)")
    refused = editor.get(f"{url}/delete")
    assert refused.status_code == 403
    assert "only their own drafts" in visible(refused.text)
    assert post_delete_unconfirmed(editor, url).status_code == 403
    assert editor.get(url).status_code == 200


@pytest.mark.parametrize("author", ["admin", "editor"])
def test_editor_cannot_delete_published_content(client_as, author):
    admin, editor = client_as("admin"), client_as("editor")
    url = create(client_as(author), "Live (sample)")
    post_status_form(admin, url, "publish")
    assert editor.get(f"{url}/delete").status_code == 403
    assert post_delete_unconfirmed(editor, url).status_code == 403
    assert "Status: Published" in visible(admin.get(url).text)


def test_admin_deletes_published_content_after_a_confirm_step(client_as, tmp_path):
    admin = client_as("admin")
    url = publish_new(admin, "Wrong score (sample)", "Delete these words")
    assert "Wrong score (sample)" in exported_text(export(tmp_path))

    confirm = visible(admin.get(f"{url}/delete").text)
    assert "Delete \u201cWrong score (sample)\u201d?" in confirm
    assert "This update is published" in confirm
    assert admin.get(url).status_code == 200  # opening the confirm screen deletes nothing

    assert delete(admin, url).status_code == 303
    assert admin.get(url).status_code == 404
    text = exported_text(export(tmp_path))
    assert "Wrong score (sample)" not in text and "Delete these words" not in text


def test_edit_screen_offers_delete_only_when_allowed(client_as):
    admin, editor = client_as("admin"), client_as("editor")
    own, others = create(editor, "Mine (sample)"), create(admin, "Theirs (sample)")
    assert f'href="{own}/delete"' in editor.get(own).text
    assert f'href="{others}/delete"' not in editor.get(others).text
    assert f'href="{others}/delete"' in admin.get(others).text


def test_editor_sees_published_content_read_only(client_as):
    admin, editor = client_as("admin"), client_as("editor")
    url = publish_new(admin, "Read only (sample)", "Live **words**")
    page = editor.get(url)
    assert page.status_code == 200
    assert "only the admin can change" in visible(page.text)
    assert f'action="{url}"' not in page.text and "<textarea" not in page.text
    assert "<strong>words</strong>" in page.text
    assert f'action="{url}"' in admin.get(url).text  # the admin can still correct it


@pytest.mark.parametrize("role", ["admin", "editor"])
@pytest.mark.parametrize("token", [None, "forged-token"])
def test_delete_without_a_valid_csrf_token_is_rejected(client_as, role, token):
    client = client_as(role)
    url = create(client, "Guarded (sample)")
    client.get(f"{url}/delete")
    data = {"csrf_token": token} if token else {}
    response = client.post(f"{url}/delete", data=data, follow_redirects=False)
    assert response.status_code == 403
    assert "Not allowed" not in visible(response.text)  # a bad form, not a role rule
    assert client.get(url).status_code == 200


def admin_routes() -> list[tuple[str, str]]:
    """(method, path) of every /admin route, read from the app's own route table."""
    paths = create_app().openapi()["paths"]
    return sorted((method.upper(), path) for path, ops in paths.items()
                  if path.startswith("/admin") for method in ops)


# Actions only the admin may take on any content, however it is written.
ADMIN_ONLY = {("POST", f"/admin/{kind}/{{item_id}}/{verb}")
              for kind in ("updates", "pages") for verb in ("publish", "unpublish")}
# User management and hand-over (T07) are the admin's alone.
ADMIN_ONLY |= {("GET", "/admin/users"), ("GET", "/admin/users/new"), ("POST", "/admin/users"),
               ("GET", "/admin/users/{user_id}/hand-over")}
ADMIN_ONLY |= {("POST", f"/admin/users/{{user_id}}/{verb}")
               for verb in ("role", "deactivate", "reactivate", "hand-over")}


@pytest.mark.parametrize("method,path", admin_routes())
def test_an_editor_is_refused_exactly_the_admin_only_routes(client_as, method, path):
    """On the editor's own draft, everything works except the admin-only actions,
    so a new admin-only route that forgets its check fails here."""
    editor = client_as("editor")
    url = path
    if "{item_id}" in path:
        kind = path.split("/")[2]  # "updates" or "pages"
        response = editor.post(f"/admin/{kind}", follow_redirects=False,
                               data={"title": "Own draft (sample)",
                                     "csrf_token": csrf_token(editor, f"/admin/{kind}/new")})
        url = path.replace("{item_id}", response.headers["location"].rsplit("/", 1)[1])
    url = url.replace("{user_id}", "1")
    response = editor.request(method, url,
                              data={"csrf_token": csrf_token(editor, NEW),
                                    "title": "Own draft (sample)"},
                              follow_redirects=False)
    if (method, path) in ADMIN_ONLY:
        assert response.status_code == 403
        assert "Not allowed" in visible(response.text)
    else:
        assert response.status_code in (200, 303)


def test_admin_only_routes_exist():
    assert ADMIN_ONLY <= set(admin_routes())


@pytest.mark.parametrize("method,path", admin_routes())
def test_every_admin_route_sends_an_anonymous_visitor_to_login(client, method, path):
    path = path.replace("{item_id}", "1").replace("{user_id}", "1")
    response = client.request(method, path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/login")
