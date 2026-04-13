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

from app.api.store_context import get_public_store
from app.core.database import get_db
from app.models.database import Session, Product, TryOn, PhotoshootModel
from app.models.schemas import (
    TryOnGenerateRequest, TryOnStatusResponse,
    StudioBackgroundResponse, StudioTryOnRequest,
)
from app.services.cache_service import CacheService

router = APIRouter(prefix="/tryon", tags=["Virtual Try-On"])
logger = logging.getLogger(__name__)


async def get_session_from_header(
    x_session_id: str = Header(..., alias="X-Session-ID"),
    store = Depends(get_public_store),
    db: DBSession = Depends(get_db),
) -> Session:
    """Get session from X-Session-ID header"""
    session = db.query(Session).filter_by(
        session_id=x_session_id,
        store_id=store.store_id,
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


def _run_studio_generation(
    try_on_id: str,
    tryon_image: bytes,
    studio_image: bytes,
    parent_try_on_id: str,
    studio_background_id: str,
):
    """Background task: generate studio-styled try-on image."""
    from app.core.database import SessionLocal
    from app.services.tryon_service import TryOnService

    db = SessionLocal()
    try:
        record = db.query(TryOn).filter_by(try_on_id=try_on_id).first()
        if not record:
            return
        record.processing_status = "processing"
        db.commit()

        start = time.time()

        service = TryOnService()
        result_bytes = service.generate_studio(
            tryon_image=tryon_image,
            studio_image=studio_image,
        )

        elapsed = time.time() - start

        cache = CacheService()
        import asyncio
        loop = asyncio.new_event_loop()
        cache_key = loop.run_until_complete(
            cache.store_tryon_result(str(try_on_id), result_bytes)
        )
        # Also cache by parent+background combo (1-hour TTL) for instant re-use
        loop.run_until_complete(
            cache.store_studio_result(parent_try_on_id, studio_background_id, result_bytes)
        )
        loop.close()

        record.processing_status = "completed"
        record.result_cache_key = cache_key
        record.processing_time_seconds = round(elapsed, 2)
        record.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Studio try-on {try_on_id} completed in {elapsed:.1f}s")

    except Exception as e:
        logger.error(f"Studio try-on {try_on_id} failed: {e}", exc_info=True)
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


# ============================================================================
# Studio Background Endpoints (must be before /{try_on_id} routes)
# ============================================================================

@router.get("/studio-backgrounds", response_model=list[StudioBackgroundResponse])
async def list_studio_backgrounds(
    gender: str = "unisex",
    db: DBSession = Depends(get_db),
):
    """
    List available model photos for the studio look feature, filtered by gender.

    Returns active models for the given gender plus all "unisex" models.
    Frontend should randomize display order client-side.

    Note: Backed by photoshoot_models table (unified model/person photo library).
    """
    backgrounds = db.query(PhotoshootModel).filter(
        PhotoshootModel.is_active == True,
        PhotoshootModel.gender.in_([gender, "unisex"]),
    ).all()

    return [
        StudioBackgroundResponse(
            id=bg.id,
            gender=bg.gender,
            image_url=f"/api/v1/tryon/studio-backgrounds/{bg.id}/image",
        )
        for bg in backgrounds
    ]


@router.get("/studio-backgrounds/{bg_id}/image")
async def get_studio_background_image(
    bg_id: str,
    db: DBSession = Depends(get_db),
):
    """Serve a model photo from static files (image_path is relative to backend/static/)."""
    import os

    bg = db.query(PhotoshootModel).filter_by(id=bg_id, is_active=True).first()
    if not bg:
        raise HTTPException(404, "Studio background not found")

    static_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "static")
    file_path = os.path.join(static_root, bg.image_path)

    if not os.path.exists(file_path):
        raise HTTPException(404, "Studio background image file not found")

    with open(file_path, "rb") as f:
        image_bytes = f.read()

    media_type = "image/jpeg" if file_path.lower().endswith(".jpg") else "image/png"
    return Response(content=image_bytes, media_type=media_type)


@router.post("/studio", status_code=202)
async def generate_studio_tryon(
    request: StudioTryOnRequest,
    background_tasks: BackgroundTasks,
    db: DBSession = Depends(get_db),
):
    """
    Generate a studio-styled try-on image.

    Takes an existing completed try-on and a studio background, and generates
    the person in that environment. Returns 202; poll GET /status for result.

    Body:
        {"try_on_id": "uuid", "studio_background_id": "uuid"}
    """
    import os

    try:
        # Validate original try-on exists and is completed
        original = db.query(TryOn).filter_by(try_on_id=str(request.try_on_id)).first()
        if not original:
            raise HTTPException(404, "Original try-on not found")
        if original.processing_status != "completed":
            raise HTTPException(409, "Original try-on is not completed yet")

        # Validate studio background
        bg = db.query(PhotoshootModel).filter_by(
            id=str(request.studio_background_id), is_active=True
        ).first()
        if not bg:
            raise HTTPException(404, "Studio background not found")

        # Check if this parent+background combo is already cached (1-hour TTL)
        cache = CacheService()
        cached_studio = await cache.get_studio_result(
            str(request.try_on_id), str(request.studio_background_id)
        )
        if cached_studio:
            # Find the existing completed TryOn record for this combo
            existing = db.query(TryOn).filter_by(
                parent_try_on_id=str(request.try_on_id),
                studio_background_id=str(request.studio_background_id),
                processing_status="completed",
            ).first()

            if existing:
                logger.info(f"Studio cache hit: parent={request.try_on_id}, bg={request.studio_background_id}")
                return {
                    "try_on_id": str(existing.try_on_id),
                    "status": "completed",
                    "result_image_url": f"/api/v1/tryon/{existing.try_on_id}/image",
                }

        # Get original try-on image from Redis
        tryon_image = await cache.get_tryon_result(str(request.try_on_id))
        if not tryon_image:
            raise HTTPException(410, "Original try-on image has expired from cache")

        # Read studio background from static file
        static_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "static",
        )
        file_path = os.path.join(static_root, bg.image_path)
        if not os.path.exists(file_path):
            raise HTTPException(500, "Studio background image file missing")

        with open(file_path, "rb") as f:
            studio_image = f.read()

        # Create new TryOn record linked to parent
        new_try_on_id = uuid.uuid4()
        tryon_record = TryOn(
            try_on_id=new_try_on_id,
            product_id=original.product_id,
            studio_background_id=bg.id,
            parent_try_on_id=original.try_on_id,
            processing_status="queued",
        )
        db.add(tryon_record)
        db.commit()

        # Launch background generation
        background_tasks.add_task(
            _run_studio_generation,
            try_on_id=str(new_try_on_id),
            tryon_image=tryon_image,
            studio_image=studio_image,
            parent_try_on_id=str(request.try_on_id),
            studio_background_id=str(request.studio_background_id),
        )

        logger.info(f"Studio try-on queued: {new_try_on_id} (parent={request.try_on_id}, bg={bg.image_path})")

        return {
            "try_on_id": str(new_try_on_id),
            "status": "processing",
            "estimated_time_seconds": 45,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Studio try-on error: {e}", exc_info=True)
        raise HTTPException(500, f"Studio try-on generation failed: {str(e)}")


# ============================================================================
# Core Try-On Endpoints
# ============================================================================

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
