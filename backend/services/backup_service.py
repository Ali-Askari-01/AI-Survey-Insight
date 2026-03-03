"""
Database Backup Service
═══════════════════════════════════════════════════════
Automated daily backup of the SQLite database with rotation.
- Copies the SQLite file safely using the backup API
- Rotates old backups (keeps last N)
- Provides manual trigger via API
- Runs on a background schedule
"""

import os
import shutil
import sqlite3
import threading
import time
import logging
from datetime import datetime, timedelta

from ..database import DB_PATH

logger = logging.getLogger("backup")

# Backup directory
BACKUP_DIR = os.path.join(os.path.dirname(DB_PATH), "backups")

# Configuration
MAX_BACKUPS = int(os.environ.get("BACKUP_MAX_COUNT", "7"))
BACKUP_INTERVAL_HOURS = int(os.environ.get("BACKUP_INTERVAL_HOURS", "24"))

# Track last backup time
_last_backup_time = None
_backup_thread = None
_stop_event = threading.Event()


def _ensure_backup_dir():
    """Create backup directory if it doesn't exist."""
    os.makedirs(BACKUP_DIR, exist_ok=True)


def create_backup(tag: str = "") -> dict:
    """
    Create a safe backup of the SQLite database using sqlite3.backup().
    This is safe even while the database is in use (WAL mode).
    
    Returns dict with backup info.
    """
    global _last_backup_time

    if not os.path.exists(DB_PATH):
        return {"success": False, "error": "Database file not found"}

    _ensure_backup_dir()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{tag}" if tag else ""
    backup_filename = f"survey_engine_{timestamp}{suffix}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    try:
        # Use SQLite's online backup API — safe during concurrent access
        start_time = time.time()
        source = sqlite3.connect(DB_PATH)
        dest = sqlite3.connect(backup_path)
        source.backup(dest)
        dest.close()
        source.close()
        duration = round(time.time() - start_time, 2)

        # Verify backup integrity
        integrity_ok = verify_backup(backup_path)

        # Get file size
        size_bytes = os.path.getsize(backup_path)
        size_mb = round(size_bytes / (1024 * 1024), 2)

        _last_backup_time = datetime.now()

        # Rotate old backups
        _rotate_backups()

        logger.info(f"Backup created: {backup_filename} ({size_mb} MB, {duration}s, integrity={'OK' if integrity_ok else 'FAIL'})")

        return {
            "success": True,
            "filename": backup_filename,
            "path": backup_path,
            "size_mb": size_mb,
            "duration_seconds": duration,
            "integrity_ok": integrity_ok,
            "timestamp": _last_backup_time.isoformat(),
            "backups_kept": MAX_BACKUPS,
        }
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        # Clean up failed backup file
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except OSError:
                pass
        return {"success": False, "error": str(e)}


def _rotate_backups():
    """Remove old backups beyond MAX_BACKUPS limit (oldest first)."""
    _ensure_backup_dir()
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")],
        key=lambda f: os.path.getmtime(os.path.join(BACKUP_DIR, f)),
    )

    while len(backups) > MAX_BACKUPS:
        oldest = backups.pop(0)
        try:
            os.remove(os.path.join(BACKUP_DIR, oldest))
        except OSError:
            pass


def list_backups() -> list:
    """List all existing backups with metadata."""
    _ensure_backup_dir()
    backups = []
    for f in sorted(os.listdir(BACKUP_DIR)):
        if not f.endswith(".db"):
            continue
        path = os.path.join(BACKUP_DIR, f)
        stat = os.stat(path)
        # Determine tag from filename
        tag = ""
        parts = f.replace("survey_engine_", "").replace(".db", "").split("_")
        if len(parts) > 2:
            tag = "_".join(parts[2:])  # Everything after the timestamp
        backups.append({
            "filename": f,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "tag": tag,
        })
    return backups


def restore_backup(filename: str) -> dict:
    """
    Restore a backup by replacing the current database.
    WARNING: This is destructive — the current database will be overwritten.
    A pre-restore backup is created automatically.
    """
    backup_path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(backup_path):
        return {"success": False, "error": f"Backup file not found: {filename}"}

    try:
        # Create a safety backup before restoring
        create_backup(tag="pre_restore")

        # Use SQLite backup API to restore
        source = sqlite3.connect(backup_path)
        dest = sqlite3.connect(DB_PATH)
        source.backup(dest)
        dest.close()
        source.close()

        return {
            "success": True,
            "restored_from": filename,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_backup_status() -> dict:
    """Get current backup status and schedule info."""
    _ensure_backup_dir()
    backups = list_backups()
    db_size_mb = round(os.path.getsize(DB_PATH) / (1024 * 1024), 2) if os.path.exists(DB_PATH) else 0
    total_backup_mb = round(sum(b["size_mb"] for b in backups), 2)

    next_backup = None
    if _last_backup_time:
        next_backup = (_last_backup_time + timedelta(hours=BACKUP_INTERVAL_HOURS)).isoformat()

    return {
        "db_size_mb": db_size_mb,
        "backup_count": len(backups),
        "total_backup_size_mb": total_backup_mb,
        "max_backups": MAX_BACKUPS,
        "interval_hours": BACKUP_INTERVAL_HOURS,
        "last_backup": _last_backup_time.isoformat() if _last_backup_time else None,
        "next_scheduled": next_backup,
        "backup_dir": BACKUP_DIR,
        "scheduler_running": _backup_thread is not None and _backup_thread.is_alive(),
        "recent_backups": backups[-5:],  # Last 5
    }


def _backup_loop():
    """Background thread that creates periodic backups."""
    global _last_backup_time
    while not _stop_event.is_set():
        try:
            result = create_backup(tag="auto")
            if result["success"]:
                logger.info(f"Auto backup: {result['filename']} ({result['size_mb']} MB, {result.get('duration_seconds', '?')}s)")
            else:
                logger.error(f"Auto backup failed: {result.get('error')}")
        except Exception as e:
            logger.error(f"Auto backup error: {e}")

        # Sleep for the interval, checking stop_event every 60s
        for _ in range(BACKUP_INTERVAL_HOURS * 60):
            if _stop_event.is_set():
                return
            _stop_event.wait(60)


def start_scheduler():
    """Start the background backup scheduler."""
    global _backup_thread
    if _backup_thread and _backup_thread.is_alive():
        return  # Already running

    _stop_event.clear()
    _backup_thread = threading.Thread(target=_backup_loop, daemon=True, name="backup-scheduler")
    _backup_thread.start()
    logger.info(f"Scheduler started (every {BACKUP_INTERVAL_HOURS}h, keeping {MAX_BACKUPS} backups)")
    print(f"[Backup] Scheduler started (every {BACKUP_INTERVAL_HOURS}h, keeping {MAX_BACKUPS} backups)")


def stop_scheduler():
    """Stop the background backup scheduler."""
    global _backup_thread
    _stop_event.set()
    if _backup_thread:
        _backup_thread.join(timeout=5)
        _backup_thread = None
    logger.info("Scheduler stopped")
    print("[Backup] Scheduler stopped")


def verify_backup(backup_path: str) -> bool:
    """Run PRAGMA integrity_check on a backup file to ensure it's not corrupt."""
    try:
        conn = sqlite3.connect(backup_path)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        return result[0] == "ok"
    except Exception:
        return False


def delete_backup(filename: str) -> dict:
    """Delete a specific backup file."""
    backup_path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(backup_path):
        return {"success": False, "error": f"Backup not found: {filename}"}
    try:
        os.remove(backup_path)
        logger.info(f"Backup deleted: {filename}")
        return {"success": True, "deleted": filename}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_db_integrity() -> dict:
    """Run integrity check on the live database."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        wal_pages = conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        journal = conn.execute("PRAGMA journal_mode").fetchone()
        conn.close()
        return {
            "integrity": result[0],
            "ok": result[0] == "ok",
            "journal_mode": journal[0] if journal else "unknown",
            "wal_pages": wal_pages[1] if wal_pages else None,
        }
    except Exception as e:
        return {"integrity": "error", "ok": False, "error": str(e)}
