"""
Main FastAPI Application — AI Survey Software
Multi-Channel AI Feedback & Insight Engine
═══════════════════════════════════════════════════════
Architecture: AI-First Event-Driven
Layers: Client → API Gateway → Application Services → AI Intelligence → Data → Infrastructure
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import json
import time
import asyncio
from typing import List

from .database import init_db
from .auth import get_current_user
from .routes import survey, interview, insights, reports, notifications, auth
from .routes import ai_processing
from .routes import infrastructure as infra_routes
from .routes import data_architecture as data_arch_routes
from .routes import performance as perf_routes
from .routes import observability as obs_routes
from .routes import security as sec_routes
from .routes import survey_publish
from .routes import backups as backup_routes
from .services.event_bus import register_default_handlers, event_bus
from .services.ai_orchestrator import AIOrchestrator
from .services.metrics_service import MetricsService
from .config import ENABLE_METRICS

app = FastAPI(
    title="AI Feedback & Insight Engine",
    description="Multi-Channel AI-powered survey, interview, and insight platform",
    version="2.0.0"
)

# ═══════════════════════════════════════════════════
# MIDDLEWARE STACK (Order matters: outermost runs first)
# ═══════════════════════════════════════════════════

# 1. CORS (outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Rate Limiter — API Gateway Security
from .middleware.rate_limiter import RateLimiterMiddleware
app.add_middleware(RateLimiterMiddleware)

# 3. Input Validator — Sanitization & Prompt Injection Protection
from .middleware.input_validator import InputValidatorMiddleware
app.add_middleware(InputValidatorMiddleware)


# 4. Security Headers — Defense-in-depth (works even without nginx)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ═══════════════════════════════════════════════════
# OBSERVABILITY: Request Metrics Middleware
# ═══════════════════════════════════════════════════
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Track request latency and status codes for observability."""
    if not ENABLE_METRICS:
        return await call_next(request)

    start = time.time()
    response = await call_next(request)
    latency_ms = (time.time() - start) * 1000

    # Record metrics (skip static files)
    path = request.url.path
    if not path.startswith(("/css/", "/js/", "/assets/")):
        MetricsService.record_request(path, latency_ms, response.status_code)

        # Access log with request ID for tracing
        import logging
        import uuid
        request_id = response.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        response.headers["X-Request-ID"] = request_id
        access_logger = logging.getLogger("access")
        access_logger.info(
            f"[{request_id}] {request.method} {path} {response.status_code} {latency_ms:.0f}ms "
            f"{request.client.host if request.client else '-'}"
        )

    return response


# ═══════════════════════════════════════════════════
# ROUTERS
# ═══════════════════════════════════════════════════
app.include_router(auth.router)
app.include_router(survey.router)
app.include_router(interview.router)
app.include_router(insights.router)
app.include_router(reports.router)
app.include_router(notifications.router)
app.include_router(ai_processing.router)
app.include_router(infra_routes.router)
app.include_router(data_arch_routes.router)
app.include_router(perf_routes.router)
app.include_router(obs_routes.router)
app.include_router(sec_routes.router)
app.include_router(survey_publish.router)
app.include_router(backup_routes.router)

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dir, "assets")), name="assets")


# ═══════════════════════════════════════════════════
# STARTUP — Initialize architecture components
# ═══════════════════════════════════════════════════
@app.on_event("startup")
async def startup():
    # ── File Logging (before anything else so all startup logs are captured) ──
    from .services.log_service import setup_file_logging
    setup_file_logging()

    import logging
    logger = logging.getLogger("server")

    # Initialize database (creates new tables: ai_metadata, event_log, hitl_corrections, pipeline_executions)
    init_db()

    # Register event-driven handlers (with Intelligence Loop integration)
    register_default_handlers()

    # Initialize infrastructure layer
    from .infrastructure.task_queue import task_queue
    from .infrastructure.worker_pool import worker_pool
    from .infrastructure.health_monitor import health_monitor

    # NOTE: Background service loops (task_queue.start_processing, worker_pool.start,
    # health_monitor.start) are disabled in single-process dev mode because their
    # continuous polling loops with sync DB I/O starve the async event loop.
    # In production, these run in separate worker processes or with proper async DB drivers.
    # All infrastructure singletons, route handlers, and on-demand operations work without them.

    print("[Infrastructure] Task Queue, Worker Pool, Health Monitor initialized (loops disabled in dev mode)")

    # Initialize Data Architecture tables (5-layer schema)
    from .data_architecture.schema import init_data_architecture_tables
    init_data_architecture_tables()
    print("[Data Architecture] 5-Layer schema, pipeline, temporal, incremental, AI memory, governance initialized")

    # Initialize Performance & Reliability Architecture
    from .performance.degradation import degradation_controller
    from .performance.load_protector import load_protector
    from .performance.auto_recovery import auto_recovery
    # Take initial load snapshot
    load_protector.take_snapshot()
    # Run initial degradation evaluation
    degradation_controller.evaluate()
    print("[Performance] Latency, SLA, Degradation, Isolation, Load Protection, DB Reliability, Idempotency, Recovery, Testing initialized")

    # Initialize Observability Architecture
    from .observability.structured_logger import structured_logger
    from .observability.alert_engine import alert_engine
    from .observability.cost_tracker import cost_tracker
    structured_logger.system_event("server_startup", "All observability modules initialized")
    print("[Observability] Logger, Tracer, AI Observer, Alerts, Cost, Journeys, Failures, Dashboard initialized")

    # Initialize Security Architecture
    from .security.token_manager import token_manager
    from .security.threat_detector import threat_detector
    from .security.security_audit import security_audit
    security_audit.log_security("server_startup", "success", ip="127.0.0.1")
    print("[Security] Tokens, RBAC, Encryption, AI Security, Threats, Compliance, Incidents, Audit initialized")

    # ── Database Backup Scheduler ──
    from .services.backup_service import start_scheduler as start_backup_scheduler
    start_backup_scheduler()
    logger.info("[Backup] Automated backup scheduler started")

    logger.info("[Architecture] All systems initialized: DB, Event Bus, AI Orchestrator, Pipelines, Intelligence Loop, Infrastructure, Data Architecture, Performance & Reliability, Observability, Security, Backups, Logging")
    print("[Architecture] All systems initialized: DB, Event Bus, AI Orchestrator, Pipelines, Intelligence Loop, Infrastructure, Data Architecture, Performance & Reliability, Observability, Security, Backups, Logging")


# ═══════════════════════════════════════════════════
# PAGE ROUTES
# ═══════════════════════════════════════════════════
@app.get("/")
def serve_landing():
    """Serve the beautiful landing page."""
    landing_path = os.path.join(frontend_dir, "landing.html")
    if os.path.exists(landing_path):
        return FileResponse(landing_path)
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/app")
def serve_frontend():
    """Serve the main app (after login)."""
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/interview/{share_code}")
def serve_interview_landing(share_code: str):
    """Serve the respondent interview landing page (choose channel)."""
    path = os.path.join(frontend_dir, "interview.html")
    if os.path.exists(path):
        return FileResponse(path)
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/interview/{share_code}/{channel}")
def serve_interview_channel(share_code: str, channel: str):
    """Serve the respondent interview page for a specific channel."""
    path = os.path.join(frontend_dir, "interview.html")
    if os.path.exists(path):
        return FileResponse(path)
    return FileResponse(os.path.join(frontend_dir, "index.html"))


# ═══════════════════════════════════════════════════
# HEALTH & OBSERVABILITY ENDPOINTS
# ═══════════════════════════════════════════════════
_server_start_time = None

@app.on_event("startup")
async def record_uptime():
    global _server_start_time
    _server_start_time = time.time()


@app.get("/health")
def health_check():
    import shutil
    import platform
    import sys
    from .infrastructure.health_monitor import health_monitor
    from .infrastructure.environment import env_config
    from .database import DB_PATH
    from .services.backup_service import get_backup_status
    from .services.log_service import get_log_files

    check_start = time.time()

    # Database connectivity check
    db_ok = False
    db_size_mb = 0
    journal_mode = "unknown"
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute("SELECT 1")
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        db_ok = True
        if os.path.exists(DB_PATH):
            db_size_mb = round(os.path.getsize(DB_PATH) / (1024 * 1024), 2)
    except Exception:
        pass

    # Disk space
    try:
        disk = shutil.disk_usage(os.path.dirname(DB_PATH))
        disk_info = {
            "total_gb": round(disk.total / (1024**3), 1),
            "free_gb": round(disk.free / (1024**3), 1),
            "used_pct": round((disk.used / disk.total) * 100, 1),
        }
    except Exception:
        disk_info = None

    # Memory usage (process RSS)
    memory_info = None
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        memory_info = {
            "rss_mb": round(mem.rss / (1024 * 1024), 1),
            "vms_mb": round(mem.vms / (1024 * 1024), 1),
        }
    except ImportError:
        # psutil not available — use basic os info
        pass

    # Uptime
    uptime_seconds = round(time.time() - _server_start_time, 1) if _server_start_time else 0
    hours, remainder = divmod(int(uptime_seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {secs}s"

    # Backup status
    backup = get_backup_status()

    # Log sizes summary
    log_files = get_log_files()
    total_log_mb = round(sum(f["size_mb"] for f in log_files), 3)

    # Determine overall status
    disk_warning = disk_info and disk_info["used_pct"] > 90
    overall_status = "healthy"
    if not db_ok:
        overall_status = "degraded"
    elif disk_warning:
        overall_status = "warning"

    check_ms = round((time.time() - check_start) * 1000, 1)

    return {
        "status": overall_status,
        "version": "2.0.0",
        "architecture": "ai-first-event-driven",
        "environment": env_config.environment.value,
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
        "infrastructure": "active",
        "health_monitor": health_monitor.stats()["overall_status"],
        "database": {
            "connected": db_ok,
            "engine": "sqlite",
            "journal_mode": journal_mode,
            "size_mb": db_size_mb,
        },
        "memory": memory_info,
        "disk": disk_info,
        "backup": {
            "last_backup": backup.get("last_backup"),
            "scheduler_running": backup.get("scheduler_running"),
            "backup_count": backup.get("backup_count"),
            "total_backup_mb": backup.get("total_backup_size_mb"),
        },
        "logs": {
            "file_count": len(log_files),
            "total_size_mb": total_log_mb,
        },
        "health_check_ms": check_ms,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@app.get("/api/db/info")
def get_db_info(user=Depends(get_current_user)):
    """Database engine info & PostgreSQL migration status."""
    from .services.pg_migration import get_connection_info, get_sqlite_schema, is_postgres
    from .services.backup_service import get_db_integrity
    info = get_connection_info()
    if not is_postgres():
        schema = get_sqlite_schema()
        info["tables"] = {name: {"rows": t["row_count"], "columns": len(t["columns"])} for name, t in schema.items()}
        info["total_tables"] = len(schema)
        info["total_rows"] = sum(t["row_count"] for t in schema.values())
        info["integrity"] = get_db_integrity()
    return info


@app.get("/api/logs")
def get_logs(file: str = "app.log", lines: int = 100, level: str = None, search: str = None, user=Depends(get_current_user)):
    """Read recent log lines for debugging. Supports level filter and text search."""
    from .services.log_service import read_recent_logs, get_log_files
    # Sanitize filename
    if ".." in file or "/" in file or "\\" in file:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid filename")
    log_lines = read_recent_logs(file, lines)
    # Filter by level if specified
    if level:
        level_upper = level.upper()
        log_lines = [l for l in log_lines if level_upper in l]
    # Filter by text search if specified
    if search:
        search_lower = search.lower()
        log_lines = [l for l in log_lines if search_lower in l.lower()]
    return {
        "file": file,
        "total_lines": len(log_lines),
        "lines": log_lines,
        "filters": {"level": level, "search": search},
        "available_files": get_log_files(),
    }


@app.get("/api/metrics")
def get_metrics():
    """Observability: System + Product metrics dashboard."""
    return MetricsService.get_full_dashboard()


@app.get("/api/metrics/system")
def get_system_metrics():
    """Observability: System-level metrics only."""
    return MetricsService.get_system_metrics()


@app.get("/api/metrics/product")
def get_product_metrics(survey_id: int = None):
    """Observability: Product-level metrics."""
    return MetricsService.get_product_metrics(survey_id)


@app.get("/api/ai/stats")
def get_ai_stats():
    """AI Orchestrator: Cache, cost, and queue statistics."""
    return AIOrchestrator.get_full_stats()


@app.get("/api/events/stats")
def get_event_stats():
    """Event Bus: Event processing statistics."""
    return event_bus.stats()


@app.post("/api/ai/cache/clear")
def clear_ai_cache():
    """Clear the AI response cache."""
    AIOrchestrator.clear_cache()
    return {"message": "AI cache cleared"}


# ═══════════════════════════════════════════════════
# WebSocket — Live Dashboard Updates
# ═══════════════════════════════════════════════════
class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


ws_manager = ConnectionManager()


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "ack", "message": data})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.websocket("/ws/live")
async def websocket_enhanced(websocket: WebSocket):
    """Enhanced WebSocket with channels, rooms, and presence (Section 13)."""
    from .infrastructure.ws_manager import enhanced_ws_manager
    client_id = await enhanced_ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await enhanced_ws_manager.handle_message(client_id, data)
    except WebSocketDisconnect:
        await enhanced_ws_manager.disconnect(client_id)


# Shutdown: gracefully stop infrastructure
@app.on_event("shutdown")
async def shutdown():
    from .infrastructure.task_queue import task_queue
    from .infrastructure.worker_pool import worker_pool
    from .infrastructure.health_monitor import health_monitor
    from .services.backup_service import stop_scheduler as stop_backup_scheduler
    stop_backup_scheduler()
    await task_queue.stop_processing()
    await worker_pool.stop(graceful=True)
    await health_monitor.stop()
    import logging
    logging.getLogger("server").info("Graceful shutdown complete")
    print("[Infrastructure] Graceful shutdown complete")


# Export ws_manager for use in route handlers
def get_ws_manager():
    return ws_manager
