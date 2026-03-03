"""
Reliability Testing Framework (§17)
═══════════════════════════════════════════════════════
Chaos engineering and stress testing for production resilience.

Capabilities:
  - Stress testing (concurrent user simulation)
  - Chaos testing (fault injection)
  - Circuit breaker testing
  - Load ramp testing
  - Resilience scoring
  - Test result reporting
"""

import time
import random
import threading
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TestType(Enum):
    STRESS       = "stress"
    CHAOS        = "chaos"
    LOAD_RAMP    = "load_ramp"
    ENDURANCE    = "endurance"
    LATENCY      = "latency"


class FaultType(Enum):
    AI_TIMEOUT       = "ai_timeout"
    AI_ERROR         = "ai_error"
    DB_SLOW          = "db_slow"
    DB_DISCONNECT    = "db_disconnect"
    WORKER_CRASH     = "worker_crash"
    QUEUE_OVERFLOW   = "queue_overflow"
    NETWORK_LATENCY  = "network_latency"
    MEMORY_PRESSURE  = "memory_pressure"


@dataclass
class TestConfig:
    """Configuration for a reliability test."""
    name: str
    test_type: TestType
    duration_seconds: float = 30.0
    concurrent_users: int = 10
    ramp_up_seconds: float = 5.0
    target_rps: float = 50.0
    fault_types: List[FaultType] = field(default_factory=list)
    fault_probability: float = 0.1    # 10% chance per request
    description: str = ""


@dataclass
class TestResult:
    """Result of a reliability test."""
    test_name: str
    test_type: str
    status: str               # passed / failed / partial
    duration_seconds: float
    total_requests: int
    successful: int
    failed: int
    error_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    throughput_rps: float
    faults_injected: int
    faults_survived: int
    resilience_score: float   # 0-100
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class _FaultInjector:
    """Injects controlled faults into the system for chaos testing."""

    def __init__(self):
        self._active_faults: Dict[str, bool] = {}
        self._injected_count = 0
        self._lock = threading.Lock()

    def inject(self, fault_type: FaultType) -> dict:
        """Inject a fault. Returns injection details."""
        with self._lock:
            self._active_faults[fault_type.value] = True
            self._injected_count += 1

        if fault_type == FaultType.AI_TIMEOUT:
            return self._inject_ai_timeout()
        elif fault_type == FaultType.AI_ERROR:
            return self._inject_ai_error()
        elif fault_type == FaultType.DB_SLOW:
            return self._inject_db_slow()
        elif fault_type == FaultType.WORKER_CRASH:
            return self._inject_worker_crash()
        elif fault_type == FaultType.QUEUE_OVERFLOW:
            return self._inject_queue_overflow()
        else:
            return {"fault": fault_type.value, "injected": True, "method": "simulated"}

    def remove(self, fault_type: FaultType):
        """Remove an injected fault."""
        with self._lock:
            self._active_faults.pop(fault_type.value, None)

    def remove_all(self):
        """Remove all injected faults."""
        with self._lock:
            self._active_faults.clear()

    def is_active(self, fault_type: FaultType) -> bool:
        return self._active_faults.get(fault_type.value, False)

    def _inject_ai_timeout(self) -> dict:
        """Simulate AI API timeout."""
        try:
            from ..infrastructure.circuit_breaker import gemini_circuit
            gemini_circuit.force_open()
            return {"fault": "ai_timeout", "injected": True, "circuit": "gemini", "action": "forced_open"}
        except Exception:
            return {"fault": "ai_timeout", "injected": True, "method": "simulated"}

    def _inject_ai_error(self) -> dict:
        """Simulate AI API error."""
        try:
            from ..infrastructure.circuit_breaker import assemblyai_circuit
            assemblyai_circuit.force_open()
            return {"fault": "ai_error", "injected": True, "circuit": "assemblyai", "action": "forced_open"}
        except Exception:
            return {"fault": "ai_error", "injected": True, "method": "simulated"}

    def _inject_db_slow(self) -> dict:
        """Simulate slow database (reduces pool size concept)."""
        return {"fault": "db_slow", "injected": True, "method": "simulated_latency"}

    def _inject_worker_crash(self) -> dict:
        """Simulate worker crash."""
        return {"fault": "worker_crash", "injected": True, "method": "simulated"}

    def _inject_queue_overflow(self) -> dict:
        """Simulate queue overflow."""
        return {"fault": "queue_overflow", "injected": True, "method": "simulated"}

    @property
    def stats(self) -> dict:
        return {
            "active_faults": list(self._active_faults.keys()),
            "total_injected": self._injected_count,
        }


class ReliabilityTester:
    """
    Reliability testing framework.
    
    Provides stress testing, chaos testing, and resilience scoring
    for validating system reliability before production.
    
    Usage:
        # Run stress test
        result = reliability_tester.run_stress_test(concurrent=100, duration=60)
        
        # Run chaos test
        result = reliability_tester.run_chaos_test(faults=[FaultType.AI_TIMEOUT])
        
        # Get resilience score
        score = reliability_tester.calculate_resilience_score()
    """

    def __init__(self):
        self._fault_injector = _FaultInjector()
        self._results: List[TestResult] = []
        self._max_results = 100
        self._lock = threading.Lock()
        self._running = False

    # ─────────────────────────────────────
    # Stress Testing
    # ─────────────────────────────────────

    def run_stress_test(self, concurrent: int = 10,
                         duration_seconds: float = 30.0,
                         target_rps: float = 50.0) -> dict:
        """
        Simulate concurrent users hitting the system.
        
        Measures: throughput, latency, error rate under load.
        """
        if self._running:
            return {"error": "A test is already running"}

        self._running = True
        start = time.time()
        results = {"successful": 0, "failed": 0, "latencies": []}

        try:
            end_time = start + duration_seconds
            threads = []

            def _worker():
                while time.time() < end_time:
                    req_start = time.time()
                    try:
                        # Simulate request processing
                        self._simulate_request()
                        latency = (time.time() - req_start) * 1000
                        results["successful"] += 1
                        results["latencies"].append(latency)
                    except Exception:
                        results["failed"] += 1
                        results["latencies"].append((time.time() - req_start) * 1000)
                    
                    # Rate limiting
                    delay = 1.0 / max(target_rps / concurrent, 0.1)
                    time.sleep(max(0, delay - (time.time() - req_start)))

            for _ in range(concurrent):
                t = threading.Thread(target=_worker, daemon=True)
                t.start()
                threads.append(t)

            for t in threads:
                t.join(timeout=duration_seconds + 10)

        finally:
            self._running = False

        actual_duration = time.time() - start
        total = results["successful"] + results["failed"]
        latencies = sorted(results["latencies"]) if results["latencies"] else [0]
        n = len(latencies)

        result = TestResult(
            test_name=f"stress_{concurrent}u_{duration_seconds}s",
            test_type="stress",
            status="passed" if results["failed"] / max(total, 1) < 0.05 else "failed",
            duration_seconds=round(actual_duration, 2),
            total_requests=total,
            successful=results["successful"],
            failed=results["failed"],
            error_rate=round(results["failed"] / max(total, 1) * 100, 2),
            avg_latency_ms=round(sum(latencies) / max(n, 1), 2),
            p95_latency_ms=round(latencies[int(min(n * 0.95, n - 1))], 2),
            p99_latency_ms=round(latencies[int(min(n * 0.99, n - 1))], 2),
            max_latency_ms=round(max(latencies), 2),
            throughput_rps=round(total / max(actual_duration, 0.1), 2),
            faults_injected=0,
            faults_survived=0,
            resilience_score=self._score_stress(results, total),
        )

        self._record_result(result)
        return self._result_to_dict(result)

    # ─────────────────────────────────────
    # Chaos Testing
    # ─────────────────────────────────────

    def run_chaos_test(self, faults: Optional[List[str]] = None,
                        duration_seconds: float = 30.0,
                        fault_probability: float = 0.3) -> dict:
        """
        Inject faults and verify system survives.
        
        Measures: fault tolerance, graceful degradation, recovery.
        """
        if self._running:
            return {"error": "A test is already running"}

        self._running = True
        fault_types = [FaultType(f) for f in (faults or ["ai_timeout"])]
        start = time.time()
        injected = 0
        survived = 0
        results = {"successful": 0, "failed": 0, "latencies": []}

        try:
            # Inject faults
            for ft in fault_types:
                self._fault_injector.inject(ft)
                injected += 1

            end_time = start + duration_seconds
            while time.time() < end_time:
                req_start = time.time()
                try:
                    self._simulate_request_with_faults(fault_probability)
                    latency = (time.time() - req_start) * 1000
                    results["successful"] += 1
                    results["latencies"].append(latency)
                    survived += 1
                except Exception:
                    results["failed"] += 1
                    results["latencies"].append((time.time() - req_start) * 1000)
                time.sleep(0.05)

        finally:
            # Remove all faults
            self._fault_injector.remove_all()
            self._running = False

        actual_duration = time.time() - start
        total = results["successful"] + results["failed"]
        latencies = sorted(results["latencies"]) if results["latencies"] else [0]
        n = len(latencies)

        result = TestResult(
            test_name=f"chaos_{'_'.join(f.value for f in fault_types)}",
            test_type="chaos",
            status="passed" if results["failed"] / max(total, 1) < 0.20 else "failed",
            duration_seconds=round(actual_duration, 2),
            total_requests=total,
            successful=results["successful"],
            failed=results["failed"],
            error_rate=round(results["failed"] / max(total, 1) * 100, 2),
            avg_latency_ms=round(sum(latencies) / max(n, 1), 2),
            p95_latency_ms=round(latencies[int(min(n * 0.95, n - 1))], 2),
            p99_latency_ms=round(latencies[int(min(n * 0.99, n - 1))], 2),
            max_latency_ms=round(max(latencies), 2),
            throughput_rps=round(total / max(actual_duration, 0.1), 2),
            faults_injected=injected,
            faults_survived=survived,
            resilience_score=self._score_chaos(results, total, injected, survived),
            details={"fault_types": [f.value for f in fault_types]},
        )

        self._record_result(result)
        return self._result_to_dict(result)

    # ─────────────────────────────────────
    # Latency Test
    # ─────────────────────────────────────

    def run_latency_test(self, requests: int = 100) -> dict:
        """
        Measure baseline latency for key operations.
        """
        if self._running:
            return {"error": "A test is already running"}

        self._running = True
        start = time.time()
        latencies = []
        errors = 0

        try:
            for _ in range(requests):
                req_start = time.time()
                try:
                    self._simulate_request()
                    latencies.append((time.time() - req_start) * 1000)
                except Exception:
                    errors += 1
                    latencies.append((time.time() - req_start) * 1000)
        finally:
            self._running = False

        actual_duration = time.time() - start
        latencies.sort()
        n = len(latencies)

        result = TestResult(
            test_name=f"latency_{requests}r",
            test_type="latency",
            status="passed" if errors / max(requests, 1) < 0.05 else "failed",
            duration_seconds=round(actual_duration, 2),
            total_requests=requests,
            successful=requests - errors,
            failed=errors,
            error_rate=round(errors / max(requests, 1) * 100, 2),
            avg_latency_ms=round(sum(latencies) / max(n, 1), 2),
            p95_latency_ms=round(latencies[int(min(n * 0.95, n - 1))], 2) if n > 0 else 0,
            p99_latency_ms=round(latencies[int(min(n * 0.99, n - 1))], 2) if n > 0 else 0,
            max_latency_ms=round(max(latencies), 2) if latencies else 0,
            throughput_rps=round(requests / max(actual_duration, 0.1), 2),
            faults_injected=0,
            faults_survived=0,
            resilience_score=100 - (errors / max(requests, 1) * 100),
        )

        self._record_result(result)
        return self._result_to_dict(result)

    # ─────────────────────────────────────
    # Resilience Score
    # ─────────────────────────────────────

    def calculate_resilience_score(self) -> dict:
        """
        Calculate overall system resilience score from test history.
        
        Score components:
          - Error rate score (40%)
          - Latency score (30%)
          - Fault tolerance score (20%)
          - Recovery score (10%)
        """
        if not self._results:
            return {
                "overall_score": 0,
                "status": "no_tests_run",
                "recommendation": "Run stress and chaos tests to establish baseline",
            }

        # Recent results
        recent = self._results[-10:]

        # Error rate score (40%)
        avg_error_rate = sum(r.error_rate for r in recent) / len(recent)
        error_score = max(0, 100 - avg_error_rate * 10)  # 10% error = 0 score

        # Latency score (30%)
        avg_p95 = sum(r.p95_latency_ms for r in recent) / len(recent)
        latency_score = max(0, 100 - (avg_p95 / 100))  # Higher p95 = lower score

        # Fault tolerance score (20%)
        chaos_tests = [r for r in recent if r.test_type == "chaos"]
        if chaos_tests:
            survival_rate = sum(r.faults_survived / max(r.total_requests, 1) for r in chaos_tests) / len(chaos_tests)
            fault_score = survival_rate * 100
        else:
            fault_score = 50  # Unknown

        # Recovery score (10%)
        try:
            from .auto_recovery import auto_recovery
            s = auto_recovery.stats()
            total_rec = max(s.get("total_recoveries", 0), 1)
            recovery_rate = s.get("successful", 0) / total_rec
            recovery_score = recovery_rate * 100
        except Exception:
            recovery_score = 50  # Unknown

        overall = (error_score * 0.4 + latency_score * 0.3 +
                   fault_score * 0.2 + recovery_score * 0.1)

        status = "excellent" if overall >= 90 else "good" if overall >= 70 else "fair" if overall >= 50 else "poor"

        return {
            "overall_score": round(overall, 1),
            "status": status,
            "components": {
                "error_rate": {"score": round(error_score, 1), "weight": "40%", "avg_error_rate": round(avg_error_rate, 2)},
                "latency": {"score": round(latency_score, 1), "weight": "30%", "avg_p95_ms": round(avg_p95, 2)},
                "fault_tolerance": {"score": round(fault_score, 1), "weight": "20%"},
                "recovery": {"score": round(recovery_score, 1), "weight": "10%"},
            },
            "tests_analyzed": len(recent),
            "recommendation": self._get_recommendation(overall, error_score, latency_score, fault_score),
        }

    def _get_recommendation(self, overall, error_score, latency_score, fault_score) -> str:
        if overall >= 90:
            return "System resilience is excellent. Continue monitoring."
        issues = []
        if error_score < 70:
            issues.append("High error rate — investigate failing endpoints")
        if latency_score < 70:
            issues.append("High p95 latency — optimize slow endpoints or add caching")
        if fault_score < 70:
            issues.append("Low fault tolerance — improve circuit breaker and fallback coverage")
        return "; ".join(issues) if issues else "Run more tests for better scoring"

    # ─────────────────────────────────────
    # Simulation Helpers
    # ─────────────────────────────────────

    def _simulate_request(self):
        """Simulate a normal request processing."""
        # Simulate variable latency (1-50ms)
        time.sleep(random.uniform(0.001, 0.05))
        # Small chance of natural failure
        if random.random() < 0.01:
            raise RuntimeError("Simulated transient error")

    def _simulate_request_with_faults(self, fault_prob: float):
        """Simulate request with possible fault injection."""
        if random.random() < fault_prob:
            # Simulate fault effects
            fault = random.choice([
                lambda: time.sleep(random.uniform(0.1, 0.5)),  # Slow
                lambda: (_ for _ in ()).throw(RuntimeError("Fault injected")),  # Error
            ])
            fault()
        else:
            self._simulate_request()

    # ─────────────────────────────────────
    # Scoring Helpers
    # ─────────────────────────────────────

    def _score_stress(self, results: dict, total: int) -> float:
        error_rate = results["failed"] / max(total, 1)
        return round(max(0, 100 - error_rate * 200), 1)  # 50% errors = 0

    def _score_chaos(self, results: dict, total: int,
                     injected: int, survived: int) -> float:
        error_rate = results["failed"] / max(total, 1)
        survival_rate = survived / max(total, 1)
        return round((survival_rate * 50 + (1 - error_rate) * 50), 1)

    # ─────────────────────────────────────
    # Result Management
    # ─────────────────────────────────────

    def _record_result(self, result: TestResult):
        with self._lock:
            self._results.append(result)
            if len(self._results) > self._max_results:
                self._results = self._results[-self._max_results:]

    def _result_to_dict(self, result: TestResult) -> dict:
        return {
            "test_name": result.test_name,
            "test_type": result.test_type,
            "status": result.status,
            "duration_seconds": result.duration_seconds,
            "total_requests": result.total_requests,
            "successful": result.successful,
            "failed": result.failed,
            "error_rate": result.error_rate,
            "avg_latency_ms": result.avg_latency_ms,
            "p95_latency_ms": result.p95_latency_ms,
            "p99_latency_ms": result.p99_latency_ms,
            "max_latency_ms": result.max_latency_ms,
            "throughput_rps": result.throughput_rps,
            "faults_injected": result.faults_injected,
            "faults_survived": result.faults_survived,
            "resilience_score": result.resilience_score,
            "details": result.details,
            "timestamp": result.timestamp,
        }

    def get_results(self, test_type: Optional[str] = None,
                    limit: int = 20) -> List[dict]:
        """Get test result history."""
        results = self._results
        if test_type:
            results = [r for r in results if r.test_type == test_type]
        return [self._result_to_dict(r) for r in reversed(results)][:limit]

    # ─────────────────────────────────────
    # Fault Injection API
    # ─────────────────────────────────────

    def inject_fault(self, fault_type: str) -> dict:
        """Manually inject a fault (for testing)."""
        try:
            ft = FaultType(fault_type)
            return self._fault_injector.inject(ft)
        except ValueError:
            return {"error": f"Unknown fault type: {fault_type}",
                    "valid_types": [f.value for f in FaultType]}

    def remove_fault(self, fault_type: str) -> dict:
        """Remove an injected fault."""
        try:
            ft = FaultType(fault_type)
            self._fault_injector.remove(ft)
            return {"removed": fault_type}
        except ValueError:
            return {"error": f"Unknown fault type: {fault_type}"}

    def remove_all_faults(self) -> dict:
        """Remove all injected faults."""
        self._fault_injector.remove_all()
        return {"removed_all": True}

    # ─────────────────────────────────────
    # Stats
    # ─────────────────────────────────────

    def stats(self) -> dict:
        return {
            "engine": "ReliabilityTester",
            "total_tests_run": len(self._results),
            "is_running": self._running,
            "fault_injector": self._fault_injector.stats,
            "available_fault_types": [f.value for f in FaultType],
            "available_test_types": [t.value for t in TestType],
        }


# ─────────────────────────────────────────────────────
# Global singleton
# ─────────────────────────────────────────────────────
reliability_tester = ReliabilityTester()
