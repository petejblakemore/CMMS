# cmms_ui.py
#
# Home CMMS – Plas Gwernoer
#
# FastAPI + SQLite + Jinja2 UI for:
#   - Locations (hierarchy)
#   - Assets
#   - Work orders (including:
#       * status + due_date on create
#       * inline status + due_date updates
#       * sortable work-order lists
#       * full edit screen via clicking the ID)
#   - Session-based authentication
#

import csv
import os
import sqlite3
from pathlib import Path
from typing import List, Optional

import bcrypt as _bcrypt

VALID_STATUSES = {"Open", "In Progress", "Queued", "Done", "Cancelled"}
VALID_PRIORITIES = {"Low", "Normal", "High", "Urgent"}
VALID_ASSET_STATUSES = {"Running", "Needs Maintenance", "Out of Service"}


from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# from passlib.hash import bcrypt
from starlette.middleware.base import BaseHTTPMiddleware

# NEW: imports for session-based authentication
from starlette.middleware.sessions import SessionMiddleware

# Adding CSRF Protection
#from starlette_csrf import CSRFMiddleware

# Path to the SQLite database file (cmms.db lives alongside this script)
DB_PATH = Path(__file__).parent / "cmms.db"

# Create the FastAPI application instance
app = FastAPI(title="Home CMMS – Plas Gwernoer")

# Base directory for templates and static files
BASE_DIR = Path(__file__).parent

# Configure Jinja2 templates directory
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Mount static files (CSS, JS, images, etc.) under /static
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# --- Auth middleware (class-based for reliable ordering) ---------------------
#
# WHY class-based instead of @app.middleware("http"):
# The @app.middleware decorator creates middleware that always ends up
# outermost in the stack, running BEFORE SessionMiddleware — which means
# request.session doesn't exist yet. Using a class with app.add_middleware()
# gives us explicit control over the execution order.


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Let login, setup, and static files through without auth
        public_paths = ["/login", "/setup"]
        if request.url.path in public_paths or request.url.path.startswith("/static"):
            return await call_next(request)

        user_id = request.session.get("user_id")
        if not user_id:
            # No session — check if any users exist yet
            conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                count = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()[
                    "count"
                ]
            finally:
                conn.close()

            # First-run: no users exist, redirect to setup page
            if count == 0:
                return RedirectResponse(
                    url="/setup", status_code=status.HTTP_303_SEE_OTHER
                )

            # Users exist but not logged in — show login page
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

        return await call_next(request)


# WHY this order matters:
# add_middleware stacks inside-out: first added = innermost, last added = outermost.
# Request flow: SessionMiddleware (outermost, runs first, sets up session)
#             → AuthMiddleware (innermost, runs second, reads session)
# Now added CSRF
app.add_middleware(AuthMiddleware)
#app.add_middleware(
#    CSRFMiddleware,
#    secret=os.environ.get("CMMS_SECRET_KEY", "the-rain-in-spain-falls-mainly"),
#)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("CMMS_SECRET_KEY", "the-rain-in-spain-falls-mainly"),
    max_age=60 * 60 * 24 * 7,
)


# --- DB helper ---------------------------------------------------------------


def get_db():
    """
    Dependency that provides a SQLite connection per request.
    """
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# --- Auth helpers ------------------------------------------------------------


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return _bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# --- Utility -----------------------------------------------------------------


def dicts(rows: List[sqlite3.Row]):
    """
    Convert a list of sqlite3.Row objects into a list of plain dicts.
    """
    return [dict(r) for r in rows]


# --- Locations: tree builder -------------------------------------------------


def build_location_tree(locations):
    """
    Build a nested tree structure from a flat list of locations.
    """
    by_id = {loc["id"]: {**loc, "children": []} for loc in locations}
    roots = []

    for loc in by_id.values():
        parent_id = loc.get("parent_id")
        if parent_id is None:
            roots.append(loc)
        else:
            parent = by_id.get(parent_id)
            if parent:
                parent["children"].append(loc)
            else:
                roots.append(loc)

    def sort_children(node):
        node["children"].sort(key=lambda c: c["name"])
        for child in node["children"]:
            sort_children(child)

    for r in roots:
        sort_children(r)

    roots.sort(key=lambda r: r["name"])
    return roots


# --- Auth routes -------------------------------------------------------------


@app.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": None},
    )


@app.post("/login")
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


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/setup")
async def setup_form(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """
    First-run setup: create the admin account.
    Only accessible when no users exist in the database.
    """
    cur = db.execute("SELECT COUNT(*) as count FROM users")
    if cur.fetchone()["count"] > 0:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        "setup.html",
        {"request": request, "error": None},
    )


@app.post("/setup")
async def setup_create_admin(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
):
    # Block setup if any user already exists
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


# --- Routes: dashboard -------------------------------------------------------


@app.get("/")
async def index(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """
    Dashboard / home page.
    """
    locations_flat = dicts(db.execute("SELECT * FROM locations WHERE active = 1"))
    location_tree = build_location_tree(locations_flat)

    assets = dicts(
        db.execute("SELECT * FROM v_assets ORDER BY location_name, asset_name")
    )

    open_wos = dicts(
        db.execute(
            "SELECT * FROM v_open_work_orders "
            "ORDER BY CASE priority "
            "  WHEN 'Urgent' THEN 3 WHEN 'High' THEN 2 "
            "  WHEN 'Normal' THEN 1 WHEN 'Low' THEN 0 ELSE -1 END DESC, "
            "due_date IS NULL, due_date"
        )
    )


    upcoming_pm = dicts(
        db.execute(
            "SELECT * FROM v_upcoming_pm "
            "WHERE date(next_due_date) <= date('now','+90 day') "
            "ORDER BY next_due_date"
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
        },
    )


# --- Locations ---------------------------------------------------------------


@app.get("/locations")
async def list_locations(request: Request, db: sqlite3.Connection = Depends(get_db)):
    locations_flat = dicts(db.execute("SELECT * FROM locations"))
    location_tree = build_location_tree(locations_flat)
    return templates.TemplateResponse(
        "locations.html",
        {"request": request, "locations": location_tree},
    )


@app.get("/locations/new")
async def new_location_form(request: Request, db: sqlite3.Connection = Depends(get_db)):
    parents = dicts(db.execute("SELECT id, name FROM locations ORDER BY name"))
    return templates.TemplateResponse(
        "location_form.html",
        {"request": request, "parents": parents},
    )


@app.post("/locations/new")
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


# --- Assets ------------------------------------------------------------------


@app.get("/assets")
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

    sort_col = sortable_columns.get(sort, "asset_name")
    dir_sql = "DESC" if direction.lower() == "desc" else "ASC"

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

    locations_list = sorted({r["location_name"] for r in db.execute("SELECT DISTINCT location_name FROM v_assets")})
    categories_list = sorted({r["category"] for r in db.execute("SELECT DISTINCT category FROM v_assets WHERE category IS NOT NULL")})
    statuses_list = sorted({r["status"] for r in db.execute("SELECT DISTINCT status FROM v_assets WHERE status IS NOT NULL")})
    manufacturers_list = sorted({r["manufacturer"] for r in db.execute("SELECT DISTINCT manufacturer FROM v_assets WHERE manufacturer IS NOT NULL")})

    return templates.TemplateResponse(
        "assets.html",
        {
            "request": request,
            "assets": assets,
            "locations_list": locations_list,
            "categories_list": categories_list,
            "statuses_list": statuses_list,
            "manufacturers_list": manufacturers_list,
            "f_location": location or "",
            "f_category": category or "",
            "f_status": asset_status or "",
            "f_manufacturer": manufacturer or "",
            "sort": sort,
            "direction": direction,
        },
    )


@app.get("/assets/new")
async def new_asset_form(request: Request, db: sqlite3.Connection = Depends(get_db)):
    locations = dicts(
        db.execute("SELECT id, name FROM locations WHERE active = 1 ORDER BY name")
    )

    categories = sorted(
        {
            row["category"]
            for row in db.execute(
                "SELECT DISTINCT category FROM assets WHERE category IS NOT NULL"
            )
        }
    )
    types = sorted(
        {
            row["type"]
            for row in db.execute(
                "SELECT DISTINCT type FROM assets WHERE type IS NOT NULL"
            )
        }
    )

    return templates.TemplateResponse(
        "asset_form.html",
        {
            "request": request,
            "locations": locations,
            "categories": categories,
            "types": types,
        },
    )


@app.post("/assets/new")
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
    notes: Optional[str] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    db.execute(
        """
        INSERT INTO assets
          (name, location_id, category, type, status, manufacturer, model,
           serial_number, purchase_date, warranty_end_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name.strip(),
            location_id,
            category or None,
            asset_type or None,
            asset_status or "Running",
            manufacturer or None,
            model or None,
            serial_number or None,
            purchase_date or None,
            warranty_end_date or None,
            notes or None,
        ),
    )
    db.commit()

    return RedirectResponse(url="/assets", status_code=status.HTTP_303_SEE_OTHER)


# --- Assets: edit ------------------------------------------------------------


@app.get("/assets/{asset_id}/edit")
async def edit_asset_form(
    request: Request,
    asset_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset = dict(row)

    locations = dicts(
        db.execute("SELECT id, name FROM locations WHERE active = 1 ORDER BY name")
    )

    categories = sorted(
        {
            r["category"]
            for r in db.execute(
                "SELECT DISTINCT category FROM assets WHERE category IS NOT NULL"
            )
        }
    )
    types = sorted(
        {
            row["type"]
            for row in db.execute(
                "SELECT DISTINCT type FROM assets WHERE type IS NOT NULL"
            )
        }
    )


    return templates.TemplateResponse(
        "asset_edit.html",
        {
            "request": request,
            "asset": asset,
            "locations": locations,
            "categories": categories,
            "types": types,
        },
    )


@app.post("/assets/{asset_id}/edit")
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
    notes: Optional[str] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT id FROM assets WHERE id = ?", (asset_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Asset not found")

    db.execute(
        """
        UPDATE assets
        SET name              = ?,
            location_id       = ?,
            category          = ?,
            type              = ?,
            status            = ?,
            manufacturer      = ?,
            model             = ?,
            serial_number     = ?,
            purchase_date     = ?,
            warranty_end_date = ?,
            notes             = ?
        WHERE id = ?
        """,
        (
            name.strip(),
            location_id,
            category or None,
            asset_type or None,
            asset_status or "Running",
            manufacturer or None,
            model or None,
            serial_number or None,
            purchase_date or None,
            warranty_end_date or None,
            notes or None,
            asset_id,
        ),
    )
    db.commit()

    return RedirectResponse(url="/assets", status_code=status.HTTP_303_SEE_OTHER)


# --- Assets: CSV import ------------------------------------------------------

ASSET_IMPORT_LOG = BASE_DIR / "asset_import.log"


@app.get("/assets/import")
async def import_assets_form(request: Request):
    return templates.TemplateResponse(
        "asset_import.html",
        {"request": request},
    )


@app.post("/assets/import")
async def import_assets_csv(
    request: Request,
    file: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
):
    raw = await file.read()
    text_lines = raw.decode("utf-8", errors="replace").splitlines()

    if not text_lines:
        return templates.TemplateResponse(
            "asset_import.html",
            {"request": request, "error": "Empty CSV file."},
        )

    reader = csv.DictReader(text_lines)

    headers = [h.upper() for h in (reader.fieldnames or [])]
    header_map = {h.upper(): h for h in (reader.fieldnames or [])}

    def get_col(name: str):
        return header_map.get(name.upper())

    required = {"ASSET", "LOCATION"}
    missing = {col for col in required if col not in headers}
    if missing:
        return templates.TemplateResponse(
            "asset_import.html",
            {
                "request": request,
                "error": f"Missing required column(s): {', '.join(sorted(missing))}",
            },
        )

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

        for i, row in enumerate(reader, start=2):
            name = (row.get(col_asset) or "").strip()
            loc_name = (row.get(col_location) or "").strip()

            if not name or not loc_name:
                log.write(f"Line {i}: SKIP (missing ASSET or LOCATION)\n")
                skipped += 1
                continue

            cur = db.execute(
                "SELECT id FROM locations WHERE name = ?",
                (loc_name,),
            )
            loc = cur.fetchone()
            if not loc:
                db.execute(
                    "INSERT INTO locations (name) VALUES (?)",
                    (loc_name,),
                )
                db.commit()
                cur = db.execute(
                    "SELECT id FROM locations WHERE name = ?",
                    (loc_name,),
                )
                loc = cur.fetchone()

            location_id = loc["id"]

            cur = db.execute(
                "SELECT id FROM assets WHERE name = ? AND location_id = ?",
                (name, location_id),
            )
            existing = cur.fetchone()
            if existing:
                log.write(
                    f"Line {i}: SKIP duplicate (asset '{name}' at '{loc_name}' already exists, id={existing['id']})\n"
                )
                skipped += 1
                continue

            category = (row.get(col_category) or None) if col_category else None
            asset_type = (row.get(col_type) or None) if col_type else None
            manufacturer = (
                (row.get(col_manufacturer) or None) if col_manufacturer else None
            )
            model = (row.get(col_model) or None) if col_model else None
            serial_number = (row.get(col_serial) or None) if col_serial else None
            purchase_date = (row.get(col_purchase) or None) if col_purchase else None
            warranty_end_date = (
                (row.get(col_warranty) or None) if col_warranty else None
            )
            notes = (row.get(col_notes) or None) if col_notes else None

            status_val = "Running"

            db.execute(
                """
                INSERT INTO assets
                  (name, location_id, category, type, manufacturer, model,
                   serial_number, purchase_date, warranty_end_date, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    location_id,
                    category or None,
                    asset_type or None,
                    manufacturer or None,
                    model or None,
                    serial_number or None,
                    purchase_date or None,
                    warranty_end_date or None,
                    status_val,
                    notes or None,
                ),
            )
            imported += 1
            log.write(f"Line {i}: IMPORTED asset '{name}' at '{loc_name}'\n")

        db.commit()
        log.write(f"Summary: imported={imported}, skipped={skipped}\n")

    return templates.TemplateResponse(
        "asset_import.html",
        {
            "request": request,
            "imported": imported,
            "skipped": skipped,
            "log_path": str(ASSET_IMPORT_LOG),
        },
    )


# --- Work Orders: list + sorting ---------------------------------------------


@app.get("/work_orders")
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
    sortable_columns = {
        "id": "work_order_id",
        "title": "title",
        "status": "status",
        "priority": "priority",
        "due_date": "due_date",
        "created_at": "created_at",
    }

    sort_col = sortable_columns.get(sort, "priority")
    dir_sql = "DESC" if direction.lower() == "desc" else "ASC"

    where_clauses = []
    params = []

    if wo_status:
        where_clauses.append("status = ?")
        params.append(wo_status)
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

    open_wos = dicts(
        db.execute(
            f"""
            SELECT * FROM v_open_work_orders
            WHERE 1=1 {extra_where}
            ORDER BY
              CASE
                WHEN ? = 'priority' THEN
                  CASE priority
                    WHEN 'Urgent' THEN 3
                    WHEN 'High'   THEN 2
                    WHEN 'Normal' THEN 1
                    WHEN 'Low'    THEN 0
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

    closed_wos = dicts(
        db.execute(
            "SELECT * FROM work_orders "
            "WHERE status = 'Done' "
            "ORDER BY completed_at DESC LIMIT 50"
        )
    )

    wo_statuses_list = ["Open", "In Progress", "Queued"]
    wo_priorities_list = ["Low", "Normal", "High", "Urgent"]
    wo_locations_list = sorted(
        {
            r["location_name"]
            for r in db.execute(
                "SELECT DISTINCT location_name FROM v_open_work_orders WHERE location_name IS NOT NULL"
            )
        }
    )
    wo_assets_list = sorted(
        {
            r["asset_name"]
            for r in db.execute(
                "SELECT DISTINCT asset_name FROM v_open_work_orders WHERE asset_name IS NOT NULL"
            )
        }
    )

    return templates.TemplateResponse(
        "work_orders.html",
        {
            "request": request,
            "open_wos": open_wos,
            "closed_wos": closed_wos,
            "sort": sort,
            "direction": direction,
            "wo_statuses_list": wo_statuses_list,
            "wo_priorities_list": wo_priorities_list,
            "wo_locations_list": wo_locations_list,
            "wo_assets_list": wo_assets_list,
            "f_status": wo_status or "",
            "f_priority": priority or "",
            "f_location": location or "",
            "f_asset": asset or "",
        },
    )


@app.get("/work_orders/queued")
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
        "id": "work_order_id",
        "title": "title",
        "status": "status",
        "priority": "priority",
        "due_date": "due_date",
        "location": "location_name",
        "asset": "asset_name",
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
                    WHEN 'Urgent' THEN 3
                    WHEN 'High'   THEN 2
                    WHEN 'Normal' THEN 1
                    WHEN 'Low'    THEN 0
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
    q_locations_list = sorted(
        {
            r["location_name"]
            for r in db.execute(
                "SELECT DISTINCT location_name FROM v_queued_work_orders WHERE location_name IS NOT NULL AND location_name != ''"
            )
        }
    )
    q_assets_list = sorted(
        {
            r["asset_name"]
            for r in db.execute(
                "SELECT DISTINCT asset_name FROM v_queued_work_orders WHERE asset_name IS NOT NULL AND asset_name != ''"
            )
        }
    )

    return templates.TemplateResponse(
        "work_orders_queued.html",
        {
            "request": request,
            "queued_wos": queued_wos,
            "sort": sort,
            "direction": direction,
            "q_priorities_list": q_priorities_list,
            "q_locations_list": q_locations_list,
            "q_assets_list": q_assets_list,
            "f_priority": priority or "",
            "f_location": location or "",
            "f_asset": asset or "",
        },
    )


# --- Work Orders: create -----------------------------------------------------


@app.get("/work_orders/new")
async def new_work_order_form(
    request: Request, db: sqlite3.Connection = Depends(get_db)
):
    assets = dicts(
        db.execute(
            "SELECT asset_id AS id, asset_name AS name, location_name "
            "FROM v_assets "
            "ORDER BY location_name, asset_name"
        )
    )

    locations = dicts(db.execute("SELECT id, name FROM locations ORDER BY name"))

    return templates.TemplateResponse(
        "work_order_form.html",
        {
            "request": request,
            "assets": assets,
            "locations": locations,
        },
    )


@app.post("/work_orders/new")
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
          (asset_id, location_id, title, description,
           status, priority, source, due_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            asset_val,
            loc_val,
            title.strip(),
            description or None,
            initial_status,
            priority,
            source,
            due_date or None,
        ),
    )
    db.commit()

    return RedirectResponse(url="/work_orders", status_code=status.HTTP_303_SEE_OTHER)


# --- Work Orders: inline status + due_date update ---------------------------


@app.post("/work_orders/{wo_id}/status")
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
        return RedirectResponse(
            url="/work_orders", status_code=status.HTTP_303_SEE_OTHER
        )

    old_status = row["status"]

    if new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    db.execute(
        """
        UPDATE work_orders
        SET status = ?,
            due_date = ?,
            completed_at = CASE
                             WHEN ? = 'Done' AND completed_at IS NULL THEN datetime('now')
                             ELSE completed_at
                           END
        WHERE id = ?
        """,
        (new_status, due_date or None, new_status, wo_id),
    )

    db.execute(
        """
        INSERT INTO work_order_history (work_order_id, old_status, new_status, note)
        VALUES (?, ?, ?, ?)
        """,
        (wo_id, old_status, new_status, note or None),
    )
    db.commit()

    return RedirectResponse(url="/work_orders", status_code=status.HTTP_303_SEE_OTHER)


# --- Work Orders: full edit screen (accessed by clicking ID) -----------------


@app.get("/work_orders/{wo_id}/edit")
async def edit_work_order_form(
    request: Request,
    wo_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute(
        "SELECT * FROM work_orders WHERE id = ?",
        (wo_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Work order not found")

    wo = dict(row)

    assets = dicts(
        db.execute(
            "SELECT asset_id AS id, asset_name AS name, location_name "
            "FROM v_assets "
            "ORDER BY location_name, asset_name"
        )
    )
    locations = dicts(db.execute("SELECT id, name FROM locations ORDER BY name"))

    return templates.TemplateResponse(
        "work_order_edit.html",
        {
            "request": request,
            "wo": wo,
            "assets": assets,
            "locations": locations,
        },
    )


@app.post("/work_orders/{wo_id}/edit")
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
        SET asset_id     = ?,
            location_id  = ?,
            title        = ?,
            description  = ?,
            status       = ?,
            priority     = ?,
            due_date     = ?,
            source       = ?,
            closed_notes = ?,
            completed_at = CASE
                             WHEN ? = 'Done' AND completed_at IS NULL THEN datetime('now')
                             ELSE completed_at
                           END
        WHERE id = ?
        """,
        (
            asset_val,
            loc_val,
            title.strip(),
            description or None,
            status_value,
            priority,
            due_date or None,
            source or None,
            closed_notes or None,
            status_value,
            wo_id,
        ),
    )

    if status_value != old_status:
        db.execute(
            """
            INSERT INTO work_order_history (work_order_id, old_status, new_status, note)
            VALUES (?, ?, ?, ?)
            """,
            (wo_id, old_status, status_value, "Edited via edit form"),
        )

    db.commit()

    return RedirectResponse(url="/work_orders", status_code=status.HTTP_303_SEE_OTHER)


# --- Run with: uvicorn cmms_ui:app --reload ----------------------------------
