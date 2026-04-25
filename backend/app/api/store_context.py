"""
Shared store-resolution dependencies for merchant-facing routes.
"""

import logging
import hashlib
import hmac
import time
from typing import Optional

import httpx
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from app.config import get_settings
from app.core.database import get_db
from app.core.security import decrypt_token, maybe_verify_session_token
from app.models.database import Store

logger = logging.getLogger(__name__)


def _resolve_proxy_shared_secret() -> str:
    settings = get_settings()
    return (
        (settings.WIDGET_PROXY_SHARED_SECRET or "").strip()
        or (settings.SHOPIFY_API_SECRET or "").strip()
    )


def _verify_storefront_proxy_signature(
    *,
    request: Request,
    shop_domain: Optional[str],
) -> None:
    settings = get_settings()
    env = (settings.APP_ENV or "").strip().lower()
    if env == "development":
        return

    shared_secret = _resolve_proxy_shared_secret()
    if not shared_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storefront proxy verification is misconfigured.",
        )

    ts_raw = (request.headers.get("X-Optimo-Proxy-Ts") or "").strip()
    sig = (request.headers.get("X-Optimo-Proxy-Sig") or "").strip().lower()
    if not ts_raw or not sig:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing trusted storefront proxy signature.",
        )

    try:
        ts = int(ts_raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid storefront proxy timestamp.",
        )

    max_skew_seconds = int(settings.WIDGET_PROXY_MAX_SKEW_SECONDS or 300)
    now = int(time.time())
    if abs(now - ts) > max_skew_seconds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Storefront proxy signature is stale.",
        )

    logged_in_customer_id = (request.headers.get("X-Logged-In-Customer-Id") or "").strip()
    anon_id = (request.headers.get("X-Optimo-Anon-Id") or "").strip()
    payload = "\n".join(
        [
            str(ts),
            request.method.upper(),
            request.url.path,
            (shop_domain or "").strip().lower(),
            logged_in_customer_id,
            anon_id,
        ]
    )
    expected = hmac.new(
        shared_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid trusted storefront proxy signature.",
        )


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


def get_public_store(
    request: Request,
    x_shopify_shop_domain: Optional[str] = Header(None, alias="X-Shopify-Shop-Domain"),
    x_shop_domain: Optional[str] = Header(None, alias="X-Shop-Domain"),
    x_store_id: Optional[str] = Header(None, alias="X-Store-ID"),
    db: DBSession = Depends(get_db),
) -> Store:
    """
    Resolve a storefront/public store identifier without requiring merchant auth.

    Public widget routes should prefer the shop domain so the browser never needs
    the internal store UUID, but `X-Store-ID` remains supported for backwards
    compatibility.
    """
    header_shop_domain = _normalize_shop_domain(x_shopify_shop_domain) or _normalize_shop_domain(x_shop_domain)
    normalized_store_id = (x_store_id or "").strip()
    _verify_storefront_proxy_signature(request=request, shop_domain=header_shop_domain)

    if header_shop_domain:
        store = _get_store_by_shop_domain(header_shop_domain, db)
        if store:
            return store
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store not found for shop: {header_shop_domain}",
        )

    if normalized_store_id:
        store = _get_store_by_id(normalized_store_id, db)
        if store:
            return store
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store not found: {normalized_store_id}",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing store identifier",
    )


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


def _missing_session_token_detail(action_label: str) -> str:
    return (
        "Store installation is incomplete and no session token was provided. "
        f"Open the app from Shopify Admin (embedded) before using {action_label}."
    )


def _token_exchange_failed_detail(action_label: str) -> str:
    return (
        "Store installation is incomplete and Shopify session token exchange failed. "
        "Complete the backend Shopify auth flow for this shop before "
        f"using {action_label}."
    )


async def _exchange_session_token_for_access(
    shop_domain: str,
    session_token: str,
    *,
    action_label: str,
) -> str:
    settings = get_settings()
    url = f"https://{shop_domain}/admin/oauth/access_token"
    payload = {
        "client_id": settings.SHOPIFY_API_KEY,
        "client_secret": settings.SHOPIFY_API_SECRET,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": session_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
        "requested_token_type": "urn:shopify:params:oauth:token-type:online-access-token",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        logger.warning("Shopify token exchange request failed for %s: %s", shop_domain, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_token_exchange_failed_detail(action_label),
        ) from exc

    if not resp.is_success:
        logger.warning(
            "Shopify token exchange response failed for %s: status=%s body=%s",
            shop_domain,
            resp.status_code,
            resp.text,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_token_exchange_failed_detail(action_label),
        )

    try:
        data = resp.json()
    except ValueError as exc:
        logger.warning("Shopify token exchange JSON parse failed for %s", shop_domain)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_token_exchange_failed_detail(action_label),
        ) from exc

    token = (data.get("access_token") or "").strip()
    if not token:
        logger.warning("Shopify token exchange returned no access token for %s", shop_domain)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_token_exchange_failed_detail(action_label),
        )

    return token


async def resolve_merchant_shopify_access_token(
    store: Store,
    credentials: Optional[HTTPAuthorizationCredentials],
    *,
    action_label: str = "this action",
) -> str:
    """
    Resolve a usable Shopify Admin API token for merchant actions.

    Order:
    1) Stored OAuth token from the store row (decrypt before returning)
    2) App Bridge session-token exchange fallback for provisional stores
    """
    stored_token = (store.shopify_access_token or "").strip()
    if stored_token:
        return decrypt_token(stored_token)

    session_token = (credentials.credentials if credentials else "").strip()
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_missing_session_token_detail(action_label),
        )

    return await _exchange_session_token_for_access(
        store.shopify_domain,
        session_token,
        action_label=action_label,
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
    2. Header fallback (`X-Shopify-Shop-Domain`, `X-Shop-Domain`, `X-Store-ID`)

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

    if authenticated_shop_domain:
        store = _get_store_by_shop_domain(authenticated_shop_domain, db)
        if store:
            return store
    else:
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

    if header_shop_domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store not found for shop: {header_shop_domain}",
        )

    if normalized_store_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store not found: {normalized_store_id}",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing session token",
    )
