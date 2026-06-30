"""
Compare a source and target PostgreSQL database after a provider migration.

Usage:
    python scripts/verify_postgres_migration.py ^
      --source-db-url "%RAILWAY_DATABASE_URL%" ^
      --target-db-url "%SUPABASE_DATABASE_URL%"

The script only reads metadata and table row counts. It does not modify either
database.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


SYSTEM_TABLES = {"alembic_version"}


@dataclass(frozen=True)
class DatabaseSnapshot:
    alembic_version: Optional[str]
    table_counts: dict[str, int]


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    if "@" not in parts.netloc:
        return url
    credentials, host = parts.netloc.rsplit("@", 1)
    username = credentials.split(":", 1)[0]
    return urlunsplit((parts.scheme, f"{username}:***@{host}", parts.path, "", ""))


def get_public_tables(engine: Engine) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            )
        )
        return [row[0] for row in rows]


def snapshot_database(url: str) -> DatabaseSnapshot:
    engine = create_engine(url, pool_pre_ping=True)
    try:
        tables = get_public_tables(engine)
        counts: dict[str, int] = {}

        with engine.connect() as conn:
            alembic_version = None
            if "alembic_version" in tables:
                alembic_version = conn.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                ).scalar()

            for table in tables:
                if table in SYSTEM_TABLES:
                    continue
                quoted_table = '"' + table.replace('"', '""') + '"'
                counts[table] = conn.execute(
                    text(f"SELECT COUNT(*) FROM public.{quoted_table}")
                ).scalar_one()

        return DatabaseSnapshot(alembic_version=alembic_version, table_counts=counts)
    finally:
        engine.dispose()


def print_count_table(source: DatabaseSnapshot, target: DatabaseSnapshot) -> bool:
    all_tables = sorted(set(source.table_counts) | set(target.table_counts))
    ok = True

    print("Table row count comparison")
    print("--------------------------")
    print(f"{'table':40} {'source':>12} {'target':>12} status")

    for table in all_tables:
        source_count = source.table_counts.get(table)
        target_count = target.table_counts.get(table)
        status = "OK" if source_count == target_count else "MISMATCH"
        ok = ok and status == "OK"
        print(f"{table:40} {source_count!s:>12} {target_count!s:>12} {status}")

    return ok


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that a PostgreSQL migration preserved tables and row counts."
    )
    parser.add_argument("--source-db-url", required=True, help="Railway/source DATABASE_URL")
    parser.add_argument("--target-db-url", required=True, help="Supabase/target DATABASE_URL")
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    print(f"Source: {redact_url(args.source_db_url)}")
    print(f"Target: {redact_url(args.target_db_url)}")

    source = snapshot_database(args.source_db_url)
    target = snapshot_database(args.target_db_url)

    versions_match = source.alembic_version == target.alembic_version
    print()
    print(f"Source Alembic version: {source.alembic_version}")
    print(f"Target Alembic version: {target.alembic_version}")
    print(f"Alembic status: {'OK' if versions_match else 'MISMATCH'}")
    print()

    counts_match = print_count_table(source, target)

    if versions_match and counts_match:
        print("\nMigration verification passed.")
        return 0

    print("\nMigration verification failed. Do not cut over DATABASE_URL yet.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
