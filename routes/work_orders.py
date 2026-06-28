# routes/work_orders.py
#
# Work order management routes: list (grouped by status), create, edit,
# delete, inline status updates, history, Kanban board, and JSON API.

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from config import VALID_PRIORITIES, VALID_STATUSES
from db import dicts, get_db, get_hierarchical_locations, templates

router = APIRouter()


# --- List all work orders (grouped by status) --------------------------------
#
# ADDED: optional ?location= and ?asset= query parameters (fix for issue #30).
# Dashboard "Open WOs by Location/Asset" links now pre-filter this view.
# The same filter is applied to every status group (Open, In Progress, Queued,
# Icebox, Done, Cancelled) so the whole page is scoped to the chosen entity.
# filter_location / filter_asset are passed to the template so it can display
# an active-filter banner with a "Clear filter" link.

@router.get("/work_orders")
async def list_work_orders(
    request: Request,
    # ADDED: location and asset are optional query params — both default to None
    # (no filter). Populated by dashboard links, the Assets "View" column, and
    # the Locations "work orders" links.
    location: Optional[str] = Query(None),
    asset: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    priority_order = (
        "CASE priority WHEN 'Urgent' THEN 3 WHEN 'High' THEN 2 "
        "WHEN 'Normal' THEN 1 WHEN 'Low' THEN 0 ELSE -1 END DESC, "
        "due_date IS NULL, due_date"
    )

    # ADDED: build a reusable SQL fragment and params list from whichever
    # filters are active. Empty string = no filter = show all.
    filter_sql = ""
    filter_params: list = []
    if location:
        filter_sql += " AND location_name = ?"
        filter_params.append(location)
    if asset:
        filter_sql += " AND asset_name = ?"
        filter_params.append(asset)

    # ADDED: inner helper so the same filter applies to every status bucket
    # without duplicating the query four times.
    def fetch(status: str):
        return dicts(db.execute(
            f"SELECT * FROM v_open_work_orders WHERE status = ?{filter_sql} ORDER BY {priority_order}",
            [status] + filter_params,
        ))

    open_wos       = fetch("Open")
    in_progress_wos = fetch("In Progress")
    queued_wos     = fetch("Queued")
    icebox_wos     = fetch("Icebox")

    # ADDED: Done/Cancelled live in the base work_orders table (not the view),
    # so when a filter is active we JOIN to assets/locations to apply it.
    # When no filter is active we use the simpler original queries.
    if filter_sql:
        closed_wos = dicts(db.execute(
            "SELECT w.* FROM work_orders w "
            "LEFT JOIN assets a ON a.id = w.asset_id "
            "LEFT JOIN locations l ON l.id = COALESCE(w.location_id, a.location_id) "
            f"WHERE w.status = 'Done'{'' if not location else ' AND l.name = ?'}"
            f"{'' if not asset else ' AND a.name = ?'} "
            "ORDER BY w.completed_at DESC LIMIT 50",
            ([location] if location else []) + ([asset] if asset else []),
        ))
        cancelled_wos = dicts(db.execute(
            "SELECT w.* FROM work_orders w "
            "LEFT JOIN assets a ON a.id = w.asset_id "
            "LEFT JOIN locations l ON l.id = COALESCE(w.location_id, a.location_id) "
            f"WHERE w.status = 'Cancelled'{'' if not location else ' AND l.name = ?'}"
            f"{'' if not asset else ' AND a.name = ?'} "
            "ORDER BY w.created_at DESC LIMIT 50",
            ([location] if location else []) + ([asset] if asset else []),
        ))
    else:
        # Original unfiltered queries — unchanged from before
        closed_wos = dicts(db.execute(
            "SELECT * FROM work_orders WHERE status = 'Done' ORDER BY completed_at DESC LIMIT 50"
        ))
        cancelled_wos = dicts(db.execute(
            "SELECT * FROM work_orders WHERE status = 'Cancelled' ORDER BY created_at DESC LIMIT 50"
        ))

    return templates.TemplateResponse(
        "work_orders.html",
        {
            "request": request,
            "open_wos": open_wos,
            "in_progress_wos": in_progress_wos,
            "queued_wos": queued_wos,
            "icebox_wos": icebox_wos,
            "closed_wos": closed_wos,
            "cancelled_wos": cancelled_wos,
            # ADDED: pass active filter values so the template can show the banner
            "filter_location": location or "",
            "filter_asset": asset or "",
        },
    )


# --- Work order history (searchable/filterable) ------------------------------

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

    statuses = ["Open", "In Progress", "Queued", "Done", "Cancelled", "Icebox"]

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


# --- Kanban board view -------------------------------------------------------

@router.get("/work_orders/board")
async def work_order_board(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
):
    all_wos = dicts(
        db.execute(
            """
            SELECT w.id, w.title, w.status, w.priority, w.due_date,
                   a.name AS asset_name, a.status AS asset_status,
                   l.name AS location_name
            FROM work_orders w
            LEFT JOIN assets a ON a.id = w.asset_id
            LEFT JOIN locations l ON l.id = COALESCE(w.location_id, a.location_id)
            WHERE w.status NOT IN ('Done', 'Cancelled')
            ORDER BY CASE w.priority
                WHEN 'Urgent' THEN 3 WHEN 'High' THEN 2
                WHEN 'Normal' THEN 1 WHEN 'Low' THEN 0
                ELSE -1
            END DESC, w.due_date IS NULL, w.due_date
            """
        )
    )

    board = {
        "Icebox": [],
        "Queued": [],
        "Open": [],
        "In Progress": [],
        "Done": [],
    }
    for wo in all_wos:
        if wo["status"] in board:
            board[wo["status"]].append(wo)

    return templates.TemplateResponse(
        "work_order_board.html",
        {"request": request, "board": board},
    )


# --- JSON API for board drag-and-drop status updates -------------------------

@router.post("/api/work_orders/{wo_id}/status")
async def api_update_work_order_status(
    request: Request,
    wo_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    from fastapi.responses import JSONResponse

    body = await request.json()
    new_status = body.get("status")

    if new_status not in VALID_STATUSES:
        return JSONResponse({"error": f"Invalid status: {new_status}"}, status_code=400)

    cur = db.execute("SELECT status FROM work_orders WHERE id = ?", (wo_id,))
    row = cur.fetchone()
    if not row:
        return JSONResponse({"error": "Work order not found"}, status_code=404)

    old_status = row["status"]

    db.execute(
        """
        UPDATE work_orders
        SET status = ?,
            completed_at = CASE
              WHEN ? = 'Done' AND completed_at IS NULL THEN datetime('now')
              ELSE completed_at
            END
        WHERE id = ?
        """,
        (new_status, new_status, wo_id),
    )

    db.execute(
        "INSERT INTO work_order_history (work_order_id, old_status, new_status, note) VALUES (?, ?, ?, ?)",
        (wo_id, old_status, new_status, "Changed via Kanban board"),
    )
    db.commit()

    return JSONResponse({"ok": True, "old_status": old_status, "new_status": new_status})


# --- Create new work order ---------------------------------------------------

@router.get("/work_orders/new")
async def new_work_order_form(request: Request, db: sqlite3.Connection = Depends(get_db)):
    assets = dicts(
        db.execute(
            "SELECT asset_id AS id, asset_name AS name, location_name "
            "FROM v_assets ORDER BY location_name, asset_name"
        )
    )
    locations = get_hierarchical_locations(db)

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


# --- Inline status + due date update from list view --------------------------

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


# --- Edit work order (full form) ---------------------------------------------

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
    locations = get_hierarchical_locations(db)

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


# --- Delete work order (confirmation page) -----------------------------------

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

    # Block deletion of completed work orders
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
                "blocked": True,
            },
        )

    # Show confirmation with linked record counts
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


# --- Delete work order (execute) ---------------------------------------------

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
        return templates.TemplateResponse(
            "confirm_delete.html",
            {
                "request": request,
                "heading": "Cannot delete this work order",
                "message": "Completed work orders cannot be deleted — they are part of the maintenance history.",
                "warning": None,
                "details": None,
                "cancel_url": "/work_orders",
                "blocked": True,
            },
        )

    # History is deleted by ON DELETE CASCADE
    db.execute("DELETE FROM work_orders WHERE id = ?", (wo_id,))
    db.commit()

    return RedirectResponse(url="/work_orders", status_code=status.HTTP_303_SEE_OTHER)
