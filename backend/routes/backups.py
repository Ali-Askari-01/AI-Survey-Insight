"""
Backup API Routes
═══════════════════════════════════════════════════════
Endpoints for managing database backups.
"""

from fastapi import APIRouter, Depends, HTTPException
from ..auth import get_current_user
from ..services.backup_service import (
    create_backup,
    list_backups,
    restore_backup,
    get_backup_status,
    verify_backup,
    delete_backup,
    get_db_integrity,
    BACKUP_DIR,
)
import os

router = APIRouter(prefix="/api/backups", tags=["backups"])


@router.get("/status")
def backup_status(user=Depends(get_current_user)):
    """Get current backup status and schedule info."""
    return get_backup_status()


@router.get("/list")
def backup_list(user=Depends(get_current_user)):
    """List all available backups."""
    backups = list_backups()
    total_mb = round(sum(b["size_mb"] for b in backups), 2)
    return {"backups": backups, "count": len(backups), "total_size_mb": total_mb}


@router.post("/create")
def backup_create(user=Depends(get_current_user)):
    """Manually trigger a database backup."""
    result = create_backup(tag="manual")
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/verify/{filename}")
def backup_verify(filename: str, user=Depends(get_current_user)):
    """Run integrity check on a specific backup file."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    backup_path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail=f"Backup not found: {filename}")
    ok = verify_backup(backup_path)
    return {"filename": filename, "integrity_ok": ok, "status": "passed" if ok else "failed"}


@router.delete("/{filename}")
def backup_delete(filename: str, user=Depends(get_current_user)):
    """Delete a specific backup (admin only)."""
    if user.get("role") not in ("founder", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can delete backups")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    result = delete_backup(filename)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/db-integrity")
def db_integrity_check(user=Depends(get_current_user)):
    """Run integrity check on the live database."""
    result = get_db_integrity()
    return result


@router.post("/restore/{filename}")
def backup_restore(filename: str, user=Depends(get_current_user)):
    """Restore a backup (admin only). Creates a safety backup first."""
    if user.get("role") not in ("founder", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can restore backups")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    result = restore_backup(filename)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
