# cmms_ui.py
#
# Home CMMS – Plas Gwernoer
#
# Main application entry point. Sets up FastAPI, middleware,
# and includes all route modules.
#
# Run with: uvicorn cmms_ui:app --reload

import os
import sqlite3
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cmms")

from fastapi import FastAPI, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from config import BASE_DIR, DB_PATH

# Create the FastAPI application instance
app = FastAPI(title="Home CMMS – Plas Gwernoer")

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# --- Auth middleware ---------------------------------------------------------

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        public_paths = ["/login", "/setup"]
        if request.url.path in public_paths or request.url.path.startswith("/static"):
            return await call_next(request)

        user_id = request.session.get("user_id")
        if not user_id:
            conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                count = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()["count"]
            finally:
                conn.close()

            if count == 0:
                return RedirectResponse(url="/setup", status_code=status.HTTP_303_SEE_OTHER)
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

        return await call_next(request)


# Middleware order: AuthMiddleware (innermost) → SessionMiddleware (outermost)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("CMMS_SECRET_KEY", "the-rain-in-spain-falls-mainly"),
    max_age=60 * 60 * 24 * 7,
)


# --- Include route modules --------------------------------------------------

from routes.auth import router as auth_router
from routes.dashboard import router as dashboard_router
from routes.locations import router as locations_router
from routes.assets import router as assets_router
from routes.work_orders import router as work_orders_router
from routes.users import router as users_router
from routes.maintenance import router as maintenance_router




app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(locations_router)
app.include_router(assets_router)
app.include_router(work_orders_router)
app.include_router(users_router)
app.include_router(maintenance_router)
