"""
Admin API Endpoints
Internal endpoints for managing the model photo, face, and ghost mannequin
reference image libraries. Protected by X-Admin-Key header.
"""

import os
import uuid
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session as DBSession

from app.core.database import get_db
from app.models.database import PhotoshootModel, PhotoshootModelFace, GhostMannequinRef
from app.config import get_settings

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger(__name__)
settings = get_settings()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
STATIC_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "static",
)


def require_admin(x_admin_key: str = Header(..., alias="X-Admin-Key")):
    """Dependency: validate admin API key."""
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(401, "Invalid admin key")


def _safe_filename(original: str, ext: str) -> str:
    """Sanitise filename: keep alphanumerics, hyphens, underscores."""
    stem = os.path.splitext(original)[0]
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)
    return f"{safe}{ext}" if safe else f"image{ext}"


def _unique_dest(dir_path: str, safe_name: str, ext: str) -> tuple[str, str]:
    """Return (dest_path, safe_name) — appends a uuid suffix if the file already exists."""
    dest = os.path.join(dir_path, safe_name)
    if os.path.exists(dest):
        safe_name = f"{os.path.splitext(safe_name)[0]}_{uuid.uuid4().hex[:6]}{ext}"
        dest = os.path.join(dir_path, safe_name)
    return dest, safe_name


# ─────────────────────────────────────────────────────────────
# Model Photos  (full-body — serves customer studio look + merchant try-on)
# ─────────────────────────────────────────────────────────────

@router.post("/model-photos/upload")
async def upload_model_photos(
    gender: Literal["male", "female", "unisex"] = Form(...),
    age: Optional[str] = Form(None, description="18-25 | 26-35 | 36-45 | 45+"),
    body_type: Optional[str] = Form(None, description="slim | athletic | regular | plus"),
    images: list[UploadFile] = File(...),
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    Upload one or more full-body model photos.

    Saves each file to static/photoshoot/{gender}/ and creates a
    photoshoot_models DB row. These images are served for both:
      - Customer studio look  (GET /tryon/studio-backgrounds)
      - Merchant AI photoshoot try-on (GET /merchant/photoshoot/models)

    Headers:
        X-Admin-Key: <ADMIN_API_KEY from .env>

    Form fields:
        gender:    "male" | "female" | "unisex"
        age:       (optional) "18-25" | "26-35" | "36-45" | "45+"
        body_type: (optional) "slim" | "athletic" | "regular" | "plus"
        images:    one or more image files (jpg/jpeg/png/webp)
    """
    if not images:
        raise HTTPException(422, "No images provided")

    gender_dir = os.path.join(STATIC_ROOT, "photoshoot", gender)
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
        if not image_data:
            errors.append({"file": original_name, "error": "File is empty"})
            continue

        safe_name = _safe_filename(original_name, ext)
        dest_path, safe_name = _unique_dest(gender_dir, safe_name, ext)

        with open(dest_path, "wb") as f:
            f.write(image_data)

        # image_path stored relative to static/ root
        relative_path = f"photoshoot/{gender}/{safe_name}"
        record = PhotoshootModel(
            gender=gender,
            age=age,
            body_type=body_type,
            image_path=relative_path,
            is_active=True,
        )
        db.add(record)
        db.flush()

        created.append({
            "id": str(record.id),
            "gender": gender,
            "age": age,
            "body_type": body_type,
            "image_path": relative_path,
            "image_url": f"/api/v1/merchant/photoshoot/models/{record.id}/image",
            "file_size_kb": round(len(image_data) / 1024, 1),
        })
        logger.info(f"Model photo uploaded: {relative_path} (id={record.id})")

    db.commit()

    return {"uploaded": len(created), "failed": len(errors), "photos": created, "errors": errors}


@router.get("/model-photos")
def list_model_photos(
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """List ALL model photos (active + inactive) across all genders. Includes file_exists flag."""
    records = db.query(PhotoshootModel).order_by(
        PhotoshootModel.gender, PhotoshootModel.image_path
    ).all()

    result = []
    for r in records:
        file_path = os.path.join(STATIC_ROOT, r.image_path)
        result.append({
            "id": str(r.id),
            "gender": r.gender,
            "age": r.age,
            "body_type": r.body_type,
            "image_path": r.image_path,
            "is_active": r.is_active,
            "image_url": f"/api/v1/merchant/photoshoot/models/{r.id}/image",
            "file_exists": os.path.exists(file_path),
            "created_at": r.created_at.isoformat(),
        })

    return {"total": len(result), "photos": result}


@router.patch("/model-photos/{photo_id}/toggle")
def toggle_model_photo(
    photo_id: str,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Toggle a model photo active/inactive without deleting it."""
    record = db.query(PhotoshootModel).filter_by(id=photo_id).first()
    if not record:
        raise HTTPException(404, "Model photo not found")

    record.is_active = not record.is_active
    db.commit()

    return {"id": photo_id, "is_active": record.is_active}


@router.delete("/model-photos/{photo_id}")
def delete_model_photo(
    photo_id: str,
    delete_file: bool = True,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    Delete a model photo DB record and optionally the image file on disk.

    Query params:
        delete_file: true (default) — also deletes the file from static/
                     false — only removes the DB row
    """
    record = db.query(PhotoshootModel).filter_by(id=photo_id).first()
    if not record:
        raise HTTPException(404, "Model photo not found")

    image_path = record.image_path
    file_path = os.path.join(STATIC_ROOT, image_path)

    db.delete(record)
    db.commit()

    file_deleted = False
    if delete_file and os.path.exists(file_path):
        os.remove(file_path)
        file_deleted = True
        logger.info(f"Model photo file deleted: {file_path}")

    logger.info(f"Model photo DB record deleted: {photo_id}")

    return {"deleted": True, "id": photo_id, "image_path": image_path, "file_deleted": file_deleted}


# ─────────────────────────────────────────────────────────────
# Model Faces  (headshots — for model swap)
# ─────────────────────────────────────────────────────────────

@router.post("/model-faces/upload")
async def upload_model_faces(
    gender: Literal["male", "female"] = Form(...),
    age: Optional[str] = Form(None, description="18-25 | 26-35 | 36-45 | 45+"),
    skin_tone: Optional[str] = Form(None, description="fair | light | medium | tan | dark"),
    images: list[UploadFile] = File(...),
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    Upload one or more face/headshot photos for the model swap library.

    Saves to static/photoshoot_faces/{gender}/ and creates a
    photoshoot_model_faces DB row per file.

    Headers:
        X-Admin-Key: <ADMIN_API_KEY from .env>

    Form fields:
        gender:    "male" | "female"
        age:       (optional) "18-25" | "26-35" | "36-45" | "45+"
        skin_tone: (optional) "fair" | "light" | "medium" | "tan" | "dark"
        images:    one or more image files (jpg/jpeg/png/webp)
    """
    if not images:
        raise HTTPException(422, "No images provided")

    gender_dir = os.path.join(STATIC_ROOT, "photoshoot_faces", gender)
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
        if not image_data:
            errors.append({"file": original_name, "error": "File is empty"})
            continue

        safe_name = _safe_filename(original_name, ext)
        dest_path, safe_name = _unique_dest(gender_dir, safe_name, ext)

        with open(dest_path, "wb") as f:
            f.write(image_data)

        relative_path = f"photoshoot_faces/{gender}/{safe_name}"
        record = PhotoshootModelFace(
            gender=gender,
            age=age,
            skin_tone=skin_tone,
            image_path=relative_path,
            is_active=True,
        )
        db.add(record)
        db.flush()

        created.append({
            "id": str(record.id),
            "gender": gender,
            "age": age,
            "skin_tone": skin_tone,
            "image_path": relative_path,
            "image_url": f"/api/v1/merchant/photoshoot/model-faces/{record.id}/image",
            "file_size_kb": round(len(image_data) / 1024, 1),
        })
        logger.info(f"Model face uploaded: {relative_path} (id={record.id})")

    db.commit()

    return {"uploaded": len(created), "failed": len(errors), "faces": created, "errors": errors}


@router.get("/model-faces")
def list_model_faces(
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """List ALL model faces (active + inactive). Includes file_exists flag."""
    records = db.query(PhotoshootModelFace).order_by(
        PhotoshootModelFace.gender, PhotoshootModelFace.image_path
    ).all()

    result = []
    for r in records:
        file_path = os.path.join(STATIC_ROOT, r.image_path)
        result.append({
            "id": str(r.id),
            "gender": r.gender,
            "age": r.age,
            "skin_tone": r.skin_tone,
            "image_path": r.image_path,
            "is_active": r.is_active,
            "image_url": f"/api/v1/merchant/photoshoot/model-faces/{r.id}/image",
            "file_exists": os.path.exists(file_path),
            "created_at": r.created_at.isoformat(),
        })

    return {"total": len(result), "faces": result}


@router.patch("/model-faces/{face_id}/toggle")
def toggle_model_face(
    face_id: str,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Toggle a model face active/inactive."""
    record = db.query(PhotoshootModelFace).filter_by(id=face_id).first()
    if not record:
        raise HTTPException(404, "Model face not found")

    record.is_active = not record.is_active
    db.commit()

    return {"id": face_id, "is_active": record.is_active}


@router.delete("/model-faces/{face_id}")
def delete_model_face(
    face_id: str,
    delete_file: bool = True,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Delete a model face DB record and optionally the image file."""
    record = db.query(PhotoshootModelFace).filter_by(id=face_id).first()
    if not record:
        raise HTTPException(404, "Model face not found")

    image_path = record.image_path
    file_path = os.path.join(STATIC_ROOT, image_path)

    db.delete(record)
    db.commit()

    file_deleted = False
    if delete_file and os.path.exists(file_path):
        os.remove(file_path)
        file_deleted = True

    logger.info(f"Model face deleted: {face_id} (file_deleted={file_deleted})")

    return {"deleted": True, "id": face_id, "image_path": image_path, "file_deleted": file_deleted}


# ─────────────────────────────────────────────────────────────
# Ghost Mannequin Reference Images  (12 fixed reference poses)
# ─────────────────────────────────────────────────────────────

@router.post("/ghost-mannequin-refs/upload")
async def upload_ghost_mannequin_ref(
    clothing_type: Literal["tops", "bottoms", "dresses", "outerwear"] = Form(...),
    pose: Literal["front", "side", "back"] = Form(...),
    image: UploadFile = File(..., description="Single reference image for this clothing_type + pose"),
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    Upload a ghost mannequin reference pose image (one at a time).

    There are 12 reference images total: 4 clothing types × 3 poses.
    If a DB record already exists for this clothing_type + pose combination,
    the file is overwritten and the DB record updated (upsert).

    Saves to static/ghost_mannequin/{clothing_type}/{pose}{ext}.

    Headers:
        X-Admin-Key: <ADMIN_API_KEY from .env>

    Form fields:
        clothing_type: "tops" | "bottoms" | "dresses" | "outerwear"
        pose:          "front" | "side" | "back"
        image:         single image file (jpg/jpeg/png/webp)
    """
    ext = os.path.splitext(image.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(422, f"Extension '{ext}' not allowed. Use jpg/jpeg/png/webp.")

    image_data = await image.read()
    if not image_data:
        raise HTTPException(422, "Image file is empty")

    type_dir = os.path.join(STATIC_ROOT, "ghost_mannequin", clothing_type)
    os.makedirs(type_dir, exist_ok=True)

    filename = f"{pose}{ext}"
    dest_path = os.path.join(type_dir, filename)
    with open(dest_path, "wb") as f:
        f.write(image_data)

    relative_path = f"ghost_mannequin/{clothing_type}/{filename}"

    # Upsert — one canonical record per clothing_type + pose
    existing = db.query(GhostMannequinRef).filter_by(
        clothing_type=clothing_type, pose=pose
    ).first()
    if existing:
        existing.image_path = relative_path
        db.commit()
        record_id = str(existing.id)
        action = "updated"
    else:
        record = GhostMannequinRef(
            clothing_type=clothing_type,
            pose=pose,
            image_path=relative_path,
        )
        db.add(record)
        db.commit()
        record_id = str(record.id)
        action = "created"

    logger.info(f"Ghost mannequin ref {action}: {relative_path} (id={record_id})")

    return {
        "id": record_id,
        "clothing_type": clothing_type,
        "pose": pose,
        "image_path": relative_path,
        "image_url": f"/api/v1/merchant/photoshoot/ghost-mannequin-refs/{record_id}/image",
        "action": action,
    }


@router.get("/ghost-mannequin-refs")
def list_ghost_mannequin_refs(
    db: DBSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """List all ghost mannequin reference images (grouped by clothing_type + pose)."""
    records = db.query(GhostMannequinRef).order_by(
        GhostMannequinRef.clothing_type, GhostMannequinRef.pose
    ).all()

    result = []
    for r in records:
        file_path = os.path.join(STATIC_ROOT, r.image_path)
        result.append({
            "id": str(r.id),
            "clothing_type": r.clothing_type,
            "pose": r.pose,
            "image_path": r.image_path,
            "image_url": f"/api/v1/merchant/photoshoot/ghost-mannequin-refs/{r.id}/image",
            "file_exists": os.path.exists(file_path),
            "created_at": r.created_at.isoformat(),
        })

    return {"total": len(result), "refs": result}
