"""
Shopify API Integration Service
Handles product sync, webhooks, and Shopify GraphQL API calls
"""

import httpx
import logging
import base64
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.models.database import Store, Product, SizeChart
from sqlalchemy.orm import Session

settings = get_settings()
logger = logging.getLogger(__name__)


class ShopifyManagedPricingError(Exception):
    """Raised when Shopify rejects Billing API charge creation for managed-pricing apps."""


class ShopifyBillingUserErrors(Exception):
    """Raised when Shopify Billing API returns userErrors for subscription creation."""

    def __init__(self, *, billing_interval: str, errors: List[Dict[str, Any]]):
        self.billing_interval = billing_interval
        self.errors = errors or []

        messages: List[str] = []
        for entry in self.errors:
            message = str((entry or {}).get("message", "")).strip()
            if message:
                messages.append(message)

        self.message = "; ".join(messages) if messages else "Shopify rejected the billing payload."
        super().__init__(self.message)


class ShopifyService:
    """Service for interacting with Shopify API"""
    ORDERS_LOOKBACK_LIMIT_DAYS = 60

    def __init__(self, shop_domain: str, access_token: str):
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.api_version = settings.SHOPIFY_API_VERSION
        self.graphql_url = f"https://{shop_domain}/admin/api/{self.api_version}/graphql.json"
        self.rest_url = f"https://{shop_domain}/admin/api/{self.api_version}"

    async def _graphql_request(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """
        Make a GraphQL request to Shopify

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            Response data
        """
        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.graphql_url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                logger.error(f"GraphQL errors: {result['errors']}")
                raise Exception(f"GraphQL error: {result['errors']}")

            return result

    async def _rest_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a REST GET request to Shopify Admin API.
        """
        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }
        url = f"{self.rest_url}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()

    async def get_active_theme_id(self) -> Optional[str]:
        """
        Resolve the currently active storefront theme ID.
        """
        payload = await self._rest_get("themes.json", params={"fields": "id,role"})
        themes = payload.get("themes", []) or []

        active_theme = next((item for item in themes if str(item.get("role", "")).lower() == "main"), None)
        if active_theme is None and themes:
            active_theme = themes[0]

        if not active_theme:
            return None
        theme_id = active_theme.get("id")
        return str(theme_id) if theme_id is not None else None

    async def list_theme_asset_keys(self, *, theme_id: str) -> List[str]:
        """
        List asset keys for a theme.
        """
        payload = await self._rest_get(
            f"themes/{theme_id}/assets.json",
            params={"fields": "key"},
        )
        assets = payload.get("assets", []) or []
        keys: List[str] = []
        for item in assets:
            key = str((item or {}).get("key") or "").strip()
            if key:
                keys.append(key)
        return keys

    async def get_theme_asset_value(self, *, theme_id: str, asset_key: str) -> str:
        """
        Fetch and decode a specific theme asset content.
        """
        payload = await self._rest_get(
            f"themes/{theme_id}/assets.json",
            params={"asset[key]": asset_key},
        )
        asset = payload.get("asset", {}) or {}
        value = asset.get("value")
        if isinstance(value, str):
            return value

        attachment = asset.get("attachment")
        if isinstance(attachment, str) and attachment:
            try:
                decoded = base64.b64decode(attachment).decode("utf-8", errors="ignore")
                return decoded
            except Exception:
                return ""
        return ""

    async def detect_optimo_theme_block(self) -> bool:
        """
        Detect whether the Optimo theme app block appears in active theme assets.
        """
        theme_id = await self.get_active_theme_id()
        if not theme_id:
            return False

        keys = await self.list_theme_asset_keys(theme_id=theme_id)
        if not keys:
            return False

        candidates: List[str] = []
        seen: set[str] = set()

        def _add_candidate(key: str) -> None:
            normalized = key.strip()
            if not normalized or normalized in seen:
                return
            seen.add(normalized)
            candidates.append(normalized)

        for key in keys:
            lower = key.lower()
            if lower == "config/settings_data.json":
                _add_candidate(key)
                continue
            if lower.startswith("templates/") and lower.endswith(".json") and "product" in lower:
                _add_candidate(key)
                continue
            if lower in {
                "sections/main-product.liquid",
                "sections/main-product.json",
                "sections/product-template.liquid",
                "sections/product.json",
            }:
                _add_candidate(key)

        markers = [
            "optimo_vts_widget",
            "optimo-vts-widget",
            "apps/optimo-vts",
        ]

        for asset_key in candidates:
            try:
                content = await self.get_theme_asset_value(theme_id=theme_id, asset_key=asset_key)
            except Exception as exc:
                logger.warning("Failed to read theme asset %s/%s: %s", theme_id, asset_key, exc)
                continue

            haystack = content.lower()
            if any(marker in haystack for marker in markers):
                return True

        return False

    async def sync_all_products(self, db: Session, store_id: str) -> Dict:
        """
        Sync all products from Shopify to database

        Args:
            db: Database session
            store_id: Store UUID

        Returns:
            Sync statistics
        """
        logger.info(f"Starting product sync for store: {store_id}")

        cursor = None
        products_synced = 0
        products_with_sizes = 0

        while True:
            # Build GraphQL query
            query = self._build_products_query(cursor)

            # Execute query
            response = await self._graphql_request(query)

            # Extract products
            products_data = response.get('data', {}).get('products', {})
            edges = products_data.get('edges', [])
            page_info = products_data.get('pageInfo', {})

            # Process each product
            for edge in edges:
                product_node = edge['node']
                product_data = self._extract_product_data(product_node)

                # Save or update product
                product = await self._save_product(db, store_id, product_data)
                products_synced += 1

                # Extract and save size chart if available
                size_chart = self._extract_size_chart(product_node)
                if size_chart:
                    await self._save_size_chart(db, product.product_id, size_chart)
                    products_with_sizes += 1

            # Check if more pages
            if not page_info.get('hasNextPage', False):
                break

            cursor = page_info.get('endCursor')

        db.commit()
        logger.info(f"Product sync completed: {products_synced} products synced")

        return {
            'products_synced': products_synced,
            'products_with_sizes': products_with_sizes,
            'products_without_sizes': products_synced - products_with_sizes,
            'timestamp': datetime.utcnow()
        }

    def _build_products_query(self, cursor: Optional[str] = None) -> str:
        """Build GraphQL query for fetching products"""
        after_clause = f', after: "{cursor}"' if cursor else ''

        return f"""
        query {{
          products(first: 50{after_clause}) {{
            pageInfo {{
              hasNextPage
              endCursor
            }}
            edges {{
              node {{
                id
                title
                descriptionHtml
                productType
                vendor
                tags
                images(first: 5) {{
                  edges {{
                    node {{
                      id
                      src
                      altText
                    }}
                  }}
                }}
                variants(first: 100) {{
                  edges {{
                    node {{
                      id
                      title
                      sku
                      price
                      availableForSale
                      selectedOptions {{
                        name
                        value
                      }}
                    }}
                  }}
                }}
                metafields(first: 20) {{
                  edges {{
                    node {{
                      namespace
                      key
                      value
                      type
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """

    def _extract_product_data(self, product_node: Dict) -> Dict:
        """Extract product data from GraphQL response"""
        shopify_product_id = product_node['id'].split('/')[-1]

        return {
            'shopify_product_id': shopify_product_id,
            'title': product_node['title'],
            'description': product_node.get('descriptionHtml'),
            'product_type': product_node.get('productType'),
            'vendor': product_node.get('vendor'),
            'category': self._categorize_product(product_node),
            'images': [
                {
                    'src': img['node']['src'],
                    'alt': img['node'].get('altText')
                }
                for img in product_node.get('images', {}).get('edges', [])
            ],
            'variants': [
                {
                    'id': var['node']['id'].split('/')[-1],
                    'title': var['node']['title'],
                    'sku': var['node'].get('sku'),
                    'price': var['node']['price'],
                    'size': self._extract_size_from_variant(var['node'])
                }
                for var in product_node.get('variants', {}).get('edges', [])
            ]
        }

    def _categorize_product(self, product_node: Dict) -> str:
        """
        Auto-categorize product based on type and tags

        Returns: 'tops', 'bottoms', 'dresses', 'outerwear', or 'unknown'
        """
        product_type = product_node.get('productType', '').lower()
        tags = [tag.lower() for tag in product_node.get('tags', [])]
        title = product_node.get('title', '').lower()

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

    def _extract_size_from_variant(self, variant_node: Dict) -> Optional[str]:
        """Extract size from variant options"""
        selected_options = variant_node.get('selectedOptions', [])
        for option in selected_options:
            if option['name'].lower() in ['size', 'sizes']:
                return option['value']
        return None

    def _extract_size_chart(self, product_node: Dict) -> Optional[Dict]:
        """Extract size chart from product metafields"""
        metafields = product_node.get('metafields', {}).get('edges', [])

        for metafield_edge in metafields:
            metafield = metafield_edge['node']

            if (metafield['namespace'] == 'custom' and
                metafield['key'] == 'size_chart'):
                try:
                    import json
                    size_data = json.loads(metafield['value'])
                    return self._parse_size_chart(size_data)
                except:
                    pass

        return None

    def _parse_size_chart(self, size_data: Dict) -> Dict:
        """Parse size chart data"""
        # TODO: Implement proper size chart parsing
        return size_data

    async def _save_product(self, db: Session, store_id: str, product_data: Dict) -> Product:
        """Save or update product in database"""
        # Check if product exists
        existing_product = db.query(Product).filter(
            Product.store_id == store_id,
            Product.shopify_product_id == product_data['shopify_product_id']
        ).first()

        if existing_product:
            # Update existing product
            for key, value in product_data.items():
                setattr(existing_product, key, value)
            existing_product.last_synced_at = datetime.utcnow()
            product = existing_product
        else:
            # Create new product
            product = Product(
                store_id=store_id,
                **product_data,
                last_synced_at=datetime.utcnow()
            )
            db.add(product)

        db.flush()
        return product

    async def _save_size_chart(self, db: Session, product_id: str, size_chart_data: Dict):
        """Save size chart for product"""
        # TODO: Implement size chart saving
        pass

    async def list_collections(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List collections for the current shop via Shopify GraphQL.
        """
        capped_limit = max(1, min(int(limit), 250))
        skip = max(int(offset), 0)

        query = """
        query ListCollections($first: Int!, $after: String, $query: String) {
          collections(first: $first, after: $after, query: $query) {
            pageInfo {
              hasNextPage
              endCursor
            }
            edges {
              node {
                id
                title
                handle
                image {
                  url
                }
                productsCount {
                  count
                }
              }
            }
          }
        }
        """

        collected: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        while True:
            variables = {
                "first": 250,
                "after": cursor,
                "query": (search or "").strip() or None,
            }
            result = await self._graphql_request(query, variables)
            payload = result.get("data", {}).get("collections", {})
            edges = payload.get("edges", []) or []

            for edge in edges:
                node = (edge or {}).get("node", {}) or {}
                collection_id = str(node.get("id") or "").strip()
                if not collection_id:
                    continue

                products_count_raw = node.get("productsCount")
                if isinstance(products_count_raw, dict):
                    products_count_raw = products_count_raw.get("count")

                products_count = None
                if isinstance(products_count_raw, int):
                    products_count = products_count_raw
                elif isinstance(products_count_raw, str) and products_count_raw.isdigit():
                    products_count = int(products_count_raw)

                collected.append(
                    {
                        "id": collection_id,
                        "title": str(node.get("title") or collection_id),
                        "handle": node.get("handle"),
                        "image_url": ((node.get("image") or {}).get("url") or None),
                        "products_count": products_count,
                    }
                )

            page_info = payload.get("pageInfo", {}) or {}
            cursor = page_info.get("endCursor")
            has_next = bool(page_info.get("hasNextPage"))
            if not has_next or len(collected) >= (skip + capped_limit):
                break

        return collected[skip: skip + capped_limit]

    async def get_product_collection_ids(self, *, shopify_product_gid: str) -> List[str]:
        """
        Fetch all collection GIDs that contain a given Shopify product.
        """
        query = """
        query ProductCollections($id: ID!, $first: Int!, $after: String) {
          product(id: $id) {
            collections(first: $first, after: $after) {
              pageInfo {
                hasNextPage
                endCursor
              }
              edges {
                node {
                  id
                }
              }
            }
          }
        }
        """

        collection_ids: List[str] = []
        cursor: Optional[str] = None

        while True:
            variables = {
                "id": shopify_product_gid,
                "first": 250,
                "after": cursor,
            }
            result = await self._graphql_request(query, variables)
            product_node = result.get("data", {}).get("product")
            if not product_node:
                return []

            collections = product_node.get("collections", {}) or {}
            edges = collections.get("edges", []) or []
            for edge in edges:
                node = (edge or {}).get("node", {}) or {}
                collection_id = str(node.get("id") or "").strip()
                if collection_id:
                    collection_ids.append(collection_id)

            page_info = collections.get("pageInfo", {}) or {}
            cursor = page_info.get("endCursor")
            if not page_info.get("hasNextPage"):
                break

        return collection_ids

    # Billing API
    # ──────────────────────────────────────────────────────────

    async def billing_create_subscription(
        self,
        plan_name: str,
        price_usd: float,
        return_url: str,
        billing_interval: str = "monthly",
        trial_days: int = 0,
        test: bool = False,
        is_upgrade: bool = False,
        usage_cap_usd: float = 500.0,
        overage_terms: str = "Usage-based overage charges apply",
    ) -> dict:
        """
        Create a recurring app subscription via Shopify Billing API.

        Args:
            plan_name: Human-readable plan label (used as subscription name)
            price_usd: Charge amount in USD (monthly price or annual total)
            return_url: URL Shopify redirects to after merchant approves
            billing_interval: 'monthly' → EVERY_30_DAYS, 'annual' → ANNUAL
            trial_days: Number of free trial days (0 = no trial)
            test: True in development to avoid real charges
            is_upgrade: If True, uses APPLY_IMMEDIATELY replacement behavior (prorated)

        Returns:
            { "confirmation_url": "...", "subscription_id": "gid://..." }

        Raises:
            Exception: If Shopify returns userErrors
        """
        shopify_interval = "ANNUAL" if billing_interval == "annual" else "EVERY_30_DAYS"
        variables = self._build_subscription_create_variables(
            plan_name=plan_name,
            price_usd=price_usd,
            return_url=return_url,
            shopify_interval=shopify_interval,
            trial_days=trial_days,
            test=test,
            is_upgrade=is_upgrade,
            usage_cap_usd=usage_cap_usd,
            overage_terms=overage_terms,
        )

        return await self._execute_subscription_create_mutation(
            variables=variables,
            billing_interval=billing_interval,
            structured_errors=False,
        )

    async def billing_create_subscription_annual(
        self,
        *,
        plan_name: str,
        price_usd: float,
        return_url: str,
        trial_days: int = 0,
        test: bool = False,
        is_upgrade: bool = False,
        usage_cap_usd: float = 500.0,
        overage_terms: str = "Usage-based overage charges apply",
    ) -> dict:
        """
        Create an ANNUAL recurring subscription (with usage billing line item).
        """
        variables = self._build_subscription_create_variables(
            plan_name=plan_name,
            price_usd=price_usd,
            return_url=return_url,
            shopify_interval="ANNUAL",
            trial_days=trial_days,
            test=test,
            is_upgrade=is_upgrade,
            usage_cap_usd=usage_cap_usd,
            overage_terms=overage_terms,
        )
        self._validate_annual_subscription_variables(variables)

        return await self._execute_subscription_create_mutation(
            variables=variables,
            billing_interval="annual",
            structured_errors=True,
        )

    def _build_subscription_create_mutation(self) -> str:
        return """
        mutation appSubscriptionCreate(
          $name: String!
          $lineItems: [AppSubscriptionLineItemInput!]!
          $returnUrl: URL!
          $test: Boolean
          $trialDays: Int
          $replacementBehavior: AppSubscriptionReplacementBehavior
        ) {
          appSubscriptionCreate(
            name: $name
            lineItems: $lineItems
            returnUrl: $returnUrl
            test: $test
            trialDays: $trialDays
            replacementBehavior: $replacementBehavior
          ) {
            confirmationUrl
            appSubscription {
              id
              status
              lineItems {
                id
                plan {
                  pricingDetails {
                    __typename
                  }
                }
              }
            }
            userErrors { field message }
          }
        }"""

    def _build_subscription_create_variables(
        self,
        *,
        plan_name: str,
        price_usd: float,
        return_url: str,
        shopify_interval: str,
        trial_days: int,
        test: bool,
        is_upgrade: bool,
        usage_cap_usd: float,
        overage_terms: str,
    ) -> Dict[str, Any]:
        variables: Dict[str, Any] = {
            "name": plan_name,
            "returnUrl": return_url,
            "test": test,
            "trialDays": trial_days if trial_days > 0 else None,
            "lineItems": [
                {
                    "plan": {
                        "appRecurringPricingDetails": {
                            "price": {
                                "amount": price_usd,
                                "currencyCode": "USD",
                            },
                            "interval": shopify_interval,
                        }
                    }
                },
                {
                    "plan": {
                        "appUsagePricingDetails": {
                            "terms": overage_terms,
                            "cappedAmount": {
                                "amount": usage_cap_usd,
                                "currencyCode": "USD",
                            },
                        }
                    }
                },
            ],
        }
        if is_upgrade:
            variables["replacementBehavior"] = "APPLY_IMMEDIATELY"
        return variables

    def _validate_annual_subscription_variables(self, variables: Dict[str, Any]) -> None:
        errors: List[Dict[str, Any]] = []

        trial_days = variables.get("trialDays")
        if trial_days is not None and (not isinstance(trial_days, int) or trial_days < 0):
            errors.append(
                {
                    "field": ["trialDays"],
                    "message": "Annual billing payload has invalid trialDays; expected a non-negative integer.",
                }
            )

        replacement_behavior = variables.get("replacementBehavior")
        if replacement_behavior is not None and replacement_behavior not in {
            "APPLY_IMMEDIATELY",
            "APPLY_ON_NEXT_BILLING_CYCLE",
        }:
            errors.append(
                {
                    "field": ["replacementBehavior"],
                    "message": "Annual billing payload has unsupported replacementBehavior.",
                }
            )

        line_items = variables.get("lineItems")
        if not isinstance(line_items, list) or len(line_items) < 2:
            errors.append(
                {
                    "field": ["lineItems"],
                    "message": "Annual billing payload must include recurring and usage billing line items.",
                }
            )
        else:
            recurring_details = next(
                (
                    details
                    for item in line_items
                    if isinstance(item, dict)
                    for details in [((item.get("plan", {}) or {}).get("appRecurringPricingDetails"))]
                    if details
                ),
                None,
            )
            usage_details = next(
                (
                    details
                    for item in line_items
                    if isinstance(item, dict)
                    for details in [((item.get("plan", {}) or {}).get("appUsagePricingDetails"))]
                    if details
                ),
                None,
            )

            if not recurring_details:
                errors.append(
                    {
                        "field": ["lineItems", "appRecurringPricingDetails"],
                        "message": "Annual billing payload is missing recurring pricing details.",
                    }
                )
            elif recurring_details.get("interval") != "ANNUAL":
                errors.append(
                    {
                        "field": ["lineItems", "appRecurringPricingDetails", "interval"],
                        "message": "Annual billing payload must use ANNUAL recurring interval.",
                    }
                )

            if not usage_details:
                errors.append(
                    {
                        "field": ["lineItems", "appUsagePricingDetails"],
                        "message": "Annual billing payload is missing usage pricing details.",
                    }
                )

        if errors:
            raise ShopifyBillingUserErrors(billing_interval="annual", errors=errors)

    def _raise_billing_user_errors(
        self,
        errors: List[Dict[str, Any]],
        *,
        billing_interval: str,
        structured_errors: bool,
    ) -> None:
        managed_pricing_error = next(
            (
                (entry or {}).get("message", "")
                for entry in errors
                if "managed pricing apps cannot use the billing api" in str((entry or {}).get("message", "")).lower()
            ),
            None,
        )
        if managed_pricing_error:
            raise ShopifyManagedPricingError(managed_pricing_error)
        if not structured_errors:
            raise Exception(f"Shopify billing error: {errors}")
        raise ShopifyBillingUserErrors(billing_interval=billing_interval, errors=errors)

    async def _execute_subscription_create_mutation(
        self,
        *,
        variables: Dict[str, Any],
        billing_interval: str,
        structured_errors: bool,
    ) -> Dict[str, Any]:
        mutation = self._build_subscription_create_mutation()
        result = await self._graphql_request(mutation, variables)
        payload = result["data"]["appSubscriptionCreate"]

        if payload.get("userErrors"):
            self._raise_billing_user_errors(
                payload["userErrors"],
                billing_interval=billing_interval,
                structured_errors=structured_errors,
            )

        usage_line_item_id = None
        for line_item in payload.get("appSubscription", {}).get("lineItems", []):
            plan = line_item.get("plan", {})
            details = plan.get("pricingDetails", {})
            if details.get("__typename") == "AppUsagePricing":
                usage_line_item_id = line_item.get("id")
                break

        return {
            "confirmation_url": payload["confirmationUrl"],
            "subscription_id": payload["appSubscription"]["id"],
            "usage_line_item_id": usage_line_item_id,
        }

    async def billing_cancel_subscription(self, subscription_gid: str) -> bool:
        """
        Cancel an active app subscription via Shopify Billing API.

        Args:
            subscription_gid: Shopify GID e.g. 'gid://shopify/AppSubscription/123'

        Returns:
            True on success

        Raises:
            Exception: If Shopify returns userErrors
        """
        mutation = """
        mutation appSubscriptionCancel($id: ID!) {
          appSubscriptionCancel(id: $id) {
            appSubscription { id status }
            userErrors { field message }
          }
        }"""

        result = await self._graphql_request(mutation, {"id": subscription_gid})
        payload = result["data"]["appSubscriptionCancel"]

        if payload.get("userErrors"):
            errors = payload["userErrors"]
            raise Exception(f"Shopify cancel error: {errors}")

        return True

    async def billing_get_status(self) -> dict | None:
        """
        Fetch the active app subscription from Shopify.

        Returns:
            Dict with subscription fields, or None if no active subscription.
        """
        query = """
        query {
          shop {
            ianaTimezone
            timezoneOffset
          }
          currentAppInstallation {
            activeSubscriptions {
              id name status currentPeriodEnd test trialDays
              createdAt
              lineItems {
                id
                plan {
                  pricingDetails {
                    ... on AppRecurringPricing {
                      price { amount currencyCode }
                      interval
                    }
                    ... on AppUsagePricing {
                      terms
                      cappedAmount { amount currencyCode }
                      balanceUsed { amount currencyCode }
                    }
                  }
                }
              }
            }
          }
        }"""

        result = await self._graphql_request(query)
        subscriptions = (
            result.get("data", {})
            .get("currentAppInstallation", {})
            .get("activeSubscriptions", [])
        )

        if not subscriptions:
            return None

        sub = subscriptions[0]
        usage_line_item_id = None
        has_usage_billing = False
        for line_item in sub.get("lineItems", []):
            details = line_item.get("plan", {}).get("pricingDetails", {})
            if details.get("__typename") == "AppUsagePricing":
                has_usage_billing = True
                usage_line_item_id = line_item.get("id")
                break

        return {
            "id": sub["id"],
            "name": sub["name"],
            "status": sub["status"],
            "current_period_end": sub.get("currentPeriodEnd"),
            "created_at": sub.get("createdAt"),
            "test": sub.get("test", False),
            "trial_days": sub.get("trialDays", 0),
            "has_usage_billing": has_usage_billing,
            "usage_line_item_id": usage_line_item_id,
            "shop_timezone": result.get("data", {}).get("shop", {}).get("ianaTimezone"),
        }

    async def billing_get_subscription(self, subscription_gid: str) -> dict | None:
        """
        Fetch a specific app subscription by ID from currentAppInstallation.
        Returns None when not found.
        """
        query = """
        query SubscriptionById($id: ID!) {
          currentAppInstallation {
            appSubscription(id: $id) {
              id
              name
              status
              currentPeriodEnd
              test
              trialDays
              createdAt
              lineItems {
                id
                plan {
                  pricingDetails {
                    __typename
                    ... on AppRecurringPricing {
                      interval
                      price { amount currencyCode }
                    }
                  }
                }
              }
            }
          }
        }
        """
        result = await self._graphql_request(query, {"id": subscription_gid})
        payload = (
            (result or {})
            .get("data", {})
            .get("currentAppInstallation", {})
            .get("appSubscription")
        )
        if not payload:
            return None
        return payload

    async def billing_create_usage_charge(
        self,
        *,
        usage_line_item_id: str,
        amount_usd: float,
        description: str,
    ) -> dict:
        """
        Create a usage charge record tied to an AppSubscription usage line item.
        """
        mutation = """
        mutation appUsageRecordCreate(
          $subscriptionLineItemId: ID!,
          $description: String!,
          $price: MoneyInput!
        ) {
          appUsageRecordCreate(
            subscriptionLineItemId: $subscriptionLineItemId,
            description: $description,
            price: $price
          ) {
            appUsageRecord {
              id
            }
            userErrors {
              field
              message
            }
          }
        }
        """
        variables = {
            "subscriptionLineItemId": usage_line_item_id,
            "description": description,
            "price": {
                "amount": amount_usd,
                "currencyCode": "USD",
            },
        }
        result = await self._graphql_request(mutation, variables)
        payload = result.get("data", {}).get("appUsageRecordCreate", {})
        errors = payload.get("userErrors", [])
        if errors:
            raise Exception(f"Shopify usage billing error: {errors}")

        app_usage_record = payload.get("appUsageRecord")
        if not app_usage_record:
            raise Exception("Shopify usage billing error: appUsageRecord missing in response")

        return {
            "usage_record_id": app_usage_record.get("id"),
        }

    # ──────────────────────────────────────────────────────────
    # Orders API
    # ──────────────────────────────────────────────────────────

    async def get_orders_with_refunds(
        self,
        since: datetime,
        customer_ids: Optional[List[str]] = None,
    ) -> dict:
        """
        Fetch orders via Shopify GraphQL Admin API created since `since`.

        Args:
            since: Fetch orders created at or after this datetime (UTC)
            customer_ids: Optional list of customer IDs to filter by (client-side)

        Returns:
            {
                "orders": [{
                    "id", "customer_id", "total_price", "refunds", "created_at", "line_items"
                }, ...],
                "return_count": int   # orders that have at least one refund
            }
        """
        now_utc = datetime.utcnow()
        min_allowed = now_utc - timedelta(days=self.ORDERS_LOOKBACK_LIMIT_DAYS)
        effective_since = since
        if effective_since.tzinfo is not None:
            effective_since = effective_since.astimezone(timezone.utc).replace(tzinfo=None)
        if effective_since < min_allowed:
            logger.info(
                "Shopify orders lookback clipped to %s days for shop=%s requested_since=%s clipped_since=%s",
                self.ORDERS_LOOKBACK_LIMIT_DAYS,
                self.shop_domain,
                since.isoformat(),
                min_allowed.isoformat(),
            )
            effective_since = min_allowed

        query = """
        query OrdersWithRefunds($first: Int!, $after: String, $query: String!) {
          orders(first: $first, after: $after, query: $query, sortKey: CREATED_AT) {
            pageInfo {
              hasNextPage
              endCursor
            }
            edges {
              node {
                id
                createdAt
                currentTotalPriceSet {
                  shopMoney {
                    amount
                  }
                }
                customer {
                  id
                }
                lineItems(first: 250) {
                  edges {
                    node {
                      id
                      quantity
                      currentQuantity
                      title
                      discountedTotalSet {
                        shopMoney { amount }
                      }
                      originalUnitPriceSet {
                        shopMoney { amount }
                      }
                      product { id }
                      variant { id }
                    }
                  }
                }
                refunds {
                  id
                  refundLineItems(first: 250) {
                    edges {
                      node {
                        quantity
                        lineItem {
                          id
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """

        created_at_iso = effective_since.replace(microsecond=0).isoformat() + "Z"
        search_query = f"created_at:>={created_at_iso} status:any"
        all_orders: List[dict] = []
        cursor: Optional[str] = None
        while True:
            variables = {"first": 100, "after": cursor, "query": search_query}
            result = await self._graphql_request(query, variables)
            orders_payload = (result.get("data", {}) or {}).get("orders", {}) or {}
            edges = orders_payload.get("edges", []) or []
            for edge in edges:
                node = (edge or {}).get("node", {}) or {}
                customer = node.get("customer") or {}
                normalized_line_items: List[dict] = []
                line_edges = ((node.get("lineItems") or {}).get("edges") or [])
                for line_edge in line_edges:
                    line_item = (line_edge or {}).get("node", {}) or {}
                    total_price = (
                        ((line_item.get("discountedTotalSet") or {}).get("shopMoney") or {}).get("amount")
                        or "0.00"
                    )
                    unit_price = (
                        ((line_item.get("originalUnitPriceSet") or {}).get("shopMoney") or {}).get("amount")
                        or "0.00"
                    )
                    quantity = int(line_item.get("quantity") or 0)
                    try:
                        total_discount = max((float(unit_price) * quantity) - float(total_price), 0.0)
                    except Exception:
                        total_discount = 0.0

                    product_gid = ((line_item.get("product") or {}).get("id") or "")
                    variant_gid = ((line_item.get("variant") or {}).get("id") or "")
                    normalized_line_items.append(
                        {
                            "id": str(line_item.get("id", "")),
                            "product_id": str(product_gid.rsplit("/", 1)[-1]) if product_gid else None,
                            "variant_id": str(variant_gid.rsplit("/", 1)[-1]) if variant_gid else None,
                            "title": line_item.get("title"),
                            "price": str(unit_price),
                            "quantity": quantity,
                            "total_discount": f"{total_discount:.2f}",
                        }
                    )

                normalized_refunds: List[dict] = []
                for refund in node.get("refunds") or []:
                    refund_edges = ((refund or {}).get("refundLineItems") or {}).get("edges") or []
                    normalized_refunds.append(
                        {
                            "id": str((refund or {}).get("id", "")),
                            "refund_line_items": [
                                {
                                    "line_item_id": str((((refund_line_edge or {}).get("node") or {}).get("lineItem") or {}).get("id", "")) or None,
                                    "quantity": int((((refund_line_edge or {}).get("node") or {}).get("quantity") or 0)),
                                    "line_item": {
                                        "id": str((((refund_line_edge or {}).get("node") or {}).get("lineItem") or {}).get("id", "") or ""),
                                    },
                                }
                                for refund_line_edge in refund_edges
                            ],
                        }
                    )

                order_total = (((node.get("currentTotalPriceSet") or {}).get("shopMoney") or {}).get("amount") or "0.00")
                customer_gid = customer.get("id")
                all_orders.append(
                    {
                        "id": str(node.get("id", "")),
                        "customer_id": str(customer_gid.rsplit("/", 1)[-1]) if customer_gid else None,
                        "total_price": str(order_total),
                        "refunds": normalized_refunds,
                        "created_at": node.get("createdAt"),
                        "line_items": normalized_line_items,
                    }
                )

            page_info = orders_payload.get("pageInfo", {}) or {}
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        # Filter by customer_ids if provided
        customer_id_set = set(customer_ids) if customer_ids else None
        if customer_id_set:
            all_orders = [o for o in all_orders if o["customer_id"] in customer_id_set]

        return_count = sum(1 for o in all_orders if o["refunds"])
        return {"orders": all_orders, "return_count": return_count}

    async def add_product_image(
        self,
        shopify_product_gid: str,
        image_url: str,
        alt_text: str = "",
    ) -> dict:
        """
        Add an image to a Shopify product via the productCreateMedia mutation.

        Args:
            shopify_product_gid: Full Shopify GID e.g. "gid://shopify/Product/123"
            image_url: Publicly accessible HTTPS URL — Shopify fetches and re-hosts it
            alt_text: Optional alt text for the image (max 512 chars)

        Returns:
            dict with keys: media_id (Shopify GID), image_url (Shopify CDN URL)

        Raises:
            Exception if Shopify returns mediaUserErrors
        """
        mutation = """
        mutation productCreateMedia($media: [CreateMediaInput!]!, $productId: ID!) {
          productCreateMedia(media: $media, productId: $productId) {
            media {
              ... on MediaImage {
                id
                image { url }
              }
            }
            mediaUserErrors { field message code }
          }
        }"""

        variables = {
            "productId": shopify_product_gid,
            "media": [{
                "alt": alt_text[:512] if alt_text else "",
                "mediaContentType": "IMAGE",
                "originalSource": image_url,
            }],
        }

        result = await self._graphql_request(mutation, variables)
        payload = result.get("data", {}).get("productCreateMedia", {})

        errors = payload.get("mediaUserErrors", [])
        if errors:
            raise Exception(f"Shopify productCreateMedia error: {errors[0]['message']}")

        media_list = payload.get("media", [])
        media = media_list[0] if media_list else {}
        return {
            "media_id": media.get("id"),
            "image_url": (media.get("image") or {}).get("url"),
        }
