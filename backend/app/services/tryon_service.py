"""
Virtual Try-On Service
Generates try-on images using Google Gemini (nano-banana) API directly
"""

import io
import logging
import time
import tempfile
import os
from typing import Optional

import google.generativeai as genai
from PIL import Image

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class TryOnService:
    """Service for generating virtual try-on images via Google Gemini API"""

    def __init__(self):
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not configured")
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

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

        # Upload person image to Gemini
        person_file = self._upload_bytes(person_image, "person.jpg")

        # Download and upload product image
        product_bytes = self._download_image(product_image_url)
        product_file = self._upload_bytes(product_bytes, "product.jpg")

        # Build prompt
        prompt = self._build_prompt(product_title, category)

        logger.info(f"Calling Gemini model={settings.GEMINI_MODEL}, prompt_len={len(prompt)}")

        # Generate
        response = self.model.generate_content(
            [prompt, person_file, product_file],
            generation_config=genai.GenerationConfig(
                response_mime_type="image/png",
            ),
        )

        # Extract image from response
        result_image = self._extract_image(response)

        elapsed = time.time() - start
        logger.info(f"Try-on generation completed in {elapsed:.1f}s")

        # Clean up uploaded files
        try:
            genai.delete_file(person_file.name)
            genai.delete_file(product_file.name)
        except Exception:
            pass  # non-critical cleanup

        return result_image

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

        tryon_file = self._upload_bytes(tryon_image, "tryon.png")
        studio_file = self._upload_bytes(studio_image, "studio.jpg")

        prompt = (
            "Place the person from the first image into the environment/background "
            "shown in the second image. Keep the person's appearance, clothing, and "
            "pose exactly the same. Only change the background and lighting to match "
            "the environment. The result should look like a natural professional photograph."
        )

        logger.info(f"Calling Gemini for studio look, model={settings.GEMINI_MODEL}")

        response = self.model.generate_content(
            [prompt, tryon_file, studio_file],
            generation_config=genai.GenerationConfig(
                response_mime_type="image/png",
            ),
        )

        result_image = self._extract_image(response)

        elapsed = time.time() - start
        logger.info(f"Studio generation completed in {elapsed:.1f}s")

        try:
            genai.delete_file(tryon_file.name)
            genai.delete_file(studio_file.name)
        except Exception:
            pass

        return result_image

    def _upload_bytes(self, image_bytes: bytes, display_name: str) -> genai.types.File:
        """Upload image bytes to Gemini file API via a temp file."""
        suffix = ".jpg" if display_name.endswith(".jpg") else ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        try:
            uploaded = genai.upload_file(tmp_path, display_name=display_name)
            return uploaded
        finally:
            os.unlink(tmp_path)

    def _download_image(self, url: str) -> bytes:
        """Download product image from URL."""
        import requests

        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.content

    def _extract_image(self, response) -> bytes:
        """Extract image bytes from Gemini response."""
        # Gemini returns image in parts[0].inline_data when response_mime_type is image/*
        for part in response.parts:
            if hasattr(part, "inline_data") and part.inline_data.data:
                return part.inline_data.data

        # Fallback: check if text response contains base64
        raise ValueError("Gemini response did not contain a generated image")
