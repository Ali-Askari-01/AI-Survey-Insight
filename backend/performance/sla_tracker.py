"""
SLA Tracker (§5, §16)
═══════════════════════════════════════════════════════
Defines and enforces Service Level Agreements across all features.

Capabilities:
  - SLA target definitions per feature/endpoint
  - Real-time percentile tracking (p50/p95/p99)
  - SLA violation detection and alerting
  - SLA compliance reports
  - Historical SLA trend analysis
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict
import statistics


# ─────────────────────────────────────────────────────
# SLA Target Definitions
# ─────────────────────────────────────────────────────

@dataclass
class SLATarget:
    """
    SLA target for a feature or endpoint.
    
    All latency values in milliseconds.
    """
    name: str
    description: str
    p50_target_ms: float       # Median target
    p95_target_ms: float       # 95th percentile target
    p99_target_ms: float       # 99th percentile target
    max_error_rate: float      # Max allowed error rate (0.01 = 1%)
    availability_target: float = 0.995   # 99.5% availability
    measurement_window_s: float = 300    # 5-minute window default


@dataclass
class SLAObservation:
    """Single observation for SLA measurement."""
    sla_name: str
    latency_ms: float
    success: bool
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SLAViolation:
    """Recorded SLA breach."""
    sla_name: str
    metric: str            # e.g., "p95", "error_rate", "availability"
    target: float
    actual: float
    timestamp: float
    window_s: float
    details: str = ""


class SLATracker:
    """
    Tracks SLA compliance across the platform.
    
    Usage:
        sla_tracker.observe("survey_submission", latency_ms=150, success=True)
        report = sla_tracker.compliance_report()
    """

    # Pre-defined SLA targets matching §16 spec
    DEFAULT_TARGETS: Dict[str, SLATarget] = {
        "survey_submission": SLATarget(
            name="survey_submission",
            description="Survey response submission",
            p50_target_ms=100, p95_target_ms=200, p99_target_ms=300,
            max_error_rate=0.005,  # 0.5%
        ),
        "chat_response": SLATarget(
            name="chat_response",
            description="Chat/interview AI response",
            p50_target_ms=1000, p95_target_ms=1800, p99_target_ms=2000,
            max_error_rate=0.01,  # 1%
        ),
        "insight_generation": SLATarget(
            name="insight_generation",
            description="AI insight generation pipeline",
            p50_target_ms=15000, p95_target_ms=45000, p99_target_ms=60000,
            max_error_rate=0.02,  # 2%
        ),
        "dashboard_load": SLATarget(
            name="dashboard_load",
            description="Dashboard page load",
            p50_target_ms=400, p95_target_ms=800, p99_target_ms=1000,
            max_error_rate=0.005,
        ),
        "report_generation": SLATarget(
            name="report_generation",
            description="Report PDF/export generation",
            p50_target_ms=3000, p95_target_ms=8000, p99_target_ms=12000,
            max_error_rate=0.02,
        ),
        "voice_transcription": SLATarget(
            name="voice_transcription",
            description="Voice feedback transcription",
            p50_target_ms=5000, p95_target_ms=12000, p99_target_ms=18000,
            max_error_rate=0.03,
        ),
        "health_check": SLATarget(
            name="health_check",
            description="System health check",
            p50_target_ms=50, p95_target_ms=200, p99_target_ms=500,
            max_error_rate=0.001,
        ),
        "data_pipeline": SLATarget(
            name="data_pipeline",
            description="5-layer data pipeline per response",
            p50_target_ms=2000, p95_target_ms=8000, p99_target_ms=15000,
            max_error_rate=0.01,
        ),
    }

    def __init__(self, max_observations: int = 10000):
        self._targets: Dict[str, SLATarget] = dict(self.DEFAULT_TARGETS)
        self._observations: Dict[str, List[SLAObservation]] = defaultdict(list)
        self._violations: List[SLAViolation] = []
        self._max_obs = max_observations
        self._lock = threading.Lock()
        self._alert_callbacks: List[Callable] = []
        self._total_observations = 0
        self._total_violations = 0

    # ─────────────────────────────────────
    # Configuration
    # ─────────────────────────────────────

    def define_sla(self, target: SLATarget):
        """Register or update an SLA target."""
        self._targets[target.name] = target

    def register_alert(self, callback: Callable[[SLAViolation], None]):
        """Register an alert handler for SLA violations."""
        self._alert_callbacks.append(callback)

    # ─────────────────────────────────────
    # Observation
    # ─────────────────────────────────────

    def observe(self, sla_name: str, latency_ms: float, success: bool = True,
                metadata: Optional[Dict] = None):
        """Record an SLA observation and check for violations."""
        obs = SLAObservation(
            sla_name=sla_name, latency_ms=latency_ms,
            success=success, timestamp=time.time(),
            metadata=metadata or {},
        )
        with self._lock:
            self._total_observations += 1
            bucket = self._observations[sla_name]
            bucket.append(obs)
            # Trim oldest observations
            if len(bucket) > self._max_obs:
                self._observations[sla_name] = bucket[-self._max_obs:]

        # Check SLA inline (fast)
        if sla_name in self._targets:
            self._check_instant_violation(sla_name, obs)

    def _check_instant_violation(self, sla_name: str, obs: SLAObservation):
        """Quick check: if single request exceeds p99, flag immediately."""
        target = self._targets[sla_name]
        if obs.latency_ms > target.p99_target_ms and obs.success:
            violation = SLAViolation(
                sla_name=sla_name, metric="p99_instant",
                target=target.p99_target_ms, actual=obs.latency_ms,
                timestamp=obs.timestamp, window_s=0,
                details=f"Single request {obs.latency_ms:.0f}ms > p99 target {target.p99_target_ms:.0f}ms",
            )
            self._record_violation(violation)

    def _record_violation(self, violation: SLAViolation):
        with self._lock:
            self._violations.append(violation)
            self._total_violations += 1
            if len(self._violations) > 5000:
                self._violations = self._violations[-5000:]
        # Fire alerts
        for cb in self._alert_callbacks:
            try:
                cb(violation)
            except Exception:
                pass

    # ─────────────────────────────────────
    # Compliance Check
    # ─────────────────────────────────────

    def check_compliance(self, sla_name: str,
                          window_s: Optional[float] = None) -> dict:
        """
        Check SLA compliance for a named target.
        
        Returns compliance status with actual vs target metrics.
        """
        if sla_name not in self._targets:
            return {"error": f"No SLA target defined for '{sla_name}'"}

        target = self._targets[sla_name]
        window = window_s or target.measurement_window_s
        cutoff = time.time() - window

        with self._lock:
            recent = [
                o for o in self._observations.get(sla_name, [])
                if o.timestamp >= cutoff
            ]

        if not recent:
            return {
                "sla_name": sla_name,
                "status": "no_data",
                "observation_count": 0,
                "window_seconds": window,
            }

        latencies = [o.latency_ms for o in recent if o.success]
        total = len(recent)
        errors = sum(1 for o in recent if not o.success)
        error_rate = errors / max(total, 1)
        availability = 1.0 - error_rate

        latencies.sort()
        n = len(latencies)

        # Compute percentiles
        p50 = latencies[int(n * 0.50)] if n > 0 else 0
        p95 = latencies[int(min(n * 0.95, n - 1))] if n > 0 else 0
        p99 = latencies[int(min(n * 0.99, n - 1))] if n > 0 else 0

        # Check each metric
        violations = []
        if n > 0 and p50 > target.p50_target_ms:
            violations.append({"metric": "p50", "target": target.p50_target_ms, "actual": round(p50, 2)})
        if n > 0 and p95 > target.p95_target_ms:
            violations.append({"metric": "p95", "target": target.p95_target_ms, "actual": round(p95, 2)})
        if n > 0 and p99 > target.p99_target_ms:
            violations.append({"metric": "p99", "target": target.p99_target_ms, "actual": round(p99, 2)})
        if error_rate > target.max_error_rate:
            violations.append({"metric": "error_rate", "target": target.max_error_rate, "actual": round(error_rate, 4)})
        if availability < target.availability_target:
            violations.append({"metric": "availability", "target": target.availability_target, "actual": round(availability, 4)})

        compliant = len(violations) == 0
        status = "compliant" if compliant else "violated"

        return {
            "sla_name": sla_name,
            "description": target.description,
            "status": status,
            "compliant": compliant,
            "window_seconds": window,
            "observation_count": total,
            "error_count": errors,
            "metrics": {
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
                "p99_ms": round(p99, 2),
                "mean_ms": round(statistics.mean(latencies), 2) if latencies else 0,
                "error_rate": round(error_rate, 4),
                "availability": round(availability, 4),
            },
            "targets": {
                "p50_ms": target.p50_target_ms,
                "p95_ms": target.p95_target_ms,
                "p99_ms": target.p99_target_ms,
                "max_error_rate": target.max_error_rate,
                "availability": target.availability_target,
            },
            "violations": violations,
        }

    def compliance_report(self, window_s: float = 300) -> dict:
        """Generate full SLA compliance report across all tracked targets."""
        report = {}
        overall_compliant = True

        for name in self._targets:
            result = self.check_compliance(name, window_s)
            report[name] = result
            if result.get("status") == "violated":
                overall_compliant = False

        return {
            "overall_status": "compliant" if overall_compliant else "violation_detected",
            "window_seconds": window_s,
            "sla_count": len(self._targets),
            "checked_at": time.time(),
            "slas": report,
        }

    # ─────────────────────────────────────
    # Violation History
    # ─────────────────────────────────────

    def get_violations(self, sla_name: Optional[str] = None,
                       limit: int = 50, since: Optional[float] = None) -> List[dict]:
        """Get recent SLA violations."""
        cutoff = since or 0
        with self._lock:
            results = [
                {
                    "sla_name": v.sla_name,
                    "metric": v.metric,
                    "target": v.target,
                    "actual": round(v.actual, 2),
                    "timestamp": v.timestamp,
                    "window_s": v.window_s,
                    "details": v.details,
                }
                for v in reversed(self._violations)
                if v.timestamp >= cutoff
                and (sla_name is None or v.sla_name == sla_name)
            ]
        return results[:limit]

    # ─────────────────────────────────────
    # Trend Analysis
    # ─────────────────────────────────────

    def get_sla_trend(self, sla_name: str, buckets: int = 12,
                       window_s: float = 3600) -> dict:
        """Get SLA metric trend over time (bucketed)."""
        if sla_name not in self._targets:
            return {"error": f"Unknown SLA: {sla_name}"}

        now = time.time()
        bucket_size = window_s / buckets
        target = self._targets[sla_name]

        with self._lock:
            obs = self._observations.get(sla_name, [])

        trend = []
        for i in range(buckets):
            bucket_start = now - window_s + (i * bucket_size)
            bucket_end = bucket_start + bucket_size
            bucket_obs = [o for o in obs if bucket_start <= o.timestamp < bucket_end]

            if not bucket_obs:
                trend.append({"bucket": i, "time": bucket_start, "count": 0})
                continue

            latencies = [o.latency_ms for o in bucket_obs if o.success]
            errors = sum(1 for o in bucket_obs if not o.success)
            latencies.sort()
            n = len(latencies)

            trend.append({
                "bucket": i,
                "time": bucket_start,
                "count": len(bucket_obs),
                "errors": errors,
                "p50": round(latencies[int(n * 0.5)], 2) if n > 0 else 0,
                "p95": round(latencies[int(min(n * 0.95, n - 1))], 2) if n > 0 else 0,
                "mean": round(statistics.mean(latencies), 2) if latencies else 0,
            })

        return {
            "sla_name": sla_name,
            "window_seconds": window_s,
            "bucket_count": buckets,
            "bucket_size_seconds": bucket_size,
            "trend": trend,
        }

    # ─────────────────────────────────────
    # Stats
    # ─────────────────────────────────────

    def stats(self) -> dict:
        return {
            "engine": "SLATracker",
            "total_sla_targets": len(self._targets),
            "total_observations": self._total_observations,
            "total_violations": self._total_violations,
            "active_targets": list(self._targets.keys()),
            "alert_handlers": len(self._alert_callbacks),
        }


# ─────────────────────────────────────────────────────
# Global singleton
# ─────────────────────────────────────────────────────
sla_tracker = SLATracker()
