"""Factory for selecting the active image-generation provider."""

from functools import lru_cache

from app.config import Settings, get_settings
from app.services.image_providers.base import ImageGenerationProvider
from app.services.image_providers.gemini_provider import GeminiProvider
from app.services.image_providers.replicate_provider import ReplicateProvider
from app.services.image_providers.seedream_provider import SeedreamProvider

SUPPORTED_IMAGE_PROVIDERS = {"gemini", "replicate", "seedream"}


def _provider_name(settings: Settings) -> str:
    return (settings.IMAGE_PROVIDER or "gemini").strip().lower()


def validate_provider_settings(settings: Settings) -> None:
    """Validate required credentials and model settings for the selected provider."""
    provider = _provider_name(settings)
    if provider not in SUPPORTED_IMAGE_PROVIDERS:
        raise ValueError(
            f"Unsupported IMAGE_PROVIDER '{settings.IMAGE_PROVIDER}'. "
            f"Supported values: {', '.join(sorted(SUPPORTED_IMAGE_PROVIDERS))}"
        )

    if provider == "gemini":
        if not settings.GOOGLE_CLOUD_PROJECT:
            raise ValueError("GOOGLE_CLOUD_PROJECT is required when IMAGE_PROVIDER=gemini")
        if not settings.TRYON_MODEL:
            raise ValueError("TRYON_MODEL is required when IMAGE_PROVIDER=gemini")
        return

    if provider == "replicate":
        if not settings.REPLICATE_API_TOKEN:
            raise ValueError("REPLICATE_API_TOKEN is required when IMAGE_PROVIDER=replicate")
        if not settings.REPLICATE_MODEL:
            raise ValueError("REPLICATE_MODEL is required when IMAGE_PROVIDER=replicate")
        return

    if not settings.SEEDREAM_API_KEY:
        raise ValueError("SEEDREAM_API_KEY is required when IMAGE_PROVIDER=seedream")
    if not settings.SEEDREAM_MODEL:
        raise ValueError("SEEDREAM_MODEL is required when IMAGE_PROVIDER=seedream")
    if not (settings.SEEDREAM_BASE_URL or "").strip():
        raise ValueError("SEEDREAM_BASE_URL is required when IMAGE_PROVIDER=seedream")


def create_image_provider(settings: Settings) -> ImageGenerationProvider:
    """Create a provider instance from a supplied Settings object."""
    validate_provider_settings(settings)
    provider = _provider_name(settings)
    if provider == "gemini":
        return GeminiProvider(settings)
    if provider == "replicate":
        return ReplicateProvider(settings)
    if provider == "seedream":
        return SeedreamProvider(settings)
    raise ValueError(f"Unsupported IMAGE_PROVIDER '{settings.IMAGE_PROVIDER}'")


@lru_cache(maxsize=1)
def get_image_provider() -> ImageGenerationProvider:
    """Get singleton provider for the running process."""
    return create_image_provider(get_settings())


def clear_image_provider_cache() -> None:
    """Clear cached provider instance (useful in tests)."""
    get_image_provider.cache_clear()
