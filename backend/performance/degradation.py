"""
Graceful Degradation Controller (§6, §15)
═══════════════════════════════════════════════════════
System-wide degradation management that sheds load in controlled levels.

Levels:
  NORMAL  — All features active, full AI processing
  LITE    — Switch to cached/heuristic AI, disable non-critical features
  STALE   — Serve only cached data, queue all new processing
  MINIMAL — Static responses only, all AI offline
  
User-facing reliability:
  Never show 500 errors.
  Always show friendly "updating…" messages.
"""

import time
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional


class DegradationLevel(IntEnum):
    """Degradation levels — higher = more degraded."""
    NORMAL  = 0
    LITE    = 1
    STALE   = 2
    MINIMAL = 3


@dataclass
class DegradationRule:
    """Condition that triggers escalation to a degradation level."""
    name: str
    target_level: DegradationLevel
    condition_fn: Callable[[], bool]
    description: str = ""
    cooldown_seconds: float = 60.0   # Min time between transitions
    last_triggered: float = 0.0


@dataclass
class DegradationEvent:
    """Recorded degradation level change."""
    from_level: DegradationLevel
    to_level: DegradationLevel
    reason: str
    timestamp: float = field(default_factory=time.time)
    auto: bool = True   # False = manual override


class DegradationController:
    """
    Controls system-wide graceful degradation.
    
    Integrates with circuit breakers, health monitor, and load protector
    to automatically shed load when the system is under stress.
    
    Usage:
        if degradation_controller.is_feature_allowed("ai_insights"):
            result = await compute_insights()
        else:
            result = get_cached_insights()  # stale but available
    """

    # Feature availability per degradation level
    FEATURE_MATRIX: Dict[str, DegradationLevel] = {
        # Feature name → max level at which it's still available
        "survey_submission":    DegradationLevel.MINIMAL,   # Always available
        "response_storage":     DegradationLevel.MINIMAL,   # Always available
        "health_check":         DegradationLevel.MINIMAL,   # Always available
        "dashboard_cached":     DegradationLevel.STALE,     # Available through STALE
        "ai_insights":          DegradationLevel.LITE,      # Disabled at STALE+
        "ai_sentiment":         DegradationLevel.LITE,      # Disabled at STALE+
        "ai_themes":            DegradationLevel.LITE,      # Disabled at STALE+
        "voice_transcription":  DegradationLevel.NORMAL,    # Only at NORMAL
        "report_generation":    DegradationLevel.LITE,      # Disabled at STALE+
        "real_time_updates":    DegradationLevel.LITE,      # Disabled at STALE+
        "notifications":        DegradationLevel.STALE,     # Available through STALE
        "data_pipeline":        DegradationLevel.LITE,      # Queued at STALE+
        "batch_processing":     DegradationLevel.NORMAL,    # Only at NORMAL
        "temporal_analysis":    DegradationLevel.LITE,      # Disabled at STALE+
        "export":               DegradationLevel.LITE,      # Disabled at STALE+
    }

    # User-facing messages per level
    USER_MESSAGES: Dict[DegradationLevel, str] = {
        DegradationLevel.NORMAL:  "",
        DegradationLevel.LITE:    "Some features are running in lite mode. Results may be less detailed.",
        DegradationLevel.STALE:   "Insights are being updated. Showing last available results.",
        DegradationLevel.MINIMAL: "System is in maintenance mode. Core features available. Full service resuming shortly.",
    }

    def __init__(self):
        self._current_level = DegradationLevel.NORMAL
        self._lock = threading.Lock()
        self._rules: List[DegradationRule] = []
        self._history: List[DegradationEvent] = []
        self._max_history = 500
        self._manual_override: Optional[DegradationLevel] = None
        self._last_transition: float = 0.0
        self._transition_cooldown: float = 30.0  # seconds between auto-transitions
        self._escalations = 0
        self._de_escalations = 0

        # Register default rules
        self._register_default_rules()

    # ─────────────────────────────────────
    # Default Rules
    # ─────────────────────────────────────

    def _register_default_rules(self):
        """Register built-in degradation rules based on system health."""

        # Rule 1: Circuit breakers open → LITE
        def _circuits_degraded():
            try:
                from ..infrastructure.circuit_breaker import circuit_registry
                unhealthy = circuit_registry.unhealthy_circuits()
                return len(unhealthy) >= 1
            except Exception:
                return False

        self.add_rule(DegradationRule(
            name="circuit_breakers_open",
            target_level=DegradationLevel.LITE,
            condition_fn=_circuits_degraded,
            description="One or more circuit breakers are open",
            cooldown_seconds=30,
        ))

        # Rule 2: Multiple circuits open → STALE
        def _circuits_critical():
            try:
                from ..infrastructure.circuit_breaker import circuit_registry
                return len(circuit_registry.unhealthy_circuits()) >= 2
            except Exception:
                return False

        self.add_rule(DegradationRule(
            name="circuits_critical",
            target_level=DegradationLevel.STALE,
            condition_fn=_circuits_critical,
            description="Multiple circuit breakers are open",
            cooldown_seconds=60,
        ))

        # Rule 3: Queue depth critical → STALE
        def _queue_overloaded():
            try:
                from ..infrastructure.task_queue import task_queue
                depth = task_queue.queue_depth()
                return depth > 8000  # 80% of 10k max
            except Exception:
                return False

        self.add_rule(DegradationRule(
            name="queue_overloaded",
            target_level=DegradationLevel.STALE,
            condition_fn=_queue_overloaded,
            description="Task queue is critically full",
            cooldown_seconds=60,
        ))

        # Rule 4: Worker pool exhausted → LITE
        def _workers_exhausted():
            try:
                from ..infrastructure.worker_pool import worker_pool
                s = worker_pool.stats()
                idle = s.get("workers_by_status", {}).get("idle", 0)
                return idle == 0 and s.get("total_workers", 0) >= s.get("max_workers", 5)
            except Exception:
                return False

        self.add_rule(DegradationRule(
            name="workers_exhausted",
            target_level=DegradationLevel.LITE,
            condition_fn=_workers_exhausted,
            description="All workers busy and pool at maximum",
            cooldown_seconds=30,
        ))

    # ─────────────────────────────────────
    # Rule Management
    # ─────────────────────────────────────

    def add_rule(self, rule: DegradationRule):
        """Add a degradation rule."""
        self._rules.append(rule)

    def remove_rule(self, name: str):
        """Remove a rule by name."""
        self._rules = [r for r in self._rules if r.name != name]

    # ─────────────────────────────────────
    # Level Management
    # ─────────────────────────────────────

    @property
    def level(self) -> DegradationLevel:
        """Current degradation level."""
        if self._manual_override is not None:
            return self._manual_override
        return self._current_level

    def set_level(self, level: DegradationLevel, reason: str = "manual"):
        """Manually override degradation level."""
        with self._lock:
            old = self._current_level
            self._manual_override = level
            if level != old:
                self._record_event(old, level, reason, auto=False)
                if level > old:
                    self._escalations += 1
                else:
                    self._de_escalations += 1

    def clear_override(self):
        """Remove manual override, return to automatic management."""
        self._manual_override = None

    def _transition(self, new_level: DegradationLevel, reason: str):
        """Auto-transition to a new level with cooldown."""
        now = time.time()
        with self._lock:
            if now - self._last_transition < self._transition_cooldown:
                return  # Too soon
            if self._manual_override is not None:
                return  # Manual override active

            old = self._current_level
            if new_level == old:
                return

            self._current_level = new_level
            self._last_transition = now
            self._record_event(old, new_level, reason, auto=True)

            if new_level > old:
                self._escalations += 1
            else:
                self._de_escalations += 1

    def _record_event(self, from_lvl, to_lvl, reason, auto=True):
        event = DegradationEvent(
            from_level=from_lvl, to_level=to_lvl,
            reason=reason, auto=auto,
        )
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    # ─────────────────────────────────────
    # Evaluate Rules
    # ─────────────────────────────────────

    def evaluate(self):
        """
        Evaluate all degradation rules and adjust level.
        Call this periodically (e.g., from health monitor).
        """
        now = time.time()
        max_triggered_level = DegradationLevel.NORMAL

        for rule in self._rules:
            if now - rule.last_triggered < rule.cooldown_seconds:
                continue
            try:
                if rule.condition_fn():
                    rule.last_triggered = now
                    if rule.target_level > max_triggered_level:
                        max_triggered_level = rule.target_level
            except Exception:
                pass

        # If no rules triggered, try to de-escalate
        if max_triggered_level < self._current_level:
            self._transition(max_triggered_level, "auto_de_escalation")
        elif max_triggered_level > self._current_level:
            # Find the rule that triggered the highest level
            reasons = [r.name for r in self._rules
                       if r.target_level == max_triggered_level
                       and now - r.last_triggered < 5]
            reason = ", ".join(reasons) if reasons else "rule_triggered"
            self._transition(max_triggered_level, reason)

    # ─────────────────────────────────────
    # Feature Availability
    # ─────────────────────────────────────

    def is_feature_allowed(self, feature_name: str) -> bool:
        """Check if a feature is available at the current degradation level."""
        max_level = self.FEATURE_MATRIX.get(feature_name, DegradationLevel.NORMAL)
        return self.level <= max_level

    def get_available_features(self) -> Dict[str, bool]:
        """Get availability of all features at current level."""
        return {
            name: self.level <= max_lvl
            for name, max_lvl in self.FEATURE_MATRIX.items()
        }

    def get_user_message(self) -> str:
        """Get user-facing degradation message."""
        return self.USER_MESSAGES.get(self.level, "")

    # ─────────────────────────────────────
    # Fallback Helpers
    # ─────────────────────────────────────

    def with_fallback(self, feature: str, primary_fn: Callable,
                       fallback_fn: Callable, *args, **kwargs) -> Any:
        """
        Execute primary_fn if feature is allowed, else fallback_fn.
        Never raises to the user.
        """
        try:
            if self.is_feature_allowed(feature):
                return primary_fn(*args, **kwargs)
            else:
                return fallback_fn(*args, **kwargs)
        except Exception:
            try:
                return fallback_fn(*args, **kwargs)
            except Exception:
                return {
                    "status": "degraded",
                    "message": self.get_user_message() or "Service temporarily unavailable",
                    "level": self.level.name,
                }

    # ─────────────────────────────────────
    # Event History
    # ─────────────────────────────────────

    def get_history(self, limit: int = 50) -> List[dict]:
        """Get degradation event history."""
        return [
            {
                "from": e.from_level.name,
                "to": e.to_level.name,
                "reason": e.reason,
                "timestamp": e.timestamp,
                "auto": e.auto,
            }
            for e in reversed(self._history)
        ][:limit]

    # ─────────────────────────────────────
    # Stats
    # ─────────────────────────────────────

    def stats(self) -> dict:
        return {
            "engine": "DegradationController",
            "current_level": self.level.name,
            "manual_override": self._manual_override.name if self._manual_override else None,
            "rules_count": len(self._rules),
            "escalations": self._escalations,
            "de_escalations": self._de_escalations,
            "history_size": len(self._history),
            "features_available": sum(1 for v in self.get_available_features().values() if v),
            "features_total": len(self.FEATURE_MATRIX),
        }


# ─────────────────────────────────────────────────────
# Global singleton
# ─────────────────────────────────────────────────────
degradation_controller = DegradationController()
