"""
Survey Publication & Respondent Management Routes
═══════════════════════════════════════════════════════
Handles:
  - Publishing surveys (draft → active) with share links
  - Generating 3 interview links (web-form, chat, audio)
  - Respondent registration via Google email
  - Respondent → survey tracking
  - Full transcript storage & retrieval
  - Survey-level analytics for group analysis
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from ..database import get_db, get_db_connection
from ..models import PublishSurveyRequest, RespondentJoinRequest
from ..services.ai_service import AIService
from ..auth import get_current_user
from datetime import datetime
import uuid
import json
import csv
import io

router = APIRouter(prefix="/api/publish", tags=["survey-publish"])


# ═══════════════════════════════════════════════════
# PUBLISH A SURVEY — Creates share links
# ═══════════════════════════════════════════════════
@router.post("/")
def publish_survey(req: PublishSurveyRequest, current_user: dict = Depends(get_current_user)):
    """Publish a survey and generate shareable links for all 3 channels."""
    conn = get_db()

    # Verify survey exists
    survey = conn.execute("SELECT * FROM surveys WHERE id = ?", (req.survey_id,)).fetchone()
    if not survey:
        conn.close()
        raise HTTPException(status_code=404, detail="Survey not found")

    survey_dict = dict(survey)
    title = req.title or survey_dict.get("title", "Untitled Survey")
    description = req.description or survey_dict.get("description", "")

    # Generate unique share code
    share_code = uuid.uuid4().hex[:12]

    # Check if already published
    existing = conn.execute(
        "SELECT * FROM survey_publications WHERE survey_id = ? AND status != 'closed'",
        (req.survey_id,)
    ).fetchone()
    if existing:
        existing_dict = dict(existing)
        conn.close()
        return {
            "id": existing_dict["id"],
            "share_code": existing_dict["share_code"],
            "status": existing_dict["status"],
            "message": "Survey already published",
            "links": _build_links(existing_dict["share_code"]),
        }

    # Get user_id from auth
    user_id = current_user["sub"]

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO survey_publications
            (survey_id, user_id, share_code, title, description, status,
             web_form_enabled, chat_enabled, audio_enabled,
             max_responses, require_email, consent_form_text, published_at)
        VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?)
    """, (
        req.survey_id, user_id, share_code, title, description,
        1 if req.web_form_enabled else 0,
        1 if req.chat_enabled else 0,
        1 if req.audio_enabled else 0,
        req.max_responses,
        1 if req.require_email else 0,
        req.consent_form_text or '',
        datetime.now().isoformat()
    ))

    # Update survey status to active
    conn.execute("UPDATE surveys SET status = 'active', updated_at = ? WHERE id = ?",
                 (datetime.now().isoformat(), req.survey_id))
    conn.commit()
    pub_id = cursor.lastrowid
    conn.close()

    return {
        "id": pub_id,
        "share_code": share_code,
        "status": "active",
        "message": "Survey published successfully",
        "links": _build_links(share_code),
    }


@router.put("/{share_code}/status")
def update_publication_status(share_code: str, data: dict, current_user: dict = Depends(get_current_user)):
    """Update publication status (draft, active, paused, closed)."""
    conn = get_db()
    pub = conn.execute("SELECT * FROM survey_publications WHERE share_code = ?", (share_code,)).fetchone()
    if not pub:
        conn.close()
        raise HTTPException(status_code=404, detail="Publication not found")

    new_status = data.get("status", "active")
    if new_status not in ("draft", "active", "paused", "closed"):
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid status. Must be: draft, active, paused, or closed")
    conn.execute("UPDATE survey_publications SET status = ?, updated_at = ? WHERE share_code = ?",
                 (new_status, datetime.now().isoformat(), share_code))
    if new_status == "closed":
        conn.execute("UPDATE survey_publications SET closed_at = ? WHERE share_code = ?",
                     (datetime.now().isoformat(), share_code))
    conn.commit()
    conn.close()
    return {"message": f"Publication status updated to {new_status}"}


# ═══════════════════════════════════════════════════
# LIST USER'S SURVEYS (My Surveys dashboard)
# ═══════════════════════════════════════════════════
@router.get("/my-surveys")
def list_my_surveys(current_user: dict = Depends(get_current_user)):
    """List all surveys with their publication status, respondent counts, and links."""
    conn = get_db()
    try:
        surveys = conn.execute("""
            SELECT s.*, rg.title as goal_title, rg.research_type
            FROM surveys s
            LEFT JOIN research_goals rg ON s.research_goal_id = rg.id
            ORDER BY s.created_at DESC
        """).fetchall()

        result = []
        for s in surveys:
            sd = dict(s)
            survey_id = sd["id"]

            # Get publication info
            pub = conn.execute(
                "SELECT * FROM survey_publications WHERE survey_id = ? ORDER BY created_at DESC LIMIT 1",
                (survey_id,)
            ).fetchone()

            # Count respondents
            resp_count = conn.execute(
                "SELECT COUNT(*) as c FROM survey_respondents WHERE survey_id = ?",
                (survey_id,)
            ).fetchone()["c"]

            # Count completed
            completed_count = conn.execute(
                "SELECT COUNT(*) as c FROM survey_respondents WHERE survey_id = ? AND status = 'completed'",
                (survey_id,)
            ).fetchone()["c"]

            # Count total sessions
            session_count = conn.execute(
                "SELECT COUNT(*) as c FROM interview_sessions WHERE survey_id = ?",
                (survey_id,)
            ).fetchone()["c"]

            # Count questions
            question_count = conn.execute(
                "SELECT COUNT(*) as c FROM questions WHERE survey_id = ?",
                (survey_id,)
            ).fetchone()["c"]

            pub_info = None
            links = None
            if pub:
                pub_dict = dict(pub)
                pub_info = {
                    "id": pub_dict["id"],
                    "share_code": pub_dict["share_code"],
                    "status": pub_dict["status"],
                    "published_at": pub_dict["published_at"],
                    "web_form_enabled": bool(pub_dict["web_form_enabled"]),
                    "chat_enabled": bool(pub_dict["chat_enabled"]),
                    "audio_enabled": bool(pub_dict["audio_enabled"]),
                }
                links = _build_links(pub_dict["share_code"])

            result.append({
                **sd,
                "publication": pub_info,
                "links": links,
                "respondent_count": resp_count,
                "completed_count": completed_count,
                "session_count": session_count,
                "question_count": question_count,
            })

        return result
    finally:
        conn.close()


# ═══════════════════════════════════════════════════
# GET SURVEY BY SHARE CODE (for respondent-facing page)
# ═══════════════════════════════════════════════════
@router.get("/s/{share_code}")
def get_survey_by_code(share_code: str):
    """Get published survey details by share code (public, no auth required)."""
    conn = get_db()

    pub = conn.execute("SELECT * FROM survey_publications WHERE share_code = ?", (share_code,)).fetchone()
    if not pub:
        conn.close()
        raise HTTPException(status_code=404, detail="Survey not found")

    pub_dict = dict(pub)
    if pub_dict["status"] == "closed":
        conn.close()
        raise HTTPException(status_code=410, detail="This survey has been closed")

    survey = conn.execute("SELECT * FROM surveys WHERE id = ?", (pub_dict["survey_id"],)).fetchone()
    questions = conn.execute(
        "SELECT id, question_text, question_type, options, order_index, is_required, tone, depth_level "
        "FROM questions WHERE survey_id = ? ORDER BY order_index",
        (pub_dict["survey_id"],)
    ).fetchall()

    # Respondent count
    resp_count = conn.execute(
        "SELECT COUNT(*) as c FROM survey_respondents WHERE survey_id = ?",
        (pub_dict["survey_id"],)
    ).fetchone()["c"]

    conn.close()

    return {
        "share_code": share_code,
        "title": pub_dict["title"],
        "description": pub_dict["description"],
        "status": pub_dict["status"],
        "survey_id": pub_dict["survey_id"],
        "web_form_enabled": bool(pub_dict["web_form_enabled"]),
        "chat_enabled": bool(pub_dict["chat_enabled"]),
        "audio_enabled": bool(pub_dict["audio_enabled"]),
        "require_email": bool(pub_dict["require_email"]),
        "consent_form_text": pub_dict.get("consent_form_text", "") or "",
        "estimated_duration": dict(survey)["estimated_duration"] if survey else 5,
        "question_count": len(questions),
        "respondent_count": resp_count,
        "questions": [dict(q) for q in questions],
    }


# ═══════════════════════════════════════════════════
# RESPONDENT JOIN — Register via email & start interview
# ═══════════════════════════════════════════════════
@router.post("/join")
def respondent_join(req: RespondentJoinRequest):
    """Respondent joins a survey via share code + email. Creates session."""
    conn = get_db()
    try:
        # Validate publication
        pub = conn.execute("SELECT * FROM survey_publications WHERE share_code = ?", (req.share_code,)).fetchone()
        if not pub:
            raise HTTPException(status_code=404, detail="Survey not found")

        pub_dict = dict(pub)
        if pub_dict["status"] != "active":
            raise HTTPException(status_code=400, detail="This survey is not currently accepting responses")

        # Check max responses
        if pub_dict["max_responses"] > 0:
            current_count = conn.execute(
                "SELECT COUNT(*) as c FROM survey_respondents WHERE survey_id = ?",
                (pub_dict["survey_id"],)
            ).fetchone()["c"]
            if current_count >= pub_dict["max_responses"]:
                raise HTTPException(status_code=400, detail="This survey has reached its maximum number of responses")

        # Create respondent record
        cursor = conn.cursor()
        cursor.execute("INSERT INTO respondents (email, name) VALUES (?, ?)", (req.email, req.name or ""))
        conn.commit()
        respondent_id = cursor.lastrowid

        # Check if respondent already took this survey
        existing = conn.execute(
            "SELECT sr.*, i.session_id as active_session FROM survey_respondents sr "
            "LEFT JOIN interview_sessions i ON sr.session_id = i.session_id "
            "WHERE sr.survey_id = ? AND sr.respondent_id = ? AND sr.status != 'completed'",
            (pub_dict["survey_id"], respondent_id)
        ).fetchone()
        if existing:
            existing_dict = dict(existing)
            if existing_dict.get("active_session"):
                return {
                    "message": "Resumed existing session",
                    "session_id": existing_dict["active_session"],
                    "respondent_id": respondent_id,
                    "survey_id": pub_dict["survey_id"],
                    "status": "resumed",
                }

        # Create interview session
        session_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO interview_sessions (survey_id, respondent_id, session_id, channel)
            VALUES (?, ?, ?, ?)
        """, (pub_dict["survey_id"], str(respondent_id), session_id, req.channel))

        # Insert AI greeting into conversation_history for transcript completeness
        survey = conn.execute("SELECT title, description FROM surveys WHERE id = ?", (pub_dict["survey_id"],)).fetchone()
        survey_title = dict(survey).get("title", "") if survey else ""
        if survey_title:
            greeting = f"Hi there! I'm your AI research interviewer. Today I'd love to chat with you about **{survey_title}**. There are no right or wrong answers — I'm just here to understand your genuine experience and thoughts. Ready to start?"
        else:
            greeting = "Hi there! I'm your AI research interviewer. I'll be asking you a few questions about your experience. There are no right or wrong answers — just share honestly."
        conn.execute("""
            INSERT INTO conversation_history (session_id, role, message, message_type)
            VALUES (?, 'ai', ?, 'text')
        """, (session_id, greeting))

        # Link respondent to survey
        conn.execute("""
            INSERT INTO survey_respondents (survey_id, publication_id, respondent_id, session_id, channel, status)
            VALUES (?, ?, ?, ?, ?, 'started')
        """, (pub_dict["survey_id"], pub_dict["id"], respondent_id, session_id, req.channel))

        # Update survey total_responses count
        conn.execute("UPDATE surveys SET total_responses = total_responses + 1, updated_at = ? WHERE id = ?",
                     (datetime.now().isoformat(), pub_dict["survey_id"]))

        conn.commit()

        return {
            "message": "Successfully joined survey",
            "session_id": session_id,
            "respondent_id": respondent_id,
            "survey_id": pub_dict["survey_id"],
            "channel": req.channel,
            "status": "started",
        }
    finally:
        conn.close()

# ═══════════════════════════════════════════════════
# SURVEY-LEVEL ANALYTICS — Group analysis
# ═══════════════════════════════════════════════════
@router.get("/analytics/{survey_id}")
def get_survey_analytics(survey_id: int, current_user: dict = Depends(get_current_user)):
    """Get comprehensive survey analytics for group-level analysis."""
    conn = get_db()
    try:
        # Basic stats
        total_respondents = conn.execute(
            "SELECT COUNT(DISTINCT respondent_id) as c FROM survey_respondents WHERE survey_id = ?",
            (survey_id,)
        ).fetchone()["c"]

        completed = conn.execute(
            "SELECT COUNT(*) as c FROM survey_respondents WHERE survey_id = ? AND status = 'completed'",
            (survey_id,)
        ).fetchone()["c"]

        in_progress = conn.execute(
            "SELECT COUNT(*) as c FROM survey_respondents WHERE survey_id = ? AND status = 'started'",
            (survey_id,)
        ).fetchone()["c"]

        # Channel breakdown
        channels = conn.execute(
            "SELECT channel, COUNT(*) as count FROM survey_respondents WHERE survey_id = ? GROUP BY channel",
            (survey_id,)
        ).fetchall()

        # Average sentiment from responses
        avg_sentiment = conn.execute(
            "SELECT AVG(r.sentiment_score) as avg_sent FROM responses r "
            "JOIN interview_sessions s ON r.session_id = s.session_id "
            "WHERE s.survey_id = ? AND r.sentiment_score IS NOT NULL",
            (survey_id,)
        ).fetchone()["avg_sent"]

        # Sentiment distribution
        sentiment_dist = conn.execute("""
            SELECT
                SUM(CASE WHEN r.sentiment_score > 0.2 THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN r.sentiment_score BETWEEN -0.2 AND 0.2 THEN 1 ELSE 0 END) as neutral,
                SUM(CASE WHEN r.sentiment_score < -0.2 THEN 1 ELSE 0 END) as negative
            FROM responses r
            JOIN interview_sessions s ON r.session_id = s.session_id
            WHERE s.survey_id = ?
        """, (survey_id,)).fetchone()

        # Emotion breakdown
        emotions = conn.execute("""
            SELECT r.emotion, COUNT(*) as count
            FROM responses r
            JOIN interview_sessions s ON r.session_id = s.session_id
            WHERE s.survey_id = ? AND r.emotion IS NOT NULL AND r.emotion != ''
            GROUP BY r.emotion ORDER BY count DESC LIMIT 8
        """, (survey_id,)).fetchall()

        # Themes discovered
        themes = conn.execute(
            "SELECT name, description, frequency, sentiment_avg, priority, business_risk, is_emerging "
            "FROM themes WHERE survey_id = ? ORDER BY frequency DESC LIMIT 10",
            (survey_id,)
        ).fetchall()

        # Average quality score
        avg_quality = conn.execute(
            "SELECT AVG(r.quality_score) as avg_q FROM responses r "
            "JOIN interview_sessions s ON r.session_id = s.session_id "
            "WHERE s.survey_id = ? AND r.quality_score IS NOT NULL",
            (survey_id,)
        ).fetchone()["avg_q"]

        # Per-question response count + avg sentiment
        question_stats = conn.execute("""
            SELECT q.question_text, q.order_index,
                COUNT(r.id) as response_count,
                AVG(r.sentiment_score) as avg_sentiment,
                AVG(r.quality_score) as avg_quality
            FROM questions q
            LEFT JOIN responses r ON q.id = r.question_id
            WHERE q.survey_id = ?
            GROUP BY q.id
            ORDER BY q.order_index
        """, (survey_id,)).fetchall()

        # Transcripts available
        transcript_count = conn.execute(
            "SELECT COUNT(*) as c FROM full_transcripts WHERE survey_id = ?",
            (survey_id,)
        ).fetchone()["c"]

        # Session-level stats (avg completion, avg engagement)
        session_stats = conn.execute("""
            SELECT AVG(completion_percentage) as avg_completion,
                   AVG(engagement_score) as avg_engagement,
                   COUNT(*) as total_sessions
            FROM interview_sessions WHERE survey_id = ?
        """, (survey_id,)).fetchone()

        # Respondent list with session info
        respondents = conn.execute("""
            SELECT resp.email, resp.name, sr.channel, sr.status, sr.started_at, sr.completed_at, sr.session_id,
                   i.completion_percentage, i.engagement_score
            FROM survey_respondents sr
            JOIN respondents resp ON sr.respondent_id = resp.id
            LEFT JOIN interview_sessions i ON sr.session_id = i.session_id
            WHERE sr.survey_id = ?
            ORDER BY sr.started_at DESC
        """, (survey_id,)).fetchall()

        return {
            "survey_id": survey_id,
            "total_respondents": total_respondents,
            "completed": completed,
            "in_progress": in_progress,
            "completion_rate": round(completed / max(total_respondents, 1) * 100, 1),
            "channel_breakdown": [dict(c) for c in channels],
            "avg_sentiment": round(avg_sentiment, 3) if avg_sentiment else 0,
            "avg_quality": round(avg_quality, 2) if avg_quality else 0,
            "sentiment_distribution": {
                "positive": dict(sentiment_dist)["positive"] or 0,
                "neutral": dict(sentiment_dist)["neutral"] or 0,
                "negative": dict(sentiment_dist)["negative"] or 0,
            } if sentiment_dist else {"positive": 0, "neutral": 0, "negative": 0},
            "emotion_breakdown": [dict(e) for e in emotions],
            "themes": [dict(t) for t in themes],
            "question_stats": [dict(q) for q in question_stats],
            "transcript_count": transcript_count,
            "session_stats": {
                "avg_completion": round(dict(session_stats)["avg_completion"] or 0, 1),
                "avg_engagement": round(dict(session_stats)["avg_engagement"] or 0, 2),
                "total_sessions": dict(session_stats)["total_sessions"] or 0,
            },
            "respondents": [dict(r) for r in respondents],
        }
    finally:
        conn.close()


# ═══════════════════════════════════════════════════
# AI ANALYSIS — Deep group-level analysis via Gemini
# ═══════════════════════════════════════════════════
@router.get("/analysis/{survey_id}")
def get_survey_analysis(survey_id: int, current_user: dict = Depends(get_current_user)):
    """Generate comprehensive AI analysis across all respondents for a survey."""
    conn = get_db()
    try:
        # Get survey info
        survey = conn.execute("SELECT * FROM surveys WHERE id = ?", (survey_id,)).fetchone()
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")
        survey_dict = dict(survey)

        # Get questions
        questions = conn.execute(
            "SELECT question_text FROM questions WHERE survey_id = ? ORDER BY order_index",
            (survey_id,)
        ).fetchall()
        question_texts = [dict(q)["question_text"] for q in questions]

        # Get all completed sessions with conversation history
        sessions = conn.execute("""
            SELECT s.session_id, s.channel, s.status, s.completion_percentage
            FROM interview_sessions s
            WHERE s.survey_id = ? AND s.status IN ('completed', 'completing', 'active')
            ORDER BY s.started_at DESC
        """, (survey_id,)).fetchall()

        transcripts = []
        for sess in sessions:
            sd = dict(sess)
            history = conn.execute(
                "SELECT role, message FROM conversation_history WHERE session_id = ? ORDER BY created_at",
                (sd["session_id"],)
            ).fetchall()
            entries = [dict(h) for h in history]
            if len(entries) >= 2:  # At least one Q&A exchange
                transcripts.append({
                    "session_id": sd["session_id"],
                    "channel": sd["channel"],
                    "entries": entries
                })

        # Count stats
        total_respondents = conn.execute(
            "SELECT COUNT(DISTINCT respondent_id) as c FROM survey_respondents WHERE survey_id = ?",
            (survey_id,)
        ).fetchone()["c"]
        completed = conn.execute(
            "SELECT COUNT(*) as c FROM survey_respondents WHERE survey_id = ? AND status = 'completed'",
            (survey_id,)
        ).fetchone()["c"]
    finally:
        conn.close()

    if len(transcripts) == 0:
        return {
            "survey_id": survey_id,
            "has_data": False,
            "message": "No completed interviews yet. Share your survey link and wait for respondents to complete their interviews.",
            "total_respondents": total_respondents,
            "completed": completed,
            "transcripts_available": 0
        }

    # Call AI for group analysis
    survey_data = {
        "title": survey_dict.get("title", ""),
        "description": survey_dict.get("description", ""),
        "questions": question_texts,
        "transcripts": transcripts,
        "respondent_count": total_respondents,
        "completed_count": completed,
    }

    try:
        analysis = AIService.generate_survey_group_analysis(survey_data)
    except Exception as e:
        print(f"[AI Analysis Error] survey_id={survey_id}: {e}")
        analysis = {
            "executive_summary": f"Analysis generation encountered an error: {str(e)[:200]}",
            "key_themes": [],
            "sentiment_overview": {"positive": 0, "neutral": 0, "negative": 0},
            "recommendations": ["Please try again later or check your AI service configuration."],
            "error": True
        }

    return {
        "survey_id": survey_id,
        "has_data": True,
        "total_respondents": total_respondents,
        "completed": completed,
        "transcripts_analyzed": len(transcripts),
        "analysis": analysis
    }


# ═══════════════════════════════════════════════════
# RESPONDENTS LIST — Separate from analytics
# ═══════════════════════════════════════════════════
@router.get("/respondents/{survey_id}")
def get_survey_respondents(survey_id: int, current_user: dict = Depends(get_current_user)):
    """Get all respondents for a survey with their session details."""
    conn = get_db()

    respondents = conn.execute("""
        SELECT resp.email, resp.name, sr.channel, sr.status, sr.started_at, sr.completed_at, sr.session_id,
               i.completion_percentage, i.engagement_score
        FROM survey_respondents sr
        JOIN respondents resp ON sr.respondent_id = resp.id
        LEFT JOIN interview_sessions i ON sr.session_id = i.session_id
        WHERE sr.survey_id = ?
        ORDER BY sr.started_at DESC
    """, (survey_id,)).fetchall()

    # For each completed respondent, check if transcript report exists
    result = []
    for r in respondents:
        rd = dict(r)
        # Check for AI report
        if rd["session_id"]:
            transcript = conn.execute(
                "SELECT id, word_count, sentiment_overall, key_topics, ai_report_json FROM full_transcripts WHERE session_id = ?",
                (rd["session_id"],)
            ).fetchone()
            if transcript:
                td = dict(transcript)
                rd["has_transcript"] = True
                rd["word_count"] = td["word_count"]
                rd["sentiment_overall"] = td["sentiment_overall"]
                rd["has_ai_report"] = bool(td.get("ai_report_json"))
            else:
                rd["has_transcript"] = False
                rd["has_ai_report"] = False
        result.append(rd)

    conn.close()
    return result


# ═══════════════════════════════════════════════════
# TRANSCRIPT MANAGEMENT
# ═══════════════════════════════════════════════════
@router.post("/transcripts/{session_id}")
def save_transcript(session_id: str):
    """Generate and store full transcript + AI analysis report for a completed session."""
    conn = get_db()
    try:
        session = conn.execute("SELECT * FROM interview_sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        session_dict = dict(session)

        # Get full conversation history
        history = conn.execute(
            "SELECT role, message, message_type, created_at FROM conversation_history "
            "WHERE session_id = ? ORDER BY created_at",
            (session_id,)
        ).fetchall()

        # Build transcript
        transcript_entries = []
        word_count = 0
        for h in history:
            entry = dict(h)
            transcript_entries.append({
                "role": entry["role"],
                "message": entry["message"],
                "type": entry["message_type"],
                "timestamp": entry["created_at"],
            })
            word_count += len(entry["message"].split())

        # Get responses with sentiment
        responses = conn.execute(
            "SELECT r.*, q.question_text FROM responses r "
            "LEFT JOIN questions q ON r.question_id = q.id "
            "WHERE r.session_id = ? ORDER BY r.created_at",
            (session_id,)
        ).fetchall()

        sentiments = [dict(r)["sentiment_score"] for r in responses if dict(r)["sentiment_score"] is not None]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else None

        # Get respondent ID from survey_respondents
        sr = conn.execute(
            "SELECT respondent_id FROM survey_respondents WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        respondent_id = dict(sr)["respondent_id"] if sr else None

        transcript_json = json.dumps(transcript_entries, indent=2)

        # Generate AI analysis report only if there's actual conversation data
        ai_report = None
        ai_report_json = None
        key_topics = None
        if len(history) >= 2 and len(responses) > 0:
            try:
                session_data = {
                    "session": session_dict,
                    "history": [dict(h) for h in history],
                    "responses": [dict(r) for r in responses]
                }
                ai_report = AIService.generate_interview_transcript_report(session_data)
                ai_report_json = json.dumps(ai_report, indent=2) if ai_report else None

                if ai_report and "transcript_summary" in ai_report:
                    topics = ai_report["transcript_summary"].get("key_topics_discussed", [])
                    key_topics = json.dumps(topics) if topics else None
            except Exception as e:
                import traceback
                traceback.print_exc()
                ai_report_json = None

        # Upsert transcript
        existing = conn.execute("SELECT id FROM full_transcripts WHERE session_id = ?", (session_id,)).fetchone()
        if existing:
            conn.execute("""
                UPDATE full_transcripts SET transcript_json = ?, ai_report_json = ?,
                word_count = ?, sentiment_overall = ?, key_topics = ?, updated_at = ?
                WHERE session_id = ?
            """, (transcript_json, ai_report_json, word_count, avg_sentiment, key_topics,
                  datetime.now().isoformat(), session_id))
        else:
            conn.execute("""
                INSERT INTO full_transcripts (session_id, survey_id, respondent_id, transcript_json, ai_report_json,
                                              word_count, sentiment_overall, key_topics)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, session_dict["survey_id"], respondent_id, transcript_json, ai_report_json,
                  word_count, avg_sentiment, key_topics))

        # Also mark survey_respondents as completed
        conn.execute("UPDATE survey_respondents SET status = 'completed', completed_at = ? WHERE session_id = ?",
                     (datetime.now().isoformat(), session_id))

        conn.commit()

        return {
            "message": "Transcript and AI report saved",
            "session_id": session_id,
            "word_count": word_count,
            "entries": len(transcript_entries),
            "avg_sentiment": avg_sentiment,
            "has_ai_report": bool(ai_report_json),
        }
    finally:
        conn.close()

@router.get("/transcripts/{survey_id}/all")
def get_all_transcripts(survey_id: int):
    """Get all transcripts for a survey (for group analysis)."""
    conn = get_db()
    transcripts = conn.execute("""
        SELECT ft.*, resp.email, resp.name as respondent_name
        FROM full_transcripts ft
        LEFT JOIN respondents resp ON ft.respondent_id = resp.id
        WHERE ft.survey_id = ?
        ORDER BY ft.created_at DESC
    """, (survey_id,)).fetchall()
    conn.close()
    return [dict(t) for t in transcripts]


@router.get("/transcripts/session/{session_id}")
def get_session_transcript(session_id: str):
    """Get single session transcript."""
    conn = get_db()
    transcript = conn.execute("SELECT * FROM full_transcripts WHERE session_id = ?", (session_id,)).fetchone()
    if not transcript:
        conn.close()
        raise HTTPException(status_code=404, detail="Transcript not found")
    conn.close()
    return dict(transcript)


# ═══════════════════════════════════════════════════
# EXPORTS — CSV & PDF-ready data
# ═══════════════════════════════════════════════════
@router.get("/export/{survey_id}/respondents-csv")
def export_respondents_csv(survey_id: int, current_user: dict = Depends(get_current_user)):
    """Export all respondent data as a downloadable CSV file."""
    conn = get_db()
    try:
        respondents = conn.execute("""
            SELECT resp.email, resp.name, sr.channel, sr.status, sr.started_at, sr.completed_at, sr.session_id,
                   i.completion_percentage, i.engagement_score
            FROM survey_respondents sr
            JOIN respondents resp ON sr.respondent_id = resp.id
            LEFT JOIN interview_sessions i ON sr.session_id = i.session_id
            WHERE sr.survey_id = ?
            ORDER BY sr.started_at DESC
        """, (survey_id,)).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Email", "Name", "Channel", "Status", "Started", "Completed", "Completion %", "Engagement"])
        for r in respondents:
            rd = dict(r)
            writer.writerow([
                rd.get("email", ""), rd.get("name", ""), rd.get("channel", ""),
                rd.get("status", ""), rd.get("started_at", ""), rd.get("completed_at", ""),
                rd.get("completion_percentage", ""), rd.get("engagement_score", "")
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=respondents_survey_{survey_id}.csv"}
        )
    finally:
        conn.close()


@router.get("/export/{survey_id}/analysis-csv")
def export_analysis_csv(survey_id: int, current_user: dict = Depends(get_current_user)):
    """Export analytics data as a downloadable CSV file."""
    conn = get_db()
    try:
        # Get responses with session and question info
        rows = conn.execute("""
            SELECT resp_tbl.email, r.response_text, r.response_type, r.sentiment_score,
                   r.emotion, r.quality_score, r.created_at, q.question_text, i.channel
            FROM responses r
            JOIN interview_sessions i ON r.session_id = i.session_id
            LEFT JOIN survey_respondents sr ON sr.session_id = i.session_id
            LEFT JOIN respondents resp_tbl ON sr.respondent_id = resp_tbl.id
            LEFT JOIN questions q ON r.question_id = q.id
            WHERE i.survey_id = ?
            ORDER BY r.created_at
        """, (survey_id,)).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Email", "Question", "Response", "Type", "Sentiment", "Emotion", "Quality", "Channel", "Timestamp"])
        for r in rows:
            rd = dict(r)
            writer.writerow([
                rd.get("email", ""), rd.get("question_text", ""), rd.get("response_text", ""),
                rd.get("response_type", ""), rd.get("sentiment_score", ""), rd.get("emotion", ""),
                rd.get("quality_score", ""), rd.get("channel", ""), rd.get("created_at", "")
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=analysis_survey_{survey_id}.csv"}
        )
    finally:
        conn.close()


@router.get("/export/{survey_id}/report-html")
def export_report_html(survey_id: int, current_user: dict = Depends(get_current_user)):
    """Export a printable/PDF-ready HTML report of the AI analysis."""
    conn = get_db()
    try:
        survey = conn.execute("SELECT * FROM surveys WHERE id = ?", (survey_id,)).fetchone()
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")
        survey_dict = dict(survey)

        # Get analytics stats
        total = conn.execute("SELECT COUNT(DISTINCT respondent_id) as c FROM survey_respondents WHERE survey_id = ?", (survey_id,)).fetchone()["c"]
        completed = conn.execute("SELECT COUNT(*) as c FROM survey_respondents WHERE survey_id = ? AND status = 'completed'", (survey_id,)).fetchone()["c"]
        avg_sent = conn.execute(
            "SELECT AVG(r.sentiment_score) as v FROM responses r JOIN interview_sessions s ON r.session_id = s.session_id WHERE s.survey_id = ? AND r.sentiment_score IS NOT NULL",
            (survey_id,)
        ).fetchone()["v"]

        respondents = conn.execute("""
            SELECT resp.email, sr.channel, sr.status, sr.completed_at
            FROM survey_respondents sr JOIN respondents resp ON sr.respondent_id = resp.id
            WHERE sr.survey_id = ? ORDER BY sr.started_at DESC
        """, (survey_id,)).fetchall()
    finally:
        conn.close()

    title = Helpers_escape(survey_dict.get("title", "Untitled Survey"))
    sent_pct = f"{(avg_sent * 100):.0f}%" if avg_sent is not None else "N/A"

    respondent_rows = ""
    for r in respondents:
        rd = dict(r)
        respondent_rows += f"<tr><td>{Helpers_escape(rd.get('email',''))}</td><td>{rd.get('channel','')}</td><td>{rd.get('status','')}</td><td>{rd.get('completed_at','')}</td></tr>"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Report — {title}</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 800px; margin: 40px auto; color: #333; line-height: 1.6; }}
h1 {{ color: #4f46e5; border-bottom: 3px solid #4f46e5; padding-bottom: 8px; }}
h2 {{ color: #374151; margin-top: 32px; }}
.stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 24px 0; }}
.stat {{ text-align: center; padding: 20px; background: #f9fafb; border-radius: 12px; border: 1px solid #e5e7eb; }}
.stat-val {{ font-size: 2rem; font-weight: 700; color: #4f46e5; }}
.stat-lbl {{ font-size: 0.85rem; color: #6b7280; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 0.9rem; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
th {{ background: #f3f4f6; font-weight: 600; }}
.footer {{ margin-top: 40px; text-align: center; font-size: 0.8rem; color: #9ca3af; }}
@media print {{ body {{ margin: 0; }} }}
</style></head><body>
<h1>Survey Report — {title}</h1>
<p style="color:#6b7280">Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
<div class="stats">
  <div class="stat"><div class="stat-val">{total}</div><div class="stat-lbl">Total Respondents</div></div>
  <div class="stat"><div class="stat-val">{completed}</div><div class="stat-lbl">Completed</div></div>
  <div class="stat"><div class="stat-val">{sent_pct}</div><div class="stat-lbl">Avg Sentiment</div></div>
</div>
<h2>Respondents</h2>
<table><thead><tr><th>Email</th><th>Channel</th><th>Status</th><th>Completed</th></tr></thead>
<tbody>{respondent_rows}</tbody></table>
<div class="footer"><p>AI Insight Engine &mdash; Confidential Report</p></div>
</body></html>"""

    return StreamingResponse(
        iter([html]),
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename=report_survey_{survey_id}.html"}
    )


def Helpers_escape(s):
    """Simple HTML escape for report generation."""
    if not s:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ═══════════════════════════════════════════════════
# HELPER
# ═══════════════════════════════════════════════════
def _build_links(share_code: str) -> dict:
    """Build the 3 interview channel links for a share code."""
    base = f"/interview/{share_code}"
    return {
        "web_form": f"{base}/web-form",
        "chat": f"{base}/chat",
        "audio": f"{base}/audio",
        "landing": f"{base}",
    }
