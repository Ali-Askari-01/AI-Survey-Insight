"""
Storage Service — File Storage Abstraction (Section 9)
═══════════════════════════════════════════════════════
Feedback includes audio, transcripts, attachments.

Storage Strategy:
  Local  → MVP (current)
  Cloud  → Scale (S3, R2, GCP Storage)

Structure:
  /org_id/
     /feedback/
         audio.wav
         transcript.txt
     /exports/
         report.pdf

This module implements:
  - Unified storage interface (local ↔ cloud transparent)
  - Organization-scoped file paths (/org_id/feedback/...)
  - Audio, transcript, and attachment management
  - File metadata tracking and retrieval
  - Storage quota monitoring per organization
  - Automatic cleanup for expired/orphaned files
  - Migration helper: local → cloud object storage
"""

import os
import shutil
import time
import uuid
import hashlib
import threading
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path


# ═══════════════════════════════════════════════════
# STORAGE BACKENDS
# ═══════════════════════════════════════════════════
class StorageBackend(Enum):
    LOCAL = "local"           # Phase 1 — MVP filesystem
    S3 = "s3"                 # Phase 2 — AWS S3
    R2 = "r2"                 # Phase 2 — Cloudflare R2
    GCS = "gcs"               # Phase 2 — Google Cloud Storage


class FileCategory(Enum):
    AUDIO = "audio"
    TRANSCRIPT = "transcript"
    ATTACHMENT = "attachment"
    EXPORT = "export"
    REPORT = "report"
    BACKUP = "backup"


# ═══════════════════════════════════════════════════
# FILE METADATA
# ═══════════════════════════════════════════════════
@dataclass
class FileMetadata:
    """Tracks metadata for every stored file."""
    file_id: str
    original_name: str
    stored_path: str
    category: FileCategory
    mime_type: str
    size_bytes: int
    checksum_md5: str
    org_id: str = "default"
    survey_id: Optional[int] = None
    session_id: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "file_id": self.file_id,
            "original_name": self.original_name,
            "stored_path": self.stored_path,
            "category": self.category.value,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "size_human": self._human_size(),
            "checksum_md5": self.checksum_md5,
            "org_id": self.org_id,
            "survey_id": self.survey_id,
            "session_id": self.session_id,
            "uploaded_by": self.uploaded_by,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "expires_at": datetime.fromtimestamp(self.expires_at).isoformat() if self.expires_at else None,
            "tags": self.tags,
        }

    def _human_size(self) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.size_bytes < 1024:
                return f"{self.size_bytes:.1f} {unit}"
            self.size_bytes /= 1024
        return f"{self.size_bytes:.1f} TB"


# ═══════════════════════════════════════════════════
# STORAGE CONFIGURATION
# ═══════════════════════════════════════════════════
@dataclass
class StorageConfig:
    """Storage service configuration."""
    backend: StorageBackend = StorageBackend.LOCAL
    base_path: str = ""                          # Local filesystem root
    max_file_size_mb: int = 100                  # Max single file size
    max_org_quota_mb: int = 5000                 # Max storage per org (5GB)
    allowed_audio_types: Tuple[str, ...] = (".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac")
    allowed_attachment_types: Tuple[str, ...] = (".pdf", ".csv", ".xlsx", ".json", ".txt", ".png", ".jpg")
    auto_cleanup_days: int = 90                  # Remove expired files after N days
    enable_checksums: bool = True                # MD5 integrity verification

    # Cloud config (Phase 2)
    cloud_bucket: str = ""
    cloud_region: str = "us-east-1"
    cloud_prefix: str = "ai-survey-engine/"

    def __post_init__(self):
        if not self.base_path:
            self.base_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "storage"
            )


# ═══════════════════════════════════════════════════
# MIME TYPE DETECTION
# ═══════════════════════════════════════════════════
MIME_MAP = {
    ".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
    ".ogg": "audio/ogg", ".webm": "audio/webm", ".flac": "audio/flac",
    ".pdf": "application/pdf", ".csv": "text/csv", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".json": "application/json", ".txt": "text/plain",
    ".png": "image/png", ".jpg": "image/jpeg",
}


def detect_mime(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return MIME_MAP.get(ext, "application/octet-stream")


def detect_category(filename: str) -> FileCategory:
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"):
        return FileCategory.AUDIO
    if ext in (".txt",) and "transcript" in filename.lower():
        return FileCategory.TRANSCRIPT
    if ext in (".pdf", ".xlsx"):
        return FileCategory.REPORT
    return FileCategory.ATTACHMENT


# ═══════════════════════════════════════════════════
# STORAGE SERVICE
# ═══════════════════════════════════════════════════
class StorageService:
    """
    Unified file storage abstraction.

    Phase 1: Local filesystem (current)
    Phase 2: Cloud object storage (S3/R2/GCS) via swappable backend

    Organization-scoped:
      /{org_id}/feedback/{session_id}/audio.wav
      /{org_id}/feedback/{session_id}/transcript.txt
      /{org_id}/exports/report_20260302.pdf

    Features:
      - Store, retrieve, delete files
      - Metadata tracking with search
      - Quota management per organization
      - Integrity verification via checksums
      - Automatic cleanup of expired files
      - Migration path to cloud storage
    """

    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self._metadata: Dict[str, FileMetadata] = {}  # file_id → metadata
        self._lock = threading.Lock()

        # Metrics
        self._metrics = {
            "total_stored": 0,
            "total_retrieved": 0,
            "total_deleted": 0,
            "total_bytes_stored": 0,
            "total_errors": 0,
        }

        # Ensure base directory exists
        os.makedirs(self.config.base_path, exist_ok=True)

    # ─── Store File ───
    def store_file(
        self,
        content: bytes,
        filename: str,
        org_id: str = "default",
        survey_id: Optional[int] = None,
        session_id: Optional[str] = None,
        category: Optional[FileCategory] = None,
        uploaded_by: Optional[str] = None,
        ttl_days: Optional[int] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> FileMetadata:
        """
        Store a file and return its metadata.

        Args:
            content: Raw file bytes
            filename: Original filename
            org_id: Organization scope
            survey_id: Associated survey
            session_id: Associated interview session
            category: File category (auto-detected if None)
            uploaded_by: User who uploaded
            ttl_days: Auto-expire after N days
            tags: Custom metadata tags

        Returns:
            FileMetadata with storage path and file_id
        """
        # Validate file size
        size_mb = len(content) / (1024 * 1024)
        if size_mb > self.config.max_file_size_mb:
            raise ValueError(f"File too large: {size_mb:.1f}MB > {self.config.max_file_size_mb}MB limit")

        # Validate extension
        ext = os.path.splitext(filename)[1].lower()
        all_allowed = self.config.allowed_audio_types + self.config.allowed_attachment_types
        if ext and ext not in all_allowed:
            raise ValueError(f"File type not allowed: {ext}")

        # Check org quota
        org_usage = self._get_org_usage_bytes(org_id)
        if (org_usage + len(content)) > (self.config.max_org_quota_mb * 1024 * 1024):
            raise ValueError(f"Organization storage quota exceeded: {self.config.max_org_quota_mb}MB")

        # Generate file ID and storage path
        file_id = f"file-{uuid.uuid4().hex[:12]}"
        cat = category or detect_category(filename)
        relative_dir = self._build_path(org_id, cat, survey_id, session_id)
        stored_name = f"{file_id}{ext}"
        full_dir = os.path.join(self.config.base_path, relative_dir)
        full_path = os.path.join(full_dir, stored_name)

        # Compute checksum
        checksum = hashlib.md5(content).hexdigest() if self.config.enable_checksums else ""

        # Write to disk
        os.makedirs(full_dir, exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)

        # Create metadata
        metadata = FileMetadata(
            file_id=file_id,
            original_name=filename,
            stored_path=os.path.join(relative_dir, stored_name),
            category=cat,
            mime_type=detect_mime(filename),
            size_bytes=len(content),
            checksum_md5=checksum,
            org_id=org_id,
            survey_id=survey_id,
            session_id=session_id,
            uploaded_by=uploaded_by,
            expires_at=time.time() + (ttl_days * 86400) if ttl_days else None,
            tags=tags or {},
        )

        with self._lock:
            self._metadata[file_id] = metadata
            self._metrics["total_stored"] += 1
            self._metrics["total_bytes_stored"] += len(content)

        return metadata

    # ─── Retrieve File ───
    def retrieve_file(self, file_id: str) -> Tuple[bytes, FileMetadata]:
        """
        Retrieve a file by ID. Returns (content_bytes, metadata).
        Verifies checksum integrity.
        """
        meta = self._metadata.get(file_id)
        if not meta:
            raise FileNotFoundError(f"File not found: {file_id}")

        # Check expiry
        if meta.expires_at and time.time() > meta.expires_at:
            self.delete_file(file_id)
            raise FileNotFoundError(f"File expired: {file_id}")

        full_path = os.path.join(self.config.base_path, meta.stored_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File missing from disk: {file_id}")

        with open(full_path, "rb") as f:
            content = f.read()

        # Verify integrity
        if self.config.enable_checksums and meta.checksum_md5:
            actual = hashlib.md5(content).hexdigest()
            if actual != meta.checksum_md5:
                self._metrics["total_errors"] += 1
                raise IOError(f"Checksum mismatch for {file_id}: expected {meta.checksum_md5}, got {actual}")

        self._metrics["total_retrieved"] += 1
        return content, meta

    # ─── Delete File ───
    def delete_file(self, file_id: str) -> bool:
        """Delete a file and its metadata."""
        meta = self._metadata.get(file_id)
        if not meta:
            return False

        full_path = os.path.join(self.config.base_path, meta.stored_path)
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
        except OSError:
            self._metrics["total_errors"] += 1

        with self._lock:
            del self._metadata[file_id]
            self._metrics["total_deleted"] += 1

        return True

    # ─── List Files ───
    def list_files(
        self,
        org_id: Optional[str] = None,
        survey_id: Optional[int] = None,
        session_id: Optional[str] = None,
        category: Optional[FileCategory] = None,
        limit: int = 100,
    ) -> List[dict]:
        """List files matching the given filters."""
        results = []
        for meta in self._metadata.values():
            if org_id and meta.org_id != org_id:
                continue
            if survey_id and meta.survey_id != survey_id:
                continue
            if session_id and meta.session_id != session_id:
                continue
            if category and meta.category != category:
                continue
            results.append(meta.to_dict())
            if len(results) >= limit:
                break
        return results

    # ─── Cleanup Expired Files ───
    def cleanup_expired(self) -> int:
        """Remove all expired files. Returns count of files removed."""
        now = time.time()
        expired_ids = [
            fid for fid, meta in self._metadata.items()
            if meta.expires_at and now > meta.expires_at
        ]
        for fid in expired_ids:
            self.delete_file(fid)
        return len(expired_ids)

    # ─── Org Usage ───
    def _get_org_usage_bytes(self, org_id: str) -> int:
        """Calculate total storage used by an organization."""
        return sum(
            meta.size_bytes for meta in self._metadata.values()
            if meta.org_id == org_id
        )

    def get_org_quota(self, org_id: str) -> dict:
        """Get storage quota status for an organization."""
        used = self._get_org_usage_bytes(org_id)
        limit = self.config.max_org_quota_mb * 1024 * 1024
        return {
            "org_id": org_id,
            "used_bytes": used,
            "used_human": self._human_size(used),
            "limit_bytes": limit,
            "limit_human": f"{self.config.max_org_quota_mb} MB",
            "usage_percent": round(used / max(limit, 1) * 100, 1),
            "remaining_bytes": max(0, limit - used),
            "file_count": sum(1 for m in self._metadata.values() if m.org_id == org_id),
        }

    # ─── Path Builder ───
    def _build_path(
        self,
        org_id: str,
        category: FileCategory,
        survey_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Build organization-scoped directory path.
        Pattern: /{org_id}/{category}/{survey_id}/{session_id}/
        """
        parts = [org_id]
        if category in (FileCategory.AUDIO, FileCategory.TRANSCRIPT, FileCategory.ATTACHMENT):
            parts.append("feedback")
        elif category in (FileCategory.EXPORT, FileCategory.REPORT):
            parts.append("exports")
        else:
            parts.append(category.value)

        if survey_id:
            parts.append(f"survey_{survey_id}")
        if session_id:
            parts.append(session_id)

        return os.path.join(*parts)

    # ─── Cloud Migration Helper ───
    def prepare_cloud_migration(self) -> dict:
        """
        Generate a migration manifest for moving from local to cloud storage.
        Returns a list of files and their target cloud paths.

        Phase 2 migration path:
          Local filesystem → AWS S3 / Cloudflare R2 / GCP Storage
        """
        manifest = {
            "source_backend": self.config.backend.value,
            "target_backend": "cloud",
            "target_bucket": self.config.cloud_bucket or "ai-survey-engine",
            "target_prefix": self.config.cloud_prefix,
            "total_files": len(self._metadata),
            "total_bytes": sum(m.size_bytes for m in self._metadata.values()),
            "files": [],
        }
        for meta in self._metadata.values():
            cloud_key = f"{self.config.cloud_prefix}{meta.stored_path}".replace("\\", "/")
            manifest["files"].append({
                "file_id": meta.file_id,
                "local_path": meta.stored_path,
                "cloud_key": cloud_key,
                "size_bytes": meta.size_bytes,
                "checksum_md5": meta.checksum_md5,
            })
        return manifest

    # ─── Utilities ───
    @staticmethod
    def _human_size(size_bytes: int) -> str:
        b = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} TB"

    # ─── Stats ───
    def stats(self) -> dict:
        """Full storage service metrics."""
        by_category = {}
        by_org = {}
        for meta in self._metadata.values():
            cat = meta.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            by_org[meta.org_id] = by_org.get(meta.org_id, 0) + 1

        return {
            "backend": self.config.backend.value,
            "base_path": self.config.base_path,
            "total_files": len(self._metadata),
            "total_bytes": sum(m.size_bytes for m in self._metadata.values()),
            "total_human": self._human_size(sum(m.size_bytes for m in self._metadata.values())),
            "by_category": by_category,
            "by_org": by_org,
            "config": {
                "max_file_size_mb": self.config.max_file_size_mb,
                "max_org_quota_mb": self.config.max_org_quota_mb,
                "auto_cleanup_days": self.config.auto_cleanup_days,
                "checksums_enabled": self.config.enable_checksums,
            },
            "metrics": self._metrics.copy(),
        }


# ═══════════════════════════════════════════════════
# GLOBAL STORAGE SERVICE SINGLETON
# ═══════════════════════════════════════════════════
storage_service = StorageService()
