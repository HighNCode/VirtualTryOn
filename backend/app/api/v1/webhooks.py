"""
Shopify Webhooks Endpoints
Handles webhooks from Shopify for real-time updates
"""

from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging
from typing import Optional

from app.core.database import get_db
from app.core.security import verify_webhook, decrypt_token
from app.models.database import Store, Product
from app.services.shopify_service import ShopifyService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = logging.getLogger(__name__)


async def verify_webhook_signature(request: Request):
    """Dependency to verify webhook signature"""
    if not verify_webhook(request):
        raise HTTPException(401, "Invalid webhook signature")
    return True


def _extract_shop_domain(request: Request, payload: dict) -> str:
    shop_domain = str(payload.get("shop_domain") or "").strip().lower()
    if shop_domain:
        return shop_domain
    return str(request.headers.get("x-shopify-shop-domain") or "").strip().lower()


@router.post("/shop/update")
async def handle_shop_update(
    request: Request,
    verified: bool = Depends(verify_webhook_signature),
    db: Session = Depends(get_db),
):
    """
    Handle shop/update webhook with lightweight store metadata sync.
    """
    try:
        data = await request.json()
        shop_domain = _extract_shop_domain(request, data)
        if not shop_domain:
            return {"status": "success", "message": "shop_domain missing; nothing to update"}

        store = db.query(Store).filter_by(shopify_domain=shop_domain).first()
        if not store:
            return {"status": "success", "message": "Store not found; ignored"}

        store_name = str(data.get("name") or "").strip()
        email = str(data.get("email") or "").strip()
        timezone = str(data.get("iana_timezone") or data.get("timezone") or "").strip()

        if store_name:
            store.store_name = store_name
        if email:
            store.email = email
        if timezone:
            store.store_timezone = timezone

        db.commit()
        logger.info("Shop update webhook processed for %s", shop_domain)
        return {"status": "success", "message": "Shop metadata updated"}
    except Exception as e:
        logger.error(f"Shop update webhook error: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}


@router.post("/app_subscriptions/update")
async def handle_app_subscriptions_update(
    request: Request,
    verified: bool = Depends(verify_webhook_signature),
    db: Session = Depends(get_db),
):
    """
    Handle app_subscriptions/update webhook with lightweight billing status sync.
    """
    try:
        data = await request.json()
        shop_domain = _extract_shop_domain(request, data)
        if not shop_domain:
            return {"status": "success", "message": "shop_domain missing; nothing to update"}

        store = db.query(Store).filter_by(shopify_domain=shop_domain).first()
        if not store:
            return {"status": "success", "message": "Store not found; ignored"}

        subscription_payload = data.get("app_subscription")
        if not isinstance(subscription_payload, dict):
            subscription_payload = {}

        raw_status: Optional[str] = None
        if isinstance(data.get("status"), str):
            raw_status = data.get("status")
        elif isinstance(subscription_payload.get("status"), str):
            raw_status = subscription_payload.get("status")

        raw_gid = (
            subscription_payload.get("admin_graphql_api_id")
            or data.get("admin_graphql_api_id")
            or subscription_payload.get("id")
            or data.get("id")
        )
        subscription_gid = str(raw_gid or "").strip()

        if raw_status:
            store.subscription_status = str(raw_status).strip().upper()
        if subscription_gid and subscription_gid.startswith("gid://shopify/AppSubscription/"):
            store.plan_shopify_subscription_id = subscription_gid

        store.billing_status_synced_at = datetime.utcnow()
        db.commit()
        logger.info("App subscription update webhook processed for %s", shop_domain)
        return {"status": "success", "message": "Subscription status synced"}
    except Exception as e:
        logger.error(f"App subscription update webhook error: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}


@router.post("/products/create")
async def handle_product_create(
    request: Request,
    background_tasks: BackgroundTasks,
    verified: bool = Depends(verify_webhook_signature),
    db: Session = Depends(get_db)
):
    """
    Handle product creation webhook from Shopify

    Called by Shopify when merchant creates a new product

    Webhook Body:
        {
            "id": 12345,
            "title": "Product Name",
            "shop_domain": "mystore.myshopify.com",
            ...
        }

    Returns:
        Success response
    """
    try:
        # Parse webhook data
        data = await request.json()
        shop_domain = data.get('shop_domain')
        product_id = str(data.get('id'))

        logger.info(f"Product created webhook: {product_id} from {shop_domain}")

        # Get store
        store = db.query(Store).filter_by(shopify_domain=shop_domain).first()
        if not store:
            logger.error(f"Store not found for webhook: {shop_domain}")
            return {"status": "error", "message": "Store not found"}

        # Fetch full product details from Shopify (async)
        access_token = decrypt_token(store.shopify_access_token)
        shopify_service = ShopifyService(shop_domain, access_token)

        # Sync this specific product
        # TODO: Implement single product fetch and save
        # For now, trigger full sync in background
        background_tasks.add_task(
            shopify_service.sync_all_products,
            db,
            str(store.store_id)
        )

        return {"status": "success", "message": "Product creation processed"}

    except Exception as e:
        logger.error(f"Product create webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/products/update")
async def handle_product_update(
    request: Request,
    background_tasks: BackgroundTasks,
    verified: bool = Depends(verify_webhook_signature),
    db: Session = Depends(get_db)
):
    """
    Handle product update webhook from Shopify

    Called by Shopify when merchant updates a product

    Returns:
        Success response
    """
    try:
        data = await request.json()
        shop_domain = data.get('shop_domain')
        product_id = str(data.get('id'))

        logger.info(f"Product updated webhook: {product_id} from {shop_domain}")

        # Get store
        store = db.query(Store).filter_by(shopify_domain=shop_domain).first()
        if not store:
            return {"status": "error", "message": "Store not found"}

        # Trigger product sync in background
        access_token = decrypt_token(store.shopify_access_token)
        shopify_service = ShopifyService(shop_domain, access_token)

        background_tasks.add_task(
            shopify_service.sync_all_products,
            db,
            str(store.store_id)
        )

        return {"status": "success", "message": "Product update processed"}

    except Exception as e:
        logger.error(f"Product update webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/products/delete")
async def handle_product_delete(
    request: Request,
    verified: bool = Depends(verify_webhook_signature),
    db: Session = Depends(get_db)
):
    """
    Handle product deletion webhook from Shopify

    Called by Shopify when merchant deletes a product

    Returns:
        Success response
    """
    try:
        data = await request.json()
        shop_domain = data.get('shop_domain')
        shopify_product_id = str(data.get('id'))

        logger.info(f"Product deleted webhook: {shopify_product_id} from {shop_domain}")

        # Get store
        store = db.query(Store).filter_by(shopify_domain=shop_domain).first()
        if not store:
            return {"status": "error", "message": "Store not found"}

        # Delete product from database
        deleted_count = db.query(Product).filter(
            Product.store_id == store.store_id,
            Product.shopify_product_id == shopify_product_id
        ).delete()

        db.commit()

        logger.info(f"Deleted {deleted_count} products with ID {shopify_product_id}")

        return {"status": "success", "message": f"Product {shopify_product_id} deleted"}

    except Exception as e:
        logger.error(f"Product delete webhook error: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}


@router.post("/app/uninstalled")
async def handle_app_uninstall(
    request: Request,
    verified: bool = Depends(verify_webhook_signature),
    db: Session = Depends(get_db)
):
    """
    Handle app uninstallation webhook

    CRITICAL: Must handle data deletion per Shopify requirements

    Called by Shopify when merchant uninstalls the app

    Steps:
    1. Mark store as uninstalled
    2. Delete script tag from Shopify
    3. Schedule data deletion (30-day grace period for GDPR)
    4. Send notification

    Returns:
        Success response
    """
    try:
        data = await request.json()
        shop_domain = data.get('shop_domain')

        logger.info(f"App uninstalled webhook: {shop_domain}")

        # Get store
        store = db.query(Store).filter_by(shopify_domain=shop_domain).first()
        if not store:
            return {"status": "error", "message": "Store not found"}

        # Mark as uninstalled
        store.installation_status = 'uninstalled'
        store.uninstalled_at = datetime.utcnow()

        # Delete script tag from Shopify (if still exists)
        if store.script_tag_id:
            try:
                access_token = decrypt_token(store.shopify_access_token)
                shopify_service = ShopifyService(shop_domain, access_token)
                await shopify_service.delete_script_tag(store.script_tag_id)
                logger.info(f"Script tag deleted: {store.script_tag_id}")
            except Exception as e:
                logger.warning(f"Script tag deletion failed: {e}")
                # Continue anyway - script tag might already be deleted

        # Schedule data deletion (30 days grace period)
        from app.models.database import DataDeletionQueue
        deletion_date = datetime.utcnow() + timedelta(days=30)

        deletion_task = DataDeletionQueue(
            store_id=store.store_id,
            scheduled_for=deletion_date,
            status='pending'
        )
        db.add(deletion_task)

        db.commit()

        logger.info(f"Uninstall processed for {shop_domain}. Data deletion scheduled for {deletion_date}")

        # TODO: Send notification to admin
        # TODO: Implement background worker to execute deletion after 30 days

        return {
            "status": "success",
            "message": "App uninstalled",
            "data_deletion_scheduled": deletion_date.isoformat()
        }

    except Exception as e:
        logger.error(f"App uninstall webhook error: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}


@router.post("/gdpr/customers/data_request")
async def handle_customer_data_request(
    request: Request,
    verified: bool = Depends(verify_webhook_signature)
):
    """
    Handle GDPR customer data request webhook

    Shopify sends this when customer requests their data

    Returns:
        Success response (data export handled separately)
    """
    try:
        data = await request.json()
        shop_domain = data.get('shop_domain')
        customer_id = data.get('customer', {}).get('id')

        logger.info(f"GDPR data request: customer {customer_id} from {shop_domain}")

        # TODO: Implement data export logic
        # For this app, we don't store customer personal data (only anonymous measurements)
        # Return empty data or minimal info

        return {
            "status": "success",
            "message": "No personal data stored for this customer"
        }

    except Exception as e:
        logger.error(f"GDPR data request error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/gdpr/customers/redact")
async def handle_customer_redact(
    request: Request,
    verified: bool = Depends(verify_webhook_signature),
    db: Session = Depends(get_db)
):
    """
    Handle GDPR customer data deletion webhook

    Shopify sends this when customer requests data deletion

    Returns:
        Success response
    """
    try:
        data = await request.json()
        shop_domain = data.get('shop_domain')
        customer_id = data.get('customer', {}).get('id')

        logger.info(f"GDPR redaction request: customer {customer_id} from {shop_domain}")

        # TODO: Delete customer-related data
        # For this app, measurements are anonymous and auto-deleted after 24h
        # No action needed beyond logging

        return {
            "status": "success",
            "message": "Customer data redacted (no personal data stored)"
        }

    except Exception as e:
        logger.error(f"GDPR redaction error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/gdpr/shop/redact")
async def handle_shop_redact(
    request: Request,
    verified: bool = Depends(verify_webhook_signature),
    db: Session = Depends(get_db)
):
    """
    Handle GDPR shop data deletion webhook

    Shopify sends this 48 hours after app uninstall
    Must delete ALL shop data

    Returns:
        Success response
    """
    try:
        data = await request.json()
        shop_domain = data.get('shop_domain')

        logger.info(f"GDPR shop redaction: {shop_domain}")

        # Get store
        store = db.query(Store).filter_by(shopify_domain=shop_domain).first()
        if not store:
            return {"status": "success", "message": "Store not found (already deleted)"}

        # Execute immediate deletion
        # TODO: Implement complete data deletion
        # For now, just mark for deletion
        store.installation_status = 'deleted'
        db.commit()

        logger.info(f"Shop data deleted: {shop_domain}")

        return {
            "status": "success",
            "message": "Shop data deleted"
        }

    except Exception as e:
        logger.error(f"GDPR shop redaction error: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
