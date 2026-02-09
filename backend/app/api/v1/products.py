"""
Products API Endpoints
Handles product sync and retrieval
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.security import decrypt_token
from app.models.database import Store, Product
from app.models.schemas import ProductSyncResponse, ProductResponse
from app.services.shopify_service import ShopifyService

router = APIRouter(prefix="/products", tags=["Products"])
logger = logging.getLogger(__name__)


async def get_store_from_header(
    x_store_id: str = Header(..., alias="X-Store-ID"),
    db: Session = Depends(get_db)
) -> Store:
    """
    Dependency to get store from X-Store-ID header

    Args:
        x_store_id: Store UUID from header
        db: Database session

    Returns:
        Store object

    Raises:
        HTTPException: If store not found
    """
    store = db.query(Store).filter_by(store_id=x_store_id).first()
    if not store:
        raise HTTPException(404, f"Store not found: {x_store_id}")
    return store


@router.post("/sync", response_model=ProductSyncResponse)
async def sync_products(
    store: Store = Depends(get_store_from_header),
    db: Session = Depends(get_db)
):
    """
    Manually trigger product sync from Shopify

    Syncs all products from Shopify to database

    Headers:
        X-Store-ID: Store UUID

    Returns:
        Sync statistics
    """
    try:
        # Decrypt access token
        access_token = decrypt_token(store.shopify_access_token)

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

    except Exception as e:
        logger.error(f"Product sync error: {e}", exc_info=True)
        raise HTTPException(500, f"Product sync failed: {str(e)}")


@router.get("/", response_model=List[ProductResponse])
async def list_products(
    store: Store = Depends(get_store_from_header),
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List products for a store

    Headers:
        X-Store-ID: Store UUID

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
    store: Store = Depends(get_store_from_header),
    db: Session = Depends(get_db)
):
    """
    Get a specific product

    Headers:
        X-Store-ID: Store UUID

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
