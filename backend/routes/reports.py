"""
Reports & Recommendations API Routes — Feature 4
Handles executive summaries, recommendations, visualizations, and exports.
"""
from fastapi import APIRouter, HTTPException, Query
from ..database import get_db
from ..models import ReportCreate
from ..services.ai_service import AIService
from typing import Optional
import json
from datetime import datetime

router = APIRouter(prefix="/api/reports", tags=["reports"])


# ── Executive Summary ──
@router.get("/summary/{survey_id}")
def get_executive_summary(
    survey_id: int,
    tone: str = Query("neutral"),
    length: str = Query("medium")
):
    """Generate AI executive summary."""
    conn = get_db()
    insights = conn.execute("SELECT * FROM insights WHERE survey_id = ? ORDER BY impact_score DESC", (survey_id,)).fetchall()
    conn.close()

    insights_list = [dict(i) for i in insights]
    summary = AIService.generate_executive_summary(insights_list, tone, length)
    return summary


@router.post("/generate")
def generate_report(report: ReportCreate):
    """Generate and store a new report."""
    conn = get_db()
    insights = conn.execute("SELECT * FROM insights WHERE survey_id = ? ORDER BY impact_score DESC", (report.survey_id,)).fetchall()
    insights_list = [dict(i) for i in insights]

    summary_data = AIService.generate_executive_summary(insights_list, report.summary_tone, report.summary_length)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reports (survey_id, title, executive_summary, summary_tone, summary_length, narrative_flow)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (report.survey_id, report.title, summary_data["summary"], report.summary_tone,
          report.summary_length, summary_data["narrative"]))
    conn.commit()
    report_id = cursor.lastrowid
    conn.close()

    return {"id": report_id, "summary": summary_data}


@router.get("/{survey_id}")
def list_reports(survey_id: int):
    conn = get_db()
    reports = conn.execute("SELECT * FROM reports WHERE survey_id = ? ORDER BY generated_at DESC", (survey_id,)).fetchall()
    conn.close()
    return [dict(r) for r in reports]


# ── Recommendations ──
@router.get("/recommendations/{survey_id}")
def get_recommendations(
    survey_id: int,
    timeframe: Optional[str] = Query(None),
    min_priority: Optional[float] = Query(None)
):
    """Get prioritized recommendations."""
    conn = get_db()
    query = """
        SELECT r.*, i.title as insight_title, i.feature_area, i.sentiment as insight_sentiment
        FROM recommendations r 
        LEFT JOIN insights i ON r.insight_id = i.id 
        WHERE r.survey_id = ?
    """
    params = [survey_id]
    if timeframe:
        query += " AND r.timeframe = ?"
        params.append(timeframe)
    if min_priority:
        query += " AND r.priority_score >= ?"
        params.append(min_priority)
    query += " ORDER BY r.priority_score DESC"

    recs = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in recs]


@router.get("/recommendations/{survey_id}/matrix")
def get_impact_effort_matrix(survey_id: int):
    """Get recommendation data for Impact vs Effort matrix."""
    conn = get_db()
    recs = conn.execute("""
        SELECT r.*, i.title as insight_title 
        FROM recommendations r 
        LEFT JOIN insights i ON r.insight_id = i.id 
        WHERE r.survey_id = ?
    """, (survey_id,)).fetchall()
    conn.close()

    matrix = {
        "quick_wins": [],     # High impact, Low effort
        "major_projects": [], # High impact, High effort
        "low_priority": [],   # Low impact, High effort
        "fill_ins": []        # Low impact, Low effort
    }

    for rec in recs:
        r = dict(rec)
        point = {
            "id": r["id"],
            "title": r["title"],
            "impact": r["impact_score"],
            "effort": r["effort_score"],
            "urgency": r["urgency_score"],
            "confidence": r["confidence"],
            "timeframe": r["timeframe"]
        }

        if r["impact_score"] >= 0.6 and r["effort_score"] <= 0.5:
            matrix["quick_wins"].append(point)
        elif r["impact_score"] >= 0.6 and r["effort_score"] > 0.5:
            matrix["major_projects"].append(point)
        elif r["impact_score"] < 0.6 and r["effort_score"] > 0.5:
            matrix["low_priority"].append(point)
        else:
            matrix["fill_ins"].append(point)

    return matrix


@router.get("/recommendations/{survey_id}/roadmap")
def get_roadmap(survey_id: int):
    """Get recommendations organized as a roadmap."""
    conn = get_db()
    recs = conn.execute("""
        SELECT r.*, i.title as insight_title, i.feature_area
        FROM recommendations r 
        LEFT JOIN insights i ON r.insight_id = i.id 
        WHERE r.survey_id = ?
        ORDER BY r.priority_score DESC
    """, (survey_id,)).fetchall()
    conn.close()

    roadmap = {
        "short": {"label": "Short-term (< 1 week)", "items": []},
        "medium": {"label": "Medium-term (2-4 weeks)", "items": []},
        "long": {"label": "Long-term (> 1 month)", "items": []}
    }

    for rec in recs:
        r = dict(rec)
        item = {
            "id": r["id"],
            "title": r["title"],
            "description": r["description"],
            "priority_score": r["priority_score"],
            "confidence": r["confidence"],
            "feature_area": r.get("feature_area", ""),
            "status": r["status"]
        }
        tf = r["timeframe"]
        if tf in roadmap:
            roadmap[tf]["items"].append(item)

    return roadmap


# ── Export ──
@router.get("/export/{survey_id}/csv")
def export_csv(survey_id: int):
    """Export recommendations as CSV-compatible data."""
    conn = get_db()
    recs = conn.execute("""
        SELECT r.title, r.description, r.action_type, r.impact_score, r.effort_score,
               r.urgency_score, r.priority_score, r.confidence, r.timeframe, r.status,
               i.feature_area, i.sentiment as insight_sentiment
        FROM recommendations r 
        LEFT JOIN insights i ON r.insight_id = i.id 
        WHERE r.survey_id = ?
        ORDER BY r.priority_score DESC
    """, (survey_id,)).fetchall()
    conn.close()

    headers = ["Title", "Description", "Type", "Impact", "Effort", "Urgency", "Priority", "Confidence", "Timeframe", "Status", "Feature Area", "Sentiment"]
    rows = [headers]
    for r in recs:
        rd = dict(r)
        rows.append([str(rd.get(k, "")) for k in ["title", "description", "action_type", "impact_score", "effort_score",
                                                     "urgency_score", "priority_score", "confidence", "timeframe", "status",
                                                     "feature_area", "insight_sentiment"]])
    return {"headers": headers, "rows": rows, "filename": f"recommendations_survey_{survey_id}.csv"}


@router.get("/export/{survey_id}/jira")
def export_jira(survey_id: int):
    """Export recommendations formatted for Jira import."""
    conn = get_db()
    recs = conn.execute("""
        SELECT r.*, i.title as insight_title, i.feature_area
        FROM recommendations r LEFT JOIN insights i ON r.insight_id = i.id
        WHERE r.survey_id = ? ORDER BY r.priority_score DESC
    """, (survey_id,)).fetchall()
    conn.close()

    jira_items = []
    for rec in recs:
        r = dict(rec)
        priority_map = {"high": "Highest", "medium": "High", "low": "Medium"}
        jira_items.append({
            "summary": r["title"],
            "description": f"{r['description']}\n\nConfidence: {int(r['confidence']*100)}%\nSupported by: {r['supporting_count']} responses",
            "priority": priority_map.get(r["timeframe"], "Medium"),
            "labels": [r.get("feature_area", ""), r["action_type"]],
            "story_points": int(r["effort_score"] * 10)
        })
    return {"items": jira_items, "format": "jira"}
