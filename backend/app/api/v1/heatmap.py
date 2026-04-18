"""
Heatmap Generation API Endpoints
Generates zone-based fit visualization payloads
"""

import uuid
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session as DBSession
from datetime import datetime
import logging

from app.api.store_context import get_public_store
from app.core.database import get_db
from app.models.database import Session, Product, UserMeasurement, SizeChart
from app.models.schemas import HeatmapGenerateRequest, HeatmapResponse
from app.services.heatmap_service import HeatmapService

router = APIRouter(prefix="/heatmap", tags=["Heatmap"])
logger = logging.getLogger(__name__)


async def get_session_from_header(
    x_session_id: str = Header(..., alias="X-Session-ID"),
    store = Depends(get_public_store),
    db: DBSession = Depends(get_db)
) -> Session:
    """Get session from X-Session-ID header"""
    session = db.query(Session).filter_by(
        session_id=x_session_id,
        store_id=store.store_id
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
        Heatmap with zone deltas and fit labels for frontend SVG rendering
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

        # Generate zone-based heatmap data
        service = HeatmapService()
        result = service.generate(
            user_measurements=measurement.measurements or {},
            gender=measurement.gender or "unisex",
            category=product.category or "unknown",
            size_name=request.size,
            size_charts_db=size_charts,
        )

        heatmap_id = uuid.uuid4()

        logger.info(
            f"Heatmap generated: {heatmap_id}, "
            f"size={request.size}, "
            f"score={result['overall_fit_score']}, "
            f"zones={len(result['zones'])}"
        )

        return HeatmapResponse(
            heatmap_id=heatmap_id,
            size=result["size"],
            overall_fit_score=result["overall_fit_score"],
            zones=result["zones"],
            legend=result["legend"],
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Heatmap generation failed: {e}")
        raise HTTPException(422, str(e))
    except Exception as e:
        logger.error(f"Heatmap generation error: {e}", exc_info=True)
        raise HTTPException(500, f"Heatmap generation failed: {str(e)}")
