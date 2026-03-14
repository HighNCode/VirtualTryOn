"""
Analytics Endpoints

Public router  → /api/v1/analytics
  POST /analytics/events         — Widget-facing event ingestion (X-Store-ID header)

Merchant router → /api/v1/merchant/analytics
  GET  /merchant/analytics/standard — Standard analytics tab (merchant store context)
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Set

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, cast, Date as SADate
from sqlalchemy.orm import Session as DBSession

from app.api.store_context import get_current_merchant_store
from app.core.database import get_db
from app.models.database import AnalyticsEvent, Store, TryOn, Product
from app.models.schemas import (
    AnalyticsEventCreate,
    AnalyticsEventSaved,
    StandardAnalyticsResponse,
    TopProductEntry,
    TrendEntry,
)
from app.services.shopify_service import ShopifyService

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Valid event types (funnel-oriented)
# ─────────────────────────────────────────────────────────────

VALID_EVENT_TYPES: Set[str] = {
    "widget_opened",
    "photo_captured",
    "measurement_completed",
    "size_recommended",
    "try_on_generated",
    "try_on_viewed",
    "size_selected",
    "added_to_cart",
}

# ─────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────

analytics_public_router = APIRouter(prefix="/analytics", tags=["Analytics"])
analytics_merchant_router = APIRouter(prefix="/merchant/analytics", tags=["Analytics"])


# ─────────────────────────────────────────────────────────────
def get_store_by_header(
    x_store_id: str = Header(..., alias="X-Store-ID"),
    db: DBSession = Depends(get_db),
) -> Store:
    """Widget-facing dependency — X-Store-ID header."""
    store = db.query(Store).filter_by(store_id=x_store_id).first()
    if not store:
        raise HTTPException(404, "Store not found")
    return store


# ─────────────────────────────────────────────────────────────
# POST /analytics/events  (public — widget-facing)
# ─────────────────────────────────────────────────────────────

@analytics_public_router.post("/events", response_model=AnalyticsEventSaved)
def ingest_event(
    body: AnalyticsEventCreate,
    store: Store = Depends(get_store_by_header),
    db: DBSession = Depends(get_db),
):
    """
    Ingest a funnel event from the storefront widget.

    Validates `event_type` against the allowed set and persists the event.
    `session_id` and `event_data` are optional but recommended for attribution.
    """
    if body.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid event_type '{body.event_type}'. "
                   f"Allowed: {sorted(VALID_EVENT_TYPES)}",
        )

    event = AnalyticsEvent(
        store_id=store.store_id,
        session_id=body.session_id,
        event_type=body.event_type,
        event_data=body.event_data,
    )
    db.add(event)
    db.commit()
    return AnalyticsEventSaved(saved=True)


# ─────────────────────────────────────────────────────────────
# GET /merchant/analytics/standard  (merchant auth)
# ─────────────────────────────────────────────────────────────

@analytics_merchant_router.get("/standard", response_model=StandardAnalyticsResponse)
async def get_standard_analytics(
    period: int = Query(30, description="Look-back window in days: 7, 30, or 90"),
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Standard analytics tab for the merchant dashboard.

    Metrics:
    - Engagement: widget opens, unique users, total try-ons, credits used, add-to-cart events
    - Conversions: cross-referenced with Shopify Orders API (null if Shopify call fails)
    - Returns: orders with at least one refund (null if Shopify call fails)
    - Top 5 products: sorted by conversion_rate DESC
    - Daily trend: per-calendar-day try-on count for the period (line chart)
    """
    if period not in (7, 30, 90):
        raise HTTPException(422, "period must be 7, 30, or 90")

    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=period)
    store_id = store.store_id

    # ── Engagement metrics from analytics_events ──────────────

    base_q = (
        db.query(AnalyticsEvent)
        .filter(
            AnalyticsEvent.store_id == store_id,
            AnalyticsEvent.created_at >= period_start,
        )
    )

    widget_opens = (
        base_q.filter(AnalyticsEvent.event_type == "widget_opened").count()
    )

    unique_users = (
        db.query(func.count(func.distinct(AnalyticsEvent.session_id)))
        .filter(
            AnalyticsEvent.store_id == store_id,
            AnalyticsEvent.event_type == "widget_opened",
            AnalyticsEvent.created_at >= period_start,
            AnalyticsEvent.session_id.isnot(None),
        )
        .scalar() or 0
    )

    add_to_cart_count = (
        base_q.filter(AnalyticsEvent.event_type == "added_to_cart").count()
    )

    # ── Try-on metrics from try_ons table ─────────────────────

    total_try_ons = (
        db.query(func.count(TryOn.try_on_id))
        .join(Product, TryOn.product_id == Product.product_id)
        .filter(
            Product.store_id == store_id,
            TryOn.processing_status == "completed",
            TryOn.created_at >= period_start,
        )
        .scalar() or 0
    )

    credits_used = total_try_ons * 4  # 1 try-on = 4 credits

    # ── Top products ──────────────────────────────────────────
    # Step 1: try_on_count per shopify_product_id

    tryons_per_product_rows = (
        db.query(
            Product.shopify_product_id,
            Product.title,
            func.count(TryOn.try_on_id).label("try_on_count"),
        )
        .join(TryOn, TryOn.product_id == Product.product_id)
        .filter(
            Product.store_id == store_id,
            TryOn.processing_status == "completed",
            TryOn.created_at >= period_start,
        )
        .group_by(Product.shopify_product_id, Product.title)
        .all()
    )

    tryons_map: dict = {
        row.shopify_product_id: {"title": row.title, "try_on_count": row.try_on_count}
        for row in tryons_per_product_rows
    }

    # Step 2: cart_count per shopify_product_id from event_data->>'product_id'
    # Uses PostgreSQL JSONB extraction; product_id stored as full GID or bare numeric
    cart_events = (
        base_q.filter(AnalyticsEvent.event_type == "added_to_cart").all()
    )

    carts_map: dict = {}
    for evt in cart_events:
        if not evt.event_data:
            continue
        pid = evt.event_data.get("product_id")
        if pid:
            # Normalise: strip GID prefix if present
            pid_str = str(pid).split("/")[-1]
            carts_map[pid_str] = carts_map.get(pid_str, 0) + 1

    # Step 3: merge, compute conversion_rate, sort, limit 5
    top_products_raw = []
    all_product_ids = set(tryons_map.keys()) | set(carts_map.keys())
    for pid in all_product_ids:
        entry = tryons_map.get(pid, {})
        title = entry.get("title") or "Unknown"
        try_on_count = entry.get("try_on_count", 0)
        cart_count = carts_map.get(pid, 0)
        conversion_rate = (cart_count / try_on_count * 100.0) if try_on_count > 0 else 0.0
        top_products_raw.append(
            TopProductEntry(
                shopify_product_id=pid,
                title=title,
                try_on_count=try_on_count,
                cart_count=cart_count,
                conversion_rate=round(conversion_rate, 2),
            )
        )

    top_products_raw.sort(key=lambda x: x.conversion_rate, reverse=True)
    top_products = top_products_raw[:5]

    # ── Daily trend (line chart) ───────────────────────────────

    daily_rows = (
        db.query(
            cast(TryOn.created_at, SADate).label("day"),
            func.count(TryOn.try_on_id).label("try_ons"),
        )
        .join(Product, TryOn.product_id == Product.product_id)
        .filter(
            Product.store_id == store_id,
            TryOn.processing_status == "completed",
            TryOn.created_at >= period_start,
        )
        .group_by(cast(TryOn.created_at, SADate))
        .all()
    )

    date_map: dict = {row.day: row.try_ons for row in daily_rows}
    trend: List[TrendEntry] = []
    for i in range(period):
        day = (period_start + timedelta(days=i)).date()
        trend.append(TrendEntry(date=day.isoformat(), try_ons=date_map.get(day, 0)))

    # ── Shopify cross-reference for conversions ───────────────

    conversions: Optional[int] = None
    conversion_rate_pct: Optional[float] = None
    revenue_impact: Optional[float] = None
    return_count: Optional[int] = None

    try:
        if store.shopify_access_token and store.shopify_domain:
            # Collect customer_ids from added_to_cart events in the period
            customer_ids: List[str] = []
            for evt in cart_events:
                if evt.event_data:
                    cid = evt.event_data.get("customer_id")
                    if cid:
                        customer_ids.append(str(cid))

            svc = ShopifyService(
                shop_domain=store.shopify_domain,
                access_token=store.shopify_access_token,
            )

            # Attribution window: period_start, Shopify returns orders in that window
            orders_result = await svc.get_orders_with_refunds(
                since=period_start,
                customer_ids=customer_ids if customer_ids else None,
            )

            customer_id_set = set(customer_ids)
            matched_orders = [
                o for o in orders_result["orders"]
                if o["customer_id"] and o["customer_id"] in customer_id_set
            ] if customer_ids else orders_result["orders"]

            conversions = len(matched_orders)
            revenue_impact = round(
                sum(float(o["total_price"]) for o in matched_orders), 2
            )
            return_count = orders_result["return_count"]

            if widget_opens > 0:
                conversion_rate_pct = round(conversions / widget_opens * 100.0, 2)

    except Exception as exc:
        logger.warning("Shopify orders fetch failed; conversion metrics will be null: %s", exc)

    return StandardAnalyticsResponse(
        period_days=period,
        period_start=period_start,
        period_end=period_end,
        widget_opens=widget_opens,
        unique_users=unique_users,
        total_try_ons=total_try_ons,
        credits_used=credits_used,
        add_to_cart_count=add_to_cart_count,
        conversions=conversions,
        conversion_rate=conversion_rate_pct,
        revenue_impact=revenue_impact,
        return_count=return_count,
        top_products=top_products,
        trend=trend,
    )
