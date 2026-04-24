"""
Analytics Endpoints

Public router  -> /api/v1/analytics
  POST /analytics/events          - Widget-facing event ingestion (storefront proxy)

Merchant router -> /api/v1/merchant/analytics
  GET  /merchant/analytics/standard - Merchant analytics dashboard payload
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.api.store_context import get_current_merchant_store, get_public_store
from app.core.database import get_db
from app.models.database import (
    AnalyticsEvent,
    Product,
    Session,
    Store,
    StoreIdentityLink,
    TryOn,
    UserMeasurement,
)
from app.models.schemas import (
    AnalyticsEventCreate,
    AnalyticsEventSaved,
    PerformanceTrendEntry,
    StandardAnalyticsResponse,
    TopPerformingProductEntry,
    TopProductEntry,
    TrendEntry,
)
from app.services.shopify_service import ShopifyService

logger = logging.getLogger(__name__)

ATTRIBUTION_WINDOW_DAYS = 7
TOP_PRODUCTS_LIMIT = 5

VALID_EVENT_TYPES: Set[str] = {
    "product_viewed",
    "widget_opened",
    "photo_captured",
    "measurement_completed",
    "size_recommended",
    "try_on_generated",
    "try_on_viewed",
    "size_selected",
    "added_to_cart",
    # Non-funnel diagnostics from widget-side resilience handlers.
    "result_image_load_failed",
}

analytics_public_router = APIRouter(prefix="/analytics", tags=["Analytics"])
analytics_merchant_router = APIRouter(prefix="/merchant/analytics", tags=["Analytics"])


def _extract_numeric_id(value: Any) -> Optional[str]:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    if candidate.isdigit():
        return candidate
    if "/" in candidate:
        tail = candidate.rsplit("/", 1)[-1]
        return tail if tail.isdigit() else None
    return None


def _parse_shopify_datetime(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _build_refunded_qty_map(refunds: Any) -> Dict[str, int]:
    refunded: Dict[str, int] = defaultdict(int)
    for refund in refunds or []:
        for refund_line_item in (refund or {}).get("refund_line_items") or []:
            quantity = int((refund_line_item or {}).get("quantity") or 0)
            if quantity <= 0:
                continue
            line_item_id = (refund_line_item or {}).get("line_item_id")
            if not line_item_id:
                line_item_id = ((refund_line_item or {}).get("line_item") or {}).get("id")
            if line_item_id:
                refunded[str(line_item_id)] += quantity
    return refunded


def _build_anon_to_customer_map(db: DBSession, store_id: Any) -> Dict[str, str]:
    rows = (
        db.query(
            StoreIdentityLink.anon_identifier,
            StoreIdentityLink.customer_identifier,
            StoreIdentityLink.updated_at,
        )
        .filter(StoreIdentityLink.store_id == store_id)
        .order_by(StoreIdentityLink.updated_at.desc())
        .all()
    )
    mapping: Dict[str, str] = {}
    for row in rows:
        anon = str(row.anon_identifier or "").strip().lower()
        customer = str(row.customer_identifier or "").strip()
        if anon and customer and anon not in mapping:
            mapping[anon] = customer
    return mapping


def _canonicalize_subject(subject: Optional[str], anon_to_customer: Dict[str, str]) -> Optional[str]:
    raw = str(subject or "").strip()
    if not raw:
        return None
    if raw.startswith("shopify:"):
        customer_id = raw.split(":", 1)[1].strip()
        return f"shopify:{customer_id}" if customer_id else None
    if raw.startswith("anon:"):
        anon_id = raw.split(":", 1)[1].strip().lower()
        if not anon_id:
            return None
        mapped_customer = anon_to_customer.get(anon_id)
        if mapped_customer:
            return f"shopify:{mapped_customer}"
        return f"anon:{anon_id}"
    if raw.isdigit():
        return f"shopify:{raw}"
    return raw


def _conversion_rate(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100.0, 2)


@analytics_public_router.post("/events", response_model=AnalyticsEventSaved)
def ingest_event(
    body: AnalyticsEventCreate,
    store: Store = Depends(get_public_store),
    db: DBSession = Depends(get_db),
):
    """
    Ingest a widget event.
    `session_id` is optional to support page-view level events.
    """
    if body.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid event_type '{body.event_type}'. Allowed: {sorted(VALID_EVENT_TYPES)}",
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


@analytics_merchant_router.get("/standard", response_model=StandardAnalyticsResponse)
async def get_standard_analytics(
    period: int = Query(30, description="Look-back window in days: 7, 30, or 90"),
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    if period not in (7, 30, 90):
        raise HTTPException(422, "period must be 7, 30, or 90")

    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=period)
    previous_period_start = period_start - timedelta(days=period)
    store_id = store.store_id

    base_event_q = (
        db.query(AnalyticsEvent)
        .filter(
            AnalyticsEvent.store_id == store_id,
            AnalyticsEvent.created_at >= period_start,
            AnalyticsEvent.created_at < period_end,
        )
    )

    widget_opens = base_event_q.filter(AnalyticsEvent.event_type == "widget_opened").count()
    product_views = base_event_q.filter(AnalyticsEvent.event_type == "product_viewed").count()
    add_to_cart_count = base_event_q.filter(AnalyticsEvent.event_type == "added_to_cart").count()
    widget_click_rate = _conversion_rate(widget_opens, product_views)

    unique_users = (
        db.query(func.count(func.distinct(AnalyticsEvent.session_id)))
        .filter(
            AnalyticsEvent.store_id == store_id,
            AnalyticsEvent.event_type == "widget_opened",
            AnalyticsEvent.created_at >= period_start,
            AnalyticsEvent.created_at < period_end,
            AnalyticsEvent.session_id.isnot(None),
        )
        .scalar() or 0
    )

    anon_to_customer = _build_anon_to_customer_map(db, store_id)

    subject_rows = (
        db.query(Session.user_identifier)
        .join(AnalyticsEvent, AnalyticsEvent.session_id == Session.session_id)
        .filter(
            AnalyticsEvent.store_id == store_id,
            AnalyticsEvent.event_type == "widget_opened",
            AnalyticsEvent.created_at >= period_start,
            AnalyticsEvent.created_at < period_end,
            Session.user_identifier.isnot(None),
        )
        .distinct()
        .all()
    )
    canonical_subjects: Set[str] = set()
    for row in subject_rows:
        canonical = _canonicalize_subject(row.user_identifier, anon_to_customer)
        if canonical:
            canonical_subjects.add(canonical)

    active_users = sum(1 for subject in canonical_subjects if subject.startswith("shopify:"))
    anonymous_users = sum(1 for subject in canonical_subjects if subject.startswith("anon:"))

    tryon_rows = (
        db.query(
            TryOn.try_on_id,
            TryOn.created_at,
            Product.shopify_product_id.label("shopify_product_id"),
            Product.title.label("product_title"),
            Session.user_identifier.label("subject_identifier"),
        )
        .join(Product, TryOn.product_id == Product.product_id)
        .outerjoin(UserMeasurement, UserMeasurement.measurement_id == TryOn.measurement_id)
        .outerjoin(Session, Session.session_id == UserMeasurement.session_id)
        .filter(
            Product.store_id == store_id,
            TryOn.processing_status == "completed",
            TryOn.created_at >= previous_period_start,
            TryOn.created_at < period_end,
        )
        .all()
    )

    tryon_sessions_by_product: Dict[str, int] = defaultdict(int)
    product_titles: Dict[str, str] = {}
    trend_counts: Dict[date, int] = defaultdict(int)
    customer_tryons_by_bucket: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        "current": defaultdict(list),
        "previous": defaultdict(list),
    }

    try_on_sessions = 0
    for row in tryon_rows:
        created_at = row.created_at
        if not created_at:
            continue
        bucket: Optional[str] = None
        if period_start <= created_at < period_end:
            bucket = "current"
        elif previous_period_start <= created_at < period_start:
            bucket = "previous"
        if not bucket:
            continue

        product_id = _extract_numeric_id(row.shopify_product_id)
        if not product_id:
            continue

        title = str(row.product_title or "Unknown")
        product_titles[product_id] = title

        if bucket == "current":
            try_on_sessions += 1
            tryon_sessions_by_product[product_id] += 1
            trend_counts[created_at.date()] += 1

        canonical_subject = _canonicalize_subject(row.subject_identifier, anon_to_customer)
        if canonical_subject and canonical_subject.startswith("shopify:"):
            customer_tryons_by_bucket[bucket][canonical_subject].append(
                {
                    "created_at": created_at,
                    "product_id": product_id,
                }
            )

    for bucket_map in customer_tryons_by_bucket.values():
        for subject in list(bucket_map.keys()):
            bucket_map[subject].sort(key=lambda item: item["created_at"])

    trend: List[TrendEntry] = []
    performance_trend: List[PerformanceTrendEntry] = []
    for offset in range(period):
        day = (period_start + timedelta(days=offset)).date()
        count = trend_counts.get(day, 0)
        trend.append(TrendEntry(date=day.isoformat(), try_ons=count))
        performance_trend.append(PerformanceTrendEntry(date=day.isoformat(), try_on_sessions=count))

    total_try_ons = try_on_sessions
    credits_used = total_try_ons * 4

    conversions: Optional[int] = 0
    conversion_rate_pct: Optional[float] = _conversion_rate(0, try_on_sessions) if try_on_sessions > 0 else None
    revenue_impact: Optional[float] = 0.0
    return_count: Optional[int] = 0
    return_reduction: Optional[float] = None
    commerce_metrics_resolved = False

    attributed_orders_by_product: Dict[str, Set[str]] = defaultdict(set)
    attributed_units_by_product: Dict[str, int] = defaultdict(int)
    returned_units_by_product: Dict[str, int] = defaultdict(int)
    revenue_by_product: Dict[str, float] = defaultdict(float)

    customer_ids: Set[str] = set()
    for bucket_name in ("current", "previous"):
        for canonical_subject in customer_tryons_by_bucket[bucket_name].keys():
            customer_id = canonical_subject.split(":", 1)[1].strip()
            if customer_id:
                customer_ids.add(customer_id)

    if store.shopify_access_token and store.shopify_domain:
        if not customer_ids:
            commerce_metrics_resolved = True
        else:
            try:
                orders_result = await ShopifyService(
                    shop_domain=store.shopify_domain,
                    access_token=store.shopify_access_token,
                ).get_orders_with_refunds(
                    since=previous_period_start,
                    customer_ids=sorted(customer_ids),
                )

                bucket_metrics: Dict[str, Dict[str, Any]] = {
                    "current": {
                        "order_ids": set(),
                        "attributed_units": 0,
                        "returned_units": 0,
                        "revenue": 0.0,
                    },
                    "previous": {
                        "order_ids": set(),
                        "attributed_units": 0,
                        "returned_units": 0,
                        "revenue": 0.0,
                    },
                }

                attribution_window = timedelta(days=ATTRIBUTION_WINDOW_DAYS)

                for order in orders_result.get("orders", []):
                    order_id = str(order.get("id", "")).strip()
                    order_customer_id = str(order.get("customer_id", "")).strip()
                    order_created_at = _parse_shopify_datetime(order.get("created_at"))
                    if not order_id or not order_customer_id or not order_created_at:
                        continue

                    order_bucket: Optional[str] = None
                    if period_start <= order_created_at < period_end:
                        order_bucket = "current"
                    elif previous_period_start <= order_created_at < period_start:
                        order_bucket = "previous"
                    if not order_bucket:
                        continue

                    subject_key = f"shopify:{order_customer_id}"
                    candidates = customer_tryons_by_bucket[order_bucket].get(subject_key) or []
                    if not candidates:
                        continue

                    refunded_qty_map = _build_refunded_qty_map(order.get("refunds"))

                    for line_item in order.get("line_items") or []:
                        product_id = _extract_numeric_id((line_item or {}).get("product_id"))
                        if not product_id:
                            continue

                        quantity = int((line_item or {}).get("quantity") or 0)
                        if quantity <= 0:
                            continue

                        matched_candidate: Optional[Dict[str, Any]] = None
                        for candidate in reversed(candidates):
                            candidate_created = candidate["created_at"]
                            if candidate["product_id"] != product_id:
                                continue
                            if candidate_created > order_created_at:
                                continue
                            if order_created_at - candidate_created > attribution_window:
                                continue
                            matched_candidate = candidate
                            break
                        if not matched_candidate:
                            continue

                        price = float((line_item or {}).get("price") or 0.0)
                        total_discount = float((line_item or {}).get("total_discount") or 0.0)
                        line_revenue = max((price * quantity) - total_discount, 0.0)

                        line_item_id = str((line_item or {}).get("id") or "").strip()
                        returned_qty = 0
                        if line_item_id:
                            returned_qty = min(quantity, refunded_qty_map.get(line_item_id, 0))

                        metrics = bucket_metrics[order_bucket]
                        metrics["order_ids"].add(order_id)
                        metrics["attributed_units"] += quantity
                        metrics["returned_units"] += returned_qty
                        metrics["revenue"] += line_revenue

                        if order_bucket == "current":
                            attributed_orders_by_product[product_id].add(order_id)
                            attributed_units_by_product[product_id] += quantity
                            returned_units_by_product[product_id] += returned_qty
                            revenue_by_product[product_id] += line_revenue
                            if product_id not in product_titles:
                                product_titles[product_id] = str((line_item or {}).get("title") or "Unknown")

                current_metrics = bucket_metrics["current"]
                previous_metrics = bucket_metrics["previous"]

                conversions = len(current_metrics["order_ids"])
                conversion_rate_pct = _conversion_rate(conversions, try_on_sessions)
                revenue_impact = round(float(current_metrics["revenue"]), 2)
                return_count = int(current_metrics["returned_units"])

                current_return_rate = _conversion_rate(
                    int(current_metrics["returned_units"]),
                    int(current_metrics["attributed_units"]),
                )
                previous_return_rate = _conversion_rate(
                    int(previous_metrics["returned_units"]),
                    int(previous_metrics["attributed_units"]),
                )
                if (
                    current_return_rate is not None
                    and previous_return_rate is not None
                    and previous_return_rate > 0
                ):
                    return_reduction = round(
                        ((previous_return_rate - current_return_rate) / previous_return_rate) * 100.0,
                        2,
                    )

                commerce_metrics_resolved = True
            except Exception as exc:
                logger.warning("Shopify orders fetch/attribution failed; commerce metrics are null: %s", exc)
                conversions = None
                conversion_rate_pct = None
                revenue_impact = None
                return_count = None
                return_reduction = None
                commerce_metrics_resolved = False
    else:
        conversions = None
        conversion_rate_pct = None
        revenue_impact = None
        return_count = None
        return_reduction = None
        commerce_metrics_resolved = False

    top_performing_rows: List[TopPerformingProductEntry] = []
    legacy_top_rows: List[TopProductEntry] = []
    all_current_product_ids = set(tryon_sessions_by_product.keys())

    for product_id in all_current_product_ids:
        product_tryons = tryon_sessions_by_product.get(product_id, 0)
        product_title = product_titles.get(product_id, "Unknown")
        product_orders = len(attributed_orders_by_product.get(product_id, set()))
        product_conversion = _conversion_rate(product_orders, product_tryons)

        if commerce_metrics_resolved:
            product_revenue = round(float(revenue_by_product.get(product_id, 0.0)), 2)
            product_return_rate = _conversion_rate(
                int(returned_units_by_product.get(product_id, 0)),
                int(attributed_units_by_product.get(product_id, 0)),
            )
        else:
            product_revenue = None
            product_return_rate = None
            product_conversion = None

        top_performing_rows.append(
            TopPerformingProductEntry(
                shopify_product_id=product_id,
                title=product_title,
                try_on_sessions=product_tryons,
                conversion_rate=product_conversion,
                return_rate=product_return_rate,
                revenue_impact=product_revenue,
            )
        )

        legacy_top_rows.append(
            TopProductEntry(
                shopify_product_id=product_id,
                title=product_title,
                try_on_count=product_tryons,
                cart_count=product_orders if commerce_metrics_resolved else 0,
                conversion_rate=round(product_conversion, 2) if product_conversion is not None else 0.0,
            )
        )

    top_performing_rows.sort(
        key=lambda row: (
            row.conversion_rate if row.conversion_rate is not None else -1.0,
            row.try_on_sessions,
        ),
        reverse=True,
    )
    legacy_top_rows.sort(key=lambda row: row.conversion_rate, reverse=True)

    top_performing_products = top_performing_rows[:TOP_PRODUCTS_LIMIT]
    top_products = legacy_top_rows[:TOP_PRODUCTS_LIMIT]

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
        return_reduction=return_reduction,
        active_users=active_users,
        anonymous_users=anonymous_users,
        try_on_sessions=try_on_sessions,
        widget_click_rate=widget_click_rate,
        performance_trend=performance_trend,
        top_performing_products=top_performing_products,
        top_products=top_products,
        trend=trend,
    )
