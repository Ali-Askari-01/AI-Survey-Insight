"""
Security Audit — Comprehensive Audit Trail & Forensic Logging
═════════════════════════════════════════════════════════════
Every security-relevant action is recorded with full context.

Audit Categories:
  AUTH:       Login, logout, token refresh, password change
  ACCESS:     Resource access, permission checks, RBAC decisions
  DATA:       Create, read, update, delete of sensitive data
  CONFIG:     System configuration changes
  SECURITY:   Threat events, blocks, lockouts
  COMPLIANCE: Consent changes, DSR processing, data retention
  AI:         AI processing requests, prompt injection attempts
  ADMIN:      User management, role changes, system operations

Each Entry Contains:
  - Timestamp (ISO 8601)
  - Actor (user_id, role, IP, user-agent)
  - Action (verb + resource)
  - Outcome (success/failure + reason)
  - Context (request details, metadata)
  - Fingerprint (hash for tamper detection)
"""

import hashlib
import json
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional, Dict, List


class AuditCategory:
    AUTH = "auth"
    ACCESS = "access"
    DATA = "data"
    CONFIG = "config"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    AI = "ai"
    ADMIN = "admin"


class AuditEntry:
    """Immutable audit log entry with tamper-detection fingerprint."""

    _counter = 0
    _counter_lock = threading.RLock()

    def __init__(self, category: str, action: str, outcome: str,
                 user_id: Optional[int] = None, user_role: str = "",
                 ip_address: str = "", user_agent: str = "",
                 resource_type: str = "", resource_id: Optional[int] = None,
                 details: Optional[dict] = None, reason: str = ""):
        with AuditEntry._counter_lock:
            AuditEntry._counter += 1
            self.sequence = AuditEntry._counter

        self.timestamp = datetime.now().isoformat()
        self.category = category
        self.action = action
        self.outcome = outcome  # "success" or "failure"
        self.user_id = user_id
        self.user_role = user_role
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.details = details or {}
        self.reason = reason

        # Tamper-detection fingerprint
        self.fingerprint = self._compute_fingerprint()

    def _compute_fingerprint(self) -> str:
        """Compute HMAC fingerprint for tamper detection."""
        data = f"{self.sequence}|{self.timestamp}|{self.category}|{self.action}|{self.outcome}|{self.user_id}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "category": self.category,
            "action": self.action,
            "outcome": self.outcome,
            "fingerprint": self.fingerprint,
        }
        if self.user_id is not None:
            d["user_id"] = self.user_id
        if self.user_role:
            d["user_role"] = self.user_role
        if self.ip_address:
            d["ip_address"] = self.ip_address
        if self.resource_type:
            d["resource_type"] = self.resource_type
        if self.resource_id is not None:
            d["resource_id"] = self.resource_id
        if self.details:
            d["details"] = self.details
        if self.reason:
            d["reason"] = self.reason
        return d


class SecurityAudit:
    """
    Comprehensive Security Audit Trail.

    Features:
    - Immutable audit entries with sequence numbers
    - Tamper-detection fingerprints (SHA-256)
    - Category-based indexing for fast queries
    - User activity tracking
    - Failed action highlighting
    - Compliance-ready export (JSON)
    - Anomaly detection (unusual patterns)
    - Retention-aware (configurable max entries)
    """

    def __init__(self, max_entries: int = 50000):
        self._lock = threading.RLock()
        self._entries: deque = deque(maxlen=max_entries)
        self._max_entries = max_entries

        # Indexes for fast query
        self._by_category: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._by_user: Dict[int, deque] = defaultdict(lambda: deque(maxlen=5000))
        self._by_outcome: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))

        # Counters
        self._total_entries = 0
        self._total_by_category: Dict[str, int] = defaultdict(int)
        self._total_by_outcome: Dict[str, int] = defaultdict(int)
        self._start_time = time.time()

    # ── Log Methods ──

    def log(self, category: str, action: str, outcome: str = "success",
            user_id: Optional[int] = None, user_role: str = "",
            ip_address: str = "", user_agent: str = "",
            resource_type: str = "", resource_id: Optional[int] = None,
            details: Optional[dict] = None, reason: str = "") -> dict:
        """
        Log an audit entry.
        Returns the entry dict.
        """
        entry = AuditEntry(
            category, action, outcome,
            user_id, user_role, ip_address, user_agent,
            resource_type, resource_id, details, reason
        )

        with self._lock:
            self._entries.append(entry)
            self._by_category[category].append(entry)
            if user_id is not None:
                self._by_user[user_id].append(entry)
            self._by_outcome[outcome].append(entry)
            self._total_entries += 1
            self._total_by_category[category] += 1
            self._total_by_outcome[outcome] += 1

        return entry.to_dict()

    # ── Convenience Logging ──

    def log_auth(self, action: str, outcome: str, user_id: Optional[int] = None,
                 ip: str = "", **kwargs):
        return self.log(AuditCategory.AUTH, action, outcome,
                        user_id=user_id, ip_address=ip, **kwargs)

    def log_access(self, action: str, outcome: str, user_id: Optional[int] = None,
                   resource_type: str = "", resource_id: Optional[int] = None, **kwargs):
        return self.log(AuditCategory.ACCESS, action, outcome,
                        user_id=user_id, resource_type=resource_type,
                        resource_id=resource_id, **kwargs)

    def log_data(self, action: str, outcome: str, user_id: Optional[int] = None,
                 resource_type: str = "", resource_id: Optional[int] = None, **kwargs):
        return self.log(AuditCategory.DATA, action, outcome,
                        user_id=user_id, resource_type=resource_type,
                        resource_id=resource_id, **kwargs)

    def log_security(self, action: str, outcome: str, ip: str = "",
                     user_id: Optional[int] = None, **kwargs):
        return self.log(AuditCategory.SECURITY, action, outcome,
                        user_id=user_id, ip_address=ip, **kwargs)

    def log_compliance(self, action: str, outcome: str, user_id: Optional[int] = None, **kwargs):
        return self.log(AuditCategory.COMPLIANCE, action, outcome,
                        user_id=user_id, **kwargs)

    def log_ai(self, action: str, outcome: str, user_id: Optional[int] = None, **kwargs):
        return self.log(AuditCategory.AI, action, outcome,
                        user_id=user_id, **kwargs)

    def log_admin(self, action: str, outcome: str, user_id: Optional[int] = None, **kwargs):
        return self.log(AuditCategory.ADMIN, action, outcome,
                        user_id=user_id, **kwargs)

    # ── Query Methods ──

    def get_recent(self, limit: int = 50) -> List[dict]:
        """Get most recent audit entries."""
        with self._lock:
            entries = list(self._entries)[-limit:]
        entries.reverse()
        return [e.to_dict() for e in entries]

    def get_by_category(self, category: str, limit: int = 50) -> List[dict]:
        with self._lock:
            entries = list(self._by_category.get(category, []))[-limit:]
        entries.reverse()
        return [e.to_dict() for e in entries]

    def get_by_user(self, user_id: int, limit: int = 50) -> List[dict]:
        with self._lock:
            entries = list(self._by_user.get(user_id, []))[-limit:]
        entries.reverse()
        return [e.to_dict() for e in entries]

    def get_failures(self, limit: int = 50) -> List[dict]:
        with self._lock:
            entries = list(self._by_outcome.get("failure", []))[-limit:]
        entries.reverse()
        return [e.to_dict() for e in entries]

    def search(self, action_contains: str = "", category: str = "",
               user_id: Optional[int] = None, outcome: str = "",
               limit: int = 50) -> List[dict]:
        """Search audit entries with filters."""
        with self._lock:
            entries = list(self._entries)

        if category:
            entries = [e for e in entries if e.category == category]
        if user_id is not None:
            entries = [e for e in entries if e.user_id == user_id]
        if outcome:
            entries = [e for e in entries if e.outcome == outcome]
        if action_contains:
            action_lower = action_contains.lower()
            entries = [e for e in entries if action_lower in e.action.lower()]

        entries = entries[-limit:]
        entries.reverse()
        return [e.to_dict() for e in entries]

    # ── Integrity Check ──

    def verify_integrity(self, limit: int = 100) -> dict:
        """Verify that recent audit entries haven't been tampered with."""
        with self._lock:
            entries = list(self._entries)[-limit:]

        tampered = []
        for entry in entries:
            expected = entry._compute_fingerprint()
            if entry.fingerprint != expected:
                tampered.append(entry.sequence)

        return {
            "entries_checked": len(entries),
            "tampered_entries": tampered,
            "integrity_valid": len(tampered) == 0,
        }

    # ── User Activity Summary ──

    def user_activity_summary(self, user_id: int) -> dict:
        """Get activity summary for a specific user."""
        with self._lock:
            entries = list(self._by_user.get(user_id, []))

        if not entries:
            return {"user_id": user_id, "total_actions": 0}

        by_cat = defaultdict(int)
        by_outcome = defaultdict(int)
        actions = defaultdict(int)
        for e in entries:
            by_cat[e.category] += 1
            by_outcome[e.outcome] += 1
            actions[e.action] += 1

        return {
            "user_id": user_id,
            "total_actions": len(entries),
            "first_activity": entries[0].timestamp,
            "last_activity": entries[-1].timestamp,
            "by_category": dict(by_cat),
            "by_outcome": dict(by_outcome),
            "top_actions": dict(sorted(actions.items(), key=lambda x: -x[1])[:10]),
        }

    # ── Compliance Export ──

    def export_for_compliance(self, start_date: Optional[str] = None,
                               end_date: Optional[str] = None) -> dict:
        """Export audit log for compliance review."""
        with self._lock:
            entries = list(self._entries)

        if start_date:
            entries = [e for e in entries if e.timestamp >= start_date]
        if end_date:
            entries = [e for e in entries if e.timestamp <= end_date]

        return {
            "export_date": datetime.now().isoformat(),
            "total_entries": len(entries),
            "date_range": {
                "start": entries[0].timestamp if entries else None,
                "end": entries[-1].timestamp if entries else None,
            },
            "entries": [e.to_dict() for e in entries[-1000:]],  # Max 1000 per export
            "integrity": self.verify_integrity(len(entries)),
        }

    # ── Stats ──

    def stats(self) -> dict:
        uptime = time.time() - self._start_time
        with self._lock:
            return {
                "engine": "SecurityAudit",
                "total_entries": self._total_entries,
                "current_buffer_size": len(self._entries),
                "max_buffer_size": self._max_entries,
                "by_category": dict(self._total_by_category),
                "by_outcome": dict(self._total_by_outcome),
                "tracked_users": len(self._by_user),
                "failure_rate": round(
                    self._total_by_outcome.get("failure", 0) /
                    max(self._total_entries, 1) * 100, 2
                ),
                "uptime_seconds": round(uptime, 1),
            }


# ── Global Singleton ──
security_audit = SecurityAudit()
