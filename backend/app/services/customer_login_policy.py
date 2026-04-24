"""
Customer login policy helpers for storefront try-on gating.
"""

from app.config import get_settings
from app.models.database import Store


def is_customer_logged_in(customer_identifier: str | None) -> bool:
    return bool((customer_identifier or "").strip())


def requires_customer_login(store: Store | None = None) -> bool:
    """
    Teaser policy:
    - Allow anonymous storefront usage up to the configured anonymous weekly cap.
    - Require login only after anonymous cap is exhausted (enforced in usage governance).
    The check-enabled endpoint should not hard-block anonymous entry.
    """
    _ = store
    _ = get_settings()
    return False


def customer_login_required_message() -> str:
    return (
        "Please log in to your store account to continue virtual try-on. "
        "Your anonymous preview limit has been reached."
    )
