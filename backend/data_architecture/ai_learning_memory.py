"""
AI Learning Memory — §12 (Hidden Gold)
═══════════════════════════════════════════════════════
Store AI reasoning history for:
  - Prompt optimization (improve over time)
  - Cost reduction (identify expensive patterns)
  - Decision auditing (explain AI outputs)
  - Model version tracking (compare performance)

Table: ai_analysis_log
  prompt_used, model_version, output, latency, cost

Why?
  Later you can: improve prompts, reduce cost, audit decisions.
"""

import json
import time
import hashlib
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
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


class AILearningMemory:
    """
    AI Learning Memory — stores every AI reasoning step for analysis.

    Capabilities:
      - Log every AI call with prompt, model, output, cost, latency
      - Analyze prompt effectiveness over time
      - Track model version performance
      - Cost analytics and optimization suggestions
      - Identify slow/expensive prompt patterns
      - Detect quality drift in AI outputs
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._session_logs = 0
        self._session_cost = 0.0
        self._session_tokens = 0

    # ─── Core Logging ───

    def log_analysis(self, task_type: str, model_version: str,
                     prompt_used: str = None, output_data: str = None,
                     pipeline_name: str = None, latency_ms: int = 0,
                     input_tokens: int = 0, output_tokens: int = 0,
                     cost_estimate: float = 0.0, was_cached: bool = False,
                     was_fallback: bool = False, error_message: str = None,
                     output_quality_score: float = None,
                     temperature: float = None,
                     context_keys: str = None) -> int:
        """
        Log an AI analysis step to the learning memory.

        Returns the log entry ID.
        """
        prompt_hash = None
        if prompt_used:
            prompt_hash = hashlib.sha256(prompt_used.encode()).hexdigest()[:16]

        # Truncate output if too large
        output_summary = None
        if output_data:
            output_summary = output_data[:5000] if len(output_data) > 5000 else output_data

        input_summary = None
        if prompt_used:
            input_summary = prompt_used[:2000] if len(prompt_used) > 2000 else prompt_used

        try:
            conn = _get_conn()
            conn.execute("""
                INSERT INTO ai_analysis_log (task_type, pipeline_name, prompt_used,
                    prompt_hash, model_version, input_data_summary, output_data,
                    output_quality_score, latency_ms, input_tokens, output_tokens,
                    cost_estimate, was_cached, was_fallback, error_message,
                    context_keys, temperature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (task_type, pipeline_name, prompt_used, prompt_hash,
                  model_version, input_summary, output_summary,
                  output_quality_score, latency_ms, input_tokens, output_tokens,
                  cost_estimate, 1 if was_cached else 0,
                  1 if was_fallback else 0, error_message,
                  context_keys, temperature))
            log_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
            conn.close()

            with self._lock:
                self._session_logs += 1
                self._session_cost += cost_estimate
                self._session_tokens += input_tokens + output_tokens

            return log_id
        except Exception:
            return -1

    # ─── Prompt Effectiveness Analysis ───

    def analyze_prompt_effectiveness(self, task_type: str = None,
                                      days: int = 30) -> Dict[str, Any]:
        """
        Analyze prompt effectiveness: which prompts produce best quality at lowest cost.
        Groups by prompt_hash to find patterns.
        """
        conn = _get_conn()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        query = """
            SELECT prompt_hash, task_type,
                   COUNT(*) as usage_count,
                   AVG(latency_ms) as avg_latency,
                   AVG(output_quality_score) as avg_quality,
                   AVG(cost_estimate) as avg_cost,
                   SUM(cost_estimate) as total_cost,
                   AVG(input_tokens) as avg_input_tokens,
                   AVG(output_tokens) as avg_output_tokens,
                   SUM(CASE WHEN error_message IS NOT NULL THEN 1 ELSE 0 END) as error_count,
                   SUM(CASE WHEN was_cached = 1 THEN 1 ELSE 0 END) as cache_hits
            FROM ai_analysis_log
            WHERE created_at >= ?
        """
        params = [cutoff]

        if task_type:
            query += " AND task_type = ?"
            params.append(task_type)

        query += " GROUP BY prompt_hash ORDER BY avg_quality DESC NULLS LAST"

        results = conn.execute(query, params).fetchall()
        conn.close()

        prompts = []
        for r in results:
            rd = dict(r)
            efficiency = 0
            if rd["avg_cost"] and rd["avg_cost"] > 0 and rd["avg_quality"]:
                efficiency = rd["avg_quality"] / rd["avg_cost"]

            prompts.append({
                "prompt_hash": rd["prompt_hash"],
                "task_type": rd["task_type"],
                "usage_count": rd["usage_count"],
                "avg_latency_ms": int(rd["avg_latency"] or 0),
                "avg_quality": round(rd["avg_quality"] or 0, 3),
                "avg_cost": round(rd["avg_cost"] or 0, 6),
                "total_cost": round(rd["total_cost"] or 0, 4),
                "error_rate": round(rd["error_count"] / max(rd["usage_count"], 1), 3),
                "cache_hit_rate": round(rd["cache_hits"] / max(rd["usage_count"], 1), 3),
                "efficiency_score": round(efficiency, 2),
            })

        return {
            "period_days": days,
            "task_type": task_type or "all",
            "total_prompt_patterns": len(prompts),
            "prompts": prompts[:50],
        }

    # ─── Model Performance Comparison ───

    def compare_models(self, days: int = 30) -> Dict[str, Any]:
        """Compare AI model performance across all tasks."""
        conn = _get_conn()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        models = conn.execute("""
            SELECT model_version,
                   COUNT(*) as total_calls,
                   AVG(latency_ms) as avg_latency,
                   AVG(output_quality_score) as avg_quality,
                   SUM(cost_estimate) as total_cost,
                   AVG(cost_estimate) as avg_cost,
                   SUM(input_tokens + output_tokens) as total_tokens,
                   SUM(CASE WHEN error_message IS NOT NULL THEN 1 ELSE 0 END) as errors,
                   SUM(CASE WHEN was_fallback = 1 THEN 1 ELSE 0 END) as fallbacks,
                   SUM(CASE WHEN was_cached = 1 THEN 1 ELSE 0 END) as cache_hits
            FROM ai_analysis_log
            WHERE created_at >= ?
            GROUP BY model_version
            ORDER BY total_calls DESC
        """, (cutoff,)).fetchall()
        conn.close()

        return {
            "period_days": days,
            "models": [
                {
                    "model": m["model_version"],
                    "total_calls": m["total_calls"],
                    "avg_latency_ms": int(m["avg_latency"] or 0),
                    "avg_quality": round(m["avg_quality"] or 0, 3),
                    "total_cost": round(m["total_cost"] or 0, 4),
                    "avg_cost_per_call": round(m["avg_cost"] or 0, 6),
                    "total_tokens": m["total_tokens"] or 0,
                    "error_rate": round(m["errors"] / max(m["total_calls"], 1), 3),
                    "fallback_rate": round(m["fallbacks"] / max(m["total_calls"], 1), 3),
                    "cache_hit_rate": round(m["cache_hits"] / max(m["total_calls"], 1), 3),
                }
                for m in models
            ],
        }

    # ─── Cost Analytics ───

    def get_cost_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get AI cost breakdown and optimization suggestions."""
        conn = _get_conn()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        # Daily cost breakdown
        daily = conn.execute("""
            SELECT DATE(created_at) as day,
                   SUM(cost_estimate) as cost,
                   COUNT(*) as calls,
                   SUM(input_tokens + output_tokens) as tokens
            FROM ai_analysis_log
            WHERE created_at >= ?
            GROUP BY DATE(created_at)
            ORDER BY day
        """, (cutoff,)).fetchall()

        # By task type
        by_task = conn.execute("""
            SELECT task_type,
                   SUM(cost_estimate) as cost,
                   COUNT(*) as calls,
                   AVG(latency_ms) as avg_latency
            FROM ai_analysis_log
            WHERE created_at >= ?
            GROUP BY task_type
            ORDER BY cost DESC
        """, (cutoff,)).fetchall()

        # Total spend
        totals = conn.execute("""
            SELECT SUM(cost_estimate) as total_cost,
                   COUNT(*) as total_calls,
                   SUM(input_tokens) as total_input_tokens,
                   SUM(output_tokens) as total_output_tokens,
                   SUM(CASE WHEN was_cached = 1 THEN cost_estimate ELSE 0 END) as cost_saved_cache
            FROM ai_analysis_log
            WHERE created_at >= ?
        """, (cutoff,)).fetchone()  
        conn.close()

        t = dict(totals) if totals else {}

        # Generate optimization suggestions
        suggestions = self._generate_cost_suggestions(t, [dict(r) for r in by_task])

        return {
            "period_days": days,
            "total_cost": round(t.get("total_cost") or 0, 4),
            "total_calls": t.get("total_calls") or 0,
            "total_tokens": (t.get("total_input_tokens") or 0) + (t.get("total_output_tokens") or 0),
            "cost_saved_by_cache": round(t.get("cost_saved_cache") or 0, 4),
            "daily_breakdown": [
                {"date": d["day"], "cost": round(d["cost"] or 0, 4),
                 "calls": d["calls"], "tokens": d["tokens"] or 0}
                for d in daily
            ],
            "by_task_type": [
                {"task": bt["task_type"], "cost": round(bt["cost"] or 0, 4),
                 "calls": bt["calls"], "avg_latency_ms": int(bt["avg_latency"] or 0)}
                for bt in by_task
            ],
            "optimization_suggestions": suggestions,
        }

    # ─── Quality Drift Detection ───

    def detect_quality_drift(self, task_type: str, window_days: int = 7) -> Dict[str, Any]:
        """
        Detect if AI output quality is drifting over time.
        Compares recent quality scores against historical baseline.
        """
        conn = _get_conn()
        now = datetime.now()

        # Recent window
        recent_cutoff = (now - timedelta(days=window_days)).isoformat()
        recent = conn.execute("""
            SELECT AVG(output_quality_score) as avg_quality,
                   COUNT(*) as sample_size
            FROM ai_analysis_log
            WHERE task_type = ? AND created_at >= ? AND output_quality_score IS NOT NULL
        """, (task_type, recent_cutoff)).fetchone()

        # Historical baseline (previous period)
        hist_start = (now - timedelta(days=window_days * 2)).isoformat()
        hist_end = recent_cutoff
        historical = conn.execute("""
            SELECT AVG(output_quality_score) as avg_quality,
                   COUNT(*) as sample_size
            FROM ai_analysis_log
            WHERE task_type = ? AND created_at >= ? AND created_at < ?
              AND output_quality_score IS NOT NULL
        """, (task_type, hist_start, hist_end)).fetchone()
        conn.close()

        recent_quality = recent["avg_quality"] if recent and recent["avg_quality"] else 0
        hist_quality = historical["avg_quality"] if historical and historical["avg_quality"] else 0
        drift = recent_quality - hist_quality

        return {
            "task_type": task_type,
            "window_days": window_days,
            "recent_quality": round(recent_quality, 3),
            "historical_quality": round(hist_quality, 3),
            "quality_drift": round(drift, 3),
            "drift_direction": "improving" if drift > 0.05 else ("degrading" if drift < -0.05 else "stable"),
            "recent_sample_size": recent["sample_size"] if recent else 0,
            "historical_sample_size": historical["sample_size"] if historical else 0,
            "alert": abs(drift) > 0.15,
        }

    # ─── Recent Log Retrieval ───

    def get_recent_logs(self, limit: int = 50, task_type: str = None,
                        errors_only: bool = False) -> List[Dict[str, Any]]:
        """Get recent AI analysis logs."""
        conn = _get_conn()
        query = "SELECT * FROM ai_analysis_log WHERE 1=1"
        params = []

        if task_type:
            query += " AND task_type = ?"
            params.append(task_type)
        if errors_only:
            query += " AND error_message IS NOT NULL"

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ─── Stats ───

    def stats(self) -> Dict[str, Any]:
        """Get AI learning memory statistics."""
        conn = None
        try:
            conn = _get_conn()
            totals = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(cost_estimate) as cost,
                       AVG(latency_ms) as avg_latency,
                       COUNT(DISTINCT model_version) as models_used,
                       COUNT(DISTINCT task_type) as task_types,
                       COUNT(DISTINCT prompt_hash) as unique_prompts
                FROM ai_analysis_log
            """).fetchone()
            t = dict(totals) if totals else {}
        except Exception:
            t = {}
        finally:
            if conn:
                conn.close()

        return {
            "total_logs": t.get("total", 0),
            "total_cost": round(t.get("cost") or 0, 4),
            "avg_latency_ms": int(t.get("avg_latency") or 0),
            "models_used": t.get("models_used", 0),
            "task_types": t.get("task_types", 0),
            "unique_prompts": t.get("unique_prompts", 0),
            "session_logs": self._session_logs,
            "session_cost": round(self._session_cost, 4),
            "session_tokens": self._session_tokens,
        }

    # ─── Private Helpers ───

    def _generate_cost_suggestions(self, totals: dict,
                                    by_task: List[dict]) -> List[str]:
        """Generate cost optimization suggestions based on usage patterns."""
        suggestions = []
        total_cost = totals.get("total_cost") or 0
        total_calls = totals.get("total_calls") or 0

        if total_calls == 0:
            return ["No AI calls recorded yet. Start using AI features to generate insights."]

        # High frequency tasks
        for task in by_task[:3]:
            if task["calls"] > total_calls * 0.3:
                suggestions.append(
                    f"'{task['task_type']}' accounts for {task['calls']}/{total_calls} calls "
                    f"({round(task['calls']/total_calls*100)}%). Consider caching or batching."
                )

        # Slow tasks
        for task in by_task:
            if (task.get("avg_latency") or 0) > 5000:
                suggestions.append(
                    f"'{task['task_type']}' has high avg latency ({int(task['avg_latency'])}ms). "
                    f"Consider prompt optimization or model downgrade for speed."
                )

        # Cache savings
        cache_saved = totals.get("cost_saved_cache") or 0
        if total_cost > 0:
            cache_ratio = cache_saved / total_cost
            if cache_ratio < 0.1:
                suggestions.append(
                    "Cache hit rate is low. Enable aggressive caching for repeated analyses."
                )

        if not suggestions:
            suggestions.append("AI usage patterns look efficient. No immediate optimizations needed.")

        return suggestions


# Global singleton
ai_memory = AILearningMemory()
