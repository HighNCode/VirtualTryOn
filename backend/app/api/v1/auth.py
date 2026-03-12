"""
Authentication & OAuth Endpoints
Handles Shopify OAuth flow
"""

import asyncio
import shopify
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.security import encrypt_token
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

    shopify.Session.setup(api_key=settings.SHOPIFY_API_KEY, secret=settings.SHOPIFY_API_SECRET)
    session = shopify.Session(shop, settings.SHOPIFY_API_VERSION)
    redirect_uri = str(request.url_for('shopify_oauth_callback'))
    auth_url = session.create_permission_url(settings.SHOPIFY_SCOPES.split(","), redirect_uri)

    logger.info(f"OAuth initiated for shop: {shop}")
    return RedirectResponse(url=auth_url)


@router.get("/callback", name="shopify_oauth_callback")
async def shopify_oauth_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Shopify OAuth callback

    Shopify redirects here after user approves app installation

    Steps:
    1. Verify HMAC + exchange code for token (via shopify.Session)
    2. Save store to database
    3. Install script tag
    4. Sync products
    5. Redirect to embedded app

    Args:
        request: FastAPI request (all query params extracted as dict)
        db: Database session

    Returns:
        Redirect to embedded app entry point
    """
    params = dict(request.query_params)
    shop = params.get("shop")
    host = params.get("host")

    if not shop:
        raise HTTPException(400, "Missing shop parameter")

    shopify.Session.setup(api_key=settings.SHOPIFY_API_KEY, secret=settings.SHOPIFY_API_SECRET)
    session = shopify.Session(shop, settings.SHOPIFY_API_VERSION)

    try:
        # session.request_token() is synchronous and auto-validates HMAC
        loop = asyncio.get_running_loop()
        access_token = await loop.run_in_executor(None, session.request_token, params)
    except Exception as e:
        logger.error(f"Token exchange failed for shop {shop}: {e}")
        raise HTTPException(403, "HMAC verification or token exchange failed")

    try:
        encrypted_token = encrypt_token(access_token)

        existing_store = db.query(Store).filter_by(shopify_domain=shop).first()

        if existing_store:
            existing_store.shopify_access_token = encrypted_token
            existing_store.installation_status = 'active'
            existing_store.reinstalled_at = datetime.utcnow()
            store = existing_store
            logger.info(f"Store reinstalled: {shop}")
        else:
            store = Store(
                shopify_domain=shop,
                shopify_access_token=encrypted_token,
                installation_status='active'
            )
            db.add(store)
            logger.info(f"New store installed: {shop}")

        db.commit()
        db.refresh(store)

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

        try:
            sync_result = await shopify_service.sync_all_products(db, str(store.store_id))
            logger.info(f"Product sync completed: {sync_result}")
        except Exception as e:
            logger.error(f"Product sync failed: {e}")

        # Redirect to embedded app entry point
        return RedirectResponse(url=f"/?shop={shop}&host={host}")

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
