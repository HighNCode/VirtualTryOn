"""Provider interface for all image-generation backends."""

from abc import ABC, abstractmethod
from typing import Optional


class ImageGenerationProvider(ABC):
    """Single contract used by both customer try-on and merchant photoshoot flows."""

    @abstractmethod
    def generate_tryon(
        self,
        person_image: bytes,
        product_image_url: str,
        product_title: str,
        category: str,
    ) -> bytes:
        """Generate a customer try-on image."""
        raise NotImplementedError

    @abstractmethod
    def generate_studio_tryon(
        self,
        tryon_image: bytes,
        studio_image: bytes,
    ) -> bytes:
        """Generate a studio-style image from an existing try-on."""
        raise NotImplementedError

    @abstractmethod
    def generate_ghost_mannequin(
        self,
        image1_bytes: bytes,
        image2_bytes: bytes,
        clothing_type: Optional[str] = None,
        reference_pose: Optional[str] = None,
    ) -> bytes:
        """Generate a ghost mannequin output from two garment images."""
        raise NotImplementedError

    @abstractmethod
    def generate_try_on_model(
        self,
        product_image_bytes: bytes,
        model_image_bytes: bytes,
    ) -> bytes:
        """Generate a model try-on output for merchant photoshoot."""
        raise NotImplementedError

    @abstractmethod
    def generate_model_swap(
        self,
        original_wearing_bytes: bytes,
        face_bytes: bytes,
    ) -> bytes:
        """Generate a face-swapped version of an existing wearing image."""
        raise NotImplementedError
