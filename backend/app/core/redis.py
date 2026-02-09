"""
Redis Connection and Caching Management
Handles temporary image storage and session caching
"""

import redis
from typing import Optional
import logging

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client wrapper with connection pooling"""

    def __init__(self):
        self.pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=False,  # Keep as bytes for image storage
        )
        self.client = redis.Redis(connection_pool=self.pool)

    def get_client(self) -> redis.Redis:
        """Get Redis client instance"""
        return self.client

    def ping(self) -> bool:
        """Check if Redis is connected"""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    def set(self, key: str, value: bytes, ttl: Optional[int] = None) -> bool:
        """
        Set a key-value pair in Redis

        Args:
            key: Redis key
            value: Value (bytes)
            ttl: Time-to-live in seconds (optional)
        """
        try:
            if ttl:
                return self.client.setex(key, ttl, value)
            else:
                return self.client.set(key, value)
        except Exception as e:
            logger.error(f"Redis SET failed for key {key}: {e}")
            return False

    def get(self, key: str) -> Optional[bytes]:
        """
        Get a value from Redis

        Args:
            key: Redis key

        Returns:
            Value as bytes or None if not found
        """
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Redis GET failed for key {key}: {e}")
            return None

    def delete(self, *keys: str) -> int:
        """
        Delete one or more keys

        Args:
            keys: Keys to delete

        Returns:
            Number of keys deleted
        """
        try:
            return self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis DELETE failed: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """Check if a key exists"""
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS failed for key {key}: {e}")
            return False

    def keys(self, pattern: str) -> list:
        """
        Find all keys matching a pattern

        Args:
            pattern: Pattern to match (e.g., "session:*")

        Returns:
            List of matching keys
        """
        try:
            return self.client.keys(pattern)
        except Exception as e:
            logger.error(f"Redis KEYS failed for pattern {pattern}: {e}")
            return []

    def close(self):
        """Close Redis connection pool"""
        self.pool.disconnect()


# Singleton instance
_redis_client: Optional[RedisClient] = None


def get_redis() -> RedisClient:
    """Get Redis client instance (singleton)"""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def check_redis_connection() -> bool:
    """
    Check if Redis connection is working
    Returns True if connected, False otherwise
    """
    try:
        redis_client = get_redis()
        return redis_client.ping()
    except Exception as e:
        logger.error(f"Redis connection check failed: {e}")
        return False
