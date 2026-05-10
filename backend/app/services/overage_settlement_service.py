"""
Daily overage settlement service.

Aggregates uncharged overage usage events and posts a single Shopify usage charge
once per store per local day, with threshold carry-forward and billing-cycle flush.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
import logging
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from app.api.store_context import require_shopify_access_token
from app.config import get_settings
from app.models.database import Store, UsageEvent, UsageStoreCycle
from app.services.shopify_service import ShopifyService

logger = logging.getLogger(__name__)
settings = get_settings()


ACTIVE_SUBSCRIPTION_STATUSES = {"ACTIVE"}
OVERAGE_SETTLEMENT_LOCK_KEY = 83614297


class UsageOverageSettlementService:
    def __init__(self, db: DBSession):
        self.db = db
        self._lock_held = False
        self._settlement_local_time = self._parse_local_time(settings.OVERAGE_SETTLEMENT_LOCAL_TIME)

    async def run_due_settlements(self, *, now_utc: datetime | None = None) -> int:
        """
        Process stores whose local settlement time has passed and haven't been settled today.
        Returns count of stores successfully charged in this run.
        """
        if now_utc is None:
            now_utc = datetime.utcnow()

        if not self._try_acquire_advisory_lock():
            logger.info("Overage settlement skipped: advisory lock is already held by another worker.")
            return 0

        successful_charges = 0
        try:
            stores = self._list_candidate_stores()
            for store in stores:
                try:
                    charged = await self._settle_store_if_due(store=store, now_utc=now_utc)
                    if charged:
                        successful_charges += 1
                except Exception as exc:
                    self.db.rollback()
                    logger.error("Overage settlement failed for store=%s: %s", store.store_id, exc, exc_info=True)
            return successful_charges
        finally:
            self._release_advisory_lock()

    async def _settle_store_if_due(self, *, store: Store, now_utc: datetime) -> bool:
        now_local, local_date = self._to_store_local(store=store, now_utc=now_utc)
        if not self._is_due_for_daily_settlement(store=store, now_local=now_local):
            return False

        events = self._fetch_pending_overage_events(store=store)
        pending_amount = self._sum_pending_amount(events)
        pending_credits = sum(int(event.overage_credits or 0) for event in events)
        cycle_ending = self._is_cycle_ending(store=store, now_utc=now_utc)
        threshold = max(Decimal("0"), Decimal(str(settings.OVERAGE_DAILY_THRESHOLD_USD)))
        should_charge = pending_amount > 0 and (pending_amount >= threshold or cycle_ending)

        if not should_charge:
            self._mark_store_settled(store=store, local_date=local_date, now_utc=now_utc)
            self.db.commit()
            return False

        try:
            svc = ShopifyService(store.shopify_domain, require_shopify_access_token(store))
            description = self._build_charge_description(
                local_date=local_date,
                pending_credits=pending_credits,
                event_count=len(events),
            )
            result = await svc.billing_create_usage_charge(
                usage_line_item_id=store.usage_line_item_id,
                amount_usd=float(pending_amount),
                description=description,
            )
            usage_record_id = str(result.get("usage_record_id") or "").strip()
            if not usage_record_id:
                raise RuntimeError("Shopify usage charge response did not include a usage_record_id.")

            for event in events:
                event.usage_charge_id = usage_record_id
                event.billing_error_code = None
                event.billing_error_message = None

            self._clear_cycle_block_flags(store=store, events=events)
            self._mark_store_settled(store=store, local_date=local_date, now_utc=now_utc)
            self.db.commit()
            logger.info(
                "Settled overage for store=%s amount=%s events=%s usage_record_id=%s",
                store.store_id,
                str(pending_amount),
                len(events),
                usage_record_id,
            )
            return True
        except Exception as exc:
            error_text = str(exc)
            reason, message = self._derive_block_reason(error_text)
            for event in events:
                event.billing_error_code = reason
                event.billing_error_message = error_text[:1000]
            self._block_cycle_overage(store=store, events=events, reason=reason, message=message)
            self._mark_store_settled(store=store, local_date=local_date, now_utc=now_utc)
            self.db.commit()
            logger.error(
                "Failed overage settlement for store=%s reason=%s error=%s",
                store.store_id,
                reason,
                error_text,
            )
            return False

    def _list_candidate_stores(self) -> list[Store]:
        return (
            self.db.query(Store)
            .filter(Store.plan_shopify_subscription_id.isnot(None))
            .filter(Store.has_usage_billing.is_(True))
            .filter(Store.usage_line_item_id.isnot(None))
            .filter(Store.subscription_status.in_(ACTIVE_SUBSCRIPTION_STATUSES))
            .all()
        )

    def _fetch_pending_overage_events(self, *, store: Store) -> list[UsageEvent]:
        return (
            self.db.query(UsageEvent)
            .filter(UsageEvent.store_id == store.store_id)
            .filter(UsageEvent.status == "consumed")
            .filter(UsageEvent.usage_charge_id.is_(None))
            .filter(UsageEvent.overage_amount_usd > 0)
            .order_by(UsageEvent.created_at.asc())
            .all()
        )

    def _sum_pending_amount(self, events: Iterable[UsageEvent]) -> Decimal:
        total = Decimal("0")
        for event in events:
            total += Decimal(str(event.overage_amount_usd or 0))
        return total.quantize(Decimal("0.0001"))

    def _is_due_for_daily_settlement(self, *, store: Store, now_local: datetime) -> bool:
        if now_local.time() < self._settlement_local_time:
            return False

        today = now_local.date()
        last_settled = store.last_overage_settlement_local_date
        if last_settled is not None and last_settled >= today:
            return False
        return True

    def _is_cycle_ending(self, *, store: Store, now_utc: datetime) -> bool:
        if not store.billing_cycle_end_at:
            return False
        cycle_end_utc = self._as_utc_aware(store.billing_cycle_end_at)
        now_utc_aware = self._as_utc_aware(now_utc)
        return now_utc_aware >= cycle_end_utc

    def _mark_store_settled(self, *, store: Store, local_date: date, now_utc: datetime) -> None:
        store.last_overage_settlement_local_date = local_date
        store.last_overage_settlement_at = now_utc

    def _clear_cycle_block_flags(self, *, store: Store, events: Iterable[UsageEvent]) -> None:
        for cycle in self._load_cycles_for_events(store=store, events=events):
            cycle.overage_blocked = False
            cycle.overage_block_reason = None
            cycle.overage_block_message = None

    def _block_cycle_overage(
        self,
        *,
        store: Store,
        events: Iterable[UsageEvent],
        reason: str,
        message: str,
    ) -> None:
        for cycle in self._load_cycles_for_events(store=store, events=events):
            cycle.overage_blocked = True
            cycle.overage_block_reason = reason
            cycle.overage_block_message = message

    def _load_cycles_for_events(self, *, store: Store, events: Iterable[UsageEvent]) -> list[UsageStoreCycle]:
        cycle_keys = {
            (event.cycle_start_at, event.cycle_end_at)
            for event in events
            if event.cycle_start_at and event.cycle_end_at
        }
        cycles: list[UsageStoreCycle] = []
        for cycle_start_at, cycle_end_at in cycle_keys:
            cycle = (
                self.db.query(UsageStoreCycle)
                .filter_by(
                    store_id=store.store_id,
                    cycle_start_at=cycle_start_at,
                    cycle_end_at=cycle_end_at,
                )
                .with_for_update()
                .first()
            )
            if cycle:
                cycles.append(cycle)
        return cycles

    def _build_charge_description(self, *, local_date: date, pending_credits: int, event_count: int) -> str:
        return (
            f"Optimo daily overage settlement for {local_date.isoformat()} "
            f"({pending_credits} credits across {event_count} generations)"
        )

    def _derive_block_reason(self, error_text: str) -> tuple[str, str]:
        lowered = error_text.lower()
        if "capped" in lowered or "cap" in lowered:
            return (
                "usage_cap_reached",
                "Usage billing cap reached. Increase cap to continue overage usage.",
            )
        return (
            "usage_charge_failed",
            "Unable to post overage charge. Overage is temporarily blocked.",
        )

    def _to_store_local(self, *, store: Store, now_utc: datetime) -> tuple[datetime, date]:
        tz = self._resolve_timezone(store.store_timezone)
        local_now = self._as_utc_aware(now_utc).astimezone(tz)
        return local_now, local_now.date()

    def _resolve_timezone(self, store_timezone: str | None):
        tz_name = (store_timezone or "UTC").strip() or "UTC"
        try:
            return ZoneInfo(tz_name)
        except Exception:
            return timezone.utc

    def _as_utc_aware(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _parse_local_time(self, raw_value: str | None) -> time:
        value = (raw_value or "").strip()
        if not value:
            return time(hour=23, minute=55)
        try:
            parsed = datetime.strptime(value, "%H:%M")
            return time(hour=parsed.hour, minute=parsed.minute)
        except ValueError:
            logger.warning("Invalid OVERAGE_SETTLEMENT_LOCAL_TIME=%s. Falling back to 23:55.", value)
            return time(hour=23, minute=55)

    def _try_acquire_advisory_lock(self) -> bool:
        try:
            locked = self.db.execute(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": OVERAGE_SETTLEMENT_LOCK_KEY},
            ).scalar()
            self._lock_held = bool(locked)
            return self._lock_held
        except Exception:
            # Non-Postgres test environments won't support advisory locks.
            self.db.rollback()
            self._lock_held = True
            return True

    def _release_advisory_lock(self) -> None:
        if not self._lock_held:
            return
        try:
            self.db.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": OVERAGE_SETTLEMENT_LOCK_KEY},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self._lock_held = False
