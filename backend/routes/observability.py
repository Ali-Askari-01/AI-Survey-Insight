"""
Observability & Monitoring API Routes
═══════════════════════════════════════════════════════
Complete API for the Observability Architecture.

Route Groups:
  /api/observability/dashboard   — Unified operational dashboard
  /api/observability/logs        — Structured logging queries
  /api/observability/traces      — Distributed tracing
  /api/observability/ai          — AI observability (model behavior, prompts)
  /api/observability/alerts      — Alert management
  /api/observability/cost        — Cost tracking
  /api/observability/journeys    — User journey analytics
  /api/observability/failures    — Failure analytics
"""

from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/observability", tags=["observability"])


# ═══════════════════════════════════════════════════
# UNIFIED DASHBOARD
# ═══════════════════════════════════════════════════

@router.get("/dashboard")
def get_operational_dashboard():
    """ONE endpoint — complete operational visibility for founders."""
    from ..observability.dashboard_aggregator import dashboard_aggregator
    return dashboard_aggregator.get_full_dashboard()


@router.get("/dashboard/system")
def get_system_panel():
    from ..observability.dashboard_aggregator import dashboard_aggregator
    return dashboard_aggregator.get_system_panel()


@router.get("/dashboard/ai")
def get_ai_panel():
    from ..observability.dashboard_aggregator import dashboard_aggregator
    return dashboard_aggregator.get_ai_panel()


@router.get("/dashboard/users")
def get_users_panel():
    from ..observability.dashboard_aggregator import dashboard_aggregator
    return dashboard_aggregator.get_user_panel()


@router.get("/dashboard/business")
def get_business_panel():
    from ..observability.dashboard_aggregator import dashboard_aggregator
    return dashboard_aggregator.get_business_panel()


@router.get("/dashboard/cost")
def get_cost_panel():
    from ..observability.dashboard_aggregator import dashboard_aggregator
    return dashboard_aggregator.get_cost_panel()


@router.get("/dashboard/alerts")
def get_alerts_panel():
    from ..observability.dashboard_aggregator import dashboard_aggregator
    return dashboard_aggregator.get_alerts_panel()


@router.get("/dashboard/failures")
def get_failures_panel():
    from ..observability.dashboard_aggregator import dashboard_aggregator
    return dashboard_aggregator.get_failure_panel()


@router.get("/overview")
def observability_overview():
    """Combined stats from all observability engines."""
    from ..observability.structured_logger import structured_logger
    from ..observability.distributed_tracer import tracer
    from ..observability.ai_observability import ai_observer
    from ..observability.alert_engine import alert_engine
    from ..observability.cost_tracker import cost_tracker
    from ..observability.user_journey_tracker import journey_tracker
    from ..observability.failure_analytics import failure_analytics
    from ..observability.dashboard_aggregator import dashboard_aggregator
    return {
        "logger": structured_logger.stats(),
        "tracer": tracer.stats(),
        "ai_observer": ai_observer.stats(),
        "alert_engine": alert_engine.stats(),
        "cost_tracker": cost_tracker.stats(),
        "journey_tracker": journey_tracker.stats(),
        "failure_analytics": failure_analytics.stats(),
        "dashboard": dashboard_aggregator.stats(),
    }


@router.get("/architecture")
def observability_architecture():
    """Full observability architecture description."""
    from ..observability.dashboard_aggregator import dashboard_aggregator
    return dashboard_aggregator.get_architecture()


# ═══════════════════════════════════════════════════
# STRUCTURED LOGGING
# ═══════════════════════════════════════════════════

@router.get("/logs/stats")
def get_log_stats():
    from ..observability.structured_logger import structured_logger
    return structured_logger.stats()


@router.get("/logs/recent")
def get_recent_logs(
    limit: int = Query(50, ge=1, le=200),
    category: Optional[str] = None,
    level: Optional[str] = None,
    event: Optional[str] = None,
):
    from ..observability.structured_logger import structured_logger
    return structured_logger.get_recent(limit, category, level, event)


@router.get("/logs/errors")
def get_error_logs(limit: int = Query(50, ge=1, le=200)):
    from ..observability.structured_logger import structured_logger
    return structured_logger.get_errors(limit)


@router.get("/logs/search")
def search_logs(keyword: str, limit: int = Query(50, ge=1, le=200)):
    from ..observability.structured_logger import structured_logger
    return structured_logger.search(keyword, limit)


@router.get("/logs/rate")
def get_log_rate():
    from ..observability.structured_logger import structured_logger
    return structured_logger.get_log_rate()


@router.get("/logs/frequency")
def get_event_frequency(top_n: int = Query(20, ge=1, le=100)):
    from ..observability.structured_logger import structured_logger
    return structured_logger.get_event_frequency(top_n)


# ═══════════════════════════════════════════════════
# DISTRIBUTED TRACING
# ═══════════════════════════════════════════════════

@router.get("/traces/stats")
def get_trace_stats():
    from ..observability.distributed_tracer import tracer
    return tracer.stats()


@router.get("/traces/recent")
def get_recent_traces(limit: int = Query(20, ge=1, le=100), status: Optional[str] = None):
    from ..observability.distributed_tracer import tracer
    return tracer.get_recent_traces(limit, status)


@router.get("/traces/slow")
def get_slow_traces(threshold_ms: float = Query(5000), limit: int = Query(20, ge=1, le=100)):
    from ..observability.distributed_tracer import tracer
    return tracer.get_slow_traces(threshold_ms, limit)


@router.get("/traces/{trace_id}")
def get_trace_detail(trace_id: str):
    from ..observability.distributed_tracer import tracer
    result = tracer.get_trace(trace_id)
    if not result:
        return {"error": "Trace not found", "trace_id": trace_id}
    return result


@router.get("/traces/analytics/spans")
def get_span_analytics():
    from ..observability.distributed_tracer import tracer
    return tracer.get_span_analytics()


@router.get("/traces/analytics/services")
def get_service_analytics():
    from ..observability.distributed_tracer import tracer
    return tracer.get_service_analytics()


@router.get("/traces/analytics/bottlenecks")
def get_bottleneck_ranking():
    from ..observability.distributed_tracer import tracer
    return tracer.get_bottleneck_ranking()


# ═══════════════════════════════════════════════════
# AI OBSERVABILITY
# ═══════════════════════════════════════════════════

@router.get("/ai/stats")
def get_ai_observer_stats():
    from ..observability.ai_observability import ai_observer
    return ai_observer.stats()


@router.get("/ai/models")
def get_model_comparison():
    from ..observability.ai_observability import ai_observer
    return ai_observer.get_model_comparison()


@router.get("/ai/tasks")
def get_task_analysis():
    from ..observability.ai_observability import ai_observer
    return ai_observer.get_task_analysis()


@router.get("/ai/prompts")
def get_prompt_versions(task_type: Optional[str] = None):
    from ..observability.ai_observability import ai_observer
    return ai_observer.get_prompt_versions(task_type)


@router.get("/ai/quality-drift")
def get_quality_drift():
    from ..observability.ai_observability import ai_observer
    return ai_observer.get_quality_drift()


@router.get("/ai/failures")
def get_ai_failure_patterns():
    from ..observability.ai_observability import ai_observer
    return ai_observer.get_failure_patterns()


@router.get("/ai/recent")
def get_recent_ai_calls(
    limit: int = Query(30, ge=1, le=100),
    model: Optional[str] = None,
    task_type: Optional[str] = None,
):
    from ..observability.ai_observability import ai_observer
    return ai_observer.get_recent_calls(limit, model, task_type)


# ═══════════════════════════════════════════════════
# ALERTING
# ═══════════════════════════════════════════════════

@router.get("/alerts/stats")
def get_alert_stats():
    from ..observability.alert_engine import alert_engine
    return alert_engine.stats()


@router.get("/alerts/active")
def get_active_alerts():
    from ..observability.alert_engine import alert_engine
    return alert_engine.get_active_alerts()


@router.get("/alerts/history")
def get_alert_history(limit: int = Query(50, ge=1, le=200), severity: Optional[str] = None):
    from ..observability.alert_engine import alert_engine
    return alert_engine.get_alert_history(limit, severity)


@router.get("/alerts/rules")
def get_alert_rules():
    from ..observability.alert_engine import alert_engine
    return alert_engine.get_rules()


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, user: str = "admin"):
    from ..observability.alert_engine import alert_engine
    ok = alert_engine.acknowledge_alert(alert_id, user)
    return {"acknowledged": ok, "alert_id": alert_id}


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: str):
    from ..observability.alert_engine import alert_engine
    ok = alert_engine.resolve_alert(alert_id)
    return {"resolved": ok, "alert_id": alert_id}


@router.post("/alerts/{alert_id}/silence")
def silence_alert(alert_id: str):
    from ..observability.alert_engine import alert_engine
    ok = alert_engine.silence_alert(alert_id)
    return {"silenced": ok, "alert_id": alert_id}


@router.post("/alerts/rules/{rule_id}/enable")
def enable_alert_rule(rule_id: str):
    from ..observability.alert_engine import alert_engine
    ok = alert_engine.enable_rule(rule_id)
    return {"enabled": ok, "rule_id": rule_id}


@router.post("/alerts/rules/{rule_id}/disable")
def disable_alert_rule(rule_id: str):
    from ..observability.alert_engine import alert_engine
    ok = alert_engine.disable_rule(rule_id)
    return {"disabled": ok, "rule_id": rule_id}


@router.post("/alerts/check")
def check_metrics(metrics: dict):
    """Manually check a set of metrics against alert rules."""
    from ..observability.alert_engine import alert_engine
    return alert_engine.check_all_metrics(metrics)


@router.get("/alerts/webhooks")
def get_webhooks():
    from ..observability.alert_engine import alert_engine
    return alert_engine.get_webhooks()


@router.post("/alerts/webhooks")
def register_webhook(data: dict):
    from ..observability.alert_engine import alert_engine
    name = data.get("name", "default")
    url = data.get("url", "")
    channel_type = data.get("channel_type", "slack")
    alert_engine.register_webhook(name, url, channel_type)
    return {"registered": True, "name": name}


# ═══════════════════════════════════════════════════
# COST TRACKING
# ═══════════════════════════════════════════════════

@router.get("/cost/stats")
def get_cost_stats():
    from ..observability.cost_tracker import cost_tracker
    return cost_tracker.stats()


@router.get("/cost/budget")
def get_budget_status():
    from ..observability.cost_tracker import cost_tracker
    return cost_tracker.get_budget_status()


@router.get("/cost/daily")
def get_daily_spend(days: int = Query(7, ge=1, le=90)):
    from ..observability.cost_tracker import cost_tracker
    return cost_tracker.get_daily_spend(days)


@router.get("/cost/models")
def get_cost_by_model():
    from ..observability.cost_tracker import cost_tracker
    return cost_tracker.get_model_breakdown()


@router.get("/cost/tasks")
def get_cost_by_task():
    from ..observability.cost_tracker import cost_tracker
    return cost_tracker.get_task_breakdown()


@router.get("/cost/channels")
def get_cost_by_channel():
    from ..observability.cost_tracker import cost_tracker
    return cost_tracker.get_channel_comparison()


@router.get("/cost/per-interview")
def get_cost_per_interview():
    from ..observability.cost_tracker import cost_tracker
    return cost_tracker.get_cost_per_interview()


@router.get("/cost/per-insight")
def get_cost_per_insight():
    from ..observability.cost_tracker import cost_tracker
    return cost_tracker.get_cost_per_insight()


@router.get("/cost/surveys")
def get_survey_costs(survey_id: Optional[int] = None):
    from ..observability.cost_tracker import cost_tracker
    return cost_tracker.get_survey_costs(survey_id)


@router.get("/cost/recent")
def get_recent_costs(limit: int = Query(30, ge=1, le=100)):
    from ..observability.cost_tracker import cost_tracker
    return cost_tracker.get_recent_costs(limit)


# ═══════════════════════════════════════════════════
# USER JOURNEY
# ═══════════════════════════════════════════════════

@router.get("/journeys/stats")
def get_journey_stats():
    from ..observability.user_journey_tracker import journey_tracker
    return journey_tracker.stats()


@router.get("/journeys/funnel")
def get_journey_funnel():
    from ..observability.user_journey_tracker import journey_tracker
    return journey_tracker.get_funnel()


@router.get("/journeys/dropoff")
def get_dropoff_analysis(survey_id: Optional[int] = None):
    from ..observability.user_journey_tracker import journey_tracker
    return journey_tracker.get_dropoff_analysis(survey_id)


@router.get("/journeys/channels")
def get_channel_funnel():
    from ..observability.user_journey_tracker import journey_tracker
    return journey_tracker.get_channel_funnel()


@router.get("/journeys/survey/{survey_id}")
def get_survey_journey(survey_id: int):
    from ..observability.user_journey_tracker import journey_tracker
    return journey_tracker.get_survey_journey(survey_id)


@router.get("/journeys/active")
def get_active_sessions():
    from ..observability.user_journey_tracker import journey_tracker
    return journey_tracker.get_active_sessions()


@router.get("/journeys/recent")
def get_recent_journeys(limit: int = Query(20, ge=1, le=100)):
    from ..observability.user_journey_tracker import journey_tracker
    return journey_tracker.get_recent_journeys(limit)


# ═══════════════════════════════════════════════════
# FAILURE ANALYTICS
# ═══════════════════════════════════════════════════

@router.get("/failures/stats")
def get_failure_stats():
    from ..observability.failure_analytics import failure_analytics
    return failure_analytics.stats()


@router.get("/failures/recent")
def get_recent_failures(limit: int = Query(30, ge=1, le=100), category: Optional[str] = None):
    from ..observability.failure_analytics import failure_analytics
    return failure_analytics.get_recent_failures(limit, category)


@router.get("/failures/top-errors")
def get_top_errors(limit: int = Query(20, ge=1, le=50)):
    from ..observability.failure_analytics import failure_analytics
    return failure_analytics.get_top_errors(limit)


@router.get("/failures/categories")
def get_failure_categories():
    from ..observability.failure_analytics import failure_analytics
    return failure_analytics.get_category_breakdown()


@router.get("/failures/components")
def get_failure_components():
    from ..observability.failure_analytics import failure_analytics
    return failure_analytics.get_component_breakdown()


@router.get("/failures/models")
def get_model_failures():
    from ..observability.failure_analytics import failure_analytics
    return failure_analytics.get_model_failure_rates()


@router.get("/failures/trend")
def get_failure_trend():
    from ..observability.failure_analytics import failure_analytics
    return failure_analytics.get_failure_rate_trend()


@router.get("/failures/spike")
def detect_failure_spike():
    from ..observability.failure_analytics import failure_analytics
    return failure_analytics.detect_spike()


@router.get("/failures/recommendations")
def get_failure_recommendations():
    from ..observability.failure_analytics import failure_analytics
    return failure_analytics.get_recommendations()
