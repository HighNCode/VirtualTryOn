"""
SQLAlchemy Database Models
All database tables for Virtual Try-On app
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, Index, UniqueConstraint, text, Numeric
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

    # Onboarding & plan columns
    onboarding_step = Column(String(50), default='welcome', nullable=False)
    # values: 'welcome' | 'goals' | 'referral' | 'widget_scope' | 'theme_setup' | 'plan' | 'complete'
    onboarding_completed_at = Column(DateTime, nullable=True)
    plan_name = Column(String(50), default='free', nullable=False)
    # values: 'free' | 'founding_trial' | 'starter' | 'growth'
    plan_shopify_subscription_id = Column(String(255), nullable=True)
    plan_activated_at = Column(DateTime, nullable=True)
    credits_limit = Column(Integer, default=0, nullable=False)
    billing_interval = Column(String(10), nullable=True)   # 'monthly' | 'annual' | null for free
    trial_ends_at = Column(DateTime, nullable=True)
    is_founding_merchant = Column(Boolean, nullable=False, default=False)
    subscription_status = Column(String(20), nullable=True)  # 'ACTIVE' | 'CANCELLED' | 'FROZEN' | ...
    billing_cycle_start_at = Column(DateTime, nullable=True)
    billing_cycle_end_at = Column(DateTime, nullable=True)
    billing_status_synced_at = Column(DateTime, nullable=True)
    store_timezone = Column(String(64), nullable=True)  # IANA TZ, e.g. "America/New_York"
    has_usage_billing = Column(Boolean, nullable=False, default=False)
    usage_line_item_id = Column(String(255), nullable=True)

    # Relationships
    products = relationship("Product", back_populates="store", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="store", cascade="all, delete-orphan")
    analytics_events = relationship("AnalyticsEvent", back_populates="store", cascade="all, delete-orphan")
    onboarding = relationship("MerchantOnboarding", back_populates="store", uselist=False, cascade="all, delete-orphan")
    widget_config = relationship("WidgetConfig", back_populates="store", uselist=False, cascade="all, delete-orphan")

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


class Plan(Base, TimestampMixin):
    """
    Subscription plan definitions (Starter, Growth).
    Stored in DB so plans can be updated without code deploys.
    Free plan is implied when a store has no plan_name match in this table.
    """
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)          # 'starter' | 'growth'
    display_name = Column(String(100), nullable=False)              # 'Starter' | 'Growth'
    price_monthly = Column(Numeric(8, 2), nullable=False)          # 17.00
    price_annual_total = Column(Numeric(8, 2), nullable=False)     # 179.00 (charged by Shopify)
    price_annual_per_month = Column(Numeric(8, 2), nullable=False) # 14.00 (display only)
    annual_discount_pct = Column(Integer, nullable=False, default=17)
    credits_monthly = Column(Integer, nullable=False)               # 600
    credits_annual = Column(Integer, nullable=False)                # 7600
    overage_usd_per_tryon = Column(Numeric(10, 4), nullable=False, default=0.14)
    trial_days = Column(Integer, nullable=True)                     # 14
    trial_credits = Column(Integer, nullable=True)                  # 80
    usage_cap_usd = Column(Numeric(10, 2), nullable=False, default=500.00)
    features = Column(JSONB, nullable=False)                        # List[str]
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

    def __repr__(self):
        return f"<Plan {self.name}>"


# StudioBackground table was merged into photoshoot_models (migration e5f6g7h8i9j0 → f6g7h8i9j0k1).
# All model/person photos now live in photoshoot_models regardless of use context.


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

    # Studio look fields
    # studio_background_id now references photoshoot_models.id (migrated from studio_backgrounds)
    studio_background_id = Column(UUID(as_uuid=True), ForeignKey('photoshoot_models.id'), nullable=True)
    parent_try_on_id = Column(UUID(as_uuid=True), ForeignKey('try_ons.try_on_id'), nullable=True)

    # Relationships
    measurement = relationship("UserMeasurement", back_populates="try_ons")
    product = relationship("Product", back_populates="try_ons")
    studio_background = relationship("PhotoshootModel", foreign_keys=[studio_background_id])
    parent_try_on = relationship("TryOn", remote_side="TryOn.try_on_id")

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


class PhotoshootModel(Base, TimestampMixin):
    """
    Unified model/person photo library.
    Serves both customer studio look (random by gender) and merchant try-on (full filters).
    image_path is relative to backend/static/ root, e.g. "photoshoot/female/model_1.jpg"
    or "studio/male/studio_1.jpg" for records migrated from the old studio_backgrounds table.
    """
    __tablename__ = "photoshoot_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gender = Column(String(10), nullable=False)        # "male", "female", "unisex"
    age = Column(String(10), nullable=True)            # "18-25" | "26-35" | "36-45" | "45+"
    body_type = Column(String(20), nullable=True)      # "slim" | "athletic" | "regular" | "plus"
    image_path = Column(String(300), nullable=False)   # Relative to static/: "photoshoot/female/model_1.jpg"
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<PhotoshootModel {self.id} - {self.gender}>"


class PhotoshootModelFace(Base, TimestampMixin):
    """
    Face/headshot photos used for the model swap feature (face-only replacement).
    image_path is relative to backend/static/ root, e.g. "photoshoot_faces/female/face_1.jpg".
    """
    __tablename__ = "photoshoot_model_faces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gender = Column(String(10), nullable=False)        # "male" | "female"
    age = Column(String(10), nullable=True)            # "18-25" | "26-35" | "36-45" | "45+"
    skin_tone = Column(String(10), nullable=True)      # "fair" | "light" | "medium" | "tan" | "dark"
    image_path = Column(String(300), nullable=False)   # Relative to static/: "photoshoot_faces/female/face_1.jpg"
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<PhotoshootModelFace {self.id} - {self.gender}>"


class GhostMannequinRef(Base, TimestampMixin):
    """
    Reference pose images (front/side/back) for each clothing type, shown in the
    ghost mannequin UI to guide the merchant on what angles to photograph.
    12 rows total: 4 clothing types × 3 poses.
    image_path relative to backend/static/ root: "ghost_mannequin/tops/front.jpg".
    """
    __tablename__ = "ghost_mannequin_refs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clothing_type = Column(String(20), nullable=False)  # "tops" | "bottoms" | "dresses" | "outerwear"
    pose = Column(String(10), nullable=False)            # "front" | "side" | "back"
    image_path = Column(String(300), nullable=False)     # "ghost_mannequin/tops/front.jpg"

    def __repr__(self):
        return f"<GhostMannequinRef {self.clothing_type}/{self.pose}>"


class PhotoshootJob(Base, TimestampMixin):
    """
    AI Photoshoot generation jobs (merchant-facing).
    Covers ghost mannequin, try-on for model, and model swap.
    """
    __tablename__ = "photoshoot_jobs"
    __table_args__ = (
        Index('idx_photoshoot_jobs_store', 'store_id'),
        Index('idx_photoshoot_jobs_status', 'processing_status'),
    )

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey('stores.store_id', ondelete='CASCADE'), nullable=False)
    job_type = Column(String(20), nullable=False)
    # values: 'ghost_mannequin' | 'try_on_model' | 'model_swap'
    shopify_product_gid = Column(String(255), nullable=False)  # e.g. gid://shopify/Product/123
    processing_status = Column(String(20), default='queued', nullable=False)
    # values: 'queued' | 'processing' | 'completed' | 'failed'
    result_cache_key = Column(String(200), nullable=True)   # Redis key for result image
    processing_time_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    shopify_media_id = Column(String(255), nullable=True)   # GID returned by Shopify after approve

    store = relationship("Store")

    def __repr__(self):
        return f"<PhotoshootJob {self.job_id} - {self.job_type} - {self.processing_status}>"


class MerchantOnboarding(Base, TimestampMixin):
    """
    Stores answers from the merchant onboarding wizard (steps 2-3).
    One record per store (unique FK).
    """
    __tablename__ = "merchant_onboarding"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(
        UUID(as_uuid=True),
        ForeignKey('stores.store_id', ondelete='CASCADE'),
        unique=True,
        nullable=False,
    )
    goals = Column(JSONB, default=list)          # List[str] e.g. ["improve_conversion", "reduce_returns"]
    referral_source = Column(String(100), nullable=True)
    referral_detail = Column(String(255), nullable=True)

    store = relationship("Store", back_populates="onboarding")

    def __repr__(self):
        return f"<MerchantOnboarding store={self.store_id}>"


class WidgetConfig(Base, TimestampMixin):
    """
    Widget display configuration set during onboarding step 4.
    One record per store (unique FK).
    """
    __tablename__ = "widget_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(
        UUID(as_uuid=True),
        ForeignKey('stores.store_id', ondelete='CASCADE'),
        unique=True,
        nullable=False,
    )
    scope_type = Column(String(20), default='all', nullable=False)
    # values: 'all' | 'selected_collections' | 'selected_products' | 'mixed'
    enabled_collection_ids = Column(JSONB, default=list)   # List[str] — Shopify GIDs
    enabled_product_ids = Column(JSONB, default=list)      # List[str] — Shopify GIDs
    theme_extension_detected = Column(Boolean, default=False, nullable=False)
    theme_id_checked = Column(String(255), nullable=True)
    widget_color = Column(String(7), nullable=True)  # Hex color e.g. '#FF0000'; default '#FF0000' applied in API layer
    weekly_tryon_limit = Column(Integer, nullable=False, default=10)

    store = relationship("Store", back_populates="widget_config")

    def __repr__(self):
        return f"<WidgetConfig store={self.store_id} scope={self.scope_type}>"


class UsageEvent(Base, TimestampMixin):
    """
    Usage accounting events for AI generation actions.
    Lifecycle:
      reserved -> consumed (success) OR refunded (failure)
    """
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("idx_usage_events_store_time", "store_id", "created_at"),
        Index("idx_usage_events_status", "status"),
        Index("idx_usage_events_ref", "reference_type", "reference_id"),
    )

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False)
    customer_identifier = Column(String(255), nullable=True)
    action_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="reserved")  # reserved | consumed | refunded

    # Credit accounting
    reserved_credits = Column(Integer, nullable=False, default=0)
    consumed_credits = Column(Integer, nullable=False, default=0)
    overage_credits = Column(Integer, nullable=False, default=0)
    overage_amount_usd = Column(Numeric(10, 4), nullable=False, default=0)

    # Billing linkage
    usage_charge_id = Column(String(255), nullable=True)
    billing_error_code = Column(String(50), nullable=True)
    billing_error_message = Column(Text, nullable=True)

    # Object this event belongs to (try_on/job etc.)
    reference_type = Column(String(50), nullable=False)  # try_on | photoshoot_job
    reference_id = Column(String(255), nullable=True)

    week_start_utc = Column(DateTime, nullable=True)
    cycle_start_at = Column(DateTime, nullable=True)
    cycle_end_at = Column(DateTime, nullable=True)

    store = relationship("Store")

    def __repr__(self):
        return f"<UsageEvent {self.event_id} {self.action_type} {self.status}>"


class UsageCustomerWeek(Base, TimestampMixin):
    """
    Weekly per-customer counters (Monday-Sunday in store timezone).
    """
    __tablename__ = "usage_customer_weeks"
    __table_args__ = (
        UniqueConstraint("store_id", "customer_identifier", "week_start_utc", name="uq_usage_customer_week"),
        Index("idx_usage_customer_weeks_store_week", "store_id", "week_start_utc"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False)
    customer_identifier = Column(String(255), nullable=False)
    week_start_utc = Column(DateTime, nullable=False)
    week_end_utc = Column(DateTime, nullable=False)
    used_count = Column(Integer, nullable=False, default=0)

    store = relationship("Store")

    def __repr__(self):
        return f"<UsageCustomerWeek store={self.store_id} customer={self.customer_identifier} used={self.used_count}>"


class UsageStoreCycle(Base, TimestampMixin):
    """
    Billing cycle usage aggregates per store.
    """
    __tablename__ = "usage_store_cycles"
    __table_args__ = (
        UniqueConstraint("store_id", "cycle_start_at", "cycle_end_at", name="uq_usage_store_cycle"),
        Index("idx_usage_store_cycles_store_end", "store_id", "cycle_end_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False)
    cycle_start_at = Column(DateTime, nullable=False)
    cycle_end_at = Column(DateTime, nullable=False)

    included_credits = Column(Integer, nullable=False, default=0)
    consumed_credits = Column(Integer, nullable=False, default=0)
    overage_credits = Column(Integer, nullable=False, default=0)
    overage_amount_usd = Column(Numeric(10, 4), nullable=False, default=0)

    overage_blocked = Column(Boolean, nullable=False, default=False)
    overage_block_reason = Column(String(80), nullable=True)
    overage_block_message = Column(Text, nullable=True)

    store = relationship("Store")

    def __repr__(self):
        return f"<UsageStoreCycle store={self.store_id} consumed={self.consumed_credits} overage={self.overage_credits}>"
