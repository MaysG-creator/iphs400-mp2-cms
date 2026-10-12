"""The FastAPI application.

The admin console answers at /admin (behind login) and the public preview at /.
Routes live in their own modules under app/routes/ and are included here. Keep
this file small.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app import auth, settings
from app.routes import admin, login
from app.templating import templates


def create_app() -> FastAPI:
    app = FastAPI(title="IPHS 400 MP2 CMS")
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY,
                       session_cookie="cms_session", same_site="strict")

    @app.exception_handler(auth.LoginRequired)
    def send_to_login(request: Request, exc: auth.LoginRequired):
        return RedirectResponse("/login", status_code=303)

    app.include_router(login.router)
    app.include_router(admin.router)

    @app.get("/")
    def public_home(request: Request):
        return templates.TemplateResponse(
            request, "public/home.html",
            {"title": settings.SITE_TITLE, "items": []},
        )

    return app


app = create_app()
