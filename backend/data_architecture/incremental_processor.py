"""
Incremental Processing Architecture — §11
═══════════════════════════════════════════════════════
DO NOT recompute everything.

Instead:
  New Response → Update affected cluster only → Recalculate delta

This is called: ✅ Incremental analytics — Massive performance gain.

Key principles:
  - Only calculate the delta from new responses
  - Track what has changed and what needs reprocessing
  - Batch micro-updates into periodic consolidation
  - Never recompute full dataset when only a few items changed
"""

import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
import sqlite3
import os
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "survey_engine.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class IncrementalProcessor:
    """
    Incremental delta processing engine.

    Instead of full recomputation on every response:
      1. Track which responses are new/changed (dirty set)
      2. Only update affected clusters/insights
      3. Recalculate aggregates incrementally
      4. Periodically run full consolidation for consistency
    """

    def __init__(self, consolidation_interval_minutes: int = 30):
        self._lock = threading.Lock()
        self._dirty_responses: Set[int] = set()
        self._affected_clusters: Set[int] = set()
        self._pending_survey_updates: Dict[int, Set[int]] = defaultdict(set)
        self._consolidation_interval = consolidation_interval_minutes
        self._last_consolidation: Optional[datetime] = None

        # Metrics
        self._delta_updates = 0
        self._full_recomputes = 0
        self._responses_skipped = 0

    # ─── Delta Processing ───

    def mark_dirty(self, response_id: int, survey_id: int):
        """Mark a response as needing incremental processing."""
        with self._lock:
            self._dirty_responses.add(response_id)
            self._pending_survey_updates[survey_id].add(response_id)

    def process_delta(self, survey_id: int) -> Dict[str, Any]:
        """
        Process only the delta — new/changed responses for a survey.
        Much faster than full recomputation.
        """
        start = time.time()

        with self._lock:
            dirty = list(self._pending_survey_updates.get(survey_id, set()))
            if not dirty:
                return {"message": "No pending updates", "survey_id": survey_id}

        conn = _get_conn()
        clusters_updated = 0
        sentiments_updated = 0
        themes_updated = 0

        try:
            for response_id in dirty:
                # Get the enrichment data for this response
                enrichment = conn.execute(
                    "SELECT sentiment_score, sentiment_label, emotion, intent, themes, urgency_score "
                    "FROM ai_enrichment WHERE response_id = ? ORDER BY id DESC LIMIT 1",
                    (response_id,)
                ).fetchone()

                if not enrichment:
                    continue

                e = dict(enrichment)
                themes = json.loads(e["themes"]) if e["themes"] else []

                # ── Update affected insight clusters ──
                for theme in themes:
                    cluster = conn.execute(
                        "SELECT id, frequency, avg_sentiment, impact_score FROM insight_clusters "
                        "WHERE survey_id = ? AND LOWER(theme_name) = LOWER(?)",
                        (survey_id, theme.strip())
                    ).fetchone()

                    if cluster:
                        c = dict(cluster)
                        new_freq = c["frequency"]  # Already incremented during pipeline
                        # Recalculate moving average sentiment
                        new_sentiment = self._incremental_avg(
                            c["avg_sentiment"], new_freq, e["sentiment_score"] or 0
                        )
                        # Recalculate impact
                        new_impact = self._calculate_impact(new_freq, new_sentiment, e["urgency_score"])

                        conn.execute("""
                            UPDATE insight_clusters
                            SET avg_sentiment = ?, impact_score = ?,
                                trend_direction = ?, last_updated = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (new_sentiment, new_impact,
                              self._determine_trend(c["avg_sentiment"], new_sentiment),
                              c["id"]))
                        clusters_updated += 1

                        with self._lock:
                            self._affected_clusters.add(c["id"])

                # ── Update theme sentiment aggregates ──
                theme_row = conn.execute(
                    "SELECT id, frequency, sentiment_avg FROM themes "
                    "WHERE survey_id = ? AND LOWER(name) LIKE LOWER(?)",
                    (survey_id, f"%{themes[0] if themes else ''}%")
                ).fetchone()

                if theme_row:
                    t = dict(theme_row)
                    new_sentiment = self._incremental_avg(
                        t["sentiment_avg"], t["frequency"], e["sentiment_score"] or 0
                    )
                    conn.execute(
                        "UPDATE themes SET sentiment_avg = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (new_sentiment, t["id"])
                    )
                    themes_updated += 1

                # ── Update survey-level sentiment ──
                if e["sentiment_score"] is not None:
                    sentiments_updated += 1

            conn.commit()

            # Clear processed items from dirty set
            with self._lock:
                for rid in dirty:
                    self._dirty_responses.discard(rid)
                self._pending_survey_updates[survey_id].clear()
                self._delta_updates += clusters_updated

        except Exception as e:
            conn.rollback()
            conn.close()
            return {"error": str(e), "survey_id": survey_id}

        conn.close()
        latency_ms = int((time.time() - start) * 1000)

        return {
            "survey_id": survey_id,
            "responses_processed": len(dirty),
            "clusters_updated": clusters_updated,
            "themes_updated": themes_updated,
            "sentiments_updated": sentiments_updated,
            "latency_ms": latency_ms,
            "method": "incremental_delta",
        }

    # ─── Full Consolidation ───

    def consolidate(self, survey_id: int) -> Dict[str, Any]:
        """
        Periodic full consolidation to ensure data consistency.
        Recomputes aggregates from source data.
        Should run less frequently than delta processing.
        """
        start = time.time()
        conn = _get_conn()

        try:
            # Recompute cluster aggregates from enrichment data
            clusters = conn.execute(
                "SELECT id, member_response_ids FROM insight_clusters WHERE survey_id = ?",
                (survey_id,)
            ).fetchall()

            clusters_consolidated = 0
            for cluster in clusters:
                c = dict(cluster)
                member_ids = json.loads(c["member_response_ids"] or "[]")
                if not member_ids:
                    continue

                # Recompute from source
                placeholders = ",".join("?" * len(member_ids))
                enrichments = conn.execute(
                    f"SELECT sentiment_score, urgency_score FROM ai_enrichment "
                    f"WHERE response_id IN ({placeholders})",
                    member_ids
                ).fetchall()

                if enrichments:
                    sentiments = [e["sentiment_score"] for e in enrichments if e["sentiment_score"] is not None]
                    urgencies = [e["urgency_score"] for e in enrichments if e["urgency_score"] is not None]

                    avg_sentiment = sum(sentiments) / max(len(sentiments), 1)
                    avg_urgency = sum(urgencies) / max(len(urgencies), 1)
                    impact = self._calculate_impact(len(member_ids), avg_sentiment, avg_urgency)

                    # Sentiment spread
                    if len(sentiments) > 1:
                        mean = avg_sentiment
                        spread = (sum((s - mean) ** 2 for s in sentiments) / (len(sentiments) - 1)) ** 0.5
                    else:
                        spread = 0

                    conn.execute("""
                        UPDATE insight_clusters
                        SET frequency = ?, avg_sentiment = ?, sentiment_spread = ?,
                            impact_score = ?, urgency_score = ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (len(member_ids), avg_sentiment, spread,
                          impact, avg_urgency, c["id"]))
                    clusters_consolidated += 1

            conn.commit()

            with self._lock:
                self._full_recomputes += 1
                self._last_consolidation = datetime.now()

        except Exception as e:
            conn.rollback()
            conn.close()
            return {"error": str(e)}

        conn.close()
        latency_ms = int((time.time() - start) * 1000)

        return {
            "survey_id": survey_id,
            "clusters_consolidated": clusters_consolidated,
            "latency_ms": latency_ms,
            "method": "full_consolidation",
        }

    # ─── Smart Recompute Decision ───

    def should_consolidate(self) -> bool:
        """Check if a full consolidation should run."""
        if self._last_consolidation is None:
            return True
        elapsed = datetime.now() - self._last_consolidation
        return elapsed.total_seconds() > self._consolidation_interval * 60

    def get_pending_count(self, survey_id: int = None) -> int:
        """Get count of pending dirty responses."""
        with self._lock:
            if survey_id:
                return len(self._pending_survey_updates.get(survey_id, set()))
            return len(self._dirty_responses)

    # ─── Processing State Queries ───

    def get_unprocessed(self, survey_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get responses that haven't completed full pipeline."""
        conn = _get_conn()
        rows = conn.execute("""
            SELECT ps.response_id, ps.last_layer, ps.retry_count, ps.error_message,
                   r.response_text, r.created_at
            FROM processing_state ps
            JOIN responses r ON r.id = ps.response_id
            WHERE ps.survey_id = ? AND ps.last_layer != 'complete'
            ORDER BY ps.processing_started_at DESC
            LIMIT ?
        """, (survey_id, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_processing_summary(self, survey_id: int) -> Dict[str, Any]:
        """Get processing state summary for a survey."""
        conn = _get_conn()
        summary = conn.execute("""
            SELECT last_layer, COUNT(*) as cnt
            FROM processing_state
            WHERE survey_id = ?
            GROUP BY last_layer
        """, (survey_id,)).fetchall()

        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM responses r JOIN interview_sessions s ON r.session_id = s.session_id WHERE s.survey_id = ?",
            (survey_id,)
        ).fetchone()

        processed = conn.execute(
            "SELECT COUNT(*) as cnt FROM processing_state WHERE survey_id = ? AND last_layer = 'complete'",
            (survey_id,)
        ).fetchone()

        conn.close()

        return {
            "survey_id": survey_id,
            "total_responses": total["cnt"] if total else 0,
            "fully_processed": processed["cnt"] if processed else 0,
            "state_distribution": {row["last_layer"]: row["cnt"] for row in summary},
            "pending_dirty": self.get_pending_count(survey_id),
            "needs_consolidation": self.should_consolidate(),
        }

    # ─── Retry Failed ───

    def retry_failed(self, survey_id: int, max_retries: int = 3) -> Dict[str, Any]:
        """Retry responses that failed during pipeline processing."""
        conn = _get_conn()
        failed = conn.execute("""
            SELECT response_id, last_layer, retry_count, error_message
            FROM processing_state
            WHERE survey_id = ? AND last_layer != 'complete'
              AND error_message IS NOT NULL AND retry_count < ?
        """, (survey_id, max_retries)).fetchall()
        conn.close()

        retried = 0
        for row in failed:
            r = dict(row)
            self.mark_dirty(r["response_id"], survey_id)

            # Increment retry count
            conn = _get_conn()
            conn.execute(
                "UPDATE processing_state SET retry_count = retry_count + 1, error_message = NULL WHERE response_id = ?",
                (r["response_id"],)
            )
            conn.commit()
            conn.close()
            retried += 1

        return {
            "survey_id": survey_id,
            "failed_found": len(failed),
            "retried": retried,
        }

    # ─── Stats ───

    def stats(self) -> Dict[str, Any]:
        """Get incremental processing statistics."""
        with self._lock:
            return {
                "dirty_responses": len(self._dirty_responses),
                "affected_clusters": len(self._affected_clusters),
                "pending_surveys": {k: len(v) for k, v in self._pending_survey_updates.items() if v},
                "delta_updates_total": self._delta_updates,
                "full_recomputes_total": self._full_recomputes,
                "responses_skipped": self._responses_skipped,
                "last_consolidation": self._last_consolidation.isoformat() if self._last_consolidation else None,
                "needs_consolidation": self.should_consolidate(),
            }

    # ─── Private Helpers ───

    def _incremental_avg(self, current_avg: float, count: int, new_value: float) -> float:
        """Calculate new average incrementally without recomputing from all values."""
        if count <= 0:
            return new_value
        return ((current_avg * (count - 1)) + new_value) / count

    def _calculate_impact(self, frequency: int, sentiment: float, urgency: float) -> float:
        """Calculate impact score from frequency, sentiment, and urgency."""
        freq_factor = min(frequency / 100, 1.0)  # Normalize to 0-1
        sent_factor = abs(sentiment)  # Magnitude of sentiment
        urg_factor = urgency or 0

        return round(
            (freq_factor * 0.4) + (sent_factor * 0.3) + (urg_factor * 0.3),
            3
        )

    def _determine_trend(self, old_sentiment: float, new_sentiment: float) -> str:
        """Determine trend direction from sentiment change."""
        diff = (new_sentiment or 0) - (old_sentiment or 0)
        if diff > 0.15:
            return "improving"
        elif diff < -0.15:
            return "worsening"
        return "stable"


# Global singleton
incremental_processor = IncrementalProcessor()
