"""
Structured Logger — Observability Pillar 1: Logs
═══════════════════════════════════════════════════════
System Memory: Records everything happening in structured JSON format.

Log Categories:
  - User Events:   survey_created, interview_started, response_submitted, interview_abandoned
  - AI Events:     prompt_sent, model_used, response_time, token_usage, failure_reason
  - System Events: database_write, queue_delay, worker_restart, api_timeout, cache_hit/miss
  - Security Events: login_attempt, token_revoked, injection_blocked, role_changed

All logs are structured JSON — enabling filtering, analytics, and debugging automation.
"""

import time
import json
import threading
import uuid
from datetime import datetime
from collections import deque, defaultdict
from enum import Enum
from typing import Optional, Dict, Any, List


# ── Log Levels ──
class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ── Log Categories ──
class LogCategory(str, Enum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DATA = "data"
    BUSINESS = "business"


class StructuredLogEntry:
    """A single structured log entry with full context."""

    def __init__(
        self,
        event: str,
        level: LogLevel,
        category: LogCategory,
        message: str = "",
        data: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        user_id: Optional[int] = None,
        survey_id: Optional[int] = None,
        session_id: Optional[str] = None,
        source: str = "backend",
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
    ):
        self.id = str(uuid.uuid4())[:12]
        self.timestamp = datetime.now().isoformat()
        self.epoch = time.time()
        self.event = event
        self.level = level.value
        self.category = category.value
        self.message = message
        self.data = data or {}
        self.trace_id = trace_id
        self.span_id = span_id
        self.user_id = user_id
        self.survey_id = survey_id
        self.session_id = session_id
        self.source = source
        self.duration_ms = duration_ms
        self.error = error

    def to_dict(self) -> dict:
        entry = {
            "id": self.id,
            "timestamp": self.timestamp,
            "event": self.event,
            "level": self.level,
            "category": self.category,
            "message": self.message,
            "source": self.source,
        }
        if self.data:
            entry["data"] = self.data
        if self.trace_id:
            entry["trace_id"] = self.trace_id
        if self.span_id:
            entry["span_id"] = self.span_id
        if self.user_id is not None:
            entry["user_id"] = self.user_id
        if self.survey_id is not None:
            entry["survey_id"] = self.survey_id
        if self.session_id:
            entry["session_id"] = self.session_id
        if self.duration_ms is not None:
            entry["duration_ms"] = round(self.duration_ms, 2)
        if self.error:
            entry["error"] = self.error
        return entry

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class StructuredLogger:
    """
    Centralized structured logging engine.

    Features:
    - Structured JSON log entries with full context
    - In-memory ring buffer (configurable size)
    - Per-category and per-level indexing for fast queries
    - Log aggregation statistics
    - Recent log retrieval with filtering
    - Log rate tracking for anomaly detection
    """

    def __init__(self, max_entries: int = 10000):
        self._lock = threading.RLock()
        self._max_entries = max_entries
        self._logs: deque = deque(maxlen=max_entries)

        # Indexes for fast retrieval
        self._by_category: Dict[str, deque] = defaultdict(lambda: deque(maxlen=2000))
        self._by_level: Dict[str, deque] = defaultdict(lambda: deque(maxlen=2000))
        self._by_event: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))

        # Counters
        self._total_logged = 0
        self._counts_by_level: Dict[str, int] = defaultdict(int)
        self._counts_by_category: Dict[str, int] = defaultdict(int)
        self._counts_by_event: Dict[str, int] = defaultdict(int)
        self._error_events: deque = deque(maxlen=500)

        # Rate tracking (per-minute buckets)
        self._rate_buckets: Dict[str, int] = defaultdict(int)
        self._start_time = time.time()

    # ── Core Logging Methods ──

    def log(
        self,
        event: str,
        level: LogLevel = LogLevel.INFO,
        category: LogCategory = LogCategory.SYSTEM,
        message: str = "",
        **kwargs
    ) -> StructuredLogEntry:
        """Create and store a structured log entry."""
        entry = StructuredLogEntry(
            event=event,
            level=level,
            category=category,
            message=message,
            **kwargs
        )

        with self._lock:
            self._logs.append(entry)
            self._by_category[category.value].append(entry)
            self._by_level[level.value].append(entry)
            self._by_event[event].append(entry)

            self._total_logged += 1
            self._counts_by_level[level.value] += 1
            self._counts_by_category[category.value] += 1
            self._counts_by_event[event] += 1

            if level in (LogLevel.ERROR, LogLevel.CRITICAL):
                self._error_events.append(entry)

            # Rate bucket (per-minute)
            minute_key = str(int(time.time() / 60))
            self._rate_buckets[minute_key] += 1

        return entry

    # ── Convenience Methods for Each Category ──

    def user_event(self, event: str, message: str = "", **kwargs) -> StructuredLogEntry:
        """Log a user-triggered event (survey_created, interview_started, etc.)."""
        return self.log(event, LogLevel.INFO, LogCategory.USER, message, **kwargs)

    def ai_event(self, event: str, message: str = "", level: LogLevel = LogLevel.INFO, **kwargs) -> StructuredLogEntry:
        """Log an AI processing event (prompt_sent, model_used, etc.)."""
        return self.log(event, level, LogCategory.AI, message, **kwargs)

    def system_event(self, event: str, message: str = "", level: LogLevel = LogLevel.INFO, **kwargs) -> StructuredLogEntry:
        """Log a system event (database_write, queue_delay, etc.)."""
        return self.log(event, level, LogCategory.SYSTEM, message, **kwargs)

    def security_event(self, event: str, message: str = "", level: LogLevel = LogLevel.WARNING, **kwargs) -> StructuredLogEntry:
        """Log a security event (login_attempt, injection_blocked, etc.)."""
        return self.log(event, level, LogCategory.SECURITY, message, **kwargs)

    def performance_event(self, event: str, message: str = "", **kwargs) -> StructuredLogEntry:
        """Log a performance event (slow_query, timeout, etc.)."""
        return self.log(event, LogLevel.INFO, LogCategory.PERFORMANCE, message, **kwargs)

    def business_event(self, event: str, message: str = "", **kwargs) -> StructuredLogEntry:
        """Log a business-level event (insight_generated, report_created, etc.)."""
        return self.log(event, LogLevel.INFO, LogCategory.BUSINESS, message, **kwargs)

    def error(self, event: str, message: str = "", category: LogCategory = LogCategory.SYSTEM, **kwargs) -> StructuredLogEntry:
        """Log an error event."""
        return self.log(event, LogLevel.ERROR, category, message, **kwargs)

    def critical(self, event: str, message: str = "", category: LogCategory = LogCategory.SYSTEM, **kwargs) -> StructuredLogEntry:
        """Log a critical event."""
        return self.log(event, LogLevel.CRITICAL, category, message, **kwargs)

    # ── Query Methods ──

    def get_recent(self, limit: int = 50, category: str = None, level: str = None, event: str = None) -> List[dict]:
        """Get recent log entries with optional filtering."""
        with self._lock:
            if event and event in self._by_event:
                source = list(self._by_event[event])
            elif category and category in self._by_category:
                source = list(self._by_category[category])
            elif level and level in self._by_level:
                source = list(self._by_level[level])
            else:
                source = list(self._logs)

        # Return most recent first
        entries = source[-limit:]
        entries.reverse()
        return [e.to_dict() for e in entries]

    def get_errors(self, limit: int = 50) -> List[dict]:
        """Get recent error and critical log entries."""
        with self._lock:
            entries = list(self._error_events)[-limit:]
        entries.reverse()
        return [e.to_dict() for e in entries]

    def search(self, keyword: str, limit: int = 50) -> List[dict]:
        """Search logs by keyword in event name or message."""
        keyword_lower = keyword.lower()
        results = []
        with self._lock:
            for entry in reversed(self._logs):
                if keyword_lower in entry.event.lower() or keyword_lower in entry.message.lower():
                    results.append(entry.to_dict())
                    if len(results) >= limit:
                        break
        return results

    # ── Analytics ──

    def get_log_rate(self) -> dict:
        """Get logging rate per minute for the last 10 minutes."""
        now = int(time.time() / 60)
        rates = {}
        with self._lock:
            for i in range(10):
                minute_key = str(now - i)
                rates[f"minute_{i}_ago"] = self._rate_buckets.get(minute_key, 0)
        return rates

    def get_event_frequency(self, top_n: int = 20) -> List[dict]:
        """Get the most common event types."""
        with self._lock:
            sorted_events = sorted(
                self._counts_by_event.items(),
                key=lambda x: x[1],
                reverse=True
            )[:top_n]
        return [{"event": e, "count": c} for e, c in sorted_events]

    # ── Stats ──

    def stats(self) -> dict:
        """Full logger statistics."""
        uptime = time.time() - self._start_time
        with self._lock:
            return {
                "engine": "StructuredLogger",
                "total_logged": self._total_logged,
                "buffer_size": len(self._logs),
                "buffer_capacity": self._max_entries,
                "uptime_seconds": round(uptime, 1),
                "logs_per_minute": round(self._total_logged / max(uptime / 60, 1), 2),
                "by_level": dict(self._counts_by_level),
                "by_category": dict(self._counts_by_category),
                "error_count": self._counts_by_level.get("ERROR", 0) + self._counts_by_level.get("CRITICAL", 0),
                "unique_events": len(self._counts_by_event),
                "top_events": [
                    {"event": e, "count": c}
                    for e, c in sorted(self._counts_by_event.items(), key=lambda x: x[1], reverse=True)[:10]
                ],
            }


# ── Global Singleton ──
structured_logger = StructuredLogger()
