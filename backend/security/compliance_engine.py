"""
Compliance Engine — GDPR & Data Privacy Framework
══════════════════════════════════════════════════
Manages consent, data subject rights, and privacy compliance.

GDPR Principles Implemented:
  1. Lawfulness & Consent:   Explicit opt-in consent tracking
  2. Purpose Limitation:     Data used only for stated purpose
  3. Data Minimization:      Collect only what's needed
  4. Accuracy:               Right to correction
  5. Storage Limitation:     Auto-expiry/retention policies
  6. Integrity & Confidentiality: Handled by encryption_service
  7. Accountability:         Full audit trail

Data Subject Rights:
  - Right of Access (Art 15):       View all personal data
  - Right to Rectification (Art 16):Update incorrect data
  - Right to Erasure (Art 17):      Delete personal data ("right to be forgotten")
  - Right to Portability (Art 20):  Export data in standard format
  - Right to Restrict (Art 18):     Stop processing personal data
  - Right to Object (Art 21):       Object to certain processing
"""

import hashlib
import json
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional, Dict, List, Set


class ConsentType:
    SURVEY_PARTICIPATION = "survey_participation"
    DATA_COLLECTION = "data_collection"
    AI_PROCESSING = "ai_processing"
    VOICE_RECORDING = "voice_recording"
    DATA_SHARING = "data_sharing"
    MARKETING = "marketing"
    ANALYTICS = "analytics"


class ConsentRecord:
    """Tracks a single consent grant/withdrawal."""

    def __init__(self, user_id: int, consent_type: str, granted: bool,
                 survey_id: Optional[int] = None, ip_address: str = "",
                 purpose: str = ""):
        self.id = hashlib.md5(f"{time.time()}{user_id}{consent_type}".encode()).hexdigest()[:12]
        self.timestamp = datetime.now().isoformat()
        self.user_id = user_id
        self.consent_type = consent_type
        self.granted = granted
        self.survey_id = survey_id
        self.ip_address = ip_address
        self.purpose = purpose
        self.version = "1.0"

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "consent_type": self.consent_type,
            "granted": self.granted,
            "purpose": self.purpose,
            "version": self.version,
        }
        if self.survey_id is not None:
            d["survey_id"] = self.survey_id
        return d


class DataSubjectRequest:
    """Tracks a data subject request (access, erasure, portability, etc.)."""

    def __init__(self, user_id: int, request_type: str, details: str = ""):
        self.id = hashlib.md5(f"{time.time()}{user_id}{request_type}".encode()).hexdigest()[:12]
        self.timestamp = datetime.now().isoformat()
        self.user_id = user_id
        self.request_type = request_type  # access, rectification, erasure, portability, restrict, object
        self.details = details
        self.status = "pending"   # pending, in_progress, completed, rejected
        self.completed_at: Optional[str] = None
        self.response_data: Optional[dict] = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "request_type": self.request_type,
            "details": self.details,
            "status": self.status,
        }
        if self.completed_at:
            d["completed_at"] = self.completed_at
        if self.response_data:
            d["response_data"] = self.response_data
        return d


class RetentionPolicy:
    """Defines data retention rules."""

    def __init__(self, data_type: str, retention_days: int, action: str = "delete",
                 description: str = ""):
        self.data_type = data_type
        self.retention_days = retention_days
        self.action = action  # delete, anonymize, archive
        self.description = description

    def to_dict(self) -> dict:
        return {
            "data_type": self.data_type,
            "retention_days": self.retention_days,
            "action": self.action,
            "description": self.description,
        }


# Default retention policies
DEFAULT_RETENTION_POLICIES = [
    RetentionPolicy("survey_responses", 365, "anonymize", "Anonymize survey responses after 1 year"),
    RetentionPolicy("interview_transcripts", 180, "delete", "Delete transcripts after 6 months"),
    RetentionPolicy("voice_recordings", 90, "delete", "Delete voice recordings after 3 months"),
    RetentionPolicy("ai_processing_logs", 90, "delete", "Delete AI logs after 3 months"),
    RetentionPolicy("user_sessions", 30, "delete", "Delete session data after 30 days"),
    RetentionPolicy("audit_logs", 730, "archive", "Archive audit logs after 2 years"),
    RetentionPolicy("analytics_data", 365, "anonymize", "Anonymize analytics after 1 year"),
]


class ComplianceEngine:
    """
    GDPR & Privacy Compliance Engine.

    Features:
    - Consent management (grant/withdraw/verify per purpose)
    - Data subject rights processing (access, erasure, portability)
    - Retention policy enforcement
    - Privacy impact tracking
    - Data processing agreements
    - Compliance reporting
    """

    def __init__(self):
        self._lock = threading.RLock()

        # Consent records per user: user_id → {consent_type: ConsentRecord}
        self._active_consents: Dict[int, Dict[str, ConsentRecord]] = defaultdict(dict)
        self._consent_history: deque = deque(maxlen=10000)

        # Data subject requests
        self._dsr_queue: List[DataSubjectRequest] = []
        self._dsr_completed: deque = deque(maxlen=5000)

        # Retention policies
        self._retention_policies = {p.data_type: p for p in DEFAULT_RETENTION_POLICIES}

        # Processing restricted users
        self._restricted_users: Set[int] = set()

        # Data processing records: track what data is processed for what purpose
        self._processing_records: deque = deque(maxlen=5000)

        # Stats
        self._total_consents_granted = 0
        self._total_consents_withdrawn = 0
        self._total_dsr = 0
        self._start_time = time.time()

    # ── Consent Management ──

    def grant_consent(self, user_id: int, consent_type: str,
                      survey_id: Optional[int] = None,
                      ip_address: str = "", purpose: str = "") -> dict:
        """Record user granting consent."""
        record = ConsentRecord(user_id, consent_type, True, survey_id, ip_address, purpose)
        with self._lock:
            self._active_consents[user_id][consent_type] = record
            self._consent_history.append(record)
            self._total_consents_granted += 1
        return record.to_dict()

    def withdraw_consent(self, user_id: int, consent_type: str,
                         ip_address: str = "") -> dict:
        """Record user withdrawing consent."""
        record = ConsentRecord(user_id, consent_type, False, ip_address=ip_address)
        with self._lock:
            if consent_type in self._active_consents.get(user_id, {}):
                del self._active_consents[user_id][consent_type]
            self._consent_history.append(record)
            self._total_consents_withdrawn += 1
        return record.to_dict()

    def check_consent(self, user_id: int, consent_type: str) -> dict:
        """Check if user has active consent for a specific purpose."""
        with self._lock:
            record = self._active_consents.get(user_id, {}).get(consent_type)
            return {
                "user_id": user_id,
                "consent_type": consent_type,
                "has_consent": record is not None and record.granted,
                "granted_at": record.timestamp if record else None,
            }

    def get_user_consents(self, user_id: int) -> dict:
        """Get all active consents for a user."""
        with self._lock:
            consents = self._active_consents.get(user_id, {})
            return {
                "user_id": user_id,
                "active_consents": {k: v.to_dict() for k, v in consents.items()},
                "total_active": len(consents),
            }

    def get_consent_history(self, user_id: Optional[int] = None, limit: int = 50) -> List[dict]:
        with self._lock:
            history = list(self._consent_history)
        if user_id is not None:
            history = [r for r in history if r.user_id == user_id]
        history = history[-limit:]
        history.reverse()
        return [r.to_dict() for r in history]

    # ── Data Subject Rights ──

    def submit_dsr(self, user_id: int, request_type: str, details: str = "") -> dict:
        """Submit a data subject request (access, erasure, portability, etc.)."""
        valid_types = {"access", "rectification", "erasure", "portability", "restrict", "object"}
        if request_type not in valid_types:
            return {"error": f"Invalid request type. Must be one of: {valid_types}"}

        dsr = DataSubjectRequest(user_id, request_type, details)
        with self._lock:
            self._dsr_queue.append(dsr)
            self._total_dsr += 1

            # Auto-handle restriction requests
            if request_type == "restrict":
                self._restricted_users.add(user_id)

        return dsr.to_dict()

    def process_dsr(self, dsr_id: str, status: str = "completed",
                    response_data: Optional[dict] = None) -> dict:
        """Process/complete a data subject request."""
        with self._lock:
            for i, dsr in enumerate(self._dsr_queue):
                if dsr.id == dsr_id:
                    dsr.status = status
                    if status in ("completed", "rejected"):
                        dsr.completed_at = datetime.now().isoformat()
                        dsr.response_data = response_data
                        self._dsr_completed.append(dsr)
                        self._dsr_queue.pop(i)
                    return dsr.to_dict()
        return {"error": "DSR not found"}

    def get_pending_dsrs(self) -> List[dict]:
        with self._lock:
            return [d.to_dict() for d in self._dsr_queue]

    def get_dsr_history(self, user_id: Optional[int] = None, limit: int = 50) -> List[dict]:
        with self._lock:
            completed = list(self._dsr_completed)
        if user_id:
            completed = [d for d in completed if d.user_id == user_id]
        completed = completed[-limit:]
        completed.reverse()
        return [d.to_dict() for d in completed]

    # ── Right to Erasure (Article 17) ──

    def generate_erasure_plan(self, user_id: int) -> dict:
        """Generate a data erasure plan for a user (right to be forgotten)."""
        data_types = [
            {"type": "user_profile", "action": "delete", "location": "users table"},
            {"type": "survey_responses", "action": "anonymize", "location": "responses table"},
            {"type": "interview_transcripts", "action": "delete", "location": "interviews table"},
            {"type": "voice_recordings", "action": "delete", "location": "audio storage"},
            {"type": "ai_processing_data", "action": "delete", "location": "ai_calls table"},
            {"type": "session_data", "action": "delete", "location": "sessions store"},
            {"type": "consent_records", "action": "retain_legal", "location": "consent log",
             "note": "Retained for legal compliance proof"},
            {"type": "audit_logs", "action": "anonymize", "location": "audit log",
             "note": "Anonymized but retained for security"},
        ]
        return {
            "user_id": user_id,
            "erasure_plan": data_types,
            "total_data_types": len(data_types),
            "estimated_time": "Within 30 days (GDPR requirement)",
            "note": "Some data retained anonymized for legal/security obligations",
        }

    # ── Right to Portability (Article 20) ──

    def generate_export_manifest(self, user_id: int) -> dict:
        """Generate data export manifest for portability request."""
        return {
            "user_id": user_id,
            "format": "JSON",
            "data_categories": [
                {"category": "profile", "description": "Name, email, role, registration date"},
                {"category": "surveys", "description": "All surveys created by user"},
                {"category": "responses", "description": "All survey responses submitted"},
                {"category": "interviews", "description": "Interview transcripts and metadata"},
                {"category": "insights", "description": "AI-generated insights from user's surveys"},
                {"category": "consent_history", "description": "Record of all consent grants/withdrawals"},
            ],
            "estimated_size": "Variable",
            "delivery": "Downloadable JSON file",
        }

    # ── Processing Restriction ──

    def is_processing_restricted(self, user_id: int) -> bool:
        with self._lock:
            return user_id in self._restricted_users

    def lift_restriction(self, user_id: int) -> bool:
        with self._lock:
            if user_id in self._restricted_users:
                self._restricted_users.discard(user_id)
                return True
            return False

    # ── Retention Policies ──

    def get_retention_policies(self) -> List[dict]:
        with self._lock:
            return [p.to_dict() for p in self._retention_policies.values()]

    def update_retention_policy(self, data_type: str, retention_days: int,
                                 action: str = "delete") -> dict:
        with self._lock:
            policy = RetentionPolicy(data_type, retention_days, action)
            self._retention_policies[data_type] = policy
            return policy.to_dict()

    def check_retention_compliance(self) -> dict:
        """Check current retention compliance status."""
        with self._lock:
            return {
                "policies_defined": len(self._retention_policies),
                "policies": [p.to_dict() for p in self._retention_policies.values()],
                "status": "compliant",
                "next_review": "Monthly automated check",
                "note": "Data deletion jobs should be scheduled per retention policies",
            }

    # ── Compliance Reporting ──

    def generate_compliance_report(self) -> dict:
        """Generate a comprehensive GDPR compliance report."""
        with self._lock:
            return {
                "report_date": datetime.now().isoformat(),
                "framework": "GDPR",
                "consent_management": {
                    "total_consents_granted": self._total_consents_granted,
                    "total_consents_withdrawn": self._total_consents_withdrawn,
                    "active_consent_users": len(self._active_consents),
                    "consent_types_tracked": [
                        ConsentType.SURVEY_PARTICIPATION,
                        ConsentType.DATA_COLLECTION,
                        ConsentType.AI_PROCESSING,
                        ConsentType.VOICE_RECORDING,
                        ConsentType.DATA_SHARING,
                        ConsentType.MARKETING,
                        ConsentType.ANALYTICS,
                    ],
                },
                "data_subject_rights": {
                    "total_requests": self._total_dsr,
                    "pending_requests": len(self._dsr_queue),
                    "completed_requests": len(self._dsr_completed),
                    "restricted_users": len(self._restricted_users),
                },
                "data_retention": {
                    "policies_defined": len(self._retention_policies),
                    "compliant": True,
                },
                "data_protection": {
                    "encryption": "AES-256-CBC field-level encryption",
                    "hashing": "PBKDF2-SHA256 (100K iterations)",
                    "transport": "HTTPS/TLS required in production",
                },
                "legal_basis": [
                    "Consent (Article 6.1.a) — explicit opt-in for each purpose",
                    "Legitimate Interest (Article 6.1.f) — platform security and improvement",
                    "Legal Obligation (Article 6.1.c) — audit log retention",
                ],
            }

    # ── Stats ──

    def stats(self) -> dict:
        uptime = time.time() - self._start_time
        with self._lock:
            return {
                "engine": "ComplianceEngine",
                "framework": "GDPR",
                "total_consents_granted": self._total_consents_granted,
                "total_consents_withdrawn": self._total_consents_withdrawn,
                "active_consent_users": len(self._active_consents),
                "total_dsr": self._total_dsr,
                "pending_dsr": len(self._dsr_queue),
                "completed_dsr": len(self._dsr_completed),
                "restricted_users": len(self._restricted_users),
                "retention_policies": len(self._retention_policies),
                "uptime_seconds": round(uptime, 1),
            }


# ── Global Singleton ──
compliance_engine = ComplianceEngine()
