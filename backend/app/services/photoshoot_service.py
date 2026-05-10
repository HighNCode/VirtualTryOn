"""Merchant photoshoot service delegating to the active image provider."""

from typing import Optional

from app.services.image_providers.base import ImageGenerationProvider
from app.services.image_providers.factory import get_image_provider


class PhotoshootService:
    """Service facade for merchant photoshoot generation flows."""

    def __init__(self, provider: Optional[ImageGenerationProvider] = None):
        self._provider = provider or get_image_provider()

    def generate_ghost_mannequin(
        self,
        image1_bytes: bytes,
        image2_bytes: bytes,
        clothing_type: Optional[str] = None,
    ) -> bytes:
        return self._provider.generate_ghost_mannequin(
            image1_bytes=image1_bytes,
            image2_bytes=image2_bytes,
            clothing_type=clothing_type,
        )

    def generate_try_on_model(
        self,
        product_image_bytes: bytes,
        model_image_bytes: bytes,
    ) -> bytes:
        return self._provider.generate_try_on_model(
            product_image_bytes=product_image_bytes,
            model_image_bytes=model_image_bytes,
        )

    def generate_model_swap(
        self,
        original_wearing_bytes: bytes,
        face_bytes: bytes,
    ) -> bytes:
        return self._provider.generate_model_swap(
            original_wearing_bytes=original_wearing_bytes,
            face_bytes=face_bytes,
        )
