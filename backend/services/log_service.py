"""
File Logging Service
═══════════════════════════════════════════════════════
Configures Python logging to persist server logs to rotating files.
- Application log: logs/app.log (general application events)
- Access log: logs/access.log (HTTP requests)
- Error log: logs/error.log (errors and exceptions only)
- Rotates at 10 MB, keeps 5 backups per file
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Log directory
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")

# Configuration
MAX_LOG_SIZE = int(os.environ.get("LOG_MAX_SIZE_MB", "10")) * 1024 * 1024  # Default 10 MB
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", "5"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Format strings
DETAILED_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
ACCESS_FORMAT = "%(asctime)s | %(message)s"
ERROR_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"


def _ensure_log_dir():
    """Create logs directory if it doesn't exist."""
    os.makedirs(LOG_DIR, exist_ok=True)


def setup_file_logging():
    """
    Configure rotating file logging for the application.
    Call this once during app startup.
    """
    _ensure_log_dir()

    # ── Root Logger ──
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Remove existing handlers to avoid duplicates on reload
    for handler in root_logger.handlers[:]:
        if isinstance(handler, RotatingFileHandler):
            root_logger.removeHandler(handler)

    # ── Application Log (all events) ──
    app_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "app.log"),
        maxBytes=MAX_LOG_SIZE,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    app_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    app_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
    root_logger.addHandler(app_handler)

    # ── Error Log (ERROR and above only) ──
    error_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "error.log"),
        maxBytes=MAX_LOG_SIZE,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(ERROR_FORMAT))
    root_logger.addHandler(error_handler)

    # ── Access Log (HTTP requests — used by middleware) ──
    access_logger = logging.getLogger("access")
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False  # Don't double-log to root

    access_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "access.log"),
        maxBytes=MAX_LOG_SIZE,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    access_handler.setFormatter(logging.Formatter(ACCESS_FORMAT))
    access_logger.addHandler(access_handler)

    # ── Security Log (auth events, violations) ──
    security_logger = logging.getLogger("security")
    security_logger.setLevel(logging.INFO)
    security_logger.propagate = False  # Separate from general logs

    security_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "security.log"),
        maxBytes=MAX_LOG_SIZE,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    security_handler.setFormatter(logging.Formatter(ERROR_FORMAT))
    security_logger.addHandler(security_handler)

    # ── Console output stays attached (uvicorn default) ──
    # Only add console handler if there isn't one already
    has_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        for h in root_logger.handlers
    )
    if not has_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        console_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
        root_logger.addHandler(console_handler)

    # Log startup
    logger = logging.getLogger("server")
    logger.info("=" * 60)
    logger.info(f"File logging initialized — Level: {LOG_LEVEL}")
    logger.info(f"Log directory: {LOG_DIR}")
    logger.info(f"Max file size: {MAX_LOG_SIZE // (1024*1024)} MB, backups: {LOG_BACKUP_COUNT}")
    logger.info("=" * 60)

    return root_logger


def get_log_files() -> list:
    """List all log files with their sizes."""
    _ensure_log_dir()
    files = []
    for f in sorted(os.listdir(LOG_DIR)):
        if not f.endswith(".log") and ".log." not in f:
            continue
        path = os.path.join(LOG_DIR, f)
        stat = os.stat(path)
        files.append({
            "filename": f,
            "size_mb": round(stat.st_size / (1024 * 1024), 3),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return files


def read_recent_logs(filename: str = "app.log", lines: int = 100) -> list:
    """Read the most recent N lines from a log file."""
    filepath = os.path.join(LOG_DIR, filename)
    if not os.path.exists(filepath):
        return []

    # Read the last N lines efficiently
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return [line.rstrip() for line in all_lines[-lines:]]
