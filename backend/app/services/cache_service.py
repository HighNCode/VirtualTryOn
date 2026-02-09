"""
Cache Service for Redis
Handles temporary storage of images and results with 24h TTL
"""

from io import BytesIO
from PIL import Image
import logging
from typing import Optional
from datetime import datetime, timedelta

from app.core.redis import get_redis
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class CacheService:
    """Service for managing temporary image cache in Redis"""

    def __init__(self):
        self.redis = get_redis()
        self.ttl = settings.IMAGE_CACHE_TTL  # 24 hours

    async def store_image(
        self,
        session_id: str,
        image_type: str,
        image_data: bytes
    ) -> str:
        """
        Store image in Redis with 24h TTL

        Args:
            session_id: Session UUID
            image_type: 'front' or 'side'
            image_data: Raw image bytes

        Returns:
            Cache key
        """
        cache_key = f"img:session:{session_id}:{image_type}"

        # Compress image before storing
        compressed = self._compress_image(image_data)

        # Store in Redis with TTL
        success = self.redis.set(cache_key, compressed, self.ttl)

        if success:
            logger.info(f"Image stored in cache: {cache_key}")
        else:
            logger.error(f"Failed to store image in cache: {cache_key}")

        return cache_key

    async def get_image(
        self,
        session_id: str,
        image_type: str
    ) -> Optional[bytes]:
        """
        Retrieve image from Redis

        Args:
            session_id: Session UUID
            image_type: 'front' or 'side'

        Returns:
            Image bytes or None if not found
        """
        cache_key = f"img:session:{session_id}:{image_type}"
        compressed = self.redis.get(cache_key)

        if not compressed:
            logger.warning(f"Image not found in cache: {cache_key}")
            return None

        # Decompress image
        return self._decompress_image(compressed)

    async def store_measurement_image(
        self,
        measurement_id: str,
        image_type: str,
        image_data: bytes
    ) -> str:
        """
        Store image linked to measurement (for reuse across sessions)

        Args:
            measurement_id: Measurement UUID
            image_type: 'front' or 'side'
            image_data: Raw image bytes

        Returns:
            Cache key
        """
        cache_key = f"img:measurement:{measurement_id}:{image_type}"

        compressed = self._compress_image(image_data)
        success = self.redis.set(cache_key, compressed, self.ttl)

        if success:
            logger.info(f"Measurement image stored: {cache_key}")

        return cache_key

    async def get_measurement_image(
        self,
        measurement_id: str,
        image_type: str
    ) -> Optional[bytes]:
        """Retrieve measurement image from cache"""
        cache_key = f"img:measurement:{measurement_id}:{image_type}"
        compressed = self.redis.get(cache_key)

        if not compressed:
            return None

        return self._decompress_image(compressed)

    async def store_tryon_result(
        self,
        try_on_id: str,
        result_image: bytes
    ) -> str:
        """
        Store try-on result image

        Args:
            try_on_id: Try-on UUID
            result_image: Generated image bytes

        Returns:
            Cache key
        """
        cache_key = f"tryon:{try_on_id}"

        compressed = self._compress_image(result_image)
        success = self.redis.set(cache_key, compressed, self.ttl)

        if success:
            logger.info(f"Try-on result stored: {cache_key}")

        return cache_key

    async def get_tryon_result(self, try_on_id: str) -> Optional[bytes]:
        """Retrieve try-on result from cache"""
        cache_key = f"tryon:{try_on_id}"
        compressed = self.redis.get(cache_key)

        if not compressed:
            return None

        return self._decompress_image(compressed)

    async def cleanup_session(self, session_id: str):
        """
        Delete all cached data for a session

        Args:
            session_id: Session UUID
        """
        keys_to_delete = [
            f"img:session:{session_id}:front",
            f"img:session:{session_id}:side"
        ]

        deleted = self.redis.delete(*keys_to_delete)
        logger.info(f"Cleaned up {deleted} cache entries for session {session_id}")

    async def image_exists(self, session_id: str, image_type: str) -> bool:
        """Check if image exists in cache"""
        cache_key = f"img:session:{session_id}:{image_type}"
        return self.redis.exists(cache_key)

    async def get_cache_expiry(self, session_id: str) -> Optional[datetime]:
        """
        Get cache expiry time for session

        Returns:
            Expiry datetime or None
        """
        cache_key = f"img:session:{session_id}:front"

        # Check TTL (time to live) in seconds
        ttl_seconds = self.redis.client.ttl(cache_key)

        if ttl_seconds > 0:
            return datetime.utcnow() + timedelta(seconds=ttl_seconds)

        return None

    def _compress_image(self, image_data: bytes) -> bytes:
        """
        Compress image to reduce Redis memory usage

        - Resize to max 1024px on longest side
        - Convert to JPEG with quality 85
        - Optimize for storage

        Args:
            image_data: Original image bytes

        Returns:
            Compressed image bytes
        """
        try:
            img = Image.open(BytesIO(image_data))

            # Resize if too large (max 1024px on longest side)
            max_size = 1024
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.LANCZOS)

            # Convert to RGB if necessary
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            # Save as JPEG with compression
            output = BytesIO()
            img.save(output, format='JPEG', quality=85, optimize=True)

            compressed_data = output.getvalue()

            # Log compression ratio
            original_size = len(image_data)
            compressed_size = len(compressed_data)
            ratio = (1 - compressed_size / original_size) * 100
            logger.debug(f"Image compressed: {original_size} → {compressed_size} bytes ({ratio:.1f}% reduction)")

            return compressed_data

        except Exception as e:
            logger.error(f"Image compression failed: {e}")
            # Return original if compression fails
            return image_data

    def _decompress_image(self, compressed_data: bytes) -> bytes:
        """
        Decompress image (actually just return as-is since JPEG is final format)

        Args:
            compressed_data: Compressed image bytes

        Returns:
            Image bytes
        """
        return compressed_data
