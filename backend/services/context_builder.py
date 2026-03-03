"""
AI Context Builder — Section 6: AI Context Management
═══════════════════════════════════════════════════════
Architecture: AI must understand conversation history, not just raw text.

Bad Prompt ❌:  "Analyze this response."
Good Prompt ✅: Survey Goal + Previous summaries + Semantic Memory + New Response

This module builds rich, layered context for every AI call,
dramatically improving intelligence quality over raw prompts.

Context Layers:
  Layer 1: Survey / Research Goal context
  Layer 2: Conversation history summary
  Layer 3: Semantic memory (entities, relationships)
  Layer 4: Theme / Insight context (what we already know)
  Layer 5: New data (the actual input to process)
"""
import json
from typing import Optional, List, Dict, Any
from ..database import get_db


class AIContextBuilder:
    """
    Builds rich, multi-layered context for AI calls.

    Architecture: Every AI pipeline call should use context_builder
    to assemble the full picture before prompting Gemini.

    Usage:
        context = AIContextBuilder.build_response_context(
            survey_id=1, session_id="abc", response_text="..."
        )
        # context["full_prompt_context"] → ready to inject into prompt
    """

    # ───────────────────────────────────────────────────────────
    # MASTER CONTEXT BUILDER
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def build_response_context(survey_id: int, session_id: str,
                               response_text: str, include_memory: bool = True,
                               include_themes: bool = True,
                               include_history: bool = True) -> dict:
        """
        Build complete context for analyzing a response.
        This is the primary context builder for Pipeline B (Response Understanding).

        Returns:
            {
                "survey_goal": str,
                "audience": str,
                "objectives": list,
                "conversation_summary": str,
                "semantic_memory": list,
                "existing_themes": list,
                "response_count": int,
                "new_response": str,
                "full_prompt_context": str  ← Ready to inject into Gemini prompt
            }
        """
        context = {
            "survey_goal": "",
            "audience": "",
            "objectives": [],
            "conversation_summary": "",
            "semantic_memory": [],
            "existing_themes": [],
            "response_count": 0,
            "new_response": response_text,
        }

        conn = get_db()

        # ── Layer 1: Survey/Research Goal ──
        survey = conn.execute("""
            SELECT s.title, s.research_type, rg.original_input, rg.parsed_goal,
                   rg.target_audience, rg.objectives
            FROM surveys s
            LEFT JOIN research_goals rg ON s.research_goal_id = rg.id
            WHERE s.id = ?
        """, (survey_id,)).fetchone()

        if survey:
            sd = dict(survey)
            context["survey_goal"] = sd.get("parsed_goal") or sd.get("original_input") or sd.get("title", "")
            context["audience"] = sd.get("target_audience", "")
            try:
                context["objectives"] = json.loads(sd.get("objectives", "[]"))
            except (json.JSONDecodeError, TypeError):
                context["objectives"] = []

        # ── Layer 2: Conversation History Summary ──
        if include_history and session_id:
            history = conn.execute("""
                SELECT role, message FROM conversation_history
                WHERE session_id = ? ORDER BY created_at DESC LIMIT 10
            """, (session_id,)).fetchall()

            if history:
                history_lines = []
                for h in reversed([dict(h) for h in history]):
                    role = "Interviewer" if h["role"] == "ai" else "Respondent"
                    history_lines.append(f"{role}: {h['message'][:150]}")
                context["conversation_summary"] = "\n".join(history_lines)

            # Response count for this session
            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM responses WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            context["response_count"] = dict(count)["cnt"] if count else 0

        # ── Layer 3: Semantic Memory ──
        if include_memory and session_id:
            memories = conn.execute("""
                SELECT entity, relation, value, confidence
                FROM semantic_memory WHERE session_id = ?
                ORDER BY confidence DESC LIMIT 12
            """, (session_id,)).fetchall()

            context["semantic_memory"] = [dict(m) for m in memories]

        # ── Layer 4: Theme / Insight Context ──
        if include_themes and survey_id:
            themes = conn.execute("""
                SELECT name, description, sentiment_avg, priority
                FROM themes WHERE survey_id = ? ORDER BY frequency DESC LIMIT 8
            """, (survey_id,)).fetchall()

            context["existing_themes"] = [dict(t) for t in themes]

        conn.close()

        # ── Build Full Prompt Context String ──
        context["full_prompt_context"] = AIContextBuilder._format_context_string(context)

        return context

    # ───────────────────────────────────────────────────────────
    # SURVEY CREATION CONTEXT
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def build_survey_context(research_goal: str, audience: str = "",
                             objectives: list = None, specific_areas: list = None) -> dict:
        """
        Build context for Pipeline A (Survey Intelligence).
        Used during question generation.
        """
        context = {
            "research_goal": research_goal,
            "audience": audience or "General users",
            "objectives": objectives or [],
            "specific_areas": specific_areas or [],
        }

        prompt_parts = [f"Research Goal: {research_goal}"]
        if audience:
            prompt_parts.append(f"Target Audience: {audience}")
        if objectives:
            prompt_parts.append(f"Objectives: {', '.join(objectives)}")
        if specific_areas:
            prompt_parts.append(f"Specific Areas to Explore: {', '.join(specific_areas)}")

        context["full_prompt_context"] = "\n".join(prompt_parts)
        return context

    # ───────────────────────────────────────────────────────────
    # INSIGHT CONTEXT (for Pipeline C)
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def build_insight_context(survey_id: int, response_batch: list = None) -> dict:
        """
        Build context for Pipeline C (Insight Formation).
        Gathers existing themes, insights, and response batch.
        """
        conn = get_db()

        # Existing themes
        themes = conn.execute("""
            SELECT name, description, frequency, sentiment_avg, priority, business_risk, is_emerging
            FROM themes WHERE survey_id = ? ORDER BY frequency DESC
        """, (survey_id,)).fetchall()

        # Existing insights
        insights = conn.execute("""
            SELECT title, description, insight_type, feature_area, sentiment, frequency,
                   impact_score, confidence
            FROM insights WHERE survey_id = ? ORDER BY impact_score DESC LIMIT 20
        """, (survey_id,)).fetchall()

        # Survey goal
        survey = conn.execute("""
            SELECT s.title, rg.parsed_goal, rg.target_audience
            FROM surveys s LEFT JOIN research_goals rg ON s.research_goal_id = rg.id
            WHERE s.id = ?
        """, (survey_id,)).fetchone()

        # If no response batch provided, get recent ones
        if not response_batch:
            recent = conn.execute("""
                SELECT response_text, sentiment_label, sentiment_score
                FROM responses WHERE session_id IN (
                    SELECT session_id FROM interview_sessions WHERE survey_id = ?
                ) ORDER BY created_at DESC LIMIT 30
            """, (survey_id,)).fetchall()
            response_batch = [dict(r) for r in recent]

        conn.close()

        context = {
            "survey_goal": dict(survey).get("parsed_goal", "") if survey else "",
            "audience": dict(survey).get("target_audience", "") if survey else "",
            "existing_themes": [dict(t) for t in themes],
            "existing_insights": [dict(i) for i in insights],
            "response_batch": response_batch,
            "response_count": len(response_batch),
        }

        # Build prompt context string
        prompt_parts = []
        if context["survey_goal"]:
            prompt_parts.append(f"Research Goal: {context['survey_goal']}")
        if context["existing_themes"]:
            theme_names = [t["name"] for t in context["existing_themes"][:8]]
            prompt_parts.append(f"Known Themes: {', '.join(theme_names)}")
        if context["existing_insights"]:
            insight_titles = [i["title"] for i in context["existing_insights"][:5]]
            prompt_parts.append(f"Existing Insights: {', '.join(insight_titles)}")
        prompt_parts.append(f"Responses to analyze: {context['response_count']}")

        context["full_prompt_context"] = "\n".join(prompt_parts)
        return context

    # ───────────────────────────────────────────────────────────
    # RECOMMENDATION CONTEXT (for Pipeline D)
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def build_recommendation_context(survey_id: int) -> dict:
        """
        Build context for Pipeline D (Recommendation Engine).
        Gathers insights, themes, sentiment trends, and business context.
        """
        conn = get_db()

        # Insights (the input for recommendations)
        insights = conn.execute("""
            SELECT title, description, insight_type, feature_area, sentiment,
                   frequency, impact_score, confidence, user_quote
            FROM insights WHERE survey_id = ? ORDER BY impact_score DESC
        """, (survey_id,)).fetchall()

        # Themes (for business context)
        themes = conn.execute("""
            SELECT name, description, priority, business_risk, sentiment_avg
            FROM themes WHERE survey_id = ? ORDER BY frequency DESC LIMIT 10
        """, (survey_id,)).fetchall()

        # Sentiment trend
        sentiments = conn.execute("""
            SELECT sentiment_label, sentiment_score, feature_area, recorded_at
            FROM sentiment_records WHERE survey_id = ?
            ORDER BY recorded_at DESC LIMIT 50
        """, (survey_id,)).fetchall()

        # Survey goal
        survey = conn.execute("""
            SELECT s.title, rg.parsed_goal, rg.target_audience
            FROM surveys s LEFT JOIN research_goals rg ON s.research_goal_id = rg.id
            WHERE s.id = ?
        """, (survey_id,)).fetchone()

        conn.close()

        context = {
            "survey_goal": dict(survey).get("parsed_goal", "") if survey else "",
            "audience": dict(survey).get("target_audience", "") if survey else "",
            "insights": [dict(i) for i in insights],
            "themes": [dict(t) for t in themes],
            "sentiment_data": [dict(s) for s in sentiments],
            "insight_count": len(insights),
        }

        # Build prompt context
        prompt_parts = []
        if context["survey_goal"]:
            prompt_parts.append(f"Research Goal: {context['survey_goal']}")
        if context["insights"]:
            prompt_parts.append(f"Total Insights: {context['insight_count']}")
            high_impact = [i for i in context["insights"] if i.get("impact_score", 0) > 0.7]
            if high_impact:
                prompt_parts.append(f"High-Impact Insights: {len(high_impact)}")
        if context["themes"]:
            high_risk = [t for t in context["themes"] if t.get("business_risk") == "high"]
            if high_risk:
                prompt_parts.append(f"High-Risk Themes: {', '.join(t['name'] for t in high_risk)}")

        context["full_prompt_context"] = "\n".join(prompt_parts)
        return context

    # ───────────────────────────────────────────────────────────
    # EXECUTIVE REPORT CONTEXT (for Pipeline E)
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def build_executive_context(survey_id: int) -> dict:
        """
        Build context for Pipeline E (Executive Intelligence).
        Aggregates everything: insights, themes, sentiment, recommendations, engagement.
        """
        conn = get_db()

        survey = conn.execute("""
            SELECT s.*, rg.parsed_goal, rg.target_audience
            FROM surveys s LEFT JOIN research_goals rg ON s.research_goal_id = rg.id
            WHERE s.id = ?
        """, (survey_id,)).fetchone()

        insights = conn.execute(
            "SELECT * FROM insights WHERE survey_id = ? ORDER BY impact_score DESC",
            (survey_id,)
        ).fetchall()

        themes = conn.execute(
            "SELECT * FROM themes WHERE survey_id = ? ORDER BY frequency DESC",
            (survey_id,)
        ).fetchall()

        sentiments = conn.execute(
            "SELECT * FROM sentiment_records WHERE survey_id = ? ORDER BY recorded_at",
            (survey_id,)
        ).fetchall()

        recommendations = conn.execute(
            "SELECT * FROM recommendations WHERE survey_id = ? ORDER BY priority_score DESC",
            (survey_id,)
        ).fetchall()

        engagement = conn.execute(
            "SELECT * FROM engagement_metrics WHERE survey_id = ?",
            (survey_id,)
        ).fetchall()

        response_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM responses WHERE session_id IN (
                SELECT session_id FROM interview_sessions WHERE survey_id = ?
            )
        """, (survey_id,)).fetchone()

        conn.close()

        context = {
            "survey_goal": dict(survey).get("parsed_goal", "") if survey else "",
            "survey_title": dict(survey).get("title", "") if survey else "",
            "audience": dict(survey).get("target_audience", "") if survey else "",
            "total_responses": dict(response_count)["cnt"] if response_count else 0,
            "insights": [dict(i) for i in insights],
            "themes": [dict(t) for t in themes],
            "sentiment_data": [dict(s) for s in sentiments],
            "recommendations": [dict(r) for r in recommendations],
            "engagement": [dict(e) for e in engagement],
        }

        # Calculate summary statistics for context
        if context["sentiment_data"]:
            scores = [s.get("sentiment_score", 0) for s in context["sentiment_data"]]
            context["avg_sentiment"] = round(sum(scores) / len(scores), 3)
        else:
            context["avg_sentiment"] = 0

        context["theme_count"] = len(context["themes"])
        context["insight_count"] = len(context["insights"])
        context["recommendation_count"] = len(context["recommendations"])

        # Build the full prompt context
        prompt_parts = [
            f"Survey: {context['survey_title']}",
            f"Research Goal: {context['survey_goal']}",
            f"Target Audience: {context['audience']}",
            f"Total Responses: {context['total_responses']}",
            f"Themes Identified: {context['theme_count']}",
            f"Insights Generated: {context['insight_count']}",
            f"Recommendations Made: {context['recommendation_count']}",
            f"Average Sentiment: {context['avg_sentiment']}",
        ]
        context["full_prompt_context"] = "\n".join(prompt_parts)

        return context

    # ───────────────────────────────────────────────────────────
    # CHAT CONTEXT BUILDER
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def build_chat_context(session_id: str, survey_id: int,
                           message: str, history: list = None) -> dict:
        """
        Build context for interactive chat responses.
        Combines survey goal, conversation history, and semantic memory.
        """
        conn = get_db()

        # Survey context
        survey = conn.execute("""
            SELECT s.title, rg.parsed_goal, rg.target_audience
            FROM surveys s LEFT JOIN research_goals rg ON s.research_goal_id = rg.id
            WHERE s.id = ?
        """, (survey_id,)).fetchone()

        # Questions (for topic guidance)
        questions = conn.execute(
            "SELECT question_text FROM questions WHERE survey_id = ? ORDER BY order_index LIMIT 12",
            (survey_id,)
        ).fetchall()

        # Semantic memory
        memories = conn.execute("""
            SELECT entity, relation, value, confidence
            FROM semantic_memory WHERE session_id = ?
            ORDER BY confidence DESC LIMIT 10
        """, (session_id,)).fetchall()

        conn.close()

        context = {
            "research_goal": dict(survey).get("parsed_goal", "") if survey else "",
            "questions": [dict(q)["question_text"] for q in questions],
            "memory": [dict(m) for m in memories],
            "history": history or [],
            "message": message,
        }

        # Build survey_context dict expected by existing chat functions
        context["survey_context"] = {
            "research_goal": context["research_goal"],
            "questions": [{"question_text": q} for q in context["questions"]],
        }

        return context

    # ───────────────────────────────────────────────────────────
    # INTERNAL: Format context for prompt injection
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def _format_context_string(context: dict) -> str:
        """Format a context dict into a structured string for Gemini prompts."""
        parts = []

        if context.get("survey_goal"):
            parts.append(f"RESEARCH CONTEXT:\nSurvey Goal: {context['survey_goal']}")

        if context.get("audience"):
            parts.append(f"Target Audience: {context['audience']}")

        if context.get("objectives"):
            parts.append(f"Research Objectives: {', '.join(context['objectives'])}")

        if context.get("conversation_summary"):
            parts.append(f"\nCONVERSATION HISTORY:\n{context['conversation_summary']}")

        if context.get("semantic_memory"):
            mem_lines = []
            for m in context["semantic_memory"][:8]:
                mem_lines.append(f"- {m.get('entity', '')} {m.get('relation', '')} {m.get('value', '')}")
            parts.append(f"\nKNOWN FACTS ABOUT RESPONDENT:\n" + "\n".join(mem_lines))

        if context.get("existing_themes"):
            theme_lines = [f"- {t.get('name', '')}: {t.get('description', '')}" for t in context["existing_themes"][:6]]
            parts.append(f"\nEXISTING THEMES:\n" + "\n".join(theme_lines))

        if context.get("new_response"):
            parts.append(f"\nNEW RESPONSE TO ANALYZE:\n\"{context['new_response']}\"")

        return "\n".join(parts)
