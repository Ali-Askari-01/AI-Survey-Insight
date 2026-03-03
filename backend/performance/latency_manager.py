"""
Latency & Timeout Management (§3-4)
═══════════════════════════════════════════════════════
Dual-tier timeout strategy:
  Soft timeout  → return cached / partial result, keep processing in background
  Hard timeout  → cancel request entirely, log failure

Per-endpoint latency budget tracking with percentile metrics.
"""

import time
import asyncio
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict
import statistics


# ─────────────────────────────────────────────────────
# Timeout Tiers
# ─────────────────────────────────────────────────────

class TimeoutTier(Enum):
    SOFT = "soft"
    HARD = "hard"


@dataclass
class TimeoutConfig:
    """Per-endpoint timeout configuration."""
    soft_timeout_ms: float = 8000       # 8s — return cached/partial
    hard_timeout_ms: float = 15000      # 15s — kill
    retry_on_soft: bool = True          # queue a background retry on soft timeout
    cache_fallback: bool = True         # serve cached data on soft timeout


# ─────────────────────────────────────────────────────
# Latency Record
# ─────────────────────────────────────────────────────

@dataclass
class LatencyRecord:
    endpoint: str
    latency_ms: float
    timestamp: float
    tier_hit: Optional[TimeoutTier] = None  # None = completed within budget
    success: bool = True


class LatencyManager:
    """
    Manages request latency budgets and dual-tier timeouts.
    
    Usage:
        with latency_manager.track("/api/insights/1"):
            result = compute_insights()
    
    Or async:
        async with latency_manager.track_async("/api/ai/sentiment"):
            result = await ai_call()
    """

    # Pre-configured endpoint timeout budgets
    DEFAULT_CONFIGS: Dict[str, TimeoutConfig] = {
        # Fast endpoints — tight budgets
        "/api/surveys":         TimeoutConfig(soft_timeout_ms=2000, hard_timeout_ms=5000),
        "/api/auth":            TimeoutConfig(soft_timeout_ms=1000, hard_timeout_ms=3000),
        "/health":              TimeoutConfig(soft_timeout_ms=500,  hard_timeout_ms=2000),

        # Moderate endpoints
        "/api/insights":        TimeoutConfig(soft_timeout_ms=5000, hard_timeout_ms=12000),
        "/api/reports":         TimeoutConfig(soft_timeout_ms=8000, hard_timeout_ms=15000),
        "/api/data":            TimeoutConfig(soft_timeout_ms=5000, hard_timeout_ms=12000),

        # AI endpoints — generous budgets (external API)
        "/api/ai":              TimeoutConfig(soft_timeout_ms=10000, hard_timeout_ms=20000),
        "/api/interview":       TimeoutConfig(soft_timeout_ms=12000, hard_timeout_ms=25000),
    }

    def __init__(self, max_history: int = 5000):
        self._configs: Dict[str, TimeoutConfig] = dict(self.DEFAULT_CONFIGS)
        self._history: List[LatencyRecord] = []
        self._max_history = max_history
        self._lock = threading.Lock()
        self._soft_timeout_count = 0
        self._hard_timeout_count = 0
        self._total_requests = 0
        self._cache_fallbacks = 0

    # ─────────────────────────────────────
    # Configuration
    # ─────────────────────────────────────

    def configure(self, endpoint_prefix: str, config: TimeoutConfig):
        """Set or override timeout config for an endpoint prefix."""
        self._configs[endpoint_prefix] = config

    def get_config(self, path: str) -> TimeoutConfig:
        """Resolve timeout config for a path using longest-prefix match."""
        best = TimeoutConfig()
        best_len = 0
        for prefix, cfg in self._configs.items():
            if path.startswith(prefix) and len(prefix) > best_len:
                best = cfg
                best_len = len(prefix)
        return best

    # ─────────────────────────────────────
    # Sync context manager
    # ─────────────────────────────────────

    def track(self, path: str):
        """Synchronous latency tracking context manager."""
        return _SyncTracker(self, path)

    # ─────────────────────────────────────
    # Async context manager
    # ─────────────────────────────────────

    def track_async(self, path: str):
        """Async latency tracking context manager."""
        return _AsyncTracker(self, path)

    # ─────────────────────────────────────
    # Execute with timeout
    # ─────────────────────────────────────

    async def execute_with_timeout(
        self,
        path: str,
        coro,
        fallback_value: Any = None,
        on_soft_timeout: Optional[Callable] = None,
    ) -> dict:
        """
        Execute a coroutine with dual-tier timeout management.
        
        Returns:
            {
                "result": <value>,
                "latency_ms": <float>,
                "timeout_tier": None | "soft" | "hard",
                "from_fallback": bool
            }
        """
        config = self.get_config(path)
        start = time.time()
        tier_hit = None
        from_fallback = False
        result = None

        try:
            # Try with soft timeout first
            soft_sec = config.soft_timeout_ms / 1000.0
            result = await asyncio.wait_for(coro, timeout=soft_sec)
        except asyncio.TimeoutError:
            tier_hit = TimeoutTier.SOFT
            self._soft_timeout_count += 1

            # Soft timeout: try fallback
            if config.cache_fallback and fallback_value is not None:
                result = fallback_value
                from_fallback = True
                self._cache_fallbacks += 1
            elif on_soft_timeout:
                result = on_soft_timeout()
                from_fallback = True
            else:
                # Escalate: wait until hard timeout
                remaining = (config.hard_timeout_ms / 1000.0) - (time.time() - start)
                if remaining > 0:
                    try:
                        result = await asyncio.wait_for(coro, timeout=remaining)
                        tier_hit = TimeoutTier.SOFT  # still counts as soft delay
                    except asyncio.TimeoutError:
                        tier_hit = TimeoutTier.HARD
                        self._hard_timeout_count += 1
                        result = fallback_value
                        from_fallback = fallback_value is not None
                else:
                    tier_hit = TimeoutTier.HARD
                    self._hard_timeout_count += 1
        except Exception:
            tier_hit = None
            raise

        latency_ms = (time.time() - start) * 1000
        self._record(path, latency_ms, tier_hit, tier_hit != TimeoutTier.HARD)

        return {
            "result": result,
            "latency_ms": round(latency_ms, 2),
            "timeout_tier": tier_hit.value if tier_hit else None,
            "from_fallback": from_fallback,
        }

    # ─────────────────────────────────────
    # Recording
    # ─────────────────────────────────────

    def _record(self, path: str, latency_ms: float,
                tier_hit: Optional[TimeoutTier], success: bool):
        """Record a latency observation."""
        record = LatencyRecord(
            endpoint=path, latency_ms=latency_ms,
            timestamp=time.time(), tier_hit=tier_hit, success=success,
        )
        with self._lock:
            self._total_requests += 1
            self._history.append(record)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    # ─────────────────────────────────────
    # Percentile Analytics
    # ─────────────────────────────────────

    def get_percentiles(self, path_prefix: str = "",
                        window_seconds: float = 300) -> dict:
        """Get p50, p90, p95, p99 latencies for an endpoint prefix."""
        cutoff = time.time() - window_seconds
        with self._lock:
            vals = [
                r.latency_ms for r in self._history
                if r.timestamp >= cutoff
                and r.endpoint.startswith(path_prefix)
                and r.success
            ]

        if not vals:
            return {"p50": 0, "p90": 0, "p95": 0, "p99": 0, "count": 0}

        vals.sort()
        n = len(vals)
        return {
            "p50":   round(vals[int(n * 0.50)], 2),
            "p90":   round(vals[int(n * 0.90)] if n > 1 else vals[0], 2),
            "p95":   round(vals[int(min(n * 0.95, n - 1))], 2),
            "p99":   round(vals[int(min(n * 0.99, n - 1))], 2),
            "mean":  round(statistics.mean(vals), 2),
            "count": n,
        }

    def get_endpoint_breakdown(self, window_seconds: float = 300) -> dict:
        """Get latency breakdown per endpoint prefix."""
        cutoff = time.time() - window_seconds
        groups: Dict[str, List[float]] = defaultdict(list)

        with self._lock:
            for r in self._history:
                if r.timestamp >= cutoff and r.success:
                    # Group by first two path segments
                    parts = r.endpoint.strip("/").split("/")
                    prefix = "/" + "/".join(parts[:2]) if len(parts) >= 2 else r.endpoint
                    groups[prefix].append(r.latency_ms)

        result = {}
        for prefix, vals in groups.items():
            vals.sort()
            n = len(vals)
            result[prefix] = {
                "count": n,
                "mean": round(statistics.mean(vals), 2),
                "p50": round(vals[int(n * 0.50)], 2),
                "p95": round(vals[int(min(n * 0.95, n - 1))], 2),
                "max": round(max(vals), 2),
            }
        return result

    def get_timeout_stats(self) -> dict:
        """Get timeout statistics."""
        return {
            "total_requests": self._total_requests,
            "soft_timeouts": self._soft_timeout_count,
            "hard_timeouts": self._hard_timeout_count,
            "cache_fallbacks": self._cache_fallbacks,
            "soft_timeout_rate": round(
                self._soft_timeout_count / max(self._total_requests, 1) * 100, 2
            ),
            "hard_timeout_rate": round(
                self._hard_timeout_count / max(self._total_requests, 1) * 100, 2
            ),
        }

    # ─────────────────────────────────────
    # Stats
    # ─────────────────────────────────────

    def stats(self) -> dict:
        return {
            "engine": "LatencyManager",
            "configured_endpoints": len(self._configs),
            "history_size": len(self._history),
            "timeouts": self.get_timeout_stats(),
            "overall_percentiles": self.get_percentiles("", 300),
        }


# ─────────────────────────────────────────────────────
# Context Managers
# ─────────────────────────────────────────────────────

class _SyncTracker:
    def __init__(self, mgr: LatencyManager, path: str):
        self._mgr = mgr
        self._path = path
        self._start = 0.0

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        latency_ms = (time.time() - self._start) * 1000
        config = self._mgr.get_config(self._path)
        tier = None
        if latency_ms > config.hard_timeout_ms:
            tier = TimeoutTier.HARD
            self._mgr._hard_timeout_count += 1
        elif latency_ms > config.soft_timeout_ms:
            tier = TimeoutTier.SOFT
            self._mgr._soft_timeout_count += 1
        self._mgr._record(self._path, latency_ms, tier, exc_type is None)
        return False


class _AsyncTracker:
    def __init__(self, mgr: LatencyManager, path: str):
        self._mgr = mgr
        self._path = path
        self._start = 0.0

    async def __aenter__(self):
        self._start = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        latency_ms = (time.time() - self._start) * 1000
        config = self._mgr.get_config(self._path)
        tier = None
        if latency_ms > config.hard_timeout_ms:
            tier = TimeoutTier.HARD
            self._mgr._hard_timeout_count += 1
        elif latency_ms > config.soft_timeout_ms:
            tier = TimeoutTier.SOFT
            self._mgr._soft_timeout_count += 1
        self._mgr._record(self._path, latency_ms, tier, exc_type is None)
        return False


# ─────────────────────────────────────────────────────
# Global singleton
# ─────────────────────────────────────────────────────
latency_manager = LatencyManager()
