"""
Continuous Intelligence Loop — Section 10: Self-Improving System
═══════════════════════════════════════════════════════════════════
Architecture: The real innovation — a self-improving feedback loop.

New Feedback → AI Understanding → Updated Insight → New Recommendation
→ Product Improvement → New Feedback (repeat)

This module implements:
  1. Smart Triggering (Section 8) — Run pipelines only when thresholds met
  2. Batch Processing (Section 8) — 100 responses → 1 clustering call
  3. Continuous Intelligence Loop (Section 10) — Auto-chain pipelines
  4. Human-in-the-Loop tracking (Section 9) — Corrections improve future output

The loop monitors incoming data, decides WHEN to trigger intelligence
pipelines, and chains them together for continuous learning.
"""
import json
import time
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from ..database import get_db


# ═══════════════════════════════════════════════════
# SMART TRIGGER THRESHOLDS (Section 8)
# ═══════════════════════════════════════════════════
class SmartTriggerConfig:
    """Thresholds that determine when intelligence pipelines should fire."""

    # Run insight pipeline when N new responses since last run
    RESPONSE_THRESHOLD = 10

    # Run trend analysis when sentiment shift exceeds this
    SENTIMENT_SHIFT_THRESHOLD = 0.3

    # Run recommendation update when N new insights since last run
    INSIGHT_THRESHOLD = 5

    # Minimum time between pipeline runs (seconds) — prevents stampede
    MIN_PIPELINE_INTERVAL_SECONDS = 60

    # Batch size for clustering (100 responses → 1 AI call)
    BATCH_CLUSTERING_SIZE = 100


# ═══════════════════════════════════════════════════
# INTELLIGENCE LOOP STATE TRACKER
# ═══════════════════════════════════════════════════
class IntelligenceLoopState:
    """
    Tracks the state of the intelligence loop for each survey.
    Determines when to trigger the next pipeline run.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Track per-survey state
        self._survey_state: Dict[int, dict] = {}
        # Global counters
        self._total_triggers = 0
        self._total_batches = 0
        self._total_corrections = 0

    def get_survey_state(self, survey_id: int) -> dict:
        """Get or create state for a survey."""
        with self._lock:
            if survey_id not in self._survey_state:
                self._survey_state[survey_id] = {
                    "responses_since_last_insight": 0,
                    "insights_since_last_recommendation": 0,
                    "last_insight_pipeline_run": 0,
                    "last_recommendation_pipeline_run": 0,
                    "last_executive_pipeline_run": 0,
                    "last_trend_analysis_run": 0,
                    "avg_sentiment": 0.0,
                    "prev_avg_sentiment": 0.0,
                    "total_responses": 0,
                    "pending_batch": [],
                }
            return self._survey_state[survey_id]

    def record_response(self, survey_id: int, response_text: str = "") -> dict:
        """
        Record a new response and check if any pipelines should trigger.

        Returns:
            {"trigger_insight": bool, "trigger_batch": bool, "batch_ready": list or None}
        """
        state = self.get_survey_state(survey_id)
        triggers = {"trigger_insight": False, "trigger_batch": False, "batch_ready": None}

        with self._lock:
            state["responses_since_last_insight"] += 1
            state["total_responses"] += 1

            # Add to pending batch
            if response_text:
                state["pending_batch"].append({
                    "response_text": response_text[:300],
                    "added_at": datetime.now().isoformat(),
                })

            # ── Smart Trigger: Response threshold ──
            now = time.time()
            time_since_last = now - state["last_insight_pipeline_run"]

            if (state["responses_since_last_insight"] >= SmartTriggerConfig.RESPONSE_THRESHOLD
                    and time_since_last >= SmartTriggerConfig.MIN_PIPELINE_INTERVAL_SECONDS):
                triggers["trigger_insight"] = True
                state["responses_since_last_insight"] = 0
                state["last_insight_pipeline_run"] = now
                self._total_triggers += 1

            # ── Batch Processing Trigger ──
            if len(state["pending_batch"]) >= SmartTriggerConfig.BATCH_CLUSTERING_SIZE:
                triggers["trigger_batch"] = True
                triggers["batch_ready"] = state["pending_batch"][:SmartTriggerConfig.BATCH_CLUSTERING_SIZE]
                state["pending_batch"] = state["pending_batch"][SmartTriggerConfig.BATCH_CLUSTERING_SIZE:]
                self._total_batches += 1

        return triggers

    def record_insight(self, survey_id: int) -> dict:
        """
        Record a new insight and check if recommendation pipeline should trigger.
        """
        state = self.get_survey_state(survey_id)
        triggers = {"trigger_recommendation": False}

        with self._lock:
            state["insights_since_last_recommendation"] += 1
            now = time.time()
            time_since_last = now - state["last_recommendation_pipeline_run"]

            if (state["insights_since_last_recommendation"] >= SmartTriggerConfig.INSIGHT_THRESHOLD
                    and time_since_last >= SmartTriggerConfig.MIN_PIPELINE_INTERVAL_SECONDS):
                triggers["trigger_recommendation"] = True
                state["insights_since_last_recommendation"] = 0
                state["last_recommendation_pipeline_run"] = now
                self._total_triggers += 1

        return triggers

    def record_sentiment_shift(self, survey_id: int, new_avg_sentiment: float) -> dict:
        """
        Record sentiment change and check if trend analysis should trigger.
        """
        state = self.get_survey_state(survey_id)
        triggers = {"trigger_trend_analysis": False, "shift_magnitude": 0.0}

        with self._lock:
            prev = state["avg_sentiment"]
            state["prev_avg_sentiment"] = prev
            state["avg_sentiment"] = new_avg_sentiment

            shift = abs(new_avg_sentiment - prev)
            triggers["shift_magnitude"] = round(shift, 3)

            if shift >= SmartTriggerConfig.SENTIMENT_SHIFT_THRESHOLD:
                now = time.time()
                if now - state["last_trend_analysis_run"] >= SmartTriggerConfig.MIN_PIPELINE_INTERVAL_SECONDS:
                    triggers["trigger_trend_analysis"] = True
                    state["last_trend_analysis_run"] = now
                    self._total_triggers += 1

        return triggers

    def record_correction(self, survey_id: int, correction_type: str):
        """Record a human-in-the-loop correction (Section 9)."""
        with self._lock:
            self._total_corrections += 1

    def stats(self) -> dict:
        return {
            "surveys_tracked": len(self._survey_state),
            "total_triggers_fired": self._total_triggers,
            "total_batches_processed": self._total_batches,
            "total_hitl_corrections": self._total_corrections,
            "config": {
                "response_threshold": SmartTriggerConfig.RESPONSE_THRESHOLD,
                "sentiment_shift_threshold": SmartTriggerConfig.SENTIMENT_SHIFT_THRESHOLD,
                "insight_threshold": SmartTriggerConfig.INSIGHT_THRESHOLD,
                "min_interval_seconds": SmartTriggerConfig.MIN_PIPELINE_INTERVAL_SECONDS,
                "batch_size": SmartTriggerConfig.BATCH_CLUSTERING_SIZE,
            },
        }


# ═══════════════════════════════════════════════════
# GLOBAL SINGLETON
# ═══════════════════════════════════════════════════
_intelligence_loop = IntelligenceLoopState()


# ═══════════════════════════════════════════════════
# CONTINUOUS INTELLIGENCE LOOP — Pipeline Chaining
# ═══════════════════════════════════════════════════
class ContinuousIntelligenceLoop:
    """
    Orchestrates the continuous intelligence loop:

    Response → Understanding → Insight → Recommendation → Report

    Each step in the loop can trigger the next based on smart thresholds.
    This is the "self-improving system" described in Section 10.
    """

    @staticmethod
    def on_response_submitted(survey_id: int, session_id: str,
                              response_text: str, response_id: int = None):
        """
        Entry point: A new response has been submitted.
        Triggers the intelligence loop chain if thresholds are met.

        Flow:
            1. Always: Run Response Understanding (Pipeline B)
            2. If threshold met: Run Insight Formation (Pipeline C)
            3. If insights updated: Run Recommendation Update (Pipeline D)
            4. Store results
        """
        from ..services.ai_pipelines import (
            ResponseUnderstandingPipeline, InsightFormationPipeline,
            RecommendationEnginePipeline
        )
        from ..services.context_builder import AIContextBuilder
        from ..services.event_bus import event_bus, Event, EventType

        # ── Step 1: Build context and run Response Understanding ──
        context = AIContextBuilder.build_response_context(
            survey_id=survey_id, session_id=session_id,
            response_text=response_text
        )
        context["response_text"] = response_text

        understanding = ResponseUnderstandingPipeline.execute(
            context, task_type="response_understanding"
        )

        # Store understanding results
        if understanding.get("valid") and understanding.get("result"):
            _store_understanding_results(
                survey_id, session_id, response_id, understanding["result"]
            )

        # ── Step 2: Check smart triggers ──
        triggers = _intelligence_loop.record_response(survey_id, response_text)

        # ── Step 3: If threshold met → Run Insight Formation ──
        if triggers.get("trigger_insight") or triggers.get("trigger_batch"):
            insight_context = AIContextBuilder.build_insight_context(
                survey_id=survey_id,
                response_batch=triggers.get("batch_ready")
            )

            insight_result = InsightFormationPipeline.execute(
                insight_context, task_type="insight_clustering"
            )

            if insight_result.get("valid") and insight_result.get("result"):
                _store_insight_results(survey_id, insight_result["result"])

                # Publish insight event
                event_bus.publish(Event(
                    EventType.INSIGHT_DISCOVERED,
                    {"survey_id": survey_id, "themes_count": insight_result["result"].get("theme_count", 0)},
                    source="intelligence_loop"
                ))

                # ── Step 4: Check if recommendations should update ──
                rec_triggers = _intelligence_loop.record_insight(survey_id)

                if rec_triggers.get("trigger_recommendation"):
                    rec_context = AIContextBuilder.build_recommendation_context(survey_id)

                    rec_result = RecommendationEnginePipeline.execute(
                        rec_context, task_type="recommendation_generation"
                    )

                    if rec_result.get("valid") and rec_result.get("result"):
                        _store_recommendation_results(survey_id, rec_result["result"])

        # ── Step 5: Check for sentiment shift ──
        sentiment = understanding.get("result", {}).get("sentiment", {})
        if sentiment and isinstance(sentiment, dict):
            new_score = sentiment.get("sentiment_score", 0)
            shift_triggers = _intelligence_loop.record_sentiment_shift(survey_id, new_score)

            if shift_triggers.get("trigger_trend_analysis"):
                event_bus.publish(Event(
                    EventType.SENTIMENT_SHIFT_DETECTED,
                    {
                        "survey_id": survey_id,
                        "shift_magnitude": shift_triggers["shift_magnitude"],
                        "shift_info": f"Sentiment shifted by {shift_triggers['shift_magnitude']:.2f}",
                    },
                    source="intelligence_loop"
                ))

    @staticmethod
    def on_interview_completed(survey_id: int, session_id: str,
                               conversation_history: list = None):
        """
        Entry point: An interview has been completed.
        Generates transcript report and triggers insight pipeline.
        """
        from ..services.ai_pipelines import ExecutiveIntelligencePipeline
        from ..services.context_builder import AIContextBuilder

        if conversation_history:
            context = {
                "conversation_history": conversation_history,
                "survey_goal": "",
            }

            # Get survey goal
            try:
                conn = get_db()
                survey = conn.execute("""
                    SELECT rg.parsed_goal FROM surveys s
                    LEFT JOIN research_goals rg ON s.research_goal_id = rg.id
                    WHERE s.id = ?
                """, (survey_id,)).fetchone()
                conn.close()
                if survey:
                    context["survey_goal"] = dict(survey).get("parsed_goal", "")
            except Exception:
                pass

            # Generate transcript report
            ExecutiveIntelligencePipeline.execute(context, task_type="transcript_report")

    @staticmethod
    def on_insight_discovered(survey_id: int):
        """
        Entry point: New insights were discovered.
        Check if recommendation pipeline should trigger.
        """
        triggers = _intelligence_loop.record_insight(survey_id)

        if triggers.get("trigger_recommendation"):
            from ..services.ai_pipelines import RecommendationEnginePipeline
            from ..services.context_builder import AIContextBuilder

            rec_context = AIContextBuilder.build_recommendation_context(survey_id)
            result = RecommendationEnginePipeline.execute(
                rec_context, task_type="recommendation_generation"
            )
            if result.get("valid") and result.get("result"):
                _store_recommendation_results(survey_id, result["result"])

    @staticmethod
    def force_full_pipeline(survey_id: int) -> dict:
        """
        Force-run the full intelligence pipeline for a survey.
        Ignores thresholds — runs all pipelines in sequence.
        Used by admin or on-demand report generation.
        """
        from ..services.ai_pipelines import (
            InsightFormationPipeline, RecommendationEnginePipeline,
            ExecutiveIntelligencePipeline
        )
        from ..services.context_builder import AIContextBuilder

        results = {"stages": []}

        # Stage 1: Insight Formation
        insight_ctx = AIContextBuilder.build_insight_context(survey_id)
        insight_result = InsightFormationPipeline.execute(insight_ctx, "insight_clustering")
        results["stages"].append({
            "pipeline": "insight_formation",
            "valid": insight_result.get("valid", False),
            "latency_ms": insight_result.get("latency_ms", 0),
        })

        if insight_result.get("valid") and insight_result.get("result"):
            _store_insight_results(survey_id, insight_result["result"])

        # Stage 2: Recommendation Engine
        rec_ctx = AIContextBuilder.build_recommendation_context(survey_id)
        rec_result = RecommendationEnginePipeline.execute(rec_ctx, "recommendation_generation")
        results["stages"].append({
            "pipeline": "recommendation_engine",
            "valid": rec_result.get("valid", False),
            "latency_ms": rec_result.get("latency_ms", 0),
        })

        if rec_result.get("valid") and rec_result.get("result"):
            _store_recommendation_results(survey_id, rec_result["result"])

        # Stage 3: Executive Summary
        exec_ctx = AIContextBuilder.build_executive_context(survey_id)
        exec_result = ExecutiveIntelligencePipeline.execute(exec_ctx, "executive_summary")
        results["stages"].append({
            "pipeline": "executive_intelligence",
            "valid": exec_result.get("valid", False),
            "latency_ms": exec_result.get("latency_ms", 0),
        })

        if exec_result.get("valid") and exec_result.get("result"):
            _store_executive_report(survey_id, exec_result["result"])

        results["completed_at"] = datetime.now().isoformat()
        results["total_latency_ms"] = sum(s.get("latency_ms", 0) for s in results["stages"])

        return results

    @staticmethod
    def get_loop_stats() -> dict:
        """Get intelligence loop statistics."""
        from ..services.ai_pipelines import get_all_pipeline_stats
        from ..services.ai_validation import AIOutputValidator

        return {
            "loop_state": _intelligence_loop.stats(),
            "pipeline_stats": get_all_pipeline_stats(),
            "validation_stats": AIOutputValidator.stats(),
        }


# ═══════════════════════════════════════════════════
# HUMAN-IN-THE-LOOP (Section 9)
# ═══════════════════════════════════════════════════
class HumanInTheLoop:
    """
    Allows manual correction of AI outputs.
    AI learns from corrections over time.

    Capabilities:
      - Manual insight correction
      - Recommendation approval/rejection
      - Feedback validation
    """

    @staticmethod
    def correct_insight(insight_id: int, corrections: dict) -> dict:
        """
        Apply human corrections to an AI-generated insight.

        Args:
            insight_id: The insight to correct
            corrections: Dict with fields to update (title, description, sentiment, etc.)
        """
        conn = get_db()
        insight = conn.execute("SELECT * FROM insights WHERE id = ?", (insight_id,)).fetchone()

        if not insight:
            conn.close()
            return {"success": False, "error": "Insight not found"}

        original = dict(insight)
        update_fields = []
        update_values = []

        for field in ["title", "description", "sentiment", "feature_area",
                       "insight_type", "impact_score", "confidence"]:
            if field in corrections:
                update_fields.append(f"{field} = ?")
                update_values.append(corrections[field])

        if update_fields:
            update_values.append(insight_id)
            conn.execute(
                f"UPDATE insights SET {', '.join(update_fields)} WHERE id = ?",
                update_values
            )

            # Log the correction
            conn.execute("""
                INSERT INTO hitl_corrections (entity_type, entity_id, original_data,
                    corrected_data, correction_type, created_at)
                VALUES (?, ?, ?, ?, 'insight_correction', ?)
            """, ("insight", insight_id, json.dumps(original),
                  json.dumps(corrections), datetime.now().isoformat()))

            conn.commit()

        conn.close()
        _intelligence_loop.record_correction(original.get("survey_id", 0), "insight")

        return {"success": True, "insight_id": insight_id, "fields_updated": list(corrections.keys())}

    @staticmethod
    def approve_recommendation(recommendation_id: int, approved: bool,
                               notes: str = "") -> dict:
        """Approve or reject an AI-generated recommendation."""
        conn = get_db()
        rec = conn.execute("SELECT * FROM recommendations WHERE id = ?", (recommendation_id,)).fetchone()

        if not rec:
            conn.close()
            return {"success": False, "error": "Recommendation not found"}

        status = "approved" if approved else "rejected"
        conn.execute(
            "UPDATE recommendations SET status = ? WHERE id = ?",
            (status, recommendation_id)
        )

        # Log the decision
        conn.execute("""
            INSERT INTO hitl_corrections (entity_type, entity_id, original_data,
                corrected_data, correction_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("recommendation", recommendation_id,
              json.dumps(dict(rec)),
              json.dumps({"status": status, "notes": notes}),
              "recommendation_approval",
              datetime.now().isoformat()))

        conn.commit()
        conn.close()

        _intelligence_loop.record_correction(dict(rec).get("survey_id", 0), "recommendation")

        return {"success": True, "recommendation_id": recommendation_id, "status": status}

    @staticmethod
    def validate_theme(theme_id: int, valid: bool, corrected_name: str = None) -> dict:
        """Validate or correct an AI-generated theme."""
        conn = get_db()
        theme = conn.execute("SELECT * FROM themes WHERE id = ?", (theme_id,)).fetchone()

        if not theme:
            conn.close()
            return {"success": False, "error": "Theme not found"}

        if not valid:
            # Mark as invalid — reduce frequency / remove
            conn.execute(
                "UPDATE themes SET frequency = MAX(frequency - 1, 0) WHERE id = ?",
                (theme_id,)
            )
        elif corrected_name:
            conn.execute(
                "UPDATE themes SET name = ? WHERE id = ?",
                (corrected_name, theme_id)
            )

        # Log correction
        conn.execute("""
            INSERT INTO hitl_corrections (entity_type, entity_id, original_data,
                corrected_data, correction_type, created_at)
            VALUES (?, ?, ?, ?, 'theme_validation', ?)
        """, ("theme", theme_id, json.dumps(dict(theme)),
              json.dumps({"valid": valid, "corrected_name": corrected_name}),
              datetime.now().isoformat()))

        conn.commit()
        conn.close()

        _intelligence_loop.record_correction(dict(theme).get("survey_id", 0), "theme")

        return {"success": True, "theme_id": theme_id, "valid": valid}

    @staticmethod
    def get_corrections(survey_id: int = None, limit: int = 50) -> list:
        """Get history of human corrections."""
        conn = get_db()
        if survey_id:
            corrections = conn.execute("""
                SELECT h.* FROM hitl_corrections h
                WHERE h.entity_id IN (
                    SELECT id FROM insights WHERE survey_id = ?
                    UNION SELECT id FROM recommendations WHERE survey_id = ?
                    UNION SELECT id FROM themes WHERE survey_id = ?
                )
                ORDER BY h.created_at DESC LIMIT ?
            """, (survey_id, survey_id, survey_id, limit)).fetchall()
        else:
            corrections = conn.execute(
                "SELECT * FROM hitl_corrections ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        conn.close()
        return [dict(c) for c in corrections]


# ═══════════════════════════════════════════════════
# STORAGE HELPERS
# ═══════════════════════════════════════════════════
def _store_understanding_results(survey_id: int, session_id: str,
                                 response_id: int, understanding: dict):
    """Store Response Understanding pipeline results in the database."""
    try:
        conn = get_db()

        # Store sentiment
        sentiment = understanding.get("sentiment", {})
        if sentiment and isinstance(sentiment, dict):
            conn.execute("""
                INSERT INTO sentiment_records (survey_id, response_id, sentiment_label,
                    sentiment_score, emotion, emotion_intensity, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (survey_id, response_id,
                  sentiment.get("sentiment_label", "neutral"),
                  sentiment.get("sentiment_score", 0),
                  sentiment.get("emotion", "neutral"),
                  sentiment.get("emotion_intensity", 0),
                  sentiment.get("confidence", 0.5)))

        # Store segments
        segments = understanding.get("segments", [])
        if segments and isinstance(segments, list):
            for seg in segments:
                conn.execute("""
                    INSERT INTO response_segments (response_id, segment_text, topic,
                        sentiment_label, sentiment_score, emotion, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (response_id,
                      seg.get("segment_text", ""),
                      seg.get("topic", "general"),
                      seg.get("sentiment_label", "neutral"),
                      seg.get("sentiment_score", 0),
                      seg.get("emotion", "neutral"),
                      seg.get("confidence", 0.7)))

        # Store quality score on the response
        quality = understanding.get("quality", {})
        if quality and isinstance(quality, dict):
            conn.execute("""
                UPDATE responses SET quality_score = ?, needs_follow_up = ?
                WHERE id = ?
            """, (quality.get("quality_score", 0.5),
                  1 if quality.get("needs_follow_up") else 0,
                  response_id))

        # Store semantic memories
        memories = understanding.get("extracted_memory", [])
        if memories and isinstance(memories, list):
            for mem in memories:
                conn.execute("""
                    INSERT INTO semantic_memory (session_id, entity, relation, value,
                        confidence, source_response_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, mem.get("entity", ""), mem.get("relation", ""),
                      mem.get("value", ""), mem.get("confidence", 0.5), response_id))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[IntelligenceLoop] Failed to store understanding results: {e}")


def _store_insight_results(survey_id: int, insight_data: dict):
    """Store Insight Formation pipeline results in the database."""
    try:
        conn = get_db()
        themes = insight_data.get("themes", [])

        for theme in themes:
            existing = conn.execute(
                "SELECT id, frequency FROM themes WHERE survey_id = ? AND name = ?",
                (survey_id, theme.get("name", ""))
            ).fetchone()

            if existing:
                conn.execute("""
                    UPDATE themes SET frequency = frequency + 1,
                        sentiment_avg = ?, updated_at = ?
                    WHERE id = ?
                """, (theme.get("sentiment_avg", 0), datetime.now().isoformat(),
                      dict(existing)["id"]))
            else:
                conn.execute("""
                    INSERT INTO themes (survey_id, name, description, frequency,
                        sentiment_avg, priority, business_risk, is_emerging)
                    VALUES (?, ?, ?, 1, ?, ?, ?, ?)
                """, (survey_id, theme.get("name", "Unknown"),
                      theme.get("description", ""),
                      theme.get("sentiment_avg", 0),
                      theme.get("priority", "medium"),
                      theme.get("business_risk", "low"),
                      1 if theme.get("is_emerging") else 0))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[IntelligenceLoop] Failed to store insight results: {e}")


def _store_recommendation_results(survey_id: int, rec_data: dict):
    """Store Recommendation Engine pipeline results in the database."""
    try:
        conn = get_db()
        recommendations = rec_data.get("recommendations", [])

        for rec in recommendations:
            # Check for existing recommendation with same title
            existing = conn.execute(
                "SELECT id FROM recommendations WHERE survey_id = ? AND title = ?",
                (survey_id, rec.get("title", ""))
            ).fetchone()

            if existing:
                conn.execute("""
                    UPDATE recommendations SET description = ?, category = ?,
                        priority_score = ?, impact_score = ?, urgency_score = ?,
                        effort_score = ?, roadmap_phase = ?, updated_at = ?
                    WHERE id = ?
                """, (rec.get("description", ""), rec.get("category", ""),
                      rec.get("priority_score", 0), rec.get("impact_score", 0),
                      rec.get("urgency_score", 0), rec.get("effort_score", 0),
                      rec.get("roadmap_phase", ""), datetime.now().isoformat(),
                      dict(existing)["id"]))
            else:
                conn.execute("""
                    INSERT INTO recommendations (survey_id, title, description, category,
                        priority_score, impact_score, urgency_score, effort_score,
                        roadmap_phase, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """, (survey_id, rec.get("title", ""),
                      rec.get("description", ""), rec.get("category", ""),
                      rec.get("priority_score", 0), rec.get("impact_score", 0),
                      rec.get("urgency_score", 0), rec.get("effort_score", 0),
                      rec.get("roadmap_phase", "")))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[IntelligenceLoop] Failed to store recommendation results: {e}")


def _store_executive_report(survey_id: int, report_data: dict):
    """Store Executive Intelligence pipeline report in the database."""
    try:
        conn = get_db()
        conn.execute("""
            INSERT INTO reports (survey_id, report_type, content, generated_at)
            VALUES (?, 'executive_intelligence', ?, ?)
        """, (survey_id, json.dumps(report_data), datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[IntelligenceLoop] Failed to store executive report: {e}")
