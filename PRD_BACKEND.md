# Virtual Try-On Shopify App - Backend PRD

**Version:** 1.0  
**Last Updated:** 2026-02-06  
**Tech Stack:** Python FastAPI, PostgreSQL, Redis, MediaPipe, OpenCV  
**Deployment:** Railway.app / AWS  

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [API Specifications](#api-specifications)
4. [Database Schema](#database-schema)
5. [Core Services](#core-services)
6. [External Integrations](#external-integrations)
7. [Security & Privacy](#security--privacy)
8. [Performance Requirements](#performance-requirements)
9. [Error Handling](#error-handling)
10. [Deployment](#deployment)

---

## Overview

### Purpose
Backend API for a Shopify app that enables virtual try-on functionality using AI-generated images based on customer body measurements extracted from photos.

### Key Features
- Shopify OAuth integration and product synchronization
- Dual-pose (front + side) body measurement extraction
- Size recommendation engine with heatmap generation
- Virtual try-on image generation using Google Imagen (nano-banana)
- Redis-based temporary image caching (24-hour retention)
- RESTful API for frontend widget consumption

### Technology Stack
```
Runtime:        Python 3.11+
Framework:      FastAPI 0.104+
Database:       PostgreSQL 15
Cache:          Redis 7
ML Libraries:   MediaPipe 0.10+, OpenCV 4.8+
Image AI:       Replicate API (nano-banana)
Deployment:     Railway.app / Docker
```

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Shopify Store                            │
│                 (Customer-facing Widget)                     │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS/JSON
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │   Shopify    │ │  Measurement │ │  Try-On      │        │
│  │   Sync       │ │  Extraction  │ │  Generation  │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└─────────┬──────────────────┬──────────────────┬────────────┘
          │                  │                  │
          ↓                  ↓                  ↓
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │PostgreSQL│      │  Redis   │      │Replicate │
    │          │      │ (Cache)  │      │   API    │
    └──────────┘      └──────────┘      └──────────┘
```

### Service Architecture

```
backend/
├── app/
│   ├── main.py                 # FastAPI application entry
│   ├── config.py               # Configuration management
│   ├── api/
│   │   ├── v1/
│   │   │   ├── auth.py         # Shopify OAuth endpoints
│   │   │   ├── products.py     # Product sync endpoints
│   │   │   ├── measurements.py # Measurement extraction endpoints
│   │   │   ├── recommendations.py # Size recommendation endpoints
│   │   │   ├── tryon.py        # Virtual try-on endpoints
│   │   │   └── heatmap.py      # Heatmap generation endpoints
│   ├── models/
│   │   ├── database.py         # SQLAlchemy models
│   │   └── schemas.py          # Pydantic schemas
│   ├── services/
│   │   ├── shopify_service.py  # Shopify API integration
│   │   ├── measurement_service.py # Body measurement extraction
│   │   ├── size_matcher.py     # Size recommendation logic
│   │   ├── heatmap_service.py  # Heatmap generation
│   │   ├── tryon_service.py    # Virtual try-on orchestration
│   │   ├── image_validator.py  # Image quality validation
│   │   └── cache_service.py    # Redis caching layer
│   ├── core/
│   │   ├── security.py         # Authentication & authorization
│   │   ├── database.py         # Database connection
│   │   └── redis.py            # Redis connection
│   └── utils/
│       ├── image_processing.py # Image manipulation utilities
│       └── validators.py       # Input validation helpers
├── tests/
├── requirements.txt
└── Dockerfile
```

---

## API Specifications

### Base URL
```
Production:  https://api.virtualtry-on.app
Development: http://localhost:8000
```

### Authentication
All API calls (except OAuth) require:
```
Headers:
  X-Store-ID: {store_uuid}
  X-Session-ID: {session_uuid}  # For customer requests
```

---

### 1. Shopify Integration APIs

#### 1.1 OAuth Initialization
```http
GET /api/v1/auth/shopify?shop={shop_domain}

Response 302:
Location: https://{shop}.myshopify.com/admin/oauth/authorize?
  client_id={app_id}&
  scope=read_products,write_script_tags&
  redirect_uri=https://api.virtualtry-on.app/api/v1/auth/callback
```

#### 1.2 OAuth Callback
```http
GET /api/v1/auth/callback?code={code}&shop={shop}&hmac={hmac}

Response 200:
{
  "store_id": "uuid",
  "shop_domain": "example.myshopify.com",
  "access_token": "encrypted_token",
  "script_tag_installed": true
}
```

#### 1.3 Sync Products
```http
POST /api/v1/products/sync
Headers:
  X-Store-ID: {store_uuid}

Response 200:
{
  "status": "success",
  "products_synced": 45,
  "products_with_sizes": 32,
  "products_without_sizes": 13
}
```

---

### 2. Measurement Extraction APIs

#### 2.1 Validate Images
```http
POST /api/v1/measurements/validate
Headers:
  X-Session-ID: {session_uuid}
Content-Type: multipart/form-data

Body:
  image: <binary>
  pose_type: "front" | "side"

Response 200:
{
  "valid": true,
  "is_person": true,
  "pose_detected": true,
  "pose_accuracy": 0.92,
  "issues": [],
  "confidence": "high"
}

Response 400 (validation failed):
{
  "valid": false,
  "is_person": false,
  "pose_detected": false,
  "pose_accuracy": 0.0,
  "issues": [
    "No person detected in image",
    "Image quality too low (minimum 640x480 required)"
  ],
  "confidence": "low"
}
```

**Validation Rules:**
- **Is Person Check:** MediaPipe pose detection must find 33 landmarks
- **Pose Accuracy:** 
  - Front: Shoulders approximately level (±15°), both arms visible
  - Side: One shoulder visible, clear side profile
- **Image Quality:** Min 640x480, good lighting (histogram analysis)
- **File Size:** Max 10MB
- **Format:** JPEG, PNG, WebP

#### 2.2 Extract Measurements
```http
POST /api/v1/measurements/extract
Headers:
  X-Session-ID: {session_uuid}
  X-Store-ID: {store_uuid}
Content-Type: multipart/form-data

Body:
  front_image: <binary>
  side_image: <binary>
  height_cm: 175.0
  weight_kg: 70.0
  gender: "male" | "female" | "unisex"

Response 200:
{
  "measurement_id": "uuid",
  "session_id": "uuid",
  "measurements": {
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
  },
  "body_type": "athletic",
  "confidence_score": 0.87,
  "missing_measurements": [],
  "cache_expires_at": "2026-02-07T12:00:00Z",
  "processing_time_ms": 2341
}

Response 422 (processing failed):
{
  "error": "measurement_extraction_failed",
  "message": "Could not detect full body pose in images",
  "details": {
    "front_image_valid": true,
    "side_image_valid": false,
    "missing_landmarks": ["left_shoulder", "left_hip"]
  }
}
```

**Processing Pipeline:**
1. Store images in Redis with 24h TTL (keys: `img:session:{uuid}:front`, `img:session:{uuid}:side`)
2. Run MediaPipe Pose on both images
3. Calculate pixel-to-cm ratio using provided height
4. Extract 2D measurements from front image
5. Extract depth measurements from side image
6. Calculate 15 body measurements using both images
7. Determine body type (slim/average/athletic/heavy) using BMI + proportions
8. Calculate confidence score based on landmark detection quality
9. Store measurements in PostgreSQL
10. Return results

---

### 3. Size Recommendation APIs

#### 3.1 Get Size Recommendation
```http
POST /api/v1/recommendations/size
Headers:
  X-Session-ID: {session_uuid}

Body:
{
  "measurement_id": "uuid",
  "product_id": "uuid"
}

Response 200:
{
  "recommendation_id": "uuid",
  "recommended_size": "M",
  "confidence": "high",
  "fit_score": 92,
  "fit_analysis": {
    "chest": {
      "status": "perfect_fit",
      "user_value": 94.5,
      "size_range": [91, 97],
      "difference": 0.5
    },
    "waist": {
      "status": "slightly_loose",
      "user_value": 78.3,
      "size_range": [86, 91],
      "difference": -7.7
    },
    "shoulder": {
      "status": "good_fit",
      "user_value": 43.2,
      "size_range": [42, 44],
      "difference": 1.2
    },
    "hip": {
      "status": "perfect_fit",
      "user_value": 98.1,
      "size_range": [97, 102],
      "difference": 1.1
    }
  },
  "alternative_sizes": [
    {
      "size": "S",
      "fit_score": 78,
      "note": "Tighter fit on chest and waist"
    },
    {
      "size": "L",
      "fit_score": 71,
      "note": "Looser fit overall"
    }
  ],
  "all_sizes": ["XS", "S", "M", "L", "XL"]
}
```

**Fit Status Values:**
- `perfect_fit`: Within 0-2cm of ideal range
- `good_fit`: Within 2-4cm of range
- `slightly_loose`: 4-7cm under minimum
- `slightly_tight`: 4-7cm over maximum
- `too_loose`: >7cm under minimum
- `too_tight`: >7cm over maximum

---

### 4. Heatmap Generation API

#### 4.1 Generate Heatmap
```http
POST /api/v1/heatmap/generate
Headers:
  X-Session-ID: {session_uuid}

Body:
{
  "measurement_id": "uuid",
  "product_id": "uuid",
  "size": "M"
}

Response 200:
{
  "heatmap_id": "uuid",
  "size": "M",
  "overall_fit_score": 87,
  "regions": {
    "shoulders": {
      "fit_status": "perfect",
      "color": "#4CAF50",
      "score": 95,
      "polygon_coords": [[x1,y1], [x2,y2], ...]
    },
    "chest": {
      "fit_status": "perfect",
      "color": "#4CAF50",
      "score": 92,
      "polygon_coords": [[x1,y1], [x2,y2], ...]
    },
    "waist": {
      "fit_status": "slightly_loose",
      "color": "#FFC107",
      "score": 72,
      "polygon_coords": [[x1,y1], [x2,y2], ...]
    },
    "hips": {
      "fit_status": "good",
      "color": "#8BC34A",
      "score": 88,
      "polygon_coords": [[x1,y1], [x2,y2], ...]
    }
  },
  "svg_overlay": "<svg>...</svg>",
  "legend": {
    "perfect": "#4CAF50",
    "good": "#8BC34A",
    "slightly_loose": "#FFC107",
    "slightly_tight": "#FF9800",
    "too_loose": "#F44336",
    "too_tight": "#D32F2F"
  }
}
```

**Heatmap Generation Logic:**
1. Retrieve pose landmarks from cached images
2. Get user measurements for body regions
3. Get garment measurements for specified size
4. Calculate fit score for each region:
   - Perfect (90-100): Green (#4CAF50)
   - Good (80-89): Light green (#8BC34A)
   - Slightly loose/tight (70-79): Yellow (#FFC107)
   - Too loose/tight (<70): Red/Orange (#F44336/#FF9800)
5. Generate SVG polygon overlays based on pose landmarks
6. Return structured heatmap data + SVG

---

### 5. Virtual Try-On API

#### 5.1 Generate Try-On Image
```http
POST /api/v1/tryon/generate
Headers:
  X-Session-ID: {session_uuid}

Body:
{
  "measurement_id": "uuid",
  "product_id": "uuid",
  "size": "M",
  "style_reference": "studio_1" | null
}

Response 202 (Accepted):
{
  "try_on_id": "uuid",
  "status": "processing",
  "estimated_time_seconds": 45
}

GET /api/v1/tryon/{try_on_id}/status

Response 200 (processing):
{
  "try_on_id": "uuid",
  "status": "processing",
  "progress": 65,
  "message": "Generating virtual try-on image..."
}

Response 200 (completed):
{
  "try_on_id": "uuid",
  "status": "completed",
  "result_image_url": "https://cdn.example.com/tryon/uuid.png",
  "size": "M",
  "processing_time_seconds": 38.2,
  "cache_expires_at": "2026-02-07T12:00:00Z"
}

Response 200 (failed):
{
  "try_on_id": "uuid",
  "status": "failed",
  "error": "Image generation failed",
  "retry_allowed": true
}
```

**Try-On Generation Pipeline:**

1. **Retrieve cached images** from Redis
   ```python
   front_image = redis.get(f"img:session:{session_id}:front")
   ```

2. **Get product image** from database
   ```python
   product_image = db.query(Product).get(product_id).images[0]
   ```

3. **Build AI prompt** based on measurements and size
   ```python
   fit_type = calculate_fit_type(user_measurements, garment_size)
   
   if fit_type == "tight":
       fit_desc = "fitted and snug across the chest and shoulders"
   elif fit_type == "loose":
       fit_desc = "loose and relaxed with extra room"
   else:
       fit_desc = "well-fitted with natural drape"
   
   prompt = f"""A realistic photograph of a person wearing a {product_type}.
   The garment should appear {fit_desc}.
   Professional product photography style, good lighting, plain background.
   Photorealistic, high quality, detailed fabric texture.
   The fit should clearly show size {size} on this person's body proportions."""
   ```

4. **Call Replicate API** (nano-banana)
   ```python
   output = replicate.run(
       "google/nano-banana",
       input={
           "prompt": prompt,
           "image_input": [front_image, product_image],
           "resolution": "2K",
           "aspect_ratio": "3:4",
           "output_format": "png"
       }
   )
   ```

5. **Cache result** in Redis (24h TTL)
   ```python
   redis.setex(
       f"tryon:{try_on_id}",
       86400,  # 24 hours
       result_image_data
   )
   ```

6. **Store metadata** in PostgreSQL
   ```python
   TryOn.create(
       try_on_id=uuid,
       measurement_id=measurement_id,
       product_id=product_id,
       size=size,
       result_url=cdn_url,
       processing_time=38.2
   )
   ```

---

### 6. Session Management API

#### 6.1 Create Session
```http
POST /api/v1/sessions/create
Headers:
  X-Store-ID: {store_uuid}

Body:
{
  "product_id": "uuid"
}

Response 200:
{
  "session_id": "uuid",
  "store_id": "uuid",
  "product_id": "uuid",
  "expires_at": "2026-02-07T12:00:00Z"
}
```

#### 6.2 Get Session Data
```http
GET /api/v1/sessions/{session_id}

Response 200:
{
  "session_id": "uuid",
  "store_id": "uuid",
  "product_id": "uuid",
  "measurement_id": "uuid" | null,
  "try_on_id": "uuid" | null,
  "created_at": "2026-02-06T12:00:00Z",
  "expires_at": "2026-02-07T12:00:00Z"
}
```

---

## Database Schema

### PostgreSQL Tables

```sql
-- Stores
CREATE TABLE stores (
    store_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shopify_domain VARCHAR(255) UNIQUE NOT NULL,
    shopify_access_token TEXT NOT NULL,
    store_name VARCHAR(255),
    email VARCHAR(255),
    script_tag_id VARCHAR(50),
    installation_status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_stores_domain ON stores(shopify_domain);

-- Products
CREATE TABLE products (
    product_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID REFERENCES stores(store_id) ON DELETE CASCADE,
    shopify_product_id VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    product_type VARCHAR(100),
    category VARCHAR(50), -- 'tops', 'bottoms', 'dresses', 'outerwear'
    vendor VARCHAR(255),
    images JSONB DEFAULT '[]',
    variants JSONB DEFAULT '[]',
    has_size_chart BOOLEAN DEFAULT FALSE,
    last_synced_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(store_id, shopify_product_id)
);

CREATE INDEX idx_products_store ON products(store_id);
CREATE INDEX idx_products_category ON products(category);

-- Size Charts
CREATE TABLE size_charts (
    size_chart_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(product_id) ON DELETE CASCADE,
    size_name VARCHAR(20) NOT NULL,
    size_system VARCHAR(20), -- 'US', 'EU', 'UK', 'LETTER'
    measurements JSONB NOT NULL,
    /*
    measurements format:
    {
      "chest": {"min": 91, "max": 97, "unit": "cm"},
      "waist": {"min": 76, "max": 81, "unit": "cm"},
      "hip": {"min": 97, "max": 102, "unit": "cm"},
      "shoulder_width": {"min": 42, "max": 44, "unit": "cm"},
      "inseam": {"min": 80, "max": 83, "unit": "cm"}
    }
    */
    source VARCHAR(50) DEFAULT 'standard', -- 'metafield', 'description', 'manual', 'standard'
    confidence_score FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_size_charts_product ON size_charts(product_id);

-- Sessions
CREATE TABLE sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID REFERENCES stores(store_id),
    product_id UUID REFERENCES products(product_id),
    measurement_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '24 hours'
);

CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- User Measurements
CREATE TABLE user_measurements (
    measurement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(session_id),
    measurements JSONB NOT NULL,
    /*
    measurements format:
    {
      "height": 175.0,
      "shoulder_width": 43.2,
      "chest": 94.5,
      "waist": 78.3,
      ...
    }
    */
    height_cm FLOAT NOT NULL,
    weight_kg FLOAT,
    gender VARCHAR(10),
    body_type VARCHAR(20), -- 'slim', 'average', 'athletic', 'heavy'
    confidence_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_measurements_session ON user_measurements(session_id);

-- Try-Ons
CREATE TABLE try_ons (
    try_on_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    measurement_id UUID REFERENCES user_measurements(measurement_id),
    product_id UUID REFERENCES products(product_id),
    size_name VARCHAR(20),
    processing_status VARCHAR(20), -- 'queued', 'processing', 'completed', 'failed'
    result_cache_key VARCHAR(200), -- Redis key for result image
    processing_time_seconds FLOAT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_try_ons_status ON try_ons(processing_status);
CREATE INDEX idx_try_ons_measurement ON try_ons(measurement_id);

-- Size Recommendations
CREATE TABLE size_recommendations (
    recommendation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    measurement_id UUID REFERENCES user_measurements(measurement_id),
    product_id UUID REFERENCES products(product_id),
    recommended_size VARCHAR(20),
    confidence VARCHAR(20), -- 'high', 'medium', 'low'
    fit_score INTEGER,
    fit_analysis JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Analytics Events (optional but recommended)
CREATE TABLE analytics_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID REFERENCES stores(store_id),
    session_id UUID,
    event_type VARCHAR(50), -- 'widget_opened', 'photo_captured', 'measurement_completed', etc.
    event_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_analytics_store_time ON analytics_events(store_id, created_at);
```

---

## Core Services

### 1. Measurement Service

**File:** `app/services/measurement_service.py`

```python
class MeasurementService:
    """
    Extracts body measurements from front and side pose images
    using MediaPipe and OpenCV
    """
    
    def __init__(self):
        self.pose_detector = mp.solutions.pose.Pose(
            static_image_mode=True,
            model_complexity=2,
            min_detection_confidence=0.7
        )
    
    async def extract_measurements(
        self,
        front_image: bytes,
        side_image: bytes,
        height_cm: float,
        weight_kg: float,
        gender: str
    ) -> Dict:
        """
        Main extraction method
        
        Returns:
        {
          "measurements": {...},
          "body_type": "athletic",
          "confidence_score": 0.87
        }
        """
        
        # 1. Detect pose landmarks
        front_landmarks = self._detect_pose(front_image)
        side_landmarks = self._detect_pose(side_image)
        
        if not front_landmarks or not side_landmarks:
            raise PoseDetectionError("Could not detect pose in images")
        
        # 2. Calculate pixel-to-cm ratio
        pixel_ratio = self._calculate_pixel_ratio(front_landmarks, height_cm)
        
        # 3. Extract measurements
        measurements = {
            "height": height_cm,
            "shoulder_width": self._measure_shoulder_width(front_landmarks, pixel_ratio),
            "chest": self._measure_chest(front_landmarks, side_landmarks, pixel_ratio, gender),
            "waist": self._measure_waist(front_landmarks, side_landmarks, pixel_ratio),
            "hip": self._measure_hip(front_landmarks, side_landmarks, pixel_ratio),
            "inseam": self._measure_inseam(front_landmarks, pixel_ratio),
            "arm_length": self._measure_arm_length(front_landmarks, pixel_ratio),
            "torso_length": self._measure_torso_length(front_landmarks, pixel_ratio),
            "neck": self._estimate_neck(front_landmarks, pixel_ratio, gender),
            "thigh": self._estimate_thigh(front_landmarks, side_landmarks, pixel_ratio),
            "upper_arm": self._estimate_upper_arm(front_landmarks, side_landmarks, pixel_ratio),
            "wrist": self._estimate_wrist(front_landmarks, pixel_ratio),
            "calf": self._estimate_calf(front_landmarks, side_landmarks, pixel_ratio),
            "ankle": self._estimate_ankle(front_landmarks, pixel_ratio),
            "bicep": self._estimate_bicep(front_landmarks, side_landmarks, pixel_ratio)
        }
        
        # 4. Determine body type
        body_type = self._classify_body_type(measurements, weight_kg, gender)
        
        # 5. Calculate confidence
        confidence = self._calculate_confidence(front_landmarks, side_landmarks)
        
        return {
            "measurements": measurements,
            "body_type": body_type,
            "confidence_score": confidence
        }
    
    def _measure_chest(self, front_landmarks, side_landmarks, pixel_ratio, gender):
        """
        Calculate chest circumference using:
        - Front width from shoulder to shoulder
        - Side depth from chest to back
        - Gender-based correction factors
        """
        # Get front chest width (pixels)
        left_shoulder = front_landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = front_landmarks[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER]
        front_width_px = abs(right_shoulder.x - left_shoulder.x)
        front_width_cm = front_width_px * pixel_ratio
        
        # Get side depth (pixels)
        chest_front = side_landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER]
        # Estimate back position (not directly visible)
        side_depth_px = front_width_px * 0.5  # Approximation
        side_depth_cm = side_depth_px * pixel_ratio
        
        # Calculate circumference from ellipse
        # C ≈ π * sqrt(2 * (a² + b²))
        # where a = width/2, b = depth/2
        import math
        a = front_width_cm / 2
        b = side_depth_cm / 2
        circumference = math.pi * math.sqrt(2 * (a**2 + b**2))
        
        # Apply gender correction
        if gender == "male":
            circumference *= 1.05  # Males typically have more depth
        elif gender == "female":
            circumference *= 1.02
        
        return round(circumference, 1)
```

**Key Measurement Formulas:**

**Direct Measurements (from landmarks):**
- Shoulder width: Distance between shoulder landmarks
- Height: Already provided by user
- Inseam: Hip to ankle distance
- Arm length: Shoulder to wrist distance
- Torso length: Shoulder to hip distance

**Calculated Circumferences:**
- Chest: Ellipse formula using front width + side depth
- Waist: Ellipse formula using front width + side depth
- Hip: Ellipse formula using front width + side depth
- Upper arm: Cylinder approximation from arm width
- Thigh: Cylinder approximation from thigh width

---

### 2. Image Validator Service

**File:** `app/services/image_validator.py`

```python
class ImageValidator:
    """
    Validates image quality and pose accuracy
    """
    
    async def validate_image(
        self,
        image: bytes,
        pose_type: str  # 'front' or 'side'
    ) -> Dict:
        """
        Comprehensive image validation
        
        Returns:
        {
          "valid": bool,
          "is_person": bool,
          "pose_detected": bool,
          "pose_accuracy": float,
          "issues": List[str],
          "confidence": str
        }
        """
        
        issues = []
        
        # 1. Check file format and size
        try:
            img = Image.open(BytesIO(image))
            width, height = img.size
        except Exception:
            return {
                "valid": False,
                "is_person": False,
                "pose_detected": False,
                "issues": ["Invalid image format"],
                "confidence": "low"
            }
        
        # 2. Check resolution
        if width < 640 or height < 480:
            issues.append(f"Image resolution too low ({width}x{height}). Minimum 640x480 required.")
        
        # 3. Check file size
        if len(image) > 10 * 1024 * 1024:  # 10MB
            issues.append("File size exceeds 10MB limit")
        
        # 4. Check lighting quality
        img_array = np.array(img.convert('L'))
        mean_brightness = np.mean(img_array)
        if mean_brightness < 50:
            issues.append("Image is too dark. Please ensure good lighting.")
        elif mean_brightness > 200:
            issues.append("Image is overexposed. Please reduce lighting.")
        
        # 5. Detect person using MediaPipe
        pose_detector = mp.solutions.pose.Pose(
            static_image_mode=True,
            min_detection_confidence=0.5
        )
        
        img_rgb = cv2.cvtColor(np.array(img), cv2.COLOR_BGR2RGB)
        results = pose_detector.process(img_rgb)
        
        if not results.pose_landmarks:
            return {
                "valid": False,
                "is_person": False,
                "pose_detected": False,
                "issues": issues + ["No person detected in image"],
                "confidence": "low"
            }
        
        # 6. Validate pose based on type
        landmarks = results.pose_landmarks.landmark
        pose_accuracy = self._validate_pose_type(landmarks, pose_type)
        
        if pose_type == "front":
            # Check if front-facing
            left_shoulder = landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER]
            right_shoulder = landmarks[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER]
            
            # Shoulders should be approximately level
            shoulder_diff = abs(left_shoulder.y - right_shoulder.y)
            if shoulder_diff > 0.1:  # More than 10% difference
                issues.append("Please stand straight with level shoulders")
                pose_accuracy *= 0.8
            
            # Both arms should be visible
            left_wrist = landmarks[mp.solutions.pose.PoseLandmark.LEFT_WRIST]
            right_wrist = landmarks[mp.solutions.pose.PoseLandmark.RIGHT_WRIST]
            if left_wrist.visibility < 0.5 or right_wrist.visibility < 0.5:
                issues.append("Please keep both arms visible and slightly away from body")
                pose_accuracy *= 0.9
        
        elif pose_type == "side":
            # Check if side profile
            # In side pose, one shoulder should be much more visible than the other
            left_shoulder_vis = landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER].visibility
            right_shoulder_vis = landmarks[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER].visibility
            
            if abs(left_shoulder_vis - right_shoulder_vis) < 0.3:
                issues.append("Please stand in a clear side profile")
                pose_accuracy *= 0.7
        
        # 7. Determine overall validity
        valid = len(issues) == 0 and pose_accuracy > 0.7
        
        confidence = "high" if pose_accuracy > 0.85 else "medium" if pose_accuracy > 0.7 else "low"
        
        return {
            "valid": valid,
            "is_person": True,
            "pose_detected": True,
            "pose_accuracy": pose_accuracy,
            "issues": issues,
            "confidence": confidence
        }
```

---

### 3. Cache Service (Redis)

**File:** `app/services/cache_service.py`

```python
class CacheService:
    """
    Manages temporary storage of images and results in Redis
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = 86400  # 24 hours
    
    async def store_image(
        self,
        session_id: str,
        image_type: str,  # 'front' or 'side'
        image_data: bytes
    ) -> str:
        """
        Store image in Redis with 24h TTL
        
        Returns: cache_key
        """
        cache_key = f"img:session:{session_id}:{image_type}"
        
        # Compress image before storing
        compressed = self._compress_image(image_data)
        
        await self.redis.setex(
            cache_key,
            self.ttl,
            compressed
        )
        
        return cache_key
    
    async def get_image(
        self,
        session_id: str,
        image_type: str
    ) -> bytes:
        """
        Retrieve image from Redis
        """
        cache_key = f"img:session:{session_id}:{image_type}"
        compressed = await self.redis.get(cache_key)
        
        if not compressed:
            raise ImageNotFoundError(f"Image not found: {cache_key}")
        
        return self._decompress_image(compressed)
    
    async def store_tryon_result(
        self,
        try_on_id: str,
        result_image: bytes
    ):
        """
        Store try-on result with 24h TTL
        """
        cache_key = f"tryon:{try_on_id}"
        compressed = self._compress_image(result_image)
        
        await self.redis.setex(
            cache_key,
            self.ttl,
            compressed
        )
    
    async def cleanup_session(
        self,
        session_id: str
    ):
        """
        Delete all cached data for a session
        """
        keys_to_delete = [
            f"img:session:{session_id}:front",
            f"img:session:{session_id}:side"
        ]
        
        await self.redis.delete(*keys_to_delete)
    
    def _compress_image(self, image_data: bytes) -> bytes:
        """
        Compress image to reduce Redis memory usage
        """
        img = Image.open(BytesIO(image_data))
        
        # Resize if too large (max 1024px on longest side)
        max_size = 1024
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = tuple(int(dim * ratio) for dim in img.size)
            img = img.resize(new_size, Image.LANCZOS)
        
        # Save as JPEG with quality 85
        output = BytesIO()
        img.convert('RGB').save(output, format='JPEG', quality=85, optimize=True)
        
        return output.getvalue()
```

**Redis Key Structure:**
```
img:session:{session_id}:front      → Front pose image (24h TTL)
img:session:{session_id}:side       → Side pose image (24h TTL)
tryon:{try_on_id}                   → Try-on result image (24h TTL)
session:{session_id}:metadata       → Session metadata (24h TTL)
```

---

## External Integrations

### 1. Shopify API Integration

**Authentication:** OAuth 2.0  
**API Version:** 2024-01 (GraphQL)  
**Rate Limits:** 2 calls/second

**Required Scopes:**
- `read_products` - Sync product data
- `write_script_tags` - Install widget
- `read_customers` - (Optional) Customer identification

**Key Operations:**

```graphql
# Fetch Products
query {
  products(first: 50) {
    edges {
      node {
        id
        title
        descriptionHtml
        productType
        vendor
        variants(first: 20) {
          edges {
            node {
              id
              title
              sku
              price
              availableForSale
            }
          }
        }
        images(first: 5) {
          edges {
            node {
              src
              altText
            }
          }
        }
        metafields(first: 10) {
          edges {
            node {
              namespace
              key
              value
            }
          }
        }
      }
    }
  }
}
```

---

### 2. Replicate API (nano-banana)

**Model:** `google/nano-banana`  
**Cost:** ~$0.02-0.04 per generation  
**Speed:** 30-60 seconds per image  

**Integration:**
```python
import replicate

output = replicate.run(
    "google/nano-banana",
    input={
        "prompt": generated_prompt,
        "image_input": [front_image, product_image],
        "resolution": "2K",
        "aspect_ratio": "3:4",
        "output_format": "png",
        "safety_filter_level": "block_only_high"
    }
)
```

**Error Handling:**
- Retry failed generations up to 2 times
- Timeout after 120 seconds
- Cache successful results to avoid regeneration

---

## Security & Privacy

### Data Privacy

**Image Storage Policy:**
- ✅ Images stored ONLY in Redis with 24h TTL
- ✅ NO permanent storage of customer photos
- ✅ Images auto-deleted after 24 hours
- ✅ NO personally identifiable information stored
- ❌ Images NOT uploaded to any third-party storage (S3, CDN, etc.)

**GDPR Compliance:**
- Session data expires after 24 hours
- Measurements stored anonymously (no customer IDs)
- Right to deletion implemented (DELETE /sessions/{id})
- Data processing agreement required for merchants

### API Security

**Authentication:**
```python
# Store authentication
@app.middleware("http")
async def verify_store(request: Request):
    store_id = request.headers.get("X-Store-ID")
    
    if not store_id:
        raise HTTPException(401, "Missing X-Store-ID header")
    
    store = db.query(Store).filter_by(store_id=store_id).first()
    if not store:
        raise HTTPException(403, "Invalid store")
    
    request.state.store = store
```

**Rate Limiting:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/measurements/extract")
@limiter.limit("10/minute")  # Max 10 extractions per minute per IP
async def extract_measurements(...):
    ...
```

**Input Validation:**
- All inputs validated using Pydantic schemas
- File uploads limited to 10MB
- Image formats restricted to JPEG, PNG, WebP
- SQL injection protection via SQLAlchemy ORM

---

## Performance Requirements

### Response Time Targets

| Endpoint | Target | Maximum |
|----------|--------|---------|
| OAuth callback | < 500ms | 1s |
| Product sync | < 3s | 10s |
| Image validation | < 2s | 5s |
| Measurement extraction | < 5s | 10s |
| Size recommendation | < 500ms | 1s |
| Heatmap generation | < 1s | 3s |
| Try-on generation | < 60s | 120s |

### Scalability Targets

**Phase 1 (Launch):**
- 100 concurrent users
- 500 try-ons/day
- 50 stores

**Phase 2 (Growth):**
- 1,000 concurrent users
- 5,000 try-ons/day
- 500 stores

**Infrastructure:**
- Auto-scaling: 2-10 instances
- Database: Connection pooling (max 100 connections)
- Redis: 2GB memory, eviction policy LRU
- CDN: Cloudflare for static assets

---

## Error Handling

### Error Response Format

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional context"
  },
  "retry_allowed": true,
  "request_id": "uuid"
}
```

### Error Codes

| Code | HTTP Status | Description | Retry |
|------|-------------|-------------|-------|
| `invalid_image_format` | 400 | Unsupported image format | No |
| `image_too_large` | 400 | File exceeds 10MB | No |
| `pose_not_detected` | 422 | No person detected in image | Yes |
| `pose_accuracy_low` | 422 | Pose quality insufficient | Yes |
| `measurement_extraction_failed` | 422 | Could not extract measurements | Yes |
| `product_not_found` | 404 | Product doesn't exist | No |
| `session_expired` | 410 | Session expired (>24h) | No |
| `rate_limit_exceeded` | 429 | Too many requests | Yes (after delay) |
| `external_api_error` | 502 | Replicate API failed | Yes |
| `internal_error` | 500 | Unexpected error | Yes |

### Logging

```python
import logging
import structlog

logger = structlog.get_logger()

# Log all errors with context
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=request.url.path,
        method=request.method,
        store_id=request.headers.get("X-Store-ID"),
        session_id=request.headers.get("X-Session-ID"),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
            "request_id": str(uuid.uuid4())
        }
    )
```

---

## Deployment

### Environment Variables

```bash
# Application
APP_ENV=production
APP_DEBUG=false
SECRET_KEY=<random-secret-key>

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://host:6379/0
REDIS_MAX_CONNECTIONS=50

# Shopify
SHOPIFY_API_KEY=<from-partner-dashboard>
SHOPIFY_API_SECRET=<from-partner-dashboard>
SHOPIFY_SCOPES=read_products,write_script_tags

# Replicate
REPLICATE_API_TOKEN=<from-replicate-account>

# Security
CORS_ORIGINS=https://yourdomain.com,https://*.myshopify.com
ALLOWED_UPLOAD_EXTENSIONS=jpg,jpeg,png,webp

# Performance
MAX_UPLOAD_SIZE=10485760  # 10MB in bytes
IMAGE_CACHE_TTL=86400  # 24 hours
SESSION_TTL=86400  # 24 hours
```

### Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/

# Run app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Health Checks

```python
@app.get("/health")
async def health_check():
    """
    Health check endpoint for load balancer
    """
    # Check database
    try:
        db.execute("SELECT 1")
        db_healthy = True
    except:
        db_healthy = False
    
    # Check Redis
    try:
        redis.ping()
        redis_healthy = True
    except:
        redis_healthy = False
    
    healthy = db_healthy and redis_healthy
    
    return {
        "status": "healthy" if healthy else "unhealthy",
        "database": "up" if db_healthy else "down",
        "redis": "up" if redis_healthy else "down",
        "timestamp": datetime.utcnow().isoformat()
    }
```

### Monitoring

**Metrics to Track:**
- Request rate (requests/second)
- Error rate (errors/second)
- Response times (p50, p95, p99)
- Database query times
- Redis hit rate
- Measurement extraction success rate
- Try-on generation success rate
- API costs (Replicate usage)

**Recommended Tools:**
- **APM:** New Relic / DataDog
- **Logging:** Sentry for errors
- **Metrics:** Prometheus + Grafana

---

## Shopify App Store Requirements

### App Listing Requirements

**Mandatory:**
1. Privacy policy URL
2. Support email
3. App icon (512x512 PNG)
4. Screenshots (min 3, 1024x768)
5. App description (min 50 chars)
6. Pricing information
7. GDPR compliance statement

### Technical Requirements

**Must Implement:**
- ✅ OAuth authentication (no password storage)
- ✅ Webhooks for `app/uninstalled`
- ✅ HTTPS only
- ✅ Data deletion upon uninstall
- ✅ Embedded app design (uses Shopify App Bridge)
- ✅ Mobile responsive
- ✅ Accessibility (WCAG 2.0 Level AA)

**App Review Checklist:**
- [ ] App loads in < 3 seconds
- [ ] All API calls use HTTPS
- [ ] Proper error handling
- [ ] No broken links
- [ ] Clear pricing display
- [ ] Privacy policy accessible
- [ ] Support contact available
- [ ] Uninstall webhook registered
- [ ] Data deletion implemented
- [ ] No hardcoded credentials

---

## API Versioning

Current version: **v1**

**Versioning Strategy:**
- URL-based: `/api/v1/...`, `/api/v2/...`
- Maintain v1 for minimum 12 months after v2 release
- Deprecation warnings in response headers:
  ```
  X-API-Deprecation: v1 will be deprecated on 2027-01-01
  X-API-Latest-Version: v2
  ```

---

## Testing Requirements

### Unit Tests
- All service methods
- Measurement calculations
- Size matching logic
- Heatmap generation

### Integration Tests
- Full API endpoints
- Database operations
- Redis caching
- External API mocking

### End-to-End Tests
- Complete user flow
- OAuth flow
- Product sync
- Measurement → Recommendation → Try-on

**Test Coverage Target:** > 80%

---

## Appendix

### Standard Size Charts

Located in: `app/data/size_standards.py`

Used when merchants don't provide size charts.

**Example:**
```python
STANDARD_SIZES = {
    'tops_women': {
        'XS': {
            'chest': (81, 86),
            'waist': (61, 66),
            'hip': (86, 91),
            'shoulder': (38, 40)
        },
        'S': {
            'chest': (86, 91),
            'waist': (66, 71),
            'hip': (91, 97),
            'shoulder': (40, 42)
        },
        # ... more sizes
    },
    # ... more categories
}
```

---

**End of Backend PRD**
