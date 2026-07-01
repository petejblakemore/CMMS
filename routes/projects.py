# routes/projects.py
#
# Project management routes: list, create, edit, delete projects,
# and manage tasks within projects.
# Phase 4: task dependencies and blocking logic.

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from db import dicts, get_db, get_hierarchical_locations, templates

router = APIRouter()

VALID_PROJECT_STATUSES = {"Planning", "Active", "Complete", "On Hold"}
VALID_TASK_STATUSES = {"Pending", "In Progress", "Done", "Blocked"}


# --- List all projects -------------------------------------------------------

@router.get("/projects")
async def list_projects(
    request: Request,
    project_status: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    query = """
        SELECT p.*,
               l.name AS location_name,
               a.name AS asset_name,
               (SELECT COUNT(*) FROM project_tasks WHERE project_id = p.id) AS total_tasks,
               (SELECT COUNT(*) FROM project_tasks WHERE project_id = p.id AND status = 'Done') AS done_tasks
        FROM projects p
        LEFT JOIN locations l ON l.id = p.location_id
        LEFT JOIN assets a ON a.id = p.asset_id
        WHERE 1=1
    """
    params = []

    if project_status:
        query += " AND p.status = ?"
        params.append(project_status)

    query += " ORDER BY CASE p.status WHEN 'Active' THEN 0 WHEN 'Planning' THEN 1 WHEN 'On Hold' THEN 2 WHEN 'Complete' THEN 3 END, p.title"
    projects = dicts(db.execute(query, params))

    for p in projects:
        total = p["total_tasks"]
        done = p["done_tasks"]
        p["pct_complete"] = round((done / total * 100) if total > 0 else 0)

    return templates.TemplateResponse(
        "projects.html",
        {
            "request": request,
            "projects": projects,
            "f_status": project_status or "",
        },
    )


# --- Create project ----------------------------------------------------------

@router.get("/projects/new")
async def new_project_form(request: Request, db: sqlite3.Connection = Depends(get_db)):
    locations = get_hierarchical_locations(db)
    assets = dicts(db.execute(
        "SELECT asset_id AS id, asset_name AS name, location_name "
        "FROM v_assets ORDER BY location_name, asset_name"
    ))

    return templates.TemplateResponse(
        "project_form.html",
        {"request": request, "locations": locations, "assets": assets, "error": None},
    )


@router.post("/projects/new")
async def create_project(
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    location_id: Optional[int] = Form(None),
    asset_id: Optional[int] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    loc_val = location_id if location_id not in (None, 0) else None
    asset_val = asset_id if asset_id not in (None, 0) else None

    db.execute(
        "INSERT INTO projects (title, description, location_id, asset_id) VALUES (?, ?, ?, ?)",
        (title.strip(), description or None, loc_val, asset_val),
    )
    db.commit()

    return RedirectResponse(url="/projects", status_code=status.HTTP_303_SEE_OTHER)


# --- Project detail (view + manage tasks) ------------------------------------

@router.get("/projects/{project_id}")
async def project_detail(
    request: Request,
    project_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("""
        SELECT p.*, l.name AS location_name, a.name AS asset_name
        FROM projects p
        LEFT JOIN locations l ON l.id = p.location_id
        LEFT JOIN assets a ON a.id = p.asset_id
        WHERE p.id = ?
    """, (project_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    project = dict(row)

    tasks = dicts(db.execute(
        "SELECT * FROM project_tasks WHERE project_id = ? ORDER BY sort_order, id",
        (project_id,),
    ))

    # Build a lookup so we can show dependency names in the template
    task_by_id = {t["id"]: t for t in tasks}
    for t in tasks:
        dep_id = t.get("depends_on_id")
        if dep_id and dep_id in task_by_id:
            t["depends_on_title"] = task_by_id[dep_id]["title"]
            t["dependency_done"] = task_by_id[dep_id]["status"] == "Done"
        else:
            t["depends_on_title"] = None
            t["dependency_done"] = True

    total_tasks = len(tasks)
    done_tasks = sum(1 for t in tasks if t["status"] == "Done")
    pct_complete = round((done_tasks / total_tasks * 100) if total_tasks > 0 else 0)

    cost_summary = {
        "est_hours": sum(t["estimated_hours"] or 0 for t in tasks),
        "est_labour": sum(t["estimated_labour_cost"] or 0 for t in tasks),
        "est_material": sum(t["estimated_material_cost"] or 0 for t in tasks),
        "act_hours": sum(t["actual_hours"] or 0 for t in tasks),
        "act_labour": sum(t["actual_labour_cost"] or 0 for t in tasks),
        "act_material": sum(t["actual_material_cost"] or 0 for t in tasks),
    }
    cost_summary["est_total"] = cost_summary["est_labour"] + cost_summary["est_material"]
    cost_summary["act_total"] = cost_summary["act_labour"] + cost_summary["act_material"]
    cost_summary["var_hours"] = cost_summary["act_hours"] - cost_summary["est_hours"]
    cost_summary["var_labour"] = cost_summary["act_labour"] - cost_summary["est_labour"]
    cost_summary["var_material"] = cost_summary["act_material"] - cost_summary["est_material"]
    cost_summary["var_total"] = cost_summary["act_total"] - cost_summary["est_total"]

    has_costs = cost_summary["est_total"] > 0 or cost_summary["act_total"] > 0

    return templates.TemplateResponse(
        "project_detail.html",
        {
            "request": request,
            "project": project,
            "tasks": tasks,
            "total_tasks": total_tasks,
            "done_tasks": done_tasks,
            "pct_complete": pct_complete,
            "cost": cost_summary,
            "has_costs": has_costs,
        },
    )


# --- Edit project -------------------------------------------------------------

@router.get("/projects/{project_id}/edit")
async def edit_project_form(
    request: Request,
    project_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    project = dict(row)
    locations = get_hierarchical_locations(db)
    assets = dicts(db.execute(
        "SELECT asset_id AS id, asset_name AS name, location_name "
        "FROM v_assets ORDER BY location_name, asset_name"
    ))

    return templates.TemplateResponse(
        "project_edit.html",
        {"request": request, "project": project, "locations": locations, "assets": assets, "error": None},
    )


@router.post("/projects/{project_id}/edit")
async def update_project(
    request: Request,
    project_id: int,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    location_id: Optional[int] = Form(None),
    asset_id: Optional[int] = Form(None),
    project_status: str = Form("Planning"),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Project not found")

    loc_val = location_id if location_id not in (None, 0) else None
    asset_val = asset_id if asset_id not in (None, 0) else None

    if project_status not in VALID_PROJECT_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {project_status}")

    if project_status == "Complete":
        incomplete = db.execute(
            "SELECT COUNT(*) as count FROM project_tasks WHERE project_id = ? AND status != 'Done'",
            (project_id,),
        ).fetchone()["count"]
        if incomplete > 0:
            project = dict(db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())
            locations = get_hierarchical_locations(db)
            assets = dicts(db.execute(
                "SELECT asset_id AS id, asset_name AS name, location_name "
                "FROM v_assets ORDER BY location_name, asset_name"
            ))
            return templates.TemplateResponse(
                "project_edit.html",
                {"request": request, "project": project, "locations": locations,
                 "assets": assets, "error": f"Cannot complete — {incomplete} task(s) are not done."},
            )

    db.execute(
        """
        UPDATE projects
        SET title = ?, description = ?, location_id = ?, asset_id = ?, status = ?
        WHERE id = ?
        """,
        (title.strip(), description or None, loc_val, asset_val, project_status, project_id),
    )
    db.commit()

    return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)


# --- Delete project -----------------------------------------------------------

@router.get("/projects/{project_id}/delete")
async def delete_project_confirm(
    request: Request,
    project_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    project = dict(row)
    task_count = db.execute(
        "SELECT COUNT(*) as count FROM project_tasks WHERE project_id = ?", (project_id,)
    ).fetchone()["count"]

    details = [f"Title: {project['title']}", f"Status: {project['status']}"]
    if task_count:
        details.append(f"{task_count} task(s) will also be deleted")

    return templates.TemplateResponse(
        "confirm_delete.html",
        {
            "request": request,
            "heading": f"Delete project: {project['title']}",
            "message": f"Are you sure you want to permanently delete '{project['title']}'?",
            "warning": "All tasks in this project will be deleted.",
            "details": details,
            "cancel_url": f"/projects/{project_id}",
        },
    )


@router.post("/projects/{project_id}/delete")
async def delete_project(
    request: Request,
    project_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Project not found")

    db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    db.commit()

    return RedirectResponse(url="/projects", status_code=status.HTTP_303_SEE_OTHER)


# --- Reopen project -----------------------------------------------------------

@router.post("/projects/{project_id}/reopen")
async def reopen_project(
    request: Request,
    project_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT id, status FROM projects WHERE id = ?", (project_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    db.execute(
        "UPDATE projects SET status = 'Active' WHERE id = ?",
        (project_id,),
    )
    db.commit()

    return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)


# --- Mark project complete ----------------------------------------------------

@router.post("/projects/{project_id}/complete")
async def complete_project(
    request: Request,
    project_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT id, status FROM projects WHERE id = ?", (project_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    incomplete = db.execute(
        "SELECT COUNT(*) as count FROM project_tasks WHERE project_id = ? AND status != 'Done'",
        (project_id,),
    ).fetchone()["count"]
    if incomplete > 0:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)

    db.execute(
        "UPDATE projects SET status = 'Complete' WHERE id = ?",
        (project_id,),
    )
    db.commit()

    return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)


# --- Add task to project ------------------------------------------------------

@router.post("/projects/{project_id}/tasks/add")
async def add_project_task(
    request: Request,
    project_id: int,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    depends_on_id: Optional[int] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    max_order = db.execute(
        "SELECT COALESCE(MAX(sort_order), 0) as max_order FROM project_tasks WHERE project_id = ?",
        (project_id,),
    ).fetchone()["max_order"]

    dep_val = depends_on_id if depends_on_id not in (None, 0) else None

    # Auto-block if the dependency task isn't done yet
    initial_status = "Pending"
    if dep_val:
        dep_task = db.execute(
            "SELECT status FROM project_tasks WHERE id = ? AND project_id = ?",
            (dep_val, project_id),
        ).fetchone()
        if dep_task and dep_task["status"] != "Done":
            initial_status = "Blocked"

    db.execute(
        "INSERT INTO project_tasks (project_id, title, description, sort_order, depends_on_id, status) VALUES (?, ?, ?, ?, ?, ?)",
        (project_id, title.strip(), description or None, max_order + 1, dep_val, initial_status),
    )
    db.commit()

    return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)


# --- Edit task ----------------------------------------------------------------

@router.get("/projects/{project_id}/tasks/{task_id}/edit")
async def edit_task_form(
    request: Request,
    project_id: int,
    task_id: int,
    cost_required: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    project = cur.fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    cur = db.execute("SELECT * FROM project_tasks WHERE id = ? AND project_id = ?", (task_id, project_id))
    task = cur.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get other tasks in this project for the dependency dropdown (exclude self)
    other_tasks = dicts(db.execute(
        "SELECT id, title FROM project_tasks WHERE project_id = ? AND id != ? ORDER BY sort_order",
        (project_id, task_id),
    ))

    return templates.TemplateResponse(
        "project_task_edit.html",
        {"request": request, "project": dict(project), "task": dict(task),
         "other_tasks": other_tasks,
         "error": "Actual costs are required before completing a task with estimated costs." if cost_required else None},
    )


@router.post("/projects/{project_id}/tasks/{task_id}/edit")
async def update_task(
    request: Request,
    project_id: int,
    task_id: int,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    depends_on_id: Optional[int] = Form(None),
    estimated_hours: Optional[str] = Form(None),
    estimated_labour_cost: Optional[str] = Form(None),
    estimated_material_cost: Optional[str] = Form(None),
    actual_hours: Optional[str] = Form(None),
    actual_labour_cost: Optional[str] = Form(None),
    actual_material_cost: Optional[str] = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    dep_val = depends_on_id if depends_on_id not in (None, 0) else None

    # Prevent circular: a task cannot depend on itself
    if dep_val == task_id:
        dep_val = None

    db.execute(
        """
        UPDATE project_tasks
        SET title = ?, description = ?, depends_on_id = ?,
            estimated_hours = ?, estimated_labour_cost = ?, estimated_material_cost = ?,
            actual_hours = ?, actual_labour_cost = ?, actual_material_cost = ?
        WHERE id = ? AND project_id = ?
        """,
        (
            title.strip(), description or None, dep_val,
            float(estimated_hours) if estimated_hours else None,
            float(estimated_labour_cost) if estimated_labour_cost else None,
            float(estimated_material_cost) if estimated_material_cost else None,
            float(actual_hours) if actual_hours else None,
            float(actual_labour_cost) if actual_labour_cost else None,
            float(actual_material_cost) if actual_material_cost else None,
            task_id, project_id,
        ),
    )

    # Re-evaluate blocked status after dependency change
    task = dict(db.execute(
        "SELECT * FROM project_tasks WHERE id = ? AND project_id = ?",
        (task_id, project_id),
    ).fetchone())

    if dep_val and task["status"] in ("Pending", "Blocked"):
        dep_task = db.execute(
            "SELECT status FROM project_tasks WHERE id = ?", (dep_val,)
        ).fetchone()
        if dep_task and dep_task["status"] != "Done":
            db.execute(
                "UPDATE project_tasks SET status = 'Blocked' WHERE id = ?", (task_id,)
            )
        else:
            db.execute(
                "UPDATE project_tasks SET status = 'Pending' WHERE id = ?", (task_id,)
            )
    elif not dep_val and task["status"] == "Blocked":
        db.execute(
            "UPDATE project_tasks SET status = 'Pending' WHERE id = ?", (task_id,)
        )

    db.commit()

    return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)


# --- Update task status -------------------------------------------------------

@router.post("/projects/{project_id}/tasks/{task_id}/status")
async def update_task_status(
    request: Request,
    project_id: int,
    task_id: int,
    new_status: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
):
    if new_status not in VALID_TASK_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    task = dict(db.execute(
        "SELECT * FROM project_tasks WHERE id = ? AND project_id = ?",
        (task_id, project_id),
    ).fetchone())

    # Block starting a task whose dependency isn't done
    if new_status == "In Progress" and task.get("depends_on_id"):
        dep_task = db.execute(
            "SELECT status FROM project_tasks WHERE id = ?",
            (task["depends_on_id"],),
        ).fetchone()
        if dep_task and dep_task["status"] != "Done":
            return RedirectResponse(
                url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER
            )

    # Close-gate: require actual costs before completing a task with estimates
    if new_status == "Done":
        has_estimates = (
            (task.get("estimated_labour_cost") and task["estimated_labour_cost"] > 0) or
            (task.get("estimated_material_cost") and task["estimated_material_cost"] > 0)
        )
        missing_actuals = (
            not task.get("actual_labour_cost") or
            not task.get("actual_material_cost")
        )
        if has_estimates and missing_actuals:
            return RedirectResponse(
                url=f"/projects/{project_id}/tasks/{task_id}/edit?cost_required=1",
                status_code=status.HTTP_303_SEE_OTHER,
            )

    db.execute(
        "UPDATE project_tasks SET status = ? WHERE id = ? AND project_id = ?",
        (new_status, task_id, project_id),
    )

    # Auto-unblock dependents when a task is completed
    if new_status == "Done":
        db.execute(
            "UPDATE project_tasks SET status = 'Pending' WHERE depends_on_id = ? AND project_id = ? AND status = 'Blocked'",
            (task_id, project_id),
        )

    # Auto-block dependents if a completed task is reopened
    if task["status"] == "Done" and new_status != "Done":
        db.execute(
            "UPDATE project_tasks SET status = 'Blocked' WHERE depends_on_id = ? AND project_id = ? AND status IN ('Pending', 'In Progress')",
            (task_id, project_id),
        )

    db.commit()

    return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)


# --- Delete task ---------------------------------------------------------------

@router.post("/projects/{project_id}/tasks/{task_id}/delete")
async def delete_project_task(
    request: Request,
    project_id: int,
    task_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    # Clear dependency references from other tasks before deleting
    db.execute(
        "UPDATE project_tasks SET depends_on_id = NULL WHERE depends_on_id = ? AND project_id = ?",
        (task_id, project_id),
    )
    # Unblock any tasks that were blocked by this one
    db.execute(
        "UPDATE project_tasks SET status = 'Pending' WHERE depends_on_id = ? AND project_id = ? AND status = 'Blocked'",
        (task_id, project_id),
    )

    db.execute(
        "DELETE FROM project_tasks WHERE id = ? AND project_id = ?",
        (task_id, project_id),
    )
    db.commit()

    tasks = db.execute(
        "SELECT id FROM project_tasks WHERE project_id = ? ORDER BY sort_order",
        (project_id,),
    ).fetchall()
    for i, task in enumerate(tasks, start=1):
        db.execute("UPDATE project_tasks SET sort_order = ? WHERE id = ?", (i, task["id"]))
    db.commit()

    return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)


# --- Move task up/down --------------------------------------------------------

@router.post("/projects/{project_id}/tasks/{task_id}/move")
async def move_project_task(
    request: Request,
    project_id: int,
    task_id: int,
    direction: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
):
    tasks = dicts(db.execute(
        "SELECT id, sort_order FROM project_tasks WHERE project_id = ? ORDER BY sort_order",
        (project_id,),
    ))

    current_idx = next((i for i, t in enumerate(tasks) if t["id"] == task_id), None)
    if current_idx is None:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)

    if direction == "up" and current_idx > 0:
        swap_idx = current_idx - 1
    elif direction == "down" and current_idx < len(tasks) - 1:
        swap_idx = current_idx + 1
    else:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)

    db.execute("UPDATE project_tasks SET sort_order = ? WHERE id = ?", (tasks[swap_idx]["sort_order"], tasks[current_idx]["id"]))
    db.execute("UPDATE project_tasks SET sort_order = ? WHERE id = ?", (tasks[current_idx]["sort_order"], tasks[swap_idx]["id"]))
    db.commit()

    return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)
