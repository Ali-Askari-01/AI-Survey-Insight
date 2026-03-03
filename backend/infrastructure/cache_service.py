"""
Cache Service — Application-Level Caching Infrastructure (Section 12)
═══════════════════════════════════════════════════════
AI dashboards repeatedly query data. Use caching.

Cache targets:
  - Dashboard stats
  - Sentiment summaries
  - Frequent queries
  - AI pipeline results

Result: 10–50x faster dashboards

This module implements:
  - In-memory LRU cache (Phase 1 — MVP)
  - TTL-based expiration
  - Cache namespaces (dashboard, ai, query, session)
  - Cache warming / pre-population
  - Hit/miss metrics for observability
  - Invalidation patterns (key, prefix, namespace)
  - Size-bounded memory management
  - Migration path to Redis (Phase 2)
"""

import time
import threading
import hashlib
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from collections import OrderedDict
from datetime import datetime


# ═══════════════════════════════════════════════════
# CACHE NAMESPACES
# ═══════════════════════════════════════════════════
class CacheNamespace(Enum):
    """Logical cache partitions for isolation and targeted invalidation."""
    DASHBOARD = "dashboard"      # Dashboard stats, summaries
    AI_RESULT = "ai_result"      # AI pipeline outputs
    QUERY = "query"              # Database query results
    SESSION = "session"          # Active session data
    INSIGHT = "insight"          # Insight/theme data
    REPORT = "report"            # Generated reports
    CONFIG = "config"            # Configuration cache


# ═══════════════════════════════════════════════════
# CACHE ENTRY
# ═══════════════════════════════════════════════════
@dataclass
class CacheEntry:
    """Individual cached item with TTL and metadata."""
    key: str
    value: Any
    namespace: CacheNamespace
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_estimate: int = 0           # Approximate memory in bytes
    tags: List[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        return self.expires_at > 0 and time.time() > self.expires_at

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "namespace": self.namespace.value,
            "age_seconds": round(self.age_seconds, 1),
            "access_count": self.access_count,
            "size_estimate": self.size_estimate,
            "is_expired": self.is_expired,
            "expires_in": round(max(0, self.expires_at - time.time()), 1) if self.expires_at > 0 else None,
            "tags": self.tags,
        }


# ═══════════════════════════════════════════════════
# CACHE CONFIGURATION
# ═══════════════════════════════════════════════════
@dataclass
class CacheConfig:
    """Cache service configuration."""
    max_entries: int = 2000              # Max total cached items
    max_memory_mb: int = 128             # Max memory usage estimate
    default_ttl_seconds: float = 3600    # 1 hour default TTL
    namespace_ttls: Dict[str, float] = field(default_factory=lambda: {
        "dashboard": 300,       # 5 min — dashboards refresh often
        "ai_result": 3600,      # 1 hour — AI results are expensive
        "query": 600,           # 10 min — DB query cache
        "session": 1800,        # 30 min — session data
        "insight": 1800,        # 30 min — insight data
        "report": 7200,         # 2 hours — reports are stable
        "config": 86400,        # 24 hours — config rarely changes
    })
    cleanup_interval_seconds: float = 60.0   # Expired entry cleanup cycle
    enable_stats: bool = True


# ═══════════════════════════════════════════════════
# CACHE SERVICE
# ═══════════════════════════════════════════════════
class CacheService:
    """
    Production-grade in-memory cache with LRU eviction and TTL expiration.

    Architecture:
      API / Service → CacheService.get() → [HIT] return cached
                                          → [MISS] compute → store → return

    Phase 1: In-process OrderedDict LRU (current — MVP)
    Phase 2: Redis cache (multi-process, multi-server)

    Features:
      - Namespace-isolated caching
      - TTL per namespace and per key
      - LRU eviction when memory/size exceeded
      - Batch get/set operations
      - Cache warming (pre-populate frequently accessed data)
      - Prefix/namespace invalidation
      - Full observability metrics
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()

        # Metrics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._invalidations = 0
        self._total_memory_estimate = 0
        self._warmups = 0

    # ─── Core Operations ───
    def get(self, key: str, namespace: CacheNamespace = CacheNamespace.QUERY) -> Optional[Any]:
        """
        Retrieve a value from cache. Returns None on miss.
        Promotes key to most-recently-used on hit.
        """
        full_key = self._full_key(key, namespace)
        with self._lock:
            entry = self._store.get(full_key)
            if entry is None:
                self._misses += 1
                return None

            # Check expiry
            if entry.is_expired:
                self._remove_entry(full_key)
                self._misses += 1
                return None

            # Cache hit — move to end (most recently used)
            self._store.move_to_end(full_key)
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        namespace: CacheNamespace = CacheNamespace.QUERY,
        ttl_seconds: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """
        Store a value in cache with optional TTL override.
        Evicts LRU entries if cache is full.
        """
        full_key = self._full_key(key, namespace)
        ttl = ttl_seconds if ttl_seconds is not None else self.config.namespace_ttls.get(
            namespace.value, self.config.default_ttl_seconds
        )
        size_est = self._estimate_size(value)
        expires = time.time() + ttl if ttl > 0 else 0

        entry = CacheEntry(
            key=full_key,
            value=value,
            namespace=namespace,
            expires_at=expires,
            size_estimate=size_est,
            tags=tags or [],
        )

        with self._lock:
            # Remove old entry if exists
            if full_key in self._store:
                old = self._store[full_key]
                self._total_memory_estimate -= old.size_estimate
                del self._store[full_key]

            # Evict LRU if needed
            self._evict_if_needed(size_est)

            self._store[full_key] = entry
            self._total_memory_estimate += size_est

    def delete(self, key: str, namespace: CacheNamespace = CacheNamespace.QUERY) -> bool:
        """Remove a specific key from cache."""
        full_key = self._full_key(key, namespace)
        with self._lock:
            if full_key in self._store:
                self._remove_entry(full_key)
                self._invalidations += 1
                return True
        return False

    def exists(self, key: str, namespace: CacheNamespace = CacheNamespace.QUERY) -> bool:
        """Check if a key exists and is not expired."""
        full_key = self._full_key(key, namespace)
        with self._lock:
            entry = self._store.get(full_key)
            if entry and not entry.is_expired:
                return True
        return False

    # ─── Batch Operations ───
    def get_many(self, keys: List[str], namespace: CacheNamespace = CacheNamespace.QUERY) -> Dict[str, Any]:
        """Batch get multiple keys. Returns dict of key → value for hits only."""
        results = {}
        for key in keys:
            val = self.get(key, namespace)
            if val is not None:
                results[key] = val
        return results

    def set_many(
        self,
        items: Dict[str, Any],
        namespace: CacheNamespace = CacheNamespace.QUERY,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        """Batch set multiple key-value pairs."""
        for key, value in items.items():
            self.set(key, value, namespace, ttl_seconds)

    # ─── Invalidation Patterns ───
    def invalidate_namespace(self, namespace: CacheNamespace) -> int:
        """Invalidate all entries in a namespace."""
        prefix = f"{namespace.value}:"
        count = 0
        with self._lock:
            keys_to_remove = [k for k in self._store if k.startswith(prefix)]
            for key in keys_to_remove:
                self._remove_entry(key)
                count += 1
            self._invalidations += count
        return count

    def invalidate_prefix(self, prefix: str, namespace: CacheNamespace = CacheNamespace.QUERY) -> int:
        """Invalidate all entries whose key starts with a prefix."""
        full_prefix = f"{namespace.value}:{prefix}"
        count = 0
        with self._lock:
            keys_to_remove = [k for k in self._store if k.startswith(full_prefix)]
            for key in keys_to_remove:
                self._remove_entry(key)
                count += 1
            self._invalidations += count
        return count

    def invalidate_tags(self, tags: List[str]) -> int:
        """Invalidate all entries matching any of the given tags."""
        tag_set = set(tags)
        count = 0
        with self._lock:
            keys_to_remove = [
                k for k, entry in self._store.items()
                if tag_set.intersection(entry.tags)
            ]
            for key in keys_to_remove:
                self._remove_entry(key)
                count += 1
            self._invalidations += count
        return count

    def clear(self) -> int:
        """Clear all cache entries."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            self._total_memory_estimate = 0
            self._invalidations += count
        return count

    # ─── Cache Warming ───
    def warm(self, loader: Callable[[], Dict[str, Any]], namespace: CacheNamespace, ttl_seconds: Optional[float] = None) -> int:
        """
        Pre-populate cache from a loader function.
        Used at startup for dashboards, frequent queries, etc.

        Args:
            loader: Function that returns Dict[str, value] to cache
            namespace: Target namespace
            ttl_seconds: Optional TTL override

        Returns:
            Number of entries warmed
        """
        try:
            data = loader()
            if not isinstance(data, dict):
                return 0
            for key, value in data.items():
                self.set(key, value, namespace, ttl_seconds)
            self._warmups += 1
            return len(data)
        except Exception:
            return 0

    # ─── Decorator for Function Caching ───
    def cached(self, namespace: CacheNamespace = CacheNamespace.QUERY, ttl_seconds: Optional[float] = None):
        """
        Decorator to automatically cache function results.

        Usage:
            @cache_service.cached(CacheNamespace.DASHBOARD, ttl_seconds=300)
            def get_dashboard_stats(survey_id):
                ...
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Build cache key from function name + args
                key_parts = [func.__name__] + [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()

                # Try cache
                result = self.get(cache_key, namespace)
                if result is not None:
                    return result

                # Execute and cache
                result = func(*args, **kwargs)
                self.set(cache_key, result, namespace, ttl_seconds)
                return result
            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper
        return decorator

    # ─── Cleanup ───
    def cleanup_expired(self) -> int:
        """Remove all expired entries. Called periodically."""
        count = 0
        with self._lock:
            keys_to_remove = [k for k, entry in self._store.items() if entry.is_expired]
            for key in keys_to_remove:
                self._remove_entry(key)
                count += 1
        return count

    # ─── Internal Helpers ───
    def _full_key(self, key: str, namespace: CacheNamespace) -> str:
        return f"{namespace.value}:{key}"

    def _remove_entry(self, full_key: str):
        """Remove entry and update memory tracking. Must be called under lock."""
        entry = self._store.pop(full_key, None)
        if entry:
            self._total_memory_estimate -= entry.size_estimate

    def _evict_if_needed(self, new_size: int):
        """Evict LRU entries if cache exceeds limits. Must be called under lock."""
        max_bytes = self.config.max_memory_mb * 1024 * 1024

        # Evict by size
        while len(self._store) >= self.config.max_entries or (self._total_memory_estimate + new_size) > max_bytes:
            if not self._store:
                break
            # Pop LRU (first item)
            evicted_key, evicted_entry = self._store.popitem(last=False)
            self._total_memory_estimate -= evicted_entry.size_estimate
            self._evictions += 1

    @staticmethod
    def _estimate_size(value: Any) -> int:
        """Rough estimate of value size in bytes."""
        try:
            if isinstance(value, (str, bytes)):
                return len(value)
            if isinstance(value, (int, float, bool)):
                return 8
            if isinstance(value, dict):
                return len(json.dumps(value, default=str))
            if isinstance(value, (list, tuple)):
                return len(json.dumps(value, default=str))
            return 256  # Default estimate for complex objects
        except Exception:
            return 256

    # ─── Stats & Observability ───
    def stats(self) -> dict:
        """Full cache observability metrics."""
        total_requests = self._hits + self._misses
        hit_rate = round(self._hits / max(total_requests, 1) * 100, 1)

        by_namespace = {}
        for entry in self._store.values():
            ns = entry.namespace.value
            if ns not in by_namespace:
                by_namespace[ns] = {"count": 0, "size_bytes": 0}
            by_namespace[ns]["count"] += 1
            by_namespace[ns]["size_bytes"] += entry.size_estimate

        return {
            "total_entries": len(self._store),
            "max_entries": self.config.max_entries,
            "memory_estimate_bytes": self._total_memory_estimate,
            "memory_estimate_human": f"{self._total_memory_estimate / (1024*1024):.1f} MB",
            "max_memory_mb": self.config.max_memory_mb,
            "hit_rate_percent": hit_rate,
            "metrics": {
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "invalidations": self._invalidations,
                "warmups": self._warmups,
                "total_requests": total_requests,
            },
            "by_namespace": by_namespace,
            "config": {
                "default_ttl_seconds": self.config.default_ttl_seconds,
                "namespace_ttls": self.config.namespace_ttls,
                "cleanup_interval": self.config.cleanup_interval_seconds,
            },
        }


# ═══════════════════════════════════════════════════
# GLOBAL CACHE SERVICE SINGLETON
# ═══════════════════════════════════════════════════
cache_service = CacheService()
