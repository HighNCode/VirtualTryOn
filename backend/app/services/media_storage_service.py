"""
Shared media storage abstraction.

Stores objects in private Google Cloud Storage and issues short-lived signed URLs
on demand. Signed URLs are never persisted to the database.
"""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
import logging
import os
import uuid
from typing import Dict, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

try:
    from google.cloud import storage as gcs_storage
except Exception:  # pragma: no cover - optional dependency in some envs
    gcs_storage = None


class MediaStorageService:
    """Backend upload + signed read service for durable media objects."""

    def __init__(self) -> None:
        self._backend = (settings.MEDIA_STORAGE_BACKEND or "gcs").strip().lower()
        self._bucket_name = (settings.GCS_BUCKET_NAME or "").strip()
        self._prefix = (settings.GCS_MEDIA_PREFIX or "v1").strip().strip("/")
        self._signed_ttl_seconds = max(60, int(settings.GCS_SIGNED_URL_TTL_SECONDS))

        self._disabled_reason: Optional[str] = None
        self._enabled = self._backend == "gcs" and bool(self._bucket_name)
        self._client = None
        self._bucket = None

        if not self._enabled:
            if self._backend != "gcs":
                self._disabled_reason = f"unsupported MEDIA_STORAGE_BACKEND={self._backend!r}"
            elif not self._bucket_name:
                self._disabled_reason = "GCS_BUCKET_NAME is missing"
            return
        if gcs_storage is None:
            logger.warning(
                "MEDIA_STORAGE_BACKEND=gcs but google-cloud-storage is unavailable. "
                "Durable media storage is disabled."
            )
            self._disabled_reason = "google-cloud-storage dependency is unavailable"
            self._enabled = False
            return
        try:
            credentials_path = (settings.GOOGLE_APPLICATION_CREDENTIALS or "").strip()
            if credentials_path:
                os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", credentials_path)
                if not os.path.isfile(credentials_path):
                    raise ValueError(
                        f"GOOGLE_APPLICATION_CREDENTIALS path does not exist: {credentials_path}"
                    )

            client_kwargs = {}
            if settings.GOOGLE_CLOUD_PROJECT:
                client_kwargs["project"] = settings.GOOGLE_CLOUD_PROJECT

            self._client = gcs_storage.Client(**client_kwargs)
            self._bucket = self._client.bucket(self._bucket_name)
        except Exception as exc:
            logger.warning("Failed to initialize GCS client for media storage: %s", exc)
            self._disabled_reason = str(exc)
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled and self._bucket is not None

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def disabled_reason(self) -> Optional[str]:
        if self.enabled:
            return None
        return self._disabled_reason or "unknown media storage configuration error"

    def upload_bytes(
        self,
        *,
        object_path: str,
        payload: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 120,
    ) -> Optional[str]:
        if not self.enabled:
            return None
        if not object_path or not payload:
            return None
        try:
            blob = self._bucket.blob(object_path)
            if metadata:
                blob.metadata = {str(k): str(v) for k, v in metadata.items()}
            blob.upload_from_string(
                payload,
                content_type=content_type or self.detect_content_type(payload),
                timeout=timeout_seconds,
            )
            return object_path
        except Exception as exc:
            logger.warning("Failed to upload object to GCS (%s): %s", object_path, exc)
            return None

    def download_bytes(self, object_path: str, *, timeout_seconds: int = 120) -> Optional[bytes]:
        if not self.enabled or not object_path:
            return None
        try:
            blob = self._bucket.blob(object_path)
            return blob.download_as_bytes(timeout=timeout_seconds)
        except Exception as exc:
            logger.warning("Failed to download object from GCS (%s): %s", object_path, exc)
            return None

    def delete_object(self, object_path: str, *, timeout_seconds: int = 120) -> bool:
        if not self.enabled or not object_path:
            return False
        try:
            blob = self._bucket.blob(object_path)
            blob.delete(timeout=timeout_seconds)
            return True
        except Exception as exc:
            logger.warning("Failed to delete object from GCS (%s): %s", object_path, exc)
            return False

    def generate_signed_get_url(
        self,
        object_path: str,
        *,
        ttl_seconds: Optional[int] = None,
    ) -> Optional[str]:
        if not self.enabled or not object_path:
            return None
        try:
            blob = self._bucket.blob(object_path)
            return blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=max(60, int(ttl_seconds or self._signed_ttl_seconds))),
                method="GET",
            )
        except Exception as exc:
            logger.warning("Failed to generate signed GET URL (%s): %s", object_path, exc)
            return None

    def generate_signed_put_url(
        self,
        object_path: str,
        *,
        ttl_seconds: Optional[int] = None,
        content_type: Optional[str] = None,
    ) -> Optional[str]:
        if not self.enabled or not object_path:
            return None
        try:
            blob = self._bucket.blob(object_path)
            return blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=max(60, int(ttl_seconds or self._signed_ttl_seconds))),
                method="PUT",
                content_type=content_type or "application/octet-stream",
            )
        except Exception as exc:
            logger.warning("Failed to generate signed PUT URL (%s): %s", object_path, exc)
            return None

    def prefixed_path(self, relative_path: str) -> str:
        normalized = "/".join(
            part.strip("/")
            for part in str(relative_path or "").split("/")
            if part and part.strip("/")
        )
        if self._prefix:
            return f"{self._prefix}/{normalized}" if normalized else self._prefix
        return normalized

    def list_object_paths(self, *, prefix: str, max_results: Optional[int] = None) -> list[str]:
        if not self.enabled:
            return []
        normalized_prefix = self.prefixed_path(prefix)
        if normalized_prefix and not normalized_prefix.endswith("/"):
            normalized_prefix = f"{normalized_prefix}/"
        try:
            iterator = self._client.list_blobs(
                self._bucket_name,
                prefix=normalized_prefix,
                max_results=max_results,
            )
            return [blob.name for blob in iterator]
        except Exception as exc:
            logger.warning("Failed to list objects in GCS prefix (%s): %s", normalized_prefix, exc)
            return []

    def delete_prefix(
        self,
        *,
        prefix: str,
        max_results: Optional[int] = None,
        timeout_seconds: int = 120,
    ) -> int:
        if not self.enabled:
            return 0
        deleted_count = 0
        for path in self.list_object_paths(prefix=prefix, max_results=max_results):
            if self.delete_object(path, timeout_seconds=timeout_seconds):
                deleted_count += 1
        return deleted_count

    def build_object_path(self, *, relative_dir: str, payload: bytes, stem: str = "asset") -> str:
        normalized_dir = "/".join(
            part.strip("/")
            for part in str(relative_dir or "").split("/")
            if part and part.strip("/")
        )
        ext = self.detect_extension(payload)
        suffix = uuid.uuid4().hex[:12]
        return f"{self.prefixed_path(normalized_dir)}/{stem}-{suffix}.{ext}"

    @staticmethod
    def detect_content_type(payload: bytes) -> str:
        if payload.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if payload.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if payload.startswith(b"GIF87a") or payload.startswith(b"GIF89a"):
            return "image/gif"
        if payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
            return "image/webp"
        return "application/octet-stream"

    @classmethod
    def detect_extension(cls, payload: bytes) -> str:
        return {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
            "image/webp": "webp",
        }.get(cls.detect_content_type(payload), "bin")


@lru_cache(maxsize=1)
def get_media_storage_service() -> MediaStorageService:
    return MediaStorageService()
