"""
Interview & Feedback Collection API Routes — Features 2 & 5
Architecture: Event-driven — responses stored immediately, AI processing asynchronously.
Includes: semantic memory, theme clustering, response segmentation, simulated interviews.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from ..database import get_db
from ..models import SessionCreate, ResponseCreate, ChatMessage, SimulationRequest
from ..services.ai_service import AIService
from ..services.transcription_service import TranscriptionService
from ..services.event_bus import event_bus, Event, EventType
from ..services.ai_orchestrator import AIOrchestrator
import uuid
import json
import os
import tempfile
from datetime import datetime

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


# ── Session Management ──
@router.post("/sessions")
def create_session(session: SessionCreate):
    """Create a new interview session with dynamic, survey-aware intro."""
    conn = get_db()
    session_id = str(uuid.uuid4())
    respondent_id = str(uuid.uuid4())[:12]
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO interview_sessions (survey_id, respondent_id, session_id, channel, device_type, language)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session.survey_id, respondent_id, session_id, session.channel, session.device_type, session.language))
    conn.commit()

    # Get survey details for dynamic intro
    survey = conn.execute("SELECT * FROM surveys WHERE id = ?", (session.survey_id,)).fetchone()
    first_question = conn.execute(
        "SELECT * FROM questions WHERE survey_id = ? ORDER BY order_index LIMIT 1",
        (session.survey_id,)
    ).fetchone()

    # Build a dynamic intro message based on the survey topic
    survey_title = ""
    survey_desc = ""
    goal_text = ""
    if survey:
        survey_dict = dict(survey)
        survey_title = survey_dict.get("title", "")
        survey_desc = survey_dict.get("description", "")
        if survey_dict.get("research_goal_id"):
            goal = conn.execute("SELECT * FROM research_goals WHERE id = ?", (survey_dict["research_goal_id"],)).fetchone()
            if goal:
                goal_text = dict(goal).get("description", "")

    # Generate a contextual welcome message
    if survey_title and survey_title != survey_desc:
        intro = f"Hi there! 👋 I'm your AI research interviewer. Today I'd love to chat with you about **{survey_title}**. There are no right or wrong answers — I'm just here to understand your genuine experience and thoughts. This should take about 5 minutes. Ready to start?"
    elif goal_text:
        topic_preview = goal_text[:120]
        intro = f"Hi there! 👋 I'm your AI research interviewer. I'll be asking you some questions to help us understand your experience better. Specifically, we're exploring: {topic_preview}. No right or wrong answers — just share honestly! Ready?"
    else:
        intro = "Hi there! 👋 I'm your AI research interviewer. I'll be asking you a few questions about your experience. There are no right or wrong answers — just share honestly. This takes about 3-5 minutes. Ready to start?"

    # Store intro in conversation history
    cursor.execute("""
        INSERT INTO conversation_history (session_id, role, message, message_type)
        VALUES (?, 'ai', ?, 'text')
    """, (session_id, intro))

    # Get question count for progress tracking
    q_count = conn.execute("SELECT COUNT(*) as c FROM questions WHERE survey_id = ?", (session.survey_id,)).fetchone()["c"]

    conn.commit()
    conn.close()

    return {
        "session_id": session_id,
        "respondent_id": respondent_id,
        "survey_title": survey_title,
        "intro_message": intro,
        "first_question": dict(first_question) if first_question else None,
        "estimated_duration": dict(survey)["estimated_duration"] if survey else 5,
        "total_questions": q_count
    }


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    conn = get_db()
    session = conn.execute("SELECT * FROM interview_sessions WHERE session_id = ?", (session_id,)).fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
    history = conn.execute(
        "SELECT * FROM conversation_history WHERE session_id = ? ORDER BY created_at",
        (session_id,)
    ).fetchall()
    conn.close()
    return {**dict(session), "history": [dict(h) for h in history]}


@router.post("/sessions/{session_id}/resume")
def resume_session(session_id: str):
    """Resume a paused/incomplete session."""
    conn = get_db()
    session = conn.execute("SELECT * FROM interview_sessions WHERE session_id = ?", (session_id,)).fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    history = conn.execute(
        "SELECT * FROM conversation_history WHERE session_id = ? ORDER BY created_at",
        (session_id,)
    ).fetchall()

    last_question = conn.execute("""
        SELECT q.* FROM questions q
        JOIN responses r ON r.question_id = q.id
        WHERE r.session_id = ?
        ORDER BY q.order_index DESC LIMIT 1
    """, (session_id,)).fetchone()

    next_question = None
    if last_question:
        next_question = conn.execute(
            "SELECT * FROM questions WHERE survey_id = ? AND order_index > ? ORDER BY order_index LIMIT 1",
            (dict(session)["survey_id"], dict(last_question)["order_index"])
        ).fetchone()

    conn.close()
    return {
        "session": dict(session),
        "history": [dict(h) for h in history],
        "next_question": dict(next_question) if next_question else None,
        "resume_message": "Welcome back! Let's continue where you left off."
    }


# ── Response Collection ──
@router.post("/respond")
def submit_response(response: ResponseCreate):
    """Submit a response and get AI-powered follow-up."""
    conn = get_db()
    # Validate session exists first
    session = conn.execute("SELECT * FROM interview_sessions WHERE session_id = ?", (response.session_id,)).fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        cursor = conn.cursor()

        # Analyze response — use fast local fallbacks for sentiment & quality,
        # keep Gemini only for follow-up generation (critical for UX)
        from ..services.ai_service import _fallback_sentiment
        sentiment = _fallback_sentiment(response.response_text)
        words = response.response_text.split()
        wc = len(words)
        _clarity = min(1.0, wc / 20) if wc > 3 else 0.3
        _depth = min(1.0, wc / 40) if wc > 5 else 0.2
        _relevance = 0.8
        _q_score = round(_clarity * 0.3 + _depth * 0.4 + _relevance * 0.3, 2)
        quality = {"quality_score": _q_score, "clarity": round(_clarity, 2), "depth": round(_depth, 2), "relevance": round(_relevance, 2), "word_count": wc, "needs_follow_up": _q_score < 0.5}
        follow_up = AIService.generate_follow_up(response.response_text)

        # Store response
        cursor.execute("""
            INSERT INTO responses (session_id, question_id, response_text, response_type, emoji_data, voice_metadata,
                sentiment_score, emotion, intent, confidence, quality_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            response.session_id, response.question_id, response.response_text, response.response_type,
            response.emoji_data, response.voice_metadata,
            sentiment["sentiment_score"], sentiment["emotion"], follow_up["intent"],
            sentiment["confidence"], quality["quality_score"]
        ))

        # Store in conversation history
        cursor.execute("""
            INSERT INTO conversation_history (session_id, role, message, message_type, metadata)
            VALUES (?, 'user', ?, ?, ?)
        """, (response.session_id, response.response_text, response.response_type,
              json.dumps({"sentiment": sentiment, "quality": quality})))

        # Get next question
        next_question = None
        if response.question_id:
            current_q = conn.execute("SELECT * FROM questions WHERE id = ?", (response.question_id,)).fetchone()
            if current_q:
                # Check for conditional logic
                cond = current_q["conditional_logic"]
                if cond:
                    try:
                        cond_data = json.loads(cond)
                        # Simple yes/no branching
                        if response.response_text.lower().strip() in ["yes", "y"]:
                            branch_id = cond_data.get("yes")
                        else:
                            branch_id = cond_data.get("no")
                        if branch_id:
                            next_question = conn.execute("SELECT * FROM questions WHERE id = ?", (branch_id,)).fetchone()
                    except (json.JSONDecodeError, TypeError):
                        pass

                if not next_question:
                    next_question = conn.execute(
                        "SELECT * FROM questions WHERE survey_id = ? AND order_index > ? ORDER BY order_index LIMIT 1",
                        (dict(session)["survey_id"], current_q["order_index"])
                    ).fetchone()

        # Update session engagement
        responses_count = conn.execute(
            "SELECT COUNT(*) as c FROM responses WHERE session_id = ?", (response.session_id,)
        ).fetchone()["c"]
        total_questions = conn.execute(
            "SELECT COUNT(*) as c FROM questions WHERE survey_id = ?", (dict(session)["survey_id"],)
        ).fetchone()["c"]

        completion = round((responses_count / max(total_questions, 1)) * 100, 1)
        conn.execute(
            "UPDATE interview_sessions SET completion_percentage = ?, engagement_score = ? WHERE session_id = ?",
            (completion, quality["quality_score"], response.session_id)
        )

        # AI follow-up message in history
        ai_msg = follow_up["follow_up"]
        if next_question:
            ai_msg = dict(next_question)["question_text"]
        elif not next_question and completion >= 90:
            ai_msg = "Thank you so much for sharing! Is there anything else you'd like to tell us that we didn't ask about?"
            conn.execute("UPDATE interview_sessions SET status = 'completing' WHERE session_id = ?", (response.session_id,))

        cursor.execute("""
            INSERT INTO conversation_history (session_id, role, message, message_type)
            VALUES (?, 'ai', ?, 'text')
        """, (response.session_id, ai_msg))

        # ── Response Segmentation ──
        segments = AIService.segment_response(response.response_text)
        response_id = cursor.lastrowid
        for idx, seg in enumerate(segments):
            cursor.execute("""
                INSERT INTO response_segments (response_id, session_id, segment_text, topic, sentiment_label, sentiment_score, emotion, confidence, order_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (response_id, response.session_id, seg.get("segment_text", ""), seg.get("topic", ""),
                  seg.get("sentiment_label", "neutral"), seg.get("sentiment_score", 0),
                  seg.get("emotion", "neutral"), seg.get("confidence", 0), idx))

        # ── Semantic Memory Extraction ──
        existing_mem = conn.execute("SELECT entity, relation, value FROM semantic_memory WHERE session_id = ?", (response.session_id,)).fetchall()
        existing_mem_list = [dict(m) for m in existing_mem]
        memories = AIService.extract_semantic_memory(response.response_text, existing_mem_list)
        for mem in memories:
            cursor.execute("""
                INSERT INTO semantic_memory (session_id, entity, relation, value, confidence, source_response_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (response.session_id, mem.get("entity", ""), mem.get("relation", ""),
                  mem.get("value", ""), mem.get("confidence", 0.5), response_id))

        # ── Theme Clustering (every 3 responses) ──
        if responses_count % 3 == 0:
            try:
                recent_responses = conn.execute(
                    "SELECT response_text FROM responses WHERE session_id = ? ORDER BY created_at DESC LIMIT 5",
                    (response.session_id,)
                ).fetchall()
                resp_list = [{"response_text": dict(r)["response_text"]} for r in recent_responses]
                existing_themes = conn.execute("SELECT name, description FROM themes WHERE survey_id = ?", (dict(session)["survey_id"],)).fetchall()
                themes = AIService.cluster_themes_from_responses(resp_list, [dict(t) for t in existing_themes])
                for theme in themes:
                    # Check if theme already exists
                    existing = conn.execute("SELECT id, frequency FROM themes WHERE survey_id = ? AND name = ?",
                        (dict(session)["survey_id"], theme.get("name", ""))).fetchone()
                    if existing:
                        conn.execute("UPDATE themes SET frequency = frequency + 1, sentiment_avg = ?, updated_at = ? WHERE id = ?",
                            (theme.get("sentiment_avg", 0), datetime.now().isoformat(), dict(existing)["id"]))
                    else:
                        conn.execute("""
                            INSERT INTO themes (survey_id, name, description, frequency, sentiment_avg, priority, business_risk, is_emerging)
                            VALUES (?, ?, ?, 1, ?, ?, ?, ?)
                        """, (dict(session)["survey_id"], theme.get("name", "Unknown"), theme.get("description", ""),
                              theme.get("sentiment_avg", 0), theme.get("priority", "medium"),
                              theme.get("business_risk", "low"), 1 if theme.get("is_emerging") else 0))
            except Exception as e:
                print(f"[Theme clustering error] {e}")

        # ── ARCHITECTURE: Publish event for background processing ──
        event_bus.publish(Event(
            EventType.RESPONSE_SUBMITTED,
            {
                "response_id": response_id,
                "session_id": response.session_id,
                "survey_id": dict(session)["survey_id"],
                "response_text": response.response_text,
                "question_id": response.question_id,
            },
            source="respond_route"
        ))

        conn.commit()

        return {
            "sentiment": sentiment,
            "quality": quality,
            "follow_up": follow_up,
            "next_question": dict(next_question) if next_question else None,
            "ai_message": ai_msg,
            "completion_percentage": completion,
            "is_complete": completion >= 100
        }
    finally:
        conn.close()


# ── Chat Interface ──
@router.post("/chat")
def chat_message(msg: ChatMessage):
    """Handle chat-style message exchange with full survey context."""
    conn = get_db()
    try:
        # Validate session exists first
        session = conn.execute("SELECT * FROM interview_sessions WHERE session_id = ?", (msg.session_id,)).fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        cursor = conn.cursor()
        is_start_signal = msg.message.strip() == '__START__'

        # Store user message in conversation history
        cursor.execute("""
            INSERT INTO conversation_history (session_id, role, message, message_type)
            VALUES (?, 'user', ?, ?)
        """, (msg.session_id, msg.message, msg.message_type))

        # Use LOCAL analysis to avoid burning Gemini quota on secondary tasks
        from ..services.ai_service import _fallback_sentiment, _fallback_follow_up
        sentiment = _fallback_sentiment(msg.message)
        follow_up = _fallback_follow_up(msg.message)
        words = msg.message.split()
        wc = len(words)
        clarity = min(1.0, wc / 20) if wc > 3 else 0.3
        depth = min(1.0, wc / 40) if wc > 5 else 0.2
        relevance = 0.8
        q_score = round(clarity * 0.3 + depth * 0.4 + relevance * 0.3, 2)
        quality = {"quality_score": q_score, "clarity": round(clarity, 2), "depth": round(depth, 2), "relevance": round(relevance, 2), "word_count": wc, "needs_follow_up": q_score < 0.5}

        # Store response record (skip for __START__ signal to avoid polluting data)
        if not is_start_signal:
            cursor.execute("""
                INSERT INTO responses (session_id, response_text, response_type, sentiment_score, emotion, intent, confidence, quality_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (msg.session_id, msg.message, msg.message_type,
                  sentiment["sentiment_score"], sentiment["emotion"], follow_up["intent"],
                  sentiment["confidence"], quality["quality_score"]))

        # ── COMMIT user data FIRST so it's not lost if Gemini fails ──
        conn.commit()

        # ── Fetch full survey context for the AI ──
        survey_context = None
        if session:
            survey = conn.execute("SELECT * FROM surveys WHERE id = ?", (dict(session)["survey_id"],)).fetchone()
            if survey:
                survey_dict = dict(survey)
                questions = conn.execute(
                    "SELECT question_text, question_type, tone, depth_level FROM questions WHERE survey_id = ? ORDER BY order_index",
                    (survey_dict["id"],)
                ).fetchall()
                # Get the research goal
                goal_text = survey_dict.get("description", "")
                if survey_dict.get("research_goal_id"):
                    goal = conn.execute("SELECT * FROM research_goals WHERE id = ?", (survey_dict["research_goal_id"],)).fetchone()
                    if goal:
                        goal_text = dict(goal).get("description", "") or goal_text
                survey_context = {
                    "research_goal": goal_text,
                    "survey_title": survey_dict.get("title", ""),
                    "questions": [dict(q) for q in questions]
                }

        # Generate AI response using Gemini conversational AI with semantic memory + survey context
        history = conn.execute(
            "SELECT role, message FROM conversation_history WHERE session_id = ? ORDER BY created_at",
            (msg.session_id,)
        ).fetchall()
        history_list = [dict(h) for h in history]

        # Fetch semantic memory for context-aware responses
        memory = conn.execute("SELECT entity, relation, value FROM semantic_memory WHERE session_id = ?", (msg.session_id,)).fetchall()
        memory_list = [dict(m) for m in memory]

        try:
            ai_response = AIService.generate_chat_response_with_memory(msg.message, history_list, memory_list, survey_context)
        except Exception as e:
            print(f"[Chat Gemini Error] session={msg.session_id}: {e}")
            ai_response = None

        # Safety net: ensure we ALWAYS return a message
        if not ai_response or len(ai_response.strip()) < 10:
            from ..services.ai_service import _dynamic_fallback_response
            ai_response = _dynamic_fallback_response(msg.message, history_list, survey_context)

        # Store AI message
        cursor.execute("""
            INSERT INTO conversation_history (session_id, role, message, message_type, metadata)
            VALUES (?, 'ai', ?, 'text', ?)
        """, (msg.session_id, ai_response, json.dumps({"sentiment": sentiment})))

        # ── Extract semantic memory from chat message (every 3rd message to save Gemini quota) ──
        response_id = cursor.lastrowid
        response_count = conn.execute("SELECT COUNT(*) as c FROM responses WHERE session_id = ?", (msg.session_id,)).fetchone()["c"]
        if response_count > 0 and response_count % 3 == 0:
            try:
                memories = AIService.extract_semantic_memory(msg.message, memory_list)
                for mem in memories:
                    cursor.execute("""
                        INSERT INTO semantic_memory (session_id, entity, relation, value, confidence, source_response_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (msg.session_id, mem.get("entity", ""), mem.get("relation", ""),
                          mem.get("value", ""), mem.get("confidence", 0.5), response_id))
            except Exception as e:
                print(f"[Semantic memory error] {e}")

        # ── Segment only longer messages to save Gemini quota ──
        if not is_start_signal and len(msg.message.split()) >= 15:
            try:
                segments = AIService.segment_response(msg.message)
                for idx, seg in enumerate(segments):
                    cursor.execute("""
                        INSERT INTO response_segments (response_id, session_id, segment_text, topic, sentiment_label, sentiment_score, emotion, confidence, order_index)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (response_id, msg.session_id, seg.get("segment_text", ""), seg.get("topic", ""),
                          seg.get("sentiment_label", "neutral"), seg.get("sentiment_score", 0),
                          seg.get("emotion", "neutral"), seg.get("confidence", 0), idx))
            except Exception as e:
                print(f"[Segmentation error] {e}")

        # Calculate progress and update completion_percentage
        total_questions = len(survey_context.get("questions", [])) if survey_context else 5
        response_count = conn.execute("SELECT COUNT(*) as c FROM responses WHERE session_id = ?", (msg.session_id,)).fetchone()["c"]
        progress = min(100, round((response_count / max(total_questions, 1)) * 100))
        interview_complete = progress >= 100

        # Always update completion_percentage on session
        conn.execute(
            "UPDATE interview_sessions SET completion_percentage = ?, engagement_score = ? WHERE session_id = ?",
            (progress, quality["quality_score"], msg.session_id)
        )

        if interview_complete:
            conn.execute("UPDATE interview_sessions SET status = 'completed', completed_at = ? WHERE session_id = ?",
                         (datetime.now().isoformat(), msg.session_id))
            # ── ARCHITECTURE: Publish interview completion event ──
            event_bus.publish(Event(
                EventType.INTERVIEW_COMPLETED,
                {"session_id": msg.session_id, "survey_id": dict(session)["survey_id"]},
                source="chat_route"
            ))

        conn.commit()

        return {
            "ai_message": ai_response,
            "sentiment": sentiment,
            "quality": quality,
            "quick_replies": _get_quick_replies(follow_up["intent"]),
            "typing_delay": _get_typing_delay(ai_response),
            "progress": progress,
            "interview_complete": interview_complete
        }
    finally:
        conn.close()


@router.get("/sessions/{session_id}/history")
def get_chat_history(session_id: str):
    conn = get_db()
    history = conn.execute(
        "SELECT * FROM conversation_history WHERE session_id = ? ORDER BY created_at",
        (session_id,)
    ).fetchall()
    conn.close()
    return [dict(h) for h in history]


@router.post("/sessions/{session_id}/complete")
def complete_interview(session_id: str):
    """Mark interview as complete and generate transcript report."""
    conn = get_db()
    session = conn.execute("SELECT * FROM interview_sessions WHERE session_id = ?", (session_id,)).fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    history = conn.execute(
        "SELECT * FROM conversation_history WHERE session_id = ? ORDER BY created_at",
        (session_id,)
    ).fetchall()
    responses = conn.execute(
        "SELECT r.*, q.question_text FROM responses r LEFT JOIN questions q ON r.question_id = q.id WHERE r.session_id = ? ORDER BY r.created_at",
        (session_id,)
    ).fetchall()

    session_data = {
        "session": dict(session),
        "history": [dict(h) for h in history],
        "responses": [dict(r) for r in responses]
    }

    # Generate AI transcript report
    report = AIService.generate_interview_transcript_report(session_data)

    # Mark session complete
    conn.execute(
        "UPDATE interview_sessions SET status = 'completed', completed_at = ? WHERE session_id = ?",
        (datetime.now().isoformat(), session_id)
    )
    conn.commit()

    # ── ARCHITECTURE: Publish event for background processing ──
    event_bus.publish(Event(
        EventType.INTERVIEW_COMPLETED,
        {"session_id": session_id, "survey_id": dict(session)["survey_id"]},
        source="interview_route"
    ))

    conn.close()

    return {
        "session_id": session_id,
        "report": report,
        "history": [dict(h) for h in history],
        "responses": [dict(r) for r in responses]
    }


# ── Engagement Metrics ──
@router.get("/metrics/{survey_id}")
def get_engagement_metrics(survey_id: int):
    conn = get_db()
    metrics = conn.execute(
        "SELECT * FROM engagement_metrics WHERE survey_id = ?", (survey_id,)
    ).fetchall()
    sessions = conn.execute("""
        SELECT channel, COUNT(*) as total, 
               AVG(completion_percentage) as avg_completion,
               AVG(engagement_score) as avg_engagement
        FROM interview_sessions WHERE survey_id = ? GROUP BY channel
    """, (survey_id,)).fetchall()
    conn.close()
    return {
        "metrics": [dict(m) for m in metrics],
        "session_stats": [dict(s) for s in sessions]
    }


def _get_quick_replies(intent: str) -> list:
    """Generate quick reply buttons based on context."""
    if intent == "complaint":
        return ["It happened once", "It happens often", "Every time", "Not sure"]
    elif intent == "confusion":
        return ["The UI", "The instructions", "The workflow", "Something else"]
    elif intent == "praise":
        return ["The design", "The speed", "The features", "Everything"]
    return ["Yes", "No", "Tell me more", "Skip"]


def _get_typing_delay(message: str) -> int:
    """Calculate realistic typing delay in ms."""
    words = len(message.split())
    return min(max(words * 80, 500), 2500)


# ── Voice Transcription (AssemblyAI) ──
@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Upload an audio file and transcribe it using AssemblyAI."""
    # Save uploaded file to temp location
    suffix = os.path.splitext(file.filename or "audio.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = TranscriptionService.transcribe_file(tmp_path)
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post("/transcribe-and-respond")
async def transcribe_and_respond(
    file: UploadFile = File(...),
    session_id: str = "",
    question_id: int = 0,
):
    """Transcribe voice audio via AssemblyAI, then process as a survey response."""
    suffix = os.path.splitext(file.filename or "audio.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        transcription = TranscriptionService.transcribe_file(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if transcription.get("error"):
        raise HTTPException(status_code=500, detail=transcription["error"])

    text = transcription.get("text", "")
    if not text:
        return {"transcript": "", "message": "No speech detected in audio."}

    # Run AI analysis on the transcript
    sentiment = AIService.analyze_sentiment(text)
    quality = AIService.score_response_quality(text)
    follow_up = AIService.generate_follow_up(text)

    # Store in DB if we have a session
    if session_id:
        conn = get_db()
        cursor = conn.cursor()
        voice_meta = json.dumps({
            "confidence": transcription.get("confidence"),
            "duration_ms": transcription.get("duration_ms"),
            "language": transcription.get("language"),
            "highlights": transcription.get("highlights", []),
            "assemblyai_sentiments": transcription.get("sentiments", []),
        })

        cursor.execute("""
            INSERT INTO responses (session_id, question_id, response_text, response_type, voice_metadata,
                sentiment_score, emotion, intent, confidence, quality_score)
            VALUES (?, ?, ?, 'voice', ?, ?, ?, ?, ?, ?)
        """, (
            session_id, question_id or None, text, voice_meta,
            sentiment["sentiment_score"], sentiment["emotion"], follow_up["intent"],
            sentiment["confidence"], quality["quality_score"]
        ))
        response_id = cursor.lastrowid

        # Store in voice_data table
        cursor.execute("""
            INSERT INTO voice_data (response_id, session_id, transcript, confidence, duration_ms, language, highlights, assemblyai_sentiments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            response_id, session_id, text,
            transcription.get("confidence"), transcription.get("duration_ms"),
            transcription.get("language", "en"),
            json.dumps(transcription.get("highlights", [])),
            json.dumps(transcription.get("sentiments", []))
        ))

        cursor.execute("""
            INSERT INTO conversation_history (session_id, role, message, message_type, metadata)
            VALUES (?, 'user', ?, 'voice', ?)
        """, (session_id, text, voice_meta))

        conn.commit()
        conn.close()

    return {
        "transcript": text,
        "transcription": transcription,
        "sentiment": sentiment,
        "quality": quality,
        "follow_up": follow_up,
    }


# ── AI Simulated Interview ──
@router.post("/simulate")
def simulate_interview(req: SimulationRequest):
    """Run an AI-simulated interview where AI plays the respondent."""
    conn = get_db()
    questions = conn.execute(
        "SELECT * FROM questions WHERE survey_id = ? ORDER BY order_index", (req.survey_id,)
    ).fetchall()
    if not questions:
        conn.close()
        raise HTTPException(status_code=404, detail="No questions found for this survey")

    q_list = [dict(q) for q in questions]
    results = []

    for i in range(req.num_simulations):
        persona = req.persona if req.persona else None
        sim_result = AIService.simulate_interview(q_list, persona)

        # Store simulated responses
        session_id = f"sim-{str(uuid.uuid4())}"
        respondent_id = f"sim-{str(uuid.uuid4())[:8]}"
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO interview_sessions (survey_id, respondent_id, session_id, channel, status)
            VALUES (?, ?, ?, 'simulation', 'completed')
        """, (req.survey_id, respondent_id, session_id))

        for resp in sim_result.get("responses", []):
            sentiment = AIService.analyze_sentiment(resp.get("response", ""))
            cursor.execute("""
                INSERT INTO responses (session_id, response_text, response_type, sentiment_score, emotion, confidence, quality_score)
                VALUES (?, ?, 'simulation', ?, ?, ?, ?)
            """, (session_id, resp.get("response", ""), sentiment.get("sentiment_score", 0),
                  resp.get("emotion", "neutral"), resp.get("confidence", 0.7), 0.8))

        conn.commit()
        sim_result["session_id"] = session_id
        results.append(sim_result)

    conn.close()
    return {"simulations": results, "count": len(results)}
