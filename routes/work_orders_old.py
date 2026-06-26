# routes/work_orders.py

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from config import VALID_PRIORITIES, VALID_STATUSES
from db import dicts, get_db, templates

router = APIRouter()


@router.get("/work_orders")
async def list_work_orders(
    request: Request,
    sort: str = Query("priority"),
    direction: str = Query("desc"),
    wo_status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    asset: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):

    open_wos = dicts(db.execute(
        "SELECT * FROM v_open_work_orders WHERE status = 'Open' ORDER BY "
        "CASE priority WHEN 'Urgent' THEN 3 WHEN 'High' THEN 2 WHEN 'Normal' THEN 1 WHEN 'Low' THEN 0 ELSE -1 END DESC, "
        "due_date IS NULL, due_date"
    ))

    in_progress_wos = dicts(db.execute(
        "SELECT * FROM v_open_work_orders WHERE status = 'In Progress' ORDER BY "
        "CASE priority WHEN 'Urgent' THEN 3 WHEN 'High' THEN 2 WHEN 'Normal' THEN 1 WHEN 'Low' THEN 0 ELSE -1 END DESC, "
        "due_date IS NULL, due_date"
    ))

    queued_wos = dicts(db.execute(
        "SELECT * FROM v_open_work_orders WHERE status = 'Queued' ORDER BY "
        "CASE priority WHEN 'Urgent' THEN 3 WHEN 'High' THEN 2 WHEN 'Normal' THEN 1 WHEN 'Low' THEN 0 ELSE -1 END DESC, "
        "due_date IS NULL, due_date"
    ))

    icebox_wos = dicts(db.execute(
        "SELECT * FROM v_open_work_orders WHERE status = 'Icebox' ORDER BY "
        "CASE priority WHEN 'Urgent' THEN 3 WHEN 'High' THEN 2 WHEN 'Normal' THEN 1 WHEN 'Low' THEN 0 ELSE -1 END DESC, "
        "due_date IS NULL, due_date"
    ))

    closed_wos = dicts(
        db.execute(
            "SELECT * FROM work_orders "
            "WHERE status = 'Done' "
            "ORDER BY completed_at DESC LIMIT 50"
        )
    )

    wo_locations_list = sorted({r["location_name"] for r in db.execute("SELECT DISTINCT location_name FROM v_open_work_orders WHERE location_name IS NOT NULL")})
    wo_assets_list = sorted({r["asset_name"] for r in db.execute("SELECT DISTINCT asset_name FROM v_open_work_orders WHERE asset_name IS NOT NULL")})
    
    return templates.TemplateResponse(
        "work_orders.html",
        {
            "request": request,
            "open_wos": open_wos,
            "in_progress_wos": in_progress_wos,
            "queued_wos": queued_wos,
            "icebox_wos": icebox_wos,
            "closed_wos": closed_wos,
        },
    )

@router.get("/work_orders/queued")
async def list_queued_work_orders(
    request: Request,
    sort: str = Query("priority"),
    direction: str = Query("desc"),
    priority: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    asset: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    sortable_columns = {
        "id": "work_order_id", "title": "title", "status": "status",
        "priority": "priority", "due_date": "due_date",
        "location": "location_name", "asset": "asset_name",
    }

    sort_col = sortable_columns.get(sort, "priority")
    dir_sql = "DESC" if direction.lower() == "desc" else "ASC"

    where_clauses = []
    params = []

    if priority:
        where_clauses.append("priority = ?")
        params.append(priority)
    if location:
        where_clauses.append("location_name = ?")
        params.append(location)
    if asset:
        where_clauses.append("asset_name = ?")
        params.append(asset)

    extra_where = (" AND " + " AND ".join(where_clauses)) if where_clauses else ""

    queued_wos = dicts(
        db.execute(
            f"""
            SELECT * FROM v_queued_work_orders
            WHERE 1=1 {extra_where}
            ORDER BY
              CASE
                WHEN ? = 'priority' THEN
                  CASE priority
                    WHEN 'Urgent' THEN 3 WHEN 'High' THEN 2
                    WHEN 'Normal' THEN 1 WHEN 'Low' THEN 0
                    ELSE -1
                  END
                ELSE 0
              END {dir_sql},
              CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
              {sort_col} {dir_sql}
            """,
            params + ["priority" if sort_col == "priority" else ""],
        )
    )

    q_priorities_list = ["Low", "Normal", "High", "Urgent"]
    q_locations_list = sorted({r["location_name"] for r in db.execute("SELECT DISTINCT location_name FROM v_queued_work_orders WHERE location_name IS NOT NULL AND location_name != ''")})
    q_assets_list = sorted({r["asset_name"] for r in db.execute("SELECT DISTINCT asset_name FROM v_queued_work_orders WHERE asset_name IS NOT NULL AND asset_name != ''")})

    return templates.TemplateResponse(
        "work_orders_queued.html",
        {
            "request": request, "queued_wos": queued_wos,
            "sort": sort, "direction": direction,
            "q_priorities_list": q_priorities_list,
            "q_locations_list": q_locations_list, "q_assets_list": q_assets_list,
            "f_priority": priority or "", "f_location": location or "", "f_asset": asset or "",
        },
    )
# Add these routes to routes/work_orders.py

# --- Work Order History ------------------------------------------------------

@router.get("/work_orders/history")
async def work_order_history(
    request: Request,
    wo_id: Optional[str] = Query(None),
    old_status: Optional[str] = Query(None),
    new_status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    query = """
        SELECT h.id, h.work_order_id, h.event_time, h.old_status, h.new_status, h.note,
               w.title AS wo_title
        FROM work_order_history h
        LEFT JOIN work_orders w ON w.id = h.work_order_id
        WHERE 1=1
    """
    params = []

    if wo_id:
        query += " AND (CAST(h.work_order_id AS TEXT) = ? OR w.title LIKE ?)"
        params.extend([wo_id, f"%{wo_id}%"])
    if old_status:
        query += " AND h.old_status = ?"
        params.append(old_status)
    if new_status:
        query += " AND h.new_status = ?"
        params.append(new_status)
    if date_from:
        query += " AND h.event_time >= ?"
        params.append(date_from)
    if date_to:
        query += " AND h.event_time < date(?, '+1 day')"
        params.append(date_to)

    query += " ORDER BY h.event_time DESC LIMIT 200"
    history = dicts(db.execute(query, params))

    statuses = ["Open", "In Progress", "Queued", "Done", "Cancelled"]

    return templates.TemplateResponse(
        "work_order_history.html",
        {
            "request": request,
            "history": history,
            "statuses": statuses,
            "f_wo_id": wo_id or "",
            "f_old_status": old_status or "",
            "f_new_status": new_status or "",
            "f_date_from": date_from or "",
            "f_date_to": date_to or "",
        },
    )

@router.get("/work_orders/new")
async def new_work_order_form(request: Request, db: sqlite3.Connection = Depends(get_db)):
    assets = dicts(
        db.execute(
            "SELECT asset_id AS id, asset_name AS name, location_name "
            "FROM v_assets ORDER BY location_name, asset_name"
        )
    )
    locations = dicts(db.execute("SELECT id, name FROM locations WHERE active = 1 ORDER BY name"))

    return templates.TemplateResponse(
        "work_order_form.html",
        {"request": request, "assets": assets, "locations": locations},
    )


@router.post("/work_orders/new")
async def create_work_order(
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    asset_id: Optional[int] = Form(None),
    location_id: Optional[int] = Form(None),
    initial_status: str = Form("Open"),
    priority: str = Form("Normal"),
    due_date: Optional[str] = Form(None),
    source: Optional[str] = Form("Manual"),
    db: sqlite3.Connection = Depends(get_db),
):
    asset_val = asset_id if asset_id not in (None, 0) else None
    loc_val = location_id if location_id not in (None, 0) else None

    if initial_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {initial_status}")
    if priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

    db.execute(
        """
        INSERT INTO work_orders
          (asset_id, location_id, title, description, status, priority, source, due_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (asset_val, loc_val, title.strip(), description or None, initial_status, priority, source, due_date or None),
    )
    db.commit()
    return RedirectResponse(url="/work_orders", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/work_orders/{wo_id}/status")
async def update_work_order_status(
    request: Request,
    wo_id: int,
    new_status: str = Form(...),
    due_date: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT status FROM work_orders WHERE id = ?", (wo_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Work order not found")

    old_status = row["status"]

    if new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    db.execute(
        """
        UPDATE work_orders
        SET status = ?, due_date = ?,
            completed_at = CASE
              WHEN ? = 'Done' AND completed_at IS NULL THEN datetime('now')
              ELSE completed_at
            END
        WHERE id = ?
        """,
        (new_status, due_date or None, new_status, wo_id),
    )

    db.execute(
        "INSERT INTO work_order_history (work_order_id, old_status, new_status, note) VALUES (?, ?, ?, ?)",
        (wo_id, old_status, new_status, note or None),
    )
    db.commit()
    return RedirectResponse(url="/work_orders", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/work_orders/{wo_id}/edit")
async def edit_work_order_form(
    request: Request, wo_id: int, db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM work_orders WHERE id = ?", (wo_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Work order not found")

    wo = dict(row)
    assets = dicts(
        db.execute(
            "SELECT asset_id AS id, asset_name AS name, location_name "
            "FROM v_assets ORDER BY location_name, asset_name"
        )
    )
    locations = dicts(db.execute("SELECT id, name FROM locations WHERE active = 1 ORDER BY name"))
    
    wo_history = dicts(
        db.execute(
            "SELECT * FROM work_order_history WHERE work_order_id = ? ORDER BY event_time DESC",
            (wo_id,),
        )
    )


    return templates.TemplateResponse(
        "work_order_edit.html",
         {"request": request, "wo": wo, "assets": assets, "locations": locations, "wo_history": wo_history},
    )


@router.post("/work_orders/{wo_id}/edit")
async def update_work_order_core(
    request: Request,
    wo_id: int,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    asset_id: Optional[int] = Form(None),
    location_id: Optional[int] = Form(None),
    status_value: str = Form("Open"),
    priority: str = Form("Normal"),
    due_date: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    closed_notes: Optional[str] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    asset_val = asset_id if asset_id not in (None, 0) else None
    loc_val = location_id if location_id not in (None, 0) else None

    cur = db.execute("SELECT status FROM work_orders WHERE id = ?", (wo_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Work order not found")

    old_status = row["status"]

    if status_value not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status_value}")
    if priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

    db.execute(
        """
        UPDATE work_orders
        SET asset_id = ?, location_id = ?, title = ?, description = ?,
            status = ?, priority = ?, due_date = ?, source = ?, closed_notes = ?,
            completed_at = CASE
              WHEN ? = 'Done' AND completed_at IS NULL THEN datetime('now')
              ELSE completed_at
            END
        WHERE id = ?
        """,
        (
            asset_val, loc_val, title.strip(), description or None,
            status_value, priority, due_date or None, source or None,
            closed_notes or None, status_value, wo_id,
        ),
    )

    if status_value != old_status:
        db.execute(
            "INSERT INTO work_order_history (work_order_id, old_status, new_status, note) VALUES (?, ?, ?, ?)",
            (wo_id, old_status, status_value, "Edited via edit form"),
        )

    db.commit()
    return RedirectResponse(url="/work_orders", status_code=status.HTTP_303_SEE_OTHER)

    # --- Work Orders: delete -----------------------------------------------------

@router.get("/work_orders/{wo_id}/delete")
async def delete_work_order_confirm(
    request: Request,
    wo_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM work_orders WHERE id = ?", (wo_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Work order not found")

    wo = dict(row)

    if wo["status"] == "Done":
        return templates.TemplateResponse(
            "confirm_delete.html",
            {
                "request": request,
                "heading": f"Cannot delete work order #{wo['id']}",
                "message": "Completed work orders cannot be deleted — they are part of the maintenance history.",
                "warning": None,
                "details": [f"Status: {wo['status']}", f"Completed: {wo.get('completed_at', 'N/A')}"],
                "cancel_url": "/work_orders",
            },
        )

    # Count history entries
    history_count = db.execute(
        "SELECT COUNT(*) as count FROM work_order_history WHERE work_order_id = ?", (wo_id,)
    ).fetchone()["count"]

    details = [f"Title: {wo['title']}", f"Status: {wo['status']}", f"Priority: {wo['priority']}"]
    if history_count:
        details.append(f"{history_count} history record(s) will also be deleted")

    return templates.TemplateResponse(
        "confirm_delete.html",
        {
            "request": request,
            "heading": f"Delete work order #{wo['id']}",
            "message": f"Are you sure you want to permanently delete work order #{wo['id']}?",
            "warning": None,
            "details": details,
            "cancel_url": "/work_orders",
        },
    )


@router.post("/work_orders/{wo_id}/delete")
async def delete_work_order(
    request: Request,
    wo_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT status FROM work_orders WHERE id = ?", (wo_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Work order not found")

    if row["status"] == "Done":
        raise HTTPException(status_code=400, detail="Completed work orders cannot be deleted")

    # History is deleted by ON DELETE CASCADE
    db.execute("DELETE FROM work_orders WHERE id = ?", (wo_id,))
    db.commit()

    return RedirectResponse(url="/work_orders", status_code=status.HTTP_303_SEE_OTHER)
