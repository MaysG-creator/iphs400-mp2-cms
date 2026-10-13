"""Write, edit, publish, unpublish, and delete updates and pages.

content_router(store) builds the same routes for each kind of content, so
pages follow exactly the rules updates do. Every route requires a signed-in
user; publish and unpublish require the admin, and editing or deleting is
checked against app/permissions.py. Only the admin may change a slug or set a
page's nav order.

The editor form has two buttons: Save stores the item, Preview re-renders the
form with the sanitized Markdown and stores nothing. Publishing only marks the
item; it reaches the public site at the next `cms publish` and `cms deploy`.

CSRF is a parameter after `user` (not `dependencies=[...]`, which FastAPI runs
first) so an anonymous POST is sent to login rather than refused with 403.
"""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import auth, markdown, permissions
from app.content import InvalidContent, Store, parse_nav_order
from app.templating import flash, templates


def content_router(store: Store) -> APIRouter:
    prefix = f"/admin/{store.plural}"
    noun = store.noun
    router = APIRouter(prefix=prefix)

    def editor_page(request: Request, user, *, item=None, title: str = "", body: str = "",
                    slug: str | None = None, nav_order: str | None = None,
                    error: str = "", status: int = 200):
        may_edit = item is None or permissions.may_edit(user, item)
        if nav_order is None and item is not None and store.has_nav_order:
            nav_order = str(item["nav_order"])
        return templates.TemplateResponse(
            request, "admin/content_edit.html",
            {"title": f"Edit {noun}" if item else f"New {noun}", "user": user,
             "kind": store, "item": item,
             "action": f"{prefix}/{item['id']}" if item else prefix,
             "form_title": title, "body": body,
             "slug": item["slug"] if slug is None and item else slug or "",
             "nav_order": nav_order or "",
             "preview": markdown.render(body), "error": error,
             "may_delete": item is not None and permissions.may_delete(user, item),
             "refused_reason": "" if may_edit else permissions.PUBLISHED_IS_ADMIN_ONLY},
            status_code=status,
        )

    def get_or_404(item_id: int):
        item = store.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"No such {noun}")
        return item

    def admin_fields(user, item, slug: str | None, nav_order: str | None):
        """Check and parse the admin-only fields; None means leave unchanged."""
        if not store.has_nav_order:
            nav_order = None
        permissions.check_admin_fields(user, item, slug=slug, nav_order=nav_order)
        if not permissions.is_admin(user):
            return None, None
        parsed = parse_nav_order(nav_order) if nav_order and nav_order.strip() else None
        return slug, parsed

    @router.get("", name=f"list_{store.plural}")
    def list_items(request: Request, user=auth.SIGNED_IN):
        return templates.TemplateResponse(
            request, "admin/content_list.html",
            {"title": store.plural.capitalize(), "user": user, "kind": store,
             "items": store.list_all()},
        )

    @router.get("/new", name=f"new_{noun}")
    def new_item(request: Request, user=auth.SIGNED_IN):
        return editor_page(request, user)

    @router.post("", name=f"create_{noun}")
    def create_item(request: Request, user=auth.SIGNED_IN, _csrf=auth.CSRF,
                    title: str = Form(""), body: str = Form(""),
                    nav_order: str | None = Form(None), action: str = Form("save")):
        if action == "preview":
            return editor_page(request, user, title=title, body=body, nav_order=nav_order)
        try:
            _, order = admin_fields(user, None, None, nav_order)
            item_id = store.create(title, body, user["id"], nav_order=order)
        except InvalidContent as exc:
            return editor_page(request, user, title=title, body=body, nav_order=nav_order,
                               error=str(exc), status=400)
        flash(request, "success", "Draft saved.")
        return RedirectResponse(f"{prefix}/{item_id}", status_code=303)

    @router.get("/{item_id}", name=f"show_{noun}")
    def show_item(request: Request, item_id: int, user=auth.SIGNED_IN):
        item = get_or_404(item_id)
        return editor_page(request, user, item=item, title=item["title"], body=item["body"])

    @router.post("/{item_id}", name=f"save_{noun}")
    def save_item(request: Request, item_id: int, user=auth.SIGNED_IN, _csrf=auth.CSRF,
                  title: str = Form(""), body: str = Form(""), slug: str | None = Form(None),
                  nav_order: str | None = Form(None), action: str = Form("save")):
        item = get_or_404(item_id)
        permissions.check_edit(user, item)
        form = {"title": title, "body": body, "slug": slug, "nav_order": nav_order}
        if action == "preview":
            return editor_page(request, user, item=item, **form)
        try:
            new_slug, order = admin_fields(user, item, slug, nav_order)
            store.edit(item_id, title, body, slug=new_slug, nav_order=order)
        except InvalidContent as exc:
            return editor_page(request, user, item=item, **form, error=str(exc), status=400)
        flash(request, "success", "Changes saved.")
        return RedirectResponse(f"{prefix}/{item_id}", status_code=303)

    def change_status(request: Request, item_id: int, change, message: str):
        get_or_404(item_id)
        change(item_id)
        flash(request, "success", message)
        return RedirectResponse(f"{prefix}/{item_id}", status_code=303)

    @router.post("/{item_id}/publish", name=f"publish_{noun}")
    def publish_item(request: Request, item_id: int, user=auth.ADMIN, _csrf=auth.CSRF):
        return change_status(request, item_id, store.publish,
                             "Published. Run cms publish and cms deploy to put it live.")

    @router.post("/{item_id}/unpublish", name=f"unpublish_{noun}")
    def unpublish_item(request: Request, item_id: int, user=auth.ADMIN, _csrf=auth.CSRF):
        return change_status(request, item_id, store.unpublish,
                             "Unpublished. Run cms publish and cms deploy to take it down.")

    @router.get("/{item_id}/delete", name=f"confirm_delete_{noun}")
    def confirm_delete(request: Request, item_id: int, user=auth.SIGNED_IN):
        item = get_or_404(item_id)
        permissions.check_delete(user, item)
        return templates.TemplateResponse(
            request, "admin/content_delete.html",
            {"title": f"Delete {noun}", "user": user, "kind": store, "item": item},
        )

    @router.post("/{item_id}/delete", name=f"delete_{noun}")
    def delete_item(request: Request, item_id: int, user=auth.SIGNED_IN, _csrf=auth.CSRF):
        item = get_or_404(item_id)
        permissions.check_delete(user, item)
        store.delete(item_id)
        if item["status"] == "published":
            flash(request, "success", f"Deleted “{item['title']}”. "
                                      "Run cms publish and cms deploy to take it down.")
        else:
            flash(request, "success", f"Deleted the draft “{item['title']}”.")
        return RedirectResponse(prefix, status_code=303)

    return router
