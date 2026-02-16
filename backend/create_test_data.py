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
TEST_PRODUCT_ID = "223e4567-e89b-12d3-a456-426614174000"  # tops (T-Shirt)
TEST_PRODUCT_PANTS_ID = "323e4567-e89b-12d3-a456-426614174000"  # bottoms
TEST_PRODUCT_DRESS_ID = "423e4567-e89b-12d3-a456-426614174000"  # dresses
TEST_PRODUCT_JACKET_ID = "523e4567-e89b-12d3-a456-426614174000"  # outerwear


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
            print("✓ Test product (tops) created")

        # --- Pants (bottoms) ---
        existing = db.query(Product).filter_by(product_id=TEST_PRODUCT_PANTS_ID).first()
        if existing:
            print("✓ Test pants already exist")
        else:
            db.add(Product(
                product_id=UUID(TEST_PRODUCT_PANTS_ID),
                store_id=UUID(TEST_STORE_ID),
                shopify_product_id="12346",
                title="Test Slim Jeans",
                description="Classic slim-fit denim jeans for testing",
                product_type="Jeans",
                category="bottoms",
                vendor="Test Vendor",
                images=[{"src": "https://via.placeholder.com/400", "alt": "Test Jeans"}],
                variants=[
                    {"id": "10", "title": "Small", "size": "S", "sku": "JEANS-S", "price": "49.99"},
                    {"id": "11", "title": "Medium", "size": "M", "sku": "JEANS-M", "price": "49.99"},
                    {"id": "12", "title": "Large", "size": "L", "sku": "JEANS-L", "price": "49.99"},
                ],
                has_size_chart=False,
            ))
            print("✓ Test product (bottoms) created")

        # --- Dress (dresses) ---
        existing = db.query(Product).filter_by(product_id=TEST_PRODUCT_DRESS_ID).first()
        if existing:
            print("✓ Test dress already exists")
        else:
            db.add(Product(
                product_id=UUID(TEST_PRODUCT_DRESS_ID),
                store_id=UUID(TEST_STORE_ID),
                shopify_product_id="12347",
                title="Test Summer Dress",
                description="A flowy summer dress for testing",
                product_type="Dress",
                category="dresses",
                vendor="Test Vendor",
                images=[{"src": "https://via.placeholder.com/400", "alt": "Test Dress"}],
                variants=[
                    {"id": "20", "title": "Small", "size": "S", "sku": "DRESS-S", "price": "59.99"},
                    {"id": "21", "title": "Medium", "size": "M", "sku": "DRESS-M", "price": "59.99"},
                    {"id": "22", "title": "Large", "size": "L", "sku": "DRESS-L", "price": "59.99"},
                ],
                has_size_chart=False,
            ))
            print("✓ Test product (dresses) created")

        # --- Jacket (outerwear) ---
        existing = db.query(Product).filter_by(product_id=TEST_PRODUCT_JACKET_ID).first()
        if existing:
            print("✓ Test jacket already exists")
        else:
            db.add(Product(
                product_id=UUID(TEST_PRODUCT_JACKET_ID),
                store_id=UUID(TEST_STORE_ID),
                shopify_product_id="12348",
                title="Test Bomber Jacket",
                description="A classic bomber jacket for testing",
                product_type="Jacket",
                category="outerwear",
                vendor="Test Vendor",
                images=[{"src": "https://via.placeholder.com/400", "alt": "Test Jacket"}],
                variants=[
                    {"id": "30", "title": "Small", "size": "S", "sku": "JACKET-S", "price": "89.99"},
                    {"id": "31", "title": "Medium", "size": "M", "sku": "JACKET-M", "price": "89.99"},
                    {"id": "32", "title": "Large", "size": "L", "sku": "JACKET-L", "price": "89.99"},
                ],
                has_size_chart=False,
            ))
            print("✓ Test product (outerwear) created")

        db.commit()

        print("\n" + "="*50)
        print("Test Data Created Successfully!")
        print("="*50)
        print(f"\nUse these values in Swagger:\n")
        print(f"X-Store-ID:          {TEST_STORE_ID}")
        print(f"Product (tops):      {TEST_PRODUCT_ID}")
        print(f"Product (bottoms):   {TEST_PRODUCT_PANTS_ID}")
        print(f"Product (dresses):   {TEST_PRODUCT_DRESS_ID}")
        print(f"Product (outerwear): {TEST_PRODUCT_JACKET_ID}")
        print("\nTest flow:")
        print("1. POST /api/v1/sessions")
        print("   Headers: X-Store-ID: " + TEST_STORE_ID)
        print("   Body: {\"product_id\": \"<any product ID above>\"}")
        print("2. POST /api/v1/measurements/extract (with front image)")
        print("3. POST /api/v1/recommendations/size")
        print("4. POST /api/v1/heatmap/generate (with size from step 3)")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_test_data()
