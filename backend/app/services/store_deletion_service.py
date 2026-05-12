"""
Scheduled uninstall fallback deletion and consented research purge.
"""

from __future__ import annotations

from datetime import datetime
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from app.models.database import DataDeletionQueue, Store
from app.services.research_retention_service import ResearchRetentionService
from app.services.store_data_deletion_service import StoreDataDeletionService

logger = logging.getLogger(__name__)

STORE_DELETION_LOCK_KEY = 83614531
RESEARCH_PURGE_LOCK_KEY = 83614532


class StoreDeletionService:
    def __init__(self, db: DBSession):
        self.db = db
        self._lock_held_key: int | None = None

    def run_due_uninstall_deletions(self, *, now_utc: datetime | None = None, limit: int = 100) -> int:
        now_utc = now_utc or datetime.utcnow()
        if not self._try_acquire_advisory_lock(STORE_DELETION_LOCK_KEY):
            logger.info("Store deletion job skipped: advisory lock already held.")
            return 0

        deleted_count = 0
        try:
            due_tasks = (
                self.db.query(DataDeletionQueue)
                .filter(DataDeletionQueue.status == "pending")
                .filter(DataDeletionQueue.scheduled_for <= now_utc)
                .order_by(DataDeletionQueue.scheduled_for.asc())
                .limit(max(1, int(limit)))
                .all()
            )
            for task in due_tasks:
                try:
                    store = self.db.query(Store).filter(Store.store_id == task.store_id).first()
                    if not store:
                        task.status = "completed"
                        task.executed_at = now_utc
                        self.db.commit()
                        continue

                    if store.installation_status == "active":
                        task.status = "cancelled"
                        task.executed_at = now_utc
                        self.db.commit()
                        continue

                    deletion_result = StoreDataDeletionService(self.db).hard_delete_store(
                        store=store,
                        reason="scheduled_uninstall_fallback",
                    )
                    if deletion_result:
                        deleted_count += 1
                except Exception as exc:
                    self.db.rollback()
                    logger.error("Failed scheduled deletion for store_id=%s: %s", task.store_id, exc, exc_info=True)
            return deleted_count
        finally:
            self._release_advisory_lock()

    def run_due_research_purge(self, *, now_utc: datetime | None = None, limit: int = 250) -> int:
        now_utc = now_utc or datetime.utcnow()
        if not self._try_acquire_advisory_lock(RESEARCH_PURGE_LOCK_KEY):
            logger.info("Research retention purge skipped: advisory lock already held.")
            return 0
        try:
            return ResearchRetentionService(self.db).purge_expired_records(now_utc=now_utc, limit=limit)
        finally:
            self._release_advisory_lock()

    def _try_acquire_advisory_lock(self, lock_key: int) -> bool:
        try:
            locked = self.db.execute(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": lock_key},
            ).scalar()
            if bool(locked):
                self._lock_held_key = lock_key
            return bool(locked)
        except Exception:
            # Test environments may not support pg advisory locks.
            self.db.rollback()
            self._lock_held_key = lock_key
            return True

    def _release_advisory_lock(self) -> None:
        if self._lock_held_key is None:
            return
        try:
            self.db.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": self._lock_held_key},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self._lock_held_key = None
