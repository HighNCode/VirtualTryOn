"""
One-time backfill for admin library media into private GCS.

Usage:
  cd backend
  python scripts/backfill_admin_library_to_gcs.py --dry-run
  python scripts/backfill_admin_library_to_gcs.py
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Tuple


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(CURRENT_DIR)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.core.database import SessionLocal  # noqa: E402
from app.models.database import GhostMannequinRef, PhotoshootModel, PhotoshootModelFace  # noqa: E402
from app.services.media_storage_service import get_media_storage_service  # noqa: E402


STATIC_ROOT = os.path.join(BACKEND_ROOT, "static")


def _read_static_payload(image_path: str) -> bytes | None:
    if not image_path:
        return None
    abs_path = os.path.join(STATIC_ROOT, image_path)
    if not os.path.exists(abs_path):
        return None
    with open(abs_path, "rb") as f:
        return f.read()


def _backfill_models(db, storage, dry_run: bool) -> Tuple[int, int]:
    scanned = 0
    updated = 0
    rows = db.query(PhotoshootModel).filter(
        PhotoshootModel.object_path.is_(None),
        PhotoshootModel.image_path.isnot(None),
    ).all()

    for row in rows:
        scanned += 1
        payload = _read_static_payload(row.image_path)
        if not payload:
            continue
        object_path = storage.build_object_path(
            relative_dir=f"admin/library/photoshoot_models/{row.gender or 'unisex'}",
            payload=payload,
            stem=(os.path.splitext(os.path.basename(row.image_path))[0] or "model"),
        )
        if dry_run:
            print(f"[dry-run] photoshoot_model {row.id} -> {object_path}")
            updated += 1
            continue
        uploaded = storage.upload_bytes(
            object_path=object_path,
            payload=payload,
            metadata={"flow": "admin", "type": "photoshoot_model_library"},
        )
        if uploaded:
            row.object_path = uploaded
            updated += 1

    return scanned, updated


def _backfill_faces(db, storage, dry_run: bool) -> Tuple[int, int]:
    scanned = 0
    updated = 0
    rows = db.query(PhotoshootModelFace).filter(
        PhotoshootModelFace.object_path.is_(None),
        PhotoshootModelFace.image_path.isnot(None),
    ).all()

    for row in rows:
        scanned += 1
        payload = _read_static_payload(row.image_path)
        if not payload:
            continue
        object_path = storage.build_object_path(
            relative_dir=f"admin/library/photoshoot_faces/{row.gender or 'unisex'}",
            payload=payload,
            stem=(os.path.splitext(os.path.basename(row.image_path))[0] or "face"),
        )
        if dry_run:
            print(f"[dry-run] photoshoot_face {row.id} -> {object_path}")
            updated += 1
            continue
        uploaded = storage.upload_bytes(
            object_path=object_path,
            payload=payload,
            metadata={"flow": "admin", "type": "photoshoot_face_library"},
        )
        if uploaded:
            row.object_path = uploaded
            updated += 1

    return scanned, updated


def _backfill_ghost_refs(db, storage, dry_run: bool) -> Tuple[int, int]:
    scanned = 0
    updated = 0
    rows = db.query(GhostMannequinRef).filter(
        GhostMannequinRef.object_path.is_(None),
        GhostMannequinRef.image_path.isnot(None),
    ).all()

    for row in rows:
        scanned += 1
        payload = _read_static_payload(row.image_path)
        if not payload:
            continue
        object_path = storage.build_object_path(
            relative_dir=f"admin/library/ghost_refs/{row.clothing_type}/{row.pose}",
            payload=payload,
            stem="reference",
        )
        if dry_run:
            print(f"[dry-run] ghost_ref {row.id} -> {object_path}")
            updated += 1
            continue
        uploaded = storage.upload_bytes(
            object_path=object_path,
            payload=payload,
            metadata={"flow": "admin", "type": "ghost_reference_library"},
        )
        if uploaded:
            row.object_path = uploaded
            updated += 1

    return scanned, updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill admin library media into GCS.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned uploads without DB writes.")
    args = parser.parse_args()

    storage = get_media_storage_service()
    if not storage.enabled:
        print("Media storage is not configured. Set MEDIA_STORAGE_BACKEND=gcs and GCS_BUCKET_NAME.")
        return 1

    db = SessionLocal()
    try:
        m_scanned, m_updated = _backfill_models(db, storage, args.dry_run)
        f_scanned, f_updated = _backfill_faces(db, storage, args.dry_run)
        g_scanned, g_updated = _backfill_ghost_refs(db, storage, args.dry_run)

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        print("Backfill summary:")
        print(f"  photoshoot_models: scanned={m_scanned}, updated={m_updated}")
        print(f"  photoshoot_faces:  scanned={f_scanned}, updated={f_updated}")
        print(f"  ghost_refs:        scanned={g_scanned}, updated={g_updated}")
        print(f"  dry_run={args.dry_run}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Backfill failed: {exc}")
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

