"""
Shared store-resolution dependencies for merchant-facing routes.
"""

import logging
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from app.config import get_settings
from app.core.database import get_db
from app.core.security import maybe_verify_session_token
from app.models.database import Store

logger = logging.getLogger(__name__)
settings = get_settings()


def _normalize_shop_domain(value: Optional[str]) -> Optional[str]:
    """Convert a header or JWT `dest` value into a bare `{shop}.myshopify.com` domain."""
    if not value:
        return None

    sanitized = value.strip().lower()
    sanitized = sanitized.replace("https://", "").replace("http://", "")
    sanitized = sanitized.split("/", 1)[0]
    return sanitized or None


def _get_store_by_shop_domain(shop_domain: str, db: DBSession) -> Optional[Store]:
    return db.query(Store).filter_by(shopify_domain=shop_domain).first()


def _get_store_by_id(store_id: str, db: DBSession) -> Optional[Store]:
    return db.query(Store).filter_by(store_id=store_id).first()


def require_shopify_access_token(store: Store) -> str:
    """
    Ensure the store finished the backend install/auth flow before calling Shopify Admin APIs.
    """
    token = (store.shopify_access_token or "").strip()
    if token:
        return token

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Store installation is incomplete. Finish the backend Shopify auth flow "
            "before calling this action."
        ),
    )


def get_current_merchant_store(
    payload: Optional[dict] = Depends(maybe_verify_session_token),
    x_shopify_shop_domain: Optional[str] = Header(None, alias="X-Shopify-Shop-Domain"),
    x_shop_domain: Optional[str] = Header(None, alias="X-Shop-Domain"),
    x_store_id: Optional[str] = Header(None, alias="X-Store-ID"),
    db: DBSession = Depends(get_db),
) -> Store:
    """
    Resolve the active merchant store.

    Preference order:
    1. Verified Shopify session token (embedded app)
    2. Non-production fallback headers (`X-Shopify-Shop-Domain`, `X-Shop-Domain`, `X-Store-ID`)

    If a verified session token is present but the store row does not exist yet, create a
    placeholder store record so onboarding can start before the full backend OAuth flow exists.
    """
    authenticated_shop_domain = _normalize_shop_domain((payload or {}).get("dest"))
    header_shop_domain = _normalize_shop_domain(x_shopify_shop_domain) or _normalize_shop_domain(x_shop_domain)

    if authenticated_shop_domain and header_shop_domain and authenticated_shop_domain != header_shop_domain:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated shop does not match requested shop",
        )

    normalized_store_id = (x_store_id or "").strip()
    allow_dev_header_fallback = settings.APP_ENV != "production"

    if authenticated_shop_domain:
        store = _get_store_by_shop_domain(authenticated_shop_domain, db)
        if store:
            return store
    elif allow_dev_header_fallback:
        if header_shop_domain:
            store = _get_store_by_shop_domain(header_shop_domain, db)
            if store:
                return store

        if normalized_store_id:
            store = _get_store_by_id(normalized_store_id, db)
            if store:
                if header_shop_domain and store.shopify_domain != header_shop_domain:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Requested store does not match requested shop",
                    )
                return store

    if authenticated_shop_domain:
        provisional_store = Store(
            shopify_domain=authenticated_shop_domain,
            shopify_access_token="",
            installation_status="pending",
        )
        db.add(provisional_store)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing_store = _get_store_by_shop_domain(authenticated_shop_domain, db)
            if existing_store:
                return existing_store
            raise

        db.refresh(provisional_store)
        logger.info(
            "Provisional merchant store created for authenticated shop %s (store_id=%s)",
            provisional_store.shopify_domain,
            provisional_store.store_id,
        )
        return provisional_store

    if header_shop_domain and allow_dev_header_fallback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store not found for shop: {header_shop_domain}",
        )

    if normalized_store_id and allow_dev_header_fallback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store not found: {normalized_store_id}",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing session token",
    )
