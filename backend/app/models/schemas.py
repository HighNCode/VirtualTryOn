"""
Pydantic Schemas for API Request/Response Validation
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# ============================================================================
# Base Schemas
# ============================================================================

class BaseResponse(BaseModel):
    """Base response schema"""
    status: str = "success"
    message: Optional[str] = None


# ============================================================================
# Shopify OAuth Schemas
# ============================================================================

class OAuthInitRequest(BaseModel):
    """OAuth initialization request"""
    shop: str = Field(..., description="Shopify shop domain (e.g., mystore.myshopify.com)")


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request"""
    code: str
    shop: str
    hmac: str
    timestamp: Optional[str] = None
    state: Optional[str] = None


class StoreResponse(BaseModel):
    """Store information response"""
    store_id: UUID
    shopify_domain: str
    store_name: Optional[str]
    email: Optional[str]
    installation_status: str
    script_tag_installed: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Product Schemas
# ============================================================================

class ProductVariant(BaseModel):
    """Product variant information"""
    id: str
    title: str
    sku: Optional[str]
    price: str
    size: Optional[str]


class ProductImage(BaseModel):
    """Product image information"""
    src: str
    alt: Optional[str]


class ProductBase(BaseModel):
    """Base product information"""
    shopify_product_id: str
    title: str
    description: Optional[str]
    product_type: Optional[str]
    category: str
    vendor: Optional[str]
    images: List[ProductImage] = []
    variants: List[ProductVariant] = []
    has_size_chart: bool = False


class ProductResponse(ProductBase):
    """Product response with ID and timestamps"""
    product_id: UUID
    store_id: UUID
    last_synced_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class ProductSyncRequest(BaseModel):
    """Manual product sync request"""
    force_sync: bool = False


class ProductSyncResponse(BaseModel):
    """Product sync response"""
    status: str
    products_synced: int
    products_with_sizes: int
    products_without_sizes: int
    timestamp: datetime


# ============================================================================
# Session Schemas
# ============================================================================

class SessionCreateRequest(BaseModel):
    """Create session request"""
    product_id: UUID
    user_identifier: Optional[str] = None


class SessionResponse(BaseModel):
    """Session response"""
    session_id: UUID
    store_id: UUID
    product_id: UUID
    has_existing_measurements: bool = False
    measurement_id: Optional[UUID] = None
    measurements: Optional[Dict[str, float]] = None
    photos_available: bool = False
    cached_until: Optional[datetime] = None
    expires_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Measurement Schemas
# ============================================================================

class MeasurementExtractRequest(BaseModel):
    """Measurement extraction request"""
    height_cm: float = Field(..., ge=100, le=250, description="Height in centimeters")
    weight_kg: float = Field(..., ge=30, le=300, description="Weight in kilograms")
    gender: str = Field(..., pattern="^(male|female|unisex)$")


class MeasurementResponse(BaseModel):
    """Measurement extraction response"""
    measurement_id: UUID
    session_id: UUID
    measurements: Dict[str, float]
    body_type: str
    confidence_score: float
    processing_time_ms: int
    cache_expires_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Size Recommendation Schemas
# ============================================================================

class FitAnalysis(BaseModel):
    """Fit analysis for a body part"""
    status: str
    user_value: float
    size_range: List[float]
    difference: float


class AlternativeSize(BaseModel):
    """Alternative size recommendation"""
    size: str
    fit_score: int
    note: str


class SizeRecommendationRequest(BaseModel):
    """Size recommendation request"""
    measurement_id: UUID
    product_id: UUID


class SizeRecommendationResponse(BaseModel):
    """Size recommendation response"""
    recommendation_id: UUID
    recommended_size: str
    confidence: str
    fit_score: int
    fit_analysis: Dict[str, FitAnalysis]
    alternative_sizes: List[AlternativeSize]
    all_sizes: List[str]

    class Config:
        from_attributes = True


# ============================================================================
# Try-On Schemas
# ============================================================================

class TryOnGenerateRequest(BaseModel):
    """Virtual try-on generation request"""
    measurement_id: UUID
    product_id: UUID
    size: str
    style_reference: Optional[str] = None


class TryOnStatusResponse(BaseModel):
    """Try-on status response"""
    try_on_id: UUID
    status: str
    progress: Optional[int] = None
    message: Optional[str] = None
    result_image_url: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    cache_expires_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_allowed: bool = False

    class Config:
        from_attributes = True


# ============================================================================
# Webhook Schemas
# ============================================================================

class WebhookProductData(BaseModel):
    """Webhook product data"""
    id: int
    title: str
    shop_domain: str


class WebhookAppUninstallData(BaseModel):
    """Webhook app uninstall data"""
    shop_domain: str


# ============================================================================
# Analytics Schemas
# ============================================================================

class AnalyticsEventCreate(BaseModel):
    """Create analytics event"""
    event_type: str
    event_data: Optional[Dict[str, Any]] = None


# ============================================================================
# Error Schemas
# ============================================================================

class ErrorResponse(BaseModel):
    """Error response schema"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    retry_allowed: bool = False
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
