"""
Circuit Breaker — Failure Isolation Design (Section 14)
═══════════════════════════════════════════════════════
AI services WILL fail. Design for failure.

Isolation Strategy:
  If Gemini fails:
    ✅ feedback saved
    ✅ retry scheduled
    ✅ user unaffected

Use:
  - retry queues
  - fallback pipelines
  - timeout policies

This module implements:
  - Circuit breaker pattern (closed → open → half-open)
  - Per-service isolation (Gemini, AssemblyAI, DB, etc.)
  - Configurable failure thresholds and recovery timeouts
  - Fallback function support
  - Half-open probe with gradual recovery
  - Metrics and observability per circuit
  - Decorator for easy integration
"""

import time
import threading
import asyncio
import traceback
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Awaitable
from datetime import datetime


# ═══════════════════════════════════════════════════
# CIRCUIT STATES
# ═══════════════════════════════════════════════════
class CircuitState(Enum):
    CLOSED = "closed"           # Normal operation — requests flow through
    OPEN = "open"               # Failures exceeded threshold — requests blocked
    HALF_OPEN = "half_open"     # Testing recovery — limited requests allowed


# ═══════════════════════════════════════════════════
# CIRCUIT BREAKER CONFIGURATION
# ═══════════════════════════════════════════════════
@dataclass
class CircuitConfig:
    """Configuration for a single circuit breaker."""
    failure_threshold: int = 5           # Failures to trip circuit
    success_threshold: int = 3           # Successes in half-open to close
    timeout_seconds: float = 60.0        # Time in OPEN before trying half-open
    half_open_max_calls: int = 3         # Max concurrent calls in half-open
    call_timeout_seconds: float = 30.0   # Individual call timeout
    exclude_exceptions: tuple = ()       # Exceptions that don't count as failures
    on_open: Optional[Callable] = None   # Callback when circuit opens
    on_close: Optional[Callable] = None  # Callback when circuit closes
    on_half_open: Optional[Callable] = None


# ═══════════════════════════════════════════════════
# CIRCUIT BREAKER
# ═══════════════════════════════════════════════════
class CircuitBreaker:
    """
    Circuit breaker for a single service/endpoint.

    State machine:
      CLOSED  → (failures >= threshold) → OPEN
      OPEN    → (timeout elapsed)       → HALF_OPEN
      HALF_OPEN → (successes >= threshold) → CLOSED
      HALF_OPEN → (any failure)            → OPEN

    If circuit is OPEN, calls are rejected immediately (fail-fast)
    with optional fallback execution.
    """

    def __init__(self, name: str, config: Optional[CircuitConfig] = None):
        self.name = name
        self.config = config or CircuitConfig()
        self._state = CircuitState.CLOSED
        self._lock = threading.Lock()

        # Counters
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change: float = time.time()

        # Metrics
        self._total_calls = 0
        self._total_successes = 0
        self._total_failures = 0
        self._total_rejected = 0
        self._total_fallbacks = 0
        self._total_timeouts = 0
        self._state_history: List[dict] = []

    @property
    def state(self) -> CircuitState:
        """Get current state, checking for timeout-based transitions."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._last_failure_time and (time.time() - self._last_failure_time) >= self.config.timeout_seconds:
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    @property
    def is_available(self) -> bool:
        """Check if the circuit allows requests."""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            with self._lock:
                return self._half_open_calls < self.config.half_open_max_calls
        return False

    # ─── Call Execution ───
    async def call(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs,
    ) -> Any:
        """
        Execute a function through the circuit breaker.

        If OPEN: immediately returns fallback or raises CircuitOpenError
        If CLOSED/HALF_OPEN: executes function with timeout
        """
        self._total_calls += 1

        # Check state
        if not self.is_available:
            self._total_rejected += 1
            if fallback:
                self._total_fallbacks += 1
                return await self._execute_fallback(fallback, *args, **kwargs)
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN — service unavailable")

        # Track half-open calls
        if self._state == CircuitState.HALF_OPEN:
            with self._lock:
                self._half_open_calls += 1

        # Execute with timeout
        try:
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.call_timeout_seconds
                )
            else:
                result = func(*args, **kwargs)

            self._on_success()
            return result

        except asyncio.TimeoutError:
            self._total_timeouts += 1
            self._on_failure()
            if fallback:
                self._total_fallbacks += 1
                return await self._execute_fallback(fallback, *args, **kwargs)
            raise

        except Exception as e:
            # Check if exception is excluded
            if isinstance(e, self.config.exclude_exceptions):
                self._on_success()
                raise

            self._on_failure()
            if fallback:
                self._total_fallbacks += 1
                return await self._execute_fallback(fallback, *args, **kwargs)
            raise

    def call_sync(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs,
    ) -> Any:
        """Synchronous version of call() for non-async contexts."""
        self._total_calls += 1

        if not self.is_available:
            self._total_rejected += 1
            if fallback:
                self._total_fallbacks += 1
                return fallback(*args, **kwargs)
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN — service unavailable")

        if self._state == CircuitState.HALF_OPEN:
            with self._lock:
                self._half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            if isinstance(e, self.config.exclude_exceptions):
                self._on_success()
                raise
            self._on_failure()
            if fallback:
                self._total_fallbacks += 1
                return fallback(*args, **kwargs)
            raise

    # ─── State Transitions ───
    def _on_success(self):
        """Record a successful call."""
        self._total_successes += 1
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    def _on_failure(self):
        """Record a failed call."""
        self._total_failures += 1
        with self._lock:
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open → back to open
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state and trigger callbacks."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()

        # Reset counters on transition
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.OPEN:
            self._success_count = 0
            self._half_open_calls = 0

        # Record history
        self._state_history.append({
            "from": old_state.value,
            "to": new_state.value,
            "at": datetime.now().isoformat(),
        })
        # Keep last 50 transitions
        if len(self._state_history) > 50:
            self._state_history = self._state_history[-50:]

        # Callbacks
        if new_state == CircuitState.OPEN and self.config.on_open:
            try:
                self.config.on_open(self.name)
            except Exception:
                pass
        elif new_state == CircuitState.CLOSED and self.config.on_close:
            try:
                self.config.on_close(self.name)
            except Exception:
                pass
        elif new_state == CircuitState.HALF_OPEN and self.config.on_half_open:
            try:
                self.config.on_half_open(self.name)
            except Exception:
                pass

    async def _execute_fallback(self, fallback: Callable, *args, **kwargs) -> Any:
        """Execute the fallback function (async-safe)."""
        if asyncio.iscoroutinefunction(fallback):
            return await fallback(*args, **kwargs)
        return fallback(*args, **kwargs)

    # ─── Manual Controls ───
    def force_open(self):
        """Manually trip the circuit breaker."""
        with self._lock:
            self._transition_to(CircuitState.OPEN)
            self._last_failure_time = time.time()

    def force_close(self):
        """Manually close (reset) the circuit breaker."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)

    def reset(self):
        """Full reset — clear all counters and history."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
            self._last_state_change = time.time()
            self._state_history.clear()

    # ─── Stats ───
    def stats(self) -> dict:
        total = self._total_successes + self._total_failures
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "time_in_state_seconds": round(time.time() - self._last_state_change, 1),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout_seconds": self.config.timeout_seconds,
                "call_timeout_seconds": self.config.call_timeout_seconds,
            },
            "metrics": {
                "total_calls": self._total_calls,
                "total_successes": self._total_successes,
                "total_failures": self._total_failures,
                "total_rejected": self._total_rejected,
                "total_fallbacks": self._total_fallbacks,
                "total_timeouts": self._total_timeouts,
                "success_rate": round(self._total_successes / max(total, 1) * 100, 1),
            },
            "recent_transitions": self._state_history[-10:],
        }


# ═══════════════════════════════════════════════════
# CIRCUIT OPEN ERROR
# ═══════════════════════════════════════════════════
class CircuitOpenError(Exception):
    """Raised when a call is made to an open circuit."""
    pass


# ═══════════════════════════════════════════════════
# CIRCUIT BREAKER REGISTRY
# ═══════════════════════════════════════════════════
class CircuitBreakerRegistry:
    """
    Central registry for all circuit breakers.

    Provides a single access point for:
      - Creating/getting circuit breakers by name
      - Aggregate health status of all external services
      - Bulk operations (reset all, stats)
    """

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_or_create(self, name: str, config: Optional[CircuitConfig] = None) -> CircuitBreaker:
        """Get existing or create new circuit breaker."""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self._breakers.get(name)

    def all_healthy(self) -> bool:
        """Check if all circuits are in CLOSED state."""
        return all(cb.state == CircuitState.CLOSED for cb in self._breakers.values())

    def unhealthy_circuits(self) -> List[str]:
        """Get names of all circuits not in CLOSED state."""
        return [name for name, cb in self._breakers.items() if cb.state != CircuitState.CLOSED]

    def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self._breakers.values():
            cb.reset()

    def stats(self) -> dict:
        """Aggregate stats for all circuit breakers."""
        return {
            "total_circuits": len(self._breakers),
            "healthy": sum(1 for cb in self._breakers.values() if cb.state == CircuitState.CLOSED),
            "open": sum(1 for cb in self._breakers.values() if cb.state == CircuitState.OPEN),
            "half_open": sum(1 for cb in self._breakers.values() if cb.state == CircuitState.HALF_OPEN),
            "all_healthy": self.all_healthy(),
            "unhealthy": self.unhealthy_circuits(),
            "circuits": {name: cb.stats() for name, cb in self._breakers.items()},
        }


# ═══════════════════════════════════════════════════
# GLOBAL CIRCUIT BREAKER REGISTRY + PRE-CONFIGURED CIRCUITS
# ═══════════════════════════════════════════════════
circuit_registry = CircuitBreakerRegistry()

# Pre-configure circuits for known external services
gemini_circuit = circuit_registry.get_or_create("gemini_api", CircuitConfig(
    failure_threshold=5,
    success_threshold=3,
    timeout_seconds=60.0,
    call_timeout_seconds=45.0,    # Gemini can be slow
))

assemblyai_circuit = circuit_registry.get_or_create("assemblyai_api", CircuitConfig(
    failure_threshold=3,
    success_threshold=2,
    timeout_seconds=120.0,        # AssemblyAI transcription is slow
    call_timeout_seconds=300.0,   # Long transcriptions
))

database_circuit = circuit_registry.get_or_create("database", CircuitConfig(
    failure_threshold=3,
    success_threshold=2,
    timeout_seconds=30.0,
    call_timeout_seconds=10.0,    # DB should be fast
))
