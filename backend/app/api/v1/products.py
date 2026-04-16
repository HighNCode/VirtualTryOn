"""
Products API Endpoints
Handles product sync and retrieval
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.api.store_context import (
    get_current_merchant_store,
    resolve_merchant_shopify_access_token,
)
from app.core.database import get_db
from app.core.security import _bearer_scheme
from app.models.database import Store, Product
from app.models.schemas import ProductSyncResponse, ProductResponse
from app.services.shopify_service import ShopifyService

router = APIRouter(prefix="/products", tags=["Products"])
logger = logging.getLogger(__name__)


@router.post("/sync", response_model=ProductSyncResponse)
async def sync_products(
    store: Store = Depends(get_current_merchant_store),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db)
):
    """
    Manually trigger product sync from Shopify

    Syncs all products from Shopify to database

    Returns:
        Sync statistics
    """
    try:
        access_token = await resolve_merchant_shopify_access_token(
            store,
            credentials,
            action_label="product sync",
        )

        # Initialize Shopify service
        shopify_service = ShopifyService(store.shopify_domain, access_token)

        # Sync products
        result = await shopify_service.sync_all_products(db, str(store.store_id))

        logger.info(f"Product sync completed for store {store.store_id}: {result}")

        return ProductSyncResponse(
            status="success",
            products_synced=result['products_synced'],
            products_with_sizes=result['products_with_sizes'],
            products_without_sizes=result['products_without_sizes'],
            timestamp=result['timestamp']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Product sync error: {e}", exc_info=True)
        error_text = str(e).lower()
        if "access_denied" in error_text or "access denied for products field" in error_text:
            raise HTTPException(
                409,
                "Shopify denied access to products. Ensure the app has read_products scope and the shop has approved the latest scopes.",
            )
        raise HTTPException(500, f"Product sync failed: {str(e)}")


@router.get("", response_model=List[ProductResponse])
@router.get("/", response_model=List[ProductResponse], include_in_schema=False)
async def list_products(
    store: Store = Depends(get_current_merchant_store),
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List products for a store

    Query Params:
        category: Filter by category (tops, bottoms, dresses, outerwear)
        limit: Max products to return (default 50)
        offset: Pagination offset (default 0)

    Returns:
        List of products
    """
    query = db.query(Product).filter_by(store_id=store.store_id)

    if category:
        query = query.filter_by(category=category)

    products = query.offset(offset).limit(limit).all()

    return products


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    store: Store = Depends(get_current_merchant_store),
    db: Session = Depends(get_db)
):
    """
    Get a specific product

    Args:
        product_id: Product UUID

    Returns:
        Product details
    """
    product = db.query(Product).filter_by(
        product_id=product_id,
        store_id=store.store_id
    ).first()

    if not product:
        raise HTTPException(404, f"Product not found: {product_id}")

    return product
