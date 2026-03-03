"""
Infrastructure & Scalability Architecture
═══════════════════════════════════════════════════════
Production-grade infrastructure layer for the AI Feedback & Insight Engine.

Modules:
  - task_queue: Async task queue with retry, dead-letter, priority scheduling
  - worker_pool: AI worker pool management with dynamic scaling
  - storage_service: File storage abstraction (audio, transcripts, attachments)
  - cache_service: Application-level caching (dashboards, queries, stats)
  - circuit_breaker: Failure isolation for external API calls
  - health_monitor: Deep health checks for all system components
  - environment: Environment-aware configuration (dev/staging/production)
  - db_manager: Connection pooling, migration tracking, read replicas
  - ws_manager: Enhanced WebSocket with channels, rooms, and presence

Design Philosophy:
  Decoupled + Scalable + Fault-Tolerant + Cloud-Portable
"""

from .task_queue import task_queue, TaskQueue, TaskPriority, TaskStatus, Task
from .worker_pool import worker_pool, WorkerPool, WorkerStatus, PoolConfig
from .storage_service import storage_service, StorageService, FileCategory
from .cache_service import cache_service, CacheService, CacheNamespace
from .circuit_breaker import circuit_registry, CircuitBreaker, CircuitBreakerRegistry, CircuitOpenError
from .health_monitor import health_monitor, HealthMonitor, HealthStatus
from .environment import env_config, EnvironmentConfig, Environment
from .db_manager import db_manager, DatabaseManager
from .ws_manager import enhanced_ws_manager, EnhancedWSManager, WSChannel

__all__ = [
    # Singletons
    "task_queue", "worker_pool", "storage_service", "cache_service",
    "circuit_registry", "health_monitor", "env_config", "db_manager",
    "enhanced_ws_manager",
    # Classes
    "TaskQueue", "WorkerPool", "StorageService", "CacheService",
    "CircuitBreaker", "CircuitBreakerRegistry", "HealthMonitor",
    "EnvironmentConfig", "DatabaseManager", "EnhancedWSManager",
    # Enums
    "TaskPriority", "TaskStatus", "WorkerStatus", "FileCategory",
    "CacheNamespace", "HealthStatus", "Environment", "WSChannel",
    # Errors
    "CircuitOpenError",
    # Configs
    "PoolConfig", "Task",
]
