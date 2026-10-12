"""The Jinja environment shared by the admin console routes.

Every admin template gets `csrf_token`, so each state-changing form can carry
it without each route passing it by hand, and `flash`, the one-time message a
route left with flash() before redirecting.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app import auth, settings


def flash(request: Request, kind: str, text: str) -> None:
    """Leave a message ("success" or "error") for the next page rendered."""
    request.session["flash"] = {"kind": kind, "text": text}


def _csrf(request: Request) -> dict[str, str]:
    return {"csrf_token": auth.csrf_token(request)}


def _flash(request: Request) -> dict[str, dict | None]:
    return {"flash": request.session.pop("flash", None)}


templates = Jinja2Templates(directory=str(settings.TEMPLATES),
                            context_processors=[_csrf, _flash])
