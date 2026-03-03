"""
AI Worker Pool — Independent Compute Engine Infrastructure (Section 7)
═══════════════════════════════════════════════════════
Workers are independent compute engines.

Each worker:
  - calls Gemini API
  - calls AssemblyAI
  - performs NLP processing
  - generates insights
  - updates database

Worker Scaling:
  1 worker  → MVP
  5 workers → Startup
  50 workers → Enterprise
  Scaling = add containers

This module implements:
  - Dynamic worker pool with configurable concurrency
  - Worker health monitoring and auto-restart
  - Task distribution with load balancing
  - Worker metrics (throughput, latency, error rate)
  - Graceful shutdown with drain mode
  - Per-worker isolation (one crash doesn't take down others)
"""

import asyncio
import time
import uuid
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

from .task_queue import TaskQueue, Task, TaskPriority, TaskStatus, task_queue


# ═══════════════════════════════════════════════════
# WORKER STATES
# ═══════════════════════════════════════════════════
class WorkerStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    DRAINING = "draining"      # Finishing current task, then stopping
    STOPPED = "stopped"
    ERROR = "error"


# ═══════════════════════════════════════════════════
# WORKER DEFINITION
# ═══════════════════════════════════════════════════
@dataclass
class Worker:
    """Represents a single processing worker."""
    worker_id: str
    status: WorkerStatus = WorkerStatus.IDLE
    current_task: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_processing_ms: float = 0.0
    started_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    error_count: int = 0
    consecutive_errors: int = 0
    _task: Optional[asyncio.Task] = field(default=None, repr=False)

    @property
    def avg_latency_ms(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return round(self.total_processing_ms / max(total, 1), 1)

    @property
    def error_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return round(self.tasks_failed / max(total, 1) * 100, 1)

    @property
    def uptime_seconds(self) -> float:
        return round(time.time() - self.started_at, 1)

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "status": self.status.value,
            "current_task": self.current_task,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "avg_latency_ms": self.avg_latency_ms,
            "error_rate": self.error_rate,
            "uptime_seconds": self.uptime_seconds,
            "consecutive_errors": self.consecutive_errors,
            "last_heartbeat": datetime.fromtimestamp(self.last_heartbeat).isoformat(),
        }


# ═══════════════════════════════════════════════════
# WORKER POOL CONFIGURATION
# ═══════════════════════════════════════════════════
@dataclass
class PoolConfig:
    """Worker pool configuration."""
    min_workers: int = 1           # Always keep at least 1 worker
    max_workers: int = 5           # MVP default
    scale_up_threshold: int = 5    # Queue depth to trigger scale-up
    scale_down_threshold: int = 0  # Queue depth to trigger scale-down
    health_check_interval: float = 10.0    # Seconds
    max_consecutive_errors: int = 5        # Restart worker after this many
    worker_idle_timeout: float = 60.0      # Stop idle workers after this (above min)
    drain_timeout: float = 30.0            # Max seconds to wait for drain


# ═══════════════════════════════════════════════════
# WORKER POOL MANAGER
# ═══════════════════════════════════════════════════
class WorkerPool:
    """
    Manages a dynamic pool of AI processing workers.

    Architecture:
      TaskQueue → WorkerPool → Workers → AI Pipeline Execution

    Features:
      - Auto-scaling based on queue depth
      - Health monitoring with auto-restart
      - Graceful drain mode for deployments
      - Per-worker metrics and isolation
    """

    def __init__(self, queue: TaskQueue, config: Optional[PoolConfig] = None):
        self.queue = queue
        self.config = config or PoolConfig()
        self.workers: Dict[str, Worker] = {}
        self._lock = threading.Lock()
        self._running = False
        self._supervisor_task: Optional[asyncio.Task] = None
        self._started_at: Optional[float] = None

        # Pool metrics
        self._total_tasks_processed = 0
        self._total_tasks_failed = 0
        self._scale_up_count = 0
        self._scale_down_count = 0
        self._worker_restarts = 0

    # ─── Lifecycle ───
    async def start(self):
        """Start the worker pool with min_workers."""
        if self._running:
            return
        self._running = True
        self._started_at = time.time()

        # Spawn initial workers
        for i in range(self.config.min_workers):
            await self._spawn_worker()

        # Start supervisor loop
        self._supervisor_task = asyncio.create_task(self._supervisor_loop())

    async def stop(self, graceful: bool = True):
        """Stop all workers. If graceful, wait for current tasks to finish."""
        self._running = False

        if graceful:
            # Put all workers in drain mode
            for worker in self.workers.values():
                if worker.status == WorkerStatus.BUSY:
                    worker.status = WorkerStatus.DRAINING

            # Wait for drain (with timeout)
            deadline = time.time() + self.config.drain_timeout
            while any(w.status in (WorkerStatus.BUSY, WorkerStatus.DRAINING) for w in self.workers.values()):
                if time.time() > deadline:
                    break
                await asyncio.sleep(0.5)

        # Cancel all worker tasks
        for worker in self.workers.values():
            if worker._task and not worker._task.done():
                worker._task.cancel()
            worker.status = WorkerStatus.STOPPED

        if self._supervisor_task:
            self._supervisor_task.cancel()

    # ─── Worker Management ───
    async def _spawn_worker(self) -> str:
        """Create and start a new worker."""
        worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        worker = Worker(worker_id=worker_id)
        self.workers[worker_id] = worker

        # Start worker coroutine
        worker._task = asyncio.create_task(self._worker_loop(worker))
        return worker_id

    async def _remove_worker(self, worker_id: str):
        """Stop and remove a worker."""
        worker = self.workers.get(worker_id)
        if not worker:
            return
        if worker._task and not worker._task.done():
            worker._task.cancel()
        worker.status = WorkerStatus.STOPPED
        del self.workers[worker_id]

    async def _restart_worker(self, worker_id: str):
        """Restart a failed worker."""
        await self._remove_worker(worker_id)
        new_id = await self._spawn_worker()
        self._worker_restarts += 1
        return new_id

    # ─── Worker Loop ───
    async def _worker_loop(self, worker: Worker):
        """
        Individual worker processing loop.
        Each worker independently pulls tasks from the queue and processes them.
        Worker isolation: one crash doesn't take down others.
        """
        while self._running and worker.status != WorkerStatus.STOPPED:
            try:
                task = self.queue.dequeue()
                if task:
                    worker.status = WorkerStatus.BUSY
                    worker.current_task = task.task_id
                    worker.last_heartbeat = time.time()
                    start = time.time()

                    try:
                        success = await self.queue.execute_task(task)
                        elapsed_ms = (time.time() - start) * 1000
                        worker.total_processing_ms += elapsed_ms

                        if success:
                            worker.tasks_completed += 1
                            worker.consecutive_errors = 0
                            self._total_tasks_processed += 1
                        else:
                            worker.tasks_failed += 1
                            worker.consecutive_errors += 1
                            worker.error_count += 1
                            self._total_tasks_failed += 1

                    except Exception:
                        worker.tasks_failed += 1
                        worker.consecutive_errors += 1
                        worker.error_count += 1
                        self._total_tasks_failed += 1

                    worker.status = WorkerStatus.IDLE
                    worker.current_task = None
                    worker.last_heartbeat = time.time()

                    # Auto-restart on too many consecutive errors
                    if worker.consecutive_errors >= self.config.max_consecutive_errors:
                        worker.status = WorkerStatus.ERROR
                        break  # Exit loop — supervisor will restart

                else:
                    worker.status = WorkerStatus.IDLE
                    worker.last_heartbeat = time.time()
                    await asyncio.sleep(1.0)  # No tasks — yield to event loop

                # Check drain mode
                if worker.status == WorkerStatus.DRAINING and not task:
                    worker.status = WorkerStatus.STOPPED
                    break

            except asyncio.CancelledError:
                worker.status = WorkerStatus.STOPPED
                break
            except Exception:
                worker.status = WorkerStatus.ERROR
                await asyncio.sleep(1)

    # ─── Supervisor Loop (Auto-Scaling + Health) ───
    async def _supervisor_loop(self):
        """
        Supervisor monitors workers and manages auto-scaling.

        Responsibilities:
          - Scale up workers when queue depth > threshold
          - Scale down idle workers when queue is empty (above min_workers)
          - Restart errored workers
          - Health check via heartbeats
        """
        while self._running:
            try:
                await self._check_health()
                await self._auto_scale()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5)

    async def _check_health(self):
        """Check worker health via heartbeats and error counts."""
        now = time.time()
        stale_timeout = self.config.health_check_interval * 3

        for worker_id, worker in list(self.workers.items()):
            # Restart errored workers
            if worker.status == WorkerStatus.ERROR:
                await self._restart_worker(worker_id)
                continue

            # Check for stale workers (no heartbeat)
            if worker.status == WorkerStatus.BUSY:
                if now - worker.last_heartbeat > stale_timeout:
                    await self._restart_worker(worker_id)

    async def _auto_scale(self):
        """
        Auto-scale the worker pool based on queue depth.

        Horizontal scaling strategy:
          Queue depth > threshold → add workers (up to max)
          Queue depth = 0, idle workers > min → remove workers
        """
        queue_depth = self.queue.queue_depth()
        active_count = len([w for w in self.workers.values() if w.status != WorkerStatus.STOPPED])

        # Scale UP
        if queue_depth > self.config.scale_up_threshold and active_count < self.config.max_workers:
            workers_needed = min(
                (queue_depth // self.config.scale_up_threshold),
                self.config.max_workers - active_count
            )
            for _ in range(max(1, workers_needed)):
                await self._spawn_worker()
                self._scale_up_count += 1

        # Scale DOWN
        elif queue_depth <= self.config.scale_down_threshold and active_count > self.config.min_workers:
            idle_workers = [
                w for w in self.workers.values()
                if w.status == WorkerStatus.IDLE
                and time.time() - w.last_heartbeat > self.config.worker_idle_timeout
            ]
            for worker in idle_workers:
                if len(self.workers) <= self.config.min_workers:
                    break
                await self._remove_worker(worker.worker_id)
                self._scale_down_count += 1

    # ─── Manual Scaling ───
    async def scale_to(self, target: int):
        """Manually set the worker count to a target."""
        target = max(self.config.min_workers, min(target, self.config.max_workers))
        active = len(self.workers)

        if target > active:
            for _ in range(target - active):
                await self._spawn_worker()
        elif target < active:
            idle = [w for w in self.workers.values() if w.status == WorkerStatus.IDLE]
            for worker in idle[:active - target]:
                await self._remove_worker(worker.worker_id)

    # ─── Stats & Observability ───
    def stats(self) -> dict:
        """Full worker pool metrics for observability."""
        workers_by_status = {}
        for worker in self.workers.values():
            status = worker.status.value
            workers_by_status[status] = workers_by_status.get(status, 0) + 1

        total_tasks = self._total_tasks_processed + self._total_tasks_failed
        avg_latency = 0.0
        if self.workers:
            total_ms = sum(w.total_processing_ms for w in self.workers.values())
            total_count = sum(w.tasks_completed + w.tasks_failed for w in self.workers.values())
            avg_latency = round(total_ms / max(total_count, 1), 1)

        return {
            "pool_running": self._running,
            "uptime_seconds": round(time.time() - self._started_at, 1) if self._started_at else 0,
            "config": {
                "min_workers": self.config.min_workers,
                "max_workers": self.config.max_workers,
                "scale_up_threshold": self.config.scale_up_threshold,
                "scale_down_threshold": self.config.scale_down_threshold,
            },
            "workers": {
                "total": len(self.workers),
                "by_status": workers_by_status,
                "details": [w.to_dict() for w in self.workers.values()],
            },
            "metrics": {
                "total_tasks_processed": self._total_tasks_processed,
                "total_tasks_failed": self._total_tasks_failed,
                "avg_latency_ms": avg_latency,
                "error_rate": round(self._total_tasks_failed / max(total_tasks, 1) * 100, 1),
                "scale_up_events": self._scale_up_count,
                "scale_down_events": self._scale_down_count,
                "worker_restarts": self._worker_restarts,
            },
            "queue": self.queue.stats(),
        }


# ═══════════════════════════════════════════════════
# GLOBAL WORKER POOL SINGLETON
# ═══════════════════════════════════════════════════
worker_pool = WorkerPool(queue=task_queue, config=PoolConfig(
    min_workers=1,
    max_workers=5,
    scale_up_threshold=5,
    scale_down_threshold=0,
    health_check_interval=10.0,
    max_consecutive_errors=5,
    worker_idle_timeout=60.0,
    drain_timeout=30.0,
))
