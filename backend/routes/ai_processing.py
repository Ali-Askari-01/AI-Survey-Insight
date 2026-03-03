"""
AI Processing Architecture — API Routes
═══════════════════════════════════════════════════════
Exposes the AI Processing Architecture through REST endpoints.

Includes:
  - Pipeline execution endpoints
  - Human-in-the-Loop (HITL) correction endpoints
  - Intelligence Loop control & stats
  - Task classification info
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/api/ai-processing", tags=["AI Processing Architecture"])


# ═══════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════
class PipelineRequest(BaseModel):
    task_type: str
    payload: Dict[str, Any] = {}


class InsightCorrectionRequest(BaseModel):
    insight_id: int
    corrections: Dict[str, Any]


class RecommendationApprovalRequest(BaseModel):
    recommendation_id: int
    approved: bool
    notes: str = ""


class ThemeValidationRequest(BaseModel):
    theme_id: int
    valid: bool
    corrected_name: Optional[str] = None


class ForcePipelineRequest(BaseModel):
    survey_id: int


# ═══════════════════════════════════════════════════
# PIPELINE EXECUTION ENDPOINTS
# ═══════════════════════════════════════════════════
@router.post("/execute")
def execute_pipeline(request: PipelineRequest):
    """
    Execute an AI task through the full pipeline architecture.
    Routes through: Task Classifier → Context Builder → Pipeline → Validator

    Body: {"task_type": "sentiment_analysis", "payload": {"response_text": "..."}}
    """
    from ..services.ai_orchestrator import AIOrchestrator

    result = AIOrchestrator.execute_pipeline(request.task_type, request.payload)
    return result


@router.post("/execute/survey-intelligence")
def execute_survey_intelligence(payload: Dict[str, Any]):
    """Execute Pipeline A — Survey Intelligence (question generation)."""
    from ..services.ai_pipelines import SurveyIntelligencePipeline

    task_type = payload.pop("task_type", "question_generation")
    return SurveyIntelligencePipeline.execute(payload, task_type=task_type)


@router.post("/execute/response-understanding")
def execute_response_understanding(payload: Dict[str, Any]):
    """Execute Pipeline B — Response Understanding (full analysis)."""
    from ..services.ai_pipelines import ResponseUnderstandingPipeline
    from ..services.context_builder import AIContextBuilder

    response_text = payload.get("response_text", "")
    survey_id = payload.get("survey_id")
    session_id = payload.get("session_id", "")

    # Build rich context if survey_id provided
    if survey_id:
        context = AIContextBuilder.build_response_context(
            survey_id=survey_id, session_id=session_id, response_text=response_text
        )
        context.update(payload)
    else:
        context = payload

    task_type = payload.get("task_type", "response_understanding")
    return ResponseUnderstandingPipeline.execute(context, task_type=task_type)


@router.post("/execute/insight-formation")
def execute_insight_formation(payload: Dict[str, Any]):
    """Execute Pipeline C — Insight Formation (theme clustering)."""
    from ..services.ai_pipelines import InsightFormationPipeline
    from ..services.context_builder import AIContextBuilder

    survey_id = payload.get("survey_id")
    if survey_id:
        context = AIContextBuilder.build_insight_context(survey_id)
        context.update(payload)
    else:
        context = payload

    task_type = payload.get("task_type", "insight_clustering")
    return InsightFormationPipeline.execute(context, task_type=task_type)


@router.post("/execute/recommendations")
def execute_recommendation_engine(payload: Dict[str, Any]):
    """Execute Pipeline D — Recommendation Engine."""
    from ..services.ai_pipelines import RecommendationEnginePipeline
    from ..services.context_builder import AIContextBuilder

    survey_id = payload.get("survey_id")
    if survey_id:
        context = AIContextBuilder.build_recommendation_context(survey_id)
        context.update(payload)
    else:
        context = payload

    task_type = payload.get("task_type", "recommendation_generation")
    return RecommendationEnginePipeline.execute(context, task_type=task_type)


@router.post("/execute/executive-intelligence")
def execute_executive_intelligence(payload: Dict[str, Any]):
    """Execute Pipeline E — Executive Intelligence (summary/report)."""
    from ..services.ai_pipelines import ExecutiveIntelligencePipeline
    from ..services.context_builder import AIContextBuilder

    survey_id = payload.get("survey_id")
    if survey_id:
        context = AIContextBuilder.build_executive_context(survey_id)
        context.update(payload)
    else:
        context = payload

    task_type = payload.get("task_type", "executive_summary")
    return ExecutiveIntelligencePipeline.execute(context, task_type=task_type)


# ═══════════════════════════════════════════════════
# FULL PIPELINE (Force-run all stages)
# ═══════════════════════════════════════════════════
@router.post("/force-full-pipeline")
def force_full_pipeline(request: ForcePipelineRequest):
    """
    Force-run the complete intelligence pipeline for a survey.
    Ignores smart trigger thresholds — runs Insight → Recommendation → Executive in sequence.
    """
    from ..services.intelligence_loop import ContinuousIntelligenceLoop

    result = ContinuousIntelligenceLoop.force_full_pipeline(request.survey_id)
    return result


# ═══════════════════════════════════════════════════
# HUMAN-IN-THE-LOOP (Section 9)
# ═══════════════════════════════════════════════════
@router.post("/hitl/correct-insight")
def correct_insight(request: InsightCorrectionRequest):
    """Apply human corrections to an AI-generated insight."""
    from ..services.intelligence_loop import HumanInTheLoop

    result = HumanInTheLoop.correct_insight(request.insight_id, request.corrections)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Correction failed"))
    return result


@router.post("/hitl/approve-recommendation")
def approve_recommendation(request: RecommendationApprovalRequest):
    """Approve or reject an AI-generated recommendation."""
    from ..services.intelligence_loop import HumanInTheLoop

    result = HumanInTheLoop.approve_recommendation(
        request.recommendation_id, request.approved, request.notes
    )
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Approval failed"))
    return result


@router.post("/hitl/validate-theme")
def validate_theme(request: ThemeValidationRequest):
    """Validate or correct an AI-generated theme."""
    from ..services.intelligence_loop import HumanInTheLoop

    result = HumanInTheLoop.validate_theme(
        request.theme_id, request.valid, request.corrected_name
    )
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Validation failed"))
    return result


@router.get("/hitl/corrections")
def get_corrections(survey_id: int = None, limit: int = 50):
    """Get history of human-in-the-loop corrections."""
    from ..services.intelligence_loop import HumanInTheLoop

    return HumanInTheLoop.get_corrections(survey_id=survey_id, limit=limit)


# ═══════════════════════════════════════════════════
# STATS & OBSERVABILITY
# ═══════════════════════════════════════════════════
@router.get("/stats")
def get_processing_stats():
    """
    Full AI Processing Architecture statistics.
    Includes: orchestrator, classifier, all pipelines, validation, intelligence loop.
    """
    from ..services.ai_orchestrator import AIOrchestrator

    return AIOrchestrator.get_pipeline_stats()


@router.get("/stats/pipelines")
def get_pipeline_stats():
    """Get stats for all processing pipelines."""
    from ..services.ai_pipelines import get_all_pipeline_stats

    return get_all_pipeline_stats()


@router.get("/stats/classifier")
def get_classifier_stats():
    """Get task classification statistics."""
    from ..services.ai_task_classifier import AITaskClassifier

    return AITaskClassifier.stats()


@router.get("/stats/validation")
def get_validation_stats():
    """Get AI output validation statistics."""
    from ..services.ai_validation import AIOutputValidator

    return AIOutputValidator.stats()


@router.get("/stats/intelligence-loop")
def get_intelligence_loop_stats():
    """Get continuous intelligence loop statistics."""
    from ..services.intelligence_loop import ContinuousIntelligenceLoop

    return ContinuousIntelligenceLoop.get_loop_stats()


# ═══════════════════════════════════════════════════
# TASK CLASSIFICATION INFO
# ═══════════════════════════════════════════════════
@router.get("/classify/{event_type}")
def classify_event(event_type: str):
    """Preview how an event type would be classified."""
    from ..services.ai_task_classifier import AITaskClassifier

    result = AITaskClassifier.classify_event(event_type)
    if not result:
        return {"event_type": event_type, "classification": None, "message": "No AI task for this event"}
    return {"event_type": event_type, "classification": result.to_dict()}


@router.get("/task-types")
def list_task_types():
    """List all available AI task types and their pipelines."""
    from ..services.ai_task_classifier import AITaskType, TASK_PIPELINE_MAP, TASK_PRIORITY

    return {
        "task_types": [
            {
                "task_type": t.value,
                "pipeline": TASK_PIPELINE_MAP.get(t, "unknown").value if TASK_PIPELINE_MAP.get(t) else "unknown",
                "priority": TASK_PRIORITY.get(t, "normal"),
            }
            for t in AITaskType
        ]
    }


@router.get("/architecture")
def get_architecture_overview():
    """Get a high-level overview of the AI Processing Architecture."""
    from ..services.ai_task_classifier import AITaskType, PipelineType

    return {
        "architecture": "AI Processing Architecture — Conversation → Intelligence Pipeline",
        "principle": "NEVER call AI directly from endpoints. All AI goes through Orchestrator → Classifier → Pipeline.",
        "components": {
            "1_orchestrator": "Central AI controller — routing, caching, cost tracking",
            "2_task_classifier": "Classifies events/requests into AI task types",
            "3_pipelines": {
                "A_survey_intelligence": "Research Goal → Questions → Logic (Pipeline A)",
                "B_response_understanding": "Raw Response → Cleaning → Context → Analysis → Structured Meaning (Pipeline B)",
                "C_insight_formation": "Multiple Responses → Themes → Clusters → Insights (Pipeline C)",
                "D_recommendation_engine": "Insights → Business Context → Reasoning → Action Plan (Pipeline D)",
                "E_executive_intelligence": "Everything → Trends → Narrative Report (Pipeline E)",
                "interactive": "Real-time chat and simulated interviews",
            },
            "4_context_builder": "Builds rich multi-layered context for every AI call",
            "5_validation": "Schema validation, range checking, hallucination detection",
            "6_intelligence_loop": "Continuous self-improving loop with smart triggering",
            "7_hitl": "Human-in-the-Loop corrections for AI learning",
        },
        "flow": "Response → Store → Event → Orchestrator → Classification → Pipeline → Gemini → Intelligence → Insight → Recommendation → Dashboard",
        "total_task_types": len(AITaskType),
        "total_pipelines": len(PipelineType),
    }
