"""
Performance & Reliability Architecture Package
═══════════════════════════════════════════════════════
Production stability layer for the AI Feedback Insight Engine.
Covers §2-18 of the Performance & Reliability Architecture spec.

Modules:
  latency_manager   — §3-4  Soft/hard timeouts, per-endpoint latency budgets
  sla_tracker        — §5,16 SLA definitions, p50/p95/p99 tracking, alerts
  degradation        — §6,15 Graceful degradation controller
  service_isolation   — §7   Concurrency limiters / bulkheads per service
  load_protector     — §9   Adaptive backpressure, queue-depth rate limiting
  db_reliability     — §10  Scheduled backups, rotation, verification
  idempotency        — §12  API-level idempotency keys
  auto_recovery      — §14  Self-healing, recovery playbooks
  reliability_testing — §17  Chaos testing, fault injection, stress harness
"""

from .latency_manager import LatencyManager, latency_manager, TimeoutTier
from .sla_tracker import SLATracker, sla_tracker, SLATarget
from .degradation import DegradationController, degradation_controller, DegradationLevel
from .service_isolation import ServiceIsolation, service_isolation
from .load_protector import LoadProtector, load_protector
from .db_reliability import DBReliability, db_reliability
from .idempotency import IdempotencyGuard, idempotency_guard
from .auto_recovery import AutoRecovery, auto_recovery
from .reliability_testing import ReliabilityTester, reliability_tester
