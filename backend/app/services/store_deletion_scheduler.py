"""
In-process scheduler for uninstall fallback deletion and research retention purge.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.core.database import SessionLocal
from app.services.store_deletion_service import StoreDeletionService

logger = logging.getLogger(__name__)
settings = get_settings()

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
except Exception:  # pragma: no cover
    AsyncIOScheduler = None

_scheduler: AsyncIOScheduler | None = None


async def _run_store_deletion_job() -> None:
    db = SessionLocal()
    try:
        deleted_count = StoreDeletionService(db).run_due_uninstall_deletions()
        if deleted_count:
            logger.info("Store deletion scheduler removed %s store(s).", deleted_count)
    except Exception as exc:
        logger.error("Store deletion scheduler job failed: %s", exc, exc_info=True)
    finally:
        db.close()


async def _run_research_purge_job() -> None:
    db = SessionLocal()
    try:
        purged_count = StoreDeletionService(db).run_due_research_purge()
        if purged_count:
            logger.info("Research purge scheduler removed %s expired record(s).", purged_count)
    except Exception as exc:
        logger.error("Research purge scheduler job failed: %s", exc, exc_info=True)
    finally:
        db.close()


def start_store_deletion_scheduler() -> None:
    global _scheduler

    if not settings.STORE_DELETION_SCHEDULER_ENABLED:
        logger.info("Store deletion scheduler is disabled via STORE_DELETION_SCHEDULER_ENABLED=false.")
        return
    if AsyncIOScheduler is None:
        logger.error("APScheduler is not installed. Store deletion scheduler cannot be started.")
        return
    if _scheduler and _scheduler.running:
        return

    interval_minutes = max(1, int(settings.STORE_DELETION_SCHEDULER_INTERVAL_MINUTES or 15))
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _run_store_deletion_job,
        "interval",
        minutes=interval_minutes,
        id="store-deletion-fallback",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        _run_research_purge_job,
        "interval",
        minutes=interval_minutes,
        id="research-retention-purge",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("Started store deletion scheduler with interval=%s minute(s).", interval_minutes)


def stop_store_deletion_scheduler() -> None:
    global _scheduler
    if not _scheduler:
        return
    try:
        if _scheduler.running:
            _scheduler.shutdown(wait=False)
    finally:
        _scheduler = None
