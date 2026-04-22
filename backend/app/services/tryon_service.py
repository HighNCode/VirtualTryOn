"""
Virtual Try-On Service
Generates try-on images using Google Vertex AI (Gemini 2.5 Flash)
"""

import logging
import os
import time
import base64
import binascii
import json
import re
from io import BytesIO
from typing import Optional

from google import genai
from google.genai import types
from PIL import Image

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
                types.Part.from_bytes(data=person_image, mime_type=self._detect_mime_type(person_image)),
                types.Part.from_bytes(data=product_bytes, mime_type=self._detect_mime_type(product_bytes)),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        result_image = self._normalize_image_bytes(self._extract_image(response))

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
                types.Part.from_bytes(data=tryon_image, mime_type=self._detect_mime_type(tryon_image)),
                types.Part.from_bytes(data=studio_image, mime_type=self._detect_mime_type(studio_image)),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        result_image = self._normalize_image_bytes(self._extract_image(response))

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
        image_bytes = resp.content

        content_type = resp.headers.get("Content-Type", "")
        content_length = resp.headers.get("Content-Length")
        width = None
        height = None
        try:
            with Image.open(BytesIO(image_bytes)) as img:
                width, height = img.size
        except Exception:
            # Keep generation behavior unchanged; just log missing decode metadata.
            width, height = None, None

        logger.info(
            "Product image downloaded: request_url=%s final_url=%s status=%s content_type=%s content_length=%s bytes=%s width=%s height=%s",
            url,
            resp.url,
            resp.status_code,
            content_type,
            content_length,
            len(image_bytes),
            width,
            height,
        )
        return image_bytes

    def _extract_image(self, response) -> bytes:
        """Extract image bytes from Vertex AI Gemini response."""
        text_fallback_samples = []
        for candidate in (response.candidates or []):
            for part in (getattr(candidate, "content", None).parts or []):
                if part.inline_data is not None and part.inline_data.data:
                    raw = part.inline_data.data
                    image_bytes = self._coerce_image_bytes(raw)
                    if image_bytes:
                        return image_bytes
                # Defensive fallback: some model responses can surface image payload in text.
                if getattr(part, "text", None):
                    text_fallback_samples.append(str(part.text)[:180])
                    image_bytes = self._coerce_image_bytes(part.text)
                    if image_bytes:
                        return image_bytes

        if text_fallback_samples:
            logger.warning("Try-on response had text parts but no decodable image. Samples=%s", text_fallback_samples[:2])

        raise ValueError(
            "Vertex AI response did not contain a generated image. "
            "Check that the model supports image output and the prompt is valid."
        )

    def _coerce_image_bytes(self, raw) -> Optional[bytes]:
        """
        Accept multiple model output formats and convert to raw image bytes:
        - direct image bytes
        - base64 string
        - data:image/...;base64,... URI
        - JSON text containing image fields
        """
        if raw is None:
            return None

        if isinstance(raw, bytes):
            if self._has_image_magic(raw):
                return raw
            try:
                raw_text = raw.decode("utf-8", errors="ignore")
            except Exception:
                raw_text = ""
            decoded_from_text = self._coerce_image_bytes_from_text(raw_text)
            if decoded_from_text:
                return decoded_from_text
            decoded_b64 = self._decode_possible_base64(raw_text)
            if decoded_b64 and self._has_image_magic(decoded_b64):
                return decoded_b64
            return None

        if isinstance(raw, str):
            return self._coerce_image_bytes_from_text(raw)

        return None

    def _coerce_image_bytes_from_text(self, text_value: str) -> Optional[bytes]:
        text = (text_value or "").strip()
        if not text:
            return None

        # 1) data URI or plain base64 in the text
        decoded_direct = self._decode_possible_base64(text)
        if decoded_direct and self._has_image_magic(decoded_direct):
            return decoded_direct

        # 2) JSON wrapper: {"image":"..."} or {"image_base64":"..."}
        parsed_json = self._extract_json_object(text)
        if isinstance(parsed_json, dict):
            for key in ("image", "image_base64", "b64_json", "output_image"):
                candidate = parsed_json.get(key)
                if isinstance(candidate, str):
                    decoded = self._decode_possible_base64(candidate)
                    if decoded and self._has_image_magic(decoded):
                        return decoded

        # 3) markdown/codeblock with embedded data URI/base64
        data_uri_match = re.search(r"data:image/[a-zA-Z0-9.+-]+;base64,([A-Za-z0-9+/=\n\r]+)", text)
        if data_uri_match:
            decoded = self._decode_possible_base64(data_uri_match.group(1))
            if decoded and self._has_image_magic(decoded):
                return decoded

        return None

    def _extract_json_object(self, text: str):
        stripped = text.strip()
        if not stripped:
            return None
        try:
            return json.loads(stripped)
        except Exception:
            pass

        # Try extracting JSON inside markdown fences
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.DOTALL)
        if fenced:
            try:
                return json.loads(fenced.group(1))
            except Exception:
                return None
        return None

    def _decode_possible_base64(self, value: str) -> Optional[bytes]:
        text = (value or "").strip()
        if not text:
            return None
        if text.startswith("data:image/"):
            comma = text.find(",")
            if comma != -1:
                text = text[comma + 1 :]
        try:
            return base64.b64decode(text, validate=True)
        except (binascii.Error, ValueError):
            return None

    def _has_image_magic(self, blob: bytes) -> bool:
        if not blob or len(blob) < 8:
            return False
        return (
            blob.startswith(b"\xff\xd8\xff")
            or blob.startswith(b"\x89PNG\r\n\x1a\n")
            or blob.startswith(b"GIF87a")
            or blob.startswith(b"GIF89a")
            or (blob.startswith(b"RIFF") and blob[8:12] == b"WEBP")
        )

    def _normalize_image_bytes(self, image_bytes: bytes) -> bytes:
        """
        Ensure model output is a valid image and normalize to JPEG bytes for cache/storage.
        Raises ValueError if output is not decodable as an image.
        """
        try:
            img = Image.open(BytesIO(image_bytes))
            img.load()
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            output = BytesIO()
            img.save(output, format="JPEG", quality=92, optimize=True)
            return output.getvalue()
        except Exception as exc:
            preview = image_bytes[:120]
            logger.error("Try-on model output was not a valid image. First bytes=%r", preview)
            raise ValueError("Generated output is not a valid image") from exc

    def _detect_mime_type(self, image_bytes: bytes) -> str:
        if not image_bytes:
            return "image/jpeg"
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
            return "image/webp"
        return "image/jpeg"
