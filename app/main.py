"""The FastAPI application.

The admin console answers at /admin (behind login) and the public preview at /.
Routes live in their own modules under app/routes/ and are included here. Keep
this file small.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app import auth, settings
from app.publish import render_home
from app.content import PAGES, UPDATES
from app.routes import admin, login, users
from app.routes.content import content_router
from app.templating import templates


def create_app() -> FastAPI:
    app = FastAPI(title="IPHS 400 MP2 CMS")
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY,
                       session_cookie="cms_session", same_site="strict")

    @app.exception_handler(auth.LoginRequired)
    def send_to_login(request: Request, exc: auth.LoginRequired):
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(auth.Refused)
    def refused_screen(request: Request, exc: auth.Refused):
        return templates.TemplateResponse(
            request, "admin/refused.html",
            {"title": "Not allowed", "reason": exc.detail,
             "user": auth.signed_in_user(request)},
            status_code=403,
        )

    app.include_router(login.router)
    app.include_router(admin.router)
    app.include_router(content_router(UPDATES))
    app.include_router(content_router(PAGES))
    app.include_router(users.router)

    @app.get("/", response_class=HTMLResponse)
    def public_home():
        # A quick look at the home page. The full site, with its stylesheet
        # and update pages, is what `cms publish` writes to site/.
        return render_home()

    return app


app = create_app()
