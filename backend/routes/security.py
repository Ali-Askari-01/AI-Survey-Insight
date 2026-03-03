"""
Security Architecture API Routes
═══════════════════════════════════════════════════════
Complete API for the Security Architecture — Zero Trust Model.

Route Groups:
  /api/security/overview           — Security posture overview
  /api/security/tokens             — Token management (JWT lifecycle)
  /api/security/rbac               — Role-based access control
  /api/security/encryption         — Data encryption & classification
  /api/security/ai                 — AI security (prompt/output scanning)
  /api/security/threats            — Threat detection & IP blocking
  /api/security/compliance         — GDPR compliance, consent, DSRs
  /api/security/incidents          — Incident response & playbooks
  /api/security/audit              — Security audit trail
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional

router = APIRouter(prefix="/api/security", tags=["security"])


# ═══════════════════════════════════════════════════
# SECURITY OVERVIEW & ARCHITECTURE
# ═══════════════════════════════════════════════════

@router.get("/overview")
def security_overview():
    """Complete security posture dashboard."""
    from ..security.token_manager import token_manager
    from ..security.rbac_engine import rbac_engine
    from ..security.encryption_service import encryption_service
    from ..security.ai_security import ai_security
    from ..security.threat_detector import threat_detector
    from ..security.compliance_engine import compliance_engine
    from ..security.incident_response import incident_response
    from ..security.security_audit import security_audit

    return {
        "security_posture": "active",
        "architecture": "zero_trust",
        "layers": [
            "user_authentication",
            "role_authorization",
            "api_validation",
            "ai_protection",
            "data_encryption",
            "threat_detection",
            "compliance_monitoring",
            "audit_trail",
        ],
        "tokens": token_manager.stats(),
        "rbac": rbac_engine.stats(),
        "encryption": encryption_service.stats(),
        "ai_security": ai_security.stats(),
        "threats": threat_detector.stats(),
        "compliance": compliance_engine.stats(),
        "incidents": incident_response.stats(),
        "audit": security_audit.stats(),
    }


@router.get("/architecture")
def security_architecture():
    """Full security architecture specification."""
    return {
        "name": "Security Architecture",
        "philosophy": "Zero Trust — nothing is trusted automatically",
        "principles": [
            "Every interaction must be authenticated",
            "Every action must be authorized",
            "Every input must be validated",
            "Every sensitive action must be logged",
        ],
        "layers": {
            "1_user_layer": {
                "description": "Identity & authentication",
                "components": ["JWT token management", "Session tracking", "Password hashing"],
            },
            "2_application_layer": {
                "description": "Role-based access control",
                "components": ["RBAC engine", "Permission matrix", "Resource ownership"],
            },
            "3_api_layer": {
                "description": "Request validation & rate limiting",
                "components": ["Rate limiter", "Input sanitization", "Payload size limits"],
            },
            "4_ai_layer": {
                "description": "AI-specific threat protection",
                "components": ["Prompt injection scanning", "Output filtering", "Token budgets", "AI rate limits"],
            },
            "5_data_layer": {
                "description": "Data encryption & classification",
                "components": ["AES-256 encryption", "Field-level encryption", "Data classification", "Secure hashing"],
            },
            "6_infrastructure_layer": {
                "description": "Infrastructure protection",
                "components": ["Threat detection", "IP blocking", "Anomaly detection", "Session integrity"],
            },
            "7_monitoring_layer": {
                "description": "Security observability",
                "components": ["Audit trail", "Compliance engine", "Incident response", "Forensic history"],
            },
        },
        "modules": [
            "token_manager", "rbac_engine", "encryption_service", "ai_security",
            "threat_detector", "compliance_engine", "incident_response", "security_audit",
        ],
    }


# ═══════════════════════════════════════════════════
# TOKEN MANAGEMENT (Section 3: Identity & Authentication)
# ═══════════════════════════════════════════════════

@router.get("/tokens/stats")
def token_stats():
    """Token manager statistics."""
    from ..security.token_manager import token_manager
    return token_manager.stats()


@router.get("/tokens/sessions")
def active_sessions(limit: int = Query(50, ge=1, le=200)):
    """List active token sessions."""
    from ..security.token_manager import token_manager
    return {
        "active_sessions": token_manager.get_active_sessions(limit),
        "total": len(token_manager.get_active_sessions(limit)),
    }


@router.get("/tokens/sessions/{user_id}")
def user_sessions(user_id: int):
    """Get all sessions for a specific user."""
    from ..security.token_manager import token_manager
    return {
        "user_id": user_id,
        "sessions": token_manager.get_user_sessions(user_id),
    }


@router.post("/tokens/revoke/{token_id}")
def revoke_token(token_id: str):
    """Revoke a specific token."""
    from ..security.token_manager import token_manager
    success = token_manager.revoke_token(token_id)
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "Token revoked", "token_id": token_id}


@router.post("/tokens/revoke-all/{user_id}")
def revoke_all_tokens(user_id: int):
    """Revoke all tokens for a user (force logout everywhere)."""
    from ..security.token_manager import token_manager
    count = token_manager.revoke_all_user_tokens(user_id)
    return {"message": f"Revoked {count} tokens for user {user_id}", "revoked_count": count}


# ═══════════════════════════════════════════════════
# RBAC ENGINE (Section 4: Authorization)
# ═══════════════════════════════════════════════════

@router.get("/rbac/stats")
def rbac_stats():
    """RBAC engine statistics."""
    from ..security.rbac_engine import rbac_engine
    return rbac_engine.stats()


@router.get("/rbac/matrix")
def rbac_role_matrix():
    """Get the full role-permission matrix."""
    from ..security.rbac_engine import rbac_engine
    return rbac_engine.get_role_matrix()


@router.get("/rbac/permissions")
def all_permissions():
    """List all defined permissions."""
    from ..security.rbac_engine import rbac_engine
    return {"permissions": rbac_engine.get_all_permissions()}


@router.get("/rbac/user/{user_id}")
def user_permissions(user_id: int, role: str = Query("respondent")):
    """Get effective permissions for a user."""
    from ..security.rbac_engine import rbac_engine
    return rbac_engine.get_user_permissions(user_id, role)


@router.post("/rbac/check")
def check_permission(data: dict):
    """Check if a user has specific permission."""
    from ..security.rbac_engine import rbac_engine
    user_id = data.get("user_id", 0)
    role = data.get("role", "respondent")
    permission = data.get("permission", "")
    resource_type = data.get("resource_type")
    resource_id = data.get("resource_id")

    result = rbac_engine.check_permission(
        user_id=user_id,
        role=role,
        permission=permission,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    return result


@router.get("/rbac/audit")
def rbac_audit_log(
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = None,
    outcome: Optional[str] = None,
):
    """Get RBAC access check audit log."""
    from ..security.rbac_engine import rbac_engine
    return {
        "entries": rbac_engine.get_audit_log(limit, user_id, outcome),
    }


# ═══════════════════════════════════════════════════
# ENCRYPTION SERVICE (Section 6: Data Security)
# ═══════════════════════════════════════════════════

@router.get("/encryption/stats")
def encryption_stats():
    """Encryption service statistics."""
    from ..security.encryption_service import encryption_service
    return encryption_service.stats()


@router.get("/encryption/classifications")
def data_classifications():
    """Get data classification scheme (what fields are sensitive)."""
    from ..security.encryption_service import encryption_service
    return encryption_service.get_classifications()


@router.get("/encryption/operations")
def encryption_operations(limit: int = Query(50, ge=1, le=200)):
    """Get recent encryption/decryption operations log."""
    from ..security.encryption_service import encryption_service
    return {"operations": encryption_service.get_operations_log(limit)}


@router.post("/encryption/encrypt")
def encrypt_test(data: dict):
    """Test field encryption (development use)."""
    from ..security.encryption_service import encryption_service
    text = data.get("text", "")
    field_name = data.get("field_name", "test")
    if not text:
        raise HTTPException(status_code=400, detail="text field required")
    encrypted = encryption_service.encrypt_field(text, field_name)
    return {"encrypted": encrypted, "field_name": field_name}


@router.post("/encryption/decrypt")
def decrypt_test(data: dict):
    """Test field decryption (development use)."""
    from ..security.encryption_service import encryption_service
    ciphertext = data.get("ciphertext", "")
    if not ciphertext:
        raise HTTPException(status_code=400, detail="ciphertext field required")
    try:
        decrypted = encryption_service.decrypt_field(ciphertext)
        return {"decrypted": decrypted}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {str(e)}")


# ═══════════════════════════════════════════════════
# AI SECURITY (Section 7: AI Threat Model)
# ═══════════════════════════════════════════════════

@router.get("/ai/stats")
def ai_security_stats():
    """AI security engine statistics."""
    from ..security.ai_security import ai_security
    return ai_security.stats()


@router.get("/ai/threats")
def ai_threat_summary():
    """Get AI-specific threat summary."""
    from ..security.ai_security import ai_security
    return ai_security.get_threat_summary()


@router.post("/ai/scan-prompt")
def scan_prompt(data: dict):
    """Scan a prompt for injection attacks."""
    from ..security.ai_security import ai_security
    text = data.get("text", "")
    user_id = data.get("user_id")
    if not text:
        raise HTTPException(status_code=400, detail="text field required")
    result = ai_security.scan_prompt(text, user_id)
    return result.to_dict() if hasattr(result, "to_dict") else result.__dict__


@router.post("/ai/scan-output")
def scan_output(data: dict):
    """Scan AI output for harmful/leaked content."""
    from ..security.ai_security import ai_security
    text = data.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="text field required")
    result = ai_security.scan_output(text)
    return result.to_dict() if hasattr(result, "to_dict") else result.__dict__


@router.post("/ai/validate-request")
def validate_ai_request(data: dict):
    """Full AI request validation (prompt scan + token budget + rate limit)."""
    from ..security.ai_security import ai_security
    prompt = data.get("prompt", "")
    user_id = data.get("user_id", 0)
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt field required")
    return ai_security.validate_ai_request(prompt, user_id)


@router.post("/ai/validate-response")
def validate_ai_response(data: dict):
    """Validate an AI response before delivery to user."""
    from ..security.ai_security import ai_security
    text = data.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="text field required")
    return ai_security.validate_ai_response(text)


@router.post("/ai/check-budget")
def check_token_budget(data: dict):
    """Check if text is within token budget."""
    from ..security.ai_security import ai_security
    text = data.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="text field required")
    return ai_security.check_token_budget(text)


# ═══════════════════════════════════════════════════
# THREAT DETECTION (Section 10: Monitoring & Threat Detection)
# ═══════════════════════════════════════════════════

@router.get("/threats/stats")
def threat_stats():
    """Threat detector statistics."""
    from ..security.threat_detector import threat_detector
    return threat_detector.stats()


@router.get("/threats/active")
def active_threats(
    limit: int = Query(50, ge=1, le=200),
    category: Optional[str] = None,
    severity: Optional[str] = None,
):
    """Get detected threat events."""
    from ..security.threat_detector import threat_detector
    return {
        "threats": threat_detector.get_threats(limit, category, severity),
    }


@router.get("/threats/blocks")
def active_blocks():
    """Get currently blocked IPs."""
    from ..security.threat_detector import threat_detector
    return threat_detector.get_active_blocks()


@router.get("/threats/ip/{ip_address}")
def ip_reputation(ip_address: str):
    """Check reputation/history for a specific IP."""
    from ..security.threat_detector import threat_detector
    return threat_detector.get_ip_reputation(ip_address)


@router.post("/threats/record-request")
def record_request(data: dict):
    """Record a request for anomaly detection analysis."""
    from ..security.threat_detector import threat_detector
    ip = data.get("ip", "127.0.0.1")
    path = data.get("path", "/")
    user_id = data.get("user_id")
    status_code = data.get("status_code", 200)
    result = threat_detector.record_request(ip, path, user_id, status_code)
    if result:
        return {"threat_detected": True, "event": result.to_dict() if hasattr(result, "to_dict") else str(result)}
    return {"threat_detected": False}


@router.post("/threats/check-session")
def check_session(data: dict):
    """Check session integrity (detect hijacking)."""
    from ..security.threat_detector import threat_detector
    session_id = data.get("session_id", "")
    ip = data.get("ip", "")
    user_agent = data.get("user_agent", "")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    return threat_detector.check_session_integrity(session_id, ip, user_agent)


# ═══════════════════════════════════════════════════
# COMPLIANCE ENGINE (Section 11: Data Privacy & Compliance)
# ═══════════════════════════════════════════════════

@router.get("/compliance/stats")
def compliance_stats():
    """Compliance engine statistics."""
    from ..security.compliance_engine import compliance_engine
    return compliance_engine.stats()


@router.get("/compliance/retention")
def retention_policies():
    """Get data retention policies."""
    from ..security.compliance_engine import compliance_engine
    return {"policies": compliance_engine.get_retention_policies()}


@router.get("/compliance/retention/check")
def check_retention():
    """Check retention compliance status."""
    from ..security.compliance_engine import compliance_engine
    return compliance_engine.check_retention_compliance()


@router.get("/compliance/consent/{user_id}")
def get_user_consents(user_id: int):
    """Get all consent records for a user."""
    from ..security.compliance_engine import compliance_engine
    return compliance_engine.get_user_consents(user_id)


@router.post("/compliance/consent/grant")
def grant_consent(data: dict):
    """Record user consent grant."""
    from ..security.compliance_engine import compliance_engine
    user_id = data.get("user_id", 0)
    consent_type = data.get("consent_type", "")
    details = data.get("details", "")
    if not user_id or not consent_type:
        raise HTTPException(status_code=400, detail="user_id and consent_type required")
    compliance_engine.grant_consent(user_id, consent_type, details)
    return {"message": f"Consent '{consent_type}' granted for user {user_id}"}


@router.post("/compliance/consent/withdraw")
def withdraw_consent(data: dict):
    """Record user consent withdrawal."""
    from ..security.compliance_engine import compliance_engine
    user_id = data.get("user_id", 0)
    consent_type = data.get("consent_type", "")
    if not user_id or not consent_type:
        raise HTTPException(status_code=400, detail="user_id and consent_type required")
    compliance_engine.withdraw_consent(user_id, consent_type)
    return {"message": f"Consent '{consent_type}' withdrawn for user {user_id}"}


@router.get("/compliance/consent/history")
def consent_history(
    user_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """Get consent change history."""
    from ..security.compliance_engine import compliance_engine
    return {"history": compliance_engine.get_consent_history(user_id, limit)}


@router.post("/compliance/dsr/submit")
def submit_dsr(data: dict):
    """Submit a Data Subject Request (GDPR right to access/erasure/etc.)."""
    from ..security.compliance_engine import compliance_engine
    user_id = data.get("user_id", 0)
    request_type = data.get("request_type", "")
    details = data.get("details", "")
    if not user_id or not request_type:
        raise HTTPException(status_code=400, detail="user_id and request_type required")
    return compliance_engine.submit_dsr(user_id, request_type, details)


@router.post("/compliance/dsr/process/{dsr_id}")
def process_dsr(dsr_id: str, data: dict):
    """Process (complete/reject) a Data Subject Request."""
    from ..security.compliance_engine import compliance_engine
    status = data.get("status", "completed")
    notes = data.get("notes", "")
    return compliance_engine.process_dsr(dsr_id, status, notes)


@router.get("/compliance/dsr/pending")
def pending_dsrs():
    """Get pending Data Subject Requests."""
    from ..security.compliance_engine import compliance_engine
    return {"pending": compliance_engine.get_pending_dsrs()}


@router.get("/compliance/dsr/history")
def dsr_history(
    user_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """Get DSR processing history."""
    from ..security.compliance_engine import compliance_engine
    return {"history": compliance_engine.get_dsr_history(user_id, limit)}


# ═══════════════════════════════════════════════════
# INCIDENT RESPONSE (Section 16: Incident Response Plan)
# ═══════════════════════════════════════════════════

@router.get("/incidents/stats")
def incident_stats():
    """Incident response statistics."""
    from ..security.incident_response import incident_response
    return incident_response.stats()


@router.get("/incidents/active")
def active_incidents(severity: Optional[str] = None):
    """Get currently active incidents."""
    from ..security.incident_response import incident_response
    return {"incidents": incident_response.get_active_incidents(severity)}


@router.get("/incidents/resolved")
def resolved_incidents(limit: int = Query(50, ge=1, le=200)):
    """Get resolved incidents history."""
    from ..security.incident_response import incident_response
    return {"incidents": incident_response.get_resolved_incidents(limit)}


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    """Get details of a specific incident."""
    from ..security.incident_response import incident_response
    result = incident_response.get_incident(incident_id)
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@router.post("/incidents/create")
def create_incident(data: dict):
    """Create a new security incident."""
    from ..security.incident_response import incident_response
    title = data.get("title", "")
    severity = data.get("severity", "medium")
    description = data.get("description", "")
    source = data.get("source", "manual")
    if not title:
        raise HTTPException(status_code=400, detail="title required")
    return incident_response.create_incident(title, severity, description, source)


@router.put("/incidents/{incident_id}/status")
def update_incident_status(incident_id: str, data: dict):
    """Update incident status (investigating, contained, resolved, etc.)."""
    from ..security.incident_response import incident_response
    status = data.get("status", "")
    user = data.get("user", "system")
    notes = data.get("notes", "")
    if not status:
        raise HTTPException(status_code=400, detail="status required")
    result = incident_response.update_status(incident_id, status, user, notes)
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@router.get("/incidents/playbooks")
def get_playbooks():
    """Get available incident response playbooks."""
    from ..security.incident_response import incident_response
    return incident_response.get_playbooks()


@router.post("/incidents/playbooks/{playbook_name}/execute")
def execute_playbook(playbook_name: str, data: dict = {}):
    """Execute a predefined incident response playbook."""
    from ..security.incident_response import incident_response
    target_user_id = data.get("target_user_id")
    target_ip = data.get("target_ip")
    result = incident_response.execute_playbook(playbook_name, target_user_id, target_ip)
    if not result:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return result


# ═══════════════════════════════════════════════════
# SECURITY AUDIT TRAIL (Section 15: Security Logging)
# ═══════════════════════════════════════════════════

@router.get("/audit/stats")
def audit_stats():
    """Security audit trail statistics."""
    from ..security.security_audit import security_audit
    return security_audit.stats()


@router.get("/audit/recent")
def recent_audit_entries(limit: int = Query(50, ge=1, le=200)):
    """Get recent audit trail entries."""
    from ..security.security_audit import security_audit
    return {"entries": security_audit.get_recent(limit)}


@router.get("/audit/category/{category}")
def audit_by_category(category: str, limit: int = Query(50, ge=1, le=200)):
    """Get audit entries by category (auth, access, data, security, compliance, ai, admin)."""
    from ..security.security_audit import security_audit
    return {"category": category, "entries": security_audit.get_by_category(category, limit)}


@router.get("/audit/user/{user_id}")
def audit_by_user(user_id: int, limit: int = Query(50, ge=1, le=200)):
    """Get audit entries for a specific user."""
    from ..security.security_audit import security_audit
    return {"user_id": user_id, "entries": security_audit.get_by_user(user_id, limit)}


@router.get("/audit/failures")
def audit_failures(limit: int = Query(50, ge=1, le=200)):
    """Get failed action audit entries."""
    from ..security.security_audit import security_audit
    return {"entries": security_audit.get_failures(limit)}


@router.get("/audit/integrity")
def verify_audit_integrity(limit: int = Query(100, ge=10, le=1000)):
    """Verify tamper-resistance of audit trail via hash chain."""
    from ..security.security_audit import security_audit
    return security_audit.verify_integrity(limit)


@router.post("/audit/search")
def search_audit(data: dict):
    """Search audit trail entries."""
    from ..security.security_audit import security_audit
    return {
        "entries": security_audit.search(
            action_contains=data.get("action", ""),
            category=data.get("category", ""),
            user_id=data.get("user_id"),
            limit=data.get("limit", 50),
        )
    }
