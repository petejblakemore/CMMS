# routes/work_orders.py
#
# Work order management: grouped list, create, edit, delete,
# inline status updates, history, Kanban board, and costing.

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from config import VALID_PRIORITIES, VALID_STATUSES
from db import dicts, get_db, get_hierarchical_locations, templates

router = APIRouter()


# --- List all work orders (grouped by status) --------------------------------

@router.get("/work_orders")
async def list_work_orders(
    request: Request,
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

    cur = db.execute("SELECT * FROM work_orders WHERE id = ?", (wo_id,))
    row = cur.fetchone()
    if not row:
        return JSONResponse({"error": "Work order not found"}, status_code=404)

    wo = dict(row)
    old_status = wo["status"]

    # Close-gate: block Done if estimates exist but actuals are missing
    if new_status == "Done":
        has_estimates = (
            (wo.get("estimated_labour_cost") and wo["estimated_labour_cost"] > 0) or
            (wo.get("estimated_material_cost") and wo["estimated_material_cost"] > 0)
        )
        missing_actuals = (
            not wo.get("actual_labour_cost") or
            not wo.get("actual_material_cost")
        )
        if has_estimates and missing_actuals:
            return JSONResponse(
                {"error": "Actual costs are required before completing this work order. Use the edit form to enter costs."},
                status_code=400,
            )

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
            "SELECT asset_id AS id, asset_name AS name, location_name, location_id "
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
    estimated_hours: Optional[str] = Form(None),
    estimated_labour_cost: Optional[str] = Form(None),
    estimated_material_cost: Optional[str] = Form(None),
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
          (asset_id, location_id, title, description, status, priority, source,
           due_date, estimated_hours, estimated_labour_cost, estimated_material_cost)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            asset_val, loc_val, title.strip(), description or None,
            initial_status, priority, source, due_date or None,
            float(estimated_hours) if estimated_hours else None,
            float(estimated_labour_cost) if estimated_labour_cost else None,
            float(estimated_material_cost) if estimated_material_cost else None,
        ),
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
            "SELECT asset_id AS id, asset_name AS name, location_name, location_id "
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
        {"request": request, "wo": wo, "assets": assets, "locations": locations,
         "wo_history": wo_history, "error": None},
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
    estimated_hours: Optional[str] = Form(None),
    estimated_labour_cost: Optional[str] = Form(None),
    estimated_material_cost: Optional[str] = Form(None),
    actual_labour_cost: Optional[str] = Form(None),
    actual_material_cost: Optional[str] = Form(None),
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

    # Close-gate: require actual costs before completing a WO with estimates
    if status_value == "Done":
        has_estimates = (
            (estimated_labour_cost and float(estimated_labour_cost) > 0) or
            (estimated_material_cost and float(estimated_material_cost) > 0)
        )
        missing_actuals = (
            not actual_labour_cost or
            not actual_material_cost
        )
        if has_estimates and missing_actuals:
            wo = dict(db.execute("SELECT * FROM work_orders WHERE id = ?", (wo_id,)).fetchone())
            assets_list = dicts(db.execute(
                "SELECT asset_id AS id, asset_name AS name, location_name "
                "FROM v_assets ORDER BY location_name, asset_name"
            ))
            locations_list = get_hierarchical_locations(db)
            wo_history = dicts(db.execute(
                "SELECT * FROM work_order_history WHERE work_order_id = ? ORDER BY event_time DESC",
                (wo_id,),
            ))
            return templates.TemplateResponse(
                "work_order_edit.html",
                {"request": request, "wo": wo, "assets": assets_list,
                 "locations": locations_list, "wo_history": wo_history,
                 "error": "Actual costs are required before completing a work order with estimated costs."},
            )

    db.execute(
        """
        UPDATE work_orders
        SET asset_id = ?, location_id = ?, title = ?, description = ?,
            status = ?, priority = ?, due_date = ?, source = ?, closed_notes = ?,
            estimated_hours = ?, estimated_labour_cost = ?, estimated_material_cost = ?,
            actual_labour_cost = ?, actual_material_cost = ?,
            completed_at = CASE
              WHEN ? = 'Done' AND completed_at IS NULL THEN datetime('now')
              ELSE completed_at
            END
        WHERE id = ?
        """,
        (
            asset_val, loc_val, title.strip(), description or None,
            status_value, priority, due_date or None, source or None,
            closed_notes or None,
            float(estimated_hours) if estimated_hours else None,
            float(estimated_labour_cost) if estimated_labour_cost else None,
            float(estimated_material_cost) if estimated_material_cost else None,
            float(actual_labour_cost) if actual_labour_cost else None,
            float(actual_material_cost) if actual_material_cost else None,
            status_value, wo_id,
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

    db.execute("DELETE FROM work_orders WHERE id = ?", (wo_id,))
    db.commit()

    return RedirectResponse(url="/work_orders", status_code=status.HTTP_303_SEE_OTHER)
