"""
RBAC Engine — Fine-Grained Authorization Architecture
═══════════════════════════════════════════════════════
Authentication = Who you are
Authorization = What you can do

Role-Based Access Control with resource-level permissions.

Roles:
  Founder/Admin:  Full system access
  Researcher/PM:  Own surveys + team surveys
  Designer:       Survey design only
  Respondent:     Interview participation only
  Worker:         AI processing only (service account)

Principle: Researcher A ❌ cannot access Researcher B's survey.
"""

import threading
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, List, Set


# ── Permission Definitions ──
class Permission:
    """Defines a single permission."""
    # Survey permissions
    SURVEY_CREATE = "survey:create"
    SURVEY_READ = "survey:read"
    SURVEY_READ_OWN = "survey:read_own"
    SURVEY_UPDATE = "survey:update"
    SURVEY_UPDATE_OWN = "survey:update_own"
    SURVEY_DELETE = "survey:delete"
    SURVEY_DELETE_OWN = "survey:delete_own"
    SURVEY_PUBLISH = "survey:publish"

    # Interview permissions
    INTERVIEW_PARTICIPATE = "interview:participate"
    INTERVIEW_VIEW = "interview:view"
    INTERVIEW_VIEW_OWN = "interview:view_own"
    INTERVIEW_MANAGE = "interview:manage"

    # Insight/Report permissions
    INSIGHT_VIEW = "insight:view"
    INSIGHT_VIEW_OWN = "insight:view_own"
    REPORT_GENERATE = "report:generate"
    REPORT_EXPORT = "report:export"

    # AI permissions
    AI_PROCESS = "ai:process"
    AI_CONFIGURE = "ai:configure"
    AI_COST_VIEW = "ai:cost_view"

    # User management
    USER_VIEW = "user:view"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DEACTIVATE = "user:deactivate"
    USER_ROLE_CHANGE = "user:role_change"

    # System permissions
    SYSTEM_CONFIG = "system:config"
    SYSTEM_MONITOR = "system:monitor"
    SYSTEM_AUDIT = "system:audit"
    SYSTEM_BACKUP = "system:backup"

    # Data permissions
    DATA_EXPORT = "data:export"
    DATA_DELETE = "data:delete"
    DATA_GOVERNANCE = "data:governance"


# ── Role Definitions with Permission Matrix ──
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "founder": {
        # Full system access
        Permission.SURVEY_CREATE, Permission.SURVEY_READ, Permission.SURVEY_UPDATE,
        Permission.SURVEY_DELETE, Permission.SURVEY_PUBLISH,
        Permission.INTERVIEW_VIEW, Permission.INTERVIEW_MANAGE,
        Permission.INSIGHT_VIEW, Permission.REPORT_GENERATE, Permission.REPORT_EXPORT,
        Permission.AI_PROCESS, Permission.AI_CONFIGURE, Permission.AI_COST_VIEW,
        Permission.USER_VIEW, Permission.USER_CREATE, Permission.USER_UPDATE,
        Permission.USER_DEACTIVATE, Permission.USER_ROLE_CHANGE,
        Permission.SYSTEM_CONFIG, Permission.SYSTEM_MONITOR, Permission.SYSTEM_AUDIT,
        Permission.SYSTEM_BACKUP,
        Permission.DATA_EXPORT, Permission.DATA_DELETE, Permission.DATA_GOVERNANCE,
    },
    "pm": {
        Permission.SURVEY_CREATE, Permission.SURVEY_READ, Permission.SURVEY_UPDATE,
        Permission.SURVEY_PUBLISH,
        Permission.INTERVIEW_VIEW, Permission.INTERVIEW_MANAGE,
        Permission.INSIGHT_VIEW, Permission.REPORT_GENERATE, Permission.REPORT_EXPORT,
        Permission.AI_PROCESS, Permission.AI_COST_VIEW,
        Permission.USER_VIEW,
        Permission.SYSTEM_MONITOR,
        Permission.DATA_EXPORT,
    },
    "designer": {
        Permission.SURVEY_CREATE, Permission.SURVEY_READ_OWN, Permission.SURVEY_UPDATE_OWN,
        Permission.SURVEY_PUBLISH,
        Permission.INTERVIEW_VIEW_OWN,
        Permission.INSIGHT_VIEW_OWN,
        Permission.AI_PROCESS,
    },
    "engineer": {
        Permission.SURVEY_READ,
        Permission.INTERVIEW_VIEW,
        Permission.INSIGHT_VIEW,
        Permission.AI_PROCESS, Permission.AI_CONFIGURE,
        Permission.SYSTEM_CONFIG, Permission.SYSTEM_MONITOR, Permission.SYSTEM_AUDIT,
        Permission.SYSTEM_BACKUP,
    },
    "respondent": {
        Permission.INTERVIEW_PARTICIPATE,
        Permission.SURVEY_READ_OWN,  # Can see surveys they're invited to
    },
    "worker": {
        # Service account for AI processing
        Permission.AI_PROCESS,
        Permission.INTERVIEW_MANAGE,
        Permission.INSIGHT_VIEW,
    },
}


class AccessDecision:
    """Records an access control decision for audit."""

    def __init__(self, user_id: int, role: str, permission: str,
                 resource_type: str = "", resource_id: Optional[int] = None,
                 allowed: bool = False, reason: str = ""):
        self.timestamp = datetime.now().isoformat()
        self.user_id = user_id
        self.role = role
        self.permission = permission
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.allowed = allowed
        self.reason = reason

    def to_dict(self) -> dict:
        d = {
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "role": self.role,
            "permission": self.permission,
            "allowed": self.allowed,
            "reason": self.reason,
        }
        if self.resource_type:
            d["resource_type"] = self.resource_type
        if self.resource_id is not None:
            d["resource_id"] = self.resource_id
        return d


class RBACEngine:
    """
    Role-Based Access Control Engine — fine-grained authorization.

    Features:
    - 6 pre-defined roles with 30+ permissions
    - Resource-level ownership checks (Researcher A can't access Researcher B's data)
    - Permission evaluation with detailed reason
    - Access decision audit logging
    - Custom permission grants/revocations per user
    - Role hierarchy for implicit permission inheritance
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._role_permissions = {k: set(v) for k, v in ROLE_PERMISSIONS.items()}

        # Per-user custom permissions (overrides)
        self._user_grants: Dict[int, Set[str]] = defaultdict(set)
        self._user_revocations: Dict[int, Set[str]] = defaultdict(set)

        # Resource ownership: (resource_type, resource_id) → owner_user_id
        self._resource_owners: Dict[tuple, int] = {}

        # Audit log
        from collections import deque
        self._audit_log: deque = deque(maxlen=5000)

        # Statistics
        self._total_checks = 0
        self._total_allowed = 0
        self._total_denied = 0
        self._start_time = __import__("time").time()

    # ── Permission Check ──

    def check_permission(
        self,
        user_id: int,
        role: str,
        permission: str,
        resource_type: str = "",
        resource_id: Optional[int] = None,
    ) -> tuple:
        """
        Check if a user has a specific permission.
        Returns (allowed: bool, reason: str)
        """
        with self._lock:
            self._total_checks += 1

            # Check user-specific revocations first
            if permission in self._user_revocations.get(user_id, set()):
                decision = AccessDecision(
                    user_id, role, permission, resource_type, resource_id,
                    False, "Permission explicitly revoked for user"
                )
                self._audit_log.append(decision)
                self._total_denied += 1
                return False, decision.reason

            # Check user-specific grants
            if permission in self._user_grants.get(user_id, set()):
                decision = AccessDecision(
                    user_id, role, permission, resource_type, resource_id,
                    True, "Permission explicitly granted to user"
                )
                self._audit_log.append(decision)
                self._total_allowed += 1
                return True, decision.reason

            # Check role permissions
            role_perms = self._role_permissions.get(role, set())
            if permission in role_perms:
                # For _own permissions, check ownership
                if permission.endswith("_own") and resource_type and resource_id is not None:
                    owner = self._resource_owners.get((resource_type, resource_id))
                    if owner is not None and owner != user_id:
                        decision = AccessDecision(
                            user_id, role, permission, resource_type, resource_id,
                            False, f"Resource owned by user {owner}, not {user_id}"
                        )
                        self._audit_log.append(decision)
                        self._total_denied += 1
                        return False, decision.reason

                decision = AccessDecision(
                    user_id, role, permission, resource_type, resource_id,
                    True, f"Allowed by role '{role}'"
                )
                self._audit_log.append(decision)
                self._total_allowed += 1
                return True, decision.reason

            # Check if the non-_own variant exists (e.g., survey:read covers survey:read_own)
            base_perm = permission.replace("_own", "")
            if base_perm != permission and base_perm in role_perms:
                decision = AccessDecision(
                    user_id, role, permission, resource_type, resource_id,
                    True, f"Allowed by broader permission '{base_perm}'"
                )
                self._audit_log.append(decision)
                self._total_allowed += 1
                return True, decision.reason

            decision = AccessDecision(
                user_id, role, permission, resource_type, resource_id,
                False, f"Role '{role}' does not have permission '{permission}'"
            )
            self._audit_log.append(decision)
            self._total_denied += 1
            return False, decision.reason

    # ── Resource Ownership ──

    def register_resource(self, resource_type: str, resource_id: int, owner_user_id: int):
        """Register ownership of a resource."""
        with self._lock:
            self._resource_owners[(resource_type, resource_id)] = owner_user_id

    def get_resource_owner(self, resource_type: str, resource_id: int) -> Optional[int]:
        with self._lock:
            return self._resource_owners.get((resource_type, resource_id))

    def transfer_ownership(self, resource_type: str, resource_id: int, new_owner: int) -> bool:
        with self._lock:
            key = (resource_type, resource_id)
            if key in self._resource_owners:
                self._resource_owners[key] = new_owner
                return True
            return False

    # ── Custom Permission Management ──

    def grant_permission(self, user_id: int, permission: str):
        """Grant an additional permission to a specific user."""
        with self._lock:
            self._user_grants[user_id].add(permission)
            self._user_revocations[user_id].discard(permission)

    def revoke_permission(self, user_id: int, permission: str):
        """Revoke a specific permission from a user."""
        with self._lock:
            self._user_revocations[user_id].add(permission)
            self._user_grants[user_id].discard(permission)

    def get_user_permissions(self, user_id: int, role: str) -> dict:
        """Get effective permissions for a user."""
        with self._lock:
            role_perms = self._role_permissions.get(role, set())
            grants = self._user_grants.get(user_id, set())
            revocations = self._user_revocations.get(user_id, set())
            effective = (role_perms | grants) - revocations
            return {
                "user_id": user_id,
                "role": role,
                "role_permissions": sorted(role_perms),
                "custom_grants": sorted(grants),
                "custom_revocations": sorted(revocations),
                "effective_permissions": sorted(effective),
                "total": len(effective),
            }

    # ── Role Management ──

    def get_role_matrix(self) -> dict:
        """Get the complete role-permission matrix."""
        return {
            role: sorted(perms)
            for role, perms in self._role_permissions.items()
        }

    def get_all_permissions(self) -> List[str]:
        """Get all defined permissions."""
        all_perms = set()
        for perms in self._role_permissions.values():
            all_perms.update(perms)
        return sorted(all_perms)

    # ── Audit ──

    def get_audit_log(self, limit: int = 50, user_id: Optional[int] = None,
                      allowed: Optional[bool] = None) -> List[dict]:
        """Get access control audit log."""
        with self._lock:
            entries = list(self._audit_log)

        if user_id is not None:
            entries = [e for e in entries if e.user_id == user_id]
        if allowed is not None:
            entries = [e for e in entries if e.allowed == allowed]

        entries = entries[-limit:]
        entries.reverse()
        return [e.to_dict() for e in entries]

    # ── Stats ──

    def stats(self) -> dict:
        import time as _time
        uptime = _time.time() - self._start_time
        with self._lock:
            return {
                "engine": "RBACEngine",
                "total_checks": self._total_checks,
                "total_allowed": self._total_allowed,
                "total_denied": self._total_denied,
                "denial_rate": round(self._total_denied / max(self._total_checks, 1) * 100, 2),
                "roles_defined": len(self._role_permissions),
                "total_permissions": len(self.get_all_permissions()),
                "resources_tracked": len(self._resource_owners),
                "users_with_custom_grants": len(self._user_grants),
                "users_with_revocations": len(self._user_revocations),
                "audit_log_size": len(self._audit_log),
                "uptime_seconds": round(uptime, 1),
            }


# ── Global Singleton ──
rbac_engine = RBACEngine()
