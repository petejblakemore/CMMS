# routes/auth.py
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse

from db import get_db, hash_password, templates, verify_password

router = APIRouter()


@router.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": None},
    )


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute(
        "SELECT id, username, display_name, password_hash FROM users WHERE username = ?",
        (username.strip().lower(),),
    )
    user = cur.fetchone()

    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password."},
        )

    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["display_name"] = user["display_name"] or user["username"]

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/setup")
async def setup_form(request: Request, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT COUNT(*) as count FROM users")
    if cur.fetchone()["count"] > 0:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        "setup.html",
        {"request": request, "error": None},
    )


@router.post("/setup")
async def setup_create_admin(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT COUNT(*) as count FROM users")
    if cur.fetchone()["count"] > 0:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if password != password_confirm:
        return templates.TemplateResponse(
            "setup.html",
            {"request": request, "error": "Passwords do not match."},
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            "setup.html",
            {"request": request, "error": "Password must be at least 6 characters."},
        )

    db.execute(
        "INSERT INTO users (username, display_name, password_hash) VALUES (?, ?, ?)",
        (username.strip().lower(), display_name.strip(), hash_password(password)),
    )
    db.commit()

    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
