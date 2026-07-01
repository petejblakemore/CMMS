-- cmms_schema.sql
--
-- Full database schema for Home CMMS – Plas Gwernoer
-- Run with: sqlite3 data/cmms.db < cmms_schema.sql

CREATE TABLE locations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    parent_id       INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    description     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    active          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE assets (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    location_id         INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    category            TEXT,
    type                TEXT,
    manufacturer        TEXT,
    model               TEXT,
    serial_number       TEXT,
    purchase_date       TEXT,
    warranty_end_date   TEXT,
    status              TEXT NOT NULL DEFAULT 'Running',
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    cost                REAL,
    vendor              TEXT
);

CREATE INDEX idx_assets_location ON assets(location_id);
CREATE INDEX idx_assets_status   ON assets(status);

CREATE TABLE maintenance_plans (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id            INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    description         TEXT,
    frequency_unit      TEXT NOT NULL,
    frequency_value     INTEGER NOT NULL,
    last_done_date      TEXT,
    next_due_date       TEXT,
    active              INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    location_id         INTEGER REFERENCES locations(id) ON DELETE SET NULL
);

CREATE INDEX idx_maintenance_asset   ON maintenance_plans(asset_id);
CREATE INDEX idx_maintenance_nextdue ON maintenance_plans(next_due_date);

CREATE TABLE work_orders (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id                INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    location_id             INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    title                   TEXT NOT NULL,
    description             TEXT,
    status                  TEXT NOT NULL DEFAULT 'Open',
    priority                TEXT NOT NULL DEFAULT 'Normal',
    source                  TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    due_date                TEXT,
    completed_at            TEXT,
    closed_notes            TEXT,
    estimated_hours         REAL,
    estimated_labour_cost   REAL,
    estimated_material_cost REAL,
    actual_labour_cost      REAL,
    actual_material_cost    REAL
);

CREATE INDEX idx_work_orders_status   ON work_orders(status);
CREATE INDEX idx_work_orders_duedate  ON work_orders(due_date);
CREATE INDEX idx_work_orders_location ON work_orders(location_id);

CREATE TABLE work_order_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id   INTEGER NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    event_time      TEXT NOT NULL DEFAULT (datetime('now')),
    old_status      TEXT,
    new_status      TEXT,
    note            TEXT
);

CREATE INDEX idx_wo_history_wo ON work_order_history(work_order_id);

CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    display_name    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE job_plan_steps (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    maintenance_plan_id INTEGER NOT NULL REFERENCES maintenance_plans(id) ON DELETE CASCADE,
    step_number         INTEGER NOT NULL,
    description         TEXT NOT NULL,
    notes               TEXT
);

CREATE INDEX idx_job_steps_plan ON job_plan_steps(maintenance_plan_id);

CREATE TABLE projects (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    title                   TEXT NOT NULL,
    description             TEXT,
    location_id             INTEGER REFERENCES locations(id),
    asset_id                INTEGER REFERENCES assets(id),
    status                  TEXT NOT NULL DEFAULT 'Planning',
    estimated_labour_cost   REAL,
    estimated_material_cost REAL,
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE project_tasks (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id              INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_task_id          INTEGER REFERENCES project_tasks(id) ON DELETE SET NULL,
    title                   TEXT NOT NULL,
    description             TEXT,
    depends_on_id           INTEGER REFERENCES project_tasks(id) ON DELETE SET NULL,
    status                  TEXT NOT NULL DEFAULT 'Pending',
    work_order_id           INTEGER REFERENCES work_orders(id),
    sort_order              INTEGER NOT NULL DEFAULT 0,
    estimated_hours         REAL,
    estimated_labour_cost   REAL,
    estimated_material_cost REAL,
    actual_hours            REAL,
    actual_labour_cost      REAL,
    actual_material_cost    REAL,
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_project_tasks_project ON project_tasks(project_id);
CREATE INDEX idx_project_tasks_depends ON project_tasks(depends_on_id);
CREATE INDEX idx_project_tasks_wo      ON project_tasks(work_order_id);

-- Views

CREATE VIEW v_assets AS
SELECT
    a.id AS asset_id, a.name AS asset_name, a.category, a.type, a.status,
    l.id AS location_id, l.name AS location_name,
    a.manufacturer, a.model, a.serial_number,
    a.purchase_date, a.warranty_end_date, a.cost, a.vendor
FROM assets a
JOIN locations l ON l.id = a.location_id;

CREATE VIEW v_open_work_orders AS
SELECT
    w.id              AS work_order_id,
    w.title, w.status, w.priority, w.due_date, w.created_at,
    a.id              AS asset_id,
    a.name            AS asset_name,
    l.id              AS location_id,
    l.name            AS location_name
FROM work_orders w
LEFT JOIN assets a   ON a.id = w.asset_id
LEFT JOIN locations l ON l.id = COALESCE(w.location_id, a.location_id)
WHERE w.status IN ('Open', 'In Progress', 'Queued', 'Icebox');

CREATE VIEW v_queued_work_orders AS
SELECT
    w.id              AS work_order_id,
    w.title, w.status, w.priority, w.due_date, w.created_at,
    a.id              AS asset_id,
    a.name            AS asset_name,
    l.id              AS location_id,
    l.name            AS location_name
FROM work_orders w
LEFT JOIN assets a    ON a.id = w.asset_id
LEFT JOIN locations l ON l.id = COALESCE(w.location_id, a.location_id)
WHERE w.status = 'Queued';

CREATE VIEW v_upcoming_pm AS
SELECT
    mp.id             AS plan_id,
    mp.title, mp.description, mp.next_due_date,
    a.id              AS asset_id,
    a.name            AS asset_name,
    l.id              AS location_id,
    l.name            AS location_name
FROM maintenance_plans mp
JOIN assets a ON a.id = mp.asset_id
JOIN locations l ON l.id = a.location_id
WHERE mp.active = 1
  AND mp.next_due_date IS NOT NULL;
