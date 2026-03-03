"""
Alert Engine — Automatic Problem Detection
═══════════════════════════════════════════════════════
System must alert BEFORE collapse.

Alert Types:
  Critical: AI failure rate > 20%, DB unreachable, queue backlog > threshold
  Warning:  Latency rising, worker retries increasing, interview drop-off spike

Alert Channels:
  - In-app notification (immediate)
  - Webhook (Slack, Discord integration)
  - Email (future)
  - SMS (future)
"""

import time
import threading
import uuid
from collections import deque, defaultdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Callable


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SILENCED = "silenced"


class AlertRule:
    """Defines a threshold-based alert rule."""

    def __init__(
        self,
        rule_id: str,
        name: str,
        description: str,
        severity: AlertSeverity,
        metric_name: str,
        condition: str,  # "gt", "lt", "gte", "lte", "eq"
        threshold: float,
        cooldown_seconds: int = 300,
        auto_resolve: bool = True,
    ):
        self.rule_id = rule_id
        self.name = name
        self.description = description
        self.severity = severity
        self.metric_name = metric_name
        self.condition = condition
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self.auto_resolve = auto_resolve
        self.enabled = True
        self.last_fired: Optional[float] = None
        self.fire_count = 0

    def evaluate(self, current_value: float) -> bool:
        """Check if the rule condition is met."""
        if not self.enabled:
            return False
        ops = {
            "gt": lambda v, t: v > t,
            "lt": lambda v, t: v < t,
            "gte": lambda v, t: v >= t,
            "lte": lambda v, t: v <= t,
            "eq": lambda v, t: v == t,
        }
        check = ops.get(self.condition, lambda v, t: False)
        return check(current_value, self.threshold)

    def can_fire(self) -> bool:
        """Check if cooldown has passed since last firing."""
        if self.last_fired is None:
            return True
        return (time.time() - self.last_fired) >= self.cooldown_seconds

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "metric_name": self.metric_name,
            "condition": self.condition,
            "threshold": self.threshold,
            "cooldown_seconds": self.cooldown_seconds,
            "enabled": self.enabled,
            "fire_count": self.fire_count,
            "last_fired": datetime.fromtimestamp(self.last_fired).isoformat() if self.last_fired else None,
        }


class Alert:
    """A single alert instance."""

    def __init__(
        self,
        rule: AlertRule,
        current_value: float,
        message: str = "",
    ):
        self.alert_id = str(uuid.uuid4())[:12]
        self.rule_id = rule.rule_id
        self.rule_name = rule.name
        self.severity = rule.severity
        self.metric_name = rule.metric_name
        self.threshold = rule.threshold
        self.current_value = current_value
        self.message = message or f"{rule.name}: {rule.metric_name} = {current_value} (threshold: {rule.threshold})"
        self.status = AlertStatus.FIRING
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.resolved_at: Optional[str] = None
        self.acknowledged_by: Optional[str] = None

    def acknowledge(self, user: str = "system"):
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_by = user
        self.updated_at = datetime.now().isoformat()

    def resolve(self):
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now().isoformat()
        self.updated_at = self.resolved_at

    def silence(self):
        self.status = AlertStatus.SILENCED
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        d = {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "metric_name": self.metric_name,
            "threshold": self.threshold,
            "current_value": self.current_value,
            "message": self.message,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.resolved_at:
            d["resolved_at"] = self.resolved_at
        if self.acknowledged_by:
            d["acknowledged_by"] = self.acknowledged_by
        return d


class AlertEngine:
    """
    Alert Engine — threshold-based automatic problem detection.

    Features:
    - Pre-configured alert rules for AI, system, and user metrics
    - Cooldown prevention (no alert spam)
    - Alert lifecycle: firing → acknowledged → resolved
    - Webhook channel support (Slack, Discord)
    - Alert history and statistics
    - Manual metric evaluation via check_metric()
    """

    def __init__(self, max_alerts: int = 2000):
        self._lock = threading.RLock()
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: deque = deque(maxlen=max_alerts)
        self._active_alerts: Dict[str, Alert] = {}
        self._webhooks: List[dict] = []

        # Statistics
        self._total_alerts_fired = 0
        self._alerts_by_severity: Dict[str, int] = defaultdict(int)
        self._alerts_by_rule: Dict[str, int] = defaultdict(int)
        self._start_time = time.time()

        # Register default rules
        self._register_defaults()

    def _register_defaults(self):
        """Register default alert rules for the AI survey platform."""
        defaults = [
            AlertRule("ai_failure_high", "AI Failure Rate High",
                      "AI model failure rate exceeds 20%",
                      AlertSeverity.CRITICAL, "ai_failure_rate", "gt", 20.0, 300),
            AlertRule("ai_latency_high", "AI Latency High",
                      "AI average response time exceeds 30 seconds",
                      AlertSeverity.WARNING, "ai_avg_latency_ms", "gt", 30000.0, 300),
            AlertRule("api_error_rate", "API Error Rate High",
                      "API error rate exceeds 10%",
                      AlertSeverity.CRITICAL, "api_error_rate", "gt", 10.0, 300),
            AlertRule("api_latency_p95", "API P95 Latency High",
                      "API P95 latency exceeds 5 seconds",
                      AlertSeverity.WARNING, "api_p95_latency_ms", "gt", 5000.0, 300),
            AlertRule("queue_backlog", "Queue Backlog Growing",
                      "Task queue has more than 100 pending jobs",
                      AlertSeverity.WARNING, "queue_pending_count", "gt", 100.0, 600),
            AlertRule("db_unreachable", "Database Unreachable",
                      "Database connection failed",
                      AlertSeverity.CRITICAL, "db_reachable", "eq", 0.0, 60),
            AlertRule("hallucination_spike", "AI Hallucination Spike",
                      "Hallucination rate exceeds 15%",
                      AlertSeverity.WARNING, "hallucination_rate", "gt", 15.0, 600),
            AlertRule("interview_dropout_high", "Interview Dropout Spike",
                      "Interview abandonment rate exceeds 40%",
                      AlertSeverity.WARNING, "interview_dropout_rate", "gt", 40.0, 900),
            AlertRule("cost_spike", "AI Cost Spike",
                      "Daily AI spend exceeds budget by 50%",
                      AlertSeverity.WARNING, "daily_cost_overage_pct", "gt", 50.0, 3600),
            AlertRule("disk_usage_high", "Disk Usage High",
                      "Disk usage exceeds 85%",
                      AlertSeverity.WARNING, "disk_usage_pct", "gt", 85.0, 1800),
        ]
        for rule in defaults:
            self._rules[rule.rule_id] = rule

    # ── Rule Management ──

    def add_rule(self, rule: AlertRule):
        with self._lock:
            self._rules[rule.rule_id] = rule

    def disable_rule(self, rule_id: str) -> bool:
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule:
                rule.enabled = False
                return True
            return False

    def enable_rule(self, rule_id: str) -> bool:
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule:
                rule.enabled = True
                return True
            return False

    def get_rules(self) -> List[dict]:
        with self._lock:
            return [r.to_dict() for r in self._rules.values()]

    # ── Metric Evaluation ──

    def check_metric(self, metric_name: str, current_value: float) -> List[dict]:
        """Evaluate a metric against all matching rules. Returns any new alerts."""
        new_alerts = []
        with self._lock:
            for rule in self._rules.values():
                if rule.metric_name != metric_name:
                    continue
                if not rule.enabled:
                    continue
                if rule.evaluate(current_value) and rule.can_fire():
                    alert = Alert(rule, current_value)
                    rule.last_fired = time.time()
                    rule.fire_count += 1

                    self._alerts.append(alert)
                    self._active_alerts[alert.alert_id] = alert
                    self._total_alerts_fired += 1
                    self._alerts_by_severity[alert.severity.value] += 1
                    self._alerts_by_rule[rule.rule_id] += 1

                    new_alerts.append(alert.to_dict())

                    # Send to webhooks
                    self._dispatch_webhooks(alert)

                elif rule.auto_resolve and not rule.evaluate(current_value):
                    # Auto-resolve any active alerts for this rule
                    for a in list(self._active_alerts.values()):
                        if a.rule_id == rule.rule_id and a.status == AlertStatus.FIRING:
                            a.resolve()
                            del self._active_alerts[a.alert_id]

        return new_alerts

    def check_all_metrics(self, metrics: Dict[str, float]) -> List[dict]:
        """Evaluate multiple metrics at once."""
        all_alerts = []
        for metric_name, value in metrics.items():
            new = self.check_metric(metric_name, value)
            all_alerts.extend(new)
        return all_alerts

    # ── Alert Management ──

    def acknowledge_alert(self, alert_id: str, user: str = "system") -> bool:
        with self._lock:
            alert = self._active_alerts.get(alert_id)
            if alert:
                alert.acknowledge(user)
                return True
            return False

    def resolve_alert(self, alert_id: str) -> bool:
        with self._lock:
            alert = self._active_alerts.pop(alert_id, None)
            if alert:
                alert.resolve()
                return True
            return False

    def silence_alert(self, alert_id: str) -> bool:
        with self._lock:
            alert = self._active_alerts.pop(alert_id, None)
            if alert:
                alert.silence()
                return True
            return False

    def get_active_alerts(self) -> List[dict]:
        with self._lock:
            return [a.to_dict() for a in self._active_alerts.values()]

    def get_alert_history(self, limit: int = 50, severity: str = None) -> List[dict]:
        with self._lock:
            alerts = list(self._alerts)
        if severity:
            alerts = [a for a in alerts if a.severity.value == severity]
        alerts = alerts[-limit:]
        alerts.reverse()
        return [a.to_dict() for a in alerts]

    # ── Webhook Channels ──

    def register_webhook(self, name: str, url: str, channel_type: str = "slack"):
        """Register an alert webhook (Slack, Discord, etc.)."""
        with self._lock:
            self._webhooks.append({
                "name": name,
                "url": url,
                "channel_type": channel_type,
                "registered_at": datetime.now().isoformat(),
                "alerts_sent": 0,
            })

    def get_webhooks(self) -> List[dict]:
        with self._lock:
            return list(self._webhooks)

    def _dispatch_webhooks(self, alert: Alert):
        """Send alert to registered webhooks (fire-and-forget)."""
        # In production, this would make HTTP requests to Slack/Discord
        for wh in self._webhooks:
            wh["alerts_sent"] += 1

    # ── Stats ──

    def stats(self) -> dict:
        uptime = time.time() - self._start_time
        with self._lock:
            return {
                "engine": "AlertEngine",
                "total_rules": len(self._rules),
                "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
                "total_alerts_fired": self._total_alerts_fired,
                "active_alerts": len(self._active_alerts),
                "by_severity": dict(self._alerts_by_severity),
                "by_rule": {
                    rule_id: count
                    for rule_id, count in sorted(self._alerts_by_rule.items(), key=lambda x: x[1], reverse=True)[:10]
                },
                "webhook_channels": len(self._webhooks),
                "uptime_seconds": round(uptime, 1),
                "alerts_per_hour": round(self._total_alerts_fired / max(uptime / 3600, 1), 2),
            }


# ── Global Singleton ──
alert_engine = AlertEngine()
