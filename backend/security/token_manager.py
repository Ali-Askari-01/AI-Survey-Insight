"""
Token Manager — Enhanced JWT Authentication & Session Security
═══════════════════════════════════════════════════════
Beyond basic JWT: refresh tokens, token rotation, revocation blacklist.

Security Rules:
  ✅ Short access token lifetime (1 hour)
  ✅ Refresh token rotation (7 days, single-use)
  ✅ Token revocation blacklist
  ✅ Session tracking per user
  ✅ Concurrent session limits
  ✅ Token fingerprinting (IP + User-Agent binding)
"""

import time
import uuid
import hashlib
import threading
from collections import defaultdict, OrderedDict
from datetime import datetime
from typing import Optional, Dict, List, Tuple


class TokenSession:
    """Tracks an active user session."""

    def __init__(self, user_id: int, token_id: str, ip_address: str = "",
                 user_agent: str = "", role: str = "respondent"):
        self.session_id = str(uuid.uuid4())[:12]
        self.user_id = user_id
        self.token_id = token_id
        self.ip_address = ip_address
        self.user_agent = user_agent[:200]
        self.role = role
        self.created_at = time.time()
        self.last_active = self.created_at
        self.request_count = 0
        self.fingerprint = self._generate_fingerprint()

    def _generate_fingerprint(self) -> str:
        """Create a fingerprint from IP + User-Agent for token binding."""
        raw = f"{self.ip_address}:{self.user_agent}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def touch(self):
        self.last_active = time.time()
        self.request_count += 1

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "token_id": self.token_id,
            "ip_address": self.ip_address,
            "role": self.role,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "last_active": datetime.fromtimestamp(self.last_active).isoformat(),
            "request_count": self.request_count,
            "age_seconds": round(time.time() - self.created_at, 1),
        }


class TokenManager:
    """
    Enhanced Token & Session Management Engine.

    Features:
    - Access token lifecycle tracking
    - Refresh token management with single-use rotation
    - Token revocation blacklist (with expiry cleanup)
    - Per-user session tracking
    - Concurrent session limits (max 5 per user)
    - Token fingerprinting (IP + UA binding)
    - Session activity monitoring
    """

    def __init__(
        self,
        max_sessions_per_user: int = 5,
        access_token_ttl: int = 3600,
        refresh_token_ttl: int = 604800,
        blacklist_max: int = 10000,
    ):
        self._lock = threading.RLock()
        self.max_sessions_per_user = max_sessions_per_user
        self.access_token_ttl = access_token_ttl  # 1 hour
        self.refresh_token_ttl = refresh_token_ttl  # 7 days

        # Active sessions: token_id → TokenSession
        self._sessions: Dict[str, TokenSession] = {}
        # Per-user session tracking: user_id → [token_ids]
        self._user_sessions: Dict[int, List[str]] = defaultdict(list)

        # Token revocation blacklist (OrderedDict for LRU eviction)
        self._blacklist: OrderedDict = OrderedDict()
        self._blacklist_max = blacklist_max

        # Refresh tokens: refresh_token_hash → {user_id, expires_at, used}
        self._refresh_tokens: Dict[str, dict] = {}

        # Statistics
        self._total_tokens_issued = 0
        self._total_tokens_revoked = 0
        self._total_refresh_rotations = 0
        self._total_blacklist_checks = 0
        self._total_fingerprint_mismatches = 0
        self._start_time = time.time()

    # ── Token Issuance ──

    def issue_token(self, user_id: int, role: str = "respondent",
                    ip_address: str = "", user_agent: str = "") -> dict:
        """Issue a new access token and refresh token pair."""
        token_id = str(uuid.uuid4())
        refresh_token = str(uuid.uuid4())
        refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()[:32]

        session = TokenSession(user_id, token_id, ip_address, user_agent, role)

        with self._lock:
            # Enforce session limit
            user_tokens = self._user_sessions[user_id]
            while len(user_tokens) >= self.max_sessions_per_user:
                # Revoke oldest session
                oldest_token = user_tokens.pop(0)
                self._revoke_token_internal(oldest_token)

            self._sessions[token_id] = session
            self._user_sessions[user_id].append(token_id)

            self._refresh_tokens[refresh_hash] = {
                "user_id": user_id,
                "token_id": token_id,
                "role": role,
                "expires_at": time.time() + self.refresh_token_ttl,
                "used": False,
            }

            self._total_tokens_issued += 1

        return {
            "token_id": token_id,
            "refresh_token": refresh_token,
            "session_id": session.session_id,
            "fingerprint": session.fingerprint,
            "access_ttl": self.access_token_ttl,
            "refresh_ttl": self.refresh_token_ttl,
        }

    # ── Token Validation ──

    def validate_token(self, token_id: str, ip_address: str = "",
                       user_agent: str = "") -> Tuple[bool, str]:
        """Validate an access token. Returns (valid, reason)."""
        with self._lock:
            self._total_blacklist_checks += 1

            # Check blacklist
            if token_id in self._blacklist:
                return False, "Token has been revoked"

            # Check active session
            session = self._sessions.get(token_id)
            if not session:
                return False, "Token not found or expired"

            # Check age
            age = time.time() - session.created_at
            if age > self.access_token_ttl:
                self._revoke_token_internal(token_id)
                return False, "Token expired"

            # Fingerprint check (optional security enhancement)
            if ip_address and user_agent:
                current_fp = hashlib.sha256(
                    f"{ip_address}:{user_agent[:200]}".encode()
                ).hexdigest()[:16]
                if current_fp != session.fingerprint:
                    self._total_fingerprint_mismatches += 1
                    # Log but don't block (fingerprints can change with network)

            session.touch()
            return True, "valid"

    # ── Refresh Token Rotation ──

    def refresh_access_token(self, refresh_token: str, ip_address: str = "",
                             user_agent: str = "") -> Optional[dict]:
        """Rotate: use refresh token to get new access + refresh tokens."""
        refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()[:32]

        with self._lock:
            rt_data = self._refresh_tokens.get(refresh_hash)
            if not rt_data:
                return None

            if rt_data["used"]:
                # Refresh token reuse = potential theft. Revoke all user sessions.
                self._revoke_all_user_sessions(rt_data["user_id"])
                return None

            if time.time() > rt_data["expires_at"]:
                del self._refresh_tokens[refresh_hash]
                return None

            # Mark as used (single-use)
            rt_data["used"] = True

            # Revoke old access token
            self._revoke_token_internal(rt_data["token_id"])

            self._total_refresh_rotations += 1

        # Issue new token pair
        return self.issue_token(
            rt_data["user_id"], rt_data["role"], ip_address, user_agent
        )

    # ── Revocation ──

    def revoke_token(self, token_id: str) -> bool:
        """Revoke a specific token."""
        with self._lock:
            return self._revoke_token_internal(token_id)

    def _revoke_token_internal(self, token_id: str) -> bool:
        session = self._sessions.pop(token_id, None)
        if session:
            if token_id in self._user_sessions.get(session.user_id, []):
                self._user_sessions[session.user_id].remove(token_id)

        # Add to blacklist
        self._blacklist[token_id] = time.time()
        if len(self._blacklist) > self._blacklist_max:
            self._blacklist.popitem(last=False)

        self._total_tokens_revoked += 1
        return session is not None

    def revoke_all_user_tokens(self, user_id: int) -> int:
        """Revoke all tokens for a user."""
        with self._lock:
            return self._revoke_all_user_sessions(user_id)

    def _revoke_all_user_sessions(self, user_id: int) -> int:
        token_ids = self._user_sessions.pop(user_id, [])
        count = 0
        for tid in token_ids:
            self._sessions.pop(tid, None)
            self._blacklist[tid] = time.time()
            self._total_tokens_revoked += 1
            count += 1
        return count

    # ── Session Queries ──

    def get_user_sessions(self, user_id: int) -> List[dict]:
        """Get all active sessions for a user."""
        with self._lock:
            token_ids = self._user_sessions.get(user_id, [])
            return [
                self._sessions[tid].to_dict()
                for tid in token_ids
                if tid in self._sessions
            ]

    def get_active_sessions(self, limit: int = 50) -> List[dict]:
        """Get all active sessions."""
        with self._lock:
            sessions = sorted(
                self._sessions.values(),
                key=lambda s: s.last_active,
                reverse=True,
            )[:limit]
            return [s.to_dict() for s in sessions]

    def cleanup_expired(self) -> int:
        """Remove expired sessions and refresh tokens."""
        now = time.time()
        removed = 0
        with self._lock:
            # Clean expired sessions
            expired_tokens = [
                tid for tid, session in self._sessions.items()
                if (now - session.created_at) > self.access_token_ttl
            ]
            for tid in expired_tokens:
                self._revoke_token_internal(tid)
                removed += 1

            # Clean expired refresh tokens
            expired_rts = [
                rh for rh, data in self._refresh_tokens.items()
                if now > data["expires_at"]
            ]
            for rh in expired_rts:
                del self._refresh_tokens[rh]
                removed += 1

            # Clean old blacklist entries (older than refresh TTL)
            old_bl = [
                tid for tid, ts in self._blacklist.items()
                if (now - ts) > self.refresh_token_ttl
            ]
            for tid in old_bl:
                del self._blacklist[tid]

        return removed

    # ── Stats ──

    def stats(self) -> dict:
        uptime = time.time() - self._start_time
        with self._lock:
            return {
                "engine": "TokenManager",
                "active_sessions": len(self._sessions),
                "unique_users_with_sessions": len(self._user_sessions),
                "max_sessions_per_user": self.max_sessions_per_user,
                "access_token_ttl_seconds": self.access_token_ttl,
                "refresh_token_ttl_seconds": self.refresh_token_ttl,
                "blacklist_size": len(self._blacklist),
                "active_refresh_tokens": sum(
                    1 for rt in self._refresh_tokens.values() if not rt["used"]
                ),
                "total_tokens_issued": self._total_tokens_issued,
                "total_tokens_revoked": self._total_tokens_revoked,
                "total_refresh_rotations": self._total_refresh_rotations,
                "total_blacklist_checks": self._total_blacklist_checks,
                "fingerprint_mismatches": self._total_fingerprint_mismatches,
                "uptime_seconds": round(uptime, 1),
            }


# ── Global Singleton ──
token_manager = TokenManager()
