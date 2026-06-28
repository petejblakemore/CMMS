# db.py
#
# Database connection, templates, and shared utility functions.

import sqlite3
from typing import List

import bcrypt as _bcrypt
from fastapi.templating import Jinja2Templates

from config import BASE_DIR, DB_PATH


templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def get_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def dicts(rows: List[sqlite3.Row]):
    return [dict(r) for r in rows]


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return _bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def build_location_tree(locations):
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


def get_hierarchical_locations(db, active_only=True):
    """
    Return locations as a flat list sorted by hierarchy,
    with display_name showing the full path (e.g. 'Plas Gwernoer → Kitchen').
    Used for dropdown menus throughout the app.
    """
    where = "WHERE active = 1" if active_only else ""
    locations = dicts(db.execute(f"SELECT id, name, parent_id FROM locations {where} ORDER BY name"))

    by_id = {loc["id"]: loc for loc in locations}

    def get_path(loc):
        parts = [loc["name"]]
        current = loc
        while current.get("parent_id") and current["parent_id"] in by_id:
            current = by_id[current["parent_id"]]
            parts.insert(0, current["name"])
        return " → ".join(parts)

    result = []
    for loc in locations:
        loc["display_name"] = get_path(loc)
        result.append(loc)

    result.sort(key=lambda x: x["display_name"])
    return result


# SQL fragment for ordering by priority
PRIORITY_ORDER_SQL = """
    CASE priority
        WHEN 'Urgent' THEN 3 WHEN 'High' THEN 2
        WHEN 'Normal' THEN 1 WHEN 'Low' THEN 0
        ELSE -1
    END
"""


def build_where_clause(filters: dict) -> tuple:
    """
    Build a WHERE clause from a dict of {column: value}.
    Skips None/empty values. Returns (sql_string, params_list).
    """
    clauses = []
    params = []
    for col, val in filters.items():
        if val:
            clauses.append(f"{col} = ?")
            params.append(val)
    sql = (" AND " + " AND ".join(clauses)) if clauses else ""
    return sql, params
