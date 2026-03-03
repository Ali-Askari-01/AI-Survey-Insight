"""
Task Queue — Async Processing Infrastructure (Section 6)
═══════════════════════════════════════════════════════
🚨 MOST IMPORTANT PART OF AI SYSTEM

AI tasks are slow. Never run AI inside API request.

Correct Flow:
  User submits feedback → FastAPI saves data → Task pushed to Queue
  → Worker processes AI → Results saved

This module implements:
  - Priority-based task scheduling (CRITICAL / HIGH / NORMAL / LOW / BATCH)
  - Retry logic with exponential backoff
  - Dead-letter queue for permanently failed tasks
  - Task deduplication to prevent redundant AI calls
  - Batch aggregation for cost optimization
  - Queue metrics and observability

Phase roadmap:
  Phase 1: In-process async queue (current — MVP/startup)
  Phase 2: Redis Queue (RQ) — multi-process
  Phase 3: Celery + Redis — distributed workers
  Enterprise: Kafka / RabbitMQ — event streaming
"""

import asyncio
import time
import uuid
import hashlib
import threading
import traceback
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Awaitable
from collections import defaultdict
from datetime import datetime


# ═══════════════════════════════════════════════════
# TASK PRIORITY LEVELS
# ═══════════════════════════════════════════════════
class TaskPriority(Enum):
    """Task priority determines execution order in the queue."""
    CRITICAL = 0   # Circuit breaker triggered, needs immediate recovery
    HIGH = 1       # Real-time user-facing tasks (sentiment, follow-up)
    NORMAL = 2     # Standard pipeline tasks (insight extraction, themes)
    LOW = 3        # Background optimization (memory, clustering)
    BATCH = 4      # Deferred batch tasks (executive reports, analytics)


class TaskStatus(Enum):
    """Lifecycle states of a task."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


# ═══════════════════════════════════════════════════
# TASK DEFINITION
# ═══════════════════════════════════════════════════
@dataclass
class Task:
    """Represents an async work item in the queue."""
    task_id: str
    task_type: str
    payload: dict
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    max_retries: int = 3
    retry_count: int = 0
    retry_delay_base: float = 2.0       # Exponential backoff base (seconds)
    timeout_seconds: float = 120.0       # Task execution timeout
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    dedup_key: Optional[str] = None      # For deduplication
    batch_group: Optional[str] = None    # For batch aggregation
    callback: Optional[str] = None       # Event to emit on completion
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "priority": self.priority.name,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "started_at": datetime.fromtimestamp(self.started_at).isoformat() if self.started_at else None,
            "completed_at": datetime.fromtimestamp(self.completed_at).isoformat() if self.completed_at else None,
            "latency_ms": int((self.completed_at - self.started_at) * 1000) if self.completed_at and self.started_at else None,
            "error": self.error,
            "batch_group": self.batch_group,
        }


# ═══════════════════════════════════════════════════
# RETRY POLICY
# ═══════════════════════════════════════════════════
class RetryPolicy:
    """Configurable retry with exponential backoff + jitter."""

    @staticmethod
    def calculate_delay(retry_count: int, base_delay: float = 2.0, max_delay: float = 60.0) -> float:
        """Exponential backoff: base * 2^retry + jitter, capped at max_delay."""
        import random
        delay = min(base_delay * (2 ** retry_count), max_delay)
        jitter = random.uniform(0, delay * 0.25)
        return delay + jitter

    @staticmethod
    def should_retry(task: Task, error: Exception) -> bool:
        """Determine if task should be retried based on error type."""
        # Never retry these
        non_retryable = (ValueError, KeyError, TypeError)
        if isinstance(error, non_retryable):
            return False
        # Retry if under limit
        return task.retry_count < task.max_retries


# ═══════════════════════════════════════════════════
# DEAD LETTER QUEUE
# ═══════════════════════════════════════════════════
class DeadLetterQueue:
    """
    Stores permanently failed tasks for manual inspection.
    These tasks exceeded retry limits or encountered non-retryable errors.
    """

    def __init__(self, max_size: int = 1000):
        self._queue: List[Task] = []
        self._lock = threading.Lock()
        self.max_size = max_size
        self.total_received = 0

    def add(self, task: Task, reason: str = "max_retries_exceeded"):
        """Add a failed task to the dead letter queue."""
        with self._lock:
            task.status = TaskStatus.DEAD_LETTER
            task.metadata["dlq_reason"] = reason
            task.metadata["dlq_time"] = datetime.now().isoformat()
            self._queue.append(task)
            self.total_received += 1
            # Evict oldest if over capacity
            if len(self._queue) > self.max_size:
                self._queue.pop(0)

    def get_all(self) -> List[dict]:
        with self._lock:
            return [t.to_dict() for t in self._queue]

    def retry_task(self, task_id: str) -> Optional[Task]:
        """Pull a task out of DLQ for manual retry."""
        with self._lock:
            for i, task in enumerate(self._queue):
                if task.task_id == task_id:
                    task = self._queue.pop(i)
                    task.status = TaskStatus.PENDING
                    task.retry_count = 0
                    task.error = None
                    return task
        return None

    def clear(self):
        with self._lock:
            self._queue.clear()

    def stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._queue),
                "max_size": self.max_size,
                "total_received": self.total_received,
                "task_types": dict(defaultdict(int, {
                    t.task_type: sum(1 for x in self._queue if x.task_type == t.task_type)
                    for t in self._queue
                })),
            }


# ═══════════════════════════════════════════════════
# BATCH AGGREGATOR
# ═══════════════════════════════════════════════════
class BatchAggregator:
    """
    Collects tasks with the same batch_group and releases them
    together once threshold or timeout is reached.
    Cost optimization: 1 batched AI call vs N individual calls.
    """

    def __init__(self, batch_size: int = 10, flush_interval: float = 30.0):
        self._batches: Dict[str, List[Task]] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_flush: Dict[str, float] = {}
        self.batch_size = batch_size
        self.flush_interval = flush_interval  # seconds
        self.total_batches_released = 0

    def add(self, task: Task) -> Optional[List[Task]]:
        """
        Add task to batch. Returns the batch if ready to release,
        otherwise returns None.
        """
        group = task.batch_group or task.task_type
        with self._lock:
            self._batches[group].append(task)
            if group not in self._last_flush:
                self._last_flush[group] = time.time()

            # Release if size threshold met
            if len(self._batches[group]) >= self.batch_size:
                return self._release_batch(group)

        return None

    def check_timeouts(self) -> List[List[Task]]:
        """Check for batches that have exceeded the flush interval."""
        now = time.time()
        released = []
        with self._lock:
            for group, last in list(self._last_flush.items()):
                if now - last >= self.flush_interval and self._batches.get(group):
                    batch = self._release_batch(group)
                    if batch:
                        released.append(batch)
        return released

    def _release_batch(self, group: str) -> List[Task]:
        """Release a batch of tasks for processing."""
        batch = self._batches.pop(group, [])
        self._last_flush.pop(group, None)
        self.total_batches_released += 1
        return batch

    def stats(self) -> dict:
        with self._lock:
            return {
                "pending_groups": len(self._batches),
                "pending_tasks": sum(len(b) for b in self._batches.values()),
                "batch_size_threshold": self.batch_size,
                "flush_interval_seconds": self.flush_interval,
                "total_batches_released": self.total_batches_released,
                "groups": {g: len(tasks) for g, tasks in self._batches.items()},
            }


# ═══════════════════════════════════════════════════
# TASK QUEUE (Core Engine)
# ═══════════════════════════════════════════════════
class TaskQueue:
    """
    Production-grade async task queue.

    Features:
      - 5-level priority scheduling
      - Exponential backoff retry
      - Dead letter queue for failed tasks
      - Task deduplication
      - Batch aggregation
      - Metrics and observability

    Architecture:
      API endpoint → enqueue(task) → priority queues → worker picks → execute → callback

    Future migration path:
      In-Process Queue → Redis Queue (RQ) → Celery + Redis → Kafka
    """

    def __init__(self, max_queue_size: int = 10000):
        # Priority queues: one list per priority level
        self._queues: Dict[TaskPriority, List[Task]] = {
            p: [] for p in TaskPriority
        }
        self._lock = threading.Lock()
        self._task_index: Dict[str, Task] = {}  # task_id → Task for lookups
        self._dedup_set: set = set()             # Active dedup keys
        self.max_queue_size = max_queue_size

        # Sub-components
        self.dead_letter = DeadLetterQueue(max_size=500)
        self.batch_aggregator = BatchAggregator(batch_size=10, flush_interval=30.0)
        self.retry_policy = RetryPolicy()

        # Handlers: task_type → callable
        self._handlers: Dict[str, Callable] = {}

        # Metrics
        self._metrics = {
            "total_enqueued": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_retried": 0,
            "total_deduplicated": 0,
            "total_cancelled": 0,
        }

        # Processing state
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None
        self._batch_check_task: Optional[asyncio.Task] = None

    # ─── Handler Registration ───
    def register_handler(self, task_type: str, handler: Callable):
        """
        Register a handler function for a task type.
        Handler signature: async def handler(payload: dict) -> Any
        """
        self._handlers[task_type] = handler

    # ─── Task Submission ───
    def enqueue(
        self,
        task_type: str,
        payload: dict,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
        timeout_seconds: float = 120.0,
        dedup_key: Optional[str] = None,
        batch_group: Optional[str] = None,
        callback_event: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Submit a task to the queue. Returns task_id or None if deduplicated.

        Never run AI inside an API request — always enqueue!
        """
        # Generate dedup key if not provided
        if dedup_key is None and batch_group is None:
            dedup_key = hashlib.md5(
                f"{task_type}:{str(sorted(payload.items()) if isinstance(payload, dict) else str(payload))}".encode()
            ).hexdigest()

        # Check dedup
        if dedup_key and dedup_key in self._dedup_set:
            self._metrics["total_deduplicated"] += 1
            return None

        task = Task(
            task_id=f"task-{uuid.uuid4().hex[:12]}",
            task_type=task_type,
            payload=payload,
            priority=priority,
            status=TaskStatus.QUEUED,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            dedup_key=dedup_key,
            batch_group=batch_group,
            callback=callback_event,
            metadata=metadata or {},
        )

        # Check if batch task → route to aggregator
        if batch_group:
            batch = self.batch_aggregator.add(task)
            if batch:
                # Batch ready — enqueue as a single combined task
                combined = Task(
                    task_id=f"batch-{uuid.uuid4().hex[:8]}",
                    task_type=f"{task_type}:batch",
                    payload={"tasks": [t.payload for t in batch], "count": len(batch)},
                    priority=TaskPriority.BATCH,
                    status=TaskStatus.QUEUED,
                    max_retries=max_retries,
                    timeout_seconds=timeout_seconds * 2,
                    metadata={"batch_size": len(batch), "original_type": task_type},
                )
                return self._enqueue_task(combined)
            # Still aggregating
            self._task_index[task.task_id] = task
            return task.task_id

        return self._enqueue_task(task)

    def _enqueue_task(self, task: Task) -> str:
        """Internal: Push task into the correct priority queue."""
        with self._lock:
            total = sum(len(q) for q in self._queues.values())
            if total >= self.max_queue_size:
                # Drop lowest priority tasks when full
                if self._queues[TaskPriority.BATCH]:
                    dropped = self._queues[TaskPriority.BATCH].pop(0)
                    self._cleanup_task(dropped)
                else:
                    raise RuntimeError("Task queue is full")

            self._queues[task.priority].append(task)
            self._task_index[task.task_id] = task
            if task.dedup_key:
                self._dedup_set.add(task.dedup_key)
            self._metrics["total_enqueued"] += 1

        return task.task_id

    # ─── Task Retrieval ───
    def dequeue(self) -> Optional[Task]:
        """
        Get the next task to process.
        Follows priority order: CRITICAL → HIGH → NORMAL → LOW → BATCH
        """
        with self._lock:
            for priority in TaskPriority:
                if self._queues[priority]:
                    task = self._queues[priority].pop(0)
                    task.status = TaskStatus.RUNNING
                    task.started_at = time.time()
                    return task
        return None

    # ─── Task Execution ───
    async def execute_task(self, task: Task) -> bool:
        """
        Execute a single task with timeout, retry, and error handling.
        Returns True if successful, False if failed.
        """
        handler = self._handlers.get(task.task_type)

        # Check for batch handler
        if not handler and task.task_type.endswith(":batch"):
            base_type = task.task_type.replace(":batch", "")
            handler = self._handlers.get(base_type)

        if not handler:
            task.error = f"No handler registered for task type: {task.task_type}"
            task.status = TaskStatus.FAILED
            self.dead_letter.add(task, reason="no_handler")
            self._metrics["total_failed"] += 1
            self._cleanup_task(task)
            return False

        try:
            # Execute with timeout
            if asyncio.iscoroutinefunction(handler):
                result = await asyncio.wait_for(
                    handler(task.payload),
                    timeout=task.timeout_seconds
                )
            else:
                result = handler(task.payload)

            # Success
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = result
            self._metrics["total_completed"] += 1
            self._cleanup_task(task)
            return True

        except asyncio.TimeoutError:
            task.error = f"Task timed out after {task.timeout_seconds}s"
            return await self._handle_failure(task, TimeoutError(task.error))

        except Exception as e:
            task.error = f"{type(e).__name__}: {str(e)}"
            return await self._handle_failure(task, e)

    async def _handle_failure(self, task: Task, error: Exception) -> bool:
        """Handle task failure: retry or send to dead letter queue."""
        if RetryPolicy.should_retry(task, error):
            # Schedule retry
            task.retry_count += 1
            task.status = TaskStatus.RETRYING
            delay = RetryPolicy.calculate_delay(task.retry_count, task.retry_delay_base)
            self._metrics["total_retried"] += 1

            # Re-enqueue after delay
            await asyncio.sleep(delay)
            with self._lock:
                task.status = TaskStatus.QUEUED
                self._queues[task.priority].append(task)
            return False
        else:
            # Permanent failure → dead letter
            task.status = TaskStatus.FAILED
            self._metrics["total_failed"] += 1
            self.dead_letter.add(task, reason=f"max_retries({task.max_retries})" if task.retry_count >= task.max_retries else "non_retryable")
            self._cleanup_task(task)
            return False

    def _cleanup_task(self, task: Task):
        """Remove task tracking data after completion/failure."""
        if task.dedup_key:
            self._dedup_set.discard(task.dedup_key)

    # ─── Processing Loop ───
    async def start_processing(self):
        """Start the async processing loop. Call this from app startup."""
        if self._running:
            return
        self._running = True
        self._processing_task = asyncio.create_task(self._processing_loop())
        self._batch_check_task = asyncio.create_task(self._batch_flush_loop())

    async def stop_processing(self):
        """Gracefully stop the processing loop."""
        self._running = False
        if self._processing_task:
            self._processing_task.cancel()
        if self._batch_check_task:
            self._batch_check_task.cancel()

    async def _processing_loop(self):
        """Main loop: continuously dequeue and execute tasks."""
        while self._running:
            task = self.dequeue()
            if task:
                try:
                    await self.execute_task(task)
                except Exception:
                    pass  # execute_task handles its own errors
            else:
                # No tasks — sleep briefly to avoid busy-waiting
                await asyncio.sleep(1.0)

    async def _batch_flush_loop(self):
        """Periodically check for timed-out batches and flush them."""
        while self._running:
            try:
                released_batches = self.batch_aggregator.check_timeouts()
                for batch in released_batches:
                    if batch:
                        combined = Task(
                            task_id=f"batch-{uuid.uuid4().hex[:8]}",
                            task_type=f"{batch[0].task_type}:batch",
                            payload={"tasks": [t.payload for t in batch], "count": len(batch)},
                            priority=TaskPriority.BATCH,
                            status=TaskStatus.QUEUED,
                            max_retries=3,
                            timeout_seconds=240.0,
                            metadata={"batch_size": len(batch), "source": "flush_timeout"},
                        )
                        self._enqueue_task(combined)
            except Exception:
                pass
            await asyncio.sleep(5)  # Check every 5 seconds

    # ─── Cancellation ───
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending/queued task."""
        with self._lock:
            task = self._task_index.get(task_id)
            if task and task.status in (TaskStatus.PENDING, TaskStatus.QUEUED):
                task.status = TaskStatus.CANCELLED
                # Remove from queue
                for q in self._queues.values():
                    if task in q:
                        q.remove(task)
                self._cleanup_task(task)
                self._metrics["total_cancelled"] += 1
                return True
        return False

    # ─── Task Lookup ───
    def get_task(self, task_id: str) -> Optional[dict]:
        """Get task status by ID."""
        task = self._task_index.get(task_id)
        return task.to_dict() if task else None

    # ─── Queue Stats ───
    def stats(self) -> dict:
        """Full queue observability metrics."""
        with self._lock:
            queue_sizes = {p.name: len(q) for p, q in self._queues.items()}
            total_pending = sum(queue_sizes.values())

        return {
            "running": self._running,
            "total_pending": total_pending,
            "by_priority": queue_sizes,
            "handlers_registered": list(self._handlers.keys()),
            "metrics": self._metrics.copy(),
            "dead_letter": self.dead_letter.stats(),
            "batch_aggregator": self.batch_aggregator.stats(),
            "dedup_keys_active": len(self._dedup_set),
            "max_queue_size": self.max_queue_size,
        }

    def queue_depth(self) -> int:
        """Total tasks waiting across all priorities."""
        with self._lock:
            return sum(len(q) for q in self._queues.values())


# ═══════════════════════════════════════════════════
# GLOBAL TASK QUEUE SINGLETON
# ═══════════════════════════════════════════════════
task_queue = TaskQueue(max_queue_size=10000)
