"""
Generate a test Shopify session token for local backend testing.
Run: python generate_test_token.py
Paste the output into Swagger /docs → Authorize → Bearer, or Postman Authorization header.
"""

import sys
from datetime import datetime, timedelta
from jose import jwt

# Load from .env or set directly
try:
    from dotenv import load_dotenv
    import os
    load_dotenv()
    SHOPIFY_API_KEY = os.environ["SHOPIFY_API_KEY"]
    SHOPIFY_API_SECRET = os.environ["SHOPIFY_API_SECRET"]
    SHOP = os.getenv("DEV_SHOP", "test-store.myshopify.com")
except Exception as e:
    print(f"Error loading env: {e}")
    sys.exit(1)

now = datetime.utcnow()
payload = {
    "iss": f"https://{SHOP}/admin",
    "dest": f"https://{SHOP}",
    "aud": SHOPIFY_API_KEY,
    "sub": "1",
    "exp": int((now + timedelta(hours=24)).timestamp()),
    "nbf": int(now.timestamp()),
    "iat": int(now.timestamp()),
    "jti": "dev-test-token",
    "sid": "dev-session",
}

token = jwt.encode(payload, SHOPIFY_API_SECRET, algorithm="HS256")
print("\nCopy this into Authorization header (Swagger Authorize button or Postman):\n")
print(f"Bearer {token}")
print(f"\nValid for: {SHOP}")
print(f"Expires: {(now + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M UTC')}\n")