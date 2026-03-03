"""
Metrics Service — Observability Architecture Layer
═══════════════════════════════════════════════════════
Tracks both system metrics and product metrics:

System Metrics:
  - Response latency (per endpoint)
  - AI processing time
  - API errors (count, type)
  - Request throughput

Product Metrics:
  - Survey completion rate
  - Dropout point analysis
  - Engagement level tracking
  - Channel performance comparison

Architecture: "You can't improve what you can't measure"
"""
import time
import threading
from collections import defaultdict
from datetime import datetime
from ..database import get_db


class MetricsCollector:
    """Thread-safe metrics collector for system and product metrics."""

    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.time()

        # ── System Metrics ──
        self.request_count = 0
        self.error_count = 0
        self.latency_sum = 0.0
        self.latency_count = 0
        self.latency_by_endpoint: dict = defaultdict(lambda: {"sum": 0.0, "count": 0, "max": 0.0})
        self.errors_by_type: dict = defaultdict(int)
        self.status_codes: dict = defaultdict(int)

        # ── AI Processing Metrics ──
        self.ai_calls = 0
        self.ai_latency_sum = 0.0
        self.ai_errors = 0
        self.ai_latency_by_task: dict = defaultdict(lambda: {"sum": 0.0, "count": 0, "max": 0.0})

    def record_request(self, endpoint: str, latency_ms: float, status_code: int):
        """Record an API request."""
        with self._lock:
            self.request_count += 1
            self.latency_sum += latency_ms
            self.latency_count += 1

            ep = self.latency_by_endpoint[endpoint]
            ep["sum"] += latency_ms
            ep["count"] += 1
            ep["max"] = max(ep["max"], latency_ms)

            self.status_codes[str(status_code)] += 1
            if status_code >= 400:
                self.error_count += 1

    def record_error(self, error_type: str):
        with self._lock:
            self.error_count += 1
            self.errors_by_type[error_type] += 1

    def record_ai_call(self, task_type: str, latency_ms: float, success: bool):
        with self._lock:
            self.ai_calls += 1
            self.ai_latency_sum += latency_ms
            if not success:
                self.ai_errors += 1

            at = self.ai_latency_by_task[task_type]
            at["sum"] += latency_ms
            at["count"] += 1
            at["max"] = max(at["max"], latency_ms)

    def get_system_metrics(self) -> dict:
        uptime = time.time() - self._start_time
        avg_latency = self.latency_sum / max(self.latency_count, 1)
        avg_ai_latency = self.ai_latency_sum / max(self.ai_calls, 1)

        # Per-endpoint averages
        endpoint_stats = {}
        for ep, data in self.latency_by_endpoint.items():
            endpoint_stats[ep] = {
                "avg_latency_ms": round(data["sum"] / max(data["count"], 1), 1),
                "max_latency_ms": round(data["max"], 1),
                "request_count": data["count"],
            }

        # Per-AI-task averages
        ai_task_stats = {}
        for task, data in self.ai_latency_by_task.items():
            ai_task_stats[task] = {
                "avg_latency_ms": round(data["sum"] / max(data["count"], 1), 1),
                "max_latency_ms": round(data["max"], 1),
                "call_count": data["count"],
            }

        return {
            "uptime_seconds": round(uptime, 1),
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate": round(self.error_count / max(self.request_count, 1) * 100, 2),
            "avg_latency_ms": round(avg_latency, 1),
            "requests_per_minute": round(self.request_count / max(uptime / 60, 1), 1),
            "status_codes": dict(self.status_codes),
            "errors_by_type": dict(self.errors_by_type),
            "endpoint_stats": endpoint_stats,
            "ai_metrics": {
                "total_calls": self.ai_calls,
                "total_errors": self.ai_errors,
                "avg_latency_ms": round(avg_ai_latency, 1),
                "by_task": ai_task_stats,
            }
        }


# Global singleton
_metrics = MetricsCollector()


class MetricsService:
    """Public API for metrics collection and retrieval."""

    @staticmethod
    def record_request(endpoint: str, latency_ms: float, status_code: int):
        _metrics.record_request(endpoint, latency_ms, status_code)

    @staticmethod
    def record_error(error_type: str):
        _metrics.record_error(error_type)

    @staticmethod
    def record_ai_call(task_type: str, latency_ms: float, success: bool):
        _metrics.record_ai_call(task_type, latency_ms, success)

    @staticmethod
    def get_system_metrics() -> dict:
        return _metrics.get_system_metrics()

    @staticmethod
    def get_product_metrics(survey_id: int = None) -> dict:
        """Get product-level metrics from the database."""
        conn = get_db()

        if survey_id:
            # Survey-specific metrics
            survey = conn.execute("SELECT * FROM surveys WHERE id = ?", (survey_id,)).fetchone()
            sessions = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                       AVG(completion_percentage) as avg_completion,
                       AVG(engagement_score) as avg_engagement
                FROM interview_sessions WHERE survey_id = ?
            """, (survey_id,)).fetchone()

            # Dropout analysis: which questions have lowest response rates
            questions = conn.execute("""
                SELECT q.id, q.question_text, q.order_index,
                       COUNT(r.id) as response_count
                FROM questions q
                LEFT JOIN responses r ON r.question_id = q.id
                WHERE q.survey_id = ?
                GROUP BY q.id
                ORDER BY q.order_index
            """, (survey_id,)).fetchall()

            # Channel breakdown
            channels = conn.execute("""
                SELECT channel, COUNT(*) as sessions,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                FROM interview_sessions WHERE survey_id = ?
                GROUP BY channel
            """, (survey_id,)).fetchall()

            conn.close()
            sd = dict(sessions) if sessions else {}

            total = sd.get("total", 0) or 0
            completed = sd.get("completed", 0) or 0

            return {
                "survey_id": survey_id,
                "total_sessions": total,
                "completed_sessions": completed,
                "completion_rate": round(completed / max(total, 1) * 100, 1),
                "avg_completion_percentage": round(sd.get("avg_completion", 0) or 0, 1),
                "avg_engagement_score": round(sd.get("avg_engagement", 0) or 0, 3),
                "dropout_analysis": [
                    {
                        "question_id": dict(q)["id"],
                        "question": dict(q)["question_text"][:80],
                        "order": dict(q)["order_index"],
                        "responses": dict(q)["response_count"],
                    }
                    for q in questions
                ],
                "channel_breakdown": [
                    {
                        "channel": dict(c)["channel"],
                        "sessions": dict(c)["sessions"],
                        "completed": dict(c)["completed"],
                        "rate": round(dict(c)["completed"] / max(dict(c)["sessions"], 1) * 100, 1),
                    }
                    for c in channels
                ],
            }
        else:
            # Global product metrics
            total_surveys = conn.execute("SELECT COUNT(*) as c FROM surveys").fetchone()
            total_responses = conn.execute("SELECT COUNT(*) as c FROM responses").fetchone()
            total_sessions = conn.execute("SELECT COUNT(*) as c FROM interview_sessions").fetchone()
            total_insights = conn.execute("SELECT COUNT(*) as c FROM insights").fetchone()
            conn.close()

            return {
                "total_surveys": dict(total_surveys)["c"],
                "total_responses": dict(total_responses)["c"],
                "total_sessions": dict(total_sessions)["c"],
                "total_insights": dict(total_insights)["c"],
            }

    @staticmethod
    def get_full_dashboard() -> dict:
        """Combined system + product metrics for the observability dashboard."""
        return {
            "system": MetricsService.get_system_metrics(),
            "product": MetricsService.get_product_metrics(),
            "timestamp": datetime.now().isoformat(),
        }
