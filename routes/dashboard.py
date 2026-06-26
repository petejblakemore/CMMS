# routes/dashboard.py

import sqlite3

from fastapi import APIRouter, Depends, Request

from db import build_location_tree, dicts, get_db, templates, PRIORITY_ORDER_SQL

router = APIRouter()


@router.get("/")
async def index(request: Request, db: sqlite3.Connection = Depends(get_db)):
    locations_flat = dicts(db.execute("SELECT * FROM locations WHERE active = 1"))
    location_tree = build_location_tree(locations_flat)

    assets = dicts(
        db.execute("SELECT * FROM v_assets ORDER BY location_name, asset_name")
    )

    open_wos = dicts(
        db.execute(
            f"SELECT * FROM v_open_work_orders "
            f"ORDER BY {PRIORITY_ORDER_SQL} DESC, due_date IS NULL, due_date"
        )
    )


    upcoming_pm = dicts(
        db.execute(
            "SELECT * FROM v_upcoming_pm "
            "WHERE date(next_due_date) <= date('now','+90 day') "
            "ORDER BY next_due_date"
        )
    )
    # Locations with open work order counts
    location_wo_counts = dicts(
        db.execute(
            """
            SELECT location_name, COUNT(*) as wo_count
            FROM v_open_work_orders
            WHERE location_name IS NOT NULL
            GROUP BY location_name
            ORDER BY wo_count DESC
            """
        )
    )
    asset_wo_counts = dicts(
        db.execute(
            """
            SELECT asset_name, COUNT(*) as wo_count
            FROM v_open_work_orders
            WHERE asset_name IS NOT NULL
            GROUP BY asset_name
            ORDER BY wo_count DESC
            """
        )
    )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "locations": location_tree,
            "assets": assets,
            "open_wos": open_wos,
            "upcoming_pm": upcoming_pm,
            "location_wo_counts": location_wo_counts,
            "asset_wo_counts": asset_wo_counts,
        },
    )
