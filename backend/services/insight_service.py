"""
Insight Service — Application Services Layer
═══════════════════════════════════════════════════════
Coordination layer for AI-generated insights.

Responsibilities:
  - Coordinates AI analysis requests (does NOT run AI itself)
  - Incremental insight updates (delta, not full recomputation)
  - Theme management and clustering coordination
  - Insight filtering and retrieval
  - Contradiction detection tracking
"""
import json
from datetime import datetime
from typing import Optional, List
from ..database import get_db
from ..services.ai_orchestrator import AIOrchestrator
from ..services.event_bus import event_bus, Event, EventType


class InsightService:
    """Coordinates insight generation, retrieval, and incremental updates."""

    @staticmethod
    def get_insights(survey_id: int, filters: dict = None) -> list:
        """Get insights for a survey with optional filters."""
        conn = get_db()
        query = "SELECT * FROM insights WHERE survey_id = ?"
        params = [survey_id]

        if filters:
            if filters.get("theme_id"):
                query += " AND theme_id = ?"
                params.append(filters["theme_id"])
            if filters.get("sentiment"):
                query += " AND sentiment = ?"
                params.append(filters["sentiment"])
            if filters.get("feature_area"):
                query += " AND feature_area = ?"
                params.append(filters["feature_area"])
            if filters.get("min_confidence"):
                query += " AND confidence >= ?"
                params.append(filters["min_confidence"])
            if filters.get("insight_type"):
                query += " AND insight_type = ?"
                params.append(filters["insight_type"])

        query += " ORDER BY impact_score DESC, frequency DESC"
        insights = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(i) for i in insights]

    @staticmethod
    def get_themes(survey_id: int) -> list:
        """Get all themes for a survey."""
        conn = get_db()
        themes = conn.execute(
            "SELECT * FROM themes WHERE survey_id = ? ORDER BY frequency DESC",
            (survey_id,)
        ).fetchall()
        conn.close()
        return [dict(t) for t in themes]

    @staticmethod
    def get_sentiment_timeline(survey_id: int, feature_area: str = None) -> list:
        """Get sentiment over time for a survey."""
        conn = get_db()
        query = "SELECT * FROM sentiment_records WHERE survey_id = ?"
        params = [survey_id]
        if feature_area:
            query += " AND feature_area = ?"
            params.append(feature_area)
        query += " ORDER BY recorded_at"
        records = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in records]

    @staticmethod
    def generate_insights_ai(survey_id: int) -> dict:
        """
        Trigger full AI insight generation for a survey.
        Uses the AI Orchestrator for caching and cost tracking.
        """
        from ..services.ai_service import AIService

        conn = get_db()
        # Gather all responses
        responses = conn.execute("""
            SELECT r.response_text, r.sentiment_score, r.emotion, r.quality_score
            FROM responses r
            JOIN interview_sessions s ON r.session_id = s.session_id
            WHERE s.survey_id = ? AND r.response_text IS NOT NULL
            ORDER BY r.created_at DESC LIMIT 200
        """, (survey_id,)).fetchall()

        existing_themes = conn.execute(
            "SELECT name, description, frequency FROM themes WHERE survey_id = ?",
            (survey_id,)
        ).fetchall()
        conn.close()

        resp_list = [dict(r) for r in responses]
        theme_list = [dict(t) for t in existing_themes]

        if not resp_list:
            return {"insights": [], "message": "No responses to analyze"}

        # Use orchestrator for caching & cost tracking
        result = AIOrchestrator.execute(
            "full_insight_generation",
            f"insights:{survey_id}:{len(resp_list)}",
            AIService.generate_full_insights,
            resp_list, theme_list, survey_id,
            cacheable=True
        )

        return result if isinstance(result, dict) else {"insights": result}

    @staticmethod
    def incremental_update(survey_id: int, new_response_text: str) -> dict:
        """
        Incremental Intelligence Updating — delta update, NOT full recomputation.

        Architecture principle: "Only calculate the delta from the new response."
        """
        conn = get_db()

        # Get current insights
        current_insights = conn.execute(
            "SELECT id, title, feature_area, frequency, sentiment, confidence FROM insights WHERE survey_id = ?",
            (survey_id,)
        ).fetchall()

        updates_made = 0
        response_lower = new_response_text.lower()

        for insight in current_insights:
            insight_dict = dict(insight)
            # Simple keyword matching for incremental relevance check
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
                updates_made += 1

        conn.commit()
        conn.close()

        # Publish event
        if updates_made > 0:
            event_bus.publish(Event(
                EventType.INSIGHT_DISCOVERED,
                {"survey_id": survey_id, "delta_updates": updates_made},
                source="insight_service"
            ))

        return {"updates": updates_made, "method": "incremental_delta"}

    @staticmethod
    def detect_contradictions(survey_id: int) -> list:
        """Find contradictory insights within a survey."""
        conn = get_db()
        insights = conn.execute(
            "SELECT * FROM insights WHERE survey_id = ? ORDER BY feature_area",
            (survey_id,)
        ).fetchall()
        conn.close()

        contradictions = []
        insight_list = [dict(i) for i in insights]

        # Group by feature area and look for sentiment conflicts
        from collections import defaultdict
        by_feature = defaultdict(list)
        for ins in insight_list:
            fa = ins.get("feature_area", "general")
            by_feature[fa].append(ins)

        for feature, group in by_feature.items():
            positive = [i for i in group if i.get("sentiment") == "positive"]
            negative = [i for i in group if i.get("sentiment") == "negative"]

            if positive and negative:
                for p in positive:
                    for n in negative:
                        contradictions.append({
                            "feature_area": feature,
                            "positive_insight": p["title"],
                            "negative_insight": n["title"],
                            "positive_id": p["id"],
                            "negative_id": n["id"],
                        })

        return contradictions

    @staticmethod
    def get_emerging_themes(survey_id: int) -> list:
        """Get themes that are newly emerging (recent and fast-growing)."""
        conn = get_db()
        themes = conn.execute(
            "SELECT * FROM themes WHERE survey_id = ? AND is_emerging = 1 ORDER BY frequency DESC",
            (survey_id,)
        ).fetchall()
        conn.close()
        return [dict(t) for t in themes]

    @staticmethod
    def get_insight_summary(survey_id: int) -> dict:
        """Get a high-level summary of insights for a survey."""
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) as c FROM insights WHERE survey_id = ?", (survey_id,)).fetchone()
        by_type = conn.execute("""
            SELECT insight_type, COUNT(*) as c FROM insights WHERE survey_id = ? GROUP BY insight_type
        """, (survey_id,)).fetchall()
        by_sentiment = conn.execute("""
            SELECT sentiment, COUNT(*) as c FROM insights WHERE survey_id = ? GROUP BY sentiment
        """, (survey_id,)).fetchall()
        avg_confidence = conn.execute(
            "SELECT AVG(confidence) as avg_conf FROM insights WHERE survey_id = ?", (survey_id,)
        ).fetchone()
        avg_impact = conn.execute(
            "SELECT AVG(impact_score) as avg_imp FROM insights WHERE survey_id = ?", (survey_id,)
        ).fetchone()
        conn.close()

        return {
            "total_insights": dict(total)["c"],
            "by_type": {dict(r)["insight_type"]: dict(r)["c"] for r in by_type},
            "by_sentiment": {dict(r)["sentiment"]: dict(r)["c"] for r in by_sentiment},
            "avg_confidence": round(dict(avg_confidence)["avg_conf"] or 0, 3),
            "avg_impact": round(dict(avg_impact)["avg_imp"] or 0, 3),
        }
