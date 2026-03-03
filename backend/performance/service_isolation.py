"""
Service Isolation / Bulkheading (§7)
═══════════════════════════════════════════════════════
Prevents one failing service from killing the entire platform.

Capabilities:
  - Per-service concurrency semaphores (max parallel calls)
  - Service health & dependency tracking
  - Failure containment boundaries
  - Independent retry systems per service
  - Service registry with isolation metrics
"""

import time
import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class ServiceStatus(Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
    ISOLATED  = "isolated"    # Failures contained, not propagating
    DOWN      = "down"


@dataclass
class ServiceConfig:
    """Configuration for an isolated service."""
    name: str
    max_concurrent: int = 10         # Maximum parallel executions
    timeout_seconds: float = 30.0    # Per-call timeout
    max_failures: int = 5            # Failures before isolation
    recovery_window_s: float = 60.0  # Time before attempting recovery
    critical: bool = False           # If True, degradation of this service triggers system alert
    dependencies: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ServiceMetrics:
    """Runtime metrics for a service."""
    total_calls: int = 0
    active_calls: int = 0
    successful: int = 0
    failed: int = 0
    rejected: int = 0          # Rejected due to semaphore full
    isolated_calls: int = 0    # Calls made while service isolated
    total_latency_ms: float = 0.0
    consecutive_failures: int = 0
    last_success: float = 0.0
    last_failure: float = 0.0
    last_error: str = ""


class _ServiceSemaphore:
    """Per-service concurrency limiter with timeout."""

    def __init__(self, max_concurrent: int):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._sync_semaphore = threading.Semaphore(max_concurrent)
        self._max = max_concurrent
        self._active = 0
        self._lock = threading.Lock()

    @property
    def active(self) -> int:
        return self._active

    @property
    def available(self) -> int:
        return max(0, self._max - self._active)

    async def acquire(self, timeout: float = 5.0) -> bool:
        """Try to acquire with timeout. Returns False if semaphore full."""
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout)
            with self._lock:
                self._active += 1
            return True
        except asyncio.TimeoutError:
            return False

    def release(self):
        with self._lock:
            self._active = max(0, self._active - 1)
        self._semaphore.release()

    def acquire_sync(self, timeout: float = 5.0) -> bool:
        result = self._sync_semaphore.acquire(timeout=timeout)
        if result:
            with self._lock:
                self._active += 1
        return result

    def release_sync(self):
        with self._lock:
            self._active = max(0, self._active - 1)
        self._sync_semaphore.release()


class ServiceIsolation:
    """
    Service isolation registry with bulkheading.
    
    Each registered service gets:
      - Its own concurrency semaphore
      - Independent failure tracking
      - Automatic isolation on repeated failures
      - Health status independent of other services
    
    Usage:
        result = await service_isolation.call("gemini_api", my_async_fn, arg1, arg2)
    """

    def __init__(self):
        self._services: Dict[str, ServiceConfig] = {}
        self._metrics: Dict[str, ServiceMetrics] = {}
        self._semaphores: Dict[str, _ServiceSemaphore] = {}
        self._statuses: Dict[str, ServiceStatus] = {}
        self._lock = threading.Lock()

        # Register default services
        self._register_defaults()

    def _register_defaults(self):
        """Register built-in service isolation boundaries."""
        defaults = [
            ServiceConfig(
                name="gemini_api", max_concurrent=5, timeout_seconds=20.0,
                max_failures=5, recovery_window_s=60.0, critical=True,
                description="Google Gemini AI API",
            ),
            ServiceConfig(
                name="assemblyai_api", max_concurrent=3, timeout_seconds=30.0,
                max_failures=3, recovery_window_s=120.0, critical=False,
                description="AssemblyAI Transcription API",
            ),
            ServiceConfig(
                name="database", max_concurrent=20, timeout_seconds=10.0,
                max_failures=3, recovery_window_s=30.0, critical=True,
                description="SQLite Database",
            ),
            ServiceConfig(
                name="survey_service", max_concurrent=15, timeout_seconds=5.0,
                max_failures=10, recovery_window_s=30.0, critical=True,
                dependencies=["database"],
                description="Survey CRUD operations",
            ),
            ServiceConfig(
                name="ai_engine", max_concurrent=5, timeout_seconds=25.0,
                max_failures=5, recovery_window_s=60.0, critical=True,
                dependencies=["gemini_api", "database"],
                description="AI Processing Engine",
            ),
            ServiceConfig(
                name="analytics_service", max_concurrent=10, timeout_seconds=15.0,
                max_failures=5, recovery_window_s=45.0, critical=False,
                dependencies=["database"],
                description="Analytics & Insights",
            ),
            ServiceConfig(
                name="voice_service", max_concurrent=3, timeout_seconds=30.0,
                max_failures=3, recovery_window_s=120.0, critical=False,
                dependencies=["assemblyai_api", "database"],
                description="Voice Transcription & Analysis",
            ),
            ServiceConfig(
                name="report_service", max_concurrent=5, timeout_seconds=20.0,
                max_failures=5, recovery_window_s=60.0, critical=False,
                dependencies=["database", "ai_engine"],
                description="Report Generation",
            ),
            ServiceConfig(
                name="notification_service", max_concurrent=10, timeout_seconds=5.0,
                max_failures=10, recovery_window_s=30.0, critical=False,
                description="WebSocket & Notification Delivery",
            ),
            ServiceConfig(
                name="data_pipeline", max_concurrent=5, timeout_seconds=15.0,
                max_failures=5, recovery_window_s=45.0, critical=False,
                dependencies=["database", "ai_engine"],
                description="5-Layer Data Pipeline",
            ),
        ]
        for cfg in defaults:
            self.register(cfg)

    # ─────────────────────────────────────
    # Registration
    # ─────────────────────────────────────

    def register(self, config: ServiceConfig):
        """Register a service with isolation boundary."""
        with self._lock:
            self._services[config.name] = config
            self._metrics[config.name] = ServiceMetrics()
            self._semaphores[config.name] = _ServiceSemaphore(config.max_concurrent)
            self._statuses[config.name] = ServiceStatus.HEALTHY

    # ─────────────────────────────────────
    # Call Through Isolation
    # ─────────────────────────────────────

    async def call(self, service_name: str, func: Callable,
                   *args, fallback: Any = None, **kwargs) -> dict:
        """
        Execute a function through service isolation.
        
        Returns:
            {
                "result": <value>,
                "service": str,
                "status": str,
                "latency_ms": float,
                "isolated": bool,
            }
        """
        if service_name not in self._services:
            return {"error": f"Unknown service: {service_name}", "result": fallback}

        config = self._services[service_name]
        metrics = self._metrics[service_name]
        sem = self._semaphores[service_name]
        status = self._statuses[service_name]

        # Check if service is isolated
        if status == ServiceStatus.DOWN:
            metrics.isolated_calls += 1
            # Check recovery window
            if time.time() - metrics.last_failure > config.recovery_window_s:
                self._statuses[service_name] = ServiceStatus.DEGRADED
            else:
                return {
                    "result": fallback,
                    "service": service_name,
                    "status": "down",
                    "latency_ms": 0,
                    "isolated": True,
                    "message": "Service is down, using fallback",
                }

        # Try to acquire semaphore
        acquired = await sem.acquire(timeout=2.0)
        if not acquired:
            metrics.rejected += 1
            return {
                "result": fallback,
                "service": service_name,
                "status": "rejected",
                "latency_ms": 0,
                "isolated": False,
                "message": f"Service '{service_name}' at capacity ({config.max_concurrent} concurrent)",
            }

        start = time.time()
        try:
            # Execute with timeout
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=config.timeout_seconds,
                )
            else:
                result = func(*args, **kwargs)

            latency_ms = (time.time() - start) * 1000
            self._on_success(service_name, latency_ms)

            return {
                "result": result,
                "service": service_name,
                "status": "success",
                "latency_ms": round(latency_ms, 2),
                "isolated": False,
            }

        except asyncio.TimeoutError:
            latency_ms = (time.time() - start) * 1000
            self._on_failure(service_name, latency_ms, "timeout")
            return {
                "result": fallback,
                "service": service_name,
                "status": "timeout",
                "latency_ms": round(latency_ms, 2),
                "isolated": False,
                "message": f"Service '{service_name}' timed out after {config.timeout_seconds}s",
            }

        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            self._on_failure(service_name, latency_ms, str(e))
            return {
                "result": fallback,
                "service": service_name,
                "status": "error",
                "latency_ms": round(latency_ms, 2),
                "isolated": False,
                "message": str(e),
            }

        finally:
            sem.release()

    def call_sync(self, service_name: str, func: Callable,
                  *args, fallback: Any = None, **kwargs) -> dict:
        """Synchronous version of call()."""
        if service_name not in self._services:
            return {"error": f"Unknown service: {service_name}", "result": fallback}

        config = self._services[service_name]
        metrics = self._metrics[service_name]
        sem = self._semaphores[service_name]
        status = self._statuses[service_name]

        if status == ServiceStatus.DOWN:
            metrics.isolated_calls += 1
            if time.time() - metrics.last_failure > config.recovery_window_s:
                self._statuses[service_name] = ServiceStatus.DEGRADED
            else:
                return {"result": fallback, "service": service_name, "status": "down",
                        "latency_ms": 0, "isolated": True}

        acquired = sem.acquire_sync(timeout=2.0)
        if not acquired:
            metrics.rejected += 1
            return {"result": fallback, "service": service_name, "status": "rejected",
                    "latency_ms": 0, "isolated": False}

        start = time.time()
        try:
            result = func(*args, **kwargs)
            latency_ms = (time.time() - start) * 1000
            self._on_success(service_name, latency_ms)
            return {"result": result, "service": service_name, "status": "success",
                    "latency_ms": round(latency_ms, 2), "isolated": False}
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            self._on_failure(service_name, latency_ms, str(e))
            return {"result": fallback, "service": service_name, "status": "error",
                    "latency_ms": round(latency_ms, 2), "isolated": False, "message": str(e)}
        finally:
            sem.release_sync()

    # ─────────────────────────────────────
    # Success / Failure Tracking
    # ─────────────────────────────────────

    def _on_success(self, name: str, latency_ms: float):
        m = self._metrics[name]
        m.total_calls += 1
        m.successful += 1
        m.total_latency_ms += latency_ms
        m.consecutive_failures = 0
        m.last_success = time.time()
        # Recover from degraded
        if self._statuses[name] in (ServiceStatus.DEGRADED, ServiceStatus.ISOLATED):
            self._statuses[name] = ServiceStatus.HEALTHY

    def _on_failure(self, name: str, latency_ms: float, error: str):
        m = self._metrics[name]
        m.total_calls += 1
        m.failed += 1
        m.total_latency_ms += latency_ms
        m.consecutive_failures += 1
        m.last_failure = time.time()
        m.last_error = error

        cfg = self._services[name]
        if m.consecutive_failures >= cfg.max_failures:
            self._statuses[name] = ServiceStatus.DOWN

    # ─────────────────────────────────────
    # Status & Health
    # ─────────────────────────────────────

    def get_status(self, name: str) -> Optional[str]:
        return self._statuses.get(name, ServiceStatus.HEALTHY).value

    def get_all_statuses(self) -> Dict[str, str]:
        return {n: s.value for n, s in self._statuses.items()}

    def get_dependency_tree(self, name: str) -> dict:
        """Get dependency tree for a service."""
        if name not in self._services:
            return {"error": f"Unknown service: {name}"}

        cfg = self._services[name]
        deps = {}
        for dep_name in cfg.dependencies:
            deps[dep_name] = {
                "status": self._statuses.get(dep_name, ServiceStatus.HEALTHY).value,
                "dependencies": self.get_dependency_tree(dep_name).get("dependencies", {}),
            }
        return {
            "service": name,
            "status": self._statuses.get(name, ServiceStatus.HEALTHY).value,
            "dependencies": deps,
        }

    def get_service_metrics(self, name: str) -> dict:
        """Get detailed metrics for a service."""
        if name not in self._metrics:
            return {"error": f"Unknown service: {name}"}

        m = self._metrics[name]
        cfg = self._services[name]
        sem = self._semaphores[name]

        return {
            "service": name,
            "description": cfg.description,
            "status": self._statuses.get(name, ServiceStatus.HEALTHY).value,
            "max_concurrent": cfg.max_concurrent,
            "active_calls": sem.active,
            "available_slots": sem.available,
            "total_calls": m.total_calls,
            "successful": m.successful,
            "failed": m.failed,
            "rejected": m.rejected,
            "isolated_calls": m.isolated_calls,
            "success_rate": round(m.successful / max(m.total_calls, 1) * 100, 2),
            "avg_latency_ms": round(m.total_latency_ms / max(m.total_calls, 1), 2),
            "consecutive_failures": m.consecutive_failures,
            "last_error": m.last_error,
            "critical": cfg.critical,
            "dependencies": cfg.dependencies,
        }

    # ─────────────────────────────────────
    # Manual Controls
    # ─────────────────────────────────────

    def isolate(self, name: str):
        """Manually isolate a service."""
        if name in self._statuses:
            self._statuses[name] = ServiceStatus.DOWN

    def recover(self, name: str):
        """Manually recover a service."""
        if name in self._statuses:
            self._statuses[name] = ServiceStatus.HEALTHY
            self._metrics[name].consecutive_failures = 0

    # ─────────────────────────────────────
    # Stats
    # ─────────────────────────────────────

    def stats(self) -> dict:
        statuses = self.get_all_statuses()
        healthy = sum(1 for s in statuses.values() if s == "healthy")
        degraded = sum(1 for s in statuses.values() if s in ("degraded", "isolated"))
        down = sum(1 for s in statuses.values() if s == "down")

        total_calls = sum(m.total_calls for m in self._metrics.values())
        total_rejected = sum(m.rejected for m in self._metrics.values())

        return {
            "engine": "ServiceIsolation",
            "total_services": len(self._services),
            "healthy": healthy,
            "degraded": degraded,
            "down": down,
            "total_calls": total_calls,
            "total_rejected": total_rejected,
            "services": statuses,
        }


# ─────────────────────────────────────────────────────
# Global singleton
# ─────────────────────────────────────────────────────
service_isolation = ServiceIsolation()
