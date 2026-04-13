"""
Size Recommendation API Endpoints
Matches user measurements to product sizes
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session as DBSession
from datetime import datetime
import logging

from app.api.store_context import get_public_store
from app.core.database import get_db
from app.models.database import (
    Session, Product, UserMeasurement, SizeChart, SizeRecommendation
)
from app.models.schemas import SizeRecommendationRequest, SizeRecommendationResponse
from app.services.size_matcher import SizeMatcher

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])
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


@router.post("/size", response_model=SizeRecommendationResponse)
async def recommend_size(
    request: SizeRecommendationRequest,
    session: Session = Depends(get_session_from_header),
    db: DBSession = Depends(get_db)
):
    """
    Get size recommendation based on user measurements and product.

    Headers:
        X-Session-ID: Session UUID
        X-Store-ID: Store UUID

    Body:
        {
            "measurement_id": "uuid",
            "product_id": "uuid"
        }

    Returns:
        Size recommendation with fit analysis for each body region
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

        # Fetch size charts for this product
        size_charts = db.query(SizeChart).filter_by(
            product_id=product.product_id
        ).all()

        # Run size matching
        matcher = SizeMatcher()
        result = matcher.recommend(
            user_measurements=measurement.measurements,
            gender=measurement.gender or "unisex",
            category=product.category or "unknown",
            size_charts_db=size_charts,
        )

        # Save recommendation to database
        recommendation = SizeRecommendation(
            measurement_id=measurement.measurement_id,
            product_id=product.product_id,
            recommended_size=result["recommended_size"],
            confidence=result["confidence"],
            fit_score=result["fit_score"],
            fit_analysis=result["fit_analysis"],
        )

        db.add(recommendation)
        db.commit()
        db.refresh(recommendation)

        logger.info(
            f"Size recommendation: {recommendation.recommendation_id}, "
            f"size={result['recommended_size']}, "
            f"score={result['fit_score']}, "
            f"confidence={result['confidence']}"
        )

        return SizeRecommendationResponse(
            recommendation_id=recommendation.recommendation_id,
            recommended_size=result["recommended_size"],
            confidence=result["confidence"],
            fit_score=result["fit_score"],
            fit_analysis=result["fit_analysis"],
            alternative_sizes=result["alternative_sizes"],
            all_sizes=result["all_sizes"],
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Size recommendation failed: {e}")
        raise HTTPException(422, str(e))
    except Exception as e:
        logger.error(f"Size recommendation error: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(500, f"Recommendation failed: {str(e)}")
