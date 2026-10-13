"""T07: user management and hand-over. Every route here is the admin's alone:
an editor is refused with 403 and an anonymous visitor is sent to login.

Exactly one admin exists at all times (CONTEXT.md). A new user is never an
admin, a role change never makes one, and the admin cannot demote or
deactivate themselves. Hand-over is the only way the admin role moves. The
rules live in app/permissions.py; the database also refuses a second active
admin (app/db.py).

CSRF is a parameter after `user` (see app/routes/content.py) so an anonymous
POST is sent to login and an editor's POST is refused before the token is read.
"""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import auth, permissions, users
from app.templating import flash, templates

router = APIRouter(prefix="/admin/users")


def users_page(request: Request, user, error: str = "", status: int = 200):
    return templates.TemplateResponse(
        request, "admin/users.html",
        {"title": "Users", "user": user, "users": users.list_users(),
         "roles": users.ROLES, "error": error},
        status_code=status,
    )


def new_user_page(request: Request, user, *, email: str = "", name: str = "",
                  role: str = "editor", error: str = "", status: int = 200):
    # The password is never sent back to the browser, not even after an error.
    return templates.TemplateResponse(
        request, "admin/user_new.html",
        {"title": "New user", "user": user, "email": email, "name": name,
         "role": role, "min_password_length": users.MIN_PASSWORD_LENGTH, "error": error},
        status_code=status,
    )


def get_or_404(user_id: int):
    target = users.get_user(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="No such user")
    return target


def back_to_list(request: Request, message: str):
    flash(request, "success", message)
    return RedirectResponse(router.prefix, status_code=303)


@router.get("", name="list_users")
def list_users(request: Request, user=auth.ADMIN):
    return users_page(request, user)


@router.get("/new", name="new_user")
def new_user(request: Request, user=auth.ADMIN):
    return new_user_page(request, user)


@router.post("", name="create_user")
def create_user(request: Request, user=auth.ADMIN, _csrf=auth.CSRF,
                email: str = Form(""), name: str = Form(""),
                role: str = Form("editor"), password: str = Form("")):
    try:
        users.add_user(email, name, password, role)
    except users.InvalidUser as exc:
        return new_user_page(request, user, email=email, name=name, role=role,
                             error=str(exc), status=400)
    return back_to_list(request, f"Added {name.strip()}. They can log in now.")


@router.post("/{user_id}/role", name="change_role")
def change_role(request: Request, user_id: int, user=auth.ADMIN, _csrf=auth.CSRF,
                role: str = Form("")):
    target = get_or_404(user_id)
    if role not in users.ROLES:
        return users_page(request, user, error="Choose a role.", status=400)
    permissions.check_role_change(user, target, role)
    users.set_role(target["id"], role)
    return back_to_list(request, f"{target['name']} is now an {role}.")


@router.post("/{user_id}/deactivate", name="deactivate_user")
def deactivate_user(request: Request, user_id: int, user=auth.ADMIN, _csrf=auth.CSRF):
    target = get_or_404(user_id)
    permissions.check_not_yourself(user, target)
    users.set_active(target["id"], False)
    return back_to_list(request, f"Deactivated {target['name']}. They can no longer "
                                 "log in; their content keeps their name.")


@router.post("/{user_id}/reactivate", name="reactivate_user")
def reactivate_user(request: Request, user_id: int, user=auth.ADMIN, _csrf=auth.CSRF):
    target = get_or_404(user_id)
    permissions.check_not_yourself(user, target)
    users.set_active(target["id"], True)
    return back_to_list(request, f"Reactivated {target['name']}. They can log in again.")


def hand_over_target(user, user_id: int):
    target = get_or_404(user_id)
    permissions.check_hand_over(user, target)
    return target


@router.get("/{user_id}/hand-over", name="confirm_hand_over")
def confirm_hand_over(request: Request, user_id: int, user=auth.ADMIN):
    return templates.TemplateResponse(
        request, "admin/user_hand_over.html",
        {"title": "Hand over admin", "user": user,
         "target": hand_over_target(user, user_id)},
    )


@router.post("/{user_id}/hand-over", name="hand_over")
def hand_over(request: Request, user_id: int, user=auth.ADMIN, _csrf=auth.CSRF):
    target = hand_over_target(user, user_id)
    try:
        users.hand_over(user["id"], target["id"])
    except users.InvalidUser as exc:
        raise auth.Refused(str(exc)) from None
    flash(request, "success", f"{target['name']} is now the admin. You are an editor.")
    return RedirectResponse("/admin", status_code=303)
