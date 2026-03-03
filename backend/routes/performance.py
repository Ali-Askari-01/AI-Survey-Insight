"""
Performance & Reliability API Routes
═══════════════════════════════════════════════════════
REST endpoints for the performance & reliability architecture.

Groups:
  /api/performance/latency        — Latency & Timeout Management (§3-4)
  /api/performance/sla            — SLA Tracking (§5, §16)
  /api/performance/degradation    — Graceful Degradation (§6, §15)
  /api/performance/isolation      — Service Isolation (§7)
  /api/performance/load           — Load Protection (§9)
  /api/performance/db             — DB Reliability (§10)
  /api/performance/idempotency    — Idempotency Guard (§12)
  /api/performance/recovery       — Auto Recovery (§14)
  /api/performance/testing        — Reliability Testing (§17)
  /api/performance/overview       — Architecture overview
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

router = APIRouter(prefix="/api/performance", tags=["Performance & Reliability"])


# ═══════════════════════════════════════════════════
# LATENCY & TIMEOUT MANAGEMENT (§3-4)
# ═══════════════════════════════════════════════════

@router.get("/latency/stats")
def get_latency_stats():
    """Get latency manager statistics."""
    from ..performance.latency_manager import latency_manager
    return latency_manager.stats()


@router.get("/latency/percentiles")
def get_latency_percentiles(
    path_prefix: str = Query("", description="Filter by endpoint prefix"),
    window: int = Query(300, ge=10, le=3600, description="Window in seconds"),
):
    """Get p50/p90/p95/p99 latency percentiles."""
    from ..performance.latency_manager import latency_manager
    return latency_manager.get_percentiles(path_prefix, window)


@router.get("/latency/endpoints")
def get_endpoint_breakdown(
    window: int = Query(300, ge=10, le=3600),
):
    """Get latency breakdown per endpoint group."""
    from ..performance.latency_manager import latency_manager
    return latency_manager.get_endpoint_breakdown(window)


@router.get("/latency/timeouts")
def get_timeout_stats():
    """Get soft/hard timeout statistics."""
    from ..performance.latency_manager import latency_manager
    return latency_manager.get_timeout_stats()


@router.get("/latency/configs")
def get_timeout_configs():
    """Get configured timeout budgets per endpoint."""
    from ..performance.latency_manager import latency_manager
    return {
        prefix: {
            "soft_timeout_ms": cfg.soft_timeout_ms,
            "hard_timeout_ms": cfg.hard_timeout_ms,
            "retry_on_soft": cfg.retry_on_soft,
            "cache_fallback": cfg.cache_fallback,
        }
        for prefix, cfg in latency_manager._configs.items()
    }


# ═══════════════════════════════════════════════════
# SLA TRACKING (§5, §16)
# ═══════════════════════════════════════════════════

@router.get("/sla/stats")
def get_sla_stats():
    """Get SLA tracker statistics."""
    from ..performance.sla_tracker import sla_tracker
    return sla_tracker.stats()


@router.get("/sla/compliance")
def get_sla_compliance(
    window: int = Query(300, ge=10, le=3600, description="Window in seconds"),
):
    """Get full SLA compliance report."""
    from ..performance.sla_tracker import sla_tracker
    return sla_tracker.compliance_report(window)


@router.get("/sla/compliance/{sla_name}")
def check_sla(sla_name: str, window: int = Query(300, ge=10, le=3600)):
    """Check compliance for a specific SLA target."""
    from ..performance.sla_tracker import sla_tracker
    return sla_tracker.check_compliance(sla_name, window)


@router.get("/sla/violations")
def get_sla_violations(
    sla_name: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    """Get recent SLA violations."""
    from ..performance.sla_tracker import sla_tracker
    return {"violations": sla_tracker.get_violations(sla_name, limit)}


@router.get("/sla/trend/{sla_name}")
def get_sla_trend(
    sla_name: str,
    buckets: int = Query(12, ge=4, le=60),
    window: int = Query(3600, ge=300, le=86400),
):
    """Get SLA metric trend over time."""
    from ..performance.sla_tracker import sla_tracker
    return sla_tracker.get_sla_trend(sla_name, buckets, window)


@router.get("/sla/targets")
def get_sla_targets():
    """Get all defined SLA targets."""
    from ..performance.sla_tracker import sla_tracker
    return {
        name: {
            "description": t.description,
            "p50_target_ms": t.p50_target_ms,
            "p95_target_ms": t.p95_target_ms,
            "p99_target_ms": t.p99_target_ms,
            "max_error_rate": t.max_error_rate,
            "availability_target": t.availability_target,
        }
        for name, t in sla_tracker._targets.items()
    }


# ═══════════════════════════════════════════════════
# GRACEFUL DEGRADATION (§6, §15)
# ═══════════════════════════════════════════════════

@router.get("/degradation/stats")
def get_degradation_stats():
    """Get degradation controller statistics."""
    from ..performance.degradation import degradation_controller
    return degradation_controller.stats()


@router.get("/degradation/level")
def get_degradation_level():
    """Get current degradation level and user message."""
    from ..performance.degradation import degradation_controller
    return {
        "level": degradation_controller.level.name,
        "message": degradation_controller.get_user_message(),
        "features": degradation_controller.get_available_features(),
    }


@router.post("/degradation/level/{level}")
def set_degradation_level(level: str, reason: str = "manual_override"):
    """Manually set degradation level (NORMAL/LITE/STALE/MINIMAL)."""
    from ..performance.degradation import degradation_controller, DegradationLevel
    try:
        lvl = DegradationLevel[level.upper()]
        degradation_controller.set_level(lvl, reason)
        return {"level": lvl.name, "message": degradation_controller.get_user_message()}
    except KeyError:
        raise HTTPException(400, f"Invalid level: {level}. Use NORMAL/LITE/STALE/MINIMAL")


@router.post("/degradation/clear-override")
def clear_degradation_override():
    """Clear manual degradation override."""
    from ..performance.degradation import degradation_controller
    degradation_controller.clear_override()
    return {"level": degradation_controller.level.name, "override_cleared": True}


@router.post("/degradation/evaluate")
def evaluate_degradation():
    """Manually trigger degradation rule evaluation."""
    from ..performance.degradation import degradation_controller
    degradation_controller.evaluate()
    return {
        "level": degradation_controller.level.name,
        "features": degradation_controller.get_available_features(),
    }


@router.get("/degradation/history")
def get_degradation_history(limit: int = Query(50, ge=1, le=200)):
    """Get degradation level change history."""
    from ..performance.degradation import degradation_controller
    return {"history": degradation_controller.get_history(limit)}


@router.get("/degradation/features")
def get_feature_matrix():
    """Get feature availability matrix per degradation level."""
    from ..performance.degradation import degradation_controller, DegradationLevel
    return {
        "current_level": degradation_controller.level.name,
        "feature_matrix": {
            name: {
                "max_level": max_lvl.name,
                "currently_available": degradation_controller.level <= max_lvl,
            }
            for name, max_lvl in degradation_controller.FEATURE_MATRIX.items()
        },
    }


# ═══════════════════════════════════════════════════
# SERVICE ISOLATION (§7)
# ═══════════════════════════════════════════════════

@router.get("/isolation/stats")
def get_isolation_stats():
    """Get service isolation statistics."""
    from ..performance.service_isolation import service_isolation
    return service_isolation.stats()


@router.get("/isolation/services")
def get_all_service_statuses():
    """Get status of all isolated services."""
    from ..performance.service_isolation import service_isolation
    return {"services": service_isolation.get_all_statuses()}


@router.get("/isolation/service/{name}")
def get_service_detail(name: str):
    """Get detailed metrics for a specific service."""
    from ..performance.service_isolation import service_isolation
    return service_isolation.get_service_metrics(name)


@router.get("/isolation/dependencies/{name}")
def get_service_dependencies(name: str):
    """Get dependency tree for a service."""
    from ..performance.service_isolation import service_isolation
    return service_isolation.get_dependency_tree(name)


@router.post("/isolation/isolate/{name}")
def isolate_service(name: str):
    """Manually isolate a service (mark as down)."""
    from ..performance.service_isolation import service_isolation
    service_isolation.isolate(name)
    return {"service": name, "status": "down", "isolated": True}


@router.post("/isolation/recover/{name}")
def recover_service(name: str):
    """Manually recover a service."""
    from ..performance.service_isolation import service_isolation
    service_isolation.recover(name)
    return {"service": name, "status": "healthy", "recovered": True}


# ═══════════════════════════════════════════════════
# LOAD PROTECTION (§9)
# ═══════════════════════════════════════════════════

@router.get("/load/stats")
def get_load_stats():
    """Get load protector statistics."""
    from ..performance.load_protector import load_protector
    return load_protector.stats()


@router.get("/load/level")
def get_load_level():
    """Get current system load level."""
    from ..performance.load_protector import load_protector
    s = load_protector.stats()
    return {
        "level": s["current_level"],
        "rps": s["rps"],
        "error_rate": s["error_rate"],
        "queue_pct": s["queue_pct"],
    }


@router.post("/load/snapshot")
def take_load_snapshot():
    """Take a point-in-time load snapshot."""
    from ..performance.load_protector import load_protector
    snap = load_protector.take_snapshot()
    return {
        "level": snap.level.value,
        "queue_depth": snap.queue_depth,
        "rps": round(snap.rps, 2),
        "error_rate": round(snap.error_rate, 4),
    }


@router.get("/load/trend")
def get_load_trend(limit: int = Query(50, ge=1, le=200)):
    """Get load level trend."""
    from ..performance.load_protector import load_protector
    return {"trend": load_protector.get_trend(limit)}


# ═══════════════════════════════════════════════════
# DATABASE RELIABILITY (§10)
# ═══════════════════════════════════════════════════

@router.get("/db/stats")
def get_db_reliability_stats():
    """Get database reliability statistics."""
    from ..performance.db_reliability import db_reliability
    return db_reliability.stats()


@router.post("/db/backup")
def create_backup(
    backup_type: str = Query("manual", regex="^(manual|hourly|daily|snapshot)$"),
    label: str = "",
):
    """Create a database backup."""
    from ..performance.db_reliability import db_reliability
    return db_reliability.create_backup(backup_type, label)


@router.get("/db/backups")
def list_backups(backup_type: Optional[str] = None):
    """List available database backups."""
    from ..performance.db_reliability import db_reliability
    return {"backups": db_reliability.list_backups(backup_type)}


@router.post("/db/backup/verify/{filename}")
def verify_backup(filename: str):
    """Verify integrity of a specific backup."""
    from ..performance.db_reliability import db_reliability
    return db_reliability.verify_backup(filename)


@router.post("/db/backup/verify-all")
def verify_all_backups():
    """Verify integrity of all stored backups."""
    from ..performance.db_reliability import db_reliability
    return db_reliability.verify_all_backups()


@router.get("/db/size")
def get_db_size():
    """Get database file size details."""
    from ..performance.db_reliability import db_reliability
    return db_reliability.get_db_size()


@router.get("/db/pool")
def get_pool_health():
    """Check database connection pool health."""
    from ..performance.db_reliability import db_reliability
    return db_reliability.check_pool_health()


@router.get("/db/recovery")
def get_recovery_status():
    """Get RPO/RTO recovery status."""
    from ..performance.db_reliability import db_reliability
    return db_reliability.recovery_status()


# ═══════════════════════════════════════════════════
# IDEMPOTENCY GUARD (§12)
# ═══════════════════════════════════════════════════

@router.get("/idempotency/stats")
def get_idempotency_stats():
    """Get idempotency guard statistics."""
    from ..performance.idempotency import idempotency_guard
    return idempotency_guard.stats()


@router.post("/idempotency/cleanup")
def cleanup_idempotency():
    """Remove expired idempotency records."""
    from ..performance.idempotency import idempotency_guard
    removed = idempotency_guard.cleanup_expired()
    return {"removed": removed, "remaining": len(idempotency_guard._store)}


@router.post("/idempotency/clear")
def clear_idempotency():
    """Clear all idempotency records."""
    from ..performance.idempotency import idempotency_guard
    idempotency_guard.clear()
    return {"cleared": True}


# ═══════════════════════════════════════════════════
# AUTO RECOVERY (§14)
# ═══════════════════════════════════════════════════

@router.get("/recovery/stats")
def get_recovery_stats():
    """Get auto recovery statistics."""
    from ..performance.auto_recovery import auto_recovery
    return auto_recovery.stats()


@router.post("/recovery/evaluate")
def evaluate_and_recover():
    """Manually trigger recovery evaluation."""
    from ..performance.auto_recovery import auto_recovery
    results = auto_recovery.evaluate_and_recover()
    return {"recovery_actions": results}


@router.post("/recovery/playbook/{name}")
def run_playbook(name: str, force: bool = False):
    """Execute a specific recovery playbook."""
    from ..performance.auto_recovery import auto_recovery
    return auto_recovery.execute_playbook(name, force)


@router.get("/recovery/events")
def get_recovery_events(
    limit: int = Query(50, ge=1, le=200),
    playbook: Optional[str] = None,
):
    """Get recovery event history."""
    from ..performance.auto_recovery import auto_recovery
    return {"events": auto_recovery.get_events(limit, playbook)}


@router.get("/recovery/playbooks")
def list_playbooks():
    """List all registered recovery playbooks."""
    from ..performance.auto_recovery import auto_recovery
    return auto_recovery.stats()["playbooks"]


# ═══════════════════════════════════════════════════
# RELIABILITY TESTING (§17)
# ═══════════════════════════════════════════════════

@router.get("/testing/stats")
def get_testing_stats():
    """Get reliability tester statistics."""
    from ..performance.reliability_testing import reliability_tester
    return reliability_tester.stats()


@router.post("/testing/stress")
def run_stress_test(
    concurrent: int = Query(10, ge=1, le=100),
    duration: int = Query(30, ge=5, le=300),
    target_rps: float = Query(50, ge=1, le=1000),
):
    """Run a stress test with simulated concurrent users."""
    from ..performance.reliability_testing import reliability_tester
    return reliability_tester.run_stress_test(concurrent, duration, target_rps)


@router.post("/testing/chaos")
def run_chaos_test(
    faults: str = Query("ai_timeout", description="Comma-separated fault types"),
    duration: int = Query(30, ge=5, le=120),
    fault_probability: float = Query(0.3, ge=0.05, le=1.0),
):
    """Run a chaos test with fault injection."""
    from ..performance.reliability_testing import reliability_tester
    fault_list = [f.strip() for f in faults.split(",")]
    return reliability_tester.run_chaos_test(fault_list, duration, fault_probability)


@router.post("/testing/latency")
def run_latency_test(requests: int = Query(100, ge=10, le=1000)):
    """Run a latency baseline test."""
    from ..performance.reliability_testing import reliability_tester
    return reliability_tester.run_latency_test(requests)


@router.get("/testing/resilience")
def get_resilience_score():
    """Calculate overall resilience score from test history."""
    from ..performance.reliability_testing import reliability_tester
    return reliability_tester.calculate_resilience_score()


@router.get("/testing/results")
def get_test_results(
    test_type: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    """Get test result history."""
    from ..performance.reliability_testing import reliability_tester
    return {"results": reliability_tester.get_results(test_type, limit)}


@router.post("/testing/fault/inject/{fault_type}")
def inject_fault(fault_type: str):
    """Manually inject a fault for testing."""
    from ..performance.reliability_testing import reliability_tester
    return reliability_tester.inject_fault(fault_type)


@router.post("/testing/fault/remove/{fault_type}")
def remove_fault(fault_type: str):
    """Remove an injected fault."""
    from ..performance.reliability_testing import reliability_tester
    return reliability_tester.remove_fault(fault_type)


@router.post("/testing/fault/remove-all")
def remove_all_faults():
    """Remove all injected faults."""
    from ..performance.reliability_testing import reliability_tester
    return reliability_tester.remove_all_faults()


# ═══════════════════════════════════════════════════
# ARCHITECTURE OVERVIEW
# ═══════════════════════════════════════════════════

@router.get("/overview")
def performance_overview():
    """Master overview of the entire performance & reliability architecture."""
    from ..performance.latency_manager import latency_manager
    from ..performance.sla_tracker import sla_tracker
    from ..performance.degradation import degradation_controller
    from ..performance.service_isolation import service_isolation
    from ..performance.load_protector import load_protector
    from ..performance.db_reliability import db_reliability
    from ..performance.idempotency import idempotency_guard
    from ..performance.auto_recovery import auto_recovery
    from ..performance.reliability_testing import reliability_tester

    return {
        "architecture": "Performance & Reliability Architecture",
        "golden_rule": "Fast when healthy. Stable when unhealthy. Never lose data.",
        "latency": latency_manager.stats(),
        "sla": sla_tracker.stats(),
        "degradation": degradation_controller.stats(),
        "isolation": service_isolation.stats(),
        "load": load_protector.stats(),
        "db_reliability": db_reliability.stats(),
        "idempotency": idempotency_guard.stats(),
        "recovery": auto_recovery.stats(),
        "testing": reliability_tester.stats(),
    }


@router.get("/architecture")
def performance_architecture_info():
    """Performance & reliability architecture specification details."""
    return {
        "name": "Performance & Reliability Architecture",
        "version": "1.0.0",
        "golden_rule": "A financial system handling intelligence instead of money.",
        "principles": [
            "LAW 1: Never block the user — async queues + background workers",
            "LAW 2: Compute once, serve many — cache AI results",
            "Fast when healthy, stable when unhealthy",
        ],
        "modules": {
            "latency_manager": {
                "sections": "§3-4",
                "description": "Dual-tier soft/hard timeouts, per-endpoint latency budgets",
                "status": "implemented",
            },
            "sla_tracker": {
                "sections": "§5, §16",
                "description": "SLA definitions, p50/p95/p99 tracking, violation alerts",
                "status": "implemented",
            },
            "degradation_controller": {
                "sections": "§6, §15",
                "description": "4-level graceful degradation with feature shedding",
                "status": "implemented",
            },
            "service_isolation": {
                "sections": "§7",
                "description": "Per-service concurrency semaphores, bulkheading",
                "status": "implemented",
            },
            "load_protector": {
                "sections": "§9",
                "description": "Adaptive backpressure, queue-depth based load shedding",
                "status": "implemented",
            },
            "db_reliability": {
                "sections": "§10",
                "description": "Scheduled backups, rotation, integrity verification, RPO/RTO",
                "status": "implemented",
            },
            "idempotency_guard": {
                "sections": "§12",
                "description": "API-level idempotency keys, concurrent deduplication",
                "status": "implemented",
            },
            "auto_recovery": {
                "sections": "§14",
                "description": "Self-healing playbooks, worker restart, DLQ retry",
                "status": "implemented",
            },
            "reliability_testing": {
                "sections": "§17",
                "description": "Stress/chaos/latency tests, fault injection, resilience scoring",
                "status": "implemented",
            },
        },
        "availability_targets": {
            "mvp": "99.5%",
            "startup": "99.9%",
            "enterprise": "99.99%",
        },
        "recovery_targets": {
            "RPO": "< 5 minutes",
            "RTO": "< 10 minutes",
            "MTTR": "< 5 minutes",
        },
        "endpoints": {
            "latency": "/api/performance/latency/stats",
            "sla": "/api/performance/sla/compliance",
            "degradation": "/api/performance/degradation/level",
            "isolation": "/api/performance/isolation/stats",
            "load": "/api/performance/load/stats",
            "db": "/api/performance/db/stats",
            "idempotency": "/api/performance/idempotency/stats",
            "recovery": "/api/performance/recovery/stats",
            "testing": "/api/performance/testing/stats",
            "overview": "/api/performance/overview",
        },
    }
