"""
Distributed Tracer — Observability Pillar 3: Traces
═══════════════════════════════════════════════════════
Follows one request across the entire multi-stage system:

  User → API → DB → Queue → AI → Cache → Dashboard

Every request gets a trace_id. Each stage creates a span.
When something is slow, tracing pinpoints the exact bottleneck.

Trace Example:
  Request R123:
    API Gateway:    120ms
    DB Write:        30ms
    Queue Wait:    4000ms  ⚠ bottleneck
    AI Processing: 8000ms
    Cache Fetch:     60ms
"""

import time
import uuid
import threading
from collections import deque, defaultdict
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import contextmanager


class Span:
    """A single span within a trace — represents one stage of processing."""

    def __init__(
        self,
        trace_id: str,
        name: str,
        parent_span_id: Optional[str] = None,
        service: str = "backend",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.span_id = str(uuid.uuid4())[:12]
        self.trace_id = trace_id
        self.name = name
        self.parent_span_id = parent_span_id
        self.service = service
        self.metadata = metadata or {}
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration_ms: Optional[float] = None
        self.status = "in_progress"
        self.error: Optional[str] = None
        self.tags: Dict[str, str] = {}
        self.events: List[dict] = []

    def add_tag(self, key: str, value: str):
        """Add a tag to the span for filtering."""
        self.tags[key] = value

    def add_event(self, name: str, data: Optional[dict] = None):
        """Add an event (annotation) within the span."""
        self.events.append({
            "name": name,
            "timestamp": datetime.now().isoformat(),
            "data": data or {},
        })

    def finish(self, error: Optional[str] = None):
        """Mark the span as completed."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = "error" if error else "ok"
        self.error = error

    def to_dict(self) -> dict:
        result = {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "name": self.name,
            "service": self.service,
            "status": self.status,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "tags": self.tags,
        }
        if self.parent_span_id:
            result["parent_span_id"] = self.parent_span_id
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        if self.events:
            result["events"] = self.events
        return result


class Trace:
    """A complete trace — represents one end-to-end request lifecycle."""

    def __init__(self, trace_id: str, root_endpoint: str = "", user_id: Optional[int] = None):
        self.trace_id = trace_id
        self.root_endpoint = root_endpoint
        self.user_id = user_id
        self.created_at = datetime.now().isoformat()
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.total_duration_ms: Optional[float] = None
        self.spans: List[Span] = []
        self.status = "active"
        self.bottleneck_span: Optional[str] = None

    def add_span(self, span: Span):
        """Add a span to this trace."""
        self.spans.append(span)

    def finish(self):
        """Finalize the trace and detect bottleneck."""
        self.end_time = time.time()
        self.total_duration_ms = (self.end_time - self.start_time) * 1000

        # Find bottleneck (slowest span)
        if self.spans:
            slowest = max(self.spans, key=lambda s: s.duration_ms or 0)
            if slowest.duration_ms and slowest.duration_ms > 0:
                self.bottleneck_span = slowest.name

        has_error = any(s.status == "error" for s in self.spans)
        self.status = "error" if has_error else "completed"

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "root_endpoint": self.root_endpoint,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "status": self.status,
            "total_duration_ms": round(self.total_duration_ms, 2) if self.total_duration_ms else None,
            "bottleneck": self.bottleneck_span,
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans],
        }


class DistributedTracer:
    """
    Distributed tracing engine for the AI Survey Platform.

    Features:
    - Automatic trace ID generation per request
    - Nested span tracking (parent/child relationships)
    - Bottleneck detection across multi-stage pipeline
    - Latency percentile analysis per span type
    - Context manager for easy span creation
    - Service-level aggregation
    """

    def __init__(self, max_traces: int = 5000):
        self._lock = threading.RLock()
        self._max_traces = max_traces
        self._traces: deque = deque(maxlen=max_traces)
        self._active_traces: Dict[str, Trace] = {}
        self._trace_index: Dict[str, Trace] = {}

        # Performance analytics
        self._span_latencies: Dict[str, List[float]] = defaultdict(lambda: deque(maxlen=500))
        self._service_latencies: Dict[str, List[float]] = defaultdict(lambda: deque(maxlen=500))
        self._total_traces = 0
        self._total_spans = 0
        self._error_traces = 0
        self._bottleneck_counts: Dict[str, int] = defaultdict(int)
        self._start_time = time.time()

    # ── Trace Lifecycle ──

    def start_trace(self, endpoint: str = "", user_id: Optional[int] = None) -> str:
        """Start a new distributed trace. Returns trace_id."""
        trace_id = str(uuid.uuid4())
        trace = Trace(trace_id, endpoint, user_id)

        with self._lock:
            self._active_traces[trace_id] = trace
            self._trace_index[trace_id] = trace
            self._total_traces += 1

        return trace_id

    def finish_trace(self, trace_id: str):
        """Complete a trace and archive it."""
        with self._lock:
            trace = self._active_traces.pop(trace_id, None)
            if not trace:
                return

            trace.finish()
            self._traces.append(trace)

            if trace.status == "error":
                self._error_traces += 1

            if trace.bottleneck_span:
                self._bottleneck_counts[trace.bottleneck_span] += 1

    # ── Span Lifecycle ──

    def start_span(
        self,
        trace_id: str,
        name: str,
        parent_span_id: Optional[str] = None,
        service: str = "backend",
        metadata: Optional[dict] = None,
    ) -> Optional[Span]:
        """Create and start a new span within a trace."""
        with self._lock:
            trace = self._active_traces.get(trace_id) or self._trace_index.get(trace_id)
            if not trace:
                return None

            span = Span(trace_id, name, parent_span_id, service, metadata)
            trace.add_span(span)
            self._total_spans += 1
            return span

    def finish_span(self, span: Span, error: Optional[str] = None):
        """Complete a span and record its latency."""
        if not span:
            return
        span.finish(error)

        with self._lock:
            if span.duration_ms is not None:
                self._span_latencies[span.name].append(span.duration_ms)
                self._service_latencies[span.service].append(span.duration_ms)

    @contextmanager
    def span(self, trace_id: str, name: str, service: str = "backend", **kwargs):
        """Context manager for automatic span lifecycle."""
        s = self.start_span(trace_id, name, service=service, **kwargs)
        try:
            yield s
        except Exception as e:
            if s:
                self.finish_span(s, error=str(e))
            raise
        else:
            if s:
                self.finish_span(s)

    # ── Query Methods ──

    def get_trace(self, trace_id: str) -> Optional[dict]:
        """Get a trace by ID."""
        with self._lock:
            trace = self._trace_index.get(trace_id)
            return trace.to_dict() if trace else None

    def get_recent_traces(self, limit: int = 20, status: str = None) -> List[dict]:
        """Get recent completed traces with optional status filter."""
        with self._lock:
            traces = list(self._traces)

        if status:
            traces = [t for t in traces if t.status == status]

        traces = traces[-limit:]
        traces.reverse()
        return [t.to_dict() for t in traces]

    def get_slow_traces(self, threshold_ms: float = 5000, limit: int = 20) -> List[dict]:
        """Get traces that exceeded the given latency threshold."""
        with self._lock:
            slow = [
                t for t in self._traces
                if t.total_duration_ms and t.total_duration_ms > threshold_ms
            ]
        slow.sort(key=lambda t: t.total_duration_ms or 0, reverse=True)
        return [t.to_dict() for t in slow[:limit]]

    # ── Analytics ──

    def get_span_analytics(self) -> dict:
        """Get latency analytics per span type."""
        analytics = {}
        with self._lock:
            for name, latencies in self._span_latencies.items():
                lat_list = list(latencies)
                if not lat_list:
                    continue
                lat_list.sort()
                n = len(lat_list)
                analytics[name] = {
                    "count": n,
                    "avg_ms": round(sum(lat_list) / n, 2),
                    "min_ms": round(lat_list[0], 2),
                    "max_ms": round(lat_list[-1], 2),
                    "p50_ms": round(lat_list[n // 2], 2),
                    "p95_ms": round(lat_list[int(n * 0.95)], 2) if n >= 20 else None,
                    "p99_ms": round(lat_list[int(n * 0.99)], 2) if n >= 100 else None,
                }
        return analytics

    def get_service_analytics(self) -> dict:
        """Get latency analytics per service."""
        analytics = {}
        with self._lock:
            for service, latencies in self._service_latencies.items():
                lat_list = list(latencies)
                if not lat_list:
                    continue
                analytics[service] = {
                    "span_count": len(lat_list),
                    "avg_ms": round(sum(lat_list) / len(lat_list), 2),
                    "max_ms": round(max(lat_list), 2),
                }
        return analytics

    def get_bottleneck_ranking(self) -> List[dict]:
        """Get the most common bottleneck span types."""
        with self._lock:
            sorted_bottlenecks = sorted(
                self._bottleneck_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        return [{"span": name, "bottleneck_count": count} for name, count in sorted_bottlenecks]

    # ── Stats ──

    def stats(self) -> dict:
        uptime = time.time() - self._start_time
        with self._lock:
            return {
                "engine": "DistributedTracer",
                "total_traces": self._total_traces,
                "total_spans": self._total_spans,
                "active_traces": len(self._active_traces),
                "archived_traces": len(self._traces),
                "error_traces": self._error_traces,
                "error_rate": round(self._error_traces / max(self._total_traces, 1) * 100, 2),
                "uptime_seconds": round(uptime, 1),
                "traces_per_minute": round(self._total_traces / max(uptime / 60, 1), 2),
                "top_bottlenecks": [
                    {"span": n, "count": c}
                    for n, c in sorted(self._bottleneck_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                ],
                "span_types_tracked": len(self._span_latencies),
                "services_tracked": len(self._service_latencies),
            }


# ── Global Singleton ──
tracer = DistributedTracer()
