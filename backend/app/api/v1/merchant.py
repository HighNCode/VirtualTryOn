"""
Merchant Admin Endpoints
Covers the 6-step onboarding wizard, billing plan management, and the
widget check-enabled endpoint consumed by the storefront widget.

Merchant routes resolve the active store from Shopify App Bridge auth when present,
with header fallbacks for the current embedded-app migration state.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.api.store_context import (
    get_current_merchant_store,
    get_public_store,
    require_shopify_access_token,
    resolve_merchant_shopify_access_token,
)
from app.core.database import get_db
from app.core.security import _bearer_scheme
from app.config import get_settings
from app.models.database import Store, MerchantOnboarding, WidgetConfig, TryOn, Product, Plan
from app.models.schemas import (
    OnboardingStatusResponse,
    GoalsRequest,
    OnboardingStepResponse,
    ReferralRequest,
    WidgetScopeRequest,
    WidgetScopeResponse,
    ThemeStatusResponse,
    ThemeStatusUpdateRequest,
    BillingActivateRequest,
    PlanResponse,
    WidgetCheckResponse,
    DashboardOverviewResponse,
    WidgetConfigUpdateRequest,
    WidgetConfigResponse,
    PlanConfigResponse,
    PlansResponse,
    CreateSubscriptionRequest,
    CreateSubscriptionResponse,
    BillingStatusResponse,
    BillingUsageSummaryResponse,
    CancelSubscriptionResponse,
    SessionResponse,
    WidgetSessionCreateRequest,
)
from app.api.v1.sessions import create_or_resume_session_for_product
from app.services.shopify_service import ShopifyService
from app.services.usage_governance_service import UsageGovernanceService

logger = logging.getLogger(__name__)

merchant_router = APIRouter(prefix="/merchant", tags=["Merchant"])
widget_router = APIRouter(prefix="/widget", tags=["Widget"])


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Shared helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _normalize_shopify_product_gid(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise HTTPException(422, "shopify_product_gid is required")
    if normalized.startswith("gid://shopify/Product/"):
        return normalized
    if normalized.isdigit():
        return f"gid://shopify/Product/{normalized}"
    return normalized


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Onboarding â€” Status
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@merchant_router.get("/onboarding/status", response_model=OnboardingStatusResponse)
def get_onboarding_status(
    store: Store = Depends(get_current_merchant_store),
):
    """
    Return the full onboarding state for the store.
    Called on every app load so the Remix frontend can route to the correct step.
    """
    ob = store.onboarding
    wc = store.widget_config

    return OnboardingStatusResponse(
        store_id=store.store_id,
        onboarding_step=store.onboarding_step,
        onboarding_completed=store.onboarding_completed_at is not None,
        plan_name=store.plan_name,
        goals=ob.goals if ob else None,
        referral_source=ob.referral_source if ob else None,
        referral_detail=ob.referral_detail if ob else None,
        scope_type=wc.scope_type if wc else None,
        enabled_collection_ids=wc.enabled_collection_ids if wc else None,
        enabled_product_ids=wc.enabled_product_ids if wc else None,
        theme_extension_detected=wc.theme_extension_detected if wc else False,
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Onboarding â€” Step 2: Goals
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@merchant_router.post("/onboarding/goals", response_model=OnboardingStepResponse)
def save_goals(
    body: GoalsRequest,
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Save merchant's goals (step 2).
    Advances onboarding_step to 'referral'.
    """
    if not body.goals:
        raise HTTPException(422, "At least one goal must be selected")

    ob = store.onboarding
    if ob is None:
        ob = MerchantOnboarding(store_id=store.store_id)
        db.add(ob)

    ob.goals = body.goals
    store.onboarding_step = "referral"
    db.commit()

    logger.info(f"Goals saved for store {store.store_id}: {body.goals}")
    return OnboardingStepResponse(saved=True, next_step="referral")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Onboarding â€” Step 3: Referral
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@merchant_router.post("/onboarding/referral", response_model=OnboardingStepResponse)
def save_referral(
    body: ReferralRequest,
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Save referral source (step 3).
    Advances onboarding_step to 'widget_scope'.
    """
    if body.referral_source == "other" and not body.referral_detail:
        raise HTTPException(422, "referral_detail is required when referral_source is 'other'")

    ob = store.onboarding
    if ob is None:
        ob = MerchantOnboarding(store_id=store.store_id)
        db.add(ob)

    ob.referral_source = body.referral_source
    ob.referral_detail = body.referral_detail
    store.onboarding_step = "widget_scope"
    db.commit()

    logger.info(f"Referral saved for store {store.store_id}: {body.referral_source}")
    return OnboardingStepResponse(saved=True, next_step="widget_scope")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Onboarding â€” Step 4: Widget Scope
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

VALID_SCOPE_TYPES = {"all", "selected_collections", "selected_products", "mixed"}


@merchant_router.get("/onboarding/widget-scope", response_model=WidgetScopeResponse)
def get_widget_scope(store: Store = Depends(get_current_merchant_store)):
    """Return current widget scope configuration (or defaults if not yet set)."""
    wc = store.widget_config
    if wc is None:
        return WidgetScopeResponse(
            scope_type="all",
            enabled_collection_ids=[],
            enabled_product_ids=[],
        )
    return WidgetScopeResponse(
        scope_type=wc.scope_type,
        enabled_collection_ids=wc.enabled_collection_ids or [],
        enabled_product_ids=wc.enabled_product_ids or [],
    )


@merchant_router.post("/onboarding/widget-scope", response_model=WidgetScopeResponse)
def save_widget_scope(
    body: WidgetScopeRequest,
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Save widget scope settings (step 4).
    Advances onboarding_step to 'theme_setup'.
    """
    if body.scope_type not in VALID_SCOPE_TYPES:
        raise HTTPException(422, f"scope_type must be one of: {', '.join(sorted(VALID_SCOPE_TYPES))}")

    wc = store.widget_config
    if wc is None:
        wc = WidgetConfig(store_id=store.store_id)
        db.add(wc)

    wc.scope_type = body.scope_type
    wc.enabled_collection_ids = body.enabled_collection_ids
    wc.enabled_product_ids = body.enabled_product_ids
    store.onboarding_step = "theme_setup"
    db.commit()

    logger.info(f"Widget scope saved for store {store.store_id}: {body.scope_type}")
    return WidgetScopeResponse(
        scope_type=wc.scope_type,
        enabled_collection_ids=wc.enabled_collection_ids,
        enabled_product_ids=wc.enabled_product_ids,
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Onboarding â€” Step 5: Theme Status
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@merchant_router.get("/onboarding/theme-status", response_model=ThemeStatusResponse)
def get_theme_status(store: Store = Depends(get_current_merchant_store)):
    """
    Return whether the theme app extension block has been detected.
    Also returns a link to the merchant's Themes admin page.
    """
    wc = store.widget_config
    detected = wc.theme_extension_detected if wc else False
    themes_url = f"https://{store.shopify_domain}/admin/online-store/themes"
    return ThemeStatusResponse(theme_extension_detected=detected, themes_url=themes_url)


@merchant_router.post("/onboarding/theme-status", response_model=OnboardingStepResponse)
def update_theme_status(
    body: ThemeStatusUpdateRequest,
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Remix reports the theme extension detection result (step 5).

    For founding merchants (first FOUNDING_MERCHANT_LIMIT installs): auto-completes
    onboarding with a free 14-day trial and skips the billing step entirely.
    For all other merchants: advances onboarding_step to 'plan'.
    """
    wc = store.widget_config
    if wc is None:
        wc = WidgetConfig(store_id=store.store_id)
        db.add(wc)
    wc.theme_extension_detected = body.detected

    settings = get_settings()

    # â”€â”€ Founding merchant slot check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if not store.is_founding_merchant:
        founding_used = (
            db.query(func.count(Store.store_id))
            .filter(Store.is_founding_merchant == True)  # noqa: E712
            .scalar()
        ) or 0
        qualifies = founding_used < settings.FOUNDING_MERCHANT_LIMIT
    else:
        # Already a founding merchant re-entering this step â†’ send to billing to pick a plan
        qualifies = False

    if qualifies:
        store.is_founding_merchant = True
        store.plan_name = "founding_trial"
        store.credits_limit = settings.FOUNDING_MERCHANT_CREDITS
        store.trial_ends_at = datetime.utcnow() + timedelta(days=settings.FOUNDING_MERCHANT_TRIAL_DAYS)
        store.onboarding_step = "complete"
        store.onboarding_completed_at = datetime.utcnow()
        db.commit()
        logger.info(
            f"Founding merchant trial granted to store {store.store_id} "
            f"(slot {founding_used + 1}/{settings.FOUNDING_MERCHANT_LIMIT})"
        )
        return OnboardingStepResponse(saved=True, next_step="complete")
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    store.onboarding_step = "plan"
    db.commit()
    logger.info(f"Theme status updated for store {store.store_id}: detected={body.detected}")
    return OnboardingStepResponse(saved=True, next_step="plan")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Billing
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _get_plan_or_404(plan_name: str, db: DBSession) -> Plan:
    """Fetch a Plan row by name, raising 422 if not found or inactive."""
    plan = db.query(Plan).filter_by(name=plan_name, is_active=True).first()
    if not plan:
        raise HTTPException(422, f"Unknown or inactive plan: '{plan_name}'")
    return plan


@merchant_router.post("/billing/activate", response_model=PlanResponse)
def activate_billing(
    body: BillingActivateRequest,
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Called by Remix after the Shopify billing callback confirms a paid subscription.
    Sets plan details, credits_limit, billing_interval, optional trial, and marks onboarding complete.
    """
    if body.billing_interval not in {"monthly", "annual"}:
        raise HTTPException(422, "billing_interval must be 'monthly' or 'annual'")

    plan = _get_plan_or_404(body.plan_name, db)

    full_credits = plan.credits_monthly if body.billing_interval == "monthly" else plan.credits_annual

    store.plan_name = body.plan_name
    store.plan_shopify_subscription_id = body.shopify_subscription_id
    store.plan_activated_at = datetime.utcnow()
    store.billing_interval = body.billing_interval
    store.subscription_status = "ACTIVE"
    store.billing_status_synced_at = None
    store.has_usage_billing = False
    store.usage_line_item_id = None
    store.billing_cycle_start_at = None
    store.billing_cycle_end_at = None
    if plan.trial_days:
        # Trial is always applied. During trial, grant trial_credits (80); full credits after.
        store.credits_limit = plan.trial_credits if plan.trial_credits else full_credits
        store.trial_ends_at = datetime.utcnow() + timedelta(days=plan.trial_days)
    else:
        store.credits_limit = full_credits
        store.trial_ends_at = None

    if store.onboarding_completed_at is None:
        store.onboarding_step = "complete"
        store.onboarding_completed_at = datetime.utcnow()

    db.commit()

    logger.info(
        f"Billing activated for store {store.store_id}: "
        f"plan={body.plan_name}, interval={body.billing_interval}, "
        f"credits={store.credits_limit}, trial_ends_at={store.trial_ends_at}"
    )
    return PlanResponse(
        plan_name=store.plan_name,
        credits_limit=store.credits_limit,
        plan_activated_at=store.plan_activated_at,
        shopify_subscription_id=store.plan_shopify_subscription_id,
    )


@merchant_router.get("/billing/plan", response_model=PlanResponse)
def get_plan(store: Store = Depends(get_current_merchant_store)):
    """Return the store's current plan details."""
    return PlanResponse(
        plan_name=store.plan_name,
        credits_limit=store.credits_limit,
        plan_activated_at=store.plan_activated_at,
        shopify_subscription_id=store.plan_shopify_subscription_id,
    )


@merchant_router.get("/billing/plans", response_model=PlansResponse)
def get_billing_plans(
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Return all active subscription plans from DB with pricing and feature details.
    The store's active plan is marked with is_current=True.
    """
    db_plans = db.query(Plan).filter_by(is_active=True).order_by(Plan.sort_order).all()
    plans = [
        PlanConfigResponse(
            id=p.id,
            name=p.name,
            display_name=p.display_name,
            price_monthly=float(p.price_monthly),
            price_annual_total=float(p.price_annual_total),
            price_annual_per_month=float(p.price_annual_per_month),
            annual_discount_pct=p.annual_discount_pct,
            credits_monthly=p.credits_monthly,
            credits_annual=p.credits_annual,
            overage_usd_per_tryon=float(p.overage_usd_per_tryon),
            usage_cap_usd=float(p.usage_cap_usd),
            trial_days=p.trial_days,
            trial_credits=p.trial_credits,
            features=p.features,
            is_current=(p.name == store.plan_name),
            is_active=p.is_active,
        )
        for p in db_plans
    ]
    return PlansResponse(plans=plans)


@merchant_router.get("/billing/status", response_model=BillingStatusResponse)
async def get_billing_status(
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Full billing status combining DB plan data with a live Shopify subscription query.

    - If the store is on the free plan (no subscription ID), Shopify fields are null.
    - If the Shopify call fails (network error, token issue), DB data is returned
      with null Shopify fields rather than erroring — the screen degrades gracefully.
    - If the trial has expired and Shopify confirms ACTIVE status, the store is
      automatically upgraded to full plan credits (lazy upgrade, no webhook needed).
    """
    shopify_status = None
    if store.plan_shopify_subscription_id:
        try:
            svc = ShopifyService(store.shopify_domain, require_shopify_access_token(store))
            shopify_status = await svc.billing_get_status()
        except Exception as exc:
            logger.warning(f"Shopify billing status call failed for store {store.store_id}: {exc}")

    if shopify_status:
        store.subscription_status = shopify_status.get("status")
        store.has_usage_billing = bool(shopify_status.get("has_usage_billing"))
        store.usage_line_item_id = shopify_status.get("usage_line_item_id")
        store.billing_status_synced_at = datetime.utcnow()
        if shopify_status.get("shop_timezone"):
            store.store_timezone = shopify_status.get("shop_timezone")

        current_end_raw = shopify_status.get("current_period_end")
        if current_end_raw:
            try:
                current_end = datetime.fromisoformat(str(current_end_raw).replace("Z", "+00:00"))
                if current_end.tzinfo:
                    current_end = current_end.astimezone(timezone.utc).replace(tzinfo=None)
                if store.billing_cycle_end_at and abs((store.billing_cycle_end_at - current_end).total_seconds()) > 60:
                    store.billing_cycle_start_at = store.billing_cycle_end_at
                elif store.billing_cycle_start_at is None:
                    cycle_days = 365 if store.billing_interval == "annual" else 30
                    store.billing_cycle_start_at = current_end - timedelta(days=cycle_days)
                store.billing_cycle_end_at = current_end
            except Exception:
                pass

    # Auto-upgrade: trial ended + Shopify is actively billing
    if (
        store.trial_ends_at
        and store.trial_ends_at < datetime.utcnow()
        and shopify_status
        and shopify_status.get("status") == "ACTIVE"
    ):
        plan = db.query(Plan).filter_by(name=store.plan_name, is_active=True).first()
        if plan:
            full_credits = (
                plan.credits_monthly
                if store.billing_interval == "monthly"
                else plan.credits_annual
            )
            store.credits_limit = full_credits
            store.trial_ends_at = None

    db.commit()

    return BillingStatusResponse(
        plan_name=store.plan_name,
        billing_interval=store.billing_interval,
        credits_limit=store.credits_limit,
        trial_ends_at=store.trial_ends_at,
        plan_activated_at=store.plan_activated_at,
        shopify_subscription_id=store.plan_shopify_subscription_id,
        subscription_status=(shopify_status or {}).get("status") or store.subscription_status,
        current_period_end=(shopify_status or {}).get("current_period_end") or store.billing_cycle_end_at,
        is_test_subscription=(shopify_status or {}).get("test"),
        has_usage_billing=store.has_usage_billing,
        store_timezone=store.store_timezone,
    )


@merchant_router.get("/billing/usage-summary", response_model=BillingUsageSummaryResponse)
async def get_billing_usage_summary(
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Cycle-based included+overage credit usage for billing UI and diagnostics.
    """
    usage_service = UsageGovernanceService(db)
    summary = await usage_service.get_usage_summary(store=store)
    return BillingUsageSummaryResponse(**summary)


@merchant_router.post("/billing/create-subscription", response_model=CreateSubscriptionResponse)
async def create_subscription(
    body: CreateSubscriptionRequest,
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
):
    """
    Create a Shopify recurring subscription for a paid plan.

    Flow:
    1. FastAPI calls Shopify appSubscriptionCreate â†’ gets confirmationUrl
    2. Returns confirmationUrl to Remix
    3. Remix redirects merchant to confirmationUrl (Shopify's approval page)
    4. After merchant approves, Shopify calls returnUrl (Remix route)
    5. Remix callback calls POST /billing/activate to update the DB

    Does NOT update the DB â€” that happens after merchant approves on Shopify's page.
    """
    if body.billing_interval not in {"monthly", "annual"}:
        raise HTTPException(422, "billing_interval must be 'monthly' or 'annual'")

    plan = _get_plan_or_404(body.plan_name, db)

    if body.plan_name == store.plan_name and body.billing_interval == store.billing_interval:
        raise HTTPException(409, f"Store is already on '{body.plan_name}' ({body.billing_interval})")

    price = float(plan.price_monthly if body.billing_interval == "monthly" else plan.price_annual_total)
    trial_days = plan.trial_days or 0  # Trial is always applied

    settings = get_settings()
    is_test = settings.APP_ENV == "development"
    is_upgrade = store.plan_name not in {"free", body.plan_name}

    try:
        access_token = await resolve_merchant_shopify_access_token(
            store,
            credentials,
            action_label="billing management",
        )
        svc = ShopifyService(store.shopify_domain, access_token)
        result = await svc.billing_create_subscription(
            plan_name=plan.display_name,
            price_usd=price,
            return_url=body.return_url,
            billing_interval=body.billing_interval,
            trial_days=trial_days,
            test=is_test,
            is_upgrade=is_upgrade,
            usage_cap_usd=float(plan.usage_cap_usd),
            overage_terms=(
                f"${float(plan.overage_usd_per_tryon):.3f} per AI generation "
                f"({settings.CREDITS_PER_GENERATION} credits per generation)."
            ),
        )
    except Exception as exc:
        logger.error(f"Shopify subscription create failed for store {store.store_id}: {exc}")
        raise HTTPException(502, f"Failed to create Shopify subscription: {exc}")

    logger.info(
        f"Subscription creation initiated for store {store.store_id}: "
        f"plan={body.plan_name}, interval={body.billing_interval}, trial_days={trial_days}"
    )
    return CreateSubscriptionResponse(
        confirmation_url=result["confirmation_url"],
        shopify_subscription_id=result["subscription_id"],
    )


@merchant_router.post("/billing/cancel-subscription", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Cancel the active Shopify subscription and revert the store to the free plan.

    Remix should show a confirmation modal before calling this endpoint.
    """
    if store.plan_name == "free":
        raise HTTPException(400, "Store is already on the free plan")
    if not store.plan_shopify_subscription_id:
        raise HTTPException(400, "No active Shopify subscription found")

    try:
        svc = ShopifyService(store.shopify_domain, require_shopify_access_token(store))
        await svc.billing_cancel_subscription(store.plan_shopify_subscription_id)
    except Exception as exc:
        logger.error(f"Shopify subscription cancel failed for store {store.store_id}: {exc}")
        raise HTTPException(502, f"Failed to cancel Shopify subscription: {exc}")

    store.plan_name = "free"
    store.credits_limit = 0
    store.billing_interval = None
    store.trial_ends_at = None
    store.plan_shopify_subscription_id = None
    store.plan_activated_at = None
    store.subscription_status = "CANCELLED"
    store.billing_cycle_start_at = None
    store.billing_cycle_end_at = None
    store.billing_status_synced_at = datetime.utcnow()
    store.has_usage_billing = False
    store.usage_line_item_id = None
    db.commit()

    logger.info(f"Subscription cancelled for store {store.store_id}, reverted to free plan")
    return CancelSubscriptionResponse(
        cancelled=True,
        plan_name="free",
        credits_limit=0,
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Dashboard â€” Overview
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@merchant_router.get("/dashboard/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Single call that feeds all three sections of the merchant dashboard overview screen.

    Section 1 â€” theme button status (mirrors onboarding step 5 data)
    Section 2 â€” try-on usage: count of completed try-ons in last 30 rolling days
    Section 3 â€” widget scope summary: scope type + counts of enabled IDs
    """
    wc = store.widget_config

    # â”€â”€ Section 1: theme detection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    theme_detected = wc.theme_extension_detected if wc else False
    themes_url = f"https://{store.shopify_domain}/admin/online-store/themes"

    # â”€â”€ Section 2: try-on usage (rolling 30 days) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    tryon_used = (
        db.query(func.count(TryOn.try_on_id))
        .join(Product, TryOn.product_id == Product.product_id)
        .filter(
            Product.store_id == store.store_id,
            TryOn.processing_status == "completed",
            TryOn.created_at >= thirty_days_ago,
        )
        .scalar()
    ) or 0

    # â”€â”€ Section 3: widget scope summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    scope_type = wc.scope_type if wc else "all"
    enabled_products_count = len(wc.enabled_product_ids or []) if wc else 0
    enabled_collections_count = len(wc.enabled_collection_ids or []) if wc else 0

    return DashboardOverviewResponse(
        theme_extension_detected=theme_detected,
        themes_url=themes_url,
        tryon_used_30d=tryon_used,
        credits_limit=store.credits_limit,
        plan_name=store.plan_name,
        scope_type=scope_type,
        enabled_collections_count=enabled_collections_count,
        enabled_products_count=enabled_products_count,
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Dashboard â€” Widget Config (GET + PATCH, post-onboarding)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_DEFAULT_WIDGET_COLOR = "#FF0000"


def _widget_config_response(wc: Optional[WidgetConfig]) -> WidgetConfigResponse:
    """Build WidgetConfigResponse, applying code-level defaults for null DB values."""
    if wc is None:
        return WidgetConfigResponse(
            scope_type="all",
            enabled_collection_ids=[],
            enabled_product_ids=[],
            theme_extension_detected=False,
            widget_color=_DEFAULT_WIDGET_COLOR,
            weekly_tryon_limit=get_settings().WEEKLY_TRYON_LIMIT_DEFAULT,
        )
    return WidgetConfigResponse(
        scope_type=wc.scope_type,
        enabled_collection_ids=wc.enabled_collection_ids or [],
        enabled_product_ids=wc.enabled_product_ids or [],
        theme_extension_detected=wc.theme_extension_detected,
        widget_color=wc.widget_color or _DEFAULT_WIDGET_COLOR,
        weekly_tryon_limit=wc.weekly_tryon_limit,
    )


@merchant_router.get("/widget-config", response_model=WidgetConfigResponse)
def get_widget_config(store: Store = Depends(get_current_merchant_store)):
    """
    Return the full widget configuration for the Settings â†’ Custom screen.
    If no config has been saved yet, returns defaults (scope_type='all', widget_color='#FF0000').
    """
    return _widget_config_response(store.widget_config)


@merchant_router.patch("/widget-config", response_model=WidgetConfigResponse)
def update_widget_config(
    body: WidgetConfigUpdateRequest,
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Partial update of WidgetConfig from the dashboard.
    Unlike POST /onboarding/widget-scope, this does NOT advance onboarding_step â€”
    safe to call for merchants who have already completed onboarding.

    Used by:
    - Settings â†’ Custom screen Save action (widget_color)
    - "Manage Products and Collections" save action (scope_type + ID lists)
    - "Mark as added" theme detection button (theme_extension_detected)
    """
    if body.scope_type is not None and body.scope_type not in VALID_SCOPE_TYPES:
        raise HTTPException(422, f"scope_type must be one of: {', '.join(sorted(VALID_SCOPE_TYPES))}")
    if body.weekly_tryon_limit is not None and not (1 <= body.weekly_tryon_limit <= 1000):
        raise HTTPException(422, "weekly_tryon_limit must be between 1 and 1000")

    wc = store.widget_config
    if wc is None:
        wc = WidgetConfig(store_id=store.store_id)
        db.add(wc)

    if body.scope_type is not None:
        wc.scope_type = body.scope_type
    if body.enabled_collection_ids is not None:
        wc.enabled_collection_ids = body.enabled_collection_ids
    if body.enabled_product_ids is not None:
        wc.enabled_product_ids = body.enabled_product_ids
    if body.theme_extension_detected is not None:
        wc.theme_extension_detected = body.theme_extension_detected
    if body.widget_color is not None:
        wc.widget_color = body.widget_color
    if body.weekly_tryon_limit is not None:
        wc.weekly_tryon_limit = body.weekly_tryon_limit

    db.commit()
    db.refresh(wc)

    logger.info(f"Widget config updated for store {store.store_id}: {body.model_dump(exclude_none=True)}")
    return _widget_config_response(wc)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Widget â€” check-enabled
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@widget_router.get("/check-enabled", response_model=WidgetCheckResponse)
def check_widget_enabled(
    shopify_product_gid: str = Query(..., description="Shopify product GID, e.g. gid://shopify/Product/123"),
    store: Store = Depends(get_public_store),
):
    """
    Called by the storefront widget to decide whether to render the try-on button.

    Scope rules:
    - 'all'                   â†’ always enabled
    - 'selected_products'     â†’ enabled only if GID is in enabled_product_ids
    - 'mixed'                 â†’ enabled if GID is in enabled_product_ids (default true if list is empty)
    - 'selected_collections'  â†’ enabled=true (collection membership check deferred to Remix layer)
    - no config yet           â†’ enabled=true (default open)

    Billing gate: widget is disabled for founding merchants whose trial has expired.
    """
    # â”€â”€ Billing gate: founding trial expired â†’ widget disabled â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if (
        store.plan_name == "founding_trial"
        and store.trial_ends_at
        and store.trial_ends_at < datetime.utcnow()
    ):
        return WidgetCheckResponse(enabled=False)
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    normalized_gid = _normalize_shopify_product_gid(shopify_product_gid)
    wc = store.widget_config
    if wc is None or wc.scope_type == "all":
        return WidgetCheckResponse(enabled=True)

    if wc.scope_type == "selected_products":
        ids = wc.enabled_product_ids
        enabled = bool(ids) and normalized_gid in ids
        return WidgetCheckResponse(enabled=enabled)

    if wc.scope_type == "mixed":
        product_ids = wc.enabled_product_ids or []
        enabled = (not product_ids) or (normalized_gid in product_ids)
        return WidgetCheckResponse(enabled=enabled)

    # 'selected_collections' â€” collection membership requires Shopify Admin API
    # (only available in Remix). Return true and let the Remix layer filter further.
    return WidgetCheckResponse(enabled=True)


@widget_router.post("/sessions", response_model=SessionResponse)
def create_widget_session(
    body: WidgetSessionCreateRequest,
    store: Store = Depends(get_public_store),
    db: DBSession = Depends(get_db),
):
    """
    Storefront widget entrypoint that accepts a Shopify product GID and returns
    a normal session payload without exposing the internal store identifier.
    """
    normalized_gid = _normalize_shopify_product_gid(body.shopify_product_gid)
    shopify_product_id = normalized_gid.split("/")[-1]

    product = db.query(Product).filter_by(
        store_id=store.store_id,
        shopify_product_id=shopify_product_id,
    ).first()

    if not product:
        raise HTTPException(
            404,
            f"Product not found for Shopify product: {body.shopify_product_gid}",
        )

    try:
        return create_or_resume_session_for_product(
            product=product,
            store=store,
            user_identifier=body.user_identifier,
            db=db,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Widget session creation failed: %s", exc, exc_info=True)
        db.rollback()
        raise HTTPException(500, f"Failed to create widget session: {exc}")

