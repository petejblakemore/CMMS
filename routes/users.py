# routes/users.py

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from db import dicts, get_db, hash_password, templates

router = APIRouter()


@router.get("/users")
async def list_users(request: Request, db: sqlite3.Connection = Depends(get_db)):
    users = dicts(db.execute("SELECT id, username, display_name, created_at FROM users ORDER BY username"))
    return templates.TemplateResponse(
        "users.html",
        {"request": request, "users": users},
    )


@router.get("/users/new")
async def new_user_form(request: Request):
    return templates.TemplateResponse(
        "user_form.html",
        {"request": request, "error": None},
    )


@router.post("/users/new")
async def create_user(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
):
    if password != password_confirm:
        return templates.TemplateResponse(
            "user_form.html",
            {"request": request, "error": "Passwords do not match."},
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            "user_form.html",
            {"request": request, "error": "Password must be at least 6 characters."},
        )

    # Check for duplicate username
    existing = db.execute("SELECT id FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
    if existing:
        return templates.TemplateResponse(
            "user_form.html",
            {"request": request, "error": f"Username '{username.strip().lower()}' already exists."},
        )

    db.execute(
        "INSERT INTO users (username, display_name, password_hash) VALUES (?, ?, ?)",
        (username.strip().lower(), display_name.strip(), hash_password(password)),
    )
    db.commit()

    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/users/{user_id}/edit")
async def edit_user_form(
    request: Request,
    user_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT id, username, display_name FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse(
        "user_edit.html",
        {"request": request, "user": dict(row), "error": None},
    )


@router.post("/users/{user_id}/edit")
async def update_user(
    request: Request,
    user_id: int,
    display_name: str = Form(...),
    new_password: Optional[str] = Form(None),
    new_password_confirm: Optional[str] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT id, username, display_name FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    user = dict(row)

    # Update display name
    db.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name.strip(), user_id))

    # Optionally update password
    if new_password:
        if new_password != new_password_confirm:
            return templates.TemplateResponse(
                "user_edit.html",
                {"request": request, "user": user, "error": "Passwords do not match."},
            )
        if len(new_password) < 6:
            return templates.TemplateResponse(
                "user_edit.html",
                {"request": request, "user": user, "error": "Password must be at least 6 characters."},
            )
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), user_id))

    db.commit()

    # Update session display name if editing yourself
    if request.session.get("user_id") == user_id:
        request.session["display_name"] = display_name.strip()

    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/users/{user_id}/delete")
async def delete_user_confirm(
    request: Request,
    user_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT id, username, display_name FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    user = dict(row)
    current_user_id = request.session.get("user_id")

    if user_id == current_user_id:
        return templates.TemplateResponse(
            "confirm_delete.html",
            {
                "request": request,
                "heading": "Cannot delete your own account",
                "message": "You cannot delete the account you are currently logged in with.",
                "warning": None,
                "details": None,
                "cancel_url": "/users",
            },
        )

    user_count = db.execute("SELECT COUNT(*) as count FROM users").fetchone()["count"]
    if user_count <= 1:
        return templates.TemplateResponse(
            "confirm_delete.html",
            {
                "request": request,
                "heading": "Cannot delete last user",
                "message": "At least one user account must exist.",
                "warning": None,
                "details": None,
                "cancel_url": "/users",
            },
        )

    return templates.TemplateResponse(
        "confirm_delete.html",
        {
            "request": request,
            "heading": f"Delete user: {user['display_name']}",
            "message": f"Are you sure you want to delete user '{user['username']}'?",
            "warning": "This action cannot be undone.",
            "details": [f"Username: {user['username']}", f"Display name: {user['display_name']}"],
            "cancel_url": "/users",
        },
    )


@router.post("/users/{user_id}/delete")
async def delete_user(
    request: Request,
    user_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    current_user_id = request.session.get("user_id")
    if user_id == current_user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    user_count = db.execute("SELECT COUNT(*) as count FROM users").fetchone()["count"]
    if user_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last user")

    cur = db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="User not found")

    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()

    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)
