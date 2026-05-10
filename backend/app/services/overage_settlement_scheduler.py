"""
In-process scheduler for daily overage settlement.
"""

from __future__ import annotations

import logging

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
except Exception:  # pragma: no cover - defensive fallback for partial envs.
    AsyncIOScheduler = None  # type: ignore[assignment]

from app.config import get_settings
from app.core.database import SessionLocal
from app.services.overage_settlement_service import UsageOverageSettlementService

logger = logging.getLogger(__name__)
settings = get_settings()

_scheduler: AsyncIOScheduler | None = None


async def _run_settlement_job() -> None:
    db = SessionLocal()
    try:
        svc = UsageOverageSettlementService(db)
        charged_count = await svc.run_due_settlements()
        logger.info("Overage settlement job completed. charged_count=%s", charged_count)
    except Exception as exc:
        logger.error("Overage settlement job failed: %s", exc, exc_info=True)
    finally:
        db.close()


def start_overage_settlement_scheduler() -> None:
    global _scheduler

    if not settings.OVERAGE_SETTLEMENT_ENABLED:
        logger.info("Overage settlement scheduler is disabled via OVERAGE_SETTLEMENT_ENABLED=false.")
        return
    if AsyncIOScheduler is None:
        logger.error("APScheduler is not installed. Overage settlement scheduler cannot be started.")
        return
    if _scheduler and _scheduler.running:
        return

    interval_minutes = max(int(settings.OVERAGE_SETTLEMENT_INTERVAL_MINUTES or 1), 1)
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _run_settlement_job,
        trigger="interval",
        minutes=interval_minutes,
        id="overage-settlement",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Started overage settlement scheduler: interval=%s minutes local_settlement_time=%s",
        interval_minutes,
        settings.OVERAGE_SETTLEMENT_LOCAL_TIME,
    )


def stop_overage_settlement_scheduler() -> None:
    global _scheduler

    if not _scheduler:
        return
    try:
        if _scheduler.running:
            _scheduler.shutdown(wait=False)
    finally:
        _scheduler = None
