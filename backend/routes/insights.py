"""
Insight Engine API Routes — Feature 3
Architecture: Routes delegate to InsightService for business logic.
Handles themes, insights, sentiment, patterns, contradictions, and incremental updates.
"""
from fastapi import APIRouter, HTTPException, Query
from ..database import get_db
from ..services.ai_service import AIService
from ..services.insight_service import InsightService
from ..services.ai_service import _ask_gemini_json
from typing import Optional
import json

router = APIRouter(prefix="/api/insights", tags=["insights"])


# ── Themes ──
@router.get("/themes/{survey_id}")
def get_themes(survey_id: int):
    conn = get_db()
    themes = conn.execute("""
        SELECT * FROM themes WHERE survey_id = ? ORDER BY frequency DESC
    """, (survey_id,)).fetchall()
    conn.close()
    return [dict(t) for t in themes]


@router.get("/themes/{survey_id}/bubble-data")
def get_theme_bubble_data(survey_id: int):
    """Get theme data formatted for bubble chart visualization."""
    conn = get_db()
    themes = conn.execute("SELECT * FROM themes WHERE survey_id = ? ORDER BY frequency DESC", (survey_id,)).fetchall()
    conn.close()

    bubbles = []
    for t in themes:
        td = dict(t)
        bubbles.append({
            "id": td["id"],
            "name": td["name"],
            "value": td["frequency"],
            "sentiment": td["sentiment_avg"],
            "intensity": td["emotion_intensity"],
            "priority": td["priority"],
            "is_emerging": bool(td["is_emerging"]),
            "color": _sentiment_color(td["sentiment_avg"])
        })
    return bubbles


# ── Insights ──
@router.get("/{survey_id}")
def get_insights(
    survey_id: int,
    theme_id: Optional[int] = Query(None),
    sentiment: Optional[str] = Query(None),
    feature_area: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None),
    insight_type: Optional[str] = Query(None)
):
    """Get insights with optional filters."""
    conn = get_db()
    query = "SELECT i.*, t.name as theme_name FROM insights i LEFT JOIN themes t ON i.theme_id = t.id WHERE i.survey_id = ?"
    params = [survey_id]

    if theme_id:
        query += " AND i.theme_id = ?"
        params.append(theme_id)
    if sentiment:
        query += " AND i.sentiment = ?"
        params.append(sentiment)
    if feature_area:
        query += " AND i.feature_area = ?"
        params.append(feature_area)
    if min_confidence:
        query += " AND i.confidence >= ?"
        params.append(min_confidence)
    if insight_type:
        query += " AND i.insight_type = ?"
        params.append(insight_type)

    query += " ORDER BY i.impact_score DESC"
    insights = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(i) for i in insights]


@router.get("/{survey_id}/summary")
def get_insight_summary(survey_id: int):
    """Get aggregated insight summary for dashboard."""
    conn = get_db()
    insights = conn.execute("SELECT * FROM insights WHERE survey_id = ?", (survey_id,)).fetchall()
    themes = conn.execute("SELECT * FROM themes WHERE survey_id = ?", (survey_id,)).fetchall()

    total_responses = conn.execute(
        "SELECT COUNT(*) as c FROM responses r JOIN interview_sessions s ON r.session_id = s.session_id WHERE s.survey_id = ?",
        (survey_id,)
    ).fetchone()

    sentiment_dist = conn.execute("""
        SELECT sentiment, COUNT(*) as count FROM insights WHERE survey_id = ? GROUP BY sentiment
    """, (survey_id,)).fetchall()

    feature_areas = conn.execute("""
        SELECT feature_area, COUNT(*) as count, AVG(impact_score) as avg_impact
        FROM insights WHERE survey_id = ? GROUP BY feature_area
    """, (survey_id,)).fetchall()

    conn.close()

    return {
        "total_insights": len(insights),
        "total_themes": len(themes),
        "total_responses": dict(total_responses)["c"] if total_responses else 0,
        "sentiment_distribution": [dict(s) for s in sentiment_dist],
        "feature_areas": [dict(f) for f in feature_areas],
        "top_insights": [dict(i) for i in sorted(insights, key=lambda x: x["impact_score"], reverse=True)[:5]],
        "emerging_themes": [dict(t) for t in themes if t["is_emerging"]]
    }


# ── Sentiment ──
@router.get("/sentiment/{survey_id}")
def get_sentiment_data(survey_id: int, feature_area: Optional[str] = Query(None)):
    """Get sentiment records for heatmaps and trend charts."""
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


@router.get("/sentiment/{survey_id}/heatmap")
def get_sentiment_heatmap(survey_id: int):
    """Get sentiment data formatted for heatmap visualization."""
    conn = get_db()
    records = conn.execute("""
        SELECT feature_area, 
               strftime('%Y-%m-%d', recorded_at) as date,
               AVG(sentiment_score) as avg_sentiment
        FROM sentiment_records 
        WHERE survey_id = ?
        GROUP BY feature_area, date
        ORDER BY date
    """, (survey_id,)).fetchall()
    conn.close()

    heatmap = {}
    for r in records:
        rd = dict(r)
        if rd["feature_area"] not in heatmap:
            heatmap[rd["feature_area"]] = []
        heatmap[rd["feature_area"]].append({
            "date": rd["date"],
            "value": round(rd["avg_sentiment"], 2)
        })
    return heatmap


@router.get("/sentiment/{survey_id}/trends")
def get_sentiment_trends(survey_id: int):
    """Get sentiment trend data over time."""
    conn = get_db()
    trends = conn.execute("""
        SELECT feature_area,
               strftime('%Y-%m-%d', recorded_at) as date,
               AVG(sentiment_score) as avg_sentiment,
               AVG(emotion_intensity) as avg_intensity
        FROM sentiment_records 
        WHERE survey_id = ?
        GROUP BY feature_area, date
        ORDER BY date
    """, (survey_id,)).fetchall()
    conn.close()

    grouped = {}
    for t in trends:
        td = dict(t)
        if td["feature_area"] not in grouped:
            grouped[td["feature_area"]] = []
        grouped[td["feature_area"]].append({
            "date": td["date"],
            "sentiment": round(td["avg_sentiment"], 2),
            "intensity": round(td["avg_intensity"], 2)
        })
    return grouped


# ── Pattern Detection ──
@router.get("/patterns/{survey_id}")
def get_patterns(survey_id: int):
    """Detect patterns and pain points across insights."""
    conn = get_db()
    insights = conn.execute("""
        SELECT i.*, t.name as theme_name 
        FROM insights i LEFT JOIN themes t ON i.theme_id = t.id 
        WHERE i.survey_id = ? ORDER BY i.frequency DESC
    """, (survey_id,)).fetchall()
    conn.close()

    patterns = {
        "recurring_issues": [dict(i) for i in insights if i["frequency"] > 30],
        "high_risk": [dict(i) for i in insights if i["impact_score"] > 0.7 and i["sentiment"] == "negative"],
        "emerging": [dict(i) for i in insights if i["is_emerging"]],
        "contradictions": [dict(i) for i in insights if i["is_contradiction"]],
        "opportunities": [dict(i) for i in insights if i["insight_type"] in ("suggestion", "positive")]
    }
    return patterns


def _sentiment_color(score: float) -> str:
    """Map sentiment score to color."""
    if score < -0.5:
        return "#ef4444"  # red
    elif score < -0.2:
        return "#f97316"  # orange
    elif score < 0.2:
        return "#eab308"  # yellow
    elif score < 0.5:
        return "#84cc16"  # lime
    else:
        return "#22c55e"  # green


# ═══════════════════════════════════════════════════
# ARCHITECTURE: Incremental Intelligence Endpoints
# ═══════════════════════════════════════════════════
@router.post("/{survey_id}/incremental-update")
def trigger_incremental_update(survey_id: int, data: dict):
    """Trigger an incremental insight update from a new response (delta, not full)."""
    response_text = data.get("response_text", "")
    if not response_text:
        raise HTTPException(status_code=400, detail="response_text is required")
    return InsightService.incremental_update(survey_id, response_text)


@router.get("/{survey_id}/contradictions")
def get_contradictions(survey_id: int):
    """Detect contradictions within survey insights."""
    return InsightService.detect_contradictions(survey_id)


@router.get("/{survey_id}/emerging")
def get_emerging_themes(survey_id: int):
    """Get newly emerging themes."""
    return InsightService.get_emerging_themes(survey_id)


@router.get("/{survey_id}/insight-summary")
def get_detailed_summary(survey_id: int):
    """Get detailed insight summary with breakdowns."""
    return InsightService.get_insight_summary(survey_id)


# ── Story Narrative Generation ──
@router.get("/{survey_id}/story")
def get_insight_story(survey_id: int):
    """Generate an AI-powered narrative story from survey insights."""
    import traceback
    try:
        return _generate_story(survey_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def _generate_story(survey_id: int):
    conn = get_db()

    # Gather all data needed for the story
    survey = conn.execute("SELECT * FROM surveys WHERE id = ?", (survey_id,)).fetchone()
    insights = conn.execute(
        "SELECT * FROM insights WHERE survey_id = ? ORDER BY impact_score DESC", (survey_id,)
    ).fetchall()
    themes = conn.execute(
        "SELECT * FROM themes WHERE survey_id = ? ORDER BY frequency DESC", (survey_id,)
    ).fetchall()
    total_responses = conn.execute(
        "SELECT COUNT(*) as c FROM responses r JOIN interview_sessions s ON r.session_id = s.session_id WHERE s.survey_id = ?",
        (survey_id,),
    ).fetchone()
    sentiment_dist = conn.execute(
        "SELECT sentiment, COUNT(*) as count FROM insights WHERE survey_id = ? GROUP BY sentiment",
        (survey_id,),
    ).fetchall()
    recommendations = conn.execute(
        "SELECT * FROM recommendations WHERE survey_id = ? ORDER BY priority_score DESC", (survey_id,)
    ).fetchall()

    conn.close()

    survey_dict = dict(survey) if survey else {}
    insights_list = [dict(i) for i in insights]
    themes_list = [dict(t) for t in themes]
    sent_dist = {dict(s)["sentiment"]: dict(s)["count"] for s in sentiment_dist}
    total_resp = dict(total_responses)["c"] if total_responses else 0
    recs_list = [dict(r) for r in recommendations]

    # If no data at all, return a minimal empty story
    if not survey and len(insights_list) == 0 and len(themes_list) == 0 and total_resp == 0:
        return {
            "headline": "No Data Yet",
            "executive_summary": "This survey hasn't collected any responses yet. Start sharing it to gather feedback.",
            "sentiment_narrative": "No sentiment data available.",
            "theme_narrative": "No themes discovered yet.",
            "key_findings": [],
            "highlight_quote": "Create surveys and collect responses to generate insights.",
            "recommendations_narrative": "Share your survey to start collecting responses.",
            "outlook": "Your first insights will appear once responses start coming in.",
            "stats": {"total_responses": 0, "total_themes": 0, "total_insights": 0, "total_recommendations": 0, "sentiment_distribution": {}},
            "themes": [],
            "survey_title": "Survey #" + str(survey_id)
        }

    # Build a context block for Gemini
    context_block = f"""Survey: {survey_dict.get('title', 'Untitled Survey')}
Total Responses: {total_resp}
Themes ({len(themes_list)}): {', '.join(t['name'] for t in themes_list[:10])}
Sentiment Distribution: {json.dumps(sent_dist)}
Top Insights ({len(insights_list)}):
"""
    for ins in insights_list[:8]:
        context_block += f"- [{ins.get('sentiment','neutral')}] {ins.get('title', ins.get('description','')[:80])} (impact: {ins.get('impact_score',0)}, confidence: {ins.get('confidence',0)})\n"

    if recs_list:
        context_block += f"\nRecommendations ({len(recs_list)}):\n"
        for rec in recs_list[:5]:
            context_block += f"- {rec.get('title', rec.get('description','')[:80])} (priority: {rec.get('priority_score','medium')})\n"

    prompt = f"""You are an expert UX research analyst. Based on the survey data below, write an engaging narrative report.

{context_block}

Return a JSON object with exactly these keys:
- "headline": A compelling one-line headline summarizing the key finding (max 15 words)
- "executive_summary": A 2-3 sentence executive summary
- "sentiment_narrative": A paragraph (3-4 sentences) describing the overall sentiment landscape
- "theme_narrative": A paragraph (3-4 sentences) about the key themes discovered
- "key_findings": An array of 3-5 objects, each with "title" (string) and "description" (string, 1-2 sentences)
- "highlight_quote": A single impactful sentence highlighting the most important takeaway
- "recommendations_narrative": A paragraph (2-3 sentences) about what to do next
- "outlook": A brief (1-2 sentence) forward-looking statement

Write in a professional but approachable tone. Be specific with numbers when available.
Return ONLY valid JSON, no markdown fences."""

    story_data = _ask_gemini_json(prompt, max_tokens=2048)

    # Attach raw stats so the frontend can render stat cards too
    story_data["stats"] = {
        "total_responses": total_resp,
        "total_themes": len(themes_list),
        "total_insights": len(insights_list),
        "total_recommendations": len(recs_list),
        "sentiment_distribution": sent_dist,
    }
    story_data["themes"] = [
        {"name": t["name"], "frequency": t.get("frequency", 0), "sentiment_avg": t.get("sentiment_avg", 0)}
        for t in themes_list[:8]
    ]
    story_data["survey_title"] = survey_dict.get("title", "Survey #" + str(survey_id))

    # Provide fallback if Gemini couldn't generate
    if "headline" not in story_data:
        pos = sent_dist.get("positive", 0)
        neg = sent_dist.get("negative", 0)
        neu = sent_dist.get("neutral", 0)
        total_sent = pos + neg + neu or 1
        story_data.update({
            "headline": f"Survey Analysis: {len(insights_list)} Insights from {total_resp} Responses",
            "executive_summary": f"Analysis of {total_resp} responses across {len(themes_list)} themes revealed {len(insights_list)} actionable insights. "
                + f"Sentiment is {'predominantly positive' if pos > neg else 'mixed' if abs(pos - neg) < total_sent * 0.2 else 'leaning negative'}.",
            "sentiment_narrative": f"Of the analyzed responses, {round(pos/total_sent*100)}% were positive, {round(neu/total_sent*100)}% neutral, and {round(neg/total_sent*100)}% negative. "
                + "This distribution suggests " + ("strong user satisfaction." if pos > neg * 2 else "areas requiring attention."),
            "theme_narrative": f"{len(themes_list)} distinct themes emerged from the analysis. "
                + (f"The most prevalent theme is '{themes_list[0]['name']}' with {themes_list[0].get('frequency', 0)} mentions." if themes_list else ""),
            "key_findings": [
                {"title": ins.get("title", "Finding"), "description": ins.get("description", "")[:150]}
                for ins in insights_list[:4]
            ],
            "highlight_quote": insights_list[0].get("description", "No key insight available.")[:200] if insights_list else "No data available yet.",
            "recommendations_narrative": "Based on the analysis, focus on addressing recurring negative themes first, then capitalize on the strengths identified in positive feedback.",
            "outlook": "Continued data collection will refine these insights and reveal emerging trends."
        })

    return story_data
