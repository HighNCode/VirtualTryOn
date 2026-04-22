"""
Virtual Try-On API Endpoints
Generates try-on images using Google Gemini (nano-banana) API
"""

import uuid
import time
import logging
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Header, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session as DBSession
from PIL import Image

from app.api.store_context import get_public_store
from app.config import get_settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.database import Session, Product, TryOn, PhotoshootModel, Store, WidgetConfig
from app.models.schemas import (
    TryOnGenerateRequest, TryOnStatusResponse,
    StudioBackgroundResponse, StudioTryOnRequest,
)
from app.services.cache_service import CacheService
from app.services.usage_governance_service import UsageGovernanceService

router = APIRouter(prefix="/tryon", tags=["Virtual Try-On"])
logger = logging.getLogger(__name__)
settings = get_settings()


def _normalize_customer_id(value: Optional[str]) -> Optional[str]:
    candidate = (value or "").strip()
    return candidate or None


def _infer_image_media_type(image_bytes: bytes) -> str:
    """Infer image mime type from magic bytes for reliable browser rendering."""
    if not image_bytes:
        return "application/octet-stream"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        return "image/gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def _is_valid_image_payload(image_bytes: bytes) -> bool:
    try:
        img = Image.open(BytesIO(image_bytes))
        img.verify()
        return True
    except Exception:
        return False


def _build_tryon_reuse_key(store_id: str, user_identifier: str, product_id: str, measurement_id: Optional[str]) -> str:
    measurement_part = measurement_id or "none"
    return f"user:{store_id}:{user_identifier}:product:{product_id}:measurement:{measurement_part}:latest_tryon"


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
    store_id: Optional[str] = None,
    user_identifier: Optional[str] = None,
    product_id: Optional[str] = None,
    measurement_id: Optional[str] = None,
    usage_event_id: Optional[str] = None,
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
        logger.info(
            "Try-on product image input: try_on_id=%s product_id=%s category=%s image_url=%s",
            try_on_id,
            product_id,
            category,
            product_image_url,
        )

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
        try:
            cache_key = loop.run_until_complete(
                cache.store_tryon_result(str(try_on_id), result_bytes)
            )
            cached_bytes = loop.run_until_complete(cache.get_tryon_result(str(try_on_id)))
            if not cached_bytes:
                raise RuntimeError(f"Try-on cached payload missing right after write: {try_on_id}")
            if not _is_valid_image_payload(cached_bytes):
                raise RuntimeError(f"Try-on cached payload invalid image bytes: {try_on_id}")
        finally:
            loop.close()

        # Update DB record
        record.processing_status = "completed"
        record.result_cache_key = cache_key
        record.processing_time_seconds = round(elapsed, 2)
        record.completed_at = datetime.utcnow()
        db.commit()

        if store_id and user_identifier and product_id:
            try:
                redis = get_redis()
                reuse_key = _build_tryon_reuse_key(
                    store_id=store_id,
                    user_identifier=user_identifier,
                    product_id=product_id,
                    measurement_id=measurement_id,
                )
                redis.set(reuse_key, str(try_on_id), settings.TRYON_RESULT_TTL_SECONDS)
            except Exception:
                logger.warning("Failed to write try-on reuse key for try_on_id=%s", try_on_id)

        if usage_event_id:
            import asyncio
            usage = UsageGovernanceService(db)
            loop2 = asyncio.new_event_loop()
            loop2.run_until_complete(
                usage.finalize_usage(
                    event_id=usage_event_id,
                    reference_id=str(try_on_id),
                )
            )
            loop2.close()

        logger.info(f"Try-on {try_on_id} completed in {elapsed:.1f}s")

    except Exception as e:
        logger.error(f"Try-on {try_on_id} failed: {e}", exc_info=True)
        try:
            record = db.query(TryOn).filter_by(try_on_id=try_on_id).first()
            if record:
                record.processing_status = "failed"
                record.error_message = str(e)[:500]
                db.commit()
            if usage_event_id:
                import asyncio
                usage = UsageGovernanceService(db)
                loop2 = asyncio.new_event_loop()
                loop2.run_until_complete(
                    usage.refund_usage(
                        event_id=usage_event_id,
                        reason=f"tryon_failed:{str(e)[:240]}",
                    )
                )
                loop2.close()
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
    usage_event_id: Optional[str] = None,
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
        try:
            cache_key = loop.run_until_complete(
                cache.store_tryon_result(str(try_on_id), result_bytes)
            )
            cached_bytes = loop.run_until_complete(cache.get_tryon_result(str(try_on_id)))
            if not cached_bytes:
                raise RuntimeError(f"Studio try-on cached payload missing right after write: {try_on_id}")
            if not _is_valid_image_payload(cached_bytes):
                raise RuntimeError(f"Studio try-on cached payload invalid image bytes: {try_on_id}")
            # Also cache by parent+background combo (1-hour TTL) for instant re-use
            loop.run_until_complete(
                cache.store_studio_result(parent_try_on_id, studio_background_id, result_bytes)
            )
        finally:
            loop.close()

        record.processing_status = "completed"
        record.result_cache_key = cache_key
        record.processing_time_seconds = round(elapsed, 2)
        record.completed_at = datetime.utcnow()
        db.commit()

        if usage_event_id:
            import asyncio
            usage = UsageGovernanceService(db)
            loop2 = asyncio.new_event_loop()
            loop2.run_until_complete(
                usage.finalize_usage(
                    event_id=usage_event_id,
                    reference_id=str(try_on_id),
                )
            )
            loop2.close()

        logger.info(f"Studio try-on {try_on_id} completed in {elapsed:.1f}s")

    except Exception as e:
        logger.error(f"Studio try-on {try_on_id} failed: {e}", exc_info=True)
        try:
            record = db.query(TryOn).filter_by(try_on_id=try_on_id).first()
            if record:
                record.processing_status = "failed"
                record.error_message = str(e)[:500]
                db.commit()
            if usage_event_id:
                import asyncio
                usage = UsageGovernanceService(db)
                loop2 = asyncio.new_event_loop()
                loop2.run_until_complete(
                    usage.refund_usage(
                        event_id=usage_event_id,
                        reason=f"studio_failed:{str(e)[:240]}",
                    )
                )
                loop2.close()
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
    x_logged_in_customer_id: Optional[str] = Header(None, alias="X-Logged-In-Customer-Id"),
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

    usage_event_id: Optional[str] = None
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

        product = db.query(Product).filter_by(product_id=original.product_id).first()
        if not product:
            raise HTTPException(404, "Product not found for original try-on")
        store = db.query(Store).filter_by(store_id=product.store_id).first()
        if not store:
            raise HTTPException(404, "Store not found")

        widget_cfg = db.query(WidgetConfig).filter_by(store_id=store.store_id).first()
        weekly_limit = widget_cfg.weekly_tryon_limit if widget_cfg else settings.WEEKLY_TRYON_LIMIT_DEFAULT
        customer_identifier = _normalize_customer_id(x_logged_in_customer_id)

        usage = UsageGovernanceService(db)
        reservation = await usage.reserve_generation(
            store=store,
            action_type="customer_tryon_studio",
            reference_type="try_on",
            customer_identifier=customer_identifier,
            enforce_weekly_limit=True,
            weekly_tryon_limit=weekly_limit,
        )
        usage_event_id = reservation.event_id

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
            usage_event_id=usage_event_id,
        )

        logger.info(f"Studio try-on queued: {new_try_on_id} (parent={request.try_on_id}, bg={bg.image_path})")

        return {
            "try_on_id": str(new_try_on_id),
            "status": "processing",
            "estimated_time_seconds": 45,
        }

    except HTTPException:
        if usage_event_id:
            usage = UsageGovernanceService(db)
            await usage.refund_usage(
                event_id=usage_event_id,
                reason="studio_request_rejected",
            )
        raise
    except Exception as e:
        logger.error(f"Studio try-on error: {e}", exc_info=True)
        if usage_event_id:
            usage = UsageGovernanceService(db)
            await usage.refund_usage(
                event_id=usage_event_id,
                reason=f"studio_request_error:{str(e)[:240]}",
            )
        raise HTTPException(500, f"Studio try-on generation failed: {str(e)}")


# ============================================================================
# Core Try-On Endpoints
# ============================================================================

@router.post("/generate", status_code=202)
async def generate_tryon(
    request: TryOnGenerateRequest,
    background_tasks: BackgroundTasks,
    x_logged_in_customer_id: Optional[str] = Header(None, alias="X-Logged-In-Customer-Id"),
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
    usage_event_id: Optional[str] = None
    try:
        # Validate product
        product = db.query(Product).filter_by(
            product_id=str(request.product_id)
        ).first()
        if not product:
            raise HTTPException(404, "Product not found")
        if str(product.store_id) != str(session.store_id):
            raise HTTPException(403, "Product does not belong to this store")

        cache = CacheService()
        redis = get_redis()
        reuse_ttl = settings.TRYON_RESULT_TTL_SECONDS
        reuse_cutoff = datetime.utcnow() - timedelta(seconds=reuse_ttl)

        # Fast path: user+product reuse key
        if session.user_identifier:
            reuse_key = _build_tryon_reuse_key(
                store_id=str(session.store_id),
                user_identifier=session.user_identifier,
                product_id=str(product.product_id),
                measurement_id=str(session.measurement_id) if session.measurement_id else None,
            )
            existing_tryon_id = redis.get(reuse_key)
            if isinstance(existing_tryon_id, bytes):
                existing_tryon_id = existing_tryon_id.decode("utf-8")
            if existing_tryon_id:
                existing = db.query(TryOn).filter_by(try_on_id=existing_tryon_id).first()
                if (
                    existing
                    and existing.processing_status == "completed"
                    and str(existing.product_id) == str(product.product_id)
                    and str(existing.measurement_id) == str(session.measurement_id)
                    and existing.created_at
                    and existing.created_at >= reuse_cutoff
                ):
                    cached_payload = await cache.get_tryon_result(str(existing.try_on_id))
                    if cached_payload:
                        return {
                            "try_on_id": str(existing.try_on_id),
                            "status": "completed",
                            "result_image_url": f"/api/v1/tryon/{existing.try_on_id}/image",
                            "reused": True,
                        }

        # Fallback: same measurement+product reuse
        if session.measurement_id:
            existing = (
                db.query(TryOn)
                .filter_by(
                    measurement_id=session.measurement_id,
                    product_id=product.product_id,
                    processing_status="completed",
                )
                .order_by(TryOn.created_at.desc())
                .first()
            )
            if existing and existing.created_at and existing.created_at >= reuse_cutoff:
                cached_payload = await cache.get_tryon_result(str(existing.try_on_id))
                if cached_payload:
                    if session.user_identifier:
                        reuse_key = _build_tryon_reuse_key(
                            store_id=str(session.store_id),
                            user_identifier=session.user_identifier,
                            product_id=str(product.product_id),
                            measurement_id=str(session.measurement_id) if session.measurement_id else None,
                        )
                        redis.set(reuse_key, str(existing.try_on_id), reuse_ttl)
                    return {
                        "try_on_id": str(existing.try_on_id),
                        "status": "completed",
                        "result_image_url": f"/api/v1/tryon/{existing.try_on_id}/image",
                        "reused": True,
                    }

        # Get person's front image from session cache
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
        logger.info(
            "Selected product image for try-on: product_id=%s category=%s image_url=%s",
            product.product_id,
            product.category or "tops",
            product_image_url,
        )

        store = db.query(Store).filter_by(store_id=session.store_id).first()
        if not store:
            raise HTTPException(404, "Store not found")
        widget_cfg = db.query(WidgetConfig).filter_by(store_id=store.store_id).first()
        weekly_limit = widget_cfg.weekly_tryon_limit if widget_cfg else settings.WEEKLY_TRYON_LIMIT_DEFAULT
        customer_identifier = _normalize_customer_id(x_logged_in_customer_id)

        usage = UsageGovernanceService(db)
        reservation = await usage.reserve_generation(
            store=store,
            action_type="customer_tryon_generate",
            reference_type="try_on",
            customer_identifier=customer_identifier,
            enforce_weekly_limit=True,
            weekly_tryon_limit=weekly_limit,
        )
        usage_event_id = reservation.event_id

        # Create TryOn DB record (measurement_id is nullable for this flow)
        try_on_id = uuid.uuid4()
        tryon_record = TryOn(
            try_on_id=try_on_id,
            measurement_id=session.measurement_id,
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
            store_id=str(session.store_id),
            user_identifier=session.user_identifier,
            product_id=str(product.product_id),
            measurement_id=str(session.measurement_id) if session.measurement_id else None,
            usage_event_id=usage_event_id,
        )

        logger.info(f"Try-on queued: {try_on_id} for product={product.title}")

        return {
            "try_on_id": str(try_on_id),
            "status": "processing",
            "estimated_time_seconds": 45,
            "reused": False,
        }

    except HTTPException:
        if usage_event_id:
            usage = UsageGovernanceService(db)
            await usage.refund_usage(
                event_id=usage_event_id,
                reason="tryon_request_rejected",
            )
        raise
    except Exception as e:
        logger.error(f"Try-on generation error: {e}", exc_info=True)
        if usage_event_id:
            usage = UsageGovernanceService(db)
            await usage.refund_usage(
                event_id=usage_event_id,
                reason=f"tryon_request_error:{str(e)[:240]}",
            )
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
        cache = CacheService()
        cached = await cache.get_tryon_result(str(try_on_id))
        if not cached:
            record.processing_status = "failed"
            record.error_message = "Generated image expired or missing from cache. Please regenerate."
            db.commit()
            status = "failed"
            message = record.error_message
        else:
            progress = 100
            message = "Try-on image ready"
            result_image_url = f"/api/v1/tryon/{try_on_id}/image"
            if record.completed_at:
                cache_expires_at = record.completed_at + timedelta(seconds=settings.TRYON_RESULT_TTL_SECONDS)
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
    if not _is_valid_image_payload(image_bytes):
        logger.error("Cached try-on payload is not a valid image for try_on_id=%s", try_on_id)
        raise HTTPException(500, "Cached try-on payload is invalid. Please generate again.")

    media_type = _infer_image_media_type(image_bytes)
    return Response(
        content=image_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{try_on_id}.jpg"'},
    )
