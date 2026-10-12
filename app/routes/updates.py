"""T02: write and edit update drafts. Every route here requires a signed-in user.

The editor form has two buttons: Save stores the update, Preview re-renders the
form with the sanitized Markdown and stores nothing.

CSRF is a parameter after `user` (not `dependencies=[...]`, which FastAPI runs
first) so an anonymous POST is sent to login rather than refused with 403.
"""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import auth, markdown, updates
from app.templating import flash, templates

router = APIRouter(prefix="/admin/updates")


def editor_page(request: Request, user, *, update=None, title: str = "", body: str = "",
                error: str = "", status: int = 200):
    action = f"/admin/updates/{update['id']}" if update else "/admin/updates"
    return templates.TemplateResponse(
        request, "admin/update_edit.html",
        {"title": "Edit update" if update else "New update", "user": user,
         "update": update, "action": action, "form_title": title, "body": body,
         "preview": markdown.render(body), "error": error},
        status_code=status,
    )


def get_or_404(update_id: int):
    update = updates.get_update(update_id)
    if update is None:
        raise HTTPException(status_code=404, detail="No such update")
    return update


@router.get("")
def list_updates(request: Request, user=auth.SIGNED_IN):
    return templates.TemplateResponse(
        request, "admin/update_list.html",
        {"title": "Updates", "user": user, "updates": updates.list_updates()},
    )


@router.get("/new")
def new_update(request: Request, user=auth.SIGNED_IN):
    return editor_page(request, user)


@router.post("")
def create_update(request: Request, user=auth.SIGNED_IN, _csrf=auth.CSRF,
                  title: str = Form(""), body: str = Form(""), action: str = Form("save")):
    if action == "preview":
        return editor_page(request, user, title=title, body=body)
    try:
        update_id = updates.create_update(title, body, user["id"])
    except updates.InvalidUpdate as exc:
        return editor_page(request, user, title=title, body=body, error=str(exc), status=400)
    flash(request, "success", "Draft saved.")
    return RedirectResponse(f"/admin/updates/{update_id}", status_code=303)


@router.get("/{update_id}")
def show_update(request: Request, update_id: int, user=auth.SIGNED_IN):
    update = get_or_404(update_id)
    return editor_page(request, user, update=update,
                       title=update["title"], body=update["body"])


@router.post("/{update_id}")
def save_update(request: Request, update_id: int, user=auth.SIGNED_IN, _csrf=auth.CSRF,
                title: str = Form(""), body: str = Form(""), action: str = Form("save")):
    update = get_or_404(update_id)
    if action == "preview":
        return editor_page(request, user, update=update, title=title, body=body)
    try:
        updates.edit_update(update_id, title, body)
    except updates.InvalidUpdate as exc:
        return editor_page(request, user, update=update, title=title, body=body,
                           error=str(exc), status=400)
    flash(request, "success", "Changes saved.")
    return RedirectResponse(f"/admin/updates/{update_id}", status_code=303)
