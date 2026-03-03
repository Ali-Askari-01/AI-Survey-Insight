"""
User Journey Tracker — Behavioral Observability
═══════════════════════════════════════════════════════
Observe behavioral flow, not just clicks.

Flow:
  Founder creates survey → Respondent starts interview → Stops at Q4
  → System learns: Question 4 is problematic
  → AI Survey Designer improves automatically

Tracks:
  - Interview completion %
  - Average interview duration
  - Drop-off question identification
  - Response richness score
  - Channel-specific engagement
  - Re-engagement patterns
"""

import time
import threading
from collections import deque, defaultdict
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum


class JourneyStage(str, Enum):
    SURVEY_CREATED = "survey_created"
    SURVEY_PUBLISHED = "survey_published"
    INTERVIEW_STARTED = "interview_started"
    QUESTION_ANSWERED = "question_answered"
    INTERVIEW_PAUSED = "interview_paused"
    INTERVIEW_RESUMED = "interview_resumed"
    INTERVIEW_COMPLETED = "interview_completed"
    INTERVIEW_ABANDONED = "interview_abandoned"
    INSIGHT_VIEWED = "insight_viewed"
    REPORT_GENERATED = "report_generated"
    FEEDBACK_GIVEN = "feedback_given"


class JourneyEvent:
    """A single event in a user's journey."""

    def __init__(
        self,
        stage: JourneyStage,
        user_id: Optional[int] = None,
        survey_id: Optional[int] = None,
        session_id: Optional[str] = None,
        question_index: Optional[int] = None,
        channel: str = "text",
        metadata: Optional[dict] = None,
    ):
        self.timestamp = datetime.now().isoformat()
        self.epoch = time.time()
        self.stage = stage.value
        self.user_id = user_id
        self.survey_id = survey_id
        self.session_id = session_id
        self.question_index = question_index
        self.channel = channel
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        d = {
            "timestamp": self.timestamp,
            "stage": self.stage,
            "channel": self.channel,
        }
        if self.user_id is not None:
            d["user_id"] = self.user_id
        if self.survey_id is not None:
            d["survey_id"] = self.survey_id
        if self.session_id:
            d["session_id"] = self.session_id
        if self.question_index is not None:
            d["question_index"] = self.question_index
        if self.metadata:
            d["metadata"] = self.metadata
        return d


class SessionJourney:
    """Tracks the complete journey of a single interview session."""

    def __init__(self, session_id: str, survey_id: int, channel: str = "text"):
        self.session_id = session_id
        self.survey_id = survey_id
        self.channel = channel
        self.started_at = time.time()
        self.ended_at: Optional[float] = None
        self.events: List[JourneyEvent] = []
        self.questions_answered = 0
        self.last_question_index = 0
        self.status = "active"
        self.duration_seconds: Optional[float] = None
        self.response_richness_scores: List[float] = []

    def add_event(self, event: JourneyEvent):
        self.events.append(event)
        if event.stage == JourneyStage.QUESTION_ANSWERED.value:
            self.questions_answered += 1
            if event.question_index is not None:
                self.last_question_index = max(self.last_question_index, event.question_index)
        elif event.stage == JourneyStage.INTERVIEW_COMPLETED.value:
            self.status = "completed"
            self.ended_at = time.time()
            self.duration_seconds = self.ended_at - self.started_at
        elif event.stage == JourneyStage.INTERVIEW_ABANDONED.value:
            self.status = "abandoned"
            self.ended_at = time.time()
            self.duration_seconds = self.ended_at - self.started_at

    def record_richness(self, score: float):
        """Record response richness score (0-1)."""
        self.response_richness_scores.append(score)

    def to_dict(self) -> dict:
        avg_richness = (
            sum(self.response_richness_scores) / len(self.response_richness_scores)
            if self.response_richness_scores else None
        )
        return {
            "session_id": self.session_id,
            "survey_id": self.survey_id,
            "channel": self.channel,
            "status": self.status,
            "questions_answered": self.questions_answered,
            "last_question_index": self.last_question_index,
            "duration_seconds": round(self.duration_seconds, 1) if self.duration_seconds else None,
            "avg_richness_score": round(avg_richness, 3) if avg_richness else None,
            "event_count": len(self.events),
        }


class UserJourneyTracker:
    """
    User Journey Observability Engine.

    Features:
    - Full session journey tracking (start → answer → complete/abandon)
    - Drop-off point identification (which question causes abandonment)
    - Response richness scoring
    - Channel-specific funnel analysis
    - Completion rate and duration trends
    - Survey-level journey aggregation
    - Problematic question detection for AI auto-improvement
    """

    def __init__(self, max_events: int = 10000, max_sessions: int = 5000):
        self._lock = threading.RLock()
        self._events: deque = deque(maxlen=max_events)
        self._sessions: Dict[str, SessionJourney] = {}
        self._completed_sessions: deque = deque(maxlen=max_sessions)

        # Drop-off tracking: survey_id → question_index → count
        self._dropoff_map: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))

        # Funnel tracking
        self._stage_counts: Dict[str, int] = defaultdict(int)
        self._channel_stats: Dict[str, dict] = defaultdict(lambda: {
            "started": 0, "completed": 0, "abandoned": 0,
            "total_duration": 0.0, "total_questions": 0,
        })

        # Survey-level stats
        self._survey_stats: Dict[int, dict] = defaultdict(lambda: {
            "started": 0, "completed": 0, "abandoned": 0,
            "total_duration": 0.0,
        })

        self._total_events = 0
        self._start_time = time.time()

    def track_event(
        self,
        stage: JourneyStage,
        user_id: Optional[int] = None,
        survey_id: Optional[int] = None,
        session_id: Optional[str] = None,
        question_index: Optional[int] = None,
        channel: str = "text",
        metadata: Optional[dict] = None,
    ):
        """Record a journey event."""
        event = JourneyEvent(
            stage=stage, user_id=user_id, survey_id=survey_id,
            session_id=session_id, question_index=question_index,
            channel=channel, metadata=metadata,
        )

        with self._lock:
            self._events.append(event)
            self._total_events += 1
            self._stage_counts[stage.value] += 1

            # Session journey management
            if session_id:
                if stage == JourneyStage.INTERVIEW_STARTED and survey_id:
                    self._sessions[session_id] = SessionJourney(session_id, survey_id, channel)
                    cs = self._channel_stats[channel]
                    cs["started"] += 1
                    if survey_id:
                        self._survey_stats[survey_id]["started"] += 1

                session = self._sessions.get(session_id)
                if session:
                    session.add_event(event)

                    if stage == JourneyStage.INTERVIEW_COMPLETED:
                        self._channel_stats[channel]["completed"] += 1
                        self._channel_stats[channel]["total_questions"] += session.questions_answered
                        if session.duration_seconds:
                            self._channel_stats[channel]["total_duration"] += session.duration_seconds
                        if survey_id:
                            self._survey_stats[survey_id]["completed"] += 1
                            if session.duration_seconds:
                                self._survey_stats[survey_id]["total_duration"] += session.duration_seconds
                        self._completed_sessions.append(session)
                        del self._sessions[session_id]

                    elif stage == JourneyStage.INTERVIEW_ABANDONED:
                        self._channel_stats[channel]["abandoned"] += 1
                        # Record drop-off point
                        if survey_id:
                            self._dropoff_map[survey_id][session.last_question_index] += 1
                            self._survey_stats[survey_id]["abandoned"] += 1
                        self._completed_sessions.append(session)
                        del self._sessions[session_id]

    def record_richness(self, session_id: str, score: float):
        """Record response richness score for a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.record_richness(score)

    # ── Query Methods ──

    def get_funnel(self) -> dict:
        """Get the complete journey funnel."""
        with self._lock:
            return {
                "stages": dict(self._stage_counts),
                "conversion_rates": self._calculate_conversions(),
            }

    def _calculate_conversions(self) -> dict:
        """Calculate conversion rates between funnel stages."""
        started = self._stage_counts.get("interview_started", 0)
        completed = self._stage_counts.get("interview_completed", 0)
        abandoned = self._stage_counts.get("interview_abandoned", 0)
        return {
            "start_to_complete": round(completed / max(started, 1) * 100, 2),
            "start_to_abandon": round(abandoned / max(started, 1) * 100, 2),
            "overall_completion_rate": round(completed / max(started, 1) * 100, 2),
        }

    def get_dropoff_analysis(self, survey_id: int = None) -> dict:
        """Identify which questions cause the most drop-offs."""
        with self._lock:
            if survey_id and survey_id in self._dropoff_map:
                dropoffs = dict(self._dropoff_map[survey_id])
            else:
                # Aggregate across all surveys
                dropoffs = defaultdict(int)
                for sid, question_map in self._dropoff_map.items():
                    for qi, count in question_map.items():
                        dropoffs[qi] += count
                dropoffs = dict(dropoffs)

        if not dropoffs:
            return {"dropoffs": [], "most_problematic_question": None}

        sorted_dropoffs = sorted(dropoffs.items(), key=lambda x: x[1], reverse=True)
        return {
            "dropoffs": [
                {"question_index": qi, "abandonment_count": count}
                for qi, count in sorted_dropoffs
            ],
            "most_problematic_question": sorted_dropoffs[0][0] if sorted_dropoffs else None,
            "survey_id": survey_id,
        }

    def get_channel_funnel(self) -> dict:
        """Get funnel metrics per channel (text vs voice)."""
        with self._lock:
            result = {}
            for channel, data in self._channel_stats.items():
                started = data["started"]
                completed = data["completed"]
                result[channel] = {
                    "started": started,
                    "completed": completed,
                    "abandoned": data["abandoned"],
                    "completion_rate": round(completed / max(started, 1) * 100, 2),
                    "avg_questions_per_session": round(
                        data["total_questions"] / max(completed, 1), 1
                    ),
                    "avg_duration_seconds": round(
                        data["total_duration"] / max(completed, 1), 1
                    ),
                }
            return result

    def get_survey_journey(self, survey_id: int) -> dict:
        """Get journey stats for a specific survey."""
        with self._lock:
            data = self._survey_stats.get(survey_id, {"started": 0, "completed": 0, "abandoned": 0, "total_duration": 0.0})
            started = data["started"]
            completed = data["completed"]
            return {
                "survey_id": survey_id,
                "started": started,
                "completed": completed,
                "abandoned": data["abandoned"],
                "completion_rate": round(completed / max(started, 1) * 100, 2),
                "avg_duration_seconds": round(
                    data["total_duration"] / max(completed, 1), 1
                ),
                "dropoff_analysis": self.get_dropoff_analysis(survey_id),
            }

    def get_active_sessions(self) -> List[dict]:
        """Get currently active interview sessions."""
        with self._lock:
            return [s.to_dict() for s in self._sessions.values()]

    def get_recent_journeys(self, limit: int = 20) -> List[dict]:
        """Get recently completed/abandoned session journeys."""
        with self._lock:
            sessions = list(self._completed_sessions)[-limit:]
        sessions.reverse()
        return [s.to_dict() for s in sessions]

    # ── Stats ──

    def stats(self) -> dict:
        uptime = time.time() - self._start_time
        with self._lock:
            started = self._stage_counts.get("interview_started", 0)
            completed = self._stage_counts.get("interview_completed", 0)
            abandoned = self._stage_counts.get("interview_abandoned", 0)
            return {
                "engine": "UserJourneyTracker",
                "total_events": self._total_events,
                "active_sessions": len(self._sessions),
                "completed_sessions": completed,
                "abandoned_sessions": abandoned,
                "overall_completion_rate": round(completed / max(started, 1) * 100, 2),
                "overall_abandonment_rate": round(abandoned / max(started, 1) * 100, 2),
                "channels_tracked": len(self._channel_stats),
                "surveys_tracked": len(self._survey_stats),
                "unique_stages_seen": len(self._stage_counts),
                "uptime_seconds": round(uptime, 1),
            }


# ── Global Singleton ──
journey_tracker = UserJourneyTracker()
