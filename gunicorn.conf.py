"""
Gunicorn Configuration — Production Deployment (Section 5)
═══════════════════════════════════════════════════════
Production: Gunicorn + Uvicorn Workers

Why Worker Processes?
  AI apps experience blocking operations.
  Workers allow:
    ✅ parallel requests
    ✅ concurrency
    ✅ stability under load

Usage:
  gunicorn -c gunicorn.conf.py backend.main:app
"""
import os
import multiprocessing

# ─── Server Socket ───
bind = "0.0.0.0:8000"
backlog = 2048

# ─── Worker Processes ───
# Rule of thumb: (2 × CPU cores) + 1
# Override with WORKERS env var
workers = int(os.environ.get("WORKERS", (2 * multiprocessing.cpu_count()) + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000             # Restart workers after N requests (prevent memory leaks)
max_requests_jitter = 50        # Add jitter to prevent all workers restarting simultaneously

# ─── Timeouts ───
timeout = 120                   # AI calls can be slow — generous timeout
graceful_timeout = 30           # Wait for in-flight requests on restart
keepalive = 5

# ─── Logging ───
accesslog = "-"                 # stdout
errorlog = "-"                  # stderr
loglevel = os.environ.get("LOG_LEVEL", "info").lower()

# ─── Process Naming ───
proc_name = "ai-survey-engine"

# ─── Lifecycle Hooks ───
def on_starting(server):
    print(f"[Gunicorn] Starting AI Survey Engine with {workers} workers")

def post_fork(server, worker):
    print(f"[Gunicorn] Worker {worker.pid} spawned")

def pre_exec(server):
    print("[Gunicorn] Forked child, re-executing")

def when_ready(server):
    print("[Gunicorn] Server is ready. Spawning workers")

def worker_exit(server, worker):
    print(f"[Gunicorn] Worker {worker.pid} exited")
