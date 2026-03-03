"""
Dashboard Aggregator — Real-Time Operational Dashboard
═══════════════════════════════════════════════════════
Founder must open ONE dashboard and see everything:

  System Panel:  API uptime, DB latency, queue size
  AI Panel:      Gemini latency, AssemblyAI success rate, processing backlog
  User Panel:    Active interviews, completion rate, feedback volume
  Business Panel: Insights generated today, surveys active, engagement trend
  Cost Panel:    Daily spend, budget status, cost per interview

Aggregates all observability pillars into a unified view.
Also implements the Observability Data Pipeline:
  Application Events → Telemetry Collector → Logs + Metrics + Traces
    → Storage Engine → Visualization Dashboard → Alerts
"""

import time
import threading
from datetime import datetime
from typing import Optional


class DashboardAggregator:
    """
    Unified Real-Time Operational Dashboard.

    Aggregates data from all observability engines:
    - StructuredLogger (logs)
    - DistributedTracer (traces)
    - AIObserver (AI behavior)
    - AlertEngine (alerts)
    - CostTracker (cost)
    - UserJourneyTracker (user behavior)
    - FailureAnalytics (failures)
    - MetricsService (system metrics)

    Provides a single-endpoint comprehensive view for founders.
    """

    def __init__(self):
        self._start_time = time.time()
        self._dashboard_views = 0
        self._lock = threading.RLock()

    def get_system_panel(self) -> dict:
        """System health overview panel."""
        try:
            from ..services.metrics_service import MetricsService
            system = MetricsService.get_system_metrics()
            return {
                "api_uptime_seconds": system.get("uptime_seconds", 0),
                "total_requests": system.get("total_requests", 0),
                "error_rate_pct": system.get("error_rate", 0),
                "avg_latency_ms": system.get("avg_latency_ms", 0),
                "requests_per_minute": system.get("requests_per_minute", 0),
                "status_codes": system.get("status_codes", {}),
            }
        except Exception:
            return {"status": "unavailable"}

    def get_ai_panel(self) -> dict:
        """AI health and performance panel."""
        try:
            from .ai_observability import ai_observer
            stats = ai_observer.stats()
            drift = ai_observer.get_quality_drift()
            return {
                "total_ai_calls": stats.get("total_ai_calls", 0),
                "models_active": stats.get("models_tracked", 0),
                "failure_rate_pct": stats.get("failure_rate", 0),
                "hallucination_rate_pct": stats.get("hallucination_rate", 0),
                "quality_drift": drift,
                "prompt_versions": stats.get("prompt_versions_tracked", 0),
            }
        except Exception:
            return {"status": "unavailable"}

    def get_user_panel(self) -> dict:
        """User activity and engagement panel."""
        try:
            from .user_journey_tracker import journey_tracker
            stats = journey_tracker.stats()
            funnel = journey_tracker.get_funnel()
            return {
                "active_interviews": stats.get("active_sessions", 0),
                "completed_interviews": stats.get("completed_sessions", 0),
                "abandoned_interviews": stats.get("abandoned_sessions", 0),
                "completion_rate_pct": stats.get("overall_completion_rate", 0),
                "funnel": funnel,
            }
        except Exception:
            return {"status": "unavailable"}

    def get_business_panel(self) -> dict:
        """Business metrics panel."""
        try:
            from ..services.metrics_service import MetricsService
            product = MetricsService.get_product_metrics()
            return {
                "total_surveys": product.get("total_surveys", 0),
                "total_responses": product.get("total_responses", 0),
                "total_insights": product.get("total_insights", 0),
                "total_sessions": product.get("total_sessions", 0),
            }
        except Exception:
            return {"status": "unavailable"}

    def get_cost_panel(self) -> dict:
        """Cost monitoring panel."""
        try:
            from .cost_tracker import cost_tracker
            budget = cost_tracker.get_budget_status()
            per_interview = cost_tracker.get_cost_per_interview()
            return {
                "daily_budget_usd": budget.get("budget_usd", 0),
                "today_spent_usd": budget.get("spent_usd", 0),
                "budget_remaining_usd": budget.get("remaining_usd", 0),
                "over_budget": budget.get("over_budget", False),
                "cost_per_interview": per_interview.get("avg_cost_per_interview", 0),
            }
        except Exception:
            return {"status": "unavailable"}

    def get_alerts_panel(self) -> dict:
        """Active alerts panel."""
        try:
            from .alert_engine import alert_engine
            active = alert_engine.get_active_alerts()
            stats = alert_engine.stats()
            return {
                "active_alerts": len(active),
                "critical_alerts": sum(1 for a in active if a.get("severity") == "critical"),
                "warning_alerts": sum(1 for a in active if a.get("severity") == "warning"),
                "total_fired": stats.get("total_alerts_fired", 0),
                "recent_alerts": active[:5],
            }
        except Exception:
            return {"status": "unavailable"}

    def get_failure_panel(self) -> dict:
        """Failure analytics panel."""
        try:
            from .failure_analytics import failure_analytics
            stats = failure_analytics.stats()
            spike = failure_analytics.detect_spike()
            recommendations = failure_analytics.get_recommendations()
            return {
                "total_failures": stats.get("total_failures", 0),
                "recovery_rate_pct": stats.get("recovery_rate", 0),
                "unique_errors": stats.get("unique_error_patterns", 0),
                "spike_detected": spike.get("spike_detected", False),
                "top_recommendations": recommendations[:3],
            }
        except Exception:
            return {"status": "unavailable"}

    def get_logs_panel(self) -> dict:
        """Logging activity panel."""
        try:
            from .structured_logger import structured_logger
            stats = structured_logger.stats()
            return {
                "total_logged": stats.get("total_logged", 0),
                "error_count": stats.get("error_count", 0),
                "logs_per_minute": stats.get("logs_per_minute", 0),
                "by_category": stats.get("by_category", {}),
                "top_events": stats.get("top_events", [])[:5],
            }
        except Exception:
            return {"status": "unavailable"}

    def get_traces_panel(self) -> dict:
        """Tracing activity panel."""
        try:
            from .distributed_tracer import tracer
            stats = tracer.stats()
            return {
                "total_traces": stats.get("total_traces", 0),
                "active_traces": stats.get("active_traces", 0),
                "error_rate_pct": stats.get("error_rate", 0),
                "top_bottlenecks": stats.get("top_bottlenecks", []),
            }
        except Exception:
            return {"status": "unavailable"}

    # ── Unified Dashboard ──

    def get_full_dashboard(self) -> dict:
        """
        ONE endpoint, complete operational visibility.

        This is the Observability Data Pipeline output:
        Application Events → Telemetry Collector → Logs + Metrics + Traces
          → Storage Engine → Visualization Dashboard
        """
        with self._lock:
            self._dashboard_views += 1

        return {
            "dashboard": "AI Survey Platform — Operational Overview",
            "generated_at": datetime.now().isoformat(),
            "panels": {
                "system": self.get_system_panel(),
                "ai": self.get_ai_panel(),
                "users": self.get_user_panel(),
                "business": self.get_business_panel(),
                "cost": self.get_cost_panel(),
                "alerts": self.get_alerts_panel(),
                "failures": self.get_failure_panel(),
                "logs": self.get_logs_panel(),
                "traces": self.get_traces_panel(),
            },
        }

    def get_architecture(self) -> dict:
        """Describe the full observability architecture."""
        return {
            "name": "Observability & Monitoring Architecture",
            "three_pillars": {
                "logs": "Structured JSON logging — user, AI, system, security events",
                "metrics": "Numerical signals — latency, error rate, token usage, completion rates",
                "traces": "Request lifecycle tracking — trace_id propagation across all stages",
            },
            "engines": {
                "structured_logger": "Event categorization, ring buffer, keyword search, rate tracking",
                "distributed_tracer": "Trace/span lifecycle, bottleneck detection, percentile analytics",
                "ai_observer": "Model behavior, prompt versioning, quality drift, hallucination tracking",
                "alert_engine": "10 default rules, cooldown, lifecycle management, webhook channels",
                "cost_tracker": "Per-model pricing, daily budgets, channel comparison, per-interview cost",
                "user_journey_tracker": "Funnel analysis, drop-off detection, richness scoring, channel funnels",
                "failure_analytics": "Error fingerprinting, spike detection, recommendations, recovery tracking",
                "dashboard_aggregator": "Unified 9-panel operational dashboard",
            },
            "data_pipeline": [
                "Application Events (user, AI, system, security)",
                "Telemetry Collector (structured logger + tracer)",
                "Logs + Metrics + Traces (three pillars)",
                "Storage Engine (in-memory ring buffers + DB)",
                "Visualization Dashboard (unified panels)",
                "Alerts (threshold-based automatic detection)",
            ],
            "self_improving_vision": (
                "Observability → Intelligence: System detects quality changes "
                "after prompt updates and recommends rollback. AI supervising AI."
            ),
        }

    def stats(self) -> dict:
        uptime = time.time() - self._start_time
        return {
            "engine": "DashboardAggregator",
            "dashboard_views": self._dashboard_views,
            "uptime_seconds": round(uptime, 1),
            "panels_available": 9,
        }


# ── Global Singleton ──
dashboard_aggregator = DashboardAggregator()
