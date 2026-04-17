"""PythonAnywhere ASGI entry that serves static frontend and existing FastAPI routes."""

import os

from fastapi.staticfiles import StaticFiles

from backend.main import app

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# One-platform mode: serve HTML/CSS/JS directly from /static-like folder at root.
if os.path.isdir(STATIC_DIR):
    static_name = "pythonanywhere-static"
    already_mounted = any(getattr(route, "name", "") == static_name for route in app.router.routes)
    if not already_mounted:
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name=static_name)
