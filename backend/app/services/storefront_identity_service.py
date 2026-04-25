"""
Storefront identity resolution for anonymous teaser + logged-in customer flows.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session as DBSession

from app.config import get_settings
from app.core.redis import get_redis
from app.models.database import Store, StoreIdentityLink, UsageCustomerWeek

logger = logging.getLogger(__name__)
settings = get_settings()


class StorefrontIdentityService:
    def __init__(self, db: DBSession):
        self.db = db
        self.redis = get_redis()

    @staticmethod
    def normalize_customer_id(value: str | None) -> str | None:
        candidate = (value or "").strip()
        return candidate or None

    @staticmethod
    def normalize_anon_id(value: str | None) -> str | None:
        candidate = (value or "").strip().lower()
        if not candidate:
            return None
        if not all(ch.isalnum() or ch == "-" for ch in candidate):
            return None
        if len(candidate) < 20 or len(candidate) > 80:
            return None
        return candidate

    @staticmethod
    def customer_subject(customer_id: str) -> str:
        return f"shopify:{customer_id}"

    @staticmethod
    def anon_subject(anon_id: str) -> str:
        return f"anon:{anon_id}"

    @staticmethod
    def is_anon_subject(subject_identifier: str | None) -> bool:
        return bool(subject_identifier and subject_identifier.startswith("anon:"))

    def resolve_subject_identifier(
        self,
        *,
        store: Store,
        logged_in_customer_id: str | None,
        anon_id: str | None,
    ) -> str | None:
        customer_id = self.normalize_customer_id(logged_in_customer_id)
        anon_normalized = self.normalize_anon_id(anon_id)

        if customer_id:
            customer_subject = self.customer_subject(customer_id)
            if anon_normalized:
                anon_subject = self.anon_subject(anon_normalized)
                self._link_and_migrate_weekly_usage(
                    store=store,
                    anon_identifier=anon_normalized,
                    customer_identifier=customer_id,
                    anon_subject=anon_subject,
                    customer_subject=customer_subject,
                )
                self._copy_measurement_pointer_if_missing(
                    store=store,
                    anon_subject=anon_subject,
                    customer_subject=customer_subject,
                )
            return customer_subject

        if anon_normalized:
            return self.anon_subject(anon_normalized)

        return None

    def _link_and_migrate_weekly_usage(
        self,
        *,
        store: Store,
        anon_identifier: str,
        customer_identifier: str,
        anon_subject: str,
        customer_subject: str,
    ) -> None:
        week_start_utc, week_end_utc, _ = self._resolve_week_window(store, datetime.utcnow())

        link = (
            self.db.query(StoreIdentityLink)
            .filter_by(
                store_id=store.store_id,
                anon_identifier=anon_identifier,
                customer_identifier=customer_identifier,
            )
            .with_for_update()
            .first()
        )
        if link is None:
            link = StoreIdentityLink(
                store_id=store.store_id,
                anon_identifier=anon_identifier,
                customer_identifier=customer_identifier,
            )
            self.db.add(link)
            self.db.flush()

        if link.last_migrated_week_start_utc == week_start_utc:
            return

        anon_week = (
            self.db.query(UsageCustomerWeek)
            .filter_by(
                store_id=store.store_id,
                customer_identifier=anon_subject,
                week_start_utc=week_start_utc,
            )
            .with_for_update()
            .first()
        )
        if anon_week and anon_week.used_count > 0:
            customer_week = (
                self.db.query(UsageCustomerWeek)
                .filter_by(
                    store_id=store.store_id,
                    customer_identifier=customer_subject,
                    week_start_utc=week_start_utc,
                )
                .with_for_update()
                .first()
            )
            if customer_week is None:
                customer_week = UsageCustomerWeek(
                    store_id=store.store_id,
                    customer_identifier=customer_subject,
                    week_start_utc=week_start_utc,
                    week_end_utc=week_end_utc,
                    used_count=0,
                )
                self.db.add(customer_week)
                self.db.flush()

            customer_week.used_count += anon_week.used_count

        link.last_migrated_week_start_utc = week_start_utc

    def _copy_measurement_pointer_if_missing(
        self,
        *,
        store: Store,
        anon_subject: str,
        customer_subject: str,
    ) -> None:
        try:
            customer_key = f"user:{store.store_id}:{customer_subject}:measurement"
            if self.redis.get(customer_key):
                return

            anon_key = f"user:{store.store_id}:{anon_subject}:measurement"
            anon_pointer = self.redis.get(anon_key)
            if not anon_pointer:
                return

            ttl = self.redis.client.ttl(anon_key)
            pointer_ttl = ttl if ttl and ttl > 0 else settings.MEASUREMENT_CACHE_TTL_SECONDS
            self.redis.set(customer_key, anon_pointer, pointer_ttl)
        except Exception as exc:
            logger.warning("Failed to copy anon measurement pointer for store=%s: %s", store.store_id, exc)

    def _resolve_week_window(self, store: Store, now_utc: datetime) -> tuple[datetime, datetime, str]:
        tz_name = (store.store_timezone or "UTC").strip() or "UTC"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz_name = "UTC"
            tz = timezone.utc

        now_local = now_utc.replace(tzinfo=timezone.utc).astimezone(tz)
        week_start_local = (now_local - timedelta(days=now_local.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_end_local = week_start_local + timedelta(days=7)

        week_start_utc = week_start_local.astimezone(timezone.utc).replace(tzinfo=None)
        week_end_utc = week_end_local.astimezone(timezone.utc).replace(tzinfo=None)
        return week_start_utc, week_end_utc, tz_name
