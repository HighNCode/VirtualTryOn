"""Gemini (Vertex AI) provider implementation."""

import base64
import binascii
import json
import logging
import os
import re
import time
from io import BytesIO
from typing import Optional

from google import genai
from google.genai import types
from PIL import Image

from app.config import Settings
from app.services.image_providers.base import ImageGenerationProvider

logger = logging.getLogger(__name__)


class GeminiProvider(ImageGenerationProvider):
    """Image-generation provider backed by Vertex AI Gemini."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._model = settings.TRYON_MODEL
        self._client = self._make_client()

    def generate_tryon(
        self,
        person_image: bytes,
        product_image_url: str,
        product_title: str,
        category: str,
    ) -> bytes:
        start = time.time()
        product_bytes = self._download_image(product_image_url)
        prompt = self._build_tryon_prompt(product_title, category)

        logger.info("Calling Vertex AI model=%s prompt_len=%s", self._model, len(prompt))

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
        logger.info("Try-on generation completed in %.1fs", time.time() - start)
        return result_image

    def generate_studio_tryon(
        self,
        tryon_image: bytes,
        studio_image: bytes,
    ) -> bytes:
        start = time.time()
        prompt = (
            "Place the person from the first image into the environment/background "
            "shown in the second image. Keep the person's appearance and clothing exactly the same from the first image. "
            "Change the background, lighting, objects and pose of the person to match "
            "the environment in the second image. The result should look like a natural professional photograph."
        )

        logger.info("Calling Vertex AI for studio look, model=%s", self._model)

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
        logger.info("Studio generation completed in %.1fs", time.time() - start)
        return result_image

    def generate_ghost_mannequin(
        self,
        image1_bytes: bytes,
        image2_bytes: bytes,
        clothing_type: Optional[str] = None,
    ) -> bytes:
        start = time.time()
        garment_hints = {
            "tops": "Pay special attention to the collar, neckline, and sleeve openings.",
            "bottoms": "Pay special attention to the waistband and leg openings.",
            "dresses": "Show the full length from neckline to hem.",
            "outerwear": "Show the collar, lapels, and front closure detail.",
        }
        garment_detail = garment_hints.get(clothing_type or "", "")

        prompt = (
            "You are given two photos of the same garment. "
            "Create a single professional ghost mannequin (invisible mannequin) product photo: "
            "the garment should appear as if worn by an invisible torso, showing the garment's "
            "full 3D shape, neckline, armholes, and bottom hem. "
            "Remove any visible model, mannequin, hanger, or background from the output. "
            "Use both images to construct the best possible result: if one shows the front and "
            "the other shows the back or inside, composite them to reveal interior collar lining "
            "or label detail. "
            f"{garment_detail} "
            "Output a clean, professional product photo on a white or light grey background."
        )

        logger.info(
            "GeminiProvider: ghost_mannequin clothing_type=%s, model=%s",
            clothing_type,
            self._model,
        )

        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=image1_bytes, mime_type=self._detect_mime_type(image1_bytes)),
                types.Part.from_bytes(data=image2_bytes, mime_type=self._detect_mime_type(image2_bytes)),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        result = self._extract_image(response)
        logger.info("ghost_mannequin completed in %.1fs", time.time() - start)
        return result

    def generate_try_on_model(
        self,
        product_image_bytes: bytes,
        model_image_bytes: bytes,
    ) -> bytes:
        start = time.time()
        prompt = (
            "You are given a garment/product photo and a photo of a model. "
            "Generate a single photorealistic image of the model wearing this exact garment. "
            "Keep the model's face, body, skin tone, hair, and pose exactly the same as in the model photo. "
            "Keep the garment's color, texture, pattern, and design details exactly the same as in the product photo. "
            "Fit the garment naturally on the model's body. "
            "The result should look like a professional fashion product photograph."
        )

        logger.info("GeminiProvider: try_on_model, model=%s", self._model)

        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=product_image_bytes, mime_type=self._detect_mime_type(product_image_bytes)),
                types.Part.from_bytes(data=model_image_bytes, mime_type=self._detect_mime_type(model_image_bytes)),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        result = self._extract_image(response)
        logger.info("try_on_model completed in %.1fs", time.time() - start)
        return result

    def generate_model_swap(
        self,
        original_wearing_bytes: bytes,
        face_bytes: bytes,
    ) -> bytes:
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

        logger.info("GeminiProvider: model_swap, model=%s", self._model)

        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(
                    data=original_wearing_bytes,
                    mime_type=self._detect_mime_type(original_wearing_bytes),
                ),
                types.Part.from_bytes(data=face_bytes, mime_type=self._detect_mime_type(face_bytes)),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        result = self._extract_image(response)
        logger.info("model_swap completed in %.1fs", time.time() - start)
        return result

    def _make_client(self) -> genai.Client:
        if not self._settings.GOOGLE_CLOUD_PROJECT:
            raise ValueError("GOOGLE_CLOUD_PROJECT is not configured")
        if self._settings.GOOGLE_APPLICATION_CREDENTIALS:
            os.environ.setdefault(
                "GOOGLE_APPLICATION_CREDENTIALS",
                self._settings.GOOGLE_APPLICATION_CREDENTIALS,
            )
        return genai.Client(
            vertexai=True,
            project=self._settings.GOOGLE_CLOUD_PROJECT,
            location=self._settings.GOOGLE_CLOUD_LOCATION,
        )

    def _build_tryon_prompt(self, product_title: str, category: str) -> str:
        category_hint = {
            "tops": "upper body garment",
            "bottoms": "lower body garment (pants/jeans)",
            "dresses": "full-body dress",
            "outerwear": "outer layer jacket/coat",
        }.get(category, "garment")

        return (
            "Using the provided person photo and product photo, generate a single "
            f"photorealistic image of the person wearing the {product_title} ({category_hint}). "
            "Keep the person's face, body, pose, and background exactly the same. "
            "Keep the product's color, texture, and design exactly the same. "
            "Fit the product naturally on the person's body. "
            "The result should look like a real photograph, not a collage."
        )

    def _download_image(self, url: str) -> bytes:
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
        text_fallback_samples = []
        for candidate in (response.candidates or []):
            for part in (getattr(candidate, "content", None).parts or []):
                if part.inline_data is not None and part.inline_data.data:
                    raw = part.inline_data.data
                    image_bytes = self._coerce_image_bytes(raw)
                    if image_bytes:
                        return image_bytes
                if getattr(part, "text", None):
                    text_fallback_samples.append(str(part.text)[:180])
                    image_bytes = self._coerce_image_bytes(part.text)
                    if image_bytes:
                        return image_bytes

        if text_fallback_samples:
            logger.warning(
                "Response had text parts but no decodable image. Samples=%s",
                text_fallback_samples[:2],
            )

        raise ValueError(
            "Vertex AI response did not contain a generated image. "
            "Check that the model supports image output and the prompt is valid."
        )

    def _coerce_image_bytes(self, raw) -> Optional[bytes]:
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

        decoded_direct = self._decode_possible_base64(text)
        if decoded_direct and self._has_image_magic(decoded_direct):
            return decoded_direct

        parsed_json = self._extract_json_object(text)
        if isinstance(parsed_json, dict):
            for key in ("image", "image_base64", "b64_json", "output_image"):
                candidate = parsed_json.get(key)
                if isinstance(candidate, str):
                    decoded = self._decode_possible_base64(candidate)
                    if decoded and self._has_image_magic(decoded):
                        return decoded

        data_uri_match = re.search(
            r"data:image/[a-zA-Z0-9.+-]+;base64,([A-Za-z0-9+/=\n\r]+)",
            text,
        )
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
