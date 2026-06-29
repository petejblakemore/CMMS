# Projects Module — Design Document (v2)

## Overview

A Projects module for grouping related maintenance tasks into a single manageable unit. Projects contain ordered tasks with dependencies, cost tracking, and optional links to work orders.

## Decisions Made

| Question | Decision |
|----------|----------|
| Currency | Single currency per install. User sets their currency symbol (£, $, €) as a global setting. Display that symbol with all costs. |
| Hours vs cost | Separate fields. Hours for scheduling, cost for budgeting. Both manual entry. |
| Labour rate | Manual entry. No auto-calculation from hours. Project level can have a total labour cost. |
| Actual cost timing | Required before closing a WO that has estimated costs. |
| Materials tracking | Simple `actual_material_cost` number for now. Full materials/inventory module is a future feature. |
| Project templates | Icebox — nice to have, not for v1. |
| Reporting | % complete with graphical indicator. Overdue tasks on dashboard by project. Cost by location/asset is a stretch goal. |
| Interface | Functional first, graphically polished later. |

---

## Schema

### Global setting (add to config.py)

```python
CURRENCY_SYMBOL = "£"  # Change to "$" or "€" as needed
```

Pass this to all templates via a template global or include in each response.

### projects

```sql
CREATE TABLE projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    description     TEXT,
    location_id     INTEGER REFERENCES locations(id),
    asset_id        INTEGER REFERENCES assets(id),
    status          TEXT NOT NULL DEFAULT 'Planning',
    estimated_labour_cost   REAL,
    estimated_material_cost REAL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Statuses:** Planning → Active → Complete | On Hold

### project_tasks

```sql
CREATE TABLE project_tasks (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id              INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_task_id          INTEGER REFERENCES project_tasks(id) ON DELETE SET NULL,
    title                   TEXT NOT NULL,
    description             TEXT,
    depends_on_id           INTEGER REFERENCES project_tasks(id),
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
```

**Statuses:** Pending → In Progress → Done | Blocked

### work_orders (new columns)

```sql
ALTER TABLE work_orders ADD COLUMN estimated_labour_cost REAL;
ALTER TABLE work_orders ADD COLUMN estimated_material_cost REAL;
ALTER TABLE work_orders ADD COLUMN actual_labour_cost REAL;
ALTER TABLE work_orders ADD COLUMN actual_material_cost REAL;
```

Note: `estimated_hours` already exists on work_orders.

---

## Cost Tracking

### Entry points

| Level | Estimated | Actual |
|-------|-----------|--------|
| Project | Manual overall estimate (labour + materials) | Auto-calculated: sum of task actuals |
| Task | Manual per-task estimate (hours, labour cost, material cost) | Manual entry, or pulled from linked WO |
| Work order | Manual estimate (hours, labour cost, material cost) | Manual entry — required before closing if estimates exist |

### Rollup

```
Project actual labour    = SUM(task actual_labour_cost)
Project actual materials = SUM(task actual_material_cost)
Project actual total     = labour + materials
Project actual hours     = SUM(task actual_hours)

Task actual costs = linked WO actuals (if WO exists) OR manual entry
```

### Display

All costs shown with the global currency symbol: `£1,250.00`

### Project summary view

| | Estimated | Actual | Variance |
|---|----------|--------|----------|
| Hours | 24h | 18h | -6h |
| Labour | £800.00 | £650.00 | -£150.00 |
| Materials | £400.00 | £375.00 | -£25.00 |
| **Total** | **£1,200.00** | **£1,025.00** | **-£175.00** |

Progress bar showing % complete (done tasks / total tasks).

---

## Business Rules

1. **Closing a WO with estimates requires actuals.** If `estimated_labour_cost` or `estimated_material_cost` is set, the user must enter actual costs before setting status to "Done". The form shows an error message if actuals are missing.

2. **Task dependencies.** A task with `depends_on_id` set cannot be started until the dependency task is "Done". UI shows it as "Blocked".

3. **Completing a task unblocks dependents.** When a task is marked "Done", any task that depends on it changes from "Blocked" to "Pending".

4. **Task ↔ Work order link.** A task can optionally generate a work order. The WO's actual costs flow back to the task. If the task has no linked WO, actual costs are entered directly on the task.

5. **Project completion.** A project can only be set to "Complete" when all its tasks are "Done".

6. **Currency symbol.** Set once in `config.py` as `CURRENCY_SYMBOL`. Displayed throughout the app. No currency conversion.

---

## Pages and Routes

### Project list — `/projects`
- Filterable by status, location, asset
- Shows: title, status, location, asset, % complete (graphical progress bar), estimated vs actual cost
- Click title to view project detail

### New project — `/projects/new`
- Title, description, location (hierarchical dropdown), asset, estimated labour cost, estimated material cost

### Project detail — `/projects/{id}`
- Project info at top (title, description, status, location, asset)
- **Progress bar** showing % complete (tasks done / total tasks)
- **Cost summary table** (estimated vs actual vs variance for hours, labour, materials)
- **Task list** below with:
  - Sort order, title, dependency indicator, status badge
  - Estimated and actual costs per task
  - "Add task" form at bottom
  - Inline "Complete" button per task
  - "Generate WO" button per task (creates a linked work order)

### Edit project — `/projects/{id}/edit`
- Edit title, description, location, asset, status, estimated costs
- Cannot set status to "Complete" unless all tasks are done

### Task management (all on the project detail page)
- Add task: title, description, estimated hours/costs, dependency dropdown
- Edit task: click to expand/edit
- Delete task: remove with confirmation
- Reorder tasks: move up/down buttons
- Complete task: inline button, enters actual costs
- Generate WO: creates a linked work order from the task

---

## Dashboard Integration

### Overdue tasks by project
On the main dashboard, show projects with overdue or blocked tasks:

| Project | Overdue | Blocked | % Complete |
|---------|---------|---------|------------|
| Paint Front Door | 2 tasks | 1 task | 37% |
| Bathroom Renovation | 0 | 3 tasks | 10% |

Clickable to go to the project detail page.

---

## Future Features (Icebox)

- Project templates (save/reuse project structures)
- Full materials/inventory tracking
- Cost by location/asset reporting
- Graphically polished interface
- Gantt chart view for project timeline
- Calendar integration

---

## Build Order

| Phase | What | Estimate |
|-------|------|----------|
| 1 | Projects + tasks CRUD (no costing, no dependencies) | 1 session |
| 2 | WO costing (estimated/actual labour + materials, close-gate) | 0.5 session |
| 3 | Task + project costing with rollup and progress bar | 1 session |
| 4 | Task dependencies and blocking logic | 0.5 session |
| 5 | Generate WO from task, link costs back | 0.5 session |
| 6 | Dashboard integration (overdue tasks by project) | 0.5 session |
| **Total** | | **~4 sessions** |

Each phase is independently testable and useful.
