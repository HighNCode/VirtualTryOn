"""
Redis-backed rate limiting helpers for storefront endpoints.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session as DBSession

from app.config import get_settings
from app.core.redis import get_redis
from app.models.database import Store

settings = get_settings()


def get_request_ip(request: Request) -> str:
    forwarded_for = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first

    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class StorefrontRateLimitService:
    def __init__(self, db: DBSession):
        self.db = db
        self.redis = get_redis()

    def enforce(
        self,
        *,
        request: Request,
        store: Store,
        endpoint_key: str,
        limit_per_minute: int,
    ) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        limit = max(int(limit_per_minute), 1)
        ip = get_request_ip(request)
        redis_key = f"ratelimit:{store.store_id}:{ip}:{endpoint_key}:60s"

        current = self.redis.client.incr(redis_key)
        if current == 1:
            self.redis.client.expire(redis_key, 60)

        if current > limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please wait and try again.",
                },
            )
