"""
Data Architecture Schema — 5-Layer Intelligence Data Model
═══════════════════════════════════════════════════════════════
§2  Layer 1 — Raw Data Layer (Source of Truth)
§3  Layer 2 — Normalized Data Layer
§4  Layer 3 — AI Enrichment Layer
§5  Layer 4 — Insight Aggregation Layer (Clusters)
§6  Layer 5 — Decision / Recommendation Layer
§8  Conversation Sessions
§9  Voice Metadata
§10 Temporal Intelligence (Insight History)
§11 Incremental Processing Tracking
§12 AI Learning Memory (Analysis Log)
§13 Data Governance (Audit Trail)

Golden Rule: Each layer stores NEW data — never overwrite the previous layer.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "survey_engine.db")


def _get_conn():
    """Get database connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_data_architecture_tables():
    """
    Create all 5-layer data architecture tables + supporting tables.
    These complement the existing schema without modifying existing tables.
    """
    conn = _get_conn()
    c = conn.cursor()

    # ═══════════════════════════════════════════════════
    # LAYER 1 — Raw Data Layer (Source of Truth) §2
    # Store feedback EXACTLY as received. No modification.
    # ═══════════════════════════════════════════════════
    c.execute("""
        CREATE TABLE IF NOT EXISTS raw_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            respondent_id TEXT,
            session_id TEXT,
            channel TEXT DEFAULT 'web',
            raw_text TEXT,
            audio_path TEXT,
            emoji_raw TEXT,
            rating_raw TEXT,
            file_attachments TEXT,
            ip_hash TEXT,
            user_agent TEXT,
            device_fingerprint TEXT,
            submission_uuid TEXT UNIQUE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # LAYER 2 — Normalized Data Layer §3
    # Standardize: voice→text, emoji→sentiment, ratings→numeric
    # ═══════════════════════════════════════════════════
    c.execute("""
        CREATE TABLE IF NOT EXISTS normalized_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_response_id INTEGER NOT NULL,
            response_id INTEGER,
            cleaned_text TEXT,
            language TEXT DEFAULT 'en',
            word_count INTEGER DEFAULT 0,
            char_count INTEGER DEFAULT 0,
            response_type TEXT DEFAULT 'text',
            detected_entities TEXT,
            detected_features TEXT,
            is_emoji_converted INTEGER DEFAULT 0,
            is_voice_transcribed INTEGER DEFAULT 0,
            is_rating_normalized INTEGER DEFAULT 0,
            rating_numeric REAL,
            normalization_version TEXT DEFAULT '1.0',
            normalized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (raw_response_id) REFERENCES raw_responses(id),
            FOREIGN KEY (response_id) REFERENCES responses(id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # LAYER 3 — AI Enrichment Layer §4
    # AI adds metadata — sentiment, emotion, themes, intent, urgency
    # AI outputs are probabilistic, NOT truth → store confidence
    # ═══════════════════════════════════════════════════
    c.execute("""
        CREATE TABLE IF NOT EXISTS ai_enrichment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER NOT NULL,
            normalized_id INTEGER,
            sentiment_score REAL,
            sentiment_label TEXT,
            emotion TEXT,
            emotion_intensity REAL,
            intent TEXT,
            themes TEXT,
            urgency_score REAL DEFAULT 0,
            ai_confidence REAL DEFAULT 0,
            key_phrases TEXT,
            topic_tags TEXT,
            language_complexity REAL,
            formality_score REAL,
            model_used TEXT,
            enrichment_version TEXT DEFAULT '1.0',
            processing_ms INTEGER DEFAULT 0,
            enriched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (response_id) REFERENCES responses(id),
            FOREIGN KEY (normalized_id) REFERENCES normalized_responses(id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # LAYER 4 — Insight Aggregation Layer (Clusters) §5
    # Individual → Collective Intelligence
    # Groups: "Slow uploads", "Upload delay", "Upload freezes" → "Performance Issue"
    # ═══════════════════════════════════════════════════
    c.execute("""
        CREATE TABLE IF NOT EXISTS insight_clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            theme_name TEXT NOT NULL,
            description TEXT,
            cluster_type TEXT DEFAULT 'auto',
            frequency INTEGER DEFAULT 0,
            avg_sentiment REAL DEFAULT 0,
            sentiment_spread REAL DEFAULT 0,
            trend_direction TEXT DEFAULT 'stable',
            impact_score REAL DEFAULT 0,
            urgency_score REAL DEFAULT 0,
            confidence REAL DEFAULT 0,
            member_response_ids TEXT,
            representative_quotes TEXT,
            parent_cluster_id INTEGER,
            is_emerging INTEGER DEFAULT 0,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (survey_id) REFERENCES surveys(id),
            FOREIGN KEY (parent_cluster_id) REFERENCES insight_clusters(id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # LAYER 5 — Decision / Recommendation Tracking §6
    # Insight → Action. Tracks lifecycle of recommendations.
    # (Complements existing recommendations table with action tracking)
    # ═══════════════════════════════════════════════════
    c.execute("""
        CREATE TABLE IF NOT EXISTS recommendation_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recommendation_id INTEGER NOT NULL,
            cluster_id INTEGER,
            action_text TEXT NOT NULL,
            action_type TEXT DEFAULT 'improvement',
            impact_score REAL DEFAULT 0,
            effort_score REAL DEFAULT 0,
            priority_rank INTEGER DEFAULT 0,
            assigned_to TEXT,
            status TEXT DEFAULT 'pending',
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            outcome_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recommendation_id) REFERENCES recommendations(id),
            FOREIGN KEY (cluster_id) REFERENCES insight_clusters(id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # §8 — Conversation Data Modeling
    # Sessions contain responses; track engagement & dropout
    # (Complements existing interview_sessions with deeper analytics)
    # ═══════════════════════════════════════════════════
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversation_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL UNIQUE,
            survey_id INTEGER NOT NULL,
            total_turns INTEGER DEFAULT 0,
            avg_response_length REAL DEFAULT 0,
            avg_response_time_ms REAL DEFAULT 0,
            engagement_trend TEXT DEFAULT 'stable',
            dropoff_question_id INTEGER,
            dropoff_reason TEXT,
            completion_rate REAL DEFAULT 0,
            depth_reached INTEGER DEFAULT 0,
            topics_covered TEXT,
            sentiment_trajectory TEXT,
            interaction_quality REAL DEFAULT 0,
            adaptive_paths_taken TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id),
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # §9 — Voice Data Architecture (Extended)
    # Separate voice-specific metrics from responses
    # (Complements existing voice_data table with ML metrics)
    # ═══════════════════════════════════════════════════
    c.execute("""
        CREATE TABLE IF NOT EXISTS voice_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voice_data_id INTEGER,
            response_id INTEGER,
            session_id TEXT,
            speaking_rate_wpm REAL,
            pause_count INTEGER DEFAULT 0,
            avg_pause_duration_ms REAL DEFAULT 0,
            hesitation_score REAL DEFAULT 0,
            vocal_emotion TEXT,
            vocal_emotion_confidence REAL DEFAULT 0,
            pitch_avg REAL,
            pitch_variance REAL,
            energy_level REAL,
            transcription_confidence REAL DEFAULT 0,
            word_error_rate REAL,
            language_detected TEXT DEFAULT 'en',
            speaker_segments TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (voice_data_id) REFERENCES voice_data(id),
            FOREIGN KEY (response_id) REFERENCES responses(id),
            FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # §10 — Temporal Intelligence (Time-Based Snapshots)
    # Track insight evolution over time for trend detection
    # ═══════════════════════════════════════════════════
    c.execute("""
        CREATE TABLE IF NOT EXISTS insight_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_id INTEGER,
            survey_id INTEGER NOT NULL,
            theme_name TEXT,
            snapshot_date DATE NOT NULL,
            frequency INTEGER DEFAULT 0,
            sentiment_avg REAL DEFAULT 0,
            sentiment_stddev REAL DEFAULT 0,
            growth_rate REAL DEFAULT 0,
            impact_score REAL DEFAULT 0,
            new_responses INTEGER DEFAULT 0,
            cumulative_responses INTEGER DEFAULT 0,
            trend_label TEXT DEFAULT 'stable',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cluster_id) REFERENCES insight_clusters(id),
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # §11 — Incremental Processing State
    # Track which responses have been processed through each layer
    # ═══════════════════════════════════════════════════
    c.execute("""
        CREATE TABLE IF NOT EXISTS processing_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER NOT NULL UNIQUE,
            survey_id INTEGER NOT NULL,
            raw_stored INTEGER DEFAULT 0,
            normalized INTEGER DEFAULT 0,
            enriched INTEGER DEFAULT 0,
            clustered INTEGER DEFAULT 0,
            recommended INTEGER DEFAULT 0,
            last_layer TEXT DEFAULT 'raw',
            processing_started_at TIMESTAMP,
            processing_completed_at TIMESTAMP,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            FOREIGN KEY (response_id) REFERENCES responses(id),
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # §12 — AI Learning Memory (Analysis Log)
    # Store every AI reasoning step for prompt optimization + audit
    # ═══════════════════════════════════════════════════
    c.execute("""
        CREATE TABLE IF NOT EXISTS ai_analysis_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            pipeline_name TEXT,
            prompt_used TEXT,
            prompt_hash TEXT,
            model_version TEXT NOT NULL,
            input_data_summary TEXT,
            output_data TEXT,
            output_quality_score REAL,
            latency_ms INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cost_estimate REAL DEFAULT 0,
            was_cached INTEGER DEFAULT 0,
            was_fallback INTEGER DEFAULT 0,
            error_message TEXT,
            context_keys TEXT,
            temperature REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ═══════════════════════════════════════════════════
    # §13 — Data Governance Audit Trail
    # Track all data access, modifications, and privacy actions
    # ═══════════════════════════════════════════════════
    c.execute("""
        CREATE TABLE IF NOT EXISTS data_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            actor TEXT DEFAULT 'system',
            actor_role TEXT DEFAULT 'system',
            details TEXT,
            ip_address TEXT,
            pii_fields_masked TEXT,
            data_before TEXT,
            data_after TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS data_retention_policy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL UNIQUE,
            retention_days INTEGER NOT NULL DEFAULT 365,
            anonymize_after_days INTEGER DEFAULT 180,
            delete_after_days INTEGER DEFAULT 730,
            is_active INTEGER DEFAULT 1,
            last_cleanup TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pii_detection_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER,
            field_name TEXT NOT NULL,
            pii_type TEXT NOT NULL,
            original_hash TEXT,
            masked_value TEXT,
            detection_method TEXT DEFAULT 'regex',
            confidence REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (response_id) REFERENCES responses(id)
        )
    """)

    # ═══════════════════════════════════════════════════
    # INDEXES for Data Architecture tables
    # ═══════════════════════════════════════════════════

    # Raw Responses
    c.execute("CREATE INDEX IF NOT EXISTS idx_raw_resp_survey ON raw_responses(survey_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_raw_resp_session ON raw_responses(session_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_raw_resp_channel ON raw_responses(channel)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_raw_resp_uuid ON raw_responses(submission_uuid)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_raw_resp_ts ON raw_responses(timestamp)")

    # Normalized
    c.execute("CREATE INDEX IF NOT EXISTS idx_norm_resp_raw ON normalized_responses(raw_response_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_norm_resp_lang ON normalized_responses(language)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_norm_resp_type ON normalized_responses(response_type)")

    # AI Enrichment
    c.execute("CREATE INDEX IF NOT EXISTS idx_enrichment_resp ON ai_enrichment(response_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_enrichment_sentiment ON ai_enrichment(sentiment_label)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_enrichment_intent ON ai_enrichment(intent)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_enrichment_model ON ai_enrichment(model_used)")

    # Insight Clusters
    c.execute("CREATE INDEX IF NOT EXISTS idx_clusters_survey ON insight_clusters(survey_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_clusters_trend ON insight_clusters(trend_direction)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_clusters_impact ON insight_clusters(impact_score)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_clusters_parent ON insight_clusters(parent_cluster_id)")

    # Recommendation Actions
    c.execute("CREATE INDEX IF NOT EXISTS idx_rec_actions_rec ON recommendation_actions(recommendation_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_rec_actions_status ON recommendation_actions(status)")

    # Conversation Analytics
    c.execute("CREATE INDEX IF NOT EXISTS idx_conv_analytics_session ON conversation_analytics(session_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_conv_analytics_survey ON conversation_analytics(survey_id)")

    # Voice Analytics
    c.execute("CREATE INDEX IF NOT EXISTS idx_voice_analytics_resp ON voice_analytics(response_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_voice_analytics_session ON voice_analytics(session_id)")

    # Insight History
    c.execute("CREATE INDEX IF NOT EXISTS idx_hist_cluster ON insight_history(cluster_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_hist_survey ON insight_history(survey_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_hist_date ON insight_history(snapshot_date)")

    # Processing State
    c.execute("CREATE INDEX IF NOT EXISTS idx_proc_state_resp ON processing_state(response_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_proc_state_survey ON processing_state(survey_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_proc_state_layer ON processing_state(last_layer)")

    # AI Analysis Log
    c.execute("CREATE INDEX IF NOT EXISTS idx_ai_log_task ON ai_analysis_log(task_type)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ai_log_pipeline ON ai_analysis_log(pipeline_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ai_log_model ON ai_analysis_log(model_version)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ai_log_created ON ai_analysis_log(created_at)")

    # Audit Log
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON data_audit_log(action)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity ON data_audit_log(entity_type, entity_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON data_audit_log(actor)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON data_audit_log(created_at)")

    # PII Detection
    c.execute("CREATE INDEX IF NOT EXISTS idx_pii_resp ON pii_detection_log(response_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_pii_type ON pii_detection_log(pii_type)")

    # Seed default retention policies
    _seed_retention_policies(c)

    conn.commit()
    conn.close()
    print("[Data Architecture] All 5-layer tables initialized successfully.")


def _seed_retention_policies(cursor):
    """Seed default data retention policies."""
    policies = [
        ("raw_responses", 365, 180, 730),
        ("normalized_responses", 365, 180, 730),
        ("ai_enrichment", 365, 365, 1095),
        ("insight_clusters", 730, 730, 1825),
        ("recommendations", 730, 730, 1825),
        ("voice_data", 180, 90, 365),
        ("ai_analysis_log", 365, 365, 730),
        ("data_audit_log", 1095, 1095, 2555),
        ("conversation_analytics", 365, 180, 730),
    ]
    for entity, retain, anon, delete in policies:
        cursor.execute("""
            INSERT OR IGNORE INTO data_retention_policy (entity_type, retention_days, anonymize_after_days, delete_after_days)
            VALUES (?, ?, ?, ?)
        """, (entity, retain, anon, delete))


def get_layer_stats() -> dict:
    """Get counts for each data layer."""
    conn = _get_conn()
    stats = {}
    tables = [
        ("layer_1_raw", "raw_responses"),
        ("layer_2_normalized", "normalized_responses"),
        ("layer_3_enrichment", "ai_enrichment"),
        ("layer_4_clusters", "insight_clusters"),
        ("layer_5_recommendations", "recommendation_actions"),
        ("conversation_analytics", "conversation_analytics"),
        ("voice_analytics", "voice_analytics"),
        ("insight_history", "insight_history"),
        ("processing_state", "processing_state"),
        ("ai_analysis_log", "ai_analysis_log"),
        ("audit_log", "data_audit_log"),
    ]
    try:
        for key, table in tables:
            try:
                row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
                stats[key] = row["cnt"] if row else 0
            except Exception:
                stats[key] = 0
    finally:
        conn.close()
    return stats
