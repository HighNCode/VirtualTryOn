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


class HeatmapZone(BaseModel):
    """Individual body zone fit data for heatmap"""
    delta_cm: float
    user_cm: float
    product_cm: float
    fit_label: str
    fit_score: int
    color: str


class HeatmapResponse(BaseModel):
    """Heatmap generation response"""
    heatmap_id: UUID
    size: str
    overall_fit_score: int
    zones: Dict[str, HeatmapZone]
    legend: Dict[str, str]


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
    """Create analytics event — sent by the storefront widget"""
    event_type: str
    session_id: Optional[UUID] = None
    event_data: Optional[Dict[str, Any]] = None


class AnalyticsEventSaved(BaseModel):
    """Acknowledgement returned after a successful event ingestion"""
    saved: bool


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
    referral_detail: Optional[str] = None
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


class BillingActivateRequest(BaseModel):
    """Called by Remix after Shopify billing callback confirms a paid subscription"""
    plan_name: str
    billing_interval: str        # 'monthly' | 'annual'
    shopify_subscription_id: str
    status: str                  # 'active'
    # Trial is always applied when the plan has trial_days set — no opt-in flag needed


class PlanResponse(BaseModel):
    """Current plan information"""
    plan_name: str
    credits_limit: int
    plan_activated_at: Optional[datetime] = None
    shopify_subscription_id: Optional[str] = None


class WidgetCheckResponse(BaseModel):
    """Whether the widget should be shown for a given product"""
    enabled: bool


class WidgetSessionCreateRequest(BaseModel):
    """Create or resume a widget session from a Shopify product GID"""
    shopify_product_gid: str
    user_identifier: Optional[str] = None


class DashboardOverviewResponse(BaseModel):
    """All data needed to render the merchant dashboard overview screen"""
    # Section 1 — theme button status
    theme_extension_detected: bool
    themes_url: str
    # Section 2 — try-on usage (rolling 30 days)
    tryon_used_30d: int
    credits_limit: int
    plan_name: str
    # Section 3 — widget scope summary
    scope_type: str
    enabled_collections_count: int
    enabled_products_count: int


class WidgetConfigResponse(BaseModel):
    """Full widget config state — returned by GET and PATCH /merchant/widget-config"""
    scope_type: str
    enabled_collection_ids: List[str]
    enabled_product_ids: List[str]
    theme_extension_detected: bool
    widget_color: str  # Hex e.g. '#FF0000'; default applied in API layer when DB value is null
    weekly_tryon_limit: int


class WidgetConfigUpdateRequest(BaseModel):
    """Partial update of WidgetConfig from the dashboard (does not touch onboarding_step)"""
    scope_type: Optional[str] = None
    enabled_collection_ids: Optional[List[str]] = None
    enabled_product_ids: Optional[List[str]] = None
    theme_extension_detected: Optional[bool] = None
    widget_color: Optional[str] = None  # Hex color e.g. '#FF0000'
    weekly_tryon_limit: Optional[int] = None


# ============================================================================
# Billing Schemas
# ============================================================================

class PlanConfigResponse(BaseModel):
    """Definition of a single subscription plan (DB-backed)"""
    id: UUID
    name: str                       # 'starter' | 'growth'
    display_name: str               # 'Starter' | 'Growth'
    price_monthly: float            # 17.0
    price_annual_total: float       # 179.0  (Shopify charge amount)
    price_annual_per_month: float   # 14.0   (UI display only)
    annual_discount_pct: int        # 17
    credits_monthly: int            # 600
    credits_annual: int             # 7600
    overage_usd_per_tryon: float
    trial_days: Optional[int] = None
    trial_credits: Optional[int] = None
    usage_cap_usd: float
    features: List[str]
    is_current: bool                # True if this is the store's active plan
    is_active: bool


class PlansResponse(BaseModel):
    """All available subscription plans"""
    plans: List[PlanConfigResponse]


class CreateSubscriptionRequest(BaseModel):
    """Request to create a Shopify subscription for a paid plan"""
    plan_name: str           # 'starter' | 'growth'
    billing_interval: str    # 'monthly' | 'annual'
    return_url: str          # Remix callback URL after merchant approves on Shopify
    # Trial is always applied (trial_days from the plan) — no opt-in flag


class CreateSubscriptionResponse(BaseModel):
    """Shopify subscription creation result"""
    confirmation_url: str         # Shopify approval page — Remix redirects merchant here
    shopify_subscription_id: str  # GID returned by Shopify (for reference)


class BillingStatusResponse(BaseModel):
    """Full billing status — DB data enriched with live Shopify subscription info"""
    plan_name: str
    billing_interval: Optional[str] = None      # 'monthly' | 'annual' | null for free
    credits_limit: int
    trial_ends_at: Optional[datetime] = None
    plan_activated_at: Optional[datetime] = None
    shopify_subscription_id: Optional[str] = None
    # Live from Shopify (null if free plan or if Shopify call fails gracefully)
    subscription_status: Optional[str] = None      # 'ACTIVE' | 'PENDING' | 'CANCELLED'
    current_period_end: Optional[datetime] = None  # Next billing date
    is_test_subscription: Optional[bool] = None
    has_usage_billing: bool = False
    store_timezone: Optional[str] = None


class BillingUsageSummaryResponse(BaseModel):
    """Cycle-based credit usage summary for billing UI and enforcement diagnostics."""
    cycle_start_at: Optional[datetime] = None
    cycle_end_at: Optional[datetime] = None
    included_credits: int = 0
    consumed_credits: int = 0
    remaining_included_credits: int = 0
    overage_credits: int = 0
    overage_amount_usd: float = 0.0
    overage_blocked: bool = False
    overage_block_reason: Optional[str] = None
    overage_block_message: Optional[str] = None
    can_auto_charge_overage: bool = False


class CancelSubscriptionResponse(BaseModel):
    """Subscription cancellation confirmation"""
    cancelled: bool
    plan_name: str     # Always 'free' after cancellation
    credits_limit: int # Always 0 after cancellation


# ============================================================================
# AI Photoshoot Schemas (Merchant-Facing)
# ============================================================================

class PhotoshootModelResponse(BaseModel):
    """A full-body model photo from the unified library (customer studio look + merchant try-on)"""
    id: UUID
    gender: str
    age: Optional[str] = None         # "18-25" | "26-35" | "36-45" | "45+"
    body_type: Optional[str] = None   # "slim" | "athletic" | "regular" | "plus"
    image_url: str                    # /api/v1/merchant/photoshoot/models/{id}/image

    class Config:
        from_attributes = True


class PhotoshootModelFaceResponse(BaseModel):
    """A face/headshot photo from the model face library (used for model swap)"""
    id: UUID
    gender: str
    age: Optional[str] = None         # "18-25" | "26-35" | "36-45" | "45+"
    skin_tone: Optional[str] = None   # "fair" | "light" | "medium" | "tan" | "dark"
    image_url: str                    # /api/v1/merchant/photoshoot/model-faces/{id}/image

    class Config:
        from_attributes = True


class GhostMannequinRefResponse(BaseModel):
    """A reference pose image for a clothing type (front/side/back) shown in ghost mannequin UI"""
    id: UUID
    clothing_type: str   # "tops" | "bottoms" | "dresses" | "outerwear"
    pose: str            # "front" | "side" | "back"
    image_url: str       # /api/v1/merchant/photoshoot/ghost-mannequin-refs/{id}/image

    class Config:
        from_attributes = True


class GhostMannequinRequest(BaseModel):
    """Start a ghost mannequin job — 2 product images from the same Shopify product"""
    image1_url: str = Field(..., description="First product image URL (Shopify CDN)")
    image2_url: str = Field(..., description="Second product image URL (Shopify CDN)")
    shopify_product_gid: str = Field(..., description="Shopify product GID e.g. gid://shopify/Product/123")
    clothing_type: str = Field(..., description="Garment type: tops | bottoms | dresses | outerwear")


class PhotoshootJobResponse(BaseModel):
    """Photoshoot job status response — returned by POST (202) and GET /status"""
    job_id: UUID
    job_type: str
    status: str
    progress: Optional[int] = None
    message: Optional[str] = None
    result_image_url: Optional[str] = None     # /api/v1/merchant/photoshoot/jobs/{id}/result
    processing_time_seconds: Optional[float] = None
    error: Optional[str] = None
    retry_allowed: bool = False

    class Config:
        from_attributes = True


class PhotoshootApproveRequest(BaseModel):
    """Approve a completed photoshoot job and push the image to the Shopify product"""
    alt_text: Optional[str] = Field(None, description="Alt text for the Shopify product image")


class PhotoshootApproveResponse(BaseModel):
    """Result of approving a photoshoot job"""
    approved: bool
    shopify_media_id: Optional[str] = None   # GID from Shopify after upload
    message: str


# ============================================================================
# Analytics Schemas
# ============================================================================

class TopProductEntry(BaseModel):
    """Top product entry for analytics"""
    shopify_product_id: str
    title: str
    try_on_count: int
    cart_count: int         # added_to_cart events for this product
    conversion_rate: float  # cart_count / try_on_count × 100 (0.0 if try_on_count == 0)


class TrendEntry(BaseModel):
    """One calendar day in the try-on trend (line chart data)"""
    date: str   # ISO date "2026-03-02"
    try_ons: int


class StandardAnalyticsResponse(BaseModel):
    """All data for the Standard analytics sub-tab"""
    period_days: int
    period_start: datetime
    period_end: datetime
    # Engagement (from our DB)
    widget_opens: int
    unique_users: int
    total_try_ons: int
    credits_used: int
    add_to_cart_count: int
    # Conversions (Shopify Orders cross-ref — null if Shopify unavailable)
    conversions: Optional[int] = None
    conversion_rate: Optional[float] = None   # conversions / widget_opens × 100
    revenue_impact: Optional[float] = None    # sum of converted order totals (USD)
    # Returns (Shopify — null if Shopify unavailable)
    return_count: Optional[int] = None
    # Breakdown
    top_products: List[TopProductEntry]  # sorted by conversion_rate DESC
    trend: List[TrendEntry]              # one entry per calendar day; Y-axis = try_ons


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
