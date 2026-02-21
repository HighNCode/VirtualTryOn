"""
Merchant Admin Endpoints
Covers the 6-step onboarding wizard, billing plan management, and the
widget check-enabled endpoint consumed by the storefront widget.

All merchant endpoints require the X-Store-ID header.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from app.core.database import get_db
from app.models.database import Store, MerchantOnboarding, WidgetConfig
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
)

logger = logging.getLogger(__name__)

merchant_router = APIRouter(prefix="/merchant", tags=["Merchant"])
widget_router = APIRouter(prefix="/widget", tags=["Widget"])

PLAN_LIMITS = {
    "free": 10,
    "starter": 100,
}


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
