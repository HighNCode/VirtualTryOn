"""
AI Photoshoot Service (Merchant-Facing)
Generates ghost mannequin, try-on for model, and model swap images
using Google Vertex AI (Gemini).
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


class PhotoshootService:
    """Service for merchant AI photoshoot features via Vertex AI (Gemini)"""

    def __init__(self):
        self._client = _client
        self._model = settings.TRYON_MODEL

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_ghost_mannequin(
        self,
        image1_bytes: bytes,
        image2_bytes: bytes,
        clothing_type: Optional[str] = None,
    ) -> bytes:
        """
        Create a ghost mannequin (invisible mannequin) product image from two
        photos of the same garment.

        Both images can be any combination of angles (front, back, inside, flat-lay,
        or worn on a model/mannequin). Gemini uses both to construct the best
        composite 3D hollow garment view.

        Args:
            clothing_type: Optional garment type hint ("tops" | "bottoms" | "dresses" | "outerwear")

        Returns:
            Generated image bytes (PNG)
        """
        start = time.time()

        garment_hints = {
            "tops":      "Pay special attention to the collar, neckline, and sleeve openings.",
            "bottoms":   "Pay special attention to the waistband and leg openings.",
            "dresses":   "Show the full length from neckline to hem.",
            "outerwear": "Show the collar, lapels, and front closure detail.",
        }
        garment_detail = garment_hints.get(clothing_type or "", "")

        prompt = (
            "You are given two photos of the same garment. "
            "Create a single professional ghost mannequin (invisible mannequin) product photo: "
            "the garment should appear as if worn by an invisible torso — showing the garment's "
            "full 3D shape, neckline, armholes, and bottom hem. "
            "Remove any visible model, mannequin, hanger, or background from the output. "
            "Use both images to construct the best possible result: if one shows the front and "
            "the other shows the back or inside, composite them to reveal interior collar lining "
            "or label detail. "
            f"{garment_detail} "
            "Output a clean, professional product photo on a white or light grey background."
        )

        logger.info(f"PhotoshootService: ghost_mannequin clothing_type={clothing_type}, model={settings.TRYON_MODEL}")

        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=image1_bytes, mime_type="image/jpeg"),
                types.Part.from_bytes(data=image2_bytes, mime_type="image/jpeg"),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        result = self._extract_image(response)
        logger.info(f"ghost_mannequin completed in {time.time() - start:.1f}s")
        return result

    def generate_try_on_model(
        self,
        product_image_bytes: bytes,
        model_image_bytes: bytes,
    ) -> bytes:
        """
        Place a product garment onto a given model photo.

        Args:
            product_image_bytes: Flat-lay or model-worn product image
            model_image_bytes: Photo of the target model

        Returns:
            Generated image bytes (PNG)
        """
        start = time.time()

        prompt = (
            "You are given a garment/product photo and a photo of a model. "
            "Generate a single photorealistic image of the model wearing this exact garment. "
            "Keep the model's face, body, skin tone, hair, and pose exactly the same as in the model photo. "
            "Keep the garment's color, texture, pattern, and design details exactly the same as in the product photo. "
            "Fit the garment naturally on the model's body. "
            "The result should look like a professional fashion product photograph."
        )

        logger.info(f"PhotoshootService: try_on_model, model={settings.TRYON_MODEL}")

        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=product_image_bytes, mime_type="image/jpeg"),
                types.Part.from_bytes(data=model_image_bytes, mime_type="image/jpeg"),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        result = self._extract_image(response)
        logger.info(f"try_on_model completed in {time.time() - start:.1f}s")
        return result

    def generate_model_swap(
        self,
        original_wearing_bytes: bytes,
        face_bytes: bytes,
    ) -> bytes:
        """
        Swap only the face in a product photo — body, pose, clothing, background,
        and lighting remain identical to the original image.

        Args:
            original_wearing_bytes: Image of original model wearing the product
            face_bytes: Headshot/face photo of the replacement face

        Returns:
            Generated image bytes (PNG)
        """
        start = time.time()

        prompt = (
            "The first image shows a model wearing a product. "
            "The second image shows a face. "
            "Replace the face of the model in the first image with the face shown in the second image. "
            "Keep everything else in the first image completely identical: "
            "the body, pose, clothing, background, and lighting must not change at all. "
            "Only the face region should be replaced. "
            "The result should look like a seamless, photorealistic professional fashion photograph."
        )

        logger.info(f"PhotoshootService: model_swap (face-only), model={settings.TRYON_MODEL}")

        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=original_wearing_bytes, mime_type="image/jpeg"),
                types.Part.from_bytes(data=face_bytes, mime_type="image/jpeg"),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        result = self._extract_image(response)
        logger.info(f"model_swap completed in {time.time() - start:.1f}s")
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _download_image(self, url: str) -> bytes:
        """Download an image from a URL (e.g. Shopify CDN)."""
        import requests
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.content

    def _extract_image(self, response) -> bytes:
        """Extract image bytes from a Vertex AI Gemini response."""
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.inline_data is not None and part.inline_data.data:
                    return part.inline_data.data

        raise ValueError(
            "Vertex AI response did not contain a generated image. "
            "Check that the model supports image output and the prompt is valid."
        )
