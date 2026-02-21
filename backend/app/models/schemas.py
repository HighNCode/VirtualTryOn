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
    measurements: Dict[str, Optional[float]]  # Can contain null values
    body_type: str
    confidence_score: float
    missing_measurements: List[str] = []  # List of measurement names that couldn't be determined
    missing_reason: Optional[str] = None  # Explanation for missing measurements
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
# Heatmap Schemas
# ============================================================================

class HeatmapGenerateRequest(BaseModel):
    """Heatmap generation request"""
    measurement_id: UUID
    product_id: UUID
    size: str


class HeatmapRegion(BaseModel):
    """Individual body region fit data for heatmap"""
    fit_status: str
    color: str
    score: int
    polygon_coords: List[List[List[float]]]


class HeatmapResponse(BaseModel):
    """Heatmap generation response"""
    heatmap_id: UUID
    size: str
    overall_fit_score: int
    regions: Dict[str, HeatmapRegion]
    svg_overlay: str
    legend: Dict[str, str]
    image_dimensions: Optional[List[int]] = None  # [width, height] if overlay mode, null for template


# ============================================================================
# Try-On Schemas
# ============================================================================

class TryOnGenerateRequest(BaseModel):
    """Virtual try-on generation request"""
    product_id: UUID


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
# Studio Background Schemas
# ============================================================================

class StudioBackgroundResponse(BaseModel):
    """Studio background image for try-on styling"""
    id: UUID
    gender: str
    image_url: str  # Endpoint URL: /api/v1/tryon/studio-backgrounds/{id}/image

    class Config:
        from_attributes = True


class StudioTryOnRequest(BaseModel):
    """Request to generate a studio-styled try-on"""
    try_on_id: UUID              # Original try-on (must be "completed")
    studio_background_id: UUID   # Which background to apply


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
# Merchant Onboarding Schemas
# ============================================================================

class OnboardingStatusResponse(BaseModel):
    """Full onboarding status — returned by GET /merchant/onboarding/status"""
    store_id: UUID
    onboarding_step: str
    onboarding_completed: bool
    plan_name: str
    goals: Optional[List[str]] = None
    referral_source: Optional[str] = None
    scope_type: Optional[str] = None
    enabled_collection_ids: Optional[List[str]] = None
    enabled_product_ids: Optional[List[str]] = None
    theme_extension_detected: bool = False


class GoalsRequest(BaseModel):
    """Step 2: merchant selects their goals"""
    goals: List[str]


class OnboardingStepResponse(BaseModel):
    """Generic response for any step that advances the wizard"""
    saved: bool
    next_step: str


class ReferralRequest(BaseModel):
    """Step 3: how the merchant heard about the app"""
    referral_source: str
    referral_detail: Optional[str] = None


class WidgetScopeRequest(BaseModel):
    """Step 4: which products the widget should appear on"""
    scope_type: str   # 'all' | 'selected_collections' | 'selected_products' | 'mixed'
    enabled_collection_ids: List[str] = []
    enabled_product_ids: List[str] = []


class WidgetScopeResponse(BaseModel):
    """Current widget scope configuration"""
    scope_type: str
    enabled_collection_ids: List[str]
    enabled_product_ids: List[str]


class ThemeStatusResponse(BaseModel):
    """Step 5: whether the theme extension block has been detected"""
    theme_extension_detected: bool
    themes_url: str


class ThemeStatusUpdateRequest(BaseModel):
    """Step 5: Remix reports detection result to the backend"""
    detected: bool


class OnboardingCompleteRequest(BaseModel):
    """Step 6: merchant completes onboarding (free plan path)"""
    plan: str   # "free"


class OnboardingCompleteResponse(BaseModel):
    """Onboarding completion confirmation"""
    completed: bool
    plan_name: str
    monthly_tryon_limit: int


class BillingActivateRequest(BaseModel):
    """Called by Remix after Shopify billing callback confirms a paid subscription"""
    plan_name: str
    shopify_subscription_id: str
    status: str   # "active"


class PlanResponse(BaseModel):
    """Current plan information"""
    plan_name: str
    monthly_tryon_limit: int
    plan_activated_at: Optional[datetime] = None
    shopify_subscription_id: Optional[str] = None


class WidgetCheckResponse(BaseModel):
    """Whether the widget should be shown for a given product"""
    enabled: bool


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
