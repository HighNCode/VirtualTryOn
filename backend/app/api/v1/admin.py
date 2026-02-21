"""
Admin API Endpoints
Internal endpoints for managing studio backgrounds and other content.
Protected by X-Admin-Key header.
"""

import os
import uuid
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session as DBSession

from app.core.database import get_db
from app.models.database import StudioBackground
from app.config import get_settings

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger(__name__)
settings = get_settings()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
STUDIO_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "static", "studio"
)


def require_admin(x_admin_key: str = Header(..., alias="X-Admin-Key")):
    """Dependency: validate admin API key."""
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(401, "Invalid admin key")


# ─────────────────────────────────────────────
# Studio Backgrounds
# ─────────────────────────────────────────────

@router.post("/studio-backgrounds/upload")
async def upload_studio_backgrounds(
    gender: Literal["male", "female", "unisex"] = Form(...),
    images: list[UploadFile] = File(...),
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    Upload one or more studio background images for a given gender.

    - Saves each file to  static/studio/{gender}/
    - Creates a StudioBackground DB row for each file
    - File and DB record are always created together (never out of sync)

    Headers:
        X-Admin-Key: <ADMIN_API_KEY from .env>

    Form fields:
        gender: "male" | "female" | "unisex"
        images: one or more image files (jpg/jpeg/png/webp)
    """
    if not images:
        raise HTTPException(422, "No images provided")

    gender_dir = os.path.join(STUDIO_STATIC_DIR, gender)
    os.makedirs(gender_dir, exist_ok=True)

    created = []
    errors = []

    for upload in images:
        original_name = upload.filename or "image"
        ext = os.path.splitext(original_name)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            errors.append({"file": original_name, "error": f"Extension '{ext}' not allowed. Use jpg/jpeg/png/webp."})
            continue

        image_data = await upload.read()
        if len(image_data) == 0:
            errors.append({"file": original_name, "error": "File is empty"})
            continue

        # Use original filename; if it already exists append a short uuid to avoid collision
        safe_name = _safe_filename(original_name, ext)
        dest_path = os.path.join(gender_dir, safe_name)
        if os.path.exists(dest_path):
            safe_name = f"{os.path.splitext(safe_name)[0]}_{uuid.uuid4().hex[:6]}{ext}"
            dest_path = os.path.join(gender_dir, safe_name)

        # Write file to disk
        with open(dest_path, "wb") as f:
            f.write(image_data)

        # Create DB record
        relative_path = f"{gender}/{safe_name}"
        bg = StudioBackground(
            gender=gender,
            image_path=relative_path,
            is_active=True,
        )
        db.add(bg)
        db.flush()  # get the generated id before commit

        created.append({
            "id": str(bg.id),
            "gender": gender,
            "image_path": relative_path,
            "image_url": f"/api/v1/tryon/studio-backgrounds/{bg.id}/image",
            "file_size_kb": round(len(image_data) / 1024, 1),
        })
        logger.info(f"Studio background uploaded: {relative_path} (id={bg.id})")

    db.commit()

    return {
        "uploaded": len(created),
        "failed": len(errors),
        "backgrounds": created,
        "errors": errors,
    }


@router.get("/studio-backgrounds")
def list_all_studio_backgrounds(
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    List ALL studio backgrounds (active and inactive) across all genders.
    Includes file_exists flag to spot any disk/DB mismatches.
    """
    bgs = db.query(StudioBackground).order_by(
        StudioBackground.gender, StudioBackground.image_path
    ).all()

    result = []
    for bg in bgs:
        file_path = os.path.join(STUDIO_STATIC_DIR, bg.image_path)
        result.append({
            "id": str(bg.id),
            "gender": bg.gender,
            "image_path": bg.image_path,
            "is_active": bg.is_active,
            "image_url": f"/api/v1/tryon/studio-backgrounds/{bg.id}/image",
            "file_exists": os.path.exists(file_path),
            "created_at": bg.created_at.isoformat(),
        })

    return {"total": len(result), "backgrounds": result}


@router.patch("/studio-backgrounds/{bg_id}/toggle")
def toggle_studio_background(
    bg_id: str,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Toggle a studio background active/inactive without deleting it."""
    bg = db.query(StudioBackground).filter_by(id=bg_id).first()
    if not bg:
        raise HTTPException(404, "Studio background not found")

    bg.is_active = not bg.is_active
    db.commit()

    return {"id": bg_id, "is_active": bg.is_active}


@router.delete("/studio-backgrounds/{bg_id}")
def delete_studio_background(
    bg_id: str,
    delete_file: bool = True,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    Delete a studio background DB record and optionally the file on disk.

    Query params:
        delete_file: true (default) — also deletes the image file from static/studio/
                     false — only removes the DB row (keeps the file)
    """
    bg = db.query(StudioBackground).filter_by(id=bg_id).first()
    if not bg:
        raise HTTPException(404, "Studio background not found")

    image_path = bg.image_path
    file_path = os.path.join(STUDIO_STATIC_DIR, image_path)

    db.delete(bg)
    db.commit()

    file_deleted = False
    if delete_file and os.path.exists(file_path):
        os.remove(file_path)
        file_deleted = True
        logger.info(f"Studio background file deleted: {file_path}")

    logger.info(f"Studio background DB record deleted: {bg_id}")

    return {
        "deleted": True,
        "id": bg_id,
        "image_path": image_path,
        "file_deleted": file_deleted,
    }


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _safe_filename(original: str, ext: str) -> str:
    """Sanitise filename: keep alphanumerics, hyphens, underscores."""
    stem = os.path.splitext(original)[0]
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)
    return f"{safe}{ext}" if safe else f"image{ext}"
