"""
Failure Analytics — Learning from Every Failure
═══════════════════════════════════════════════════════
Every failure becomes learning. System evolves continuously.

Tracks:
  - Failed AI prompts (why, which model, which template)
  - Incomplete clustering (data quality issues)
  - Transcription errors (AssemblyAI failures)
  - Pipeline stage failures
  - Retry patterns and recovery success
  - Failure correlation (time-of-day, load level, model)

Self-Improving Vision: Observability → Intelligence
  System detects: "Insight quality decreased after latest prompt update"
  → Recommends rollback
  (AI supervising AI)
"""

import time
import threading
import hashlib
from collections import deque, defaultdict
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum


class FailureCategory(str, Enum):
    AI_PROMPT = "ai_prompt"
    AI_TIMEOUT = "ai_timeout"
    AI_HALLUCINATION = "ai_hallucination"
    AI_QUALITY = "ai_quality"
    TRANSCRIPTION = "transcription"
    CLUSTERING = "clustering"
    PIPELINE = "pipeline"
    DATABASE = "database"
    VALIDATION = "validation"
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"


class FailureRecord:
    """A single recorded failure with full context."""

    def __init__(
        self,
        category: FailureCategory,
        error_message: str,
        component: str = "unknown",
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        survey_id: Optional[int] = None,
        session_id: Optional[str] = None,
        prompt_hash: Optional[str] = None,
        retry_count: int = 0,
        recovered: bool = False,
        context: Optional[dict] = None,
    ):
        self.timestamp = datetime.now().isoformat()
        self.epoch = time.time()
        self.category = category.value
        self.error_message = error_message[:500]
        self.component = component
        self.model = model
        self.task_type = task_type
        self.survey_id = survey_id
        self.session_id = session_id
        self.prompt_hash = prompt_hash
        self.retry_count = retry_count
        self.recovered = recovered
        self.context = context or {}
        # Fingerprint for deduplication
        self.fingerprint = hashlib.md5(
            f"{category.value}:{component}:{error_message[:100]}".encode()
        ).hexdigest()[:12]

    def to_dict(self) -> dict:
        d = {
            "timestamp": self.timestamp,
            "category": self.category,
            "error_message": self.error_message,
            "component": self.component,
            "fingerprint": self.fingerprint,
            "retry_count": self.retry_count,
            "recovered": self.recovered,
        }
        if self.model:
            d["model"] = self.model
        if self.task_type:
            d["task_type"] = self.task_type
        if self.survey_id is not None:
            d["survey_id"] = self.survey_id
        if self.session_id:
            d["session_id"] = self.session_id
        if self.prompt_hash:
            d["prompt_hash"] = self.prompt_hash
        if self.context:
            d["context"] = self.context
        return d


class FailureAnalytics:
    """
    Failure Analytics Engine — continuous learning from every failure.

    Features:
    - Failure classification by category and component
    - Error fingerprinting for deduplication and trending
    - Retry/recovery tracking
    - Failure rate per component, model, and task type
    - Time-based failure correlation (spike detection)
    - Top failure patterns for root cause analysis
    - Recommendations based on failure patterns
    """

    def __init__(self, max_records: int = 5000):
        self._lock = threading.RLock()
        self._records: deque = deque(maxlen=max_records)

        # Category counts
        self._by_category: Dict[str, int] = defaultdict(int)
        self._by_component: Dict[str, int] = defaultdict(int)
        self._by_model: Dict[str, int] = defaultdict(int)
        self._by_task: Dict[str, int] = defaultdict(int)

        # Fingerprint tracking (unique error patterns)
        self._fingerprint_counts: Dict[str, int] = defaultdict(int)
        self._fingerprint_samples: Dict[str, FailureRecord] = {}

        # Recovery tracking
        self._total_failures = 0
        self._total_retries = 0
        self._total_recovered = 0

        # Time-based tracking (per-minute buckets)
        self._minute_buckets: Dict[str, int] = defaultdict(int)

        self._start_time = time.time()

    def record_failure(
        self,
        category: FailureCategory,
        error_message: str,
        component: str = "unknown",
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        survey_id: Optional[int] = None,
        session_id: Optional[str] = None,
        prompt_hash: Optional[str] = None,
        retry_count: int = 0,
        recovered: bool = False,
        context: Optional[dict] = None,
    ):
        """Record a failure event."""
        record = FailureRecord(
            category=category, error_message=error_message, component=component,
            model=model, task_type=task_type, survey_id=survey_id,
            session_id=session_id, prompt_hash=prompt_hash,
            retry_count=retry_count, recovered=recovered, context=context,
        )

        with self._lock:
            self._records.append(record)
            self._total_failures += 1
            self._total_retries += retry_count
            if recovered:
                self._total_recovered += 1

            self._by_category[category.value] += 1
            self._by_component[component] += 1
            if model:
                self._by_model[model] += 1
            if task_type:
                self._by_task[task_type] += 1

            # Fingerprint tracking
            self._fingerprint_counts[record.fingerprint] += 1
            if record.fingerprint not in self._fingerprint_samples:
                self._fingerprint_samples[record.fingerprint] = record

            # Time bucket
            minute_key = str(int(time.time() / 60))
            self._minute_buckets[minute_key] += 1

    # ── Query Methods ──

    def get_recent_failures(self, limit: int = 30, category: str = None) -> List[dict]:
        """Get recent failure records with optional category filter."""
        with self._lock:
            records = list(self._records)
        if category:
            records = [r for r in records if r.category == category]
        records = records[-limit:]
        records.reverse()
        return [r.to_dict() for r in records]

    def get_top_errors(self, limit: int = 20) -> List[dict]:
        """Get the most frequent unique error patterns."""
        with self._lock:
            sorted_fps = sorted(
                self._fingerprint_counts.items(),
                key=lambda x: x[1], reverse=True
            )[:limit]

        results = []
        for fp, count in sorted_fps:
            sample = self._fingerprint_samples.get(fp)
            results.append({
                "fingerprint": fp,
                "count": count,
                "category": sample.category if sample else "unknown",
                "component": sample.component if sample else "unknown",
                "error_preview": sample.error_message[:100] if sample else "",
                "model": sample.model if sample else None,
            })
        return results

    def get_category_breakdown(self) -> dict:
        """Get failure count per category."""
        with self._lock:
            total = self._total_failures
            return {
                cat: {
                    "count": count,
                    "percentage": round(count / max(total, 1) * 100, 2),
                }
                for cat, count in sorted(
                    self._by_category.items(), key=lambda x: x[1], reverse=True
                )
            }

    def get_component_breakdown(self) -> dict:
        """Get failure count per component."""
        with self._lock:
            return dict(
                sorted(self._by_component.items(), key=lambda x: x[1], reverse=True)
            )

    def get_model_failure_rates(self) -> dict:
        """Get failure counts per AI model."""
        with self._lock:
            return dict(
                sorted(self._by_model.items(), key=lambda x: x[1], reverse=True)
            )

    def get_failure_rate_trend(self) -> dict:
        """Get failure rate per minute for the last 10 minutes."""
        now = int(time.time() / 60)
        trend = {}
        with self._lock:
            for i in range(10):
                key = str(now - i)
                trend[f"minute_{i}_ago"] = self._minute_buckets.get(key, 0)
        return trend

    def detect_spike(self, window_minutes: int = 5, threshold_multiplier: float = 3.0) -> dict:
        """Detect if current failure rate is anomalously high."""
        now = int(time.time() / 60)
        with self._lock:
            # Recent window
            recent = sum(
                self._minute_buckets.get(str(now - i), 0)
                for i in range(window_minutes)
            )
            # Historical baseline (prior 30 minutes)
            historical = sum(
                self._minute_buckets.get(str(now - window_minutes - i), 0)
                for i in range(30)
            )
            baseline_per_window = (historical / 6) if historical > 0 else 1

        is_spike = recent > (baseline_per_window * threshold_multiplier) and recent > 5
        return {
            "spike_detected": is_spike,
            "recent_failures": recent,
            "baseline_per_window": round(baseline_per_window, 1),
            "window_minutes": window_minutes,
            "multiplier": threshold_multiplier,
        }

    def get_recommendations(self) -> List[dict]:
        """Generate recommendations based on failure patterns."""
        recommendations = []
        with self._lock:
            total = self._total_failures

            # High AI failure rate
            ai_failures = self._by_category.get("ai_prompt", 0) + self._by_category.get("ai_timeout", 0)
            if ai_failures > total * 0.3 and ai_failures > 5:
                recommendations.append({
                    "priority": "high",
                    "category": "ai",
                    "recommendation": "AI failure rate is high. Consider prompt optimization or model fallback.",
                    "metric": f"{ai_failures}/{total} failures are AI-related",
                })

            # High hallucination rate
            hallucinations = self._by_category.get("ai_hallucination", 0)
            if hallucinations > 3:
                recommendations.append({
                    "priority": "high",
                    "category": "ai_quality",
                    "recommendation": "Hallucinations detected. Review prompt templates and add output validation.",
                    "metric": f"{hallucinations} hallucination events",
                })

            # Transcription failures
            transcription = self._by_category.get("transcription", 0)
            if transcription > total * 0.1 and transcription > 3:
                recommendations.append({
                    "priority": "medium",
                    "category": "voice",
                    "recommendation": "Transcription failures are significant. Check audio quality and AssemblyAI limits.",
                    "metric": f"{transcription} transcription failures",
                })

            # Low recovery rate
            if self._total_failures > 10 and self._total_recovered < self._total_failures * 0.5:
                recommendations.append({
                    "priority": "medium",
                    "category": "resilience",
                    "recommendation": "Recovery rate is low. Improve retry logic and fallback mechanisms.",
                    "metric": f"{self._total_recovered}/{self._total_failures} recovered",
                })

        if not recommendations:
            recommendations.append({
                "priority": "info",
                "category": "system",
                "recommendation": "No significant failure patterns detected. System is healthy.",
                "metric": f"{total} total failures recorded",
            })

        return recommendations

    # ── Stats ──

    def stats(self) -> dict:
        uptime = time.time() - self._start_time
        with self._lock:
            return {
                "engine": "FailureAnalytics",
                "total_failures": self._total_failures,
                "total_retries": self._total_retries,
                "total_recovered": self._total_recovered,
                "recovery_rate": round(self._total_recovered / max(self._total_failures, 1) * 100, 2),
                "unique_error_patterns": len(self._fingerprint_counts),
                "categories_seen": len(self._by_category),
                "components_affected": len(self._by_component),
                "models_with_failures": len(self._by_model),
                "spike_status": self.detect_spike(),
                "uptime_seconds": round(uptime, 1),
                "failures_per_hour": round(self._total_failures / max(uptime / 3600, 1), 2),
            }


# ── Global Singleton ──
failure_analytics = FailureAnalytics()
