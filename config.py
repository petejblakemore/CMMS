# config.py
#
# Shared constants and paths for the CMMS application.

from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "cmms.db"
ASSET_IMPORT_LOG = BASE_DIR / "asset_import.log"

VALID_STATUSES = {"Open", "In Progress", "Queued", "Done", "Cancelled", "Icebox"}
VALID_PRIORITIES = {"Low", "Normal", "High", "Urgent"}
VALID_ASSET_STATUSES = {"Running", "Needs Maintenance", "Out of Service"}
