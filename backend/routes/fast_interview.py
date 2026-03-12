"""
Fast Interview Routes — Optimized for Speed & Voice Input
- Immediate response saving with background AI processing
- Unified survey interface with mode selection
- Speech-to-text support for web form and chat modes
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from ..database import get_db
from ..models import ResponseCreate, ChatMessage, SessionCreate
from ..services.ai_service import AIService
from ..services.transcription_service import TranscriptionService
from ..services.event_bus import event_bus, Event, EventType
import uuid
import json
import os
import tempfile
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/api/fast-interview", tags=["fast-interview"])

# ============================================================================
# UNIFIED SURVEY ENTRY POINT
# ============================================================================

@router.get("/survey/{survey_id}", response_class=HTMLResponse)
def unified_survey_interface(survey_id: str):
    """Unified survey landing page with mode selection (web form, chat, audio)"""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Survey — InsightAI</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700&family=Playfair+Display:wght@500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        :root {{
            --gold: #F5A623; --gold-hover: #E09000; --gold-light: rgba(245,166,35,0.08);
            --cream: #FAF7F2; --cream-dark: #F0EBE3; --card-bg: #FFFFFF;
            --text-dark: #1A1A2E; --text-body: #374151; --text-muted: #6B7280;
            --border: #E5E0D8; --success: #22c55e; --danger: #ef4444;
            --radius-lg: 12px; --radius-xl: 16px; --shadow-lg: 0 10px 30px rgba(26,26,46,0.1);
        }}
        body {{
            font-family: 'DM Sans', system-ui, sans-serif; background: var(--cream);
            min-height: 100vh; display: flex; align-items: center; justify-content: center;
            padding: 20px; color: var(--text-dark);
        }}
        .container {{ width: 100%; max-width: 800px; }}
        .card {{
            background: var(--card-bg); border-radius: var(--radius-xl); box-shadow: var(--shadow-lg);
            overflow: hidden; animation: slideUp 0.4s ease; border: 1px solid var(--border);
        }}
        @keyframes slideUp {{ from {{ opacity: 0; transform: translateY(20px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        .card-header {{
            background: linear-gradient(135deg, var(--gold) 0%, #E09000 100%);
            padding: 32px; color: var(--text-dark); text-align: center;
        }}
        .card-header h1 {{ font-family: 'Playfair Display', serif; font-size: 2rem; font-weight: 700; margin-bottom: 8px; }}
        .card-header p {{ opacity: 0.8; font-size: 1.1rem; }}
        .card-body {{ padding: 40px; }}
        
        .mode-grid {{ 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); 
            gap: 24px; margin: 32px 0;
        }}
        .mode-card {{
            border: 2px solid var(--border); border-radius: var(--radius-lg);
            padding: 32px 24px; text-align: center; cursor: pointer; transition: all 0.3s ease;
            background: var(--card-bg); position: relative;
        }}
        .mode-card:hover {{
            border-color: var(--gold); transform: translateY(-6px); box-shadow: 0 12px 40px rgba(245,166,35,0.15);
        }}
        .mode-card.selected {{ 
            border-color: var(--gold); background: var(--gold-light); 
            box-shadow: 0 8px 32px rgba(245,166,35,0.2);
        }}
        .mode-icon {{ 
            font-size: 3rem; margin-bottom: 16px; background: var(--gold-light);
            width: 80px; height: 80px; border-radius: 50%; display: flex;
            align-items: center; justify-content: center; margin: 0 auto 16px;
            color: var(--gold); transition: all 0.3s ease;
        }}
        .mode-card:hover .mode-icon {{ background: var(--gold); color: white; }}
        .mode-card h3 {{ font-size: 1.3rem; font-weight: 600; margin-bottom: 8px; }}
        .mode-card p {{ font-size: 0.95rem; color: var(--text-muted); line-height: 1.5; }}
        .mode-features {{
            list-style: none; text-align: left; margin-top: 16px;
            font-size: 0.85rem; color: var(--text-body);
        }}
        .mode-features li {{ margin-bottom: 6px; }}
        .mode-features li:before {{ content: "✓ "; color: var(--success); font-weight: bold; }}
        
        .btn {{
            display: inline-flex; align-items: center; gap: 10px; padding: 14px 28px;
            border: none; border-radius: var(--radius-lg); font-size: 1.1rem; font-weight: 600;
            cursor: pointer; transition: all 0.2s; font-family: inherit; text-decoration: none;
        }}
        .btn-primary {{
            background: var(--gold); color: var(--text-dark); 
            box-shadow: 0 4px 16px rgba(245,166,35,0.3);
        }}
        .btn-primary:hover {{
            background: var(--gold-hover); transform: translateY(-2px);
            box-shadow: 0 6px 24px rgba(245,166,35,0.4);
        }}
        .btn-primary:disabled {{
            background: var(--border); color: var(--text-muted); cursor: not-allowed; 
            transform: none; box-shadow: none;
        }}
        .btn-block {{ width: 100%; justify-content: center; }}
        
        .info-section {{
            background: var(--gold-light); border-radius: var(--radius-lg); 
            padding: 24px; margin: 24px 0; text-align: center;
        }}
        .info-section h4 {{ color: var(--gold); margin-bottom: 8px; }}
        .info-section p {{ font-size: 0.95rem; color: var(--text-body); }}
        
        @media (max-width: 768px) {{
            .mode-grid {{ grid-template-columns: 1fr; }}
            .card-body {{ padding: 24px; }}
            .mode-card {{ padding: 24px 16px; }}
            .mode-icon {{ width: 64px; height: 64px; font-size: 2.2rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="card-header">
                <h1><i class="fas fa-sparkles"></i> Welcome to Your Survey</h1>
                <p>Choose how you'd like to share your thoughts with us</p>
            </div>
            
            <div class="card-body">
                <div class="info-section">
                    <h4><i class="fas fa-clock"></i> Takes about 5 minutes</h4>
                    <p>No right or wrong answers — just share your honest experience and thoughts.</p>
                </div>
                
                <div class="mode-grid">
                    <div class="mode-card" onclick="selectMode('webform')">
                        <div class="mode-icon"><i class="fas fa-file-text"></i></div>
                        <h3>Web Form</h3>
                        <p>Traditional form with questions and text boxes.</p>
                        <ul class="mode-features">
                            <li>Familiar interface</li>
                            <li>Voice typing available</li>
                            <li>Easy to navigate</li>
                        </ul>
                    </div>
                    
                    <div class="mode-card" onclick="selectMode('chat')">
                        <div class="mode-icon"><i class="fas fa-comments"></i></div>
                        <h3>Chat Interview</h3>
                        <p>Conversational AI that adapts to your responses.</p>
                        <ul class="mode-features">
                            <li>Natural conversation</li>
                            <li>Adaptive follow-ups</li>
                            <li>Voice input supported</li>
                        </ul>
                    </div>
                    
                    <div class="mode-card" onclick="selectMode('audio')">
                        <div class="mode-icon"><i class="fas fa-microphone"></i></div>
                        <h3>Voice Interview</h3>
                        <p>Speak your answers naturally — we'll transcribe everything.</p>
                        <ul class="mode-features">
                            <li>Hands-free experience</li>
                            <li>Natural speech</li>
                            <li>Perfect for mobile</li>
                        </ul>
                    </div>
                </div>
                
                <button class="btn btn-primary btn-block" id="start-btn" onclick="startSurvey()" disabled>
                    <i class="fas fa-play"></i> Start Survey
                </button>
            </div>
        </div>
    </div>
    
    <script>
        let selectedMode = null;
        const surveyId = '{survey_id}';
        
        function selectMode(mode) {{
            selectedMode = mode;
            document.querySelectorAll('.mode-card').forEach(card => card.classList.remove('selected'));
            event.currentTarget.classList.add('selected');
            document.getElementById('start-btn').disabled = false;
        }}
        
        function startSurvey() {{
            if (!selectedMode) return;
            
            const baseUrl = window.location.origin;
            let redirectUrl;
            
            switch(selectedMode) {{
                case 'webform':
                    redirectUrl = `${{baseUrl}}/survey-form.html?survey_id=${{surveyId}}`;
                    break;
                case 'chat':
                    redirectUrl = `${{baseUrl}}/survey-chat.html?survey_id=${{surveyId}}`;
                    break;
                case 'audio':
                    redirectUrl = `${{baseUrl}}/survey-audio.html?survey_id=${{surveyId}}`;
                    break;
            }}
            
            if (redirectUrl) {{
                window.location.href = redirectUrl;
            }}
        }}
    </script>
</body>
</html>
    """

# ============================================================================
# FAST RESPONSE ENDPOINTS
# ============================================================================

async def process_ai_analysis(response_data: dict):
    """Background task for AI processing - doesn't block user"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Full AI analysis (sentiment, themes, semantic memory, etc.)
        response_text = response_data["response_text"]
        session_id = response_data["session_id"]
        response_id = response_data["response_id"]
        
        # Generate insights asynchronously
        follow_up = AIService.generate_follow_up(response_text, response_data.get("context", {{}}))
        segments = AIService.segment_response(response_text)
        
        # Store segments
        for idx, seg in enumerate(segments):
            cursor.execute("""
                INSERT INTO response_segments (response_id, session_id, segment_text, topic, 
                    sentiment_label, sentiment_score, emotion, confidence, order_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (response_id, session_id, seg.get("segment_text", ""), seg.get("topic", ""),
                  seg.get("sentiment_label", "neutral"), seg.get("sentiment_score", 0),
                  seg.get("emotion", "neutral"), seg.get("confidence", 0), idx))
        
        # Extract semantic memory
        existing_mem = conn.execute("SELECT entity, relation, value FROM semantic_memory WHERE session_id = ?", (session_id,)).fetchall()
        existing_mem_list = [dict(m) for m in existing_mem]
        memories = AIService.extract_semantic_memory(response_text, existing_mem_list)
        for mem in memories:
            cursor.execute("""
                INSERT INTO semantic_memory (session_id, entity, relation, value, confidence, source_response_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, mem.get("entity", ""), mem.get("relation", ""),
                  mem.get("value", ""), mem.get("confidence", 0.5), response_id))
        
        conn.commit()
        conn.close()
        
        # Publish event for further processing
        event_bus.publish(Event(
            EventType.AI_ANALYSIS_COMPLETE,
            response_data,
            source="background_ai_processor"
        ))
        
    except Exception as e:
        print(f"[Background AI processing error] {{e}}")

@router.post("/respond-fast")
async def submit_response_fast(response: ResponseCreate, background_tasks: BackgroundTasks):
    """Fast response submission - saves immediately, processes AI in background"""
    conn = get_db()
    
    # Validate session
    session = conn.execute("SELECT * FROM interview_sessions WHERE session_id = ?", (response.session_id,)).fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        cursor = conn.cursor()
        
        # Quick local analysis for immediate feedback
        words = response.response_text.split()
        wc = len(words)
        quality_score = min(1.0, wc / 30) if wc > 2 else 0.2
        
        # Store response immediately
        cursor.execute("""
            INSERT INTO responses (session_id, question_id, response_text, response_type, 
                emoji_data, voice_metadata, quality_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            response.session_id, response.question_id, response.response_text, 
            response.response_type, response.emoji_data, response.voice_metadata, quality_score
        ))
        
        response_id = cursor.lastrowid
        
        # Store in conversation history  
        cursor.execute("""
            INSERT INTO conversation_history (session_id, role, message, message_type)
            VALUES (?, 'user', ?, ?)
        """, (response.session_id, response.response_text, response.response_type))
        
        # Get next question
        next_question = None
        if response.question_id:
            current_q = conn.execute("SELECT * FROM questions WHERE id = ?", (response.question_id,)).fetchone()
            if current_q:
                next_question = conn.execute(
                    "SELECT * FROM questions WHERE survey_id = ? AND order_index > ? ORDER BY order_index LIMIT 1",
                    (dict(session)["survey_id"], current_q["order_index"])
                ).fetchone()
        
        # Update completion percentage
        responses_count = conn.execute(
            "SELECT COUNT(*) as c FROM responses WHERE session_id = ?", (response.session_id,)
        ).fetchone()["c"]
        total_questions = conn.execute(
            "SELECT COUNT(*) as c FROM questions WHERE survey_id = ?", (dict(session)["survey_id"],)
        ).fetchone()["c"]
        
        completion = round((responses_count / max(total_questions, 1)) * 100, 1)
        conn.execute(
            "UPDATE interview_sessions SET completion_percentage = ? WHERE session_id = ?",
            (completion, response.session_id)
        )
        
        # Determine AI message
        if next_question:
            ai_message = dict(next_question)["question_text"] 
        elif completion >= 90:
            ai_message = "Thank you so much for sharing! Is there anything else you'd like to tell us?"
            conn.execute("UPDATE interview_sessions SET status = 'completing' WHERE session_id = ?", (response.session_id,))
        else:
            ai_message = "Thank you for that response. Let's continue..."
            
        # Store AI message
        cursor.execute("""
            INSERT INTO conversation_history (session_id, role, message, message_type)
            VALUES (?, 'ai', ?, 'text')
        """, (response.session_id, ai_message))
        
        # Commit immediately for fast response
        conn.commit()
        
        # Schedule background AI processing
        background_tasks.add_task(process_ai_analysis, {{
            "response_id": response_id,
            "session_id": response.session_id,
            "survey_id": dict(session)["survey_id"],
            "response_text": response.response_text,
            "question_id": response.question_id,
            "context": response.interview_context
        }})
        
        return {{
            "success": True,
            "next_question": dict(next_question) if next_question else None,
            "ai_message": ai_message,
            "completion_percentage": completion,
            "is_complete": completion >= 100,
            "quality_score": quality_score,
            "processing_status": "saved_immediately"
        }}
        
    finally:
        conn.close()

# ============================================================================
# VOICE INPUT ENDPOINTS
# ============================================================================

@router.post("/transcribe-audio")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """Convert speech to text for voice input"""
    if not audio_file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Invalid audio file")
    
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            content = await audio_file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Transcribe using AI service
        transcription = await TranscriptionService.transcribe_audio(temp_path)
        
        # Clean up temp file
        os.unlink(temp_path)
        
        return {{
            "success": True,
            "text": transcription.get("text", ""),
            "confidence": transcription.get("confidence", 0),
            "language": transcription.get("language", "en")
        }}
        
    except Exception as e:
        # Clean up temp file if it exists
        if 'temp_path' in locals():
            try:
                os.unlink(temp_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Transcription failed: {{str(e)}}")

@router.post("/speech-to-text")
async def speech_to_text(session_id: str, audio_file: UploadFile = File(...)):
    """Process voice input with session context"""
    transcription_result = await transcribe_audio(audio_file)
    
    if not transcription_result["success"]:
        raise HTTPException(status_code=500, detail="Failed to transcribe audio")
    
    # Store voice metadata in session
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO conversation_history (session_id, role, message, message_type, metadata)
        VALUES (?, 'user', ?, 'voice', ?)
    """, (session_id, transcription_result["text"], "voice", 
          json.dumps({{"confidence": transcription_result["confidence"], "language": transcription_result["language"]}})))
    conn.commit()
    conn.close()
    
    return transcription_result