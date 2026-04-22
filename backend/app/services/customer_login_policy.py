"""
Customer login policy helpers for storefront try-on gating.
"""

from app.config import get_settings
from app.models.database import Store


def is_customer_logged_in(customer_identifier: str | None) -> bool:
    return bool((customer_identifier or "").strip())


def requires_customer_login(store: Store | None = None) -> bool:
    """
    In development, allow anonymous storefront usage for testing.
    In non-development environments, require logged-in customers for try-on limits.
    """
    env = (get_settings().APP_ENV or "").strip().lower()
    if env == "development":
        return False
    return True


def customer_login_required_message() -> str:
    return (
        "Please log in to your store account to continue virtual try-on. "
        "After logging in, reopen this widget and continue."
    )
