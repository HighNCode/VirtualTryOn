"""
Persistent media archival service.

Customer flows remain Redis-first for reads; this service is write-only for
private archival storage in GCS.
"""

from __future__ import annotations

from functools import lru_cache
import logging
from typing import Optional, Tuple

from app.services.media_storage_service import get_media_storage_service

logger = logging.getLogger(__name__)


class MediaArchiveService:
    """Uploads media to private GCS for internal archival/audit usage."""

    def __init__(self) -> None:
        self._storage = get_media_storage_service()

    @property
    def enabled(self) -> bool:
        return self._storage.enabled

    def archive_customer_measurement_images(
        self,
        *,
        store_id: str,
        measurement_id: str,
        front_image_bytes: bytes,
        side_image_bytes: bytes,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Archive customer-uploaded front/side photos.

        Returns tuple of object paths (front_path, side_path). None means skipped/failed.
        """
        if not self.enabled:
            return None, None

        front_path = self._storage.build_object_path(
            relative_dir=f"stores/{store_id}/measurements/{measurement_id}/front",
            payload=front_image_bytes,
            stem="front",
        )
        side_path = self._storage.build_object_path(
            relative_dir=f"stores/{store_id}/measurements/{measurement_id}/side",
            payload=side_image_bytes,
            stem="side",
        )

        metadata = {
            "flow": "customer",
            "visibility": "archival_only_after_cache_expiry",
            "type": "measurement_upload",
        }
        uploaded_front = self._storage.upload_bytes(
            object_path=front_path,
            payload=front_image_bytes,
            metadata=metadata,
        )
        uploaded_side = self._storage.upload_bytes(
            object_path=side_path,
            payload=side_image_bytes,
            metadata=metadata,
        )
        return uploaded_front, uploaded_side

    def archive_customer_tryon_result(
        self,
        *,
        store_id: str,
        try_on_id: str,
        result_bytes: bytes,
        flow_variant: str,
    ) -> Optional[str]:
        """
        Archive generated customer try-on/studio output.

        `flow_variant` is a short label such as "generate" or "studio".
        """
        if not self.enabled:
            return None

        object_path = self._storage.build_object_path(
            relative_dir=f"stores/{store_id}/tryons/{try_on_id}/output",
            payload=result_bytes,
            stem=str(flow_variant or "output"),
        )
        return self._storage.upload_bytes(
            object_path=object_path,
            payload=result_bytes,
            metadata={
                "flow": "customer",
                "visibility": "archival_only_after_cache_expiry",
                "type": "tryon_output",
                "variant": str(flow_variant or "output"),
            },
        )

    def generate_signed_get_url(self, object_path: str) -> Optional[str]:
        """
        Generate a signed GET URL.

        This is available for internal or merchant use. Customer flow guardrails
        are enforced in API handlers by not using this for customer cache misses.
        """
        return self._storage.generate_signed_get_url(object_path)


@lru_cache(maxsize=1)
def get_media_archive_service() -> MediaArchiveService:
    return MediaArchiveService()
