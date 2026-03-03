"""
Incident Response — Automated Breach Detection & Response
═════════════════════════════════════════════════════════
Coordinates automated and manual incident response workflows.

Incident Severity Levels:
  P1 (Critical):  Active data breach, system compromise
  P2 (High):      Suspected breach, credential leak, mass lockout
  P3 (Medium):    Suspicious activity, policy violation
  P4 (Low):       Minor security event, false positive investigation

Response Workflow:
  1. DETECT  → Automated detection via threat_detector or manual report
  2. TRIAGE  → Classify severity, assign responder
  3. CONTAIN → Isolate affected systems/users (auto-block, revoke tokens)
  4. ANALYZE → Determine scope and root cause
  5. REMEDIATE → Fix vulnerability, restore services
  6. REVIEW  → Post-incident review, update procedures

Automated Actions:
  - Token revocation on suspected credential leak
  - IP blocking on confirmed attack
  - Session invalidation on session hijack
  - User lockout on compromised account
  - Alert escalation to admin channels
"""

import hashlib
import threading
import time
from collections import deque, defaultdict
from datetime import datetime
from typing import Optional, Dict, List


class IncidentSeverity:
    P1_CRITICAL = "P1_critical"
    P2_HIGH = "P2_high"
    P3_MEDIUM = "P3_medium"
    P4_LOW = "P4_low"


class IncidentStatus:
    DETECTED = "detected"
    TRIAGED = "triaged"
    CONTAINED = "contained"
    ANALYZING = "analyzing"
    REMEDIATING = "remediating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ContainmentAction:
    """Records an automated containment action."""

    def __init__(self, action_type: str, target: str, details: str = ""):
        self.timestamp = datetime.now().isoformat()
        self.action_type = action_type  # block_ip, revoke_tokens, lock_user, invalidate_sessions
        self.target = target
        self.details = details
        self.success = True

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "action_type": self.action_type,
            "target": self.target,
            "details": self.details,
            "success": self.success,
        }


class Incident:
    """A security incident with full lifecycle tracking."""

    def __init__(self, title: str, severity: str, description: str,
                 source: str = "automated", reporter_id: Optional[int] = None,
                 affected_users: Optional[List[int]] = None,
                 affected_ips: Optional[List[str]] = None):
        self.id = hashlib.md5(f"{time.time()}{title}".encode()).hexdigest()[:12]
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.title = title
        self.severity = severity
        self.description = description
        self.status = IncidentStatus.DETECTED
        self.source = source
        self.reporter_id = reporter_id
        self.affected_users = affected_users or []
        self.affected_ips = affected_ips or []
        self.containment_actions: List[ContainmentAction] = []
        self.timeline: List[dict] = [
            {"timestamp": self.created_at, "event": "Incident detected", "actor": source}
        ]
        self.root_cause: Optional[str] = None
        self.resolution: Optional[str] = None
        self.resolved_at: Optional[str] = None
        self.lessons_learned: Optional[str] = None

    def add_timeline_event(self, event: str, actor: str = "system"):
        self.updated_at = datetime.now().isoformat()
        self.timeline.append({
            "timestamp": self.updated_at,
            "event": event,
            "actor": actor,
        })

    def add_containment_action(self, action: ContainmentAction):
        self.containment_actions.append(action)
        self.add_timeline_event(f"Containment: {action.action_type} on {action.target}")

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "title": self.title,
            "severity": self.severity,
            "status": self.status,
            "description": self.description,
            "source": self.source,
            "affected_users": self.affected_users,
            "affected_ips": self.affected_ips,
            "containment_actions": [a.to_dict() for a in self.containment_actions],
            "timeline": self.timeline,
        }
        if self.reporter_id is not None:
            d["reporter_id"] = self.reporter_id
        if self.root_cause:
            d["root_cause"] = self.root_cause
        if self.resolution:
            d["resolution"] = self.resolution
        if self.resolved_at:
            d["resolved_at"] = self.resolved_at
        if self.lessons_learned:
            d["lessons_learned"] = self.lessons_learned
        return d


class IncidentResponse:
    """
    Incident Response Coordinator.

    Features:
    - Incident creation (automated + manual)
    - Severity-based automated containment
    - Full incident lifecycle management
    - Containment action tracking
    - Timeline and audit trail
    - Post-incident review support
    - Playbook-based response automation
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._active_incidents: Dict[str, Incident] = {}
        self._resolved_incidents: deque = deque(maxlen=2000)
        self._total_incidents = 0
        self._by_severity: Dict[str, int] = defaultdict(int)
        self._start_time = time.time()

        # Auto-response playbooks
        self._playbooks = {
            "brute_force": {
                "severity": IncidentSeverity.P2_HIGH,
                "auto_actions": ["block_ip", "lock_user"],
                "description": "Automated response to brute force attacks",
            },
            "session_hijack": {
                "severity": IncidentSeverity.P1_CRITICAL,
                "auto_actions": ["invalidate_sessions", "lock_user", "revoke_tokens"],
                "description": "Response to suspected session hijacking",
            },
            "data_exfiltration": {
                "severity": IncidentSeverity.P1_CRITICAL,
                "auto_actions": ["lock_user", "revoke_tokens", "block_ip"],
                "description": "Response to suspected data exfiltration",
            },
            "privilege_escalation": {
                "severity": IncidentSeverity.P2_HIGH,
                "auto_actions": ["lock_user", "revoke_tokens"],
                "description": "Response to privilege escalation attempts",
            },
            "ai_abuse": {
                "severity": IncidentSeverity.P3_MEDIUM,
                "auto_actions": ["lock_user"],
                "description": "Response to AI system abuse",
            },
        }

    # ── Incident Creation ──

    def create_incident(self, title: str, severity: str, description: str,
                        source: str = "automated", reporter_id: Optional[int] = None,
                        affected_users: Optional[List[int]] = None,
                        affected_ips: Optional[List[str]] = None) -> dict:
        """Create a new security incident."""
        incident = Incident(title, severity, description, source,
                            reporter_id, affected_users, affected_ips)

        with self._lock:
            self._active_incidents[incident.id] = incident
            self._total_incidents += 1
            self._by_severity[severity] += 1

        return incident.to_dict()

    def create_from_threat(self, threat_event: dict) -> dict:
        """Create an incident from a threat detector event."""
        severity_map = {
            "critical": IncidentSeverity.P1_CRITICAL,
            "high": IncidentSeverity.P2_HIGH,
            "medium": IncidentSeverity.P3_MEDIUM,
            "low": IncidentSeverity.P4_LOW,
        }
        severity = severity_map.get(threat_event.get("level", "low"), IncidentSeverity.P4_LOW)

        return self.create_incident(
            title=f"Auto: {threat_event.get('category', 'unknown')} threat",
            severity=severity,
            description=threat_event.get("description", "Automated threat detection"),
            source="threat_detector",
            affected_users=[threat_event["user_id"]] if threat_event.get("user_id") else None,
            affected_ips=[threat_event["source_ip"]] if threat_event.get("source_ip") else None,
        )

    # ── Lifecycle Management ──

    def triage_incident(self, incident_id: str, severity: Optional[str] = None,
                        notes: str = "") -> dict:
        """Triage an incident — optionally update severity."""
        with self._lock:
            incident = self._active_incidents.get(incident_id)
            if not incident:
                return {"error": "Incident not found"}
            incident.status = IncidentStatus.TRIAGED
            if severity:
                incident.severity = severity
            incident.add_timeline_event(f"Triaged{': ' + notes if notes else ''}", "admin")
            return incident.to_dict()

    def contain_incident(self, incident_id: str, actions: Optional[List[dict]] = None) -> dict:
        """Mark incident as contained, record containment actions."""
        with self._lock:
            incident = self._active_incidents.get(incident_id)
            if not incident:
                return {"error": "Incident not found"}
            incident.status = IncidentStatus.CONTAINED
            if actions:
                for a in actions:
                    action = ContainmentAction(
                        a.get("type", "manual"),
                        a.get("target", "unknown"),
                        a.get("details", "")
                    )
                    incident.add_containment_action(action)
            else:
                incident.add_timeline_event("Contained — awaiting analysis")
            return incident.to_dict()

    def update_status(self, incident_id: str, status: str,
                      notes: str = "", actor: str = "admin") -> dict:
        """Update incident status."""
        valid_statuses = {
            IncidentStatus.TRIAGED, IncidentStatus.CONTAINED,
            IncidentStatus.ANALYZING, IncidentStatus.REMEDIATING,
            IncidentStatus.RESOLVED, IncidentStatus.CLOSED,
        }
        if status not in valid_statuses:
            return {"error": f"Invalid status. Must be one of: {valid_statuses}"}

        with self._lock:
            incident = self._active_incidents.get(incident_id)
            if not incident:
                return {"error": "Incident not found"}
            incident.status = status
            incident.add_timeline_event(
                f"Status → {status}{': ' + notes if notes else ''}", actor
            )
            if status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
                incident.resolved_at = datetime.now().isoformat()
                self._resolved_incidents.append(incident)
                del self._active_incidents[incident_id]
            return incident.to_dict()

    def set_root_cause(self, incident_id: str, root_cause: str) -> dict:
        with self._lock:
            incident = self._active_incidents.get(incident_id)
            if not incident:
                return {"error": "Incident not found"}
            incident.root_cause = root_cause
            incident.add_timeline_event(f"Root cause identified: {root_cause[:100]}")
            return incident.to_dict()

    def set_resolution(self, incident_id: str, resolution: str) -> dict:
        with self._lock:
            incident = self._active_incidents.get(incident_id)
            if not incident:
                return {"error": "Incident not found"}
            incident.resolution = resolution
            incident.add_timeline_event(f"Resolution documented")
            return incident.to_dict()

    def add_lessons_learned(self, incident_id: str, lessons: str) -> dict:
        """Add post-incident review notes to resolved incident."""
        with self._lock:
            # Check both active and resolved
            incident = self._active_incidents.get(incident_id)
            if not incident:
                for r in self._resolved_incidents:
                    if r.id == incident_id:
                        incident = r
                        break
            if not incident:
                return {"error": "Incident not found"}
            incident.lessons_learned = lessons
            return incident.to_dict()

    # ── Playbook Execution ──

    def execute_playbook(self, playbook_name: str, target_user_id: Optional[int] = None,
                         target_ip: Optional[str] = None) -> dict:
        """Execute an automated response playbook."""
        playbook = self._playbooks.get(playbook_name)
        if not playbook:
            return {"error": f"Playbook '{playbook_name}' not found"}

        actions_taken = []
        for action_type in playbook["auto_actions"]:
            action = ContainmentAction(
                action_type,
                f"user:{target_user_id}" if target_user_id else f"ip:{target_ip}",
                f"Automated via playbook: {playbook_name}"
            )
            actions_taken.append(action.to_dict())

        # Create incident
        incident = self.create_incident(
            title=f"Playbook: {playbook_name}",
            severity=playbook["severity"],
            description=playbook["description"],
            source="playbook",
            affected_users=[target_user_id] if target_user_id else None,
            affected_ips=[target_ip] if target_ip else None,
        )

        return {
            "playbook": playbook_name,
            "incident_id": incident["id"],
            "severity": playbook["severity"],
            "actions_executed": actions_taken,
            "description": playbook["description"],
        }

    def get_playbooks(self) -> dict:
        return dict(self._playbooks)

    # ── Queries ──

    def get_active_incidents(self, severity: Optional[str] = None) -> List[dict]:
        with self._lock:
            incidents = list(self._active_incidents.values())
        if severity:
            incidents = [i for i in incidents if i.severity == severity]
        return [i.to_dict() for i in incidents]

    def get_incident(self, incident_id: str) -> dict:
        with self._lock:
            incident = self._active_incidents.get(incident_id)
            if incident:
                return incident.to_dict()
            for r in self._resolved_incidents:
                if r.id == incident_id:
                    return r.to_dict()
        return {"error": "Incident not found"}

    def get_resolved_incidents(self, limit: int = 50) -> List[dict]:
        with self._lock:
            resolved = list(self._resolved_incidents)[-limit:]
        resolved.reverse()
        return [i.to_dict() for i in resolved]

    # ── Stats ──

    def stats(self) -> dict:
        uptime = time.time() - self._start_time
        with self._lock:
            return {
                "engine": "IncidentResponse",
                "total_incidents": self._total_incidents,
                "active_incidents": len(self._active_incidents),
                "resolved_incidents": len(self._resolved_incidents),
                "by_severity": dict(self._by_severity),
                "playbooks_available": len(self._playbooks),
                "uptime_seconds": round(uptime, 1),
            }


# ── Global Singleton ──
incident_response = IncidentResponse()
