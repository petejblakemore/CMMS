# CMMS Coding Standards

## Naming Conventions

All code follows Python PEP 8 naming:

| What | Convention | Examples |
|------|-----------|----------|
| Variables | `snake_case` | `asset_id`, `open_wo_count`, `sort_col` |
| Functions | `snake_case` | `list_assets`, `create_work_order`, `build_location_tree` |
| Classes | `PascalCase` | `AuthMiddleware` |
| Constants | `UPPER_SNAKE_CASE` | `VALID_STATUSES`, `DB_PATH`, `PRIORITY_ORDER_SQL` |
| Template variables | `snake_case` | `location_wo_counts`, `f_status` |
| URL parameters | `snake_case` | `asset_id`, `wo_status`, `due_date` |
| Database columns | `snake_case` | `location_id`, `next_due_date`, `created_at` |
| HTML template files | `snake_case` | `work_order_edit.html`, `asset_form.html` |
| Python files | `snake_case` | `work_orders.py`, `maintenance.py` |

## Prefix Conventions

| Prefix | Meaning | Used in |
|--------|---------|---------|
| `f_` | Filter value (current filter selection from query params) | Template context: `f_status`, `f_location`, `f_priority` |
| `v_` | Database view | SQL: `v_assets`, `v_open_work_orders` |
| `wo_` | Work order related | Variables: `wo_id`, `wo_history`, `wo_count` |
| `q_` | Queued work orders page | Template context: `q_priorities_list`, `q_locations_list` |
| `col_` | CSV column mapping | CSV import: `col_asset`, `col_location` |

## Comment Standards

### File headers
Every Python file starts with a comment block explaining its purpose:

```python
# routes/assets.py
#
# Asset management routes: list, create, edit, delete, CSV import.
# Assets belong to locations and can have work orders raised against them.
```

### Function comments
Add a brief comment above each route function explaining:
- What the page/action does
- Any non-obvious business rules

```python
# Show the asset list with optional filters and column sorting.
# Filters: location, category, status, manufacturer.
# Sort defaults to asset name ascending.
@router.get("/assets")
async def list_assets(...):
```

### Inline comments
Use sparingly — only for non-obvious logic:

```python
# Treat 0 as "no selection" from the dropdown (HTML sends 0 for the empty option)
asset_val = asset_id if asset_id not in (None, 0) else None

# Prevent a location from being its own parent (would create a cycle)
if parent_val == location_id:
    parent_val = None
```

### Don't comment obvious code

```python
# BAD — the code is self-explanatory
# Get the location name
location_name = row["name"]

# GOOD — explains WHY, not WHAT
# Fall back to the asset's location if the WO doesn't have one directly assigned
location_id = plan.get("location_id") or asset_location_id
```

## File Structure

Each route file follows this order:
1. File header comment
2. Imports
3. Logger setup
4. Router creation
5. List route (GET)
6. Create form route (GET)
7. Create action route (POST)
8. Edit form route (GET)
9. Edit action route (POST)
10. Delete confirm route (GET)
11. Delete action route (POST)
12. Any special routes (e.g., CSV import, complete PM)

## Template Variables

When passing data to templates, use descriptive names:

```python
# Filter values passed back to maintain state after form submission
"f_location": location or "",
"f_category": category or "",

# Data lists for dropdown population
"locations_list": locations_list,
"categories_list": categories_list,

# Primary data for the page
"assets": assets,
"plan": plan,
"wo": wo,
```
it seems that adding information in the header is old fashioned and now out of use