"""
Merchant Admin Endpoints
Covers the 6-step onboarding wizard, billing plan management, and the
widget check-enabled endpoint consumed by the storefront widget.

All merchant endpoints require the X-Store-ID header.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.core.database import get_db
from app.config import get_settings
from app.models.database import Store, MerchantOnboarding, WidgetConfig, TryOn, Product
from app.models.schemas import (
    OnboardingStatusResponse,
    GoalsRequest,
    OnboardingStepResponse,
    ReferralRequest,
    WidgetScopeRequest,
    WidgetScopeResponse,
    ThemeStatusResponse,
    ThemeStatusUpdateRequest,
    OnboardingCompleteRequest,
    OnboardingCompleteResponse,
    BillingActivateRequest,
    PlanResponse,
    WidgetCheckResponse,
    DashboardOverviewResponse,
    WidgetConfigUpdateRequest,
    WidgetConfigResponse,
    PlanConfig,
    PlansResponse,
    CreateSubscriptionRequest,
    CreateSubscriptionResponse,
    BillingStatusResponse,
    CancelSubscriptionResponse,
)
from app.services.shopify_service import ShopifyService

logger = logging.getLogger(__name__)

merchant_router = APIRouter(prefix="/merchant", tags=["Merchant"])
widget_router = APIRouter(prefix="/widget", tags=["Widget"])

PLAN_CONFIGS: dict[str, dict] = {
    "free": {
        "display_name": "Free Plan",
        "price_usd": 0.0,
        "monthly_tryon_limit": 10,
        "features": ["10 try-ons/month", "Basic widget", "Email support"],
    },
    "starter": {
        "display_name": "Starter Plan",
        "price_usd": 9.99,
        "monthly_tryon_limit": 100,
        "features": ["100 try-ons/month", "AI Studio Look", "Fit heatmap", "Analytics", "Priority support"],
    },
}

# Derived lookup kept for backward-compatibility with existing endpoints
PLAN_LIMITS = {name: cfg["monthly_tryon_limit"] for name, cfg in PLAN_CONFIGS.items()}


# ─────────────────────────────────────────────────────────────
# Shared dependency
# ─────────────────────────────────────────────────────────────

def get_store(
    x_store_id: str = Header(..., alias="X-Store-ID"),
    db: DBSession = Depends(get_db),
) -> Store:
    store = db.query(Store).filter_by(store_id=x_store_id).first()
    if not store:
        raise HTTPException(404, "Store not found")
    return store


# ─────────────────────────────────────────────────────────────
# Onboarding — Status
# ─────────────────────────────────────────────────────────────

@merchant_router.get("/onboarding/status", response_model=OnboardingStatusResponse)
def get_onboarding_status(
    store: Store = Depends(get_store),
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
        scope_type=wc.scope_type if wc else None,
        enabled_collection_ids=wc.enabled_collection_ids if wc else None,
        enabled_product_ids=wc.enabled_product_ids if wc else None,
        theme_extension_detected=wc.theme_extension_detected if wc else False,
    )


# ─────────────────────────────────────────────────────────────
# Onboarding — Step 2: Goals
# ─────────────────────────────────────────────────────────────

@merchant_router.post("/onboarding/goals", response_model=OnboardingStepResponse)
def save_goals(
    body: GoalsRequest,
    store: Store = Depends(get_store),
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


# ─────────────────────────────────────────────────────────────
# Onboarding — Step 3: Referral
# ─────────────────────────────────────────────────────────────

@merchant_router.post("/onboarding/referral", response_model=OnboardingStepResponse)
def save_referral(
    body: ReferralRequest,
    store: Store = Depends(get_store),
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


# ─────────────────────────────────────────────────────────────
# Onboarding — Step 4: Widget Scope
# ─────────────────────────────────────────────────────────────

VALID_SCOPE_TYPES = {"all", "selected_collections", "selected_products", "mixed"}


@merchant_router.get("/onboarding/widget-scope", response_model=WidgetScopeResponse)
def get_widget_scope(store: Store = Depends(get_store)):
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
    store: Store = Depends(get_store),
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


# ─────────────────────────────────────────────────────────────
# Onboarding — Step 5: Theme Status
# ─────────────────────────────────────────────────────────────

@merchant_router.get("/onboarding/theme-status", response_model=ThemeStatusResponse)
def get_theme_status(store: Store = Depends(get_store)):
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
    store: Store = Depends(get_store),
    db: DBSession = Depends(get_db),
):
    """
    Remix reports the theme extension detection result (step 5).
    Advances onboarding_step to 'plan'.
    """
    wc = store.widget_config
    if wc is None:
        wc = WidgetConfig(store_id=store.store_id)
        db.add(wc)

    wc.theme_extension_detected = body.detected
    store.onboarding_step = "plan"
    db.commit()

    logger.info(f"Theme status updated for store {store.store_id}: detected={body.detected}")
    return OnboardingStepResponse(saved=True, next_step="plan")


# ─────────────────────────────────────────────────────────────
# Onboarding — Step 6: Complete (free plan)
# ─────────────────────────────────────────────────────────────

@merchant_router.post("/onboarding/complete", response_model=OnboardingCompleteResponse)
def complete_onboarding(
    body: OnboardingCompleteRequest,
    store: Store = Depends(get_store),
    db: DBSession = Depends(get_db),
):
    """
    Complete onboarding on the free plan (step 6).
    Paid plan completion is handled by POST /merchant/billing/activate after
    Shopify confirms the subscription.
    """
    if body.plan != "free":
        raise HTTPException(422, "Use POST /merchant/billing/activate for paid plans")

    store.plan_name = "free"
    store.monthly_tryon_limit = PLAN_LIMITS["free"]
    store.onboarding_step = "complete"
    store.onboarding_completed_at = datetime.utcnow()
    db.commit()

    logger.info(f"Onboarding completed (free) for store {store.store_id}")
    return OnboardingCompleteResponse(
        completed=True,
        plan_name="free",
        monthly_tryon_limit=PLAN_LIMITS["free"],
    )


# ─────────────────────────────────────────────────────────────
# Billing
# ─────────────────────────────────────────────────────────────

@merchant_router.post("/billing/activate", response_model=PlanResponse)
def activate_billing(
    body: BillingActivateRequest,
    store: Store = Depends(get_store),
    db: DBSession = Depends(get_db),
):
    """
    Called by Remix after the Shopify billing callback confirms a paid subscription.
    Sets plan details and marks onboarding as complete.
    """
    limit = PLAN_LIMITS.get(body.plan_name)
    if limit is None:
        raise HTTPException(422, f"Unknown plan: {body.plan_name}. Valid plans: {list(PLAN_LIMITS)}")

    store.plan_name = body.plan_name
    store.plan_shopify_subscription_id = body.shopify_subscription_id
    store.plan_activated_at = datetime.utcnow()
    store.monthly_tryon_limit = limit
    store.onboarding_step = "complete"
    store.onboarding_completed_at = datetime.utcnow()
    db.commit()

    logger.info(f"Billing activated for store {store.store_id}: plan={body.plan_name}")
    return PlanResponse(
        plan_name=store.plan_name,
        monthly_tryon_limit=store.monthly_tryon_limit,
        plan_activated_at=store.plan_activated_at,
        shopify_subscription_id=store.plan_shopify_subscription_id,
    )


@merchant_router.get("/billing/plan", response_model=PlanResponse)
def get_plan(store: Store = Depends(get_store)):
    """Return the store's current plan details."""
    return PlanResponse(
        plan_name=store.plan_name,
        monthly_tryon_limit=store.monthly_tryon_limit,
        plan_activated_at=store.plan_activated_at,
        shopify_subscription_id=store.plan_shopify_subscription_id,
    )


@merchant_router.get("/billing/plans", response_model=PlansResponse)
def get_billing_plans(store: Store = Depends(get_store)):
    """
    Return all available subscription plans with pricing and feature details.
    The store's active plan is marked with is_current=True.
    """
    plans = [
        PlanConfig(
            name=name,
            display_name=cfg["display_name"],
            price_usd=cfg["price_usd"],
            monthly_tryon_limit=cfg["monthly_tryon_limit"],
            features=cfg["features"],
            is_current=(name == store.plan_name),
        )
        for name, cfg in PLAN_CONFIGS.items()
    ]
    return PlansResponse(plans=plans)


@merchant_router.get("/billing/status", response_model=BillingStatusResponse)
async def get_billing_status(store: Store = Depends(get_store)):
    """
    Full billing status combining DB plan data with a live Shopify subscription query.

    - If the store is on the free plan (no subscription ID), Shopify fields are null.
    - If the Shopify call fails (network error, token issue), DB data is returned
      with null Shopify fields rather than erroring — the screen degrades gracefully.
    """
    shopify_status = None
    if store.plan_shopify_subscription_id:
        try:
            svc = ShopifyService(store.shopify_domain, store.shopify_access_token)
            shopify_status = await svc.billing_get_status()
        except Exception as exc:
            logger.warning(f"Shopify billing status call failed for store {store.store_id}: {exc}")

    return BillingStatusResponse(
        plan_name=store.plan_name,
        monthly_tryon_limit=store.monthly_tryon_limit,
        plan_activated_at=store.plan_activated_at,
        shopify_subscription_id=store.plan_shopify_subscription_id,
        subscription_status=shopify_status["status"] if shopify_status else None,
        current_period_end=shopify_status["current_period_end"] if shopify_status else None,
        is_test_subscription=shopify_status["test"] if shopify_status else None,
    )


@merchant_router.post("/billing/create-subscription", response_model=CreateSubscriptionResponse)
async def create_subscription(
    body: CreateSubscriptionRequest,
    store: Store = Depends(get_store),
):
    """
    Create a Shopify recurring subscription for a paid plan.

    Flow:
    1. FastAPI calls Shopify appSubscriptionCreate → gets confirmationUrl
    2. Returns confirmationUrl to Remix
    3. Remix redirects merchant to confirmationUrl (Shopify's approval page)
    4. After merchant approves, Shopify calls returnUrl (Remix route)
    5. Remix callback calls POST /billing/activate to update the DB

    Does NOT update the DB — that happens after merchant approves on Shopify's page.
    """
    if body.plan_name not in PLAN_CONFIGS:
        raise HTTPException(422, f"Unknown plan: {body.plan_name}. Valid plans: {list(PLAN_CONFIGS)}")
    if body.plan_name == "free":
        raise HTTPException(422, "Cannot create a Shopify subscription for the free plan")
    if body.plan_name == store.plan_name:
        raise HTTPException(409, f"Store is already on the '{body.plan_name}' plan")

    cfg = PLAN_CONFIGS[body.plan_name]
    settings = get_settings()
    is_test = settings.APP_ENV == "development"
    is_upgrade = store.plan_name != "free"  # switching between paid plans

    try:
        svc = ShopifyService(store.shopify_domain, store.shopify_access_token)
        result = await svc.billing_create_subscription(
            plan_name=cfg["display_name"],
            price_usd=cfg["price_usd"],
            return_url=body.return_url,
            test=is_test,
            is_upgrade=is_upgrade,
        )
    except Exception as exc:
        logger.error(f"Shopify subscription create failed for store {store.store_id}: {exc}")
        raise HTTPException(502, f"Failed to create Shopify subscription: {exc}")

    logger.info(f"Subscription creation initiated for store {store.store_id}: plan={body.plan_name}")
    return CreateSubscriptionResponse(
        confirmation_url=result["confirmation_url"],
        shopify_subscription_id=result["subscription_id"],
    )


@merchant_router.post("/billing/cancel-subscription", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    store: Store = Depends(get_store),
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
        svc = ShopifyService(store.shopify_domain, store.shopify_access_token)
        await svc.billing_cancel_subscription(store.plan_shopify_subscription_id)
    except Exception as exc:
        logger.error(f"Shopify subscription cancel failed for store {store.store_id}: {exc}")
        raise HTTPException(502, f"Failed to cancel Shopify subscription: {exc}")

    store.plan_name = "free"
    store.monthly_tryon_limit = PLAN_CONFIGS["free"]["monthly_tryon_limit"]
    store.plan_shopify_subscription_id = None
    store.plan_activated_at = None
    db.commit()

    logger.info(f"Subscription cancelled for store {store.store_id}, reverted to free plan")
    return CancelSubscriptionResponse(
        cancelled=True,
        plan_name="free",
        monthly_tryon_limit=PLAN_CONFIGS["free"]["monthly_tryon_limit"],
    )


# ─────────────────────────────────────────────────────────────
# Dashboard — Overview
# ─────────────────────────────────────────────────────────────

@merchant_router.get("/dashboard/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    store: Store = Depends(get_store),
    db: DBSession = Depends(get_db),
):
    """
    Single call that feeds all three sections of the merchant dashboard overview screen.

    Section 1 — theme button status (mirrors onboarding step 5 data)
    Section 2 — try-on usage: count of completed try-ons in last 30 rolling days
    Section 3 — widget scope summary: scope type + counts of enabled IDs
    """
    wc = store.widget_config

    # ── Section 1: theme detection ────────────────────────────
    theme_detected = wc.theme_extension_detected if wc else False
    themes_url = f"https://{store.shopify_domain}/admin/online-store/themes"

    # ── Section 2: try-on usage (rolling 30 days) ─────────────
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

    # ── Section 3: widget scope summary ───────────────────────
    scope_type = wc.scope_type if wc else "all"
    enabled_products_count = len(wc.enabled_product_ids or []) if wc else 0
    enabled_collections_count = len(wc.enabled_collection_ids or []) if wc else 0

    return DashboardOverviewResponse(
        theme_extension_detected=theme_detected,
        themes_url=themes_url,
        tryon_used_30d=tryon_used,
        monthly_tryon_limit=store.monthly_tryon_limit,
        plan_name=store.plan_name,
        scope_type=scope_type,
        enabled_collections_count=enabled_collections_count,
        enabled_products_count=enabled_products_count,
    )


# ─────────────────────────────────────────────────────────────
# Dashboard — Widget Config (GET + PATCH, post-onboarding)
# ─────────────────────────────────────────────────────────────

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
        )
    return WidgetConfigResponse(
        scope_type=wc.scope_type,
        enabled_collection_ids=wc.enabled_collection_ids or [],
        enabled_product_ids=wc.enabled_product_ids or [],
        theme_extension_detected=wc.theme_extension_detected,
        widget_color=wc.widget_color or _DEFAULT_WIDGET_COLOR,
    )


@merchant_router.get("/widget-config", response_model=WidgetConfigResponse)
def get_widget_config(store: Store = Depends(get_store)):
    """
    Return the full widget configuration for the Settings → Custom screen.
    If no config has been saved yet, returns defaults (scope_type='all', widget_color='#FF0000').
    """
    return _widget_config_response(store.widget_config)


@merchant_router.patch("/widget-config", response_model=WidgetConfigResponse)
def update_widget_config(
    body: WidgetConfigUpdateRequest,
    store: Store = Depends(get_store),
    db: DBSession = Depends(get_db),
):
    """
    Partial update of WidgetConfig from the dashboard.
    Unlike POST /onboarding/widget-scope, this does NOT advance onboarding_step —
    safe to call for merchants who have already completed onboarding.

    Used by:
    - Settings → Custom screen Save action (widget_color)
    - "Manage Products and Collections" save action (scope_type + ID lists)
    - "Mark as added" theme detection button (theme_extension_detected)
    """
    if body.scope_type is not None and body.scope_type not in VALID_SCOPE_TYPES:
        raise HTTPException(422, f"scope_type must be one of: {', '.join(sorted(VALID_SCOPE_TYPES))}")

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

    db.commit()
    db.refresh(wc)

    logger.info(f"Widget config updated for store {store.store_id}: {body.model_dump(exclude_none=True)}")
    return _widget_config_response(wc)


# ─────────────────────────────────────────────────────────────
# Widget — check-enabled
# ─────────────────────────────────────────────────────────────

@widget_router.get("/check-enabled", response_model=WidgetCheckResponse)
def check_widget_enabled(
    shopify_product_gid: str = Query(..., description="Shopify product GID, e.g. gid://shopify/Product/123"),
    store: Store = Depends(get_store),
):
    """
    Called by the storefront widget to decide whether to render the try-on button.

    Scope rules:
    - 'all'                   → always enabled
    - 'selected_products'     → enabled only if GID is in enabled_product_ids
    - 'mixed'                 → enabled if GID is in enabled_product_ids (default true if list is empty)
    - 'selected_collections'  → enabled=true (collection membership check deferred to Remix layer)
    - no config yet           → enabled=true (default open)
    """
    wc = store.widget_config
    if wc is None or wc.scope_type == "all":
        return WidgetCheckResponse(enabled=True)

    if wc.scope_type == "selected_products":
        ids = wc.enabled_product_ids
        enabled = bool(ids) and shopify_product_gid in ids
        return WidgetCheckResponse(enabled=enabled)

    if wc.scope_type == "mixed":
        product_ids = wc.enabled_product_ids or []
        enabled = (not product_ids) or (shopify_product_gid in product_ids)
        return WidgetCheckResponse(enabled=enabled)

    # 'selected_collections' — collection membership requires Shopify Admin API
    # (only available in Remix). Return true and let the Remix layer filter further.
    return WidgetCheckResponse(enabled=True)
