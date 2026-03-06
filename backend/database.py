"""
SQLite Database Setup for AI Survey Software
Handles all database initialization, connection management, and schema creation.
"""

import sqlite3
import os
import json
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "survey_engine.db")

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

    conn.commit()
    conn.close()
    print("Database initialized successfully.")


def seed_demo_data():
    """Seed database with demo data for all features."""
    conn = get_db()
    cursor = conn.cursor()

    # Check if data exists
    cursor.execute("SELECT COUNT(*) FROM surveys")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    # Research Goal
    cursor.execute("""
        INSERT INTO research_goals (title, description, research_type, problem_space, target_outcome, target_audience, success_criteria, estimated_duration, quality_score, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "User Churn Analysis",
        "Understand why users stop using the mobile app after the first week",
        "discovery",
        "User retention and onboarding",
        "Identify top 3 friction points causing early churn",
        "Users who signed up in last 30 days but became inactive",
        "Identify 3+ recurring onboarding friction points with 85%+ confidence",
        6, 91.0, "active"
    ))

    # Survey
    cursor.execute("""
        INSERT INTO surveys (research_goal_id, title, description, status, channel_type, estimated_duration, interview_style, total_responses)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        1, "App Churn Discovery Interview",
        "AI-guided interview to discover why new users disengage",
        "active", "multi", 6, 'balanced', 247
    ))

    # Questions
    questions_data = [
        ("Tell me about your first experience using the app.", "open_ended", None, 0, 1, None, '["why", "example", "emotion"]', "friendly", 1),
        ("What were you trying to accomplish?", "open_ended", None, 1, 1, None, '["impact", "expectation"]', "neutral", 1),
        ("Did you face any issues during checkout?", "yes_no", '["Yes", "No"]', 2, 1, '{"yes": 4, "no": 5}', '["describe", "frequency"]', "neutral", 2),
        ("Please describe what happened during checkout.", "open_ended", None, 3, 1, '{"parent": 3, "condition": "yes"}', '["emotion", "impact"]', "empathetic", 3),
        ("How would you rate the overall onboarding experience?", "rating", '["1","2","3","4","5"]', 4, 1, None, '["why", "improvement"]', "neutral", 1),
        ("What would make you come back to using the app?", "open_ended", None, 5, 0, None, '["priority", "example"]', "encouraging", 2),
        ("Is there anything else you'd like to share?", "open_ended", None, 6, 0, None, '["reflection"]', "warm", 1),
    ]
    for q in questions_data:
        cursor.execute("""
            INSERT INTO questions (survey_id, question_text, question_type, options, order_index, is_required, conditional_logic, follow_up_seeds, tone, depth_level)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, q)

    # Themes
    themes_data = [
        ("Checkout Failures", "Users report checkout freezing or failing", 134, -0.72, 0.85, "high", "high", 0),
        ("Onboarding Confusion", "New users find setup steps unclear", 98, -0.55, 0.65, "high", "medium", 0),
        ("Slow Performance", "App lag and loading delays", 76, -0.62, 0.70, "medium", "medium", 0),
        ("UI Navigation Issues", "Users struggle finding features", 54, -0.45, 0.50, "medium", "low", 0),
        ("Positive UX Elements", "Users praise visual design and simplicity", 43, 0.78, 0.60, "low", "low", 0),
        ("Payment Method Gaps", "Missing preferred payment options", 38, -0.58, 0.55, "medium", "medium", 1),
        ("Tutorial Effectiveness", "Mixed feedback on tutorial usefulness", 29, -0.15, 0.30, "low", "low", 0),
        ("Feature Requests", "Users requesting new capabilities", 25, 0.35, 0.40, "low", "low", 0),
    ]
    for t in themes_data:
        cursor.execute("""
            INSERT INTO themes (survey_id, name, description, frequency, sentiment_avg, emotion_intensity, priority, business_risk, is_emerging)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
        """, t)

    # Insights
    insights_data = [
        (1, "Checkout Freeze Causes 50% Drop-off", "Half of new users abandon at checkout due to freezing", "pain_point", "Checkout", "negative", "frustration", 0.92, 0.95, 134, '["new_users", "mobile"]'),
        (2, "Onboarding Steps Unclear for New Users", "Setup wizard skips critical instructions", "pain_point", "Onboarding", "negative", "confusion", 0.87, 0.82, 98, '["new_users"]'),
        (3, "App Performance Degrades Under Load", "Loading times exceed 5s during peak hours", "observation", "Performance", "negative", "frustration", 0.85, 0.78, 76, '["all_users"]'),
        (4, "Navigation Structure Not Intuitive", "Key features buried in submenus", "suggestion", "UI/UX", "negative", "confusion", 0.78, 0.65, 54, '["power_users"]'),
        (5, "Visual Design Praised by Users", "Clean aesthetics and color scheme appreciated", "positive", "UI/UX", "positive", "satisfaction", 0.90, 0.30, 43, '["all_users"]'),
        (6, "JazzCash/EasyPaisa Payment Not Supported", "Local payment methods missing, causing abandonment", "pain_point", "Payment", "negative", "disappointment", 0.88, 0.85, 38, '["local_users"]'),
    ]
    for ins in insights_data:
        cursor.execute("""
            INSERT INTO insights (survey_id, theme_id, title, description, insight_type, feature_area, sentiment, emotion, confidence, impact_score, frequency, user_segments)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ins)

    # Recommendations
    recs_data = [
        (1, "Optimize Checkout Backend", "Fix checkout freezing by optimizing payment gateway and adding timeout handling", "fix", 0.95, 0.60, 0.95, 0.95, 0.92, "short", 134, '["new_users", "mobile"]'),
        (2, "Redesign Onboarding Wizard", "Simplify setup steps and add progress indicators", "improvement", 0.82, 0.50, 0.80, 0.85, 0.87, "medium", 98, '["new_users"]'),
        (3, "Add Performance Monitoring", "Implement server-side caching and CDN for static assets", "improvement", 0.78, 0.70, 0.70, 0.72, 0.85, "medium", 76, '["all_users"]'),
        (6, "Integrate Local Payment Methods", "Add JazzCash and EasyPaisa as payment options", "feature", 0.85, 0.40, 0.75, 0.88, 0.88, "short", 38, '["local_users"]'),
        (4, "Restructure Navigation Menu", "Flatten navigation hierarchy and add quick-access toolbar", "improvement", 0.65, 0.55, 0.50, 0.58, 0.78, "medium", 54, '["power_users"]'),
        (5, "Add Tutorial Tooltips", "Context-sensitive help tooltips during first use", "improvement", 0.50, 0.25, 0.40, 0.52, 0.72, "short", 29, '["new_users"]'),
    ]
    for rec in recs_data:
        cursor.execute("""
            INSERT INTO recommendations (survey_id, insight_id, title, description, action_type, impact_score, effort_score, urgency_score, priority_score, confidence, timeframe, supporting_count, user_segments)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rec)

    # Sentiment Records (time series)
    import random
    base_date = datetime(2026, 2, 1)
    for day in range(28):
        for feature in ["Checkout", "Onboarding", "Performance", "UI/UX", "Payment"]:
            sentiment = random.uniform(-0.9, 0.5) if feature != "UI/UX" else random.uniform(-0.3, 0.9)
            cursor.execute("""
                INSERT INTO sentiment_records (survey_id, sentiment_label, sentiment_score, emotion, emotion_intensity, feature_area, recorded_at)
                VALUES (1, ?, ?, ?, ?, ?, ?)
            """, (
                "negative" if sentiment < -0.2 else ("positive" if sentiment > 0.2 else "neutral"),
                round(sentiment, 2),
                random.choice(["frustration", "confusion", "satisfaction", "disappointment", "excitement"]),
                round(random.uniform(0.3, 0.95), 2),
                feature,
                datetime(2026, 2, 1 + day).isoformat()
            ))

    # Notifications
    notif_data = [
        ("alert", "Critical: Checkout Frustration Spike", "Checkout-related frustration increased 25% in the last 48 hours. 134 users affected.", "critical"),
        ("warning", "Emerging Theme: Payment Methods", "New pattern detected — users requesting local payment options (JazzCash/EasyPaisa)", "high"),
        ("info", "Survey Milestone", "App Churn Discovery Interview has reached 247 responses", "low"),
        ("insight", "New Insight Detected", "iOS users report 60% more payment issues than Android users", "medium"),
        ("alert", "Drop-off Rate Increasing", "Onboarding completion rate dropped to 68% this week", "high"),
    ]
    for n in notif_data:
        cursor.execute("""
            INSERT INTO notifications (survey_id, type, title, message, severity)
            VALUES (1, ?, ?, ?, ?)
        """, n)

    # Engagement Metrics
    for channel in ["web", "chat", "voice"]:
        cursor.execute("""
            INSERT INTO engagement_metrics (survey_id, channel, total_sessions, completed_sessions, avg_completion_time, avg_response_quality, drop_off_rate)
            VALUES (1, ?, ?, ?, ?, ?, ?)
        """, (
            channel,
            {"web": 150, "chat": 72, "voice": 25}[channel],
            {"web": 102, "chat": 58, "voice": 19}[channel],
            {"web": 5.2, "chat": 3.8, "voice": 6.1}[channel],
            {"web": 0.72, "chat": 0.85, "voice": 0.78}[channel],
            {"web": 0.32, "chat": 0.19, "voice": 0.24}[channel],
        ))

    conn.commit()
    conn.close()
    print("Demo data seeded successfully.")


if __name__ == "__main__":
    init_db()
