"""
PostgreSQL Migration Module
═══════════════════════════════════════════════════════
Handles the migration path from SQLite to PostgreSQL.

Strategy:
  1. Environment-based database selection (DATABASE_URL env var)
  2. If DATABASE_URL is set → use PostgreSQL
  3. If not set → continue using SQLite (current behavior)
  4. Migration script exports SQLite data and imports into PostgreSQL

Usage:
  # Set env and restart:
  DATABASE_URL=postgresql://user:pass@host:5432/survey_db

  # Or run migration manually:
  python -m backend.services.pg_migration migrate

Prerequisites:
  pip install psycopg2-binary  (only needed when migrating/using PostgreSQL)
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
from contextlib import contextmanager

# Import the existing SQLite path
from ..database import DB_PATH


# ═══════════════════════════════════════════════════
# DATABASE URL DETECTION
# ═══════════════════════════════════════════════════
DATABASE_URL = os.environ.get("DATABASE_URL", "")

def is_postgres() -> bool:
    """Check if the app is configured for PostgreSQL."""
    return DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")


def get_connection_info() -> dict:
    """Get current database connection info."""
    if is_postgres():
        # Mask password in URL
        safe_url = DATABASE_URL
        if "@" in safe_url:
            parts = safe_url.split("@")
            creds = parts[0].split("//")[1] if "//" in parts[0] else parts[0]
            user = creds.split(":")[0] if ":" in creds else creds
            safe_url = f"postgresql://{user}:****@{parts[1]}"
        return {
            "engine": "postgresql",
            "url": safe_url,
            "status": "configured",
        }
    return {
        "engine": "sqlite",
        "path": DB_PATH,
        "size_mb": round(os.path.getsize(DB_PATH) / (1024 * 1024), 2) if os.path.exists(DB_PATH) else 0,
        "status": "active",
        "migration_hint": "Set DATABASE_URL env var to switch to PostgreSQL",
    }


# ═══════════════════════════════════════════════════
# POSTGRESQL CONNECTION (lazy import)
# ═══════════════════════════════════════════════════
def _get_pg_connection():
    """Get a PostgreSQL connection. Requires psycopg2."""
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        raise RuntimeError(
            "psycopg2 is required for PostgreSQL. Install it: pip install psycopg2-binary"
        )
    conn = psycopg2.connect(DATABASE_URL)
    return conn


@contextmanager
def pg_connection():
    """Context manager for PostgreSQL connections."""
    conn = _get_pg_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ═══════════════════════════════════════════════════
# SCHEMA TRANSLATION: SQLite → PostgreSQL
# ═══════════════════════════════════════════════════
SQLITE_TO_PG_TYPE_MAP = {
    "INTEGER PRIMARY KEY AUTOINCREMENT": "SERIAL PRIMARY KEY",
    "INTEGER": "INTEGER",
    "TEXT": "TEXT",
    "REAL": "DOUBLE PRECISION",
    "BLOB": "BYTEA",
    "TIMESTAMP": "TIMESTAMP",
    "BOOLEAN": "BOOLEAN",
    "DEFAULT CURRENT_TIMESTAMP": "DEFAULT NOW()",
}


def _translate_create_table(sqlite_sql: str) -> str:
    """Translate a SQLite CREATE TABLE statement to PostgreSQL syntax."""
    pg_sql = sqlite_sql
    for sqlite_type, pg_type in SQLITE_TO_PG_TYPE_MAP.items():
        pg_sql = pg_sql.replace(sqlite_type, pg_type)
    # Fix AUTOINCREMENT remnants
    pg_sql = pg_sql.replace("AUTOINCREMENT", "")
    return pg_sql


def get_sqlite_tables() -> list:
    """Get all table names from the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables


def get_sqlite_schema() -> dict:
    """Get the full schema from SQLite for all tables."""
    conn = sqlite3.connect(DB_PATH)
    tables = {}
    for table in get_sqlite_tables():
        cursor = conn.execute(f"PRAGMA table_info({table})")
        columns = []
        for col in cursor.fetchall():
            columns.append({
                "cid": col[0],
                "name": col[1],
                "type": col[2],
                "notnull": col[3],
                "default": col[4],
                "pk": col[5],
            })
        # Get row count
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        # Get CREATE statement
        create_sql = conn.execute(
            f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        tables[table] = {
            "columns": columns,
            "row_count": count,
            "create_sql": create_sql[0] if create_sql else None,
        }
    conn.close()
    return tables


# ═══════════════════════════════════════════════════
# MIGRATION ENGINE
# ═══════════════════════════════════════════════════
def create_pg_schema():
    """Create all tables in PostgreSQL based on SQLite schema."""
    schema = get_sqlite_schema()

    with pg_connection() as pg_conn:
        pg_cursor = pg_conn.cursor()

        for table_name, table_info in schema.items():
            create_sql = table_info.get("create_sql")
            if not create_sql:
                print(f"  ⚠ Skipping {table_name} — no CREATE statement")
                continue

            pg_create = _translate_create_table(create_sql)

            # Drop IF EXISTS for clean migration
            pg_cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
            try:
                pg_cursor.execute(pg_create)
                print(f"  ✓ Created table: {table_name}")
            except Exception as e:
                print(f"  ✗ Failed to create {table_name}: {e}")
                # Fallback: create a simple version
                cols = ", ".join(
                    f'"{c["name"]}" {c["type"] or "TEXT"}'
                    for c in table_info["columns"]
                )
                try:
                    pg_cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({cols})")
                    print(f"  ✓ Created table (fallback): {table_name}")
                except Exception as e2:
                    print(f"  ✗ Fallback also failed for {table_name}: {e2}")

        pg_conn.commit()


def migrate_data(batch_size: int = 500):
    """Migrate all data from SQLite to PostgreSQL."""
    schema = get_sqlite_schema()
    sqlite_conn = sqlite3.connect(DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    stats = {"tables": 0, "rows": 0, "errors": []}

    with pg_connection() as pg_conn:
        pg_cursor = pg_conn.cursor()

        for table_name, table_info in schema.items():
            row_count = table_info["row_count"]
            if row_count == 0:
                print(f"  ○ {table_name}: empty, skipping")
                continue

            columns = [c["name"] for c in table_info["columns"]]
            col_list = ", ".join(f'"{c}"' for c in columns)
            placeholders = ", ".join(["%s"] * len(columns))
            insert_sql = f'INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})'

            try:
                # Read from SQLite in batches
                offset = 0
                table_rows = 0
                while True:
                    rows = sqlite_conn.execute(
                        f"SELECT * FROM {table_name} LIMIT {batch_size} OFFSET {offset}"
                    ).fetchall()
                    if not rows:
                        break

                    for row in rows:
                        values = [row[col] for col in columns]
                        try:
                            pg_cursor.execute(insert_sql, values)
                            table_rows += 1
                        except Exception as e:
                            stats["errors"].append(f"{table_name} row {offset + table_rows}: {e}")

                    offset += batch_size

                pg_conn.commit()

                # Reset sequences for serial columns
                for col_info in table_info["columns"]:
                    if col_info["pk"]:
                        seq_name = f"{table_name}_{col_info['name']}_seq"
                        try:
                            pg_cursor.execute(
                                f"SELECT setval('{seq_name}', COALESCE((SELECT MAX({col_info['name']}) FROM {table_name}), 1))"
                            )
                        except Exception:
                            pass  # Sequence may not exist for non-serial PKs

                pg_conn.commit()
                stats["tables"] += 1
                stats["rows"] += table_rows
                print(f"  ✓ {table_name}: {table_rows}/{row_count} rows migrated")

            except Exception as e:
                stats["errors"].append(f"{table_name}: {e}")
                print(f"  ✗ {table_name}: {e}")

    sqlite_conn.close()
    return stats


def run_full_migration() -> dict:
    """Run the complete SQLite → PostgreSQL migration."""
    if not is_postgres():
        return {
            "success": False,
            "error": "DATABASE_URL not set. Set it to a PostgreSQL connection string.",
        }

    print("=" * 60)
    print("SQLite → PostgreSQL Migration")
    print("=" * 60)

    start = datetime.now()

    # Step 1: Schema
    print("\n[1/3] Creating PostgreSQL schema...")
    create_pg_schema()

    # Step 2: Data
    print("\n[2/3] Migrating data...")
    stats = migrate_data()

    # Step 3: Verify
    print("\n[3/3] Verifying migration...")
    sqlite_schema = get_sqlite_schema()
    total_source_rows = sum(t["row_count"] for t in sqlite_schema.values())

    elapsed = (datetime.now() - start).total_seconds()

    result = {
        "success": len(stats["errors"]) == 0,
        "duration_seconds": round(elapsed, 2),
        "tables_migrated": stats["tables"],
        "rows_migrated": stats["rows"],
        "source_rows": total_source_rows,
        "errors": stats["errors"][:20],  # Cap error output
    }

    print(f"\n{'=' * 60}")
    print(f"Migration {'COMPLETE' if result['success'] else 'COMPLETED WITH ERRORS'}")
    print(f"Tables: {stats['tables']}, Rows: {stats['rows']}/{total_source_rows}, Time: {elapsed:.1f}s")
    if stats["errors"]:
        print(f"Errors: {len(stats['errors'])}")
    print(f"{'=' * 60}")

    return result


# ═══════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        run_full_migration()
    elif len(sys.argv) > 1 and sys.argv[1] == "schema":
        schema = get_sqlite_schema()
        for table, info in schema.items():
            print(f"{table}: {info['row_count']} rows, {len(info['columns'])} columns")
    else:
        print("Usage:")
        print("  python -m backend.services.pg_migration migrate  — Run full migration")
        print("  python -m backend.services.pg_migration schema   — Show current SQLite schema")
