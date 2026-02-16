"""
Virtual Try-On API Endpoints
Generates try-on images using Google Gemini (nano-banana) API
"""

import uuid
import time
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Header, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session as DBSession

from app.core.database import get_db
from app.models.database import Session, Product, TryOn
from app.models.schemas import TryOnGenerateRequest, TryOnStatusResponse
from app.services.cache_service import CacheService

router = APIRouter(prefix="/tryon", tags=["Virtual Try-On"])
logger = logging.getLogger(__name__)


async def get_session_from_header(
    x_session_id: str = Header(..., alias="X-Session-ID"),
    x_store_id: str = Header(..., alias="X-Store-ID"),
    db: DBSession = Depends(get_db),
) -> Session:
    """Get session from X-Session-ID header"""
    session = db.query(Session).filter_by(
        session_id=x_session_id,
        store_id=x_store_id,
    ).first()

    if not session:
        raise HTTPException(404, f"Session not found: {x_session_id}")

    if session.expires_at < datetime.utcnow():
        raise HTTPException(410, "Session expired")

    return session


def _run_tryon_generation(
    try_on_id: str,
    person_image: bytes,
    product_image_url: str,
    product_title: str,
    category: str,
):
    """
    Background task: generate the try-on image, cache it, update DB record.

    Runs in a separate thread via BackgroundTasks so the endpoint returns 202
    immediately.
    """
    from app.core.database import SessionLocal
    from app.services.tryon_service import TryOnService

    db = SessionLocal()
    try:
        # Mark as processing
        record = db.query(TryOn).filter_by(try_on_id=try_on_id).first()
        if not record:
            return
        record.processing_status = "processing"
        db.commit()

        start = time.time()

        service = TryOnService()
        result_bytes = service.generate(
            person_image=person_image,
            product_image_url=product_image_url,
            product_title=product_title,
            category=category,
        )

        elapsed = time.time() - start

        # Cache result image in Redis
        cache = CacheService()
        import asyncio
        loop = asyncio.new_event_loop()
        cache_key = loop.run_until_complete(
            cache.store_tryon_result(str(try_on_id), result_bytes)
        )
        loop.close()

        # Update DB record
        record.processing_status = "completed"
        record.result_cache_key = cache_key
        record.processing_time_seconds = round(elapsed, 2)
        record.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Try-on {try_on_id} completed in {elapsed:.1f}s")

    except Exception as e:
        logger.error(f"Try-on {try_on_id} failed: {e}", exc_info=True)
        try:
            record = db.query(TryOn).filter_by(try_on_id=try_on_id).first()
            if record:
                record.processing_status = "failed"
                record.error_message = str(e)[:500]
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/generate", status_code=202)
async def generate_tryon(
    request: TryOnGenerateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session_from_header),
    db: DBSession = Depends(get_db),
):
    """
    Start virtual try-on image generation.

    Only needs a product_id — the person's image is taken from the session's
    cached front photo. No measurements, size, or fit data needed; the model
    simply fits the product on the person as-is.

    Returns 202 immediately. Poll GET /tryon/{try_on_id}/status for result.

    Headers:
        X-Session-ID: Session UUID
        X-Store-ID: Store UUID

    Body:
        {"product_id": "uuid"}
    """
    try:
        # Validate product
        product = db.query(Product).filter_by(
            product_id=str(request.product_id)
        ).first()
        if not product:
            raise HTTPException(404, "Product not found")
        if str(product.store_id) != str(session.store_id):
            raise HTTPException(403, "Product does not belong to this store")

        # Get person's front image from session cache
        cache = CacheService()
        person_image = await cache.get_image(str(session.session_id), "front")

        if not person_image:
            raise HTTPException(
                422,
                "Person's front image not found in cache. "
                "Please upload an image first via the measurements endpoint.",
            )

        # Get product image URL
        product_images = product.images or []
        if not product_images:
            raise HTTPException(422, "Product has no images")
        first = product_images[0]
        product_image_url = first.get("src") if isinstance(first, dict) else first.src

        # Create TryOn DB record (measurement_id is nullable for this flow)
        try_on_id = uuid.uuid4()
        tryon_record = TryOn(
            try_on_id=try_on_id,
            product_id=product.product_id,
            processing_status="queued",
        )
        db.add(tryon_record)
        db.commit()

        # Launch generation in background
        background_tasks.add_task(
            _run_tryon_generation,
            try_on_id=str(try_on_id),
            person_image=person_image,
            product_image_url=product_image_url,
            product_title=product.title or "garment",
            category=product.category or "tops",
        )

        logger.info(f"Try-on queued: {try_on_id} for product={product.title}")

        return {
            "try_on_id": str(try_on_id),
            "status": "processing",
            "estimated_time_seconds": 45,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Try-on generation error: {e}", exc_info=True)
        raise HTTPException(500, f"Try-on generation failed: {str(e)}")


@router.get("/{try_on_id}/status", response_model=TryOnStatusResponse)
async def get_tryon_status(
    try_on_id: str,
    db: DBSession = Depends(get_db),
):
    """
    Poll for try-on generation status.

    Returns current status, and result_image_url when completed.
    """
    record = db.query(TryOn).filter_by(try_on_id=try_on_id).first()
    if not record:
        raise HTTPException(404, "Try-on not found")

    status = record.processing_status

    progress = None
    message = None
    result_image_url = None
    cache_expires_at = None

    if status == "queued":
        progress = 0
        message = "Queued for processing..."
    elif status == "processing":
        progress = 50
        message = "Generating virtual try-on image..."
    elif status == "completed":
        progress = 100
        message = "Try-on image ready"
        result_image_url = f"/api/v1/tryon/{try_on_id}/image"
        if record.completed_at:
            from datetime import timedelta
            cache_expires_at = record.completed_at + timedelta(hours=24)
    elif status == "failed":
        message = record.error_message or "Image generation failed"

    return TryOnStatusResponse(
        try_on_id=record.try_on_id,
        status=status,
        progress=progress,
        message=message,
        result_image_url=result_image_url,
        processing_time_seconds=record.processing_time_seconds,
        cache_expires_at=cache_expires_at,
        error=record.error_message if status == "failed" else None,
        retry_allowed=status == "failed",
    )


@router.get("/{try_on_id}/image")
async def get_tryon_image(try_on_id: str, db: DBSession = Depends(get_db)):
    """
    Serve the generated try-on image from Redis cache.
    """
    record = db.query(TryOn).filter_by(try_on_id=try_on_id).first()
    if not record:
        raise HTTPException(404, "Try-on not found")

    if record.processing_status != "completed":
        raise HTTPException(409, f"Try-on is {record.processing_status}, not ready")

    cache = CacheService()
    image_bytes = await cache.get_tryon_result(str(try_on_id))

    if not image_bytes:
        raise HTTPException(410, "Try-on image has expired from cache")

    return Response(content=image_bytes, media_type="image/png")
