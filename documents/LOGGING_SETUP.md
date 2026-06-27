# Adding Logging to Home CMMS

This guide adds structured logging to the CMMS application for monitoring, debugging, and audit purposes.

## Step 1: Configure logging in cmms_ui.py

Add these lines near the top of `cmms_ui.py`, after the existing imports:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cmms")
```

## Step 2: Add logger to each route file

At the top of each route file, after the existing imports, add:

```python
import logging
logger = logging.getLogger("cmms")
```

Files to update:
- `routes/auth.py`
- `routes/dashboard.py`
- `routes/locations.py`
- `routes/assets.py`
- `routes/work_orders.py`
- `routes/users.py`

## Step 3: Add logging statements

### routes/auth.py

In the `login` function, after a successful login (after setting session values):

```python
    logger.info(f"User '{user['username']}' logged in from {request.client.host}")
```

After a failed login (before returning the error template):

```python
    logger.warning(f"Failed login attempt for '{username}' from {request.client.host}")
```

In the `logout` function, before clearing the session:

```python
    logger.info(f"User '{request.session.get('username')}' logged out")
```

In `setup_create_admin`, after creating the admin account:

```python
    logger.info(f"Admin account '{username.strip().lower()}' created during first-run setup")
```

### routes/locations.py

In `create_location`, after `db.commit()`:

```python
    logger.info(f"Location created: '{name.strip()}'")
```

In `update_location`, after `db.commit()`:

```python
    logger.info(f"Location #{location_id} updated: '{name.strip()}'")
```

In `delete_location` (the POST handler), after deactivating:

```python
    logger.info(f"Location #{location_id} deactivated")
```

When deletion is blocked:

```python
    logger.warning(f"Blocked deactivation of location #{location_id} — {open_wo_count} open work order(s)")
```

### routes/assets.py

In `create_asset`, after `db.commit()`:

```python
    logger.info(f"Asset created: '{name.strip()}' at location #{location_id}")
```

In `update_asset`, after `db.commit()`:

```python
    logger.info(f"Asset #{asset_id} updated: '{name.strip()}'")
```

In `delete_asset` (the POST handler), after deleting:

```python
    logger.info(f"Asset #{asset_id} deleted")
```

When deletion is blocked:

```python
    logger.warning(f"Blocked deletion of asset #{asset_id} — {open_wo_count} open work order(s)")
```

In `import_assets_csv`, after the import completes:

```python
    logger.info(f"CSV import from '{file.filename}': {imported} imported, {skipped} skipped")
```

### routes/work_orders.py

In `create_work_order`, after `db.commit()`:

```python
    logger.info(f"Work order created: '{title.strip()}' (status={initial_status}, priority={priority})")
```

In `update_work_order_status`, after `db.commit()`:

```python
    logger.info(f"Work order #{wo_id} status changed: {old_status} -> {new_status}")
```

In `update_work_order_core`, after `db.commit()`:

```python
    logger.info(f"Work order #{wo_id} updated: '{title.strip()}'")
```

In `delete_work_order` (the POST handler), after deleting:

```python
    logger.info(f"Work order #{wo_id} deleted")
```

When deletion is blocked (Done status):

```python
    logger.warning(f"Blocked deletion of completed work order #{wo_id}")
```

### routes/users.py

In `create_user`, after `db.commit()`:

```python
    logger.info(f"User account created: '{username.strip().lower()}'")
```

In `update_user`, after `db.commit()`:

```python
    logger.info(f"User #{user_id} updated")
```

When a password is reset:

```python
    logger.info(f"Password reset for user #{user_id}")
```

In `delete_user` (the POST handler), after deleting:

```python
    logger.info(f"User #{user_id} ('{row['username']}') deleted")
```

## Log levels

| Level | When to use |
|-------|------------|
| `logger.debug()` | Detailed diagnostic info (filter params, query details). Only visible when level is set to DEBUG. |
| `logger.info()` | Normal operations: logins, record creation, updates, deletes. |
| `logger.warning()` | Something unexpected but not broken: failed logins, blocked deletes, deactivated records accessed. |
| `logger.error()` | Something went wrong: missing records, database errors, unexpected state. |

## Changing the log level

In `cmms_ui.py`, change `level=logging.INFO` to see more or less detail:

```python
# Show everything including debug
logging.basicConfig(level=logging.DEBUG, ...)

# Show only warnings and errors (quiet production mode)
logging.basicConfig(level=logging.WARNING, ...)
```

## Example output

```
2026-06-24 10:15:32 INFO     cmms: User 'pete' logged in from 192.168.1.211
2026-06-24 10:15:45 INFO     cmms: Work order created: 'Fix leaking tap' (status=Open, priority=High)
2026-06-24 10:16:02 INFO     cmms: Work order #12 status changed: Open -> In Progress
2026-06-24 10:16:30 WARNING  cmms: Blocked deletion of asset #5 — 2 open work order(s)
2026-06-24 10:17:01 WARNING  cmms: Failed login attempt for 'admin' from 192.168.1.100
```

## Optional: Log to a file

To also write logs to a file, add a file handler after the `basicConfig` call in `cmms_ui.py`:

```python
file_handler = logging.FileHandler("cmms.log")
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
logging.getLogger("cmms").addHandler(file_handler)
```

Add `cmms.log` to `.gitignore` if you do this.
