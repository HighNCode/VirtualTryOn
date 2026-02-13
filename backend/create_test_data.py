"""
Create Test Data for Development
Run this script to insert test store and product
"""

import sys
from uuid import UUID

# Add app to path
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.database import Store, Product

# Test UUIDs (fixed for easy reference)
TEST_STORE_ID = "123e4567-e89b-12d3-a456-426614174000"
TEST_PRODUCT_ID = "223e4567-e89b-12d3-a456-426614174000"


def create_test_data():
    """Create test store and product"""
    db = SessionLocal()

    try:
        # Check if test store already exists
        existing_store = db.query(Store).filter_by(store_id=TEST_STORE_ID).first()

        if existing_store:
            print("✓ Test store already exists")
        else:
            # Create test store
            test_store = Store(
                store_id=UUID(TEST_STORE_ID),
                shopify_domain="test-store.myshopify.com",
                shopify_access_token="test-token",
                store_name="Test Store",
                email="test@example.com",
                installation_status="active"
            )
            db.add(test_store)
            print("✓ Test store created")

        # Check if test product already exists
        existing_product = db.query(Product).filter_by(product_id=TEST_PRODUCT_ID).first()

        if existing_product:
            print("✓ Test product already exists")
        else:
            # Create test product
            test_product = Product(
                product_id=UUID(TEST_PRODUCT_ID),
                store_id=UUID(TEST_STORE_ID),
                shopify_product_id="12345",
                title="Test T-Shirt",
                description="A comfortable cotton t-shirt for testing",
                product_type="T-Shirt",
                category="tops",
                vendor="Test Vendor",
                images=[
                    {
                        "src": "https://via.placeholder.com/400",
                        "alt": "Test T-Shirt Front"
                    }
                ],
                variants=[
                    {
                        "id": "1",
                        "title": "Small",
                        "size": "S",
                        "sku": "TEST-S",
                        "price": "29.99"
                    },
                    {
                        "id": "2",
                        "title": "Medium",
                        "size": "M",
                        "sku": "TEST-M",
                        "price": "29.99"
                    },
                    {
                        "id": "3",
                        "title": "Large",
                        "size": "L",
                        "sku": "TEST-L",
                        "price": "29.99"
                    }
                ],
                has_size_chart=False
            )
            db.add(test_product)
            print("✓ Test product created")

        db.commit()

        print("\n" + "="*50)
        print("✅ Test Data Created Successfully!")
        print("="*50)
        print(f"\nUse these values in Swagger:\n")
        print(f"X-Store-ID: {TEST_STORE_ID}")
        print(f"Product ID: {TEST_PRODUCT_ID}")
        print("\nTest in Swagger:")
        print("1. POST /api/v1/sessions")
        print("   Headers: X-Store-ID: " + TEST_STORE_ID)
        print("   Body: {\"product_id\": \"" + TEST_PRODUCT_ID + "\"}")
        print("\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_test_data()
