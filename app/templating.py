"""The Jinja environment shared by the admin console routes.

Every admin template gets `csrf_token`, so each state-changing form can carry
it without each route passing it by hand.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app import auth, settings


def _csrf(request: Request) -> dict[str, str]:
    return {"csrf_token": auth.csrf_token(request)}


templates = Jinja2Templates(directory=str(settings.TEMPLATES), context_processors=[_csrf])
