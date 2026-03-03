"""
Health Monitor — Deep Health Checks + API Gateway (Sections 10, 13)
═══════════════════════════════════════════════════════
As system grows, introduce gateway layer.

Responsibilities:
  ✅ rate limiting (already in middleware)
  ✅ request routing
  ✅ authentication validation
  ✅ logging
  ✅ deep health checks for all components

Real-Time Infrastructure:
  WebSocket layer for live dashboard updates, processing status, alerts.

This module implements:
  - Deep health checks for every system component
  - Component health registry with dependency tracking
  - System resource monitoring (CPU, memory, disk)
  - Readiness vs liveness probes (Kubernetes-compatible)
  - Alerting when components degrade
  - Health history and trend tracking
  - WebSocket health broadcast for live dashboards
"""

import time
import os
import sys
import threading
import asyncio
import sqlite3
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime


# ═══════════════════════════════════════════════════
# HEALTH STATUS
# ═══════════════════════════════════════════════════
class HealthStatus(Enum):
    HEALTHY = "healthy"           # All good
    DEGRADED = "degraded"         # Working but impaired
    UNHEALTHY = "unhealthy"       # Not functioning
    UNKNOWN = "unknown"           # Not checked yet


class ComponentType(Enum):
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    WORKER_POOL = "worker_pool"
    STORAGE = "storage"
    AI_SERVICE = "ai_service"       # Gemini API
    TRANSCRIPTION = "transcription"  # AssemblyAI
    EVENT_BUS = "event_bus"
    WEBSOCKET = "websocket"
    CIRCUIT_BREAKER = "circuit_breaker"


# ═══════════════════════════════════════════════════
# HEALTH CHECK RESULT
# ═══════════════════════════════════════════════════
@dataclass
class HealthCheckResult:
    """Result of a single component health check."""
    component: str
    component_type: ComponentType
    status: HealthStatus
    latency_ms: float = 0.0
    message: str = ""
    details: dict = field(default_factory=dict)
    checked_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "type": self.component_type.value,
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
            "message": self.message,
            "details": self.details,
            "checked_at": datetime.fromtimestamp(self.checked_at).isoformat(),
        }


# ═══════════════════════════════════════════════════
# HEALTH CHECK CONFIGURATION
# ═══════════════════════════════════════════════════
@dataclass
class HealthConfig:
    """Health monitor configuration."""
    check_interval_seconds: float = 30.0      # How often to run checks
    history_max_entries: int = 100             # Health history per component
    degraded_latency_threshold_ms: float = 5000  # Mark degraded above this
    alert_on_unhealthy: bool = True
    enable_system_resources: bool = True       # Monitor CPU/memory/disk


# ═══════════════════════════════════════════════════
# SYSTEM RESOURCE MONITOR
# ═══════════════════════════════════════════════════
class SystemResourceMonitor:
    """Monitor system-level resources (CPU, memory, disk)."""

    @staticmethod
    def get_resources() -> dict:
        """Get current system resource usage."""
        import platform

        resources = {
            "platform": platform.system(),
            "python_version": sys.version.split()[0],
            "pid": os.getpid(),
        }

        # Memory usage (portable via resource or psutil-like fallback)
        try:
            import resource as res_module
            usage = res_module.getrusage(res_module.RUSAGE_SELF)
            resources["memory_mb"] = round(usage.ru_maxrss / 1024, 1)  # Linux: KB
        except (ImportError, AttributeError):
            # Windows fallback
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                c_ulong = ctypes.c_ulong

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ('dwLength', ctypes.c_ulong),
                        ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong),
                        ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong),
                        ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong),
                        ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                    ]

                mem_status = MEMORYSTATUSEX()
                mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status))
                resources["memory_load_percent"] = mem_status.dwMemoryLoad
                resources["total_memory_gb"] = round(mem_status.ullTotalPhys / (1024 ** 3), 1)
                resources["available_memory_gb"] = round(mem_status.ullAvailPhys / (1024 ** 3), 1)
            except Exception:
                resources["memory_mb"] = "unavailable"

        # Disk usage
        try:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
            if os.path.exists(data_dir):
                total, used, free = 0, 0, 0
                if hasattr(os, 'statvfs'):
                    st = os.statvfs(data_dir)
                    total = st.f_frsize * st.f_blocks
                    free = st.f_frsize * st.f_bavail
                    used = total - free
                else:
                    # Windows
                    import ctypes
                    free_bytes = ctypes.c_ulonglong(0)
                    total_bytes = ctypes.c_ulonglong(0)
                    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                        data_dir, None, ctypes.pointer(total_bytes), ctypes.pointer(free_bytes)
                    )
                    total = total_bytes.value
                    free = free_bytes.value
                    used = total - free

                resources["disk"] = {
                    "total_gb": round(total / (1024 ** 3), 1),
                    "used_gb": round(used / (1024 ** 3), 1),
                    "free_gb": round(free / (1024 ** 3), 1),
                    "usage_percent": round(used / max(total, 1) * 100, 1),
                }
        except Exception:
            resources["disk"] = "unavailable"

        # Database file size
        try:
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "survey_engine.db")
            if os.path.exists(db_path):
                resources["db_size_mb"] = round(os.path.getsize(db_path) / (1024 * 1024), 2)
        except Exception:
            pass

        return resources


# ═══════════════════════════════════════════════════
# HEALTH MONITOR
# ═══════════════════════════════════════════════════
class HealthMonitor:
    """
    Centralized health monitoring for all system components.

    Features:
      - Registered health check functions per component
      - Periodic background checks
      - Liveness probe (is the process alive?)
      - Readiness probe (are all dependencies ready?)
      - Health history tracking
      - Alert callbacks on degradation
      - System resource monitoring

    Kubernetes-compatible:
      /health/live   → liveness (always 200 if process running)
      /health/ready  → readiness (200 only if all deps healthy)
    """

    def __init__(self, config: Optional[HealthConfig] = None):
        self.config = config or HealthConfig()
        self._checks: Dict[str, Callable] = {}           # component → check function
        self._check_types: Dict[str, ComponentType] = {}  # component → type
        self._last_results: Dict[str, HealthCheckResult] = {}
        self._history: Dict[str, List[dict]] = {}
        self._alert_callbacks: List[Callable] = []
        self._lock = threading.Lock()
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._started_at: Optional[float] = None

    # ─── Registration ───
    def register(self, component: str, component_type: ComponentType, check_fn: Callable):
        """
        Register a health check function for a component.
        check_fn should return HealthCheckResult or dict with status info.
        """
        self._checks[component] = check_fn
        self._check_types[component] = component_type
        self._history[component] = []

    def register_alert(self, callback: Callable):
        """Register an alert callback: called when component becomes unhealthy."""
        self._alert_callbacks.append(callback)

    # ─── Run All Checks ───
    async def check_all(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks and return results."""
        results = {}
        loop = asyncio.get_event_loop()
        for component, check_fn in self._checks.items():
            try:
                start = time.time()
                if asyncio.iscoroutinefunction(check_fn):
                    result = await check_fn()
                else:
                    # Run sync checks in executor to avoid blocking the event loop
                    result = await loop.run_in_executor(None, check_fn)

                latency = (time.time() - start) * 1000

                if isinstance(result, HealthCheckResult):
                    result.latency_ms = latency
                elif isinstance(result, dict):
                    status = HealthStatus.HEALTHY if result.get("ok", True) else HealthStatus.UNHEALTHY
                    result = HealthCheckResult(
                        component=component,
                        component_type=self._check_types.get(component, ComponentType.DATABASE),
                        status=status,
                        latency_ms=latency,
                        message=result.get("message", ""),
                        details=result,
                    )
                else:
                    result = HealthCheckResult(
                        component=component,
                        component_type=self._check_types.get(component, ComponentType.DATABASE),
                        status=HealthStatus.HEALTHY,
                        latency_ms=latency,
                    )

                # Mark degraded if latency too high
                if latency > self.config.degraded_latency_threshold_ms and result.status == HealthStatus.HEALTHY:
                    result.status = HealthStatus.DEGRADED
                    result.message = f"High latency: {latency:.0f}ms"

            except Exception as e:
                result = HealthCheckResult(
                    component=component,
                    component_type=self._check_types.get(component, ComponentType.DATABASE),
                    status=HealthStatus.UNHEALTHY,
                    message=f"{type(e).__name__}: {str(e)}",
                )

            results[component] = result

            # Update history
            with self._lock:
                self._last_results[component] = result
                self._history[component].append(result.to_dict())
                if len(self._history[component]) > self.config.history_max_entries:
                    self._history[component] = self._history[component][-self.config.history_max_entries:]

            # Alert on unhealthy
            if result.status == HealthStatus.UNHEALTHY and self.config.alert_on_unhealthy:
                for cb in self._alert_callbacks:
                    try:
                        cb(component, result)
                    except Exception:
                        pass

        return results

    def check_single(self, component: str) -> Optional[HealthCheckResult]:
        """Get last result for a specific component."""
        return self._last_results.get(component)

    # ─── Kubernetes-Compatible Probes ───
    def liveness(self) -> dict:
        """
        Liveness probe — is the process alive?
        Always returns healthy if the process is running.
        """
        return {
            "status": "alive",
            "uptime_seconds": round(time.time() - self._started_at, 1) if self._started_at else 0,
            "pid": os.getpid(),
            "timestamp": datetime.now().isoformat(),
        }

    def readiness(self) -> dict:
        """
        Readiness probe — are all dependencies ready?
        Returns healthy only if ALL components are healthy or degraded.
        """
        if not self._last_results:
            return {"status": "unknown", "message": "No health checks have run yet"}

        unhealthy = [
            name for name, result in self._last_results.items()
            if result.status == HealthStatus.UNHEALTHY
        ]
        degraded = [
            name for name, result in self._last_results.items()
            if result.status == HealthStatus.DEGRADED
        ]

        if unhealthy:
            return {
                "status": "not_ready",
                "unhealthy_components": unhealthy,
                "degraded_components": degraded,
            }

        return {
            "status": "ready",
            "components_checked": len(self._last_results),
            "degraded_components": degraded,
        }

    # ─── Background Monitor ───
    async def start(self):
        """Start the background health monitoring loop."""
        if self._running:
            return
        self._running = True
        self._started_at = time.time()
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """Stop the background monitor."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()

    async def _monitor_loop(self):
        """Periodically run health checks."""
        while self._running:
            try:
                await self.check_all()
            except asyncio.CancelledError:
                break
            except Exception:
                pass
            await asyncio.sleep(self.config.check_interval_seconds)

    # ─── Stats ───
    def stats(self) -> dict:
        """Full health monitor status."""
        component_status = {}
        for name, result in self._last_results.items():
            component_status[name] = {
                "status": result.status.value,
                "latency_ms": round(result.latency_ms, 2),
                "message": result.message,
                "checked_at": datetime.fromtimestamp(result.checked_at).isoformat(),
            }

        overall = HealthStatus.HEALTHY
        for result in self._last_results.values():
            if result.status == HealthStatus.UNHEALTHY:
                overall = HealthStatus.UNHEALTHY
                break
            if result.status == HealthStatus.DEGRADED:
                overall = HealthStatus.DEGRADED

        # System resources
        resources = {}
        if self.config.enable_system_resources:
            try:
                resources = SystemResourceMonitor.get_resources()
            except Exception:
                resources = {"error": "Unable to collect system resources"}

        return {
            "overall_status": overall.value,
            "running": self._running,
            "uptime_seconds": round(time.time() - self._started_at, 1) if self._started_at else 0,
            "total_components": len(self._checks),
            "healthy": sum(1 for r in self._last_results.values() if r.status == HealthStatus.HEALTHY),
            "degraded": sum(1 for r in self._last_results.values() if r.status == HealthStatus.DEGRADED),
            "unhealthy": sum(1 for r in self._last_results.values() if r.status == HealthStatus.UNHEALTHY),
            "components": component_status,
            "system_resources": resources,
            "config": {
                "check_interval_seconds": self.config.check_interval_seconds,
                "degraded_latency_threshold_ms": self.config.degraded_latency_threshold_ms,
            },
        }


# ═══════════════════════════════════════════════════
# DEFAULT HEALTH CHECK FUNCTIONS
# ═══════════════════════════════════════════════════
def check_database() -> HealthCheckResult:
    """Health check for SQLite database."""
    try:
        from ..database import get_db
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM surveys")
        count = cursor.fetchone()[0]
        cursor.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()[0]
        conn.close()

        status = HealthStatus.HEALTHY if integrity == "ok" else HealthStatus.DEGRADED
        return HealthCheckResult(
            component="database",
            component_type=ComponentType.DATABASE,
            status=status,
            message=f"OK — {count} surveys, integrity={integrity}",
            details={"survey_count": count, "integrity": integrity, "engine": "sqlite_wal"},
        )
    except Exception as e:
        return HealthCheckResult(
            component="database",
            component_type=ComponentType.DATABASE,
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


def check_task_queue() -> HealthCheckResult:
    """Health check for the task queue."""
    try:
        from .task_queue import task_queue
        stats = task_queue.stats()
        depth = stats["total_pending"]
        status = HealthStatus.HEALTHY
        if depth > 500:
            status = HealthStatus.DEGRADED
        if depth > 5000:
            status = HealthStatus.UNHEALTHY

        return HealthCheckResult(
            component="task_queue",
            component_type=ComponentType.QUEUE,
            status=status,
            message=f"Depth={depth}, Running={stats['running']}",
            details={"depth": depth, "running": stats["running"], "dead_letter": stats["dead_letter"]["size"]},
        )
    except Exception as e:
        return HealthCheckResult(
            component="task_queue",
            component_type=ComponentType.QUEUE,
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


def check_worker_pool() -> HealthCheckResult:
    """Health check for the AI worker pool."""
    try:
        from .worker_pool import worker_pool
        stats = worker_pool.stats()
        active = stats["workers"]["total"]
        status = HealthStatus.HEALTHY
        if active == 0:
            status = HealthStatus.UNHEALTHY
        elif stats["metrics"]["error_rate"] > 50:
            status = HealthStatus.DEGRADED

        return HealthCheckResult(
            component="worker_pool",
            component_type=ComponentType.WORKER_POOL,
            status=status,
            message=f"Workers={active}, Processed={stats['metrics']['total_tasks_processed']}",
            details={
                "active_workers": active,
                "error_rate": stats["metrics"]["error_rate"],
                "total_processed": stats["metrics"]["total_tasks_processed"],
            },
        )
    except Exception as e:
        return HealthCheckResult(
            component="worker_pool",
            component_type=ComponentType.WORKER_POOL,
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


def check_cache() -> HealthCheckResult:
    """Health check for the cache service."""
    try:
        from .cache_service import cache_service
        stats = cache_service.stats()
        return HealthCheckResult(
            component="cache",
            component_type=ComponentType.CACHE,
            status=HealthStatus.HEALTHY,
            message=f"Entries={stats['total_entries']}, HitRate={stats['hit_rate_percent']}%",
            details={"entries": stats["total_entries"], "hit_rate": stats["hit_rate_percent"]},
        )
    except Exception as e:
        return HealthCheckResult(
            component="cache",
            component_type=ComponentType.CACHE,
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


def check_storage() -> HealthCheckResult:
    """Health check for storage service."""
    try:
        from .storage_service import storage_service
        stats = storage_service.stats()
        base_path = stats["base_path"]
        writable = os.access(base_path, os.W_OK) if os.path.exists(base_path) else False
        status = HealthStatus.HEALTHY if writable else HealthStatus.DEGRADED

        return HealthCheckResult(
            component="storage",
            component_type=ComponentType.STORAGE,
            status=status,
            message=f"Files={stats['total_files']}, Writable={writable}",
            details={"total_files": stats["total_files"], "writable": writable, "backend": stats["backend"]},
        )
    except Exception as e:
        return HealthCheckResult(
            component="storage",
            component_type=ComponentType.STORAGE,
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


def check_circuits() -> HealthCheckResult:
    """Health check for circuit breakers."""
    try:
        from .circuit_breaker import circuit_registry
        stats = circuit_registry.stats()
        status = HealthStatus.HEALTHY
        if stats["open"] > 0:
            status = HealthStatus.UNHEALTHY
        elif stats["half_open"] > 0:
            status = HealthStatus.DEGRADED

        return HealthCheckResult(
            component="circuit_breakers",
            component_type=ComponentType.CIRCUIT_BREAKER,
            status=status,
            message=f"Healthy={stats['healthy']}, Open={stats['open']}, HalfOpen={stats['half_open']}",
            details=stats,
        )
    except Exception as e:
        return HealthCheckResult(
            component="circuit_breakers",
            component_type=ComponentType.CIRCUIT_BREAKER,
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


def check_event_bus() -> HealthCheckResult:
    """Health check for the event bus."""
    try:
        from ..services.event_bus import event_bus
        stats = event_bus.stats()
        status = HealthStatus.HEALTHY
        return HealthCheckResult(
            component="event_bus",
            component_type=ComponentType.EVENT_BUS,
            status=status,
            message=f"Handlers={stats.get('total_handlers', 0)}, Events={stats.get('total_events_emitted', 0)}",
            details=stats,
        )
    except Exception as e:
        return HealthCheckResult(
            component="event_bus",
            component_type=ComponentType.EVENT_BUS,
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


# ═══════════════════════════════════════════════════
# GLOBAL HEALTH MONITOR SINGLETON
# ═══════════════════════════════════════════════════
health_monitor = HealthMonitor()

# Register all default health checks
health_monitor.register("database", ComponentType.DATABASE, check_database)
health_monitor.register("task_queue", ComponentType.QUEUE, check_task_queue)
health_monitor.register("worker_pool", ComponentType.WORKER_POOL, check_worker_pool)
health_monitor.register("cache", ComponentType.CACHE, check_cache)
health_monitor.register("storage", ComponentType.STORAGE, check_storage)
health_monitor.register("circuit_breakers", ComponentType.CIRCUIT_BREAKER, check_circuits)
health_monitor.register("event_bus", ComponentType.EVENT_BUS, check_event_bus)
