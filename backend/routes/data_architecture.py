"""
Data Architecture API Routes
═══════════════════════════════════════════════════════
REST endpoints for the 5-layer data architecture.

Groups:
  /api/data/pipeline     — Data Pipeline (§7)
  /api/data/layers       — Layer statistics (§2-6)
  /api/data/temporal     — Temporal Intelligence (§10)
  /api/data/incremental  — Incremental Processing (§11)
  /api/data/ai-memory    — AI Learning Memory (§12)
  /api/data/governance   — Governance & Privacy (§13)
  /api/data/overview     — Architecture overview
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import date

router = APIRouter(prefix="/api/data", tags=["Data Architecture"])


# ═══════════════════════════════════════════════════
# LAYER STATISTICS (§2-6)
# ═══════════════════════════════════════════════════

@router.get("/layers/stats")
def get_layer_stats():
    """Get record counts across all 5 data layers."""
    from ..data_architecture.schema import get_layer_stats
    return {"layers": get_layer_stats()}


# ═══════════════════════════════════════════════════
# DATA PIPELINE (§7)
# ═══════════════════════════════════════════════════

@router.get("/pipeline/stats")
def get_pipeline_stats():
    """Get data pipeline processing statistics."""
    from ..data_architecture.data_pipeline import data_pipeline
    return data_pipeline.stats()


@router.post("/pipeline/process/{response_id}")
def process_single_response(response_id: int, survey_id: int, session_id: str,
                             response_text: str = ""):
    """Process a single response through the full 5-layer pipeline."""
    from ..data_architecture.data_pipeline import data_pipeline
    result = data_pipeline.process_response(
        response_id=response_id, survey_id=survey_id,
        session_id=session_id, response_text=response_text
    )
    return result


@router.post("/pipeline/batch/{survey_id}")
def process_batch(survey_id: int, limit: int = Query(100, ge=1, le=1000)):
    """Process unprocessed responses in batch through the pipeline."""
    from ..data_architecture.data_pipeline import data_pipeline
    return data_pipeline.process_batch(survey_id, limit)


@router.get("/pipeline/state/{survey_id}")
def get_processing_state(survey_id: int):
    """Get processing state summary for a survey."""
    from ..data_architecture.incremental_processor import incremental_processor
    return incremental_processor.get_processing_summary(survey_id)


@router.get("/pipeline/unprocessed/{survey_id}")
def get_unprocessed_responses(survey_id: int,
                               limit: int = Query(50, ge=1, le=500)):
    """Get responses that haven't completed full pipeline processing."""
    from ..data_architecture.incremental_processor import incremental_processor
    return {"unprocessed": incremental_processor.get_unprocessed(survey_id, limit)}


# ═══════════════════════════════════════════════════
# TEMPORAL INTELLIGENCE (§10)
# ═══════════════════════════════════════════════════

@router.post("/temporal/snapshot/{survey_id}")
def take_temporal_snapshot(survey_id: int):
    """Take a point-in-time snapshot of insight clusters for trend tracking."""
    from ..data_architecture.temporal_intelligence import temporal_intel
    return temporal_intel.take_snapshot(survey_id)


@router.get("/temporal/trends/{survey_id}")
def get_trends(survey_id: int, days: int = Query(30, ge=1, le=365)):
    """Get trend analysis: rising, falling, stable, and emerging themes."""
    from ..data_architecture.temporal_intelligence import temporal_intel
    return temporal_intel.get_trends(survey_id, days)


@router.get("/temporal/drift/{survey_id}")
def detect_sentiment_drift(survey_id: int,
                            threshold: float = Query(0.2, ge=0.05, le=1.0),
                            days: int = Query(14, ge=1, le=90)):
    """Detect significant sentiment shifts in insight clusters."""
    from ..data_architecture.temporal_intelligence import temporal_intel
    return {
        "drifts": temporal_intel.detect_sentiment_drift(survey_id, threshold, days)
    }


@router.get("/temporal/emerging/{survey_id}")
def detect_emerging_themes(survey_id: int,
                            min_growth: float = Query(0.5, ge=0.1, le=5.0),
                            days: int = Query(7, ge=1, le=30)):
    """Detect newly emerging themes with rapid growth."""
    from ..data_architecture.temporal_intelligence import temporal_intel
    return {
        "emerging": temporal_intel.detect_emerging_themes(survey_id, min_growth, days)
    }


@router.get("/temporal/timeline/{survey_id}")
def get_theme_timeline(survey_id: int, theme: str = Query(..., min_length=1),
                        days: int = Query(90, ge=1, le=365)):
    """Get complete timeline for a specific theme."""
    from ..data_architecture.temporal_intelligence import temporal_intel
    return {
        "theme": theme,
        "timeline": temporal_intel.get_theme_timeline(survey_id, theme, days)
    }


@router.get("/temporal/stats")
def get_temporal_stats():
    """Get temporal intelligence engine statistics."""
    from ..data_architecture.temporal_intelligence import temporal_intel
    return temporal_intel.stats()


# ═══════════════════════════════════════════════════
# INCREMENTAL PROCESSING (§11)
# ═══════════════════════════════════════════════════

@router.get("/incremental/stats")
def get_incremental_stats():
    """Get incremental processing statistics."""
    from ..data_architecture.incremental_processor import incremental_processor
    return incremental_processor.stats()


@router.post("/incremental/delta/{survey_id}")
def process_delta(survey_id: int):
    """Process only the dirty/changed responses (incremental delta)."""
    from ..data_architecture.incremental_processor import incremental_processor
    return incremental_processor.process_delta(survey_id)


@router.post("/incremental/consolidate/{survey_id}")
def consolidate_data(survey_id: int):
    """Run full data consolidation for consistency verification."""
    from ..data_architecture.incremental_processor import incremental_processor
    return incremental_processor.consolidate(survey_id)


@router.post("/incremental/retry-failed/{survey_id}")
def retry_failed_processing(survey_id: int,
                             max_retries: int = Query(3, ge=1, le=10)):
    """Retry responses that failed during pipeline processing."""
    from ..data_architecture.incremental_processor import incremental_processor
    return incremental_processor.retry_failed(survey_id, max_retries)


# ═══════════════════════════════════════════════════
# AI LEARNING MEMORY (§12)
# ═══════════════════════════════════════════════════

@router.get("/ai-memory/stats")
def get_ai_memory_stats():
    """Get AI learning memory statistics."""
    from ..data_architecture.ai_learning_memory import ai_memory
    return ai_memory.stats()


@router.get("/ai-memory/prompts")
def analyze_prompts(task_type: Optional[str] = None,
                    days: int = Query(30, ge=1, le=365)):
    """Analyze prompt effectiveness across AI tasks."""
    from ..data_architecture.ai_learning_memory import ai_memory
    return ai_memory.analyze_prompt_effectiveness(task_type, days)


@router.get("/ai-memory/models")
def compare_models(days: int = Query(30, ge=1, le=365)):
    """Compare AI model performance."""
    from ..data_architecture.ai_learning_memory import ai_memory
    return ai_memory.compare_models(days)


@router.get("/ai-memory/costs")
def get_cost_analytics(days: int = Query(30, ge=1, le=365)):
    """Get AI cost breakdown and optimization suggestions."""
    from ..data_architecture.ai_learning_memory import ai_memory
    return ai_memory.get_cost_analytics(days)


@router.get("/ai-memory/quality-drift")
def check_quality_drift(task_type: str = Query(..., min_length=1),
                         window_days: int = Query(7, ge=1, le=90)):
    """Detect quality drift in AI outputs for a task type."""
    from ..data_architecture.ai_learning_memory import ai_memory
    return ai_memory.detect_quality_drift(task_type, window_days)


@router.get("/ai-memory/logs")
def get_ai_logs(limit: int = Query(50, ge=1, le=500),
                task_type: Optional[str] = None,
                errors_only: bool = False):
    """Get recent AI analysis logs."""
    from ..data_architecture.ai_learning_memory import ai_memory
    return {"logs": ai_memory.get_recent_logs(limit, task_type, errors_only)}


# ═══════════════════════════════════════════════════
# GOVERNANCE & PRIVACY (§13)
# ═══════════════════════════════════════════════════

@router.get("/governance/stats")
def get_governance_stats():
    """Get data governance statistics."""
    from ..data_architecture.data_governance import data_governance
    return data_governance.stats()


@router.get("/governance/compliance")
def get_compliance_report():
    """Generate a data governance compliance report."""
    from ..data_architecture.data_governance import data_governance
    return data_governance.compliance_report()


@router.get("/governance/audit")
def get_audit_log(limit: int = Query(50, ge=1, le=500),
                  action: Optional[str] = None,
                  entity_type: Optional[str] = None,
                  actor: Optional[str] = None):
    """Query the data audit trail."""
    from ..data_architecture.data_governance import data_governance
    return {"audit_log": data_governance.get_audit_log(limit, action, entity_type, actor)}


@router.get("/governance/pii")
def get_pii_stats():
    """Get PII detection statistics."""
    from ..data_architecture.data_governance import data_governance
    return data_governance.get_pii_stats()


@router.post("/governance/pii/scan")
def scan_text_for_pii(text: str = ""):
    """Scan text for PII (for testing/demo)."""
    from ..data_architecture.data_governance import PIIMasker
    detections = PIIMasker.detect_pii(text)
    masked, count = PIIMasker.mask_pii(text)
    return {
        "original_length": len(text),
        "detections": detections,
        "masked_text": masked,
        "pii_count": count,
    }


@router.get("/governance/retention")
def get_retention_policies():
    """Get data retention policies."""
    from ..data_architecture.schema import _get_conn
    conn = _get_conn()
    policies = conn.execute("SELECT * FROM data_retention_policy").fetchall()
    conn.close()
    return {"policies": [dict(p) for p in policies]}


@router.post("/governance/retention/enforce")
def enforce_retention(dry_run: bool = Query(True)):
    """Enforce data retention policies. Use dry_run=true to preview."""
    from ..data_architecture.data_governance import data_governance
    return data_governance.enforce_retention(dry_run)


@router.get("/governance/roles")
def get_access_roles():
    """Get role-based access control definitions."""
    from ..data_architecture.data_governance import DataGovernance
    return {"roles": DataGovernance.ROLE_PERMISSIONS}


# ═══════════════════════════════════════════════════
# ARCHITECTURE OVERVIEW
# ═══════════════════════════════════════════════════

@router.get("/overview")
def data_architecture_overview():
    """Master overview of the entire data architecture."""
    from ..data_architecture.data_pipeline import data_pipeline
    from ..data_architecture.temporal_intelligence import temporal_intel
    from ..data_architecture.incremental_processor import incremental_processor
    from ..data_architecture.ai_learning_memory import ai_memory
    from ..data_architecture.data_governance import data_governance
    from ..data_architecture.schema import get_layer_stats

    return {
        "architecture": "5-Layer Intelligence Data Model",
        "philosophy": "Never destroy raw data. Always layer intelligence on top.",
        "layers": get_layer_stats(),
        "pipeline": data_pipeline.stats(),
        "temporal": temporal_intel.stats(),
        "incremental": incremental_processor.stats(),
        "ai_memory": ai_memory.stats(),
        "governance": data_governance.stats(),
    }


@router.get("/architecture")
def data_architecture_info():
    """Data architecture specification and design details."""
    return {
        "name": "5-Layer Intelligence Data Architecture",
        "version": "1.0.0",
        "golden_rule": "Never destroy raw data. Always layer intelligence on top.",
        "layers": {
            "layer_1_raw": {
                "name": "Raw Data Layer (Source of Truth)",
                "table": "raw_responses",
                "section": "§2",
                "status": "implemented",
            },
            "layer_2_normalized": {
                "name": "Normalized Data Layer",
                "table": "normalized_responses",
                "section": "§3",
                "status": "implemented",
            },
            "layer_3_enrichment": {
                "name": "AI Enrichment Layer",
                "table": "ai_enrichment",
                "section": "§4",
                "status": "implemented",
            },
            "layer_4_clusters": {
                "name": "Insight Aggregation Layer",
                "table": "insight_clusters",
                "section": "§5",
                "status": "implemented",
            },
            "layer_5_recommendations": {
                "name": "Decision / Recommendation Layer",
                "table": "recommendation_actions",
                "section": "§6",
                "status": "implemented",
            },
        },
        "supporting_modules": {
            "data_pipeline": {"section": "§7", "module": "data_architecture.data_pipeline"},
            "conversation_analytics": {"section": "§8", "table": "conversation_analytics"},
            "voice_analytics": {"section": "§9", "table": "voice_analytics"},
            "temporal_intelligence": {"section": "§10", "module": "data_architecture.temporal_intelligence"},
            "incremental_processing": {"section": "§11", "module": "data_architecture.incremental_processor"},
            "ai_learning_memory": {"section": "§12", "module": "data_architecture.ai_learning_memory"},
            "data_governance": {"section": "§13", "module": "data_architecture.data_governance"},
        },
        "evolution_roadmap": {
            "mvp": "SQLite single DB — CURRENT",
            "growth": "Split: Operational DB + Analytics DB + AI Metadata DB",
            "scale": "Data warehouse: OLTP → OLAP pipeline",
        },
        "endpoints": {
            "layers": "/api/data/layers/stats",
            "pipeline": "/api/data/pipeline/stats",
            "temporal": "/api/data/temporal/stats",
            "incremental": "/api/data/incremental/stats",
            "ai_memory": "/api/data/ai-memory/stats",
            "governance": "/api/data/governance/stats",
            "overview": "/api/data/overview",
        },
    }
