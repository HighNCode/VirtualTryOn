# Virtual Try-On Shopify App - Backend PRD

**Version:** 1.1
**Last Updated:** 2026-02-17
**Tech Stack:** Python FastAPI, PostgreSQL, Redis, MediaPipe, SMPL, Google Vertex AI (Gemini)
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
ML Libraries:   MediaPipe 0.10+, OpenCV 4.8+, PyTorch, SMPL-X
Image AI:       Google Vertex AI — Gemini 2.5 Flash (image generation)
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
    │PostgreSQL│      │  Redis   │      │ Google   │
    │          │      │ (Cache)  │      │Vertex AI │
    │ Local:   │      │          │      │   API    │
    │ Docker   │      │          │      │(nano-    │
    │ Prod:    │      │          │      │ banana)  │
    │ Railway  │      │          │      │          │
    └──────────┘      └──────────┘      └──────────┘
```

### Database Configuration

**Local Development:**
```bash
# Use Docker Compose for local PostgreSQL
docker-compose up -d

# Connection string
DATABASE_URL=postgresql://dev:dev123@localhost:5432/virtual_tryon_dev
```

**Production (Railway.app):**
```bash
# Railway automatically provisions PostgreSQL
# Connection string provided by Railway (injected as env var)
DATABASE_URL=${DATABASE_URL}  # Auto-populated by Railway

# Railway also provides:
# - Automatic backups
# - Connection pooling
# - SSL encryption
```

**docker-compose.yml for Local:**
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: virtual_tryon_dev
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

volumes:
  postgres_data:
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
│   │   ├── measurement_service.py # SMPL-based body measurement extraction
│   │   ├── size_matcher.py     # Size recommendation logic
│   │   ├── heatmap_service.py  # Heatmap generation (SVG overlays)
│   │   ├── tryon_service.py    # Virtual try-on via Google Vertex AI (Gemini)
│   │   ├── image_validator.py  # Image quality validation
│   │   └── cache_service.py    # Redis caching layer
│   ├── data/
│   │   └── size_standards.py   # Fallback size charts (men/women)
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

#### Header-Based Auth (Store/Session APIs)
All API calls (except OAuth and App Bridge routes) require:
```
Headers:
  X-Store-ID: {store_uuid}
  X-Session-ID: {session_uuid}  # For customer requests
```

#### FastAPI Setup

**ShopifyAPI handles the OAuth flow, and python-jose handles session token JWT verification.**

**Step 1: OAuth Endpoints**

```
GET /api/v1/auth/shopify?shop={shop_domain}
  → Redirects to Shopify OAuth consent screen

GET /api/v1/auth/callback?shop=...&code=...&hmac=...&host=...
  → session.request_token(params) auto-validates HMAC
  → Saves store + encrypted access_token to DB
  → Installs script tag, triggers product sync
  → Redirects to /?shop={shop}&host={host}  (embedded app entry point)
```

Uses `shopify.Session` from `ShopifyAPI==10.0.0`. `session.request_token()` exchanges the code for an access token and verifies the HMAC automatically — no manual HMAC computation needed.

**Step 2: Session Token Verification Middleware**

Every API request from the React frontend (via Shopify App Bridge) carries a Shopify-issued JWT in the `Authorization` header. Verified by the `verify_session_token` dependency in `core/security.py`:

- Decodes HS256 JWT using `SHOPIFY_API_SECRET` as key, `audience=SHOPIFY_API_KEY`
- Validates `dest` claim is contained within `iss` claim (shop domain check)
- Returns decoded payload on success; raises HTTP 401 on failure

```python
# Protect any endpoint with:
from app.core.security import verify_session_token

@router.get("/some-endpoint")
async def endpoint(payload: dict = Depends(verify_session_token)):
    shop = payload["dest"]  # e.g. "https://mystore.myshopify.com"
    # use shop to look up access_token from DB for Shopify API calls
```

**CORS**

`main.py` configures `CORSMiddleware` with `allow_origin_regex=r"https://.*\.myshopify\.com"` in addition to the explicit `CORS_ORIGINS` env var, so requests from any merchant's embedded app iframe are accepted.

---

### 1. Shopify Integration APIs

#### How Product Data is Fetched from Shopify

**When a store installs the app:**

1. **OAuth completes** → Store data saved with access_token
2. **Webhook registered** → `products/create`, `products/update`, `products/delete`
3. **Initial sync triggered** → Fetches all products using Shopify GraphQL API
4. **Subsequent updates** → Automatic via webhooks

**Shopify GraphQL Product Sync:**

```graphql
# Query executed by backend to fetch products
query getProducts($cursor: String) {
  products(first: 50, after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        title
        descriptionHtml
        productType
        vendor
        tags
        
        # Product images
        images(first: 5) {
          edges {
            node {
              id
              src
              altText
            }
          }
        }
        
        # Variants (sizes)
        variants(first: 100) {
          edges {
            node {
              id
              title
              sku
              price
              availableForSale
              selectedOptions {
                name
                value
              }
            }
          }
        }
        
        # Metafields (for size charts if merchant added them)
        metafields(first: 20) {
          edges {
            node {
              namespace
              key
              value
              type
            }
          }
        }
      }
    }
  }
}
```

**Implementation:**

```python
# app/services/shopify_service.py

class ShopifyService:
    def __init__(self, shop_domain: str, access_token: str):
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.api_url = f"https://{shop_domain}/admin/api/2024-01/graphql.json"
    
    async def sync_all_products(self, store_id: str):
        """
        Fetch all products from Shopify and store in database
        
        Called during:
        1. Initial app installation (OAuth callback)
        2. Manual sync trigger from merchant dashboard
        3. Daily cron job (optional)
        """
        
        cursor = None
        products_synced = 0
        
        while True:
            # Fetch batch of products
            query = self._build_products_query(cursor)
            response = await self._graphql_request(query)
            
            products = response['data']['products']['edges']
            page_info = response['data']['products']['pageInfo']
            
            # Process each product
            for product_edge in products:
                product_node = product_edge['node']
                
                # Extract product data
                product_data = self._extract_product_data(product_node)
                
                # Save to database
                await self._save_product(store_id, product_data)
                
                # Extract size chart if available
                size_chart = self._extract_size_chart(product_node)
                if size_chart:
                    await self._save_size_chart(product_data['product_id'], size_chart)
                
                products_synced += 1
            
            # Check if more pages
            if not page_info['hasNextPage']:
                break
            
            cursor = page_info['endCursor']
        
        return {
            'products_synced': products_synced,
            'timestamp': datetime.utcnow()
        }
    
    def _extract_product_data(self, product_node: dict) -> dict:
        """
        Transform Shopify product data to our format
        """
        return {
            'shopify_product_id': product_node['id'].split('/')[-1],
            'title': product_node['title'],
            'description': product_node['descriptionHtml'],
            'product_type': product_node['productType'],
            'vendor': product_node['vendor'],
            'category': self._categorize_product(product_node),
            'images': [
                {
                    'src': img['node']['src'],
                    'alt': img['node']['altText']
                }
                for img in product_node['images']['edges']
            ],
            'variants': [
                {
                    'id': var['node']['id'].split('/')[-1],
                    'title': var['node']['title'],
                    'sku': var['node']['sku'],
                    'price': var['node']['price'],
                    'size': self._extract_size_from_variant(var['node'])
                }
                for var in product_node['variants']['edges']
            ]
        }
    
    def _extract_size_chart(self, product_node: dict) -> dict:
        """
        Extract size chart from metafields if merchant configured it
        
        Expected metafield format:
        namespace: "custom"
        key: "size_chart"
        value: JSON string with size measurements
        """
        metafields = product_node.get('metafields', {}).get('edges', [])
        
        for metafield_edge in metafields:
            metafield = metafield_edge['node']
            
            if (metafield['namespace'] == 'custom' and 
                metafield['key'] == 'size_chart'):
                
                try:
                    size_data = json.loads(metafield['value'])
                    return self._parse_size_chart(size_data)
                except:
                    pass
        
        return None
    
    def _categorize_product(self, product_node: dict) -> str:
        """
        Auto-categorize product based on type and tags
        
        Returns: 'tops', 'bottoms', 'dresses', 'outerwear', or 'unknown'
        """
        product_type = product_node['productType'].lower()
        tags = [tag.lower() for tag in product_node.get('tags', [])]
        title = product_node['title'].lower()
        
        # Check product type first
        if any(keyword in product_type for keyword in ['shirt', 'tee', 't-shirt', 'top', 'blouse']):
            return 'tops'
        if any(keyword in product_type for keyword in ['pants', 'jeans', 'trousers', 'shorts']):
            return 'bottoms'
        if 'dress' in product_type:
            return 'dresses'
        if any(keyword in product_type for keyword in ['jacket', 'coat', 'hoodie', 'sweater']):
            return 'outerwear'
        
        # Check tags
        if 'tops' in tags or 'shirts' in tags:
            return 'tops'
        if 'bottoms' in tags or 'pants' in tags:
            return 'bottoms'
        if 'dresses' in tags:
            return 'dresses'
        if 'outerwear' in tags or 'jackets' in tags:
            return 'outerwear'
        
        return 'unknown'
```

**Webhook Handlers for Real-time Sync:**

```python
# app/api/v1/webhooks.py

@app.post("/api/v1/webhooks/products/create")
async def handle_product_create(request: Request):
    """
    Called by Shopify when merchant creates a new product
    """
    # Verify webhook authenticity
    if not verify_webhook(request):
        raise HTTPException(401, "Invalid webhook")
    
    product_data = await request.json()
    store = get_store_from_shop_domain(product_data['shop_domain'])
    
    # Fetch full product details from Shopify
    shopify_service = ShopifyService(store.shopify_domain, store.access_token)
    product = await shopify_service.fetch_product(product_data['id'])
    
    # Save to database
    await save_product(store.store_id, product)
    
    return {"status": "success"}

@app.post("/api/v1/webhooks/products/update")
async def handle_product_update(request: Request):
    """
    Called when merchant updates product
    """
    # Similar to create, but update existing record
    pass

@app.post("/api/v1/webhooks/products/delete")
async def handle_product_delete(request: Request):
    """
    Called when merchant deletes product
    """
    product_data = await request.json()
    shopify_product_id = str(product_data['id'])
    
    # Delete from database
    await db.execute(
        "DELETE FROM products WHERE shopify_product_id = :id",
        {"id": shopify_product_id}
    )
    
    return {"status": "success"}

@app.post("/api/v1/webhooks/app/uninstalled")
async def handle_app_uninstall(request: Request):
    """
    Called by Shopify when merchant uninstalls the app
    
    CRITICAL: Must handle data deletion per Shopify requirements
    """
    if not verify_webhook(request):
        raise HTTPException(401, "Invalid webhook")
    
    webhook_data = await request.json()
    shop_domain = webhook_data['shop_domain']
    
    logger.info(f"App uninstalled by: {shop_domain}")
    
    # Get store from database
    store = await db.query(Store).filter_by(shopify_domain=shop_domain).first()
    
    if not store:
        return {"status": "store_not_found"}
    
    store_id = store.store_id
    
    # Mark store as uninstalled (soft delete)
    store.installation_status = 'uninstalled'
    store.uninstalled_at = datetime.utcnow()
    await db.commit()
    
    # Delete script tag from Shopify (if still exists)
    try:
        shopify_service = ShopifyService(shop_domain, store.shopify_access_token)
        await shopify_service.delete_script_tag(store.script_tag_id)
    except:
        pass  # Script tag might already be deleted
    
    # Schedule data deletion (optional: wait 30 days per GDPR)
    await schedule_data_deletion(store_id, days=30)
    
    # Send notification to admin
    await send_uninstall_notification(shop_domain, store_id)
    
    logger.info(f"Uninstall processed for {shop_domain}")
    
    return {"status": "success"}

async def schedule_data_deletion(store_id: str, days: int = 30):
    """
    Schedule complete data deletion after grace period
    
    Gives merchants time to reinstall if uninstalled by mistake
    """
    deletion_date = datetime.utcnow() + timedelta(days=days)
    
    # Create deletion task
    await db.execute(
        """
        INSERT INTO data_deletion_queue (store_id, scheduled_for)
        VALUES (:store_id, :scheduled_for)
        """,
        {"store_id": store_id, "scheduled_for": deletion_date}
    )

async def execute_data_deletion(store_id: str):
    """
    Permanently delete all store data
    
    Called by background worker after grace period
    """
    logger.info(f"Executing data deletion for store: {store_id}")
    
    # Delete in correct order (respect foreign keys)
    tables = [
        'analytics_events',
        'size_recommendations',
        'try_ons',
        'user_measurements',
        'sessions',
        'size_charts',
        'products',
        'stores'
    ]
    
    for table in tables:
        await db.execute(
            f"DELETE FROM {table} WHERE store_id = :store_id",
            {"store_id": store_id}
        )
    
    # Clear Redis cache for this store
    pattern = f"*:store:{store_id}:*"
    keys = await redis.keys(pattern)
    if keys:
        await redis.delete(*keys)
    
    logger.info(f"Data deletion completed for store: {store_id}")
    
    return {"status": "deleted", "store_id": store_id}
```

**Uninstall Flow Diagram:**

```
Merchant clicks "Uninstall" in Shopify
    ↓
Shopify sends webhook to /api/v1/webhooks/app/uninstalled
    ↓
Backend marks store as "uninstalled"
    ↓
Backend deletes script tag from Shopify
    ↓
Backend schedules data deletion (30 days grace period)
    ↓
[30 days later]
    ↓
Background worker executes permanent deletion
    ↓
All store data removed from database + Redis
```

**Merchant Re-installation:**

If merchant reinstalls within 30 days:
- Cancel scheduled deletion
- Reactivate store record
- Reinstall script tag
- All data preserved

```python
@app.get("/api/v1/auth/callback")
async def oauth_callback(code: str, shop: str, hmac: str):
    """
    OAuth callback - handles both new installs and re-installs
    """
    # ... exchange code for access_token ...
    
    # Check if store previously existed
    existing_store = await db.query(Store).filter_by(
        shopify_domain=shop
    ).first()
    
    if existing_store and existing_store.installation_status == 'uninstalled':
        # Re-installation - reactivate account
        existing_store.installation_status = 'active'
        existing_store.shopify_access_token = access_token
        existing_store.reinstalled_at = datetime.utcnow()
        
        # Cancel scheduled deletion
        await db.execute(
            "DELETE FROM data_deletion_queue WHERE store_id = :store_id",
            {"store_id": existing_store.store_id}
        )
        
        logger.info(f"Store re-installed: {shop}")
        
    else:
        # New installation
        existing_store = Store.create(
            shopify_domain=shop,
            shopify_access_token=access_token,
            installation_status='active'
        )
    
    # Continue with normal setup...
    await install_script_tag(existing_store)
    await sync_products(existing_store.store_id)
    
    return redirect_to_shopify_admin(shop)
```

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
  Authorization: Bearer <shopify_session_token>

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

**Processing Pipeline (SMPL-Based, 3-Stage):**
1. Store images in Redis with 24h TTL (keys: `img:session:{uuid}:front`, `img:session:{uuid}:side`)
2. **Stage 1 - PoseDetector:** Run MediaPipe Pose → extract 33 2D landmarks
3. **Stage 2 - SMPLShapeFitter:** Optimize SMPL body model betas to fit 2D keypoints (PyTorch Adam optimizer, weak perspective projection)
4. **Stage 3 - SMPLMeasurer:** Extract 15 measurements from the fitted SMPL mesh
   - Primary method: SMPL-Anthropometry library (plane-cut cross-sections)
   - Fallback method: Vertex-based (convex hull / ellipse fitting)
5. Front image required, side image optional (weighted average 60/40 if both available)
6. Measurements can be `null` for low-confidence values (`missing_measurements` list returned)
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
      "polygon_coords": [[[x1,y1], [x2,y2], ...]]
    },
    "chest": {
      "fit_status": "perfect",
      "color": "#4CAF50",
      "score": 92,
      "polygon_coords": [[[x1,y1], [x2,y2], ...]]
    },
    "sleeves": {
      "fit_status": "good",
      "color": "#8BC34A",
      "score": 85,
      "polygon_coords": [
        [[x1,y1], ...],  // left arm rectangle
        [[x1,y1], ...]   // right arm rectangle
      ]
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
  },
  "image_dimensions": {"width": 1024, "height": 1024}
}
```

**Heatmap Generation Logic:**
1. Retrieve pose landmarks from cached front image (or use template mode if unavailable)
2. Get user measurements for body regions
3. Get garment measurements for specified size (from DB size_charts or fallback `size_standards.py`)
4. Calculate fit score for each region:
   - Perfect (90-100): Green (#4CAF50)
   - Good (80-89): Light green (#8BC34A)
   - Slightly loose/tight (70-79): Yellow (#FFC107)
   - Too loose/tight (<70): Red/Orange (#F44336/#FF9800)
5. Generate SVG polygon overlays based on pose landmarks (overlay mode) or template coordinates
6. `polygon_coords` is `List[List[List[float]]]` — list of sub-polygons, each rendered as a separate `<polygon>` SVG element (needed for multi-part regions like sleeves)
7. Arm rectangles use perpendicular-to-arm-direction vectors for proper diagonal rendering

**Regions by Category:**
- **tops:** shoulders, chest, waist, neck, sleeves (arm_length)
- **bottoms:** waist, hips, thigh, calf, ankle
- **dresses:** shoulders, chest, waist, hips, neck, sleeves (arm_length)
- **outerwear:** shoulders, chest, waist, sleeves (arm_length)

8. Return structured heatmap data + SVG

---

### 5. Virtual Try-On API

#### 5.1 Generate Try-On Image
```http
POST /api/v1/tryon/generate
Headers:
  X-Session-ID: {session_uuid}
  X-Store-ID: {store_uuid}

Body:
{
  "product_id": "uuid"
}

Response 202 (Accepted):
{
  "try_on_id": "uuid",
  "status": "processing",
  "estimated_time_seconds": 45
}
```

**Note:** The try-on request only requires `product_id`. The person's image is taken from the session's cached front photo. No measurements, size, or fit data are needed — the model simply fits the product on the person as-is.

#### 5.2 Poll Try-On Status
```http
GET /api/v1/tryon/{try_on_id}/status

Response 200 (processing):
{
  "try_on_id": "uuid",
  "status": "processing",
  "progress": 50,
  "message": "Generating virtual try-on image..."
}

Response 200 (completed):
{
  "try_on_id": "uuid",
  "status": "completed",
  "result_image_url": "/api/v1/tryon/{try_on_id}/image",
  "processing_time_seconds": 38.2,
  "cache_expires_at": "2026-02-18T18:00:00Z"
}

Response 200 (failed):
{
  "try_on_id": "uuid",
  "status": "failed",
  "error": "Image generation failed",
  "retry_allowed": true
}
```

#### 5.3 Get Try-On Image
```http
GET /api/v1/tryon/{try_on_id}/image

Response 200:
Content-Type: image/png
<binary image data>

Response 410:
"Try-on image has expired from cache"
```

**Try-On Generation Pipeline:**

1. **Retrieve person image** from session cache in Redis
   ```python
   front_image = cache.get_image(session_id, "front")
   ```

2. **Get product image URL** from database
   ```python
   product_image_url = product.images[0]["src"]
   ```

3. **Build simple prompt** (no measurement/size awareness)
   ```python
   prompt = (
       f"Using the provided person photo and product photo, generate a single "
       f"photorealistic image of the person wearing the {product_title} ({category}). "
       f"Keep the person's face, body, pose, and background exactly the same. "
       f"Keep the product's color, texture, and design exactly the same. "
       f"Fit the product naturally on the person's body. "
       f"The result should look like a real photograph, not a collage."
   )
   ```

4. **Call Google Vertex AI (Gemini 2.5 Flash)**
   ```python
   import vertexai
   from vertexai.generative_models import GenerativeModel, GenerationConfig, Part

   vertexai.init(project=settings.GOOGLE_CLOUD_PROJECT,
                 location=settings.GOOGLE_CLOUD_LOCATION)
   model = GenerativeModel(settings.TRYON_MODEL)

   # Pass images directly as Parts (no file upload API needed)
   response = model.generate_content(
       [
           Part.from_data(data=person_image, mime_type="image/jpeg"),
           Part.from_data(data=product_bytes, mime_type="image/jpeg"),
           prompt,
       ],
       generation_config=GenerationConfig(
           response_modalities=["IMAGE"],
       ),
   )

   # Extract generated image
   result_image = response.candidates[0].content.parts[0].inline_data.data
   ```

5. **Cache result** in Redis (24h TTL)
   ```python
   cache.store_tryon_result(try_on_id, result_image)
   ```

6. **Store metadata** in PostgreSQL
   ```python
   TryOn(
       try_on_id=uuid,
       product_id=product_id,
       result_cache_key=f"tryon:{try_on_id}",
       processing_time_seconds=elapsed,
       processing_status="completed"
   )
   ```

**Background Processing:** The `POST /generate` endpoint returns 202 immediately and runs generation in a `BackgroundTasks` thread. The client polls `GET /status` until completion.

---

### 5.4 Studio Look Feature

Allows users to place their try-on result into different studio/environment backgrounds.

**DB Model:**
```sql
CREATE TABLE studio_backgrounds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gender VARCHAR(10) NOT NULL,         -- "male", "female", "unisex"
    image_path VARCHAR(300) NOT NULL,    -- Relative path: "male/studio_1.jpg"
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Static images** stored in `backend/static/studio/{gender}/` directory. Frontend randomizes display order.

**TryOn table extensions:**
```sql
ALTER TABLE try_ons ADD COLUMN studio_background_id UUID REFERENCES studio_backgrounds(id);
ALTER TABLE try_ons ADD COLUMN parent_try_on_id UUID REFERENCES try_ons(try_on_id);
```

#### 5.4.1 List Studio Backgrounds
```http
GET /api/v1/tryon/studio-backgrounds?gender=male

Response 200:
[
  {
    "id": "uuid",
    "gender": "male",
    "image_url": "/api/v1/tryon/studio-backgrounds/{id}/image"
  },
  ...
]
```

Returns backgrounds matching the given gender plus all "unisex" backgrounds.

#### 5.4.2 Get Studio Background Image
```http
GET /api/v1/tryon/studio-backgrounds/{id}/image

Response 200:
Content-Type: image/jpeg
<binary image data>
```

#### 5.4.3 Generate Studio Try-On
```http
POST /api/v1/tryon/studio

Body:
{
  "try_on_id": "uuid",              // Original completed try-on
  "studio_background_id": "uuid"    // Which background to apply
}

Response 202 (new generation):
{
  "try_on_id": "new-uuid",
  "status": "processing",
  "estimated_time_seconds": 45
}

Response 200 (cached — same parent+background generated within 1 hour):
{
  "try_on_id": "existing-uuid",
  "status": "completed",
  "result_image_url": "/api/v1/tryon/{try_on_id}/image"
}
```

Uses the same `GET /status` and `GET /image` endpoints for polling and serving.

**Studio Caching (1-hour TTL):**
- Results are cached in Redis keyed by `studio:{parent_try_on_id}:{studio_background_id}`
- When the same parent+background combo is requested again within 1 hour, the endpoint returns `status: "completed"` with `result_image_url` immediately (no re-generation)
- Configurable via `STUDIO_CACHE_TTL` env var (default: 3600 seconds)

**Studio Generation Pipeline:**
1. Check Redis for cached studio result (parent+background combo)
2. If cached: return existing try-on ID and image URL immediately
3. If not cached: retrieve original try-on image from Redis cache
4. Read studio background from static file
5. Send both to Vertex AI (Gemini) with prompt: "Place the person into the environment. Keep appearance, clothing, pose the same. Only change background and lighting."
6. Cache result in both `tryon:{id}` (24h) and `studio:{parent}:{bg}` (1h) keys, update DB record

---

### 6. Session Management API

#### User Recognition & Session Reuse

**Key Feature:** If a user has taken photos within the last 24 hours, they don't need to retake them.

**Implementation Strategy:**
- Use browser fingerprinting + optional cookie for user identification
- Store user_identifier in Redis with measurement_id mapping
- Check if user has recent measurements before asking for photos

#### 6.1 Create or Resume Session
```http
POST /api/v1/sessions/create
Headers:
  X-Store-ID: {store_uuid}

Body:
{
  "product_id": "uuid",
  "user_identifier": "browser_fingerprint_hash"  // From frontend
}

Response 200 (new user):
{
  "session_id": "uuid",
  "store_id": "uuid",
  "product_id": "uuid",
  "has_existing_measurements": false,
  "expires_at": "2026-02-07T12:00:00Z"
}

Response 200 (returning user within 24h):
{
  "session_id": "uuid",
  "store_id": "uuid",
  "product_id": "uuid",
  "has_existing_measurements": true,
  "measurement_id": "existing_uuid",
  "measurements": {
    "height": 175.0,
    "chest": 94.5,
    // ... all measurements
  },
  "photos_available": true,
  "cached_until": "2026-02-07T12:00:00Z",
  "expires_at": "2026-02-07T12:00:00Z"
}
```

**Backend Logic:**

```python
# app/api/v1/sessions.py

@app.post("/api/v1/sessions/create")
async def create_or_resume_session(
    store_id: str,
    product_id: str,
    user_identifier: str
):
    """
    Create new session or resume existing one if user has recent data
    """
    
    # Check if user has measurements from last 24 hours
    cache_key = f"user:{store_id}:{user_identifier}:measurement"
    cached_measurement_id = await redis.get(cache_key)
    
    if cached_measurement_id:
        # User has recent measurements
        measurement = await db.query(UserMeasurement).get(cached_measurement_id)
        
        # Check if images still in cache
        front_img_key = f"img:measurement:{cached_measurement_id}:front"
        side_img_key = f"img:measurement:{cached_measurement_id}:side"
        
        front_exists = await redis.exists(front_img_key)
        side_exists = await redis.exists(side_img_key)
        
        photos_available = front_exists and side_exists
        
        # Create new session but link to existing measurements
        session = Session.create(
            store_id=store_id,
            product_id=product_id,
            measurement_id=cached_measurement_id if photos_available else None
        )
        
        return {
            "session_id": session.session_id,
            "store_id": store_id,
            "product_id": product_id,
            "has_existing_measurements": True,
            "measurement_id": cached_measurement_id,
            "measurements": measurement.measurements,
            "photos_available": photos_available,
            "cached_until": get_cache_expiry(cached_measurement_id),
            "expires_at": session.expires_at
        }
    
    else:
        # New user or expired cache
        session = Session.create(
            store_id=store_id,
            product_id=product_id
        )
        
        return {
            "session_id": session.session_id,
            "store_id": store_id,
            "product_id": product_id,
            "has_existing_measurements": False,
            "expires_at": session.expires_at
        }

# After successful measurement extraction:
@app.post("/api/v1/measurements/extract")
async def extract_measurements(...):
    # ... existing extraction logic ...
    
    # After saving measurements, cache user mapping
    if user_identifier:
        cache_key = f"user:{store_id}:{user_identifier}:measurement"
        await redis.setex(
            cache_key,
            86400,  # 24 hours
            measurement_id
        )
        
        # Also store images with measurement_id as key for easier retrieval
        await redis.rename(
            f"img:session:{session_id}:front",
            f"img:measurement:{measurement_id}:front"
        )
        await redis.rename(
            f"img:session:{session_id}:side",
            f"img:measurement:{measurement_id}:side"
        )
    
    return response
```

#### Cross-Product Session Reuse

**Scenario:** User tries on Product A, then navigates to Product B and clicks "Try On"

**Flow:**
1. Widget creates session for Product B
2. Backend detects user has recent measurements
3. Backend returns `has_existing_measurements: true` with data
4. **Frontend skips** photo capture and measurement screens
5. **Frontend goes directly** to generating try-on for Product B
6. Backend uses cached images + new product to generate try-on

**Frontend receives:**
```json
{
  "has_existing_measurements": true,
  "measurement_id": "abc-123",
  "measurements": { /* all 15 measurements */ },
  "photos_available": true
}
```

**Frontend behavior:**
```javascript
if (sessionData.has_existing_measurements && sessionData.photos_available) {
  // Skip to generating try-on directly
  showProcessingScreen();
  
  // Generate size recommendation
  const recommendation = await api.getSizeRecommendation(
    sessionData.measurement_id,
    newProductId
  );
  
  // Generate heatmap
  const heatmap = await api.generateHeatmap(
    sessionData.measurement_id,
    newProductId,
    recommendation.recommended_size
  );
  
  // Generate try-on
  const tryOn = await api.generateTryOn(
    sessionData.measurement_id,
    newProductId,
    recommendation.recommended_size
  );
  
  // Show results
  showResultsScreen(tryOn, heatmap, recommendation);
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
    measurement_id UUID REFERENCES user_measurements(measurement_id),  -- nullable, not required
    product_id UUID REFERENCES products(product_id) NOT NULL,
    processing_status VARCHAR(20), -- 'queued', 'processing', 'completed', 'failed'
    result_cache_key VARCHAR(200), -- Redis key for result image
    processing_time_seconds FLOAT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
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

### 1. Measurement Service (SMPL-Based)

**File:** `app/services/measurement_service.py`

**Three-stage pipeline:**

```python
class PoseDetector:
    """Stage 1: MediaPipe Pose → 33 2D landmarks"""
    def detect(self, image_bytes: bytes) -> dict:
        # Returns {"landmarks": List[33 landmarks], "image_shape": (H, W)}

class SMPLShapeFitter:
    """Stage 2: Optimize SMPL betas to fit 2D keypoints"""
    def fit(self, landmarks_2d, image_shape, height_cm, gender) -> dict:
        # Uses PyTorch Adam optimizer with weak perspective projection
        # Optimizes 10 SMPL shape parameters (betas) to match 2D keypoints
        # Returns {"betas": tensor, "vertices": ndarray, "joints_3d": ndarray}

class SMPLMeasurer:
    """Stage 3: Extract 15 measurements from fitted SMPL mesh"""
    def measure(self, vertices, joints_3d, gender, height_cm) -> dict:
        # Primary: SMPL-Anthropometry library (plane-cut cross-sections)
        # Fallback: Vertex-based (convex hull / ellipse fitting)
        # Returns {"measurements": dict, "confidence": float, "missing": list}
```

**15 Extracted Measurements:**
height, shoulder_width, arm_length, torso_length, inseam, chest, waist, hip, neck, thigh, upper_arm, wrist, calf, ankle, bicep

**Key Design Decisions:**
- Measurements can be `Optional[float]` — returns `null` for low-confidence values
- `missing_measurements` list + `missing_reason` string in response
- Front image required, side image optional (weighted average 60/40 if both available)
- Circumference methods: ellipse fitting (primary), convex hull (fallback)
- Arm measurements use perpendicular slicing (not horizontal) since T-pose

**Dependencies:** `torch`, `smplx`, `mediapipe`, `opencv-python`, `scipy`, `trimesh`
**Git submodule:** `backend/libs/smpl_anthropometry/` (SMPL-Anthropometry library)

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

### 7. Merchant Dashboard API

#### Overview
Merchant-facing dashboard to show ROI and value metrics. Demonstrates decreased returns, increased conversions, and customer engagement.

**Access:** Embedded in Shopify admin using App Bridge

#### 7.1 Dashboard Overview
```http
GET /api/v1/merchant/dashboard
Headers:
  Authorization: Bearer <shopify_session_token>

Response 200:
{
  "overview": {
    "total_try_ons": 1247,
    "unique_users": 892,
    "total_products": 156,
    "products_with_try_on": 134
  },
  "period_stats": {
    "period": "last_30_days",
    "try_ons": 387,
    "try_ons_growth": "+23%",
    "add_to_carts": 156,
    "conversion_rate": 40.3,
    "conversion_growth": "+12%"
  },
  "roi_metrics": {
    "estimated_returns_prevented": 23,
    "estimated_savings": 1150.00,  // currency
    "average_cart_value_with_vto": 89.50,
    "average_cart_value_without_vto": 67.30,
    "lift": "+33%"
  },
  "top_products": [
    {
      "product_id": "uuid",
      "title": "Classic Denim Jacket",
      "try_ons": 89,
      "add_to_carts": 42,
      "conversion_rate": 47.2
    },
    // ... top 5 products
  ]
}
```

**ROI Calculation Logic:**

```python
class MerchantAnalyticsService:
    """
    Calculate merchant-facing analytics and ROI
    """
    
    def calculate_returns_prevented(self, store_id: str, period_days: int = 30):
        """
        Estimate returns prevented by virtual try-on
        
        Logic:
        1. Industry average return rate: 30-40% for apparel
        2. With proper sizing: Estimated 15-20% return rate
        3. Difference = Returns prevented
        """
        
        # Get orders with VTO in last 30 days
        vto_orders = db.query("""
            SELECT COUNT(*) as count, SUM(order_value) as revenue
            FROM orders
            WHERE store_id = :store_id
            AND created_at > NOW() - INTERVAL :days DAY
            AND order_properties LIKE '%_vto_session%'
        """, {"store_id": store_id, "days": period_days})
        
        # Industry baseline: 35% return rate
        baseline_return_rate = 0.35
        
        # VTO-enabled: Estimated 18% return rate (based on studies)
        vto_return_rate = 0.18
        
        # Calculate prevented returns
        prevented_rate = baseline_return_rate - vto_return_rate  # 17%
        estimated_returns_prevented = int(vto_orders.count * prevented_rate)
        
        # Calculate savings (assume average return costs $50)
        avg_return_cost = 50.0
        estimated_savings = estimated_returns_prevented * avg_return_cost
        
        return {
            "estimated_returns_prevented": estimated_returns_prevented,
            "estimated_savings": estimated_savings,
            "methodology": "Industry benchmark vs VTO-enabled orders"
        }
    
    def calculate_conversion_lift(self, store_id: str):
        """
        Compare conversion rates: with VTO vs without VTO
        """
        
        # Sessions with VTO that added to cart
        vto_sessions = db.query("""
            SELECT 
                COUNT(DISTINCT s.session_id) as total_sessions,
                COUNT(DISTINCT CASE WHEN s.added_to_cart THEN s.session_id END) as conversions
            FROM sessions s
            WHERE s.store_id = :store_id
            AND s.measurement_id IS NOT NULL
        """, {"store_id": store_id})
        
        vto_conversion = vto_sessions.conversions / vto_sessions.total_sessions
        
        # Overall store conversion rate (from Shopify)
        overall_conversion = get_store_conversion_rate(store_id)
        
        lift_percentage = ((vto_conversion - overall_conversion) / overall_conversion) * 100
        
        return {
            "vto_conversion_rate": vto_conversion * 100,
            "overall_conversion_rate": overall_conversion * 100,
            "lift": f"+{lift_percentage:.1f}%"
        }
```

#### 7.2 Analytics Breakdown
```http
GET /api/v1/merchant/analytics/breakdown
Headers:
  X-Store-ID: {store_uuid}
Query:
  period: "7d" | "30d" | "90d" | "all"
  metric: "try_ons" | "conversions" | "engagement"

Response 200:
{
  "period": "30d",
  "metric": "try_ons",
  "time_series": [
    {
      "date": "2026-02-01",
      "value": 23,
      "conversions": 12
    },
    // ... daily data points
  ],
  "breakdown_by_category": {
    "tops": 156,
    "bottoms": 89,
    "dresses": 67,
    "outerwear": 75
  },
  "breakdown_by_size": {
    "XS": 45,
    "S": 123,
    "M": 234,
    "L": 178,
    "XL": 67
  }
}
```

#### 7.3 Product Performance
```http
GET /api/v1/merchant/analytics/products
Headers:
  X-Store-ID: {store_uuid}
Query:
  sort_by: "try_ons" | "conversions" | "revenue"
  limit: 20

Response 200:
{
  "products": [
    {
      "product_id": "uuid",
      "title": "Classic Denim Jacket",
      "image_url": "...",
      "metrics": {
        "try_ons": 89,
        "unique_users": 73,
        "add_to_carts": 42,
        "conversion_rate": 47.2,
        "average_session_time": 124  // seconds
      },
      "size_distribution": {
        "S": 12,
        "M": 28,
        "L": 31,
        "XL": 18
      },
      "fit_feedback": {
        "perfect_fit": 34,
        "slightly_loose": 8,
        "slightly_tight": 3
      }
    }
  ],
  "total_count": 134
}
```

#### 7.4 User Engagement
```http
GET /api/v1/merchant/analytics/engagement
Headers:
  X-Store-ID: {store_uuid}

Response 200:
{
  "funnel": {
    "widget_opened": 1450,
    "photos_captured": 1120,  // 77% completion
    "measurements_completed": 1089,  // 97% of photos
    "try_on_generated": 1034,  // 95% of measurements
    "size_selected": 892,  // 86% of try-ons
    "added_to_cart": 387  // 43% of selections
  },
  "drop_off_points": [
    {
      "step": "photo_capture",
      "drop_off_rate": 23,
      "reason": "Camera permission denied or upload failed"
    },
    {
      "step": "try_on_view",
      "drop_off_rate": 14,
      "reason": "Did not proceed to add to cart"
    }
  ],
  "average_session_duration": 156,  // seconds
  "return_user_rate": 18.3  // % of users who tried on multiple products
}
```

#### 7.5 Settings
```http
GET /api/v1/merchant/settings
Headers:
  X-Store-ID: {store_uuid}

Response 200:
{
  "store_info": {
    "store_name": "Fashion Boutique",
    "shopify_domain": "fashion-boutique.myshopify.com",
    "installation_date": "2026-01-15T10:30:00Z",
    "status": "active"
  },
  "widget_settings": {
    "enabled": true,
    "button_text": "Try Me On",
    "button_color": "#000000",
    "placement": "below_add_to_cart"
  },
  "products_synced": 156,
  "last_sync": "2026-02-06T08:00:00Z",
  "next_sync": "2026-02-07T08:00:00Z"
}

PUT /api/v1/merchant/settings
Headers:
  X-Store-ID: {store_uuid}
Body:
{
  "widget_settings": {
    "enabled": true,
    "button_text": "Virtual Try-On",
    "button_color": "#FF5733"
  }
}

Response 200:
{
  "status": "updated",
  "settings": { /* updated settings */ }
}
```

#### 7.6 Manual Product Sync
```http
POST /api/v1/merchant/products/sync
Headers:
  X-Store-ID: {store_uuid}

Response 202:
{
  "status": "started",
  "job_id": "uuid",
  "estimated_time": 30  // seconds
}

GET /api/v1/merchant/products/sync/{job_id}

Response 200:
{
  "job_id": "uuid",
  "status": "completed",
  "products_synced": 156,
  "products_updated": 23,
  "products_added": 3,
  "completed_at": "2026-02-06T12:00:00Z"
}
```

---

### 8. Admin API

Internal endpoints for platform management. All routes require the `X-Admin-Key` header matching `ADMIN_API_KEY` in `.env`.

#### 8.1 Studio Background Management

**Authentication:**
```http
X-Admin-Key: <ADMIN_API_KEY>
```

##### Upload Studio Backgrounds (Bulk)
```http
POST /api/v1/admin/studio-backgrounds/upload
Content-Type: multipart/form-data
X-Admin-Key: <key>

Form fields:
  gender  string  "male" | "female" | "unisex"
  images  file[]  One or more image files (jpg/jpeg/png/webp)

Response 200:
{
  "uploaded": 3,
  "failed": 0,
  "backgrounds": [
    {
      "id": "uuid",
      "gender": "male",
      "image_path": "male/studio_1.jpg",
      "image_url": "/api/v1/tryon/studio-backgrounds/{id}/image",
      "file_size_kb": 142.3
    }
  ],
  "errors": []
}
```

**Behaviour:** Each image is written to `backend/static/studio/{gender}/` and a `StudioBackground` DB row is created atomically — disk and DB are always in sync.

**Filename conflict:** If a file with the same name already exists, a short UUID suffix is appended automatically.

##### List All Studio Backgrounds (Admin)
```http
GET /api/v1/admin/studio-backgrounds
X-Admin-Key: <key>

Response 200:
{
  "total": 8,
  "backgrounds": [
    {
      "id": "uuid",
      "gender": "male",
      "image_path": "male/studio_1.jpg",
      "is_active": true,
      "image_url": "/api/v1/tryon/studio-backgrounds/{id}/image",
      "file_exists": true,
      "created_at": "2026-02-21T10:00:00"
    }
  ]
}
```

Includes `file_exists` flag to surface any disk/DB mismatches.

##### Toggle Active State
```http
PATCH /api/v1/admin/studio-backgrounds/{id}/toggle
X-Admin-Key: <key>

Response 200:
{ "id": "uuid", "is_active": false }
```

##### Delete Background
```http
DELETE /api/v1/admin/studio-backgrounds/{id}?delete_file=true
X-Admin-Key: <key>

Response 200:
{
  "deleted": true,
  "id": "uuid",
  "image_path": "male/studio_1.jpg",
  "file_deleted": true
}
```

`delete_file=true` (default) removes the file from disk as well as the DB row.

#### 8.2 Workflow: Adding New Studio Backgrounds

```
1. Upload images locally (server running at localhost:8000):
   POST /api/v1/admin/studio-backgrounds/upload
   → files saved to backend/static/studio/{gender}/
   → DB rows created

2. Commit and push:
   git add backend/static/studio/
   git commit -m "feat: Add studio backgrounds"
   git push

3. Railway auto-redeploys → images live in production
```

> ⚠️ **Important:** Railway uses ephemeral containers. Images uploaded via the API on Railway (not locally) are lost on redeploy since they are not in the git repo. Always upload locally and commit.

#### 8.3 Future Admin Endpoints (Reserved, Not Yet Implemented)

```http
GET  /api/v1/admin/stores                    # All stores
GET  /api/v1/admin/stores/{id}/health        # Store health metrics
GET  /api/v1/admin/analytics/platform        # Platform-wide analytics
GET  /api/v1/admin/ml/performance            # Model performance monitoring
```

---

### 9. External Integrations

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

### 2. Google Vertex AI — Gemini 2.5 Flash

**Model:** `gemini-2.5-flash` (configurable via `TRYON_MODEL` env var — swap to any Vertex AI model without code changes)
**Library:** `google-cloud-aiplatform` Python SDK (`vertexai` namespace)
**Speed:** 30-60 seconds per image
**Auth:** Google Application Default Credentials (service account JSON key)

**Integration:**
```python
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig, Part

vertexai.init(project=settings.GOOGLE_CLOUD_PROJECT,
              location=settings.GOOGLE_CLOUD_LOCATION)
model = GenerativeModel(settings.TRYON_MODEL)

# Pass images directly as Parts — no file upload API required
response = model.generate_content(
    [
        Part.from_data(data=person_image_bytes, mime_type="image/jpeg"),
        Part.from_data(data=product_image_bytes, mime_type="image/jpeg"),
        prompt,
    ],
    generation_config=GenerationConfig(
        response_modalities=["IMAGE"],
    ),
)

# Extract generated image
result_image = response.candidates[0].content.parts[0].inline_data.data
```

**Error Handling:**
- Retry failed generations up to 2 times
- Timeout after 120 seconds (`TRYON_TIMEOUT` config)
- Cache successful results to avoid regeneration

**GCP Setup Required:**
1. Enable Vertex AI API in GCP console
2. Create service account with `Vertex AI User` role
3. Download JSON key → save as `backend/gcp-service-account.json`
4. Set `GOOGLE_APPLICATION_CREDENTIALS=gcp-service-account.json` in `.env`

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
| `external_api_error` | 502 | Google Vertex AI API failed | Yes |
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

# Google Vertex AI (Virtual Try-On)
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=gcp-service-account.json  # path to service account JSON key
TRYON_MODEL=gemini-2.5-flash-image         # must be a model that supports image output (response_modalities=IMAGE)
TRYON_TIMEOUT=120

# Admin API
ADMIN_API_KEY=<strong-random-secret>       # used for X-Admin-Key header on /api/v1/admin/* routes

# Security
CORS_ORIGINS=https://yourdomain.com,https://*.myshopify.com
ALLOWED_UPLOAD_EXTENSIONS=jpg,jpeg,png,webp

# Performance
MAX_UPLOAD_SIZE=10485760  # 10MB in bytes
IMAGE_CACHE_TTL=86400     # 24 hours (try-on results)
STUDIO_CACHE_TTL=3600     # 1 hour (studio look results, keyed by parent+background)
SESSION_TTL=86400          # 24 hours
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
- API costs (Google Vertex AI usage — Gemini 2.5 Flash pricing)

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

## Development Helper Scripts

One-off scripts in `backend/` for local setup and data maintenance. Never needed in production.

### `create_test_data.py`
Seeds the Railway DB with a test store and 4 test products (tops/bottoms/dresses/outerwear) with real garment image URLs. Also seeds placeholder studio backgrounds if the table is empty.

```bash
cd backend
python create_test_data.py
```

### `seed_studio_backgrounds.py`
Clears and re-seeds the `studio_backgrounds` table from the hardcoded list matching the files in `backend/static/studio/`. Use this if the DB and static folder get out of sync.

```bash
cd backend
python seed_studio_backgrounds.py
```

### `update_product_images.py`
Updates the `images` column on the 4 test products to use real Unsplash garment photo URLs (replacing the old `via.placeholder.com` placeholder). Run once if the test products were seeded before this fix.

```bash
cd backend
python update_product_images.py
```

---

---

## Merchant Onboarding & Billing — Backend Requirements

### Overview

When a merchant installs the app, they are taken through a 6-step onboarding wizard embedded in Shopify Admin. The FastAPI backend stores all onboarding responses, widget configuration, and billing state. The Remix merchant admin frontend calls these endpoints during onboarding.

---

### New Database Tables

#### `stores` — Additional Columns Required

```sql
ALTER TABLE stores ADD COLUMN onboarding_step VARCHAR(50) DEFAULT 'welcome';
-- Values: 'welcome', 'goals', 'referral', 'widget_scope', 'theme_setup', 'plan', 'complete'

ALTER TABLE stores ADD COLUMN onboarding_completed_at TIMESTAMP;
ALTER TABLE stores ADD COLUMN plan_name VARCHAR(50) DEFAULT 'free';
-- Values: 'free', 'starter'

ALTER TABLE stores ADD COLUMN plan_shopify_subscription_id VARCHAR(255);
-- Shopify GID of active AppSubscription (null for free plan)

ALTER TABLE stores ADD COLUMN plan_activated_at TIMESTAMP;
ALTER TABLE stores ADD COLUMN monthly_tryon_limit INTEGER DEFAULT 10;
-- Free: 10, Starter: 100
```

#### `merchant_onboarding` — New Table

Stores the merchant's answers from steps 2 and 3.

```sql
CREATE TABLE merchant_onboarding (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID REFERENCES stores(store_id) ON DELETE CASCADE UNIQUE,

    -- Step 2: Goals (checkboxes, multiple allowed)
    goals TEXT[],
    -- Example values: 'improve_conversion', 'reduce_returns',
    -- 'collect_emails', 'create_marketing_content', 'improve_ux'

    -- Step 3: Referral source (radio, single)
    referral_source VARCHAR(100),
    -- Example values: 'shopify_app_store', 'google', 'social_media',
    -- 'friend_colleague', 'influencer', 'other'
    referral_detail VARCHAR(255),  -- free text if 'other'

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `widget_configs` — New Table

Stores the merchant's widget placement and scope configuration from step 4.

```sql
CREATE TABLE widget_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID REFERENCES stores(store_id) ON DELETE CASCADE UNIQUE,

    -- Placement scope: what determines which products show the widget
    scope_type VARCHAR(20) DEFAULT 'all',
    -- Values: 'all', 'selected_collections', 'selected_products', 'mixed'

    -- Selected Shopify GID strings (e.g. "gid://shopify/Collection/123456")
    enabled_collection_ids TEXT[] DEFAULT '{}',
    enabled_product_ids    TEXT[] DEFAULT '{}',

    -- Theme extension status (updated in step 5)
    theme_extension_detected BOOLEAN DEFAULT FALSE,
    theme_id_checked VARCHAR(255),
    -- The Shopify theme GID where detection was last checked

    -- Button customization (future — not in onboarding yet)
    button_text VARCHAR(100) DEFAULT 'Try it on',

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

### New API Endpoints — Onboarding

All onboarding endpoints require the merchant's `store_id`. Authentication uses the same `X-Store-ID` header as other endpoints. In production with Remix, the store is identified via Shopify session token.

#### Get Onboarding State
```http
GET /api/v1/merchant/onboarding/status
Headers:
  X-Store-ID: {store_uuid}

Response 200:
{
  "store_id": "uuid",
  "onboarding_step": "goals",       // Current step merchant is on
  "onboarding_completed": false,
  "plan_name": "free",
  "goals": null,                     // null if not yet completed
  "referral_source": null,
  "widget_scope": null,
  "theme_extension_detected": false
}
```

#### Step 2: Save Goals
```http
POST /api/v1/merchant/onboarding/goals
Headers:
  X-Store-ID: {store_uuid}

Body:
{
  "goals": ["improve_conversion", "reduce_returns", "create_marketing_content"]
  // At least 1 required. Accepted values:
  // improve_conversion | reduce_returns | collect_emails |
  // create_marketing_content | improve_ux
}

Response 200:
{
  "saved": true,
  "next_step": "referral"
}
```

#### Step 3: Save Referral Source
```http
POST /api/v1/merchant/onboarding/referral
Headers:
  X-Store-ID: {store_uuid}

Body:
{
  "referral_source": "google",      // Required
  "referral_detail": null           // Required only if referral_source == "other"
  // Accepted values: shopify_app_store | google | social_media |
  // friend_colleague | influencer | other
}

Response 200:
{
  "saved": true,
  "next_step": "widget_scope"
}
```

#### Step 4: Save Widget Scope (Collections & Products)
```http
GET /api/v1/merchant/onboarding/widget-scope
Headers:
  X-Store-ID: {store_uuid}

Response 200:
{
  "scope_type": "all",
  "enabled_collection_ids": [],
  "enabled_product_ids": []
}

POST /api/v1/merchant/onboarding/widget-scope
Headers:
  X-Store-ID: {store_uuid}

Body:
{
  "scope_type": "mixed",  // "all" | "selected_collections" | "selected_products" | "mixed"
  "enabled_collection_ids": [
    "gid://shopify/Collection/123456",
    "gid://shopify/Collection/789012"
  ],
  "enabled_product_ids": [
    "gid://shopify/Product/555555"
  ]
}
// If scope_type == "all", both arrays should be empty.
// "mixed" allows a combination of collections AND individual products.

Response 200:
{
  "saved": true,
  "scope_type": "mixed",
  "enabled_collection_ids": ["gid://shopify/Collection/123456", ...],
  "enabled_product_ids": ["gid://shopify/Product/555555"],
  "next_step": "theme_setup"
}
```

#### Step 5: Check / Update Theme Extension Status
```http
GET /api/v1/merchant/onboarding/theme-status
Headers:
  X-Store-ID: {store_uuid}

Response 200:
{
  "theme_extension_detected": false,
  "theme_editor_url": "https://merchant.myshopify.com/admin/themes/123/editor?context=apps&template=product&activateAppId=..."
  // Deep link that opens Theme Editor with our widget block pre-selected
}

POST /api/v1/merchant/onboarding/theme-status
Headers:
  X-Store-ID: {store_uuid}

Body:
{
  "detected": true   // Merchant confirms they've added the block
}

Response 200:
{
  "saved": true,
  "theme_extension_detected": true,
  "next_step": "plan"
}
```

Note: The Remix frontend layer is also responsible for calling the Shopify Themes API to auto-detect if the block has been added to the published theme. The FastAPI endpoint stores the outcome.

#### Step 6: Complete Onboarding (Free Plan)
```http
POST /api/v1/merchant/onboarding/complete
Headers:
  X-Store-ID: {store_uuid}

Body:
{
  "plan": "free"
}

Response 200:
{
  "completed": true,
  "plan_name": "free",
  "monthly_tryon_limit": 10,
  "dashboard_url": "/app/dashboard"
}
```

---

### New API Endpoints — Billing

The Shopify Billing API is called from the **Remix server layer** (not directly from FastAPI), because it requires the Shopify Admin GraphQL client authenticated via session token. FastAPI receives the outcome after the Shopify billing flow completes.

#### Record Billing Activation (Called After Shopify Billing Callback)
```http
POST /api/v1/merchant/billing/activate
Headers:
  X-Store-ID: {store_uuid}

Body:
{
  "plan_name": "starter",
  "shopify_subscription_id": "gid://shopify/AppSubscription/12345",
  "status": "active"
}

Response 200:
{
  "activated": true,
  "plan_name": "starter",
  "monthly_tryon_limit": 100
}
```

#### Get Current Plan
```http
GET /api/v1/merchant/billing/plan
Headers:
  X-Store-ID: {store_uuid}

Response 200:
{
  "plan_name": "starter",
  "monthly_tryon_limit": 100,
  "tryon_count_this_month": 23,
  "plan_activated_at": "2026-02-21T10:00:00Z",
  "shopify_subscription_id": "gid://shopify/AppSubscription/12345"
}
```

---

### Plan Definitions

```python
PLANS = {
    "free": {
        "display_name": "Free",
        "price_usd": 0,
        "monthly_tryon_limit": 10,
        "features": [
            "10 monthly try-ons",
            "Virtual try-on widget",
            "Basic size recommendations",
            "Community support"
        ],
    },
    "starter": {
        "display_name": "Starter",
        "price_usd": 10.00,
        "monthly_tryon_limit": 100,
        "shopify_billing_name": "Virtual Try-On Starter",
        "features": [
            "100 monthly try-ons",
            "AI Studio Look backgrounds",
            "Fit heatmap visualization",
            "Analytics dashboard",
            "Email support"
        ],
    },
}
```

---

### Widget Scope — How It Affects the Storefront Widget

When the customer-facing widget loads on a product page, it must check if the widget is enabled for that product. The backend endpoint `POST /api/v1/sessions/create` (or a new lightweight check endpoint) should verify:

1. Look up `widget_configs` for the store
2. If `scope_type == "all"`: widget is enabled for all products → proceed normally
3. If `scope_type == "selected_collections"`: check if the product belongs to any enabled collection
4. If `scope_type == "selected_products"`: check if the product ID is in `enabled_product_ids`
5. If `scope_type == "mixed"`: check both collections and products

**New endpoint for this check:**

```http
GET /api/v1/widget/check-enabled?product_id={shopify_product_gid}
Headers:
  X-Store-ID: {store_uuid}

Response 200:
{
  "enabled": true
}

Response 200 (disabled for this product):
{
  "enabled": false
}
```

The storefront widget JS calls this on initialization. If `enabled: false`, the widget button is not injected.

---

### Onboarding State Machine

```
install → 'welcome' → 'goals' → 'referral' → 'widget_scope' → 'theme_setup' → 'plan' → 'complete'
```

- Each `POST /onboarding/{step}` advances `stores.onboarding_step` to the next value
- `GET /onboarding/status` always returns the current step so the Remix app can resume from where the merchant left off if they close the browser mid-onboarding
- Steps 4 and 5 have a "Skip for now" option — skipping still advances the step but leaves config at defaults (`scope_type: "all"`, `theme_extension_detected: false`)
- If the merchant reinstalls the app, `onboarding_step` is reset to `'welcome'`

---

## Merchant Settings — Custom Screen

**Added:** 2026-02-22

### Purpose
Merchant dashboard **Settings → Custom** sub-screen. Allows brand colour customisation for the storefront widget. The colour is stored per-store; the storefront widget reads it at runtime.

### Database Changes (migration `d4e5f6g7h8i9`)

| Change | Table | Column |
|--------|-------|--------|
| Drop | `widget_configs` | `button_text` — removed; button text is hardcoded on the widget |
| Add | `widget_configs` | `widget_color VARCHAR(7) NULL` — hex colour e.g. `#FF0000` |

**Default colour rule:** `widget_color` is `NULL` in the DB for new stores. The API layer returns `#FF0000` whenever the DB value is `NULL`. This keeps the default logic in code, not in the DB schema.

### Endpoints

#### `GET /api/v1/merchant/widget-config`
Returns the full widget configuration including colour. Used by the Custom screen on load.

```http
GET /api/v1/merchant/widget-config
Headers:
  X-Store-ID: {store_uuid}

Response 200:
{
  "scope_type": "all",
  "enabled_collection_ids": [],
  "enabled_product_ids": [],
  "theme_extension_detected": false,
  "widget_color": "#FF0000"
}
```

- If no `WidgetConfig` row exists for the store yet, defaults are returned (`scope_type: "all"`, `widget_color: "#FF0000"`).

#### `PATCH /api/v1/merchant/widget-config` (updated)
Partial update — accepts any subset of fields. Does **not** touch `onboarding_step`.

```http
PATCH /api/v1/merchant/widget-config
Headers:
  X-Store-ID: {store_uuid}
Content-Type: application/json

Body (all fields optional):
{
  "widget_color": "#3B82F6"
}

Response 200:
{
  "scope_type": "all",
  "enabled_collection_ids": [],
  "enabled_product_ids": [],
  "theme_extension_detected": false,
  "widget_color": "#3B82F6"
}
```

- `widget_color` must be a 7-character hex string including `#` (e.g. `"#FF0000"`). Validation is done on the frontend; the backend stores whatever string is sent.
- Response always includes `widget_color`; if the DB value is still `NULL` after a partial update that didn't include `widget_color`, the API returns `"#FF0000"`.

### Updated `WidgetConfigResponse` Schema

```python
class WidgetConfigResponse(BaseModel):
    scope_type: str
    enabled_collection_ids: List[str]
    enabled_product_ids: List[str]
    theme_extension_detected: bool
    widget_color: str   # '#FF0000' default applied in API layer
```

### Cancel / Revert Behaviour
The frontend holds the last-saved state from the GET response. On Cancel, it resets local state to that snapshot — no API call required.

---

## Segment 11 — Billing Module Overhaul

**Added:** 2026-03-02

### Overview
Replaces the hardcoded PLAN_CONFIGS dict with a DB-backed `plans` table. Introduces monthly/annual billing toggle, 17% annual discount, 14-day free trial, and credits as the primary usage metric (1 try-on = 4 credits).

### Plan Catalog

| Plan | Monthly | Annual (billed) | Annual (display/mo) | Discount | Credits/mo | Credits/yr | Trial |
|---|---|---|---|---|---|---|---|
| Starter | $17/mo | $179/yr | $14/mo | 17% | 600 | 7,600 | 14 days / 80 credits |
| Growth | $29/mo | $299/yr | $24/mo | 17% | 1,000 | 12,800 | 14 days / 80 credits |

Free plan: legacy only. New merchants must subscribe to Starter or Growth (both include a mandatory 14-day trial). Founding merchants (first 50 by default) get `plan_name="founding_trial"` with 300 credits for 14 days at no charge, skipping the billing step.

### Database Changes (migration `20260302_billing_plans.py`, revision `g7h8i9j0k1l2`)

#### New `plans` table
All plan config lives in DB — editable without code deploys.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | String(50) UNIQUE | `"starter"` \| `"growth"` |
| display_name | String(100) | `"Starter"` |
| price_monthly | Numeric(8,2) | `17.00` |
| price_annual_total | Numeric(8,2) | `179.00` — Shopify charge amount |
| price_annual_per_month | Numeric(8,2) | `14.00` — display only |
| annual_discount_pct | Integer | `17` |
| credits_monthly | Integer | `600` |
| credits_annual | Integer | `7600` — full yearly total |
| trial_days | Integer nullable | `14` |
| trial_credits | Integer nullable | `80` |
| features | JSONB | List of feature strings |
| is_active | Boolean | soft-disable without delete |
| sort_order | Integer | display order |

#### `stores` table alterations (migration `20260302_billing_plans.py`)
- `monthly_tryon_limit` renamed → `credits_limit` (Integer, default 0 for free)
- `billing_interval` VARCHAR(10) added — `"monthly"` \| `"annual"` \| null (free)
- `trial_ends_at` TIMESTAMP added — null unless on trial

#### `stores` table alterations (migration `20260302_founding_merchant.py`, revision `h8i9j0k1l2m3`)
- `is_founding_merchant` BOOLEAN NOT NULL DEFAULT FALSE — persists even after upgrade to paid plan

### Shopify Billing Flow

```
Monthly upgrade:
  Remix → POST /billing/create-subscription { plan_name, billing_interval: "monthly", return_url }
       <- { confirmation_url }
  Remix redirect -> Shopify approval page (EVERY_30_DAYS, trialDays: 14)
  Merchant approves
  Shopify -> returnUrl callback
  Remix -> POST /billing/activate { plan_name, billing_interval, shopify_subscription_id, status }
        <- { plan_name, credits_limit, ... }

Annual upgrade:
  Same flow but interval: "annual" -> Shopify ANNUAL, price = price_annual_total

Cancel / downgrade:
  Remix -> POST /billing/cancel-subscription
       <- { cancelled: true, plan_name: "free", credits_limit: 0 }
```

#### Founding Merchant Flow (first FOUNDING_MERCHANT_LIMIT installs)
`POST /onboarding/theme-status` counts `is_founding_merchant=true` stores.
- If count < limit: auto-completes the store with `plan_name="founding_trial"`, `credits_limit=300`, `trial_ends_at=now+14d`, `is_founding_merchant=true`, `onboarding_step="complete"`. Returns `next_step="complete"` — billing step skipped entirely.
- After 14 days: `GET /widget/check-enabled` returns `enabled=false`. Frontend redirects to billing screen (same Starter/Growth screen as regular merchants).

### ShopifyService update (billing_create_subscription)
Signature: `billing_create_subscription(plan_name, price_usd, return_url, billing_interval="monthly", trial_days=0, test=False, is_upgrade=False)`
- `"monthly"` -> Shopify `EVERY_30_DAYS`
- `"annual"` -> Shopify `ANNUAL`
- `trial_days > 0` -> adds `trialDays` to GraphQL variables

### Admin Plan Management Endpoints
Protected by `X-Admin-Key` header.

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/admin/plans` | List all plans with `store_count` |
| POST | `/api/v1/admin/plans` | Create new plan |
| PATCH | `/api/v1/admin/plans/{id}` | Partial update any field |
| PATCH | `/api/v1/admin/plans/{id}/toggle` | Toggle `is_active` |
| DELETE | `/api/v1/admin/plans/{id}` | Delete (422 if stores subscribed) |

### Merchant Billing Endpoints

**Auth:** All `/merchant/billing/*` endpoints require `Authorization: Bearer <shopify_session_token>` (App Bridge JWT). Shop identity is derived from the token — no `X-Store-ID` header needed.

#### GET /api/v1/merchant/billing/plans -> PlansResponse
Queries active plans from DB ordered by `sort_order`. Marks `is_current` by `store.plan_name`.

#### POST /api/v1/merchant/billing/create-subscription
```json
{
  "plan_name": "starter",
  "billing_interval": "annual",
  "return_url": "https://myapp.myshopify.com/app/billing/callback"
}
```
Response: `{ "confirmation_url": "...", "shopify_subscription_id": "gid://..." }`
Errors: 422 unknown/inactive plan, 409 already on same plan+interval, 502 Shopify error.

#### POST /api/v1/merchant/billing/activate
Sets `credits_limit = plan.trial_credits` (80 during trial), `billing_interval`, and `trial_ends_at = now + 14d`. After trial expiry, `GET /billing/status` auto-upgrades `credits_limit` to full plan credits.

#### GET /api/v1/merchant/billing/status -> BillingStatusResponse
Returns `plan_name`, `billing_interval`, `credits_limit`, `trial_ends_at`, `plan_activated_at`, `shopify_subscription_id`, plus live Shopify fields.

#### POST /api/v1/merchant/billing/cancel-subscription
Resets: `credits_limit=0`, `billing_interval=null`, `trial_ends_at=null`, `plan_name="free"`, clears subscription ID.
Response: `{ "cancelled": true, "plan_name": "free", "credits_limit": 0 }`

#### GET /api/v1/merchant/billing/plan
Quick DB-only plan lookup. Returns `plan_name`, `credits_limit`, `plan_activated_at`, `shopify_subscription_id`.

### Dashboard
`GET /api/v1/merchant/dashboard/overview` field renamed: `monthly_tryon_limit` -> `credits_limit`.

### Payment method & Invoices
No Shopify API exists for these. Both link to `https://{store.shopify_domain}/admin/settings/billing`.


## Segment 10 — AI Photoshoot (Merchant-Facing)

**Purpose:** Allow merchants to generate professional product imagery using AI directly from the Shopify admin dashboard. Three features share a common backend pattern.

### AI Provider
Google Vertex AI (Gemini) — same model already used for customer try-ons (`TRYON_MODEL`). No new API credentials needed.

### New Scope Required
`write_products` added to `SHOPIFY_SCOPES`. Merchants who installed before this segment must reinstall/reauthorize to grant this scope (needed for `productCreateMedia`).

### New Config Variable
`PUBLIC_URL` (env var) — base URL of this backend, e.g. `https://your-app.railway.app`. Used to construct the result image URL that Shopify fetches during approval. Defaults to `http://localhost:8000` for dev.

---

### Database

#### `photoshoot_models`
Pre-defined model photos served from `backend/static/photoshoot/{gender}/`.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| gender | String(10) | "male" / "female" / "unisex" |
| image_path | String(300) | Relative path e.g. "female/model_1.jpg" |
| is_active | Boolean | Soft-delete |
| created_at / updated_at | DateTime | |

#### `photoshoot_jobs`
One record per generation job. Status lifecycle: `queued → processing → completed / failed`.

| Column | Type | Notes |
|---|---|---|
| job_id | UUID PK | |
| store_id | UUID FK → stores | CASCADE delete |
| job_type | String(20) | "ghost_mannequin" / "try_on_model" / "model_swap" |
| shopify_product_gid | String(255) | Full Shopify GID for the approve step |
| processing_status | String(20) | queued / processing / completed / failed |
| result_cache_key | String(200) | Redis key: `photoshoot:{job_id}` |
| processing_time_seconds | Float | |
| error_message | Text | Populated on failure |
| completed_at | DateTime | |
| approved_at | DateTime | Set when merchant pushes to Shopify |
| shopify_media_id | String(255) | GID returned by productCreateMedia |

**Redis cache:** `photoshoot:{job_id}` — 24h TTL (same as customer try-on). Image served from `GET /jobs/{job_id}/result`, which Shopify fetches immediately on approve.

**Alembic migration:** `20260222_add_photoshoot.py` (revision `e5f6g7h8i9j0`)

---

### Features

#### 1. Ghost Mannequin
Input: 2 product image URLs from the same Shopify product (any angles — front, back, flat-lay, worn).
AI: Gemini composites both images into a 3D hollow invisible-mannequin product photo on white/grey background.
No specific front+back requirement — merchant picks any 2 images from the product's gallery.

#### 2. Try-On for Model
Input: 1 product image URL (Shopify CDN) + 1 model photo (from built-in library OR merchant upload).
AI: Gemini places the product garment on the selected model, preserving model appearance and garment details.

#### 3. Model Swap
Input: 1 image of original model wearing the product (Shopify CDN) + 1 new model photo (library OR upload).
AI: Gemini replaces the original model with the new model while keeping the garment identical.

---

### Endpoints

**Router prefix:** `/api/v1/merchant/photoshoot`
**Auth:** All endpoints (except `GET /models/{id}/image` and `GET /jobs/{id}/result`) require `Authorization: Bearer <shopify_session_token>` (App Bridge JWT). Image-serving endpoints are public so Shopify CDN can fetch them.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/models` | App Bridge JWT | List built-in model photos (filter by `?gender=`) |
| GET | `/models/{id}/image` | None | Serve model photo bytes |
| POST | `/ghost-mannequin` | App Bridge JWT | Start ghost mannequin job (JSON) → 202 |
| POST | `/try-on-model` | App Bridge JWT | Start try-on job (multipart) → 202 |
| POST | `/model-swap` | App Bridge JWT | Start model swap job (multipart) → 202 |
| GET | `/jobs/{job_id}/status` | App Bridge JWT | Poll job status |
| GET | `/jobs/{job_id}/result` | None | Serve result image bytes (for preview + Shopify) |
| POST | `/jobs/{job_id}/approve` | App Bridge JWT | Push result image to Shopify product |

#### `POST /ghost-mannequin` — JSON body
```json
{
  "image1_url": "https://cdn.shopify.com/...",
  "image2_url": "https://cdn.shopify.com/...",
  "shopify_product_gid": "gid://shopify/Product/123456"
}
```

#### `POST /try-on-model` — multipart/form-data
```
shopify_product_gid  (string, required)
product_image_url    (string, required)
library_id           (string, optional UUID — mutually exclusive with photo_upload)
photo_upload         (file, optional — mutually exclusive with library_id)
```

#### `POST /model-swap` — multipart/form-data
```
shopify_product_gid    (string, required)
original_image_url     (string, required — model wearing product)
new_model_library_id   (string, optional UUID — mutually exclusive with new_model_image)
new_model_image        (file, optional — mutually exclusive with new_model_library_id)
```

#### `GET /jobs/{job_id}/status` → `PhotoshootJobResponse`
```json
{
  "job_id": "uuid",
  "job_type": "ghost_mannequin",
  "status": "completed",
  "progress": 100,
  "message": "Image ready",
  "result_image_url": "/api/v1/merchant/photoshoot/jobs/{job_id}/result",
  "processing_time_seconds": 38.2,
  "error": null,
  "retry_allowed": false
}
```

#### `POST /jobs/{job_id}/approve` — JSON body
```json
{ "alt_text": "Ghost mannequin view of Blue Linen Shirt" }
```
Response:
```json
{
  "approved": true,
  "shopify_media_id": "gid://shopify/MediaImage/987654",
  "message": "Image pushed to Shopify product. It will appear in the product gallery within seconds."
}
```

---

### Approve Flow (Shopify image upload)

1. Merchant clicks Approve in the Remix UI
2. Remix calls `POST /jobs/{job_id}/approve`
3. Backend verifies image is in Redis (409 if expired, telling merchant to regenerate)
4. Backend builds public URL: `{PUBLIC_URL}/api/v1/merchant/photoshoot/jobs/{job_id}/result`
5. Backend calls `ShopifyService.add_product_image(shopify_product_gid, public_url, alt_text)`
6. Shopify fetches the image from the public URL **immediately** and re-hosts it on its CDN
7. Backend marks job `approved_at` and stores `shopify_media_id`
8. Image appears in Shopify product gallery within seconds

Note: `GET /jobs/{job_id}/result` has **no auth** so Shopify can fetch without credentials.

---

### Model Library Management
Model photos are managed via the Admin API (no UI needed):

```bash
# Upload full-body model photos (served for both customer studio look + merchant try-on)
curl -X POST /api/v1/admin/model-photos/upload \
  -H "X-Admin-Key: <key>" \
  -F "gender=female" -F "age=26-35" -F "body_type=slim" \
  -F "images=@model1.jpg" -F "images=@model2.jpg"

# Upload face/headshot photos (for model swap)
curl -X POST /api/v1/admin/model-faces/upload \
  -H "X-Admin-Key: <key>" \
  -F "gender=female" -F "age=26-35" -F "skin_tone=medium" \
  -F "images=@face1.jpg"

# Upload ghost mannequin reference images (12 total: 4 types × 3 poses)
curl -X POST /api/v1/admin/ghost-mannequin-refs/upload \
  -H "X-Admin-Key: <key>" \
  -F "clothing_type=tops" -F "pose=front" -F "image=@tops_front.jpg"
```

Files are saved to `backend/static/` and committed to git for deployment.

---

### Unified Model Photo Architecture

`studio_backgrounds` and `photoshoot_models` were merged into one table (`photoshoot_models`) because they store the same type of image (full-body person photos). The customer studio look and merchant AI photoshoot both draw from the same pool.

| Use case | Endpoint | Filter |
|---|---|---|
| Customer studio look | `GET /tryon/studio-backgrounds?gender=` | gender only |
| Merchant try-on-model | `GET /merchant/photoshoot/models?gender=&age=&body_type=` | gender + age + body_type |

All `image_path` values in `photoshoot_models` are relative to `backend/static/` (e.g. `"photoshoot/female/model_1.jpg"`). New uploads go to `static/photoshoot/{gender}/`.

---

### Static Directory Structure

```
backend/static/
├── photoshoot/            ← full-body model photos (paths: "photoshoot/female/…")
│   ├── female/, male/, unisex/
├── photoshoot_faces/      ← face/headshot photos for model swap (paths: "photoshoot_faces/female/…")
│   ├── female/, male/
└── ghost_mannequin/       ← reference pose images (paths: "ghost_mannequin/tops/front.jpg")
    ├── tops/, bottoms/, dresses/, outerwear/
```

---

### New / Updated Services & Files

| File | Change |
|---|---|
| `backend/app/api/v1/photoshoot.py` | Updated: 12 endpoints total (+4 face & ghost-ref endpoints; model-swap reworked to face-only) |
| `backend/app/api/v1/admin.py` | Replaced studio admin with unified model-photos admin; added model-faces + ghost-mannequin-refs admin |
| `backend/app/api/v1/tryon.py` | Updated studio-background endpoints to query `photoshoot_models` |
| `backend/app/services/photoshoot_service.py` | `generate_ghost_mannequin` adds `clothing_type` hint; `generate_model_swap` updated to face-only prompt |
| `backend/app/models/database.py` | `PhotoshootModel` + `age`/`body_type`; added `PhotoshootModelFace`, `GhostMannequinRef`; removed `StudioBackground` |
| `backend/app/models/schemas.py` | Added `PhotoshootModelFaceResponse`, `GhostMannequinRefResponse`; updated `GhostMannequinRequest` (+`clothing_type`) |
| `backend/alembic/versions/20260222_extend_photoshoot.py` | Migration: merge studio_backgrounds → photoshoot_models; create photoshoot_model_faces + ghost_mannequin_refs |

---

## Segment 12 — Standard Analytics

### Overview

Adds the Standard analytics sub-tab to the merchant dashboard.
Provides engagement metrics, conversion data (cross-referenced with Shopify Orders), and a daily try-on trend line chart.

### Conversion Attribution Model

The widget flow ends at `added_to_cart`. The widget cannot reliably fire a checkout event (that happens on Shopify's hosted checkout page). Conversions are computed by cross-referencing `added_to_cart` events (those that carry a `customer_id` in `event_data`) against the Shopify Orders REST API. An order is considered a conversion if the order's `customer.id` matches a `customer_id` from our cart events within the look-back period.

### Valid Event Types

Only these 8 funnel event types are accepted for ingestion:

| Event | Funnel stage |
|---|---|
| `widget_opened` | Top of funnel |
| `photo_captured` | User took a photo |
| `measurement_completed` | Body measurements extracted |
| `size_recommended` | Size recommendation shown |
| `try_on_generated` | Virtual try-on generated |
| `try_on_viewed` | Try-on result viewed |
| `size_selected` | User selected a size |
| `added_to_cart` | Bottom of our funnel |

`checkout_completed` is not in scope (not reliably fireable from widget context). Future: Shopify App Pixels or Order Webhooks could surface this.

### New File: `backend/app/api/v1/analytics.py`

Two routers:

```
analytics_public_router   → prefix /analytics    (widget-facing)
analytics_merchant_router → prefix /merchant/analytics  (merchant auth)
```

#### POST /api/v1/analytics/events

Widget-facing event ingestion. Requires `X-Store-ID` header.

**Request body:**
```json
{
  "event_type": "widget_opened",
  "session_id": "uuid (optional)",
  "event_data": {
    "product_id": "gid://shopify/Product/123",
    "anonymous_id": "fp_abc"
  }
}
```

**Response:** `{ "saved": true }`

Returns 422 if `event_type` is not in the valid set.

#### GET /api/v1/merchant/analytics/standard

Merchant dashboard analytics. Requires `Authorization: Bearer <shopify_session_token>` (App Bridge JWT).

**Query param:** `period` — look-back window in days. Accepted values: `7`, `30` (default), `90`.

**Response (`StandardAnalyticsResponse`):**

| Field | Source | Notes |
|---|---|---|
| `period_days` | Query param | 7 / 30 / 90 |
| `period_start` / `period_end` | Computed | UTC datetimes |
| `widget_opens` | `analytics_events` WHERE `event_type=widget_opened` | — |
| `unique_users` | COUNT DISTINCT `session_id` on widget_opened events | — |
| `total_try_ons` | `try_ons` WHERE `status=completed` + product join | — |
| `credits_used` | `total_try_ons × 4` | 1 try-on = 4 credits |
| `add_to_cart_count` | `analytics_events` WHERE `event_type=added_to_cart` | — |
| `conversions` | Shopify Orders cross-ref | null if Shopify call fails |
| `conversion_rate` | `conversions / widget_opens × 100` | null if widget_opens==0 or Shopify fails |
| `revenue_impact` | SUM(`total_price`) for matched orders | null if Shopify fails |
| `return_count` | Orders with at least one refund | null if Shopify fails |
| `top_products` | Merged try-on + cart counts, sorted by `conversion_rate` DESC, limit 5 | `[]` if no data |
| `trend` | Per-calendar-day try-on count for the period | 0-filled for days with no data |

### New Shopify Service Method

`ShopifyService.get_orders_with_refunds(since, customer_ids?)` added to `backend/app/services/shopify_service.py`:

- Calls `GET /admin/api/2024-01/orders.json?status=any&created_at_min=...&limit=250&fields=id,customer,total_price,refunds,created_at`
- Paginates via `Link` header
- Filters by `customer_ids` client-side if provided
- Returns `{ "orders": [...], "return_count": int }`

### Schema Changes (`backend/app/models/schemas.py`)

Added `session_id` field to existing `AnalyticsEventCreate`.

New schemas added:
- `AnalyticsEventSaved` — `{ saved: bool }`
- `TopProductEntry` — `shopify_product_id`, `title`, `try_on_count`, `cart_count`, `conversion_rate`
- `TrendEntry` — `date` (ISO string), `try_ons` (int)
- `StandardAnalyticsResponse` — all fields listed in the table above

### `backend/app/main.py` Changes

```python
from app.api.v1 import ... analytics
app.include_router(analytics.analytics_public_router, prefix="/api/v1")
app.include_router(analytics.analytics_merchant_router, prefix="/api/v1")
```

### Verification Checklist

1. `POST /analytics/events` with `event_type="widget_opened"` → 200 `{ "saved": true }`
2. `POST /analytics/events` with `event_type="checkout_completed"` → 422
3. `POST /analytics/events` with unknown event type → 422
4. `GET /merchant/analytics/standard` → DB metrics populated; Shopify fields null if no subscription
5. `GET /merchant/analytics/standard?period=7` → `trend` has 7 entries
6. `GET /merchant/analytics/standard?period=90` → `trend` has 90 entries
7. No events in DB → all zeros, Shopify fields null, `top_products` empty, trend all zeros
8. Shopify API error → `conversions`, `revenue_impact`, `return_count` are null; rest of response intact
9. `top_products` sorted by `conversion_rate` DESC
10. `trend` dates are contiguous, ascending, `period_days` entries total

---

**End of Backend PRD**
