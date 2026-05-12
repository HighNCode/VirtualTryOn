"""Shared hardening helpers for image-generation providers."""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Callable, Dict, List, Optional, Tuple

import requests
from PIL import Image


class ImageEchoError(ValueError):
    """Raised when generated output appears to echo an input image."""


def build_tryon_prompt(product_title: str, category: str, strict: bool = False) -> str:
    category_hint = {
        "tops": "upper body garment",
        "bottoms": "lower body garment (pants/jeans)",
        "dresses": "full-body dress",
        "outerwear": "outer layer jacket/coat",
    }.get(category, "garment")

    base_prompt = (
        "Using the provided person photo and product photo, generate a single "
        f"photorealistic image of the person wearing the {product_title} ({category_hint}). "
        "Keep the person's face, body, pose, and background exactly the same. "
        "Keep the product's color, texture, and design exactly the same. "
        "Fit the product naturally on the person's body. "
        "The result should look like a real photograph, not a collage."
    )
    if strict:
        base_prompt += (
            " CRITICAL: Do not return the unchanged person image. "
            "The output must visibly include the provided product worn by the person."
        )
    return base_prompt


def download_and_validate_product_image(
    url: str,
    *,
    timeout_seconds: int,
    logger,
    min_width: int = 120,
    min_height: int = 120,
) -> bytes:
    resp = requests.get(url, timeout=timeout_seconds)
    resp.raise_for_status()
    image_bytes = resp.content

    content_type = (resp.headers.get("Content-Type", "") or "").lower()
    content_length = resp.headers.get("Content-Length")
    if content_type and not content_type.startswith("image/"):
        raise ValueError(
            f"TRYON_PRODUCT_IMAGE_INVALID: expected image content-type, got '{content_type}'"
        )

    width = None
    height = None
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            width, height = img.size
    except Exception as exc:
        raise ValueError("TRYON_PRODUCT_IMAGE_INVALID: downloaded payload is not a decodable image") from exc

    if not width or not height or width < min_width or height < min_height:
        raise ValueError(
            f"TRYON_PRODUCT_IMAGE_INVALID: product image too small ({width}x{height}), minimum is {min_width}x{min_height}"
        )

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


def compute_reference_hashes(
    person_image: bytes,
    product_image: bytes,
    normalize_fn: Callable[[bytes], bytes],
) -> Dict[str, object]:
    person_norm = normalize_fn(person_image)
    product_norm = normalize_fn(product_image)
    return {
        "person_sha": hashlib.sha256(person_norm).hexdigest(),
        "person_ahash": _average_hash(person_norm),
        "product_sha": hashlib.sha256(product_norm).hexdigest(),
        "product_ahash": _average_hash(product_norm),
    }


def select_best_non_echo_candidate(
    candidates: List[Tuple[bytes, str]],
    *,
    reference_hashes: Dict[str, object],
    normalize_fn: Callable[[bytes], bytes],
    logger,
) -> Tuple[bytes, str]:
    person_sha = reference_hashes.get("person_sha")
    person_ahash = reference_hashes.get("person_ahash")
    product_sha = reference_hashes.get("product_sha")
    product_ahash = reference_hashes.get("product_ahash")

    scored: List[Tuple[int, bytes, str]] = []
    echo_count = 0
    for raw_bytes, source in candidates:
        normalized = normalize_fn(raw_bytes)
        cand_sha = hashlib.sha256(normalized).hexdigest()
        cand_hash = _average_hash(normalized)

        same_as_person = cand_sha == person_sha
        if not same_as_person and person_ahash is not None and cand_hash is not None:
            same_as_person = _hamming_distance(cand_hash, person_ahash) <= 2

        same_as_product = cand_sha == product_sha
        if not same_as_product and product_ahash is not None and cand_hash is not None:
            same_as_product = _hamming_distance(cand_hash, product_ahash) <= 2

        if same_as_person or same_as_product:
            echo_count += 1
            logger.info(
                "echo_rejected event=tryon_candidate_rejected source=%s same_as_person=%s same_as_product=%s",
                source,
                same_as_person,
                same_as_product,
            )
            continue

        score = len(normalized)
        scored.append((score, normalized, source))

    if not scored:
        raise ImageEchoError(
            f"TRYON_OUTPUT_INVALID_OR_ECHO: all {len(candidates)} candidates matched input media (echo_count={echo_count})"
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    _, selected_bytes, selected_source = scored[0]
    return selected_bytes, selected_source


def _average_hash(image_bytes: bytes) -> Optional[int]:
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
            gray = img.convert("L").resize((8, 8), resample)
            pixels = list(gray.getdata())
        avg = sum(pixels) / len(pixels)
        bits = 0
        for idx, px in enumerate(pixels):
            if px >= avg:
                bits |= 1 << idx
        return bits
    except Exception:
        return None


def _hamming_distance(left: Optional[int], right: Optional[int]) -> int:
    if left is None or right is None:
        return 64
    return (left ^ right).bit_count()
