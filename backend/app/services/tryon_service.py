"""Virtual try-on service delegating to the active image provider."""

from typing import Optional

from app.services.image_providers.base import ImageGenerationProvider
from app.services.image_providers.factory import get_image_provider


class TryOnService:
    """Service facade for customer try-on and studio-try-on generation."""

    def __init__(self, provider: Optional[ImageGenerationProvider] = None):
        self._provider = provider or get_image_provider()

    def generate(
        self,
        person_image: bytes,
        product_image_url: str,
        product_title: str,
        category: str,
    ) -> bytes:
        return self._provider.generate_tryon(
            person_image=person_image,
            product_image_url=product_image_url,
            product_title=product_title,
            category=category,
        )

    def generate_studio(
        self,
        tryon_image: bytes,
        studio_image: bytes,
    ) -> bytes:
        return self._provider.generate_studio_tryon(
            tryon_image=tryon_image,
            studio_image=studio_image,
        )
