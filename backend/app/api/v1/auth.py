"""
Authentication & OAuth Endpoints
Handles Shopify OAuth flow
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.security import (
    verify_shopify_hmac,
    get_shopify_auth_url,
    exchange_code_for_token,
    encrypt_token
)
from app.models.database import Store
from app.models.schemas import StoreResponse
from app.services.shopify_service import ShopifyService
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.get("/shopify")
async def shopify_oauth_init(shop: str, request: Request):
    """
    Initialize Shopify OAuth flow

    User clicks "Install App" → redirects here → redirects to Shopify OAuth

    Args:
        shop: Shop domain (e.g., mystore.myshopify.com)

    Returns:
        Redirect to Shopify authorization page
    """
    if not settings.SHOPIFY_API_KEY:
        raise HTTPException(500, "Shopify API key not configured")

    # Build redirect URI (this endpoint's callback)
    redirect_uri = str(request.url_for('shopify_oauth_callback'))

    # Generate Shopify OAuth URL
    auth_url = get_shopify_auth_url(shop, redirect_uri)

    logger.info(f"OAuth initiated for shop: {shop}")

    return RedirectResponse(url=auth_url)


@router.get("/callback", name="shopify_oauth_callback")
async def shopify_oauth_callback(
    code: str,
    shop: str,
    hmac: str,
    timestamp: str = None,
    state: str = None,
    db: Session = Depends(get_db)
):
    """
    Shopify OAuth callback

    Shopify redirects here after user approves app installation

    Steps:
    1. Verify HMAC signature
    2. Exchange code for access token
    3. Save store to database
    4. Install script tag
    5. Sync products
    6. Redirect to Shopify admin

    Args:
        code: OAuth authorization code
        shop: Shop domain
        hmac: HMAC signature for verification
        timestamp: Request timestamp
        state: CSRF state token
        db: Database session

    Returns:
        Redirect to Shopify admin dashboard
    """
    # Verify HMAC
    params = {
        'code': code,
        'shop': shop,
        'timestamp': timestamp or '',
        'state': state or ''
    }

    if not verify_shopify_hmac(params, hmac):
        logger.error(f"HMAC verification failed for shop: {shop}")
        raise HTTPException(403, "Invalid HMAC signature")

    try:
        # Exchange code for access token
        access_token = await exchange_code_for_token(shop, code)

        # Encrypt token for storage
        encrypted_token = encrypt_token(access_token)

        # Check if store already exists (reinstallation)
        existing_store = db.query(Store).filter_by(shopify_domain=shop).first()

        if existing_store:
            # Reinstallation - update token and status
            existing_store.shopify_access_token = encrypted_token
            existing_store.installation_status = 'active'
            existing_store.reinstalled_at = datetime.utcnow()

            # Cancel any scheduled deletion
            # TODO: Implement deletion cancellation

            store = existing_store
            logger.info(f"Store reinstalled: {shop}")
        else:
            # New installation
            store = Store(
                shopify_domain=shop,
                shopify_access_token=encrypted_token,
                installation_status='active'
            )
            db.add(store)
            logger.info(f"New store installed: {shop}")

        db.commit()
        db.refresh(store)

        # Initialize Shopify service
        shopify_service = ShopifyService(shop, access_token)

        # Install script tag (widget)
        # TODO: Update with actual widget URL
        widget_url = f"https://cdn.yourdomain.com/widget.js?store={store.store_id}"
        try:
            script_tag_id = await shopify_service.install_script_tag(widget_url)
            store.script_tag_id = script_tag_id
            db.commit()
            logger.info(f"Script tag installed: {script_tag_id}")
        except Exception as e:
            logger.error(f"Script tag installation failed: {e}")
            # Continue anyway - can retry later

        # Trigger product sync (async background task)
        # For now, sync immediately (in production, use background task)
        try:
            sync_result = await shopify_service.sync_all_products(db, str(store.store_id))
            logger.info(f"Product sync completed: {sync_result}")
        except Exception as e:
            logger.error(f"Product sync failed: {e}")
            # Continue anyway - can retry later

        # Redirect to Shopify admin
        redirect_url = f"https://{shop}/admin/apps"
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(500, f"Installation failed: {str(e)}")


@router.get("/verify")
async def verify_installation(
    shop: str,
    db: Session = Depends(get_db)
):
    """
    Verify if a shop has the app installed

    Args:
        shop: Shop domain
        db: Database session

    Returns:
        Installation status
    """
    store = db.query(Store).filter_by(shopify_domain=shop).first()

    if not store:
        return {
            "installed": False,
            "shop": shop
        }

    return {
        "installed": True,
        "shop": shop,
        "status": store.installation_status,
        "store_id": str(store.store_id)
    }
