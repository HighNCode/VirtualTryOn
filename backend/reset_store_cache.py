"""
Store-scoped Redis cleanup for customer-flow artifacts.

This script removes cache keys tied to one store by:
1) scanning store-specific user mapping keys, and
2) resolving session/measurement/try_on IDs from Postgres and deleting only
   corresponding Redis keys.

Usage examples:
  python reset_store_cache.py
  python reset_store_cache.py --dry-run
  python reset_store_cache.py --store-id 9863d2ce-87e0-4005-99f6-a04f90022b82
"""

from __future__ import annotations

import argparse
import os
from typing import Iterable, List, Set

import redis
from sqlalchemy import create_engine, text

try:
    from app.config import get_settings
except Exception:
    get_settings = None


# Prefilled for your current dev store.
DEFAULT_STORE_ID = "9863d2ce-87e0-4005-99f6-a04f90022b82"


def chunked(values: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(values), size):
        yield values[i : i + size]


def fetch_ids(database_url: str, store_id: str) -> tuple[Set[str], Set[str], Set[str], Set[str]]:
    engine = create_engine(database_url)
    sessions: Set[str] = set()
    measurements: Set[str] = set()
    tryons: Set[str] = set()
    studio_keys: Set[str] = set()

    with engine.connect() as conn:
        session_rows = conn.execute(
            text("SELECT session_id::text FROM sessions WHERE store_id = :store_id"),
            {"store_id": store_id},
        )
        sessions = {row[0] for row in session_rows}

        measurement_rows = conn.execute(
            text(
                """
                SELECT m.measurement_id::text
                FROM user_measurements m
                JOIN sessions s ON s.session_id = m.session_id
                WHERE s.store_id = :store_id
                """
            ),
            {"store_id": store_id},
        )
        measurements = {row[0] for row in measurement_rows}

        tryon_rows = conn.execute(
            text(
                """
                SELECT t.try_on_id::text,
                       t.parent_try_on_id::text,
                       t.studio_background_id::text
                FROM try_ons t
                JOIN products p ON p.product_id = t.product_id
                WHERE p.store_id = :store_id
                """
            ),
            {"store_id": store_id},
        )
        for try_on_id, parent_try_on_id, studio_background_id in tryon_rows:
            if try_on_id:
                tryons.add(try_on_id)
            if parent_try_on_id and studio_background_id:
                studio_keys.add(f"studio:{parent_try_on_id}:{studio_background_id}")

    return sessions, measurements, tryons, studio_keys


def main() -> None:
    parser = argparse.ArgumentParser(description="Clear Redis customer-flow cache for one store.")
    parser.add_argument("--store-id", default=DEFAULT_STORE_ID, help="Target store_id UUID")
    parser.add_argument("--dry-run", action="store_true", help="Print keys but do not delete")
    args = parser.parse_args()

    redis_url = os.getenv("REDIS_URL")
    database_url = os.getenv("DATABASE_URL")
    if (not redis_url or not database_url) and get_settings is not None:
        try:
            settings = get_settings()
            redis_url = redis_url or settings.REDIS_URL
            database_url = database_url or settings.DATABASE_URL
        except Exception:
            pass
    if not redis_url:
        raise SystemExit("REDIS_URL is missing in environment.")
    if not database_url:
        raise SystemExit("DATABASE_URL is missing in environment.")

    sessions, measurements, tryons, studio_keys = fetch_ids(database_url, args.store_id)

    keys: Set[str] = set()

    # Store-scoped pointer keys.
    r = redis.Redis.from_url(redis_url, decode_responses=False)
    user_patterns = [
        f"user:{args.store_id}:*:measurement",
        f"user:{args.store_id}:*:product:*:latest_tryon",
    ]
    for pattern in user_patterns:
        for key in r.scan_iter(match=pattern, count=500):
            keys.add(key.decode("utf-8") if isinstance(key, bytes) else str(key))

    # Session/measurement image caches.
    for sid in sessions:
        keys.add(f"img:session:{sid}:front")
        keys.add(f"img:session:{sid}:side")
    for mid in measurements:
        keys.add(f"img:measurement:{mid}:front")
        keys.add(f"img:measurement:{mid}:side")

    # Try-on and studio caches.
    for tid in tryons:
        keys.add(f"tryon:{tid}")
    keys.update(studio_keys)

    sorted_keys = sorted(keys)
    print(f"store_id={args.store_id}")
    print(f"sessions={len(sessions)} measurements={len(measurements)} try_ons={len(tryons)}")
    print(f"redis_keys_targeted={len(sorted_keys)}")

    if args.dry_run:
        for key in sorted_keys:
            print(key)
        print("dry-run complete (no keys deleted).")
        return

    deleted_total = 0
    for batch in chunked(sorted_keys, 1000):
        deleted_total += r.delete(*batch) if batch else 0
    print(f"deleted={deleted_total}")


if __name__ == "__main__":
    main()
