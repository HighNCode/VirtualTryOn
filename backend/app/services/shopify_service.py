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
