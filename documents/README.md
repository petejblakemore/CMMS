# Home CMMS – Plas Gwernoer

A self-hosted Computerized Maintenance Management System for the Plas Gwernoer estate, built with Python, FastAPI, SQLite, and Jinja2 templates.

## What it manages

- **Locations** — hierarchical (Plas Gwernoer → Workshop, Farm, Vehicles, etc.)
- **Assets** — equipment and property items at each location with cost and vendor tracking
- **Work orders** — with status tracking, priority, due dates, Kanban board, calendar, costing (estimated and actual), and full audit history
- **Planned maintenance** — recurring schedules with job plan steps
- **Projects** — grouped tasks with dependencies, cost rollup, linked work orders, and progress tracking
- **Users** — multi-user access with bcrypt-hashed passwords

## Prerequisites

- Python 3.9+
- pip

## Quick start

```
# Clone the repo
git clone https://github.com/petejblakemore/CMMS.git
cd CMMS

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialise the database (first time only)
mkdir -p data
sqlite3 data/cmms.db < cmms_schema.sql

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
│   ├── dashboard.py        # Home page with operational overview
│   ├── locations.py        # Location CRUD + soft delete
│   ├── assets.py           # Asset CRUD + CSV import + delete
│   ├── work_orders.py      # Work order CRUD + board + history + delete + task sync
│   ├── maintenance.py      # Planned maintenance + job plan steps
│   ├── projects.py         # Project CRUD + tasks + dependencies + WO generation
│   └── users.py            # User management (create, edit, delete)
├── templates/              # Jinja2 HTML templates
├── static/
│   └── style.css           # Sidebar layout + Kanban board styles
├── data/                   # Database and runtime files (gitignored)
│   ├── cmms.db             # SQLite database
│   ├── asset_import.log    # CSV import activity log
│   └── *.pem               # SSL certificates (production only)
├── documents/              # Project documentation
├── imports/
│   └── asset.csv           # Sample CSV for asset import
├── cmms_schema.sql         # Full database schema
└── requirements.txt
```

## Features

### Dashboard

- Open work orders count by location (click to filter)
- Open work orders count by asset (click to filter)
- Active projects summary with progress bars, blocked and overdue task counts
- Upcoming preventive maintenance with "Generate Work Orders" button
- Priority-sorted open work orders list

### Locations

- Hierarchical tree structure with parent-child relationships
- Create, edit, and deactivate (soft delete)
- Deactivated locations hidden from all dropdowns and forms
- Cannot deactivate a location with open work orders

### Assets

- Full CRUD with sortable, filterable list views
- Filter by location, category, status, or manufacturer
- Category and type fields with auto-suggest from existing values
- Cost and vendor tracking
- Colour-coded status badges (Running / Needs Maintenance / Out of Service)
- CSV bulk import with duplicate detection and logging
- Cannot delete an asset with open work orders

### Work orders

- Status workflow: Icebox → Open → Queued → In Progress → Done (also Cancelled)
- Priority levels: Low, Normal, High, Urgent (with correct sort ordering)
- Grouped list view with separate sections per status
- **Kanban board** with drag-and-drop status changes
- **Calendar view** with monthly navigation
- Inline status and due date updates from the list view
- Full edit screen via click on work order ID (stays open after saves)
- Costing: estimated and actual labour and material costs
- Close-gate: actual costs required before completing a WO with estimates
- Status change audit trail in `work_order_history`
- Searchable/filterable history page
- Server-side validation on status and priority values
- Completed work orders cannot be deleted
- Cancelled work orders in a collapsible section
- Context-aware navigation: Close button returns to the calling page (projects or work orders list)

### Projects

- Create projects linked to a location and/or asset
- Project statuses: Planning → Active → Complete | On Hold
- **Task management** with ordered tasks, inline status buttons, move up/down, delete
- **Task dependencies** (`depends_on_id`): tasks auto-block when their dependency isn't done, auto-unblock when it is
- **Cost tracking**: estimated and actual hours, labour, and material costs per task, with project-level rollup and variance display
- **Progress bar** showing % complete (done tasks / total tasks)
- **Close-gate**: project cannot be marked Complete until all tasks are Done; tasks with estimates require actual costs
- **Generate Work Order from task**: creates a linked WO pre-populated with task details and project location/asset
- **WO-as-master**: linked tasks mirror WO status automatically (Open→Pending, In Progress→In Progress, Done→Done with cost sync, Cancelled→Pending); task status buttons are disabled for WO-managed tasks
- **Dependency enforcement**: WO cannot be completed if its linked task has an unsatisfied dependency
- **Mark Complete / Reopen** workflow for both projects and individual tasks

### Planned maintenance

- Create recurring maintenance plans against assets or locations
- Configurable frequency (every N days/months/years)
- Job plan steps with notes for tools/materials
- "Complete" action advances the due date and creates a work order
- "Generate Work Orders" button on dashboard batch-processes overdue PMs
- Work orders created from PMs include job plan steps in the description

### Users

- Create, edit, and delete user accounts
- Password reset via edit screen
- Cannot delete your own account or the last remaining user

## Database

SQLite database with 9 tables:

| Table | Purpose |
| --- | --- |
| `locations` | Hierarchical location tree with active/inactive flag |
| `assets` | Equipment with cost, vendor, and status tracking |
| `work_orders` | Maintenance tasks with status, priority, due dates, and costing |
| `work_order_history` | Audit trail of all status changes |
| `maintenance_plans` | Recurring maintenance schedules |
| `job_plan_steps` | Checklist steps for maintenance plans |
| `users` | Login credentials with bcrypt-hashed passwords |
| `projects` | Project groupings with status and location/asset links |
| `project_tasks` | Ordered tasks within projects with dependencies, costs, and WO links |

Views:

- `v_assets` — assets with location names, cost, and vendor
- `v_open_work_orders` — open, in-progress, queued, and icebox work orders
- `v_queued_work_orders` — queued work orders only
- `v_upcoming_pm` — preventive maintenance tasks due within 90 days

## CSV asset import

Upload a CSV at `/assets/import`. Required columns (case-insensitive):

- `ASSET` — asset name
- `LOCATION` — location name (auto-created if it doesn't exist)

Optional columns: `CATEGORY`, `TYPE`, `MANUFACTURER`, `MODEL`, `SERIAL #`, `DATE PURCHASED`, `WARRANTY ENDS`, `NOTES`

Duplicate assets (same name + location) are skipped. Import activity is logged to `data/asset_import.log`.

## Authentication

Session-based login with bcrypt password hashing. Sessions last 7 days.

- First run redirects to `/setup` to create the admin account
- All pages require authentication except `/login` and `/setup`
- Set `CMMS_SECRET_KEY` environment variable for session signing
- Never commit your secret key to the repository

## Deployment

### Local development

```
export CMMS_SECRET_KEY="dev-key"
uvicorn cmms_ui:app --host 127.0.0.1 --port 8000 --reload
```

### LAN server with HTTPS

See `documents/SSL_SETUP.md` for full instructions using `mkcert`.

```
export CMMS_SECRET_KEY="your-secret-key"
uvicorn cmms_ui:app --host 0.0.0.0 --port 8000 --reload \
  --ssl-keyfile=data/192.168.1.224+3-key.pem \
  --ssl-certfile=data/192.168.1.224+3.pem
```

### Dev → Production workflow

See `documents/GIT_WORKFLOW.md` for the full push/pull workflow between machines.

1. Edit and test on Mac Mini (`localhost:8000`)
2. Commit and push to GitHub
3. Pull on production server

### Currency

Set the currency symbol in `config.py`:

```python
CURRENCY_SYMBOL = "£"  # Change to "$" or "€" as needed
```

All costs throughout the app display with this symbol.

## Future features (backlog)

- Gantt chart timeline view for projects
- Home Assistant integration (sensor-triggered work orders)
- Project templates (save/reuse project structures)
- Full materials/inventory tracking
- Cost by location/asset reporting
- Parent hierarchy in asset dropdowns
- Logging implementation across all route files

## License

GPL-3.0
