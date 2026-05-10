"""Replicate provider scaffold."""

from typing import Optional

from app.config import Settings
from app.services.image_providers.base import ImageGenerationProvider


class ReplicateProvider(ImageGenerationProvider):
    """
    Replicate provider scaffold.

    The abstraction and config wiring are in place, but operation-level request
    mapping is model-dependent and should be implemented against the selected
    Replicate model contract.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._model = settings.REPLICATE_MODEL

    def generate_tryon(
        self,
        person_image: bytes,
        product_image_url: str,
        product_title: str,
        category: str,
    ) -> bytes:
        raise NotImplementedError("Replicate provider methods are not implemented yet.")

    def generate_studio_tryon(
        self,
        tryon_image: bytes,
        studio_image: bytes,
    ) -> bytes:
        raise NotImplementedError("Replicate provider methods are not implemented yet.")

    def generate_ghost_mannequin(
        self,
        image1_bytes: bytes,
        image2_bytes: bytes,
        clothing_type: Optional[str] = None,
    ) -> bytes:
        raise NotImplementedError("Replicate provider methods are not implemented yet.")

    def generate_try_on_model(
        self,
        product_image_bytes: bytes,
        model_image_bytes: bytes,
    ) -> bytes:
        raise NotImplementedError("Replicate provider methods are not implemented yet.")

    def generate_model_swap(
        self,
        original_wearing_bytes: bytes,
        face_bytes: bytes,
    ) -> bytes:
        raise NotImplementedError("Replicate provider methods are not implemented yet.")
