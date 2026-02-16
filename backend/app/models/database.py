"""
SQLAlchemy Database Models
All database tables for Virtual Try-On app
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, Index, UniqueConstraint, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid

from app.core.database import Base


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Store(Base, TimestampMixin):
    """
    Shopify stores that have installed the app
    """
    __tablename__ = "stores"

    store_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shopify_domain = Column(String(255), unique=True, nullable=False, index=True)
    shopify_access_token = Column(Text, nullable=False)
    store_name = Column(String(255))
    email = Column(String(255))
    script_tag_id = Column(String(50))
    installation_status = Column(String(20), default='active', nullable=False)
    uninstalled_at = Column(DateTime, nullable=True)
    reinstalled_at = Column(DateTime, nullable=True)

    # Relationships
    products = relationship("Product", back_populates="store", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="store", cascade="all, delete-orphan")
    analytics_events = relationship("AnalyticsEvent", back_populates="store", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Store {self.shopify_domain}>"


class Product(Base, TimestampMixin):
    """
    Products synced from Shopify
    """
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint('store_id', 'shopify_product_id', name='uix_store_product'),
        Index('idx_products_store', 'store_id'),
        Index('idx_products_category', 'category'),
    )

    product_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey('stores.store_id', ondelete='CASCADE'), nullable=False)
    shopify_product_id = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    product_type = Column(String(100))
    category = Column(String(50))  # 'tops', 'bottoms', 'dresses', 'outerwear', 'unknown'
    vendor = Column(String(255))
    images = Column(JSONB, default=list)
    variants = Column(JSONB, default=list)
    has_size_chart = Column(Boolean, default=False)
    last_synced_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    store = relationship("Store", back_populates="products")
    size_charts = relationship("SizeChart", back_populates="product", cascade="all, delete-orphan")
    try_ons = relationship("TryOn", back_populates="product")
    size_recommendations = relationship("SizeRecommendation", back_populates="product")

    def __repr__(self):
        return f"<Product {self.title}>"


class SizeChart(Base, TimestampMixin):
    """
    Size charts for products
    Stores measurement ranges for each size (S, M, L, etc.)
    """
    __tablename__ = "size_charts"
    __table_args__ = (
        Index('idx_size_charts_product', 'product_id'),
    )

    size_chart_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey('products.product_id', ondelete='CASCADE'), nullable=False)
    size_name = Column(String(20), nullable=False)
    size_system = Column(String(20))  # 'US', 'EU', 'UK', 'LETTER'
    measurements = Column(JSONB, nullable=False)
    """
    measurements format:
    {
      "chest": {"min": 91, "max": 97, "unit": "cm"},
      "waist": {"min": 76, "max": 81, "unit": "cm"},
      "hip": {"min": 97, "max": 102, "unit": "cm"},
      "shoulder_width": {"min": 42, "max": 44, "unit": "cm"},
      "inseam": {"min": 80, "max": 83, "unit": "cm"}
    }
    """
    source = Column(String(50), default='standard')  # 'metafield', 'description', 'manual', 'standard'
    confidence_score = Column(Float, default=1.0)

    # Relationships
    product = relationship("Product", back_populates="size_charts")

    def __repr__(self):
        return f"<SizeChart {self.size_name} for Product {self.product_id}>"


class Session(Base, TimestampMixin):
    """
    User sessions for virtual try-on
    Each session represents one product try-on attempt
    """
    __tablename__ = "sessions"
    __table_args__ = (
        Index('idx_sessions_expires', 'expires_at'),
    )

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey('stores.store_id'), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey('products.product_id'), nullable=False)
    measurement_id = Column(UUID(as_uuid=True), nullable=True)  # Reference to measurement (no FK constraint to avoid circular dependency)
    user_identifier = Column(String(255), nullable=True)  # Browser fingerprint for returning users
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24))

    # Relationships
    store = relationship("Store", back_populates="sessions")
    product = relationship("Product")

    def __repr__(self):
        return f"<Session {self.session_id}>"


class UserMeasurement(Base, TimestampMixin):
    """
    Body measurements extracted from user photos
    """
    __tablename__ = "user_measurements"
    __table_args__ = (
        Index('idx_measurements_session', 'session_id'),
    )

    measurement_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey('sessions.session_id'), nullable=False)
    measurements = Column(JSONB, nullable=False)
    """
    measurements format:
    {
      "height": 175.0,
      "shoulder_width": 43.2,
      "chest": 94.5,
      "waist": 78.3,
      "hip": 98.1,
      "inseam": 81.2,
      "arm_length": 61.4,
      "torso_length": 65.8,
      "neck": 38.5,
      "thigh": 58.2,
      "upper_arm": 32.1,
      "wrist": 17.3,
      "calf": 36.8,
      "ankle": 23.4,
      "bicep": 31.5
    }
    """
    height_cm = Column(Float, nullable=False)
    weight_kg = Column(Float)
    gender = Column(String(10))  # 'male', 'female', 'unisex'
    body_type = Column(String(20))  # 'slim', 'average', 'athletic', 'heavy'
    confidence_score = Column(Float)

    # Relationships
    session = relationship("Session", foreign_keys=[session_id])
    try_ons = relationship("TryOn", back_populates="measurement")
    size_recommendations = relationship("SizeRecommendation", back_populates="measurement")

    def __repr__(self):
        return f"<UserMeasurement {self.measurement_id}>"


class TryOn(Base, TimestampMixin):
    """
    Virtual try-on generation results
    """
    __tablename__ = "try_ons"
    __table_args__ = (
        Index('idx_try_ons_status', 'processing_status'),
        Index('idx_try_ons_measurement', 'measurement_id'),
    )

    try_on_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    measurement_id = Column(UUID(as_uuid=True), ForeignKey('user_measurements.measurement_id'), nullable=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey('products.product_id'), nullable=False)
    processing_status = Column(String(20), default='queued')  # 'queued', 'processing', 'completed', 'failed'
    result_cache_key = Column(String(200))  # Redis key for result image
    processing_time_seconds = Column(Float)
    error_message = Column(Text)
    completed_at = Column(DateTime)

    # Relationships
    measurement = relationship("UserMeasurement", back_populates="try_ons")
    product = relationship("Product", back_populates="try_ons")

    def __repr__(self):
        return f"<TryOn {self.try_on_id} - {self.processing_status}>"


class SizeRecommendation(Base, TimestampMixin):
    """
    Size recommendations for users based on measurements
    """
    __tablename__ = "size_recommendations"

    recommendation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    measurement_id = Column(UUID(as_uuid=True), ForeignKey('user_measurements.measurement_id'), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey('products.product_id'), nullable=False)
    recommended_size = Column(String(20))
    confidence = Column(String(20))  # 'high', 'medium', 'low'
    fit_score = Column(Integer)  # 0-100
    fit_analysis = Column(JSONB)
    """
    fit_analysis format:
    {
      "chest": {
        "status": "perfect_fit",
        "user_value": 94.5,
        "size_range": [91, 97],
        "difference": 0.5
      },
      "waist": {...},
      ...
    }
    """

    # Relationships
    measurement = relationship("UserMeasurement", back_populates="size_recommendations")
    product = relationship("Product", back_populates="size_recommendations")

    def __repr__(self):
        return f"<SizeRecommendation {self.recommended_size} - {self.fit_score}%>"


class AnalyticsEvent(Base, TimestampMixin):
    """
    Analytics events for tracking user behavior and conversions
    """
    __tablename__ = "analytics_events"
    __table_args__ = (
        Index('idx_analytics_store_time', 'store_id', 'created_at'),
    )

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey('stores.store_id'), nullable=False)
    session_id = Column(UUID(as_uuid=True))
    event_type = Column(String(50), nullable=False)
    """
    event_type values:
    - widget_opened
    - photo_captured
    - measurement_completed
    - size_recommended
    - try_on_generated
    - try_on_viewed
    - size_selected
    - added_to_cart
    - checkout_completed
    """
    event_data = Column(JSONB)

    # Relationships
    store = relationship("Store", back_populates="analytics_events")

    def __repr__(self):
        return f"<AnalyticsEvent {self.event_type}>"


class DataDeletionQueue(Base, TimestampMixin):
    """
    Queue for scheduled data deletion after app uninstall
    GDPR compliance - 30 day grace period
    """
    __tablename__ = "data_deletion_queue"

    deletion_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), nullable=False)
    scheduled_for = Column(DateTime, nullable=False)
    status = Column(String(20), default='pending')  # 'pending', 'completed', 'cancelled'
    executed_at = Column(DateTime)

    def __repr__(self):
        return f"<DataDeletionQueue {self.store_id} - {self.status}>"
