"""
SQLite Database Setup for AI Survey Software
Handles all database initialization, connection management, and schema creation.
"""

import sqlite3
import os
import json
from datetime import datetime
from contextlib import contextmanager

def _resolve_data_dir() -> str:
    """Resolve persistent data directory with safe fallbacks.

    Priority:
    1) DATA_DIR env var (explicit override)
    2) /data (Railway persistent volume mount if configured)
    3) ../data (local/dev fallback)
    """
    env_data_dir = os.environ.get("DATA_DIR", "").strip()
    if env_data_dir:
        return env_data_dir

    if os.path.isdir("/data"):
        return "/data"

    return os.path.join(os.path.dirname(__file__), "..", "data")


_data_dir = _resolve_data_dir()
DB_PATH = os.path.join(_data_dir, "survey_engine.db")

# Track if WAL mode has been set this process
_wal_initialized = False


def get_db():
    """Get database connection with row factory (legacy - prefer get_db_connection context manager)."""
    global _wal_initialized
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    if not _wal_initialized:
        conn.execute("PRAGMA journal_mode=WAL")
        _wal_initialized = True
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db_connection():
    """Context manager for safe database connections. Always closes on exit."""
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    """Check whether a column exists on a SQLite table."""
    rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row[1] == column_name for row in rows)


def _delete_where_in(cursor, table_name: str, column_name: str, values: list):
    """Delete rows using a safe IN clause for variable-length identifiers."""
    if not values:
        return
    placeholders = ",".join("?" for _ in values)
    cursor.execute(f"DELETE FROM {table_name} WHERE {column_name} IN ({placeholders})", values)


def _cleanup_demo_surveys(cursor) -> int:
    """Remove known demo/fake surveys and dependent records from legacy databases."""
    table_rows = cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    tables = {row[0] for row in table_rows}
    if "surveys" not in tables:
        return 0

    demo_surveys = cursor.execute("""
        SELECT id, research_goal_id
        FROM surveys
        WHERE (
            LOWER(COALESCE(title, '')) LIKE '%demo%'
            OR LOWER(COALESCE(title, '')) LIKE '%sample%'
            OR LOWER(COALESCE(title, '')) LIKE '%fake%'
            OR LOWER(COALESCE(title, '')) IN (
                'quick test',
                'respondent feature test',
                'e2e test survey',
                'delete test survey',
                'smoke test survey'
            )
        )
        OR LOWER(COALESCE(title, '')) = 'app churn discovery interview'
        OR LOWER(COALESCE(description, '')) = 'ai-guided interview to discover why new users disengage'
    """).fetchall()

    if not demo_surveys:
        return 0

    deleted_count = 0
    goal_ids = set()

    for survey_id, goal_id in demo_surveys:
        if goal_id:
            goal_ids.add(goal_id)

        session_ids = []
        if "interview_sessions" in tables:
            session_rows = cursor.execute(
                "SELECT session_id FROM interview_sessions WHERE survey_id = ?",
                (survey_id,)
            ).fetchall()
            session_ids = [row[0] for row in session_rows]

        if session_ids:
            for table_name in ["semantic_memory", "response_segments", "voice_data", "conversation_history", "full_transcripts"]:
                if table_name in tables:
                    _delete_where_in(cursor, table_name, "session_id", session_ids)

            if "responses" in tables:
                response_rows = cursor.execute(
                    f"SELECT id FROM responses WHERE session_id IN ({','.join('?' for _ in session_ids)})",
                    session_ids
                ).fetchall()
                response_ids = [row[0] for row in response_rows]
                if response_ids and "sentiment_records" in tables and _column_exists(cursor, "sentiment_records", "response_id"):
                    _delete_where_in(cursor, "sentiment_records", "response_id", response_ids)
                _delete_where_in(cursor, "responses", "session_id", session_ids)

        survey_scoped_tables = [
            "survey_respondents",
            "chatbot_conversations",
            "survey_publications",
            "recommendations",
            "insights",
            "themes",
            "sentiment_records",
            "reports",
            "notifications",
            "engagement_metrics",
            "respondent_experience",
            "feature_usage",
            "llm_usage",
            "conversation_flow",
            "questions",
            "interview_sessions",
        ]
        for table_name in survey_scoped_tables:
            if table_name in tables:
                cursor.execute(f"DELETE FROM {table_name} WHERE survey_id = ?", (survey_id,))

        cursor.execute("DELETE FROM surveys WHERE id = ?", (survey_id,))
        deleted_count += 1

    # Remove orphaned demo goals only when they are no longer linked to any survey.
    if "research_goals" in tables:
        for goal_id in goal_ids:
            linked_surveys = cursor.execute(
                "SELECT COUNT(*) FROM surveys WHERE research_goal_id = ?",
                (goal_id,)
            ).fetchone()[0]
            if linked_surveys:
                continue

            goal = cursor.execute(
                "SELECT title, description FROM research_goals WHERE id = ?",
                (goal_id,)
            ).fetchone()
            if not goal:
                continue

            title = (goal[0] or "").lower()
            description = (goal[1] or "").lower()
            if (
                title == "user churn analysis"
                or "demo" in title
                or "sample" in title
                or "fake" in title
                or "test" in title
                or "demo" in description
            ):
                cursor.execute("DELETE FROM research_goals WHERE id = ?", (goal_id,))

    return deleted_count


def init_db():
    """Initialize all database tables."""
    conn = get_db()
    cursor = conn.cursor()

    # ── Users & Authentication ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'pm',
            avatar_url TEXT,
            is_active INTEGER DEFAULT 1,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Feature 1: Survey Designer Tables ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            research_type TEXT DEFAULT 'discovery',
            problem_space TEXT,
            target_outcome TEXT,
            target_audience TEXT,
            success_criteria TEXT,
            estimated_duration INTEGER DEFAULT 5,
            quality_score REAL DEFAULT 0,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS surveys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            research_goal_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'draft',
            channel_type TEXT DEFAULT 'web',
            estimated_duration INTEGER DEFAULT 5,
            interview_style TEXT DEFAULT 'balanced',
            total_responses INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (research_goal_id) REFERENCES research_goals(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT DEFAULT 'open_ended',
            options TEXT,
            order_index INTEGER DEFAULT 0,
            is_required INTEGER DEFAULT 1,
            conditional_logic TEXT,
            follow_up_seeds TEXT,
            tone TEXT DEFAULT 'neutral',
            depth_level INTEGER DEFAULT 1,
            audience_tag TEXT DEFAULT 'general',
            bias_score REAL DEFAULT 0,
            clarity_score REAL DEFAULT 0,
            insight_probability REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_flow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            node_id TEXT NOT NULL,
            topic TEXT,
            parent_node_id TEXT,
            question_id INTEGER,
            condition_type TEXT,
            condition_value TEXT,
            depth_level INTEGER DEFAULT 1,
            priority_score REAL DEFAULT 0,
            followups TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )
    """)

    # ── Feature 2 & 5: Interview / Response Collection Tables ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interview_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            respondent_id TEXT NOT NULL,
            session_id TEXT UNIQUE NOT NULL,
            channel TEXT DEFAULT 'web',
            status TEXT DEFAULT 'active',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            engagement_score REAL DEFAULT 0,
            completion_percentage REAL DEFAULT 0,
            device_type TEXT,
            language TEXT DEFAULT 'en',
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            question_id INTEGER,
            response_text TEXT,
            response_type TEXT DEFAULT 'text',
            emoji_data TEXT,
            voice_metadata TEXT,
            sentiment_score REAL,
            emotion TEXT,
            intent TEXT,
            confidence REAL,
            quality_score REAL DEFAULT 0,
            response_time_ms INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id),
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            message_type TEXT DEFAULT 'text',
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id)
        )
    """)

    # ── Feature 3: Insight Engine Tables ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            frequency INTEGER DEFAULT 0,
            sentiment_avg REAL DEFAULT 0,
            emotion_intensity REAL DEFAULT 0,
            priority TEXT DEFAULT 'medium',
            business_risk TEXT DEFAULT 'low',
            is_emerging INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER,
            theme_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            insight_type TEXT DEFAULT 'observation',
            feature_area TEXT,
            sentiment TEXT DEFAULT 'neutral',
            emotion TEXT,
            confidence REAL DEFAULT 0,
            impact_score REAL DEFAULT 0,
            frequency INTEGER DEFAULT 0,
            user_segments TEXT,
            supporting_responses TEXT,
            is_contradiction INTEGER DEFAULT 0,
            is_emerging INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id),
            FOREIGN KEY (theme_id) REFERENCES themes(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sentiment_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER,
            survey_id INTEGER,
            sentiment_label TEXT,
            sentiment_score REAL,
            emotion TEXT,
            emotion_intensity REAL,
            feature_area TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (response_id) REFERENCES responses(id),
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    """)

    # ── Feature 4: Reports & Recommendations Tables ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER,
            title TEXT NOT NULL,
            executive_summary TEXT,
            summary_tone TEXT DEFAULT 'neutral',
            summary_length TEXT DEFAULT 'medium',
            narrative_flow TEXT,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER,
            insight_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            action_type TEXT DEFAULT 'improvement',
            impact_score REAL DEFAULT 0,
            effort_score REAL DEFAULT 0,
            urgency_score REAL DEFAULT 0,
            priority_score REAL DEFAULT 0,
            confidence REAL DEFAULT 0,
            timeframe TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            supporting_count INTEGER DEFAULT 0,
            user_segments TEXT,
            export_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id),
            FOREIGN KEY (insight_id) REFERENCES insights(id)
        )
    """)

    # ── Feature 5: Notifications & Alerts ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER,
            type TEXT DEFAULT 'info',
            title TEXT NOT NULL,
            message TEXT,
            severity TEXT DEFAULT 'low',
            is_read INTEGER DEFAULT 0,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS engagement_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER,
            channel TEXT,
            total_sessions INTEGER DEFAULT 0,
            completed_sessions INTEGER DEFAULT 0,
            avg_completion_time REAL DEFAULT 0,
            avg_response_quality REAL DEFAULT 0,
            drop_off_rate REAL DEFAULT 0,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    """)

    # ── Voice Data Table (separate from responses) ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS voice_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER,
            session_id TEXT,
            audio_url TEXT,
            transcript TEXT,
            confidence REAL,
            duration_ms INTEGER,
            language TEXT DEFAULT 'en',
            highlights TEXT,
            assemblyai_sentiments TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (response_id) REFERENCES responses(id),
            FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id)
        )
    """)

    # ── Response Segments Table (multi-topic segmentation) ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS response_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER NOT NULL,
            session_id TEXT,
            segment_text TEXT NOT NULL,
            topic TEXT,
            sentiment_label TEXT,
            sentiment_score REAL,
            emotion TEXT,
            confidence REAL DEFAULT 0,
            order_index INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (response_id) REFERENCES responses(id),
            FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id)
        )
    """)

    # ── Semantic Memory Graph ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semantic_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            entity TEXT NOT NULL,
            relation TEXT,
            value TEXT,
            confidence REAL DEFAULT 0.8,
            source_response_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id),
            FOREIGN KEY (source_response_id) REFERENCES responses(id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # ARCHITECTURE: AI Metadata Tracking
    # Logs every AI call for observability & cost tracking
    # ═══════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_hash TEXT,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            success INTEGER DEFAULT 1,
            cached INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ═══════════════════════════════════════════════════
    # ARCHITECTURE: Event Log
    # Persists all system events for audit trail & replay
    # ═══════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT,
            source TEXT DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ═══════════════════════════════════════════════════
    # ARCHITECTURE: Indexes for performance
    # ═══════════════════════════════════════════════════
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_metadata_task ON ai_metadata(task_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_metadata_created ON ai_metadata(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_log(event_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_log_created ON event_log(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_responses_session ON responses(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_survey ON interview_sessions(survey_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_themes_survey ON themes(survey_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_insights_survey ON insights(survey_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_survey ON sentiment_records(survey_id)")

    # ═══════════════════════════════════════════════════
    # AI PROCESSING ARCHITECTURE: Human-in-the-Loop Corrections
    # Tracks manual corrections to AI outputs for learning
    # ═══════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hitl_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            original_data TEXT,
            corrected_data TEXT,
            correction_type TEXT NOT NULL,
            corrected_by TEXT DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ═══════════════════════════════════════════════════
    # AI PROCESSING ARCHITECTURE: Pipeline Execution Log
    # Tracks every pipeline execution for audit + optimization
    # ═══════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_name TEXT NOT NULL,
            task_type TEXT NOT NULL,
            survey_id INTEGER,
            session_id TEXT,
            latency_ms INTEGER DEFAULT 0,
            success INTEGER DEFAULT 1,
            result_summary TEXT,
            context_keys TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Indexes for new tables
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hitl_entity ON hitl_corrections(entity_type, entity_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hitl_created ON hitl_corrections(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_exec_name ON pipeline_executions(pipeline_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_exec_survey ON pipeline_executions(survey_id)")

    # ═══════════════════════════════════════════════════
    # SURVEY PUBLICATIONS — Published surveys with share links
    # Tracks draft → active → closed lifecycle
    # ═══════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS survey_publications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            share_code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'draft',
            audience_label TEXT DEFAULT 'general',
            web_form_enabled INTEGER DEFAULT 1,
            chat_enabled INTEGER DEFAULT 1,
            audio_enabled INTEGER DEFAULT 1,
            max_responses INTEGER DEFAULT 0,
            require_email INTEGER DEFAULT 1,
            consent_form_text TEXT DEFAULT '',
            published_at TIMESTAMP,
            closed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # RESPONDENTS — Track every respondent by Google email
    # Links respondents to surveys + stores metadata
    # ═══════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS respondents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            name TEXT,
            avatar_url TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_respondents_email ON respondents(email)")

    # ═══════════════════════════════════════════════════
    # SURVEY_RESPONDENTS — Many-to-many: respondent ↔ survey
    # Tracks which respondents took which surveys
    # ═══════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS survey_respondents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            publication_id INTEGER,
            respondent_id INTEGER NOT NULL,
            session_id TEXT,
            channel TEXT DEFAULT 'web',
            status TEXT DEFAULT 'started',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id),
            FOREIGN KEY (publication_id) REFERENCES survey_publications(id),
            FOREIGN KEY (respondent_id) REFERENCES respondents(id),
            FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # FULL TRANSCRIPTS — Complete interview transcripts per session
    # Stores the entire Q&A flow for group-level analysis
    # ═══════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS full_transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            survey_id INTEGER NOT NULL,
            respondent_id INTEGER,
            transcript_json TEXT NOT NULL,
            ai_report_json TEXT,
            summary TEXT,
            word_count INTEGER DEFAULT 0,
            duration_seconds INTEGER DEFAULT 0,
            sentiment_overall REAL,
            key_topics TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id),
            FOREIGN KEY (survey_id) REFERENCES surveys(id),
            FOREIGN KEY (respondent_id) REFERENCES respondents(id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # SURVEY ANALYSIS CHATBOT — Conversation history
    # Stores user questions and AI answers about survey data
    # ═══════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chatbot_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            user_id INTEGER,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Indexes for new publication/respondent tables
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_publications_survey ON survey_publications(survey_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_publications_code ON survey_publications(share_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_publications_user ON survey_publications(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_survey_resp_survey ON survey_respondents(survey_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_survey_resp_respondent ON survey_respondents(respondent_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_survey ON full_transcripts(survey_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_session ON full_transcripts(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chatbot_conv_survey ON chatbot_conversations(survey_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chatbot_conv_id ON chatbot_conversations(conversation_id)")

    # ═══════════════════════════════════════════════════
    # COLLABORATIVE ANNOTATIONS
    # Team members can annotate insights and chatbot messages
    # ═══════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            user_id INTEGER,
            user_name TEXT,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            content TEXT NOT NULL,
            color TEXT DEFAULT '#fbbf24',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_annotations_survey ON annotations(survey_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_annotations_target ON annotations(target_type, target_id)")

    # ═══════════════════════════════════════════════════
    # PLATFORM GOVERNANCE — Flags, Experiments, Prompt Registry
    # ═══════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feature_flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            description TEXT,
            is_enabled INTEGER DEFAULT 0,
            rollout_percentage INTEGER DEFAULT 100,
            conditions_json TEXT DEFAULT '{}',
            target_scope TEXT DEFAULT 'global',
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feature_flags_key ON feature_flags(key)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ab_experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            feature_flag_key TEXT,
            status TEXT DEFAULT 'draft',
            start_at TIMESTAMP,
            end_at TIMESTAMP,
            variants_json TEXT DEFAULT '[]',
            allocation_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (feature_flag_key) REFERENCES feature_flags(key)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_experiments_status ON ab_experiments(status)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiment_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL,
            user_key TEXT NOT NULL,
            variant TEXT NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(experiment_id, user_key),
            FOREIGN KEY (experiment_id) REFERENCES ab_experiments(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exp_assign_experiment ON experiment_assignments(experiment_id)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompt_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            version INTEGER NOT NULL,
            prompt_text TEXT NOT NULL,
            metadata_json TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, version),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompt_versions_name ON prompt_versions(name)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_version_id INTEGER,
            feature_name TEXT,
            model_name TEXT,
            input_hash TEXT,
            output_hash TEXT,
            latency_ms INTEGER DEFAULT 0,
            success INTEGER DEFAULT 1,
            error_message TEXT,
            survey_id INTEGER,
            session_id TEXT,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions(id),
            FOREIGN KEY (survey_id) REFERENCES surveys(id),
            FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_runs_feature ON model_runs(feature_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_runs_created ON model_runs(created_at)")

    # ═══════════════════════════════════════════════════
    # LLM USAGE, AUDIT, AND JOB DURABILITY
    # ═══════════════════════════════════════════════════
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT,
            feature_name TEXT,
            model_name TEXT,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            success INTEGER DEFAULT 1,
            error_message TEXT,
            survey_id INTEGER,
            session_id TEXT,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id),
            FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_created ON llm_usage(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_feature ON llm_usage(feature_name)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_trail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            path TEXT,
            method TEXT,
            status_code INTEGER,
            ip_address TEXT,
            user_agent TEXT,
            metadata_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_trail(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_trail(user_id)")

    # ═══════════════════════════════════════════════════
    # OWNERSHIP MIGRATION — Per-user survey/goal ownership
    # ═══════════════════════════════════════════════════
    if not _column_exists(cursor, "research_goals", "owner_user_id"):
        cursor.execute("ALTER TABLE research_goals ADD COLUMN owner_user_id INTEGER")

    if not _column_exists(cursor, "surveys", "owner_user_id"):
        cursor.execute("ALTER TABLE surveys ADD COLUMN owner_user_id INTEGER")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_research_goals_owner ON research_goals(owner_user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_surveys_owner ON surveys(owner_user_id)")

    # Backfill legacy surveys from publication owner.
    cursor.execute("""
        UPDATE surveys
        SET owner_user_id = (
            SELECT sp.user_id
            FROM survey_publications sp
            WHERE sp.survey_id = surveys.id
            ORDER BY sp.created_at ASC
            LIMIT 1
        )
        WHERE owner_user_id IS NULL
    """)

    # Backfill legacy goals from associated survey owners.
    cursor.execute("""
        UPDATE research_goals
        SET owner_user_id = (
            SELECT s.owner_user_id
            FROM surveys s
            WHERE s.research_goal_id = research_goals.id
              AND s.owner_user_id IS NOT NULL
            ORDER BY s.created_at ASC
            LIMIT 1
        )
        WHERE owner_user_id IS NULL
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type TEXT NOT NULL,
            status TEXT DEFAULT 'queued',
            payload_json TEXT DEFAULT '{}',
            result_json TEXT,
            error_message TEXT,
            attempt_count INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3,
            run_at TIMESTAMP,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_runat ON jobs(status, run_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            attempt_number INTEGER NOT NULL,
            status TEXT,
            error_message TEXT,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_attempts_job ON job_attempts(job_id)")

    # ── Safe migrations for existing databases ──
    try:
        cursor.execute("ALTER TABLE questions ADD COLUMN audience_tag TEXT DEFAULT 'general'")
    except Exception:
        pass  # Column already exists
    try:
        cursor.execute("ALTER TABLE survey_publications ADD COLUMN audience_label TEXT DEFAULT 'general'")
    except Exception:
        pass  # Column already exists
    try:
        cursor.execute("ALTER TABLE surveys ADD COLUMN interview_style TEXT DEFAULT 'balanced'")
    except Exception:
        pass  # Column already exists

    # ═══════════════════════════════════════════════════
    # ANALYTICS & FEEDBACK SYSTEM
    # ═══════════════════════════════════════════════════
    
    # Website Visit Tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS website_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id TEXT,
            page_url TEXT NOT NULL,
            page_title TEXT,
            referrer TEXT,
            user_agent TEXT,
            ip_address TEXT,
            country TEXT,
            device_type TEXT,
            browser TEXT,
            time_on_page INTEGER DEFAULT 0,
            exit_page INTEGER DEFAULT 0,
            conversion_event TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_created ON website_analytics(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_user ON website_analytics(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_session ON website_analytics(session_id)")

    # User Feedback about the Software
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            feedback_type TEXT DEFAULT 'general',
            rating INTEGER,
            title TEXT,
            description TEXT NOT NULL,
            feature_area TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'open',
            browser_info TEXT,
            url_context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_feedback_created ON user_feedback(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_feedback_type ON user_feedback(feedback_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_feedback_status ON user_feedback(status)")

    # Respondent Experience Feedback (30-second max)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS respondent_experience (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            survey_id INTEGER NOT NULL,
            respondent_id INTEGER,
            overall_rating INTEGER,
            easiness_rating INTEGER,
            clarity_rating INTEGER,
            time_rating INTEGER,
            technical_issues INTEGER DEFAULT 0,
            would_recommend INTEGER,
            quick_feedback TEXT,
            improvement_suggestion TEXT,
            completion_time INTEGER,
            device_type TEXT,
            channel_used TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id),
            FOREIGN KEY (survey_id) REFERENCES surveys(id),
            FOREIGN KEY (respondent_id) REFERENCES respondents(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resp_exp_survey ON respondent_experience(survey_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resp_exp_session ON respondent_experience(session_id)")

    # Survey Feature Usage Analytics
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feature_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            survey_id INTEGER,
            feature_name TEXT NOT NULL,
            action TEXT NOT NULL,
            metadata_json TEXT DEFAULT '{}',
            session_duration INTEGER,
            success INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feature_usage_feature ON feature_usage(feature_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feature_usage_user ON feature_usage(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feature_usage_created ON feature_usage(created_at)")

    # Daily Analytics Summary (for dashboard efficiency)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_recorded DATE UNIQUE NOT NULL,
            total_users INTEGER DEFAULT 0,
            active_users INTEGER DEFAULT 0,
            new_signups INTEGER DEFAULT 0,
            surveys_created INTEGER DEFAULT 0,
            surveys_published INTEGER DEFAULT 0,
            responses_collected INTEGER DEFAULT 0,
            page_views INTEGER DEFAULT 0,
            unique_visitors INTEGER DEFAULT 0,
            avg_session_duration REAL DEFAULT 0,
            conversion_rate REAL DEFAULT 0,
            user_feedback_count INTEGER DEFAULT 0,
            avg_user_satisfaction REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(date_recorded)")

    removed_demo_count = _cleanup_demo_surveys(cursor)

    conn.commit()
    conn.close()
    if removed_demo_count:
        print(f"Removed {removed_demo_count} demo/fake surveys during initialization.")
    print("Database initialized successfully.")


if __name__ == "__main__":
    init_db()
