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
