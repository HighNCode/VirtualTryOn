"""
Smoke test a Redis-compatible service using REDIS_URL.

Usage:
    python scripts/verify_redis_connection.py --redis-url "%REDIS_URL%"

The script creates one short-lived key, verifies it, and deletes it. It does
not read or modify application cache keys.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from typing import Iterable, Optional
from urllib.parse import urlsplit, urlunsplit

import redis


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    if "@" not in parts.netloc:
        return url
    credentials, host = parts.netloc.rsplit("@", 1)
    username = credentials.split(":", 1)[0]
    return urlunsplit((parts.scheme, f"{username}:***@{host}", parts.path, "", ""))


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Redis connectivity with PING, SETEX, GET, TTL, and DEL."
    )
    parser.add_argument("--redis-url", required=True, help="Redis URL to verify")
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    key = f"migration:smoke:{secrets.token_hex(8)}"
    expected = b"ok"

    print(f"Redis: {redact_url(args.redis_url)}")
    client = redis.Redis.from_url(args.redis_url, decode_responses=False)

    try:
        pong = client.ping()
        print(f"PING: {'OK' if pong else 'FAILED'}")

        if not client.setex(key, 60, expected):
            print("SETEX: FAILED")
            return 1
        print("SETEX: OK")

        value = client.get(key)
        if value != expected:
            print("GET: FAILED")
            return 1
        print("GET: OK")

        ttl = client.ttl(key)
        if ttl <= 0:
            print(f"TTL: FAILED ({ttl})")
            return 1
        print(f"TTL: OK ({ttl}s)")

        deleted = client.delete(key)
        if deleted != 1:
            print(f"DEL: FAILED ({deleted})")
            return 1
        print("DEL: OK")

        print("\nRedis verification passed.")
        return 0
    finally:
        try:
            client.delete(key)
        finally:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
