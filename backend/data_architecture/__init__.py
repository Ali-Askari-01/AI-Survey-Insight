"""
Data Architecture Package — 5-Layer Intelligence Data Model
═══════════════════════════════════════════════════════════════
Philosophy: Never destroy raw data. Always layer intelligence on top.

Layers:
  Layer 1 — Raw Data Layer (Source of Truth)
  Layer 2 — Normalized Data Layer
  Layer 3 — AI Enrichment Layer
  Layer 4 — Insight Aggregation Layer
  Layer 5 — Decision / Recommendation Layer

Supporting:
  - Data Pipeline Orchestrator (§7)
  - Conversation Data Modeling (§8)
  - Voice Data Architecture (§9)
  - Temporal Intelligence (§10)
  - Incremental Processing (§11)
  - AI Learning Memory (§12)
  - Data Governance & Privacy (§13)
"""

from .schema import init_data_architecture_tables
from .data_pipeline import DataPipelineOrchestrator, data_pipeline
from .temporal_intelligence import TemporalIntelligence, temporal_intel
from .incremental_processor import IncrementalProcessor, incremental_processor
from .ai_learning_memory import AILearningMemory, ai_memory
from .data_governance import DataGovernance, PIIMasker, data_governance

__all__ = [
    # Schema
    "init_data_architecture_tables",
    # Pipeline
    "DataPipelineOrchestrator", "data_pipeline",
    # Temporal
    "TemporalIntelligence", "temporal_intel",
    # Incremental
    "IncrementalProcessor", "incremental_processor",
    # AI Memory
    "AILearningMemory", "ai_memory",
    # Governance
    "DataGovernance", "PIIMasker", "data_governance",
]
