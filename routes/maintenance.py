# routes/maintenance.py

import sqlite3
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from db import dicts, get_db, templates

router = APIRouter()


# --- List all maintenance plans ----------------------------------------------

@router.get("/maintenance")
async def list_maintenance_plans(
    request: Request,
    location: Optional[str] = Query(None),
    asset: Optional[str] = Query(None),
    show_inactive: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    query = """
        SELECT mp.*, a.name AS asset_name, l.name AS location_name
        FROM maintenance_plans mp
        LEFT JOIN assets a ON a.id = mp.asset_id
        LEFT JOIN locations l ON l.id = COALESCE(mp.location_id, a.location_id)
        WHERE 1=1
    """
    params = []

    if not show_inactive:
        query += " AND mp.active = 1"
    if location:
        query += " AND l.name = ?"
        params.append(location)
    if asset:
        query += " AND a.name = ?"
        params.append(asset)

    query += " ORDER BY mp.next_due_date IS NULL, mp.next_due_date"
    plans = dicts(db.execute(query, params))

    today = date.today().isoformat()
    for p in plans:
        if p["next_due_date"] and p["next_due_date"] <= today:
            p["overdue"] = True
        else:
            p["overdue"] = False

    locations_list = sorted({r["location_name"] for r in db.execute(
        "SELECT DISTINCT l.name AS location_name FROM maintenance_plans mp "
        "LEFT JOIN assets a ON a.id = mp.asset_id "
        "LEFT JOIN locations l ON l.id = COALESCE(mp.location_id, a.location_id) "
        "WHERE l.name IS NOT NULL AND mp.active = 1"
    )})
    assets_list = sorted({r["asset_name"] for r in db.execute(
        "SELECT DISTINCT a.name AS asset_name FROM maintenance_plans mp "
        "JOIN assets a ON a.id = mp.asset_id WHERE mp.active = 1"
    )})

    return templates.TemplateResponse(
        "maintenance_plans.html",
        {
            "request": request,
            "plans": plans,
            "locations_list": locations_list,
            "assets_list": assets_list,
            "f_location": location or "",
            "f_asset": asset or "",
            "show_inactive": show_inactive or "",
            "today": today,
        },
    )


# --- Create maintenance plan -------------------------------------------------

@router.get("/maintenance/new")
async def new_maintenance_plan_form(request: Request, db: sqlite3.Connection = Depends(get_db)):
    assets = dicts(db.execute(
        "SELECT asset_id AS id, asset_name AS name, location_name "
        "FROM v_assets ORDER BY location_name, asset_name"
    ))
    locations = dicts(db.execute(
        "SELECT id, name FROM locations WHERE active = 1 ORDER BY name"
    ))

    return templates.TemplateResponse(
        "maintenance_plan_form.html",
        {"request": request, "assets": assets, "locations": locations, "error": None},
    )


@router.post("/maintenance/new")
async def create_maintenance_plan(
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    asset_id: Optional[int] = Form(None),
    location_id: Optional[int] = Form(None),
    frequency_value: int = Form(...),
    frequency_unit: str = Form(...),
    next_due_date: Optional[str] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    asset_val = asset_id if asset_id not in (None, 0) else None
    loc_val = location_id if location_id not in (None, 0) else None

    if not asset_val and not loc_val:
        assets = dicts(db.execute(
            "SELECT asset_id AS id, asset_name AS name, location_name "
            "FROM v_assets ORDER BY location_name, asset_name"
        ))
        locations = dicts(db.execute(
            "SELECT id, name FROM locations WHERE active = 1 ORDER BY name"
        ))
        return templates.TemplateResponse(
            "maintenance_plan_form.html",
            {"request": request, "assets": assets, "locations": locations,
             "error": "An asset or location is required."},
        )

    if frequency_unit not in ("day", "month", "year"):
        raise HTTPException(status_code=400, detail="Invalid frequency unit")

    db.execute(
        """
        INSERT INTO maintenance_plans
          (title, description, asset_id, location_id, frequency_value, frequency_unit, next_due_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (title.strip(), description or None, asset_val, loc_val,
         frequency_value, frequency_unit, next_due_date or None),
    )
    db.commit()

    return RedirectResponse(url="/maintenance", status_code=status.HTTP_303_SEE_OTHER)


# --- Edit maintenance plan ---------------------------------------------------

@router.get("/maintenance/{plan_id}/edit")
async def edit_maintenance_plan_form(
    request: Request, plan_id: int, db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM maintenance_plans WHERE id = ?", (plan_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Maintenance plan not found")

    plan = dict(row)
    assets = dicts(db.execute(
        "SELECT asset_id AS id, asset_name AS name, location_name "
        "FROM v_assets ORDER BY location_name, asset_name"
    ))
    locations = dicts(db.execute(
        "SELECT id, name FROM locations WHERE active = 1 ORDER BY name"
    ))

    steps = dicts(db.execute(
        "SELECT * FROM job_plan_steps WHERE maintenance_plan_id = ? ORDER BY step_number",
        (plan_id,),
    ))

    return templates.TemplateResponse(
        "maintenance_plan_edit.html",
        {"request": request, "plan": plan, "assets": assets, "locations": locations,
         "steps": steps, "error": None},
    )


@router.post("/maintenance/{plan_id}/edit")
async def update_maintenance_plan(
    request: Request,
    plan_id: int,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    asset_id: Optional[int] = Form(None),
    location_id: Optional[int] = Form(None),
    frequency_value: int = Form(...),
    frequency_unit: str = Form(...),
    next_due_date: Optional[str] = Form(None),
    active: Optional[int] = Form(1),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT id FROM maintenance_plans WHERE id = ?", (plan_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Maintenance plan not found")

    asset_val = asset_id if asset_id not in (None, 0) else None
    loc_val = location_id if location_id not in (None, 0) else None

    if not asset_val and not loc_val:
        raise HTTPException(status_code=400, detail="An asset or location is required.")

    db.execute(
        """
        UPDATE maintenance_plans
        SET title = ?, description = ?, asset_id = ?, location_id = ?,
            frequency_value = ?, frequency_unit = ?, next_due_date = ?, active = ?
        WHERE id = ?
        """,
        (title.strip(), description or None, asset_val, loc_val,
         frequency_value, frequency_unit, next_due_date or None,
         1 if active else 0, plan_id),
    )
    db.commit()

    return RedirectResponse(url="/maintenance", status_code=status.HTTP_303_SEE_OTHER)


# --- Delete (deactivate) maintenance plan ------------------------------------

@router.get("/maintenance/{plan_id}/delete")
async def delete_maintenance_plan_confirm(
    request: Request, plan_id: int, db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM maintenance_plans WHERE id = ?", (plan_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Maintenance plan not found")

    plan = dict(row)
    return templates.TemplateResponse(
        "confirm_delete.html",
        {
            "request": request,
            "heading": f"Deactivate: {plan['title']}",
            "message": f"Are you sure you want to deactivate '{plan['title']}'?",
            "warning": "The plan will be hidden but not deleted.",
            "details": None,
            "cancel_url": "/maintenance",
        },
    )


@router.post("/maintenance/{plan_id}/delete")
async def delete_maintenance_plan(
    request: Request, plan_id: int, db: sqlite3.Connection = Depends(get_db),
):
    db.execute("UPDATE maintenance_plans SET active = 0 WHERE id = ?", (plan_id,))
    db.commit()
    return RedirectResponse(url="/maintenance", status_code=status.HTTP_303_SEE_OTHER)


# --- Job plan steps ----------------------------------------------------------

@router.post("/maintenance/{plan_id}/steps/add")
async def add_job_plan_step(
    request: Request,
    plan_id: int,
    description: str = Form(...),
    notes: Optional[str] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    max_step = db.execute(
        "SELECT COALESCE(MAX(step_number), 0) as max_step FROM job_plan_steps WHERE maintenance_plan_id = ?",
        (plan_id,),
    ).fetchone()["max_step"]

    db.execute(
        "INSERT INTO job_plan_steps (maintenance_plan_id, step_number, description, notes) VALUES (?, ?, ?, ?)",
        (plan_id, max_step + 1, description.strip(), notes or None),
    )
    db.commit()

    return RedirectResponse(url=f"/maintenance/{plan_id}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/maintenance/{plan_id}/steps/{step_id}/delete")
async def delete_job_plan_step(
    request: Request, plan_id: int, step_id: int, db: sqlite3.Connection = Depends(get_db),
):
    db.execute("DELETE FROM job_plan_steps WHERE id = ? AND maintenance_plan_id = ?", (step_id, plan_id))
    db.commit()

    # Renumber remaining steps
    steps = db.execute(
        "SELECT id FROM job_plan_steps WHERE maintenance_plan_id = ? ORDER BY step_number",
        (plan_id,),
    ).fetchall()
    for i, step in enumerate(steps, start=1):
        db.execute("UPDATE job_plan_steps SET step_number = ? WHERE id = ?", (i, step["id"]))
    db.commit()

    return RedirectResponse(url=f"/maintenance/{plan_id}/edit", status_code=status.HTTP_303_SEE_OTHER)


# --- Complete a PM -----------------------------------------------------------

@router.post("/maintenance/{plan_id}/complete")
async def complete_maintenance_plan(
    request: Request, plan_id: int, db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM maintenance_plans WHERE id = ?", (plan_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Maintenance plan not found")

    plan = dict(row)
    today = date.today()

    # Calculate next due date
    freq_val = plan["frequency_value"]
    freq_unit = plan["frequency_unit"]

    if freq_unit == "day":
        next_due = today + timedelta(days=freq_val)
    elif freq_unit == "month":
        month = today.month + freq_val
        year = today.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(today.day, 28)
        next_due = date(year, month, day)
    elif freq_unit == "year":
        next_due = date(today.year + freq_val, today.month, min(today.day, 28))
    else:
        next_due = today + timedelta(days=30)

    # Update the plan
    db.execute(
        "UPDATE maintenance_plans SET last_done_date = ?, next_due_date = ? WHERE id = ?",
        (today.isoformat(), next_due.isoformat(), plan_id),
    )

    # Create a work order
    location_id = plan["location_id"]
    if not location_id and plan["asset_id"]:
        loc_row = db.execute("SELECT location_id FROM assets WHERE id = ?", (plan["asset_id"],)).fetchone()
        if loc_row:
            location_id = loc_row["location_id"]

    # Build description with job plan steps
    steps = dicts(db.execute(
        "SELECT * FROM job_plan_steps WHERE maintenance_plan_id = ? ORDER BY step_number",
        (plan_id,),
    ))

    wo_description = plan["description"] or ""
    if steps:
        wo_description += "\n\nJob plan steps:\n"
        for s in steps:
            wo_description += f"  {s['step_number']}. {s['description']}"
            if s.get("notes"):
                wo_description += f" ({s['notes']})"
            wo_description += "\n"

    db.execute(
        """
        INSERT INTO work_orders
          (asset_id, location_id, title, description, status, priority, source)
        VALUES (?, ?, ?, ?, 'Open', 'Normal', 'Planned Maintenance')
        """,
        (plan["asset_id"], location_id, f"PM: {plan['title']}", wo_description.strip()),
    )

    db.commit()

    return RedirectResponse(url="/maintenance", status_code=status.HTTP_303_SEE_OTHER)


# --- Generate all overdue PMs ------------------------------------------------

@router.post("/maintenance/generate")
async def generate_overdue_pms(
    request: Request, db: sqlite3.Connection = Depends(get_db),
):
    today = date.today().isoformat()

    overdue = dicts(db.execute(
        "SELECT * FROM maintenance_plans WHERE active = 1 AND next_due_date IS NOT NULL AND next_due_date <= ?",
        (today,),
    ))

    generated = 0
    for plan in overdue:
        # Calculate next due date
        freq_val = plan["frequency_value"]
        freq_unit = plan["frequency_unit"]
        today_date = date.today()

        if freq_unit == "day":
            next_due = today_date + timedelta(days=freq_val)
        elif freq_unit == "month":
            month = today_date.month + freq_val
            year = today_date.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            day = min(today_date.day, 28)
            next_due = date(year, month, day)
        elif freq_unit == "year":
            next_due = date(today_date.year + freq_val, today_date.month, min(today_date.day, 28))
        else:
            next_due = today_date + timedelta(days=30)

        # Update the plan
        db.execute(
            "UPDATE maintenance_plans SET last_done_date = ?, next_due_date = ? WHERE id = ?",
            (today, next_due.isoformat(), plan["id"]),
        )

        # Get location
        location_id = plan.get("location_id")
        if not location_id and plan["asset_id"]:
            loc_row = db.execute("SELECT location_id FROM assets WHERE id = ?", (plan["asset_id"],)).fetchone()
            if loc_row:
                location_id = loc_row["location_id"]

        # Build description with job plan steps
        steps = dicts(db.execute(
            "SELECT * FROM job_plan_steps WHERE maintenance_plan_id = ? ORDER BY step_number",
            (plan["id"],),
        ))

        wo_description = plan.get("description") or ""
        if steps:
            wo_description += "\n\nJob plan steps:\n"
            for s in steps:
                wo_description += f"  {s['step_number']}. {s['description']}"
                if s.get("notes"):
                    wo_description += f" ({s['notes']})"
                wo_description += "\n"

        db.execute(
            """
            INSERT INTO work_orders
              (asset_id, location_id, title, description, status, priority, source)
            VALUES (?, ?, ?, ?, 'Open', 'Normal', 'Planned Maintenance')
            """,
            (plan["asset_id"], location_id, f"PM: {plan['title']}", wo_description.strip()),
        )
        generated += 1

    db.commit()

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
