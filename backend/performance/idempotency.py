"""
Idempotency Guard (§12)
═══════════════════════════════════════════════════════
API-level idempotency protection to prevent duplicate submissions.

Every mutating request can carry an Idempotency-Key header (UUID).
If the same key is seen again within the retention window, the
original response is returned instead of re-processing.

Capabilities:
  - UUID-based idempotency keys
  - Configurable retention window
  - Stored response replay
  - Concurrent request deduplication (lock on key)
  - Metrics: duplicate detection rate, cache hit/miss
"""

import time
import hashlib
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
from collections import OrderedDict


@dataclass
class IdempotencyRecord:
    """Stored result for a processed idempotency key."""
    key: str
    response_status: int
    response_body: Any
    created_at: float
    request_hash: str = ""   # Hash of request body for collision detection
    hit_count: int = 0       # How many times this was replayed


class IdempotencyGuard:
    """
    API-level idempotency guard.
    
    Usage in FastAPI middleware or endpoint:
        key = request.headers.get("Idempotency-Key")
        if key:
            cached = idempotency_guard.get(key)
            if cached:
                return JSONResponse(content=cached.response_body, status_code=cached.response_status)
            
            # ... process request ...
            
            idempotency_guard.store(key, status_code=200, body=result, request_hash=hash)
    """

    def __init__(self, max_entries: int = 10000,
                 retention_seconds: float = 86400):  # 24 hours
        self._store: OrderedDict[str, IdempotencyRecord] = OrderedDict()
        self._max_entries = max_entries
        self._retention_seconds = retention_seconds
        self._lock = threading.Lock()
        self._processing: Dict[str, threading.Event] = {}  # Keys currently being processed

        # Metrics
        self._total_checks = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._collisions = 0      # Same key, different request body
        self._concurrent_dedup = 0  # Concurrent duplicate blocked

    # ─────────────────────────────────────
    # Core Operations
    # ─────────────────────────────────────

    def check(self, key: str, request_hash: str = "") -> Tuple[bool, Optional[IdempotencyRecord]]:
        """
        Check if a request with this idempotency key was already processed.
        
        Returns:
            (is_duplicate: bool, record: Optional[IdempotencyRecord])
        """
        self._total_checks += 1

        with self._lock:
            if key in self._store:
                record = self._store[key]
                # Check expiration
                if time.time() - record.created_at > self._retention_seconds:
                    del self._store[key]
                    self._cache_misses += 1
                    return False, None

                # Check for collision (same key, different request)
                if request_hash and record.request_hash and request_hash != record.request_hash:
                    self._collisions += 1
                    # Collision: different request using same key — treat as new
                    return False, None

                record.hit_count += 1
                self._cache_hits += 1
                return True, record

            self._cache_misses += 1
            return False, None

    def store(self, key: str, status_code: int, body: Any,
              request_hash: str = ""):
        """Store the result of a processed request for future replay."""
        record = IdempotencyRecord(
            key=key, response_status=status_code,
            response_body=body, created_at=time.time(),
            request_hash=request_hash,
        )

        with self._lock:
            self._store[key] = record
            # Move to end (LRU)
            self._store.move_to_end(key)

            # Evict oldest if over capacity
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)

            # Release processing lock if held
            if key in self._processing:
                self._processing[key].set()
                del self._processing[key]

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        """Get stored record for a key (convenience wrapper)."""
        is_dup, record = self.check(key)
        return record if is_dup else None

    # ─────────────────────────────────────
    # Concurrent Deduplication
    # ─────────────────────────────────────

    def acquire_processing(self, key: str, timeout: float = 10.0) -> bool:
        """
        Try to acquire exclusive processing for a key.
        
        If another request with the same key is in-flight, wait for it
        to complete and return False (indicating caller should replay).
        
        Returns True if caller should process, False if should replay.
        """
        with self._lock:
            if key in self._processing:
                # Another request is processing this key — wait
                event = self._processing[key]
            else:
                # We're first — acquire
                self._processing[key] = threading.Event()
                return True

        # Wait for the other request to finish
        completed = event.wait(timeout=timeout)
        self._concurrent_dedup += 1
        return False  # Caller should replay from store

    def release_processing(self, key: str):
        """Release processing lock without storing (e.g., on error)."""
        with self._lock:
            if key in self._processing:
                self._processing[key].set()
                del self._processing[key]

    # ─────────────────────────────────────
    # Request Hash Helper
    # ─────────────────────────────────────

    @staticmethod
    def hash_request(method: str, path: str, body: str = "") -> str:
        """Create a hash of the request for collision detection."""
        content = f"{method}:{path}:{body}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    # ─────────────────────────────────────
    # Cleanup
    # ─────────────────────────────────────

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        now = time.time()
        removed = 0
        with self._lock:
            expired_keys = [
                k for k, v in self._store.items()
                if now - v.created_at > self._retention_seconds
            ]
            for k in expired_keys:
                del self._store[k]
                removed += 1
        return removed

    def clear(self):
        """Clear all stored idempotency records."""
        with self._lock:
            self._store.clear()
            self._processing.clear()

    # ─────────────────────────────────────
    # Stats
    # ─────────────────────────────────────

    def stats(self) -> dict:
        total = max(self._total_checks, 1)
        return {
            "engine": "IdempotencyGuard",
            "stored_keys": len(self._store),
            "max_entries": self._max_entries,
            "retention_seconds": self._retention_seconds,
            "total_checks": self._total_checks,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate_pct": round(self._cache_hits / total * 100, 2),
            "collisions": self._collisions,
            "concurrent_dedup": self._concurrent_dedup,
            "in_flight_keys": len(self._processing),
        }


# ─────────────────────────────────────────────────────
# Global singleton
# ─────────────────────────────────────────────────────
idempotency_guard = IdempotencyGuard()
