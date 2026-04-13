"""
Session Management Endpoints
Handles user session creation and retrieval
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session as DBSession
from datetime import datetime
import logging
from uuid import UUID

from app.api.store_context import get_public_store
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.database import Store, Product, Session, UserMeasurement
from app.models.schemas import SessionCreateRequest, SessionResponse

router = APIRouter(prefix="/sessions", tags=["Sessions"])
logger = logging.getLogger(__name__)


def create_or_resume_session_for_product(
    *,
    product: Product,
    store: Store,
    user_identifier: str | None,
    db: DBSession,
) -> SessionResponse:
    """
    Shared session bootstrap used by both the direct API and the storefront
    widget bridge that resolves products from Shopify product GIDs.
    """
    cached_measurement_id = None
    has_existing_measurements = False
    measurements = None
    photos_available = False
    cached_until = None

    if user_identifier:
        redis = get_redis()
        cache_key = f"user:{store.store_id}:{user_identifier}:measurement"
        cached_measurement_id = redis.get(cache_key)

        if cached_measurement_id:
            cached_measurement_id = (
                cached_measurement_id.decode("utf-8")
                if isinstance(cached_measurement_id, bytes)
                else cached_measurement_id
            )

            measurement = db.query(UserMeasurement).filter_by(
                measurement_id=cached_measurement_id
            ).first()

            if measurement:
                has_existing_measurements = True
                measurements = measurement.measurements

                front_key = f"img:measurement:{cached_measurement_id}:front"
                side_key = f"img:measurement:{cached_measurement_id}:side"

                front_exists = redis.exists(front_key)
                side_exists = redis.exists(side_key)
                photos_available = front_exists and side_exists

                ttl = redis.client.ttl(front_key)
                if ttl > 0:
                    from datetime import timedelta

                    cached_until = datetime.utcnow() + timedelta(seconds=ttl)

    new_session = Session(
        store_id=store.store_id,
        product_id=product.product_id,
        measurement_id=cached_measurement_id if has_existing_measurements else None,
        user_identifier=user_identifier,
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    logger.info(
        "Session created: %s, has_measurements=%s",
        new_session.session_id,
        has_existing_measurements,
    )

    return SessionResponse(
        session_id=new_session.session_id,
        store_id=store.store_id,
        product_id=product.product_id,
        has_existing_measurements=has_existing_measurements,
        measurement_id=UUID(cached_measurement_id) if cached_measurement_id else None,
        measurements=measurements,
        photos_available=photos_available,
        cached_until=cached_until,
        expires_at=new_session.expires_at,
    )


@router.post("/", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    store: Store = Depends(get_public_store),
    db: DBSession = Depends(get_db)
):
    """
    Create or resume session

    Headers:
        X-Store-ID: Store UUID

    Body:
        {
            "product_id": "uuid",
            "user_identifier": "browser_fingerprint_hash" (optional)
        }

    Returns:
        Session with existing measurements if available (returning user)
    """
    try:
        product = db.query(Product).filter_by(
            product_id=request.product_id,
            store_id=store.store_id
        ).first()

        if not product:
            raise HTTPException(404, f"Product not found: {request.product_id}")

        return create_or_resume_session_for_product(
            product=product,
            store=store,
            user_identifier=request.user_identifier,
            db=db,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session creation error: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(500, f"Failed to create session: {str(e)}")


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    store: Store = Depends(get_public_store),
    db: DBSession = Depends(get_db)
):
    """
    Get session details

    Headers:
        X-Store-ID: Store UUID

    Args:
        session_id: Session UUID

    Returns:
        Session details
    """
    session = db.query(Session).filter_by(
        session_id=session_id,
        store_id=store.store_id
    ).first()

    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")

    # Check if session expired
    if session.expires_at < datetime.utcnow():
        raise HTTPException(410, "Session expired")

    # Get measurement if exists
    measurements = None
    if session.measurement_id:
        measurement = db.query(UserMeasurement).filter_by(
            measurement_id=session.measurement_id
        ).first()
        if measurement:
            measurements = measurement.measurements

    return SessionResponse(
        session_id=session.session_id,
        store_id=session.store_id,
        product_id=session.product_id,
        has_existing_measurements=session.measurement_id is not None,
        measurement_id=session.measurement_id,
        measurements=measurements,
        expires_at=session.expires_at
    )
