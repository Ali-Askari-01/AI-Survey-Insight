"""
Data Pipeline Orchestrator — §7 Data Flow Lifecycle
═══════════════════════════════════════════════════════
Full lifecycle:
  User Feedback → Raw Storage → Normalization → AI Enrichment → Insight Clustering → Recommendation → Dashboard

Key Principles:
  ✅ Each step writes NEW data — NEVER overwrite previous layer
  ✅ Pipeline is resumable — if step fails, resume from last checkpoint
  ✅ Every layer independently queryable for audit / debug
  ✅ Batch + single-response modes
"""

import json
import time
import hashlib
import uuid
import sqlite3
import os
import re
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from dataclasses import dataclass, field


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "survey_engine.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ═══════════════════════════════════════════════════
# PIPELINE STAGES
# ═══════════════════════════════════════════════════
class PipelineStage(Enum):
    RAW = "raw"
    NORMALIZED = "normalized"
    ENRICHED = "enriched"
    CLUSTERED = "clustered"
    RECOMMENDED = "recommended"
    COMPLETE = "complete"


STAGE_ORDER = [
    PipelineStage.RAW,
    PipelineStage.NORMALIZED,
    PipelineStage.ENRICHED,
    PipelineStage.CLUSTERED,
    PipelineStage.RECOMMENDED,
    PipelineStage.COMPLETE,
]


@dataclass
class PipelineResult:
    """Result from a single pipeline step."""
    stage: PipelineStage
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: int = 0


# ═══════════════════════════════════════════════════
# DATA PIPELINE ORCHESTRATOR
# ═══════════════════════════════════════════════════
class DataPipelineOrchestrator:
    """
    Orchestrates the 5-layer data flow for every incoming response.

    Flow:
      1. store_raw()       → Layer 1: Raw text preserved permanently
      2. normalize()       → Layer 2: Text cleaned, entities detected
      3. enrich()          → Layer 3: AI adds sentiment, emotion, intent
      4. cluster()         → Layer 4: Group into insight clusters
      5. recommend()       → Layer 5: Generate/update recommendations

    Each step is independently callable and records its own state.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Metrics
        self._total_processed = 0
        self._total_errors = 0
        self._stage_latencies: Dict[str, List[int]] = {s.value: [] for s in PipelineStage if s != PipelineStage.COMPLETE}
        self._stage_errors: Dict[str, int] = {s.value: 0 for s in PipelineStage if s != PipelineStage.COMPLETE}

    # ─── Full Pipeline Execution ───

    def process_response(self, response_id: int, survey_id: int,
                         session_id: str, response_text: str,
                         channel: str = "web", response_type: str = "text",
                         emoji_data: str = None, audio_path: str = None) -> Dict[str, Any]:
        """
        Execute full 5-layer pipeline for a single response.
        Resumable: checks processing_state to skip completed layers.
        """
        results = []
        start = time.time()

        # Check existing processing state
        current_stage = self._get_processing_state(response_id)

        try:
            # ── Layer 1: Raw Storage ──
            if self._should_process(current_stage, PipelineStage.RAW):
                raw_result = self.store_raw(
                    response_id=response_id, survey_id=survey_id,
                    session_id=session_id, raw_text=response_text,
                    channel=channel, audio_path=audio_path,
                    emoji_raw=emoji_data
                )
                results.append(raw_result)
                if not raw_result.success:
                    return self._build_result(results, start)

            # ── Layer 2: Normalization ──
            if self._should_process(current_stage, PipelineStage.NORMALIZED):
                norm_result = self.normalize(
                    response_id=response_id,
                    raw_text=response_text,
                    response_type=response_type,
                    emoji_data=emoji_data
                )
                results.append(norm_result)
                if not norm_result.success:
                    return self._build_result(results, start)

            # ── Layer 3: AI Enrichment ──
            if self._should_process(current_stage, PipelineStage.ENRICHED):
                enrich_result = self.enrich(response_id=response_id, survey_id=survey_id)
                results.append(enrich_result)
                if not enrich_result.success:
                    return self._build_result(results, start)

            # ── Layer 4: Clustering ──
            if self._should_process(current_stage, PipelineStage.CLUSTERED):
                cluster_result = self.cluster(response_id=response_id, survey_id=survey_id)
                results.append(cluster_result)
                if not cluster_result.success:
                    return self._build_result(results, start)

            # ── Layer 5: Recommendations ──
            if self._should_process(current_stage, PipelineStage.RECOMMENDED):
                rec_result = self.recommend(response_id=response_id, survey_id=survey_id)
                results.append(rec_result)

            # Mark complete
            self._update_state(response_id, survey_id, "complete", completed=True)
            with self._lock:
                self._total_processed += 1

        except Exception as e:
            with self._lock:
                self._total_errors += 1
            results.append(PipelineResult(
                stage=PipelineStage.RAW, success=False,
                error=str(e)
            ))

        return self._build_result(results, start)

    # ─── Layer 1: Raw Storage ───

    def store_raw(self, response_id: int, survey_id: int,
                  session_id: str, raw_text: str,
                  channel: str = "web", audio_path: str = None,
                  emoji_raw: str = None) -> PipelineResult:
        """
        Layer 1 — Store feedback EXACTLY as received. No modification.
        Generates submission_uuid for idempotency.
        """
        start = time.time()
        try:
            conn = _get_conn()
            submission_uuid = str(uuid.uuid4())

            # Content hash for deduplication detection
            content_hash = hashlib.sha256(
                f"{survey_id}:{session_id}:{raw_text or ''}".encode()
            ).hexdigest()[:16]

            conn.execute("""
                INSERT INTO raw_responses (survey_id, session_id, channel, raw_text,
                    audio_path, emoji_raw, submission_uuid, respondent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (survey_id, session_id, channel, raw_text, audio_path,
                  emoji_raw, submission_uuid, content_hash))
            raw_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
            conn.close()

            self._update_state(response_id, survey_id, "raw")
            latency = int((time.time() - start) * 1000)
            self._record_stage_latency("raw", latency)

            return PipelineResult(
                stage=PipelineStage.RAW, success=True,
                data={"raw_response_id": raw_id, "submission_uuid": submission_uuid},
                latency_ms=latency
            )
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            self._record_stage_error("raw")
            return PipelineResult(
                stage=PipelineStage.RAW, success=False,
                error=str(e), latency_ms=latency
            )

    # ─── Layer 2: Normalization ───

    def normalize(self, response_id: int, raw_text: str,
                  response_type: str = "text",
                  emoji_data: str = None) -> PipelineResult:
        """
        Layer 2 — Standardize inputs: Voice→text, Emoji→tokens, Ratings→numeric.
        Detect language, count words, classify response type.
        """
        start = time.time()
        try:
            # Text cleaning
            cleaned = self._clean_text(raw_text or "")

            # Detect response classification
            detected_type = self._classify_response(cleaned)

            # Emoji conversion
            is_emoji = 0
            if emoji_data:
                cleaned = self._convert_emoji(cleaned, emoji_data)
                is_emoji = 1

            # Rating normalization
            is_rating = 0
            rating_numeric = None
            if response_type == "rating":
                rating_numeric = self._normalize_rating(raw_text)
                is_rating = 1

            # Entity detection (simple keyword-based)
            entities = self._detect_entities(cleaned)
            features = self._detect_features(cleaned)

            # Language detection (simplified)
            language = self._detect_language(cleaned)

            # Get raw_response_id
            conn = _get_conn()
            raw_row = conn.execute(
                "SELECT id FROM raw_responses WHERE rowid = (SELECT MAX(rowid) FROM raw_responses WHERE session_id IN (SELECT session_id FROM responses WHERE id = ?))",
                (response_id,)
            ).fetchone()
            raw_id = raw_row["id"] if raw_row else None

            conn.execute("""
                INSERT INTO normalized_responses (raw_response_id, response_id, cleaned_text,
                    language, word_count, char_count, response_type, detected_entities,
                    detected_features, is_emoji_converted, is_rating_normalized, rating_numeric)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (raw_id, response_id, cleaned, language,
                  len(cleaned.split()), len(cleaned), detected_type,
                  json.dumps(entities), json.dumps(features),
                  is_emoji, is_rating, rating_numeric))
            norm_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
            conn.close()

            survey_id = self._get_survey_id(response_id)
            self._update_state(response_id, survey_id or 0, "normalized")
            latency = int((time.time() - start) * 1000)
            self._record_stage_latency("normalized", latency)

            return PipelineResult(
                stage=PipelineStage.NORMALIZED, success=True,
                data={
                    "normalized_id": norm_id,
                    "cleaned_text": cleaned[:200],
                    "language": language,
                    "word_count": len(cleaned.split()),
                    "response_type": detected_type,
                    "entities": entities,
                    "features": features,
                },
                latency_ms=latency
            )
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            self._record_stage_error("normalized")
            return PipelineResult(
                stage=PipelineStage.NORMALIZED, success=False,
                error=str(e), latency_ms=latency
            )

    # ─── Layer 3: AI Enrichment ───

    def enrich(self, response_id: int, survey_id: int) -> PipelineResult:
        """
        Layer 3 — AI adds metadata: sentiment, emotion, themes, intent, urgency.
        Uses existing AI pipeline if available, falls back to heuristic.
        """
        start = time.time()
        try:
            conn = _get_conn()

            # Get normalized text
            norm = conn.execute(
                "SELECT cleaned_text FROM normalized_responses WHERE response_id = ? ORDER BY id DESC LIMIT 1",
                (response_id,)
            ).fetchone()

            # Fallback to raw response text
            if not norm:
                resp = conn.execute("SELECT response_text FROM responses WHERE id = ?", (response_id,)).fetchone()
                text = resp["response_text"] if resp else ""
            else:
                text = norm["cleaned_text"]

            # Get existing AI analysis from responses table (already enriched by AI pipeline)
            existing = conn.execute(
                "SELECT sentiment_score, emotion, intent, confidence FROM responses WHERE id = ?",
                (response_id,)
            ).fetchone()

            # Use existing AI data if available, otherwise run heuristic
            if existing and existing["sentiment_score"] is not None:
                sentiment_score = existing["sentiment_score"]
                sentiment_label = "positive" if sentiment_score > 0.2 else ("negative" if sentiment_score < -0.2 else "neutral")
                emotion = existing["emotion"] or self._detect_emotion_heuristic(text)
                intent = existing["intent"] or self._detect_intent_heuristic(text)
                confidence = existing["confidence"] or 0.7
            else:
                # Heuristic fallback when AI hasn't processed yet
                sentiment_score, sentiment_label = self._sentiment_heuristic(text)
                emotion = self._detect_emotion_heuristic(text)
                intent = self._detect_intent_heuristic(text)
                confidence = 0.5

            # Extract themes and urgency
            themes = self._extract_themes(text)
            urgency = self._calculate_urgency(text, sentiment_score)
            key_phrases = self._extract_key_phrases(text)

            norm_id_row = conn.execute(
                "SELECT id FROM normalized_responses WHERE response_id = ? ORDER BY id DESC LIMIT 1",
                (response_id,)
            ).fetchone()
            norm_id = norm_id_row["id"] if norm_id_row else None

            conn.execute("""
                INSERT INTO ai_enrichment (response_id, normalized_id, sentiment_score,
                    sentiment_label, emotion, intent, themes, urgency_score,
                    ai_confidence, key_phrases, model_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (response_id, norm_id, sentiment_score, sentiment_label,
                  emotion, intent, json.dumps(themes), urgency,
                  confidence, json.dumps(key_phrases), "heuristic+existing"))
            conn.commit()
            conn.close()

            self._update_state(response_id, survey_id, "enriched")
            latency = int((time.time() - start) * 1000)
            self._record_stage_latency("enriched", latency)

            return PipelineResult(
                stage=PipelineStage.ENRICHED, success=True,
                data={
                    "sentiment": sentiment_label,
                    "sentiment_score": sentiment_score,
                    "emotion": emotion,
                    "intent": intent,
                    "themes": themes,
                    "urgency": urgency,
                    "confidence": confidence,
                },
                latency_ms=latency
            )
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            self._record_stage_error("enriched")
            return PipelineResult(
                stage=PipelineStage.ENRICHED, success=False,
                error=str(e), latency_ms=latency
            )

    # ─── Layer 4: Insight Clustering ───

    def cluster(self, response_id: int, survey_id: int) -> PipelineResult:
        """
        Layer 4 — Group individual enriched responses into insight clusters.
        Incrementally updates existing clusters or creates new ones.
        """
        start = time.time()
        try:
            conn = _get_conn()

            # Get enrichment data
            enrichment = conn.execute(
                "SELECT themes, sentiment_score, intent, urgency_score FROM ai_enrichment WHERE response_id = ? ORDER BY id DESC LIMIT 1",
                (response_id,)
            ).fetchone()

            if not enrichment:
                conn.close()
                return PipelineResult(
                    stage=PipelineStage.CLUSTERED, success=True,
                    data={"message": "No enrichment data to cluster"}
                )

            themes = json.loads(enrichment["themes"]) if enrichment["themes"] else []
            sentiment = enrichment["sentiment_score"] or 0

            clusters_updated = 0
            clusters_created = 0

            for theme in themes:
                theme_lower = theme.lower().strip()
                if not theme_lower:
                    continue

                # Find existing cluster by theme similarity
                existing = conn.execute(
                    "SELECT id, frequency, avg_sentiment, member_response_ids FROM insight_clusters WHERE survey_id = ? AND LOWER(theme_name) = ?",
                    (survey_id, theme_lower)
                ).fetchone()

                if existing:
                    # Update existing cluster
                    freq = existing["frequency"] + 1
                    avg_sent = ((existing["avg_sentiment"] * existing["frequency"]) + sentiment) / freq
                    members = json.loads(existing["member_response_ids"] or "[]")
                    members.append(response_id)

                    conn.execute("""
                        UPDATE insight_clusters
                        SET frequency = ?, avg_sentiment = ?, member_response_ids = ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (freq, avg_sent, json.dumps(members[-500:]), existing["id"]))
                    clusters_updated += 1
                else:
                    # Create new cluster
                    conn.execute("""
                        INSERT INTO insight_clusters (survey_id, theme_name, frequency,
                            avg_sentiment, impact_score, member_response_ids, is_emerging)
                        VALUES (?, ?, 1, ?, ?, ?, 1)
                    """, (survey_id, theme, sentiment,
                          abs(sentiment) * 0.5, json.dumps([response_id])))
                    clusters_created += 1

            conn.commit()
            conn.close()

            self._update_state(response_id, survey_id, "clustered")
            latency = int((time.time() - start) * 1000)
            self._record_stage_latency("clustered", latency)

            return PipelineResult(
                stage=PipelineStage.CLUSTERED, success=True,
                data={
                    "clusters_updated": clusters_updated,
                    "clusters_created": clusters_created,
                    "themes_processed": len(themes),
                },
                latency_ms=latency
            )
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            self._record_stage_error("clustered")
            return PipelineResult(
                stage=PipelineStage.CLUSTERED, success=False,
                error=str(e), latency_ms=latency
            )

    # ─── Layer 5: Recommendation ───

    def recommend(self, response_id: int, survey_id: int) -> PipelineResult:
        """
        Layer 5 — Update recommendation priorities based on new cluster data.
        Checks if high-impact clusters need new or updated recommendations.
        """
        start = time.time()
        try:
            conn = _get_conn()

            # Get high-impact clusters without recommendations
            high_impact = conn.execute("""
                SELECT ic.id, ic.theme_name, ic.frequency, ic.avg_sentiment, ic.impact_score
                FROM insight_clusters ic
                WHERE ic.survey_id = ? AND ic.impact_score > 0.3 AND ic.frequency >= 3
                AND ic.id NOT IN (
                    SELECT DISTINCT cluster_id FROM recommendation_actions WHERE cluster_id IS NOT NULL
                )
                ORDER BY ic.impact_score DESC
                LIMIT 5
            """, (survey_id,)).fetchall()

            actions_created = 0
            for cluster in high_impact:
                cluster_dict = dict(cluster)
                # Generate action text based on cluster
                action_text = self._generate_action(cluster_dict)
                action_type = "fix" if cluster_dict["avg_sentiment"] < -0.3 else "improvement"

                # Find or create a recommendation
                rec = conn.execute(
                    "SELECT id FROM recommendations WHERE survey_id = ? AND title LIKE ? LIMIT 1",
                    (survey_id, f"%{cluster_dict['theme_name'][:30]}%")
                ).fetchone()

                rec_id = rec["id"] if rec else None
                if not rec_id:
                    # Create recommendation if none exists
                    conn.execute("""
                        INSERT INTO recommendations (survey_id, title, description, action_type,
                            impact_score, priority_score, confidence, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                    """, (survey_id, f"Address: {cluster_dict['theme_name']}",
                          action_text, action_type, cluster_dict["impact_score"],
                          cluster_dict["impact_score"] * cluster_dict["frequency"] / 10,
                          0.7))
                    rec_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                conn.execute("""
                    INSERT INTO recommendation_actions (recommendation_id, cluster_id,
                        action_text, action_type, impact_score, priority_rank)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (rec_id, cluster_dict["id"], action_text, action_type,
                      cluster_dict["impact_score"],
                      int(cluster_dict["impact_score"] * 100)))
                actions_created += 1

            conn.commit()
            conn.close()

            self._update_state(response_id, survey_id, "recommended")
            latency = int((time.time() - start) * 1000)
            self._record_stage_latency("recommended", latency)

            return PipelineResult(
                stage=PipelineStage.RECOMMENDED, success=True,
                data={"actions_created": actions_created},
                latency_ms=latency
            )
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            self._record_stage_error("recommended")
            return PipelineResult(
                stage=PipelineStage.RECOMMENDED, success=False,
                error=str(e), latency_ms=latency
            )

    # ─── Batch Processing ───

    def process_batch(self, survey_id: int, limit: int = 100) -> Dict[str, Any]:
        """
        Process unprocessed responses in batch.
        Finds responses without processing_state or incomplete state.
        """
        conn = _get_conn()
        unprocessed = conn.execute("""
            SELECT r.id, r.response_text, r.response_type, r.session_id,
                   s.survey_id, s.channel
            FROM responses r
            JOIN interview_sessions s ON r.session_id = s.session_id
            LEFT JOIN processing_state ps ON ps.response_id = r.id
            WHERE s.survey_id = ? AND (ps.id IS NULL OR ps.last_layer != 'complete')
            ORDER BY r.created_at DESC
            LIMIT ?
        """, (survey_id, limit)).fetchall()
        conn.close()

        results = {"total": len(unprocessed), "success": 0, "failed": 0, "details": []}

        for resp in unprocessed:
            r = dict(resp)
            result = self.process_response(
                response_id=r["id"], survey_id=r["survey_id"],
                session_id=r["session_id"], response_text=r["response_text"] or "",
                channel=r["channel"] or "web", response_type=r["response_type"] or "text"
            )
            if result.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1
            results["details"].append({
                "response_id": r["id"],
                "success": result.get("success", False),
            })

        return results

    # ─── Pipeline Stats ───

    def stats(self) -> Dict[str, Any]:
        """Get pipeline processing statistics."""
        with self._lock:
            stage_stats = {}
            for stage, latencies in self._stage_latencies.items():
                stage_stats[stage] = {
                    "count": len(latencies),
                    "avg_latency_ms": int(sum(latencies) / max(len(latencies), 1)),
                    "max_latency_ms": max(latencies) if latencies else 0,
                    "errors": self._stage_errors.get(stage, 0),
                }

        # Get processing state summary
        conn = None
        try:
            conn = _get_conn()
            state_summary = conn.execute("""
                SELECT last_layer, COUNT(*) as cnt
                FROM processing_state
                GROUP BY last_layer
            """).fetchall()
            state_dist = {row["last_layer"]: row["cnt"] for row in state_summary}
        except Exception:
            state_dist = {}
        finally:
            if conn:
                conn.close()

        return {
            "total_processed": self._total_processed,
            "total_errors": self._total_errors,
            "stages": stage_stats,
            "processing_state_distribution": state_dist,
        }

    # ═══════════════════════════════════════════════════
    # PRIVATE HELPERS
    # ═══════════════════════════════════════════════════

    def _get_processing_state(self, response_id: int) -> Optional[str]:
        """Get current processing state for a response."""
        try:
            conn = _get_conn()
            row = conn.execute(
                "SELECT last_layer FROM processing_state WHERE response_id = ?",
                (response_id,)
            ).fetchone()
            conn.close()
            return row["last_layer"] if row else None
        except Exception:
            return None

    def _should_process(self, current_stage: Optional[str], target: PipelineStage) -> bool:
        """Check if target stage should be processed based on current state."""
        if current_stage is None:
            return True
        if current_stage == "complete":
            return False
        try:
            current_idx = [s.value for s in STAGE_ORDER].index(current_stage)
            target_idx = [s.value for s in STAGE_ORDER].index(target.value)
            return target_idx > current_idx
        except ValueError:
            return True

    def _update_state(self, response_id: int, survey_id: int, layer: str,
                      completed: bool = False):
        """Update processing state for a response."""
        try:
            conn = _get_conn()
            existing = conn.execute(
                "SELECT id FROM processing_state WHERE response_id = ?",
                (response_id,)
            ).fetchone()

            kwargs = {
                "raw_stored": 1 if layer in ("raw", "normalized", "enriched", "clustered", "recommended", "complete") else 0,
                "normalized": 1 if layer in ("normalized", "enriched", "clustered", "recommended", "complete") else 0,
                "enriched": 1 if layer in ("enriched", "clustered", "recommended", "complete") else 0,
                "clustered": 1 if layer in ("clustered", "recommended", "complete") else 0,
                "recommended": 1 if layer in ("recommended", "complete") else 0,
            }

            if existing:
                conn.execute("""
                    UPDATE processing_state
                    SET last_layer = ?, raw_stored = ?, normalized = ?,
                        enriched = ?, clustered = ?, recommended = ?,
                        processing_completed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE processing_completed_at END
                    WHERE response_id = ?
                """, (layer, kwargs["raw_stored"], kwargs["normalized"],
                      kwargs["enriched"], kwargs["clustered"], kwargs["recommended"],
                      completed, response_id))
            else:
                conn.execute("""
                    INSERT INTO processing_state (response_id, survey_id, last_layer,
                        raw_stored, normalized, enriched, clustered, recommended,
                        processing_started_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (response_id, survey_id, layer,
                      kwargs["raw_stored"], kwargs["normalized"],
                      kwargs["enriched"], kwargs["clustered"], kwargs["recommended"]))

            conn.commit()
            conn.close()
        except Exception:
            pass  # State tracking is non-critical

    def _get_survey_id(self, response_id: int) -> Optional[int]:
        """Get survey_id for a response."""
        try:
            conn = _get_conn()
            row = conn.execute("""
                SELECT s.survey_id FROM interview_sessions s
                JOIN responses r ON r.session_id = s.session_id
                WHERE r.id = ?
            """, (response_id,)).fetchone()
            conn.close()
            return row["survey_id"] if row else None
        except Exception:
            return None

    def _build_result(self, results: List[PipelineResult], start: float) -> Dict[str, Any]:
        """Build final pipeline execution result."""
        total_ms = int((time.time() - start) * 1000)
        success = all(r.success for r in results)
        return {
            "success": success,
            "total_latency_ms": total_ms,
            "stages_completed": len([r for r in results if r.success]),
            "stages_total": len(results),
            "stages": [
                {
                    "stage": r.stage.value,
                    "success": r.success,
                    "data": r.data,
                    "error": r.error,
                    "latency_ms": r.latency_ms,
                }
                for r in results
            ],
        }

    # ─── Text Processing Helpers ───

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text input."""
        if not text:
            return ""
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        text = re.sub(r' {3,}', '  ', text)
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        return text.strip()

    def _classify_response(self, text: str) -> str:
        """Classify response as complaint/praise/request/neutral."""
        text_lower = text.lower()
        complaint_words = ["broken", "slow", "crash", "error", "bug", "terrible", "worst", "awful", "hate", "frustrat"]
        praise_words = ["love", "great", "amazing", "excellent", "perfect", "awesome", "fantastic", "wonderful", "best"]
        request_words = ["please", "would be nice", "should add", "wish", "need", "want", "could you", "can you", "feature request"]

        complaint_score = sum(1 for w in complaint_words if w in text_lower)
        praise_score = sum(1 for w in praise_words if w in text_lower)
        request_score = sum(1 for w in request_words if w in text_lower)

        scores = {"complaint": complaint_score, "praise": praise_score, "request": request_score}
        max_type = max(scores, key=scores.get)
        return max_type if scores[max_type] > 0 else "neutral"

    def _convert_emoji(self, text: str, emoji_data: str) -> str:
        """Convert emoji data to sentiment tokens appended to text."""
        emoji_sentiments = {
            "😀": "[positive]", "😊": "[positive]", "👍": "[positive]", "❤️": "[love]",
            "😢": "[sadness]", "😡": "[anger]", "😤": "[frustration]", "👎": "[negative]",
            "🤔": "[confusion]", "😐": "[neutral]", "🔥": "[urgency]", "💯": "[strong_positive]",
        }
        tokens = []
        for char in (emoji_data or ""):
            if char in emoji_sentiments:
                tokens.append(emoji_sentiments[char])
        if tokens:
            text += " " + " ".join(tokens)
        return text

    def _normalize_rating(self, text: str) -> Optional[float]:
        """Extract numeric rating from response text."""
        try:
            numbers = re.findall(r'\d+(?:\.\d+)?', text)
            if numbers:
                val = float(numbers[0])
                if 1 <= val <= 5:
                    return val
                elif 1 <= val <= 10:
                    return val / 2  # Normalize to 5-point scale
            return None
        except Exception:
            return None

    def _detect_entities(self, text: str) -> List[str]:
        """Simple entity detection from text."""
        entity_patterns = {
            "feature": r'\b(?:feature|function|capability|tool|option)\b',
            "performance": r'\b(?:slow|fast|speed|lag|loading|performance)\b',
            "ui": r'\b(?:ui|ux|interface|design|button|screen|layout|navigation)\b',
            "payment": r'\b(?:payment|checkout|billing|price|cost)\b',
            "security": r'\b(?:security|privacy|password|login|auth)\b',
            "mobile": r'\b(?:mobile|phone|app|android|ios|tablet)\b',
        }
        found = []
        text_lower = text.lower()
        for entity, pattern in entity_patterns.items():
            if re.search(pattern, text_lower):
                found.append(entity)
        return found

    def _detect_features(self, text: str) -> List[str]:
        """Detect product features mentioned in text."""
        features = {
            "checkout": r'\b(?:checkout|cart|purchase|buy)\b',
            "onboarding": r'\b(?:onboard|signup|sign.up|register|setup|tutorial)\b',
            "search": r'\b(?:search|find|filter|sort)\b',
            "upload": r'\b(?:upload|attach|file|image|photo)\b',
            "notification": r'\b(?:notif|alert|reminder|email|push)\b',
            "dashboard": r'\b(?:dashboard|analytics|report|chart|graph)\b',
            "chat": r'\b(?:chat|message|support|help)\b',
        }
        found = []
        text_lower = text.lower()
        for feat, pattern in features.items():
            if re.search(pattern, text_lower):
                found.append(feat)
        return found

    def _detect_language(self, text: str) -> str:
        """Simple language detection heuristic."""
        if not text:
            return "en"
        # Check for non-ASCII characters suggesting non-English
        non_ascii = sum(1 for c in text if ord(c) > 127)
        ratio = non_ascii / max(len(text), 1)
        if ratio > 0.3:
            return "unknown"
        return "en"

    # ─── AI Heuristics ───

    def _sentiment_heuristic(self, text: str) -> Tuple[float, str]:
        """Simple rule-based sentiment analysis."""
        text_lower = text.lower()
        positive = ["love", "great", "amazing", "excellent", "good", "awesome", "perfect", "wonderful",
                     "best", "happy", "pleased", "nice", "fantastic", "brilliant"]
        negative = ["hate", "terrible", "awful", "worst", "bad", "horrible", "frustrating", "annoying",
                     "broken", "slow", "crash", "error", "bug", "painful", "disappointing"]

        pos_count = sum(1 for w in positive if w in text_lower)
        neg_count = sum(1 for w in negative if w in text_lower)

        if pos_count > neg_count:
            score = min(0.3 + pos_count * 0.15, 1.0)
            return (score, "positive")
        elif neg_count > pos_count:
            score = max(-0.3 - neg_count * 0.15, -1.0)
            return (score, "negative")
        return (0.0, "neutral")

    def _detect_emotion_heuristic(self, text: str) -> str:
        """Detect primary emotion from text."""
        text_lower = text.lower()
        emotions = {
            "frustration": ["frustrat", "annoy", "irritat", "fed up", "tired of"],
            "anger": ["angry", "furious", "outrag", "infuriat"],
            "sadness": ["sad", "disappoint", "upset", "unhappy"],
            "confusion": ["confus", "unclear", "don't understand", "complicated"],
            "satisfaction": ["satisfied", "happy", "pleased", "content", "enjoy"],
            "excitement": ["excit", "thrilled", "amazing", "awesome", "love"],
        }
        for emotion, keywords in emotions.items():
            if any(kw in text_lower for kw in keywords):
                return emotion
        return "neutral"

    def _detect_intent_heuristic(self, text: str) -> str:
        """Detect user intent from text."""
        text_lower = text.lower()
        intents = {
            "bug_report": ["bug", "broken", "crash", "error", "doesn't work", "not working"],
            "feature_request": ["wish", "would be nice", "please add", "need", "feature", "should"],
            "ux_issue": ["confusing", "hard to", "difficult", "can't find", "unclear"],
            "performance": ["slow", "lag", "loading", "freeze", "hang"],
            "praise": ["love", "great", "amazing", "perfect", "excellent"],
            "question": ["how", "what", "where", "when", "can i", "is it possible"],
        }
        for intent, keywords in intents.items():
            if any(kw in text_lower for kw in keywords):
                return intent
        return "feedback"

    def _extract_themes(self, text: str) -> List[str]:
        """Extract topics/themes from text."""
        themes = []
        text_lower = text.lower()
        theme_map = {
            "Performance": ["slow", "speed", "lag", "loading", "performance", "fast"],
            "UI/UX": ["ui", "ux", "design", "interface", "layout", "button", "screen"],
            "Checkout": ["checkout", "payment", "cart", "purchase", "buy"],
            "Onboarding": ["onboard", "signup", "register", "setup", "tutorial", "getting started"],
            "Bugs": ["bug", "error", "crash", "broken", "glitch", "fix"],
            "Features": ["feature", "add", "missing", "need", "want", "wish"],
            "Support": ["help", "support", "contact", "customer service"],
            "Mobile": ["mobile", "app", "phone", "android", "ios"],
            "Security": ["security", "privacy", "password", "data", "safe"],
        }
        for theme, keywords in theme_map.items():
            if any(kw in text_lower for kw in keywords):
                themes.append(theme)
        return themes if themes else ["General"]

    def _calculate_urgency(self, text: str, sentiment: float) -> float:
        """Calculate urgency score (0-1) based on text and sentiment."""
        urgency = 0.0
        text_lower = text.lower()

        # Strong negative indicators
        urgent_words = ["urgent", "asap", "critical", "blocker", "broken", "crash", "immediately", "emergency"]
        urgency += sum(0.15 for w in urgent_words if w in text_lower)

        # Negative sentiment increases urgency
        if sentiment < -0.5:
            urgency += 0.3
        elif sentiment < -0.2:
            urgency += 0.15

        # Exclamation marks indicate urgency
        urgency += min(text.count("!") * 0.05, 0.2)

        # Cap words
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        if caps_ratio > 0.3:
            urgency += 0.15

        return min(urgency, 1.0)

    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases from text using simple n-gram approach."""
        words = text.lower().split()
        stop_words = {"the", "a", "an", "is", "was", "are", "were", "be", "been",
                       "being", "have", "has", "had", "do", "does", "did", "will",
                       "would", "could", "should", "may", "might", "can", "shall",
                       "i", "you", "he", "she", "it", "we", "they", "my", "your",
                       "his", "her", "its", "our", "their", "this", "that", "to",
                       "of", "in", "for", "on", "with", "at", "by", "from", "and",
                       "or", "but", "not", "so", "if", "when", "very", "just", "really"}
        # Bigrams
        phrases = []
        for i in range(len(words) - 1):
            if words[i] not in stop_words and words[i + 1] not in stop_words:
                phrase = f"{words[i]} {words[i + 1]}"
                if len(phrase) > 5:
                    phrases.append(phrase)
        return phrases[:10]

    def _generate_action(self, cluster: dict) -> str:
        """Generate action text based on cluster data."""
        theme = cluster.get("theme_name", "Unknown")
        freq = cluster.get("frequency", 0)
        sentiment = cluster.get("avg_sentiment", 0)

        if sentiment < -0.5:
            return f"Critical: Address '{theme}' issue affecting {freq} users. High negative sentiment detected — prioritize immediate investigation and fix."
        elif sentiment < -0.2:
            return f"Improvement needed: '{theme}' reported by {freq} users with negative sentiment. Investigate root cause and plan remediation."
        else:
            return f"Monitor: '{theme}' mentioned by {freq} users. Consider enhancement based on user feedback patterns."

    def _record_stage_latency(self, stage: str, latency_ms: int):
        """Record latency for a pipeline stage."""
        with self._lock:
            self._stage_latencies[stage].append(latency_ms)
            # Keep last 1000 entries per stage
            if len(self._stage_latencies[stage]) > 1000:
                self._stage_latencies[stage] = self._stage_latencies[stage][-1000:]

    def _record_stage_error(self, stage: str):
        """Record error for a pipeline stage."""
        with self._lock:
            self._stage_errors[stage] = self._stage_errors.get(stage, 0) + 1


# Global singleton
data_pipeline = DataPipelineOrchestrator()
