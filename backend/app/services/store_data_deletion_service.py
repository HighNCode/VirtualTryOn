"""
Hard-delete service for store-scoped uninstall/redaction cleanup.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Iterable
import uuid

from sqlalchemy.orm import Session as DBSession

from app.core.redis import get_redis
from app.models.database import DataDeletionQueue, PhotoshootJob, Product, Session, Store, TryOn, UserMeasurement
from app.services.media_storage_service import get_media_storage_service

logger = logging.getLogger(__name__)


class StoreDataDeletionService:
    def __init__(self, db: DBSession):
        self.db = db
        self.storage = get_media_storage_service()
        self.redis = get_redis()

    def hard_delete_store(self, *, store: Store, reason: str) -> dict:
        store_id = store.store_id
        store_id_str = str(store_id)

        runtime_ids = self._collect_runtime_ids(store_id=store_id)
        object_paths = self._collect_object_paths(store_id=store_id)

        redis_deleted = self._purge_store_redis_keys(
            store_id=store_id_str,
            session_ids=runtime_ids["session_ids"],
            measurement_ids=runtime_ids["measurement_ids"],
            try_on_ids=runtime_ids["try_on_ids"],
            photoshoot_job_ids=runtime_ids["photoshoot_job_ids"],
        )
        gcs_deleted = self._purge_store_gcs_objects(store_id=store_id_str, object_paths=object_paths)

        now = datetime.utcnow()
        pending_tasks = (
            self.db.query(DataDeletionQueue)
            .filter(DataDeletionQueue.store_id == store_id)
            .filter(DataDeletionQueue.status == "pending")
            .all()
        )
        for task in pending_tasks:
            task.status = "completed"
            task.executed_at = now

        self.db.delete(store)
        self.db.commit()

        logger.info(
            "Hard-deleted store=%s reason=%s redis_deleted=%s gcs_deleted=%s",
            store_id_str,
            reason,
            redis_deleted,
            gcs_deleted,
        )
        return {
            "store_id": store_id_str,
            "reason": reason,
            "redis_deleted": redis_deleted,
            "gcs_deleted": gcs_deleted,
            "pending_tasks_marked_completed": len(pending_tasks),
        }

    def hard_delete_by_store_id(self, *, store_id: str | uuid.UUID, reason: str) -> dict | None:
        store_uuid = uuid.UUID(str(store_id))
        store = self.db.query(Store).filter_by(store_id=store_uuid).first()
        if not store:
            return None
        return self.hard_delete_store(store=store, reason=reason)

    def _collect_runtime_ids(self, *, store_id: uuid.UUID) -> dict[str, set[str]]:
        session_ids = {
            str(row[0])
            for row in self.db.query(Session.session_id).filter(Session.store_id == store_id).all()
            if row[0]
        }
        measurement_ids = {
            str(row[0])
            for row in (
                self.db.query(UserMeasurement.measurement_id)
                .join(Session, UserMeasurement.session_id == Session.session_id)
                .filter(Session.store_id == store_id)
                .all()
            )
            if row[0]
        }
        try_on_ids = {
            str(row[0])
            for row in (
                self.db.query(TryOn.try_on_id)
                .join(Product, TryOn.product_id == Product.product_id)
                .filter(Product.store_id == store_id)
                .all()
            )
            if row[0]
        }
        photoshoot_job_ids = {
            str(row[0])
            for row in self.db.query(PhotoshootJob.job_id).filter(PhotoshootJob.store_id == store_id).all()
            if row[0]
        }
        return {
            "session_ids": session_ids,
            "measurement_ids": measurement_ids,
            "try_on_ids": try_on_ids,
            "photoshoot_job_ids": photoshoot_job_ids,
        }

    def _collect_object_paths(self, *, store_id: uuid.UUID) -> set[str]:
        object_paths: set[str] = set()

        measurement_rows = (
            self.db.query(UserMeasurement.front_image_object_path, UserMeasurement.side_image_object_path)
            .join(Session, UserMeasurement.session_id == Session.session_id)
            .filter(Session.store_id == store_id)
            .all()
        )
        for front_path, side_path in measurement_rows:
            if front_path:
                object_paths.add(front_path)
            if side_path:
                object_paths.add(side_path)

        tryon_rows = (
            self.db.query(TryOn.result_object_path)
            .join(Product, TryOn.product_id == Product.product_id)
            .filter(Product.store_id == store_id)
            .all()
        )
        for (result_path,) in tryon_rows:
            if result_path:
                object_paths.add(result_path)

        photoshoot_rows = (
            self.db.query(
                PhotoshootJob.input1_object_path,
                PhotoshootJob.input2_object_path,
                PhotoshootJob.output_object_path,
            )
            .filter(PhotoshootJob.store_id == store_id)
            .all()
        )
        for input1_path, input2_path, output_path in photoshoot_rows:
            if input1_path:
                object_paths.add(input1_path)
            if input2_path:
                object_paths.add(input2_path)
            if output_path:
                object_paths.add(output_path)

        return object_paths

    def _purge_store_redis_keys(
        self,
        *,
        store_id: str,
        session_ids: set[str],
        measurement_ids: set[str],
        try_on_ids: set[str],
        photoshoot_job_ids: set[str],
    ) -> int:
        try:
            keys_to_delete: set[str] = set()
            for session_id in session_ids:
                keys_to_delete.add(f"img:session:{session_id}:front")
                keys_to_delete.add(f"img:session:{session_id}:side")
            for measurement_id in measurement_ids:
                keys_to_delete.add(f"img:measurement:{measurement_id}:front")
                keys_to_delete.add(f"img:measurement:{measurement_id}:side")
            for try_on_id in try_on_ids:
                keys_to_delete.add(f"tryon:{try_on_id}")
            for job_id in photoshoot_job_ids:
                keys_to_delete.add(f"photoshoot:{job_id}")

            try_on_ids_lookup = set(try_on_ids)
            studio_keys = self.redis.keys("studio:*")
            for raw_key in studio_keys:
                key = raw_key.decode("utf-8") if isinstance(raw_key, bytes) else str(raw_key)
                parts = key.split(":")
                if len(parts) >= 3 and parts[1] in try_on_ids_lookup:
                    keys_to_delete.add(key)

            user_keys = self.redis.keys(f"user:{store_id}:*")
            for raw_key in user_keys:
                keys_to_delete.add(raw_key.decode("utf-8") if isinstance(raw_key, bytes) else str(raw_key))

            if not keys_to_delete:
                return 0

            deleted = 0
            batch: list[str] = []
            for key in keys_to_delete:
                batch.append(key)
                if len(batch) >= 250:
                    deleted += self.redis.delete(*batch)
                    batch = []
            if batch:
                deleted += self.redis.delete(*batch)
            return int(deleted)
        except Exception as exc:
            logger.warning("Failed to purge redis keys for store=%s: %s", store_id, exc)
            return 0

    def _purge_store_gcs_objects(self, *, store_id: str, object_paths: Iterable[str]) -> int:
        if not self.storage.enabled:
            return 0
        deleted = 0

        deleted += self.storage.delete_prefix(prefix=f"stores/{store_id}")

        for path in object_paths:
            if path and self.storage.delete_object(path):
                deleted += 1
        return deleted
