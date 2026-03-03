"""
AI Observability — Next-Gen AI Monitoring
═══════════════════════════════════════════════════════
Traditional monitoring is insufficient for AI systems.

Tracks:
  - Model Behavior:      prompt version, response quality, reasoning length, confidence, failure patterns
  - Prompt Versioning:   v1 → 65% satisfaction, v2 → 82% satisfaction → prompts become measurable assets
  - Quality Scoring:     hallucination flags, coherence, relevance, completeness
  - Performance Drift:   model speed degradation, accuracy changes over time

AI becomes improvable engineering, not magic.
"""

import time
import threading
import hashlib
from collections import deque, defaultdict
from datetime import datetime
from typing import Optional, Dict, Any, List


class PromptVersion:
    """Tracks a specific prompt version and its effectiveness."""

    def __init__(self, prompt_hash: str, task_type: str, template_preview: str = ""):
        self.prompt_hash = prompt_hash
        self.task_type = task_type
        self.template_preview = template_preview[:200]
        self.created_at = datetime.now().isoformat()
        self.total_uses = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_quality_score = 0.0
        self.total_latency_ms = 0.0
        self.total_tokens = 0
        self.hallucination_flags = 0
        self.satisfaction_scores: List[float] = []

    def record_use(self, success: bool, quality_score: float = 0.0, latency_ms: float = 0.0,
                   tokens: int = 0, hallucination: bool = False, satisfaction: float = None):
        self.total_uses += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.total_quality_score += quality_score
        self.total_latency_ms += latency_ms
        self.total_tokens += tokens
        if hallucination:
            self.hallucination_flags += 1
        if satisfaction is not None:
            self.satisfaction_scores.append(satisfaction)

    def to_dict(self) -> dict:
        avg_quality = self.total_quality_score / max(self.total_uses, 1)
        avg_latency = self.total_latency_ms / max(self.total_uses, 1)
        avg_satisfaction = (
            sum(self.satisfaction_scores) / len(self.satisfaction_scores)
            if self.satisfaction_scores else None
        )
        return {
            "prompt_hash": self.prompt_hash,
            "task_type": self.task_type,
            "template_preview": self.template_preview,
            "created_at": self.created_at,
            "total_uses": self.total_uses,
            "success_rate": round(self.success_count / max(self.total_uses, 1) * 100, 2),
            "failure_count": self.failure_count,
            "avg_quality_score": round(avg_quality, 3),
            "avg_latency_ms": round(avg_latency, 1),
            "total_tokens": self.total_tokens,
            "avg_tokens_per_use": round(self.total_tokens / max(self.total_uses, 1), 1),
            "hallucination_rate": round(self.hallucination_flags / max(self.total_uses, 1) * 100, 2),
            "avg_satisfaction": round(avg_satisfaction, 3) if avg_satisfaction else None,
        }


class ModelBehaviorRecord:
    """Tracks a single AI model call and its observed behavior."""

    def __init__(
        self,
        model: str,
        task_type: str,
        prompt_hash: str,
        latency_ms: float,
        tokens_in: int = 0,
        tokens_out: int = 0,
        success: bool = True,
        quality_score: float = 0.0,
        confidence: float = 0.0,
        reasoning_length: int = 0,
        hallucination_flag: bool = False,
        failure_reason: Optional[str] = None,
    ):
        self.timestamp = datetime.now().isoformat()
        self.epoch = time.time()
        self.model = model
        self.task_type = task_type
        self.prompt_hash = prompt_hash
        self.latency_ms = latency_ms
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.total_tokens = tokens_in + tokens_out
        self.success = success
        self.quality_score = quality_score
        self.confidence = confidence
        self.reasoning_length = reasoning_length
        self.hallucination_flag = hallucination_flag
        self.failure_reason = failure_reason

    def to_dict(self) -> dict:
        d = {
            "timestamp": self.timestamp,
            "model": self.model,
            "task_type": self.task_type,
            "prompt_hash": self.prompt_hash,
            "latency_ms": round(self.latency_ms, 1),
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "total_tokens": self.total_tokens,
            "success": self.success,
            "quality_score": round(self.quality_score, 3),
            "confidence": round(self.confidence, 3),
            "reasoning_length": self.reasoning_length,
            "hallucination_flag": self.hallucination_flag,
        }
        if self.failure_reason:
            d["failure_reason"] = self.failure_reason
        return d


class AIObserver:
    """
    AI Observability Engine — monitors model behavior, prompt effectiveness, and quality.

    Features:
    - Per-model performance tracking (latency, tokens, success rate)
    - Prompt version effectiveness measurement
    - Hallucination detection rate
    - Confidence score distribution
    - Quality drift detection (comparing recent vs historical quality)
    - Failure pattern analysis
    - AI cost correlation per task type
    """

    def __init__(self, max_records: int = 5000):
        self._lock = threading.RLock()
        self._records: deque = deque(maxlen=max_records)
        self._prompt_versions: Dict[str, PromptVersion] = {}

        # Model-level aggregation
        self._model_stats: Dict[str, dict] = defaultdict(lambda: {
            "calls": 0, "successes": 0, "failures": 0,
            "total_latency": 0.0, "total_tokens": 0,
            "hallucinations": 0, "total_quality": 0.0,
        })

        # Task-level aggregation
        self._task_stats: Dict[str, dict] = defaultdict(lambda: {
            "calls": 0, "successes": 0, "failures": 0,
            "total_latency": 0.0, "total_tokens": 0,
            "total_quality": 0.0,
        })

        # Failure patterns
        self._failure_patterns: Dict[str, int] = defaultdict(int)
        self._failure_history: deque = deque(maxlen=200)

        # Quality drift detection
        self._quality_window_recent: deque = deque(maxlen=100)  # last 100
        self._quality_window_historical: deque = deque(maxlen=1000)  # last 1000

        self._total_calls = 0
        self._start_time = time.time()

    @staticmethod
    def hash_prompt(template: str) -> str:
        """Generate a deterministic hash for a prompt template."""
        return hashlib.sha256(template.encode()).hexdigest()[:16]

    def record_ai_call(
        self,
        model: str,
        task_type: str,
        prompt_template: str = "",
        latency_ms: float = 0.0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        success: bool = True,
        quality_score: float = 0.0,
        confidence: float = 0.0,
        reasoning_length: int = 0,
        hallucination_flag: bool = False,
        failure_reason: Optional[str] = None,
        satisfaction: Optional[float] = None,
    ):
        """Record a single AI model call with full observability data."""
        prompt_hash = self.hash_prompt(prompt_template) if prompt_template else "unknown"

        record = ModelBehaviorRecord(
            model=model,
            task_type=task_type,
            prompt_hash=prompt_hash,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            success=success,
            quality_score=quality_score,
            confidence=confidence,
            reasoning_length=reasoning_length,
            hallucination_flag=hallucination_flag,
            failure_reason=failure_reason,
        )

        with self._lock:
            self._records.append(record)
            self._total_calls += 1

            # Model stats
            ms = self._model_stats[model]
            ms["calls"] += 1
            ms["total_latency"] += latency_ms
            ms["total_tokens"] += tokens_in + tokens_out
            ms["total_quality"] += quality_score
            if success:
                ms["successes"] += 1
            else:
                ms["failures"] += 1
            if hallucination_flag:
                ms["hallucinations"] += 1

            # Task stats
            ts = self._task_stats[task_type]
            ts["calls"] += 1
            ts["total_latency"] += latency_ms
            ts["total_tokens"] += tokens_in + tokens_out
            ts["total_quality"] += quality_score
            if success:
                ts["successes"] += 1
            else:
                ts["failures"] += 1

            # Prompt version tracking
            if prompt_hash not in self._prompt_versions:
                self._prompt_versions[prompt_hash] = PromptVersion(
                    prompt_hash, task_type, prompt_template
                )
            self._prompt_versions[prompt_hash].record_use(
                success, quality_score, latency_ms,
                tokens_in + tokens_out, hallucination_flag, satisfaction
            )

            # Failure tracking
            if not success and failure_reason:
                pattern_key = f"{model}:{task_type}:{failure_reason}"
                self._failure_patterns[pattern_key] += 1
                self._failure_history.append(record)

            # Quality drift
            self._quality_window_recent.append(quality_score)
            self._quality_window_historical.append(quality_score)

    def get_model_comparison(self) -> dict:
        """Compare performance across all models."""
        comparison = {}
        with self._lock:
            for model, ms in self._model_stats.items():
                calls = ms["calls"]
                comparison[model] = {
                    "total_calls": calls,
                    "success_rate": round(ms["successes"] / max(calls, 1) * 100, 2),
                    "avg_latency_ms": round(ms["total_latency"] / max(calls, 1), 1),
                    "avg_quality": round(ms["total_quality"] / max(calls, 1), 3),
                    "total_tokens": ms["total_tokens"],
                    "avg_tokens_per_call": round(ms["total_tokens"] / max(calls, 1), 1),
                    "hallucination_rate": round(ms["hallucinations"] / max(calls, 1) * 100, 2),
                }
        return comparison

    def get_task_analysis(self) -> dict:
        """Analyze AI performance per task type."""
        analysis = {}
        with self._lock:
            for task, ts in self._task_stats.items():
                calls = ts["calls"]
                analysis[task] = {
                    "total_calls": calls,
                    "success_rate": round(ts["successes"] / max(calls, 1) * 100, 2),
                    "avg_latency_ms": round(ts["total_latency"] / max(calls, 1), 1),
                    "avg_quality": round(ts["total_quality"] / max(calls, 1), 3),
                    "total_tokens": ts["total_tokens"],
                }
        return analysis

    def get_prompt_versions(self, task_type: str = None) -> List[dict]:
        """Get prompt version effectiveness data."""
        with self._lock:
            versions = list(self._prompt_versions.values())
        if task_type:
            versions = [v for v in versions if v.task_type == task_type]
        versions.sort(key=lambda v: v.total_uses, reverse=True)
        return [v.to_dict() for v in versions[:50]]

    def get_quality_drift(self) -> dict:
        """Detect quality drift by comparing recent vs historical quality scores."""
        with self._lock:
            recent = list(self._quality_window_recent)
            historical = list(self._quality_window_historical)

        if not recent or not historical:
            return {"drift_detected": False, "message": "Insufficient data"}

        recent_avg = sum(recent) / len(recent)
        historical_avg = sum(historical) / len(historical)
        drift = recent_avg - historical_avg
        drift_pct = (drift / max(abs(historical_avg), 0.01)) * 100

        return {
            "drift_detected": abs(drift_pct) > 10,
            "recent_avg_quality": round(recent_avg, 3),
            "historical_avg_quality": round(historical_avg, 3),
            "drift_absolute": round(drift, 3),
            "drift_percentage": round(drift_pct, 2),
            "recent_sample_size": len(recent),
            "historical_sample_size": len(historical),
            "recommendation": (
                "Quality improved" if drift > 0.05
                else "Quality degraded — consider prompt rollback" if drift < -0.05
                else "Quality stable"
            ),
        }

    def get_failure_patterns(self) -> List[dict]:
        """Get the most common AI failure patterns."""
        with self._lock:
            sorted_patterns = sorted(
                self._failure_patterns.items(),
                key=lambda x: x[1], reverse=True
            )
        results = []
        for pattern_key, count in sorted_patterns[:20]:
            parts = pattern_key.split(":", 2)
            results.append({
                "model": parts[0] if len(parts) > 0 else "unknown",
                "task_type": parts[1] if len(parts) > 1 else "unknown",
                "failure_reason": parts[2] if len(parts) > 2 else "unknown",
                "count": count,
            })
        return results

    def get_recent_calls(self, limit: int = 30, model: str = None, task_type: str = None) -> List[dict]:
        """Get recent AI call records with optional filtering."""
        with self._lock:
            records = list(self._records)
        if model:
            records = [r for r in records if r.model == model]
        if task_type:
            records = [r for r in records if r.task_type == task_type]
        records = records[-limit:]
        records.reverse()
        return [r.to_dict() for r in records]

    def stats(self) -> dict:
        uptime = time.time() - self._start_time
        with self._lock:
            total_hallucinations = sum(ms["hallucinations"] for ms in self._model_stats.values())
            total_failures = sum(ms["failures"] for ms in self._model_stats.values())
            return {
                "engine": "AIObserver",
                "total_ai_calls": self._total_calls,
                "models_tracked": len(self._model_stats),
                "task_types_tracked": len(self._task_stats),
                "prompt_versions_tracked": len(self._prompt_versions),
                "total_failures": total_failures,
                "total_hallucinations": total_hallucinations,
                "failure_rate": round(total_failures / max(self._total_calls, 1) * 100, 2),
                "hallucination_rate": round(total_hallucinations / max(self._total_calls, 1) * 100, 2),
                "uptime_seconds": round(uptime, 1),
                "calls_per_minute": round(self._total_calls / max(uptime / 60, 1), 2),
                "quality_drift": self.get_quality_drift(),
            }


# ── Global Singleton ──
ai_observer = AIObserver()
