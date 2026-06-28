# routes/locations.py
#
# Location management routes: list, create, edit, soft delete.
# Locations form a hierarchy with parent-child relationships.

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from db import build_location_tree, dicts, get_db, get_hierarchical_locations, templates

router = APIRouter()


@router.get("/locations")
async def list_locations(request: Request, db: sqlite3.Connection = Depends(get_db)):
    locations_flat = dicts(db.execute("SELECT * FROM locations"))
    location_tree = build_location_tree(locations_flat)

    wo_counts = {
        r["location_id"]: r["wo_count"]
        for r in db.execute(
            "SELECT location_id, COUNT(*) as wo_count FROM work_orders "
            "WHERE status NOT IN ('Done', 'Cancelled') AND location_id IS NOT NULL "
            "GROUP BY location_id"
        )
    }

    return templates.TemplateResponse(
        "locations.html",
        {"request": request, "locations": location_tree, "wo_counts": wo_counts},
    )


@router.get("/locations/new")
async def new_location_form(request: Request, db: sqlite3.Connection = Depends(get_db)):
    parents = get_hierarchical_locations(db)
    return templates.TemplateResponse(
        "location_form.html",
        {"request": request, "parents": parents},
    )


@router.post("/locations/new")
async def create_location(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    parent_id: Optional[int] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    parent_val = parent_id if parent_id not in (None, 0) else None

    db.execute(
        "INSERT INTO locations (name, description, parent_id) VALUES (?, ?, ?)",
        (name.strip(), description or None, parent_val),
    )
    db.commit()

    return RedirectResponse(url="/locations", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/locations/{location_id}/edit")
async def edit_location_form(
    request: Request,
    location_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM locations WHERE id = ?", (location_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Location not found")

    location = dict(row)
    parents = [loc for loc in get_hierarchical_locations(db) if loc["id"] != location_id]

    return templates.TemplateResponse(
        "location_edit.html",
        {
            "request": request,
            "location": location,
            "parents": parents,
        },
    )


@router.post("/locations/{location_id}/edit")
async def update_location(
    request: Request,
    location_id: int,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    parent_id: Optional[int] = Form(None),
    active: Optional[int] = Form(1),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT id FROM locations WHERE id = ?", (location_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Location not found")

    parent_val = parent_id if parent_id not in (None, 0) else None

    if parent_val == location_id:
        parent_val = None

    db.execute(
        """
        UPDATE locations
        SET name        = ?,
            description = ?,
            parent_id   = ?,
            active      = ?
        WHERE id = ?
        """,
        (
            name.strip(),
            description or None,
            parent_val,
            1 if active else 0,
            location_id,
        ),
    )
    db.commit()

    return RedirectResponse(url="/locations", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/locations/{location_id}/delete")
async def delete_location_confirm(
    request: Request,
    location_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM locations WHERE id = ?", (location_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Location not found")

    location = dict(row)

    asset_count = db.execute(
        "SELECT COUNT(*) as count FROM assets WHERE location_id = ?", (location_id,)
    ).fetchone()["count"]

    wo_count = db.execute(
        "SELECT COUNT(*) as count FROM work_orders WHERE location_id = ?", (location_id,)
    ).fetchone()["count"]

    details = []
    if asset_count:
        details.append(f"{asset_count} asset(s) are at this location")
    if wo_count:
        details.append(f"{wo_count} work order(s) reference this location")

    warning = None
    if details:
        warning = "This location has linked records. Deactivating it will hide it from forms but keep all data."

    return templates.TemplateResponse(
        "confirm_delete.html",
        {
            "request": request,
            "heading": f"Deactivate location: {location['name']}",
            "message": f"Are you sure you want to deactivate '{location['name']}'?",
            "warning": warning,
            "details": details,
            "cancel_url": "/locations",
        },
    )


@router.post("/locations/{location_id}/delete")
async def delete_location(
    request: Request,
    location_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT id, name FROM locations WHERE id = ?", (location_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Location not found")

    open_wo_count = db.execute(
        "SELECT COUNT(*) as count FROM work_orders WHERE location_id = ? AND status NOT IN ('Done', 'Cancelled')",
        (location_id,),
    ).fetchone()["count"]

    if open_wo_count > 0:
        return templates.TemplateResponse(
            "confirm_delete.html",
            {
                "request": request,
                "heading": f"Cannot deactivate: {row['name']}",
                "message": f"This location has {open_wo_count} open work order(s). Close or reassign them first.",
                "warning": None,
                "details": None,
                "cancel_url": "/locations",
                "blocked": True,
            },
        )

    db.execute("UPDATE locations SET active = 0 WHERE id = ?", (location_id,))
    db.commit()

    return RedirectResponse(url="/locations", status_code=status.HTTP_303_SEE_OTHER)
