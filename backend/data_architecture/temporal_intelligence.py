"""
Temporal Intelligence — §10 Time-Based Data Intelligence
═══════════════════════════════════════════════════════
Insights change over time. Store trends.

Detect:
  ✅ Emerging problems
  ✅ Improving UX
  ✅ Market shifts
  ✅ Sentiment drift
  ✅ Growth patterns

Creates daily snapshots of insight clusters for time-series analysis.
"""

import json
import time
import threading
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "survey_engine.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class TemporalIntelligence:
    """
    Time-based intelligence engine for trend detection and insight evolution tracking.

    Core capabilities:
      - Daily snapshot generation for all insight clusters
      - Trend direction calculation (rising / falling / stable / emerging)
      - Growth rate computation
      - Sentiment drift detection over time
      - Alert generation for significant shifts
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._snapshots_taken = 0
        self._trends_detected = 0

    # ─── Snapshot Generation ───

    def take_snapshot(self, survey_id: int, snapshot_date: date = None) -> Dict[str, Any]:
        """
        Take a point-in-time snapshot of all insight clusters for a survey.
        Called daily (or on-demand) to build trend history.
        """
        snapshot_date = snapshot_date or date.today()
        start = time.time()

        conn = _get_conn()

        # Check if snapshot already exists for this date
        existing = conn.execute(
            "SELECT COUNT(*) as cnt FROM insight_history WHERE survey_id = ? AND snapshot_date = ?",
            (survey_id, snapshot_date.isoformat())
        ).fetchone()

        if existing["cnt"] > 0:
            conn.close()
            return {"message": "Snapshot already exists for this date", "date": snapshot_date.isoformat()}

        # Get current clusters
        clusters = conn.execute(
            "SELECT * FROM insight_clusters WHERE survey_id = ?",
            (survey_id,)
        ).fetchall()

        snapshots_created = 0
        for cluster in clusters:
            c = dict(cluster)

            # Get previous snapshot for growth rate calculation
            prev = conn.execute("""
                SELECT frequency, sentiment_avg, impact_score
                FROM insight_history
                WHERE cluster_id = ? AND snapshot_date < ?
                ORDER BY snapshot_date DESC LIMIT 1
            """, (c["id"], snapshot_date.isoformat())).fetchone()

            # Calculate growth rate
            growth_rate = 0.0
            if prev and prev["frequency"] > 0:
                growth_rate = (c["frequency"] - prev["frequency"]) / prev["frequency"]

            # Calculate sentiment standard deviation from recent enrichments
            member_ids = json.loads(c.get("member_response_ids") or "[]")
            sentiment_stddev = 0.0
            if member_ids:
                recent_ids = member_ids[-50:]  # Last 50 responses
                placeholders = ",".join("?" * len(recent_ids))
                sentiments = conn.execute(
                    f"SELECT sentiment_score FROM ai_enrichment WHERE response_id IN ({placeholders})",
                    recent_ids
                ).fetchall()
                if sentiments:
                    scores = [s["sentiment_score"] for s in sentiments if s["sentiment_score"] is not None]
                    if len(scores) > 1:
                        mean = sum(scores) / len(scores)
                        variance = sum((s - mean) ** 2 for s in scores) / (len(scores) - 1)
                        sentiment_stddev = variance ** 0.5

            # Count new responses since last snapshot
            new_responses = 0
            if prev:
                new_responses = max(c["frequency"] - prev["frequency"], 0)
            else:
                new_responses = c["frequency"]

            # Determine trend label
            trend_label = self._calculate_trend(growth_rate, c.get("avg_sentiment", 0), prev)

            conn.execute("""
                INSERT INTO insight_history (cluster_id, survey_id, theme_name, snapshot_date,
                    frequency, sentiment_avg, sentiment_stddev, growth_rate, impact_score,
                    new_responses, cumulative_responses, trend_label)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (c["id"], survey_id, c["theme_name"], snapshot_date.isoformat(),
                  c["frequency"], c.get("avg_sentiment", 0), sentiment_stddev,
                  growth_rate, c.get("impact_score", 0), new_responses,
                  c["frequency"], trend_label))
            snapshots_created += 1

        # Also snapshot themes from the existing themes table
        themes = conn.execute(
            "SELECT * FROM themes WHERE survey_id = ?",
            (survey_id,)
        ).fetchall()

        for theme in themes:
            t = dict(theme)
            # Check for existing cluster match
            existing_cluster = conn.execute(
                "SELECT id FROM insight_clusters WHERE survey_id = ? AND LOWER(theme_name) = LOWER(?)",
                (survey_id, t["name"])
            ).fetchone()

            if not existing_cluster:
                # Create snapshot from theme table data
                conn.execute("""
                    INSERT INTO insight_history (survey_id, theme_name, snapshot_date,
                        frequency, sentiment_avg, growth_rate, trend_label)
                    VALUES (?, ?, ?, ?, ?, 0, 'stable')
                """, (survey_id, t["name"], snapshot_date.isoformat(),
                      t["frequency"], t.get("sentiment_avg", 0)))
                snapshots_created += 1

        conn.commit()
        conn.close()

        with self._lock:
            self._snapshots_taken += snapshots_created

        latency_ms = int((time.time() - start) * 1000)
        return {
            "survey_id": survey_id,
            "snapshot_date": snapshot_date.isoformat(),
            "snapshots_created": snapshots_created,
            "latency_ms": latency_ms,
        }

    # ─── Trend Analysis ───

    def get_trends(self, survey_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get trend analysis for all themes over a time period.
        Returns rising, falling, stable, and emerging themes.
        """
        conn = _get_conn()
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        history = conn.execute("""
            SELECT theme_name, snapshot_date, frequency, sentiment_avg, growth_rate, trend_label
            FROM insight_history
            WHERE survey_id = ? AND snapshot_date >= ?
            ORDER BY theme_name, snapshot_date
        """, (survey_id, cutoff)).fetchall()
        conn.close()

        # Group by theme
        themes: Dict[str, List[dict]] = {}
        for row in history:
            r = dict(row)
            name = r["theme_name"]
            if name not in themes:
                themes[name] = []
            themes[name].append(r)

        # Analyze each theme
        rising = []
        falling = []
        stable = []
        emerging = []

        for theme_name, snapshots in themes.items():
            if len(snapshots) < 2:
                # Only one data point — emerging
                emerging.append({
                    "theme": theme_name,
                    "frequency": snapshots[0]["frequency"],
                    "sentiment": snapshots[0]["sentiment_avg"],
                })
                continue

            # Calculate overall trend
            first = snapshots[0]
            last = snapshots[-1]
            freq_change = last["frequency"] - first["frequency"]
            sent_change = (last["sentiment_avg"] or 0) - (first["sentiment_avg"] or 0)

            avg_growth = sum(s.get("growth_rate", 0) for s in snapshots) / len(snapshots)

            trend_data = {
                "theme": theme_name,
                "frequency_start": first["frequency"],
                "frequency_end": last["frequency"],
                "frequency_change": freq_change,
                "sentiment_start": first["sentiment_avg"],
                "sentiment_end": last["sentiment_avg"],
                "sentiment_change": round(sent_change, 3),
                "avg_growth_rate": round(avg_growth, 3),
                "data_points": len(snapshots),
            }

            if avg_growth > 0.1:
                rising.append(trend_data)
            elif avg_growth < -0.1:
                falling.append(trend_data)
            else:
                stable.append(trend_data)

        with self._lock:
            self._trends_detected += len(rising) + len(falling) + len(emerging)

        return {
            "survey_id": survey_id,
            "period_days": days,
            "rising": sorted(rising, key=lambda x: x["avg_growth_rate"], reverse=True),
            "falling": sorted(falling, key=lambda x: x["avg_growth_rate"]),
            "stable": stable,
            "emerging": emerging,
            "total_themes": len(themes),
        }

    # ─── Sentiment Drift Detection ───

    def detect_sentiment_drift(self, survey_id: int, threshold: float = 0.2,
                                days: int = 14) -> List[Dict[str, Any]]:
        """
        Detect significant sentiment shifts (drift) in insight clusters.

        A drift occurs when avg_sentiment changes by more than threshold
        over the specified number of days.
        """
        conn = _get_conn()
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        # Get earliest and latest snapshots per cluster
        clusters = conn.execute("""
            SELECT cluster_id, theme_name,
                   MIN(snapshot_date) as first_date, MAX(snapshot_date) as last_date
            FROM insight_history
            WHERE survey_id = ? AND snapshot_date >= ? AND cluster_id IS NOT NULL
            GROUP BY cluster_id
            HAVING COUNT(*) >= 2
        """, (survey_id, cutoff)).fetchall()

        drifts = []
        for c in clusters:
            c_dict = dict(c)
            first = conn.execute(
                "SELECT sentiment_avg FROM insight_history WHERE cluster_id = ? AND snapshot_date = ?",
                (c_dict["cluster_id"], c_dict["first_date"])
            ).fetchone()
            last = conn.execute(
                "SELECT sentiment_avg FROM insight_history WHERE cluster_id = ? AND snapshot_date = ?",
                (c_dict["cluster_id"], c_dict["last_date"])
            ).fetchone()

            if first and last:
                drift = (last["sentiment_avg"] or 0) - (first["sentiment_avg"] or 0)
                if abs(drift) >= threshold:
                    drifts.append({
                        "cluster_id": c_dict["cluster_id"],
                        "theme": c_dict["theme_name"],
                        "sentiment_before": first["sentiment_avg"],
                        "sentiment_after": last["sentiment_avg"],
                        "drift": round(drift, 3),
                        "direction": "improving" if drift > 0 else "worsening",
                        "period": f"{c_dict['first_date']} to {c_dict['last_date']}",
                    })

        conn.close()
        return sorted(drifts, key=lambda x: abs(x["drift"]), reverse=True)

    # ─── Theme Emergence Detection ───

    def detect_emerging_themes(self, survey_id: int, min_growth_rate: float = 0.5,
                                days: int = 7) -> List[Dict[str, Any]]:
        """
        Detect newly emerging themes with rapid growth.
        Themes with growth rate > min_growth_rate in the last N days.
        """
        conn = _get_conn()
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        emerging = conn.execute("""
            SELECT cluster_id, theme_name, frequency, sentiment_avg, growth_rate,
                   impact_score, snapshot_date
            FROM insight_history
            WHERE survey_id = ? AND snapshot_date >= ? AND growth_rate > ?
            ORDER BY growth_rate DESC
        """, (survey_id, cutoff, min_growth_rate)).fetchall()
        conn.close()

        # Deduplicate by cluster
        seen = set()
        results = []
        for row in emerging:
            r = dict(row)
            cid = r.get("cluster_id") or r["theme_name"]
            if cid not in seen:
                seen.add(cid)
                results.append({
                    "cluster_id": r["cluster_id"],
                    "theme": r["theme_name"],
                    "frequency": r["frequency"],
                    "growth_rate": r["growth_rate"],
                    "sentiment": r["sentiment_avg"],
                    "last_snapshot": r["snapshot_date"],
                })
        return results

    # ─── Timeline View ───

    def get_theme_timeline(self, survey_id: int, theme_name: str,
                           days: int = 90) -> List[Dict[str, Any]]:
        """Get complete timeline for a specific theme."""
        conn = _get_conn()
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        history = conn.execute("""
            SELECT snapshot_date, frequency, sentiment_avg, sentiment_stddev,
                   growth_rate, impact_score, new_responses, cumulative_responses, trend_label
            FROM insight_history
            WHERE survey_id = ? AND LOWER(theme_name) = LOWER(?) AND snapshot_date >= ?
            ORDER BY snapshot_date
        """, (survey_id, theme_name, cutoff)).fetchall()
        conn.close()

        return [dict(h) for h in history]

    # ─── Stats ───

    def stats(self) -> Dict[str, Any]:
        """Get temporal intelligence statistics."""
        conn = None
        try:
            conn = _get_conn()
            total_snapshots = conn.execute("SELECT COUNT(*) as cnt FROM insight_history").fetchone()["cnt"]
            unique_dates = conn.execute("SELECT COUNT(DISTINCT snapshot_date) as cnt FROM insight_history").fetchone()["cnt"]
            unique_themes = conn.execute("SELECT COUNT(DISTINCT theme_name) as cnt FROM insight_history").fetchone()["cnt"]
        except Exception:
            total_snapshots = 0
            unique_dates = 0
            unique_themes = 0
        finally:
            if conn:
                conn.close()

        return {
            "total_snapshots": total_snapshots,
            "unique_snapshot_dates": unique_dates,
            "unique_themes_tracked": unique_themes,
            "snapshots_taken_this_session": self._snapshots_taken,
            "trends_detected_this_session": self._trends_detected,
        }

    # ─── Private Helpers ───

    def _calculate_trend(self, growth_rate: float, sentiment: float,
                         previous: Optional[sqlite3.Row]) -> str:
        """Calculate trend label from growth rate and sentiment change."""
        if not previous:
            return "new"

        if growth_rate > 0.3:
            return "rising_fast"
        elif growth_rate > 0.1:
            return "rising"
        elif growth_rate < -0.3:
            return "falling_fast"
        elif growth_rate < -0.1:
            return "falling"
        else:
            # Check sentiment change
            prev_sentiment = previous["sentiment_avg"] if previous else 0
            sent_change = sentiment - (prev_sentiment or 0)
            if sent_change > 0.15:
                return "improving"
            elif sent_change < -0.15:
                return "worsening"
            return "stable"


# Global singleton
temporal_intel = TemporalIntelligence()
