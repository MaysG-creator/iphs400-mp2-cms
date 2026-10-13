"""The dashboard and the content list. Every route here requires a signed-in
user; admin and editor see the same screens."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app import auth, content
from app.templating import templates

router = APIRouter()


@router.get("/admin")
def admin_home(request: Request, user=auth.SIGNED_IN):
    return templates.TemplateResponse(
        request, "admin/dashboard.html",
        {"title": "Dashboard", "user": user, "counts": content.dashboard_counts()},
    )


@router.get("/admin/content")
def content_list(request: Request, user=auth.SIGNED_IN,
                 status: str = "", type: str = ""):
    # An unknown or blank filter means "any", so a stale link still shows something.
    status = status if status in content.STATUSES else None
    noun = type if type in content.STORES else None
    return templates.TemplateResponse(
        request, "admin/content_all.html",
        {"title": "Content", "user": user, "status": status, "noun": noun,
         "statuses": content.STATUSES, "stores": content.STORES,
         "items": content.list_content(status, noun)},
    )
