"""
Recommendation Service — Application Services Layer
═══════════════════════════════════════════════════════
Transforms insights into actionable recommendations.

Responsibilities:
  - Convert insights → prioritized action items
  - Priority scoring (impact × urgency / effort)
  - Roadmap suggestions with timeframes
  - Export formatting (Jira/Linear/CSV)
"""
import json
from datetime import datetime
from typing import Optional, List
from ..database import get_db
from ..services.ai_orchestrator import AIOrchestrator


class RecommendationService:
    """Transforms insights into actionable recommendations."""

    @staticmethod
    def get_recommendations(survey_id: int, sort_by: str = "priority_score") -> list:
        """Get all recommendations for a survey, sorted by priority."""
        valid_sorts = ["priority_score", "impact_score", "urgency_score", "effort_score", "created_at"]
        if sort_by not in valid_sorts:
            sort_by = "priority_score"

        conn = get_db()
        recs = conn.execute(
            f"SELECT * FROM recommendations WHERE survey_id = ? ORDER BY {sort_by} DESC",
            (survey_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in recs]

    @staticmethod
    def get_recommendation(rec_id: int) -> Optional[dict]:
        conn = get_db()
        rec = conn.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,)).fetchone()
        conn.close()
        return dict(rec) if rec else None

    @staticmethod
    def generate_recommendations_ai(survey_id: int) -> dict:
        """AI generates recommendations from survey insights."""
        from ..services.ai_service import AIService

        conn = get_db()
        insights = conn.execute(
            "SELECT * FROM insights WHERE survey_id = ? ORDER BY impact_score DESC",
            (survey_id,)
        ).fetchall()
        conn.close()

        if not insights:
            return {"recommendations": [], "message": "No insights to generate recommendations from"}

        insight_list = [dict(i) for i in insights]

        result = AIOrchestrator.execute(
            "recommendation_generation",
            f"recs:{survey_id}:{len(insight_list)}",
            AIService.generate_recommendations,
            insight_list, survey_id,
            cacheable=True
        )

        return result if isinstance(result, dict) else {"recommendations": result}

    @staticmethod
    def calculate_priority(impact: float, urgency: float, effort: float) -> float:
        """
        Priority = (Impact × Urgency) / Effort
        Higher is more important; low effort boosts priority.
        """
        effort = max(effort, 0.1)  # Avoid division by zero
        return round((impact * urgency) / effort, 3)

    @staticmethod
    def update_status(rec_id: int, status: str) -> dict:
        """Update recommendation status (pending/in_progress/completed/dismissed)."""
        valid_statuses = ["pending", "in_progress", "completed", "dismissed"]
        if status not in valid_statuses:
            return {"error": f"Invalid status. Must be one of: {valid_statuses}"}

        conn = get_db()
        conn.execute("UPDATE recommendations SET status = ? WHERE id = ?", (status, rec_id))
        conn.commit()
        conn.close()
        return {"message": f"Recommendation {rec_id} status updated to {status}"}

    @staticmethod
    def get_roadmap(survey_id: int) -> dict:
        """Get recommendations organized into a priority roadmap."""
        conn = get_db()
        recs = conn.execute(
            "SELECT * FROM recommendations WHERE survey_id = ? ORDER BY priority_score DESC",
            (survey_id,)
        ).fetchall()
        conn.close()

        roadmap = {"short": [], "medium": [], "long": []}
        for r in recs:
            rd = dict(r)
            timeframe = rd.get("timeframe", "medium")
            if timeframe in roadmap:
                roadmap[timeframe].append({
                    "id": rd["id"],
                    "title": rd["title"],
                    "description": rd["description"],
                    "action_type": rd["action_type"],
                    "priority_score": rd["priority_score"],
                    "impact_score": rd["impact_score"],
                    "effort_score": rd["effort_score"],
                    "status": rd["status"],
                })

        return {
            "roadmap": roadmap,
            "total": len(recs),
            "by_timeframe": {k: len(v) for k, v in roadmap.items()},
        }

    @staticmethod
    def export_jira(survey_id: int) -> list:
        """Export recommendations in Jira-compatible format."""
        conn = get_db()
        recs = conn.execute(
            "SELECT r.*, i.title as insight_title FROM recommendations r LEFT JOIN insights i ON r.insight_id = i.id WHERE r.survey_id = ? ORDER BY r.priority_score DESC",
            (survey_id,)
        ).fetchall()
        conn.close()

        jira_items = []
        for r in recs:
            rd = dict(r)
            priority_map = {"short": "Highest", "medium": "High", "long": "Medium"}
            jira_items.append({
                "summary": rd["title"],
                "description": f"{rd['description']}\n\nBased on insight: {rd.get('insight_title', 'N/A')}\nImpact: {rd['impact_score']}, Effort: {rd['effort_score']}",
                "priority": priority_map.get(rd.get("timeframe", "medium"), "Medium"),
                "labels": ["ai-generated", rd.get("action_type", "improvement")],
                "story_points": int(rd.get("effort_score", 0.5) * 10),
            })

        return jira_items

    @staticmethod
    def get_summary(survey_id: int) -> dict:
        """Get high-level recommendation summary."""
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) as c FROM recommendations WHERE survey_id = ?", (survey_id,)).fetchone()
        by_status = conn.execute("""
            SELECT status, COUNT(*) as c FROM recommendations WHERE survey_id = ? GROUP BY status
        """, (survey_id,)).fetchall()
        by_type = conn.execute("""
            SELECT action_type, COUNT(*) as c FROM recommendations WHERE survey_id = ? GROUP BY action_type
        """, (survey_id,)).fetchall()
        avg_priority = conn.execute(
            "SELECT AVG(priority_score) as avg_p FROM recommendations WHERE survey_id = ?", (survey_id,)
        ).fetchone()
        conn.close()

        return {
            "total": dict(total)["c"],
            "by_status": {dict(r)["status"]: dict(r)["c"] for r in by_status},
            "by_type": {dict(r)["action_type"]: dict(r)["c"] for r in by_type},
            "avg_priority": round(dict(avg_priority)["avg_p"] or 0, 3),
        }
