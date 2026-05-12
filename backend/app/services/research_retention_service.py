"""
Consented research retention service.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Optional
import uuid

from sqlalchemy.orm import Session as DBSession

from app.config import get_settings
from app.models.database import ConsentedResearchDataset
from app.services.media_storage_service import get_media_storage_service

logger = logging.getLogger(__name__)
settings = get_settings()


class ResearchRetentionService:
    def __init__(self, db: DBSession):
        self.db = db
        self.storage = get_media_storage_service()

    def archive_consented_measurement_data(
        self,
        *,
        store_id: str | uuid.UUID,
        session_id: str | uuid.UUID,
        measurement_id: str | uuid.UUID,
        front_image_bytes: bytes,
        side_image_bytes: bytes,
        measurements: dict,
        height_cm: Optional[float],
        weight_kg: Optional[float],
        gender: Optional[str],
        consent_policy_version: str,
        consent_source: str,
        consent_granted_at: Optional[datetime] = None,
    ) -> Optional[ConsentedResearchDataset]:
        if not self.storage.enabled:
            logger.warning(
                "Skipping consented research archival for measurement=%s because media storage is disabled.",
                measurement_id,
            )
            return None

        store_uuid = uuid.UUID(str(store_id))
        session_uuid = uuid.UUID(str(session_id))
        measurement_uuid = uuid.UUID(str(measurement_id))

        granted_at = consent_granted_at or datetime.utcnow()
        expires_at = granted_at + timedelta(days=max(1, int(settings.RESEARCH_RETENTION_DAYS or 365)))

        front_path = self.storage.build_object_path(
            relative_dir=f"research/consented/measurements/{measurement_uuid}/front",
            payload=front_image_bytes,
            stem="front",
        )
        side_path = self.storage.build_object_path(
            relative_dir=f"research/consented/measurements/{measurement_uuid}/side",
            payload=side_image_bytes,
            stem="side",
        )

        metadata = {
            "dataset": "consented_research",
            "consent_policy_version": str(consent_policy_version),
            "consent_source": str(consent_source),
            "measurement_id": str(measurement_uuid),
        }
        uploaded_front = self.storage.upload_bytes(
            object_path=front_path,
            payload=front_image_bytes,
            metadata=metadata,
        )
        uploaded_side = self.storage.upload_bytes(
            object_path=side_path,
            payload=side_image_bytes,
            metadata=metadata,
        )
        if not uploaded_front or not uploaded_side:
            logger.warning(
                "Skipping consented research DB write for measurement=%s due to storage upload failure.",
                measurement_uuid,
            )
            return None

        record = ConsentedResearchDataset(
            source_store_id=store_uuid,
            source_session_id=session_uuid,
            source_measurement_id=measurement_uuid,
            consent_granted_at=granted_at,
            consent_policy_version=str(consent_policy_version),
            consent_source=str(consent_source),
            front_image_object_path=uploaded_front,
            side_image_object_path=uploaded_side,
            measurements=measurements or {},
            height_cm=height_cm,
            weight_kg=weight_kg,
            gender=gender,
            expires_at=expires_at,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def purge_expired_records(self, *, now_utc: Optional[datetime] = None, limit: int = 250) -> int:
        now_utc = now_utc or datetime.utcnow()
        expired = (
            self.db.query(ConsentedResearchDataset)
            .filter(ConsentedResearchDataset.expires_at <= now_utc)
            .order_by(ConsentedResearchDataset.expires_at.asc())
            .limit(max(1, int(limit)))
            .all()
        )

        deleted = 0
        for row in expired:
            if row.front_image_object_path:
                self.storage.delete_object(row.front_image_object_path)
            if row.side_image_object_path:
                self.storage.delete_object(row.side_image_object_path)
            self.db.delete(row)
            deleted += 1

        if deleted:
            self.db.commit()
            logger.info("Purged %s expired consented research dataset records.", deleted)
        return deleted
