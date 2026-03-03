"""
Response Service — Application Services Layer
═══════════════════════════════════════════════════════
Response Ingestion Pipeline:
  Raw Response → Channel Tagged → Timestamped → Validated → Stored → Event Published

Responsibilities:
  - Response ingestion and normalization
  - Metadata tagging (channel, device, language)
  - Data anonymization (optional)
  - Event publishing for background AI processing
"""
import re
import json
import hashlib
from datetime import datetime
from typing import Optional
from ..database import get_db
from ..services.event_bus import event_bus, Event, EventType
from ..config import ANONYMIZE_RESPONSES


class ResponseService:
    """Response ingestion, normalization, and metadata tagging."""

    @staticmethod
    def ingest_response(session_id: str, response_text: str, question_id: int = None,
                        response_type: str = "text", emoji_data: str = None,
                        voice_metadata: str = None, response_time_ms: int = None) -> dict:
        """
        Full response ingestion pipeline:
        1. Validate & normalize text
        2. Apply anonymization if enabled
        3. Store to database
        4. Publish RESPONSE_SUBMITTED event for background AI processing
        """
        # ── Step 1: Normalize ──
        normalized_text = ResponseService._normalize_text(response_text)
        if not normalized_text:
            return {"error": "Empty response after normalization"}

        # ── Step 2: Anonymize if configured ──
        if ANONYMIZE_RESPONSES:
            normalized_text = ResponseService._anonymize(normalized_text)

        # ── Step 3: Get session info for context ──
        conn = get_db()
        session = conn.execute(
            "SELECT survey_id, channel FROM interview_sessions WHERE session_id = ?",
            (session_id,)
        ).fetchone()

        if not session:
            conn.close()
            return {"error": "Session not found"}

        session_dict = dict(session)
        survey_id = session_dict["survey_id"]

        # ── Step 4: Store response ──
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO responses (session_id, question_id, response_text, response_type,
                emoji_data, voice_metadata, response_time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session_id, question_id, normalized_text, response_type,
              emoji_data, voice_metadata, response_time_ms))
        conn.commit()
        response_id = cursor.lastrowid
        conn.close()

        # ── Step 5: Publish event for async AI processing ──
        event_bus.publish(Event(
            EventType.RESPONSE_SUBMITTED,
            {
                "response_id": response_id,
                "session_id": session_id,
                "survey_id": survey_id,
                "response_text": normalized_text,
                "response_type": response_type,
                "question_id": question_id,
                "channel": session_dict.get("channel", "web"),
            },
            source="response_service"
        ))

        return {
            "response_id": response_id,
            "message": "Response recorded",
            "processing": "background"
        }

    @staticmethod
    def get_session_responses(session_id: str) -> list:
        """Get all responses for a session."""
        conn = get_db()
        responses = conn.execute(
            "SELECT * FROM responses WHERE session_id = ? ORDER BY created_at",
            (session_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in responses]

    @staticmethod
    def get_survey_responses(survey_id: int, limit: int = 100) -> list:
        """Get all responses for a survey across all sessions."""
        conn = get_db()
        responses = conn.execute("""
            SELECT r.*, s.channel, s.survey_id
            FROM responses r
            JOIN interview_sessions s ON r.session_id = s.session_id
            WHERE s.survey_id = ?
            ORDER BY r.created_at DESC
            LIMIT ?
        """, (survey_id, limit)).fetchall()
        conn.close()
        return [dict(r) for r in responses]

    @staticmethod
    def get_response_stats(survey_id: int) -> dict:
        """Get response statistics for a survey."""
        conn = get_db()
        stats = conn.execute("""
            SELECT
                COUNT(*) as total_responses,
                COUNT(DISTINCT r.session_id) as unique_sessions,
                AVG(r.quality_score) as avg_quality,
                AVG(r.sentiment_score) as avg_sentiment,
                COUNT(CASE WHEN r.response_type = 'voice' THEN 1 END) as voice_count,
                COUNT(CASE WHEN r.response_type = 'text' THEN 1 END) as text_count,
                COUNT(CASE WHEN r.response_type = 'emoji' THEN 1 END) as emoji_count
            FROM responses r
            JOIN interview_sessions s ON r.session_id = s.session_id
            WHERE s.survey_id = ?
        """, (survey_id,)).fetchone()
        conn.close()
        return dict(stats) if stats else {}

    # ─── Private Helpers ───
    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize response text: trim, collapse whitespace, remove control chars."""
        if not text:
            return ""
        # Remove control characters except newlines
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        # Collapse excessive whitespace
        text = re.sub(r' {3,}', '  ', text)
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        return text.strip()

    @staticmethod
    def _anonymize(text: str) -> str:
        """
        Remove PII from response text:
        - Email addresses → [EMAIL]
        - Phone numbers → [PHONE]
        - Names preceded by "I'm" or "my name is" → [NAME]
        """
        # Emails
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
        # Phone numbers (various formats)
        text = re.sub(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b', '[PHONE]', text)
        # Names after common patterns
        text = re.sub(r"(?:I'm|I am|my name is|name's)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                      lambda m: m.group(0).replace(m.group(1), '[NAME]'), text, flags=re.IGNORECASE)
        return text
