"""
Usage governance service
Enforces weekly customer limits and cycle-based credit accounting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session as DBSession

from app.api.store_context import require_shopify_access_token
from app.config import get_settings
from app.models.database import (
    Store,
    Plan,
    UsageEvent,
    UsageCustomerWeek,
    UsageStoreCycle,
)
from app.services.customer_login_policy import (
    customer_login_required_message,
)
from app.services.shopify_service import ShopifyService

logger = logging.getLogger(__name__)
settings = get_settings()


ACTIVE_SUBSCRIPTION_STATUSES = {"ACTIVE"}


@dataclass
class UsageReservation:
    event_id: str
    overage_credits: int
    overage_amount_usd: float


class UsageGovernanceService:
    def __init__(self, db: DBSession):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def reserve_generation(
        self,
        *,
        store: Store,
        action_type: str,
        reference_type: str,
        customer_identifier: str | None = None,
        enforce_weekly_limit: bool = False,
        weekly_tryon_limit: int | None = None,
        reference_id: str | None = None,
    ) -> UsageReservation:
        now = datetime.utcnow()

        await self._ensure_store_billing_synced(store)
        self._enforce_store_generation_allowed(store, now)

        plan = self._get_active_plan(store)
        cycle_start_at, cycle_end_at = self._resolve_cycle_window(store, now)
        included_credits = self._resolve_included_credits(store, now, plan)

        cycle = (
            self.db.query(UsageStoreCycle)
            .filter_by(store_id=store.store_id, cycle_start_at=cycle_start_at, cycle_end_at=cycle_end_at)
            .with_for_update()
            .first()
        )
        if cycle is None:
            cycle = UsageStoreCycle(
                store_id=store.store_id,
                cycle_start_at=cycle_start_at,
                cycle_end_at=cycle_end_at,
                included_credits=included_credits,
                consumed_credits=0,
                overage_credits=0,
                overage_amount_usd=0,
            )
            self.db.add(cycle)
            self.db.flush()
        else:
            cycle.included_credits = included_credits

        # If paid-plan trial credits are exhausted before trial ends, end trial entitlement
        # early and switch to full plan credits immediately (no hard lock).
        if self._should_transition_plan_trial_on_credit_exhaustion(
            store=store,
            cycle=cycle,
            included_credits=included_credits,
            now=now,
            plan=plan,
        ):
            included_credits = self._transition_plan_trial_to_full_plan(
                store=store,
                cycle=cycle,
                plan=plan,
                now=now,
            )

        # Intro/founding trial has no overage path; lock and require billing selection.
        if (
            store.trial_mode == "intro_free"
            and cycle.consumed_credits >= included_credits
        ):
            self._lock_intro_trial_for_credit_exhaustion(store=store, now=now)
            self.db.commit()
            self._raise_usage_error(
                status_code=402,
                code="TRIAL_CREDITS_EXHAUSTED",
                message="Trial ended. Select a plan to re-enable widget and customer try-ons.",
            )

        week_start_utc = None
        weekly_counter = None
        normalized_subject = (customer_identifier or "").strip()
        is_logged_in_subject = normalized_subject.startswith("shopify:")
        is_anonymous_subject = not is_logged_in_subject

        if enforce_weekly_limit and not normalized_subject:
            self._raise_usage_error(
                status_code=401,
                code="CUSTOMER_LOGIN_REQUIRED",
                message=customer_login_required_message(),
            )

        if enforce_weekly_limit:
            week_start_utc, week_end_utc, tz_name = self._resolve_week_window(store, now)
            effective_limit = (
                int(settings.ANON_WEEKLY_TRYON_LIMIT)
                if is_anonymous_subject
                else int(weekly_tryon_limit or settings.WEEKLY_TRYON_LIMIT_DEFAULT)
            )

            weekly_counter = (
                self.db.query(UsageCustomerWeek)
                .filter_by(
                    store_id=store.store_id,
                    customer_identifier=normalized_subject,
                    week_start_utc=week_start_utc,
                )
                .with_for_update()
                .first()
            )
            if weekly_counter is None:
                weekly_counter = UsageCustomerWeek(
                    store_id=store.store_id,
                    customer_identifier=normalized_subject,
                    week_start_utc=week_start_utc,
                    week_end_utc=week_end_utc,
                    used_count=0,
                )
                self.db.add(weekly_counter)
                self.db.flush()

            if weekly_counter.used_count + 1 > effective_limit:
                reset_at = week_end_utc.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
                if is_anonymous_subject:
                    self._raise_usage_error(
                        status_code=401,
                        code="CUSTOMER_LOGIN_REQUIRED",
                        message=customer_login_required_message(),
                        reset_at=reset_at,
                        timezone=tz_name,
                    )
                self._raise_usage_error(
                    status_code=429,
                    code="WEEKLY_LIMIT_REACHED",
                    message=(
                        "Weekly limit reached. Try-on resets next week. "
                        "Contact the store if you need additional attempts."
                    ),
                    reset_at=reset_at,
                    timezone=tz_name,
                )

        credits_to_reserve = settings.CREDITS_PER_GENERATION
        included_remaining = max(cycle.included_credits - cycle.consumed_credits, 0)
        included_reserved = min(credits_to_reserve, included_remaining)
        overage_reserved = credits_to_reserve - included_reserved
        overage_per_tryon = self._resolve_overage_usd_per_tryon(plan)
        credits_per_generation = max(int(settings.CREDITS_PER_GENERATION), 1)
        overage_amount = (
            (Decimal(str(overage_reserved)) / Decimal(str(credits_per_generation))) * overage_per_tryon
        ).quantize(Decimal("0.0001"))

        if overage_reserved > 0:
            self._enforce_overage_eligibility(store=store, cycle=cycle)

        # Reserve counters atomically so concurrent requests can't overbook included credits.
        cycle.consumed_credits += included_reserved
        cycle.overage_credits += overage_reserved
        cycle.overage_amount_usd = (Decimal(str(cycle.overage_amount_usd)) + overage_amount)

        if weekly_counter is not None:
            weekly_counter.used_count += 1

        event = UsageEvent(
            store_id=store.store_id,
            customer_identifier=normalized_subject or None,
            action_type=action_type,
            status="reserved",
            reserved_credits=credits_to_reserve,
            consumed_credits=included_reserved,
            overage_credits=overage_reserved,
            overage_amount_usd=overage_amount,
            reference_type=reference_type,
            reference_id=reference_id,
            week_start_utc=week_start_utc,
            cycle_start_at=cycle_start_at,
            cycle_end_at=cycle_end_at,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        return UsageReservation(
            event_id=str(event.event_id),
            overage_credits=overage_reserved,
            overage_amount_usd=float(overage_amount),
        )

    async def finalize_usage(
        self,
        *,
        event_id: str,
        reference_id: str | None = None,
    ) -> None:
        event = self.db.query(UsageEvent).filter_by(event_id=event_id).with_for_update().first()
        if not event or event.status != "reserved":
            return

        cycle = (
            self.db.query(UsageStoreCycle)
            .filter_by(
                store_id=event.store_id,
                cycle_start_at=event.cycle_start_at,
                cycle_end_at=event.cycle_end_at,
            )
            .with_for_update()
            .first()
        )
        store = self.db.query(Store).filter_by(store_id=event.store_id).first()
        if not cycle or not store:
            return

        if reference_id:
            event.reference_id = reference_id

        if event.overage_credits > 0 and event.overage_amount_usd > 0:
            try:
                usage_charge_id = await self._create_usage_charge(store=store, event=event)
                event.usage_charge_id = usage_charge_id
                event.billing_error_code = None
                event.billing_error_message = None
            except Exception as exc:
                error_text = str(exc)
                logger.error("Usage charge failed for event=%s: %s", event_id, error_text)

                reason = "usage_charge_failed"
                message = "Unable to post overage charge. Overage is temporarily blocked."
                if "capped" in error_text.lower() or "cap" in error_text.lower():
                    reason = "usage_cap_reached"
                    message = "Usage billing cap reached. Increase cap to continue overage usage."

                cycle.overage_blocked = True
                cycle.overage_block_reason = reason
                cycle.overage_block_message = message
                event.billing_error_code = reason
                event.billing_error_message = error_text[:1000]

        event.status = "consumed"
        self.db.commit()

    async def refund_usage(
        self,
        *,
        event_id: str,
        reason: str | None = None,
    ) -> None:
        event = self.db.query(UsageEvent).filter_by(event_id=event_id).with_for_update().first()
        if not event or event.status != "reserved":
            return

        cycle = (
            self.db.query(UsageStoreCycle)
            .filter_by(
                store_id=event.store_id,
                cycle_start_at=event.cycle_start_at,
                cycle_end_at=event.cycle_end_at,
            )
            .with_for_update()
            .first()
        )
        if cycle:
            cycle.consumed_credits = max(cycle.consumed_credits - event.consumed_credits, 0)
            cycle.overage_credits = max(cycle.overage_credits - event.overage_credits, 0)
            cycle.overage_amount_usd = max(
                Decimal("0"),
                Decimal(str(cycle.overage_amount_usd)) - Decimal(str(event.overage_amount_usd)),
            )

        if event.customer_identifier and event.week_start_utc:
            week_row = (
                self.db.query(UsageCustomerWeek)
                .filter_by(
                    store_id=event.store_id,
                    customer_identifier=event.customer_identifier,
                    week_start_utc=event.week_start_utc,
                )
                .with_for_update()
                .first()
            )
            if week_row:
                week_row.used_count = max(week_row.used_count - 1, 0)

        event.status = "refunded"
        if reason:
            event.billing_error_message = reason[:1000]

        self.db.commit()

    async def get_usage_summary(self, *, store: Store) -> dict:
        now = datetime.utcnow()
        await self._ensure_store_billing_synced(store)

        cycle_start_at, cycle_end_at = self._resolve_cycle_window(store, now)
        included_credits = self._resolve_included_credits(store, now)
        cycle = (
            self.db.query(UsageStoreCycle)
            .filter_by(store_id=store.store_id, cycle_start_at=cycle_start_at, cycle_end_at=cycle_end_at)
            .first()
        )

        consumed_credits = cycle.consumed_credits if cycle else 0
        overage_credits = cycle.overage_credits if cycle else 0
        overage_amount = float(cycle.overage_amount_usd) if cycle else 0.0
        overage_blocked = cycle.overage_blocked if cycle else False
        overage_block_reason = cycle.overage_block_reason if cycle else None
        overage_block_message = cycle.overage_block_message if cycle else None

        remaining = max(included_credits - consumed_credits, 0)
        status = (store.subscription_status or "").upper()
        can_auto_charge_overage = bool(
            store.plan_shopify_subscription_id
            and store.has_usage_billing
            and store.usage_line_item_id
            and status in ACTIVE_SUBSCRIPTION_STATUSES
        )

        return {
            "cycle_start_at": cycle_start_at,
            "cycle_end_at": cycle_end_at,
            "included_credits": included_credits,
            "consumed_credits": consumed_credits,
            "remaining_included_credits": remaining,
            "overage_credits": overage_credits,
            "overage_amount_usd": overage_amount,
            "overage_blocked": overage_blocked,
            "overage_block_reason": overage_block_reason,
            "overage_block_message": overage_block_message,
            "can_auto_charge_overage": can_auto_charge_overage,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _ensure_store_billing_synced(self, store: Store) -> None:
        # Free/founding stores may not have a Shopify subscription.
        if not store.plan_shopify_subscription_id:
            return

        now = datetime.utcnow()
        if (
            store.billing_status_synced_at
            and now - store.billing_status_synced_at < timedelta(minutes=5)
        ):
            return

        try:
            svc = ShopifyService(store.shopify_domain, require_shopify_access_token(store))
            status = await svc.billing_get_status()
        except Exception as exc:
            logger.warning("Failed to sync billing status for store=%s: %s", store.store_id, exc)
            return

        if not status:
            store.subscription_status = "CANCELLED"
            store.has_usage_billing = False
            store.usage_line_item_id = None
            store.billing_status_synced_at = now
            self.db.commit()
            return

        store.subscription_status = status.get("status")
        store.has_usage_billing = bool(status.get("has_usage_billing"))
        store.usage_line_item_id = status.get("usage_line_item_id")
        if status.get("shop_timezone"):
            store.store_timezone = status.get("shop_timezone")

        current_end = self._parse_iso_datetime(status.get("current_period_end"))
        created_at = self._parse_iso_datetime(status.get("created_at"))
        cycle_delta = self._billing_cycle_delta(store)

        if current_end:
            if store.billing_cycle_end_at and abs((store.billing_cycle_end_at - current_end).total_seconds()) > 60:
                # New period boundary observed from Shopify.
                store.billing_cycle_start_at = store.billing_cycle_end_at
                store.billing_cycle_end_at = current_end
            else:
                store.billing_cycle_end_at = current_end
                if not store.billing_cycle_start_at:
                    guessed_start = current_end - cycle_delta
                    if created_at and created_at > guessed_start:
                        guessed_start = created_at
                    store.billing_cycle_start_at = guessed_start
        elif not store.billing_cycle_start_at and created_at:
            store.billing_cycle_start_at = created_at
            store.billing_cycle_end_at = created_at + cycle_delta

        store.billing_status_synced_at = now
        self.db.commit()

    def _enforce_store_generation_allowed(self, store: Store, now: datetime) -> None:
        if store.plan_name == "free":
            self._raise_usage_error(
                status_code=402,
                code="PLAN_REQUIRED",
                message="A paid plan is required to use AI generation features.",
            )

        if store.trial_mode == "intro_free":
            if store.trial_ends_at and store.trial_ends_at < now:
                store.billing_lock_reason = "trial_expired"
                if not store.trial_end_reason:
                    store.trial_end_reason = "time_expired"
                self.db.commit()
            if store.billing_lock_reason in {"trial_expired", "trial_credits_exhausted"}:
                self._raise_usage_error(
                    status_code=402,
                    code="TRIAL_EXPIRED",
                    message="Trial ended. Select a plan to re-enable widget and customer try-ons.",
                )

        if (
            store.plan_name in {"founding_trial", "free_trial"}
            and store.trial_ends_at
            and store.trial_ends_at < now
        ):
            if not store.billing_lock_reason:
                store.billing_lock_reason = "trial_expired"
            if not store.trial_end_reason:
                store.trial_end_reason = "time_expired"
            self.db.commit()
            self._raise_usage_error(
                status_code=402,
                code="TRIAL_EXPIRED",
                message="Trial ended. Select a plan to re-enable widget and customer try-ons.",
            )

        if store.plan_shopify_subscription_id:
            status = (store.subscription_status or "").upper()
            if status and status not in ACTIVE_SUBSCRIPTION_STATUSES:
                self._raise_usage_error(
                    status_code=402,
                    code="SUBSCRIPTION_INACTIVE",
                    message="Subscription is not active. Please reactivate billing to continue AI generation.",
                )

    def _enforce_overage_eligibility(self, *, store: Store, cycle: UsageStoreCycle) -> None:
        if cycle.overage_blocked:
            self._raise_usage_error(
                status_code=402,
                code="OVERAGE_BLOCKED",
                message=cycle.overage_block_message or "Overage usage is currently blocked due to billing issues.",
            )

        status = (store.subscription_status or "").upper()
        if status not in ACTIVE_SUBSCRIPTION_STATUSES:
            self._raise_usage_error(
                status_code=402,
                code="SUBSCRIPTION_INACTIVE",
                message="Subscription is not active. Overage is unavailable.",
            )

        if not store.has_usage_billing or not store.usage_line_item_id:
            self._raise_usage_error(
                status_code=402,
                code="LEGACY_SUBSCRIPTION_UPGRADE_REQUIRED",
                message=(
                    "Included credits are exhausted. To enable overage auto-billing, "
                    "re-approve your plan from Billing settings."
                ),
            )

    def _get_active_plan(self, store: Store) -> Plan | None:
        return self.db.query(Plan).filter_by(name=store.plan_name, is_active=True).first()

    def _resolve_included_credits(self, store: Store, now: datetime, plan: Plan | None = None) -> int:
        if plan is None:
            plan = self._get_active_plan(store)
        if plan:
            if store.trial_ends_at and store.trial_ends_at > now and plan.trial_credits:
                return int(plan.trial_credits)
            if store.billing_interval == "annual":
                return int(plan.credits_annual)
            return int(plan.credits_monthly)
        return int(store.credits_limit or 0)

    def _should_transition_plan_trial_on_credit_exhaustion(
        self,
        *,
        store: Store,
        cycle: UsageStoreCycle,
        included_credits: int,
        now: datetime,
        plan: Plan | None,
    ) -> bool:
        if store.trial_mode != "plan_trial":
            return False
        if not store.trial_ends_at or store.trial_ends_at <= now:
            return False
        if not plan:
            return False
        if included_credits <= 0:
            return False
        return cycle.consumed_credits >= included_credits

    def _transition_plan_trial_to_full_plan(
        self,
        *,
        store: Store,
        cycle: UsageStoreCycle,
        plan: Plan | None,
        now: datetime,
    ) -> int:
        if plan is None:
            return cycle.included_credits

        full_credits = int(plan.credits_annual if store.billing_interval == "annual" else plan.credits_monthly)
        store.trial_ends_at = now
        store.trial_mode = "none"
        store.trial_end_reason = "credits_exhausted"
        store.credits_limit = full_credits
        cycle.included_credits = max(cycle.included_credits, full_credits)
        return cycle.included_credits

    def _lock_intro_trial_for_credit_exhaustion(self, *, store: Store, now: datetime) -> None:
        store.billing_lock_reason = "trial_credits_exhausted"
        store.trial_end_reason = "credits_exhausted"
        if not store.trial_ends_at or store.trial_ends_at > now:
            store.trial_ends_at = now

    def _resolve_overage_usd_per_tryon(self, plan: Plan | None) -> Decimal:
        if plan and plan.overage_usd_per_tryon is not None:
            value = Decimal(str(plan.overage_usd_per_tryon))
            if value > 0:
                return value
        # Fallback for older plan rows before explicit per-plan overage is configured.
        return Decimal(str(settings.OVERAGE_USD_PER_CREDIT)) * Decimal(str(max(settings.CREDITS_PER_GENERATION, 1)))

    def _resolve_week_window(self, store: Store, now_utc: datetime) -> tuple[datetime, datetime, str]:
        tz_name = (store.store_timezone or "UTC").strip() or "UTC"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            # Windows environments may not have IANA tz data available (tzdata missing).
            # Fall back to built-in UTC tzinfo so usage gating never hard-fails.
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

    def _resolve_cycle_window(self, store: Store, now_utc: datetime) -> tuple[datetime, datetime]:
        if store.billing_cycle_start_at and store.billing_cycle_end_at and store.billing_cycle_end_at > store.billing_cycle_start_at:
            return store.billing_cycle_start_at, store.billing_cycle_end_at

        delta = self._billing_cycle_delta(store)
        anchor = store.plan_activated_at or now_utc
        if anchor > now_utc:
            anchor = now_utc

        # Roll forward from anchor to include "now" in current cycle.
        cycle_start = anchor
        cycle_end = cycle_start + delta
        while cycle_end < now_utc:
            cycle_start = cycle_end
            cycle_end = cycle_start + delta
        return cycle_start, cycle_end

    def _billing_cycle_delta(self, store: Store) -> timedelta:
        return timedelta(days=365 if store.billing_interval == "annual" else 30)

    def _parse_iso_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return None

    async def _create_usage_charge(self, *, store: Store, event: UsageEvent) -> str:
        amount = float(event.overage_amount_usd or 0)
        if amount <= 0:
            return ""

        svc = ShopifyService(store.shopify_domain, require_shopify_access_token(store))
        description = f"Optimo overage charge for {event.action_type} ({event.overage_credits} credits)"
        result = await svc.billing_create_usage_charge(
            usage_line_item_id=store.usage_line_item_id,
            amount_usd=amount,
            description=description,
        )
        return result["usage_record_id"]

    def _raise_usage_error(self, *, status_code: int, code: str, message: str, **extra) -> None:
        detail = {"code": code, "message": message}
        for key, value in extra.items():
            if value is not None:
                detail[key] = value
        raise HTTPException(status_code=status_code, detail=detail)
