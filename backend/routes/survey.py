"""
Survey Designer API Routes — Feature 1
Architecture: Routes are THIN — delegate to Service Layer.
"""
from fastapi import APIRouter, HTTPException, Depends
from ..database import get_db
from ..models import (
    ResearchGoalCreate, SurveyCreate, QuestionCreate, QuestionUpdate,
    AIGoalRequest, AIQuestionGenerateRequest
)
from ..services.survey_service import SurveyService
from ..services.ai_service import AIService
from ..auth import get_current_user
import json
import uuid

router = APIRouter(prefix="/api/surveys", tags=["surveys"])


# ═══════════════════════════════════════════════════
# SURVEY TEMPLATES — Pre-built starting points
# ═══════════════════════════════════════════════════
SURVEY_TEMPLATES = [
    {
        "id": "customer-satisfaction",
        "title": "Customer Satisfaction Survey",
        "icon": "fa-face-smile",
        "color": "#10b981",
        "category": "Customer",
        "description": "Measure overall customer satisfaction, identify pain points, and discover improvement opportunities.",
        "goal_text": "We want to understand how satisfied our customers are with our product/service. We need to identify what they love, what frustrates them, and what improvements would make the biggest impact on their experience.",
        "research_type": "satisfaction",
        "suggested_questions": 7,
    },
    {
        "id": "product-feedback",
        "title": "Product Feedback Survey",
        "icon": "fa-box-open",
        "color": "#6366f1",
        "category": "Product",
        "description": "Collect detailed product feedback on features, usability, and future direction.",
        "goal_text": "We need in-depth feedback about our product from active users. We want to understand which features they use most, what's confusing or difficult, what features are missing, and how they would prioritize improvements.",
        "research_type": "discovery",
        "suggested_questions": 8,
    },
    {
        "id": "employee-engagement",
        "title": "Employee Engagement Survey",
        "icon": "fa-users-gear",
        "color": "#f59e0b",
        "category": "HR",
        "description": "Gauge employee morale, identify workplace concerns, and improve company culture.",
        "goal_text": "We want to measure employee engagement and understand what drives satisfaction, what causes frustration, how employees feel about management and company culture, and what changes would make them more productive and fulfilled.",
        "research_type": "evaluation",
        "suggested_questions": 8,
    },
    {
        "id": "user-onboarding",
        "title": "User Onboarding Experience",
        "icon": "fa-rocket",
        "color": "#ec4899",
        "category": "Product",
        "description": "Evaluate the onboarding flow, first impressions, and early user experience.",
        "goal_text": "We need to understand how new users experience our onboarding process. What was their first impression? Where did they get stuck? How long did it take to reach their first 'aha moment'? What would make the getting-started experience smoother?",
        "research_type": "discovery",
        "suggested_questions": 7,
    },
    {
        "id": "market-research",
        "title": "Market Research Survey",
        "icon": "fa-chart-pie",
        "color": "#8b5cf6",
        "category": "Strategy",
        "description": "Explore market needs, competitive landscape, and customer buying behavior.",
        "goal_text": "We need to understand our target market better. What problems are potential customers trying to solve? What solutions do they currently use? What factors influence their purchasing decisions? How do they perceive our brand vs competitors?",
        "research_type": "discovery",
        "suggested_questions": 8,
    },
    {
        "id": "event-feedback",
        "title": "Event / Workshop Feedback",
        "icon": "fa-calendar-check",
        "color": "#14b8a6",
        "category": "Events",
        "description": "Gather post-event feedback on content, speakers, logistics, and overall experience.",
        "goal_text": "We want detailed feedback from event attendees. How did they rate the overall experience? What sessions were most valuable? Was the event well-organized? What topics should we cover next time? Would they attend again or recommend it?",
        "research_type": "evaluation",
        "suggested_questions": 7,
    },
]


@router.get("/templates")
def get_survey_templates(current_user: dict = Depends(get_current_user)):
    """Return pre-built survey templates."""
    return SURVEY_TEMPLATES


# ── Research Goals ──
@router.post("/goals")
def create_research_goal(goal: ResearchGoalCreate, current_user: dict = Depends(get_current_user)):
    return SurveyService.create_goal(
        title=goal.title, description=goal.description, research_type=goal.research_type,
        problem_space=goal.problem_space, target_outcome=goal.target_outcome,
        target_audience=goal.target_audience, success_criteria=goal.success_criteria,
        estimated_duration=goal.estimated_duration
    )


@router.post("/goals/ai-parse")
def ai_parse_goal(req: AIGoalRequest, current_user: dict = Depends(get_current_user)):
    """AI parses natural language into structured research goal."""
    return SurveyService.ai_parse_goal(req.user_input)


@router.get("/goals")
def list_research_goals(current_user: dict = Depends(get_current_user)):
    return SurveyService.list_goals()


@router.get("/goals/{goal_id}")
def get_research_goal(goal_id: int):
    goal = SurveyService.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


# ── Surveys ──
@router.post("/")
def create_survey(survey: SurveyCreate, current_user: dict = Depends(get_current_user)):
    return SurveyService.create_survey(
        research_goal_id=survey.research_goal_id, title=survey.title,
        description=survey.description, channel_type=survey.channel_type,
        estimated_duration=survey.estimated_duration,
        interview_style=survey.interview_style
    )


@router.get("/")
def list_surveys(current_user: dict = Depends(get_current_user)):
    return SurveyService.list_surveys()


@router.get("/{survey_id}")
def get_survey(survey_id: int):
    survey = SurveyService.get_survey(survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    return survey


# ── Questions ──
@router.post("/questions")
def create_question(question: QuestionCreate, current_user: dict = Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO questions (survey_id, question_text, question_type, options, order_index, is_required, conditional_logic, follow_up_seeds, tone, depth_level, audience_tag)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (question.survey_id, question.question_text, question.question_type, question.options,
          question.order_index, 1 if question.is_required else 0, question.conditional_logic,
          question.follow_up_seeds, question.tone, question.depth_level, question.audience_tag))
    conn.commit()
    q_id = cursor.lastrowid
    conn.close()
    return {"id": q_id, "message": "Question created"}


@router.put("/questions/{question_id}")
def update_question(question_id: int, update: QuestionUpdate, current_user: dict = Depends(get_current_user)):
    conn = get_db()
    q = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    if not q:
        conn.close()
        raise HTTPException(status_code=404, detail="Question not found")

    updates = {}
    if update.question_text is not None:
        updates["question_text"] = update.question_text
    if update.question_type is not None:
        updates["question_type"] = update.question_type
    if update.options is not None:
        updates["options"] = update.options
    if update.order_index is not None:
        updates["order_index"] = update.order_index
    if update.is_required is not None:
        updates["is_required"] = 1 if update.is_required else 0
    if update.conditional_logic is not None:
        updates["conditional_logic"] = update.conditional_logic
    if update.tone is not None:
        updates["tone"] = update.tone

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [question_id]
        conn.execute(f"UPDATE questions SET {set_clause} WHERE id = ?", values)
        conn.commit()
    conn.close()
    return {"message": "Question updated"}


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_db()
    conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    conn.commit()
    conn.close()
    return {"message": "Question deleted"}


@router.post("/questions/reorder")
def reorder_questions(data: dict, current_user: dict = Depends(get_current_user)):
    """Reorder questions by providing list of {id, order_index}."""
    conn = get_db()
    for item in data.get("orders", []):
        conn.execute("UPDATE questions SET order_index = ? WHERE id = ?", (item["order_index"], item["id"]))
    conn.commit()
    conn.close()
    return {"message": "Questions reordered"}


@router.post("/questions/ai-generate")
def ai_generate_questions(req: AIQuestionGenerateRequest, current_user: dict = Depends(get_current_user)):
    """AI generates contextual questions for a research goal."""
    result = SurveyService.ai_generate_questions(req.research_goal_id, req.count)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/questions/ai-generate-deep")
def ai_generate_deep_questions(data: dict, current_user: dict = Depends(get_current_user)):
    """AI generates in-depth questions with follow-ups and analysis."""
    goal_text = data.get("goal_text", "")
    research_type = data.get("research_type", "discovery")
    count = data.get("count", 8)
    if not goal_text:
        raise HTTPException(status_code=400, detail="goal_text is required")
    return SurveyService.ai_generate_deep_questions(goal_text, research_type, count)


@router.post("/intake/clarify")
def intake_clarify(data: dict, current_user: dict = Depends(get_current_user)):
    """Multi-step AI intake: AI asks clarifying questions before generating survey."""
    user_input = data.get("message", "")
    conversation = data.get("conversation", [])
    if not user_input:
        raise HTTPException(status_code=400, detail="message is required")
    return SurveyService.ai_intake_clarify(user_input, conversation)


@router.post("/questions/ai-generate-audience-targeted")
def ai_generate_audience_targeted(data: dict, current_user: dict = Depends(get_current_user)):
    """AI generates audience-specific questions for each target audience + generic survey."""
    goal_text = data.get("goal_text", "")
    target_audiences = data.get("target_audiences", [])
    research_type = data.get("research_type", "discovery")
    count_per_audience = data.get("count_per_audience", 6)
    if not goal_text:
        raise HTTPException(status_code=400, detail="goal_text is required")
    if not target_audiences or not isinstance(target_audiences, list):
        raise HTTPException(status_code=400, detail="target_audiences must be a non-empty list")
    return SurveyService.ai_generate_audience_targeted(
        goal_text, target_audiences, research_type, count_per_audience
    )


# ── Conversation Flow ──
@router.get("/{survey_id}/flow")
def get_conversation_flow(survey_id: int):
    conn = get_db()
    nodes = conn.execute("SELECT * FROM conversation_flow WHERE survey_id = ? ORDER BY depth_level", (survey_id,)).fetchall()
    conn.close()
    return [dict(n) for n in nodes]


@router.post("/{survey_id}/flow")
def create_flow_node(survey_id: int, data: dict):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO conversation_flow (survey_id, node_id, topic, parent_node_id, question_id, condition_type, condition_value, depth_level, priority_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        survey_id, data.get("node_id", str(uuid.uuid4())[:8]),
        data.get("topic"), data.get("parent_node_id"), data.get("question_id"),
        data.get("condition_type"), data.get("condition_value"),
        data.get("depth_level", 1), data.get("priority_score", 0)
    ))
    conn.commit()
    conn.close()
    return {"message": "Flow node created"}


@router.post("/generate-consent")
def generate_consent_form(data: dict, current_user: dict = Depends(get_current_user)):
    """Generate an AI consent form for the survey."""
    title = data.get("title", "Research Survey")
    goal = data.get("goal", "")
    consent_form = AIService.generate_consent_form(title, goal)
    return {"consent_form": consent_form}


@router.delete("/{survey_id}")
def delete_survey(survey_id: int, current_user: dict = Depends(get_current_user)):
    """Permanently delete a survey and ALL related data (questions, sessions, responses, etc.)."""
    conn = get_db()
    try:
        # Verify survey exists
        survey = conn.execute("SELECT id, title FROM surveys WHERE id = ?", (survey_id,)).fetchone()
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")

        # Enable foreign keys for cascade
        conn.execute("PRAGMA foreign_keys = ON")

        # Get all session_ids for this survey (needed for child table cleanup)
        session_rows = conn.execute(
            "SELECT session_id FROM interview_sessions WHERE survey_id = ?", (survey_id,)
        ).fetchall()
        session_ids = [r["session_id"] for r in session_rows]

        # Delete in dependency order (children first)
        if session_ids:
            placeholders = ",".join("?" for _ in session_ids)
            conn.execute(f"DELETE FROM semantic_memory WHERE session_id IN ({placeholders})", session_ids)
            conn.execute(f"DELETE FROM response_segments WHERE session_id IN ({placeholders})", session_ids)
            conn.execute(f"DELETE FROM voice_data WHERE session_id IN ({placeholders})", session_ids)
            conn.execute(f"DELETE FROM conversation_history WHERE session_id IN ({placeholders})", session_ids)
            conn.execute(f"DELETE FROM full_transcripts WHERE session_id IN ({placeholders})", session_ids)

            # Delete responses (need response_ids for sentiment_records)
            resp_rows = conn.execute(
                f"SELECT id FROM responses WHERE session_id IN ({placeholders})", session_ids
            ).fetchall()
            if resp_rows:
                resp_ids = [r["id"] for r in resp_rows]
                rp = ",".join("?" for _ in resp_ids)
                conn.execute(f"DELETE FROM sentiment_records WHERE response_id IN ({rp})", resp_ids)
            conn.execute(f"DELETE FROM responses WHERE session_id IN ({placeholders})", session_ids)

        # Delete survey-level data
        conn.execute("DELETE FROM survey_respondents WHERE survey_id = ?", (survey_id,))
        conn.execute("DELETE FROM interview_sessions WHERE survey_id = ?", (survey_id,))
        conn.execute("DELETE FROM chatbot_conversations WHERE survey_id = ?", (survey_id,))
        conn.execute("DELETE FROM survey_publications WHERE survey_id = ?", (survey_id,))
        conn.execute("DELETE FROM recommendations WHERE survey_id = ?", (survey_id,))
        conn.execute("DELETE FROM insights WHERE survey_id = ?", (survey_id,))
        conn.execute("DELETE FROM themes WHERE survey_id = ?", (survey_id,))
        conn.execute("DELETE FROM sentiment_records WHERE survey_id = ?", (survey_id,))
        conn.execute("DELETE FROM reports WHERE survey_id = ?", (survey_id,))
        conn.execute("DELETE FROM notifications WHERE survey_id = ?", (survey_id,))
        conn.execute("DELETE FROM engagement_metrics WHERE survey_id = ?", (survey_id,))
        conn.execute("DELETE FROM conversation_flow WHERE survey_id = ?", (survey_id,))
        conn.execute("DELETE FROM questions WHERE survey_id = ?", (survey_id,))

        # Finally delete the survey itself
        conn.execute("DELETE FROM surveys WHERE id = ?", (survey_id,))
        conn.commit()

        return {"message": f"Survey '{dict(survey)['title']}' and all related data permanently deleted"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete survey: {str(e)}")
    finally:
        conn.close()
