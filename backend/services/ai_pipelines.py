"""
AI Processing Pipelines — Component 3: The Intelligence Engine
═══════════════════════════════════════════════════════════════════
Architecture: Instead of one AI call, route through specialized pipelines.

Pipeline A — Survey Intelligence Pipeline (Question Generation)
Pipeline B — Response Understanding Pipeline (Raw → Structured Meaning)
Pipeline C — Insight Formation Pipeline (Responses → Themes → Clusters)
Pipeline D — Recommendation Engine Pipeline (Insights → Action Plans)
Pipeline E — Executive Intelligence Pipeline (Everything → Narrative Report)

Each pipeline:
  1. Receives classified task + rich context
  2. Executes multi-step AI processing
  3. Validates output
  4. Returns structured intelligence
"""
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from ..database import get_db


# ═══════════════════════════════════════════════════════════════
# BASE PIPELINE CLASS
# ═══════════════════════════════════════════════════════════════
class BasePipeline:
    """Base class for all AI processing pipelines."""

    pipeline_name: str = "base"
    _invocation_count: int = 0
    _error_count: int = 0
    _total_latency_ms: int = 0

    @classmethod
    def execute(cls, context: dict, task_type: str = None) -> dict:
        """Execute the pipeline with full context. Override in subclasses."""
        raise NotImplementedError

    @classmethod
    def _record_metrics(cls, latency_ms: int, success: bool):
        cls._invocation_count += 1
        cls._total_latency_ms += latency_ms
        if not success:
            cls._error_count += 1

    @classmethod
    def stats(cls) -> dict:
        avg_latency = (
            cls._total_latency_ms // max(cls._invocation_count, 1)
        )
        return {
            "pipeline": cls.pipeline_name,
            "invocations": cls._invocation_count,
            "errors": cls._error_count,
            "avg_latency_ms": avg_latency,
        }


# ═══════════════════════════════════════════════════════════════
# PIPELINE A — Survey Intelligence Pipeline
# ═══════════════════════════════════════════════════════════════
class SurveyIntelligencePipeline(BasePipeline):
    """
    Pipeline A: Research Goal → Prompt Engineering → Questions → Logic Suggestions

    Handles:
      - Question generation from research goals
      - Deep question generation with follow-up paths
      - Intake clarification (multi-step intake)
      - Follow-up question generation during interviews

    Flow:
      Research Goal → Context Build → Gemini Prompt → Question Set → Logic Suggestions
    """

    pipeline_name = "pipeline_a_survey_intelligence"

    @classmethod
    def execute(cls, context: dict, task_type: str = "question_generation") -> dict:
        """
        Execute Survey Intelligence Pipeline.

        Args:
            context: Must contain 'research_goal'. Optional: 'audience', 'objectives', 'specific_areas'
            task_type: One of 'question_generation', 'deep_question_generation',
                       'follow_up_generation', 'intake_clarification'
        """
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService
        from ..services.ai_validation import AIOutputValidator

        start = time.time()

        try:
            if task_type == "question_generation":
                result = cls._generate_questions(context)
            elif task_type == "deep_question_generation":
                result = cls._generate_deep_questions(context)
            elif task_type == "follow_up_generation":
                result = cls._generate_follow_up(context)
            elif task_type == "intake_clarification":
                result = cls._intake_clarification(context)
            else:
                result = cls._generate_questions(context)

            latency = int((time.time() - start) * 1000)
            cls._record_metrics(latency, True)

            # Validate output
            validated = AIOutputValidator.validate_pipeline_output(
                cls.pipeline_name, task_type, result
            )

            return {
                "pipeline": cls.pipeline_name,
                "task_type": task_type,
                "result": validated["data"] if validated["valid"] else result,
                "valid": validated["valid"],
                "latency_ms": latency,
                "warnings": validated.get("warnings", []),
            }

        except Exception as e:
            latency = int((time.time() - start) * 1000)
            cls._record_metrics(latency, False)
            return {
                "pipeline": cls.pipeline_name,
                "task_type": task_type,
                "result": None,
                "valid": False,
                "error": str(e),
                "latency_ms": latency,
            }

    @classmethod
    def _generate_questions(cls, context: dict) -> dict:
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        research_goal = context.get("research_goal", "")
        audience = context.get("audience", "")
        research_type = context.get("research_type", "discovery")
        question_count = context.get("question_count", 8)

        # Use orchestrator for caching + cost tracking
        cache_key = f"survey_intel:gen:{research_goal[:100]}:{question_count}"
        result = AIOrchestrator.execute(
            "question_generation",
            cache_key,
            AIService.generate_questions,
            research_goal, research_type, question_count,
            cacheable=True
        )
        return result if isinstance(result, dict) else {"questions": result}

    @classmethod
    def _generate_deep_questions(cls, context: dict) -> dict:
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        research_goal = context.get("research_goal", "")
        base_questions = context.get("base_questions", [])

        cache_key = f"survey_intel:deep:{research_goal[:80]}:{len(base_questions)}"
        result = AIOrchestrator.execute(
            "deep_question_generation",
            cache_key,
            AIService.generate_deep_questions,
            research_goal, base_questions,
            cacheable=True
        )
        return result if isinstance(result, dict) else {"questions": result}

    @classmethod
    def _generate_follow_up(cls, context: dict) -> dict:
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        response_text = context.get("response_text", "")
        research_goal = context.get("research_goal", "")

        result = AIOrchestrator.execute(
            "follow_up_generation",
            f"followup:{response_text[:100]}",
            AIService.generate_follow_up,
            response_text, research_goal,
            cacheable=False
        )
        return result if isinstance(result, dict) else {"follow_up": result}

    @classmethod
    def _intake_clarification(cls, context: dict) -> dict:
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        user_input = context.get("user_input", "")
        conversation = context.get("conversation_history", [])

        result = AIOrchestrator.execute(
            "intake_clarification",
            f"intake:{user_input[:100]}",
            AIService.generate_intake_clarification,
            user_input, conversation,
            cacheable=False
        )
        return result if isinstance(result, dict) else {"ai_message": str(result)}


# ═══════════════════════════════════════════════════════════════
# PIPELINE B — Response Understanding Pipeline
# ═══════════════════════════════════════════════════════════════
class ResponseUnderstandingPipeline(BasePipeline):
    """
    Pipeline B: Raw Response → Cleaning → Context Injection → AI Analysis → Structured Meaning

    Multi-step processing:
      Step 1: Clean/normalize the response
      Step 2: Build rich context (via context_builder)
      Step 3: Run sentiment analysis
      Step 4: Segment response (if multi-topic)
      Step 5: Score quality
      Step 6: Extract semantic memory
      Step 7: Return structured understanding

    Extracts: intent, emotion, feature mention, urgency, sentiment
    """

    pipeline_name = "pipeline_b_response_understanding"

    @classmethod
    def execute(cls, context: dict, task_type: str = "response_understanding") -> dict:
        """
        Full response understanding pipeline.

        Args:
            context: Must contain 'response_text'. Ideally has 'full_prompt_context' from context_builder.
            task_type: Which sub-task to run. 'response_understanding' runs the full pipeline.
        """
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService
        from ..services.ai_validation import AIOutputValidator

        start = time.time()

        try:
            response_text = context.get("response_text", context.get("new_response", ""))
            if not response_text:
                return {"pipeline": cls.pipeline_name, "error": "No response text provided", "valid": False}

            # Route to specific sub-task or full pipeline
            if task_type == "sentiment_analysis":
                result = cls._analyze_sentiment(response_text, context)
            elif task_type == "response_segmentation":
                result = cls._segment_response(response_text)
            elif task_type == "quality_scoring":
                result = cls._score_quality(response_text)
            else:
                # Full understanding pipeline (all steps)
                result = cls._full_understanding(response_text, context)

            latency = int((time.time() - start) * 1000)
            cls._record_metrics(latency, True)

            validated = AIOutputValidator.validate_pipeline_output(
                cls.pipeline_name, task_type, result
            )

            return {
                "pipeline": cls.pipeline_name,
                "task_type": task_type,
                "result": validated["data"] if validated["valid"] else result,
                "valid": validated["valid"],
                "latency_ms": latency,
                "warnings": validated.get("warnings", []),
            }

        except Exception as e:
            latency = int((time.time() - start) * 1000)
            cls._record_metrics(latency, False)
            return {
                "pipeline": cls.pipeline_name,
                "task_type": task_type,
                "result": None,
                "valid": False,
                "error": str(e),
                "latency_ms": latency,
            }

    @classmethod
    def _full_understanding(cls, response_text: str, context: dict) -> dict:
        """Full multi-step response understanding pipeline."""
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        understanding = {
            "response_text": response_text,
            "word_count": len(response_text.split()),
            "processed_at": datetime.now().isoformat(),
        }

        # ── Step 1: Clean/Normalize ──
        cleaned = response_text.strip()
        understanding["cleaned_text"] = cleaned

        # ── Step 2: Sentiment Analysis (with context) ──
        sentiment = AIOrchestrator.execute(
            "sentiment_analysis",
            f"sentiment:{cleaned[:200]}",
            AIService.analyze_sentiment,
            cleaned,
            cacheable=False
        )
        understanding["sentiment"] = sentiment or {}

        # ── Step 3: Response Segmentation (if long enough) ──
        if len(cleaned.split()) > 15:
            segments = AIOrchestrator.execute(
                "response_segmentation",
                f"segment:{cleaned[:200]}",
                AIService.segment_response,
                cleaned,
                cacheable=False
            )
            understanding["segments"] = segments if isinstance(segments, list) else []
        else:
            understanding["segments"] = [{
                "segment_text": cleaned,
                "topic": "single_topic",
                "sentiment_label": understanding.get("sentiment", {}).get("sentiment_label", "neutral"),
                "sentiment_score": understanding.get("sentiment", {}).get("sentiment_score", 0),
            }]

        # ── Step 4: Quality Scoring ──
        quality = AIOrchestrator.execute(
            "quality_scoring",
            f"quality:{cleaned[:200]}",
            AIService.score_response_quality,
            cleaned,
            cacheable=False
        )
        understanding["quality"] = quality or {}

        # ── Step 5: Semantic Memory Extraction ──
        existing_memory = context.get("semantic_memory", [])
        memories = AIOrchestrator.execute(
            "memory_extraction",
            f"memory:{cleaned[:200]}",
            AIService.extract_semantic_memory,
            cleaned, existing_memory,
            cacheable=False
        )
        understanding["extracted_memory"] = memories if isinstance(memories, list) else []

        # ── Step 6: Follow-up Assessment ──
        research_goal = context.get("survey_goal", context.get("research_goal", ""))
        follow_up = AIOrchestrator.execute(
            "follow_up_generation",
            f"followup_assess:{cleaned[:150]}",
            AIService.generate_follow_up,
            cleaned, research_goal,
            cacheable=False
        )
        understanding["follow_up"] = follow_up or {}

        return understanding

    @classmethod
    def _analyze_sentiment(cls, response_text: str, context: dict) -> dict:
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        return AIOrchestrator.execute(
            "sentiment_analysis",
            f"sentiment:{response_text[:200]}",
            AIService.analyze_sentiment,
            response_text,
            cacheable=False
        )

    @classmethod
    def _segment_response(cls, response_text: str) -> list:
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        result = AIOrchestrator.execute(
            "response_segmentation",
            f"segment:{response_text[:200]}",
            AIService.segment_response,
            response_text,
            cacheable=False
        )
        return result if isinstance(result, list) else []

    @classmethod
    def _score_quality(cls, response_text: str) -> dict:
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        return AIOrchestrator.execute(
            "quality_scoring",
            f"quality:{response_text[:200]}",
            AIService.score_response_quality,
            response_text,
            cacheable=False
        )


# ═══════════════════════════════════════════════════════════════
# PIPELINE C — Insight Formation Pipeline
# ═══════════════════════════════════════════════════════════════
class InsightFormationPipeline(BasePipeline):
    """
    Pipeline C: Multiple Responses → Similarity → Theme Grouping → Cluster Formation

    Multi-step processing:
      Step 1: Gather response batch + existing themes
      Step 2: Run theme clustering via AI
      Step 3: Identify emerging patterns
      Step 4: Calculate insight deltas
      Step 5: Store updated themes + insights

    Result: Performance Issues, UI Confusion, Missing Features, etc.
    """

    pipeline_name = "pipeline_c_insight_formation"

    @classmethod
    def execute(cls, context: dict, task_type: str = "insight_clustering") -> dict:
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService
        from ..services.ai_validation import AIOutputValidator

        start = time.time()

        try:
            if task_type == "theme_extraction":
                result = cls._extract_themes(context)
            elif task_type == "memory_extraction":
                result = cls._extract_memory(context)
            else:
                result = cls._full_insight_formation(context)

            latency = int((time.time() - start) * 1000)
            cls._record_metrics(latency, True)

            validated = AIOutputValidator.validate_pipeline_output(
                cls.pipeline_name, task_type, result
            )

            return {
                "pipeline": cls.pipeline_name,
                "task_type": task_type,
                "result": validated["data"] if validated["valid"] else result,
                "valid": validated["valid"],
                "latency_ms": latency,
                "warnings": validated.get("warnings", []),
            }

        except Exception as e:
            latency = int((time.time() - start) * 1000)
            cls._record_metrics(latency, False)
            return {
                "pipeline": cls.pipeline_name, "task_type": task_type,
                "result": None, "valid": False, "error": str(e),
                "latency_ms": latency,
            }

    @classmethod
    def _full_insight_formation(cls, context: dict) -> dict:
        """Full insight formation: batch responses → themes → insight clusters."""
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        response_batch = context.get("response_batch", [])
        existing_themes = context.get("existing_themes", [])
        survey_goal = context.get("survey_goal", "")

        if not response_batch:
            return {"themes": [], "insights_updated": 0, "message": "No responses to analyze"}

        # ── Step 1: Theme Clustering via AI (batch call — 100 responses → 1 AI call) ──
        themes = AIOrchestrator.execute(
            "theme_extraction",
            f"themes_batch:{len(response_batch)}:{survey_goal[:60]}",
            AIService.cluster_themes_from_responses,
            response_batch, existing_themes,
            cacheable=False
        )

        if not isinstance(themes, list):
            themes = []

        # ── Step 2: Identify emerging patterns ──
        emerging = [t for t in themes if t.get("is_emerging")]

        # ── Step 3: Classify themes by business risk ──
        high_risk = [t for t in themes if t.get("business_risk") == "high"]
        sentiment_negative = [t for t in themes if (t.get("sentiment_avg", 0) or 0) < -0.3]

        # ── Step 4: Build insight summary ──
        insight_result = {
            "themes": themes,
            "theme_count": len(themes),
            "emerging_themes": [t.get("name", "") for t in emerging],
            "high_risk_themes": [t.get("name", "") for t in high_risk],
            "negative_themes": [t.get("name", "") for t in sentiment_negative],
            "responses_analyzed": len(response_batch),
            "processed_at": datetime.now().isoformat(),
        }

        return insight_result

    @classmethod
    def _extract_themes(cls, context: dict) -> list:
        """Theme extraction sub-task."""
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        response_batch = context.get("response_batch", [])
        existing_themes = context.get("existing_themes", [])

        result = AIOrchestrator.execute(
            "theme_extraction",
            f"themes:{len(response_batch)}",
            AIService.cluster_themes_from_responses,
            response_batch, existing_themes,
            cacheable=False
        )
        return result if isinstance(result, list) else []

    @classmethod
    def _extract_memory(cls, context: dict) -> list:
        """Semantic memory extraction sub-task."""
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        response_text = context.get("response_text", "")
        existing_memory = context.get("existing_memory", context.get("semantic_memory", []))

        result = AIOrchestrator.execute(
            "memory_extraction",
            f"memory:{response_text[:200]}",
            AIService.extract_semantic_memory,
            response_text, existing_memory,
            cacheable=False
        )
        return result if isinstance(result, list) else []


# ═══════════════════════════════════════════════════════════════
# PIPELINE D — Recommendation Engine Pipeline
# ═══════════════════════════════════════════════════════════════
class RecommendationEnginePipeline(BasePipeline):
    """
    Pipeline D: Insight Cluster → Business Context → Gemini Reasoning → Action Plan

    The highest-value pipeline in the system.

    Multi-step processing:
      Step 1: Gather insights + business context
      Step 2: AI generates reasoning over insight clusters
      Step 3: Produce action plan with priority, impact, effort, roadmap
      Step 4: Validate and rank recommendations

    Output: priority, impact, effort, roadmap suggestions
    """

    pipeline_name = "pipeline_d_recommendation_engine"

    @classmethod
    def execute(cls, context: dict, task_type: str = "recommendation_generation") -> dict:
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService
        from ..services.ai_validation import AIOutputValidator

        start = time.time()

        try:
            if task_type == "action_plan_generation":
                result = cls._generate_action_plan(context)
            else:
                result = cls._generate_recommendations(context)

            latency = int((time.time() - start) * 1000)
            cls._record_metrics(latency, True)

            validated = AIOutputValidator.validate_pipeline_output(
                cls.pipeline_name, task_type, result
            )

            return {
                "pipeline": cls.pipeline_name,
                "task_type": task_type,
                "result": validated["data"] if validated["valid"] else result,
                "valid": validated["valid"],
                "latency_ms": latency,
                "warnings": validated.get("warnings", []),
            }

        except Exception as e:
            latency = int((time.time() - start) * 1000)
            cls._record_metrics(latency, False)
            return {
                "pipeline": cls.pipeline_name, "task_type": task_type,
                "result": None, "valid": False, "error": str(e),
                "latency_ms": latency,
            }

    @classmethod
    def _generate_recommendations(cls, context: dict) -> dict:
        """Generate recommendations from insights + business context."""
        from ..services.ai_service import _ask_gemini_json

        insights = context.get("insights", [])
        themes = context.get("themes", [])
        survey_goal = context.get("survey_goal", "")
        prompt_context = context.get("full_prompt_context", "")

        if not insights:
            return {"recommendations": [], "message": "No insights available for recommendations"}

        # Build rich prompt with full business context
        insight_text = json.dumps([{
            "title": i.get("title", ""),
            "description": i.get("description", ""),
            "sentiment": i.get("sentiment", ""),
            "impact_score": i.get("impact_score", 0),
            "frequency": i.get("frequency", 0),
            "feature_area": i.get("feature_area", ""),
            "user_quote": i.get("user_quote", ""),
        } for i in insights[:15]], indent=2)

        theme_text = json.dumps([{
            "name": t.get("name", ""),
            "priority": t.get("priority", ""),
            "business_risk": t.get("business_risk", ""),
            "sentiment_avg": t.get("sentiment_avg", 0),
        } for t in themes[:10]], indent=2)

        prompt = f"""You are a product strategy AI. Generate actionable recommendations from these research insights.

{prompt_context}

INSIGHTS:
{insight_text}

THEMES:
{theme_text}

For each recommendation, provide:
- "title": Short action title (5-10 words)
- "description": What to do and why (2-3 sentences)
- "category": "feature", "ux", "performance", "content", "process", or "strategy"
- "priority": "critical", "high", "medium", or "low"
- "impact_score": float 0.0-1.0 (expected impact)
- "urgency_score": float 0.0-1.0 (how urgent)
- "effort_score": float 0.0-1.0 (implementation effort, lower = easier)
- "roadmap_phase": "immediate" (0-2 weeks), "short_term" (2-6 weeks), "medium_term" (1-3 months), "long_term" (3+ months)
- "supporting_insights": list of insight titles that support this recommendation
- "expected_outcome": 1 sentence describing expected business outcome

Generate 3-8 recommendations prioritized by impact and urgency.
Return a JSON object: {{"recommendations": [...], "summary": "1-2 sentence overall recommendation summary"}}
Return ONLY valid JSON."""

        result = _ask_gemini_json(prompt, max_tokens=3000)

        if isinstance(result, dict) and "recommendations" in result:
            # Calculate priority scores
            for rec in result["recommendations"]:
                impact = rec.get("impact_score", 0.5)
                urgency = rec.get("urgency_score", 0.5)
                effort = max(rec.get("effort_score", 0.5), 0.1)
                rec["priority_score"] = round((impact * urgency) / effort, 3)

            # Sort by priority score
            result["recommendations"].sort(key=lambda r: r.get("priority_score", 0), reverse=True)
            return result

        # Fallback
        return {
            "recommendations": [{
                "title": "Review High-Impact Insights",
                "description": "Focus on the highest-impact insights identified in the research.",
                "category": "strategy",
                "priority": "high",
                "impact_score": 0.8,
                "urgency_score": 0.7,
                "effort_score": 0.3,
                "priority_score": 1.867,
                "roadmap_phase": "immediate",
                "supporting_insights": [],
                "expected_outcome": "Prioritized action plan based on user feedback.",
            }],
            "summary": "Review and act on the most impactful insights from user feedback."
        }

    @classmethod
    def _generate_action_plan(cls, context: dict) -> dict:
        """Generate a detailed action plan from recommendations."""
        from ..services.ai_service import _ask_gemini_json

        recommendations = context.get("recommendations", [])
        if not recommendations:
            return {"action_plan": [], "message": "No recommendations to build action plan from"}

        rec_text = json.dumps([{
            "title": r.get("title", ""),
            "priority": r.get("priority", ""),
            "roadmap_phase": r.get("roadmap_phase", ""),
            "effort_score": r.get("effort_score", 0.5),
        } for r in recommendations[:10]], indent=2)

        prompt = f"""You are a product manager AI. Create a phased action plan from these recommendations.

RECOMMENDATIONS:
{rec_text}

Return a JSON object with:
- "action_plan": [
    {{
      "phase": "immediate|short_term|medium_term|long_term",
      "phase_label": "human-readable phase name",
      "actions": [
        {{
          "title": "action title",
          "description": "what to do",
          "owner_suggestion": "engineering|design|product|marketing",
          "estimated_days": integer,
          "dependencies": ["other action titles if any"]
        }}
      ]
    }}
  ]
- "total_estimated_days": integer
- "quick_wins": ["list of actions that can be done in < 3 days"]

Return ONLY valid JSON."""

        result = _ask_gemini_json(prompt, max_tokens=2048)
        if isinstance(result, dict) and "action_plan" in result:
            return result

        return {
            "action_plan": [{
                "phase": "immediate",
                "phase_label": "Quick Wins (0-2 weeks)",
                "actions": [{"title": r.get("title", ""), "description": r.get("description", ""),
                             "owner_suggestion": "product", "estimated_days": 7, "dependencies": []}
                            for r in recommendations[:3]]
            }],
            "total_estimated_days": 30,
            "quick_wins": [r.get("title", "") for r in recommendations[:2]]
        }


# ═══════════════════════════════════════════════════════════════
# PIPELINE E — Executive Intelligence Pipeline
# ═══════════════════════════════════════════════════════════════
class ExecutiveIntelligencePipeline(BasePipeline):
    """
    Pipeline E: Insights → Trends → AI Summarization → Executive Report

    This is what founders actually read.

    Multi-step processing:
      Step 1: Aggregate all intelligence (insights, themes, sentiment, recommendations)
      Step 2: Identify trends and patterns
      Step 3: AI generates narrative summary
      Step 4: Format as executive report

    Output: Narrative report with key findings, trends, and recommended actions
    """

    pipeline_name = "pipeline_e_executive_intelligence"

    @classmethod
    def execute(cls, context: dict, task_type: str = "executive_summary") -> dict:
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService
        from ..services.ai_validation import AIOutputValidator

        start = time.time()

        try:
            if task_type == "transcript_report":
                result = cls._generate_transcript_report(context)
            elif task_type == "trend_analysis":
                result = cls._analyze_trends(context)
            else:
                result = cls._generate_executive_summary(context)

            latency = int((time.time() - start) * 1000)
            cls._record_metrics(latency, True)

            validated = AIOutputValidator.validate_pipeline_output(
                cls.pipeline_name, task_type, result
            )

            return {
                "pipeline": cls.pipeline_name,
                "task_type": task_type,
                "result": validated["data"] if validated["valid"] else result,
                "valid": validated["valid"],
                "latency_ms": latency,
                "warnings": validated.get("warnings", []),
            }

        except Exception as e:
            latency = int((time.time() - start) * 1000)
            cls._record_metrics(latency, False)
            return {
                "pipeline": cls.pipeline_name, "task_type": task_type,
                "result": None, "valid": False, "error": str(e),
                "latency_ms": latency,
            }

    @classmethod
    def _generate_executive_summary(cls, context: dict) -> dict:
        """Generate full executive intelligence report."""
        from ..services.ai_service import _ask_gemini_json

        prompt_context = context.get("full_prompt_context", "")
        insights = context.get("insights", [])
        themes = context.get("themes", [])
        recommendations = context.get("recommendations", [])
        sentiment_data = context.get("sentiment_data", [])

        # Build comprehensive prompt
        insight_text = json.dumps([{
            "title": i.get("title", ""),
            "description": i.get("description", ""),
            "impact_score": i.get("impact_score", 0),
            "sentiment": i.get("sentiment", ""),
        } for i in insights[:12]], indent=2)

        theme_text = json.dumps([{
            "name": t.get("name", ""),
            "description": t.get("description", ""),
            "priority": t.get("priority", ""),
            "business_risk": t.get("business_risk", ""),
        } for t in themes[:8]], indent=2)

        rec_text = json.dumps([{
            "title": r.get("title", ""),
            "priority": r.get("priority", ""),
            "roadmap_phase": r.get("roadmap_phase", ""),
        } for r in recommendations[:6]], indent=2)

        # Calculate sentiment trend
        avg_sentiment = context.get("avg_sentiment", 0)

        prompt = f"""You are an executive research analyst. Create a comprehensive executive intelligence report.

{prompt_context}

INSIGHTS:
{insight_text}

THEMES:
{theme_text}

RECOMMENDATIONS:
{rec_text}

Average Sentiment Score: {avg_sentiment}

Generate an executive report with:
- "executive_summary": 3-5 sentence high-level summary for C-level audience
- "key_findings": [3-5 most important findings, each as {{"finding": "title", "detail": "1-2 sentences", "severity": "critical|high|medium|low"}}]
- "sentiment_overview": {{"overall": "positive|negative|neutral|mixed", "score": float, "trend": "improving|declining|stable", "narrative": "1-2 sentences"}}
- "theme_analysis": [Top 3-5 themes with {{"theme": "name", "narrative": "2-3 sentences explaining the theme and its business impact"}}]
- "risk_assessment": [Any high-risk items as {{"risk": "title", "level": "high|medium|low", "mitigation": "suggested action"}}]
- "recommended_actions": [Top 3-5 prioritized actions as {{"action": "title", "priority": "critical|high|medium|low", "timeframe": "phase"}}]
- "confidence_score": float 0.0-1.0 (how confident in these conclusions)

Write in professional, executive-friendly language. Be concise and actionable.
Return ONLY valid JSON."""

        result = _ask_gemini_json(prompt, max_tokens=4096)
        if isinstance(result, dict) and "executive_summary" in result:
            result["generated_at"] = datetime.now().isoformat()
            result["data_basis"] = {
                "insights_analyzed": len(insights),
                "themes_identified": len(themes),
                "recommendations_available": len(recommendations),
                "sentiment_records": len(sentiment_data),
            }
            return result

        # Fallback
        return {
            "executive_summary": "Insufficient data to generate a comprehensive executive report. More user feedback is needed.",
            "key_findings": [],
            "sentiment_overview": {"overall": "neutral", "score": 0, "trend": "stable", "narrative": "Not enough data."},
            "theme_analysis": [],
            "risk_assessment": [],
            "recommended_actions": [],
            "confidence_score": 0.3,
            "generated_at": datetime.now().isoformat(),
            "data_basis": {"insights_analyzed": len(insights), "themes_identified": len(themes),
                           "recommendations_available": len(recommendations), "sentiment_records": len(sentiment_data)},
        }

    @classmethod
    def _generate_transcript_report(cls, context: dict) -> dict:
        """Generate a report from interview transcript."""
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        conversation_history = context.get("conversation_history", [])
        survey_goal = context.get("survey_goal", context.get("research_goal", ""))

        result = AIOrchestrator.execute(
            "transcript_report",
            f"transcript:{len(conversation_history)}:{survey_goal[:60]}",
            AIService.generate_interview_transcript_report,
            conversation_history, survey_goal,
            cacheable=True
        )
        return result if isinstance(result, dict) else {"report": str(result)}

    @classmethod
    def _analyze_trends(cls, context: dict) -> dict:
        """Analyze sentiment and theme trends over time."""
        from ..services.ai_service import _ask_gemini_json

        sentiment_data = context.get("sentiment_data", [])
        themes = context.get("themes", [])

        if not sentiment_data and not themes:
            return {"trends": [], "message": "Insufficient data for trend analysis"}

        time_data = json.dumps([{
            "sentiment_label": s.get("sentiment_label", ""),
            "sentiment_score": s.get("sentiment_score", 0),
            "feature_area": s.get("feature_area", ""),
            "recorded_at": s.get("recorded_at", ""),
        } for s in sentiment_data[:30]], indent=2)

        prompt = f"""Analyze these sentiment records over time and identify trends.

SENTIMENT RECORDS:
{time_data}

KNOWN THEMES: {json.dumps([t.get("name", "") for t in themes[:8]])}

Return a JSON object with:
- "trends": [
    {{
      "trend_name": "short name",
      "direction": "improving|declining|stable|volatile",
      "affected_areas": ["feature areas affected"],
      "narrative": "1-2 sentence explanation",
      "severity": "high|medium|low"
    }}
  ]
- "overall_trajectory": "improving|declining|stable"
- "alert_areas": ["areas needing immediate attention"]
- "positive_areas": ["areas doing well"]

Return ONLY valid JSON."""

        result = _ask_gemini_json(prompt, max_tokens=2048)
        if isinstance(result, dict) and "trends" in result:
            return result

        return {
            "trends": [],
            "overall_trajectory": "stable",
            "alert_areas": [],
            "positive_areas": [],
            "message": "Trend analysis requires more data points."
        }


# ═══════════════════════════════════════════════════════════════
# INTERACTIVE PIPELINE (Chat + Simulated Interview)
# ═══════════════════════════════════════════════════════════════
class InteractivePipeline(BasePipeline):
    """
    Interactive Pipeline: Handles real-time chat and simulated interviews.
    These are critical-priority tasks (user is waiting).
    """

    pipeline_name = "pipeline_interactive"

    @classmethod
    def execute(cls, context: dict, task_type: str = "chat_response") -> dict:
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        start = time.time()

        try:
            if task_type == "chat_response":
                result = cls._generate_chat(context)
            elif task_type == "simulated_interview":
                result = cls._simulate_interview(context)
            else:
                result = cls._generate_chat(context)

            latency = int((time.time() - start) * 1000)
            cls._record_metrics(latency, True)

            return {
                "pipeline": cls.pipeline_name,
                "task_type": task_type,
                "result": result,
                "valid": True,
                "latency_ms": latency,
            }

        except Exception as e:
            latency = int((time.time() - start) * 1000)
            cls._record_metrics(latency, False)
            return {
                "pipeline": cls.pipeline_name, "task_type": task_type,
                "result": None, "valid": False, "error": str(e),
                "latency_ms": latency,
            }

    @classmethod
    def _generate_chat(cls, context: dict) -> str:
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        message = context.get("message", "")
        history = context.get("history", [])
        memory = context.get("memory", [])
        survey_context = context.get("survey_context", {})

        result = AIOrchestrator.execute(
            "chat_response",
            f"chat:{message[:100]}",
            AIService.generate_chat_response_with_memory,
            message, history, memory, survey_context,
            cacheable=False
        )
        return result if isinstance(result, str) else str(result)

    @classmethod
    def _simulate_interview(cls, context: dict) -> dict:
        from ..services.ai_orchestrator import AIOrchestrator
        from ..services.ai_service import AIService

        questions = context.get("questions", [])
        persona = context.get("persona", None)

        result = AIOrchestrator.execute(
            "simulated_interview",
            f"simulate:{len(questions)}",
            AIService.simulate_interview,
            questions, persona,
            cacheable=True
        )
        return result if isinstance(result, dict) else {"responses": []}


# ═══════════════════════════════════════════════════════════════
# PIPELINE REGISTRY — Central access to all pipelines
# ═══════════════════════════════════════════════════════════════
PIPELINE_REGISTRY: Dict[str, type] = {
    "pipeline_a_survey_intelligence": SurveyIntelligencePipeline,
    "pipeline_b_response_understanding": ResponseUnderstandingPipeline,
    "pipeline_c_insight_formation": InsightFormationPipeline,
    "pipeline_d_recommendation_engine": RecommendationEnginePipeline,
    "pipeline_e_executive_intelligence": ExecutiveIntelligencePipeline,
    "pipeline_interactive": InteractivePipeline,
}


def get_pipeline(pipeline_name: str) -> Optional[type]:
    """Get a pipeline class by name."""
    return PIPELINE_REGISTRY.get(pipeline_name)


def get_all_pipeline_stats() -> dict:
    """Get stats for all pipelines."""
    return {name: cls.stats() for name, cls in PIPELINE_REGISTRY.items()}
