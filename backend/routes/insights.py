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
    result = InsightService.incremental_update(survey_id, response_text)
    # Broadcast dashboard refresh event via WebSocket
    import asyncio
    try:
        from ..main import get_ws_manager
        ws = get_ws_manager()
        asyncio.get_event_loop().create_task(ws.broadcast({
            "type": "dashboard_refresh",
            "survey_id": survey_id,
            "event": "incremental_update",
            "timestamp": __import__('time').time()
        }))
    except Exception:
        pass  # WS broadcast is best-effort
    return result


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


# ═══════════════════════════════════════════════════
# COLLABORATIVE ANNOTATIONS
# Team members can annotate insights and chatbot messages
# ═══════════════════════════════════════════════════

@router.post("/{survey_id}/annotations")
def create_annotation(survey_id: int, data: dict):
    """Create a new annotation on an insight or chatbot message."""
    content = (data.get("content") or "").strip()
    target_type = data.get("target_type", "insight")  # "insight" or "chatbot_message"
    target_id = str(data.get("target_id", ""))
    user_name = (data.get("user_name") or "Anonymous").strip()
    color = data.get("color", "#fbbf24")

    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    if len(content) > 1000:
        raise HTTPException(status_code=400, detail="content too long (max 1000 chars)")
    if target_type not in ("insight", "chatbot_message", "theme", "general"):
        raise HTTPException(status_code=400, detail="invalid target_type")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO annotations (survey_id, user_name, target_type, target_id, content, color) VALUES (?, ?, ?, ?, ?, ?)",
        (survey_id, user_name, target_type, target_id, content, color)
    )
    annotation_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {"id": annotation_id, "message": "Annotation created"}


@router.get("/{survey_id}/annotations")
def get_annotations(survey_id: int, target_type: Optional[str] = Query(None), target_id: Optional[str] = Query(None)):
    """Get annotations for a survey, optionally filtered by target."""
    conn = get_db()
    query = "SELECT * FROM annotations WHERE survey_id = ?"
    params = [survey_id]
    if target_type:
        query += " AND target_type = ?"
        params.append(target_type)
    if target_id:
        query += " AND target_id = ?"
        params.append(target_id)
    query += " ORDER BY created_at DESC"
    annotations = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(a) for a in annotations]


@router.delete("/{survey_id}/annotations/{annotation_id}")
def delete_annotation(survey_id: int, annotation_id: int):
    """Delete an annotation."""
    conn = get_db()
    conn.execute("DELETE FROM annotations WHERE id = ? AND survey_id = ?", (annotation_id, survey_id))
    conn.commit()
    conn.close()
    return {"message": "Annotation deleted"}


# ═══════════════════════════════════════════════════
# SURVEY ANALYSIS CHATBOT
# AI-powered Q&A about survey data, insights, and responses
# ═══════════════════════════════════════════════════

@router.post("/{survey_id}/chat")
def chatbot_query(survey_id: int, data: dict):
    """Ask the AI chatbot a question about survey data and get an analytical answer."""
    import uuid
    import traceback

    user_message = (data.get("message") or "").strip()
    conversation_id = data.get("conversation_id") or uuid.uuid4().hex[:16]
    persona = data.get("persona", "analyst")

    if not user_message:
        raise HTTPException(status_code=400, detail="message is required")
    if len(user_message) > 2000:
        raise HTTPException(status_code=400, detail="message too long (max 2000 chars)")
    if persona not in ("analyst", "executive", "researcher", "casual"):
        persona = "analyst"

    try:
        # 1. Gather comprehensive survey context
        context = _build_chatbot_context(survey_id)

        if not context["has_data"]:
            return {
                "answer": "This survey doesn't have any data yet. Start collecting responses to enable analysis chat.",
                "conversation_id": conversation_id,
                "sources": []
            }

        # 2. Load recent conversation history for continuity
        conv_history = _get_conversation_history(survey_id, conversation_id, limit=6)

        # 3. Build the prompt with context + history + question + persona
        prompt = _build_chatbot_prompt(context, conv_history, user_message, persona=persona)

        # 4. Ask Gemini
        raw_answer = _ask_gemini_json(prompt, max_tokens=1500)

        if isinstance(raw_answer, dict):
            answer = raw_answer.get("answer", "I couldn't generate a response. Please try rephrasing your question.")
            sources = raw_answer.get("sources", [])
            follow_ups = raw_answer.get("follow_up_questions", [])
        else:
            answer = str(raw_answer) if raw_answer else "I couldn't generate a response. Please try again."
            sources = []
            follow_ups = []

        # 5. Store conversation in database
        _save_chatbot_message(survey_id, conversation_id, "user", user_message)
        _save_chatbot_message(survey_id, conversation_id, "assistant", answer)

        return {
            "answer": answer,
            "conversation_id": conversation_id,
            "sources": sources[:5],
            "follow_up_questions": follow_ups[:3]
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chatbot error: {str(e)}")


@router.get("/{survey_id}/chat/history")
def get_chatbot_history(survey_id: int, conversation_id: str = Query(...)):
    """Get conversation history for a chatbot session."""
    conn = get_db()
    messages = conn.execute(
        "SELECT role, message, created_at FROM chatbot_conversations WHERE survey_id = ? AND conversation_id = ? ORDER BY created_at ASC",
        (survey_id, conversation_id)
    ).fetchall()
    conn.close()
    return [dict(m) for m in messages]


@router.get("/{survey_id}/chat/conversations")
def list_chatbot_conversations(survey_id: int):
    """List all chatbot conversations for a survey."""
    conn = get_db()
    conversations = conn.execute("""
        SELECT conversation_id, 
               MIN(created_at) as started_at, 
               MAX(created_at) as last_message_at,
               COUNT(*) as message_count,
               MIN(CASE WHEN role = 'user' THEN message END) as first_question
        FROM chatbot_conversations 
        WHERE survey_id = ?
        GROUP BY conversation_id
        ORDER BY MAX(created_at) DESC
    """, (survey_id,)).fetchall()
    conn.close()
    return [dict(c) for c in conversations]


def _build_chatbot_context(survey_id: int) -> dict:
    """Build comprehensive survey context for the chatbot."""
    conn = get_db()

    survey = conn.execute("SELECT * FROM surveys WHERE id = ?", (survey_id,)).fetchone()
    if not survey:
        conn.close()
        return {"has_data": False}

    survey_dict = dict(survey)

    # Questions
    questions = conn.execute(
        "SELECT question_text, question_type, order_index FROM questions WHERE survey_id = ? ORDER BY order_index",
        (survey_id,)
    ).fetchall()

    # Response count and samples
    total_responses = conn.execute(
        "SELECT COUNT(*) as c FROM responses r JOIN interview_sessions s ON r.session_id = s.session_id WHERE s.survey_id = ?",
        (survey_id,)
    ).fetchone()

    # Sample responses (most recent, limit to keep token costs down)
    sample_responses = conn.execute("""
        SELECT r.response_text, r.sentiment_score, r.emotion, r.intent, r.quality_score,
               q.question_text
        FROM responses r
        JOIN interview_sessions s ON r.session_id = s.session_id
        LEFT JOIN questions q ON r.question_id = q.id
        WHERE s.survey_id = ? AND r.response_text IS NOT NULL AND r.response_text != ''
        ORDER BY r.created_at DESC LIMIT 50
    """, (survey_id,)).fetchall()

    # Themes
    themes = conn.execute(
        "SELECT name, frequency, sentiment_avg, priority, is_emerging FROM themes WHERE survey_id = ? ORDER BY frequency DESC",
        (survey_id,)
    ).fetchall()

    # Insights
    insights = conn.execute(
        "SELECT title, description, insight_type, sentiment, confidence, impact_score, feature_area FROM insights WHERE survey_id = ? ORDER BY impact_score DESC",
        (survey_id,)
    ).fetchall()

    # Sentiment distribution
    sentiment_dist = conn.execute(
        "SELECT sentiment, COUNT(*) as count FROM insights WHERE survey_id = ? GROUP BY sentiment",
        (survey_id,)
    ).fetchall()

    # Recommendations
    recommendations = conn.execute(
        "SELECT title, description, action_type, impact_score, effort_score, priority_score, status FROM recommendations WHERE survey_id = ? ORDER BY priority_score DESC",
        (survey_id,)
    ).fetchall()

    # Session stats
    sessions = conn.execute(
        "SELECT COUNT(*) as total, AVG(engagement_score) as avg_engagement, AVG(completion_percentage) as avg_completion FROM interview_sessions WHERE survey_id = ?",
        (survey_id,)
    ).fetchone()

    conn.close()

    resp_count = dict(total_responses)["c"] if total_responses else 0
    session_stats = dict(sessions) if sessions else {}

    return {
        "has_data": resp_count > 0 or len([dict(i) for i in insights]) > 0,
        "survey": survey_dict,
        "questions": [dict(q) for q in questions],
        "total_responses": resp_count,
        "sample_responses": [dict(r) for r in sample_responses],
        "themes": [dict(t) for t in themes],
        "insights": [dict(i) for i in insights],
        "sentiment_distribution": {dict(s)["sentiment"]: dict(s)["count"] for s in sentiment_dist},
        "recommendations": [dict(r) for r in recommendations],
        "session_stats": session_stats
    }


def _get_conversation_history(survey_id: int, conversation_id: str, limit: int = 6) -> list:
    """Retrieve recent conversation history for context."""
    conn = get_db()
    messages = conn.execute(
        "SELECT role, message FROM chatbot_conversations WHERE survey_id = ? AND conversation_id = ? ORDER BY created_at DESC LIMIT ?",
        (survey_id, conversation_id, limit)
    ).fetchall()
    conn.close()
    return [dict(m) for m in reversed(messages)]


def _save_chatbot_message(survey_id: int, conversation_id: str, role: str, message: str):
    """Save a chatbot message to the database."""
    conn = get_db()
    conn.execute(
        "INSERT INTO chatbot_conversations (survey_id, conversation_id, role, message) VALUES (?, ?, ?, ?)",
        (survey_id, conversation_id, role, message)
    )
    conn.commit()
    conn.close()


def _detect_comparison_intent(user_message: str) -> dict:
    """Detect if the user is asking a comparison question and extract comparison targets."""
    import re
    comparison_patterns = [
        r'compare\s+(.+?)\s+(?:vs\.?|versus|and|with|to|against)\s+(.+)',
        r'(.+?)\s+vs\.?\s+(.+)',
        r'difference(?:s)?\s+between\s+(.+?)\s+and\s+(.+)',
        r'how\s+does?\s+(.+?)\s+(?:compare|differ|stack up)\s+(?:to|with|against)\s+(.+)',
        r'(.+?)\s+compared\s+to\s+(.+)',
        r'contrast\s+(.+?)\s+(?:with|and)\s+(.+)',
    ]
    for pattern in comparison_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            return {"is_comparison": True, "target_a": match.group(1).strip(), "target_b": match.group(2).strip()}
    # Keyword heuristic
    comparison_keywords = ['compare', 'comparison', 'versus', ' vs ', 'differ', 'contrast', 'better', 'worse']
    if any(kw in user_message.lower() for kw in comparison_keywords):
        return {"is_comparison": True, "target_a": None, "target_b": None}
    return {"is_comparison": False}


def _build_chatbot_prompt(context: dict, conv_history: list, user_message: str, persona: str = "analyst") -> str:
    """Build the AI prompt with full survey context and conversation history."""
    survey = context["survey"]
    questions = context["questions"]
    responses = context["sample_responses"]
    themes = context["themes"]
    insights = context["insights"]
    sent_dist = context["sentiment_distribution"]
    recommendations = context["recommendations"]
    session_stats = context["session_stats"]

    # Persona system instructions
    persona_instructions = {
        "analyst": "You are an expert survey data analyst chatbot. You help users understand their survey results by analyzing the data provided. Be thorough, specific, and data-driven.",
        "executive": "You are a concise executive briefing assistant. Summarize survey findings in a strategic, high-level manner suitable for C-suite stakeholders. Focus on business impact, ROI, and actionable decisions. Use bullet points and keep answers brief.",
        "researcher": "You are a UX research specialist. Analyze survey data through the lens of user experience methodology. Highlight user pain points, behavioral patterns, and design implications. Reference specific respondent quotes when relevant.",
        "casual": "You are a friendly, approachable survey insights helper. Explain findings in simple, everyday language. Avoid jargon and make data accessible to non-technical stakeholders. Use analogies when helpful.",
    }
    persona_prompt = persona_instructions.get(persona, persona_instructions["analyst"])

    # Build context block
    ctx = f"""=== SURVEY DATA CONTEXT ===
Survey: "{survey.get('title', 'Untitled')}"
Description: {survey.get('description', 'N/A')}
Status: {survey.get('status', 'unknown')} | Channel: {survey.get('channel_type', 'web')}
Total Responses: {context['total_responses']}
Sessions: {session_stats.get('total', 0)} | Avg Engagement: {round(session_stats.get('avg_engagement', 0) or 0, 2)} | Avg Completion: {round(session_stats.get('avg_completion', 0) or 0, 1)}%

Survey Questions ({len(questions)}):
"""
    for q in questions[:15]:
        ctx += f"  Q{q['order_index']+1}: {q['question_text']}\n"

    ctx += f"\nThemes ({len(themes)}):\n"
    for t in themes[:10]:
        ctx += f"  - {t['name']} (frequency: {t['frequency']}, sentiment: {round(t['sentiment_avg'], 2)}, priority: {t['priority']}{', EMERGING' if t['is_emerging'] else ''})\n"

    ctx += f"\nSentiment Distribution: {json.dumps(sent_dist)}\n"

    ctx += f"\nKey Insights ({len(insights)}):\n"
    for i in insights[:12]:
        ctx += f"  - [{i.get('sentiment','neutral')}] {i.get('title', '')}: {(i.get('description','') or '')[:120]} (impact: {i.get('impact_score',0)}, confidence: {i.get('confidence',0)}, area: {i.get('feature_area', 'general')})\n"

    if recommendations:
        ctx += f"\nRecommendations ({len(recommendations)}):\n"
        for r in recommendations[:8]:
            ctx += f"  - {r.get('title', r.get('description','')[:80])} (impact: {r.get('impact_score',0)}, effort: {r.get('effort_score',0)}, priority: {r.get('priority_score',0)}, status: {r.get('status','pending')})\n"

    ctx += f"\nSample Respondent Answers ({len(responses)} most recent):\n"
    for r in responses[:25]:
        q_text = r.get('question_text', '?')[:60]
        r_text = (r.get('response_text', '') or '')[:150]
        sentiment = f"sentiment:{r.get('sentiment_score','?')}" if r.get('sentiment_score') else ""
        emotion = f"emotion:{r.get('emotion','?')}" if r.get('emotion') else ""
        ctx += f"  Q: {q_text}\n  A: {r_text} {sentiment} {emotion}\n"

    # Build conversation history block
    history_block = ""
    if conv_history:
        history_block = "\n=== CONVERSATION HISTORY ===\n"
        for msg in conv_history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            history_block += f"{role_label}: {msg['message']}\n"

    # Detect comparison intent and add comparison-specific instructions
    comparison = _detect_comparison_intent(user_message)
    comparison_instructions = ""
    if comparison["is_comparison"]:
        comparison_instructions = """

=== COMPARISON MODE ===
The user is asking a comparison question. Structure your answer as a clear comparison:
1. **Overview**: Briefly describe both items being compared
2. **Side-by-Side Analysis**: Compare them across key dimensions (sentiment, frequency, impact, themes, user feedback)
3. **Key Differences**: Highlight the most important distinctions with specific data points
4. **Key Similarities**: Note any common ground
5. **Verdict/Recommendation**: Provide a data-backed recommendation or conclusion

Use a comparison table format (using markdown) when it helps clarity. Always cite specific numbers from the data."""

    prompt = f"""{persona_prompt}

{ctx}
{history_block}

=== USER'S QUESTION ===
{user_message}
{comparison_instructions}

=== INSTRUCTIONS ===
Answer the user's question based ONLY on the survey data provided above. Be specific with numbers, percentages, and references to actual themes/insights/responses.

If the user asks something not answerable from the data, say so honestly.

Provide actionable, data-driven answers. Reference specific themes, insights, sentiment scores, and respondent quotes when relevant.

Return a JSON object with exactly these keys:
- "answer": Your detailed response (use markdown formatting for readability: bold, lists, etc.)
- "sources": An array of strings citing which data points you used (e.g., "Theme: Performance - 45 mentions", "Insight: Users struggle with onboarding")
- "follow_up_questions": An array of 2-3 suggested follow-up questions the user might want to ask
{'"is_comparison": true,' if comparison["is_comparison"] else ''}

Return ONLY valid JSON, no markdown fences."""

    return prompt
