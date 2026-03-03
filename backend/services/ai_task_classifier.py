"""
AI Task Classification Layer — Component 2
═══════════════════════════════════════════════════════
Architecture: Every incoming data must first answer: "What AI job is required?"

This module classifies incoming events/requests into the correct AI task type
and routes them to the appropriate processing pipeline.

Incoming Event  →  Task Classifier  →  Route to Correct AI Pipeline

Task Types:
  - question_generation     → Pipeline A (Survey Intelligence)
  - follow_up_generation    → Pipeline A (Survey Intelligence)
  - response_understanding  → Pipeline B (Response Understanding)
  - sentiment_analysis      → Pipeline B (Response Understanding)
  - theme_extraction        → Pipeline C (Insight Formation)
  - insight_clustering      → Pipeline C (Insight Formation)
  - recommendation_gen      → Pipeline D (Recommendation Engine)
  - executive_summary       → Pipeline E (Executive Intelligence)
"""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


# ═══════════════════════════════════════════════════
# TASK TYPE TAXONOMY
# ═══════════════════════════════════════════════════
class AITaskType(str, Enum):
    """All classifiable AI task types in the system."""
    # Pipeline A — Survey Intelligence
    QUESTION_GENERATION = "question_generation"
    DEEP_QUESTION_GENERATION = "deep_question_generation"
    FOLLOW_UP_GENERATION = "follow_up_generation"
    INTAKE_CLARIFICATION = "intake_clarification"

    # Pipeline B — Response Understanding
    RESPONSE_UNDERSTANDING = "response_understanding"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    RESPONSE_SEGMENTATION = "response_segmentation"
    QUALITY_SCORING = "quality_scoring"

    # Pipeline C — Insight Formation
    THEME_EXTRACTION = "theme_extraction"
    INSIGHT_CLUSTERING = "insight_clustering"
    MEMORY_EXTRACTION = "memory_extraction"

    # Pipeline D — Recommendation Engine
    RECOMMENDATION_GENERATION = "recommendation_generation"
    ACTION_PLAN_GENERATION = "action_plan_generation"

    # Pipeline E — Executive Intelligence
    EXECUTIVE_SUMMARY = "executive_summary"
    TRANSCRIPT_REPORT = "transcript_report"
    TREND_ANALYSIS = "trend_analysis"

    # Chat / Interactive
    CHAT_RESPONSE = "chat_response"
    SIMULATED_INTERVIEW = "simulated_interview"


# ═══════════════════════════════════════════════════
# PIPELINE MAPPING
# ═══════════════════════════════════════════════════
class PipelineType(str, Enum):
    """The 5 core processing pipelines."""
    SURVEY_INTELLIGENCE = "pipeline_a_survey_intelligence"
    RESPONSE_UNDERSTANDING = "pipeline_b_response_understanding"
    INSIGHT_FORMATION = "pipeline_c_insight_formation"
    RECOMMENDATION_ENGINE = "pipeline_d_recommendation_engine"
    EXECUTIVE_INTELLIGENCE = "pipeline_e_executive_intelligence"
    INTERACTIVE = "pipeline_interactive"


# Task → Pipeline routing table
TASK_PIPELINE_MAP: Dict[AITaskType, PipelineType] = {
    # Pipeline A
    AITaskType.QUESTION_GENERATION: PipelineType.SURVEY_INTELLIGENCE,
    AITaskType.DEEP_QUESTION_GENERATION: PipelineType.SURVEY_INTELLIGENCE,
    AITaskType.FOLLOW_UP_GENERATION: PipelineType.SURVEY_INTELLIGENCE,
    AITaskType.INTAKE_CLARIFICATION: PipelineType.SURVEY_INTELLIGENCE,
    # Pipeline B
    AITaskType.RESPONSE_UNDERSTANDING: PipelineType.RESPONSE_UNDERSTANDING,
    AITaskType.SENTIMENT_ANALYSIS: PipelineType.RESPONSE_UNDERSTANDING,
    AITaskType.RESPONSE_SEGMENTATION: PipelineType.RESPONSE_UNDERSTANDING,
    AITaskType.QUALITY_SCORING: PipelineType.RESPONSE_UNDERSTANDING,
    # Pipeline C
    AITaskType.THEME_EXTRACTION: PipelineType.INSIGHT_FORMATION,
    AITaskType.INSIGHT_CLUSTERING: PipelineType.INSIGHT_FORMATION,
    AITaskType.MEMORY_EXTRACTION: PipelineType.INSIGHT_FORMATION,
    # Pipeline D
    AITaskType.RECOMMENDATION_GENERATION: PipelineType.RECOMMENDATION_ENGINE,
    AITaskType.ACTION_PLAN_GENERATION: PipelineType.RECOMMENDATION_ENGINE,
    # Pipeline E
    AITaskType.EXECUTIVE_SUMMARY: PipelineType.EXECUTIVE_INTELLIGENCE,
    AITaskType.TRANSCRIPT_REPORT: PipelineType.EXECUTIVE_INTELLIGENCE,
    AITaskType.TREND_ANALYSIS: PipelineType.EXECUTIVE_INTELLIGENCE,
    # Interactive
    AITaskType.CHAT_RESPONSE: PipelineType.INTERACTIVE,
    AITaskType.SIMULATED_INTERVIEW: PipelineType.INTERACTIVE,
}


# ═══════════════════════════════════════════════════
# EVENT → TASK CLASSIFICATION RULES
# ═══════════════════════════════════════════════════
# Maps event_type strings to the AI task they trigger
EVENT_TASK_MAP: Dict[str, AITaskType] = {
    "survey.created": AITaskType.QUESTION_GENERATION,
    "questions.generated": AITaskType.DEEP_QUESTION_GENERATION,
    "response.submitted": AITaskType.RESPONSE_UNDERSTANDING,
    "chat.message_received": AITaskType.CHAT_RESPONSE,
    "interview.completed": AITaskType.EXECUTIVE_SUMMARY,
    "insight.discovered": AITaskType.RECOMMENDATION_GENERATION,
    "theme.updated": AITaskType.INSIGHT_CLUSTERING,
    "sentiment.shift_detected": AITaskType.TREND_ANALYSIS,
    "metric.updated": AITaskType.TREND_ANALYSIS,
}


# ═══════════════════════════════════════════════════
# CLASSIFICATION RESULT
# ═══════════════════════════════════════════════════
class ClassificationResult:
    """Result of classifying an incoming request/event."""

    def __init__(self, task_type: AITaskType, pipeline: PipelineType,
                 priority: str = "normal", batch_eligible: bool = False,
                 context_requirements: list = None):
        self.task_type = task_type
        self.pipeline = pipeline
        self.priority = priority  # "critical", "high", "normal", "low"
        self.batch_eligible = batch_eligible
        self.context_requirements = context_requirements or []
        self.classified_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type.value,
            "pipeline": self.pipeline.value,
            "priority": self.priority,
            "batch_eligible": self.batch_eligible,
            "context_requirements": self.context_requirements,
            "classified_at": self.classified_at,
        }


# ═══════════════════════════════════════════════════
# TASK PRIORITY RULES
# ═══════════════════════════════════════════════════
TASK_PRIORITY: Dict[AITaskType, str] = {
    AITaskType.CHAT_RESPONSE: "critical",          # User is waiting
    AITaskType.FOLLOW_UP_GENERATION: "critical",    # User is waiting
    AITaskType.INTAKE_CLARIFICATION: "critical",    # User is waiting
    AITaskType.SENTIMENT_ANALYSIS: "high",          # Needed for real-time dashboard
    AITaskType.RESPONSE_UNDERSTANDING: "high",      # Part of main data flow
    AITaskType.QUALITY_SCORING: "high",             # Affects follow-up decisions
    AITaskType.RESPONSE_SEGMENTATION: "normal",     # Can run in background
    AITaskType.MEMORY_EXTRACTION: "normal",         # Can run in background
    AITaskType.QUESTION_GENERATION: "normal",       # One-time during creation
    AITaskType.DEEP_QUESTION_GENERATION: "normal",
    AITaskType.THEME_EXTRACTION: "normal",          # Batch-eligible
    AITaskType.INSIGHT_CLUSTERING: "low",           # Can wait for threshold
    AITaskType.RECOMMENDATION_GENERATION: "low",    # Depends on insights
    AITaskType.ACTION_PLAN_GENERATION: "low",
    AITaskType.EXECUTIVE_SUMMARY: "low",            # On-demand
    AITaskType.TRANSCRIPT_REPORT: "low",
    AITaskType.TREND_ANALYSIS: "low",
    AITaskType.SIMULATED_INTERVIEW: "normal",
}

# Tasks eligible for batch processing (Section 8)
BATCH_ELIGIBLE_TASKS = {
    AITaskType.THEME_EXTRACTION,
    AITaskType.INSIGHT_CLUSTERING,
    AITaskType.TREND_ANALYSIS,
    AITaskType.RECOMMENDATION_GENERATION,
}

# Context requirements per task
TASK_CONTEXT_REQUIREMENTS: Dict[AITaskType, list] = {
    AITaskType.QUESTION_GENERATION: ["research_goal", "audience", "objectives"],
    AITaskType.DEEP_QUESTION_GENERATION: ["research_goal", "base_questions"],
    AITaskType.FOLLOW_UP_GENERATION: ["research_goal", "response_text", "conversation_history"],
    AITaskType.INTAKE_CLARIFICATION: ["user_input", "conversation_history"],
    AITaskType.RESPONSE_UNDERSTANDING: ["response_text", "survey_goal", "conversation_history"],
    AITaskType.SENTIMENT_ANALYSIS: ["response_text", "survey_goal"],
    AITaskType.RESPONSE_SEGMENTATION: ["response_text"],
    AITaskType.QUALITY_SCORING: ["response_text"],
    AITaskType.THEME_EXTRACTION: ["responses_batch", "existing_themes"],
    AITaskType.INSIGHT_CLUSTERING: ["responses_batch", "existing_insights", "themes"],
    AITaskType.MEMORY_EXTRACTION: ["response_text", "existing_memory"],
    AITaskType.RECOMMENDATION_GENERATION: ["insights", "survey_goal", "business_context"],
    AITaskType.ACTION_PLAN_GENERATION: ["recommendations", "priorities"],
    AITaskType.EXECUTIVE_SUMMARY: ["insights", "themes", "sentiment_data", "survey_goal"],
    AITaskType.TRANSCRIPT_REPORT: ["conversation_history", "survey_goal"],
    AITaskType.TREND_ANALYSIS: ["sentiment_timeline", "theme_timeline"],
    AITaskType.CHAT_RESPONSE: ["message", "conversation_history", "memory", "survey_context"],
    AITaskType.SIMULATED_INTERVIEW: ["questions", "persona"],
}


# ═══════════════════════════════════════════════════
# AI TASK CLASSIFIER (Main Class)
# ═══════════════════════════════════════════════════
class AITaskClassifier:
    """
    Classifies incoming requests/events into the correct AI task and pipeline.

    Architecture Flow:
        Incoming Event → Task Classifier → ClassificationResult → Pipeline Router
    """

    _classification_count = 0
    _classification_errors = 0

    @classmethod
    def classify_event(cls, event_type: str, payload: dict = None) -> Optional[ClassificationResult]:
        """
        Classify a system event into an AI task.

        Args:
            event_type: The event type string (e.g. "response.submitted")
            payload: Event payload with data for classification hints

        Returns:
            ClassificationResult or None if no AI task needed
        """
        cls._classification_count += 1

        task_type = EVENT_TASK_MAP.get(event_type)
        if not task_type:
            return None

        # Refine classification based on payload context
        if payload:
            task_type = cls._refine_classification(task_type, event_type, payload)

        pipeline = TASK_PIPELINE_MAP.get(task_type)
        if not pipeline:
            cls._classification_errors += 1
            return None

        priority = TASK_PRIORITY.get(task_type, "normal")
        batch_eligible = task_type in BATCH_ELIGIBLE_TASKS
        context_reqs = TASK_CONTEXT_REQUIREMENTS.get(task_type, [])

        return ClassificationResult(
            task_type=task_type,
            pipeline=pipeline,
            priority=priority,
            batch_eligible=batch_eligible,
            context_requirements=context_reqs
        )

    @classmethod
    def classify_request(cls, task_type_str: str, payload: dict = None) -> Optional[ClassificationResult]:
        """
        Classify a direct API request into an AI task.

        Args:
            task_type_str: Explicit task type string (e.g. "sentiment_analysis")
            payload: Request data

        Returns:
            ClassificationResult or None if invalid task type
        """
        cls._classification_count += 1

        try:
            task_type = AITaskType(task_type_str)
        except ValueError:
            cls._classification_errors += 1
            return None

        pipeline = TASK_PIPELINE_MAP.get(task_type)
        if not pipeline:
            cls._classification_errors += 1
            return None

        priority = TASK_PRIORITY.get(task_type, "normal")
        batch_eligible = task_type in BATCH_ELIGIBLE_TASKS
        context_reqs = TASK_CONTEXT_REQUIREMENTS.get(task_type, [])

        return ClassificationResult(
            task_type=task_type,
            pipeline=pipeline,
            priority=priority,
            batch_eligible=batch_eligible,
            context_requirements=context_reqs
        )

    @classmethod
    def _refine_classification(cls, base_task: AITaskType, event_type: str,
                               payload: dict) -> AITaskType:
        """
        Refine the task classification based on payload signals.
        Example: response.submitted with short text → quality_scoring first,
                 response.submitted with long text → full understanding pipeline.
        """
        if event_type == "response.submitted":
            response_text = payload.get("response_text", "")
            word_count = len(response_text.split())

            # Very short responses need quality scoring, not full analysis
            if word_count < 5:
                return AITaskType.QUALITY_SCORING

            # Multi-topic responses need segmentation first
            if word_count > 50:
                return AITaskType.RESPONSE_SEGMENTATION

        if event_type == "interview.completed":
            # If we have chat history, generate transcript report
            if payload.get("conversation_history"):
                return AITaskType.TRANSCRIPT_REPORT

        if event_type == "theme.updated":
            # After theme update, check if we have enough for recommendations
            theme_count = payload.get("themes_count", 0)
            if theme_count >= 3:
                return AITaskType.RECOMMENDATION_GENERATION

        return base_task

    @classmethod
    def get_pipeline_for_task(cls, task_type: AITaskType) -> Optional[PipelineType]:
        """Get the pipeline that handles a specific task type."""
        return TASK_PIPELINE_MAP.get(task_type)

    @classmethod
    def validate_context(cls, task_type: AITaskType, provided_context: dict) -> dict:
        """
        Validate that required context is available for a task.

        Returns:
            {"valid": bool, "missing": [...], "provided": [...]}
        """
        required = TASK_CONTEXT_REQUIREMENTS.get(task_type, [])
        provided = [k for k in required if k in provided_context and provided_context[k]]
        missing = [k for k in required if k not in provided_context or not provided_context[k]]

        return {
            "valid": len(missing) == 0,
            "missing": missing,
            "provided": provided,
            "task_type": task_type.value,
        }

    @classmethod
    def stats(cls) -> dict:
        """Return classification statistics."""
        return {
            "total_classifications": cls._classification_count,
            "classification_errors": cls._classification_errors,
            "registered_task_types": len(AITaskType),
            "registered_pipelines": len(PipelineType),
            "batch_eligible_tasks": [t.value for t in BATCH_ELIGIBLE_TASKS],
        }
