"""
Measurements API Endpoints
Handles image validation and measurement extraction
"""

from fastapi import APIRouter, HTTPException, Depends, Header, UploadFile, File, Form
from sqlalchemy.orm import Session as DBSession
from datetime import datetime
import time
import logging

from app.api.store_context import get_public_store
from app.core.database import get_db
from app.core.redis import get_redis
from app.config import get_settings
from app.models.database import Store, Session, UserMeasurement, PhotoValidationEvent
from app.models.schemas import MeasurementResponse
from app.services.image_validator import ImageValidator
from app.services.measurement_service import MeasurementService
from app.services.cache_service import CacheService

router = APIRouter(prefix="/measurements", tags=["Measurements"])
logger = logging.getLogger(__name__)
settings = get_settings()


async def get_session_from_header(
    x_session_id: str = Header(..., alias="X-Session-ID"),
    store: Store = Depends(get_public_store),
    db: DBSession = Depends(get_db)
) -> Session:
    """Get session from X-Session-ID header"""
    session = db.query(Session).filter_by(
        session_id=x_session_id,
        store_id=store.store_id
    ).first()

    if not session:
        raise HTTPException(404, f"Session not found: {x_session_id}")

    # Check expiry
    if session.expires_at < datetime.utcnow():
        raise HTTPException(410, "Session expired")

    return session


@router.post("/validate")
async def validate_image(
    image: UploadFile = File(...),
    pose_type: str = Form(...),
    session: Session = Depends(get_session_from_header),
    db: DBSession = Depends(get_db),
):
    """
    Validate image quality and pose

    Headers:
        X-Session-ID: Session UUID
        X-Store-ID: Store UUID

    Form Data:
        image: Image file (JPEG/PNG, max 10MB)
        pose_type: "front" or "side"

    Returns:
        {
            "valid": bool,
            "is_person": bool,
            "pose_detected": bool,
            "pose_accuracy": float,
            "issues": [],
            "confidence": str
        }
    """
    try:
        # Validate pose_type
        if pose_type not in ["front", "side"]:
            raise HTTPException(400, "pose_type must be 'front' or 'side'")

        # Read image data
        image_data = await image.read()

        # Validate file size (10MB max)
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(400, "Image size exceeds 10MB limit")

        # Validate image
        validator = ImageValidator()
        result = await validator.validate_image(image_data, pose_type)

        await _persist_validation_event(
            db=db,
            session=session,
            pose_type=pose_type,
            result=result,
        )

        logger.info(f"Image validation: {pose_type}, valid={result['valid']}, confidence={result['confidence']}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image validation error: {e}", exc_info=True)
        raise HTTPException(500, f"Validation failed: {str(e)}")


async def _persist_validation_event(
    *,
    db: DBSession,
    session: Session,
    pose_type: str,
    result: dict,
) -> None:
    """
    Persist one audit row for each validation attempt.
    Failures in audit logging must not block user flow.
    """
    try:
        metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
        warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
        hard_failures = result.get("hard_failures") if isinstance(result.get("hard_failures"), list) else []

        image_meta = {
            "width": metrics.get("width"),
            "height": metrics.get("height"),
            "file_size_bytes": metrics.get("file_size_bytes"),
            "mean_brightness": metrics.get("mean_brightness"),
        }

        event = PhotoValidationEvent(
            store_id=session.store_id,
            session_id=session.session_id,
            pose_type=pose_type,
            status=str(result.get("status") or ("accepted" if result.get("valid") else "rejected")),
            valid=bool(result.get("valid")),
            pose_accuracy=float(result.get("pose_accuracy") or 0.0),
            confidence=str(result.get("confidence") or "low"),
            reasons_json={
                "warnings": warnings,
                "hard_failures": hard_failures,
            },
            metrics_json=metrics,
            image_meta_json=image_meta,
        )
        db.add(event)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to persist photo validation audit event: %s", exc)


@router.post("/extract", response_model=MeasurementResponse)
async def extract_measurements(
    front_image: UploadFile = File(...),
    side_image: UploadFile = File(...),
    height_cm: float = Form(...),
    weight_kg: float = Form(...),
    gender: str = Form(...),
    session: Session = Depends(get_session_from_header),
    db: DBSession = Depends(get_db)
):
    """
    Extract body measurements from front and side images

    Headers:
        X-Session-ID: Session UUID
        X-Store-ID: Store UUID

    Form Data:
        front_image: Front pose image
        side_image: Side pose image
        height_cm: Height in centimeters (100-250)
        weight_kg: Weight in kilograms (30-300)
        gender: "male", "female", or "unisex"

    Returns:
        Measurement data with 15 body measurements
    """
    start_time = time.time()

    try:
        # Validate inputs
        if height_cm < 100 or height_cm > 250:
            raise HTTPException(400, "Height must be between 100-250 cm")

        if weight_kg < 30 or weight_kg > 300:
            raise HTTPException(400, "Weight must be between 30-300 kg")

        if gender not in ["male", "female", "unisex"]:
            raise HTTPException(400, "Gender must be 'male', 'female', or 'unisex'")

        # Read images
        front_data = await front_image.read()
        side_data = await side_image.read()

        # Validate file sizes
        if len(front_data) > 10 * 1024 * 1024 or len(side_data) > 10 * 1024 * 1024:
            raise HTTPException(400, "Image size exceeds 10MB limit")

        # Store images in Redis cache
        cache_service = CacheService()
        await cache_service.store_image(str(session.session_id), "front", front_data)
        await cache_service.store_image(str(session.session_id), "side", side_data)

        logger.info(f"Images cached for session: {session.session_id}")

        # Extract measurements
        measurement_service = MeasurementService()
        result = await measurement_service.extract_measurements(
            front_data,
            side_data,
            height_cm,
            weight_kg,
            gender
        )

        # Save to database
        measurement = UserMeasurement(
            session_id=session.session_id,
            measurements=result['measurements'],
            height_cm=height_cm,
            weight_kg=weight_kg,
            gender=gender,
            body_type=result['body_type'],
            confidence_score=result['confidence_score']
        )

        db.add(measurement)
        db.flush()

        # Update session with measurement_id
        session.measurement_id = measurement.measurement_id

        db.commit()
        db.refresh(measurement)

        # Cache user measurement mapping (for returning users)
        if session.user_identifier:
            redis = get_redis()
            cache_key = f"user:{session.store_id}:{session.user_identifier}:measurement"
            redis.set(cache_key, str(measurement.measurement_id), settings.MEASUREMENT_CACHE_TTL_SECONDS)

            # Also rename images to measurement keys
            await cache_service.store_measurement_image(
                str(measurement.measurement_id),
                "front",
                front_data
            )
            await cache_service.store_measurement_image(
                str(measurement.measurement_id),
                "side",
                side_data
            )

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Get cache expiry
        cache_expiry = await cache_service.get_cache_expiry(str(session.session_id))

        logger.info(
            f"Measurements extracted: {measurement.measurement_id}, "
            f"body_type={result['body_type']}, "
            f"confidence={result['confidence_score']}, "
            f"time={processing_time_ms}ms"
        )

        return MeasurementResponse(
            measurement_id=measurement.measurement_id,
            session_id=session.session_id,
            measurements=result['measurements'],
            body_type=result['body_type'],
            confidence_score=result['confidence_score'],
            missing_measurements=result.get('missing_measurements', []),
            missing_reason=result.get('missing_reason'),
            processing_time_ms=processing_time_ms,
            cache_expires_at=cache_expiry
        )

    except HTTPException:
        raise
    except ValueError as e:
        # Pose detection errors
        logger.warning(f"Measurement extraction failed: {e}")
        raise HTTPException(422, str(e))
    except Exception as e:
        logger.error(f"Measurement extraction error: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(500, f"Extraction failed: {str(e)}")
