# Home CMMS – Plas Gwernoer

A self-hosted Computerized Maintenance Management System for the Plas Gwernoer estate, built with Python, FastAPI, SQLite, and Jinja2 templates.

## What it manages

- **Locations** — hierarchical (Plas Gwernoer → Workshop, Farm, Vehicles, etc.)
- **Assets** — equipment and property items at each location
- **Work orders** — with status tracking, priority, due dates, and full audit history
- **Users** — multi-user access with bcrypt-hashed passwords
- **Preventive maintenance plans** — scheduled recurring tasks (planned)

## Prerequisites

- Python 3.9+
- pip

## Quick start

```bash
# Clone the repo
git clone https://github.com/petejblakemore/CMMS.git
cd CMMS

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialise the database (first time only)
sqlite3 cmms.db < cmms_schema.sql

# Generate a secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Set the secret key and start the server
export CMMS_SECRET_KEY="paste-your-generated-key-here"
uvicorn cmms_ui:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` in your browser. On first run you'll be prompted to create an admin account.

## Project structure

```
CMMS/
├── cmms_ui.py              # App entry point — FastAPI setup + middleware
├── config.py               # Paths, validation constants, shared settings
├── db.py                   # DB connection, templates, shared helpers
├── routes/
│   ├── __init__.py
│   ├── auth.py             # Login, logout, first-run setup
│   ├── dashboard.py        # Home page
│   ├── locations.py        # Location CRUD + soft delete
│   ├── assets.py           # Asset CRUD + CSV import + delete
│   ├── work_orders.py      # Work order CRUD + status updates + delete
│   └── users.py            # User management (create, edit, delete)
├── templates/
│   ├── base.html           # Shared layout with nav
│   ├── index.html          # Dashboard
│   ├── login.html          # Login page
│   ├── setup.html          # First-run admin setup
│   ├── confirm_delete.html # Shared delete confirmation
│   ├── locations.html
│   ├── location_form.html
│   ├── location_edit.html
│   ├── assets.html
│   ├── asset_form.html
│   ├── asset_edit.html
│   ├── asset_import.html
│   ├── work_orders.html
│   ├── work_orders_queued.html
│   ├── work_order_form.html
│   ├── work_order_edit.html
│   ├── users.html
│   ├── user_form.html
│   └── user_edit.html
├── static/
│   └── style.css
├── imports/
│   └── asset.csv           # Sample CSV for asset import
├── cmms_schema.sql         # Full database schema (tables, views, indexes)
├── rebuild_cmms.db.sql     # Rebuild script for fresh database
├── regenkey.sh             # Generate a new secret key
├── startup.sh              # Server start script
└── requirements.txt
```

## Features

### Locations
- Hierarchical tree structure with parent-child relationships
- Create, edit, and deactivate (soft delete)
- Deactivated locations hidden from all dropdowns and forms
- Cannot deactivate a location with open work orders

### Assets
- Full CRUD with sortable, filterable list views
- Filter by location, category, status, or manufacturer
- Category and type fields with auto-suggest from existing values
- CSV bulk import with duplicate detection and logging
- Cannot delete an asset with open work orders

### Work orders
- Status workflow: Open → In Progress → Done (also Queued and Cancelled)
- Priority levels: Low, Normal, High, Urgent (with correct sort ordering)
- Inline status and due date updates from the list view
- Full edit screen via click on work order ID
- Separate queued work orders view with filtering
- Status change audit trail in `work_order_history`
- Server-side validation on status and priority values
- Completed work orders cannot be deleted

### Users
- Create, edit, and delete user accounts
- Password reset via edit screen
- Cannot delete your own account or the last remaining user

## Database

SQLite database with 6 tables:

| Table | Purpose |
|-------|---------|
| `locations` | Hierarchical location tree with active/inactive flag |
| `assets` | Equipment and property items linked to locations |
| `work_orders` | Maintenance tasks with status, priority, and due dates |
| `work_order_history` | Audit trail of all status changes |
| `maintenance_plans` | Recurring maintenance schedules (planned) |
| `users` | Login credentials with bcrypt-hashed passwords |

4 views join related tables for list pages:
- `v_assets` — assets with location names
- `v_open_work_orders` — open, in-progress, and queued work orders
- `v_queued_work_orders` — queued work orders only
- `v_upcoming_pm` — preventive maintenance tasks due within 90 days

### Schema changes

The schema file (`cmms_schema.sql`) is a full rebuild script. To apply changes to an existing database without losing data, run individual ALTER/CREATE statements directly:

```bash
sqlite3 cmms.db "ALTER TABLE ..."
```

## CSV asset import

Upload a CSV at `/assets/import`. Required columns (case-insensitive):

- `ASSET` — asset name
- `LOCATION` — location name (auto-created if it doesn't exist)

Optional columns: `CATEGORY`, `TYPE`, `MANUFACTURER`, `MODEL`, `SERIAL #`, `DATE PURCHASED`, `WARRANTY ENDS`, `NOTES`

Duplicate assets (same name + location) are skipped. Import activity is logged to `asset_import.log`.

## Authentication

Session-based login with bcrypt password hashing. Sessions last 7 days.

- First run redirects to `/setup` to create the admin account
- All pages require authentication except `/login` and `/setup`
- Set `CMMS_SECRET_KEY` environment variable for session signing
- Use `regenkey.sh` to generate a new secret key
- Never commit your secret key to the repository

## Deployment

### Local development
```bash
uvicorn cmms_ui:app --host 127.0.0.1 --port 8000 --reload
```

### LAN server
```bash
export CMMS_SECRET_KEY="your-secret-key"
uvicorn cmms_ui:app --host 0.0.0.0 --port 8000 --reload
```

Or use the provided `startup.sh` script.

### Synology NAS
Deploy using Docker or a Python virtual environment. Set `CMMS_SECRET_KEY` in your container environment and bind to port 8000.

## License

GPL-3.0
