"""
Infrastructure API Routes — Observability & Management Endpoints
═══════════════════════════════════════════════════════
Exposes the entire infrastructure layer via REST API.

Endpoint Groups:
  /api/infrastructure/health      — Deep health checks, liveness, readiness
  /api/infrastructure/queue       — Task queue management and stats
  /api/infrastructure/workers     — Worker pool management and scaling
  /api/infrastructure/cache       — Cache management and invalidation
  /api/infrastructure/storage     — File storage management
  /api/infrastructure/circuits    — Circuit breaker status and controls
  /api/infrastructure/db          — Database manager stats and backup
  /api/infrastructure/ws          — WebSocket presence and stats
  /api/infrastructure/env         — Environment configuration info
  /api/infrastructure/overview    — Full infrastructure dashboard
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from typing import Optional, List
import time

router = APIRouter(prefix="/api/infrastructure", tags=["Infrastructure"])


# ═══════════════════════════════════════════════════
# HEALTH ENDPOINTS (Sections 10, 13)
# ═══════════════════════════════════════════════════
@router.get("/health")
async def deep_health_check():
    """Run deep health checks on all infrastructure components."""
    from ..infrastructure.health_monitor import health_monitor
    results = await health_monitor.check_all()
    return {
        "status": "ok",
        "components": {name: r.to_dict() for name, r in results.items()},
        "summary": health_monitor.stats(),
    }


@router.get("/health/live")
def liveness_probe():
    """Kubernetes-compatible liveness probe — is the process alive?"""
    from ..infrastructure.health_monitor import health_monitor
    return health_monitor.liveness()


@router.get("/health/ready")
def readiness_probe():
    """Kubernetes-compatible readiness probe — all dependencies ready?"""
    from ..infrastructure.health_monitor import health_monitor
    result = health_monitor.readiness()
    if result.get("status") == "not_ready":
        raise HTTPException(status_code=503, detail=result)
    return result


@router.get("/health/resources")
def system_resources():
    """System resource monitoring — CPU, memory, disk."""
    from ..infrastructure.health_monitor import SystemResourceMonitor
    return SystemResourceMonitor.get_resources()


# ═══════════════════════════════════════════════════
# TASK QUEUE ENDPOINTS (Section 6)
# ═══════════════════════════════════════════════════
@router.get("/queue/stats")
def queue_stats():
    """Task queue metrics — depth, throughput, dead-letter count."""
    from ..infrastructure.task_queue import task_queue
    return task_queue.stats()


@router.get("/queue/task/{task_id}")
def get_task(task_id: str):
    """Get status of a specific task."""
    from ..infrastructure.task_queue import task_queue
    task = task_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return task


@router.post("/queue/cancel/{task_id}")
def cancel_task(task_id: str):
    """Cancel a pending/queued task."""
    from ..infrastructure.task_queue import task_queue
    success = task_queue.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Task not found or not cancellable: {task_id}")
    return {"message": f"Task {task_id} cancelled", "task_id": task_id}


@router.get("/queue/dead-letter")
def dead_letter_queue():
    """List all tasks in the dead-letter queue."""
    from ..infrastructure.task_queue import task_queue
    return {
        "tasks": task_queue.dead_letter.get_all(),
        "stats": task_queue.dead_letter.stats(),
    }


@router.post("/queue/dead-letter/retry/{task_id}")
def retry_dead_letter(task_id: str):
    """Pull a task from dead-letter queue and re-enqueue it."""
    from ..infrastructure.task_queue import task_queue
    task = task_queue.dead_letter.retry_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found in DLQ: {task_id}")
    task_queue._enqueue_task(task)
    return {"message": f"Task {task_id} re-enqueued from DLQ"}


@router.post("/queue/dead-letter/clear")
def clear_dead_letter():
    """Clear the entire dead-letter queue."""
    from ..infrastructure.task_queue import task_queue
    task_queue.dead_letter.clear()
    return {"message": "Dead-letter queue cleared"}


# ═══════════════════════════════════════════════════
# WORKER POOL ENDPOINTS (Section 7)
# ═══════════════════════════════════════════════════
@router.get("/workers/stats")
def worker_stats():
    """Worker pool metrics — active workers, throughput, scaling events."""
    from ..infrastructure.worker_pool import worker_pool
    return worker_pool.stats()


@router.post("/workers/scale/{target}")
async def scale_workers(target: int):
    """Manually scale the worker pool to a target count."""
    from ..infrastructure.worker_pool import worker_pool
    if target < 1 or target > 50:
        raise HTTPException(status_code=400, detail="Target must be between 1 and 50")
    await worker_pool.scale_to(target)
    return {
        "message": f"Worker pool scaling to {target}",
        "current_workers": len(worker_pool.workers),
    }


# ═══════════════════════════════════════════════════
# CACHE ENDPOINTS (Section 12)
# ═══════════════════════════════════════════════════
@router.get("/cache/stats")
def cache_stats():
    """Cache metrics — hit rate, entries, memory usage."""
    from ..infrastructure.cache_service import cache_service
    return cache_service.stats()


@router.post("/cache/clear")
def clear_cache():
    """Clear all cached data."""
    from ..infrastructure.cache_service import cache_service
    count = cache_service.clear()
    return {"message": f"Cache cleared — {count} entries removed"}


@router.post("/cache/invalidate/namespace/{namespace}")
def invalidate_namespace(namespace: str):
    """Invalidate all entries in a cache namespace."""
    from ..infrastructure.cache_service import cache_service, CacheNamespace
    try:
        ns = CacheNamespace(namespace)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid namespace: {namespace}. Valid: {[n.value for n in CacheNamespace]}")
    count = cache_service.invalidate_namespace(ns)
    return {"message": f"Invalidated {count} entries in namespace '{namespace}'"}


@router.post("/cache/cleanup")
def cleanup_cache():
    """Remove expired cache entries."""
    from ..infrastructure.cache_service import cache_service
    count = cache_service.cleanup_expired()
    return {"message": f"Cleaned up {count} expired entries"}


# ═══════════════════════════════════════════════════
# STORAGE ENDPOINTS (Section 9)
# ═══════════════════════════════════════════════════
@router.get("/storage/stats")
def storage_stats():
    """Storage service metrics — files, usage, backend type."""
    from ..infrastructure.storage_service import storage_service
    return storage_service.stats()


@router.get("/storage/files")
def list_files(
    org_id: Optional[str] = None,
    survey_id: Optional[int] = None,
    session_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
):
    """List stored files with optional filters."""
    from ..infrastructure.storage_service import storage_service, FileCategory
    cat = None
    if category:
        try:
            cat = FileCategory(category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    return storage_service.list_files(org_id, survey_id, session_id, cat, limit)


@router.get("/storage/quota/{org_id}")
def storage_quota(org_id: str):
    """Get storage quota status for an organization."""
    from ..infrastructure.storage_service import storage_service
    return storage_service.get_org_quota(org_id)


@router.post("/storage/upload")
async def upload_file(
    file: UploadFile = File(...),
    org_id: str = "default",
    survey_id: Optional[int] = None,
    session_id: Optional[str] = None,
):
    """Upload a file to storage."""
    from ..infrastructure.storage_service import storage_service
    content = await file.read()
    try:
        metadata = storage_service.store_file(
            content=content,
            filename=file.filename or "unnamed",
            org_id=org_id,
            survey_id=survey_id,
            session_id=session_id,
        )
        return {"message": "File stored", "file": metadata.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/storage/file/{file_id}")
def delete_file(file_id: str):
    """Delete a stored file."""
    from ..infrastructure.storage_service import storage_service
    success = storage_service.delete_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")
    return {"message": f"File {file_id} deleted"}


@router.post("/storage/cleanup")
def cleanup_storage():
    """Remove all expired files."""
    from ..infrastructure.storage_service import storage_service
    count = storage_service.cleanup_expired()
    return {"message": f"Cleaned up {count} expired files"}


@router.get("/storage/migration-manifest")
def migration_manifest():
    """Generate cloud migration manifest for local→cloud transition."""
    from ..infrastructure.storage_service import storage_service
    return storage_service.prepare_cloud_migration()


# ═══════════════════════════════════════════════════
# CIRCUIT BREAKER ENDPOINTS (Section 14)
# ═══════════════════════════════════════════════════
@router.get("/circuits/stats")
def circuit_stats():
    """All circuit breaker statuses — Gemini, AssemblyAI, Database."""
    from ..infrastructure.circuit_breaker import circuit_registry
    return circuit_registry.stats()


@router.get("/circuits/{name}")
def circuit_detail(name: str):
    """Get detailed status of a specific circuit breaker."""
    from ..infrastructure.circuit_breaker import circuit_registry
    cb = circuit_registry.get(name)
    if not cb:
        raise HTTPException(status_code=404, detail=f"Circuit not found: {name}")
    return cb.stats()


@router.post("/circuits/{name}/force-open")
def force_open_circuit(name: str):
    """Manually trip a circuit breaker (block all calls)."""
    from ..infrastructure.circuit_breaker import circuit_registry
    cb = circuit_registry.get(name)
    if not cb:
        raise HTTPException(status_code=404, detail=f"Circuit not found: {name}")
    cb.force_open()
    return {"message": f"Circuit '{name}' forced OPEN", "state": cb.state.value}


@router.post("/circuits/{name}/force-close")
def force_close_circuit(name: str):
    """Manually close (reset) a circuit breaker."""
    from ..infrastructure.circuit_breaker import circuit_registry
    cb = circuit_registry.get(name)
    if not cb:
        raise HTTPException(status_code=404, detail=f"Circuit not found: {name}")
    cb.force_close()
    return {"message": f"Circuit '{name}' forced CLOSED", "state": cb.state.value}


@router.post("/circuits/reset-all")
def reset_all_circuits():
    """Reset all circuit breakers to CLOSED state."""
    from ..infrastructure.circuit_breaker import circuit_registry
    circuit_registry.reset_all()
    return {"message": "All circuits reset to CLOSED"}


# ═══════════════════════════════════════════════════
# DATABASE MANAGER ENDPOINTS (Section 8)
# ═══════════════════════════════════════════════════
@router.get("/db/stats")
def db_stats():
    """Database manager metrics — pool, queries, slow queries."""
    from ..infrastructure.db_manager import db_manager
    return db_manager.stats()


@router.get("/db/health")
def db_health():
    """Database health check — integrity, latency, pool status."""
    from ..infrastructure.db_manager import db_manager
    return db_manager.health_check()


@router.get("/db/schema")
def db_schema():
    """Database schema info — tables, row counts, version."""
    from ..infrastructure.db_manager import db_manager
    return db_manager.get_schema_info()


@router.get("/db/migrations")
def db_migrations():
    """List all applied database migrations."""
    from ..infrastructure.db_manager import db_manager
    return db_manager.get_migration_history()


@router.post("/db/backup")
def create_backup():
    """Create a database backup."""
    from ..infrastructure.db_manager import db_manager
    try:
        path = db_manager.backup()
        return {"message": "Backup created", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/db/backups")
def list_backups():
    """List available database backups."""
    from ..infrastructure.db_manager import db_manager
    return db_manager.list_backups()


# ═══════════════════════════════════════════════════
# WEBSOCKET MANAGER ENDPOINTS (Section 13)
# ═══════════════════════════════════════════════════
@router.get("/ws/stats")
def ws_stats():
    """WebSocket manager metrics — connections, channels, messages."""
    from ..infrastructure.ws_manager import enhanced_ws_manager
    return enhanced_ws_manager.stats()


@router.get("/ws/presence")
def ws_presence():
    """Current WebSocket presence — who's connected, channels, rooms."""
    from ..infrastructure.ws_manager import enhanced_ws_manager
    return enhanced_ws_manager.get_presence()


# ═══════════════════════════════════════════════════
# ENVIRONMENT ENDPOINTS (Section 15)
# ═══════════════════════════════════════════════════
@router.get("/env")
def environment_info():
    """Current environment — dev/staging/production config and feature flags."""
    from ..infrastructure.environment import env_config
    return env_config.info()


@router.get("/env/feature-flags")
def feature_flags():
    """All feature flags for the current environment."""
    from ..infrastructure.environment import env_config
    return env_config.all_feature_flags()


# ═══════════════════════════════════════════════════
# FULL INFRASTRUCTURE OVERVIEW
# ═══════════════════════════════════════════════════
@router.get("/overview")
async def infrastructure_overview():
    """
    Complete infrastructure dashboard — all components in one view.
    This is the master observability endpoint.
    """
    from ..infrastructure.task_queue import task_queue
    from ..infrastructure.worker_pool import worker_pool
    from ..infrastructure.cache_service import cache_service
    from ..infrastructure.storage_service import storage_service
    from ..infrastructure.circuit_breaker import circuit_registry
    from ..infrastructure.health_monitor import health_monitor
    from ..infrastructure.db_manager import db_manager
    from ..infrastructure.ws_manager import enhanced_ws_manager
    from ..infrastructure.environment import env_config

    # Run health checks
    health_results = await health_monitor.check_all()

    return {
        "environment": env_config.info(),
        "health": {
            "overall": health_monitor.stats()["overall_status"],
            "components": {name: r.to_dict() for name, r in health_results.items()},
        },
        "task_queue": task_queue.stats(),
        "worker_pool": worker_pool.stats(),
        "cache": cache_service.stats(),
        "storage": storage_service.stats(),
        "circuits": circuit_registry.stats(),
        "database": db_manager.stats(),
        "websocket": enhanced_ws_manager.stats(),
    }


@router.get("/architecture")
def architecture_info():
    """Infrastructure architecture summary — sections, modules, evolution roadmap."""
    return {
        "name": "Infrastructure & Scalability Architecture",
        "version": "1.0.0",
        "philosophy": "Decoupled + Scalable + Fault-Tolerant + Cloud-Portable",
        "sections": {
            "§5_containerization": {"module": "Dockerfile, docker-compose.yml", "status": "implemented"},
            "§6_async_processing": {"module": "infrastructure.task_queue", "status": "implemented"},
            "§7_worker_infrastructure": {"module": "infrastructure.worker_pool", "status": "implemented"},
            "§8_database_infrastructure": {"module": "infrastructure.db_manager", "status": "implemented"},
            "§9_storage_infrastructure": {"module": "infrastructure.storage_service", "status": "implemented"},
            "§10_api_gateway": {"module": "infrastructure.health_monitor", "status": "implemented"},
            "§12_caching": {"module": "infrastructure.cache_service", "status": "implemented"},
            "§13_realtime": {"module": "infrastructure.ws_manager", "status": "implemented"},
            "§14_failure_isolation": {"module": "infrastructure.circuit_breaker", "status": "implemented"},
            "§15_environment": {"module": "infrastructure.environment", "status": "implemented"},
            "§16_cicd": {"module": ".github/workflows/ci.yml", "status": "implemented"},
        },
        "evolution_roadmap": {
            "stage_1_mvp": "Single VM, Docker compose, SQLite, In-process queue — CURRENT",
            "stage_2_startup": "Multiple containers, Postgres, Worker scaling, Cloud storage",
            "stage_3_growth": "Load balancer, Auto scaling, Vector DB, Observability stack",
            "stage_4_enterprise": "Multi-region deployment, AI microservices, Event streaming",
        },
        "endpoints": {
            "health": "/api/infrastructure/health",
            "liveness": "/api/infrastructure/health/live",
            "readiness": "/api/infrastructure/health/ready",
            "queue": "/api/infrastructure/queue/stats",
            "workers": "/api/infrastructure/workers/stats",
            "cache": "/api/infrastructure/cache/stats",
            "storage": "/api/infrastructure/storage/stats",
            "circuits": "/api/infrastructure/circuits/stats",
            "database": "/api/infrastructure/db/stats",
            "websocket": "/api/infrastructure/ws/stats",
            "environment": "/api/infrastructure/env",
            "overview": "/api/infrastructure/overview",
        },
    }
