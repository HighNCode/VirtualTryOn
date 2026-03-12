"""
Security & Authentication Utilities
Handles Shopify HMAC verification and webhook authentication
"""

import hmac
import hashlib
import base64
from typing import Dict, Optional
from fastapi import Header, HTTPException, Request
from urllib.parse import urlencode
from jose import jwt, JWTError
import logging

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def verify_shopify_hmac(params: Dict[str, str], hmac_to_verify: str) -> bool:
    """
    Verify Shopify HMAC signature for OAuth callback

    Args:
        params: Query parameters from OAuth callback (excluding 'hmac')
        hmac_to_verify: HMAC value from query params

    Returns:
        True if HMAC is valid, False otherwise
    """
    if not settings.SHOPIFY_API_SECRET:
        logger.warning("SHOPIFY_API_SECRET not configured, skipping HMAC verification")
        return True  # Skip verification in development if not configured

    # Remove hmac and signature from params
    params_copy = {k: v for k, v in params.items() if k not in ['hmac', 'signature']}

    # Sort params and create query string
    sorted_params = sorted(params_copy.items())
    params_string = urlencode(sorted_params)

    # Calculate HMAC
    computed_hmac = hmac.new(
        settings.SHOPIFY_API_SECRET.encode('utf-8'),
        params_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # Compare
    return hmac.compare_digest(computed_hmac, hmac_to_verify)


def verify_webhook(request: Request) -> bool:
    """
    Verify Shopify webhook authenticity using HMAC

    Shopify sends webhooks with X-Shopify-Hmac-SHA256 header

    Args:
        request: FastAPI request object

    Returns:
        True if webhook is authentic, False otherwise
    """
    if not settings.SHOPIFY_API_SECRET:
        logger.warning("SHOPIFY_API_SECRET not configured, skipping webhook verification")
        return True

    # Get HMAC from header
    hmac_header = request.headers.get('X-Shopify-Hmac-SHA256')
    if not hmac_header:
        logger.error("Webhook missing X-Shopify-Hmac-SHA256 header")
        return False

    # Get request body
    body = request._body if hasattr(request, '_body') else b''

    # Calculate HMAC
    computed_hmac = base64.b64encode(
        hmac.new(
            settings.SHOPIFY_API_SECRET.encode('utf-8'),
            body,
            hashlib.sha256
        ).digest()
    ).decode('utf-8')

    # Compare
    is_valid = hmac.compare_digest(computed_hmac, hmac_header)

    if not is_valid:
        logger.error("Webhook HMAC verification failed")

    return is_valid


async def verify_webhook_dependency(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
    x_shopify_shop_domain: Optional[str] = Header(None)
) -> bool:
    """
    FastAPI dependency for webhook verification

    Usage:
        @app.post("/webhooks/products/create")
        async def handle_webhook(verified: bool = Depends(verify_webhook_dependency)):
            if not verified:
                raise HTTPException(401, "Invalid webhook")
    """
    if not verify_webhook(request):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    return True


def get_shopify_auth_url(shop: str, redirect_uri: str) -> str:
    """
    Generate Shopify OAuth authorization URL

    Args:
        shop: Shop domain (e.g., mystore.myshopify.com)
        redirect_uri: Callback URL

    Returns:
        Authorization URL
    """
    if not settings.SHOPIFY_API_KEY:
        raise ValueError("SHOPIFY_API_KEY not configured")

    # Ensure shop domain is valid
    if not shop.endswith('.myshopify.com'):
        shop = f"{shop}.myshopify.com"

    params = {
        'client_id': settings.SHOPIFY_API_KEY,
        'scope': settings.SHOPIFY_SCOPES,
        'redirect_uri': redirect_uri,
        'state': generate_state_token(),
    }

    query_string = urlencode(params)
    auth_url = f"https://{shop}/admin/oauth/authorize?{query_string}"

    return auth_url


def generate_state_token() -> str:
    """
    Generate random state token for OAuth CSRF protection

    Returns:
        Random token string
    """
    import secrets
    return secrets.token_urlsafe(32)


async def exchange_code_for_token(shop: str, code: str) -> str:
    """
    Exchange OAuth code for access token

    Args:
        shop: Shop domain
        code: OAuth authorization code

    Returns:
        Access token
    """
    import httpx

    if not shop.endswith('.myshopify.com'):
        shop = f"{shop}.myshopify.com"

    url = f"https://{shop}/admin/oauth/access_token"

    data = {
        'client_id': settings.SHOPIFY_API_KEY,
        'client_secret': settings.SHOPIFY_API_SECRET,
        'code': code
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data)
        response.raise_for_status()
        result = response.json()
        return result['access_token']


def encrypt_token(token: str) -> str:
    """
    Encrypt access token for storage

    In production, use proper encryption (e.g., Fernet)
    For now, return as-is (TODO: implement encryption)

    Args:
        token: Access token to encrypt

    Returns:
        Encrypted token
    """
    # TODO: Implement proper encryption
    return token


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt access token from storage

    Args:
        encrypted_token: Encrypted token

    Returns:
        Decrypted token
    """
    # TODO: Implement proper decryption
    return encrypted_token


def verify_session_token(authorization: Optional[str] = Header(None)) -> dict:
    """
    Verify Shopify session token (JWT) from App Bridge.

    The React frontend sends: Authorization: Bearer <session_token>
    Token is HS256 signed with SHOPIFY_API_SECRET, audience = SHOPIFY_API_KEY.

    Args:
        authorization: Authorization header value

    Returns:
        Decoded JWT payload dict

    Raises:
        HTTPException 401: If token is missing, malformed, or invalid
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing session token")

    token = authorization.replace("Bearer ", "")

    try:
        payload = jwt.decode(
            token,
            settings.SHOPIFY_API_SECRET,
            algorithms=["HS256"],
            audience=settings.SHOPIFY_API_KEY,
        )
        dest = payload.get("dest")
        iss = payload.get("iss")
        if not dest or not iss or dest not in iss:
            raise HTTPException(status_code=401, detail="Invalid token claims")
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
