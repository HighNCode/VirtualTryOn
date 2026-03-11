"""
Virtual Try-On Service
Generates try-on images using Google Vertex AI (Gemini 2.5 Flash)
"""

import logging
import os
import time
from typing import Optional

from google import genai
from google.genai import types

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _make_client() -> genai.Client:
    if not settings.GOOGLE_CLOUD_PROJECT:
        raise ValueError("GOOGLE_CLOUD_PROJECT is not configured")
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        os.environ.setdefault(
            "GOOGLE_APPLICATION_CREDENTIALS",
            settings.GOOGLE_APPLICATION_CREDENTIALS,
        )
    return genai.Client(
        vertexai=True,
        project=settings.GOOGLE_CLOUD_PROJECT,
        location=settings.GOOGLE_CLOUD_LOCATION,
    )


_client = _make_client()


class TryOnService:
    """Service for generating virtual try-on images via Vertex AI (Gemini)"""

    def __init__(self):
        self._client = _client
        self._model = settings.TRYON_MODEL

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        person_image: bytes,
        product_image_url: str,
        product_title: str,
        category: str,
    ) -> bytes:
        """
        Generate a virtual try-on image.

        Args:
            person_image: Person's front photo bytes (from Redis cache)
            product_image_url: URL of the product image
            product_title: Product name for prompt context
            category: Product category (tops, bottoms, dresses, outerwear)

        Returns:
            Generated image bytes (PNG)
        """
        start = time.time()

        product_bytes = self._download_image(product_image_url)
        prompt = self._build_prompt(product_title, category)

        logger.info(
            f"Calling Vertex AI model={settings.TRYON_MODEL}, "
            f"prompt_len={len(prompt)}"
        )

        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=person_image, mime_type="image/jpeg"),
                types.Part.from_bytes(data=product_bytes, mime_type="image/jpeg"),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        result_image = self._extract_image(response)

        elapsed = time.time() - start
        logger.info(f"Try-on generation completed in {elapsed:.1f}s")

        return result_image

    def generate_studio(
        self,
        tryon_image: bytes,
        studio_image: bytes,
    ) -> bytes:
        """
        Generate a studio-styled try-on image.

        Takes an already-generated try-on image and a studio background,
        and produces the person in that environment.

        Args:
            tryon_image: The completed try-on image bytes (person wearing product)
            studio_image: Studio background image bytes

        Returns:
            Generated image bytes (PNG)
        """
        start = time.time()

        prompt = (
            "Place the person from the first image into the environment/background "
            "shown in the second image. Keep the person's appearance and clothing exactly the same from the first image. "
            "Change the background, lighting, objects and pose of the person to match "
            "the environment in the second image. The result should look like a natural professional photograph."
        )

        logger.info(f"Calling Vertex AI for studio look, model={settings.TRYON_MODEL}")

        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=tryon_image, mime_type="image/png"),
                types.Part.from_bytes(data=studio_image, mime_type="image/jpeg"),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        result_image = self._extract_image(response)

        elapsed = time.time() - start
        logger.info(f"Studio generation completed in {elapsed:.1f}s")

        return result_image

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, product_title: str, category: str) -> str:
        """Build the generation prompt."""
        category_hint = {
            "tops": "upper body garment",
            "bottoms": "lower body garment (pants/jeans)",
            "dresses": "full-body dress",
            "outerwear": "outer layer jacket/coat",
        }.get(category, "garment")

        return (
            f"Using the provided person photo and product photo, generate a single "
            f"photorealistic image of the person wearing the {product_title} ({category_hint}). "
            f"Keep the person's face, body, pose, and background exactly the same. "
            f"Keep the product's color, texture, and design exactly the same. "
            f"Fit the product naturally on the person's body. "
            f"The result should look like a real photograph, not a collage."
        )

    def _download_image(self, url: str) -> bytes:
        """Download product image from URL."""
        import requests

        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.content

    def _extract_image(self, response) -> bytes:
        """Extract image bytes from Vertex AI Gemini response."""
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.inline_data is not None and part.inline_data.data:
                    return part.inline_data.data

        raise ValueError(
            "Vertex AI response did not contain a generated image. "
            "Check that the model supports image output and the prompt is valid."
        )
