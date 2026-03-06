"""
Governance & Platform Ops API
Feature flags, experiments, prompts, usage analytics, audit trail, jobs.
"""

import json
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..services.governance_service import GovernanceService
from ..database import get_db


router = APIRouter(prefix="/api/governance", tags=["governance"])


@router.get("/feature-flags")
def list_feature_flags(current_user: dict = Depends(get_current_user)):
    return GovernanceService.list_feature_flags()


@router.post("/feature-flags")
def create_feature_flag(data: dict, current_user: dict = Depends(get_current_user)):
    key = (data.get("key") or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    return GovernanceService.create_feature_flag(
        key=key,
        description=data.get("description", ""),
        is_enabled=bool(data.get("is_enabled", False)),
        rollout_percentage=int(data.get("rollout_percentage", 100)),
        conditions_json=json.dumps(data.get("conditions", {})),
        target_scope=data.get("target_scope", "global"),
        created_by=current_user.get("sub"),
    )


@router.put("/feature-flags/{key}")
def update_feature_flag(key: str, data: dict, current_user: dict = Depends(get_current_user)):
    row = GovernanceService.update_feature_flag(key, data)
    if not row:
        raise HTTPException(status_code=404, detail="Feature flag not found or no valid fields provided")
    return row


@router.post("/feature-flags/{key}/evaluate")
def evaluate_feature_flag(key: str, data: dict, current_user: dict = Depends(get_current_user)):
    user_key = data.get("user_key") or f"user:{current_user.get('sub')}"
    context = data.get("context") or {}
    return GovernanceService.evaluate_flag(key, user_key=user_key, context=context)


@router.get("/experiments")
def list_experiments(current_user: dict = Depends(get_current_user)):
    return GovernanceService.list_experiments()


@router.post("/experiments")
def create_experiment(data: dict, current_user: dict = Depends(get_current_user)):
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    return GovernanceService.create_experiment(
        name=name,
        description=data.get("description", ""),
        feature_flag_key=data.get("feature_flag_key"),
        status=data.get("status", "draft"),
        variants_json=json.dumps(data.get("variants", [])),
        allocation_json=json.dumps(data.get("allocation", {})),
    )


@router.post("/experiments/{experiment_id}/assign")
def assign_experiment_variant(experiment_id: int, data: dict, current_user: dict = Depends(get_current_user)):
    user_key = (data.get("user_key") or f"user:{current_user.get('sub')}").strip()
    if not user_key:
        raise HTTPException(status_code=400, detail="user_key is required")
    row = GovernanceService.assign_experiment_variant(experiment_id, user_key)
    if not row:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return row


@router.get("/prompt-versions")
def list_prompt_versions(name: str | None = Query(None), current_user: dict = Depends(get_current_user)):
    return GovernanceService.list_prompt_versions(name)


@router.post("/prompt-versions")
def create_prompt_version(data: dict, current_user: dict = Depends(get_current_user)):
    name = (data.get("name") or "").strip()
    prompt_text = data.get("prompt_text") or ""
    version = int(data.get("version", 1))
    if not name or not prompt_text:
        raise HTTPException(status_code=400, detail="name and prompt_text are required")
    return GovernanceService.create_prompt_version(
        name=name,
        version=version,
        prompt_text=prompt_text,
        metadata_json=json.dumps(data.get("metadata", {})),
        is_active=bool(data.get("is_active", False)),
        created_by=current_user.get("sub"),
    )


@router.put("/prompt-versions/{name}/{version}/activate")
def activate_prompt_version(name: str, version: int, current_user: dict = Depends(get_current_user)):
    row = GovernanceService.activate_prompt_version(name, version)
    if not row:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    return row


@router.get("/llm-usage")
def list_llm_usage(limit: int = Query(200, ge=1, le=2000), current_user: dict = Depends(get_current_user)):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM llm_usage ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/model-runs")
def list_model_runs(limit: int = Query(200, ge=1, le=2000), current_user: dict = Depends(get_current_user)):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM model_runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/audit-trail")
def list_audit_trail(limit: int = Query(200, ge=1, le=2000), current_user: dict = Depends(get_current_user)):
    return GovernanceService.list_audit_events(limit=limit)


@router.get("/jobs")
def list_jobs(status: str | None = Query(None), limit: int = Query(100, ge=1, le=2000), current_user: dict = Depends(get_current_user)):
    return GovernanceService.list_jobs(status=status, limit=limit)


@router.post("/jobs")
def create_job(data: dict, current_user: dict = Depends(get_current_user)):
    job_type = (data.get("job_type") or "").strip()
    if not job_type:
        raise HTTPException(status_code=400, detail="job_type is required")
    return GovernanceService.create_job(
        job_type=job_type,
        payload_json=json.dumps(data.get("payload", {})),
        run_at=data.get("run_at"),
        created_by=current_user.get("sub"),
        max_attempts=int(data.get("max_attempts", 3)),
    )


@router.put("/jobs/{job_id}/status")
def update_job_status(job_id: int, data: dict, current_user: dict = Depends(get_current_user)):
    status = (data.get("status") or "").strip()
    if not status:
        raise HTTPException(status_code=400, detail="status is required")
    row = GovernanceService.update_job_status(
        job_id,
        status=status,
        result_json=json.dumps(data.get("result", {})) if data.get("result") is not None else None,
        error_message=data.get("error_message", ""),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return row
