"""Seedream provider implementation via Volcengine Ark HTTP API."""

import base64
import binascii
import logging
from io import BytesIO
from typing import Any, Optional, Tuple

import requests
from PIL import Image

from app.config import Settings
from app.services.image_providers.base import ImageGenerationProvider
from app.services.image_providers.hardening import (
    ImageEchoError,
    build_tryon_prompt,
    compute_reference_hashes,
    download_and_validate_product_image,
    select_best_non_echo_candidate,
)

logger = logging.getLogger(__name__)


class SeedreamProvider(ImageGenerationProvider):
    """Image-generation provider backed by Ark /images/generations."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._model = settings.SEEDREAM_MODEL
        self._base_url = (settings.SEEDREAM_BASE_URL or "").rstrip("/")
        self._timeout = settings.SEEDREAM_TIMEOUT_SECONDS

    def generate_tryon(
        self,
        person_image: bytes,
        product_image_url: str,
        product_title: str,
        category: str,
    ) -> bytes:
        product_bytes = download_and_validate_product_image(
            product_image_url,
            timeout_seconds=self._timeout,
            logger=logger,
        )
        reference_hashes = compute_reference_hashes(
            person_image,
            product_bytes,
            normalize_fn=self._normalize_image_bytes,
        )

        prompt = build_tryon_prompt(product_title, category, strict=False)
        result, source = self._generate_image(
            prompt=prompt,
            image=[
                self._image_bytes_to_data_uri(person_image),
                self._image_bytes_to_data_uri(product_bytes),
            ],
        )
        try:
            selected, selected_source = select_best_non_echo_candidate(
                [(result, source)],
                reference_hashes=reference_hashes,
                normalize_fn=self._normalize_image_bytes,
                logger=logger,
            )
            logger.info(
                "Try-on candidate selection: total=%s selected_source=%s selected_bytes=%s",
                1,
                selected_source,
                len(selected),
            )
            return selected
        except ImageEchoError:
            retry_prompt = build_tryon_prompt(product_title, category, strict=True)
            logger.warning("retry_attempted event=tryon_echo_rejected reason=echo_output_detected")
            retry_result, retry_source = self._generate_image(
                prompt=retry_prompt,
                image=[
                    self._image_bytes_to_data_uri(person_image),
                    self._image_bytes_to_data_uri(product_bytes),
                ],
            )
            try:
                selected, selected_source = select_best_non_echo_candidate(
                    [(retry_result, retry_source)],
                    reference_hashes=reference_hashes,
                    normalize_fn=self._normalize_image_bytes,
                    logger=logger,
                )
                logger.info(
                    "Try-on candidate selection: total=%s selected_source=%s selected_bytes=%s",
                    1,
                    selected_source,
                    len(selected),
                )
                return selected
            except ImageEchoError as exc:
                raise ValueError("TRYON_OUTPUT_INVALID_OR_ECHO: model returned echoed input image") from exc

    def generate_studio_tryon(
        self,
        tryon_image: bytes,
        studio_image: bytes,
    ) -> bytes:
        prompt = (
            "Place the person from the first image into the environment/background "
            "shown in the second image. Keep the person's appearance and clothing exactly the same from the first image. "
            "Change the background, lighting, objects and pose of the person to match "
            "the environment in the second image. The result should look like a natural professional photograph."
        )
        result, _ = self._generate_image(
            prompt=prompt,
            image=[
                self._image_bytes_to_data_uri(tryon_image),
                self._image_bytes_to_data_uri(studio_image),
            ],
        )
        return self._normalize_image_bytes(result)

    def generate_ghost_mannequin(
        self,
        image1_bytes: bytes,
        image2_bytes: bytes,
        clothing_type: Optional[str] = None,
    ) -> bytes:
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
        result, _ = self._generate_image(
            prompt=prompt,
            image=[
                self._image_bytes_to_data_uri(image1_bytes),
                self._image_bytes_to_data_uri(image2_bytes),
            ],
        )
        return result

    def generate_try_on_model(
        self,
        product_image_bytes: bytes,
        model_image_bytes: bytes,
    ) -> bytes:
        prompt = (
            "You are given a garment/product photo and a photo of a model. "
            "Generate a single photorealistic image of the model wearing this exact garment. "
            "Keep the model's face, body, skin tone, hair, and pose exactly the same as in the model photo. "
            "Keep the garment's color, texture, pattern, and design details exactly the same as in the product photo. "
            "Fit the garment naturally on the model's body. "
            "The result should look like a professional fashion product photograph."
        )
        result, _ = self._generate_image(
            prompt=prompt,
            image=[
                self._image_bytes_to_data_uri(product_image_bytes),
                self._image_bytes_to_data_uri(model_image_bytes),
            ],
        )
        return result

    def generate_model_swap(
        self,
        original_wearing_bytes: bytes,
        face_bytes: bytes,
    ) -> bytes:
        prompt = (
            "The first image shows a model wearing a product. "
            "The second image shows a face. "
            "Replace the face of the model in the first image with the face shown in the second image. "
            "Keep everything else in the first image completely identical: "
            "the body, pose, clothing, background, and lighting must not change at all. "
            "Only the face region should be replaced. "
            "The result should look like a seamless, photorealistic professional fashion photograph."
        )
        result, _ = self._generate_image(
            prompt=prompt,
            image=[
                self._image_bytes_to_data_uri(original_wearing_bytes),
                self._image_bytes_to_data_uri(face_bytes),
            ],
        )
        return result

    def _generate_image(self, prompt: str, image: str | list[str]) -> Tuple[bytes, str]:
        if not self._settings.SEEDREAM_API_KEY:
            raise ValueError("SEEDREAM_API_KEY is not configured")
        if not self._model:
            raise ValueError("SEEDREAM_MODEL is not configured")
        if not self._base_url:
            raise ValueError("SEEDREAM_BASE_URL is not configured")

        endpoint = f"{self._base_url}/images/generations"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "image": image,
            "response_format": "b64_json",
            "sequential_image_generation": "disabled",
            "stream": False,
            "watermark": False,
        }
        headers = {
            "Authorization": f"Bearer {self._settings.SEEDREAM_API_KEY}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=self._timeout,
        )
        try:
            response.raise_for_status()
        except Exception as exc:
            body = response.text[:300] if response.text else ""
            raise RuntimeError(f"Seedream request failed ({response.status_code}): {body}") from exc

        try:
            response_json = response.json()
        except ValueError as exc:
            preview = response.text[:300] if response.text else ""
            raise RuntimeError(f"Seedream response was not valid JSON: {preview}") from exc

        self._validate_api_response(response_json)
        return self._extract_output_bytes(response_json)

    def _image_bytes_to_data_uri(self, image_bytes: bytes) -> str:
        mime_type = self._detect_mime_type(image_bytes)
        b64 = base64.b64encode(image_bytes).decode("ascii")
        return f"data:{mime_type};base64,{b64}"

    def _extract_output_bytes(self, response_json: dict[str, Any]) -> Tuple[bytes, str]:
        first = response_json["data"][0]

        b64_payload = first.get("b64_json")
        if isinstance(b64_payload, str) and b64_payload.strip():
            try:
                return base64.b64decode(b64_payload, validate=True), "b64_json"
            except (binascii.Error, ValueError) as exc:
                raise ValueError("Seedream b64_json output is invalid") from exc

        image_url = first.get("url")
        if isinstance(image_url, str) and image_url.strip():
            result = requests.get(image_url, timeout=self._timeout)
            try:
                result.raise_for_status()
            except Exception as exc:
                raise RuntimeError(
                    f"Seedream output URL download failed ({result.status_code}): {image_url}"
                ) from exc
            return result.content, "url"

        raise ValueError("Seedream response did not include b64_json or url output")

    def _validate_api_response(self, response_json: dict[str, Any]) -> None:
        if not isinstance(response_json, dict):
            raise ValueError("Seedream response has invalid shape")

        error = response_json.get("error")
        if isinstance(error, dict):
            code = str(error.get("code") or "").strip()
            message = str(error.get("message") or "").strip()
            if code or message:
                raise RuntimeError(f"Seedream API error [{code or 'unknown'}]: {message or 'no message'}")

        data = response_json.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError("Seedream response contains no generated image data")
        if not isinstance(data[0], dict):
            raise ValueError("Seedream response data item is malformed")

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
            logger.error("Seedream output was not a valid image. First bytes=%r", preview)
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
