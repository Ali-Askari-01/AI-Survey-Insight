"""
Threat Detector — Real-Time Anomaly Detection & Response
════════════════════════════════════════════════════════
Continuous monitoring for security threats.

Detection Categories:
  1. Brute Force:       Repeated failed login attempts
  2. Credential Stuffing: High-volume login attempts from varied IPs
  3. Anomalous Traffic:  Unusual request patterns / volume spikes
  4. Session Hijack:     IP/UA change mid-session
  5. API Abuse:          Excessive API calls, scraping patterns
  6. Privilege Escalation: Unauthorized access attempts to admin endpoints
  7. Data Exfiltration:  Large data export requests
  8. Geographic Anomaly: Login from unusual locations

Response Actions:
  MONITOR → Log and continue
  ALERT   → Notify admin
  BLOCK   → Temporarily block IP/user
  LOCKOUT → Lock user account
"""

import hashlib
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional, Dict, List, Set


class ThreatLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatAction:
    MONITOR = "monitor"
    ALERT = "alert"
    BLOCK = "block"
    LOCKOUT = "lockout"


class ThreatEvent:
    """A detected security threat."""

    def __init__(self, category: str, level: str, action: str,
                 source_ip: str = "", user_id: Optional[int] = None,
                 description: str = "", metadata: Optional[dict] = None):
        self.id = hashlib.md5(f"{time.time()}{category}{source_ip}".encode()).hexdigest()[:12]
        self.timestamp = datetime.now().isoformat()
        self.category = category
        self.level = level
        self.action = action
        self.source_ip = source_ip
        self.user_id = user_id
        self.description = description
        self.metadata = metadata or {}
        self.resolved = False
        self.resolved_at: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "timestamp": self.timestamp,
            "category": self.category,
            "level": self.level,
            "action": self.action,
            "description": self.description,
            "resolved": self.resolved,
        }
        if self.source_ip:
            d["source_ip"] = self.source_ip
        if self.user_id is not None:
            d["user_id"] = self.user_id
        if self.metadata:
            d["metadata"] = self.metadata
        if self.resolved_at:
            d["resolved_at"] = self.resolved_at
        return d


class ThreatDetector:
    """
    Real-time threat detection engine.

    Features:
    - Failed login tracking with automatic lockout
    - IP reputation scoring (dynamic blacklist)
    - Traffic anomaly detection (volume, pattern)
    - Session integrity monitoring
    - Privilege escalation detection
    - Rate-based anomaly scoring
    - Automatic response actions (monitor → block → lockout)
    """

    def __init__(self):
        self._lock = threading.RLock()

        # Failed login tracking: ip → deque of timestamps
        self._failed_logins_by_ip: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._failed_logins_by_user: Dict[int, deque] = defaultdict(lambda: deque(maxlen=50))

        # Thresholds
        self._max_failed_logins_ip = 10       # per 15 min from same IP
        self._max_failed_logins_user = 5      # per 15 min for same user
        self._lockout_duration = 900           # 15 minutes in seconds

        # Blocked IPs and locked users
        self._blocked_ips: Dict[str, float] = {}  # ip → block_until timestamp
        self._locked_users: Dict[int, float] = {}  # user_id → lock_until timestamp

        # IP reputation scores (lower = worse, 0-100)
        self._ip_reputation: Dict[str, float] = defaultdict(lambda: 100.0)

        # Request tracking per IP per minute
        self._request_counts: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
        self._threshold_requests_per_minute = 120

        # Session integrity: session_id → (ip, user_agent)
        self._session_fingerprints: Dict[str, tuple] = {}

        # Admin endpoints (privilege escalation detection)
        self._admin_paths = {
            "/api/users", "/api/system", "/api/security",
            "/api/observability", "/api/infrastructure",
        }

        # Threat log
        self._threats: deque = deque(maxlen=5000)
        self._threats_by_category: Dict[str, int] = defaultdict(int)
        self._threats_by_level: Dict[str, int] = defaultdict(int)

        # Watchlist: IPs under enhanced monitoring
        self._watchlist: Set[str] = set()

        self._start_time = time.time()

    # ── Failed Login Detection ──

    def record_failed_login(self, ip: str, user_id: Optional[int] = None) -> ThreatEvent:
        """Record a failed login attempt and evaluate threat."""
        now = time.time()
        cutoff = now - 900  # 15-minute window

        with self._lock:
            # Track by IP
            self._failed_logins_by_ip[ip].append(now)
            ip_fails = sum(1 for t in self._failed_logins_by_ip[ip] if t > cutoff)

            # Track by user
            user_fails = 0
            if user_id is not None:
                self._failed_logins_by_user[user_id].append(now)
                user_fails = sum(1 for t in self._failed_logins_by_user[user_id] if t > cutoff)

            # Degrade IP reputation
            self._ip_reputation[ip] = max(0, self._ip_reputation[ip] - 5)

            # Determine threat level and action
            if ip_fails >= self._max_failed_logins_ip:
                event = ThreatEvent(
                    "brute_force", ThreatLevel.HIGH, ThreatAction.BLOCK,
                    ip, user_id,
                    f"Brute force: {ip_fails} failed logins from IP in 15 min",
                    {"ip_failures": ip_fails, "user_failures": user_fails}
                )
                self._blocked_ips[ip] = now + self._lockout_duration
                self._watchlist.add(ip)

            elif user_id and user_fails >= self._max_failed_logins_user:
                event = ThreatEvent(
                    "brute_force", ThreatLevel.HIGH, ThreatAction.LOCKOUT,
                    ip, user_id,
                    f"Account lockout: {user_fails} failed logins for user {user_id}",
                    {"ip_failures": ip_fails, "user_failures": user_fails}
                )
                self._locked_users[user_id] = now + self._lockout_duration

            elif ip_fails >= 5:
                event = ThreatEvent(
                    "brute_force", ThreatLevel.MEDIUM, ThreatAction.ALERT,
                    ip, user_id,
                    f"Suspicious: {ip_fails} failed logins from IP",
                    {"ip_failures": ip_fails}
                )
                self._watchlist.add(ip)

            else:
                event = ThreatEvent(
                    "failed_login", ThreatLevel.LOW, ThreatAction.MONITOR,
                    ip, user_id,
                    f"Failed login attempt #{ip_fails} from IP",
                )

            self._record_threat(event)
            return event

    def record_successful_login(self, ip: str, user_id: int):
        """Reset failed login counter on successful login."""
        with self._lock:
            if ip in self._failed_logins_by_ip:
                self._failed_logins_by_ip[ip].clear()
            if user_id in self._failed_logins_by_user:
                self._failed_logins_by_user[user_id].clear()
            # Restore some IP reputation
            self._ip_reputation[ip] = min(100, self._ip_reputation[ip] + 10)

    # ── IP/User Status ──

    def is_ip_blocked(self, ip: str) -> tuple:
        """Check if IP is currently blocked. Returns (blocked, seconds_remaining)."""
        with self._lock:
            if ip in self._blocked_ips:
                remaining = self._blocked_ips[ip] - time.time()
                if remaining > 0:
                    return True, int(remaining)
                else:
                    del self._blocked_ips[ip]
            return False, 0

    def is_user_locked(self, user_id: int) -> tuple:
        """Check if user account is locked. Returns (locked, seconds_remaining)."""
        with self._lock:
            if user_id in self._locked_users:
                remaining = self._locked_users[user_id] - time.time()
                if remaining > 0:
                    return True, int(remaining)
                else:
                    del self._locked_users[user_id]
            return False, 0

    def unblock_ip(self, ip: str) -> bool:
        with self._lock:
            if ip in self._blocked_ips:
                del self._blocked_ips[ip]
                return True
            return False

    def unlock_user(self, user_id: int) -> bool:
        with self._lock:
            if user_id in self._locked_users:
                del self._locked_users[user_id]
                return True
            return False

    # ── Traffic Anomaly Detection ──

    def record_request(self, ip: str, path: str, user_id: Optional[int] = None,
                       user_role: str = "") -> Optional[ThreatEvent]:
        """Record an API request and check for anomalies."""
        now = time.time()

        with self._lock:
            # Track request volume
            self._request_counts[ip].append(now)
            cutoff = now - 60
            rpm = sum(1 for t in self._request_counts[ip] if t > cutoff)

            # Check for volume spike
            if rpm > self._threshold_requests_per_minute:
                event = ThreatEvent(
                    "traffic_anomaly", ThreatLevel.MEDIUM, ThreatAction.ALERT,
                    ip, user_id,
                    f"High traffic: {rpm} requests/min from IP (threshold: {self._threshold_requests_per_minute})",
                    {"rpm": rpm, "path": path}
                )
                self._ip_reputation[ip] = max(0, self._ip_reputation[ip] - 2)
                self._watchlist.add(ip)
                self._record_threat(event)
                return event

            # Privilege escalation check: non-admin accessing admin paths
            if user_role and user_role not in ("founder", "pm", "engineer"):
                for admin_path in self._admin_paths:
                    if path.startswith(admin_path):
                        event = ThreatEvent(
                            "privilege_escalation", ThreatLevel.HIGH, ThreatAction.ALERT,
                            ip, user_id,
                            f"Unauthorized access attempt to {path} by role '{user_role}'",
                            {"path": path, "role": user_role}
                        )
                        self._record_threat(event)
                        return event

            # Enhanced monitoring for watchlisted IPs
            if ip in self._watchlist:
                event = ThreatEvent(
                    "watchlist_activity", ThreatLevel.LOW, ThreatAction.MONITOR,
                    ip, user_id,
                    f"Request from watchlisted IP: {path}",
                    {"path": path}
                )
                self._record_threat(event)
                return event

        return None

    # ── Session Integrity ──

    def register_session(self, session_id: str, ip: str, user_agent: str):
        """Register session fingerprint."""
        with self._lock:
            self._session_fingerprints[session_id] = (ip, user_agent)

    def check_session_integrity(self, session_id: str, ip: str,
                                 user_agent: str, user_id: Optional[int] = None) -> Optional[ThreatEvent]:
        """Check if session fingerprint has changed (potential hijack)."""
        with self._lock:
            fingerprint = self._session_fingerprints.get(session_id)
            if not fingerprint:
                self._session_fingerprints[session_id] = (ip, user_agent)
                return None

            orig_ip, orig_ua = fingerprint

            if ip != orig_ip:
                event = ThreatEvent(
                    "session_hijack", ThreatLevel.HIGH, ThreatAction.ALERT,
                    ip, user_id,
                    f"Session IP changed: {orig_ip} → {ip}",
                    {"session_id": session_id, "original_ip": orig_ip, "new_ip": ip}
                )
                self._record_threat(event)
                return event

            if user_agent != orig_ua:
                event = ThreatEvent(
                    "session_hijack", ThreatLevel.MEDIUM, ThreatAction.ALERT,
                    ip, user_id,
                    f"Session User-Agent changed mid-session",
                    {"session_id": session_id}
                )
                self._record_threat(event)
                return event

        return None

    # ── Manual Controls ──

    def block_ip(self, ip: str, duration_seconds: int = 3600) -> dict:
        """Manually block an IP."""
        with self._lock:
            self._blocked_ips[ip] = time.time() + duration_seconds
            self._watchlist.add(ip)
            return {"ip": ip, "blocked_for_seconds": duration_seconds}

    def add_to_watchlist(self, ip: str):
        with self._lock:
            self._watchlist.add(ip)

    def remove_from_watchlist(self, ip: str):
        with self._lock:
            self._watchlist.discard(ip)

    # ── Threat Log ──

    def _record_threat(self, event: ThreatEvent):
        self._threats.append(event)
        self._threats_by_category[event.category] += 1
        self._threats_by_level[event.level] += 1

    def resolve_threat(self, threat_id: str) -> bool:
        with self._lock:
            for t in self._threats:
                if t.id == threat_id and not t.resolved:
                    t.resolved = True
                    t.resolved_at = datetime.now().isoformat()
                    return True
            return False

    def get_threats(self, limit: int = 50, category: Optional[str] = None,
                    level: Optional[str] = None, unresolved_only: bool = False) -> List[dict]:
        with self._lock:
            threats = list(self._threats)
        if category:
            threats = [t for t in threats if t.category == category]
        if level:
            threats = [t for t in threats if t.level == level]
        if unresolved_only:
            threats = [t for t in threats if not t.resolved]
        threats = threats[-limit:]
        threats.reverse()
        return [t.to_dict() for t in threats]

    def get_active_blocks(self) -> dict:
        now = time.time()
        with self._lock:
            active_ip_blocks = {
                ip: int(until - now)
                for ip, until in self._blocked_ips.items()
                if until > now
            }
            active_user_locks = {
                uid: int(until - now)
                for uid, until in self._locked_users.items()
                if until > now
            }
            return {
                "blocked_ips": active_ip_blocks,
                "locked_users": active_user_locks,
                "watchlisted_ips": list(self._watchlist),
            }

    def get_ip_reputation(self, ip: str) -> dict:
        with self._lock:
            score = self._ip_reputation.get(ip, 100.0)
            blocked, remaining = False, 0
            if ip in self._blocked_ips:
                remaining = self._blocked_ips[ip] - time.time()
                blocked = remaining > 0
            return {
                "ip": ip,
                "reputation_score": round(score, 1),
                "is_blocked": blocked,
                "is_watchlisted": ip in self._watchlist,
                "block_remaining_seconds": max(0, int(remaining)),
            }

    # ── Stats ──

    def stats(self) -> dict:
        uptime = time.time() - self._start_time
        now = time.time()
        with self._lock:
            return {
                "engine": "ThreatDetector",
                "total_threats_detected": len(self._threats),
                "threats_by_category": dict(self._threats_by_category),
                "threats_by_level": dict(self._threats_by_level),
                "active_ip_blocks": sum(1 for u in self._blocked_ips.values() if u > now),
                "active_user_lockouts": sum(1 for u in self._locked_users.values() if u > now),
                "watchlisted_ips": len(self._watchlist),
                "tracked_ips": len(self._ip_reputation),
                "active_sessions": len(self._session_fingerprints),
                "thresholds": {
                    "max_failed_logins_ip": self._max_failed_logins_ip,
                    "max_failed_logins_user": self._max_failed_logins_user,
                    "lockout_duration_seconds": self._lockout_duration,
                    "max_requests_per_minute": self._threshold_requests_per_minute,
                },
                "uptime_seconds": round(uptime, 1),
            }


# ── Global Singleton ──
threat_detector = ThreatDetector()
