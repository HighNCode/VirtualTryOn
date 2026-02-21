"""
One-time script: update test product image URLs in the DB.
Run from the backend/ directory:  python update_product_images.py
"""

import sys
import json
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.database import Product

UPDATES = {
    "223e4567-e89b-12d3-a456-426614174000": {   # T-Shirt (tops)
        "images": [{"src": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800&q=80", "alt": "Test T-Shirt Front"}],
    },
    "323e4567-e89b-12d3-a456-426614174000": {   # Slim Jeans (bottoms)
        "images": [{"src": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=800&q=80", "alt": "Test Jeans"}],
    },
    "423e4567-e89b-12d3-a456-426614174000": {   # Summer Dress (dresses)
        "images": [{"src": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=800&q=80", "alt": "Test Dress"}],
    },
    "523e4567-e89b-12d3-a456-426614174000": {   # Bomber Jacket (outerwear)
        "images": [{"src": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=800&q=80", "alt": "Test Jacket"}],
    },
}

def main():
    db = SessionLocal()
    try:
        updated = 0
        for product_id, fields in UPDATES.items():
            product = db.query(Product).filter_by(product_id=product_id).first()
            if not product:
                print(f"  ⚠  Product {product_id} not found — skipping")
                continue
            product.images = fields["images"]
            updated += 1
            print(f"  ✓  {product.title} → {fields['images'][0]['src'][:60]}...")

        db.commit()
        print(f"\n✅ Updated {updated} products successfully.")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
