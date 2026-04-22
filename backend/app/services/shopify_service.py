"""
Shopify API Integration Service
Handles product sync, webhooks, and Shopify GraphQL API calls
"""

import httpx
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.config import get_settings
from app.models.database import Store, Product, SizeChart
from sqlalchemy.orm import Session

settings = get_settings()
logger = logging.getLogger(__name__)


class ShopifyService:
    """Service for interacting with Shopify API"""

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

    async def install_script_tag(self, widget_url: str) -> Optional[str]:
        """
        Install script tag for widget on Shopify store

        Args:
            widget_url: URL of the widget JavaScript file

        Returns:
            Script tag ID
        """
        url = f"{self.rest_url}/script_tags.json"

        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }

        data = {
            "script_tag": {
                "event": "onload",
                "src": widget_url,
                "display_scope": "all"
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
            return str(result['script_tag']['id'])

    async def delete_script_tag(self, script_tag_id: str):
        """Delete script tag from Shopify store"""
        url = f"{self.rest_url}/script_tags/{script_tag_id}.json"

        headers = {
            "X-Shopify-Access-Token": self.access_token
        }

        async with httpx.AsyncClient() as client:
            await client.delete(url, headers=headers)

    # ──────────────────────────────────────────────────────────
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

        mutation = """
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

        variables = {
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

        result = await self._graphql_request(mutation, variables)
        payload = result["data"]["appSubscriptionCreate"]

        if payload.get("userErrors"):
            errors = payload["userErrors"]
            raise Exception(f"Shopify billing error: {errors}")

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
        Fetch orders via Shopify REST Admin API created since `since`.

        Args:
            since: Fetch orders created at or after this datetime (UTC)
            customer_ids: Optional list of customer IDs to filter by (client-side)

        Returns:
            {
                "orders": [{"id", "customer_id", "total_price", "refunds", "created_at"}, ...],
                "return_count": int   # orders that have at least one refund
            }
        """
        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

        url = (
            f"{self.rest_url}/orders.json"
            f"?status=any"
            f"&created_at_min={since.isoformat()}Z"
            f"&limit=250"
            f"&fields=id,customer,total_price,refunds,created_at"
        )

        all_orders: List[dict] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            while url:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                page_orders = data.get("orders", [])

                for order in page_orders:
                    customer = order.get("customer") or {}
                    all_orders.append({
                        "id": str(order.get("id", "")),
                        "customer_id": str(customer.get("id", "")) if customer.get("id") else None,
                        "total_price": order.get("total_price", "0.00"),
                        "refunds": order.get("refunds", []),
                        "created_at": order.get("created_at"),
                    })

                # Paginate via Link header
                link_header = response.headers.get("Link", "")
                url = self._parse_next_link(link_header)

        # Filter by customer_ids if provided
        customer_id_set = set(customer_ids) if customer_ids else None
        if customer_id_set:
            all_orders = [o for o in all_orders if o["customer_id"] in customer_id_set]

        return_count = sum(1 for o in all_orders if o["refunds"])
        return {"orders": all_orders, "return_count": return_count}

    @staticmethod
    def _parse_next_link(link_header: str) -> Optional[str]:
        """Parse the 'next' URL from a Shopify Link header."""
        if not link_header:
            return None
        for part in link_header.split(","):
            part = part.strip()
            if 'rel="next"' in part:
                # Format: <https://...>; rel="next"
                url_part = part.split(";")[0].strip()
                return url_part.strip("<>")
        return None

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
