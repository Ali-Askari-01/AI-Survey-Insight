"""
Survey Service — Application Services Layer
═══════════════════════════════════════════════════════
Encapsulates all survey business logic.
Routes call this service; this service calls the database and AI orchestrator.

Responsibilities:
  - Survey CRUD with validation
  - Research goal management
  - Question generation coordination
  - Survey template management
  - Conditional logic handling
"""
from datetime import datetime
from typing import Optional, List
from ..database import get_db
from ..services.ai_orchestrator import AIOrchestrator
from ..services.event_bus import event_bus, Event, EventType


class SurveyService:
    """Business logic for surveys, goals, and questions."""

    # ─── Research Goals ───
    @staticmethod
    def create_goal(title: str, description: str = None, research_type: str = "discovery",
                    problem_space: str = None, target_outcome: str = None,
                    target_audience: str = None, success_criteria: str = None,
                    estimated_duration: int = 5) -> dict:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO research_goals (title, description, research_type, problem_space,
                target_outcome, target_audience, success_criteria, estimated_duration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, description, research_type, problem_space,
              target_outcome, target_audience, success_criteria, estimated_duration))
        conn.commit()
        goal_id = cursor.lastrowid
        conn.close()
        return {"id": goal_id, "message": "Research goal created"}

    @staticmethod
    def get_goal(goal_id: int) -> Optional[dict]:
        conn = get_db()
        goal = conn.execute("SELECT * FROM research_goals WHERE id = ?", (goal_id,)).fetchone()
        conn.close()
        return dict(goal) if goal else None

    @staticmethod
    def list_goals() -> list:
        conn = get_db()
        goals = conn.execute("SELECT * FROM research_goals ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(g) for g in goals]

    @staticmethod
    def ai_parse_goal(user_input: str) -> dict:
        """AI parses natural language into a structured research goal."""
        from ..services.ai_service import AIService
        return AIOrchestrator.execute(
            "goal_parsing",
            f"parse_goal:{user_input[:300]}",
            AIService.parse_research_goal,
            user_input,
            cacheable=True
        )

    # ─── Surveys ───
    @staticmethod
    def create_survey(research_goal_id: int = None, title: str = "",
                      description: str = None, channel_type: str = "web",
                      estimated_duration: int = 5,
                      interview_style: str = "balanced") -> dict:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO surveys (research_goal_id, title, description, channel_type, estimated_duration, interview_style)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (research_goal_id, title, description, channel_type, estimated_duration, interview_style))
        conn.commit()
        survey_id = cursor.lastrowid
        conn.close()

        # Publish event
        event_bus.publish(Event(
            EventType.SURVEY_CREATED,
            {"survey_id": survey_id, "title": title, "channel_type": channel_type},
            source="survey_service"
        ))

        return {"id": survey_id, "message": "Survey created"}

    @staticmethod
    def get_survey(survey_id: int) -> Optional[dict]:
        conn = get_db()
        survey = conn.execute("SELECT * FROM surveys WHERE id = ?", (survey_id,)).fetchone()
        if not survey:
            conn.close()
            return None
        questions = conn.execute(
            "SELECT * FROM questions WHERE survey_id = ? ORDER BY order_index",
            (survey_id,)
        ).fetchall()
        conn.close()
        return {**dict(survey), "questions": [dict(q) for q in questions]}

    @staticmethod
    def list_surveys() -> list:
        conn = get_db()
        surveys = conn.execute("SELECT * FROM surveys ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(s) for s in surveys]

    @staticmethod
    def get_survey_context(survey_id: int) -> dict:
        """Get full context of a survey for AI prompts."""
        conn = get_db()
        survey = conn.execute("SELECT * FROM surveys WHERE id = ?", (survey_id,)).fetchone()
        if not survey:
            conn.close()
            return {}
        survey_dict = dict(survey)

        # Research goal
        goal = None
        if survey_dict.get("research_goal_id"):
            g = conn.execute("SELECT * FROM research_goals WHERE id = ?",
                             (survey_dict["research_goal_id"],)).fetchone()
            if g:
                goal = dict(g)

        # Questions
        questions = conn.execute(
            "SELECT * FROM questions WHERE survey_id = ? ORDER BY order_index",
            (survey_id,)
        ).fetchall()

        # Themes
        themes = conn.execute(
            "SELECT * FROM themes WHERE survey_id = ?",
            (survey_id,)
        ).fetchall()

        conn.close()

        return {
            "survey": survey_dict,
            "research_goal": goal,
            "questions": [dict(q) for q in questions],
            "themes": [dict(t) for t in themes],
        }

    # ─── Questions ───
    @staticmethod
    def create_question(survey_id: int, question_text: str, question_type: str = "open_ended",
                        options: str = None, order_index: int = 0, is_required: bool = True,
                        conditional_logic: str = None, follow_up_seeds: str = None,
                        tone: str = "neutral", depth_level: int = 1) -> dict:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO questions (survey_id, question_text, question_type, options, order_index,
                is_required, conditional_logic, follow_up_seeds, tone, depth_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (survey_id, question_text, question_type, options, order_index,
              1 if is_required else 0, conditional_logic, follow_up_seeds, tone, depth_level))
        conn.commit()
        q_id = cursor.lastrowid
        conn.close()
        return {"id": q_id, "message": "Question created"}

    @staticmethod
    def ai_generate_questions(research_goal_id: int, count: int = 5) -> dict:
        """AI generates contextual questions for a research goal."""
        from ..services.ai_service import AIService
        goal = SurveyService.get_goal(research_goal_id)
        if not goal:
            return {"error": "Research goal not found"}

        questions = AIOrchestrator.execute(
            "question_generation",
            f"gen_questions:{goal.get('research_type', '')}:{count}",
            AIService.generate_questions,
            goal["research_type"], count,
            cacheable=True
        )

        # Publish event
        event_bus.publish(Event(
            EventType.QUESTIONS_GENERATED,
            {"research_goal_id": research_goal_id, "count": len(questions) if isinstance(questions, list) else 0},
            source="survey_service"
        ))

        return {"questions": questions}

    @staticmethod
    def ai_generate_deep_questions(goal_text: str, research_type: str = "discovery",
                                    count: int = 8) -> dict:
        """AI generates in-depth questions with follow-ups and analysis."""
        from ..services.ai_service import AIService
        return AIOrchestrator.execute(
            "deep_question_generation",
            f"deep_gen:{goal_text[:200]}:{research_type}:{count}",
            AIService.generate_deep_questions,
            goal_text, research_type, count,
            cacheable=True
        )

    @staticmethod
    def ai_intake_clarify(user_input: str, conversation: list) -> dict:
        """Multi-step AI intake: AI asks clarifying questions."""
        from ..services.ai_service import AIService
        return AIOrchestrator.execute(
            "intake_clarification",
            f"intake:{user_input[:200]}:{len(conversation)}",
            AIService.generate_intake_clarification,
            user_input, conversation,
            cacheable=False
        )

    @staticmethod
    def ai_generate_audience_targeted(goal_text: str, target_audiences: list,
                                       research_type: str = "discovery",
                                       count_per_audience: int = 6) -> dict:
        """AI generates audience-specific questions for each target audience + generic."""
        from ..services.ai_service import AIService
        audiences_key = ",".join(sorted(target_audiences))
        return AIOrchestrator.execute(
            "audience_targeted_generation",
            f"aud_gen:{goal_text[:150]}:{audiences_key}:{count_per_audience}",
            AIService.generate_audience_targeted_questions,
            goal_text, target_audiences, research_type, count_per_audience,
            cacheable=True
        )
