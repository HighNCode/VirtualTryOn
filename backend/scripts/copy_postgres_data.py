"""
Copy public-schema data between two PostgreSQL databases.

This is a fallback for environments without pg_dump/pg_restore. It assumes the
target schema already exists, usually by running Alembic migrations first.

Usage:
    python scripts/copy_postgres_data.py ^
      --source-db-url "%RAILWAY_DATABASE_URL%" ^
      --target-db-url "%SUPABASE_DATABASE_URL%"
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable, Optional
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import MetaData, create_engine, func, insert, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import Table


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    if "@" not in parts.netloc:
        return url
    credentials, host = parts.netloc.rsplit("@", 1)
    username = credentials.split(":", 1)[0]
    return urlunsplit((parts.scheme, f"{username}:***@{host}", parts.path, "", ""))


def public_metadata(engine: Engine) -> MetaData:
    metadata = MetaData()
    metadata.reflect(bind=engine, schema="public")
    return metadata


def table_label(table: Table) -> str:
    return table.name if table.schema in (None, "public") else f"{table.schema}.{table.name}"


def qualified_table_names(engine: Engine, tables: Iterable[Table]) -> list[str]:
    preparer = engine.dialect.identifier_preparer
    return [
        f"{preparer.quote_schema(table.schema or 'public')}.{preparer.quote(table.name)}"
        for table in tables
    ]


def truncate_target_tables(engine: Engine, tables: list[Table]) -> None:
    if not tables:
        return
    names = ", ".join(qualified_table_names(engine, tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))


def copy_table(source: Engine, target: Engine, table: Table, batch_size: int) -> int:
    copied = 0
    column_names = [column.name for column in table.columns]
    statement = select(table)

    with source.connect().execution_options(stream_results=True) as source_conn:
        result = source_conn.execute(statement)
        while True:
            rows = result.fetchmany(batch_size)
            if not rows:
                break

            payload = [
                {column: row._mapping[column] for column in column_names}
                for row in rows
            ]
            with target.begin() as target_conn:
                target_conn.execute(insert(table), payload)
            copied += len(payload)

    return copied


def reset_sequences(engine: Engine, tables: Iterable[Table]) -> None:
    with engine.begin() as conn:
        for table in tables:
            for column in table.columns:
                sequence_name = conn.execute(
                    text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                    {
                        "table_name": f"{table.schema or 'public'}.{table.name}",
                        "column_name": column.name,
                    },
                ).scalar()
                if not sequence_name:
                    continue

                max_value = conn.execute(select(func.max(column))).scalar()
                if max_value is None:
                    conn.execute(text("SELECT setval(:sequence_name, 1, false)"), {"sequence_name": sequence_name})
                else:
                    conn.execute(
                        text("SELECT setval(:sequence_name, :max_value, true)"),
                        {"sequence_name": sequence_name, "max_value": max_value},
                    )


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy public-schema rows from a source PostgreSQL database to a target."
    )
    parser.add_argument("--source-db-url", required=True, help="Source DATABASE_URL")
    parser.add_argument("--target-db-url", required=True, help="Target DATABASE_URL")
    parser.add_argument("--batch-size", type=int, default=500, help="Rows per insert batch")
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    print(f"Source: {redact_url(args.source_db_url)}")
    print(f"Target: {redact_url(args.target_db_url)}")

    source_engine = create_engine(args.source_db_url, pool_pre_ping=True)
    target_engine = create_engine(args.target_db_url, pool_pre_ping=True)

    try:
        source_metadata = public_metadata(source_engine)
        target_metadata = public_metadata(target_engine)

        source_table_names = {table.name for table in source_metadata.sorted_tables}
        target_table_names = {table.name for table in target_metadata.sorted_tables}
        missing = sorted(source_table_names - target_table_names)
        if missing:
            print(f"Target is missing source tables: {', '.join(missing)}")
            return 1

        tables = [
            table
            for table in target_metadata.sorted_tables
            if table.name in source_table_names
        ]

        print(f"Truncating {len(tables)} target public tables.")
        truncate_target_tables(target_engine, tables)

        for target_table in tables:
            source_table = source_metadata.tables[f"public.{target_table.name}"]
            count = copy_table(source_engine, target_engine, source_table, args.batch_size)
            print(f"{table_label(target_table)}: copied {count} rows")

        reset_sequences(target_engine, tables)
        print("\nPostgreSQL data copy completed.")
        return 0
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
