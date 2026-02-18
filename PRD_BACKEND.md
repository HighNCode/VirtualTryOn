# Virtual Try-On Shopify App - Backend PRD

**Version:** 1.1
**Last Updated:** 2026-02-17
**Tech Stack:** Python FastAPI, PostgreSQL, Redis, MediaPipe, SMPL, Google Gemini
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
Image AI:       Google Gemini API (direct, no Replicate)
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
    │          │      │ (Cache)  │      │ Gemini   │
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
│   │   ├── tryon_service.py    # Virtual try-on via Google Gemini API
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
All API calls (except OAuth) require:
```
Headers:
  X-Store-ID: {store_uuid}
  X-Session-ID: {session_uuid}  # For customer requests
```

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

4. **Call Google Gemini API directly** (not via Replicate)
   ```python
   import google.generativeai as genai

   genai.configure(api_key=settings.GOOGLE_API_KEY)
   model = genai.GenerativeModel(settings.GEMINI_MODEL)

   # Upload images to Gemini File API
   person_file = genai.upload_file(person_image_path)
   product_file = genai.upload_file(product_image_path)

   # Generate with image output
   response = model.generate_content(
       [prompt, person_file, product_file],
       generation_config=genai.GenerationConfig(
           response_mime_type="image/png",
       ),
   )

   # Extract generated image
   result_image = response.parts[0].inline_data.data
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

Response 202:
{
  "try_on_id": "new-uuid",
  "status": "processing",
  "estimated_time_seconds": 45
}
```

Uses the same `GET /status` and `GET /image` endpoints for polling and serving.

**Studio Generation Pipeline:**
1. Retrieve original try-on image from Redis cache
2. Read studio background from static file
3. Send both to Gemini with prompt: "Place the person into the environment. Keep appearance, clothing, pose the same. Only change background and lighting."
4. Cache result, update DB record with `parent_try_on_id` and `studio_background_id`

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
  X-Store-ID: {store_uuid}

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

### 8. Admin Dashboard API (Future - Not Implemented in MVP)

**Provision for Super Admin Dashboard**

Reserved endpoints for platform-level admin:

```http
# View all stores
GET /api/v1/admin/stores
Authorization: Bearer {admin_token}

# Store health metrics
GET /api/v1/admin/stores/{store_id}/health

# Platform-wide analytics
GET /api/v1/admin/analytics/platform

# Feature flags
GET /api/v1/admin/features
PUT /api/v1/admin/features/{feature_id}

# Model performance monitoring
GET /api/v1/admin/ml/performance
```

**Not implemented in MVP but database schema supports:**
- Admin users table
- Feature flags table
- Platform-wide analytics aggregation
- A/B testing framework

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

### 2. Google Gemini API (Direct)

**Model:** `gemini-2.0-flash-exp` (configurable via `GEMINI_MODEL` env var)
**Library:** `google-generativeai` Python SDK
**Speed:** 30-60 seconds per image

**Integration:**
```python
import google.generativeai as genai

genai.configure(api_key=settings.GOOGLE_API_KEY)
model = genai.GenerativeModel(settings.GEMINI_MODEL)

# Upload person + product images via File API
person_file = genai.upload_file(person_image_path)
product_file = genai.upload_file(product_image_path)

# Generate try-on image directly
response = model.generate_content(
    [prompt, person_file, product_file],
    generation_config=genai.GenerationConfig(
        response_mime_type="image/png",
    ),
)

result_image = response.parts[0].inline_data.data

# Cleanup uploaded files
genai.delete_file(person_file.name)
genai.delete_file(product_file.name)
```

**Error Handling:**
- Retry failed generations up to 2 times
- Timeout after 120 seconds (`TRYON_TIMEOUT` config)
- Cache successful results to avoid regeneration
- Cleanup uploaded files after generation

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
| `external_api_error` | 502 | Google Gemini API failed | Yes |
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

# Google Gemini (Virtual Try-On)
GOOGLE_API_KEY=<from-google-ai-studio>
GEMINI_MODEL=gemini-2.0-flash-exp
TRYON_TIMEOUT=120

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
- API costs (Google Gemini usage)

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
