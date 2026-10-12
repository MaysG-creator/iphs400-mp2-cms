"""T01: log in and out."""
from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app import auth, users
from app.templating import templates

router = APIRouter()

LOGIN_ERROR = "Email or password is incorrect. Please try again."


def login_page(request: Request, error: str = "", email: str = "", status: int = 200):
    return templates.TemplateResponse(
        request, "admin/login.html",
        {"title": "Log in", "error": error, "email": email},
        status_code=status,
    )


@router.get("/login")
def show_login(request: Request):
    return login_page(request)


@router.post("/login", dependencies=[auth.CSRF])
def log_in(request: Request, email: str = Form(""), password: str = Form("")):
    user = users.authenticate(email, password)
    if user is None:
        return login_page(request, LOGIN_ERROR, email=email, status=401)
    auth.start_session(request, user)
    return RedirectResponse("/admin", status_code=303)


@router.post("/logout", dependencies=[auth.CSRF])
def log_out(request: Request):
    auth.end_session(request)
    return RedirectResponse("/login", status_code=303)
