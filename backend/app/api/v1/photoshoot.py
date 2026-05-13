"""
AI Photoshoot API Endpoints (Merchant-Facing)
Three features: ghost mannequin, try-on for model, model swap.

Merchant routes resolve the active store from Shopify App Bridge auth when present,
with header fallbacks for the current embedded-app migration state.
Image-serving endpoints are public (no auth) so Shopify CDN can fetch them.
"""

import os
import re
import uuid
import time
import logging
from datetime import datetime
from typing import Optional, Set

import requests
from fastapi import (
    APIRouter, Depends, HTTPException,
    BackgroundTasks, UploadFile, File, Form, Query
)
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session as DBSession

from app.api.store_context import get_current_merchant_store, require_shopify_access_token
from app.core.database import get_db
from app.models.database import Store, Product, PhotoshootJob, PhotoshootModel, PhotoshootModelFace, GhostMannequinRef
from app.models.schemas import (
    PhotoshootJobResponse,
    PhotoshootModelResponse,
    PhotoshootModelFaceResponse,
    GhostMannequinRefResponse,
    PhotoshootApproveRequest,
    PhotoshootApproveResponse,
)
from app.services.cache_service import CacheService
from app.services.media_storage_service import get_media_storage_service
from app.services.usage_governance_service import UsageGovernanceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/merchant/photoshoot", tags=["AI Photoshoot"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
ALLOWED_CLOTHING_TYPES = {"tops", "bottoms", "dresses", "outerwear"}


# ─────────────────────────────────────────────────────────────
# Static file helpers
# ─────────────────────────────────────────────────────────────

def _static_root() -> str:
    """Absolute path to backend/static/"""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "static",
    )


def _read_static_image(image_path: str) -> bytes:
    """Read an image from static/ using image_path relative to the static root."""
    file_path = os.path.join(_static_root(), image_path)
    if not os.path.exists(file_path):
        raise HTTPException(404, f"Image file not found: {image_path}")
    with open(file_path, "rb") as f:
        return f.read()


def _media_type(image_path: str) -> str:
    return "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"


def _read_library_image(*, object_path: Optional[str], image_path: Optional[str]) -> bytes:
    """Load library image bytes from GCS object path with static fallback."""
    storage = get_media_storage_service()
    if object_path and storage.enabled:
        payload = storage.download_bytes(object_path)
        if payload:
            return payload

    if not image_path:
        raise HTTPException(404, "Image file not found")
    return _read_static_image(image_path)


def _normalize_shopify_product_gid(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip()
    if not normalized:
        return None
    if normalized.startswith("gid://shopify/Product/"):
        return normalized
    if normalized.isdigit():
        return f"gid://shopify/Product/{normalized}"
    return normalized


def _extract_shopify_numeric_id(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip()
    if not normalized:
        return None
    if normalized.isdigit():
        return normalized
    match = re.search(r"/(\d+)$", normalized)
    if match:
        return match.group(1)
    return None


def _resolve_product_for_store(
    *,
    db: DBSession,
    store: Store,
    shopify_product_gid: Optional[str],
) -> Product:
    normalized_gid = _normalize_shopify_product_gid(shopify_product_gid)
    if not normalized_gid:
        raise HTTPException(422, "shopify_product_gid is required for store image selection")
    numeric_id = _extract_shopify_numeric_id(normalized_gid)
    if not numeric_id:
        raise HTTPException(422, "shopify_product_gid is invalid")
    product = db.query(Product).filter_by(
        store_id=store.store_id,
        shopify_product_id=numeric_id,
    ).first()
    if not product:
        raise HTTPException(404, "Product not found for this store")
    return product


def _extract_product_image_urls(product: Product) -> Set[str]:
    urls: Set[str] = set()
    for image in product.images or []:
        if isinstance(image, dict):
            src = image.get("src")
        else:
            src = getattr(image, "src", None)
        if isinstance(src, str) and src.strip():
            urls.add(src.strip())
    return urls


def _validate_store_image_url(
    *,
    product: Product,
    image_url: str,
    field_name: str,
) -> None:
    normalized_url = (image_url or "").strip()
    if not normalized_url:
        raise HTTPException(422, f"{field_name} is required")
    allowed_urls = _extract_product_image_urls(product)
    if normalized_url not in allowed_urls:
        raise HTTPException(422, f"{field_name} must be selected from the chosen store product gallery")


async def _read_upload_image(
    upload: UploadFile,
    *,
    field_name: str,
) -> bytes:
    if upload is None:
        raise HTTPException(422, f"{field_name} is required")
    payload = await upload.read()
    if not payload:
        raise HTTPException(422, f"{field_name} is empty")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(422, f"{field_name} exceeds the 10MB upload limit")
    content_type = (upload.content_type or "").lower().strip()
    if content_type and content_type not in ALLOWED_UPLOAD_MIME_TYPES:
        raise HTTPException(422, f"{field_name} must be jpg, png, or webp")
    return payload


def _download_image_from_url(*, image_url: str, field_name: str) -> bytes:
    try:
        response = requests.get(image_url, timeout=20)
        response.raise_for_status()
    except Exception as exc:
        raise HTTPException(422, f"Could not download {field_name}: {exc}")
    payload = response.content
    if not payload:
        raise HTTPException(422, f"{field_name} returned empty content")
    return payload


def _require_storage_enabled() -> None:
    storage = get_media_storage_service()
    if not storage.enabled:
        reason = storage.disabled_reason or "unknown configuration error"
        raise HTTPException(
            500,
            f"Media storage is not configured. Ensure GCS bucket access is available. Reason: {reason}",
        )


# ─────────────────────────────────────────────────────────────
# Background task helpers
# ─────────────────────────────────────────────────────────────

def _job_status_response(job: PhotoshootJob) -> PhotoshootJobResponse:
    """Build a PhotoshootJobResponse from a DB record."""
    status = job.processing_status
    progress = {"queued": 0, "processing": 50, "completed": 100}.get(status)
    messages = {
        "queued": "Queued for processing...",
        "processing": "Generating image with AI...",
        "completed": "Image ready",
        "failed": job.error_message or "Image generation failed",
    }
    result_image_url = (
        f"/api/v1/merchant/photoshoot/jobs/{job.job_id}/result"
        if status == "completed"
        else None
    )
    return PhotoshootJobResponse(
        job_id=job.job_id,
        job_type=job.job_type,
        status=status,
        progress=progress,
        message=messages.get(status),
        result_image_url=result_image_url,
        processing_time_seconds=job.processing_time_seconds,
        error=job.error_message if status == "failed" else None,
        retry_allowed=(status == "failed"),
    )


def _run_photoshoot_job(
    job_id: str,
    job_type: str,
    image1_bytes: bytes,
    image2_bytes: bytes,
    clothing_type: Optional[str] = None,
    usage_event_id: Optional[str] = None,
):
    """
    Background task: run the Gemini generation, cache the result, update DB.
    Handles all three job types — job_type determines which prompt is used.
    clothing_type is only forwarded for ghost_mannequin.
    """
    from app.core.database import SessionLocal
    from app.services.photoshoot_service import PhotoshootService

    db = SessionLocal()
    try:
        job = db.query(PhotoshootJob).filter_by(job_id=job_id).first()
        if not job:
            return
        job.processing_status = "processing"
        db.commit()

        start = time.time()
        service = PhotoshootService()

        if job_type == "ghost_mannequin":
            result_bytes = service.generate_ghost_mannequin(
                image1_bytes, image2_bytes, clothing_type=clothing_type
            )
        elif job_type == "try_on_model":
            result_bytes = service.generate_try_on_model(image1_bytes, image2_bytes)
        elif job_type == "model_swap":
            result_bytes = service.generate_model_swap(image1_bytes, image2_bytes)
        else:
            raise ValueError(f"Unknown job_type: {job_type}")

        elapsed = time.time() - start

        import asyncio
        cache = CacheService()
        loop = asyncio.new_event_loop()
        cache_key = loop.run_until_complete(
            cache.store_photoshoot_result(job_id, result_bytes)
        )
        loop.close()

        storage = get_media_storage_service()
        if not storage.enabled:
            raise RuntimeError("Media storage is unavailable during photoshoot processing")

        output_path = storage.build_object_path(
            relative_dir=f"stores/{job.store_id}/photoshoot/{job_type}/{job_id}/output",
            payload=result_bytes,
            stem="output",
        )
        output_object_path = storage.upload_bytes(
            object_path=output_path,
            payload=result_bytes,
            metadata={
                "flow": "merchant",
                "type": "photoshoot_output",
                "job_type": job_type,
            },
        )
        if not output_object_path:
            raise RuntimeError("Failed to archive photoshoot output to media storage")

        job.processing_status = "completed"
        job.result_cache_key = cache_key
        job.output_object_path = output_object_path
        job.processing_time_seconds = round(elapsed, 2)
        job.completed_at = datetime.utcnow()
        db.commit()

        if usage_event_id:
            import asyncio
            usage = UsageGovernanceService(db)
            loop2 = asyncio.new_event_loop()
            loop2.run_until_complete(
                usage.finalize_usage(
                    event_id=usage_event_id,
                    reference_id=job_id,
                )
            )
            loop2.close()

        logger.info(f"Photoshoot job {job_id} ({job_type}) completed in {elapsed:.1f}s")

    except Exception as e:
        logger.error(f"Photoshoot job {job_id} failed: {e}", exc_info=True)
        try:
            job = db.query(PhotoshootJob).filter_by(job_id=job_id).first()
            if job:
                job.processing_status = "failed"
                job.error_message = str(e)[:500]
                db.commit()
            if usage_event_id:
                import asyncio
                usage = UsageGovernanceService(db)
                loop2 = asyncio.new_event_loop()
                loop2.run_until_complete(
                    usage.refund_usage(
                        event_id=usage_event_id,
                        reason=f"photoshoot_failed:{str(e)[:240]}",
                    )
                )
                loop2.close()
        except Exception:
            pass
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# Model Library Endpoints (full-body — for try-on-model)
# ─────────────────────────────────────────────────────────────

@router.get("/models", response_model=list[PhotoshootModelResponse])
async def list_photoshoot_models(
    gender: str = Query("unisex", description="Filter by gender: male | female | unisex"),
    age: Optional[str] = Query(None, description="Filter by age: 18-25 | 26-35 | 36-45 | 45+"),
    body_type: Optional[str] = Query(None, description="Filter by body type: slim | athletic | regular | plus"),
    db: DBSession = Depends(get_db),
    store: Store = Depends(get_current_merchant_store),
):
    """
    List available full-body model photos from the library.

    Returns active models for the given gender plus all 'unisex' models.
    Optionally narrow results by age and body_type.
    """
    query = db.query(PhotoshootModel).filter(
        PhotoshootModel.is_active == True,
        PhotoshootModel.gender.in_([gender, "unisex"]),
    )
    if age:
        query = query.filter(PhotoshootModel.age == age)
    if body_type:
        query = query.filter(PhotoshootModel.body_type == body_type)

    models = query.all()

    return [
        PhotoshootModelResponse(
            id=m.id,
            gender=m.gender,
            age=m.age,
            body_type=m.body_type,
            image_url=f"/api/v1/merchant/photoshoot/models/{m.id}/image",
        )
        for m in models
    ]


@router.get("/models/{model_id}/image")
async def get_photoshoot_model_image(
    model_id: str,
    db: DBSession = Depends(get_db),
):
    """Serve a photoshoot model photo via short-lived signed URL."""
    model = db.query(PhotoshootModel).filter_by(id=model_id, is_active=True).first()
    if not model:
        raise HTTPException(404, "Model not found")

    storage = get_media_storage_service()
    if model.object_path and storage.enabled:
        signed_url = storage.generate_signed_get_url(model.object_path)
        if signed_url:
            return RedirectResponse(url=signed_url, status_code=307)

    image_bytes = _read_library_image(object_path=model.object_path, image_path=model.image_path)
    return Response(content=image_bytes, media_type=_media_type(model.image_path))


# ─────────────────────────────────────────────────────────────
# Model Face Library Endpoints (headshots — for model swap)
# ─────────────────────────────────────────────────────────────

@router.get("/model-faces", response_model=list[PhotoshootModelFaceResponse])
async def list_model_faces(
    gender: str = Query(..., description="Filter by gender: male | female"),
    age: Optional[str] = Query(None, description="Filter by age: 18-25 | 26-35 | 36-45 | 45+"),
    skin_tone: Optional[str] = Query(None, description="Filter by skin tone: fair | light | medium | tan | dark"),
    db: DBSession = Depends(get_db),
    store: Store = Depends(get_current_merchant_store),
):
    """
    List available face/headshot photos from the face library.

    Used by the model swap feature to select the replacement face.
    """
    query = db.query(PhotoshootModelFace).filter(
        PhotoshootModelFace.is_active == True,
        PhotoshootModelFace.gender == gender,
    )
    if age:
        query = query.filter(PhotoshootModelFace.age == age)
    if skin_tone:
        query = query.filter(PhotoshootModelFace.skin_tone == skin_tone)

    faces = query.all()

    return [
        PhotoshootModelFaceResponse(
            id=f.id,
            gender=f.gender,
            age=f.age,
            skin_tone=f.skin_tone,
            image_url=f"/api/v1/merchant/photoshoot/model-faces/{f.id}/image",
        )
        for f in faces
    ]


@router.get("/model-faces/{face_id}/image")
async def get_model_face_image(
    face_id: str,
    db: DBSession = Depends(get_db),
):
    """Serve a face/headshot photo via short-lived signed URL."""
    face = db.query(PhotoshootModelFace).filter_by(id=face_id, is_active=True).first()
    if not face:
        raise HTTPException(404, "Model face not found")

    storage = get_media_storage_service()
    if face.object_path and storage.enabled:
        signed_url = storage.generate_signed_get_url(face.object_path)
        if signed_url:
            return RedirectResponse(url=signed_url, status_code=307)

    image_bytes = _read_library_image(object_path=face.object_path, image_path=face.image_path)
    return Response(content=image_bytes, media_type=_media_type(face.image_path))


# ─────────────────────────────────────────────────────────────
# Ghost Mannequin Reference Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/ghost-mannequin-refs", response_model=list[GhostMannequinRefResponse])
async def list_ghost_mannequin_refs(
    clothing_type: str = Query(..., description="Clothing type: tops | bottoms | dresses | outerwear"),
    db: DBSession = Depends(get_db),
    store: Store = Depends(get_current_merchant_store),
):
    """
    List the 3 reference pose images (front/side/back) for a clothing type.

    Displayed in the ghost mannequin UI to guide the merchant on which product
    photos produce the best ghost mannequin result for this garment type.
    """
    refs = db.query(GhostMannequinRef).filter(
        GhostMannequinRef.clothing_type == clothing_type
    ).order_by(GhostMannequinRef.pose).all()

    return [
        GhostMannequinRefResponse(
            id=r.id,
            clothing_type=r.clothing_type,
            pose=r.pose,
            image_url=f"/api/v1/merchant/photoshoot/ghost-mannequin-refs/{r.id}/image",
        )
        for r in refs
    ]


@router.get("/ghost-mannequin-refs/{ref_id}/image")
async def get_ghost_mannequin_ref_image(
    ref_id: str,
    db: DBSession = Depends(get_db),
):
    """Serve a ghost mannequin reference image via short-lived signed URL."""
    ref = db.query(GhostMannequinRef).filter_by(id=ref_id).first()
    if not ref:
        raise HTTPException(404, "Ghost mannequin reference not found")

    storage = get_media_storage_service()
    if ref.object_path and storage.enabled:
        signed_url = storage.generate_signed_get_url(ref.object_path)
        if signed_url:
            return RedirectResponse(url=signed_url, status_code=307)

    image_bytes = _read_library_image(object_path=ref.object_path, image_path=ref.image_path)
    return Response(content=image_bytes, media_type=_media_type(ref.image_path))


# ─────────────────────────────────────────────────────────────
# Generation Endpoints
# ─────────────────────────────────────────────────────────────

@router.post("/ghost-mannequin", status_code=202, response_model=PhotoshootJobResponse)
async def start_ghost_mannequin(
    background_tasks: BackgroundTasks,
    shopify_product_gid: Optional[str] = Form(None, description="Optional Shopify product GID"),
    clothing_type: str = Form(..., description="Garment type: tops | bottoms | dresses | outerwear"),
    image1_url: Optional[str] = Form(None, description="First product image URL from selected store product"),
    image2_url: Optional[str] = Form(None, description="Second product image URL from selected store product"),
    image1_file: Optional[UploadFile] = File(None, description="Optional local upload for image 1"),
    image2_file: Optional[UploadFile] = File(None, description="Optional local upload for image 2"),
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Start a ghost mannequin generation job.

    Accepts exactly two slots. Each slot can be either:
    - a URL from the selected store product gallery, or
    - a local uploaded image file.

    Returns 202 immediately. Poll GET /jobs/{job_id}/status for result.
    """
    _require_storage_enabled()

    if clothing_type not in ALLOWED_CLOTHING_TYPES:
        raise HTTPException(422, f"Invalid clothing_type. Expected one of: {', '.join(sorted(ALLOWED_CLOTHING_TYPES))}")

    normalized_product_gid = _normalize_shopify_product_gid(shopify_product_gid)

    has_image1_url = bool((image1_url or "").strip())
    has_image2_url = bool((image2_url or "").strip())
    has_image1_file = bool(image1_file and image1_file.filename)
    has_image2_file = bool(image2_file and image2_file.filename)

    if has_image1_url == has_image1_file:
        raise HTTPException(422, "Provide exactly one of image1_url or image1_file")
    if has_image2_url == has_image2_file:
        raise HTTPException(422, "Provide exactly one of image2_url or image2_file")

    selected_product: Optional[Product] = None
    if has_image1_url or has_image2_url:
        selected_product = _resolve_product_for_store(
            db=db,
            store=store,
            shopify_product_gid=normalized_product_gid,
        )
        if has_image1_url:
            _validate_store_image_url(product=selected_product, image_url=image1_url or "", field_name="image1_url")
        if has_image2_url:
            _validate_store_image_url(product=selected_product, image_url=image2_url or "", field_name="image2_url")
    elif normalized_product_gid:
        _resolve_product_for_store(
            db=db,
            store=store,
            shopify_product_gid=normalized_product_gid,
        )

    usage_event_id: Optional[str] = None
    try:
        if has_image1_url:
            image1_bytes = _download_image_from_url(image_url=(image1_url or "").strip(), field_name="image1_url")
        else:
            image1_bytes = await _read_upload_image(image1_file, field_name="image1_file")

        if has_image2_url:
            image2_bytes = _download_image_from_url(image_url=(image2_url or "").strip(), field_name="image2_url")
        else:
            image2_bytes = await _read_upload_image(image2_file, field_name="image2_file")

        usage = UsageGovernanceService(db)
        reservation = await usage.reserve_generation(
            store=store,
            action_type="merchant_ghost_mannequin",
            reference_type="photoshoot_job",
            customer_identifier=None,
            enforce_weekly_limit=False,
        )
        usage_event_id = reservation.event_id

        job_id = uuid.uuid4()
        storage = get_media_storage_service()
        input1_object_path = None
        input2_object_path = None
        input1_path = storage.build_object_path(
            relative_dir=f"stores/{store.store_id}/photoshoot/ghost_mannequin/{job_id}/inputs/1",
            payload=image1_bytes,
            stem="input1",
        )
        input2_path = storage.build_object_path(
            relative_dir=f"stores/{store.store_id}/photoshoot/ghost_mannequin/{job_id}/inputs/2",
            payload=image2_bytes,
            stem="input2",
        )
        input1_object_path = storage.upload_bytes(
            object_path=input1_path,
            payload=image1_bytes,
            metadata={"flow": "merchant", "type": "photoshoot_input", "job_type": "ghost_mannequin"},
        )
        input2_object_path = storage.upload_bytes(
            object_path=input2_path,
            payload=image2_bytes,
            metadata={"flow": "merchant", "type": "photoshoot_input", "job_type": "ghost_mannequin"},
        )
        if not input1_object_path or not input2_object_path:
            raise HTTPException(500, "Failed to archive ghost mannequin input images to media storage")

        job = PhotoshootJob(
            job_id=job_id,
            store_id=store.store_id,
            job_type="ghost_mannequin",
            shopify_product_gid=normalized_product_gid,
            processing_status="queued",
            input1_object_path=input1_object_path,
            input2_object_path=input2_object_path,
        )
        db.add(job)
        db.commit()

        background_tasks.add_task(
            _run_photoshoot_job,
            job_id=str(job_id),
            job_type="ghost_mannequin",
            image1_bytes=image1_bytes,
            image2_bytes=image2_bytes,
            clothing_type=clothing_type,
            usage_event_id=usage_event_id,
        )

        logger.info(f"Ghost mannequin job queued: {job_id} (clothing_type={clothing_type})")
        return _job_status_response(job)

    except HTTPException:
        if usage_event_id:
            usage = UsageGovernanceService(db)
            await usage.refund_usage(
                event_id=usage_event_id,
                reason="ghost_mannequin_request_rejected",
            )
        raise
    except Exception as e:
        logger.error(f"ghost-mannequin start error: {e}", exc_info=True)
        if usage_event_id:
            usage = UsageGovernanceService(db)
            await usage.refund_usage(
                event_id=usage_event_id,
                reason=f"ghost_mannequin_request_error:{str(e)[:240]}",
            )
        raise HTTPException(500, f"Failed to start ghost mannequin job: {e}")


@router.post("/try-on-model", status_code=202, response_model=PhotoshootJobResponse)
async def start_try_on_model(
    background_tasks: BackgroundTasks,
    shopify_product_gid: Optional[str] = Form(None, description="Optional Shopify product GID"),
    product_image_url: Optional[str] = Form(None, description="Product image URL selected from store"),
    product_image_file: Optional[UploadFile] = File(None, description="Optional uploaded product image"),
    library_id: Optional[str] = Form(None, description="ID of a built-in model photo"),
    model_library_id: Optional[str] = Form(None, description="Alias for library_id"),
    photo_upload: Optional[UploadFile] = File(None, description="Uploaded model photo"),
    model_image: Optional[UploadFile] = File(None, description="Alias for photo_upload"),
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Start a try-on for model job.

    Provide one product source (URL from store product gallery or local file) and either:
    - library_id — pick from the built-in model library
    - photo_upload — upload your own model photo

    Returns 202 immediately. Poll GET /jobs/{job_id}/status for result.
    """
    _require_storage_enabled()

    normalized_product_gid = _normalize_shopify_product_gid(shopify_product_gid)
    resolved_library_id = (library_id or "").strip() or None
    alias_library_id = (model_library_id or "").strip() or None
    if resolved_library_id and alias_library_id and resolved_library_id != alias_library_id:
        raise HTTPException(422, "library_id and model_library_id must match when both are provided")
    if not resolved_library_id:
        resolved_library_id = alias_library_id

    resolved_photo_upload = photo_upload if photo_upload and photo_upload.filename else None
    alias_photo_upload = model_image if model_image and model_image.filename else None
    if resolved_photo_upload and alias_photo_upload:
        raise HTTPException(422, "Provide only one of photo_upload or model_image")
    if not resolved_photo_upload:
        resolved_photo_upload = alias_photo_upload

    has_product_url = bool((product_image_url or "").strip())
    has_product_file = bool(product_image_file and product_image_file.filename)
    if has_product_url == has_product_file:
        raise HTTPException(422, "Provide exactly one of product_image_url or product_image_file")

    if not resolved_library_id and not resolved_photo_upload:
        raise HTTPException(422, "Provide either library_id/model_library_id or upload a model image")
    if resolved_library_id and resolved_photo_upload:
        raise HTTPException(422, "Provide only one model source: library or upload")

    selected_product: Optional[Product] = None
    if has_product_url:
        selected_product = _resolve_product_for_store(
            db=db,
            store=store,
            shopify_product_gid=normalized_product_gid,
        )
        _validate_store_image_url(
            product=selected_product,
            image_url=(product_image_url or "").strip(),
            field_name="product_image_url",
        )
    elif normalized_product_gid:
        _resolve_product_for_store(
            db=db,
            store=store,
            shopify_product_gid=normalized_product_gid,
        )

    usage_event_id: Optional[str] = None
    try:
        if has_product_url:
            product_bytes = _download_image_from_url(
                image_url=(product_image_url or "").strip(),
                field_name="product_image_url",
            )
        else:
            product_bytes = await _read_upload_image(product_image_file, field_name="product_image_file")

        if resolved_library_id:
            model_record = db.query(PhotoshootModel).filter_by(
                id=resolved_library_id, is_active=True
            ).first()
            if not model_record:
                raise HTTPException(404, "Model not found in library")
            model_bytes = _read_library_image(
                object_path=model_record.object_path,
                image_path=model_record.image_path,
            )
        else:
            model_bytes = await _read_upload_image(resolved_photo_upload, field_name="photo_upload")

        usage = UsageGovernanceService(db)
        reservation = await usage.reserve_generation(
            store=store,
            action_type="merchant_try_on_model",
            reference_type="photoshoot_job",
            customer_identifier=None,
            enforce_weekly_limit=False,
        )
        usage_event_id = reservation.event_id

        job_id = uuid.uuid4()
        storage = get_media_storage_service()
        input1_path = storage.build_object_path(
            relative_dir=f"stores/{store.store_id}/photoshoot/try_on_model/{job_id}/inputs/1",
            payload=product_bytes,
            stem="input1",
        )
        input2_path = storage.build_object_path(
            relative_dir=f"stores/{store.store_id}/photoshoot/try_on_model/{job_id}/inputs/2",
            payload=model_bytes,
            stem="input2",
        )
        input1_object_path = storage.upload_bytes(
            object_path=input1_path,
            payload=product_bytes,
            metadata={"flow": "merchant", "type": "photoshoot_input", "job_type": "try_on_model"},
        )
        input2_object_path = storage.upload_bytes(
            object_path=input2_path,
            payload=model_bytes,
            metadata={"flow": "merchant", "type": "photoshoot_input", "job_type": "try_on_model"},
        )
        if not input1_object_path or not input2_object_path:
            raise HTTPException(500, "Failed to archive try-on model input images to media storage")

        job = PhotoshootJob(
            job_id=job_id,
            store_id=store.store_id,
            job_type="try_on_model",
            shopify_product_gid=normalized_product_gid,
            processing_status="queued",
            input1_object_path=input1_object_path,
            input2_object_path=input2_object_path,
        )
        db.add(job)
        db.commit()

        background_tasks.add_task(
            _run_photoshoot_job,
            job_id=str(job_id),
            job_type="try_on_model",
            image1_bytes=product_bytes,
            image2_bytes=model_bytes,
            usage_event_id=usage_event_id,
        )

        logger.info(f"Try-on model job queued: {job_id}")
        return _job_status_response(job)

    except HTTPException:
        if usage_event_id:
            usage = UsageGovernanceService(db)
            await usage.refund_usage(
                event_id=usage_event_id,
                reason="try_on_model_request_rejected",
            )
        raise
    except Exception as e:
        logger.error(f"try-on-model start error: {e}", exc_info=True)
        if usage_event_id:
            usage = UsageGovernanceService(db)
            await usage.refund_usage(
                event_id=usage_event_id,
                reason=f"try_on_model_request_error:{str(e)[:240]}",
            )
        raise HTTPException(500, f"Failed to start try-on model job: {e}")


@router.post("/model-swap", status_code=202, response_model=PhotoshootJobResponse)
async def start_model_swap(
    background_tasks: BackgroundTasks,
    shopify_product_gid: Optional[str] = Form(None, description="Optional Shopify product GID"),
    original_image_url: Optional[str] = Form(None, description="Original image URL from selected store product"),
    original_image_file: Optional[UploadFile] = File(None, description="Optional uploaded original image"),
    face_library_id: Optional[str] = Form(None, description="ID of a face photo from the face library"),
    new_model_library_id: Optional[str] = Form(None, description="Alias for face_library_id"),
    face_image: Optional[UploadFile] = File(None, description="Uploaded face/headshot photo"),
    new_model_image: Optional[UploadFile] = File(None, description="Alias for face_image"),
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Start a model swap job (face-only swap).

    Provide one original image source (URL from store product gallery or local file) and either:
    - face_library_id — pick a replacement face from the built-in face library
    - face_image — upload a headshot photo

    Only the face is replaced. The body, pose, clothing, background, and
    lighting from the original image remain identical.

    Returns 202 immediately. Poll GET /jobs/{job_id}/status for result.
    """
    _require_storage_enabled()

    normalized_product_gid = _normalize_shopify_product_gid(shopify_product_gid)

    resolved_face_library_id = (face_library_id or "").strip() or None
    alias_face_library_id = (new_model_library_id or "").strip() or None
    if resolved_face_library_id and alias_face_library_id and resolved_face_library_id != alias_face_library_id:
        raise HTTPException(422, "face_library_id and new_model_library_id must match when both are provided")
    if not resolved_face_library_id:
        resolved_face_library_id = alias_face_library_id

    resolved_face_upload = face_image if face_image and face_image.filename else None
    alias_face_upload = new_model_image if new_model_image and new_model_image.filename else None
    if resolved_face_upload and alias_face_upload:
        raise HTTPException(422, "Provide only one of face_image or new_model_image")
    if not resolved_face_upload:
        resolved_face_upload = alias_face_upload

    has_original_url = bool((original_image_url or "").strip())
    has_original_file = bool(original_image_file and original_image_file.filename)
    if has_original_url == has_original_file:
        raise HTTPException(422, "Provide exactly one of original_image_url or original_image_file")

    if not resolved_face_library_id and not resolved_face_upload:
        raise HTTPException(422, "Provide either face_library_id/new_model_library_id or upload a face image")
    if resolved_face_library_id and resolved_face_upload:
        raise HTTPException(422, "Provide only one face source: library or upload")

    selected_product: Optional[Product] = None
    if has_original_url:
        selected_product = _resolve_product_for_store(
            db=db,
            store=store,
            shopify_product_gid=normalized_product_gid,
        )
        _validate_store_image_url(
            product=selected_product,
            image_url=(original_image_url or "").strip(),
            field_name="original_image_url",
        )
    elif normalized_product_gid:
        _resolve_product_for_store(
            db=db,
            store=store,
            shopify_product_gid=normalized_product_gid,
        )

    usage_event_id: Optional[str] = None
    try:
        if has_original_url:
            original_bytes = _download_image_from_url(
                image_url=(original_image_url or "").strip(),
                field_name="original_image_url",
            )
        else:
            original_bytes = await _read_upload_image(original_image_file, field_name="original_image_file")

        if resolved_face_library_id:
            face_record = db.query(PhotoshootModelFace).filter_by(
                id=resolved_face_library_id, is_active=True
            ).first()
            if not face_record:
                raise HTTPException(404, "Face not found in library")
            face_bytes = _read_library_image(
                object_path=face_record.object_path,
                image_path=face_record.image_path,
            )
        else:
            face_bytes = await _read_upload_image(resolved_face_upload, field_name="face_image")

        usage = UsageGovernanceService(db)
        reservation = await usage.reserve_generation(
            store=store,
            action_type="merchant_model_swap",
            reference_type="photoshoot_job",
            customer_identifier=None,
            enforce_weekly_limit=False,
        )
        usage_event_id = reservation.event_id

        job_id = uuid.uuid4()
        storage = get_media_storage_service()
        input1_path = storage.build_object_path(
            relative_dir=f"stores/{store.store_id}/photoshoot/model_swap/{job_id}/inputs/1",
            payload=original_bytes,
            stem="input1",
        )
        input2_path = storage.build_object_path(
            relative_dir=f"stores/{store.store_id}/photoshoot/model_swap/{job_id}/inputs/2",
            payload=face_bytes,
            stem="input2",
        )
        input1_object_path = storage.upload_bytes(
            object_path=input1_path,
            payload=original_bytes,
            metadata={"flow": "merchant", "type": "photoshoot_input", "job_type": "model_swap"},
        )
        input2_object_path = storage.upload_bytes(
            object_path=input2_path,
            payload=face_bytes,
            metadata={"flow": "merchant", "type": "photoshoot_input", "job_type": "model_swap"},
        )
        if not input1_object_path or not input2_object_path:
            raise HTTPException(500, "Failed to archive model swap input images to media storage")

        job = PhotoshootJob(
            job_id=job_id,
            store_id=store.store_id,
            job_type="model_swap",
            shopify_product_gid=normalized_product_gid,
            processing_status="queued",
            input1_object_path=input1_object_path,
            input2_object_path=input2_object_path,
        )
        db.add(job)
        db.commit()

        background_tasks.add_task(
            _run_photoshoot_job,
            job_id=str(job_id),
            job_type="model_swap",
            image1_bytes=original_bytes,
            image2_bytes=face_bytes,
            usage_event_id=usage_event_id,
        )

        logger.info(f"Model swap job queued: {job_id}")
        return _job_status_response(job)

    except HTTPException:
        if usage_event_id:
            usage = UsageGovernanceService(db)
            await usage.refund_usage(
                event_id=usage_event_id,
                reason="model_swap_request_rejected",
            )
        raise
    except Exception as e:
        logger.error(f"model-swap start error: {e}", exc_info=True)
        if usage_event_id:
            usage = UsageGovernanceService(db)
            await usage.refund_usage(
                event_id=usage_event_id,
                reason=f"model_swap_request_error:{str(e)[:240]}",
            )
        raise HTTPException(500, f"Failed to start model swap job: {e}")


# ─────────────────────────────────────────────────────────────
# Job Status / Result / Approve Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}/status", response_model=PhotoshootJobResponse)
async def get_job_status(
    job_id: str,
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """Poll the status of a photoshoot generation job."""
    job = db.query(PhotoshootJob).filter_by(
        job_id=job_id, store_id=store.store_id
    ).first()
    if not job:
        raise HTTPException(404, "Photoshoot job not found")

    return _job_status_response(job)


@router.get("/jobs/{job_id}/result")
async def get_job_result(
    job_id: str,
    db: DBSession = Depends(get_db),
):
    """
    Serve the generated photoshoot image from Redis cache.

    No auth on this endpoint — Shopify must be able to fetch this URL
    during productCreateMedia without the X-Store-ID header.
    """
    job = db.query(PhotoshootJob).filter_by(job_id=job_id).first()
    if not job:
        raise HTTPException(404, "Photoshoot job not found")
    if job.processing_status != "completed":
        raise HTTPException(409, f"Job is {job.processing_status}, not ready")

    cache = CacheService()
    image_bytes = await cache.get_photoshoot_result(job_id)
    if image_bytes:
        return Response(content=image_bytes, media_type="image/jpeg")

    storage = get_media_storage_service()
    if job.output_object_path and storage.enabled:
        signed_url = storage.generate_signed_get_url(job.output_object_path)
        if signed_url:
            return RedirectResponse(url=signed_url, status_code=307)

    raise HTTPException(410, "Result image has expired from cache. Please regenerate.")


@router.post("/jobs/{job_id}/approve", response_model=PhotoshootApproveResponse)
async def approve_job(
    job_id: str,
    request: PhotoshootApproveRequest,
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Approve a completed photoshoot job and push the generated image to the
    Shopify product via productCreateMedia.

    The backend constructs a public URL pointing to GET /jobs/{job_id}/result,
    which Shopify fetches immediately and re-hosts on its own CDN.

    Body:
        {"alt_text": "Ghost mannequin view of Blue T-Shirt"}  (optional)
    """
    from app.services.shopify_service import ShopifyService

    job = db.query(PhotoshootJob).filter_by(
        job_id=job_id, store_id=store.store_id
    ).first()
    if not job:
        raise HTTPException(404, "Photoshoot job not found")
    if job.processing_status != "completed":
        raise HTTPException(409, f"Job is {job.processing_status}. Only completed jobs can be approved.")
    if job.approved_at:
        raise HTTPException(409, "Job has already been approved and pushed to Shopify.")

    requested_gid = _normalize_shopify_product_gid(request.shopify_product_gid)
    if not job.shopify_product_gid:
        if not requested_gid:
            raise HTTPException(
                422,
                "shopify_product_gid is required for approval when this job was generated without a bound product",
            )
        _resolve_product_for_store(
            db=db,
            store=store,
            shopify_product_gid=requested_gid,
        )
        job.shopify_product_gid = requested_gid
        db.commit()
    elif requested_gid and requested_gid != job.shopify_product_gid:
        raise HTTPException(409, "shopify_product_gid does not match the product originally attached to this job")

    storage = get_media_storage_service()
    if not storage.enabled:
        reason = storage.disabled_reason or "unknown configuration error"
        raise HTTPException(500, f"Media storage is not configured. Reason: {reason}")

    if not job.output_object_path:
        cache = CacheService()
        image_bytes = await cache.get_photoshoot_result(job_id)
        if not image_bytes:
            raise HTTPException(
                410,
                "Result image has expired from cache. Please regenerate before approving.",
            )
        output_path = storage.build_object_path(
            relative_dir=f"stores/{store.store_id}/photoshoot/{job.job_type}/{job_id}/output",
            payload=image_bytes,
            stem="output",
        )
        job.output_object_path = storage.upload_bytes(
            object_path=output_path,
            payload=image_bytes,
            metadata={"flow": "merchant", "type": "photoshoot_output", "job_type": job.job_type},
        )
        db.commit()

    result_url = storage.generate_signed_get_url(job.output_object_path)
    if not result_url:
        raise HTTPException(500, "Failed to generate signed URL for Shopify media upload")
    alt_text = request.alt_text or f"AI generated {job.job_type.replace('_', ' ')} image"

    try:
        svc = ShopifyService(store.shopify_domain, require_shopify_access_token(store))
        media_result = await svc.add_product_image(
            shopify_product_gid=str(job.shopify_product_gid),
            image_url=result_url,
            alt_text=alt_text,
        )
    except Exception as e:
        logger.error(f"Shopify productCreateMedia failed for job {job_id}: {e}")
        raise HTTPException(502, f"Failed to push image to Shopify: {e}")

    job.approved_at = datetime.utcnow()
    job.shopify_media_id = media_result.get("media_id")
    db.commit()

    logger.info(f"Photoshoot job {job_id} approved → Shopify media {job.shopify_media_id}")

    return PhotoshootApproveResponse(
        approved=True,
        shopify_media_id=job.shopify_media_id,
        message="Image pushed to Shopify product. It will appear in the product gallery within seconds.",
    )
