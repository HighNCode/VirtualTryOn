"""
AI Photoshoot API Endpoints (Merchant-Facing)
Three features: ghost mannequin, try-on for model, model swap.

Merchant routes resolve the active store from Shopify App Bridge auth when present,
with header fallbacks for the current embedded-app migration state.
Image-serving endpoints are public (no auth) so Shopify CDN can fetch them.
"""

import os
import uuid
import time
import logging
from datetime import datetime
from typing import Optional

from fastapi import (
    APIRouter, Depends, HTTPException,
    BackgroundTasks, UploadFile, File, Form, Query
)
from fastapi.responses import Response
from sqlalchemy.orm import Session as DBSession

from app.api.store_context import get_current_merchant_store, require_shopify_access_token
from app.core.database import get_db
from app.config import get_settings
from app.models.database import Store, PhotoshootJob, PhotoshootModel, PhotoshootModelFace, GhostMannequinRef
from app.models.schemas import (
    GhostMannequinRequest,
    PhotoshootJobResponse,
    PhotoshootModelResponse,
    PhotoshootModelFaceResponse,
    GhostMannequinRefResponse,
    PhotoshootApproveRequest,
    PhotoshootApproveResponse,
)
from app.services.cache_service import CacheService

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/merchant/photoshoot", tags=["AI Photoshoot"])


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

        job.processing_status = "completed"
        job.result_cache_key = cache_key
        job.processing_time_seconds = round(elapsed, 2)
        job.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Photoshoot job {job_id} ({job_type}) completed in {elapsed:.1f}s")

    except Exception as e:
        logger.error(f"Photoshoot job {job_id} failed: {e}", exc_info=True)
        try:
            job = db.query(PhotoshootJob).filter_by(job_id=job_id).first()
            if job:
                job.processing_status = "failed"
                job.error_message = str(e)[:500]
                db.commit()
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
    """Serve a photoshoot model photo from static files (no auth)."""
    model = db.query(PhotoshootModel).filter_by(id=model_id, is_active=True).first()
    if not model:
        raise HTTPException(404, "Model not found")

    image_bytes = _read_static_image(model.image_path)
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
    """Serve a face/headshot photo from static files (no auth)."""
    face = db.query(PhotoshootModelFace).filter_by(id=face_id, is_active=True).first()
    if not face:
        raise HTTPException(404, "Model face not found")

    image_bytes = _read_static_image(face.image_path)
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
    """Serve a ghost mannequin reference image from static files (no auth)."""
    ref = db.query(GhostMannequinRef).filter_by(id=ref_id).first()
    if not ref:
        raise HTTPException(404, "Ghost mannequin reference not found")

    image_bytes = _read_static_image(ref.image_path)
    return Response(content=image_bytes, media_type=_media_type(ref.image_path))


# ─────────────────────────────────────────────────────────────
# Generation Endpoints
# ─────────────────────────────────────────────────────────────

@router.post("/ghost-mannequin", status_code=202, response_model=PhotoshootJobResponse)
async def start_ghost_mannequin(
    request: GhostMannequinRequest,
    background_tasks: BackgroundTasks,
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Start a ghost mannequin generation job.

    Accepts two Shopify CDN image URLs from the same product and the clothing type.
    The merchant can pick any two angles — Gemini constructs the best 3D hollow
    garment view from whatever images are provided.

    Returns 202 immediately. Poll GET /jobs/{job_id}/status for result.

    Body:
        {
          "image1_url": "...", "image2_url": "...",
          "shopify_product_gid": "gid://...",
          "clothing_type": "tops"
        }
    """
    import requests as req_lib

    try:
        try:
            img1 = req_lib.get(request.image1_url, timeout=15)
            img1.raise_for_status()
            img2 = req_lib.get(request.image2_url, timeout=15)
            img2.raise_for_status()
        except Exception as e:
            raise HTTPException(422, f"Could not download product images: {e}")

        job_id = uuid.uuid4()
        job = PhotoshootJob(
            job_id=job_id,
            store_id=store.store_id,
            job_type="ghost_mannequin",
            shopify_product_gid=request.shopify_product_gid,
            processing_status="queued",
        )
        db.add(job)
        db.commit()

        background_tasks.add_task(
            _run_photoshoot_job,
            job_id=str(job_id),
            job_type="ghost_mannequin",
            image1_bytes=img1.content,
            image2_bytes=img2.content,
            clothing_type=request.clothing_type,
        )

        logger.info(f"Ghost mannequin job queued: {job_id} (clothing_type={request.clothing_type})")
        return _job_status_response(job)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ghost-mannequin start error: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to start ghost mannequin job: {e}")


@router.post("/try-on-model", status_code=202, response_model=PhotoshootJobResponse)
async def start_try_on_model(
    background_tasks: BackgroundTasks,
    shopify_product_gid: str = Form(..., description="Shopify product GID"),
    product_image_url: str = Form(..., description="Product garment image URL (Shopify CDN)"),
    library_id: Optional[str] = Form(None, description="ID of a built-in model photo"),
    photo_upload: Optional[UploadFile] = File(None, description="Uploaded model photo"),
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Start a try-on for model job.

    Provide the product image URL (from the ResourcePicker) and either:
    - library_id — pick from the built-in model library
    - photo_upload — upload your own model photo

    Returns 202 immediately. Poll GET /jobs/{job_id}/status for result.
    """
    import requests as req_lib

    if not library_id and not photo_upload:
        raise HTTPException(422, "Provide either library_id or upload a photo_upload file")
    if library_id and photo_upload and photo_upload.filename:
        raise HTTPException(422, "Provide only one of library_id or photo_upload, not both")

    try:
        try:
            product_resp = req_lib.get(product_image_url, timeout=15)
            product_resp.raise_for_status()
            product_bytes = product_resp.content
        except Exception as e:
            raise HTTPException(422, f"Could not download product image: {e}")

        if library_id:
            model_record = db.query(PhotoshootModel).filter_by(
                id=library_id, is_active=True
            ).first()
            if not model_record:
                raise HTTPException(404, "Model not found in library")
            model_bytes = _read_static_image(model_record.image_path)
        else:
            model_bytes = await photo_upload.read()
            if not model_bytes:
                raise HTTPException(422, "Uploaded photo is empty")

        job_id = uuid.uuid4()
        job = PhotoshootJob(
            job_id=job_id,
            store_id=store.store_id,
            job_type="try_on_model",
            shopify_product_gid=shopify_product_gid,
            processing_status="queued",
        )
        db.add(job)
        db.commit()

        background_tasks.add_task(
            _run_photoshoot_job,
            job_id=str(job_id),
            job_type="try_on_model",
            image1_bytes=product_bytes,
            image2_bytes=model_bytes,
        )

        logger.info(f"Try-on model job queued: {job_id}")
        return _job_status_response(job)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"try-on-model start error: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to start try-on model job: {e}")


@router.post("/model-swap", status_code=202, response_model=PhotoshootJobResponse)
async def start_model_swap(
    background_tasks: BackgroundTasks,
    shopify_product_gid: str = Form(..., description="Shopify product GID"),
    original_image_url: str = Form(..., description="Image of original model wearing the product (Shopify CDN)"),
    face_library_id: Optional[str] = Form(None, description="ID of a face photo from the face library"),
    face_image: Optional[UploadFile] = File(None, description="Uploaded face/headshot photo"),
    store: Store = Depends(get_current_merchant_store),
    db: DBSession = Depends(get_db),
):
    """
    Start a model swap job (face-only swap).

    Provide an image of the original model wearing the product and either:
    - face_library_id — pick a replacement face from the built-in face library
    - face_image — upload a headshot photo

    Only the face is replaced. The body, pose, clothing, background, and
    lighting from the original image remain identical.

    Returns 202 immediately. Poll GET /jobs/{job_id}/status for result.
    """
    import requests as req_lib

    if not face_library_id and not face_image:
        raise HTTPException(422, "Provide either face_library_id or upload a face_image file")
    if face_library_id and face_image and face_image.filename:
        raise HTTPException(422, "Provide only one of face_library_id or face_image, not both")

    try:
        try:
            orig_resp = req_lib.get(original_image_url, timeout=15)
            orig_resp.raise_for_status()
            original_bytes = orig_resp.content
        except Exception as e:
            raise HTTPException(422, f"Could not download original image: {e}")

        if face_library_id:
            face_record = db.query(PhotoshootModelFace).filter_by(
                id=face_library_id, is_active=True
            ).first()
            if not face_record:
                raise HTTPException(404, "Face not found in library")
            face_bytes = _read_static_image(face_record.image_path)
        else:
            face_bytes = await face_image.read()
            if not face_bytes:
                raise HTTPException(422, "Uploaded face image is empty")

        job_id = uuid.uuid4()
        job = PhotoshootJob(
            job_id=job_id,
            store_id=store.store_id,
            job_type="model_swap",
            shopify_product_gid=shopify_product_gid,
            processing_status="queued",
        )
        db.add(job)
        db.commit()

        background_tasks.add_task(
            _run_photoshoot_job,
            job_id=str(job_id),
            job_type="model_swap",
            image1_bytes=original_bytes,
            image2_bytes=face_bytes,
        )

        logger.info(f"Model swap job queued: {job_id}")
        return _job_status_response(job)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"model-swap start error: {e}", exc_info=True)
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
    if not image_bytes:
        raise HTTPException(410, "Result image has expired from cache (24h TTL). Please regenerate.")

    return Response(content=image_bytes, media_type="image/jpeg")


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

    cache = CacheService()
    image_bytes = await cache.get_photoshoot_result(job_id)
    if not image_bytes:
        raise HTTPException(
            410,
            "Result image has expired from cache (24h TTL). Please regenerate before approving."
        )

    public_url = settings.PUBLIC_URL.rstrip("/")
    result_url = f"{public_url}/api/v1/merchant/photoshoot/jobs/{job_id}/result"
    alt_text = request.alt_text or f"AI generated {job.job_type.replace('_', ' ')} image"

    try:
        svc = ShopifyService(store.shopify_domain, require_shopify_access_token(store))
        media_result = await svc.add_product_image(
            shopify_product_gid=job.shopify_product_gid,
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
