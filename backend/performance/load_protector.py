"""
Load Protection (§9)
═══════════════════════════════════════════════════════
Protects the system from traffic spikes and sudden load surges.

Capabilities:
  - Adaptive backpressure at the API layer
  - Queue-depth–based request acceptance
  - Dynamic rate limiting based on system load
  - Traffic spike detection
  - Load shedding policies (priority-based)
"""

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from collections import deque


class LoadLevel(Enum):
    NORMAL    = "normal"     # System healthy, accept all
    ELEVATED  = "elevated"   # Slight pressure, warn
    HIGH      = "high"       # Reject low-priority, queue buffering
    CRITICAL  = "critical"   # Accept only critical requests
    OVERLOAD  = "overload"   # Emergency — reject everything except health


@dataclass
class LoadConfig:
    """Thresholds for load level transitions."""
    # Queue depth thresholds (percentage of max)
    elevated_queue_pct: float = 0.30     # 30% → elevated
    high_queue_pct: float = 0.60         # 60% → high
    critical_queue_pct: float = 0.80     # 80% → critical
    overload_queue_pct: float = 0.95     # 95% → overload

    # Request rate thresholds (requests per second)
    elevated_rps: float = 50.0
    high_rps: float = 100.0
    critical_rps: float = 200.0

    # Error rate thresholds
    elevated_error_rate: float = 0.05    # 5%
    high_error_rate: float = 0.10        # 10%
    critical_error_rate: float = 0.20    # 20%

    # Queue max size
    max_queue_size: int = 10000

    # Spike detection
    spike_window_s: float = 10.0         # Window for spike detection
    spike_multiplier: float = 3.0        # 3x normal = spike


@dataclass
class LoadSnapshot:
    """Point-in-time load measurement."""
    timestamp: float
    level: LoadLevel
    queue_depth: int
    queue_pct: float
    rps: float
    error_rate: float
    accepted: int
    rejected: int
    shed: int


class LoadProtector:
    """
    Adaptive load protection layer.
    
    Monitors system load and makes accept/reject decisions for incoming
    requests based on priority, queue depth, and error rate.
    
    Usage:
        allowed, reason = load_protector.should_accept(priority="normal", path="/api/surveys")
        if not allowed:
            return JSONResponse(status_code=503, content={"message": reason})
    """

    # Request priority levels (lower = higher priority)
    PRIORITY_MAP = {
        "critical": 0,   # Health checks, recovery endpoints
        "high": 1,        # Survey submissions, auth
        "normal": 2,      # Dashboard loads, insights
        "low": 3,         # Reports, exports, batch ops
        "background": 4,  # Analytics, temporal snapshots
    }

    # Path → priority mapping
    PATH_PRIORITIES = {
        "/health": "critical",
        "/api/auth": "high",
        "/api/surveys": "high",
        "/api/interview": "high",
        "/api/insights": "normal",
        "/api/data": "normal",
        "/api/reports": "low",
        "/api/ai": "normal",
        "/api/performance": "low",
        "/api/infrastructure": "low",
        "/api/metrics": "low",
        "/api/notifications": "low",
    }

    def __init__(self, config: Optional[LoadConfig] = None):
        self._config = config or LoadConfig()
        self._lock = threading.Lock()
        self._current_level = LoadLevel.NORMAL

        # Request tracking (sliding window)
        self._request_times: deque = deque(maxlen=10000)
        self._error_times: deque = deque(maxlen=5000)
        self._window_s = 60.0  # 1-minute measurement window

        # Counters
        self._total_accepted = 0
        self._total_rejected = 0
        self._total_shed = 0

        # Spike detection
        self._rps_history: deque = deque(maxlen=100)  # RPS over time

        # Snapshots for trend analysis
        self._snapshots: List[LoadSnapshot] = []
        self._max_snapshots = 500

    # ─────────────────────────────────────
    # Request Decision
    # ─────────────────────────────────────

    def should_accept(self, priority: str = "normal",
                       path: str = "") -> Tuple[bool, str]:
        """
        Decide whether to accept an incoming request.
        
        Returns:
            (allowed: bool, reason: str)
        """
        now = time.time()
        self._request_times.append(now)

        # Resolve priority from path if not explicit
        if path and priority == "normal":
            for prefix, prio in self.PATH_PRIORITIES.items():
                if path.startswith(prefix):
                    priority = prio
                    break

        # Always accept critical
        if priority == "critical":
            self._total_accepted += 1
            return True, "accepted"

        # Evaluate current load level
        level = self._evaluate_level()

        # Decision based on level + priority
        prio_rank = self.PRIORITY_MAP.get(priority, 2)

        if level == LoadLevel.NORMAL:
            self._total_accepted += 1
            return True, "accepted"

        if level == LoadLevel.ELEVATED:
            # Accept everything but track
            self._total_accepted += 1
            return True, "accepted_elevated"

        if level == LoadLevel.HIGH:
            # Reject low priority and background
            if prio_rank >= 3:
                self._total_shed += 1
                return False, f"Load HIGH — low-priority requests shed (queue at {self._get_queue_pct():.0%})"
            self._total_accepted += 1
            return True, "accepted_high"

        if level == LoadLevel.CRITICAL:
            # Only high and critical
            if prio_rank >= 2:
                self._total_shed += 1
                return False, f"Load CRITICAL — only high-priority requests accepted"
            self._total_accepted += 1
            return True, "accepted_critical"

        if level == LoadLevel.OVERLOAD:
            # Only critical (health checks)
            self._total_rejected += 1
            return False, "System overloaded — please retry in a few moments"

        self._total_accepted += 1
        return True, "accepted"

    def record_error(self):
        """Record a request error for error rate tracking."""
        self._error_times.append(time.time())

    def record_success(self):
        """Record a successful request."""
        pass  # Request already tracked in should_accept

    # ─────────────────────────────────────
    # Load Level Evaluation
    # ─────────────────────────────────────

    def _evaluate_level(self) -> LoadLevel:
        """Evaluate current load level from all signals."""
        queue_pct = self._get_queue_pct()
        rps = self._get_rps()
        error_rate = self._get_error_rate()
        cfg = self._config

        level = LoadLevel.NORMAL

        # Queue depth signal
        if queue_pct >= cfg.overload_queue_pct:
            level = max(level, LoadLevel.OVERLOAD, key=lambda l: list(LoadLevel).index(l))
        elif queue_pct >= cfg.critical_queue_pct:
            level = max(level, LoadLevel.CRITICAL, key=lambda l: list(LoadLevel).index(l))
        elif queue_pct >= cfg.high_queue_pct:
            level = max(level, LoadLevel.HIGH, key=lambda l: list(LoadLevel).index(l))
        elif queue_pct >= cfg.elevated_queue_pct:
            level = max(level, LoadLevel.ELEVATED, key=lambda l: list(LoadLevel).index(l))

        # RPS signal
        if rps >= cfg.critical_rps:
            level = max(level, LoadLevel.CRITICAL, key=lambda l: list(LoadLevel).index(l))
        elif rps >= cfg.high_rps:
            level = max(level, LoadLevel.HIGH, key=lambda l: list(LoadLevel).index(l))
        elif rps >= cfg.elevated_rps:
            level = max(level, LoadLevel.ELEVATED, key=lambda l: list(LoadLevel).index(l))

        # Error rate signal
        if error_rate >= cfg.critical_error_rate:
            level = max(level, LoadLevel.CRITICAL, key=lambda l: list(LoadLevel).index(l))
        elif error_rate >= cfg.high_error_rate:
            level = max(level, LoadLevel.HIGH, key=lambda l: list(LoadLevel).index(l))
        elif error_rate >= cfg.elevated_error_rate:
            level = max(level, LoadLevel.ELEVATED, key=lambda l: list(LoadLevel).index(l))

        # Spike detection
        if self._detect_spike():
            if level.value == "normal":
                level = LoadLevel.ELEVATED

        self._current_level = level
        return level

    def _get_queue_pct(self) -> float:
        """Get current queue depth as percentage of max."""
        try:
            from ..infrastructure.task_queue import task_queue
            depth = task_queue.queue_depth()
            return depth / max(self._config.max_queue_size, 1)
        except Exception:
            return 0.0

    def _get_rps(self) -> float:
        """Get requests per second over the last window."""
        now = time.time()
        cutoff = now - self._window_s
        count = sum(1 for t in self._request_times if t >= cutoff)
        rps = count / self._window_s
        self._rps_history.append((now, rps))
        return rps

    def _get_error_rate(self) -> float:
        """Get error rate over the last window."""
        now = time.time()
        cutoff = now - self._window_s
        total = sum(1 for t in self._request_times if t >= cutoff)
        errors = sum(1 for t in self._error_times if t >= cutoff)
        return errors / max(total, 1)

    def _detect_spike(self) -> bool:
        """Detect traffic spike (sudden increase in RPS)."""
        if len(self._rps_history) < 10:
            return False

        recent = [rps for _, rps in list(self._rps_history)[-5:]]
        historical = [rps for _, rps in list(self._rps_history)[-20:-5]]

        if not historical:
            return False

        avg_recent = sum(recent) / len(recent)
        avg_historical = sum(historical) / len(historical)

        if avg_historical == 0:
            return avg_recent > 10  # More than 10 rps from zero

        return avg_recent > avg_historical * self._config.spike_multiplier

    # ─────────────────────────────────────
    # Snapshot
    # ─────────────────────────────────────

    def take_snapshot(self) -> LoadSnapshot:
        """Take a point-in-time load snapshot."""
        snap = LoadSnapshot(
            timestamp=time.time(),
            level=self._current_level,
            queue_depth=int(self._get_queue_pct() * self._config.max_queue_size),
            queue_pct=self._get_queue_pct(),
            rps=self._get_rps(),
            error_rate=self._get_error_rate(),
            accepted=self._total_accepted,
            rejected=self._total_rejected,
            shed=self._total_shed,
        )
        self._snapshots.append(snap)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]
        return snap

    def get_trend(self, limit: int = 50) -> List[dict]:
        """Get load trend from snapshots."""
        return [
            {
                "timestamp": s.timestamp,
                "level": s.level.value,
                "queue_pct": round(s.queue_pct, 4),
                "rps": round(s.rps, 2),
                "error_rate": round(s.error_rate, 4),
            }
            for s in self._snapshots[-limit:]
        ]

    # ─────────────────────────────────────
    # Stats
    # ─────────────────────────────────────

    def stats(self) -> dict:
        return {
            "engine": "LoadProtector",
            "current_level": self._current_level.value,
            "rps": round(self._get_rps(), 2),
            "error_rate": round(self._get_error_rate(), 4),
            "queue_pct": round(self._get_queue_pct(), 4),
            "total_accepted": self._total_accepted,
            "total_rejected": self._total_rejected,
            "total_shed": self._total_shed,
            "shed_rate": round(
                self._total_shed / max(self._total_accepted + self._total_rejected + self._total_shed, 1) * 100, 2
            ),
            "spike_detected": self._detect_spike(),
            "snapshot_count": len(self._snapshots),
        }


# ─────────────────────────────────────────────────────
# Global singleton
# ─────────────────────────────────────────────────────
load_protector = LoadProtector()
