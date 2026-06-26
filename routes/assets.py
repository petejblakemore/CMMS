# routes/assets.py
#
# Asset management routes: list, create, edit, delete, and CSV import.
# Assets belong to locations and can have work orders raised against them.
# Each asset has a category, type, status, and optional manufacturer/vendor details.

import csv
import logging
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import RedirectResponse

from config import ASSET_IMPORT_LOG
from db import dicts, get_db, templates

logger = logging.getLogger("cmms")
router = APIRouter()


# --- List all assets with optional filtering and column sorting --------------

@router.get("/assets")
async def list_assets(
    request: Request,
    sort: str = Query("asset_name"),
    direction: str = Query("asc"),
    location: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    asset_status: Optional[str] = Query(None),
    manufacturer: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    # Map URL sort parameter to actual database column names
    sortable_columns = {
        "asset_name": "asset_name",
        "location": "location_name",
        "category": "category",
        "type": "type",
        "status": "status",
        "manufacturer": "manufacturer",
        "model": "model",
        "purchased": "purchase_date",
        "warranty": "warranty_end_date",
    }

    # Default to asset_name if an invalid sort column is requested
    sort_col = sortable_columns.get(sort, "asset_name")
    dir_sql = "DESC" if direction.lower() == "desc" else "ASC"

    # Build dynamic WHERE clause from active filters
    query = "SELECT * FROM v_assets WHERE 1=1"
    params = []

    if location:
        query += " AND location_name = ?"
        params.append(location)
    if category:
        query += " AND category = ?"
        params.append(category)
    if asset_status:
        query += " AND status = ?"
        params.append(asset_status)
    if manufacturer:
        query += " AND manufacturer = ?"
        params.append(manufacturer)

    query += f" ORDER BY {sort_col} {dir_sql}, asset_name ASC"
    assets = dicts(db.execute(query, params))

    # Fetch distinct values for filter dropdowns (from all assets, not just filtered ones)
    locations_list = sorted({r["location_name"] for r in db.execute("SELECT DISTINCT location_name FROM v_assets")})
    categories_list = sorted({r["category"] for r in db.execute("SELECT DISTINCT category FROM v_assets WHERE category IS NOT NULL")})
    statuses_list = sorted({r["status"] for r in db.execute("SELECT DISTINCT status FROM v_assets WHERE status IS NOT NULL")})
    manufacturers_list = sorted({r["manufacturer"] for r in db.execute("SELECT DISTINCT manufacturer FROM v_assets WHERE manufacturer IS NOT NULL")})

    return templates.TemplateResponse(
        "assets.html",
        {
            "request": request,
            "assets": assets,
            # Dropdown options for filter bar
            "locations_list": locations_list,
            "categories_list": categories_list,
            "statuses_list": statuses_list,
            "manufacturers_list": manufacturers_list,
            # f_ prefix = current filter selection, passed back to maintain state after submit
            "f_location": location or "",
            "f_category": category or "",
            "f_status": asset_status or "",
            "f_manufacturer": manufacturer or "",
            # Current sort state for column header links
            "sort": sort,
            "direction": direction,
        },
    )


# --- Show the new asset form ------------------------------------------------

@router.get("/assets/new")
async def new_asset_form(request: Request, db: sqlite3.Connection = Depends(get_db)):
    # Only show active locations in the dropdown
    locations = dicts(
        db.execute("SELECT id, name FROM locations WHERE active = 1 ORDER BY name")
    )
    # Auto-suggest existing categories and types (datalist dropdowns)
    categories = sorted(
        {row["category"] for row in db.execute("SELECT DISTINCT category FROM assets WHERE category IS NOT NULL")}
    )
    types = sorted(
        {row["type"] for row in db.execute("SELECT DISTINCT type FROM assets WHERE type IS NOT NULL")}
    )

    return templates.TemplateResponse(
        "asset_form.html",
        {"request": request, "locations": locations, "categories": categories, "types": types},
    )


# --- Handle new asset form submission ---------------------------------------

@router.post("/assets/new")
async def create_asset(
    request: Request,
    name: str = Form(...),
    location_id: int = Form(...),
    category: Optional[str] = Form(None),
    asset_type: Optional[str] = Form(None),
    asset_status: Optional[str] = Form("Running"),
    manufacturer: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    serial_number: Optional[str] = Form(None),
    purchase_date: Optional[str] = Form(None),
    warranty_end_date: Optional[str] = Form(None),
    cost: Optional[str] = Form(None),
    vendor: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    db.execute(
        """
        INSERT INTO assets
          (name, location_id, category, type, status, manufacturer, model,
           serial_number, purchase_date, warranty_end_date, cost, vendor, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name.strip(), location_id, category or None, asset_type or None,
            asset_status or "Running", manufacturer or None, model or None,
            serial_number or None, purchase_date or None, warranty_end_date or None,
            float(cost) if cost else None, vendor or None, notes or None,
        ),
    )
    db.commit()

    logger.info(f"Asset created: '{name.strip()}' at location #{location_id}")
    return RedirectResponse(url="/assets", status_code=status.HTTP_303_SEE_OTHER)


# --- Show the edit asset form (prefilled with current values) ----------------

@router.get("/assets/{asset_id}/edit")
async def edit_asset_form(
    request: Request, asset_id: int, db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset = dict(row)
    locations = dicts(db.execute("SELECT id, name FROM locations WHERE active = 1 ORDER BY name"))
    categories = sorted(
        {r["category"] for r in db.execute("SELECT DISTINCT category FROM assets WHERE category IS NOT NULL")}
    )
    types = sorted(
        {row["type"] for row in db.execute("SELECT DISTINCT type FROM assets WHERE type IS NOT NULL")}
    )

    return templates.TemplateResponse(
        "asset_edit.html",
        {"request": request, "asset": asset, "locations": locations, "categories": categories, "types": types},
    )


# --- Handle edit asset form submission ---------------------------------------

@router.post("/assets/{asset_id}/edit")
async def update_asset(
    request: Request,
    asset_id: int,
    name: str = Form(...),
    location_id: int = Form(...),
    category: Optional[str] = Form(None),
    asset_type: Optional[str] = Form(None),
    asset_status: Optional[str] = Form("Running"),
    manufacturer: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    serial_number: Optional[str] = Form(None),
    purchase_date: Optional[str] = Form(None),
    warranty_end_date: Optional[str] = Form(None),
    cost: Optional[str] = Form(None),
    vendor: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT id FROM assets WHERE id = ?", (asset_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Asset not found")

    db.execute(
        """
        UPDATE assets
        SET name = ?, location_id = ?, category = ?, type = ?, status = ?,
            manufacturer = ?, model = ?, serial_number = ?,
            purchase_date = ?, warranty_end_date = ?, cost = ?, vendor = ?, notes = ?
        WHERE id = ?
        """,
        (
            name.strip(), location_id, category or None, asset_type or None,
            asset_status or "Running", manufacturer or None, model or None,
            serial_number or None, purchase_date or None, warranty_end_date or None,
            float(cost) if cost else None, vendor or None, notes or None,
            asset_id,
        ),
    )
    db.commit()

    logger.info(f"Asset #{asset_id} updated: '{name.strip()}'")
    return RedirectResponse(url="/assets", status_code=status.HTTP_303_SEE_OTHER)


# --- Show delete confirmation page ------------------------------------------
# Assets are hard-deleted. Blocked if there are open work orders linked.

@router.get("/assets/{asset_id}/delete")
async def delete_asset_confirm(
    request: Request,
    asset_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset = dict(row)

    # Check for linked work orders to warn the user
    wo_count = db.execute(
        "SELECT COUNT(*) as count FROM work_orders WHERE asset_id = ?", (asset_id,)
    ).fetchone()["count"]

    details = []
    warning = None
    if wo_count:
        details.append(f"{wo_count} work order(s) reference this asset")
        warning = "Linked work orders will keep their data but lose the asset reference."

    return templates.TemplateResponse(
        "confirm_delete.html",
        {
            "request": request,
            "heading": f"Delete asset: {asset['name']}",
            "message": f"Are you sure you want to permanently delete '{asset['name']}'?",
            "warning": warning,
            "details": details,
            "cancel_url": "/assets",
        },
    )


# --- Execute asset deletion --------------------------------------------------
# Blocked if there are open (non-Done, non-Cancelled) work orders.

@router.post("/assets/{asset_id}/delete")
async def delete_asset(
    request: Request,
    asset_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT id, name FROM assets WHERE id = ?", (asset_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Block deletion if there are active work orders against this asset
    open_wo_count = db.execute(
        "SELECT COUNT(*) as count FROM work_orders WHERE asset_id = ? AND status NOT IN ('Done', 'Cancelled')",
        (asset_id,),
    ).fetchone()["count"]

    if open_wo_count > 0:
        logger.warning(f"Blocked deletion of asset #{asset_id} — {open_wo_count} open work order(s)")
        return templates.TemplateResponse(
            "confirm_delete.html",
            {
                "request": request,
                "heading": f"Cannot delete: {row['name']}",
                "message": f"This asset has {open_wo_count} open work order(s). Close or reassign them first.",
                "warning": None,
                "details": None,
                "cancel_url": "/assets",
            },
        )

    db.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    db.commit()

    logger.info(f"Asset #{asset_id} deleted: '{row['name']}'")
    return RedirectResponse(url="/assets", status_code=status.HTTP_303_SEE_OTHER)


# --- CSV import: show upload form --------------------------------------------

@router.get("/assets/import")
async def import_assets_form(request: Request):
    return templates.TemplateResponse("asset_import.html", {"request": request})


# --- CSV import: process uploaded file ---------------------------------------
# Expected columns: ASSET (required), LOCATION (required),
# CATEGORY, TYPE, MANUFACTURER, MODEL, SERIAL #, DATE PURCHASED, WARRANTY ENDS, NOTES
# Locations are auto-created if they don't exist.
# Duplicate assets (same name + location) are skipped.
# All activity is logged to asset_import.log.

@router.post("/assets/import")
async def import_assets_csv(
    request: Request,
    file: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
):
    raw = await file.read()
    text_lines = raw.decode("utf-8", errors="replace").splitlines()

    if not text_lines:
        return templates.TemplateResponse(
            "asset_import.html", {"request": request, "error": "Empty CSV file."},
        )

    reader = csv.DictReader(text_lines)

    # Build a case-insensitive mapping from CSV headers to actual column names
    headers = [h.upper() for h in (reader.fieldnames or [])]
    header_map = {h.upper(): h for h in (reader.fieldnames or [])}

    def get_col(name: str):
        """Look up the original CSV header for a logical column name (case-insensitive)."""
        return header_map.get(name.upper())

    # Validate required columns exist
    required = {"ASSET", "LOCATION"}
    missing = {col for col in required if col not in headers}
    if missing:
        return templates.TemplateResponse(
            "asset_import.html",
            {"request": request, "error": f"Missing required column(s): {', '.join(sorted(missing))}"},
        )

    # Map logical column names to actual CSV headers
    col_asset = get_col("ASSET")
    col_location = get_col("LOCATION")
    col_category = get_col("CATEGORY")
    col_type = get_col("TYPE")
    col_manufacturer = get_col("MANUFACTURER")
    col_model = get_col("MODEL")
    col_serial = get_col("SERIAL #")
    col_purchase = get_col("DATE PURCHASED")
    col_warranty = get_col("WARRANTY ENDS")
    col_notes = get_col("NOTES")

    imported = 0
    skipped = 0

    with ASSET_IMPORT_LOG.open("a", encoding="utf-8") as log:
        log.write(f"\n--- Import from {file.filename} ---\n")

        for i, row in enumerate(reader, start=2):  # start=2 because row 1 is the header
            name = (row.get(col_asset) or "").strip()
            loc_name = (row.get(col_location) or "").strip()

            if not name or not loc_name:
                log.write(f"Line {i}: SKIP (missing ASSET or LOCATION)\n")
                skipped += 1
                continue

            # Find location by name, or auto-create it if it doesn't exist
            cur = db.execute("SELECT id FROM locations WHERE name = ?", (loc_name,))
            loc = cur.fetchone()
            if not loc:
                db.execute("INSERT INTO locations (name) VALUES (?)", (loc_name,))
                db.commit()
                cur = db.execute("SELECT id FROM locations WHERE name = ?", (loc_name,))
                loc = cur.fetchone()

            location_id = loc["id"]

            # Skip if this asset already exists at this location
            cur = db.execute(
                "SELECT id FROM assets WHERE name = ? AND location_id = ?",
                (name, location_id),
            )
            existing = cur.fetchone()
            if existing:
                log.write(f"Line {i}: SKIP duplicate (asset '{name}' at '{loc_name}' already exists, id={existing['id']})\n")
                skipped += 1
                continue

            # Extract optional columns (None if column doesn't exist in CSV)
            category = (row.get(col_category) or None) if col_category else None
            asset_type = (row.get(col_type) or None) if col_type else None
            manufacturer = (row.get(col_manufacturer) or None) if col_manufacturer else None
            model = (row.get(col_model) or None) if col_model else None
            serial_number = (row.get(col_serial) or None) if col_serial else None
            purchase_date = (row.get(col_purchase) or None) if col_purchase else None
            warranty_end_date = (row.get(col_warranty) or None) if col_warranty else None
            notes = (row.get(col_notes) or None) if col_notes else None

            db.execute(
                """
                INSERT INTO assets
                  (name, location_id, category, type, manufacturer, model,
                   serial_number, purchase_date, warranty_end_date, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name, location_id, category or None, asset_type or None,
                    manufacturer or None, model or None, serial_number or None,
                    purchase_date or None, warranty_end_date or None, "Running",
                    notes or None,
                ),
            )
            imported += 1
            log.write(f"Line {i}: IMPORTED asset '{name}' at '{loc_name}'\n")

        db.commit()
        log.write(f"Summary: imported={imported}, skipped={skipped}\n")

    logger.info(f"CSV import from '{file.filename}': {imported} imported, {skipped} skipped")

    return templates.TemplateResponse(
        "asset_import.html",
        {"request": request, "imported": imported, "skipped": skipped, "log_path": str(ASSET_IMPORT_LOG)},
    )
