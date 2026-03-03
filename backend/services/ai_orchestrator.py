"""
AI Orchestrator — Central AI Intelligence Controller
═══════════════════════════════════════════════════════
Architecture Rule: NEVER call AI directly from endpoints.
All AI goes through: API → AI Orchestrator → AI Worker → Gemini

This module controls:
  - Gemini prompt management & routing
  - Response caching (LRU in-memory)
  - Cost tracking & optimization
  - AI task queuing for background processing
  - Prompt versioning & metadata logging
  - Retry + fallback orchestration
  - Task classification → Pipeline routing (AI Processing Architecture)
  - Batch processing & smart triggering
"""
import json
import time
import hashlib
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Optional
from ..database import get_db


# ═══════════════════════════════════════════════════
# IN-MEMORY CACHE (Thread-Safe LRU)
# ═══════════════════════════════════════════════════
class AICache:
    """Thread-safe LRU cache for AI responses to save Gemini quota."""

    def __init__(self, max_size: int = 200, ttl_seconds: int = 3600):
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self.max_size = max_size
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0

    def _make_key(self, prompt: str, task_type: str) -> str:
        """Generate a cache key from prompt + task type."""
        content = f"{task_type}:{prompt[:500]}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, prompt: str, task_type: str) -> Optional[str]:
        key = self._make_key(prompt, task_type)
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if time.time() - entry["ts"] < self.ttl:
                    self._cache.move_to_end(key)
                    self.hits += 1
                    return entry["value"]
                else:
                    del self._cache[key]
            self.misses += 1
            return None

    def put(self, prompt: str, task_type: str, value: str):
        key = self._make_key(prompt, task_type)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = {"value": value, "ts": time.time()}
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / max(total, 1) * 100, 1),
            "ttl_seconds": self.ttl,
        }

    def clear(self):
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0


# ═══════════════════════════════════════════════════
# COST TRACKER
# ═══════════════════════════════════════════════════
class CostTracker:
    """Track AI API usage costs and quotas."""

    # Approximate token costs per model (per 1M tokens)
    MODEL_COSTS = {
        "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-2.5-flash-lite": {"input": 0.075, "output": 0.30},
        "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
        "gemini-3-flash-preview": {"input": 0.15, "output": 0.60},
    }

    def __init__(self):
        self._lock = threading.Lock()
        self.total_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.calls_by_model = {}
        self.calls_by_task = {}
        self.errors = 0
        self.cache_savings = 0

    def record_call(self, model: str, task_type: str, input_tokens: int, output_tokens: int, cached: bool = False):
        with self._lock:
            self.total_calls += 1
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

            # Estimate cost
            costs = self.MODEL_COSTS.get(model, {"input": 0.15, "output": 0.60})
            call_cost = (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000
            self.total_cost_usd += call_cost

            # Per-model tracking
            if model not in self.calls_by_model:
                self.calls_by_model[model] = {"calls": 0, "tokens": 0, "cost": 0.0}
            self.calls_by_model[model]["calls"] += 1
            self.calls_by_model[model]["tokens"] += input_tokens + output_tokens
            self.calls_by_model[model]["cost"] += call_cost

            # Per-task tracking
            if task_type not in self.calls_by_task:
                self.calls_by_task[task_type] = {"calls": 0, "avg_tokens": 0, "total_tokens": 0}
            self.calls_by_task[task_type]["calls"] += 1
            self.calls_by_task[task_type]["total_tokens"] += input_tokens + output_tokens
            self.calls_by_task[task_type]["avg_tokens"] = (
                self.calls_by_task[task_type]["total_tokens"] // self.calls_by_task[task_type]["calls"]
            )

            if cached:
                self.cache_savings += 1

    def record_error(self):
        with self._lock:
            self.errors += 1

    def get_stats(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": round(self.total_cost_usd, 6),
            "errors": self.errors,
            "cache_savings": self.cache_savings,
            "by_model": self.calls_by_model,
            "by_task": self.calls_by_task,
        }


# ═══════════════════════════════════════════════════
# AI METADATA LOGGER
# ═══════════════════════════════════════════════════
class AIMetadataLogger:
    """Log every AI call's metadata to the database for observability."""

    @staticmethod
    def log(task_type: str, model: str, prompt_hash: str,
            input_tokens: int, output_tokens: int, latency_ms: int,
            success: bool, cached: bool = False, error_msg: str = ""):
        try:
            conn = get_db()
            conn.execute("""
                INSERT INTO ai_metadata (task_type, model, prompt_hash, input_tokens, output_tokens,
                    latency_ms, success, cached, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (task_type, model, prompt_hash, input_tokens, output_tokens,
                  latency_ms, 1 if success else 0, 1 if cached else 0, error_msg))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[AIMetadata] Failed to log: {e}")


# ═══════════════════════════════════════════════════
# AI TASK QUEUE (In-Process Background Worker)
# ═══════════════════════════════════════════════════
class AITaskQueue:
    """
    Simple in-process task queue for background AI processing.
    Architecture: API → Store response → Queue AI task → Worker processes later
    MVP uses threading; production would use Redis/Celery.
    """

    def __init__(self, max_workers: int = 2):
        self._queue = []
        self._lock = threading.Lock()
        self._workers_active = 0
        self.max_workers = max_workers
        self.processed = 0
        self.failed = 0

    def enqueue(self, task_fn, *args, **kwargs):
        """Add a task to the queue and start a worker if available."""
        with self._lock:
            self._queue.append((task_fn, args, kwargs))

        self._try_start_worker()

    def _try_start_worker(self):
        with self._lock:
            if self._workers_active < self.max_workers and self._queue:
                self._workers_active += 1
                task = self._queue.pop(0)
                thread = threading.Thread(target=self._run_task, args=(task,), daemon=True)
                thread.start()

    def _run_task(self, task):
        task_fn, args, kwargs = task
        try:
            task_fn(*args, **kwargs)
            with self._lock:
                self.processed += 1
        except Exception as e:
            print(f"[AITaskQueue] Task failed: {e}")
            with self._lock:
                self.failed += 1
        finally:
            with self._lock:
                self._workers_active -= 1
            # Check if more tasks are queued
            self._try_start_worker()

    def stats(self) -> dict:
        return {
            "queued": len(self._queue),
            "active_workers": self._workers_active,
            "max_workers": self.max_workers,
            "processed": self.processed,
            "failed": self.failed,
        }


# ═══════════════════════════════════════════════════
# AI ORCHESTRATOR (Main Entrypoint)
# ═══════════════════════════════════════════════════
# Global singletons
_cache = AICache(max_size=200, ttl_seconds=3600)
_cost_tracker = CostTracker()
_task_queue = AITaskQueue(max_workers=2)
_metadata_logger = AIMetadataLogger()


class AIOrchestrator:
    """
    Central AI controller — ALL AI requests go through here.

    Architecture Flow:
        Endpoint → AIOrchestrator.execute() → Cache Check → AI Service → Log metadata → Return

    Pipeline-Routed Flow (AI Processing Architecture):
        Endpoint → AIOrchestrator.execute_pipeline() → Classify → Build Context → Route Pipeline → Validate → Return

    For background tasks:
        Endpoint → AIOrchestrator.enqueue_background() → Store immediately → AI later
    """

    @staticmethod
    def execute_pipeline(task_type_str: str, payload: dict) -> dict:
        """
        Execute an AI task through the full pipeline architecture.

        Flow:
            1. Task Classifier identifies the task type + pipeline
            2. Context Builder assembles rich context
            3. Pipeline executes the AI processing
            4. Validation layer checks the output
            5. Return structured result

        Args:
            task_type_str: Task type string (e.g. 'sentiment_analysis', 'executive_summary')
            payload: Data required for the task

        Returns:
            Pipeline execution result dict
        """
        from .ai_task_classifier import AITaskClassifier, AITaskType
        from .ai_pipelines import get_pipeline

        # ── Step 1: Classify ──
        classification = AITaskClassifier.classify_request(task_type_str, payload)
        if not classification:
            return {
                "error": f"Unknown task type: {task_type_str}",
                "valid": False,
            }

        # ── Step 2: Validate context ──
        context_check = AITaskClassifier.validate_context(
            classification.task_type, payload
        )

        # ── Step 3: Get pipeline ──
        pipeline_cls = get_pipeline(classification.pipeline.value)
        if not pipeline_cls:
            return {
                "error": f"Pipeline not found: {classification.pipeline.value}",
                "valid": False,
            }

        # ── Step 4: Execute pipeline ──
        result = pipeline_cls.execute(payload, task_type=classification.task_type.value)

        # Attach classification metadata
        result["classification"] = classification.to_dict()
        result["context_validation"] = context_check

        return result

    @staticmethod
    def execute_event(event_type: str, payload: dict) -> dict:
        """
        Execute AI processing triggered by a system event.

        Flow:
            Event → Classify → Route to Pipeline → Execute

        Args:
            event_type: System event type (e.g. 'response.submitted')
            payload: Event payload data
        """
        from .ai_task_classifier import AITaskClassifier
        from .ai_pipelines import get_pipeline

        classification = AITaskClassifier.classify_event(event_type, payload)
        if not classification:
            return {"skipped": True, "reason": f"No AI task for event: {event_type}"}

        pipeline_cls = get_pipeline(classification.pipeline.value)
        if not pipeline_cls:
            return {"skipped": True, "reason": f"Pipeline not found: {classification.pipeline.value}"}

        # Check if batch-eligible — defer if threshold not met
        if classification.batch_eligible:
            from .intelligence_loop import _intelligence_loop
            survey_id = payload.get("survey_id")
            if survey_id:
                # Let intelligence loop handle batch timing
                return {
                    "deferred": True,
                    "reason": "Batch-eligible task — handled by intelligence loop",
                    "task_type": classification.task_type.value,
                }

        result = pipeline_cls.execute(payload, task_type=classification.task_type.value)
        result["classification"] = classification.to_dict()
        return result

    @staticmethod
    def execute(task_type: str, prompt: str, ai_fn, *args,
                cacheable: bool = True, max_tokens: int = 1024, **kwargs):
        """
        Execute an AI task through the orchestrator pipeline.

        Args:
            task_type: Category of AI task (e.g. 'sentiment', 'chat_response', 'question_gen')
            prompt: The prompt text (used for caching key)
            ai_fn: The actual AI function to call
            cacheable: Whether to cache the result
            max_tokens: Token budget for this call
        Returns:
            The AI function's result
        """
        start_time = time.time()
        prompt_hash = hashlib.sha256(prompt[:500].encode()).hexdigest()[:16]

        # ── Step 1: Check cache ──
        if cacheable:
            cached_result = _cache.get(prompt, task_type)
            if cached_result is not None:
                latency = int((time.time() - start_time) * 1000)
                _cost_tracker.record_call("cache", task_type, 0, 0, cached=True)
                _metadata_logger.log(task_type, "cache", prompt_hash, 0, 0, latency, True, cached=True)
                # Try to deserialize if it looks like JSON
                try:
                    return json.loads(cached_result)
                except (json.JSONDecodeError, TypeError):
                    return cached_result

        # ── Step 2: Execute AI function ──
        try:
            result = ai_fn(*args, **kwargs)
            latency = int((time.time() - start_time) * 1000)

            # Estimate tokens (rough: 4 chars per token)
            input_tokens = len(prompt) // 4
            output_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
            output_tokens = len(output_str) // 4

            # ── Step 3: Record cost ──
            from ..config import GEMINI_MODEL
            _cost_tracker.record_call(GEMINI_MODEL, task_type, input_tokens, output_tokens)

            # ── Step 4: Cache result ──
            if cacheable and result:
                cache_value = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                _cache.put(prompt, task_type, cache_value)

            # ── Step 5: Log metadata ──
            _metadata_logger.log(task_type, GEMINI_MODEL, prompt_hash,
                                 input_tokens, output_tokens, latency, True)

            return result

        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            _cost_tracker.record_error()
            _metadata_logger.log(task_type, "error", prompt_hash, 0, 0, latency, False, error_msg=str(e)[:200])
            raise

    @staticmethod
    def enqueue_background(task_fn, *args, **kwargs):
        """Queue an AI task for background processing (non-blocking)."""
        _task_queue.enqueue(task_fn, *args, **kwargs)

    @staticmethod
    def get_cache_stats() -> dict:
        return _cache.stats()

    @staticmethod
    def get_cost_stats() -> dict:
        return _cost_tracker.get_stats()

    @staticmethod
    def get_queue_stats() -> dict:
        return _task_queue.stats()

    @staticmethod
    def get_full_stats() -> dict:
        return {
            "cache": _cache.stats(),
            "costs": _cost_tracker.get_stats(),
            "queue": _task_queue.stats(),
        }

    @staticmethod
    def get_pipeline_stats() -> dict:
        """Get stats for the full AI Processing Architecture."""
        from .ai_task_classifier import AITaskClassifier
        from .ai_pipelines import get_all_pipeline_stats
        from .ai_validation import AIOutputValidator
        from .intelligence_loop import ContinuousIntelligenceLoop

        return {
            "orchestrator": {
                "cache": _cache.stats(),
                "costs": _cost_tracker.get_stats(),
                "queue": _task_queue.stats(),
            },
            "classifier": AITaskClassifier.stats(),
            "pipelines": get_all_pipeline_stats(),
            "validation": AIOutputValidator.stats(),
            "intelligence_loop": ContinuousIntelligenceLoop.get_loop_stats(),
        }

    @staticmethod
    def clear_cache():
        _cache.clear()
