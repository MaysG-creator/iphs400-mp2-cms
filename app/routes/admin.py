"""The admin console home. Every route here requires a signed-in user."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app import auth
from app.templating import templates

router = APIRouter()


@router.get("/admin")
def admin_home(request: Request, user=auth.SIGNED_IN):
    return templates.TemplateResponse(
        request, "admin/hello.html", {"title": "Admin", "user": user},
    )
