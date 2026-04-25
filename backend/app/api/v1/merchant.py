"""
Merchant Admin Endpoints
Covers the 6-step onboarding wizard, billing plan management, and the
widget check-enabled endpoint consumed by the storefront widget.

Merchant routes resolve the active store from Shopify App Bridge auth when present,
with header fallbacks for the current embedded-app migration state.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
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
from app.models.database import (
    Store,
    MerchantOnboarding,
    WidgetConfig,
    MerchantDashboardFeedback,
    TryOn,
    Product,
    Plan,
)
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
    DashboardFeedbackRequest,
    DashboardFeedbackResponse,
    MerchantCollectionResponse,
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
from app.services.customer_login_policy import (
    customer_login_required_message,
    is_customer_logged_in,
    requires_customer_login,
)
from app.services.usage_governance_service import UsageGovernanceService
from app.services.storefront_identity_service import StorefrontIdentityService
from app.services.rate_limit_service import StorefrontRateLimitService

logger = logging.getLogger(__name__)

merchant_router = APIRouter(prefix="/merchant", tags=["Merchant"])
widget_router = APIRouter(prefix="/widget", tags=["Widget"])

INTRO_TRIAL_DAYS = 14
INTRO_TRIAL_CREDITS = 80
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


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


def _extract_shopify_numeric_id(value: str) -> Optional[str]:
    normalized = (value or "").strip()
    if not normalized:
        return None
    if normalized.isdigit():
        return normalized

    match = re.search(r"/(\d+)$", normalized)
    if match:
        return match.group(1)
    return None


def _normalize_shopify_collection_gid(value: str) -> Optional[str]:
    normalized = (value or "").strip()
    if not normalized:
        return None
    if normalized.startswith("gid://shopify/Collection/"):
        return normalized
    numeric = _extract_shopify_numeric_id(normalized)
    if numeric:
        return f"gid://shopify/Collection/{numeric}"
    return normalized


def _expand_product_identifier_variants(values: List[str]) -> set[str]:
    expanded: set[str] = set()
    for raw in values:
        normalized = str(raw or "").strip()
        if not normalized:
            continue
        expanded.add(normalized)
        numeric = _extract_shopify_numeric_id(normalized)
        if numeric:
            expanded.add(numeric)
            expanded.add(f"gid://shopify/Product/{numeric}")
    return expanded


def _normalize_collection_identifier_set(values: List[str]) -> set[str]:
    normalized_set: set[str] = set()
    for raw in values:
        normalized = _normalize_shopify_collection_gid(str(raw or ""))
        if not normalized:
            continue
        normalized_set.add(normalized)
        numeric = _extract_shopify_numeric_id(normalized)
        if numeric:
            normalized_set.add(numeric)
    return normalized_set


def _parse_collection_ids_query(value: Optional[str]) -> tuple[List[str], bool]:
    if value is None:
        return [], False
    parts = [item.strip() for item in value.split(",")]
    parsed = [item for item in parts if item]
    return parsed, True


async def _resolve_product_collection_identifiers(
    *,
    store: Store,
    shopify_product_gid: str,
    provided_collection_ids: List[str],
    provided_collection_ids_present: bool,
) -> List[str]:
    if provided_collection_ids_present:
        return provided_collection_ids

    service = ShopifyService(store.shopify_domain, require_shopify_access_token(store))
    return await service.get_product_collection_ids(shopify_product_gid=shopify_product_gid)


def _build_theme_editor_urls(shop_domain: str) -> tuple[str, str]:
    """
    Build valid Shopify Admin theme editor URLs.

    - theme_editor_url: generic editor entry
    - add_to_theme_url: editor deep link that opens product template and preps app block add flow
    """
    theme_editor_url = f"https://{shop_domain}/admin/themes/current/editor"

    api_key = (get_settings().SHOPIFY_API_KEY or "").strip()
    block_handle = "optimo_vts_widget"
    if not api_key:
        return theme_editor_url, theme_editor_url

    query = urlencode(
        {
            "template": "product",
            "addAppBlockId": f"{api_key}/{block_handle}",
            "target": "mainSection",
        }
    )
    add_to_theme_url = f"{theme_editor_url}?{query}"
    return theme_editor_url, add_to_theme_url


def _sync_billing_lock_flags(store: Store) -> None:
    """
    Keep billing lock fields consistent with current trial state.
    """
    now = datetime.utcnow()

    if store.trial_mode == "intro_free":
        if store.trial_ends_at and store.trial_ends_at < now and not store.billing_lock_reason:
            store.billing_lock_reason = "trial_expired"
            if not store.trial_end_reason:
                store.trial_end_reason = "time_expired"
        return

    # Paid plans and non-intro states should not retain intro lock flags.
    if store.billing_lock_reason in {"trial_expired", "trial_credits_exhausted"}:
        store.billing_lock_reason = None


def _billing_lock_message(lock_reason: Optional[str]) -> Optional[str]:
    if lock_reason == "trial_expired":
        return "Trial ended. Select a plan to re-enable widget and customer try-ons."
    if lock_reason == "trial_credits_exhausted":
        return "Trial credits are exhausted. Select a plan to re-enable widget and customer try-ons."
    return None


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Onboarding â€” Status
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@merchant_router.get("/onboarding/status", response_model=OnboardingStatusResponse)
def get_onboarding_status(
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Return the full onboarding state for the store.
    Called on every app load so the Remix frontend can route to the correct step.
    """
    ob = store.onboarding
    _sync_billing_lock_flags(store)
    wc = store.widget_config

    # Auto-heal stale onboarding records where billing is already active.
    if (
        store.onboarding_step == "plan"
        and not store.billing_lock_reason
        and (
            bool(store.plan_shopify_subscription_id)
            or store.plan_name in {"free_trial", "founding_trial", "starter", "growth", "professional", "scale"}
        )
    ):
        store.onboarding_step = "complete"
        if store.onboarding_completed_at is None:
            store.onboarding_completed_at = datetime.utcnow()

    db.commit()

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
        billing_lock_reason=store.billing_lock_reason,
        trial_mode=store.trial_mode,
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


@merchant_router.get("/collections", response_model=List[MerchantCollectionResponse])
async def list_merchant_collections(
    store: Store = Depends(get_current_merchant_store),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    limit: int = Query(100, ge=1, le=250),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
):
    """
    List Shopify collections for dashboard/onboarding scope selection screens.
    """
    access_token = await resolve_merchant_shopify_access_token(
        store,
        credentials,
        action_label="collection listing",
    )
    svc = ShopifyService(store.shopify_domain, access_token)
    return await svc.list_collections(limit=limit, offset=offset, search=search)


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
    if store.onboarding_step != "complete" and store.onboarding_completed_at is None:
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
    Also returns links to the merchant's theme editor and add-to-theme deep link.
    """
    wc = store.widget_config
    detected = wc.theme_extension_detected if wc else False
    theme_editor_url, add_to_theme_url = _build_theme_editor_urls(store.shopify_domain)
    return ThemeStatusResponse(
        theme_extension_detected=detected,
        themes_url=theme_editor_url,
        add_to_theme_url=add_to_theme_url,
    )


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
        store.trial_mode = "intro_free"
        store.has_used_intro_trial = True
        store.trial_end_reason = None
        store.billing_lock_reason = None
        store.credits_limit = settings.FOUNDING_MERCHANT_CREDITS
        store.trial_ends_at = datetime.utcnow() + timedelta(days=settings.FOUNDING_MERCHANT_TRIAL_DAYS)
        store.plan_shopify_subscription_id = None
        store.plan_activated_at = datetime.utcnow()
        store.billing_interval = None
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


@merchant_router.post("/onboarding/start-free-trial", response_model=OnboardingStepResponse)
def start_intro_free_trial(
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Step 7 option: start 14-day / 80-credit free intro trial with no Shopify billing approval.
    """
    if store.plan_shopify_subscription_id:
        raise HTTPException(409, "A paid subscription is already active for this store.")

    if store.has_used_intro_trial and store.plan_name not in {"free_trial", "founding_trial"}:
        raise HTTPException(409, "Intro trial has already been used for this store.")

    store.plan_name = "free_trial"
    store.trial_mode = "intro_free"
    store.has_used_intro_trial = True
    store.trial_end_reason = None
    store.billing_lock_reason = None
    store.credits_limit = INTRO_TRIAL_CREDITS
    store.trial_ends_at = datetime.utcnow() + timedelta(days=INTRO_TRIAL_DAYS)
    store.plan_shopify_subscription_id = None
    store.plan_activated_at = datetime.utcnow()
    store.billing_interval = None
    store.subscription_status = None
    store.has_usage_billing = False
    store.usage_line_item_id = None
    store.onboarding_step = "complete"
    if store.onboarding_completed_at is None:
        store.onboarding_completed_at = datetime.utcnow()

    db.commit()
    logger.info("Intro free trial started for store %s", store.store_id)
    return OnboardingStepResponse(saved=True, next_step="complete")


@merchant_router.post("/onboarding/complete-from-billing", response_model=OnboardingStepResponse)
def complete_onboarding_from_billing(
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Idempotent completion endpoint for Step 7 actions like:
    - Current Plan
    - Continue with current setup
    """
    _sync_billing_lock_flags(store)
    if store.billing_lock_reason:
        db.commit()
        raise HTTPException(409, _billing_lock_message(store.billing_lock_reason) or "Billing is locked.")

    is_eligible = bool(store.plan_shopify_subscription_id) or store.plan_name in {"founding_trial", "free_trial"}
    if not is_eligible:
        db.commit()
        raise HTTPException(409, "Complete billing selection first to finish onboarding.")

    store.onboarding_step = "complete"
    if store.onboarding_completed_at is None:
        store.onboarding_completed_at = datetime.utcnow()
    db.commit()
    return OnboardingStepResponse(saved=True, next_step="complete")


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

    previous_plan_name = store.plan_name
    previous_trial_mode = store.trial_mode
    full_credits = plan.credits_monthly if body.billing_interval == "monthly" else plan.credits_annual
    applied_trial_days = 0 if store.has_used_intro_trial else int(plan.trial_days or 0)

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
    if applied_trial_days > 0:
        # Trial is always applied. During trial, grant trial_credits (80); full credits after.
        store.credits_limit = plan.trial_credits if plan.trial_credits else full_credits
        store.trial_ends_at = datetime.utcnow() + timedelta(days=applied_trial_days)
        store.trial_mode = "plan_trial"
        store.trial_end_reason = None
    else:
        store.credits_limit = full_credits
        store.trial_ends_at = None
        store.trial_mode = "none"
        if previous_trial_mode == "intro_free":
            store.trial_end_reason = "converted_to_plan"

    if previous_plan_name in {"free_trial", "founding_trial"}:
        store.trial_end_reason = "converted_to_plan"
    store.billing_lock_reason = None

    store.onboarding_step = "complete"
    if store.onboarding_completed_at is None:
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
    _sync_billing_lock_flags(store)
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
            if store.trial_mode == "plan_trial":
                store.trial_mode = "none"
                if not store.trial_end_reason:
                    store.trial_end_reason = "time_expired"

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
        trial_mode=store.trial_mode,
        trial_end_reason=store.trial_end_reason,
        billing_lock_reason=store.billing_lock_reason,
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
    trial_days = 0 if store.has_used_intro_trial else int(plan.trial_days or 0)

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
    store.trial_mode = "none"
    store.trial_end_reason = "manual"
    store.billing_lock_reason = None
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
    Single call that feeds the merchant dashboard overview screen.

    Section 1 â€” theme button status (mirrors onboarding step 5 data)
    Section 2 â€” try-on usage: count of completed try-ons in last 30 rolling days
    Section 3 â€” widget scope summary: scope type + counts of enabled IDs
    Section 4 â€” whether one-time merchant feedback has been submitted
    """
    wc = store.widget_config

    # â”€â”€ Section 1: theme detection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    theme_detected = wc.theme_extension_detected if wc else False
    themes_url, add_to_theme_url = _build_theme_editor_urls(store.shopify_domain)

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
    feedback_submitted = bool(store.dashboard_feedback)

    return DashboardOverviewResponse(
        theme_extension_detected=theme_detected,
        themes_url=themes_url,
        add_to_theme_url=add_to_theme_url,
        tryon_used_30d=tryon_used,
        credits_limit=store.credits_limit,
        plan_name=store.plan_name,
        scope_type=scope_type,
        enabled_collections_count=enabled_collections_count,
        enabled_products_count=enabled_products_count,
        feedback_submitted=feedback_submitted,
        billing_lock_reason=store.billing_lock_reason,
    )


@merchant_router.post("/dashboard/feedback", response_model=DashboardFeedbackResponse)
def submit_dashboard_feedback(
    body: DashboardFeedbackRequest,
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Save one-time merchant feedback from the dashboard overview.
    """
    if store.dashboard_feedback is not None:
        raise HTTPException(409, "Dashboard feedback has already been submitted for this store.")

    improvement_text = (body.improvement_text or "").strip()
    if body.rating < 5 and not improvement_text:
        raise HTTPException(422, "improvement_text is required when rating is below 5.0")

    feedback = MerchantDashboardFeedback(
        store_id=store.store_id,
        rating=body.rating,
        improvement_text=None if body.rating == 5 else improvement_text,
        submitted_at=datetime.utcnow(),
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return DashboardFeedbackResponse(
        saved=True,
        rating=feedback.rating,
        submitted_at=feedback.submitted_at,
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Dashboard â€” Widget Config (GET + PATCH, post-onboarding)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _normalize_hex_color(value: Optional[str]) -> Optional[str]:
    candidate = (value or "").strip()
    if not candidate:
        return None
    if not _HEX_COLOR_RE.fullmatch(candidate):
        return None
    return candidate.upper()


def _widget_config_response(wc: Optional[WidgetConfig]) -> WidgetConfigResponse:
    """Build WidgetConfigResponse, applying code-level defaults for null DB values."""
    if wc is None:
        return WidgetConfigResponse(
            scope_type="all",
            enabled_collection_ids=[],
            enabled_product_ids=[],
            theme_extension_detected=False,
            widget_color="",
            weekly_tryon_limit=get_settings().WEEKLY_TRYON_LIMIT_DEFAULT,
        )
    return WidgetConfigResponse(
        scope_type=wc.scope_type,
        enabled_collection_ids=wc.enabled_collection_ids or [],
        enabled_product_ids=wc.enabled_product_ids or [],
        theme_extension_detected=wc.theme_extension_detected,
        widget_color=_normalize_hex_color(wc.widget_color) or "",
        weekly_tryon_limit=wc.weekly_tryon_limit,
    )


@merchant_router.get("/widget-config", response_model=WidgetConfigResponse)
def get_widget_config(store: Store = Depends(get_current_merchant_store)):
    """
    Return the full widget configuration for the Settings â†’ Custom screen.
    If no config has been saved yet, returns defaults (scope_type='all', widget_color='').
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
    if body.weekly_tryon_limit is not None and not (5 <= body.weekly_tryon_limit <= 100):
        raise HTTPException(422, "weekly_tryon_limit must be between 5 and 100")

    normalized_widget_color: Optional[str] = None
    widget_color_was_provided = body.widget_color is not None
    if body.widget_color is not None:
        raw_widget_color = (body.widget_color or "").strip()
        if not raw_widget_color:
            normalized_widget_color = ""
        else:
            normalized_widget_color = _normalize_hex_color(raw_widget_color)
            if normalized_widget_color is None:
                raise HTTPException(422, "widget_color must be a valid hex color like #FF0000")

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
    if widget_color_was_provided:
        wc.widget_color = normalized_widget_color or None
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
async def check_widget_enabled(
    shopify_product_gid: str = Query(..., description="Shopify product GID, e.g. gid://shopify/Product/123"),
    shopify_collection_ids: Optional[str] = Query(
        None,
        description="Optional comma-separated Shopify collection IDs/GIDs for the current product.",
    ),
    x_logged_in_customer_id: Optional[str] = Header(None, alias="X-Logged-In-Customer-Id"),
    store: Store = Depends(get_public_store),
    db: DBSession = Depends(get_db),
):
    """
    Called by the storefront widget to decide whether to render the try-on button.

    Scope rules:
    - 'all'                  -> always enabled
    - 'selected_products'    -> enabled only when product ID/GID is explicitly selected
    - 'selected_collections' -> enabled only when product belongs to selected collections
    - 'mixed'                -> enabled when either product or collection selection matches
    - no config yet          -> enabled=true (default open)

    Billing gate: widget is disabled whenever billing lock is active
    (expired/exhausted intro or founding trial).
    """
    customer_logged_in = is_customer_logged_in(x_logged_in_customer_id)
    login_required = requires_customer_login(store)
    login_message = customer_login_required_message() if login_required else None
    widget_color = _normalize_hex_color(store.widget_config.widget_color if store.widget_config else None) or ""

    def _response(enabled: bool) -> WidgetCheckResponse:
        return WidgetCheckResponse(
            enabled=enabled,
            widget_color=widget_color,
            customer_login_required=login_required,
            customer_logged_in=customer_logged_in,
            login_message=login_message,
        )

    lock_before = store.billing_lock_reason
    trial_end_before = store.trial_end_reason
    _sync_billing_lock_flags(store)
    if lock_before != store.billing_lock_reason or trial_end_before != store.trial_end_reason:
        db.commit()
    if store.billing_lock_reason:
        return _response(False)

    normalized_gid = _normalize_shopify_product_gid(shopify_product_gid)
    normalized_numeric = _extract_shopify_numeric_id(normalized_gid)
    wc = store.widget_config
    if wc is None or wc.scope_type == "all":
        return _response(True)

    configured_product_ids = _expand_product_identifier_variants(wc.enabled_product_ids or [])
    configured_collection_ids = _normalize_collection_identifier_set(wc.enabled_collection_ids or [])
    request_collection_ids, request_collection_ids_present = _parse_collection_ids_query(shopify_collection_ids)

    def _product_match() -> bool:
        if not configured_product_ids:
            return False
        if normalized_gid in configured_product_ids:
            return True
        if normalized_numeric and normalized_numeric in configured_product_ids:
            return True
        return False

    async def _collection_match() -> bool:
        if not configured_collection_ids:
            return False
        try:
            resolved_collection_ids = await _resolve_product_collection_identifiers(
                store=store,
                shopify_product_gid=normalized_gid,
                provided_collection_ids=request_collection_ids,
                provided_collection_ids_present=request_collection_ids_present,
            )
        except Exception as exc:
            logger.warning(
                "Collection membership resolution failed for store %s and product %s: %s",
                store.store_id,
                normalized_gid,
                exc,
            )
            return False

        product_collection_ids = _normalize_collection_identifier_set(resolved_collection_ids)
        if not product_collection_ids:
            return False
        return bool(configured_collection_ids.intersection(product_collection_ids))

    if wc.scope_type == "selected_products":
        return _response(_product_match())

    if wc.scope_type == "selected_collections":
        return _response(await _collection_match())

    if wc.scope_type == "mixed":
        has_any_scope = bool(configured_product_ids or configured_collection_ids)
        enabled = has_any_scope and (_product_match() or await _collection_match())
        return _response(enabled)

    return _response(False)


@widget_router.post("/theme-detected")
def mark_theme_extension_detected(
    store: Store = Depends(get_public_store),
    db: DBSession = Depends(get_db),
):
    """
    Mark theme extension as detected from storefront/theme-editor runtime.

    The app block script pings this endpoint when it loads in Shopify design mode.
    """
    lock_before = store.billing_lock_reason
    trial_end_before = store.trial_end_reason
    _sync_billing_lock_flags(store)
    if lock_before != store.billing_lock_reason or trial_end_before != store.trial_end_reason:
        db.commit()
    wc = store.widget_config
    if wc is None:
        wc = WidgetConfig(store_id=store.store_id)
        db.add(wc)

    if not wc.theme_extension_detected:
        wc.theme_extension_detected = True
        logger.info("Theme extension runtime detection set for store %s", store.store_id)

    db.commit()
    return {"detected": True}


@widget_router.post("/sessions", response_model=SessionResponse)
def create_widget_session(
    body: WidgetSessionCreateRequest,
    request: Request,
    x_logged_in_customer_id: Optional[str] = Header(None, alias="X-Logged-In-Customer-Id"),
    x_optimo_anon_id: Optional[str] = Header(None, alias="X-Optimo-Anon-Id"),
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

    StorefrontRateLimitService(db).enforce(
        request=request,
        store=store,
        endpoint_key="widget_sessions",
        limit_per_minute=get_settings().RATE_LIMIT_WIDGET_SESSIONS_PER_MINUTE,
    )

    identity = StorefrontIdentityService(db)
    resolved_subject_identifier = identity.resolve_subject_identifier(
        store=store,
        logged_in_customer_id=x_logged_in_customer_id,
        anon_id=x_optimo_anon_id,
    )

    try:
        return create_or_resume_session_for_product(
            product=product,
            store=store,
            user_identifier=resolved_subject_identifier or body.user_identifier,
            db=db,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Widget session creation failed: %s", exc, exc_info=True)
        db.rollback()
        raise HTTPException(500, f"Failed to create widget session: {exc}")

