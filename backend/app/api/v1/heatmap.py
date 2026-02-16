"""
Heatmap Generation API Endpoints
Generates color-coded fit visualization for body regions
"""

import uuid
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session as DBSession
from datetime import datetime
import logging

from app.core.database import get_db
from app.models.database import Session, Product, UserMeasurement, SizeChart
from app.models.schemas import HeatmapGenerateRequest, HeatmapResponse
from app.services.heatmap_service import HeatmapService
from app.services.cache_service import CacheService

router = APIRouter(prefix="/heatmap", tags=["Heatmap"])
logger = logging.getLogger(__name__)


async def get_session_from_header(
    x_session_id: str = Header(..., alias="X-Session-ID"),
    x_store_id: str = Header(..., alias="X-Store-ID"),
    db: DBSession = Depends(get_db)
) -> Session:
    """Get session from X-Session-ID header"""
    session = db.query(Session).filter_by(
        session_id=x_session_id,
        store_id=x_store_id
    ).first()

    if not session:
        raise HTTPException(404, f"Session not found: {x_session_id}")

    if session.expires_at < datetime.utcnow():
        raise HTTPException(410, "Session expired")

    return session


@router.post("/generate", response_model=HeatmapResponse)
async def generate_heatmap(
    request: HeatmapGenerateRequest,
    session: Session = Depends(get_session_from_header),
    db: DBSession = Depends(get_db)
):
    """
    Generate fit heatmap for a specific size.

    Called initially with the recommended size, then again each time
    the user switches sizes on the frontend.

    Headers:
        X-Session-ID: Session UUID
        X-Store-ID: Store UUID

    Body:
        {
            "measurement_id": "uuid",
            "product_id": "uuid",
            "size": "M"
        }

    Returns:
        Heatmap with color-coded body regions, SVG overlay, and fit scores
    """
    try:
        # Fetch measurement
        measurement = db.query(UserMeasurement).filter_by(
            measurement_id=str(request.measurement_id)
        ).first()

        if not measurement:
            raise HTTPException(404, "Measurement not found")

        if str(measurement.session_id) != str(session.session_id):
            raise HTTPException(403, "Measurement does not belong to this session")

        # Fetch product
        product = db.query(Product).filter_by(
            product_id=str(request.product_id)
        ).first()

        if not product:
            raise HTTPException(404, "Product not found")

        if str(product.store_id) != str(session.store_id):
            raise HTTPException(403, "Product does not belong to this store")

        # Fetch size charts
        size_charts = db.query(SizeChart).filter_by(
            product_id=product.product_id
        ).all()

        # Try to retrieve pose landmarks from cached front image
        pose_landmarks = None
        image_shape = None

        try:
            cache_service = CacheService()
            front_image = await cache_service.get_measurement_image(
                str(measurement.measurement_id), "front"
            )

            if front_image:
                from app.services.measurement_service import PoseDetector
                detector = PoseDetector()
                pose_result = detector.detect(front_image)

                if pose_result:
                    pose_landmarks = pose_result["landmarks"]
                    image_shape = pose_result["image_shape"]
                    logger.info("Using pose landmarks for heatmap overlay mode")
                else:
                    logger.info("Pose detection failed, using template mode")
            else:
                logger.info("Front image not in cache, using template mode")
        except Exception as e:
            logger.warning(f"Landmark retrieval failed ({e}), using template mode")

        # Generate heatmap
        service = HeatmapService()
        result = service.generate(
            user_measurements=measurement.measurements,
            gender=measurement.gender or "unisex",
            category=product.category or "unknown",
            size_name=request.size,
            size_charts_db=size_charts,
            pose_landmarks=pose_landmarks,
            image_shape=image_shape,
        )

        heatmap_id = uuid.uuid4()

        logger.info(
            f"Heatmap generated: {heatmap_id}, "
            f"size={request.size}, "
            f"score={result['overall_fit_score']}, "
            f"mode={'overlay' if pose_landmarks is not None else 'template'}"
        )

        return HeatmapResponse(
            heatmap_id=heatmap_id,
            size=result["size"],
            overall_fit_score=result["overall_fit_score"],
            regions=result["regions"],
            svg_overlay=result["svg_overlay"],
            legend=result["legend"],
            image_dimensions=result.get("image_dimensions"),
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Heatmap generation failed: {e}")
        raise HTTPException(422, str(e))
    except Exception as e:
        logger.error(f"Heatmap generation error: {e}", exc_info=True)
        raise HTTPException(500, f"Heatmap generation failed: {str(e)}")
