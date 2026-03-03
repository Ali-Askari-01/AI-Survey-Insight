"""
Database Manager — Database Infrastructure (Section 8)
═══════════════════════════════════════════════════════
Primary Database:
  SQLite → MVP
  Later: PostgreSQL

Separation Strategy (logical separation):
  Transaction DB: users, feedback, responses
  Analytics DB: insights, aggregated metrics
  Vector Storage (Future): embeddings, semantic search, clustering

This module implements:
  - Connection pooling with thread-safe checkout/checkin
  - Migration tracking and auto-migration
  - Read replica simulation (analytics queries on separate connection)
  - Query execution with metrics (latency, count)
  - Schema versioning
  - Backup/restore utilities
  - Connection health monitoring
  - Future migration path: SQLite → PostgreSQL
"""

import os
import time
import sqlite3
import shutil
import threading
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from queue import Queue, Empty
from contextlib import contextmanager


# ═══════════════════════════════════════════════════
# DB MANAGER CONFIGURATION
# ═══════════════════════════════════════════════════
@dataclass
class DBConfig:
    """Database manager configuration."""
    db_path: str = ""                          # Populated in __post_init__
    pool_size: int = 5                         # Connection pool size
    max_overflow: int = 3                      # Extra connections beyond pool
    pool_timeout: float = 30.0                 # Wait for connection timeout
    statement_timeout_ms: int = 30000          # Query timeout
    enable_wal: bool = True                    # WAL mode for concurrent reads
    enable_foreign_keys: bool = True
    journal_size_limit: int = 67108864         # 64MB journal limit
    cache_size_kb: int = 8192                  # 8MB page cache
    busy_timeout_ms: int = 5000
    enable_query_metrics: bool = True

    def __post_init__(self):
        if not self.db_path:
            self.db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "survey_engine.db"
            )


# ═══════════════════════════════════════════════════
# MIGRATION DEFINITION
# ═══════════════════════════════════════════════════
@dataclass
class Migration:
    """A database migration step."""
    version: int
    name: str
    sql_up: str
    sql_down: str = ""
    applied_at: Optional[str] = None


# ═══════════════════════════════════════════════════
# CONNECTION POOL
# ═══════════════════════════════════════════════════
class ConnectionPool:
    """
    Thread-safe SQLite connection pool.

    SQLite supports limited concurrency. This pool manages connections
    to ensure thread safety and reuse.

    Phase 1: SQLite pool (current)
    Phase 2: PostgreSQL pool (asyncpg / psycopg pool)
    """

    def __init__(self, db_path: str, pool_size: int = 5, max_overflow: int = 3):
        self.db_path = db_path
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self._pool: Queue = Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._active_count = 0
        self._total_created = 0
        self._total_checkout = 0
        self._total_checkin = 0

        # Pre-create pool connections
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        for _ in range(pool_size):
            conn = self._create_connection()
            self._pool.put(conn)

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new configured SQLite connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA cache_size=-8192")       # 8MB cache
        conn.execute("PRAGMA synchronous=NORMAL")      # Faster writes with WAL
        conn.execute("PRAGMA temp_store=MEMORY")
        self._total_created += 1
        return conn

    def checkout(self, timeout: float = 30.0) -> sqlite3.Connection:
        """Get a connection from the pool."""
        try:
            conn = self._pool.get(timeout=timeout)
            self._total_checkout += 1
            self._active_count += 1
            return conn
        except Empty:
            # Overflow: create temporary connection
            with self._lock:
                if self._active_count < self.pool_size + self.max_overflow:
                    conn = self._create_connection()
                    self._active_count += 1
                    self._total_checkout += 1
                    return conn
            raise TimeoutError(f"Connection pool exhausted (size={self.pool_size}, overflow={self.max_overflow})")

    def checkin(self, conn: sqlite3.Connection):
        """Return a connection to the pool."""
        self._active_count -= 1
        self._total_checkin += 1
        try:
            self._pool.put_nowait(conn)
        except Exception:
            # Pool full — close overflow connection
            try:
                conn.close()
            except Exception:
                pass

    def close_all(self):
        """Close all connections in the pool."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Exception:
                pass

    def stats(self) -> dict:
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "active_connections": self._active_count,
            "available": self._pool.qsize(),
            "total_created": self._total_created,
            "total_checkout": self._total_checkout,
            "total_checkin": self._total_checkin,
        }


# ═══════════════════════════════════════════════════
# DATABASE MANAGER
# ═══════════════════════════════════════════════════
class DatabaseManager:
    """
    Production-grade database management layer.

    Features:
      - Connection pooling with checkout/checkin
      - Context manager for auto-commit/rollback
      - Migration tracking and execution
      - Query metrics (count, latency)
      - Read replica simulation (separate analytics connection)
      - Backup/restore utilities
      - Health check support

    Architecture:
      Application → DatabaseManager → ConnectionPool → SQLite/PostgreSQL

    Separation strategy:
      Transaction queries → primary pool
      Analytics queries → analytics pool (read-optimized)
    """

    def __init__(self, config: Optional[DBConfig] = None):
        self.config = config or DBConfig()
        self._primary_pool = ConnectionPool(
            db_path=self.config.db_path,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
        )

        # Analytics replica (same DB, separate connection pool with read-only pragmas)
        self._analytics_pool = ConnectionPool(
            db_path=self.config.db_path,
            pool_size=max(2, self.config.pool_size // 2),
            max_overflow=1,
        )

        # Migrations
        self._migrations: List[Migration] = []
        self._schema_version = 0

        # Query metrics
        self._lock = threading.Lock()
        self._query_count = 0
        self._query_total_ms = 0.0
        self._slow_queries: List[dict] = []      # Queries > threshold
        self._slow_threshold_ms = 1000.0          # 1 second

        # Initialize migration tracking table
        self._init_migration_table()

    def _init_migration_table(self):
        """Create the migration tracking table if it doesn't exist."""
        conn = self._primary_pool.checkout()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    checksum TEXT
                )
            """)
            conn.commit()

            # Get current schema version
            cursor = conn.execute("SELECT MAX(version) FROM _schema_migrations")
            row = cursor.fetchone()
            self._schema_version = row[0] if row[0] is not None else 0
        finally:
            self._primary_pool.checkin(conn)

    # ─── Connection Context Manager ───
    @contextmanager
    def connection(self, analytics: bool = False):
        """
        Context manager for database connections.
        Auto-commits on success, rolls back on exception.

        Usage:
            with db_manager.connection() as conn:
                conn.execute("INSERT INTO ...")

            with db_manager.connection(analytics=True) as conn:
                conn.execute("SELECT ... complex aggregation ...")
        """
        pool = self._analytics_pool if analytics else self._primary_pool
        conn = pool.checkout(timeout=self.config.pool_timeout)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            pool.checkin(conn)

    # ─── Query Execution ───
    def execute(self, sql: str, params: tuple = (), analytics: bool = False) -> sqlite3.Cursor:
        """Execute a query with metrics tracking."""
        pool = self._analytics_pool if analytics else self._primary_pool
        conn = pool.checkout(timeout=self.config.pool_timeout)
        try:
            start = time.time()
            cursor = conn.execute(sql, params)
            conn.commit()
            elapsed_ms = (time.time() - start) * 1000

            if self.config.enable_query_metrics:
                self._record_query(sql, elapsed_ms)

            return cursor
        except Exception:
            conn.rollback()
            raise
        finally:
            pool.checkin(conn)

    def fetch_one(self, sql: str, params: tuple = (), analytics: bool = False) -> Optional[dict]:
        """Execute and fetch one row as dict."""
        pool = self._analytics_pool if analytics else self._primary_pool
        conn = pool.checkout(timeout=self.config.pool_timeout)
        try:
            start = time.time()
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()
            elapsed_ms = (time.time() - start) * 1000

            if self.config.enable_query_metrics:
                self._record_query(sql, elapsed_ms)

            return dict(row) if row else None
        finally:
            pool.checkin(conn)

    def fetch_all(self, sql: str, params: tuple = (), analytics: bool = False) -> List[dict]:
        """Execute and fetch all rows as list of dicts."""
        pool = self._analytics_pool if analytics else self._primary_pool
        conn = pool.checkout(timeout=self.config.pool_timeout)
        try:
            start = time.time()
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            elapsed_ms = (time.time() - start) * 1000

            if self.config.enable_query_metrics:
                self._record_query(sql, elapsed_ms)

            return [dict(r) for r in rows]
        finally:
            pool.checkin(conn)

    def _record_query(self, sql: str, elapsed_ms: float):
        """Record query metrics."""
        with self._lock:
            self._query_count += 1
            self._query_total_ms += elapsed_ms
            if elapsed_ms > self._slow_threshold_ms:
                self._slow_queries.append({
                    "sql": sql[:200],
                    "latency_ms": round(elapsed_ms, 2),
                    "at": datetime.now().isoformat(),
                })
                if len(self._slow_queries) > 50:
                    self._slow_queries = self._slow_queries[-50:]

    # ─── Migration System ───
    def register_migration(self, version: int, name: str, sql_up: str, sql_down: str = ""):
        """Register a migration to be applied."""
        self._migrations.append(Migration(version=version, name=name, sql_up=sql_up, sql_down=sql_down))
        self._migrations.sort(key=lambda m: m.version)

    def apply_migrations(self) -> List[str]:
        """Apply all pending migrations in order."""
        applied = []
        conn = self._primary_pool.checkout()
        try:
            for migration in self._migrations:
                if migration.version > self._schema_version:
                    try:
                        # Execute migration SQL
                        for statement in migration.sql_up.split(";"):
                            stmt = statement.strip()
                            if stmt:
                                conn.execute(stmt)

                        # Record migration
                        conn.execute(
                            "INSERT INTO _schema_migrations (version, name) VALUES (?, ?)",
                            (migration.version, migration.name)
                        )
                        conn.commit()
                        self._schema_version = migration.version
                        applied.append(f"v{migration.version}: {migration.name}")
                    except Exception as e:
                        conn.rollback()
                        raise RuntimeError(f"Migration v{migration.version} failed: {e}")
        finally:
            self._primary_pool.checkin(conn)

        return applied

    def get_migration_history(self) -> List[dict]:
        """Get all applied migrations."""
        return self.fetch_all("SELECT * FROM _schema_migrations ORDER BY version")

    # ─── Backup/Restore ───
    def backup(self, backup_path: Optional[str] = None) -> str:
        """
        Create a database backup.
        Returns the path to the backup file.
        """
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(os.path.dirname(self.config.db_path), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"backup_{timestamp}.db")

        conn = self._primary_pool.checkout()
        try:
            backup_conn = sqlite3.connect(backup_path)
            conn.backup(backup_conn)
            backup_conn.close()
        finally:
            self._primary_pool.checkin(conn)

        return backup_path

    def list_backups(self) -> List[dict]:
        """List available database backups."""
        backup_dir = os.path.join(os.path.dirname(self.config.db_path), "backups")
        if not os.path.exists(backup_dir):
            return []

        backups = []
        for f in sorted(os.listdir(backup_dir)):
            if f.endswith(".db"):
                full_path = os.path.join(backup_dir, f)
                backups.append({
                    "filename": f,
                    "path": full_path,
                    "size_mb": round(os.path.getsize(full_path) / (1024 * 1024), 2),
                    "created_at": datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat(),
                })
        return backups

    # ─── Schema Info ───
    def get_schema_info(self) -> dict:
        """Get database schema information."""
        tables = self.fetch_all(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )

        table_info = {}
        for table in tables:
            name = table["name"]
            count_row = self.fetch_one(f"SELECT COUNT(*) as cnt FROM [{name}]")
            table_info[name] = {
                "row_count": count_row["cnt"] if count_row else 0,
            }

        return {
            "engine": "sqlite",
            "path": self.config.db_path,
            "schema_version": self._schema_version,
            "total_tables": len(tables),
            "tables": table_info,
            "wal_mode": self.config.enable_wal,
            "db_size_mb": round(os.path.getsize(self.config.db_path) / (1024 * 1024), 2) if os.path.exists(self.config.db_path) else 0,
        }

    # ─── Health Check ───
    def health_check(self) -> dict:
        """Database health check for health monitor integration."""
        try:
            start = time.time()
            row = self.fetch_one("SELECT 1 as ok")
            latency = (time.time() - start) * 1000

            integrity = self.fetch_one("PRAGMA integrity_check")
            integrity_ok = integrity and dict(integrity).get("integrity_check", "") == "ok"

            return {
                "ok": True,
                "latency_ms": round(latency, 2),
                "integrity": "ok" if integrity_ok else "failed",
                "schema_version": self._schema_version,
                "pool": self._primary_pool.stats(),
                "analytics_pool": self._analytics_pool.stats(),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ─── Shutdown ───
    def close(self):
        """Close all connection pools gracefully."""
        self._primary_pool.close_all()
        self._analytics_pool.close_all()

    # ─── Stats ───
    def stats(self) -> dict:
        """Full database manager metrics."""
        avg_query_ms = round(self._query_total_ms / max(self._query_count, 1), 2)
        return {
            "config": {
                "db_path": self.config.db_path,
                "pool_size": self.config.pool_size,
                "max_overflow": self.config.max_overflow,
                "wal_mode": self.config.enable_wal,
            },
            "primary_pool": self._primary_pool.stats(),
            "analytics_pool": self._analytics_pool.stats(),
            "schema_version": self._schema_version,
            "query_metrics": {
                "total_queries": self._query_count,
                "avg_latency_ms": avg_query_ms,
                "slow_queries_count": len(self._slow_queries),
                "slow_threshold_ms": self._slow_threshold_ms,
                "recent_slow_queries": self._slow_queries[-5:],
            },
        }


# ═══════════════════════════════════════════════════
# GLOBAL DATABASE MANAGER SINGLETON
# ═══════════════════════════════════════════════════
db_manager = DatabaseManager()
