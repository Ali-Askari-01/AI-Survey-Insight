"""
Event Bus — Event-Driven Processing System
═══════════════════════════════════════════════════════
Architecture: Data → Events → Intelligence → Decisions

When a new response arrives:
  1. Response stored IMMEDIATELY (no waiting for AI)
  2. Event created
  3. AI processing happens asynchronously in background
  4. Dashboard updates automatically via WebSocket

This prevents: UI freezing, timeout errors, poor UX.
"""
import json
import time
import threading
from datetime import datetime
from typing import Callable, Dict, List, Any
from ..database import get_db


# ═══════════════════════════════════════════════════
# EVENT TYPES
# ═══════════════════════════════════════════════════
class EventType:
    """All event types in the system."""
    # Response events
    RESPONSE_SUBMITTED = "response.submitted"
    RESPONSE_ANALYZED = "response.analyzed"

    # Chat events
    CHAT_MESSAGE_RECEIVED = "chat.message_received"
    CHAT_RESPONSE_GENERATED = "chat.response_generated"

    # Survey events
    SURVEY_CREATED = "survey.created"
    QUESTIONS_GENERATED = "questions.generated"
    INTERVIEW_STARTED = "interview.started"
    INTERVIEW_COMPLETED = "interview.completed"

    # AI events
    AI_PROCESSING_STARTED = "ai.processing_started"
    AI_PROCESSING_COMPLETED = "ai.processing_completed"
    AI_PROCESSING_FAILED = "ai.processing_failed"

    # Insight events
    INSIGHT_DISCOVERED = "insight.discovered"
    THEME_UPDATED = "theme.updated"
    SENTIMENT_SHIFT_DETECTED = "sentiment.shift_detected"

    # Alert events
    ALERT_TRIGGERED = "alert.triggered"
    METRIC_UPDATED = "metric.updated"


class Event:
    """Represents a system event."""

    def __init__(self, event_type: str, payload: dict, source: str = "system"):
        self.event_type = event_type
        self.payload = payload
        self.source = source
        self.timestamp = datetime.now().isoformat()
        self.event_id = f"{event_type}-{int(time.time() * 1000)}"

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "source": self.source,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════
# EVENT BUS (In-Process Pub/Sub)
# ═══════════════════════════════════════════════════
class EventBus:
    """
    Simple in-process event bus for pub/sub pattern.
    Subscribers receive events asynchronously via background threads.
    MVP uses threading; production would use Redis Pub/Sub or Kafka.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
        self._event_count = 0
        self._error_count = 0

    def subscribe(self, event_type: str, handler: Callable):
        """Register a handler for an event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)

    def publish(self, event: Event):
        """Publish an event — all subscribers notified asynchronously."""
        with self._lock:
            self._event_count += 1
            handlers = self._subscribers.get(event.event_type, []).copy()

        # Log the event to database
        self._log_event(event)

        # Dispatch to handlers in background threads
        for handler in handlers:
            thread = threading.Thread(
                target=self._safe_dispatch,
                args=(handler, event),
                daemon=True
            )
            thread.start()

    def _safe_dispatch(self, handler: Callable, event: Event):
        """Safely dispatch event to handler with error handling."""
        try:
            handler(event)
        except Exception as e:
            with self._lock:
                self._error_count += 1
            print(f"[EventBus] Handler error for {event.event_type}: {e}")

    def _log_event(self, event: Event):
        """Persist event to the event_log table."""
        try:
            conn = get_db()
            conn.execute("""
                INSERT INTO event_log (event_id, event_type, payload, source, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (event.event_id, event.event_type, json.dumps(event.payload),
                  event.source, event.timestamp))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[EventBus] Failed to log event: {e}")

    def stats(self) -> dict:
        return {
            "total_events_published": self._event_count,
            "subscriber_count": sum(len(h) for h in self._subscribers.values()),
            "event_types_active": list(self._subscribers.keys()),
            "errors": self._error_count,
        }


# ═══════════════════════════════════════════════════
# GLOBAL EVENT BUS SINGLETON
# ═══════════════════════════════════════════════════
event_bus = EventBus()


# ═══════════════════════════════════════════════════
# EVENT HANDLERS (Background AI Processing)
# ═══════════════════════════════════════════════════
def handle_response_submitted(event: Event):
    """
    Background handler: When a new response arrives,
    run the full Continuous Intelligence Loop (AI Processing Architecture).

    Flow:
      Response → Pipeline B (Understanding) → Smart Trigger Check →
      Pipeline C (Insight) if threshold met → Pipeline D (Recommendation) if threshold met
    """
    from ..services.intelligence_loop import ContinuousIntelligenceLoop

    payload = event.payload
    session_id = payload.get("session_id", "")
    response_text = payload.get("response_text", "")
    response_id = payload.get("response_id")
    survey_id = payload.get("survey_id")

    if not response_text or not session_id:
        return

    # Delegate to the Continuous Intelligence Loop
    # This handles: understanding → insight formation → recommendations → storage
    try:
        ContinuousIntelligenceLoop.on_response_submitted(
            survey_id=survey_id,
            session_id=session_id,
            response_text=response_text,
            response_id=response_id
        )
    except Exception as e:
        print(f"[EventHandler] Intelligence loop failed: {e}")

    # Publish completion event
    event_bus.publish(Event(
        EventType.RESPONSE_ANALYZED,
        {"session_id": session_id, "response_id": response_id},
        source="intelligence_loop"
    ))


def handle_interview_completed(event: Event):
    """
    Background handler: When an interview completes,
    update metrics and trigger executive intelligence pipeline.
    """
    from ..services.intelligence_loop import ContinuousIntelligenceLoop

    payload = event.payload
    survey_id = payload.get("survey_id")
    session_id = payload.get("session_id")

    if not survey_id:
        return

    try:
        conn = get_db()
        # Update survey total_responses
        conn.execute(
            "UPDATE surveys SET total_responses = total_responses + 1 WHERE id = ?",
            (survey_id,)
        )

        # Recalculate engagement metrics
        stats = conn.execute("""
            SELECT channel,
                   COUNT(*) as total,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                   AVG(completion_percentage) as avg_completion,
                   AVG(engagement_score) as avg_engagement
            FROM interview_sessions WHERE survey_id = ? GROUP BY channel
        """, (survey_id,)).fetchall()

        for s in stats:
            sd = dict(s)
            total = sd["total"]
            completed = sd["completed"] or 0
            drop_off = round(1.0 - (completed / max(total, 1)), 3)

            existing = conn.execute(
                "SELECT id FROM engagement_metrics WHERE survey_id = ? AND channel = ?",
                (survey_id, sd["channel"])
            ).fetchone()

            if existing:
                conn.execute("""
                    UPDATE engagement_metrics SET total_sessions = ?, completed_sessions = ?,
                        avg_response_quality = ?, drop_off_rate = ?, recorded_at = ?
                    WHERE id = ?
                """, (total, completed, round(sd["avg_engagement"] or 0, 3), drop_off,
                      datetime.now().isoformat(), dict(existing)["id"]))
            else:
                conn.execute("""
                    INSERT INTO engagement_metrics (survey_id, channel, total_sessions, completed_sessions,
                        avg_response_quality, drop_off_rate)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (survey_id, sd["channel"], total, completed,
                      round(sd["avg_engagement"] or 0, 3), drop_off))

        # Get conversation history for transcript report
        history = conn.execute("""
            SELECT role, message FROM conversation_history
            WHERE session_id = ? ORDER BY created_at
        """, (session_id,)).fetchall() if session_id else []

        conn.commit()
        conn.close()

        # Trigger Intelligence Loop for interview completion
        conversation_history = [dict(h) for h in history] if history else None
        ContinuousIntelligenceLoop.on_interview_completed(
            survey_id=survey_id,
            session_id=session_id,
            conversation_history=conversation_history
        )

        # Publish metric update event
        event_bus.publish(Event(
            EventType.METRIC_UPDATED,
            {"survey_id": survey_id, "type": "engagement"},
            source="interview_completion_worker"
        ))

    except Exception as e:
        print(f"[EventHandler] Interview completion handler failed: {e}")


def handle_sentiment_shift(event: Event):
    """Background handler: Create alert notification when sentiment shift detected."""
    payload = event.payload
    survey_id = payload.get("survey_id")
    shift_info = payload.get("shift_info", "Significant sentiment change detected")

    if not survey_id:
        return

    try:
        conn = get_db()
        conn.execute("""
            INSERT INTO notifications (survey_id, type, title, message, severity)
            VALUES (?, 'alert', 'Sentiment Shift Detected', ?, 'high')
        """, (survey_id, shift_info))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[EventHandler] Sentiment shift handler failed: {e}")


def _incremental_insight_update(survey_id: int, new_response_text: str):
    """
    Incremental Intelligence Updating — NOT full recomputation.
    Only calculates the delta from the new response.
    """
    conn = get_db()

    # Get current insight state
    current_insights = conn.execute(
        "SELECT id, title, feature_area, frequency, sentiment FROM insights WHERE survey_id = ?",
        (survey_id,)
    ).fetchall()

    # Check if the new response matches any existing insight pattern
    response_lower = new_response_text.lower()

    for insight in current_insights:
        insight_dict = dict(insight)
        # Simple keyword matching for incremental update
        title_words = insight_dict["title"].lower().split()
        feature = (insight_dict.get("feature_area") or "").lower()

        match_score = sum(1 for w in title_words if w in response_lower and len(w) > 3)
        if feature and feature in response_lower:
            match_score += 2

        if match_score >= 2:
            # Increment frequency for matching insight
            conn.execute(
                "UPDATE insights SET frequency = frequency + 1 WHERE id = ?",
                (insight_dict["id"],)
            )

    conn.commit()
    conn.close()


def handle_insight_discovered(event: Event):
    """
    Background handler: When new insights are discovered,
    trigger the recommendation pipeline via the intelligence loop.
    """
    from ..services.intelligence_loop import ContinuousIntelligenceLoop

    payload = event.payload
    survey_id = payload.get("survey_id")

    if not survey_id:
        return

    try:
        ContinuousIntelligenceLoop.on_insight_discovered(survey_id)
    except Exception as e:
        print(f"[EventHandler] Insight discovered handler failed: {e}")


# ═══════════════════════════════════════════════════
# REGISTER DEFAULT EVENT HANDLERS
# ═══════════════════════════════════════════════════
def register_default_handlers():
    """Register all default event handlers. Called during app startup."""
    event_bus.subscribe(EventType.RESPONSE_SUBMITTED, handle_response_submitted)
    event_bus.subscribe(EventType.INTERVIEW_COMPLETED, handle_interview_completed)
    event_bus.subscribe(EventType.SENTIMENT_SHIFT_DETECTED, handle_sentiment_shift)
    event_bus.subscribe(EventType.INSIGHT_DISCOVERED, handle_insight_discovered)
    print("[EventBus] Default event handlers registered (with Intelligence Loop).")
