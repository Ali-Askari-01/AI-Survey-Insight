"""
Governance Service
Feature flags, experiments, prompt registry, usage logging, audit trail, and job tracking.
"""

import hashlib
import json
from datetime import datetime
from typing import Optional

from ..database import get_db


class GovernanceService:
    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()

    @staticmethod
    def _stable_bucket(key: str) -> int:
        digest = hashlib.md5(key.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % 100

    # ---------------- Feature Flags ----------------
    @staticmethod
    def list_feature_flags() -> list[dict]:
        conn = get_db()
        try:
            rows = conn.execute("SELECT * FROM feature_flags ORDER BY key").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def create_feature_flag(key: str, description: str = "", is_enabled: bool = False,
                            rollout_percentage: int = 100, conditions_json: str = "{}",
                            target_scope: str = "global", created_by: Optional[int] = None) -> dict:
        conn = get_db()
        try:
            conn.execute(
                """
                INSERT INTO feature_flags
                (key, description, is_enabled, rollout_percentage, conditions_json, target_scope, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (key, description, 1 if is_enabled else 0, max(0, min(100, rollout_percentage)),
                 conditions_json or "{}", target_scope, created_by, GovernanceService._now(), GovernanceService._now())
            )
            conn.commit()
            row = conn.execute("SELECT * FROM feature_flags WHERE key = ?", (key,)).fetchone()
            return dict(row)
        finally:
            conn.close()

    @staticmethod
    def update_feature_flag(key: str, patch: dict) -> Optional[dict]:
        allowed = {"description", "is_enabled", "rollout_percentage", "conditions_json", "target_scope"}
        updates = {k: v for k, v in patch.items() if k in allowed}
        if not updates:
            return None

        if "is_enabled" in updates:
            updates["is_enabled"] = 1 if bool(updates["is_enabled"]) else 0
        if "rollout_percentage" in updates:
            updates["rollout_percentage"] = max(0, min(100, int(updates["rollout_percentage"])))
        updates["updated_at"] = GovernanceService._now()

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [key]

        conn = get_db()
        try:
            conn.execute(f"UPDATE feature_flags SET {set_clause} WHERE key = ?", values)
            conn.commit()
            row = conn.execute("SELECT * FROM feature_flags WHERE key = ?", (key,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def evaluate_flag(key: str, user_key: Optional[str] = None, context: Optional[dict] = None) -> dict:
        conn = get_db()
        try:
            row = conn.execute("SELECT * FROM feature_flags WHERE key = ?", (key,)).fetchone()
            if not row:
                return {"flag_key": key, "enabled": False, "reason": "flag_not_found"}

            flag = dict(row)
            if not bool(flag.get("is_enabled")):
                return {"flag_key": key, "enabled": False, "reason": "disabled"}

            rollout = int(flag.get("rollout_percentage", 100))
            if user_key:
                bucket = GovernanceService._stable_bucket(f"{key}:{user_key}")
                enabled = bucket < rollout
            else:
                enabled = rollout >= 100

            return {
                "flag_key": key,
                "enabled": enabled,
                "reason": "rollout_pass" if enabled else "rollout_filtered",
                "rollout_percentage": rollout,
                "user_key": user_key,
                "context": context or {},
            }
        finally:
            conn.close()

    # ---------------- Experiments ----------------
    @staticmethod
    def list_experiments() -> list[dict]:
        conn = get_db()
        try:
            rows = conn.execute("SELECT * FROM ab_experiments ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def create_experiment(name: str, description: str = "", feature_flag_key: Optional[str] = None,
                          status: str = "draft", variants_json: str = "[]", allocation_json: str = "{}") -> dict:
        conn = get_db()
        try:
            conn.execute(
                """
                INSERT INTO ab_experiments
                (name, description, feature_flag_key, status, variants_json, allocation_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, description, feature_flag_key, status, variants_json or "[]", allocation_json or "{}",
                 GovernanceService._now(), GovernanceService._now())
            )
            conn.commit()
            row = conn.execute("SELECT * FROM ab_experiments WHERE name = ?", (name,)).fetchone()
            return dict(row)
        finally:
            conn.close()

    @staticmethod
    def assign_experiment_variant(experiment_id: int, user_key: str) -> Optional[dict]:
        conn = get_db()
        try:
            existing = conn.execute(
                "SELECT * FROM experiment_assignments WHERE experiment_id = ? AND user_key = ?",
                (experiment_id, user_key),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE experiment_assignments SET last_seen_at = ? WHERE id = ?",
                    (GovernanceService._now(), dict(existing)["id"]),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM experiment_assignments WHERE id = ?", (dict(existing)["id"],)).fetchone()
                return dict(row)

            exp = conn.execute("SELECT * FROM ab_experiments WHERE id = ?", (experiment_id,)).fetchone()
            if not exp:
                return None
            exp_d = dict(exp)

            variants = json.loads(exp_d.get("variants_json") or "[]")
            allocation = json.loads(exp_d.get("allocation_json") or "{}")
            if not variants:
                variants = ["control", "variant_a"]
                allocation = {"control": 50, "variant_a": 50}

            bucket = GovernanceService._stable_bucket(f"exp:{experiment_id}:{user_key}")
            running = 0
            selected = variants[0]
            for v in variants:
                running += int(allocation.get(v, 0))
                if bucket < running:
                    selected = v
                    break

            conn.execute(
                """
                INSERT INTO experiment_assignments (experiment_id, user_key, variant, assigned_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (experiment_id, user_key, selected, GovernanceService._now(), GovernanceService._now()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM experiment_assignments WHERE experiment_id = ? AND user_key = ?",
                (experiment_id, user_key),
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    # ---------------- Prompt Registry ----------------
    @staticmethod
    def list_prompt_versions(name: Optional[str] = None) -> list[dict]:
        conn = get_db()
        try:
            if name:
                rows = conn.execute(
                    "SELECT * FROM prompt_versions WHERE name = ? ORDER BY version DESC", (name,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM prompt_versions ORDER BY created_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def create_prompt_version(name: str, version: int, prompt_text: str,
                              metadata_json: str = "{}", is_active: bool = False,
                              created_by: Optional[int] = None) -> dict:
        conn = get_db()
        try:
            if is_active:
                conn.execute("UPDATE prompt_versions SET is_active = 0 WHERE name = ?", (name,))
            conn.execute(
                """
                INSERT INTO prompt_versions
                (name, version, prompt_text, metadata_json, is_active, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (name, version, prompt_text, metadata_json or "{}", 1 if is_active else 0, created_by, GovernanceService._now()),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM prompt_versions WHERE name = ? AND version = ?", (name, version)).fetchone()
            return dict(row)
        finally:
            conn.close()

    @staticmethod
    def activate_prompt_version(name: str, version: int) -> Optional[dict]:
        conn = get_db()
        try:
            row = conn.execute("SELECT * FROM prompt_versions WHERE name = ? AND version = ?", (name, version)).fetchone()
            if not row:
                return None
            conn.execute("UPDATE prompt_versions SET is_active = 0 WHERE name = ?", (name,))
            conn.execute(
                "UPDATE prompt_versions SET is_active = 1 WHERE name = ? AND version = ?",
                (name, version),
            )
            conn.commit()
            active = conn.execute("SELECT * FROM prompt_versions WHERE name = ? AND version = ?", (name, version)).fetchone()
            return dict(active)
        finally:
            conn.close()

    # ---------------- LLM Usage / Model Runs ----------------
    @staticmethod
    def log_llm_usage(endpoint: str, feature_name: str, model_name: str,
                      prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0,
                      latency_ms: int = 0, success: bool = True, error_message: str = "",
                      survey_id: Optional[int] = None, session_id: Optional[str] = None,
                      user_id: Optional[int] = None):
        conn = get_db()
        try:
            conn.execute(
                """
                INSERT INTO llm_usage
                (endpoint, feature_name, model_name, prompt_tokens, completion_tokens, total_tokens,
                 latency_ms, success, error_message, survey_id, session_id, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (endpoint, feature_name, model_name, prompt_tokens, completion_tokens, total_tokens,
                 latency_ms, 1 if success else 0, error_message, survey_id, session_id, user_id, GovernanceService._now()),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def log_model_run(prompt_version_id: Optional[int], feature_name: str, model_name: str,
                      input_hash: str = "", output_hash: str = "", latency_ms: int = 0,
                      success: bool = True, error_message: str = "",
                      survey_id: Optional[int] = None, session_id: Optional[str] = None,
                      user_id: Optional[int] = None):
        conn = get_db()
        try:
            conn.execute(
                """
                INSERT INTO model_runs
                (prompt_version_id, feature_name, model_name, input_hash, output_hash,
                 latency_ms, success, error_message, survey_id, session_id, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (prompt_version_id, feature_name, model_name, input_hash, output_hash,
                 latency_ms, 1 if success else 0, error_message, survey_id, session_id, user_id, GovernanceService._now()),
            )
            conn.commit()
        finally:
            conn.close()

    # ---------------- Audit Trail ----------------
    @staticmethod
    def log_audit_event(action: str, path: str, method: str, status_code: int,
                        user_id: Optional[int] = None, resource_type: str = "api",
                        resource_id: Optional[str] = None, ip_address: str = "",
                        user_agent: str = "", metadata: Optional[dict] = None):
        conn = get_db()
        try:
            conn.execute(
                """
                INSERT INTO audit_trail
                (user_id, action, resource_type, resource_id, path, method, status_code,
                 ip_address, user_agent, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, action, resource_type, resource_id, path, method, status_code,
                 ip_address, user_agent, json.dumps(metadata or {}), GovernanceService._now()),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def list_audit_events(limit: int = 200) -> list[dict]:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM audit_trail ORDER BY created_at DESC LIMIT ?",
                (max(1, min(1000, limit)),),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ---------------- Jobs ----------------
    @staticmethod
    def create_job(job_type: str, payload_json: str = "{}", run_at: Optional[str] = None,
                   created_by: Optional[int] = None, max_attempts: int = 3) -> dict:
        conn = get_db()
        try:
            now = GovernanceService._now()
            conn.execute(
                """
                INSERT INTO jobs
                (job_type, status, payload_json, max_attempts, run_at, created_by, created_at, updated_at)
                VALUES (?, 'queued', ?, ?, ?, ?, ?, ?)
                """,
                (job_type, payload_json or "{}", max(1, max_attempts), run_at or now, created_by, now, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT 1").fetchone()
            return dict(row)
        finally:
            conn.close()

    @staticmethod
    def list_jobs(status: Optional[str] = None, limit: int = 100) -> list[dict]:
        conn = get_db()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, max(1, min(1000, limit))),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                    (max(1, min(1000, limit)),),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def update_job_status(job_id: int, status: str, result_json: Optional[str] = None,
                          error_message: str = "") -> Optional[dict]:
        conn = get_db()
        try:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            now = GovernanceService._now()
            started_at = now if status == "running" and not dict(row).get("started_at") else dict(row).get("started_at")
            finished_at = now if status in ("succeeded", "failed", "cancelled") else None

            conn.execute(
                """
                UPDATE jobs
                SET status = ?, result_json = COALESCE(?, result_json), error_message = ?,
                    started_at = COALESCE(?, started_at), finished_at = COALESCE(?, finished_at), updated_at = ?
                WHERE id = ?
                """,
                (status, result_json, error_message, started_at, finished_at, now, job_id),
            )
            conn.commit()
            updated = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return dict(updated)
        finally:
            conn.close()
