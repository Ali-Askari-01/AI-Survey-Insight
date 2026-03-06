"""
Pydantic models for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── User & Authentication Models ──
class UserRegister(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ── Research Goal Models ──
class ResearchGoalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    research_type: str = "discovery"
    problem_space: Optional[str] = None
    target_outcome: Optional[str] = None
    target_audience: Optional[str] = None
    success_criteria: Optional[str] = None
    estimated_duration: int = 5


class ResearchGoalResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    research_type: str
    problem_space: Optional[str]
    target_outcome: Optional[str]
    target_audience: Optional[str]
    success_criteria: Optional[str]
    estimated_duration: int
    quality_score: float
    status: str
    created_at: str


# ── Survey Models ──
class SurveyCreate(BaseModel):
    research_goal_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    channel_type: str = "web"
    estimated_duration: int = 5
    interview_style: str = "balanced"


class QuestionCreate(BaseModel):
    survey_id: int
    question_text: str
    question_type: str = "open_ended"
    options: Optional[str] = None
    order_index: int = 0
    is_required: bool = True
    conditional_logic: Optional[str] = None
    follow_up_seeds: Optional[str] = None
    tone: str = "neutral"
    depth_level: int = 1
    audience_tag: str = "general"


class QuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    options: Optional[str] = None
    order_index: Optional[int] = None
    is_required: Optional[bool] = None
    conditional_logic: Optional[str] = None
    tone: Optional[str] = None


# ── Interview Session Models ──
class SessionCreate(BaseModel):
    survey_id: int
    channel: str = "web"
    device_type: Optional[str] = None
    language: str = "en"


class ResponseCreate(BaseModel):
    session_id: str
    question_id: Optional[int] = None
    response_text: str
    response_type: str = "text"
    emoji_data: Optional[str] = None
    voice_metadata: Optional[str] = None
    interview_context: Optional[dict] = None


class ChatMessage(BaseModel):
    session_id: str
    message: str
    message_type: str = "text"
    history: Optional[List[dict]] = None
    interview_context: Optional[dict] = None


# ── Insight Models ──
class InsightFilter(BaseModel):
    theme_id: Optional[int] = None
    sentiment: Optional[str] = None
    feature_area: Optional[str] = None
    min_confidence: Optional[float] = None
    user_segment: Optional[str] = None


# ── Report Models ──
class ReportCreate(BaseModel):
    survey_id: int
    title: str
    summary_tone: str = "neutral"
    summary_length: str = "medium"


# ── Notification Model ──
class NotificationCreate(BaseModel):
    survey_id: Optional[int] = None
    type: str = "info"
    title: str
    message: Optional[str] = None
    severity: str = "low"


# ── AI Request Models ──
class AIGoalRequest(BaseModel):
    user_input: str


class AIQuestionGenerateRequest(BaseModel):
    research_goal_id: int
    count: int = 5


# ── Simulation Model ──
class SimulationRequest(BaseModel):
    survey_id: int
    persona: Optional[str] = None
    num_simulations: int = 1


# ── Survey Publication Models ──
class PublishSurveyRequest(BaseModel):
    survey_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    web_form_enabled: bool = True
    chat_enabled: bool = True
    audio_enabled: bool = True
    max_responses: int = 0
    require_email: bool = True
    consent_form_text: Optional[str] = None


class RespondentJoinRequest(BaseModel):
    email: str
    name: Optional[str] = None
    share_code: str
    channel: str = "web"


# ── Survey Analysis Chatbot Models ──
class ChatbotQuery(BaseModel):
    survey_id: int
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
